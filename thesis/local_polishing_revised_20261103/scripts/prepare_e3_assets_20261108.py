#!/usr/bin/env python3
"""Rebuild display panels from selected real RGB files and frozen masks.

No inpainting, segmentation edits, smoothing, or image synthesis. The common
native-pixel crop is identical before/after and across every displayed run.
Use --research-root only to copy the seven figure pairs from the read-only
archive; ordinary regeneration uses bundled manuscript assets.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
os.environ.setdefault('MPLCONFIGDIR','/tmp/thesis_matplotlib_20261108')
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

P=Path(__file__).resolve().parents[1]
V=P/'provenance/results_20261108'
F=P/'figures'
N=F/'e3_native'
LABELS=['N-1','P1-1','D1-1','D2-1','D2-3','D1-4','P2-1']
CROP=[175,39,325,135]


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def prepare(root):
    manifest=json.loads((root/'reports/20261023_E3_image_removal_report/image_pair_manifest.json').read_text())
    inputs=[]
    for label in LABELS:
        pair=next(p for p in manifest['pairs'] if p['display_run']==label)
        out=N/label;out.mkdir(parents=True,exist_ok=True)
        for key in ['before','after']:
            src=Path(pair[key]['path'])
            assert sha(src)==pair[key]['sha256']
            shutil.copy2(src,out/(key+'.png'))
        src=root/'reports/20261023_E3_image_removal_report/runs'/label
        for name in ['initial_ink_mask.png','final_ink_mask_aligned.png','roi_before.png','final_occlusion_mask_aligned.png','final_rgb_aligned.png']:
            shutil.copy2(src/name,out/name)
        inputs.append(dict(label=label,run_id=pair['original_run_id'],
            before_sha256=pair['before']['sha256'],after_sha256=pair['after']['sha256'],
            native_shape=[240,424,3],crop_native_xyxy=CROP,
            display='RGB at native aspect; nearest-neighbor display only; unchanged binary masks; vector contours/hatching',
            source_pair_manifest='provenance/results_20261108/image_pair_manifest.json'))
    (V/'e3_display_manifest.json').write_text(json.dumps(inputs,indent=2)+'\n')


def panel(labels,name):
    fig,axes=plt.subplots(2*len(labels),2,figsize=(7.4,4.15*len(labels)),
        gridspec_kw={'height_ratios':sum(([1.,.72] for _ in labels),[])},squeeze=False)
    metrics={r['display_label']:r for r in __import__('csv').DictReader((V/'e3_raw_reproduction.csv').open())}
    x0,y0,x1,y1=CROP
    for i,label in enumerate(labels):
        folder=N/label;r=metrics[label]
        rgb=[np.asarray(Image.open(folder/'before.png')),np.asarray(Image.open(folder/'after.png'))]
        roi=np.asarray(Image.open(folder/'roi_before.png'))>0
        occ=np.asarray(Image.open(folder/'final_occlusion_mask_aligned.png'))>0
        mask=[np.asarray(Image.open(folder/'initial_ink_mask.png'))>0,
              np.asarray(Image.open(folder/'final_ink_mask_aligned.png'))>0]
        for j in range(2):
            ax=axes[2*i,j];ax.imshow(rgb[j],interpolation='nearest');ax.axis('off')
            title=f'{label} | '+('Before RGB' if j==0 else 'After RGB')
            ax.set_title(title,fontsize=12,pad=4)
            ax=axes[2*i+1,j]
            # White background with exact black ink pixels supports grayscale print.
            ax.imshow(~mask[j][y0:y1,x0:x1],cmap='gray',vmin=0,vmax=1,
                interpolation='nearest',extent=[x0,x1,y1,y0])
            ax.contour(roi[y0:y1,x0:x1],levels=[.5],colors=['.4'],linewidths=.8,
                linestyles='--',extent=[x0,x1,y1,y0],origin='upper')
            if j and occ.any():
                ax.contourf(occ[y0:y1,x0:x1],levels=[.5,1.5],colors=['none'],hatches=['////'],
                    extent=[x0,x1,y1,y0],origin='upper')
            count=int(mask[j].sum())
            title=('Before' if j==0 else 'After')+f' ink mask: {count} px'
            if j and r['A_after_px']=='':
                title=f'After ink mask\nWhole area unavailable; visible {count} px'
            ax.set_title(title,fontsize=10 if '\n' in title else 10.5,pad=3)
            ax.set_xticks([175,225,275,325]);ax.set_yticks([40,85,130]);ax.tick_params(labelsize=8)
            for spine in ax.spines.values():spine.set_color('.65')
    fig.subplots_adjust(left=.055,right=.99,bottom=.065 if len(labels)==1 else .035,
        top=.925 if len(labels)==1 else .965,hspace=.40,wspace=.16)
    fig.canvas.draw()
    renderer=fig.canvas.get_renderer()
    for ax in axes.flat:
        labels=[*ax.get_xticklabels(),*ax.get_yticklabels()] if ax.axison else []
        for text in [ax.title,*labels]:
            if not text.get_visible() or not text.get_text():continue
            box=text.get_window_extent(renderer)
            assert (box.x0>=0 and box.y0>=0 and box.x1<=fig.bbox.width
                and box.y1<=fig.bbox.height),(name,text.get_text(),box)
    fig.savefig(F/(name+'.pdf'))
    fig.savefig(F/(name+'.png'),dpi=180)
    plt.close(fig)


def main(root):
    if root:prepare(root)
    plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,'font.size':11})
    panel(['N-1','P1-1'],'e3_first_index_evidence_np')
    panel(['D1-1','D2-1'],'e3_first_index_evidence_d')
    for label,name in [('D1-4','e3_D1-4_native_evidence'),('P2-1','e3_P2-1_native_evidence'),('D2-3','e3_D2-3_native_evidence')]:
        panel([label],name)
    print('Built five panels from seven original RGB pairs; native masks/crop preserved.')


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--research-root',type=Path)
    main(a.parse_args().research_root)
