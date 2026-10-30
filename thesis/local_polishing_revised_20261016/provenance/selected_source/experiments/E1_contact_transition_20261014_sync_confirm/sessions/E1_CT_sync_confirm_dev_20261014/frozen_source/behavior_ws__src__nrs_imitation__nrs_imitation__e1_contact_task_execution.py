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
    def __init__(self, config, execution_start_s):
        self.evaluator = TaskEvaluator(config, execution_start_s)
        self.cursor = float(execution_start_s)
        self.samples = {'tcp_pose': [], 'wrench': []}
        self.force_history = []
        self.closed = False

    def add(self, stream, row):
        if self.closed or stream not in self.samples:
            return
        fields = ('x', 'y', 'z') if stream == 'tcp_pose' else ('fx', 'fy', 'fz')
        time = int(row['receipt_monotonic_ns']) / 1e9
        values = np.asarray([row[k] for k in fields], float)
        seq = self.samples[stream]
        if seq and time <= seq[-1][0]:
            return
        seq.append((time, values))
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
            if pi is None or fi is None:
                ev.observe_interval(a, b, None, None, 0., observed=False)
            else:
                ev.observe_interval(a, b, _position(pose, a, pi), _position(pose, b, pi), _fz(force.value[fi]))
            if ev.completion_time_s is not None:
                self.cursor = ev.completion_time_s
                self.closed = True
                return
        self.cursor = watermark
        # Keep one left sample for interpolation and every pending right one.
        for name, rows in self.samples.items():
            left = max(0, int(np.searchsorted([r[0] for r in rows], self.cursor, side='right'))-1)
            self.samples[name] = rows[left:]

    def finalize(self, end, reason):
        self.consume(end)
        self.closed = True
        result = self.evaluator.finalize(end, reason)
        force = Signal.synthetic([r[0] for r in self.force_history], [r[1] for r in self.force_history])
        result.update(_force_metrics(force, self.evaluator.execution_start_s,
            result['evaluation_end_s'], self.evaluator.config))
        result['force_metrics_scope'] = 'all observed force support independent of position support; offline analysis reports gaps explicitly'
        return result
