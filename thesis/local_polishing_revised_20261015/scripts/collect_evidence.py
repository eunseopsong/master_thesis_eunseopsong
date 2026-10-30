#!/usr/bin/env python3
"""Read archived evidence; write only inside this revised thesis project.

No ROS imports, robot calls, training, or changes to source experiments.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import shutil
import subprocess

import h5py
import numpy as np
import pandas as pd
from PIL import Image, ImageOps
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--repo', type=Path, default=Path('/home/eunseop/nrs_imitation'))
args = parser.parse_args()
REPO = args.repo.resolve()
assert ROOT != REPO and REPO not in ROOT.parents
DATA = ROOT / 'data'
FIG = ROOT / 'figures'
PROV = ROOT / 'provenance'
for p in [DATA / 'traces', FIG, PROV]:
    p.mkdir(parents=True, exist_ok=True)
inputs = {}
figures = []


def source(path):
    path = Path(path)
    if not path.is_absolute():
        path = REPO / path
    if str(path) not in inputs:
        h = hashlib.sha256()
        with path.open('rb') as f:
            for buf in iter(lambda: f.read(1024 * 1024), b''):
                h.update(buf)
        inputs[str(path)] = {'sha256': h.hexdigest(), 'bytes': path.stat().st_size}
    return path


def read_json(path):
    return json.loads(source(path).read_text())


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def asset(figure_id, path, destination, chapter, processing='copied without pixel changes', **extra):
    path = source(path)
    shutil.copy2(path, FIG / destination)
    figures.append(dict(figure_id=figure_id, output='figures/' + destination,
                        sources=[str(path)], processing=processing, location=chapter, **extra))


def summarize(df, group, metrics):
    rows = []
    for name, part in df.groupby(group, sort=True):
        row = {group: name, 'attempts': len(part)}
        for key in metrics:
            v = pd.to_numeric(part[key], errors='coerce').dropna()
            row.update({key + '_n': len(v), key + '_mean': v.mean(), key + '_sd': v.std(ddof=1)})
        rows.append(row)
    return pd.DataFrame(rows)


e1 = pd.read_csv(source('reports/20261014_E1_contact_task_pdf_report/metrics_per_run.csv'))
e2 = pd.read_csv(source('reports/20261013_E2_pdf_report/metrics_per_run.csv'))
assert len(e1) == len(e2) == 15
assert set(e1['session_id']) == {'E1_CT_sync_confirm_dev_20261014'}
e1['label'] = e1['method'] + e1['repeat_index'].astype(str)
e1['completion_time_s'] = pd.to_numeric(e1['completion_time_s'], errors='coerce')
e2['task_outcome'] = np.where(e2.label == 'A4', 'incomplete_contact_release_operator_stopped',
                              'operator_reported_completed')
e2['completion_time_corrected_s'] = np.where(e2.label == 'A4', np.nan, e2.execution_duration_s)
e2['outcome_basis'] = 'operator report; latest task instruction corrects A4; original event fields retained'
e2['original_report_completion_s'] = e2.operator_confirmed_completion_time_s
write_json(DATA / 'e2_operator_correction.json', {
    'source': 'user instruction for this thesis rewrite, 2026-10-15',
    'run_id': str(e2.loc[e2.label == 'A4', 'run_id'].iloc[0]),
    'observation_ko': '접촉 해제 단계로 넘어가지 못하고 계속 접촉을 유지해 작업자가 중단했다.',
    'execution_duration_s': 28.750087346,
    'completion_time_s': None,
    'included_in_all_attempt_statistics': True,
    'raw_operator_finish_and_normal_completion_unchanged': True,
    'causal_attribution_to_force_ablation': 'not established',
    'supersedes': 'reports/20261013_E2_pdf_report/operator_completion_criterion.json for A4 only'})

e1cols = ['label', 'method', 'repeat_index', 'run_id', 'run_directory', 'session_id', 'stage',
          'config_version_id', 'execution_order', 'outcome', 'completion_time_s', 'evaluation_end_s',
          'actual_execution_to_stop_s', 'execution_start_monotonic_ns', 'J_excess_Ns',
          'peak_Fz_base_N', 'Fz_timeweighted_mean_N', 'ordered_pass_segment_count',
          'pass_completed_at_s', 'original_stop_reason', 'z_contact_ref_mm']
e1cols = [k for k in e1cols if k in e1]
e1[e1cols].to_csv(DATA / 'e1_runs.csv', index=False)
e2cols = ['label', 'condition', 'repeat_index', 'run_id', 'run_directory', 'execution_order',
          'execution_start_local', 'execution_start_monotonic_ns', 'first_stop_requested_monotonic_ns',
          'execution_duration_s', 'completion_time_corrected_s', 'task_outcome', 'outcome_basis',
          'original_report_completion_s', 'mean_fz_N', 'peak_fz_N', 'temporal_sd_fz_N',
          'time_fz_ge_3N_s', 'tcp_xy_path_mm', 'gate_on_s', 'gate_transitions',
          'force_feedback_hz', 'first_stop_reason', 'terminal_event', 'video_count']
e2[e2cols].to_csv(DATA / 'e2_runs_corrected.csv', index=False)
es1 = summarize(e1, 'method', ['completion_time_s', 'J_excess_Ns', 'peak_Fz_base_N', 'Fz_timeweighted_mean_N'])
es1['completed'] = [int((e1[e1.method == x].outcome == 'completed').sum()) for x in es1.method]
es1.to_csv(DATA / 'e1_summary.csv', index=False)
es2 = summarize(e2, 'condition', ['completion_time_corrected_s', 'execution_duration_s', 'mean_fz_N',
                                 'peak_fz_N', 'time_fz_ge_3N_s', 'tcp_xy_path_mm', 'gate_transitions'])
es2['completed'] = [int(e2[e2.condition == x].completion_time_corrected_s.notna().sum()) for x in es2.condition]
es2.to_csv(DATA / 'e2_summary_corrected.csv', index=False)
baseline = pd.read_csv(source('reports/E1_contact_task_pass_height_v2/baseline_replay/baseline_replay_comparison.csv'))
baseline.to_csv(DATA / 'e1_height_reference_replay.csv', index=False)
replay = baseline.copy()
replay['B_completion_time_s'] = pd.to_numeric(replay.B_completion_time_s, errors='coerce')
summarize(replay, 'method', ['B_completion_time_s', 'B_J_excess_Ns']).to_csv(DATA / 'e1_replay_summary.csv', index=False)

# Independently integrate native force CSV values on archived analysis windows.
# Each held interval needs two receipt samples; gaps > 0.2 s have no support.
validation = []
runtime_records = []
for cohort, df in [('E1', e1), ('E2', e2)]:
    for _, row in df.iterrows():
        run = Path(row.run_directory)
        runtime = run / ('execution_config.json' if cohort == 'E1' else 'runtime.json')
        config = read_json(runtime)
        cp = config.get('il', {}).get('checkpoint', '')
        expected = '/e2_force_cleanup_20261012/' + (str(row.method) if cohort == 'E1' else str(row.condition))
        if cohort == 'E2' or row.method == 'C':
            assert expected in cp, (row.run_id, cp)
        runtime_records.append({'cohort': cohort, 'label': row.label, 'run_id': row.run_id,
                                'runtime_file': str(runtime), 'checkpoint': cp,
                                'il': config.get('il'), 'executor': config.get('executor'),
                                'common_force_observation': config.get('common', {}).get('force_observation'),
                                'external_force_N': config.get('external_force_N'),
                                'common_conditioner': config.get('rtc_pose_conditioning'),
                                'config_sha256': inputs[str(runtime)]['sha256']})
        start_ns = int(row.execution_start_monotonic_ns)
        end = float(row.evaluation_end_s if cohort == 'E1' else row.execution_duration_s)
        integ = observed = 0.0
        for kind, cols in [('force', ['fx', 'fy', 'fz', 'tx', 'ty', 'tz']),
                           ('pose', ['x', 'y', 'z', 'rx', 'ry', 'rz'])]:
            fname = 'wrench.csv' if kind == 'force' else 'tcp_pose.csv'
            matches = list(run.glob('executor/**/' + fname))
            assert len(matches) == 1
            raw = pd.read_csv(source(matches[0]))
            raw['time_s'] = (raw.receipt_monotonic_ns.astype('int64') - start_ns) / 1e9
            # Retain one bracketing sample on either side for supported interpolation.
            lo = max(0, int(np.searchsorted(raw.time_s, 0.0, side='right')) - 1)
            hi = min(len(raw), int(np.searchsorted(raw.time_s, end, side='right')) + 1)
            trace = raw.iloc[lo:hi][['time_s'] + cols].copy()
            trace.to_csv(DATA / 'traces' / f'{cohort}_{row.label}_{kind}.csv', index=False)
            if kind == 'force':
                t = raw.time_s.to_numpy(); f = raw.fz.to_numpy()
                left = np.maximum(t[:-1], 0.0); right = np.minimum(t[1:], end)
                dt = np.maximum(right - left, 0.0)
                dt[(np.diff(t) > .2) | ~np.isfinite(f[:-1])] = 0
                observed = float(dt.sum())
                integ = float(np.dot(dt, np.maximum(f[:-1] - 30.812396273, 0)))
                mean = float(np.dot(dt, f[:-1]) / observed)
                peak = float(np.max(f[(t >= 0) & (t <= end)]))
        if cohort == 'E1':
            error = integ - float(row.J_excess_Ns)
            validation.append(dict(cohort=cohort, label=row.label, J_excess_csv_Ns=integ,
                                   J_excess_report_Ns=float(row.J_excess_Ns), integral_error=error,
                                   observed_s=observed, analysis_end_s=end))
            assert abs(error) < 1e-7, (row.label, error)
        else:
            validation.append(dict(cohort=cohort, label=row.label, mean_csv_N=mean,
                                   mean_report_N=float(row.mean_fz_N), mean_error=mean-float(row.mean_fz_N),
                                   peak_csv_N=peak, peak_report_N=float(row.peak_fz_N),
                                   observed_s=observed, analysis_end_s=end))
            assert abs(mean - float(row.mean_fz_N)) < 1e-7
            assert abs(peak - float(row.peak_fz_N)) < 1e-7

pd.DataFrame(validation).to_csv(DATA / 'native_csv_validation.csv', index=False)
write_json(PROV / 'run_runtime_evidence.json', runtime_records)

# Preserve documented non-start separately, without changing the source cohort.
exclusion = read_json('reports/20261014_E1_contact_task_pdf_report/exclusion_manifest.json')
write_json(PROV / 'e1_original_nonstart_registration.json', exclusion)
height_status = []
for rel in ['experiments/E1_contact_task_pass_height_v2/sessions',
            'experiments/E1_contact_task_pass_height_v2_heights/sessions']:
    for session in sorted((REPO / rel).iterdir()):
        if session.is_dir():
            attempts = read_json(session / 'attempts.json')
            height_status.append({'session': session.name, 'attempts': len(attempts),
                                  'status': 'not_run' if not attempts else 'has_attempts'})
write_json(PROV / 'height_session_status.json', height_status)

models = read_json('experiments/e2_force_cleanup_20261012/model_manifest.json')
configs = read_json('experiments/e2_force_cleanup_20261012/training_configs.json')
dataset = read_json('experiments/e2_force_cleanup_20261012/dataset_manifest.json')
write_json(PROV / 'model_manifest.json', models)
write_json(PROV / 'training_configs.json', configs)
write_json(PROV / 'dataset_summary.json', {k:dataset[k] for k in
           ['schema', 'status', 'source_dataset', 'dataset', 'rules', 'split', 'totals',
            'use_relative_position', 'relative_transform_version', 'rotation_aligned']})

# A compact, portable teaching example. Source time is preserved, not guessed.
path = source(Path(dataset['dataset']) / 'episode_29.hdf5')
with h5py.File(path, 'r') as f:
    obs = f['observations/position'][:]; force = f['observations/force'][:]
    force_action = f['action/force'][:]
    original_path = source(str(f.attrs['source_h5']))
    ep = str(f.attrs['source_episode'])
    attrs = {k:np.asarray(v).tolist() if isinstance(v, (np.ndarray, np.generic)) else v for k,v in f.attrs.items()}
    for idx in [0, 85, 150, 400]:
        filename = f'teaching_ep29_frame{idx:03d}.png'
        Image.fromarray(f['observations/images/cam0'][idx]).save(FIG / filename)
        figures.append(dict(figure_id='fig:teaching_frames', output='figures/' + filename,
                            sources=[str(path)], source_dataset_key='observations/images/cam0',
                            frame_index=idx, processing='exact RGB frame, PNG encoding', location='Chapter 4'))
with h5py.File(original_path, 'r') as f:
    g = f['episodes/' + ep]
    times = g['sample_time_unix'][:]; times -= times[0]
    raw_ft = g['raw_ft'][:]; ema = g['ft'][:]; raw_pose = g['raw_position'][:]
    assert len(times) == len(obs)
    attrs['source_recording'] = {k:np.asarray(v).tolist() if isinstance(v, (np.ndarray,np.generic)) else v
                                 for k,v in g.attrs.items()}
    attrs['source_root'] = {k:np.asarray(v).tolist() if isinstance(v, (np.ndarray,np.generic)) else v
                            for k,v in f.attrs.items()}
base = Rotation.from_rotvec(obs[:, 3:6]).apply(force)
demo = pd.DataFrame({'time_s': times, 'x_rel_mm':obs[:,0], 'y_rel_mm':obs[:,1], 'z_mm':obs[:,2],
                     'rx_rad':obs[:,3], 'ry_rad':obs[:,4], 'rz_rad':obs[:,5]})
for j,name in enumerate(['fx','fy','fz']):
    demo[name+'_cleanup_N'] = force[:,j]
    demo[name+'_action_N'] = force_action[:,j]
    demo[name+'_raw_published_N'] = raw_ft[:,j]
    demo[name+'_ema_N'] = ema[:,j]
    demo[name+'_base_N'] = base[:,j]
demo.to_csv(DATA / 'teaching_episode29.csv', index=False)
write_json(PROV / 'teaching_episode29_metadata.json', attrs)
demo_rows = []
for p in sorted(Path(dataset['dataset']).glob('episode_*.hdf5')):
    with h5py.File(p,'r') as f:
        demo_rows.append(dict(episode=p.name, frames=len(f['observations/position']),
                              split='validation' if p.name in dataset['split']['validation'] else 'train',
                              source_h5=str(f.attrs.get('source_h5')),source_episode=str(f.attrs.get('source_episode')),
                              origin_x=float(f.attrs['stain_origin_xy_mm'][0]), origin_y=float(f.attrs['stain_origin_xy_mm'][1])))
pd.DataFrame(demo_rows).to_csv(DATA / 'dataset_episodes.csv', index=False)

# Use first run of each method, without selection on result.
for method in ['R','T','C']:
    row = e1[(e1.method == method) & (e1.repeat_index == 1)].iloc[0]
    run = Path(row.run_directory)
    for phase in ['initial','final']:
        p = list(run.glob('provider/**/snapshots/' + phase + '_image.png'))
        assert len(p) == 1
        asset('fig:e1_photos', p[0], f'E1_{method}1_{phase}.png', 'Chapter 7',
              run_id=row.run_id, selection='first started execution per method; no outcome selection',
              timing='provider snapshot; not synchronized surface metrology')

row = e1[(e1.method == 'C') & (e1.repeat_index == 1)].iloc[0]
heatmap = next(Path(row.run_directory).glob('removal_visualization/**/01_removal_heatmap.png'))
asset('fig:diagnostic_heatmap', heatmap, 'E1_C1_diagnostic_heatmap.png', 'Chapter 8',
      run_id=row.run_id, interpretation='uncalibrated execution-derived diagnostic, arbitrary units; not depth')

# One genuine archived setup photograph. No identity inferred for unseen parts.
photo = Path('/home/eunseop/Downloads/20260807_144759.jpg')
if photo.exists():
    image = ImageOps.exif_transpose(Image.open(source(photo)))
    image.thumbnail((1400, 1800)); image.save(FIG / 'apparatus_20260807.jpg', quality=92)
    figures.append(dict(figure_id='fig:apparatus',output='figures/apparatus_20260807.jpg',
                        sources=[str(photo)],processing='EXIF orientation 6 (clockwise 90 degrees); proportional downsize; JPEG quality 92',
                        capture_time_exif='2026:08:07 14:47:59',
                        location='Chapter 3', context='archived apparatus photo; not a photograph of the October E1/E2 runs'))
asset('fig:mark_example', 'images/home_pose_stain_detection.png', 'mark_detection_example.png',
      'Chapter 3', context='archived spatial registration example; not the evaluated E1 fixed datum')

# Extract uniformly spaced frames in the first E2 C video. Times are video offsets.
row = e2[e2.label == 'C1'].iloc[0]
video = next(Path(row.run_directory).glob('video/*.webm'))
source(video)
probe = subprocess.run(['ffprobe','-v','quiet','-show_entries','format=duration','-of','json',str(video)],
                       check=True, capture_output=True, text=True)
duration_value = json.loads(probe.stdout)['format'].get('duration')
if duration_value is None:
    # This archived WebM has no declared container duration. Use its actual
    # decodable frame timestamps, without inventing an acquisition clock.
    probe = subprocess.run(['ffprobe','-v','quiet','-select_streams','v:0',
                            '-show_entries','frame=best_effort_timestamp_time',
                            '-of','json',str(video)],check=True,capture_output=True,text=True)
    duration_value = max(float(f['best_effort_timestamp_time'])
                         for f in json.loads(probe.stdout)['frames']
                         if 'best_effort_timestamp_time' in f)
duration = float(duration_value)
for j,fraction in enumerate([.1,.4,.7,.9]):
    t = fraction * duration; destination = FIG / f'E2_C1_video_{j}.png'
    subprocess.run(['ffmpeg','-loglevel','error','-ss',f'{t:.6f}','-i',str(video),'-frames:v','1',
                    '-vf','scale=960:-1','-y',str(destination)],check=True)
    figures.append(dict(figure_id='fig:e2_sequence', output=str(destination.relative_to(ROOT)),
                        sources=[str(video)],run_id=row.run_id,video_offset_s=t,
                        video_duration_s=duration,processing='ffmpeg frame at stated video offset; proportional scale',
                        selection='first C execution; uniform fractions 0.1/0.4/0.7/0.9',location='Chapter 7',
                        limitation='archived WebM ends prematurely; decoded portion only; no complete-exit certification'))

# Compact source evidence: copies are for reading, never imported or executed.
selected_sources = [
 'experiments/e2_force_cleanup_20261012/snapshot/source/models/flow_core.py',
 'experiments/e2_force_cleanup_20261012/snapshot/source/models/dinov3_backbone.py',
 'experiments/e2_force_cleanup_20261012/snapshot/source/data/dataset.py',
 'reports/20261014_E1_correspondence_audit_v2_force/force_pipeline.md',
 'reports/20261014_E1_correspondence_audit_v2_force/force_transform_evidence.json',
 'reports/20261014_E1_correspondence_audit_v2_force/force_reference_definition.json',
 'reports/20261014_E1_correspondence_audit_v2_force/force_stats.csv',
 'behavior_ws/src/vive_tracker_ros2/yaml/calibration_matrix.yaml',
 'reports/20261012_contact_transition_diagnosis/controller/Y2ForceCon/src/admittance_control.cpp',
 'reports/20261012_contact_transition_diagnosis/controller/Y2RobMotion/config/setup_parameters.yaml',
 'reports/20261012_contact_transition_diagnosis/controller/Y2RobMotion/src/force_control.cpp',
 'behavior_ws/src/nrs_imitation/nrs_imitation/polishing_removal_recorder.py',
 'behavior_ws/src/nrs_imitation/nrs_imitation/e2_blending.py',
 'experiments/e2_c_blending_20261013/README.md',
 'reports/20261014_E2_C_adaptive_velocity_feedback_replan/README.md',
 'reports/20261013_E2_pdf_report/operator_completion_criterion.json']
frozen = REPO / 'experiments/E1_contact_transition_20261014_sync_confirm/sessions/E1_CT_sync_confirm_dev_20261014/frozen_source'
selected_sources += [str(p) for p in frozen.glob('*.py') if any(s in p.name for s in
                    ['e2_timed_execution','e1_contact_task.py','e1_contact_task_execution','inference_core'])]
for rel in selected_sources:
    p = source(rel)
    target = PROV / 'selected_source' / p.relative_to(REPO)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, target)

write_json(PROV / 'input_manifest.json', inputs)
write_json(ROOT / 'figure_manifest.json', figures)
print(es1[['method','completed','completion_time_s_mean','J_excess_Ns_mean']].to_string(index=False))
print(es2[['condition','completed','completion_time_corrected_s_mean','completion_time_corrected_s_sd',
           'execution_duration_s_mean']].to_string(index=False))
print('Read-only native CSV validation passed for all 30 executions.')
