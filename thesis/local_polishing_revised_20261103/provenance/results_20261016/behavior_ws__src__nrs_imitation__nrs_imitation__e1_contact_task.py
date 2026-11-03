"""Observed contact-task milestones, independent of providers and robot commands.

Positions are measured robot-base TCP millimetres and force is already processed
robot-base Fz in newtons.  This module never rotates or corrects either input and
has no ROS, publisher, controller, or execution dependencies.

``observe_interval`` accepts proven continuous joint support: force ZOH and a
linear TCP segment. The signal adapter verifies receipt-clock gaps before
supplying that support. Milestones use positive-duration intervals, never an
isolated point. Event times and ``TaskEvaluator.completion_time_s`` use the
caller's clock; the result's ``completion_time_s`` is elapsed execution time.

Frozen old configs retain ``first_contact_ref_v1`` by default. Explicit
``pass_height_ref_v2`` uses the continuous-time measured-Z lower median of the
first successful loaded pass as its release-height reference. This changes
only observed completion; it never produces a path or modifies a force gate
used by a controller or provider.
"""

import math

import numpy as np


DEFAULTS = {
    'evaluation_version': 'first_contact_ref_v1',
    'endpoints_base_mm': [[445.0, 395.0, 172.0], [487.0, 345.0, 172.0]],
    'half_width_mm': 12.5,
    'segment_count': 14,
    'contact_on_N': 3.0,
    'contact_off_N': 1.2,
    'contact_event_confirm_s': 0.2,
    'release_event_confirm_s': 0.2,
    'release_rise_mm': 5.0,
    'max_gap_s': 0.2,
    'force_reference_upper_N': 30.812396273,
}
EPS = 1e-10


def normalize_config(config):
    """Accept an experiment's task_evaluation mapping or its direct mapping."""
    supplied = (config or {}).get('task_evaluation', config or {})
    result = dict(DEFAULTS)
    result.update({key: supplied[key] for key in DEFAULTS if key in supplied})
    endpoints = np.asarray(result['endpoints_base_mm'], dtype=float)
    if endpoints.shape != (2, 3) or not np.isfinite(endpoints).all():
        raise ValueError('endpoints_base_mm must contain two finite xyz points')
    if np.linalg.norm(endpoints[1, :2] - endpoints[0, :2]) <= EPS:
        raise ValueError('Task XY centerline must have positive length')
    count = result['segment_count']
    if isinstance(count, bool) or int(count) != count or count < 2:
        raise ValueError('segment_count must be an integer >= 2')
    result['segment_count'] = int(count)
    if result['evaluation_version'] not in ('first_contact_ref_v1', 'pass_height_ref_v2'):
        raise ValueError('Unknown evaluation_version')
    for key in DEFAULTS:
        if key in ('endpoints_base_mm', 'segment_count', 'evaluation_version'):
            continue
        value = float(result[key])
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f'{key} must be finite and positive')
        result[key] = value
    if result['contact_off_N'] >= result['contact_on_N']:
        raise ValueError('Require OFF threshold < ON threshold')
    result['endpoints_base_mm'] = endpoints.tolist()
    return result


def _weighted_z_median(pieces):
    """Time median of measured linearly interpolated Z over confirmation support."""
    total = sum(duration for _, _, duration in pieces)
    lower = min(min(a, b) for a, b, _ in pieces)
    upper = max(max(a, b) for a, b, _ in pieces)
    if upper - lower <= EPS:
        return float(lower)
    # Each nonconstant linear segment contributes a uniform Z distribution;
    # constant segments are point masses. Find the lower median by its CDF.
    for _ in range(70):
        value = (lower + upper) / 2.0
        mass = 0.0
        for a, b, duration in pieces:
            lo, hi = min(a, b), max(a, b)
            if hi - lo <= EPS:
                mass += duration if value >= lo else 0.0
            else:
                mass += duration * float(np.clip((value - lo) / (hi - lo), 0, 1))
        if mass >= total / 2.0:
            upper = value
        else:
            lower = value
    return float((lower + upper) / 2.0)


def time_weighted_z_median(pieces):
    """Lower continuous-time median, vectorized for full-rate pass support.

    The legacy first-contact helper above deliberately remains unchanged.
    ``pieces`` contains measured linear Z endpoints and positive durations.
    Each constant piece is a point mass; each changing piece contributes its
    time uniformly between its endpoints. No resampling or sample-count weight
    is introduced. Online and offline v2 evaluation call this same function.
    """
    values = np.asarray(pieces, dtype=float)
    if values.ndim != 2 or values.shape[1] != 3 or not len(values):
        raise ValueError('Time median requires nonempty Z endpoint/duration pieces')
    if not np.isfinite(values).all() or np.any(values[:, 2] <= 0):
        raise ValueError('Time median requires finite values and positive durations')
    lo = np.minimum(values[:, 0], values[:, 1])
    hi = np.maximum(values[:, 0], values[:, 1])
    weights = values[:, 2]
    constant = hi - lo <= EPS
    span = np.where(constant, 1.0, hi - lo)
    lower, upper = float(np.min(lo)), float(np.max(hi))
    if upper - lower <= EPS:
        return lower
    half_time = float(np.sum(weights)) / 2.0
    # A half-mass tie must retain the lower median when equal support is split
    # differently into receipt intervals. This tolerance covers floating-point
    # summation only; it is many orders below an observed time resolution.
    mass_roundoff = 8.0 * np.finfo(float).eps * float(np.sum(weights))
    for _ in range(70):
        value = (lower + upper) / 2.0
        fraction = np.where(constant, value >= lo, np.clip((value - lo) / span, 0.0, 1.0))
        if float(np.sum(weights * fraction)) >= half_time - mass_roundoff:
            upper = value
        else:
            lower = value
    return float((lower + upper) / 2.0)


class TaskEvaluator:
    """Per-attempt observed-only evaluator; instantiate/reset for every run."""

    def __init__(self, config=None, execution_start_s=0.0):
        self.config = normalize_config(config)
        self.execution_start_s = float(execution_start_s)
        if not math.isfinite(self.execution_start_s):
            raise ValueError('execution_start_s must be finite')
        self.endpoints = np.asarray(self.config['endpoints_base_mm'], float)
        delta = self.endpoints[1, :2] - self.endpoints[0, :2]
        self.length_mm = float(np.linalg.norm(delta))
        self.along = delta / self.length_mm
        self.across = np.array([-self.along[1], self.along[0]])
        self.edges = np.linspace(0, self.length_mm, self.config['segment_count'] + 1)
        self.phase = 'WAIT_CONTACT'
        self.gate = None
        self.events = []
        self.completion_time_s = None
        self.contact_at_s = None
        self.contact_started_at_s = None
        self.pass_completed_at_s = None
        self.release_at_s = None
        self.z_contact_ref_mm = None
        self.z_work_ref_mm = None
        self.z_release_threshold_mm = None
        self.work_reference_support = []
        self.work_reference_frozen_at_s = None
        self._contact_start = None
        self._contact_pieces = []
        self._release_start = None
        self._candidate = None
        self.pass_candidates = []
        self.visited_segments = set()
        self.best_pass_segments = []
        self.contact_loss_count = 0
        self.contact_loss_duration_s = 0.0
        self.observed_duration_s = 0.0
        self.missing_duration_s = 0.0
        self.discontinuity_count = 0
        self.tcp_xy_distance_mm = 0.0
        self.J_excess_Ns = 0.0
        self.force_excess_duration_s = 0.0
        self.peak_Fz_base_N = None
        self._last_end = self.execution_start_s
        self._last_pose = None
        self._had_missing = False
        self._finalized = None
        self._event('phase_entered', self.execution_start_s, phase=self.phase)

    def _event(self, kind, time, **data):
        self.events.append(dict(event=kind, time_s=float(time),
                                elapsed_s=float(time - self.execution_start_s), **data))

    def spatial_coordinates(self, pose):
        delta = np.asarray(pose, float)[:2] - self.endpoints[0, :2]
        return float(delta @ self.along), float(delta @ self.across)

    def segment_index(self, pose):
        s, d = self.spatial_coordinates(pose)
        if s < -EPS or s > self.length_mm + EPS or abs(d) > self.config['half_width_mm'] + EPS:
            return None
        # Tolerance handles roundoff at a recorded endpoint, not positions
        # outside the domain. No off-domain samples are assigned to end bins.
        if abs(s - self.length_mm) <= EPS:
            return self.config['segment_count'] - 1
        if s < 0:
            s = 0.0
        return min(int(np.searchsorted(self.edges, s, side='right') - 1),
                   self.config['segment_count'] - 1)

    def _end_candidate(self, time, reason):
        if self._candidate is None:
            return
        candidate = dict(self._candidate)
        candidate.update(end_s=float(time), completed=False, interruption_reason=reason)
        self.pass_candidates.append(candidate)
        self._event('pass_interrupted', time, reason=reason,
                    visited_segments=list(candidate['visited_segments']))
        self._candidate = None

    def _break_support(self, start, end, reason):
        self._end_candidate(start, reason)
        self._contact_start = None
        self._contact_pieces = []
        self._release_start = None
        self.gate = None
        self._last_pose = None
        self._had_missing = True
        self.missing_duration_s += max(0.0, end - start)
        self._event('observation_gap', start, end_s=float(end), reason=reason)

    def _set_gate(self, time, force, source_metadata=None):
        previous = self.gate
        if force >= self.config['contact_on_N']:
            self.gate = True
        elif force <= self.config['contact_off_N']:
            self.gate = False
        # In the hysteresis interval an UNKNOWN state stays UNKNOWN: missing
        # support must never be filled with an assumed previous contact state.
        if self.gate != previous:
            evidence = {} if source_metadata is None else {'source_metadata': dict(source_metadata)}
            self._event('contact_gate', time, contact=self.gate, fz_base_N=float(force), **evidence)
            if previous is True and self.gate is False:
                if self.phase == 'CONTACT_OBSERVED':
                    self.contact_loss_count += 1
                self._end_candidate(time, 'contact_off')
        if self.gate is not True:
            self._contact_start = None
            self._contact_pieces = []
            self._end_candidate(time, 'contact_off' if self.gate is False else 'contact_unknown')

    def _track_pass(self, start, end, index, p0, p1, source_metadata=None):
        if self.phase != 'CONTACT_OBSERVED':
            return
        if self.gate is not True:
            return
        if index is None:
            self._end_candidate(start, 'outside_task_strip')
            return
        self.visited_segments.add(index)
        last_bin = self.config['segment_count'] - 1
        if self._candidate is None:
            if index not in (0, last_bin):
                return
            self._candidate = dict(start_s=float(start), direction=1 if index == 0 else -1,
                                   visited_segments=[index], visit_times_s=[float(end)])
            if self.config['evaluation_version'] == 'pass_height_ref_v2':
                self._candidate['work_reference_support'] = []
            self._event('pass_started', start, direction=self._candidate['direction'], segment=index)
        else:
            sequence = self._candidate['visited_segments']
            expected = sequence[-1] + self._candidate['direction']
            if index == expected:
                sequence.append(index)
                self._candidate['visit_times_s'].append(float(end))
            elif index not in sequence:
                self._end_candidate(start, 'nonadjacent_segment')
                self._track_pass(start, end, index, p0, p1, source_metadata)
                return
        if self.config['evaluation_version'] == 'pass_height_ref_v2':
            # These slices are jointly observed, in the fixed ROI, and ON.
            # Their actual durations, not command-loop counts, supply weight.
            self._candidate['work_reference_support'].append({
                'start_s': float(start), 'end_s': float(end),
                'z_start_mm': float(p0[2]), 'z_end_mm': float(p1[2]),
                'duration_s': float(end - start),
                'source_metadata': None if source_metadata is None else dict(source_metadata),
            })
        sequence = self._candidate['visited_segments']
        if len(sequence) > len(self.best_pass_segments):
            self.best_pass_segments = list(sequence)
        if len(sequence) == self.config['segment_count']:
            candidate = dict(self._candidate)
            candidate.update(end_s=float(end), completed=True, interruption_reason=None)
            self.pass_candidates.append(candidate)
            self._candidate = None
            self.pass_completed_at_s = float(end)
            if self.config['evaluation_version'] == 'pass_height_ref_v2':
                self.work_reference_support = list(candidate['work_reference_support'])
                self.z_work_ref_mm = time_weighted_z_median([
                    (piece['z_start_mm'], piece['z_end_mm'], piece['duration_s'])
                    for piece in self.work_reference_support
                ])
                self.z_release_threshold_mm = self.z_work_ref_mm + self.config['release_rise_mm']
                self.work_reference_frozen_at_s = float(end)
            self.phase = 'REQUIRED_PASS_OBSERVED'
            evidence = {} if self.config['evaluation_version'] != 'pass_height_ref_v2' else {
                'z_work_ref_mm': self.z_work_ref_mm,
                'z_release_threshold_mm': self.z_release_threshold_mm,
                'work_reference_start_s': candidate['start_s'],
                'work_reference_end_s': candidate['end_s'],
                'work_reference_valid_duration_s': sum(p['duration_s'] for p in self.work_reference_support),
                'work_reference_piece_count': len(self.work_reference_support),
            }
            self._event('phase_entered', end, phase=self.phase,
                        direction=candidate['direction'], visited_segments=list(sequence), **evidence)

    def _consume(self, start, end, p0, p1, force, source_metadata=None):
        """Consume a slice homogeneous in XY occupancy and release height."""
        if end - start <= EPS or self.completion_time_s is not None:
            return
        self._set_gate(start, force, source_metadata)
        cut = end
        if self.phase == 'WAIT_CONTACT' and self.gate is True:
            if self._contact_start is None:
                self._contact_start = start
            confirm = self._contact_start + self.config['contact_event_confirm_s']
            if start < confirm < end - EPS:
                cut = confirm
        release_ok = (self.phase == 'REQUIRED_PASS_OBSERVED' and self.gate is False
                      and self.z_release_threshold_mm is not None
                      and (p0[2] + p1[2]) / 2.0 >= self.z_release_threshold_mm - EPS)
        if release_ok:
            if self._release_start is None:
                self._release_start = start
            confirm = self._release_start + self.config['release_event_confirm_s']
            if start < confirm < cut - EPS:
                cut = confirm
        else:
            self._release_start = None
        fraction = (cut - start) / (end - start)
        pc = p0 + fraction * (p1 - p0)
        duration = cut - start
        self.observed_duration_s += duration
        self.tcp_xy_distance_mm += float(np.linalg.norm(pc[:2] - p0[:2]))
        excess = max(force - self.config['force_reference_upper_N'], 0.0)
        self.J_excess_Ns += excess * duration
        if excess > 0:
            self.force_excess_duration_s += duration
        self.peak_Fz_base_N = force if self.peak_Fz_base_N is None else max(self.peak_Fz_base_N, force)
        if self.phase == 'CONTACT_OBSERVED' and self.gate is False:
            self.contact_loss_duration_s += duration
        if self.phase == 'WAIT_CONTACT' and self.gate is True:
            self._contact_pieces.append((float(p0[2]), float(pc[2]), duration))
            if cut >= self._contact_start + self.config['contact_event_confirm_s'] - EPS:
                self.contact_started_at_s = float(self._contact_start)
                self.contact_at_s = float(cut)
                median = (time_weighted_z_median if self.config['evaluation_version'] == 'pass_height_ref_v2'
                          else _weighted_z_median)
                self.z_contact_ref_mm = median(self._contact_pieces)
                if self.config['evaluation_version'] == 'first_contact_ref_v1':
                    self.z_release_threshold_mm = self.z_contact_ref_mm + self.config['release_rise_mm']
                self.phase = 'CONTACT_OBSERVED'
                self._event('phase_entered', cut, phase=self.phase,
                            confirmation_start_s=self.contact_started_at_s,
                            z_contact_ref_mm=self.z_contact_ref_mm)
                # Confirmation support itself is not retroactively pooled into
                # the ordered pass. The next positive contact span starts it.
        else:
            self._track_pass(start, cut, self.segment_index((p0 + pc) / 2.0), p0, pc, source_metadata)
        if release_ok and cut >= self._release_start + self.config['release_event_confirm_s'] - EPS:
            self.release_at_s = float(cut)
            self.phase = 'RELEASE_OBSERVED'
            self._event('phase_entered', cut, phase=self.phase,
                        confirmation_start_s=float(self._release_start))
            self.phase = 'TASK_COMPLETED'
            self.completion_time_s = float(cut)
            self._event('phase_entered', cut, phase=self.phase)
        if cut < end - EPS and self.completion_time_s is None:
            self._consume(cut, end, pc, p1, force, source_metadata)

    def observe_interval(self, start_s, end_s, pose_start_xyz, pose_end_xyz,
                         fz_base_N, observed=True, source_metadata=None):
        """Add positive-duration jointly supported data; never issue commands.

        Callers establish continuity and the source-record max-gap rule. Use
        observed=False for unavailable intervals. Backwards/overlapping input is
        rejected, and a changed TCP at a shared boundary is a discontinuity.
        A finalized evaluator ignores later observations (including recovery).
        Optional source_metadata identifies the actual receipt samples that
        bracket this support. It affects evidence only, never signal values.
        """
        if self._finalized is not None or self.completion_time_s is not None:
            return
        start, end = float(start_s), float(end_s)
        if not math.isfinite(start) or not math.isfinite(end) or end <= start:
            raise ValueError('Intervals require finite start < end')
        if start < self._last_end - EPS:
            raise ValueError('Observation intervals must not overlap or go backwards')
        if start > self._last_end + EPS:
            self._break_support(self._last_end, start, 'missing_interval')
        if not observed:
            self._break_support(start, end, 'unobserved_source_support')
            self._last_end = end
            return
        p0, p1 = np.asarray(pose_start_xyz, float)[:3], np.asarray(pose_end_xyz, float)[:3]
        force = float(fz_base_N)
        if p0.shape != (3,) or p1.shape != (3,) or not np.isfinite(p0).all() or not np.isfinite(p1).all() or not math.isfinite(force):
            self._break_support(start, end, 'invalid_values')
            self._last_end = end
            return
        if self._last_pose is not None and np.linalg.norm(p0 - self._last_pose) > 1e-7:
            self.discontinuity_count += 1
            self._break_support(start, start, 'position_discontinuity')
        # Exact crossings split both directions. Midpoint occupancy preserves
        # half-open length bins and cannot grant several visits to one point.
        s0, d0 = self.spatial_coordinates(p0)
        s1, d1 = self.spatial_coordinates(p1)
        crossings = [0.0, 1.0]
        tests = [(s0, s1, boundary) for boundary in self.edges]
        tests += [(d0, d1, boundary) for boundary in (-self.config['half_width_mm'], self.config['half_width_mm'])]
        if self.z_release_threshold_mm is not None:
            tests.append((p0[2], p1[2], self.z_release_threshold_mm))
        for value0, value1, boundary in tests:
            if abs(value1 - value0) > EPS:
                fraction = (boundary - value0) / (value1 - value0)
                if EPS < fraction < 1.0 - EPS:
                    crossings.append(float(fraction))
        crossings = sorted(set(crossings))
        for left, right in zip(crossings[:-1], crossings[1:]):
            if self.completion_time_s is not None:
                break
            self._consume(start + left * (end - start), start + right * (end - start),
                          p0 + left * (p1 - p0), p0 + right * (p1 - p0), force, source_metadata)
        self._last_end = self.completion_time_s if self.completion_time_s is not None else end
        self._last_pose = p1.copy()

    def finalize(self, end_s, stop_reason=None):
        """Freeze at the first end/stop; later recovery cannot change outcome."""
        if self._finalized is not None:
            return self._finalized
        requested_end = float(end_s)
        if not math.isfinite(requested_end) or requested_end < self.execution_start_s:
            raise ValueError('end_s must be finite and not precede execution start')
        if self.completion_time_s is not None:
            end = self.completion_time_s
        else:
            if requested_end < self._last_end - EPS:
                raise ValueError('Finalize before consumed observations; cut at stop before observation')
            end = requested_end
            if end > self._last_end + EPS:
                self._break_support(self._last_end, end, 'missing_final_support')
            self._end_candidate(end, 'evaluation_window_end')
        completed = self.completion_time_s is not None
        outcome = 'completed' if completed else ('observation_unavailable' if self._had_missing else 'incomplete')
        duration = end - self.execution_start_s
        self._event('evaluation_finalized', end, outcome=outcome, stop_reason=stop_reason)
        self._finalized = {
            'evaluation_version': self.config['evaluation_version'],
            'completed': completed,
            'completion_observed': completed,
            'outcome': outcome,
            'phase': self.phase,
            'failure_stage': None if completed else self.phase,
            'execution_start_s': self.execution_start_s,
            'evaluation_end_s': float(end),
            'actual_execution_time_s': float(duration),
            'completion_at_s': self.completion_time_s,
            'completion_time_s': None if not completed else self.completion_time_s - self.execution_start_s,
            'contact_started_at_s': self.contact_started_at_s,
            'contact_at_s': self.contact_at_s,
            'pass_completed_at_s': self.pass_completed_at_s,
            'release_at_s': self.release_at_s,
            'contact_to_complete_s': None if not completed else self.completion_time_s - self.contact_at_s,
            'z_contact_ref_mm': self.z_contact_ref_mm,
            'z_first_contact_mm': self.z_contact_ref_mm,
            'z_work_ref_mm': self.z_work_ref_mm,
            'z_release_threshold_mm': self.z_release_threshold_mm,
            'work_reference_frozen_at_s': self.work_reference_frozen_at_s,
            'work_reference_start_s': None if not self.work_reference_support else self.work_reference_support[0]['start_s'],
            'work_reference_end_s': None if not self.work_reference_support else self.work_reference_support[-1]['end_s'],
            'work_reference_valid_duration_s': sum(p['duration_s'] for p in self.work_reference_support),
            'work_reference_piece_count': len(self.work_reference_support),
            'work_reference_support': self.work_reference_support,
            'work_reference_definition': (
                'Lower median of the continuous-time distribution of actual TCP Z, '
                'linearly interpolated only on jointly observed in-ROI ON support of '
                'the first successfully completed ordered pass; each piece weighted '
                'by end_s-start_s. Constants are point masses; nonconstant pieces '
                'are uniform in Z. Frozen causally at first REQUIRED_PASS_OBSERVED.'
            ),
            'contact_loss_count': self.contact_loss_count,
            'contact_loss_duration_s': self.contact_loss_duration_s,
            'segments_visited': sorted(self.visited_segments),
            'ordered_pass_segment_count': len(self.best_pass_segments),
            'ordered_pass_segments': list(self.best_pass_segments),
            'missing_segments': sorted(set(range(self.config['segment_count'])) - self.visited_segments),
            'pass_candidates': self.pass_candidates,
            'observed_duration_s': self.observed_duration_s,
            'missing_duration_s': self.missing_duration_s,
            'discontinuity_count': self.discontinuity_count,
            'observation_sufficient': not self._had_missing,
            'J_excess_Ns': self.J_excess_Ns,
            'force_observed_duration_s': self.observed_duration_s,
            'force_excess_duration_s': self.force_excess_duration_s,
            'peak_Fz_base_N': self.peak_Fz_base_N,
            'tcp_xy_distance_mm': self.tcp_xy_distance_mm,
            'stop_reason': stop_reason,
            'events': self.events,
            'interpretation': 'Operational observed contact procedure; not removal or independently calibrated contact truth.',
        }
        return self._finalized


def _support_index(signal, time, max_gap):
    index = int(np.searchsorted(signal.time, time, side='right') - 1)
    if index < 0 or index + 1 >= len(signal.time):
        return None
    duration = float(signal.time[index + 1] - signal.time[index])
    if duration <= 0 or duration > max_gap + EPS or signal.break_before[index + 1]:
        return None
    values = np.asarray(signal.value[index:index + 2], float)
    if not np.isfinite(values).all():
        return None
    return index


def _position(signal, time, index):
    fraction = (time - signal.time[index]) / (signal.time[index + 1] - signal.time[index])
    a, b = np.asarray(signal.value[index:index + 2], float)[:, :3]
    return a + fraction * (b - a)


def _fz(value):
    vector = np.asarray(value, float).reshape(-1)
    return float(vector[2] if len(vector) >= 3 else vector[0])


def _force_metrics(force, start, end, config):
    integral = observed = exceeded = 0.0
    peak = None
    # A recorded point is evidence for peak, even if it has no positive ZOH
    # duration (e.g. a final sample exactly at stop). Such a point still cannot
    # contribute time, integral, contact confirmation, or a segment visit.
    for time, value in zip(force.time, force.value):
        if start <= float(time) <= end and np.isfinite(np.asarray(value, float)).all():
            sample = _fz(value)
            peak = sample if peak is None else max(peak, sample)
    for index in range(max(0, len(force.time) - 1)):
        a = max(start, float(force.time[index]))
        b = min(end, float(force.time[index + 1]))
        if b <= a or _support_index(force, (a + b) / 2.0, config['max_gap_s']) != index:
            continue
        value = _fz(force.value[index])
        excess = max(value - config['force_reference_upper_N'], 0.0)
        integral += excess * (b - a)
        observed += b - a
        exceeded += b - a if excess > 0 else 0.0
        peak = value if peak is None else max(peak, value)
    return dict(J_excess_Ns=integral, force_observed_duration_s=observed,
                force_missing_duration_s=max(0.0, end - start - observed),
                force_excess_duration_s=exceeded, peak_Fz_base_N=peak)


def evaluate_signals(pose, force, execution_start_s, end_s, config=None, stop_reason=None,
                     source_metadata=None):
    """Replay receipt-clock Signals using bounded linear pose and force ZOH.

    Signals need ``time``, ``value``, and ``break_before`` arrays; the existing
    ``e1_contact_metrics.Signal`` is accepted. Pose's first three fields are xyz
    mm. Force can be Fz-only or xyz N (third field). Missing values, explicit
    breaks, >max_gap source intervals, or out-of-record data are unobserved.
    Force integrals use all force support, even when pose is unavailable.
    """
    evaluator = TaskEvaluator(config, execution_start_s)
    start, end = float(execution_start_s), float(end_s)
    if end < start:
        raise ValueError('Evaluation end precedes execution start')
    stamps = {start, end}
    for signal in (pose, force):
        stamps.update(float(t) for t in signal.time if start < t < end)
    stamps = sorted(stamps)
    for a, b in zip(stamps[:-1], stamps[1:]):
        if evaluator.completion_time_s is not None:
            break
        pi = _support_index(pose, (a + b) / 2.0, evaluator.config['max_gap_s'])
        fi = _support_index(force, (a + b) / 2.0, evaluator.config['max_gap_s'])
        if pi is None or fi is None:
            evaluator.observe_interval(a, b, None, None, 0.0, observed=False)
        else:
            evidence = None
            if evaluator.config['evaluation_version'] == 'pass_height_ref_v2':
                evidence = dict(source_metadata or {})
                evidence.update({
                    'source': evidence.get('source', 'recorded_receipt_signals'),
                    'force_source_index': int(fi),
                    'force_receipt_time_s': float(force.time[fi]),
                    'pose_left_source_index': int(pi),
                    'pose_right_source_index': int(pi + 1),
                    'pose_left_receipt_time_s': float(pose.time[pi]),
                    'pose_right_receipt_time_s': float(pose.time[pi + 1]),
                })
                # Epoch is supplied only when the caller read actual receipt
                # nanoseconds. Synthetic/unknown clocks never invent one.
                if 'receipt_epoch_ns' in evidence:
                    epoch = int(evidence['receipt_epoch_ns'])
                    evidence.update({
                        'force_receipt_monotonic_ns': epoch + round(float(force.time[fi]) * 1e9),
                        'pose_left_receipt_monotonic_ns': epoch + round(float(pose.time[pi]) * 1e9),
                        'pose_right_receipt_monotonic_ns': epoch + round(float(pose.time[pi + 1]) * 1e9),
                    })
            evaluator.observe_interval(a, b, _position(pose, a, pi), _position(pose, b, pi),
                                       _fz(force.value[fi]), source_metadata=evidence)
    result = evaluator.finalize(end, stop_reason)
    result.update(_force_metrics(force, start, result['evaluation_end_s'], evaluator.config))
    return result
