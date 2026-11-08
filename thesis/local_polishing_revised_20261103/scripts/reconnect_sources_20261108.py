#!/usr/bin/env python3
"""Read frozen research evidence; write only inside this manuscript project.

No ROS imports, execution wrappers, checkpoint loading, or original-file writes.
The E3 numerical functions are extracted verbatim from the archived offline
analyzer after reviewing its side effects. Only pure array functions execute.
"""
from pathlib import Path
import argparse
import ast
import csv
import hashlib
import json
import shutil
import statistics
import cv2
import numpy as np
from PIL import Image

P = Path(__file__).resolve().parents[1]
V = P / 'provenance/results_20261108'
D = P / 'data'
csv.field_size_limit(20000000)


def read(p):
    return json.loads(Path(p).read_text())


def rows(p):
    with Path(p).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def save(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def csvout(p, values):
    with Path(p).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(values[0]))
        w.writeheader()
        w.writerows(values)


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def main(root):
    root = root.resolve()
    assert root != P and root.is_dir()
    V.mkdir(parents=True, exist_ok=True)
    inputs, checks = {}, []

    def track(p, expected=None):
        p = Path(p)
        assert p.is_file(), str(p)
        digest = sha(p)
        if expected is not None:
            assert digest == expected, ('frozen hash mismatch', str(p), expected, digest)
        inputs[str(p)] = dict(path=str(p), size=p.stat().st_size, sha256=digest)
        return p

    def check(name, ok, detail):
        checks.append(dict(check=name, passed=bool(ok), detail=detail))
        assert ok, (name, detail)

    # Link every original nominal run to the frozen report and precision values.
    e1r = root/'reports/20261015_E1_nominal_pass_height_v2_pdf_report'
    e1manifest = read(track(e1r/'input_manifest.json'))
    e1source = rows(track(e1r/'numeric_per_run.csv'))
    e1saved = rows(D/'e1_runs.csv')
    check('E1 frozen original membership',
          {r['run_id'] for r in e1saved} == {r['run_id'] for r in e1manifest['included_runs']},
          '15 frozen original R/T/C; original C5 retained')
    for r in e1saved:
        s = next(x for x in e1source if x['run_id'] == r['run_id'])
        for key in ['completion_time_s','J_excess_Ns','peak_Fz_base_N','tcp_xy_distance_mm']:
            check('E1 '+r['label']+' '+key, abs(float(r[key])-float(s[key])) < 1e-9, s[key])
        origin = next(x for x in e1manifest['included_runs'] if x['run_id']==r['run_id'])
        for name in ['run_context.json','execution_config.json','task_evaluation.json']:
            track(Path(origin['run_directory'])/name)
    track(root/'reports/E1_contact_task_pass_height_v2/baseline_manifest.json')

    rr = root/'reports/20261019_E1_R_dataset_mean_feed_pdf_report'
    source = rows(track(rr/'analysis/diagnostic_metrics_per_run.csv'))
    audits = rows(track(rr/'audit_per_run.csv'))
    track(rr/'input_manifest.csv')
    track(rr/'code_versions.json')
    comparison=rows(track(rr/'analysis/original_R5_vs_dataset_mean_R5.csv'))
    save(V/'e1_r_retiming_source_summary.json',comparison)
    compact = []
    for r in source:
        a = next(x for x in audits if x['run_id']==r['run_id'])
        directory = Path(r['run_directory'])
        context = read(track(directory/'run_context.json'))
        check('Rstar identity '+r['repeat_index'], context['run_id']==r['run_id'], r['run_id'])
        for name in ['execution_config.json','task_definition.json','task_evaluation.json','runtime_source_versions.json']:
            track(directory/name)
        track(a['template'], a['template_sha256'])
        compact.append(dict(display_label='R*'+r['repeat_index'], run_id=r['run_id'],
            date='2026-10-19', session_id=r['session_id'], config_version=r['config_version_id'],
            completion_time_s=float(r['completion_time_s']), J_excess_Ns=float(r['J_excess_Ns']),
            peak_Fz_base_N=float(r['peak_Fz_base_N']),
            pass_mean_xy_mm_s=float(r['successful_pass_actual_xy_mean_mm_s']),
            source=str((rr/'analysis/diagnostic_metrics_per_run.csv').relative_to(root)),
            value_precision='source-derived; unrounded archived analysis CSV',
            template_sha256=a['template_sha256']))
    check('Rstar separate five', len(compact)==5, [r['run_id'] for r in compact])
    csvout(D/'e1_rstar_source_runs.csv', compact)
    csvout(V/'e1_rstar_audit_source.csv', audits)

    # Check A4's original stop events without reversing the field correction.
    e2r = root/'reports/20261013_E2_pdf_report'
    e2source = rows(track(e2r/'metrics_per_run.csv'))
    track(e2r/'input_manifest.json')
    e2saved = rows(D/'e2_runs_corrected.csv')
    for r in e2saved:
        s = next(x for x in e2source if x['run_id']==r['run_id'])
        for key in ['execution_duration_s','mean_fz_N','peak_fz_N','tcp_xy_path_mm']:
            check('E2 '+r['label']+' '+key, abs(float(r[key])-float(s[key]))<1e-9, s[key])
        directory = Path(s['run_directory'])
        check('E2 source run directory '+r['label'], directory.is_dir(), r['run_id'])
        # The earlier E2 archive predates E1/E3's per-run run_context schema.
        track(directory/'runtime.json')
        for context_file in sorted((directory/'launch_context').glob('*.json')):
            track(context_file)
    correction = read(D/'e2_operator_correction.json')
    event_path = track(correction['raw_log_evidence']['source'])
    events = [json.loads(line) for line in event_path.read_text().splitlines() if line.strip()]
    check('A4 corrected completion remains null',
          next(r for r in e2saved if r['label']=='A4')['completion_time_corrected_s']=='',
          '28.750087346 s interruption; original software events preserved')
    save(V/'e2_a4_event_check.json', dict(source_sha256=sha(event_path),event_count=len(events),
        correction=correction,validation='original event file reopened; field correction remains authoritative'))

    e3r = root/'reports/20261023_E3_image_removal_report'
    execr = root/'reports/20261023_E3_pdf_report'
    config = read(track(e3r/'analysis_config.json'))
    annotations = read(track(e3r/'annotations.json'))
    pairs = read(track(e3r/'image_pair_manifest.json'))
    original = rows(track(e3r/'removal_metrics_per_run.csv'))
    track(e3r/'removal_summary_by_condition.csv')
    track(e3r/'image_pair_manifest.csv')
    track(e3r/'occluded_runs.csv')
    frozen = read(track(execr/'selection_manifest.json'))
    execution = rows(track(execr/'metrics_per_run.csv'))
    for c, obj in frozen.items():
        track(obj['path'], obj['sha256'])
        check('E3 frozen '+c, {x['original_run_id'] for x in pairs['pairs'] if x['condition']==c}==set(obj['selected_run_ids']), 'same five IDs as frozen selection')
    track(pairs['source_selection'], pairs['source_selection_sha256'])
    # Pure functions, no module import of prepare_inputs and no analyzer entrypoint.
    analyzer = track(e3r/'analyze_images.py')
    code = analyzer.read_text()
    names = {'polygon_mask','dilate','warp_image','stable_mask','align'}
    functions = [x for x in ast.parse(code).body if isinstance(x,ast.FunctionDef) and x.name in names]
    check('E3 pure function extraction', {x.name for x in functions}==names, sorted(names))
    frozen_source = '"""Verbatim pure functions from the frozen E3 analyzer; original SHA-256: '+sha(analyzer)+'"""\nimport cv2\nimport numpy as np\n\n'
    frozen_source += '\n\n'.join(ast.get_source_segment(code,x) for x in functions)+'\n'
    (P/'scripts/e3_segmentation_frozen.py').write_text(frozen_source)
    scope = {'cv2':cv2,'np':np}
    exec(compile(ast.Module(body=functions,type_ignores=[]),str(analyzer),'exec'), scope)
    polygon,dilate,warp,align=(scope[x] for x in ['polygon_mask','dilate','warp_image','align'])
    reproduced, layouts, maskchecks = [], [], []
    for pair in pairs['pairs']:
        name=pair['display_run']; ann=annotations['runs'][name]
        s = next(r for r in original if r['display_run']==name)
        ex = next(r for r in execution if r['run_id']==pair['original_run_id'])
        directory=Path(ex['run_directory'])
        context=read(track(directory/'run_context.json'))
        cfg=read(track(directory/'execution_config.json'))
        track(directory/'task_registration.json')
        runtime_versions=read(track(directory/'runtime_source_versions.json'))
        for source_name in ['behavior_ws/src/nrs_imitation/nrs_imitation/inference_core.py']:
            snapshot=directory/'source_snapshot'/source_name.replace('/','__')
            track(snapshot,runtime_versions[source_name])
        layout=context['registered_layout']
        timing=cfg['e3_spatial_transfer']
        check('E3 timing '+name, cfg['il']['replan_interval_steps']==120 and
              timing['inference_replan_lead_sec']==.5 and timing['effective_replan_interval_s']==3.5,
              'nominal stride 4.0 s; configured plan-age threshold 3.5 s, not measured call interval')
        check('E3 common checkpoint '+name,
              cfg['il']['checkpoint_sha256']=='60d55e7092cb18035938e281f3022e3c6107fdbb51331b66a29dcca242d4d59f' and
              cfg['il']['normalizer_sha256']=='09111fa4acc3717e3085d9ef85474eb99270af33cbf78453eb793069b3759c49',
              'recorded checkpoint/normalizer hashes; artifacts hashed separately, never loaded')
        layouts.append(dict(display_label=name,run_id=pair['original_run_id'],condition=pair['condition'],
            delta_x_mm=layout['translation_xy_mm'][0],delta_y_mm=layout['translation_xy_mm'][1],phi_deg=layout['phi_deg'],
            config_version=context['config_version_id'],retry_of=context['retry_of'],
            home_execution=ex['home_execution'],require_commanded_release=ex['require_commanded_release'],
            nominal_stride_s=4.0,replan_lead_s=.5,configured_plan_age_s=3.5,
            source='saved run_context.json and execution_config.json; source-derived'))
        before=np.asarray(Image.open(track(pair['before']['path'],pair['before']['sha256'])).convert('RGB'))
        after=np.asarray(Image.open(track(pair['after']['path'],pair['after']['sha256'])).convert('RGB'))
        check('E3 native RGB '+name,before.shape==after.shape==(240,424,3),list(before.shape))
        support=dilate(polygon(before.shape,[ann['initial_visible_ink_polygon']]),ann['initial_support_expansion_px'])
        roi=dilate(polygon(before.shape,[ann['initial_visible_ink_polygon']]),config['roi_margin_px'])
        support_a=polygon(after.shape,ann['final_visible_ink_polygons'])
        occ=polygon(after.shape,[ann['final_occlusion_polygon_native']])
        matrix, alignment=align(before,after,pair,config)
        mb=(cv2.cvtColor(before,cv2.COLOR_RGB2GRAY)<=45)&support&roi
        ma_native=(cv2.cvtColor(after,cv2.COLOR_RGB2GRAY)<=45)&support_a&~occ
        ma=warp(ma_native.astype(np.uint8),matrix,before.shape,nearest=True).astype(bool)&roi
        valid=not ann['final_occluded'] and alignment['valid'] and int(mb.sum())>0
        ab=int(mb.sum()); aa=int(ma.sum()) if valid else None
        rate=100*(ab-aa)/ab if valid else None
        check('E3 area '+name, ab==int(s['A_before']) and (aa==int(s['A_after']) if valid else s['A_after']==''),
              dict(before_px=ab,after_px=aa,removal_pct=rate))
        check('E3 visible residual '+name, valid or int(ma.sum())==int(s['visible_residual_diagnostic_px']),int(ma.sum()))
        folder=V/'recomputed_masks'/name;folder.mkdir(parents=True,exist_ok=True)
        for filename,arr in [('initial_ink_mask.png',mb),('final_ink_mask_aligned.png',ma),('roi_before.png',roi)]:
            saved=np.asarray(Image.open(track(e3r/'runs'/name/filename)))>0
            match=np.array_equal(saved,arr)
            maskchecks.append(dict(display_run=name,file=filename,identical=match,different_pixels=int(np.count_nonzero(saved!=arr))))
            check('E3 mask '+name+' '+filename,match,int(np.count_nonzero(saved!=arr)))
            Image.fromarray(arr.astype(np.uint8)*255).save(folder/filename)
        save(folder/'alignment.json',alignment)
        reproduced.append(dict(display_label=name,condition=pair['condition'],repeat_index=pair['repeat'],
            run_id=pair['original_run_id'],date=pair['original_run_id'].split('_')[-2][:8],A_before_px=ab,A_after_px=aa,
            removal_percent=rate,image_evaluable=valid,main_condition=pair['condition']!='P2',
            final_tool_occlusion=ann['final_occluded'],original_stop_reason=pair['original_stop_reason'],
            visible_residual_diagnostic_px=int(ma.sum()) if not valid else None,
            unavailable_reason='final tool occlusion' if not valid else '',
            source='provenance/results_20261108/e3_raw_reproduction.csv',
            precision='source-derived; reproduced from original RGB, unchanged annotations/ROI/gray45; masks pixel-identical'))
    check('E3 25/20/19',len(reproduced)==25 and sum(x['main_condition'] for x in reproduced)==20 and sum(x['image_evaluable'] for x in reproduced)==19,'six occluded nulls retained')
    csvout(V/'e3_raw_reproduction.csv',reproduced)
    csvout(D/'e3_source_area_runs.csv',reproduced)
    csvout(V/'e3_mask_comparison.csv',maskchecks)
    csvout(V/'e3_run_config_mapping.csv',layouts)
    for filename in ['analysis_config.json','annotations.json','image_pair_manifest.json','image_pair_manifest.csv','occluded_runs.csv']:
        shutil.copy2(e3r/filename,V/filename)
    for name in ['N','P1','D1','D2']:
        vals=[r for r in reproduced if r['condition']==name and r['image_evaluable']]
        print(name,len(vals),statistics.mean(r['removal_percent'] for r in vals),statistics.stdev(r['removal_percent'] for r in vals))
    # Recorded model identity is independently checked by hashing files, not loading.
    modelrefs=read(track(execr/'input_manifest.json'))['model_artifacts']
    for f,h in modelrefs.items():track(f,h)
    for f in [root/'results/20261015/E1_report_20261015_nominal_pass_height_v2.pdf',
              root/'results/20261019/E1_report_20261019_R_dataset_mean_feed_5runs.pdf',
              root/'results/20261013/E2_report_20261013.pdf',root/'results/20261023/E3_report_20261023.pdf',
              e3r/'E3_image_removal_report_20261023.pdf']:
        track(f)
    save(V/'source_inputs.json',dict(research_root=str(root),inputs=list(inputs.values()),
        read_only=True,python_opencv=cv2.__version__,numpy=np.__version__,source_files_modified=False))
    save(V/'source_validation.json',dict(checks=checks,passed=len(checks),failures=0,
        validation_levels=dict(E1='frozen membership, precision CSV and saved configs; evaluator not rerun',
        Rstar='unrounded CSV, five identities, config metadata and template hash',
        E2='15 original precision rows and A4 original events; field correction retained',
        E3='25 original RGB pairs hashed; unchanged annotations/ROI/algorithm; 75 masks pixel-identical; 19 ratios reproduced'),
        no_robot_no_ros_no_training=True))
    print('PASS',len(checks),'checks;',len(inputs),'read-only source files')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--research-root',type=Path,default=Path.home()/'nrs_imitation')
    main(parser.parse_args().research_root)
