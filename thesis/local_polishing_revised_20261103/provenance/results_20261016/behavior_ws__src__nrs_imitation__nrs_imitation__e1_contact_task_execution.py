"""New E1 adapters: one-time R/T clock alignment and recorded observations.

The existing timed executor retains all feedback checks, command conditioning,
rate limits, timeout, and stop behavior. No evaluation target drives motion.
"""
import numpy as np

from .e2_timed_execution import TimedExecution
from .e1_contact_metrics import Signal
from .e1_contact_task import TaskEvaluator, _support_index, _position, _fz, _force_metrics


class ContactStartClock:
    def __init__(self, boundary_s, confirm_s=0.2, max_gap_s=0.2):
        self.boundary_s = float(boundary_s)
        if not np.isfinite(self.boundary_s) or self.boundary_s < 0:
            raise ValueError('Finite nonnegative processing boundary required')
        self.start_s = self.contact_s = None
        self.source_elapsed_s = 0.0
        self.confirm_s, self.max_gap_s = float(confirm_s), float(max_gap_s)
        if not np.isfinite([self.confirm_s, self.max_gap_s]).all() or min(self.confirm_s, self.max_gap_s) <= 0:
            raise ValueError('Positive event confirmation and observation gap required')
        self.candidate_on_s = self.last_observation_s = None

    def start(self, now):
        self.start_s = float(now)
        self.contact_s = None
        self.source_elapsed_s = 0.0
        self.candidate_on_s = self.last_observation_s = None

    def sample(self, now, contact, observation_time_s=None):
        """Confirm the existing gate from distinct receipt times, once.

        The approach keeps advancing throughout confirmation. Cached feedback
        cannot supply additional duration, and OFF/unknown/gaps break it.
        """
        observation = float(now if observation_time_s is None else observation_time_s)
        just_synchronized = False
        if self.contact_s is None:
            valid = np.isfinite(observation) and self.start_s <= observation <= float(now)
            if not valid or contact is None:
                self.candidate_on_s = self.last_observation_s = None
            elif self.last_observation_s is None or observation > self.last_observation_s + 1e-10:
                if self.last_observation_s is not None and observation-self.last_observation_s > self.max_gap_s + 1e-10:
                    self.candidate_on_s = None
                self.last_observation_s = observation
                if contact:
                    if self.candidate_on_s is None:
                        self.candidate_on_s = observation
                    if observation-self.candidate_on_s >= self.confirm_s - 1e-10:
                        self.contact_s = float(now)
                        just_synchronized = True
                else:
                    self.candidate_on_s = None
        self.source_elapsed_s = (self.boundary_s + float(now) - self.contact_s
            if self.contact_s is not None else min(float(now) - self.start_s, self.boundary_s))
        return self.start_s + self.source_elapsed_s, just_synchronized


class ContactSynchronizedExecution(TimedExecution):
    """One finite R/T plan, using a confirmed original ON/OFF gate once."""
    def __init__(self, settings, boundary_s, contact_confirm_s=0.2, max_observation_gap_s=0.2):
        super().__init__(settings)
        self.reference_clock = ContactStartClock(boundary_s, contact_confirm_s, max_observation_gap_s)
        self.last_sync_event = None

    def start(self, now, pose):
        super().start(now, pose)
        self.reference_clock.start(now)

    def tick(self, now, pose, force, pose_age, force_age, **kwargs):
        if self.start_time is None:
            return super().tick(now, pose, force, pose_age, force_age, **kwargs)
        # Predict exactly the gate that TimedExecution updates below. This is
        # the existing measured-base-Fz event, not the task's confirmation.
        contact = self.contact
        force_array = np.asarray(force, float).reshape(-1) if force is not None else np.array([])
        if len(force_array) >= 3 and np.isfinite(force_array).all() and force_age <= self.cfg['feedback_max_age_s']:
            if not contact and force_array[2] >= self.cfg['contact_on_N']:
                contact = True
            elif contact and force_array[2] <= self.cfg['contact_off_N']:
                contact = False
        previous = self.reference_clock.source_elapsed_s
        fresh = (len(force_array) >= 3 and np.isfinite(force_array).all()
                 and 0 <= force_age <= self.cfg['feedback_max_age_s'])
        reference, synced = self.reference_clock.sample(now, contact if fresh else None,
            observation_time_s=float(now)-float(force_age))
        if synced:
            # Advance the private finite chunk view, then join the selected
            # work reference with the archived conditioner from the current
            # command. Its acceleration state is retained, never reset.
            if self.conditioner is not None:
                self.conditioner.sample(reference)
                self.conditioner.bridge_at = reference
                self.conditioner.bridge_pose = self.command[:6].copy()
                self.conditioner.bridge_velocity = self.conditioner.velocity.copy()
            self.last_sync_event = dict(contact_monotonic_s=float(now),
                source_boundary_s=self.reference_clock.boundary_s,
                approach_elapsed_before_sync_s=previous,
                source_elapsed_after_sync_s=self.reference_clock.source_elapsed_s,
                confirmation_start_observation_s=self.reference_clock.candidate_on_s,
                confirmation_duration_s=self.reference_clock.confirm_s,
                confirmation_end_observation_s=self.reference_clock.last_observation_s,
                kind='one_time_confirmed_existing_contact_gate_clock_sync')
        kwargs['reference_now'] = reference
        return super().tick(now, pose, force, pose_age, force_age, **kwargs)


class RecordedObservationEvaluator:
    """Incremental replay of the same rows saved by ExecutionRecorder.

    Waits for brackets in *both* streams; it never uses cached 125-Hz feedback
    as additional observations. The final offline replay remains authoritative.
    """
    def __init__(self, config, execution_start_s, interval_callback=None):
        self.evaluator = TaskEvaluator(config, execution_start_s)
        self.evidence_v2 = config.get("evaluation_version") == "pass_height_ref_v2"
        self.interval_callback = interval_callback
        self.source_rows = {"tcp_pose": [], "wrench": []}
        self._frozen_result = None
        self.cursor = float(execution_start_s)
        self.samples = {'tcp_pose': [], 'wrench': []}
        self.force_history = []
        self.closed = False

    def add(self, stream, row):
        if self.closed or stream not in self.samples:
            return
        fields = ('x', 'y', 'z') if stream == 'tcp_pose' else ('fx', 'fy', 'fz')
        time = int(row['receipt_monotonic_ns']) / 1e9
        values = np.asarray([row.get(k, np.nan) for k in fields], float)
        if self.evidence_v2 and (row.get("validity", "valid") != "valid" or not np.isfinite(values).all()):
            # Retain an invalid reception as an explicit break. Never skip it
            # and bridge valid samples around the missing observation.
            values[:] = np.nan
        seq = self.samples[stream]
        if seq and time <= seq[-1][0]:
            return
        seq.append((time, values))
        self.source_rows[stream].append(dict(row))
        if stream == 'wrench':
            self.force_history.append((time, values))
        self.consume()

    def signals(self):
        return tuple(Signal.synthetic([r[0] for r in self.samples[name]],
            [r[1] for r in self.samples[name]]) for name in ('tcp_pose', 'wrench'))

    def consume(self, end=None):
        pose, force = self.signals()
        if not len(pose.time) or not len(force.time):
            return
        watermark = min(float(pose.time[-1]), float(force.time[-1]))
        if end is not None:
            watermark = min(watermark, float(end))
        if watermark <= self.cursor:
            return
        stamps = {self.cursor, watermark}
        for signal in (pose, force):
            stamps.update(float(t) for t in signal.time if self.cursor < t < watermark)
        ordered = sorted(stamps)
        ev = self.evaluator
        for a, b in zip(ordered[:-1], ordered[1:]):
            pi = _support_index(pose, (a+b)/2, ev.config['max_gap_s'])
            fi = _support_index(force, (a+b)/2, ev.config['max_gap_s'])
            metadata = self.interval_sources(pi, fi) if self.evidence_v2 else None
            p0 = _position(pose, a, pi) if pi is not None else None
            p1 = _position(pose, b, pi) if pi is not None else None
            fz = _fz(force.value[fi]) if fi is not None else 0.
            observed = pi is not None and fi is not None
            if self.evidence_v2 and observed:
                observed = bool(np.isfinite(p0).all() and np.isfinite(p1).all() and np.isfinite(fz))
            if not observed:
                p0 = p1 = None
                fz = 0.
            if self.evidence_v2:
                ev.observe_interval(a, b, p0, p1, fz, observed=observed,
                                    source_metadata=metadata)
                if self.interval_callback is not None:
                    self.interval_callback(dict(start_s=float(a), end_s=float(b),
                        p0=None if p0 is None else p0.tolist(),
                        p1=None if p1 is None else p1.tolist(), fz_base_N=float(fz),
                        observed=bool(observed), source_metadata=metadata))
            else:
                ev.observe_interval(a, b, p0, p1, fz, observed=observed)
            if ev.completion_time_s is not None:
                self.cursor = ev.completion_time_s
                self.closed = True
                return
        self.cursor = watermark
        # Keep one left sample for interpolation and every pending right one.
        for name, rows in self.samples.items():
            left = max(0, int(np.searchsorted([r[0] for r in rows], self.cursor, side='right'))-1)
            self.samples[name] = rows[left:]
            self.source_rows[name] = self.source_rows[name][left:]

    def interval_sources(self, pose_index, force_index):
        """Identity of actual callback rows supporting this causal interval."""
        metadata = dict(source="observer_raw_receipt",
                        observation_source="received_observations_v2")
        if pose_index is not None:
            for side, offset in (("left", 0), ("right", 1)):
                row = self.source_rows["tcp_pose"][pose_index + offset]
                metadata["pose_" + side + "_sample_id"] = row.get("sample_id")
                metadata["pose_" + side + "_receipt_monotonic_ns"] = row["receipt_monotonic_ns"]
                metadata["pose_" + side + "_source_stamp_ns"] = row.get("source_stamp_ns")
        if force_index is not None:
            row = self.source_rows["wrench"][force_index]
            metadata["force_sample_id"] = row.get("sample_id")
            metadata["force_receipt_monotonic_ns"] = row["receipt_monotonic_ns"]
            metadata["force_source_stamp_ns"] = row.get("source_stamp_ns")
            right = self.source_rows["wrench"][force_index + 1]
            metadata["force_support_right_sample_id"] = right.get("sample_id")
            metadata["force_support_right_receipt_monotonic_ns"] = right["receipt_monotonic_ns"]
        return metadata

    def finalize(self, end, reason):
        if self._frozen_result is not None:
            return self._frozen_result
        self.consume(end)
        self.closed = True
        result = self.evaluator.finalize(end, reason)
        force = Signal.synthetic([r[0] for r in self.force_history], [r[1] for r in self.force_history])
        result.update(_force_metrics(force, self.evaluator.execution_start_s,
            result['evaluation_end_s'], self.evaluator.config))
        if self.evidence_v2:
            _qualify_force_support(result)
        result['force_metrics_scope'] = 'all observed force support independent of position support; offline analysis reports gaps explicitly'
        result['observer_version'] = 'received_observations_v2' if self.evidence_v2 else 'recorded_rows_v1'
        result['causal_observed_through_s'] = self.cursor
        result['post_stop_brackets_used'] = False
        self._frozen_result = result
        return result


def _qualify_force_support(result):
    """An integral over missing force support is a partial lower bound."""
    result['J_excess_observed_lower_bound_Ns'] = result['J_excess_Ns']
    result['force_metrics_complete'] = result['force_missing_duration_s'] <= 1e-8
    if not result['force_metrics_complete']:
        result['J_excess_Ns'] = None


def replay_evidence_events(events, config, execution_start_s, end_s, stop_reason,
                           relative_time=False):
    """Replay the exact causal inputs saved by the v2 observer, without ROS.

    Each ``task_observation_interval`` is the supported input actually consumed
    online. Its force/pose source identities remain in original receipt ns.
    Raw callback force rows supply the independent whole-window force integral.
    Rows received after the first stop cannot provide interpolation brackets.
    ``relative_time`` feeds zero-based semantic times for report compatibility;
    source timestamps are never shifted or synthesized.
    """
    shift = float(execution_start_s) if relative_time else 0.
    start = float(execution_start_s) - shift
    end = float(end_s) - shift
    evaluator = TaskEvaluator(config, start)
    force_rows = []
    force_breaks = []
    last_force_sequence = None
    intervals = []
    evidence_dropped = {'tcp_pose': 0, 'wrench': 0, 'intervals': 0}
    interval_sequences = []
    for event in events:
        details = event.get('details', {})
        name = event.get('event')
        if name == 'task_observation_received' and details.get('stream') == 'wrench':
            row = details['row']
            receipt = int(row['receipt_monotonic_ns']) / 1e9
            if receipt <= float(end_s) + 1e-10:
                values = np.asarray([row.get(key, np.nan) for key in ('fx', 'fy', 'fz')], float)
                if row.get('validity', 'valid') != 'valid' or not np.isfinite(values).all():
                    values[:] = np.nan
                sample_id = row.get('sample_id', '')
                try:
                    sequence = int(str(sample_id).rsplit(':', 1)[1])
                except (IndexError, ValueError):
                    sequence = None
                force_breaks.append(last_force_sequence is not None and
                    sequence is not None and sequence != last_force_sequence + 1)
                last_force_sequence = sequence
                force_rows.append((receipt - shift, values))
        elif name == 'task_observation_interval':
            interval = details['interval']
            if interval['end_s'] <= float(end_s) + 1e-10:
                intervals.append(interval)
                if details.get('interval_sequence') is not None:
                    interval_sequences.append(int(details['interval_sequence']))
        elif name == 'task_observer_finalized':
            evidence_dropped.update(details.get('observer_evidence_dropped', {}))
    for interval in intervals:
        a, b = float(interval['start_s']) - shift, float(interval['end_s']) - shift
        if b <= start or a >= end or evaluator.completion_time_s is not None:
            continue
        # Recorded intervals already begin at execution start and are bounded
        # by the actual causal watermark; partial intervals are not fabricated.
        if a < start - 1e-10 or b > end + 1e-10:
            raise ValueError('Observer interval lies outside its causal evaluation window')
        evaluator.observe_interval(a, b, interval.get('p0'), interval.get('p1'),
            interval.get('fz_base_N', 0.), observed=bool(interval['observed']),
            source_metadata=interval.get('source_metadata'))
    result = evaluator.finalize(end, stop_reason)
    force = Signal.synthetic([r[0] for r in force_rows], [r[1] for r in force_rows], force_breaks)
    result.update(_force_metrics(force, start, result['evaluation_end_s'], evaluator.config))
    _qualify_force_support(result)
    sequence_complete = not interval_sequences or interval_sequences == list(range(1, len(interval_sequences) + 1))
    result.update(observer_version='received_observations_v2',
        evidence_replay_source='exact_consumed_intervals_and_actual_received_force_rows',
        observer_evidence_dropped=evidence_dropped,
        observer_evidence_complete=not any(evidence_dropped.values()) and sequence_complete,
        causal_observed_through_s=evaluator._last_end,
        post_stop_brackets_used=False,
        force_metrics_scope='all actual pre-stop force receipts, independent of position support')
    return result
