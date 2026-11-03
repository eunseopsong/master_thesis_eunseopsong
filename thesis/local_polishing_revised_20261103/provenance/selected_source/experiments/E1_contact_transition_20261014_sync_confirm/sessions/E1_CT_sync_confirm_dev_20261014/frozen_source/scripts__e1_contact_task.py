#!/usr/bin/env python3
"""Manage an immutable E1 session and explicitly start at most one selected trial."""
import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'behavior_ws/src/nrs_imitation'))
from nrs_imitation.e1_contact_task_session import (DEFAULT_SEED, EXPERIMENT, allocate_attempt,
    init_session, make_plan, peek_trial, record_surface_setup, record_analysis_result, session_directory)


def launch_command(config, method, cfg, *, check=False):
    command = ['ros2', 'launch', 'nrs_imitation', 'e1_contact_task.launch.py',
               'config:=' + str(config), 'method:=' + method, 'mode:=' + ('check' if check else 'run')]
    if method == 'C':
        command += ['checkpoint:=' + cfg['il']['checkpoint']]
    if method == 'T':
        command += ['episode:=' + cfg['replay']['episode_id']]
    return command


def run_launch(command, cwd):
    """Wait for the existing ROS launch shutdown before analyzing its logs.

    A terminal sends SIGINT to its whole foreground process group, including
    the launch and its nodes. Do not kill it while its existing controlled
    stop is still being verified, and do not discard the aborted attempt.
    """
    try:
        process = subprocess.Popen(command, cwd=cwd)
    except OSError as exc:
        return 127, str(exc), False
    interrupted = False
    while True:
        try:
            return process.wait(), None, interrupted
        except KeyboardInterrupt:
            interrupted = True
            print('중단 요청 후 기존 ROS 종료와 기록 마무리를 기다립니다.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'plan', 'status', 'show', 'record-surface', 'run', 'next'])
    parser.add_argument('--session', default='E1_contact_transition_dev_20261014')
    parser.add_argument('--stage', choices=['development', 'main'], default='development')
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED)
    parser.add_argument('--config-dir', type=Path, default=EXPERIMENT)
    parser.add_argument('--method', choices=['next', 'R', 'T', 'C'], default='next')
    parser.add_argument('--height-condition', choices=['NOMINAL', 'HIGH', 'LOW'])
    parser.add_argument('--retry-of', default='')
    parser.add_argument('--retry-reason', default='')
    parser.add_argument('--statement', default='', help='Operator report describing the actual current physical placement')
    parser.add_argument('--relative-height-mm', type=float, help='Optional operator-reported measurement, never inferred from label')
    parser.add_argument('--measurement-method')
    parser.add_argument('--execute', action='store_true', help='Explicitly run one ROS launch; otherwise preview only')
    args = parser.parse_args()
    settings = dict(stage=args.stage, seed=args.seed, config_dir=args.config_dir)
    if args.command == 'init':
        manifest, directory = init_session(args.session, **settings)
        print(json.dumps(dict(session_directory=str(directory), manifest=manifest), indent=2))
    elif args.command == 'plan':
        path = session_directory(args.session, args.config_dir) / 'trial_plan.json'
        if path.exists():
            plan = json.loads(path.read_text())
        else:
            experiment = json.loads((args.config_dir / 'experiment_config.json').read_text())
            plan = make_plan(args.seed, experiment.get('execution_order', 'randomized_blocks'))
        print(json.dumps(plan, indent=2))
    elif args.command == 'status':
        directory = session_directory(args.session, args.config_dir)
        attempts_path = directory / 'attempts.json'
        attempts = json.loads(attempts_path.read_text()) if attempts_path.exists() else []
        print(json.dumps(dict(session=args.session, attempts=attempts,
            next_trial=peek_trial(args.session, args.method, args.height_condition, **settings)
            if len({row['plan_index'] for row in attempts if not row.get('retry_of')}) < 45 else None), indent=2))
    elif args.command == 'record-surface':
        if args.height_condition is None:
            parser.error('record-surface requires --height-condition')
        print(json.dumps(record_surface_setup(args.session, args.height_condition, args.statement,
            relative_height_mm=args.relative_height_mm, measurement_method=args.measurement_method, **settings), indent=2))
    else:
        trial = peek_trial(args.session, args.method, args.height_condition,
                           retry_of=args.retry_of or None, **settings)
        method = trial['method']
        config = args.config_dir / f'execution_{method}.json'
        cfg = json.loads(config.read_text())
        if args.command == 'show' or not args.execute:
            print(json.dumps(dict(selected_trial=trial, stage=args.stage,
                fixed_task_datum_xy_mm=cfg['e1_contact_task']['fixed_task_datum_xy_mm'],
                planner=cfg['e1_contact_task']['planner'],
                single_trial=True, attempt_allocated=False, robot_started=False,
                instruction='Add --execute to allocate and start exactly this one trial; record actual physical setup separately'), indent=2))
            command = [sys.executable, str(ROOT / 'scripts/e1_contact_task.py'), 'run',
                       '--session', args.session, '--stage', args.stage, '--seed', str(args.seed),
                       '--config-dir', str(args.config_dir), '--method', method,
                       '--height-condition', trial['height_condition'], '--execute']
            if args.retry_of:
                command += ['--retry-of', args.retry_of, '--retry-reason', args.retry_reason]
            print(shlex.join(command))
            return
        context, run, cfg = allocate_attempt(args.session, method, trial['height_condition'],
            retry_of=args.retry_of, retry_reason=args.retry_reason, **settings)
        command = launch_command(run / 'execution_config.json', method, cfg)
        print('Single trial directory: ' + str(run), flush=True)
        print('Physical setup: ' + context['physical_setup_status'] + '; label alone is not a measured height change', flush=True)
        print(shlex.join(command), flush=True)
        with (run / 'wrapper_command.json').open('x') as stream:
            json.dump(dict(command=command, one_trial_only=True,
                context_file=str(run / 'run_context.json')), stream, indent=2)
            stream.write('\n')
        returncode, launch_error, interrupted = run_launch(command, ROOT)
        with (run / 'wrapper_exit.json').open('x') as stream:
            json.dump(dict(process_returncode=returncode, launch_error=launch_error,
                wrapper_interrupted=interrupted,
                outcome_is_not_inferred_from_process_exit=True), stream, indent=2)
            stream.write('\n')
        # ROS shutdown has completed here. Both readers operate only on saved
        # files; they never start the next robot trial or emit control commands.
        analyzer = ROOT / 'scripts/analyze_e1_contact_task.py'
        analysis_commands = [[sys.executable, str(analyzer), '--run-directory', str(run),
                '--output', str(run / 'analysis')],
            [sys.executable, str(analyzer), '--session', context['session_directory'],
                '--output', str(ROOT / 'reports/E1_contact_transition_20261014/sessions' / args.session)]]
        analysis_results = []
        for analysis_command in analysis_commands:
            with (run / 'post_analysis_stdout.log').open('a') as stream:
                observed = subprocess.run(analysis_command, cwd=ROOT, check=False,
                    stdout=stream, stderr=subprocess.STDOUT)
                analysis_results.append(dict(command=analysis_command, returncode=observed.returncode))
            if len(analysis_results) == 1 and observed.returncode == 0:
                outcome_file = run / 'analysis' / 'runs' / context['run_id'] / 'outcome.json'
                if outcome_file.exists():
                    metrics = json.loads(outcome_file.read_text())
                    record_analysis_result(context, dict(metrics,
                        task_outcome=metrics.get('outcome'), last_stage=metrics.get('phase'),
                        failure_reason=metrics.get('failure_stage'),
                        original_stop_reason=metrics.get('original_stop_reason', metrics.get('stop_reason'))))
        with (run / 'post_analysis_exit.json').open('x') as stream:
            json.dump(analysis_results, stream, indent=2)
            stream.write('\n')
        if launch_error:
            print('Single-trial launch failed: ' + launch_error, file=sys.stderr)
        raise SystemExit(130 if interrupted else returncode)


if __name__ == '__main__':
    main()
