#!/usr/bin/env python3
"""Generate manuscript tables, macros, and plots from verified source-derived CSVs.

Run reconnect_sources_20261108.py once against the read-only research archive.
This step uses bundled numeric evidence; no robot, model, or source PDF parsing.
"""
from pathlib import Path
import csv
import json
import statistics as st
import numpy as np
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/thesis_matplotlib_20261108')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

P = Path(__file__).resolve().parents[1]
D, T, F = (P / x for x in ('data', 'tables', 'figures'))
V = P / 'provenance/results_20261108'


def readcsv(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


def writecsv(path, rows, fields=None):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields or list(rows[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def stats(values):
    v = [float(x) for x in values if x not in ('', None)]
    return {'mean': st.mean(v) if v else None,
            'sd': st.stdev(v) if len(v) > 1 else None, 'n': len(v)}


def savejson(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def pm(s, digits):
    return rf'${s["mean"]:.{digits}f} \pm {s["sd"]:.{digits}f}$'


def table(name, columns, header, rows):
    text = '\\begin{tabular}{' + columns + '}\n\\toprule\n'
    text += ' & '.join(header) + ' \\\\\n\\midrule\n'
    text += ''.join(' & '.join(map(str, row)) + ' \\\\\n' for row in rows)
    (T / name).write_text(text + '\\bottomrule\n\\end{tabular}\n')


def main():
    e1 = readcsv(D / 'e1_runs.csv')
    e2 = readcsv(D / 'e2_runs_corrected.csv')
    old = json.loads((D / 'diagnostic_cases_20261108.json').read_text())
    e1summary = {}
    for m in ('R', 'T', 'C'):
        rows = [r for r in e1 if r['method'] == m]
        assert len(rows) == 5
        e1summary[m] = {'attempted': 5, 'completed': 5,
                        'time_s': stats(r['completion_time_s'] for r in rows),
                        'J_excess_Ns': stats(r['J_excess_Ns'] for r in rows),
                        'peak_Fz_N': stats(r['peak_Fz_base_N'] for r in rows),
                        'travel_mm': stats(r['tcp_xy_distance_mm'] for r in rows)}

    rstar = readcsv(D / 'e1_rstar_source_runs.csv')
    for r in rstar:
        for key in ('completion_time_s','J_excess_Ns','peak_Fz_base_N','pass_mean_xy_mm_s'):
            r[key] = float(r[key])
    e1summary['Rstar'] = {'attempted':5, 'completed':5,
        'time_s':stats(r['completion_time_s'] for r in rstar),
        'J_excess_Ns':stats(r['J_excess_Ns'] for r in rstar),
        'pass_mean_xy_mm_s':stats(r['pass_mean_xy_mm_s'] for r in rstar),
        'summary_precision':'unrounded source-derived per-run CSV'}

    e2summary = {}
    for c in ('A', 'B', 'C'):
        rows = [r for r in e2 if r['condition'] == c]
        time = stats(r['completion_time_corrected_s'] for r in rows)
        e2summary[c] = {'attempted': len(rows), 'completed': time['n'],
                        'time_s': time, 'interval_s': stats(r['execution_duration_s'] for r in rows),
                        'peak_Fz_N': stats(r['peak_fz_N'] for r in rows),
                        'mean_Fz_N': stats(r['mean_fz_N'] for r in rows),
                        'travel_mm': stats(r['tcp_xy_path_mm'] for r in rows),
                        'contact_time_s': stats(r['time_fz_ge_3N_s'] for r in rows),
                        'gate_changes': stats(r['gate_transitions'] for r in rows)}
    a4 = next(r for r in e2 if r['label'] == 'A4')
    assert a4['completion_time_corrected_s'] == '' and abs(float(a4['execution_duration_s'])-28.750087346) < 1e-10

    e3 = readcsv(D / 'e3_source_area_runs.csv')
    for r in e3:
        for key in ('image_evaluable','main_condition','final_tool_occlusion'):
            r[key] = r[key] == 'True'
        for key in ('repeat_index','A_before_px','A_after_px','visible_residual_diagnostic_px'):
            r[key] = None if r[key] == '' else int(r[key])
        r['removal_percent'] = None if r['removal_percent'] == '' else float(r['removal_percent'])
    assert len(e3)==25 and sum(r['main_condition'] for r in e3)==20
    assert sum(r['image_evaluable'] for r in e3)==19
    e3summary = {}
    for c in ('N','P1','D1','D2','P2'):
        group = [r for r in e3 if r['condition']==c]
        e3summary[c] = {'selected_n':len(group),
            'removal_percent':stats(r['removal_percent'] for r in group),
            'unavailable_n':sum(not r['image_evaluable'] for r in group)}
    mapping = readcsv(V/'e3_run_config_mapping.csv')
    placements = {}
    for c in ('N','P1','D1','D2'):
        group = [r for r in mapping if r['condition']==c]
        values = [[float(r[k]) for k in ('delta_x_mm','delta_y_mm','phi_deg')] for r in group]
        assert all(v==values[0] for v in values)
        placements[c]=values[0]
    writecsv(D/'e3_registered_placements.csv',
        [dict(condition=c,delta_x_mm=v[0],delta_y_mm=v[1],phi_deg=v[2],
            source='source-derived; frozen run_context registered_layout, all five run IDs checked')
        for c,v in placements.items()])
    rcomparison=json.loads((V/'e1_r_retiming_source_summary.json').read_text())
    roriginal=next(r for r in rcomparison if r['cohort']=='original_R_5')
    original_speed=dict(mean=float(roriginal['successful_pass_actual_xy_mean_mm_s_mean']),
        sd=float(roriginal['successful_pass_actual_xy_mean_mm_s_sample_sd']),n=5)
    time_gain=e1summary['R']['time_s']['mean']-e1summary['Rstar']['time_s']['mean']
    summary = {'E1': e1summary, 'E2': e2summary, 'E3': e3summary,
               'E1_C5': old['E1_C5'], 'C6': old['C6'],
               'E2_A4': {'interval_s': float(a4['execution_duration_s']), 'completion_time_s': None,
                         'mean_force_N': float(a4['mean_fz_N']), 'contact_time_s':float(a4['time_fz_ge_3N_s'])},
               'E1_processing_peak_feed_mm_s': 14.940779233290927,
               'E1_source_processing_mean_mm_s': 14.940779233290927 / 1.875,
               'E1_original_pass_mean_xy_mm_s': original_speed,
               'E1_Rstar_time_difference_s': time_gain, 'E1_Rstar_time_reduction_percent': 100*time_gain/e1summary['R']['time_s']['mean'],
               'E2_B_minus_C_s': e2summary['B']['time_s']['mean']-e2summary['C']['time_s']['mean'],
               'E2_B_to_C_percent': 100*(1-e2summary['C']['time_s']['mean']/e2summary['B']['time_s']['mean']),
               'E3_placements': placements, 'E3_archive_n':25, 'E3_main_n':20, 'E3_image_n':19,
               'unit': 'run; sample SD ddof=1',
               'source_status': 'source-derived: E1/E2 matched frozen precision CSVs; Rstar unrounded CSV and run IDs; E3 original RGB and 75 pixel-identical masks, unchanged annotations/ROI/gray45',
               'force_reference_upper_N': 30.812396273}
    savejson(D / 'results_summary_20261108.json', summary)
    precision=[]
    for study, groups in [('E1', e1summary), ('E2', e2summary), ('E3', e3summary)]:
        for c, row in groups.items():
            for k,v in row.items():
                if isinstance(v,dict) and 'mean' in v:
                    precision.append(dict(study=study, condition=c, metric=k, **v))
    writecsv(D/'results_precision_20261108.csv', precision)

    # Every current result macro is generated from this one summary, including
    # retained diagnostic numbers; no result-macro file is used as an input.
    macros = {}
    def number(name, value, digits): macros[name] = f'{value:.{digits}f}'
    for c in ('R','T','C','Rstar'):
        for short,key in [('Time','time_s'),('Excess','J_excess_Ns')]:
            for end,field in [('', 'mean'),('SD','sd')]:
                number('Eone'+c+short+end, e1summary[c][key][field], 3)
        if c!='Rstar':
            for short,key in [('Peak','peak_Fz_N'),('Travel','travel_mm')]:
                for end,field in [('', 'mean'),('SD','sd')]:
                    number('Eone'+c+short+end,e1summary[c][key][field],2)
    for c in ('A','B','C'):
        for short,key in [('Time','time_s'),('Interval','interval_s'),('Peak','peak_Fz_N'),('MeanForce','mean_Fz_N'),('Travel','travel_mm'),('ContactTime','contact_time_s'),('GateChanges','gate_changes')]:
            for end,field in [('', 'mean'),('SD','sd')]:
                number('Etwo'+c+short+end, e2summary[c][key][field], 2)
        macros['Etwo'+c+'TimeN']=str(e2summary[c]['time_s']['n'])
    for label,row in [('Cfive',summary['E1_C5']),('Csix',summary['C6'])]:
        for short,key in [('Time','completion_time_s'),('Excess','J_excess_Ns'),('Contact','contact_at_s'),('Pass','pass_completed_at_s'),('WorkZ','z_work_ref_mm'),('ReleaseZ','z_release_threshold_mm'),('ExcessTime','force_excess_duration_s')]:
            number(label+short,row[key],3)
        number(label+'Peak',row['peak_Fz_base_N'],2 if label=='Cfive' else 3)
    number('ForceExposureReference',summary['force_reference_upper_N'],9)
    for short,key in [('Interval','interval_s'),('MeanForce','mean_force_N'),('ContactTime','contact_time_s')]:
        number('Afour'+short,summary['E2_A4'][key],3)
    for c,short in [('N','N'),('P1','Pone'),('D1','Done'),('D2','Dtwo')]:
        number('Ethree'+short+'Removal',e3summary[c]['removal_percent']['mean'],2)
        number('Ethree'+short+'SD',e3summary[c]['removal_percent']['sd'],2)
        macros['Ethree'+short+'N']=str(e3summary[c]['removal_percent']['n'])
    macros.update(EthreeArchiveN='25', EthreeMainN='20', EthreeImageN='19')
    number('RstarTimeMeanPrecision',e1summary['Rstar']['time_s']['mean'],6)
    number('RstarTimeSDPrecision',e1summary['Rstar']['time_s']['sd'],6)
    number('RstarTimeGain',summary['E1_Rstar_time_difference_s'],3)
    number('RstarTimePercent',summary['E1_Rstar_time_reduction_percent'],1)
    number('BCSeconds',summary['E2_B_minus_C_s'],2);number('BCPercent',summary['E2_B_to_C_percent'],1)
    (T/'result_numbers.tex').write_text('% Generated from the single current data/results_summary_20261108.json.\n'+''.join('\\newcommand{\\'+k+'}{'+v+'}\n' for k,v in macros.items()))
    table('e1_latest.tex','llcrr',['Method','Date / cohort','Done/run','Time (s)',r'$J_{\mathrm{excess}}$ (N\,s)'],
          [[r'$R^{*}$','19 Oct / additional','5/5',pm(e1summary['Rstar']['time_s'],3),pm(e1summary['Rstar']['J_excess_Ns'],3)]]+
          [[c,'15 Oct / original','5/5',pm(e1summary[c]['time_s'],3),pm(e1summary[c]['J_excess_Ns'],3)] for c in ('T','C')])
    table('e1_r_retiming.tex','lrr',['Metric','Original R (15 Oct)',r'Additional $R^{*}$ (19 Oct)'],[
        ['Completed / executed','5/5','5/5'],['Peak-feed parameter (mm/s)','10.000000','14.940779'],
        ['Completion time (s)',pm(e1summary['R']['time_s'],3),pm(e1summary['Rstar']['time_s'],3)],
        ['Measured pass XY speed (mm/s)',pm(summary['E1_original_pass_mean_xy_mm_s'],3),pm(e1summary['Rstar']['pass_mean_xy_mm_s'],3)],
        [r'$J_{\mathrm{excess}}$ (N\,s)',pm(e1summary['R']['J_excess_Ns'],3),pm(e1summary['Rstar']['J_excess_Ns'],3)]])
    table('e1_rstar_all.tex','lrrrr',['Run','Time (s)',r'$J_{\mathrm{excess}}$ (N\,s)','Peak (N)','Pass (mm/s)'],
          [[r['display_label'].replace('*',r'$^{*}$')]+[f'{r[k]:.3f}' for k in ('completion_time_s','J_excess_Ns','peak_Fz_base_N','pass_mean_xy_mm_s')] for r in rstar])
    table('e1_rstar_ids.tex','ll',['Run','Original run identifier'],
          [[r['display_label'].replace('*',r'$^{*}$'),r'\texttt{'+r['run_id'].replace('_',r'\_')+'}'] for r in rstar])
    table('e2_corrected_primary.tex','lccrr',['Condition','Done/attempt','Time n','Time (s)','Mean peak (N)'],
          [[c,f'{e2summary[c]["completed"]}/5',e2summary[c]['time_s']['n'],pm(e2summary[c]['time_s'],2),pm(e2summary[c]['peak_Fz_N'],2)] for c in ('A','B','C')])
    table('e3_main_results.tex','lccrc',['Condition','Selected n','Image n','Removal (\%)','Unavailable'],
          [[c,5,e3summary[c]['removal_percent']['n'],pm(e3summary[c]['removal_percent'],2),e3summary[c]['unavailable_n']] for c in placements])
    table('e3_placements.tex','lrrr',['Condition',r'$\Delta X$ (mm)',r'$\Delta Y$ (mm)',r'$\varphi$ (deg)'],
          [[c]+[f'{v:+.2f}' if v else '0.00' for v in values] for c,values in placements.items()])
    table('e3_all_runs.tex','lrrrl',['Run',r'$A_{\mathrm{before}}$ (px)',r'$A_{\mathrm{after}}$ (px)','Removal (\%)','Note'],
          [[r['display_label'],r['A_before_px'],r'\NA' if r['A_after_px'] is None else r['A_after_px'],r'\NA' if r['removal_percent'] is None else f'{r["removal_percent"]:.3f}', 'tool occlusion' if not r['image_evaluable'] else 'image evaluable'] for r in e3 if r['main_condition']])
    table('e3_p2_archive.tex','lrrl',['Run',r'$A_{\mathrm{before}}$ (px)','Image result','Original stop'],
          [[r['display_label'],r['A_before_px'],'unavailable',r'\texttt{operator\_finish}'] for r in e3 if not r['main_condition']])

    manifest=[]
    def mrow(study, label, run_id, cohort, version, role, reason, source, available):
        manifest.append(dict(experiment=study,display_label=label,run_id=run_id,cohort=cohort,
                             analysis_version=version,role=role,reason=reason,source=source,source_available=available))
    for r in e1:
        mrow('E1',r['label'],r['run_id'],'original_20261015','pass_height_ref_v2 / received_observations_v2',
             'original comparison; T/C also latest summary' if r['method']!='R' else 'original comparison; adjacent auxiliary summary',
             'original planned slot; C5 retained','data/e1_runs.csv','source-derived; original frozen run IDs/configs/precision CSV verified')
    for r in rstar:
        mrow('E1',r['display_label'],r['run_id'],'Rstar_additional_20261019','pass_height_ref_v2 / received_observations_v2',
             'latest summary; separate additional cohort','one initial diagnostic then four extension runs; original identities recovered',r['source'],'source-derived; unrounded CSV, configs and template SHA-256 verified')
    mrow('E1','C6',old['C6']['run_id'],'additional_C6_20261015','pass_height_ref_v2 / received_observations_v2','diagnostic only','does not replace original C5','data/e1_c6_diagnostic.csv','source-derived; archived precision CSV checked; field correction retained')
    for r in e2:
        mrow('E2',r['label'],r['run_id'],'corrected_20261013','operator interval; A4 field correction','main; time excluded only for A4' if r['label']=='A4' else 'main',
             'incomplete release; stop retained; completion null' if r['label']=='A4' else 'all original attempts retained','data/e2_runs_corrected.csv','source-derived; archived precision CSV checked; field correction retained')
    for r in e3:
        mrow('E3',r['display_label'],r['run_id'],'archive25_main20_image19_20261023','post-hoc gray45 + saved visible-boundary annotations',
             'archive only; P2 excluded from main' if not r['main_condition'] else 'main selected; image unavailable' if not r['image_evaluable'] else 'main removal statistic',
             r['unavailable_reason'] or 'raw RGB and frozen annotations reproduced; automatic completion not an inclusion criterion',r['source'], 'source-derived; original RGB hashes, saved ROI/annotations, pixel-identical masks')
    writecsv(P/'results_manifest_20261108.csv',manifest)
    savejson(V/'metric_definitions.json',dict(E1='execution_start to first TASK_COMPLETED; J=integral max(base Fz-30.812396273,0), archived ZOH and 0.2s gap rules; no reevaluation',
        E2='operator completed interval; A4 completion null, interval/peak/path retained; run peak means n5',
        E3='100*(A_before-A_after)/A_before; original RGB and unchanged gray45/ROI/annotation integer px; unweighted run arithmetic mean, ddof1; 25 archive,20 main,19 images',
        segmentation='frozen gray<=45/255 plus saved manual visible boundaries; 6px ROI margin; no new annotation or threshold selection',
        precision='E1/E2 matched archived precision CSV; Rstar unrounded per-run values; E3 raw RGB-derived integer areas, pixel-identical saved masks',
        verification_record='provenance/results_20261108/source_validation.json',
        no_robot_or_training=True))

    plot_results(e1,rstar,e1summary,e3,e3summary,placements)
    print('Generated: 61-row manifest; E1 original15 + Rstar5 + C6, E2 15, E3 archive25/main20/image19.')
    print('E3 mean/SD:', {c:(v['removal_percent']['mean'],v['removal_percent']['sd'],v['removal_percent']['n']) for c,v in e3summary.items()})


def plot_results(e1,rstar,e1summary,e3,e3summary,placements):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
    colors=['#8b96a1','#d58b27','#398684','#4c64b3']
    groups=[('R', [r for r in e1 if r['method']=='R']),('Rstar',rstar),('T',[r for r in e1 if r['method']=='T']),('C',[r for r in e1 if r['method']=='C'])]
    fig,axes=plt.subplots(1,2,figsize=(8.3,3.7),layout='constrained')
    for ax,key,lab in zip(axes,['completion_time_s','J_excess_Ns'],['First procedural completion (s)',r'Excess-force integral (N s)']):
        for i,(c,rows) in enumerate(groups):
            vals=[float(r[key]) for r in rows]; x=np.arange(5)*.10+i-.20
            ax.scatter(x,vals,c=colors[i],marker=['o','s','^','v'][i],edgecolors='black',linewidths=.35,s=30,zorder=3)
            for j,(xx,yy) in enumerate(zip(x,vals)):
                if (c=='Rstar' and j==0 and key=='completion_time_s') or (c=='C' and j==4):
                    ax.annotate('R*1' if c=='Rstar' else 'C5',(xx,yy),xytext=(0,6),textcoords='offset points',fontsize=8,ha='center')
            s=e1summary[c]['time_s' if key=='completion_time_s' else 'J_excess_Ns']
            ax.errorbar(i+.34,s['mean'],yerr=s['sd'],fmt='D',color='#172d43',markersize=5,capsize=4,zorder=4)
        ax.set_xticks(range(4),['R original\n15 Oct','R* additional\n19 Oct','T original\n15 Oct','C original\n15 Oct'])
        ax.set_ylabel(lab);ax.grid(axis='y',alpha=.2); ax.set_xlim(-.45,3.6)
        ax.set_ylim((-2,34) if key=='completion_time_s' else (-1.7,8.0))
        ax.axvline(1.5,color='#aeb4bb',ls=':',lw=1)
    for ext in ('pdf','svg','png'): fig.savefig(F/f'e1_latest_metrics.{ext}',dpi=200)
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(7.5,3.8),layout='constrained')
    for i,c in enumerate(placements):
        rows=[r for r in e3 if r['condition']==c and r['image_evaluable']]
        x=i+np.linspace(-.14,.14,len(rows))
        vals=[r['removal_percent'] for r in rows]
        ax.scatter(x,vals,color=colors[i],marker=['o','s','^','v'][i],edgecolors='black',linewidths=.35,s=35,zorder=3)
        for xx,r in zip(x,rows):ax.annotate(str(r['repeat_index']),(xx,r['removal_percent']),xytext=(0,6),textcoords='offset points',ha='center',fontsize=9)
        s=e3summary[c]['removal_percent'];ax.errorbar(i+.23,s['mean'],yerr=s['sd'],fmt='D',color='#172d43',capsize=5,zorder=4)
    ax.set_xticks(range(4),[f'{c}\nimage n={e3summary[c]["removal_percent"]["n"]}' for c in placements])
    ax.set_ylabel('Image-based stain-area removal (%)');ax.set_ylim(75,106);ax.set_xlim(-.45,3.55)
    ax.grid(axis='y',alpha=.2)
    ax.text(.02,.04,'D1-4: final tool occlusion; no imputed value',transform=ax.transAxes,fontsize=9)
    for ext in ('pdf','svg','png'):fig.savefig(F/f'e3_removal_metrics.{ext}',dpi=200)
    plt.close(fig)
    fig,(ax,bx)=plt.subplots(1,2,figsize=(8.1,3.5),layout='constrained')
    for i,(c,(x,y,phi)) in enumerate(placements.items()):
        ax.scatter(x,y,color=colors[i],s=40)
        offset={'N':(4,6),'P1':(-8,-17),'D1':(-25,4),'D2':(5,-12)}[c]
        ax.annotate(c,(x,y),xytext=offset,textcoords='offset points',color=colors[i],weight='bold')
        rad=np.deg2rad(phi)
        bx.arrow(0,0,np.cos(rad),np.sin(rad),head_width=.04,length_includes_head=True,color=colors[i],lw=2)
        bx.text(1.13*np.cos(rad),1.13*np.sin(rad),f'{c}: {phi:+.2f}°' if phi else 'N / P1: 0°',ha='left',va='center',fontsize=9,color=colors[i]) if c!='P1' else None
    ax.axhline(0,color='.75',lw=.7);ax.axvline(0,color='.75',lw=.7)
    ax.set(xlabel=r'Registered $\Delta X$ (mm)',ylabel=r'Registered $\Delta Y$ (mm)',xlim=(-7,36),ylim=(-8,28),title='Registered centers');ax.set_aspect('equal');ax.grid(alpha=.18)
    bx.set(xlim=(-.1,1.85),ylim=(-.85,1.0),title='Direction relative to nominal')
    bx.set_aspect('equal');bx.axis('off')
    for ext in ('pdf','svg','png'):fig.savefig(F/f'e3_registered_layout.{ext}',dpi=200)
    plt.close(fig)



if __name__ == '__main__':
    main()
