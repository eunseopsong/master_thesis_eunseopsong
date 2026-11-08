#!/usr/bin/env python3
"""Whitelist the document bundle, then test the exact ZIP in isolation."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from PIL import Image

P=Path(__file__).resolve().parents[1]
OUT=P/'submission_20261108'
QA=P/'review/20261108'
ROOTNAME='Thesis_Source_20261108'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def collect():
    files=set()
    for fls in ['ThesisMain.fls','ThesisCover.fls']:
        for line in (P/fls).read_text().splitlines():
            if not line.startswith('INPUT '):continue
            f=Path(line[6:]);f=(P/f).resolve() if not f.is_absolute() else f.resolve()
            try:rel=f.relative_to(P)
            except ValueError:continue
            if f.suffix.lower() in ['.tex','.sty','.cls','.bst','.bib','.png','.jpg','.jpeg','.pdf','.eps']:
                files.add(rel)
    for name in ['build.sh','Bibliography/ThesisRef.bib','XThesis_skku_eng.sty','IEEEtran.cls','IEEEtran.bst','notebook.sty',
                 'README.md','REPRODUCIBILITY_20261108.md','CHANGELOG_20261108.md','FINAL_CHECKLIST_20261108.md',
                 'claim_evidence_map_20261108.md','results_manifest_20261108.csv','figure_manifest_20261108.json']:
        if (P/name).is_file():files.add(Path(name))
    for name in ['e1_runs.csv','e2_runs_corrected.csv','e2_operator_correction.json','e1_c6_diagnostic.csv',
                 'e1_rstar_source_runs.csv','e3_source_area_runs.csv','e3_registered_placements.csv',
                 'diagnostic_cases_20261108.json','results_summary_20261108.json','results_precision_20261108.csv',
                 'dataset_episodes.csv']:
        files.add(Path('data')/name)
    for name in ['update_results_20261108.py','prepare_e3_assets_20261108.py','reconnect_sources_20261108.py',
                 'e3_segmentation_frozen.py','validate_examination_20261108.py','render_examination_20261108.py',
                 'package_examination_20261108.py']:
        files.add(Path('scripts')/name)
    for name in ['e3_raw_reproduction.csv','e3_mask_comparison.csv','e3_run_config_mapping.csv',
                 'e1_r_retiming_source_summary.json','e1_rstar_audit_source.csv','source_validation.json',
                 'source_inputs.json','image_pair_manifest.json','image_pair_manifest.csv','analysis_config.json',
                 'annotations.json','occluded_runs.csv','administrative_metadata.json','official_guidance_manifest.json',
                 'manuscript_invariants.json','build_analysis_environment.json','bibliography_audit.json',
                 'photograph_source_checks.json','e1_c6_source_check.json','metric_definitions.json','e3_display_manifest.json']:
        files.add(Path('provenance/results_20261108')/name)
    files.update(f.relative_to(P) for f in (P/'figures/e3_native').rglob('*') if f.is_file())
    # Keep the exact original snapshots used to build the inherited qualitative panels.
    for pattern in ['E1_*1_initial.png','E1_*1_final.png','E2_C1_video_*.png']:
        files.update(f.relative_to(P) for f in (P/'figures').glob(pattern))
    forbidden={'.ckpt','.pth','.pkl','.h5','.hdf5','.bag','.db3','.mcap','.mp4','.webm','.ttf','.otf','.woff','.woff2','.pfb','.log'}
    assert all(f.suffix.lower() not in forbidden and '.git' not in f.parts for f in files)
    assert all((P/f).is_file() for f in files),[str(f) for f in files if not (P/f).is_file()]
    return sorted(files)


def stage():
    files=collect();base=Path(tempfile.mkdtemp(prefix='thesis_submission_stage_20261108_',dir='/tmp'))
    target=base/ROOTNAME
    for rel in files:
        dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(P/rel,dest)
    result=dict(stage_directory=str(target),files=[str(f) for f in files],
        file_hashes={str(f):sha(P/f) for f in files})
    QA.mkdir(parents=True,exist_ok=True)
    (QA/'packaging_stage.json').write_text(json.dumps(result,indent=2)+'\n')
    print(str(target))


def archive():
    files=collect();OUT.mkdir(exist_ok=True)
    manifest=dict(files=[dict(path=str(f),sha256=sha(P/f),bytes=(P/f).stat().st_size) for f in files],
        excluded='preservation backup, earlier manuscript projects, full datasets/logs, checkpoints, videos, font binaries, private CV/screenshot')
    (QA/'source_bundle_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    path=OUT/(ROOTNAME+'.zip')
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for rel in files:z.write(P/rel,str(Path(ROOTNAME)/rel))
        z.writestr(ROOTNAME+'/source_bundle_manifest.json',json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(zip=str(path),sha256=sha(path),files=len(files),bytes=path.stat().st_size)))


def test():
    path=OUT/(ROOTNAME+'.zip')
    base=Path(tempfile.mkdtemp(prefix='thesis_submission_ziptest_20261108_',dir='/tmp'))
    with zipfile.ZipFile(path) as z:
        assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist())
        z.extractall(base)
    target=base/ROOTNAME
    env=os.environ.copy()
    for key in ['TEXINPUTS','BIBINPUTS','BSTINPUTS']:env.pop(key,None)
    env['MPLCONFIGDIR']=str(base/'matplotlib')
    completed=subprocess.run(['bash','build.sh'],cwd=target,env=env,capture_output=True,text=True)
    (QA/'portable_build_stdout.log').write_text(completed.stdout+completed.stderr)
    assert completed.returncode==0,completed.stdout+completed.stderr
    validation=subprocess.run(['python3','scripts/validate_examination_20261108.py'],cwd=target,env=env,capture_output=True,text=True)
    (QA/'portable_validation_stdout.log').write_text(validation.stdout+validation.stderr)
    assert validation.returncode==0,validation.stdout+validation.stderr
    original_text=subprocess.check_output(['pdftotext','-layout',str(P/'ThesisMain.pdf'),'-'])
    rebuilt_text=subprocess.check_output(['pdftotext','-layout',str(target/'ThesisMain.pdf'),'-'])
    assert original_text==rebuilt_text,'portable PDF text differs'
    leaked=[]
    for line in (target/'ThesisMain.fls').read_text().splitlines():
        if line.startswith('INPUT ') and str(P)+'/' in line:leaked.append(line)
    assert not leaked,leaked
    # Compare every rebuilt page with the actually reviewed PDF, at the same DPI.
    current=json.loads((QA/'visual/current_render_index.json').read_text())
    assert current['pdf_sha256']==sha(P/'ThesisMain.pdf')
    render=base/'render';render.mkdir()
    subprocess.run(['pdftoppm','-r','95','-png',str(target/'ThesisMain.pdf'),str(render/'page')],check=True)
    originals=[P/f for f in current['rendered_pages']]
    rebuilds=sorted(render.glob('page-*.png'))
    assert len(originals)==len(rebuilds)
    identical=[]
    for i,(a,b) in enumerate(zip(originals,rebuilds),1):
        ia,ib=Image.open(a).convert('RGB'),Image.open(b).convert('RGB')
        ok=ia.size==ib.size and ia.tobytes()==ib.tobytes()
        identical.append(dict(pdf_page=i,pixel_identical=ok))
    assert all(r['pixel_identical'] for r in identical),[r for r in identical if not r['pixel_identical']]
    for filename in ['full_build.log','latex_pass1.log','bibtex.log','latex_pass2.log','latex_pass3.log','cover_build.log']:
        shutil.copy2(target/'review'/filename,QA/('portable_'+filename))
    result=dict(zip_sha256=sha(path),tested_exact_zip=str(path),extracted_directory=str(target),
        build_returncode=completed.returncode,validation_returncode=validation.returncode,
        identical_searchable_text=True,original_project_inputs_used=leaked,
        pages=len(identical),all_rendered_pages_pixel_identical=True,render_comparisons=identical,
        tested_without_original_data_model_ros_or_gpu=True,source_only_system_TeX_dependencies=True)
    (QA/'portable_build_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='render_comparisons'}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['stage','archive','test'])
    {'stage':stage,'archive':archive,'test':test}[parser.parse_args().operation]()
