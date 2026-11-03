#!/usr/bin/env python3
"""Regenerate all measured plots from bundled, unmodified CSV extracts."""
from pathlib import Path
import json
import os
os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / '.mplconfig'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / 'data'; F = ROOT / 'figures'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,
                     'axes.spines.right':False,'pdf.fonttype':42,'ps.fonttype':42,
                     'axes.grid':True,'grid.alpha':.18,'savefig.bbox':'tight'})
colors = {'R':'#326b93','T':'#b16b24','C':'#40816b','A':'#9c4d5c','B':'#71609b'}
e1 = pd.read_csv(D/'e1_runs.csv'); e2 = pd.read_csv(D/'e2_runs_corrected.csv')
manifest = json.loads((ROOT/'figure_manifest.json').read_text())
manifest = [x for x in manifest if not x.get('generated_plot')]
input_paths = list(json.loads((ROOT/'provenance/input_manifest.json').read_text()))
asset_sources = {x['output']:x.get('sources',[]) for x in manifest}


def save(fig,name,fig_id,sources,location,description):
    fig.savefig(F/(name+'.pdf')); fig.savefig(F/(name+'.png'),dpi=150)
    plt.close(fig)
    expanded=[];original=[];run_ids=[]
    for item in sources:
        paths=sorted(ROOT.glob(item)) if '*' in item else [ROOT/item]
        expanded.extend(str(p.relative_to(ROOT)) for p in paths)
        for p in paths:
            rel=str(p.relative_to(ROOT))
            if p.parent.name=='traces':
                cohort,label,kind=p.stem.split('_');df=e1 if cohort=='E1' else e2
                row=df[df.label==label].iloc[0];run_ids.append(row.run_id)
                original.extend(x for x in input_paths if x.startswith(row.run_directory+'/')
                                and x.endswith('/'+('wrench.csv' if kind=='force' else 'tcp_pose.csv')))
            original.extend(asset_sources.get(rel,[]))
            if p.name=='e1_runs.csv': original.extend(x for x in input_paths if x.endswith('20261014_E1_contact_task_pdf_report/metrics_per_run.csv'))
            if p.name=='e2_runs_corrected.csv': original.extend(x for x in input_paths if x.endswith('20261013_E2_pdf_report/metrics_per_run.csv'))
            if p.name=='e1_height_reference_replay.csv': original.extend(x for x in input_paths if x.endswith('baseline_replay_comparison.csv'))
            if p.name=='teaching_episode29.csv':
                meta=json.loads((ROOT/'provenance/teaching_episode29_metadata.json').read_text())
                original.append(meta['source_h5'])
                original.extend(x for x in input_paths if x.endswith('imitation_form/episode_29.hdf5'))
    manifest.append(dict(figure_id=fig_id,output='figures/'+name+'.pdf',sources=sorted(set(expanded)),
                         original_sources=sorted(set(original)),run_ids=sorted(set(run_ids)),
                         provenance='provenance/input_manifest.json and data run inventories',
                         processing=description,location=location,generated_plot=True))


def trace(cohort,label,kind):
    return pd.read_csv(D/'traces'/f'{cohort}_{label}_{kind}.csv')


# Native force values: no temporal smoothing, no clipping, no normalization.
for cohort,df,groups in [('E1',e1,['R','T','C']),('E2',e2,['A','B','C'])]:
    fig,axes=plt.subplots(3,1,figsize=(6.5,6.4),sharex=True,sharey=True,layout='constrained')
    for ax,g in zip(axes,groups):
        part=df[df['method' if cohort=='E1' else 'condition']==g]
        for _,r in part.iterrows():
            s=trace(cohort,r.label,'force')
            end=r.evaluation_end_s if cohort=='E1' else r.execution_duration_s
            z=s[(s.time_s>=0)&(s.time_s<=end)]
            ax.step(z.time_s,z.fz,where='post',alpha=.8,lw=.85,label=r.label,
                    color=plt.cm.tab10(int(r.repeat_index)-1))
        if cohort=='E1': ax.axhline(30.812396273,color='black',ls='--',lw=.8,label='Demo Q95')
        ax.set_ylabel(g+'  $F_z^B$ (N)'); ax.legend(ncols=6,fontsize=7,loc='upper right')
    axes[-1].set_xlabel('Time from execution start (s)')
    save(fig,cohort.lower()+'_force_all','fig:'+cohort.lower()+'_force_all',
         [f'data/traces/{cohort}_*_force.csv'],'Chapter 7',
         'All five executions per method; raw logged values shown with ZOH; archived analysis windows; full force range')

# Full XY trajectories, including approach and exit, and the fixed E1 strip.
p0=np.array([445,395]);p1=np.array([487,345]);v=p1-p0;unit=v/np.linalg.norm(v);normal=np.array([-unit[1],unit[0]])
band=np.array([p0+12.5*normal,p1+12.5*normal,p1-12.5*normal,p0-12.5*normal])
fig,axes=plt.subplots(1,3,figsize=(6.8,3.0),sharex=True,sharey=True,layout='constrained')
for ax,g in zip(axes,['R','T','C']):
    ax.add_patch(Polygon(band,facecolor='#dce8dc',edgecolor='gray',alpha=.5))
    for _,r in e1[e1.method==g].iterrows():
        s=trace('E1',r.label,'pose');s=s[(s.time_s>=0)&(s.time_s<=r.evaluation_end_s)]
        ax.plot(s.x,s.y,lw=.85,alpha=.8);ax.scatter([s.x.iloc[0]],[s.y.iloc[0]],s=9,color='black')
    ax.set_title(g);ax.set_xlabel('Base X (mm)');ax.set_aspect('equal',adjustable='box')
axes[0].set_ylabel('Base Y (mm)')
save(fig,'e1_xy_all','fig:e1_xy_all',['data/traces/E1_*_pose.csv'],'Chapter 7',
     'All 15 measured XY paths; full observed approach/pass/exit extent; shaded geometric evaluation band, not a measured footprint')

# Main E1 metrics include incomplete trials visibly, with no imputed time.
fig,axes=plt.subplots(1,2,figsize=(6.6,3.2),layout='constrained')
for i,g in enumerate(['R','T','C']):
    p=e1[e1.method==g];dx=np.linspace(-.14,.14,len(p))
    for j,(_,r) in enumerate(p.iterrows()):
        ok=np.isfinite(r.completion_time_s)
        axes[0].scatter(i+dx[j],r.completion_time_s if ok else r.evaluation_end_s,
                         marker='o' if ok else 'x',s=35,color=colors[g])
        axes[1].scatter(i+dx[j],r.J_excess_Ns,s=28,color=colors[g])
    y=p.completion_time_s.dropna()
    axes[0].errorbar(i,y.mean(),yerr=y.std(ddof=1),fmt='_',color='black',capsize=4)
    axes[0].text(i,38,f'{len(y)}/5',ha='center',fontsize=9)
for ax in axes:ax.set_xticks(range(3),['R','T','C']);ax.set_xlim(-.5,2.5)
axes[0].set_ylabel('Completion or last observation (s)');axes[0].set_ylim(0,41)
axes[0].set_title('Circles: completed; crosses: incomplete',fontsize=8)
axes[1].set_ylabel('$J_{\\mathrm{excess}}$ (N s)');axes[1].set_ylim(bottom=-.15)
save(fig,'e1_primary_metrics','fig:e1_primary_metrics',['data/e1_runs.csv'],'Chapter 7',
     'All 15 points; incomplete completion times remain missing; crosses show archived observation end only; mean/sample SD for completed times')

h=pd.read_csv(D/'e1_height_reference_replay.csv')
fig,ax=plt.subplots(figsize=(6.7,3.2),layout='constrained')
x=np.arange(len(h))
ax.scatter(x,h.A_release_threshold_mm,label='Original: initial contact reference +5 mm',marker='x',s=35)
ax.scatter(x,h.B_release_threshold_mm,label='Replay: loaded-pass reference +5 mm',marker='o',s=20)
ax.set_xticks(x,h.report_label,rotation=45);ax.set_ylabel('Base Z release threshold (mm)')
ax.legend(fontsize=8);ax.set_ylim(bottom=170)
save(fig,'e1_height_reference','fig:e1_height_reference',['data/e1_height_reference_replay.csv'],
     'Chapter 7','Both archived height thresholds for every run; no change to measured trajectories; not new robot trials')

fig,axes=plt.subplots(1,3,figsize=(7,3.1),layout='constrained')
for i,g in enumerate(['A','B','C']):
    p=e2[e2.condition==g];dx=np.linspace(-.14,.14,5)
    for j,(_,r) in enumerate(p.iterrows()):
        ok=np.isfinite(r.completion_time_corrected_s)
        axes[0].scatter(i+dx[j],r.execution_duration_s,marker='o' if ok else 'x',s=35,
                        color=colors[g])
        if not ok:axes[0].annotate('A4 stop',(i+dx[j],r.execution_duration_s),xytext=(7,0),textcoords='offset points',fontsize=7)
        axes[1].scatter(i+dx[j],r.peak_fz_N,s=24,color=colors[g])
        axes[2].scatter(i+dx[j],r.tcp_xy_path_mm,s=24,color=colors[g])
    y=p.completion_time_corrected_s.dropna()
    axes[0].errorbar(i,y.mean(),yerr=y.std(ddof=1),fmt='_',color='black',capsize=3)
for ax in axes:ax.set_xticks(range(3),['A','B','C']);ax.set_xlim(-.5,2.5)
axes[0].set_ylabel('Completion / interruption (s)');axes[0].set_ylim(0,33)
axes[1].set_ylabel('Measured peak $F_z^B$ (N)');axes[1].set_ylim(0,37)
axes[2].set_ylabel('Measured XY travel (mm)');axes[2].set_ylim(0,370)
save(fig,'e2_primary_metrics','fig:e2_primary_metrics',['data/e2_runs_corrected.csv'],'Chapter 7',
     'All 15 attempts; A4 marked as interruption; time mean/sample SD use A completed 4, B/C 5; force/travel include A4')

fig,axes=plt.subplots(2,2,figsize=(6.6,4.6),sharex='col',layout='constrained')
for j,label in enumerate(['A4','B4']):
    force=trace('E2',label,'force');pose=trace('E2',label,'pose')
    r=e2[e2.label==label].iloc[0];end=r.execution_duration_s
    for df in [force,pose]: df.drop(df[(df.time_s<0)|(df.time_s>end)].index,inplace=True)
    axes[0,j].step(force.time_s,force.fz,where='post',color=colors[label[0]],lw=1)
    axes[1,j].plot(pose.time_s,pose.z,color=colors[label[0]],lw=1)
    axes[0,j].set_title(label+(' — operator stopped' if label=='A4' else ' — gate transitions: 38'),fontsize=9)
    axes[1,j].set_xlabel('Time from execution start (s)')
axes[0,0].set_ylabel('Measured $F_z^B$ (N)');axes[1,0].set_ylabel('Measured base Z (mm)')
save(fig,'e2_transition_cases','fig:e2_transition_cases',
     ['data/traces/E2_A4_force.csv','data/traces/E2_A4_pose.csv','data/traces/E2_B4_force.csv','data/traces/E2_B4_pose.csv'],
     'Chapter 7','A4 retained on operator-corrected outcome; B4 chosen for maximum recorded gate transition count; full intervals, no smoothing')

demo=pd.read_csv(D/'teaching_episode29.csv')
fig,axes=plt.subplots(3,1,figsize=(6.5,5.4),sharex=True,layout='constrained')
axes[0].plot(demo.time_s,demo.x_rel_mm,label='X relative');axes[0].plot(demo.time_s,demo.y_rel_mm,label='Y relative')
axes[0].set_ylabel('Position (mm)');axes[0].legend(fontsize=8,ncols=2)
axes[1].plot(demo.time_s,demo.z_mm,color='#555555');axes[1].axhline(175,ls=':',color='black',lw=.8)
axes[1].set_ylabel('Stored Z (mm)')
for j,name in enumerate(['fx','fy','fz']):axes[2].plot(demo.time_s,demo[name+'_cleanup_N'],label=name,lw=1)
axes[2].set_ylabel('Native force (N)');axes[2].legend(ncols=3,fontsize=8)
axes[-1].set_xlabel('Original paired source time (s)')
save(fig,'teaching_motion_force','fig:teaching_motion_force',['data/teaching_episode29.csv'],'Chapter 4',
     'Actual episode29 on its preserved original source receipt-time axis; no smoothing beyond the archived dataset preprocessing')

fig,axes=plt.subplots(2,1,figsize=(6.5,4.2),sharex=True,layout='constrained')
for col,label in [('fz_raw_published_N','Published, before offline EMA'),('fz_ema_N','EMA before cleanup'),
                  ('fz_cleanup_N','Learning cleanup')]:
    axes[0].plot(demo.time_s,demo[col],label=label,lw=.9)
axes[0].set_ylabel('Native Fz (N)');axes[0].legend(fontsize=7,ncols=1)
axes[1].plot(demo.time_s,demo.fz_base_N,lw=1,label='Cleanup full vector rotated to base')
axes[1].set_ylabel('Base Fz (N)');axes[1].set_xlabel('Original paired source time (s)');axes[1].legend(fontsize=8)
save(fig,'force_processing','fig:force_processing',['data/teaching_episode29.csv'],'Chapter 4',
     'Archived post-publisher raw, offline EMA, cleanup, and full three-axis pose rotation; no duplicate bias/gravity corrections')

dataset=pd.read_csv(D/'dataset_episodes.csv')
fig,ax=plt.subplots(figsize=(6.5,2.9),layout='constrained')
dataset['number']=dataset.episode.str.extract(r'(\d+)').astype(int);dataset.sort_values('number',inplace=True)
ax.bar(dataset.number,dataset.frames,color=['#b16b24' if x=='validation' else '#326b93' for x in dataset.split],width=.8)
ax.set_xlabel('Episode index');ax.set_ylabel('Stored paired frames');ax.set_xticks(range(0,42,5))
ax.text(.02,.96,'Blue: optimization train (38); orange: validation (4)',ha='left',va='top',transform=ax.transAxes,fontsize=8)
save(fig,'dataset_split','fig:dataset_split',['data/dataset_episodes.csv'],'Chapter 4',
     'All 42 episode lengths; episode-level split; not windows counted as independent trials')

fig,axes=plt.subplots(3,2,figsize=(6.6,5),layout='constrained')
for i,method in enumerate(['R','T','C']):
    for j,phase in enumerate(['initial','final']):
        axes[i,j].imshow(plt.imread(F/f'E1_{method}1_{phase}.png'))
        axes[i,j].set_title(f'{method}1 — {phase} snapshot',fontsize=9);axes[i,j].axis('off')
save(fig,'e1_snapshot_panel','fig:e1_photos',
     [f'figures/E1_{m}1_{p}.png' for m in ['R','T','C'] for p in ['initial','final']],
     'Chapter 7','Full provider snapshot images in a panel; first run per method; acquisition viewpoints/timing not matched for metrology')

fig,axes=plt.subplots(2,2,figsize=(6.6,4.0),layout='constrained')
seq=[x for x in manifest if x['figure_id']=='fig:e2_sequence']
for ax,entry in zip(axes.flat,seq):
    pixels=plt.imread(ROOT/entry['output'])
    # Preserve the complete camera pane; omit the adjacent diagnostic bars.
    # The full decoded frame remains in the project and in the manifest.
    camera=pixels[:,:pixels.shape[1]//2]
    ax.imshow(camera);ax.axis('off')
    ax.set_title(f'Video offset {entry["video_offset_s"]:.2f} s',fontsize=9)
save(fig,'e2_sequence','fig:e2_sequence',[x['output'] for x in seq],'Chapter 7',
     'Uniform video-relative offsets; left camera pane cropped at exactly half full-frame width; original camera overlays preserved; full decoded frames bundled')

concepts=[('fig:faire_architecture','chapters/03_problem_system.tex','Chapter 3'),
          ('fig:demo_transfer','chapters/04_demonstration_dataset.tex','Chapter 4'),
          ('fig:force_history_policy','chapters/05_skill_learning.tex','Chapter 5'),
          ('fig:execution_architecture','chapters/06_execution_evaluation.tex','Chapter 6')]
for fid,src,chapter in concepts:
    if not any(x['figure_id']==fid for x in manifest):
        manifest.append(dict(figure_id=fid,output=src,sources=[src],location=chapter,
                             processing='editable TikZ conceptual diagram derived from documented implementation',
                             type='conceptual; not measured'))

(ROOT/'figure_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print('Generated measured figures from bundled CSV extracts; original experiments were not opened for writing.')
