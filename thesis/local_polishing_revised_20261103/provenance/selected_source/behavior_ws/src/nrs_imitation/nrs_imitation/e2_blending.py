"""Hardware-free Preston dose reconstruction and finite E2 C blending plans.

Positions are robot-base mm, orientations are rotation-vector rad, forces N.
An uncalibrated rotary model produces relative dose, never measured depth.
"""
import csv
import heapq
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_dilation, binary_erosion, distance_transform_edt, label
from scipy.optimize import lsq_linear, minimize
from scipy.signal import fftconvolve
from scipy.sparse import coo_matrix
from scipy.spatial.transform import Rotation


SCHEMA = 'E2_C_blending_v1'
DEFAULTS = dict(
    schema=SCHEMA, initial_inference_sec=0.0, display_wait_sec=5.0,
    require_display_ack=True, display_ack_timeout_s=15.0,
    load_settle_sec=0.0, release_settle_sec=0.0,
    inference_replan_lead_sec=0.5, inference_plan_grace_sec=0.5,
    control_period_s=0.008, sample_period_s=0.02, max_sample_gap_s=0.2,
    cell_mm=1.0, pad_radius_mm=20.0, blend_width_mm=3.0,
    lane_spacing_mm=3.0, waypoint_spacing_mm=5.0,
    feed_speed_mm_s=10.0, min_feed_speed_mm_s=1.0, transfer_speed_mm_s=5.0,
    blending_normal_force_N=4.0, uniformity_level_weight=0.1, overcut_weight=1.0,
    max_normal_force_N=10.0, force_rate_N_s=30.0,
    contact_on_N=3.0, contact_off_N=1.2, clearance_mm=5.0,
    clearance_force_limit_N=3.0, clearance_contact_confirm_sec=0.2,
    final_position_tolerance_mm=1.0, final_stationary_tolerance_mm=0.2,
    release_timeout_s=10.0, replay_timeout_margin_s=5.0,
    max_blending_duration_s=180.0, target_quantile=1.0,
    active_fraction=0.02, solver_stride=2, solver_iterations=200,
    surface_normal_base=[0.0, 0.0, 1.0], compression_sign=1.0,
    controller_force_frame='tcp', surface_z_mm=None,
    rpm_setpoint=None, rpm_topic='', spindle_on_topic='',
    spindle_assumed_on=True, preston_coefficient=1.0,
    calibrated=False, calibration_id='', pressure_model='uniform_disk',
    contact_model_id='assumed_disk_20mm', specimen_id='', abrasive_id='',
)


def load_blending_config(path):
    value = json.loads(Path(path).expanduser().read_text())
    unknown = set(value)-set(DEFAULTS)
    if unknown:
        raise ValueError('Unknown blending settings: '+', '.join(sorted(unknown)))
    return validate_config(dict(DEFAULTS, **value))


def validate_config(c):
    c = dict(DEFAULTS, **c)
    if c['schema'] != SCHEMA:
        raise ValueError('Unsupported blending schema')
    positive = ('display_wait_sec', 'display_ack_timeout_s', 'control_period_s', 'sample_period_s',
        'max_sample_gap_s', 'cell_mm', 'pad_radius_mm', 'blend_width_mm',
        'lane_spacing_mm', 'waypoint_spacing_mm', 'feed_speed_mm_s', 'min_feed_speed_mm_s',
        'blending_normal_force_N', 'uniformity_level_weight', 'overcut_weight',
        'transfer_speed_mm_s', 'max_normal_force_N', 'force_rate_N_s',
        'contact_on_N', 'contact_off_N', 'clearance_mm', 'clearance_force_limit_N',
        'clearance_contact_confirm_sec', 'final_position_tolerance_mm',
        'final_stationary_tolerance_mm', 'release_timeout_s',
        'replay_timeout_margin_s', 'max_blending_duration_s', 'preston_coefficient')
    for key in positive:
        v = c[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not np.isfinite(v) or v <= 0:
            raise ValueError('Positive finite blending.'+key+' required')
    if not isinstance(c['require_display_ack'], bool):
        raise ValueError('require_display_ack must be boolean')
    for key in ('load_settle_sec', 'release_settle_sec'):
        value = c[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) or not 0 <= value <= 5:
            raise ValueError(key+' must be finite and between 0 and 5 s')
    if not np.isfinite(c['initial_inference_sec']) or not 0 <= c['initial_inference_sec'] <= 45:
        raise ValueError('initial_inference_sec must be 0 (finish) or at most 45 s')
    for key in ('inference_replan_lead_sec', 'inference_plan_grace_sec'):
        v = c[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not np.isfinite(v) or not 0 <= v <= 1:
            raise ValueError(key+' must be finite and between 0 and 1 s')
    if c['contact_off_N'] >= c['contact_on_N']:
        raise ValueError('Contact hysteresis thresholds are reversed')
    if c['sample_period_s'] > c['max_sample_gap_s']:
        raise ValueError('Sample period exceeds gap limit')
    if c['lane_spacing_mm'] > 2*c['pad_radius_mm']:
        raise ValueError('Lane spacing exceeds the tool footprint diameter')
    if c['feed_speed_mm_s'] > 10 or c['transfer_speed_mm_s'] > 10 or c['force_rate_N_s'] > 30:
        raise ValueError('Blending must retain E2 speed and force-slew limits')
    if c['max_normal_force_N'] > 20:
        raise ValueError('Blending normal-force command exceeds 20 N')
    if not c['contact_on_N'] < c['blending_normal_force_N'] <= c['max_normal_force_N']:
        raise ValueError('blending_normal_force_N must exceed contact_on_N and stay within the force limit')
    if c['min_feed_speed_mm_s'] > c['feed_speed_mm_s']:
        raise ValueError('min_feed_speed_mm_s exceeds the feed speed limit')
    if c['clearance_force_limit_N'] > 20 or c['clearance_contact_confirm_sec'] > 1:
        raise ValueError('Clearance contact limit must be at most 20 N and confirmation at most 1 s')
    if c['final_position_tolerance_mm'] > 5 or c['final_stationary_tolerance_mm'] > 1:
        raise ValueError('Final position tolerance must be at most 5 mm and stationary tolerance at most 1 mm')
    if c['pressure_model'] != 'uniform_disk':
        raise ValueError('Only the explicitly assumed uniform_disk pressure model is supported')
    if not np.array_equal(c['surface_normal_base'], [0., 0., 1.]):
        raise ValueError('This first experiment supports a flat base-XY surface only')
    if c['compression_sign'] not in (-1., 1.) or c['controller_force_frame'] not in ('tcp', 'robot_base'):
        raise ValueError('Explicit compression sign and controller force frame required')
    if not np.isfinite(c['target_quantile']) or not 0 < c['target_quantile'] <= 1:
        raise ValueError('target_quantile must be above zero and at most one')
    if not np.isfinite(c['active_fraction']) or not 0 < c['active_fraction'] < 1:
        raise ValueError('active_fraction must be between zero and one')
    for key in ('solver_stride', 'solver_iterations'):
        if isinstance(c[key], bool) or not isinstance(c[key], int) or c[key] < 1:
            raise ValueError(key+' must be a positive integer')
    for key in ('surface_z_mm', 'rpm_setpoint'):
        if c[key] is not None and (not np.isfinite(c[key]) or (key == 'rpm_setpoint' and c[key] <= 0)):
            raise ValueError('Invalid '+key)
    if c['rpm_topic'] and c['rpm_setpoint'] is None:
        raise ValueError('rpm_topic needs a positive rpm_setpoint for planning')
    if not isinstance(c['calibrated'], bool) or not isinstance(c['spindle_assumed_on'], bool):
        raise ValueError('calibrated/spindle_assumed_on must be boolean')
    if c['calibrated'] and (not c['calibration_id'] or c['rpm_setpoint'] is None or
            not c['specimen_id'] or not c['abrasive_id']):
        raise ValueError('Calibrated depth needs coefficient calibration, RPM, specimen and abrasive IDs')
    return c


def heatmap_snapshot_id(message):
    return dict(frame_id=message.header.frame_id, stamp_sec=message.header.stamp.sec,
                stamp_nanosec=message.header.stamp.nanosec)


def controller_blending_config(c, info):
    """Use the live inline replay contract without changing force-control settings."""
    if (info.get('version') != 'cmd_continue9d_inline_v2' or
            info.get('inline_replay_allowed') is not True or
            isinstance(info.get('force_control_mode'), bool) or
            info.get('force_control_mode') not in range(5) or
            info.get('contact_observation') != 'signed_robot_base_fz' or
            info.get('force_frame') != c['controller_force_frame'] or
            abs(float(info.get('period_s', float('nan')))-c['control_period_s']) > 1e-9 or
            not np.isfinite(float(info.get('period_s', float('nan'))))):
        raise ValueError('Controller CmdContinue9D v2/mode/period/force-frame mismatch; restart the updated singleArm_cmd')
    for key in ('contact_on_N', 'contact_off_N'):
        value = float(info.get(key, float('nan')))
        if not np.isfinite(value) or abs(value-c[key]) > 1e-9:
            raise ValueError('Controller signed contact threshold mismatch: '+key)
    if info.get('normal_contact_transition_enabled') is True:
        if info.get('force_reference_owner') != 'motion_controller':
            raise ValueError('Normal contact transition must own the replay force reference')
        for key in ('contact_confirm_s', 'capture_stop_s', 'position_to_force_s',
                    'force_to_position_s', 'force_slew_N_s', 'normal_reference_speed_mm_s'):
            value = float(info.get(key, float('nan')))
            if not np.isfinite(value) or value <= 0:
                raise ValueError('Invalid controller contact transition setting: '+key)
        if info['force_slew_N_s'] < c['force_rate_N_s'] or info['normal_reference_speed_mm_s'] < c['transfer_speed_mm_s']:
            raise ValueError('Blending exceeds the configured normal-axis slew/speed')
        c = dict(c, load_settle_sec=max(c['load_settle_sec'], info['position_to_force_s']+
            info['contact_confirm_s']+info['capture_stop_s']),
            release_settle_sec=max(c['release_settle_sec'], info['force_to_position_s']))
    elif info.get('normal_contact_transition_enabled') is not False or info.get('force_reference_owner') != 'inline_contact_gate':
        raise ValueError('Controller contact transition ownership is unspecified')
    return validate_config(c)


def inference_replan_interval_s(steps, trajectory_hz, c):
    """Reserve time for the inference timer, model execution and plan transport."""
    interval = steps/trajectory_hz-c['inference_replan_lead_sec']
    if not np.isfinite(interval) or interval <= 0:
        raise ValueError('Inference replan lead must be shorter than the nominal interval')
    return float(interval)


def normal_force(force3, c):
    return max(0., c['compression_sign']*float(np.dot(force3, c['surface_normal_base'])))


class ClearanceContactMonitor:
    """Confirm compression at clearance using distinct force receipt times."""
    def __init__(self, config):
        self.config = config
        self.reset()

    def reset(self):
        self.since = None

    def update(self, receipt_s, force):
        force3 = np.asarray(force, float).reshape(-1)[:3]
        if not np.isfinite(receipt_s) or force3.shape != (3,) or not np.isfinite(force3).all():
            raise ValueError('Invalid clearance force feedback')
        fn = normal_force(force3, self.config)
        if fn < self.config['clearance_force_limit_N']:
            self.reset()
            return False
        if self.since is None or receipt_s < self.since:
            self.since = receipt_s
        return receipt_s-self.since >= self.config['clearance_contact_confirm_sec']


def removal_kernel(c):
    """Per-unit normal force and time; area is discretized in mm^2.

    With RPM, weights are pressure times rotary sliding speed per RPM.
    Without RPM, rotary speed has unit mean over the assumed contact disk.
    Feed speed is not substituted for spindle sliding speed.
    """
    n = int(np.ceil(c['pad_radius_mm']/c['cell_mm']))
    yy, xx = np.mgrid[-n:n+1, -n:n+1]*c['cell_mm']
    radius = np.hypot(xx, yy)
    disk = radius <= c['pad_radius_mm']
    pressure = disk/(disk.sum()*c['cell_mm']**2)
    if c['rpm_setpoint'] is None:
        velocity = radius/max(float(radius[disk].mean()), 1e-12)
    else:
        velocity = (2*np.pi/60.)*radius
    return c['preston_coefficient']*pressure*velocity


def grid_for_samples(samples, c):
    if len(samples) < 2:
        raise ValueError('No usable measured trajectory')
    xy = np.asarray([s['pose'][:2] for s in samples], float)
    margin = 2*c['pad_radius_mm']+c['blend_width_mm']+c['waypoint_spacing_mm']
    lo = np.floor((xy.min(0)-margin)/c['cell_mm'])*c['cell_mm']
    hi = np.ceil((xy.max(0)+margin)/c['cell_mm'])*c['cell_mm']
    if np.max((hi-lo)/c['cell_mm']) > 1000:
        raise ValueError('Measured path would require an oversized removal grid')
    return (np.arange(lo[0], hi[0]+.5*c['cell_mm'], c['cell_mm']),
            np.arange(lo[1], hi[1]+.5*c['cell_mm'], c['cell_mm']))


def dose_maps(samples, c, grid=None):
    """Integrate measured feedback, separating stages and excluding data gaps."""
    c = validate_config(c)
    x, y = grid_for_samples(samples, c) if grid is None else grid
    raw = {stage: np.zeros((len(y), len(x))) for stage in ('inference', 'blending')}
    dwell = {stage: np.zeros_like(raw[stage]) for stage in raw}
    skipped_gap_s = 0.
    contact = False
    times = np.asarray([s['t'] for s in samples], float)
    if not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
        raise ValueError('Measured sample times must be finite and strictly increasing')
    for a, b in zip(samples[:-1], samples[1:]):
        dt = b['t']-a['t']
        if a['stage'] != b['stage']:
            contact = False
            continue
        if dt > c['max_sample_gap_s']:
            skipped_gap_s += dt
            contact = False
            continue
        f = np.asarray(a['force'], float)
        pose = .5*(np.asarray(a['pose'], float)+np.asarray(b['pose'], float))
        if f.shape != (3,) or pose.shape != (6,) or not np.isfinite(np.r_[f, pose]).all():
            raise ValueError('Nonfinite/invalid measured feedback')
        fn = normal_force(f, c)
        if not contact and fn >= c['contact_on_N']:
            contact = True
        elif contact and fn <= c['contact_off_N']:
            contact = False
        if not a['spindle_on'] or not contact:
            continue
        ix, iy = np.rint((pose[:2]-[x[0], y[0]])/c['cell_mm']).astype(int)
        if not (0 <= ix < len(x) and 0 <= iy < len(y)):
            raise ValueError('Measured contact outside the common removal grid')
        rpm = a.get('rpm')
        scale = 1. if c['rpm_setpoint'] is None else rpm
        if scale is None or not np.isfinite(scale) or scale <= 0:
            raise ValueError('Missing positive RPM for the configured rotary model')
        raw[a['stage']][iy, ix] += fn*dt*scale
        dwell[a['stage']][iy, ix] += dt
    kernel = removal_kernel(c)
    maps = {s: np.maximum(fftconvolve(v, kernel, mode='same'), 0.) for s, v in raw.items()}
    maps['combined'] = maps['inference']+maps['blending']
    return dict(x_mm=x, y_mm=y, kernel=kernel, maps=maps, dwell=dwell,
        skipped_gap_s=skipped_gap_s, unit='um' if c['calibrated'] else 'relative Preston dose (a.u.)',
        model='rotation_dominant_uniform_disk' if c['rpm_setpoint'] is not None else 'normalized_rotary_speed_uniform_disk',
        calibrated=c['calibrated'], config=c)


def load_measured_samples(path):
    """Read the measured CSV without starting ROS or sending commands."""
    with Path(path).open() as stream:
        rows = list(csv.DictReader(stream))
    return [dict(t=float(row['receipt_monotonic_s']), stage=row['stage'],
        pose=[float(row[key]) for key in ('x_mm', 'y_mm', 'z_mm', 'rx_rad', 'ry_rad', 'rz_rad')],
        force=[float(row[key]) for key in ('fx_base_N', 'fy_base_N', 'fz_base_N')],
        rpm=float(row['rpm']) if row['rpm'] else None, spindle_on=row['spindle_on'] == 'True')
        for row in rows]


def footprint_disk(c):
    radius = int(np.ceil(c['pad_radius_mm']/c['cell_mm']))
    yy, xx = np.mgrid[-radius:radius+1, -radius:radius+1]*c['cell_mm']
    return np.hypot(xx, yy) <= c['pad_radius_mm']


def blending_region(result, c):
    """Limit the swept tool footprint to the measured footprint plus the margin.

    The dose threshold does not define geometry: even the zero rotary-speed
    center belongs to the swept disk. Erosion accounts for tool size before
    choosing tool centers, instead of putting centers on the footprint edge.
    """
    disk = footprint_disk(c)
    centers = result['dwell']['inference'] > 0
    if not centers.any():
        raise ValueError('No measured contact footprint for blending')
    processed = binary_dilation(centers, structure=disk)
    allowed = distance_transform_edt(~processed)*c['cell_mm'] <= c['blend_width_mm']
    allowed_centers = binary_erosion(allowed, structure=disk, border_value=0)
    return processed, allowed, allowed_centers


def target_map(current, c, processed=None):
    peak = float(current.max())
    if peak <= 0:
        raise ValueError('No measured contact dose; cannot construct a blending target')
    core = current > c['active_fraction']*peak
    geometry = core if processed is None else processed
    distance = distance_transform_edt(~geometry)*c['cell_mm']
    taper = .5*(1+np.cos(np.pi*np.minimum(distance/c['blend_width_mm'], 1.)))
    height = float(np.quantile(current[core], c['target_quantile']))
    target = np.maximum(current, height*taper)
    return target, np.maximum(target-current, 0.)


def segment_in_region(a, b, region, x, y, cell_mm):
    """Check the full straight segment, including connectors between lanes."""
    ends = (np.asarray([a, b])-[x[0], y[0]])/cell_mm
    delta = ends[1]-ends[0]
    crossings = [0., 1.]
    for axis in range(2):
        if abs(delta[axis]) < 1e-12:
            continue
        lo, hi = sorted(ends[:, axis])
        boundaries = np.arange(np.ceil(lo-.5), np.floor(hi-.5)+1)+.5
        crossings.extend((boundaries-ends[0, axis])/delta[axis])
    crossings = np.unique(np.clip(crossings, 0., 1.))
    parameters = np.r_[crossings, .5*(crossings[:-1]+crossings[1:])]
    xy = ends[0]+parameters[:, None]*delta
    indices = np.rint(xy).astype(int)
    # Check both sides of exact cell boundaries. At a diagonal corner, banker's
    # rounding can otherwise admit a forbidden cell on just one 8 ms row.
    boundary = np.isclose(xy-np.floor(xy), .5, atol=1e-9, rtol=0.)
    lower = np.where(boundary, np.floor(xy).astype(int), indices)
    upper = lower+boundary.astype(int)
    for ix, iy in ((lower[:, 0], lower[:, 1]), (lower[:, 0], upper[:, 1]),
                   (upper[:, 0], lower[:, 1]), (upper[:, 0], upper[:, 1])):
        valid = (ix >= 0)&(ix < len(x))&(iy >= 0)&(iy < len(y))
        if not valid.all() or not region[iy, ix].all():
            return False
    return True


def route_in_region(a, b, region, x, y, cell_mm):
    """Find and simplify an interior route when a straight connector clips an edge."""
    ends = np.rint((np.asarray([a, b])-[x[0], y[0]])/cell_mm).astype(int)
    start, goal = map(tuple, ends)
    for ix, iy in (start, goal):
        if not (0 <= ix < len(x) and 0 <= iy < len(y) and region[iy, ix]):
            return None
    # Four-neighbor edges stay in occupied cells without cutting diagonal corners.
    costs, parent = {start: 0}, {start: None}
    frontier = [(abs(start[0]-goal[0])+abs(start[1]-goal[1]), 0, start)]
    while frontier:
        _, cost, node = heapq.heappop(frontier)
        if cost != costs[node]:
            continue
        if node == goal:
            break
        ix, iy = node
        for neighbor in ((ix-1, iy), (ix+1, iy), (ix, iy-1), (ix, iy+1)):
            nx, ny = neighbor
            if not (0 <= nx < len(x) and 0 <= ny < len(y) and region[ny, nx]):
                continue
            new_cost = cost+1
            if new_cost >= costs.get(neighbor, float('inf')):
                continue
            costs[neighbor] = new_cost; parent[neighbor] = node
            estimate = abs(nx-goal[0])+abs(ny-goal[1])
            heapq.heappush(frontier, (new_cost+estimate, new_cost, neighbor))
    if goal not in parent:
        return None
    nodes, node = [], goal
    while node is not None:
        nodes.append([x[node[0]], y[node[1]]]); node = parent[node]
    coordinates = np.vstack([a, nodes[::-1], b])
    coordinates = coordinates[np.r_[True, np.linalg.norm(np.diff(coordinates, axis=0), axis=1) > 1e-9]]
    simplified, i = [coordinates[0]], 0
    while i < len(coordinates)-1:
        j = len(coordinates)-1
        while j > i+1 and not segment_in_region(coordinates[i], coordinates[j], region, x, y, cell_mm):
            j -= 1
        simplified.append(coordinates[j]); i = j
    return np.asarray(simplified)[1:]


def raster_points(additional, x, y, c, allowed_centers=None, return_starts=False,
                  transfer_clearance_mm=None):
    active = additional > c['active_fraction']*float(additional.max())
    if not active.any():
        raise ValueError('No positive additional-removal target')
    region = active if allowed_centers is None else allowed_centers
    # Retain only feasible centers whose footprint can reach positive target.
    reachable = fftconvolve(active.astype(float), footprint_disk(c).astype(float), mode='same') > .5
    region = region & reachable
    if not region.any():
        raise ValueError('No tool centers fit inside the allowed blending region')
    components, component_count = label(region)
    lane_step = max(1, int(np.floor(c['lane_spacing_mm']/c['cell_mm'])))
    clearance = c['clearance_mm'] if transfer_clearance_mm is None else transfer_clearance_mm
    points, starts = [], []
    # Finish each connected component before lifting to the next one.
    for component in range(1, component_count+1):
        component_region = components == component
        ys, _ = np.nonzero(component_region)
        row_indices = list(range(int(ys.min()), int(ys.max())+1, lane_step))
        if row_indices[-1] != ys.max():
            row_indices.append(int(ys.max()))
        for lane, iy in enumerate(row_indices):
            xs = np.flatnonzero(component_region[iy])
            runs = np.split(xs, np.flatnonzero(np.diff(xs) > 1)+1)
            if lane % 2:
                runs = runs[::-1]
            for run in runs:
                if not len(run):
                    continue
                lo, hi = x[run[0]], x[run[-1]]
                count = max(2, int(np.ceil((hi-lo)/c['waypoint_spacing_mm']))+1)
                values = np.linspace(lo, hi, count)
                if lane % 2:
                    values = values[::-1]
                for vx in values:
                    point = np.array([vx, y[iy]])
                    if points and np.linalg.norm(point-points[-1]) < 1e-9:
                        continue
                    connected = bool(points) and segment_in_region(points[-1], point, region, x, y, c['cell_mm'])
                    if points and not connected:
                        route = route_in_region(points[-1], point, region, x, y, c['cell_mm'])
                        if route is not None:
                            distance = np.linalg.norm(np.diff(np.vstack([points[-1], route]), axis=0), axis=1).sum()
                            interior_time = 1.875*distance/c['feed_speed_mm_s']
                            lifted_time = 1.875*(2*clearance+np.linalg.norm(point-points[-1]))/c['transfer_speed_mm_s']
                            if interior_time <= lifted_time:
                                points.extend(route); starts.extend([False]*len(route))
                                continue
                    starts.append(not connected)
                    points.append(point)
    points = np.asarray(points, float)
    if len(points) < 2 or len(points) > 2000:
        raise ValueError('Invalid/oversized raster plan')
    starts = np.asarray(starts, bool)
    return (points, starts) if return_starts else points


def uniformity_region(processed, c):
    """Use a fixed interior mask, keeping the unavoidable footprint edge separate."""
    interior = distance_transform_edt(processed)*c['cell_mm'] >= .5*c['pad_radius_mm']
    return interior if interior.any() else processed.copy()


def uniformity_metrics(values, region):
    dose = np.asarray(values)[region]
    if not len(dose):
        raise ValueError('Empty uniformity region')
    mean = float(dose.mean())
    return dict(cell_count=int(len(dose)), mean=mean, std=float(dose.std()),
        cv=float(dose.std()/mean) if mean > 0 else None,
        minimum=float(dose.min()), maximum=float(dose.max()),
        p10=float(np.quantile(dose, .1)), p90=float(np.quantile(dose, .9)))


def predicted_dose(profile, c, grid, exclude_work=False):
    """Integrate requested forces with the same hysteresis as the measured maps."""
    samples = [dict(t=float(t), pose=a[:6],
        force=c['compression_sign']*fn*np.asarray(c['surface_normal_base']),
        stage='blending', rpm=c['rpm_setpoint'],
        spindle_on=not (exclude_work and phase == 'blending'))
        for t, a, fn, phase in zip(profile['time'], profile['action'],
            profile['normal_force'], profile['phase'])]
    return dose_maps(samples, c, grid)['maps']['blending']


def fit_durations(points, current, target, processed, x, y, c, kernel,
                  path_start, base_profile):
    """Fit residence time at sustained contact force to combined-map variance.

    A force-only fit can command less than the controller's contact threshold.
    Use a constant contact force and bounded segment speeds instead. The
    objective includes the existing inference dose and the load/release dose;
    it penalizes excess mean dose as well as spatial variation. All transfer
    and ramp time is charged to the same finite replay budget.
    """
    period = c['control_period_s']
    ds = np.linalg.norm(np.diff(points, axis=0), axis=1)
    lower = np.ceil(np.maximum(1.875*ds/c['feed_speed_mm_s'], period)/period-1e-9)*period
    upper = np.ceil(np.maximum(1.875*ds/c['min_feed_speed_mm_s'], period)/period-1e-9)*period
    lower[path_start[1:]] = 0.; upper[path_start[1:]] = 0.
    work_indices = np.flatnonzero(lower > 0)
    if not len(work_indices):
        raise ValueError('No connected contact segments for blending')
    extra_budget = max(0., c['max_blending_duration_s']-float(base_profile['time'][-1]))
    fixed = predicted_dose(base_profile, c, (x, y), exclude_work=True)
    stride = c['solver_stride']
    gy, gx = np.mgrid[0:len(y):stride, 0:len(x):stride]
    rows, cols, values = [], [], []
    middle = np.array(kernel.shape)//2
    rpm = 1. if c['rpm_setpoint'] is None else c['rpm_setpoint']
    # Each column is dose per second on a moving quintic segment, rather than
    # a stationary disk at an endpoint. Round tool centers on the map grid,
    # exactly as dose_maps does, before looking up the rotary kernel.
    for column, j in enumerate(work_indices):
        count = max(8, int(np.ceil(lower[j]/period)))
        u = (np.arange(count)+.5)/count
        contribution = np.zeros(gx.size)
        for w in u**3*(10-15*u+6*u*u):
            center = points[j]+w*(points[j+1]-points[j])
            ix, iy = np.rint((center-[x[0], y[0]])/c['cell_mm']).astype(int)
            kx = gx.ravel()-ix+middle[1]; ky = gy.ravel()-iy+middle[0]
            valid = (kx >= 0)&(kx < kernel.shape[1])&(ky >= 0)&(ky < kernel.shape[0])
            contribution[valid] += kernel[ky[valid], kx[valid]]/count
        index = np.flatnonzero(contribution > 0)
        rows.extend(index); cols.extend([column]*len(index))
        values.extend(contribution[index]*rpm*c['blending_normal_force_N'])
    matrix = coo_matrix((values, (rows, cols)), shape=(gx.size, len(work_indices))).tocsr()
    core = current > c['active_fraction']*float(current.max())
    height = float(np.quantile(current[core], c['target_quantile']))
    # Normalization makes dwell selection invariant to Preston K/RPM units.
    matrix = matrix/height
    baseline = (current+fixed)[gy, gx].ravel()/height+matrix@lower[work_indices]
    desired = target[gy, gx].ravel()/height
    interior = uniformity_region(processed, c)
    mask = interior[gy, gx].ravel()
    if not mask.any():
        raise ValueError('Solver grid misses the blending interior; reduce solver_stride')
    weights = np.where(mask, 4., np.where(processed[gy, gx].ravel(), 1., .1))
    capacity = upper[work_indices]-lower[work_indices]
    # Equal bounds occur for sub-grid connectors; retain a negligible finite
    # solver bound and remove it again when quantizing the result to 8 ms.
    bounds = np.maximum(capacity, 1e-12)
    seed_fit = lsq_linear(matrix.multiply(weights[:, None]), (desired-baseline)*weights,
        bounds=(0., bounds), max_iter=c['solver_iterations'], lsmr_tol=1e-6, tol=1e-6)
    seed = np.clip(seed_fit.x, 0., capacity)
    if seed.sum() > extra_budget:
        seed *= extra_budget/seed.sum()
    a = matrix[mask]
    b = baseline[mask]
    mean_a = np.asarray(a.mean(axis=0)).ravel(); mean_b = float(b.mean())
    quadratic = (a.T@a).toarray()/len(b)
    linear = np.asarray(a.T@b).ravel()/len(b)
    constant = float(b@b/len(b))

    def objective(extra):
        mean = mean_b+mean_a@extra
        qe = quadratic@extra
        variance = max(0., constant+2*linear@extra+extra@qe-mean*mean)
        derivative = 2*(linear+qe-mean*mean_a)
        # Normalize by the fixed inference target, not the achieved mean: a
        # higher total removal alone must not count as improved flatness.
        value = variance+c['uniformity_level_weight']*(mean-1)**2
        gradient = derivative+2*c['uniformity_level_weight']*(mean-1)*mean_a
        return value, gradient

    # Scale seconds to keep SLSQP variables/gradients near unity. Unscaled
    # residence times otherwise converge slowly along overlapping footprints.
    time_unit_s = 20.

    def scaled_objective(value):
        cost, gradient = objective(value*time_unit_s)
        return cost, gradient*time_unit_s

    solution = minimize(scaled_objective, seed/time_unit_s, jac=True, method='SLSQP',
        bounds=list(zip(np.zeros(len(bounds)), bounds/time_unit_s)),
        constraints=[dict(type='ineq', fun=lambda v: extra_budget/time_unit_s-v.sum(),
            jac=lambda v: -np.ones(len(v)))],
        options=dict(maxiter=c['solver_iterations'], ftol=1e-9))
    # A finite feasible warm start remains usable if the optimizer reaches its
    # iteration limit. Choose it when the unfinished iterate is worse.
    extra = np.clip(solution.x*time_unit_s, 0., capacity)
    if not np.isfinite(extra).all():
        raise ValueError('Nonfinite residence-time fit')
    if extra.sum() > extra_budget:
        extra *= extra_budget/extra.sum()
    if objective(extra)[0] > objective(seed)[0]:
        extra = seed
    durations = lower.copy()
    # Round extensions down so row quantization cannot exceed the total budget.
    durations[work_indices] += np.floor(extra/period)*period
    residual = matrix@durations[work_indices]+(current+fixed)[gy, gx].ravel()/height-desired
    return durations, interior, dict(solver_success=bool(solution.success),
        solver_status=int(solution.status), solver_message=str(solution.message),
        solver_iterations_used=int(solution.nit),
        coarse_residual_norm=float(np.linalg.norm(residual)*height),
        target_norm=float(np.linalg.norm((target-current)[gy, gx])),
        objective='combined interior variance / fixed target level squared + mean-level penalty',
        objective_value=float(objective(extra)[0]), target_level=height,
        sustained_normal_force_N=c['blending_normal_force_N'],
        minimum_feed_speed_mm_s=c['min_feed_speed_mm_s'],
        total_duration_budget_s=c['max_blending_duration_s'],
        budget_active=bool(extra_budget-extra.sum() < period),
        fit_model='moving rotary footprint, bounded segment residence time and load/release dose; dense 8 ms replay validation')


def replay_profile(points, forces, start_pose, surface_z, c, path_start=None, segment_durations=None):
    """Uniform controller-period rows; zero-force travel, ramp, work and lift."""
    start = np.asarray(start_pose, float)
    if start.shape != (6,) or not np.isfinite(start).all() or start[2] < surface_z+c['clearance_mm']-.5:
        raise ValueError('Blending must begin at verified clearance above the working plane')
    rows, phases = [np.r_[start, np.zeros(3)]], ['transfer']
    fn_rows = [0.]
    current = start.copy()

    def append(target, fn0, fn1, speed, phase, segment_duration=None):
        nonlocal current
        length = np.linalg.norm(target[:3]-current[:3])
        duration = max(1.875*length/speed, 1.875*abs(fn1-fn0)/c['force_rate_N_s'], c['control_period_s'])
        if segment_duration is not None:
            if not np.isfinite(segment_duration) or segment_duration < duration-1e-9:
                raise ValueError('Fitted residence time violates a replay speed or force-slew limit')
            duration = max(duration, segment_duration)
        count = int(np.ceil(duration/c['control_period_s']-1e-9))
        u = np.arange(1, count+1)/count
        s = u**3*(10-15*u+6*u*u)
        for w in s:
            pose = current+w*(target-current)
            fn = float(fn0+w*(fn1-fn0))
            base_force = c['compression_sign']*fn*np.asarray(c['surface_normal_base'])
            force = (Rotation.from_rotvec(pose[3:]).inv().apply(base_force)
                     if c['controller_force_frame'] == 'tcp' else base_force)
            rows.append(np.r_[pose, force]); phases.append(phase); fn_rows.append(fn)
        current = target.copy()

    def settle(force, duration, phase):
        if duration > 0:
            append(current.copy(), force, force, c['feed_speed_mm_s'], phase, duration)

    above = start.copy(); above[:2] = points[0]
    append(above, 0., 0., c['transfer_speed_mm_s'], 'transfer')
    touch = above.copy(); touch[2] = surface_z
    append(touch, 0., 0., c['transfer_speed_mm_s'], 'approach')
    append(touch, 0., forces[0], c['feed_speed_mm_s'], 'load')
    settle(forces[0], c['load_settle_sec'], 'load_settle')
    path_start = np.zeros(len(points), bool) if path_start is None else np.asarray(path_start, bool)
    if segment_durations is not None and np.shape(segment_durations) != (len(points)-1,):
        raise ValueError('One residence time per path segment required')
    for j, (xy, a, b) in enumerate(zip(points[1:], forces[:-1], forces[1:]), 1):
        if path_start[j]:
            append(current.copy(), a, 0., c['feed_speed_mm_s'], 'release')
            settle(0., c['release_settle_sec'], 'release_settle')
            lift = current.copy(); lift[2] = start[2]
            append(lift, 0., 0., c['transfer_speed_mm_s'], 'retract')
            above = lift.copy(); above[:2] = xy
            append(above, 0., 0., c['transfer_speed_mm_s'], 'transfer')
            touch = above.copy(); touch[2] = surface_z
            append(touch, 0., 0., c['transfer_speed_mm_s'], 'approach')
            append(touch, 0., b, c['feed_speed_mm_s'], 'load')
            settle(b, c['load_settle_sec'], 'load_settle')
            continue
        target = touch.copy(); target[:2] = xy
        duration = None if segment_durations is None else segment_durations[j-1]
        append(target, a, b, c['feed_speed_mm_s'], 'blending', duration)
    append(current.copy(), forces[-1], 0., c['feed_speed_mm_s'], 'release')
    settle(0., c['release_settle_sec'], 'release_settle')
    lift = current.copy(); lift[2] = start[2]
    append(lift, 0., 0., c['transfer_speed_mm_s'], 'retract')
    rows, fn_rows = np.asarray(rows), np.asarray(fn_rows)
    t = np.arange(len(rows))*c['control_period_s']
    if t[-1] > c['max_blending_duration_s']:
        raise ValueError(f'Blending duration {t[-1]:.1f}s exceeds configured budget')
    return dict(time=t, action=rows, phase=np.asarray(phases), normal_force=fn_rows)


def plan_blending(result, samples, start_pose, c):
    x, y = result['x_mm'], result['y_mm']
    contact = [s for s in samples if s['spindle_on'] and normal_force(s['force'], c) >= c['contact_on_N']]
    if not contact:
        raise ValueError('No contact samples for working-plane estimation')
    surface_z = (float(np.quantile([s['pose'][2] for s in contact], .9))
                 if c['surface_z_mm'] is None else float(c['surface_z_mm']))
    processed, allowed, allowed_centers = blending_region(result, c)
    current = result['maps']['inference']
    target, additional = target_map(current, c, processed)
    peak = float(current.max())
    # Compare feasible work regions by the existing dose under the rotary
    # footprint. A low-dose tool-center pixel alone is misleading: the center
    # of an already heavily polished ring can itself have near-zero dose.
    kernel = result['kernel']
    existing = fftconvolve(current/peak, kernel[::-1, ::-1]/kernel.sum(), mode='same')
    interior = uniformity_region(processed, c)
    records, seen, best = [], set(), None
    for fraction in np.linspace(.2, 1., 6)[::-1]:
        work_centers = allowed_centers.copy()
        if fraction < 1:
            threshold = float(np.quantile(existing[allowed_centers], fraction))
            work_centers &= existing <= threshold+1e-12
        signature = np.packbits(work_centers).tobytes()
        if signature in seen:
            continue
        seen.add(signature)
        record = dict(existing_dose_quantile=float(fraction), center_count=int(work_centers.sum()))
        try:
            points, path_start = raster_points(additional, x, y, c, work_centers, return_starts=True,
                transfer_clearance_mm=max(c['clearance_mm'], float(start_pose[2])-surface_z))
            if np.linalg.norm(points[-1]-start_pose[:2]) < np.linalg.norm(points[0]-start_pose[:2]):
                points = points[::-1]; path_start = np.r_[True, path_start[:0:-1]]
            forces = np.full(len(points), c['blending_normal_force_N'])
            base_profile = replay_profile(points, forces, np.asarray(start_pose), surface_z, c, path_start)
            durations, _, fit = fit_durations(points, current, target, processed, x, y,
                c, kernel, path_start, base_profile)
            profile = replay_profile(points, forces, np.asarray(start_pose), surface_z, c, path_start, durations)
            work = profile['normal_force'] > 0
            indices = np.rint((profile['action'][work, :2]-[x[0], y[0]])/c['cell_mm']).astype(int)
            if not work_centers[indices[:, 1], indices[:, 0]].all():
                raise ValueError('Dense contact replay leaves the selected blending region')
            predicted = predicted_dose(profile, c, (x, y))
            combined = current+predicted
            stats = uniformity_metrics(combined, interior)
            predicted_peak = float(combined[allowed].max())
            height = fit['target_level']
            score = ((stats['std']/height)**2+
                c['uniformity_level_weight']*(stats['mean']/height-1)**2+
                c['overcut_weight']*max(0., predicted_peak/peak-1)**2)
            record.update(score=float(score), interior_std=stats['std'], interior_cv=stats['cv'],
                predicted_peak=predicted_peak, duration_s=float(profile['time'][-1]))
            if best is None or score < best['score']:
                best = dict(score=score, profile=profile, points=points, path_start=path_start,
                    forces=forces, durations=durations, fit=fit, predicted=predicted,
                    work_centers=work_centers, selected_quantile=float(fraction))
        except ValueError as exc:
            record['error'] = str(exc)
        records.append(record)
    if best is None:
        raise ValueError('No feasible dose-based blending plan: '+str(records[0].get('error')))
    profile, points, path_start = best['profile'], best['points'], best['path_start']
    forces, durations, fit, predicted = best['forces'], best['durations'], best['fit'], best['predicted']
    fit.update(selection_objective='fixed-target normalized interior variance + mean-level error + peak overcut penalty',
        selection_score=float(best['score']), work_region_candidates=records)
    speeds = np.divide(1.875*np.linalg.norm(np.diff(points, axis=0), axis=1), durations,
        out=np.zeros_like(durations), where=durations > 0)
    uniformity = dict(metric='population standard deviation / mean; lower is more uniform',
        interior_edge_exclusion_mm=.5*c['pad_radius_mm'],
        interior=dict(inference=uniformity_metrics(result['maps']['inference'], interior),
            predicted_combined=uniformity_metrics(result['maps']['inference']+predicted, interior)),
        footprint=dict(inference=uniformity_metrics(result['maps']['inference'], processed),
            predicted_combined=uniformity_metrics(result['maps']['inference']+predicted, processed)))
    return dict(**profile, target=target, additional=additional, predicted=predicted,
        points=points, path_start=path_start, processed_region=processed,
        allowed_region=allowed, allowed_centers=allowed_centers,
        work_centers=best['work_centers'],
        uniformity_region=interior, uniformity=uniformity,
        segment_duration_s=durations, segment_peak_speed_mm_s=speeds,
        geometry=dict(source='measured contact swept disk', margin_mm=c['blend_width_mm'],
            lane_spacing_mm=c['lane_spacing_mm'], disconnected_transfers_at_clearance=int(path_start[1:].sum()),
            connector_routing='shortest interior grid route with line-of-sight simplification',
            work_region_selection='Preston-footprint weighted existing dose; compare dense combined predictions on the same full footprint',
            selected_existing_dose_quantile=best['selected_quantile'],
            resolution_mm=c['cell_mm'], tool_radius_mm=c['pad_radius_mm']),
        fitted_forces=forces, surface_z_mm=surface_z,
        surface_z_source='configured' if c['surface_z_mm'] is not None else '90th percentile measured contact Z',
        fit=dict(fit, dense_residual_norm=float(np.linalg.norm(predicted-additional)),
            dense_relative_residual=float(np.linalg.norm(predicted-additional)/max(np.linalg.norm(additional), 1e-12))))


def save_maps(path, result, plan=None):
    arrays = dict(x_mm=result['x_mm'], y_mm=result['y_mm'],
        inference=result['maps']['inference'], blending=result['maps']['blending'],
        combined=result['maps']['combined'], kernel=result['kernel'])
    if plan is not None:
        arrays.update(target=plan['target'], additional=plan['additional'], predicted_blending=plan['predicted'])
        for key in ('processed_region', 'allowed_region', 'allowed_centers', 'points', 'path_start',
                    'uniformity_region', 'work_centers', 'segment_duration_s', 'segment_peak_speed_mm_s'):
            if key in plan:
                arrays[key] = plan[key]
    np.savez_compressed(path, **arrays)


def render_maps(path, result, combined=False, plan=None, execution_outcome=None):
    # Imported only on a worker while the robot is at observed clearance.
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    names = ['inference', 'blending', 'combined'] if combined else ['inference']
    fig = Figure(figsize=(5.3*len(names), 5.)); canvas = FigureCanvasAgg(fig)
    vmax = max(float(result['maps'][s].max()) for s in names) or 1.
    extent = [result['x_mm'][0], result['x_mm'][-1], result['y_mm'][0], result['y_mm'][-1]]
    for i, name in enumerate(names, 1):
        ax = fig.add_subplot(1, len(names), i)
        im = ax.imshow(result['maps'][name], origin='lower', extent=extent, aspect='equal',
            vmin=0, vmax=vmax, cmap='magma')
        title = {'inference': 'inference only', 'blending': 'blending path only',
                 'combined': 'combined'}[name]
        ax.set(title=title, xlabel='robot base X (mm)', ylabel='robot base Y (mm)')
        if plan is not None and not combined:
            splits = np.flatnonzero(plan.get('path_start', np.zeros(len(plan['points']), bool)))[1:]
            for work_path in np.split(plan['points'], splits):
                ax.plot(work_path[:, 0], work_path[:, 1], color='cyan', alpha=.7, linewidth=.7)
            if 'allowed_region' in plan:
                ax.contour(result['x_mm'], result['y_mm'], plan['allowed_region'],
                    levels=[.5], colors=['cyan'], linewidths=.6, linestyles='dashed')
        fig.colorbar(im, ax=ax, label=result['unit'])
    outcome = '' if execution_outcome in (None, 'completed') else ' | '+execution_outcome
    title = 'inference + blending' if combined else (
        'inference' if execution_outcome == 'blending plan failed' else 'inference; next: blending')
    fig.suptitle('E2 C | '+title+outcome+'\n'+
        ('calibrated estimate' if result['calibrated'] else 'UNCALIBRATED rotary model'), fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, .93)); canvas.draw(); canvas.print_png(str(path))
    return np.asarray(canvas.buffer_rgba())[:, :, :3].copy()
