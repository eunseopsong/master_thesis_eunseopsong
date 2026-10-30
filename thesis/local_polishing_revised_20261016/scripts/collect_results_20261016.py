#!/usr/bin/env python3
"""Read existing E1/E2 evidence; write compact thesis-only extracts.

Primary E1 membership comes from the report's frozen run-id inventory, never
from the subsequently extended session list. No ROS or model code is imported.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import numpy as np
import pandas as pd

P = Path(__file__).resolve().parents[1]
UPPER = 30.812396273
SESSION = 'E1_CT_pass_height_v2_nominal_dev_20261015'
C6_ID = 'E1_CT_NOMINAL_C_r5_20261015T233551_9021584d0a'
REPORT = 'reports/20261015_E1_nominal_pass_height_v2_pdf_report'
FILES = {}


def js(path):
    path = Path(path)
    blob = path.read_bytes()
    FILES[str(path)] = {'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob)}
    return json.loads(blob)


def record(path):
    path = Path(path)
    blob = path.read_bytes()
    FILES[str(path)] = {'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob)}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def received_signals(event_path, result):
    """Extract original receipt events and re-integrate the existing force metric.

    Completion and height-reference recognition are reused from the archived
    evaluation, checked against its original online outcome snapshot. Their
    state machine and median calculation are not rerun or changed here.
    """
    signals = {'wrench': [], 'tcp_pose': []}
    starts, snapshots, stops = [], [], []
    digest = hashlib.sha256()
    with event_path.open('rb') as stream:
        for line in stream:
            digest.update(line)
            if not any(token in line for token in [b'"task_observation_received"',
                        b'"execution_start"', b'"task_outcome_snapshot"', b'"stop_requested"']):
                continue
            event = json.loads(line)
            kind = event.get('event')
            if kind == 'task_observation_received':
                detail = event['details']
                signals[detail['stream']].append(detail['row'])
            elif kind == 'execution_start':
                starts.append(event)
            elif kind == 'task_outcome_snapshot':
                snapshots.append(event['details']['result'])
            elif kind == 'stop_requested' and not event['details'].get('initial_reset'):
                stops.append(event)
    FILES[str(event_path)] = {'sha256': digest.hexdigest(), 'bytes': event_path.stat().st_size}
    assert len(starts) == 1 and snapshots and stops
    start_ns = starts[0]['receipt_monotonic_ns']
    assert start_ns == result['execution_start_monotonic_ns']
    end = float(result['evaluation_end_s'])
    stop_ns = stops[0]['receipt_monotonic_ns']
    snapshot = snapshots[0]
    for key in ['completion_time_s', 'z_work_ref_mm', 'z_release_threshold_mm']:
        assert abs(snapshot[key]-result[key]) < 3e-7, (result['run_id'], key)
    for key in ['contact_at_s', 'pass_completed_at_s', 'completion_at_s']:
        assert abs(snapshot[key]-start_ns*1e-9-result[key]) < 3e-7, (result['run_id'], key)
    force = sorted(signals['wrench'], key=lambda r:r['receipt_monotonic_ns'])
    integral = duration = excess_time = force_integral = 0.0
    peak = -np.inf
    for left, right in zip(force, force[1:]):
        t0 = (left['receipt_monotonic_ns']-start_ns)*1e-9
        t1 = (right['receipt_monotonic_ns']-start_ns)*1e-9
        a, b = max(0.0,t0), min(end,t1)
        if b <= a or t1-t0 > .2 or left.get('validity') != 'valid' or right['receipt_monotonic_ns'] > stop_ns:
            continue
        fz = float(left['fz']); dt = b-a
        duration += dt; force_integral += fz*dt
        integral += max(fz-UPPER,0.0)*dt
        excess_time += dt if fz > UPPER else 0.0
        peak = max(peak,fz)
    errors = {key: float(value-result[key]) for key,value in
              [('J_excess_Ns',integral),('force_excess_duration_s',excess_time),('peak_Fz_base_N',peak)]}
    assert max(abs(x) for x in errors.values()) < 3e-7, (result['run_id'],errors)
    assert abs(duration-end) < 3e-7
    traces = {}
    for stream, rows in signals.items():
        rows = sorted(rows,key=lambda r:r['receipt_monotonic_ns'])
        times = np.array([(r['receipt_monotonic_ns']-start_ns)*1e-9 for r in rows])
        lo = max(0,int(np.searchsorted(times,0,side='right'))-1)
        hi = min(len(rows),int(np.searchsorted(times,end,side='right'))+1)
        keys = ['fx','fy','fz'] if stream == 'wrench' else ['x','y','z']
        traces['force' if stream=='wrench' else 'pose'] = pd.DataFrame([
            dict(time_s=float(t), receipt_monotonic_ns=r['receipt_monotonic_ns'],
                 sample_id=r['sample_id'], **{k:r[k] for k in keys})
            for t,r in zip(times[lo:hi],rows[lo:hi]) if r['receipt_monotonic_ns'] <= stop_ns])
    within = traces['force'].query('0 <= time_s <= @end').time_s.to_numpy()
    return traces, dict(run_id=result['run_id'], J_excess_recalculated_Ns=integral,
                       J_error_Ns=errors['J_excess_Ns'], peak_recalculated_N=peak,
                       peak_error_N=errors['peak_Fz_base_N'], full_window_support_s=duration,
                       excess_time_recalculated_s=excess_time, mean_fz_N=force_integral/duration,
                       actual_force_receipt_hz=(len(within)-1)/(within[-1]-within[0]),
                       online_outcome_snapshot_matches=True,source=str(event_path))


def e2_event_bounds(path, expected_ns, expected_duration):
    selected = []
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for line in f:
            digest.update(line)
            if not any(t in line for t in [b'"execution_start"',b'"stop_requested"',b'"normal_completion"']):
                continue
            e = json.loads(line)
            if e.get('event') in ['execution_start','stop_requested','normal_completion']:
                selected.append(e)
    FILES[str(path)] = {'sha256':digest.hexdigest(),'bytes':path.stat().st_size}
    start = next(e for e in selected if e['event']=='execution_start')
    stop = next(e for e in selected if e['event']=='stop_requested' and not e['details'].get('initial_reset'))
    assert start['receipt_monotonic_ns']==expected_ns
    duration = (stop['receipt_monotonic_ns']-expected_ns)*1e-9
    assert abs(duration-expected_duration)<1e-8
    return dict(source=str(path),duration_s=duration,original_first_stop_details=stop['details'],
                original_terminal_events=[e['event'] for e in selected if e['event']=='normal_completion'])


def summary(df, group, metrics, completed_column):
    rows=[]
    for label, part in df.groupby(group,sort=False):
        row={group:label,'attempts':len(part),'completed':int(part[completed_column].count())}
        for metric in metrics:
            values=part[metric].dropna()
            row.update({metric+'_mean':float(values.mean()),metric+'_sd':float(values.std(ddof=1)),metric+'_n':int(len(values))})
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,default=Path('/home/eunseop/nrs_imitation'))
    repo=ap.parse_args().repo.resolve();data=P/'data';prov=P/'provenance/results_20261016'
    prov.mkdir(exist_ok=True);(data/'history').mkdir(exist_ok=True)
    # Historical results are retained independently; no later invocation may
    # overwrite them with the new primary cohort.
    for name in ['e1_runs.csv','e1_summary.csv']:
        old=data/'history'/name.replace('.csv','_20261014.csv')
        if not old.exists():shutil.copyfile(data/name,old)
    frozen=js(repo/REPORT/'input_manifest.json')
    results=js(repo/REPORT/'report_metrics.json')
    numbers=pd.read_csv(repo/REPORT/'numeric_per_run.csv');record(repo/REPORT/'numeric_per_run.csv')
    session=repo/'experiments/E1_contact_task_pass_height_v2/sessions'/SESSION
    attempts=js(session/'attempts.json');plan=js(session/'trial_plan.json')
    selected_ids=[r['run_id'] for r in frozen['included_runs']]
    assert len(set(selected_ids))==15 and set(selected_ids)==set(numbers.run_id)
    assert len(results)==15 and {r['run_id'] for r in results}==set(selected_ids)
    planned={r['plan_index']:(r['method'],r['repeat_index']) for r in plan['trials']}
    assert len(planned)==15
    actual={r['run_id']:r for r in attempts}
    assert {actual[r]['plan_index'] for r in selected_ids}==set(planned)
    assert all(actual[r]['retry_of'] is None and planned[actual[r]['plan_index']]==(actual[r]['method'],actual[r]['repeat_index']) for r in selected_ids)
    assert C6_ID not in selected_ids and C6_ID in actual
    for name in ['numeric_per_run.csv','numeric_group_summary.csv','report_statistics.json','analysis/analysis_metadata.json',
                 'numeric_validation.json','report_validation.json','delivery_validation.json','input_manifest.json','plot_observation_manifest.json']:
        src=repo/REPORT/name;record(src);shutil.copyfile(src,prov/(name.replace('/','__')))
    for name in ['session.json','trial_plan.json']:
        src=session/name;record(src);shutil.copyfile(src,prov/name)
    shutil.copyfile(session/'attempts.json',prov/'current_session_attempts.json')
    for src in (session/'frozen_config').glob('*.json'):
        record(src);shutil.copyfile(src,prov/src.name)
    for name in ['behavior_ws__src__nrs_imitation__nrs_imitation__e1_contact_task.py',
                 'behavior_ws__src__nrs_imitation__nrs_imitation__e1_contact_task_execution.py']:
        src=session/'frozen_source'/name
        record(src);shutil.copyfile(src,prov/name)
    c6=actual[C6_ID]
    c6_path=Path(c6['run_directory'])/'analysis/runs'/C6_ID/'outcome.json'
    c6_result=js(c6_path)
    all_results=results+[c6_result];rows=[];checks=[];manifest=[];source_details=[]
    for r in all_results:
        diagnostic=r['run_id']==C6_ID
        label='C6' if diagnostic else r['method']+str(r['repeat_index'])
        run=Path(r['run_directory']);event_paths=list((run/'executor').glob('*/events.jsonl'))
        assert len(event_paths)==1
        print('Reading existing E1 receipt events:',label,flush=True)
        traces,check=received_signals(event_paths[0],r);check['display_label']=label;checks.append(check)
        for kind,trace in traces.items():trace.to_csv(data/'traces'/f'E1_{label}_{kind}.csv',index=False)
        row={k:r.get(k) for k in ['run_id','run_directory','method','repeat_index','plan_index','randomization_block','execution_order',
            'evaluation_version','observer_version','completion_time_s','evaluation_end_s','J_excess_Ns','force_excess_duration_s',
            'peak_Fz_base_N','tcp_xy_distance_mm','contact_at_s','pass_completed_at_s','z_work_ref_mm','z_release_threshold_mm',
            'contact_loss_count','ordered_pass_segment_count','work_reference_start_s','work_reference_valid_duration_s','execution_start_monotonic_ns']}
        row.update(label=label,outcome='completed',stage='development',primary_or_diagnostic='diagnostic' if diagnostic else 'primary',
                   mean_fz_N=check['mean_fz_N'],actual_force_receipt_hz=check['actual_force_receipt_hz'])
        rows.append(row)
        model=(frozen['artifacts']['C_checkpoint']['sha256'] if r['method']=='C' else frozen['artifacts'][r['method']+'_template']['sha256'])
        manifest.append(dict(experiment='E1',cohort=SESSION,original_run_id=r['run_id'],display_label=label,date='2026-10-15',
            model_version=model,evaluator_version=r['evaluation_version'],observer_version=r['observer_version'],
            primary_or_diagnostic=row['primary_or_diagnostic'],inclusion_reason='Additional post-comparison execution; retains original C5 and is excluded from primary means' if diagnostic else 'Original report-frozen planned slot; one execution for each of 15 slots',
            source_path=str(run),original_repeat_index=r['repeat_index'],original_label='C5' if diagnostic else label,
            plan_index=r['plan_index'],execution_order=r['execution_order'],stage='development',
            original_retry_of=actual[r['run_id']].get('retry_of'),original_retry_reason=actual[r['run_id']].get('retry_reason')))
        source_details.append({k:r.get(k) for k in ['run_id','evaluation_version','observer_version','completed','completion_time_s','contact_at_s',
            'pass_completed_at_s','z_work_ref_mm','z_release_threshold_mm','work_reference_definition','contact_loss_count','original_stop_reason','online_offline_same_evidence_matches']})
        config=js(run/'execution_config.json')
        assert config['common']['stain_canon_enable'] is False
    e1=pd.DataFrame(rows);primary=e1[e1.primary_or_diagnostic=='primary'].copy()
    primary.to_csv(data/'e1_runs.csv',index=False)
    e1[e1.primary_or_diagnostic=='diagnostic'].to_csv(data/'e1_c6_diagnostic.csv',index=False)
    e1[e1.label.isin(['C5','C6'])].to_csv(data/'e1_c5_c6.csv',index=False)
    e1s=summary(primary,'method',['completion_time_s','J_excess_Ns','peak_Fz_base_N','tcp_xy_distance_mm'],'completion_time_s')
    e1s.to_csv(data/'e1_summary.csv',index=False);pd.DataFrame(checks).to_csv(data/'e1_receipt_recalculation.csv',index=False)
    archive=repo/'reports/20261013_E2_pdf_report';source=archive/'metrics_per_run.csv';record(source)
    e2=pd.read_csv(source);assert len(e2)==15 and e2.run_id.nunique()==15
    e2['completion_time_corrected_s']=e2.execution_duration_s
    e2['task_outcome']='operator completed'
    e2.loc[e2.label=='A4','completion_time_corrected_s']=np.nan
    e2.loc[e2.label=='A4','task_outcome']='interrupted/incomplete contact release'
    old=pd.read_csv(data/'e2_runs_corrected.csv').set_index('run_id')
    for metric in ['execution_duration_s','mean_fz_N','peak_fz_N','tcp_xy_path_mm','completion_time_corrected_s']:
        assert np.allclose(e2.set_index('run_id')[metric].sort_index(),old[metric].sort_index(),equal_nan=True)
    e2.to_csv(data/'e2_runs_corrected.csv',index=False)
    e2s=summary(e2,'condition',['completion_time_corrected_s','execution_duration_s','mean_fz_N','peak_fz_N','tcp_xy_path_mm','time_fz_ge_3N_s','gate_transitions'],'completion_time_corrected_s')
    e2s.to_csv(data/'e2_summary_corrected.csv',index=False)
    event_checks=[]
    for r in e2.to_dict('records'):
        run=Path(r['run_directory']);runtime=js(run/'runtime.json')
        event_path=next((run/'executor').glob('*/events.jsonl'))
        bounds=e2_event_bounds(event_path,int(r['execution_start_monotonic_ns']),r['execution_duration_s']);bounds['label']=r['label'];event_checks.append(bounds)
        manifest.append(dict(experiment='E2',cohort='E2_force_cleanup_20261013',original_run_id=r['run_id'],display_label=r['label'],date='2026-10-13',
            model_version=runtime['il'].get('checkpoint'),evaluator_version=None,observer_version=None,primary_or_diagnostic='primary',
            inclusion_reason='Original five attempts per condition; A4 field-corrected outcome with all-attempt metrics retained' if r['label']=='A4' else 'Original five attempts per condition',
            source_path=str(run),original_repeat_index=int(r['repeat_index']),original_label=r['label'],plan_index=None,
            execution_order=int(r['execution_order']),stage='recorded force-cleanup comparison'))
    correction=json.loads((data/'e2_operator_correction.json').read_text())
    correction['reaffirmed_source']='User field confirmation and fixed thesis scope, 2026-10-16'
    correction['raw_log_evidence']=next(x for x in event_checks if x['label']=='A4')
    write_json(data/'e2_operator_correction.json',correction)
    for name in ['numeric_validation.json','operator_completion_criterion.json','README.txt']:
        record(archive/name);shutil.copyfile(archive/name,prov/('E2_'+name))
    b=e2s.set_index('condition').loc['B','completion_time_corrected_s_mean']
    c=e2s.set_index('condition').loc['C','completion_time_corrected_s_mean']
    write_json(data/'results_summary.json',dict(E1=e1s.to_dict('records'),E2=e2s.to_dict('records'),
        E1_C5=primary[primary.label=='C5'].to_dict('records')[0],C6=e1[e1.label=='C6'].to_dict('records')[0],
        B_minus_C_seconds=float(b-c),B_to_C_reduction_percent=float((b-c)/b*100),
        B_to_C_definition='(mean_B-mean_C)/mean_B * 100; descriptive operator-based completion intervals',
        force_reference_upper_N=UPPER,primary_attempts=30,additional_diagnostics=1))
    write_json(data/'cohort_manifest.json',manifest);pd.DataFrame(manifest).to_csv(data/'cohort_manifest.csv',index=False)
    write_json(prov/'e1_online_outcome_fields.json',source_details)
    write_json(prov/'e2_original_event_bounds.json',event_checks)
    write_json(prov/'source_files.json',{k:v for k,v in FILES.items() if Path(k).is_relative_to(repo)})
    write_json(prov/'analysis_scope.json',dict(
        E1='Reaggregated report-frozen 15 runs; independently reintegrated the existing force metric and extracted actual receipt traces',
        C6='Original per-run outcome and actual receipt trace checked separately; not a replacement or primary sample',
        E2='Reaggregated archived per-run precision values; checked original event bounds; reused prior native force/path validation',
        reused='Existing force correspondence v2, E1 state-machine/height-reference and storage verification, E2 native CSV validation; no repeat calibration or full input audit',
        session_list_now_contains=len(attempts),primary_E1_count=15,primary_E2_count=15,diagnostic_count=1,
        stale_handoff='baseline_manifest still reports zero attempts; actual report, fixed membership and original run evidence take precedence',
        raw_data_modified=False,robot_or_policy_executed=False))
    print(e1s.to_string(index=False));print(e2s[['condition','completed','completion_time_corrected_s_mean','completion_time_corrected_s_sd']].to_string(index=False))
    print(f'B-C: {b-c:.9f} s; {(b-c)/b*100:.9f}%; wrote primary 15+15 and diagnostic 1.')


if __name__=='__main__':main()
