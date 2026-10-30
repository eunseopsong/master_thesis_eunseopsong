#!/usr/bin/env python3
"""Draw a picture-first English block diagram of the existing XY adapter.

Reuses the previously checked implementation. No ROS, robot, dataset, checkpoint,
or experiment is executed. The drawn point clouds and paths are schematic.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import re
import tempfile

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'stain_frame_diagram_mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Ellipse, Circle
import numpy as np

ROOT = Path(__file__).resolve().parent
BASE = 'stain_relative_frame_block_diagram'
SOURCES = {
    'behavior_ws/src/stain_relative_frame/stain_relative_frame/stain_detect.py': ['dark_cloud_origin'],
    'behavior_ws/src/stain_relative_frame/stain_relative_frame/inference_adapter.py': ['_on_origin'],
    'behavior_ws/src/stain_relative_frame/stain_relative_frame/relative_frame.py': ['to_relative', 'to_absolute'],
    'behavior_ws/src/stain_relative_frame/stain_relative_frame/dataset_relativize.py': ['convert_episode'],
    'behavior_ws/src/nrs_imitation/nrs_imitation/inference_core.py': [
        '_wrap_axis_delta', '_canon_setup', '_canon_obs_pose6', '_canon_rotate_image',
        '_canon_cmd_seq', '_srf_observation_pose6', '_srf_command_seq'],
}
C = dict(ink='#172C42', muted='#7F8DA0', line='#DCE5ED', blue='#2677B7',
         teal='#16897F', purple='#8056B5', pink='#CF4C87', faint='#F5F8FB',
         pale_blue='#EDF5FB', pale_purple='#F5F0FC')
THETA = math.radians(34)  # Illustration angle, not a measured/reference setting.
R = lambda angle: np.array([[math.cos(angle), -math.sin(angle)],
                            [math.sin(angle), math.cos(angle)]])
# A fixed schematic stroke; not a trajectory sampled from an experiment.
STROKE = np.array([[-.90,-.11],[.86,-.07],[-.77,-.02],[.80,.03],[-.65,.08],[.70,.13]])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT)
    parser.add_argument('--repo', type=Path, default=Path.home()/'nrs_imitation')
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans', 'mathtext.fontset':'dejavusans',
                         'svg.fonttype':'path', 'pdf.fonttype':42, 'axes.unicode_minus':False})
    fig=plt.figure(figsize=(16,9),facecolor='white')
    ax=fig.add_axes([0,0,1,1])
    ax.set(xlim=(0,16),ylim=(9,0));ax.axis('off')
    texts=[]

    def text(x,y,s,size=16,color=None,weight='normal',ha='center',va='center'):
        assert not re.search('[\uac00-\ud7a3]',s), s
        t=ax.text(x,y,s,fontsize=size,color=color or C['ink'],fontweight=weight,
                  ha=ha,va=va,zorder=12)
        texts.append(t);return t

    def rounded(x,y,w,h,fill='white',edge=None,lw=1,r=.14,dash=False,z=1):
        p=FancyBboxPatch((x,y),w,h,boxstyle=f'round,pad=0,rounding_size={r}',
                        facecolor=fill,edgecolor=edge or C['line'],linewidth=lw,
                        linestyle=(0,(4,3)) if dash else '-',zorder=z)
        ax.add_patch(p);return p

    def arrow(a,b,color=None,lw=1.7,head=12,dash=False,curve=None,z=8):
        kw=dict(arrowstyle='-|>',mutation_scale=head,color=color or C['muted'],
                linewidth=lw,shrinkA=0,shrinkB=0,
                linestyle=(0,(4,3)) if dash else '-',zorder=z)
        if curve is not None:kw['connectionstyle']=f'arc3,rad={curve}'
        ax.add_patch(FancyArrowPatch(a,b,**kw))

    def plot(points,color,lw=1.4,alpha=1,dash=False,z=5):
        a=np.asarray(points)
        ax.plot(a[:,0],a[:,1],color=color,lw=lw,alpha=alpha,
                linestyle=(0,(3,3)) if dash else '-',zorder=z,
                solid_capstyle='round',solid_joinstyle='round')

    def screen(points,cx,cy,scale=1):
        points=np.atleast_2d(points).copy()
        return np.c_[cx+points[:,0]*scale,cy-points[:,1]*scale]

    def axes(cx,cy,scale=.88,origin=(0,0),labels=False,extent=1.10):
        o=np.array(origin)
        for endpoint in [o+[extent,0],o+[0,extent]]:
            a,b=screen([o,endpoint],cx,cy,scale)
            arrow(a,b,color='#B3C0CE',lw=1.15,head=8,z=3)
        if labels:
            xx=screen([o+[extent+.10,0]],cx,cy,scale)[0]
            yy=screen([o+[0,extent+.12]],cx,cy,scale)[0]
            text(*xx,'X',size=10.2,color=C['muted'])
            text(*yy,'Y',size=10.2,color=C['muted'])

    def grid(cx,cy,scale=.88,origin=(0,0),faint=True):
        for value in [-.8,-.4,0,.4,.8]:
            for points in [np.array([[-1.05,value],[1.05,value]]),
                           np.array([[value,-.80],[value,.80]])]:
                plot(screen(points,cx,cy,scale),C['line'],lw=.7,alpha=.52 if faint else .8,z=2)
        axes(cx,cy,scale,origin,labels=True,extent=1.14 if origin==(0,0) else 1.85)

    def center_dot(x,y,color=None,size=.065):
        color=color or C['blue']
        ax.add_patch(Circle((x,y),size*1.9,facecolor='white',edgecolor='white',lw=2,zorder=8))
        ax.add_patch(Circle((x,y),size,facecolor=color,edgecolor='white',lw=.8,zorder=10))
        for a,b in [((x-.17,y),(x+.17,y)),((x,y-.17),(x,y+.17))]:
            plot([a,b],color,lw=1.0,z=9)

    def stain(cx,cy,scale=.88,center=(0,0),angle=0,ghost=False,points=True,axis=True):
        c=np.asarray(center)
        xy=screen([c],cx,cy,scale)[0]
        col='#BDCCDB' if ghost else C['blue']
        ax.add_patch(Ellipse(xy,1.97*scale,.57*scale,angle=-math.degrees(angle),
                             facecolor='none' if ghost else '#D6EAF7',edgecolor=col,
                             linestyle=(0,(4,3)) if ghost else '-',linewidth=1.4,
                             alpha=.55 if ghost else .9,zorder=4))
        if points and not ghost:
            # Deterministic schematic geometry, with no experimental values.
            for i in range(43):
                x=.88*math.sin(i*2.39996)
                y=.18*math.sin(i*1.791)*math.sqrt(max(0,1-(x/.97)**2))
                q=R(angle)@np.array([x,y])+c
                px,py=screen([q],cx,cy,scale)[0]
                ax.add_patch(Circle((px,py),.018,color=col,alpha=.35,zorder=5))
        if axis:
            line=np.array([[-1.15,0],[1.15,0]])@R(angle).T+c
            plot(screen(line,cx,cy,scale),col,lw=1.3,dash=True,z=6)
        if not ghost:center_dot(*xy)

    def trajectory(cx,cy,scale=.88,center=(0,0),angle=0,lw=2.7,color=None):
        points=STROKE@R(angle).T+np.asarray(center)
        p=screen(points,cx,cy,scale)
        plot(p,'white',lw=lw+2,z=9)
        plot(p,color or C['pink'],lw=lw,z=10)
        ax.add_patch(Circle(p[0],.037,facecolor='white',edgecolor=color or C['pink'],lw=1.3,zorder=11))
        arrow(p[-2],p[-1],color=color or C['pink'],lw=lw,head=9,z=11)

    def camera(cx,cy,scale=1,color=None):
        color=color or C['blue']
        rounded(cx-.26*scale,cy-.16*scale,.52*scale,.32*scale,fill='white',edge=color,lw=1.3,r=.045*scale,z=8)
        ax.add_patch(Circle((cx,cy),.085*scale,facecolor='white',edgecolor=color,lw=1.2,zorder=9))
        rounded(cx-.16*scale,cy-.22*scale,.15*scale,.08*scale,fill=color,edge=color,r=.02,z=8)

    def waveform(cx,cy,width=.65,height=.23,color=None):
        x=np.linspace(-width/2,width/2,70)
        y=.65*height*np.exp(-(x/(width*.27))**2)*np.sin(x/width*14)
        plot(np.c_[cx+x,cy-y],color or C['teal'],lw=1.6,z=9)

    # One title, no explanatory paragraph.
    text(.52,.62,'Stain-Relative Coordinates',size=27,weight='bold',ha='left')
    ax.plot([.52,15.48],[1.05,1.05],color=C['line'],lw=1)

    # Small, graphical center-only training branch.
    rounded(5.52,1.30,6.35,1.18,fill='#F3FAF7',edge='#E0EEE8',r=.14)
    text(6.00,1.54,'Train',size=12.5,color=C['teal'],weight='bold')
    axes(7.02,1.91,.42,origin=(-1.0,-.50),labels=False,extent=1.9)
    trajectory(7.02,1.91,.43,center=(.35,.20),angle=0,lw=1.7,color=C['teal'])
    center_dot(7.02+.35*.43,1.91-.20*.43,C['teal'],size=.035)
    arrow((7.76,1.86),(8.23,1.86),C['teal'],head=10)
    text(7.995,1.52,r'$-c_{\mathrm{demo}}$',size=12.3,color=C['teal'])
    axes(8.89,1.91,.42,labels=False,extent=1.05)
    trajectory(8.89,1.91,.43,lw=1.7,color=C['teal'])
    arrow((9.55,1.86),(10.13,1.86),C['teal'],head=10)
    rounded(10.30,1.49,1.39,.75,fill=C['pale_purple'],edge=C['purple'],lw=1.2,r=.10)
    for i in range(4):
        for j in range(3):
            ax.add_patch(Circle((10.57+i*.26,1.68+j*.18),.045,
                                facecolor=C['purple'],edgecolor='none',alpha=.35+.15*((i+j)%3),zorder=5))
    arrow((11.08,2.48),(11.08,3.02),C['teal'],lw=1.55,head=12,dash=True)

    positions=[.46,3.54,6.62,9.70,12.78]
    w,y,h=2.76,3.05,4.37
    titles=['Detect','Center','Align','Generate','Restore']
    colors=[C['blue'],C['blue'],C['purple'],C['purple'],C['pink']]
    for x,title,color in zip(positions,titles,colors):
        rounded(x,y,w,h,fill='white',edge=C['line'],lw=1.15,r=.16)
        ax.plot([x+.22,x+w-.22],[y+.025,y+.025],color=color,lw=3,zorder=2)
        text(x+w/2,3.49,title,size=20,weight='bold',color=color)
    for x in positions[:-1]:
        arrow((x+w+.045,5.17),(x+3.08-.045,5.17),head=12)

    # 1: task registration in base XY; center and axis are frozen later.
    cx=positions[0]+w/2;cy=5.27
    rounded(positions[0]+.18,4.04,w-.36,2.32,fill=C['faint'],edge='#E4EBF2',r=.08)
    grid(cx,cy,.90,origin=(-.99,-.73))
    stain(cx,cy,.90,center=(.18,.06),angle=THETA)
    camera(positions[0]+.50,4.24,.70)
    cp=screen([[.18,.06]],cx,cy,.90)[0]
    arc=[cp+[.36*math.cos(a),-.36*math.sin(a)] for a in np.linspace(0,THETA,24)]
    plot(arc,C['purple'],lw=1.2,z=7)
    text(cp[0]+.49,cp[1]-.14,r'$\theta$',size=13.8,color=C['purple'])
    text(cx,6.92,r'$c,\;\theta_{\mathrm{live}}$',size=18,color=C['blue'])

    # 2: identical strip orientation, translated to the origin.
    cx=positions[1]+w/2
    grid(cx,cy,.90)
    stain(cx,cy,.90,angle=THETA)
    ghost=screen([[.65,.57]],cx,cy,.9)[0]
    ax.add_patch(Circle(ghost,.052,facecolor='white',edgecolor=C['muted'],lw=1.1,zorder=8))
    arrow(ghost+[-.05,.04],(cx+.13,cy-.12),C['teal'],lw=1.5,head=10)
    text(ghost[0]-.17,ghost[1]-.28,r'$-c$',size=14,color=C['teal'])
    text(cx-.13,cy+.25,'0',size=10,color=C['muted'])
    text(cx,6.92,r'$p_{xy}-c$',size=18,color=C['blue'])

    # 3: optional direction adapter; reference angle is shown schematically.
    cx=positions[2]+w/2
    grid(cx,cy,.90)
    stain(cx,cy,.90,angle=THETA,ghost=True,points=False)
    stain(cx,cy,.90,angle=0)
    a=screen([[.98*math.cos(THETA),.98*math.sin(THETA)]],cx,cy,.9)[0]
    b=screen([[.98,0]],cx,cy,.9)[0]
    arrow(a,b,C['purple'],curve=-.30,lw=1.9,head=11)
    text(cx+.94,cy-.39,r'$\alpha$',size=17,color=C['purple'])
    text(cx,3.92,'Optional',size=11.7,color=C['muted'])
    text(cx,6.98,r'$R(\alpha)$',size=18,color=C['purple'])
    # Tiny RGB rotation glyph retains its role without a sentence.
    camera(cx-.63,6.31,.50,C['muted'])
    arrow((cx-.39,6.26),(cx-.22,6.41),C['muted'],curve=-.5,lw=1.0,head=7)

    # 4: image/state/force cues condition the same policy, then a local path is generated.
    cx=positions[3]+w/2
    rounded(cx-.68,4.49,1.36,.72,fill=C['pale_purple'],edge=C['purple'],lw=1.25,r=.10)
    text(cx,4.85,'Flow',size=18,color=C['purple'],weight='bold')
    camera(cx-.82,4.04,.65)
    text(cx,4.04,r'$q$',size=17,color=C['muted'])
    waveform(cx+.82,4.04,width=.51,height=.17)
    for offset in [-.67,0,.67]:
        arrow((cx+offset,4.25),(cx+offset*.65,4.46),C['muted'],lw=.9,head=7)
    arrow((cx,5.26),(cx,5.60),C['purple'],lw=1.5,head=10)
    stain(cx,6.02,.81,angle=0,points=False,axis=False)
    trajectory(cx,6.02,.81)
    text(cx,6.98,r'$\widehat{u},\;z,\;\rho,\;F^*$',size=17.5,color=C['purple'])

    # 5: inverse XY rotation followed by the original live center addition.
    cx=positions[4]+w/2
    grid(cx,cy,.90,origin=(-.99,-.73))
    stain(cx,cy,.90,center=(.18,.06),angle=THETA,points=False)
    trajectory(cx,cy,.90,center=(.18,.06),angle=THETA)
    text(cx,6.94,r'$R(-\alpha)\widehat{u}+c$',size=17.2,color=C['pink'])

    # A visual brace identifies the shared registration of the transform pair.
    ax.plot([4.92,4.92,14.16,14.16],[7.59,7.91,7.91,7.59],color=C['line'],lw=1.4,zorder=2)
    rounded(8.80,7.73,1.20,.35,fill='white',edge='white',r=0,lw=0,z=3)
    text(9.40,7.91,r'$c,\;\alpha$',size=14.3,color=C['muted'])
    text(.52,8.50,'XY only',size=13,color=C['muted'],weight='bold',ha='left')
    text(15.48,8.50,r'$z,\;\rho,\;F$ unchanged',size=12.3,color=C['muted'],ha='right')

    fig.canvas.draw();renderer=fig.canvas.get_renderer();bounds=fig.bbox
    for t in texts:
        bb=t.get_window_extent(renderer)
        assert bb.x0>=bounds.x0 and bb.y0>=bounds.y0 and bb.x1<=bounds.x1 and bb.y1<=bounds.y1,t.get_text()
    for ext in ['png','svg','pdf']:
        path=args.output_dir/(BASE+'.'+ext)
        metadata={'Title':'Stain-Relative Coordinates','Description':'English picture-first implementation schematic; illustrated geometry is not experimental data.'} if ext=='svg' else None
        fig.savefig(path,dpi=240,facecolor='white',metadata=metadata)
        print(path)
    plt.close(fig)
    source_records=[]
    for relative,functions in SOURCES.items():
        f=args.repo/relative
        source_records.append(dict(path=str(f),functions=functions,
                            sha256=hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None))
    record=dict(date='2026-10-18',figure_id=BASE,revision='English, picture-first',
                kind='implementation schematic',aspect_ratio='16:9',png_pixels=[3840,2160],
                sources=source_records,
                existing_evidence_reused=True,new_model_or_experiment_analysis=False,
                drawing='Illustrative point cloud, strip angle and strokes; no experimental values or trajectories.',
                scope='Center-only training; optional inference XY/image alignment; inverse XY restoration.',
                exclusions='Z/orientation/force are not rotated by this XY adapter; no measured generalization claim; E1/E2 alignment was OFF.',
                mathematical_notes=dict(alpha='wrap_pi(theta_ref - theta_live)',
                                        wrap_pi='((delta + pi/2) mod pi) - pi/2',
                                        c='Frozen live stain center; same c and alpha in forward/inverse transforms.'),
                unchanged='Robot code, model, dataset, experimental log and thesis source/PDF.',
                visible_text=[t.get_text() for t in texts],
                outputs={ext:hashlib.sha256((args.output_dir/(BASE+'.'+ext)).read_bytes()).hexdigest() for ext in ['png','svg','pdf']})
    (args.output_dir/(BASE+'_provenance.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
