#!/usr/bin/env python3
"""Prepare versioned E1 contact-task artifacts without importing ROS or moving a robot."""
import argparse
import copy
import csv
import hashlib
import json
import sys
from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'behavior_ws/src/nrs_imitation'))
from nrs_imitation.e2_providers import TimedActions, pose_waypoint_actions, rule_actions
from nrs_imitation.e1_contact_task_session import DEFAULT_SEED, EXECUTION_ORDERS, EXPERIMENT, make_plan, sha, write_plan_csv

SOURCE = ROOT / 'experiments/e1_contact_coverage_20261012/versions/20261013_force_cleanup_C/execution_C.json'
DATASET = ROOT / 'datasets/polishing/single_cam/e2_force_cleanup_20261012/imitation_form'


def save_json(path, value):
    payload = json.dumps(value, indent=2, ensure_ascii=False) + '\n'
    if path.exists():
        if json.loads(path.read_text()) != value:
            raise ValueError(f'Existing version differs: {path}; select a new --output-dir')
    else:
        with path.open('x') as stream:
            stream.write(payload)


def save_template(path, template, **arrays):
    if path.exists():
        saved = TimedActions.load(path)
        np.testing.assert_array_equal(saved.time, template.time)
        np.testing.assert_array_equal(saved.action, template.action)
        np.testing.assert_array_equal(saved.phase, template.phase)
        if saved.metadata != template.metadata:
            raise ValueError(f'Existing template metadata differs: {path}')
    else:
        with path.open('xb') as stream:
            np.savez_compressed(stream, time=template.time, action=template.action,
                phase=template.phase, metadata=np.array(json.dumps(template.metadata, ensure_ascii=False)), **arrays)


def export_cleanup_episode():
    episode = DATASET / 'episode_29.hdf5'
    manifest = json.loads((DATASET / 'force_preprocessing_manifest.json').read_text())
    if episode.name not in manifest['split']['train']:
        raise ValueError('episode_29 is absent from the recorded C optimization train split')
    with h5py.File(episode, 'r') as stream:
        attrs = dict(stream.attrs)
        assert attrs['relative_transform_version'] == 'stain_relative_v1'
        assert not attrs['rotation_aligned'] and not attrs['truncated']
        position, force = stream['action/position'][:], stream['action/force'][:]
        obs_position, obs_force = stream['observations/position'][:], stream['observations/force'][:]
        absolute = stream['analysis/absolute/action_position'][:]
        assert np.array_equal(position, obs_position)
        assert np.array_equal(force, obs_force)
        source_file, source_group = Path(str(attrs['source_h5'])), str(attrs['source_episode'])
        correction, origin = np.asarray(attrs['xyz_correction_mm']), np.asarray(attrs['stain_origin_xy_mm'])
    with h5py.File(source_file, 'r') as stream:
        source = stream['episodes/' + source_group]
        unix, source_idx = source['sample_time_unix'][:], source['source_index'][:]
        source_pose, source_ema_force = source['position'][:], source['ft'][:]
        sync_clock, record_hz = str(source.attrs['sync_clock']), float(source.attrs['record_hz'])
    assert len(position) == len(unix) == 443
    np.testing.assert_array_equal(source_idx, np.arange(len(unix)))
    expected_position = source_pose.copy()
    expected_position[:, :3] += correction
    np.testing.assert_allclose(absolute, expected_position, rtol=0, atol=5e-5)
    expected_relative = absolute.copy()
    expected_relative[:, :2] -= origin
    np.testing.assert_allclose(position, expected_relative, rtol=0, atol=5e-5)
    expected_force = source_ema_force.copy()
    expected_force[:, 2] = np.maximum(expected_force[:, 2], 0)
    expected_force[position[:, 2] > 175] = 0
    np.testing.assert_array_equal(force, expected_force)
    time = unix - unix[0]
    loaded_action = np.column_stack([position, force])
    indices = np.flatnonzero(force[:, 2] > 3.)
    work_start, work_end = int(indices[0]), int(indices[-1])
    metadata = dict(method='T', frame='stain_relative_v1', units=['mm', 'rotvec_rad', 'N'],
        task_type='line', source_episode=str(episode), episode_sha256=sha(episode),
        normalizer_sha256=json.loads(SOURCE.read_text())['il']['normalizer_sha256'],
        source_h5=str(source_file), source_h5_sha256=sha(source_file), source_group=source_group,
        source_timestamp_key='sample_time_unix', source_clock=sync_clock, source_record_hz=record_hz,
        source_time_origin_unix=float(unix[0]), source_index_mapping='identity; verified all 443 source indices',
        source_origin_xy_mm=origin.tolist(), xyz_correction_mm=correction.tolist(), rotation_aligned=False,
        source_action_sha256=hashlib.sha256(loaded_action.astype(np.float32).tobytes()).hexdigest(),
        scaling=1., smoothing='none', preprocessing_version='e2_force_cleanup_v1',
        force_preprocessing_manifest=str(DATASET / 'force_preprocessing_manifest.json'),
        force_preprocessing_manifest_sha256=sha(DATASET / 'force_preprocessing_manifest.json'),
        force_conversion='C cleanup action/force copied exactly; no rotation, gravity, offset, or sign reapplied',
        force_frame='published processed tool axes; native signed controller target interface retained',
        teacher_force_topic='/ftsensor/measured_Cvalue', selected_success=True,
        selection_evidence='User explicitly selected episode_29 as T source; new task does not infer success from that selection',
        phase_source='source Fz > 3N diagnostic boundaries, not independent evaluation task stages',
        source_work_indices=[work_start, work_end],
        source_work_time_s=[float(time[work_start]), float(time[work_end])],
        sync_boundary_s=float(time[work_start]), normal_teaching_exit_included=True,
        phase_labels_are_provider_diagnostics=True, force_audit_classification='A')
    original = TimedActions(time, loaded_action, np.full(len(time), 'source', dtype='<U24'), metadata)
    phase = np.full(len(time), 'approach', dtype='<U24')
    phase[work_start:work_end + 1] = 'processing'
    phase[work_end + 1:] = 'normal_release'
    template = TimedActions(time, loaded_action, phase, dict(metadata, preprocessing_template_version='E1_cleanup_replay_v1'))
    return original, template, unix, source_idx


def prepare(output=EXPERIMENT, delta_h_mm=1., seed=DEFAULT_SEED, execution_order='randomized_blocks'):
    output = Path(output).resolve()
    if not np.isfinite(delta_h_mm) or delta_h_mm <= 0:
        raise ValueError('delta_h_mm must be finite and positive')
    if execution_order not in EXECUTION_ORDERS:
        raise ValueError('unknown execution_order')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'templates').mkdir(exist_ok=True)
    source = json.loads(SOURCE.read_text())
    checkpoint = Path(source['il']['checkpoint'])
    if sha(checkpoint) != source['il']['checkpoint_sha256'] or sha(checkpoint.with_name('dataset_stats.pkl')) != source['il']['normalizer_sha256']:
        raise ValueError('C source checkpoint/normalizer identity mismatch')
    # Actual execution snapshot independently identifies the same cleanup model.
    recorded = ROOT / 'results/20261013/E1_contact_coverage/E1_contact_coverage_20261013/C/E1_CC_C_r1_20261013T195506_375fde77fd/execution_config.json'
    actual = json.loads(recorded.read_text())
    assert actual['il']['checkpoint'] == source['il']['checkpoint']
    assert actual['il']['checkpoint_sha256'] == source['il']['checkpoint_sha256']
    datum = np.array([457.4, 375.])
    ends = np.array([[445., 395., 172.], [487., 345., 172.]])
    length = float(np.linalg.norm(ends[1, :2] - ends[0, :2]))
    provenance = dict(surface_reference_z_mm=dict(value=172., origin='user approximate physical surface height; no TCP contact gate'),
        delta_h_mm=dict(value=delta_h_mm, origin='new experiment development default; physical placement by operator'),
        roi=dict(origin='user approximate endpoints/width adopted as new fixed task definition'),
        fixed_task_datum_xy_mm=dict(value=datum.tolist(), origin='audited original demonstration relative-coordinate registration; not stain midpoint'),
        event_confirm_s=dict(value=.2, origin='new event evaluation development default'),
        release_rise_mm=dict(value=5., origin='new displacement evaluation development default'),
        contact_gate=dict(on_N=3., off_N=1.2, origin='existing E1 executor measured base Fz hysteresis'),
        force_reference_upper_N=dict(value=30.812396273, origin='force audit v2 A; all42 demo base-axis Q95; analysis only'),
        common_execution=dict(path=str(SOURCE), sha256=sha(SOURCE)),
        actual_C_run=dict(path=str(recorded), sha256=sha(recorded)),
        stain_mask=dict(origin='user excluded mask validation; existing image interface retained'))
    task = dict(schema='E1_contact_task_definition_v1', experiment_version='20261014_v1',
        task='contact formation, one loaded ordered end-to-end pass inside fixed XY band, unload and rise',
        endpoints_base_mm=ends.tolist(), fixed_task_datum_xy_mm=datum.tolist(),
        length_mm=length, width_mm=25., half_width_mm=12.5, segment_count=14,
        TCP_center_occupancy=True, Z_height_gate_enabled=False, orientation_gate_enabled=False,
        pass_directions=['P0_to_P1', 'P1_to_P0'], pass_additional_reward=False,
        legacy_dwell_required_s=length / 14. / 10., legacy_dwell_is_primary=False,
        actual_removal_claim=False, provenance=provenance)
    evaluation = dict(schema='E1_contact_task_evaluation_v1', endpoints_base_mm=ends.tolist(),
        half_width_mm=12.5, segment_count=14, contact_on_N=3., contact_off_N=1.2,
        contact_event_confirm_s=.2, release_event_confirm_s=.2, event_confirm_s=.2,
        release_rise_mm=5., max_gap_s=.2, force_reference_upper_N=30.812396273,
        force_input_frame='robot_base', force_processing='none; already processed base-axis executor/wrench.csv',
        time_basis='same_host_receipt_monotonic_ns', force_interpolation='ZOH; no extrapolation',
        position_interpolation='linear inside recorded intervals; no extrapolation',
        legacy_dwell_required_s=length / 14. / 10., task_definition_file=str(output / 'task_definition.json'),
        evaluation_only=True, force_limit_or_stop_threshold=False, provenance=provenance)
    experiment = dict(schema='E1_contact_task_experiment_v1', experiment_version='20261014_v1',
        surface_reference_z_mm=172., delta_h_mm=delta_h_mm,
        height_conditions=dict(NOMINAL=0., HIGH=delta_h_mm, LOW=-delta_h_mm),
        height_is_metadata_only=True, physical_height_changed_by_label=False,
        task_definition_file=str(output / 'task_definition.json'), task_evaluation_file=str(output / 'task_evaluation.json'),
        seed=seed, planned_repeats=5, planned_trials=45, development_default=True,
        stage_immutable_at_session_creation=True, unattended_batch_execution=False,
        original_command_period_s=source['executor']['control_period_s'],
        original_C_trajectory_hz=source['il']['trajectory_hz'], original_C_stride_points=source['il']['replan_interval_steps'],
        original_C_chunk_points=source['il']['chunk_size'], RPM=source['common'].get('rpm_setpoint'),
        physical_setup_record_required_for_height_claim=True, provenance=provenance)
    if execution_order == 'method_blocks':
        experiment.update(experiment_version='20261014_method_blocks_v1',
            execution_order='method_blocks', randomized=False,
            execution_order_provenance='User requested R5 then T5 then C5; applied within each height condition',
            seed_usage='Recorded for reproducibility; method and height order are user-fixed')
    original_T, T, unix, source_idx = export_cleanup_episode()
    original_path = output / 'templates/episode_29_cleanup_original.npz'
    template_path = output / 'templates/episode_29_force_cleanup.npz'
    save_template(original_path, original_T, sample_time_unix=unix, source_index=source_idx)
    save_template(template_path, T, sample_time_unix=unix, source_index=source_idx)
    t_clock_path = output / 'templates/episode_29_source_clock.csv'
    if not t_clock_path.exists():
        with t_clock_path.open('x', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['derived_sample_index', 'source_sample_index', 'source_group', 'sample_time_unix', 'elapsed_s', 'provider_phase'])
            writer.writerows(zip(range(len(unix)), source_idx, [T.metadata['source_group']] * len(unix), unix, T.time, T.phase))
    # R uses the unchanged recipe work Z, source approach depths, and primitives.
    # Only the newly declared XY work line changes. No height-label offset is used.
    work_z = float(source['task']['endpoints_relative_mm'][0][2])
    rule_task = copy.deepcopy(source['task'])
    rule_task['endpoints_relative_mm'] = [[float(xy[0] - datum[0]), float(xy[1] - datum[1]), work_z] for xy in ends[:, :2]]
    rule_task['line_width_mm'] = 25.
    recipe = copy.deepcopy(source['recipe'])
    recipe.pop('return_home', None)
    recipe['approach']['waypoints_pose6'][-1] = rule_task['endpoints_relative_mm'][0] + rule_task['orientation_rotvec_rad']
    recipe['force_reference_N'], recipe['feed_speed_mm_s'], recipe['pass_count'] = 18., 10., 1
    recipe['normal_release'] = dict(primitive='e2_providers.pose_waypoint_actions',
        end_z_mm=float(source['common']['demo_start_pose6'][2]), at='final working XY',
        target_force_N=0., return_home=False,
        provenance='existing zero-force quintic waypoint primitive and existing source demo-start Z')
    R_work = rule_actions(rule_task, recipe, hz=125.)
    release_start = R_work.action[-1, :6].astype(float)
    release_end = release_start.copy()
    release_end[2] = source['common']['demo_start_pose6'][2]
    rt, ra, _ = pose_waypoint_actions([release_start, release_end],
        source['executor']['linear_speed_mm_s'], source['executor']['angular_speed_rad_s'], hz=125.)
    R = TimedActions(np.r_[R_work.time, R_work.time[-1] + rt[1:]],
        np.vstack([R_work.action, ra[1:]]),
        np.r_[R_work.phase, np.full(len(rt) - 1, 'normal_release')],
        dict(R_work.metadata, template_version='E1_rule_explicit_release_v1',
             sync_boundary_s=float(R_work.metadata['approach_duration_s']),
             normal_release_start_s=float(R_work.time[-1]),
             normal_release_in_plan=True, return_home_enabled=False,
             height_condition_pose_offset_applied=False))
    if R.time[-1] > source['common']['task_time_budget_s']:
        raise ValueError('Explicit R normal release exceeds existing50s budget; no automatic budget increase')
    R_path = output / 'templates/rule_contact_task.npz'
    save_template(R_path, R)
    common_template = copy.deepcopy(source)
    for key in ('e1_contact_coverage', 'e1_contact_coverage_definition', 'launch_context'):
        common_template.pop(key, None)
    common_template['task'] = rule_task
    common_template['recipe'] = recipe
    common_template['common']['reference_detection'] = 'fixed task datum XY override; existing translation-only interface'
    common_template['common']['task_datum_xy_mm'] = datum.tolist()
    common_template['common']['approach_retract_protocol'] = dict(
        approach='R source-backed approach; T original cleanup teacher approach; C policy approach through shared conditioner',
        finish='existing idling/cancel queue/Position hold after observed task completion or existing termination',
        retract='R explicit zero-force normal upward waypoint in its plan; T original teaching exit; C policy-generated exit',
        completion_scope='observed contact, ordered loaded pass, unload and rise; no home return success condition')
    common_template['common']['force_frame_sign_verification'].update(
        teacher_axis_equivalence_newly_verified=True,
        basis='force audit v2 A; user confirmed tool-mounted sensor +XYZ aligned; published corrections already applied',
        independent_physical_calibration_performed=False,
        force_audit_manifest=str(ROOT / 'reports/20261014_E1_correspondence_audit_v2_force/force_transform_evidence.json'))
    common_template['common']['use_stain_mask'] = False
    common_template['common']['stain_canon_enable'] = False
    common_template['replay'].update(template=str(template_path), source_dataset=str(DATASET),
        template_sha256=sha(template_path), original_template=str(original_path),
        original_template_sha256=sha(original_path), scaling=1., smoothing='none',
        preprocessing_version='e2_force_cleanup_v1', time_axis='original source ep_0003 sample_time_unix',
        resample_hz=None, source_record_hz=T.metadata['source_record_hz'],
        executor_command_hz=1. / source['executor']['control_period_s'])
    common_template['e1_contact_task'] = dict(schema='E1_contact_task_runtime_v1',
        task_definition_file=str(output / 'task_definition.json'), task_evaluation_file=str(output / 'task_evaluation.json'),
        fixed_task_datum_xy_mm=datum.tolist(), evaluation_only=True, finish_on_task_completed=True,
        height_condition_not_policy_input=True, planned_normal_release_provider=True)
    for method in ('R', 'T', 'C'):
        cfg = copy.deepcopy(common_template)
        plan = R if method == 'R' else T if method == 'T' else None
        cfg['e1_contact_task']['method'] = method
        cfg['e1_contact_task']['planned_normal_release_provider'] = method != 'C'
        cfg['e1_contact_task']['planner'] = (dict(template=str(R_path if method == 'R' else template_path),
            sync_boundary_s=plan.metadata['sync_boundary_s'], source_plan_end_s=float(plan.time[-1]),
            contact_start_sync=True, one_shot_only=True,
            contact_sync_version='confirmed_gate_receipt_clock_v2',
            contact_event_confirm_s=evaluation['contact_event_confirm_s'],
            max_observation_gap_s=evaluation['max_gap_s'],
            instantaneous_force_gate_unchanged=True,
            approach_progress_continues_without_contact=True,
            phase_labels_are_provider_diagnostics=True) if plan else dict(
            template=None, contact_start_sync=False, source_plan_end_s=None,
            evaluator_cannot_edit_policy_path=True))
        save_json(output / f'execution_{method}.json', cfg)
    for name, value in [('experiment_config.json', experiment), ('task_definition.json', task), ('task_evaluation.json', evaluation)]:
        save_json(output / name, value)
    plan = make_plan(seed, execution_order)
    save_json(output / 'trial_plan.json', plan)
    write_plan_csv(output / 'trial_plan.csv', plan)
    write_plan_csv(output / 'plan.csv', plan)
    manifest = dict(schema='E1_contact_task_preparation_v1', source_execution_config=str(SOURCE),
        source_execution_config_sha256=sha(SOURCE), actual_C_execution_snapshot=str(recorded),
        actual_C_execution_snapshot_sha256=sha(recorded), checkpoint=str(checkpoint),
        checkpoint_sha256=sha(checkpoint), normalizer_sha256=sha(checkpoint.with_name('dataset_stats.pkl')),
        T_template=dict(path=str(template_path), sha256=sha(template_path), sample_count=len(T.time),
            original_cleanup_template=str(original_path), duration_s=float(T.time[-1]),
            source_group=T.metadata['source_group'], sync_boundary_s=T.metadata['sync_boundary_s'],
            all_source_samples_times_poses_forces_exact=True, original_exit_included=True),
        R_template=dict(path=str(R_path), sha256=sha(R_path), duration_s=float(R.time[-1]),
            sync_boundary_s=R.metadata['sync_boundary_s'], release_start_s=R.metadata['normal_release_start_s'],
            unchanged_recipe_work_z_mm=work_z, normal_release_end_z_mm=float(release_end[2]),
            normal_release_in_plan=True, home_return_in_success=False),
        original_controller_executor_limits_unchanged=True, no_height_label_pose_offset=True,
        command_period_s=.008, command_hz=125., C_trajectory_hz=30., C_chunk_size=128, C_stride_points=120,
        hardware_executed_by_codex=False, physical_height_measured_by_codex=False)
    save_json(output / 'preparation_manifest.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=EXPERIMENT)
    parser.add_argument('--delta-h-mm', type=float, default=1.)
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED)
    parser.add_argument('--execution-order', choices=EXECUTION_ORDERS, default='randomized_blocks')
    args = parser.parse_args()
    print(json.dumps(prepare(args.output_dir, args.delta_h_mm, args.seed, args.execution_order), indent=2))


if __name__ == '__main__':
    main()
