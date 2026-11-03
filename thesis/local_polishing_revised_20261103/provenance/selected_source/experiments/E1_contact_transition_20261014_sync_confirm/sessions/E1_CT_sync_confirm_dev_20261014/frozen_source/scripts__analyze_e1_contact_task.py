#!/usr/bin/env python3
"""Measured-only E1 contact procedure analysis. Never imports ROS or publishes commands.

Receipt monotonic time, force ZOH, pose interpolation within supported intervals.
Historical replay is an explicitly separate cohort; it is not a height experiment.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'behavior_ws/src/nrs_imitation'))
from nrs_imitation.e1_contact_metrics import Signal, read_signal, read_events, event_stamp, segment
from nrs_imitation.e1_contact_task import evaluate_signals, normalize_config

EXPERIMENT = ROOT / 'experiments/E1_contact_transition_20261014'
REPORT = ROOT / 'reports/E1_contact_transition_20261014'
HEIGHTS = ('NOMINAL', 'HIGH', 'LOW')
METHODS = ('R', 'T', 'C')
UPPER = 30.812396273
LOWER_LEGACY = 0.449838867


def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def write_csv(path, rows, fields=()):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    keys = list(dict.fromkeys([*fields, *(k for row in rows for k in row)]))
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys); writer.writeheader()
        for row in rows:
            writer.writerow({k: '—' if row.get(k) is None else json.dumps(row[k], ensure_ascii=False)
                if isinstance(row[k], (dict, list, tuple)) else row[k] for k in keys})


def read_json(path, default=None):
    return json.loads(Path(path).read_text()) if Path(path).exists() else default


def load_config(path=None):
    path = Path(path or EXPERIMENT/'task_evaluation.json')
    if not path.exists():
        raise FileNotFoundError(f'Task evaluation config does not exist: {path}')
    if path.suffix in ('.yaml', '.yml'):
        import yaml
        value = yaml.safe_load(path.read_text())
    else: value = read_json(path)
    return normalize_config(value)


def executor_folder(run):
    folders = [run/'executor'] if (run/'executor/events.jsonl').exists() else sorted((run/'executor').glob('*'))
    valid = [p for p in folders if (p/'events.jsonl').exists()]
    if len(valid) > 1:
        raise ValueError(f'Multiple executor streams in {run}; do not pool independent executions')
    return valid[0] if valid else run/'executor'


def end_from_events(events, start_ns, pose, force):
    endings = []
    for e in events:
        t = event_stamp(e)
        if t is None or t < start_ns or e.get('details', {}).get('initial_reset'): continue
        if e.get('event') in ('stop_requested','trajectory_end','normal_completion','safety_stop','stop_failed',
                              'execution_timeout','run_timeout','manual_abort'):
            endings.append(e)
    endings.sort(key=event_stamp)
    if endings:
        e = endings[0]
        reason = e.get('details', {}).get('reason') or e.get('event')
        return (event_stamp(e)-start_ns)/1e9, reason, True, e
    last = max([float(s.time[-1]) for s in (pose,force) if len(s.time)] or [0.])
    return max(0., last), 'termination_event_missing', False, None


def force_integral(force, end_s, config):
    """Independent direct integration; no pose requirement, no tail extrapolation."""
    threshold = config.get('force_reference_upper_N', UPPER)
    observed = excess = above = 0.
    sample_mask=(force.time>=0)&(force.time<=end_s+1e-12)
    peak=float(np.max(force.value[sample_mask,-1])) if np.any(sample_mask) else None
    for i in range(max(0, len(force.time)-1)):
        a, b = max(0., float(force.time[i])), min(end_s, float(force.time[i+1]))
        if b <= a or force.break_before[i+1] or force.time[i+1]-force.time[i] > config['max_gap_s']+1e-12: continue
        f = float(force.value[i,-1]); dt = b-a
        observed += dt; excess += max(f-threshold, 0.)*dt; above += dt*(f>threshold)
        peak = f if peak is None else max(peak, f)
    missing = max(0., end_s-observed)
    complete = missing <= 1e-8
    return dict(J_excess_Ns=excess if complete else None, J_excess_observed_lower_bound_Ns=excess,
        force_observed_duration_s=observed, force_unobserved_duration_s=missing,
        force_integral_complete=complete, peak_Fz_base_N=peak, force_excess_duration_s=above,
        force_excess_time_is_partial=not complete)


def legacy_dwell(pose, force, end_s, config):
    """Separate old per-bin cumulative dwell diagnostic; never controls the task evaluator."""
    p0, p1 = np.asarray(config['endpoints_base_mm'])[:, :2]
    length = float(np.linalg.norm(p1-p0)); u = (p1-p0)/length; v = np.array([-u[1],u[0]])
    n = int(config['segment_count']); edges = np.linspace(0.,length,n+1)
    xy_dwell = np.zeros(n); qualified = np.zeros(n)
    half = config['half_width_mm']; max_gap = config['max_gap_s']
    times = sorted(set([0.,end_s,*pose.time[(pose.time>0)&(pose.time<end_s)],*force.time[(force.time>0)&(force.time<end_s)]]))
    for a,b in zip(times[:-1],times[1:]):
        ip = segment(pose,(a+b)/2,max_gap)
        if ip is None or b<=a: continue
        t0,t1=pose.time[ip:ip+2]; x0,x1=pose.value[ip:ip+2,:3]
        pa=x0+(a-t0)/(t1-t0)*(x1-x0); pb=x0+(b-t0)/(t1-t0)*(x1-x0)
        sa,da=(pa[:2]-p0)@u,(pa[:2]-p0)@v; sb,db=(pb[:2]-p0)@u,(pb[:2]-p0)@v
        cuts=[a,b]
        for va,vb,bd in [*( (sa,sb,e) for e in edges), (da,db,-half),(da,db,half)]:
            if abs(vb-va)>1e-12:
                q=(bd-va)/(vb-va)
                if 0<q<1: cuts.append(a+q*(b-a))
        cuts=sorted(set(cuts)); jf=segment(force,(a+b)/2,max_gap)
        fz=float(force.value[jf,-1]) if jf is not None else None
        for c,d in zip(cuts[:-1],cuts[1:]):
            q=((c+d)/2-a)/(b-a); s=sa+q*(sb-sa); cross=da+q*(db-da)
            if not (0<=s<=length and abs(cross)<=half+1e-10): continue
            j=min(int(np.searchsorted(edges,s,side='right')-1),n-1)
            if j<0: continue
            xy_dwell[j]+=d-c
            if fz is not None and LOWER_LEGACY<=fz<=config['force_reference_upper_N']:qualified[j]+=d-c
    required=length/n/10.
    rows=[dict(segment_index=i, s_start_mm=edges[i],s_end_mm=edges[i+1],legacy_required_s=required,
        xy_dwell_s=float(xy_dwell[i]), range_qualified_dwell_s=float(qualified[i]),
        xy_dwell_fulfilled=bool(xy_dwell[i]>=required-1e-10),
        legacy_range_qualified_fulfilled=bool(qualified[i]>=required-1e-10),
        legacy_only=True, legacy_lower_N=LOWER_LEGACY,legacy_upper_N=config['force_reference_upper_N']) for i in range(n)]
    return rows


def analyze_run(run, config, identity=None):
    run=Path(run); context=read_json(run/'run_context.json',{})
    execution=read_json(run/'execution_config.json',{})
    identity=identity or {}; task_context=execution.get('e1_contact_task',{})
    base={**task_context,**context,**identity}
    base.update(run_id=base.get('run_id',run.name), method=base.get('method',base.get('condition')),
        height_condition=base.get('height_condition','unknown'), stage=base.get('stage','development'),
        session_id=base.get('session_id',base.get('session','unknown')),run_directory=str(run),attempted=True)
    # Individual executions always use their frozen evaluation snapshot where available.
    own=run/'task_evaluation.json'
    frozen_path=base.get('task_evaluation_file')
    if base['stage']!='historical':
        if own.exists():config=load_config(own)
        elif frozen_path:
            frozen=Path(frozen_path)
            if not frozen.is_absolute():frozen=run/frozen
            config=load_config(frozen)
    base['evaluation_config_sha256']=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
    executor=executor_folder(run); events=read_events(executor/'events.jsonl')
    starts=[e for e in events if e.get('event')=='execution_start' and event_stamp(e) is not None]
    starts.sort(key=event_stamp)
    if not starts:
        base.update(started=False,completed=None,outcome='not_started',completion_time_s=None,J_excess_Ns=None,
            failure_stage=None,stop_reason='execution_start_missing',observation_status='not_started')
        return base,dict(events=events,pose=Signal.synthetic([],np.empty((0,6))),force=Signal.synthetic([],np.empty((0,3)))),[]
    if len(starts)>1:raise ValueError(f'Multiple execution_start events in {run}; separate independent execution attempts')
    start_ns=event_stamp(starts[0]); force=read_signal(executor/'wrench.csv',['fx','fy','fz'],start_ns,'force')
    pose=read_signal(executor/'tcp_pose.csv',['x','y','z','rx','ry','rz'],start_ns,'pose')
    end,stop_reason,known_ending,ending=end_from_events(events,start_ns,pose,force)
    result=evaluate_signals(pose,force,0.,end,config,stop_reason=stop_reason)
    primary_end=float(result.get('completion_at_s')) if result.get('completed') else end
    independent=force_integral(force,primary_end,config)
    if result.get('J_excess_Ns') is not None and independent['J_excess_Ns'] is not None:
        if abs(result['J_excess_Ns']-independent['J_excess_Ns'])>1e-7:raise AssertionError('Evaluator/direct force integration disagree')
    base.update(result); base.update(independent)
    base.update(started=True,execution_start_monotonic_ns=start_ns,evaluation_end_s=primary_end,
        observed_stop_after_s=end,termination_event_known=known_ending,
        first_stop_event=ending.get('event') if ending else None,
        original_stop_reason=stop_reason,final_recorded_stop_reason=next((e.get('details',{}).get('reason',e.get('event'))
            for e in reversed(events) if e.get('event') in ('stop_requested','safety_stop','stop_failed','normal_completion')),None),
        recovery_events=[dict(time_s=(event_stamp(e)-start_ns)/1e9,event=e.get('event'),details=e.get('details')) for e in events
            if event_stamp(e) is not None and (event_stamp(e)-start_ns)/1e9>end and any(k in e.get('event','') for k in ('retract','return','home','stop_failed','safety_stop'))],
        invalid_tcp_rows=pose.invalid_rows,invalid_force_rows=force.invalid_rows,
        actual_execution_to_stop_s=end,
        actual_stop_after_task_complete_s=end-primary_end if result.get('completed') else None,
        failure_stage=result.get('phase') if not result.get('completed') and result.get('outcome')=='incomplete' else None,
        observation_status=result.get('outcome'),force_semantics='logged robot_base N; no rotation/re-zero/re-gravity',
        criteria_scope='operational contact procedure; not material removal or independent physical calibration')
    if not known_ending and not base.get('completed'):
        base.update(outcome='observation_unavailable',observation_status='termination_event_missing',completed=None,failure_stage=None)
    elif base.get('outcome')=='observation_unavailable':base['completed']=None
    for key in ('contact_at_s','pass_completed_at_s','release_at_s'):
        if base.get(key) is not None:base[key.replace('_at_s','_from_execution_s')]=float(base[key])
    base['contact_to_complete_s']=base['completion_time_s']-base['contact_at_s'] if base.get('completed') and base.get('contact_at_s') is not None else None
    dwell=legacy_dwell(pose,force,primary_end,config)
    base['legacy_xy_dwell_coverage_percent']=100*sum(r['xy_dwell_fulfilled'] for r in dwell)/config['segment_count']
    base['legacy_range_qualified_coverage_percent']=100*sum(r['legacy_range_qualified_fulfilled'] for r in dwell)/config['segment_count']
    return base,dict(events=events,pose=pose,force=force,start_ns=start_ns,end_s=primary_end,stop_s=end,config=config),dwell


def gate_records(executor, raw_events, evaluation_events, start_ns, end_s):
    """Preserve independent and pre-existing gate provenance without conflating axes."""
    rows=[]
    for e in evaluation_events:
        if e.get('event')=='contact_gate':
            rows.append(dict(time_s=e.get('time_s'),source='offline_recomputed_base_Fz_gate',contact=e.get('contact'),
                force_frame='robot_base',detail=e,scope='evaluation'))
    commands=executor/'commands.csv';last=None
    if commands.exists():
        with commands.open() as stream:
            for row in csv.DictReader(stream):
                if row.get('command_stage')!='time_sampled':continue
                try:
                    detail=json.loads(row.get('details') or '{}');t=(int(row['receipt_monotonic_ns'])-start_ns)/1e9
                except (ValueError,KeyError,TypeError,json.JSONDecodeError):continue
                contact=detail.get('contact')
                if contact is None or contact==last:continue
                last=contact
                rows.append(dict(time_s=t,source='existing_executor_gate',contact=contact,force_frame='robot_base',detail=detail,
                    scope='pre_execution' if t<0 else 'evaluation' if t<=end_s else 'post_evaluation'))
    for e in raw_events:
        if e.get('event')!='controller_contact_transition' or event_stamp(e) is None:continue
        detail=e.get('details',{});raw=detail.get('raw_values');fields=detail.get('field_order',[])
        if raw is not None and 'contact' in fields:
            index=fields.index('contact')
            if index<len(raw):
                t=(event_stamp(e)-start_ns)/1e9
                rows.append(dict(time_s=t,source='existing_lower_controller_transition',contact=bool(raw[index]),
                    force_frame='controller native normal; separate diagnostic',detail=detail,
                    scope='pre_execution' if t<0 else 'evaluation' if t<=end_s else 'post_evaluation'))
    return sorted(rows,key=lambda r:r['time_s'])


def _stats(values):
    values=[float(v) for v in values if v is not None and math.isfinite(float(v))]
    return (float(np.mean(values)) if values else None,float(np.std(values,ddof=1)) if len(values)>1 else None,len(values))


def summaries(rows, plan=None, force_all_groups=True):
    groups=defaultdict(list)
    for r in rows:groups[(r.get('stage','development'),r.get('height_condition'),r.get('method'))].append(r)
    stages=sorted({r.get('stage','development') for r in rows}|{r.get('stage','development') for r in (plan or [])}) or ['development']
    if force_all_groups:
        for stage in stages:
            if stage in ('development','main'):
                for h in HEIGHTS:
                    for m in METHODS:groups.setdefault((stage,h,m),[])
    output=[]
    for (stage,h,m),values in sorted(groups.items()):
        attempted=sum(r.get('attempted') is True for r in values)
        started=[r for r in values if r.get('started') is True]
        completed=[r for r in started if r.get('completed') is True]
        unknown=[r for r in started if r.get('outcome')=='observation_unavailable']
        tm,ts,tn=_stats([r.get('completion_time_s') for r in completed]); jm,js,jn=_stats([r.get('J_excess_Ns') for r in started])
        planned=sum(r.get('height_condition')==h and r.get('method')==m and r.get('stage',stage)==stage for r in (plan or []))
        output.append(dict(stage=stage,height_condition=h,method=m,planned=planned,
            attempted=attempted,started=len(started),completed=len(completed),
            observation_unavailable=len(unknown),not_started=attempted-len(started),
            completion_rate=len(completed)/len(started) if started else None,
            completion_rate_interpretation='observed completed / all started; unresolved observations separately shown' if unknown else 'completed / started',
            completion_time_mean_s=tm,completion_time_std_s=ts,completion_time_n=tn,
            J_excess_mean_Ns=jm,J_excess_std_Ns=js,J_excess_n=jn,
            failure_counts=dict(Counter(r.get('failure_stage') or r.get('phase','unknown') for r in started if r.get('outcome')=='incomplete')),
            status='not_run' if not attempted else 'observation_unavailable' if unknown else 'analyzed',
            height_change_physically_documented_started=sum(r.get('physical_height_condition_confirmed') is True for r in started),
            height_setup_unconfirmed_started=sum(r.get('physical_height_condition_confirmed') is not True for r in started),
            completed_time_scope='completed runs only; always show completed/started'))
    return output


def condition_comparisons(summary):
    lookup={(r['stage'],r['height_condition'],r['method']):r for r in summary};out=[]
    for stage in sorted({r['stage'] for r in summary if r['stage'] in ('development','main')}):
        for m in METHODS:
            nominal=lookup.get((stage,'NOMINAL',m),{})
            for h in ('HIGH','LOW'):
                changed=lookup.get((stage,h,m),{});a=nominal.get('completion_rate');b=changed.get('completion_rate')
                valid=a is not None and b is not None and not nominal.get('observation_unavailable') and not changed.get('observation_unavailable') and not nominal.get('height_setup_unconfirmed_started') and not changed.get('height_setup_unconfirmed_started')
                out.append(dict(stage=stage,method=m,height_condition=h,nominal_started=nominal.get('started',0),changed_started=changed.get('started',0),
                    completion_rate_difference_from_nominal=b-a if valid else None,
                    interpretation='height comparison unavailable until observations and physical setup records support both conditions' if not valid else 'changed minus NOMINAL; physical setup is operator documented, not Codex measured'))
    return out


def plot_run(output,row,trace):
    os.environ.setdefault('MPLCONFIGDIR',str(output/'.matplotlib'))
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    pose,force=trace['pose'],trace['force'];config=trace.get('config')
    if not len(pose.time) and not len(force.time):return
    folder=output/'figures/runs';folder.mkdir(parents=True,exist_ok=True)
    fig,axes=plt.subplots(4,1,figsize=(10,11),sharex=True)
    if len(force.time):
        f=force.value[:,-1].copy()
        f[:-1][(np.diff(force.time)>config['max_gap_s'])|force.break_before[1:]]=np.nan
        axes[0].step(force.time,f,where='post',label='measured base Fz',color='#b14b3f')
        for level,label in [(config['force_reference_upper_N'],'Q95 reference'),(3,'contact ON'),(1.2,'contact OFF')]:axes[0].axhline(level,ls='--',lw=.7,label=label)
    if len(pose.time):
        xyz=pose.value[:,:3].copy();xyz[:-1][(np.diff(pose.time)>config['max_gap_s'])|pose.break_before[1:]]=np.nan
        p0,p1=np.asarray(config['endpoints_base_mm'])[:,:2];u=(p1-p0)/np.linalg.norm(p1-p0);v=np.array([-u[1],u[0]])
        s=(xyz[:,:2]-p0)@u;d=(xyz[:,:2]-p0)@v
        axes[1].plot(pose.time,s,label='along-line s');axes[1].plot(pose.time,d,label='cross-line d')
        for e in np.linspace(0,np.linalg.norm(p1-p0),config['segment_count']+1):axes[1].axhline(e,color='gray',lw=.4,alpha=.4)
        for e in (-config['half_width_mm'],config['half_width_mm']):axes[1].axhline(e,color='#af7b15',ls='--')
        axes[2].plot(pose.time,xyz[:,2],label='measured TCP Z')
        if row.get('z_contact_ref_mm') is not None:axes[2].axhline(row['z_contact_ref_mm']+config['release_rise_mm'],ls='--',label='contact-relative rise')
    phases={'WAIT_CONTACT':0,'CONTACT_OBSERVED':1,'REQUIRED_PASS_OBSERVED':2,'RELEASE_OBSERVED':3,'TASK_COMPLETED':4}
    times=[0.];states=[0]
    for event in row.get('events',[]):
        when=event.get('time_s',event.get('at_s'));phase=event.get('phase',event.get('state'))
        if when is not None and phase in phases:times.append(when);states.append(phases[phase])
    if len(times)==1:
        for key,phase in [('contact_at_s','CONTACT_OBSERVED'),('pass_completed_at_s','REQUIRED_PASS_OBSERVED'),('release_at_s','RELEASE_OBSERVED'),('completion_at_s','TASK_COMPLETED')]:
            if row.get(key) is not None:times.append(row[key]);states.append(phases[phase])
    order=np.argsort(times);axes[3].step(np.asarray(times)[order],np.asarray(states)[order],where='post')
    axes[3].set(yticks=list(phases.values()),yticklabels=list(phases),xlabel='Seconds from execution_start')
    for ax in axes:
        ax.axvline(trace['end_s'],color='black',ls=':',label='evaluation end');ax.set_xlim(0,max(trace['stop_s'],trace['end_s'])+.1);ax.grid(alpha=.2)
    axes[0].set_ylabel('N');axes[1].set_ylabel('mm');axes[2].set_ylabel('Z (mm)')
    for ax in axes[:3]:ax.legend(loc='best',fontsize=7)
    fig.suptitle(f"{row['run_id']} | {row['outcome']} | stop: {row['original_stop_reason']}\noperational task observation; recovery after first stop excluded",fontsize=10)
    fig.tight_layout();fig.savefig(folder/(row['run_id']+'.png'));plt.close(fig)


def plot_groups(output,summary,rows):
    os.environ.setdefault('MPLCONFIGDIR',str(output/'.matplotlib'))
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    folder=output/'figures';folder.mkdir(parents=True,exist_ok=True)
    stages=sorted({r['stage'] for r in summary})
    for stage in stages:
        values=[r for r in summary if r['stage']==stage];fig,axes=plt.subplots(1,3,figsize=(15,5))
        labels=[r['height_condition']+'\n'+str(r['method']) for r in values];x=np.arange(len(values))
        for i,r in enumerate(values):
            if r['completion_rate'] is None:axes[0].text(i,.03,'not_run',ha='center',rotation=90,fontsize=8)
            else:axes[0].bar(i,r['completion_rate'],color={'R':'#bd5e28','T':'#3983b9','C':'#359869'}.get(r['method'],'gray'));axes[0].text(i,min(1.05,r['completion_rate']+.04),f"{r['completed']}/{r['started']}",ha='center',fontsize=8)
            matching=[z for z in rows if z.get('stage')==stage and z.get('height_condition')==r['height_condition'] and z.get('method')==r['method']]
            for j,(metric,title) in enumerate([('completion_time_s','Completed-run task time (s)'),('J_excess_Ns','All-started excess integral (N s)')],1):
                samples=[z[metric] for z in matching if z.get(metric) is not None and (metric!='completion_time_s' or z.get('completed') is True)]
                if samples:axes[j].scatter([i]*len(samples),samples,s=20);mean,sd,n=_stats(samples);axes[j].errorbar(i,mean,yerr=sd if sd is not None else 0,color='black',fmt='_')
                else:axes[j].text(i,.03,'not_run' if not matching else 'NA',transform=axes[j].get_xaxis_transform(),rotation=90,ha='center',fontsize=8)
                axes[j].set_title(title)
        axes[0].set(title='Observed contact-task completion',ylim=(0,1.12),ylabel='Completed / started')
        for ax in axes:ax.set_xticks(x,labels,fontsize=8);ax.grid(axis='y',alpha=.2)
        fig.suptitle(stage+'; task completion is not a material-removal measurement')
        fig.tight_layout();fig.savefig(folder/('group_metrics_'+stage+'.png'));plt.close(fig)


def calculate(records,output,config,plan=None,plot=True):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);rows=[];dwells=[]
    for run,identity in records:
        row,trace,dwell=analyze_run(run,config,identity);rows.append(row)
        per=output/'runs'/row['run_id'];per.mkdir(parents=True,exist_ok=True)
        write_json(per/'outcome.json',row);write_csv(per/'stage_events.csv',row.get('events',[]),('time_s','event','phase'))
        write_csv(per/'pass_candidates.csv',row.get('pass_candidates',[]),('start_s','end_s','direction','segments','end_reason'))
        write_csv(per/'legacy_segment_dwell.csv',dwell,('segment_index','xy_dwell_s','range_qualified_dwell_s','legacy_only'))
        timeline=[]
        if trace.get('start_ns') is not None:
            for e in trace['events']:
                stamp=event_stamp(e)
                if stamp is None:continue
                t=(stamp-trace['start_ns'])/1e9
                timeline.append(dict(time_s=t,event=e.get('event'),scope='before_execution' if t<0 else 'evaluation' if t<=trace['end_s'] else 'after_completion' if t<=trace['stop_s'] else 'post_first_stop_recovery',details=e.get('details')))
        write_csv(per/'raw_event_timeline.csv',timeline,('time_s','event','scope','details'))
        gates=gate_records(executor_folder(Path(run)),trace['events'],row.get('events',[]),trace['start_ns'],trace['end_s']) if trace.get('start_ns') is not None else []
        write_csv(per/'contact_gate_provenance.csv',gates,('time_s','source','contact','force_frame','scope','detail'))
        dwells.extend(dict(run_id=row['run_id'],**r) for r in dwell)
        if plot:plot_run(output,row,trace)
    report=summaries(rows,plan,force_all_groups=True)
    if plan is not None:
        plan_status=[]
        for planned in plan:
            linked=[r for r in rows if str(r.get('plan_index'))==str(planned.get('plan_index')) and r.get('height_condition')==planned.get('height_condition') and r.get('method')==planned.get('method')]
            plan_status.append(dict(**planned,status='not_run' if not linked else 'attempted',run_ids=[r['run_id'] for r in linked],
                attempted=len(linked),started=sum(r.get('started') is True for r in linked),completed=sum(r.get('completed') is True for r in linked),
                completion_time_s=None if not linked else [r.get('completion_time_s') for r in linked],measurement_values_generated=False))
        write_csv(output/'planned_trial_status.csv',plan_status,('plan_index','height_condition','method','status','run_ids','attempted','started','completed','completion_time_s'))
    write_csv(output/'metrics_per_run.csv',rows,('height_condition','method','run_id','attempted','started','completed','outcome','completion_time_s','J_excess_Ns'))
    write_json(output/'outcomes.json',rows)
    write_csv(output/'condition_summary.csv',report,('height_condition','method','attempted','started','completed','completion_rate','completion_time_mean_s','completion_time_std_s','completion_time_n','J_excess_mean_Ns','J_excess_std_Ns','J_excess_n','failure_counts'))
    write_csv(output/'condition_comparison.csv',condition_comparisons(report),('stage','method','height_condition','completion_rate_difference_from_nominal'))
    write_csv(output/'legacy_segment_dwell.csv',dwells,('run_id','segment_index','xy_dwell_s','range_qualified_dwell_s','legacy_only'))
    write_json(output/'analysis_metadata.json',dict(schema='e1_contact_task_analysis_v1',config=config,
        config_sha256=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest(),
        attempts=len(rows),started=sum(r.get('started') is True for r in rows),
        historical_is_excluded_from_height_trials=all(r.get('stage')=='historical' for r in rows) if rows else False,
        reference_upper_is_analysis_only=True,pose_source='measured TCP robot_base mm',force_source='measured base Fz N, no repeated correction',
        force_interpolation='ZOH within recorded bounds',position_interpolation='linear within recorded bounds',max_gap_s=config['max_gap_s'],
        outcome_is_operational_procedure_not_removal=True,completion_time_is_completed_only=True,
        legacy_dwell_is_not_primary_completion=True,planned_trials_are_not_executed_measurements=True))
    if plot:plot_groups(output,report,rows)
    return rows,report


def historical_records():
    inventory=ROOT/'reports/20261013_E1_pdf_report/current_block_analysis/run_inventory.csv'
    with inventory.open(encoding='utf-8-sig') as stream:rows=list(csv.DictReader(stream))
    if len(rows)!=17 or {r['block_id'] for r in rows}!={'b_d1bf512f345f'}:raise ValueError('Historical inventory does not match the fixed current block')
    return [(Path(r['run_directory']),dict(run_id=r['run_id'],method=r['condition'],height_condition='historical_not_height_trial',stage='historical',
        repeat_index=int(r['repeat_index']),execution_order=int(r['execution_order']),session_id='20261013_b_d1bf512f345f',
        retry_of=None if r.get('retry_of') in ('NA','',None) else r['retry_of'],historical_replay_only=True)) for r in rows]


def session_records(session):
    session=Path(session).resolve()
    # A configuration session and a results session can be supplied independently.
    manifest=read_json(session/'session.json',{})
    sid=manifest.get('session_id',session.name)
    plan_path=next((p for p in (session/'trial_plan.csv',session/'plan.csv',EXPERIMENT/'sessions'/sid/'trial_plan.csv',EXPERIMENT/'trial_plan.csv') if p.exists()),None)
    with plan_path.open(encoding='utf-8-sig') as stream:plan=list(csv.DictReader(stream))
    stage=manifest.get('stage','development')
    for r in plan:r.setdefault('stage',stage)
    roots=[session]
    roots.extend(p for p in (ROOT/'results').glob('*/E1_contact_transition/'+sid) if p!=session)
    runs={p.parent.resolve() for folder in roots for p in folder.glob('**/run_context.json')}
    records=[]
    for p in sorted(runs):
        context=read_json(p/'run_context.json',{})
        if context.get('session_id',context.get('session',sid))==sid:records.append((p,context))
    return records,plan,sid


def synthetic_records(folder, config):
    """Clearly labeled synthetic logger fixtures, never physical experiment results."""
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    a,b=np.asarray(config['endpoints_base_mm']);delta=b-a
    transverse=np.r_[np.array([-delta[1],delta[0]])/np.linalg.norm(delta[:2]),0.]
    cases=['complete_forward','complete_reverse','excess_does_not_stop','unloaded_path','partial_path','contact_loss','width_loss',
        'off_without_rise','rise_without_off','early_release','recovery_after_abort','observation_gap']
    records=[]
    for case in cases:
        run=folder/case;executor=run/'executor';executor.mkdir(parents=True,exist_ok=True)
        times=np.round(np.arange(0.,3.051,.05),8)
        if case=='observation_gap':times=times[~((times>1.25)&(times<1.75))]
        pose=[];force=[]
        start,finish=(b,a) if case=='complete_reverse' else (a,b)
        for t in times:
            progress=np.clip((t-.6)/1.6,0.,1.)
            if case=='partial_path':progress*=.5
            xyz=start+progress*(finish-start);fz=0. if t<.3 else 18.
            if t<.3:xyz=xyz+np.array([0.,0.,6.])
            if t>=2.4:
                fz=0.;xyz=xyz+np.array([0.,0.,6.*min(1.,(t-2.4)/.2)])
            if case=='unloaded_path':fz=0.
            if case=='excess_does_not_stop' and .8<=t<1.4:fz=config['force_reference_upper_N']+12.
            if case=='contact_loss' and 1.25<=t<1.5:fz=0.
            if case=='width_loss' and 1.25<=t<1.5:xyz=xyz+18*transverse
            if case=='off_without_rise' and t>=2.4:xyz[2]=start[2]
            if case=='rise_without_off' and t>=2.4:fz=18.
            if case=='early_release' and t>=1.35:
                fz=0.;xyz=xyz+np.array([0.,0.,6.])
            pose.append([*xyz,0.,0.,0.]);force.append([0.,0.,fz])
        start_ns=1_000_000_000
        for name,fields,values in [('tcp_pose.csv',['x','y','z','rx','ry','rz'],pose),('wrench.csv',['fx','fy','fz'],force)]:
            with (executor/name).open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=['receipt_monotonic_ns',*fields]);writer.writeheader()
                for t,value in zip(times,values):writer.writerow(dict(receipt_monotonic_ns=start_ns+round(t*1e9),**dict(zip(fields,value))))
        cutoff=2.3 if case=='recovery_after_abort' else 3.
        events=[dict(event='execution_start',receipt_monotonic_ns=start_ns,details={'synthetic':True}),
                dict(event='stop_requested',receipt_monotonic_ns=start_ns+round(cutoff*1e9),details={'reason':'manual_abort' if case=='recovery_after_abort' else 'trajectory_end','synthetic':True})]
        if case=='recovery_after_abort':events.append(dict(event='return_retract_done',receipt_monotonic_ns=start_ns+3_000_000_000,details={'synthetic':True}))
        (executor/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
        identity=dict(run_id=case,method='fixture',height_condition='synthetic_not_height_trial',stage='synthetic',
            session_id='synthetic_logger_fixtures',synthetic=True,physical_height_condition_confirmed=False)
        write_json(run/'run_context.json',identity);write_json(run/'task_evaluation.json',config)
        records.append((run,identity))
    return records


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    select=parser.add_mutually_exclusive_group(required=True)
    select.add_argument('--run-directory',type=Path);select.add_argument('--session',type=Path)
    select.add_argument('--replay-20261013',action='store_true');select.add_argument('--plan-only',action='store_true')
    select.add_argument('--synthetic-examples',action='store_true')
    parser.add_argument('--config',type=Path);parser.add_argument('--output',type=Path);parser.add_argument('--no-plots',action='store_true')
    args=parser.parse_args(argv);config=load_config(args.config);plan=None
    if args.synthetic_examples:
        output=args.output or REPORT/'synthetic_validation'
        records=synthetic_records(output/'synthetic_signals',config)
    elif args.replay_20261013:records=historical_records();output=args.output or REPORT/'historical_replay_20261013'
    elif args.plan_only:
        with (EXPERIMENT/'trial_plan.csv').open(encoding='utf-8-sig') as stream:plan=list(csv.DictReader(stream))
        records=[];output=args.output or REPORT/'planned_not_run'
    elif args.run_directory:records=[(args.run_directory,None)];output=args.output or args.run_directory/'task_analysis'
    else:records,plan,sid=session_records(args.session);output=args.output or REPORT/'sessions'/sid
    rows,summary=calculate(records,output,config,plan,not args.no_plots)
    if args.synthetic_examples:
        expected={r['run_id']: ('completed' if r['run_id'] in ('complete_forward','complete_reverse','excess_does_not_stop') else 'observation_unavailable' if r['run_id']=='observation_gap' else 'incomplete') for r in rows}
        checks=[dict(case=r['run_id'],expected=expected[r['run_id']],observed=r['outcome'],passed=r['outcome']==expected[r['run_id']]) for r in rows]
        write_json(output/'validation.json',dict(synthetic=True,never_a_physical_trial=True,checks=checks,all_passed=all(c['passed'] for c in checks)))
        if not all(c['passed'] for c in checks):raise AssertionError('Synthetic logger replay case failed')
    print(json.dumps(dict(output=str(output),attempted=len(rows),started=sum(r.get('started') is True for r in rows),completed=sum(r.get('completed') is True for r in rows),summary_groups=len(summary)),ensure_ascii=False))


if __name__=='__main__':main()
