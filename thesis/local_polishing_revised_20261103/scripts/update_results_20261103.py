#!/usr/bin/env python3
"""Reaggregate saved run results and published integer areas; never run a robot/model.

The original nrs_imitation repository was not present at revision time. This
entrypoint records that distinction rather than fabricating source precision or
claiming to revalidate segmentation. E3 counts are transcribed by parsing the
unchanged report tables. Report-embedded evidence panels are reused unchanged.
"""
from pathlib import Path
import csv
import hashlib
import json
import re
import statistics as st
import subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

P = Path(__file__).resolve().parents[1]
D, T, F = (P / x for x in ('data', 'tables', 'figures'))
V = P / 'provenance/results_20261103'
REPORT = V / 'reports'
E3PDF = REPORT / 'E3_image_removal_report_20261023.pdf'
RPDF = REPORT / 'E1_report_20261019_R_dataset_mean_feed_5runs.pdf'


def readcsv(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


def writecsv(path, rows, fields=None):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields or list(rows[0]))
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


def pdftext(path):
    return subprocess.run(['pdftotext', '-layout', str(path), '-'],
                          capture_output=True, text=True, check=True).stdout


def main():
    e1 = readcsv(D / 'e1_runs.csv')
    e2 = readcsv(D / 'e2_runs_corrected.csv')
    old = json.loads((D / 'results_summary.json').read_text())
    e1summary = {}
    for m in ('R', 'T', 'C'):
        rows = [r for r in e1 if r['method'] == m]
        assert len(rows) == 5
        e1summary[m] = {'attempted': 5, 'completed': 5,
                        'time_s': stats(r['completion_time_s'] for r in rows),
                        'J_excess_Ns': stats(r['J_excess_Ns'] for r in rows),
                        'peak_Fz_N': stats(r['peak_Fz_base_N'] for r in rows),
                        'travel_mm': stats(r['tcp_xy_distance_mm'] for r in rows)}

    # Page 5 contains the five additional executions, at printed 0.001 precision.
    rpages = pdftext(RPDF).split('\f')
    matches = re.findall(r'^\s*R([1-5])\s+True\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*$', rpages[4], re.M)
    assert len(matches) == 5
    rstar = [dict(display_label='R*' + i, run_id='', date='2026-10-19',
                  completion_time_s=float(t), J_excess_Ns=float(j),
                  peak_Fz_base_N=float(peak), pass_mean_xy_mm_s=float(speed),
                  source='E1_report_20261019_R_dataset_mean_feed_5runs.pdf, p.5',
                  value_precision='printed 0.001; original per-run CSV unavailable',
                  config_version=('e1ct_6c29a198a24df7a2' if i == '1' else 'e1ct_c5c424abc45fac4c'))
             for i, t, j, peak, speed in matches]
    writecsv(D / 'e1_rstar_report_runs.csv', rstar)
    # Published summary takes precedence over recomputing an SD from rounded rows.
    e1summary['Rstar'] = {'attempted': 5, 'completed': 5,
                         'time_s': {'mean': 24.840, 'sd': 1.321, 'n': 5},
                         'J_excess_Ns': {'mean': 0.0, 'sd': 0.0, 'n': 5},
                         'pass_mean_xy_mm_s': {'mean': 10.841, 'sd': 0.088, 'n': 5},
                         'summary_precision': 'published 0.001, report p.1',
                         'rounded_rows_time_check': stats(r['completion_time_s'] for r in rstar)}
    assert abs(e1summary['Rstar']['rounded_rows_time_check']['sd'] - 1.321) < .001

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

    # All E3 identities and exact integer pixel counts occur on report pp.5--9.
    epages = pdftext(E3PDF).split('\f')
    e3 = []
    pattern = (r'^\s*(E3_\w+_)\s*\n'
               r'\s*(N|P1|P2|D1|D2)-(\d)\s+(\d+)\s+(\d+|—)\s+([\d.]+|—)\s+([YN])\s+([YN])\s+([YN])\s*\n'
               r'\s*(\d{8}T\d{6}_[a-f0-9]+)\s*$')
    for page in range(4, 9):
        rows = re.findall(pattern, epages[page], re.M)
        assert len(rows) == 5, (page + 1, rows)
        for prefix, c, i, before, after, printed, avail, initial_occ, final_occ, suffix in rows:
            b, a = int(before), None if after == '—' else int(after)
            value = None if a is None else 100 * (b-a) / b
            if value is not None:
                assert abs(value - float(printed)) <= .000501
            label = f'{c}-{i}'
            e3.append(dict(display_label=label, condition=c, repeat_index=int(i),
                           run_id=prefix+suffix, date=suffix[:8], A_before_px=b, A_after_px=a,
                           removal_percent=value, image_evaluable=avail == 'Y',
                           main_condition=c != 'P2', final_tool_occlusion=final_occ == 'Y',
                           original_stop_reason='manual_abort' if label == 'D1-4' else 'operator_finish',
                           report_page=page+1, evidence_page=10+len(e3),
                           unavailable_reason='final tool occlusion' if a is None else '',
                           source='E3_image_removal_report_20261023.pdf',
                           precision='exact integer areas printed in report; CSV/masks not re-audited'))
    assert len(e3) == 25 and sum(r['main_condition'] for r in e3) == 20
    assert sum(r['image_evaluable'] for r in e3) == 19
    writecsv(D / 'e3_report_area_runs.csv', e3)
    e3summary = {}
    for c in ('N', 'P1', 'D1', 'D2', 'P2'):
        rows = [r for r in e3 if r['condition'] == c]
        e3summary[c] = {'selected_n': len(rows), 'removal_percent': stats(r['removal_percent'] for r in rows),
                        'unavailable_n': sum(not r['image_evaluable'] for r in rows)}
    # Placement values are the user's confirmed execution record, not an invented
    # measurement or a value verified against an unavailable run-context file.
    placements = {'N': [0., 0., 0.], 'P1': [29.55, 21.80, 0.],
                  'D1': [-1.06, -1.36, 42.17], 'D2': [-.75, -3.53, -31.03]}
    writecsv(D / 'e3_registered_placements.csv', [dict(condition=c, delta_x_mm=v[0], delta_y_mm=v[1], phi_deg=v[2], source='user-confirmed revision instruction, 2026-11-03; run_context not locally available') for c,v in placements.items()])
    summary = {'E1': e1summary, 'E2': e2summary, 'E3': e3summary,
               'E1_C5': old['E1_C5'], 'C6': old['C6'],
               'E2_A4': {'interval_s': float(a4['execution_duration_s']), 'completion_time_s': None,
                         'mean_force_N': float(a4['mean_fz_N']), 'contact_time_s':float(a4['time_fz_ge_3N_s'])},
               'E1_processing_peak_feed_mm_s': 14.940779233290927,
               'E1_source_processing_mean_mm_s': 14.940779233290927 / 1.875,
               'E1_original_pass_mean_xy_mm_s': {'mean': 7.918, 'sd': .124, 'n': 5},
               'E1_Rstar_time_difference_s': 4.697, 'E1_Rstar_time_reduction_percent': 15.9,
               'E2_B_minus_C_s': e2summary['B']['time_s']['mean']-e2summary['C']['time_s']['mean'],
               'E2_B_to_C_percent': 100*(1-e2summary['C']['time_s']['mean']/e2summary['B']['time_s']['mean']),
               'E3_placements': placements, 'E3_archive_n':25, 'E3_main_n':20, 'E3_image_n':19,
               'unit': 'run; sample SD ddof=1',
               'source_status': 'E1/E2 inherited precision CSVs; Rstar published summary/rounded per-run values; E3 exact published integer areas; original nrs_imitation folder unavailable',
               'force_reference_upper_N': 30.812396273}
    savejson(D / 'results_summary_20261103.json', summary)
    precision=[]
    for study, groups in [('E1', e1summary), ('E2', e2summary), ('E3', e3summary)]:
        for c, row in groups.items():
            for k,v in row.items():
                if isinstance(v,dict) and 'mean' in v:
                    precision.append(dict(study=study, condition=c, metric=k, **v))
    writecsv(D/'results_precision_20261103.csv', precision)

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
    number('RstarTimeGain',summary['E1_Rstar_time_difference_s'],3)
    number('RstarTimePercent',summary['E1_Rstar_time_reduction_percent'],1)
    number('BCSeconds',summary['E2_B_minus_C_s'],2);number('BCPercent',summary['E2_B_to_C_percent'],1)
    (T/'result_numbers.tex').write_text('% Generated from the single current data/results_summary_20261103.json.\n'+''.join('\\newcommand{\\'+k+'}{'+v+'}\n' for k,v in macros.items()))
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
             'original planned slot; C5 retained','data/e1_runs.csv','inherited precision CSV; original session absent')
    for r in rstar:
        mrow('E1',r['display_label'],'','Rstar_additional_20261019','pass_height_ref_v2 / received_observations_v2',
             'latest summary; separate additional cohort','one initial diagnostic then four extension runs; original run_id absent from PDF',r['source'],'PDF only; rounded per-run values')
    mrow('E1','C6',old['C6']['run_id'],'additional_C6_20261015','pass_height_ref_v2 / received_observations_v2','diagnostic only','does not replace original C5','data/e1_c6_diagnostic.csv','inherited precision CSV')
    for r in e2:
        mrow('E2',r['label'],r['run_id'],'corrected_20261013','operator interval; A4 field correction','main; time excluded only for A4' if r['label']=='A4' else 'main',
             'incomplete release; stop retained; completion null' if r['label']=='A4' else 'all original attempts retained','data/e2_runs_corrected.csv','inherited precision CSV')
    for r in e3:
        mrow('E3',r['display_label'],r['run_id'],'archive25_main20_image19_20261023','post-hoc gray45 + saved visible-boundary annotations',
             'archive only; P2 excluded from main' if not r['main_condition'] else 'main selected; image unavailable' if not r['image_evaluable'] else 'main removal statistic',
             r['unavailable_reason'] or 'exact printed areas; automatic completion not an inclusion criterion',f'{r["source"]}, pp.{r["report_page"]},{r["evidence_page"]}', 'PDF exact integer counts and embedded evidence; original manifest/masks unavailable')
    writecsv(P/'results_manifest_20261103.csv',manifest)
    savejson(V/'metric_definitions.json',dict(E1='execution_start to first TASK_COMPLETED; J=integral max(base Fz-30.812396273,0), archived ZOH and 0.2s gap rules; no reevaluation',
        E2='operator completed interval; A4 completion null, interval/peak/path retained; run peak means n5',
        E3='100*(A_before-A_after)/A_before; exact report integer px; unweighted run arithmetic mean, ddof1; 25 archive,20 main,19 images',
        segmentation='reported gray<=45/255 plus saved manual visible boundaries; 6px ROI margin; no new annotation or threshold selection',
        precision='E1/E2 inherited precision CSV; Rstar report mean/SD authoritative, per-run rounded; E3 exact integer report areas',
        not_read_locally=['nrs_imitation original analysis CSV/JSON/run_context/template','E3 image_pair_manifest, annotations, original RGB/masks','Rstar input_manifest and original run_ids','25-page original E3 execution report'],
        no_robot_or_training=True))

    plot_results(e1,rstar,e1summary,e3,e3summary,placements)
    extract_evidence(e3)
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
            ax.scatter(x,vals,c=colors[i],s=30,zorder=3)
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
        ax.scatter(x,vals,color=colors[i],s=35,zorder=3)
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


def extract_evidence(e3):
    out=V/'e3_report_panels';out.mkdir(exist_ok=True)
    subprocess.run(['pdfimages','-f','10','-l','34','-png',str(E3PDF),str(out/'panel')],check=True)
    panels=sorted(out.glob('panel-*.png'))
    assert len(panels)==25
    manifest=[]
    for row,panel in zip(e3,panels):
        manifest.append(dict(run_id=row['run_id'],label=row['display_label'],report_page=row['evidence_page'],
            embedded_panel=str(panel.relative_to(P)),sha256=hashlib.sha256(panel.read_bytes()).hexdigest(),
            source='unchanged report-embedded evidence image; not a fresh read of original RGB or image_pair_manifest',
            display_transform='none for archived panel; fixed rectangles for thesis composite',
            image_evaluable=row['image_evaluable']))
    savejson(V/'e3_evidence_panel_manifest.json',manifest)
    # Display-only crops: identical rectangles on all four first-index examples.
    # These extract report RGB+ROI and mask panels, never measure their pixels.
    def panelgrid(labels, filename):
        fig,axes=plt.subplots(len(labels),4,figsize=(10,2.1*len(labels)),squeeze=False)
        rects=[(17,86,376,289),(393,86,752,289),(17,351,376,540),(393,351,752,540)]
        for i,label in enumerate(labels):
            idx=next(k for k,r in enumerate(e3) if r['display_label']==label)
            im=Image.open(panels[idx])
            for j,rect in enumerate(rects):
                axes[i,j].imshow(im.crop(rect));axes[i,j].axis('off')
                if i==0:axes[i,j].set_title(['Before RGB + ROI','After RGB + ROI','Before ink mask','After ink mask'][j],fontsize=10)
            axes[i,0].text(-.03,.5,label,transform=axes[i,0].transAxes,ha='right',va='center',fontsize=11,weight='bold')
        fig.subplots_adjust(left=.07,right=.995,top=.94,bottom=.01,wspace=.03,hspace=.1)
        for ext in ('pdf','png'):fig.savefig(F/f'{filename}.{ext}',dpi=200)
        plt.close(fig)
    panelgrid(['N-1','P1-1','D1-1','D2-1'],'e3_first_index_evidence')
    # Preserve occluded examples in the archive; original report panels include
    # hatching and explanatory labels that must not be reconstructed.
    for label in ['D1-4']+[f'P2-{i}' for i in range(1,6)]:
        idx=next(k for k,r in enumerate(e3) if r['display_label']==label)
        dest=F/f'e3_{label}_report_evidence.png'
        dest.write_bytes(panels[idx].read_bytes())


if __name__ == '__main__':
    main()
