#!/usr/bin/env python3
"""Update E1/C6 plots and E1 photographs only; retain valid E2/method assets."""
from pathlib import Path
import json,os,shutil
P=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(P/'.mplconfig'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from PIL import Image
import numpy as np
import pandas as pd

D=P/'data';F=P/'figures';e1=pd.read_csv(D/'e1_runs.csv')
manifest=json.loads((P/'figure_manifest.json').read_text())
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,
    'axes.spines.right':False,'pdf.fonttype':42,'axes.grid':True,'grid.alpha':.18,'savefig.bbox':'tight'})
colors={'R':'#326b93','T':'#b16b24','C':'#40816b'}


def save(fig,name,label,description,run_ids=None,sources=None,location='Chapter 7'):
    fig.savefig(F/(name+'.pdf'));fig.savefig(F/(name+'.png'),dpi=150);plt.close(fig)
    global manifest
    manifest=[x for x in manifest if x.get('output')!='figures/'+name+'.pdf']
    manifest.append(dict(figure_id=label,output='figures/'+name+'.pdf',sources=sources or ['data/e1_runs.csv'],
        run_ids=run_ids or e1.run_id.tolist(),cohort='E1_CT_pass_height_v2_nominal_dev_20261015',
        processing=description,location=location,generated_plot=True,
        provenance='data/cohort_manifest.json; provenance/results_20261016/source_files.json'))


def trace(label,kind):
    return pd.read_csv(D/'traces'/f'E1_{label}_{kind}.csv')


def bounded(frame,end,columns,force=False):
    t=frame.time_s.to_numpy();values=frame[columns].to_numpy()
    inner=t[(t>0)&(t<end)];edges=np.r_[0,inner,end]
    if force:
        out=values[np.clip(np.searchsorted(t,edges,side='right')-1,0,len(t)-1)]
    else:out=np.column_stack([np.interp(edges,t,values[:,i]) for i in range(len(columns))])
    return edges,out


fig,axes=plt.subplots(1,2,figsize=(6.6,3.1),layout='constrained')
for i,method in enumerate('RTC'):
    part=e1[e1.method==method].sort_values('repeat_index')
    for ax,key in zip(axes,['completion_time_s','J_excess_Ns']):
        values=part[key].to_numpy();x=i+np.linspace(-.13,.13,5)
        ax.scatter(x,values,color=colors[method],s=29,zorder=3)
        ax.errorbar(i+.20,values.mean(),yerr=values.std(ddof=1),fmt='D',color='black',ms=3.2,capsize=3,zorder=4)
        if method=='C':ax.annotate('C5',(x[-1],values[-1]),xytext=(-19,9),textcoords='offset points',fontsize=8)
    axes[0].text(i,31,'5/5',ha='center',fontsize=8)
for ax in axes:ax.set_xticks(range(3),list('RTC'));ax.set_xlim(-.5,2.5)
axes[0].set_ylim(0,33);axes[0].set_ylabel('First procedural completion (s)')
axes[1].set_ylabel(r'$J_{\mathrm{excess}}$ (N s)')
save(fig,'e1_primary_metrics','fig:e1_primary_metrics','Original planned 15 runs only; all individual points and mean/sample SD for both metrics; C5 retained; C6 excluded')

fig,axes=plt.subplots(3,1,figsize=(6.5,5.7),sharex=True,sharey=True,layout='constrained')
for ax,method in zip(axes,'RTC'):
    for _,r in e1[e1.method==method].sort_values('repeat_index').iterrows():
        t,y=bounded(trace(r.label,'force'),r.evaluation_end_s,['fz'],True)
        ax.step(t,y[:,0],where='post',lw=1.1 if r.label=='C5' else .8,label=r.label,alpha=.85)
    ax.axhline(30.812396273,color='black',ls='--',lw=.75,label='Teaching Q95')
    ax.set_ylabel(method+r'  $F_z^B$ (N)');ax.legend(ncols=6,fontsize=8.5,loc='upper right')
axes[-1].set_xlabel('Time from execution start (s)')
save(fig,'e1_force_all','fig:e1_force_all','All five original runs per method; actual receipt-event force, ZOH to first completion; no smoothing, clipping, force correction or cached-command resampling',
    sources=['data/traces/E1_'+r.label+'_force.csv' for _,r in e1.iterrows()])

p0=np.array([445,395]);p1=np.array([487,345]);d=(p1-p0)/np.linalg.norm(p1-p0);n=np.array([-d[1],d[0]])
band=np.array([p0+12.5*n,p1+12.5*n,p1-12.5*n,p0-12.5*n])
fig,axes=plt.subplots(1,3,figsize=(6.8,3.1),sharex=True,sharey=True,layout='constrained')
for ax,method in zip(axes,'RTC'):
    ax.add_patch(Polygon(band,facecolor='#dce8dc',edgecolor='gray',alpha=.5))
    for _,r in e1[e1.method==method].sort_values('repeat_index').iterrows():
        t,y=bounded(trace(r.label,'pose'),r.evaluation_end_s,['x','y'])
        line=ax.plot(y[:,0],y[:,1],lw=.85,label=r.label,alpha=.85)[0]
        ax.scatter(y[-1,0],y[-1,1],s=12,marker='s',color=line.get_color())
    ax.set_title(method);ax.set_xlabel('Base X (mm)');ax.set_aspect('equal',adjustable='box');ax.legend(fontsize=8.5,ncols=2)
axes[0].set_ylabel('Base Y (mm)')
save(fig,'e1_xy_all','fig:e1_xy_all','All 15 actual receipt trajectories through first completion; same fixed 25 mm evaluation band; no fit to trajectories',
    sources=['data/traces/E1_'+r.label+'_pose.csv' for _,r in e1.iterrows()])

diag=pd.read_csv(D/'e1_c5_c6.csv');fig,axes=plt.subplots(2,2,figsize=(6.7,4.8),sharex='col',sharey='row',layout='constrained')
for j,label in enumerate(['C5','C6']):
    r=diag[diag.label==label].iloc[0]
    t,y=bounded(trace(label,'force'),r.evaluation_end_s,['fz'],True)
    axes[0,j].step(t,y[:,0],where='post',color=colors['C'],lw=.9)
    axes[0,j].axhline(30.812396273,color='black',ls='--',lw=.7)
    t,y=bounded(trace(label,'pose'),r.evaluation_end_s,['z']);axes[1,j].plot(t,y[:,0],color=colors['C'],lw=.9)
    axes[1,j].axhline(r.z_release_threshold_mm,color='gray',ls='--',lw=.7)
    for ax in axes[:,j]:
        for key,style,color in [('contact_at_s',':','#777777'),('pass_completed_at_s','--','#326b93'),('completion_time_s','-','#b16b24')]:
            ax.axvline(r[key],ls=style,color=color,lw=.8)
        ax.set_xlim(0,19)
    axes[0,j].set_title(label+(' (primary)' if label=='C5' else ' (additional diagnostic)'),fontsize=9)
    axes[1,j].set_xlabel('Time from execution start (s)')
axes[0,0].set_ylabel(r'Measured $F_z^B$ (N)');axes[1,0].set_ylabel('Measured base Z (mm)')
save(fig,'e1_c5_c6','fig:e1_c5_c6','Original C5 and additional C6 shown separately, full first-completion windows; vertical lines: confirmed contact, required pass, first completion; no pooled mean',
    run_ids=diag.run_id.tolist(),sources=['data/e1_c5_c6.csv']+[f'data/traces/E1_{x}_{k}.csv' for x in ['C5','C6'] for k in ['force','pose']])

# Only update E1 photographs; E2 photographs and video crops are retained.
photos=[]
for method in 'RTC':
    r=e1[e1.label==method+'1'].iloc[0]
    for phase in ['initial','final']:
        dst=F/f'E1_{method}1_{phase}.png'
        existing=next((x for x in manifest if x.get('output')==str(dst.relative_to(P)) and x.get('run_id')==r.run_id),None)
        if existing and dst.is_file():
            src=Path(existing['sources'][0])  # Provenance only; bundled pixels suffice.
        else:
            folder=next((Path(r.run_directory)/'provider').iterdir())/'snapshots'
            src=folder/(phase+'_image.png');assert src.is_file(),src
            shutil.copyfile(src,dst)
        photos.append((method,phase,dst,src,r.run_id))
        manifest=[x for x in manifest if x.get('output')!=str(dst.relative_to(P))]
        manifest.append(dict(figure_id='fig:e1_photos',output=str(dst.relative_to(P)),sources=[str(src)],run_id=r.run_id,
            cohort='E1_CT_pass_height_v2_nominal_dev_20261015',selection='First original planned run per method; no outcome screening',
            processing='Copied original snapshot without pixel editing',location='Chapter 7',timing='Provider snapshot; not matched surface metrology'))
fig,axes=plt.subplots(3,2,figsize=(6.7,6.1),layout='constrained')
for i,method in enumerate('RTC'):
    for j,phase in enumerate(['initial','final']):
        dst=next(x[2] for x in photos if x[0]==method and x[1]==phase)
        axes[i,j].imshow(Image.open(dst));axes[i,j].axis('off');axes[i,j].set_title(method+'1 '+phase,fontsize=9)
save(fig,'e1_snapshot_panel','fig:e1_photos','Full initial/final snapshots from the first planned run per method on 15 October; different times/viewpoints; no image-derived removal measurement',
    run_ids=[x[4] for x in photos],sources=[str(x[2].relative_to(P)) for x in photos])
for item in manifest:
    if item.get('figure_id')=='fig:e1_height_reference':
        item['location']='Appendix B; historical 14 October cohort only'
    if item.get('figure_id')=='fig:diagnostic_heatmap':
        item['location']='Chapter 8; historical 14 October E1 C1 diagnostic'
(P/'figure_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print('Updated five E1 plot assets and six E1 source snapshots; E2/method figures retained.')
