#!/usr/bin/env python3
"""Regenerate every data figure of the thesis from the bundled data/ extracts.

Only presentation changes here (typeface, colour, layout). The plotted values,
analysis windows, and run selections are read unchanged from data/; nothing is
smoothed, clipped, imputed, or re-estimated.

Usage:  python3 scripts/make_figures.py
Needs:  numpy, matplotlib (>= 3.5), pillow.
"""
from pathlib import Path
import csv
import statistics as st

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon
from PIL import Image

P = Path(__file__).resolve().parents[1]
D = P / 'data'
F = P / 'figures'
W = 5.9  # text width in inches (150 mm): figures are included at \linewidth

INK = '#1a1a1a'
MUTED = '#6b6b6b'
GRID = '#d9d9d9'
# Fixed colour per entity, reused in every figure.
METHOD = {'R': '#5b6b7b', 'Rstar': '#d98a1f', 'T': '#1f8a70', 'C': '#3b5bb5',
          'A': '#b0486a', 'B': '#7d5fb2'}
MARKER = {'R': 'o', 'Rstar': 's', 'T': '^', 'C': 'v', 'A': 'o', 'B': 's'}
PLACE = {'N': '#5b6b7b', 'P1': '#d98a1f', 'D1': '#1f8a70', 'D2': '#3b5bb5'}
PLACE_MARKER = {'N': 'o', 'P1': 's', 'D1': '^', 'D2': 'v'}
RUN = ['#0072B2', '#E69F00', '#009E73', '#D55E00', '#CC79A7']  # repeats 1..5
Q95 = 30.812396273  # teaching Q95 reference (N)

plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['STIXGeneral', 'Nimbus Roman', 'Liberation Serif', 'Times New Roman', 'DejaVu Serif'],
    'mathtext.fontset': 'stix',
    'font.size': 9, 'axes.labelsize': 9, 'axes.titlesize': 9.5,
    'xtick.labelsize': 8, 'ytick.labelsize': 8, 'legend.fontsize': 8,
    'axes.edgecolor': INK, 'axes.labelcolor': INK, 'text.color': INK,
    'xtick.color': INK, 'ytick.color': INK,
    'axes.linewidth': .6, 'xtick.major.width': .6, 'ytick.major.width': .6,
    'xtick.major.size': 3, 'ytick.major.size': 3,
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': .5, 'axes.axisbelow': True,
    'legend.frameon': False, 'legend.handlelength': 1.6, 'legend.columnspacing': 1.2,
    'lines.linewidth': 1.1,
    'pdf.fonttype': 42, 'ps.fonttype': 42, 'savefig.dpi': 300,
})


def rows(name):
    with (D / name).open(newline='') as f:
        return list(csv.DictReader(f))


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float('nan')


def trace(cohort, label, kind):
    with (D / 'traces' / f'{cohort}_{label}_{kind}.csv').open(newline='') as f:
        r = csv.reader(f)
        head = next(r)
        arr = np.array([[num(v) for v in line] for line in r])
    return {h: arr[:, i] for i, h in enumerate(head)}


def bounded(tr, end, columns, hold=False):
    """Restrict a trace to [0, end]; zero-order hold for force, linear for pose."""
    t = tr['time_s']
    values = np.column_stack([tr[c] for c in columns])
    inner = t[(t > 0) & (t < end)]
    edges = np.r_[0, inner, end]
    if hold:
        out = values[np.clip(np.searchsorted(t, edges, side='right') - 1, 0, len(t) - 1)]
    else:
        out = np.column_stack([np.interp(edges, t, values[:, i]) for i in range(len(columns))])
    return edges, out


def stats(values):
    v = [float(x) for x in values if x not in ('', None)]
    return st.mean(v), (st.stdev(v) if len(v) > 1 else 0.0), len(v)


def save(fig, name):
    fig.savefig(F / (name + '.pdf'))
    plt.close(fig)
    print('wrote', name + '.pdf')


def panel_label(ax, text):
    ax.set_title(text, loc='left', fontweight='bold', pad=4)


def mean_sd(ax, x, mean, sd):
    ax.errorbar(x, mean, yerr=sd, fmt='D', color=INK, ms=4, capsize=3, lw=.9, zorder=4)


MEAN_HANDLE = Line2D([], [], marker='D', color=INK, ms=4, lw=.9, label=r'mean $\pm$ sample SD')

e1 = rows('e1_runs.csv')
e2 = rows('e2_runs_corrected.csv')
for r in e1 + e2:
    r['repeat_index'] = int(r['repeat_index'])


# ---------------------------------------------------------------- Chapter 4
def teaching_figures():
    with (D / 'teaching_episode29.csv').open(newline='') as f:
        r = csv.reader(f)
        head = next(r)
        arr = np.array([[num(v) for v in line] for line in r])
    demo = {h: arr[:, i] for i, h in enumerate(head)}
    t = demo['time_s']

    fig, axes = plt.subplots(2, 1, figsize=(W, 3.9), sharex=True, layout='constrained')
    for col, label, color, lw in [
            ('fz_raw_published_N', 'Published, before offline EMA', '#9aa5b1', .8),
            ('fz_ema_N', 'EMA before cleanup', RUN[1], 1.0),
            ('fz_cleanup_N', 'Learning cleanup', RUN[0], 1.2)]:
        axes[0].plot(t, demo[col], label=label, color=color, lw=lw)
    axes[0].set_ylabel(r'Native $F_z$ (N)')
    axes[0].legend(loc='upper left')
    panel_label(axes[0], '(a) Processing stages')
    axes[1].plot(t, demo['fz_base_N'], color=RUN[0], lw=1.2)
    axes[1].set_ylabel(r'Base $F_z$ (N)')
    axes[1].set_xlabel('Original paired source time (s)')
    panel_label(axes[1], '(b) Cleanup vector rotated to the robot base')
    save(fig, 'force_processing')

    fig, axes = plt.subplots(3, 1, figsize=(W, 5.0), sharex=True, layout='constrained')
    axes[0].plot(t, demo['x_rel_mm'], label=r'$x$ relative', color=RUN[0])
    axes[0].plot(t, demo['y_rel_mm'], label=r'$y$ relative', color=RUN[3])
    axes[0].set_ylabel('Position (mm)')
    axes[0].legend(ncol=2, loc='upper left')
    panel_label(axes[0], '(a) Task-relative XY')
    axes[1].plot(t, demo['z_mm'], color=INK)
    axes[1].axhline(175, ls=':', color=MUTED, lw=.9)
    axes[1].set_ylabel(r'Stored $z$ (mm)')
    panel_label(axes[1], '(b) Height')
    for name, color in [('fx', RUN[0]), ('fy', RUN[1]), ('fz', RUN[2])]:
        axes[2].plot(t, demo[name + '_cleanup_N'], label=f'$f_{name[1]}$', color=color)
    axes[2].set_ylabel('Native force (N)')
    axes[2].legend(ncol=3, loc='upper left')
    axes[2].set_xlabel('Original paired source time (s)')
    panel_label(axes[2], '(c) Cleaned force')
    save(fig, 'teaching_motion_force')

    data = rows('dataset_episodes.csv')
    for r in data:
        r['number'] = int(''.join(ch for ch in r['episode'].split('.')[0] if ch.isdigit()))
    data.sort(key=lambda r: r['number'])
    fig, ax = plt.subplots(figsize=(W, 2.5), layout='constrained')
    for split, color, label in [('train', METHOD['C'], 'Optimization (38 episodes)'),
                                ('validation', METHOD['Rstar'], 'Validation (4 episodes)')]:
        part = [r for r in data if (r['split'] == 'validation') == (split == 'validation')]
        ax.bar([r['number'] for r in part], [int(r['frames']) for r in part], width=.72,
               color=color, label=label, hatch='///' if split == 'validation' else None,
               edgecolor='white', linewidth=.4)
    ax.set_xlabel('Episode index')
    ax.set_ylabel('Stored paired frames')
    ax.set_xticks(range(0, 42, 5))
    ax.set_xlim(-1, 42)
    ax.set_ylim(0, 540)
    ax.grid(axis='x', visible=False)
    ax.legend(ncol=2, loc='upper right')
    save(fig, 'dataset_split')


# ---------------------------------------------------------------- E1
def e1_figures():
    rstar = rows('e1_rstar_source_runs.csv')
    groups = [('R', [r for r in e1 if r['method'] == 'R']), ('Rstar', rstar),
              ('T', [r for r in e1 if r['method'] == 'T']), ('C', [r for r in e1 if r['method'] == 'C'])]
    ticks = ['R\n15 Oct', '$R^{*}$\n19 Oct', 'T\n15 Oct', 'C\n15 Oct']
    fig, axes = plt.subplots(1, 2, figsize=(W, 2.9), layout='constrained')
    for ax, key, lab, title in zip(
            axes, ['completion_time_s', 'J_excess_Ns'],
            ['First procedural completion (s)', r'Excess-force integral $J_{\mathrm{excess}}$ (N$\cdot$s)'],
            ['(a) Completion time', '(b) Excess-force exposure']):
        for i, (c, part) in enumerate(groups):
            vals = [float(r[key]) for r in part]
            x = np.arange(5) * .10 + i - .22
            ax.scatter(x, vals, color=METHOD[c], marker=MARKER[c], edgecolors='white',
                       linewidths=.4, s=26, zorder=3)
            for j, (xx, yy) in enumerate(zip(x, vals)):
                if (c == 'Rstar' and j == 0 and key == 'completion_time_s') or (c == 'C' and j == 4):
                    ax.annotate('$R^{*}$1' if c == 'Rstar' else 'C5', (xx, yy), xytext=(0, 5),
                                textcoords='offset points', fontsize=7.5, ha='center')
            m, sd, _ = stats(vals)
            mean_sd(ax, i + .36, m, sd)
        ax.set_xticks(range(4))
        ax.set_xticklabels(ticks)
        ax.set_ylabel(lab)
        ax.grid(axis='x', visible=False)
        ax.set_xlim(-.5, 3.65)
        ax.set_ylim((-2, 34) if key == 'completion_time_s' else (-1.7, 8.0))
        ax.axvline(1.57, color=MUTED, ls=':', lw=.8)
        panel_label(ax, title)
    axes[0].legend(handles=[MEAN_HANDLE], loc='lower left')
    save(fig, 'e1_latest_metrics')

    fig, axes = plt.subplots(3, 1, figsize=(W, 5.4), sharex=True, sharey=True, layout='constrained')
    for ax, method in zip(axes, 'RTC'):
        for r in sorted((r for r in e1 if r['method'] == method), key=lambda r: r['repeat_index']):
            t, y = bounded(trace('E1', r['label'], 'force'), float(r['evaluation_end_s']), ['fz'], True)
            ax.step(t, y[:, 0], where='post', lw=.7, alpha=.9, label=r['label'],
                    color=RUN[r['repeat_index'] - 1])
        ax.axhline(Q95, color=INK, ls='--', lw=.8, label='Teaching Q95')
        ax.set_ylabel(r'$F_z^B$ (N)')
        ax.set_ylim(-5, 54)
        panel_label(ax, {'R': '(a) R: rule', 'T': '(b) T: demonstration replay',
                         'C': '(c) C: force-conditioned policy'}[method])
        leg = ax.legend(ncol=6, loc='upper right', borderaxespad=.2, handlelength=1.3)
        for line in leg.get_lines():
            line.set_linewidth(1.6)
    axes[-1].set_xlabel('Time from execution start (s)')
    save(fig, 'e1_force_all')

    p0 = np.array([445, 395]); p1 = np.array([487, 345])
    d = (p1 - p0) / np.linalg.norm(p1 - p0); n = np.array([-d[1], d[0]])
    band = np.array([p0 + 12.5 * n, p1 + 12.5 * n, p1 - 12.5 * n, p0 - 12.5 * n])
    fig, axes = plt.subplots(1, 3, figsize=(W, 2.75), sharex=True, sharey=True, layout='constrained')
    for ax, method in zip(axes, 'RTC'):
        ax.add_patch(Polygon(band, facecolor='#e9eef2', edgecolor='#9aa5b1', lw=.6))
        for r in sorted((r for r in e1 if r['method'] == method), key=lambda r: r['repeat_index']):
            _, y = bounded(trace('E1', r['label'], 'pose'), float(r['evaluation_end_s']), ['x', 'y'])
            color = RUN[r['repeat_index'] - 1]
            ax.plot(y[:, 0], y[:, 1], lw=.9, label=r['label'], color=color, alpha=.9)
            ax.scatter(y[-1, 0], y[-1, 1], s=12, marker='s', color=color, zorder=3)
        panel_label(ax, {'R': '(a) R', 'T': '(b) T', 'C': '(c) C'}[method])
        ax.set_xlabel(r'Base $x$ (mm)')
        ax.set_aspect('equal', adjustable='box')
        ax.legend(ncol=1, loc='upper right', handlelength=1.2, labelspacing=.25, borderaxespad=.1)
    axes[0].set_ylabel(r'Base $y$ (mm)')
    save(fig, 'e1_xy_all')

    diag = rows('e1_c5_c6.csv')
    fig, axes = plt.subplots(2, 2, figsize=(W, 4.3), sharex='col', sharey='row', layout='constrained')
    events = [('contact_at_s', ':', MUTED, 'Confirmed contact'),
              ('pass_completed_at_s', '--', RUN[0], 'Required pass completed'),
              ('completion_time_s', '-', RUN[3], 'First completion')]
    for j, label in enumerate(['C5', 'C6']):
        r = next(x for x in diag if x['label'] == label)
        end = float(r['evaluation_end_s'])
        t, y = bounded(trace('E1', label, 'force'), end, ['fz'], True)
        axes[0, j].step(t, y[:, 0], where='post', color=METHOD['C'], lw=.8)
        axes[0, j].axhline(Q95, color=INK, ls='--', lw=.8)
        t, y = bounded(trace('E1', label, 'pose'), end, ['z'])
        axes[1, j].plot(t, y[:, 0], color=METHOD['C'], lw=1.0)
        axes[1, j].axhline(float(r['z_release_threshold_mm']), color=MUTED, ls='--', lw=.8)
        for ax in axes[:, j]:
            for key, style, color, _ in events:
                ax.axvline(float(r[key]), ls=style, color=color, lw=.9)
            ax.set_xlim(0, 19)
        panel_label(axes[0, j], '(a) C5 (primary)' if label == 'C5' else '(b) C6 (additional diagnostic)')
        axes[1, j].set_xlabel('Time from execution start (s)')
    axes[0, 0].set_ylabel(r'Measured $F_z^B$ (N)')
    axes[1, 0].set_ylabel(r'Measured base $z$ (mm)')
    handles = [Line2D([], [], color=c, ls=s, lw=.9, label=l) for _, s, c, l in events]
    handles += [Line2D([], [], color=INK, ls='--', lw=.8, label='Teaching Q95 / release height')]
    axes[1, 0].legend(handles=handles, loc='upper right', bbox_to_anchor=(.85, 1.0), borderaxespad=.2)
    save(fig, 'e1_c5_c6')

    h = rows('e1_height_reference_replay.csv')
    fig, ax = plt.subplots(figsize=(W, 2.8), layout='constrained')
    x = np.arange(len(h))
    ax.scatter(x, [float(r['A_release_threshold_mm']) for r in h], marker='x', s=30, lw=1.1,
               color=RUN[3], label='Original: initial-contact reference + 5 mm')
    ax.scatter(x, [float(r['B_release_threshold_mm']) for r in h], marker='o', s=18,
               color=RUN[0], label='Replay: loaded-pass reference + 5 mm')
    ax.set_xticks(x)
    ax.set_xticklabels([r['report_label'] for r in h])
    ax.set_ylabel(r'Base $z$ release threshold (mm)')
    ax.set_ylim(bottom=170)
    ax.grid(axis='x', visible=False)
    ax.legend(loc='center right')
    save(fig, 'e1_height_reference')

    fig, axes = plt.subplots(3, 2, figsize=(W, 5.6), layout='constrained')
    for i, method in enumerate('RTC'):
        for j, phase in enumerate(['initial', 'final']):
            axes[i, j].imshow(Image.open(F / f'E1_{method}1_{phase}.png'))
            axes[i, j].axis('off')
            axes[i, j].set_title(f'{method}1, {phase}', pad=3)
    save(fig, 'e1_snapshot_panel')


# ---------------------------------------------------------------- E2
def e2_figures():
    fig, axes = plt.subplots(1, 3, figsize=(W, 2.7), layout='constrained')
    for i, g in enumerate('ABC'):
        part = [r for r in e2 if r['condition'] == g]
        dx = np.linspace(-.20, .12, 5)
        for j, r in enumerate(part):
            ok = r['completion_time_corrected_s'] != ''
            axes[0].scatter(i + dx[j], float(r['execution_duration_s']), marker=MARKER[g] if ok else 'x',
                            s=26 if ok else 34, color=METHOD[g], edgecolors='white' if ok else None,
                            linewidths=.4 if ok else 1.3, zorder=3)
            if not ok:
                axes[0].annotate('A4 interrupted', (i + dx[j], float(r['execution_duration_s'])),
                                 xytext=(6, -1), textcoords='offset points', fontsize=7.5, va='center')
            for ax, key in [(axes[1], 'peak_fz_N'), (axes[2], 'tcp_xy_path_mm')]:
                ax.scatter(i + dx[j], float(r[key]), s=26, marker=MARKER[g], color=METHOD[g],
                           edgecolors='white', linewidths=.4, zorder=3)
        m, sd, _ = stats(r['completion_time_corrected_s'] for r in part)
        mean_sd(axes[0], i + .30, m, sd)
    for ax, title in zip(axes, ['(a) Time', '(b) Peak force', '(c) XY travel']):
        ax.set_xticks(range(3))
        ax.set_xticklabels(list('ABC'))
        ax.set_xlim(-.5, 2.6)
        ax.grid(axis='x', visible=False)
        panel_label(ax, title)
    axes[0].set_ylabel('Completion / interruption (s)'); axes[0].set_ylim(0, 33)
    axes[1].set_ylabel(r'Measured peak $F_z^B$ (N)'); axes[1].set_ylim(0, 37)
    axes[2].set_ylabel('Measured XY travel (mm)'); axes[2].set_ylim(0, 370)
    axes[0].legend(handles=[MEAN_HANDLE], loc='lower left', handletextpad=.3, borderaxespad=.1)
    save(fig, 'e2_primary_metrics')

    fig, axes = plt.subplots(3, 1, figsize=(W, 5.4), sharex=True, sharey=True, layout='constrained')
    for ax, g in zip(axes, 'ABC'):
        for r in [r for r in e2 if r['condition'] == g]:
            s = trace('E2', r['label'], 'force')
            keep = (s['time_s'] >= 0) & (s['time_s'] <= float(r['execution_duration_s']))
            ax.step(s['time_s'][keep], s['fz'][keep], where='post', alpha=.9, lw=.7,
                    label=r['label'], color=RUN[r['repeat_index'] - 1])
        ax.set_ylabel(r'$F_z^B$ (N)')
        ax.set_ylim(-4, 43)
        panel_label(ax, {'A': '(a) A: pose-only learning, external force target',
                         'B': '(b) B: motion–force learning, masked force observation',
                         'C': '(c) C: motion–force learning, measured-force conditioning'}[g])
        leg = ax.legend(ncol=5, loc='upper right', borderaxespad=.2, handlelength=1.3)
        for line in leg.get_lines():
            line.set_linewidth(1.6)
    axes[-1].set_xlabel('Time from execution start (s)')
    save(fig, 'e2_force_all')

    fig, axes = plt.subplots(2, 2, figsize=(W, 4.0), sharex='col', layout='constrained')
    for j, label in enumerate(['A4', 'B4']):
        r = next(x for x in e2 if x['label'] == label)
        end = float(r['execution_duration_s'])
        force = trace('E2', label, 'force'); pose = trace('E2', label, 'pose')
        kf = (force['time_s'] >= 0) & (force['time_s'] <= end)
        kp = (pose['time_s'] >= 0) & (pose['time_s'] <= end)
        axes[0, j].step(force['time_s'][kf], force['fz'][kf], where='post', color=METHOD[label[0]], lw=.8)
        axes[1, j].plot(pose['time_s'][kp], pose['z'][kp], color=METHOD[label[0]], lw=1.0)
        panel_label(axes[0, j], '(a) A4: operator stopped' if label == 'A4' else '(b) B4: 38 gate transitions')
        axes[1, j].set_xlabel('Time from execution start (s)')
    axes[0, 0].set_ylabel(r'Measured $F_z^B$ (N)')
    axes[1, 0].set_ylabel(r'Measured base $z$ (mm)')
    save(fig, 'e2_transition_cases')

    offsets = [1.69, 6.76, 11.83, 15.21]  # archived video-relative offsets (s)
    fig, axes = plt.subplots(2, 2, figsize=(W, 3.7), layout='constrained')
    for k, (ax, off) in enumerate(zip(axes.flat, offsets)):
        pixels = np.asarray(Image.open(F / f'E2_C1_video_{k}.png'))
        ax.imshow(pixels[:, :pixels.shape[1] // 2])  # camera pane only
        ax.axis('off')
        ax.set_title(f'Video offset {off:.2f} s', pad=3)
    save(fig, 'e2_sequence')


# ---------------------------------------------------------------- E3
def e3_figures():
    e3 = rows('e3_source_area_runs.csv')
    order = ['N', 'P1', 'D1', 'D2']
    fig, ax = plt.subplots(figsize=(W, 3.1), layout='constrained')
    for i, c in enumerate(order):
        part = [r for r in e3 if r['condition'] == c and r['image_evaluable'] == 'True']
        vals = [float(r['removal_percent']) for r in part]
        x = i + np.linspace(-.20, .12, len(part))
        ax.scatter(x, vals, color=PLACE[c], marker=PLACE_MARKER[c], edgecolors='white',
                   linewidths=.4, s=30, zorder=3)
        for xx, r, v in zip(x, part, vals):
            ax.annotate(r['repeat_index'], (xx, v), xytext=(0, 5), textcoords='offset points',
                        ha='center', fontsize=7.5)
        m, sd, _ = stats(vals)
        mean_sd(ax, i + .28, m, sd)
    counts = {c: sum(r['condition'] == c and r['image_evaluable'] == 'True' for r in e3) for c in order}
    ax.set_xticks(range(4))
    ax.set_xticklabels([f'{c}\n$n={counts[c]}$' for c in order])
    ax.set_ylabel('Image-based stain-area removal (%)')
    ax.set_ylim(75, 106); ax.set_xlim(-.5, 3.6)
    ax.grid(axis='x', visible=False)
    ax.legend(handles=[MEAN_HANDLE], loc='lower left', bbox_to_anchor=(0, .08))
    ax.text(.012, .03, 'D1-4: final tool occlusion; no imputed value', transform=ax.transAxes,
            fontsize=8, color=MUTED)
    save(fig, 'e3_removal_metrics')

    place = {r['condition']: (float(r['delta_x_mm']), float(r['delta_y_mm']), float(r['phi_deg']))
             for r in rows('e3_registered_placements.csv')}
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(W, 2.8), layout='constrained')
    offsets = {'N': (5, 6), 'P1': (-6, -12), 'D1': (-17, 3), 'D2': (5, -10)}
    for c in order:
        x, y, phi = place[c]
        ax.scatter(x, y, color=PLACE[c], marker=PLACE_MARKER[c], s=34, edgecolors='white',
                   linewidths=.4, zorder=3)
        ax.annotate(c, (x, y), xytext=offsets[c], textcoords='offset points', fontweight='bold')
        if c == 'P1':
            continue
        rad = np.deg2rad(phi)
        bx.annotate('', xy=(np.cos(rad), np.sin(rad)), xytext=(0, 0),
                    arrowprops=dict(arrowstyle='-|>', color=PLACE[c], lw=1.8, shrinkA=0, shrinkB=0))
        bx.text(1.08 * np.cos(rad), 1.08 * np.sin(rad),
                f'{c}: ${phi:+.2f}^\\circ$' if phi else r'N / P1: $0^\circ$', ha='left', va='center')
    ax.axhline(0, color=MUTED, lw=.6); ax.axvline(0, color=MUTED, lw=.6)
    ax.set_xlabel(r'Registered $\Delta x$ (mm)'); ax.set_ylabel(r'Registered $\Delta y$ (mm)')
    ax.set_xlim(-7, 36); ax.set_ylim(-8, 28); ax.set_aspect('equal')
    panel_label(ax, '(a) Registered centers')
    bx.set_xlim(-.1, 1.85); bx.set_ylim(-.85, 1.0); bx.set_aspect('equal'); bx.axis('off')
    bx.set_title('(b) Direction relative to nominal', loc='left', fontweight='bold', pad=4)
    save(fig, 'e3_registered_layout')

    metrics = {r['display_label']: r for r in rows('e3_raw_reproduction.csv')}
    x0, y0, x1, y1 = 175, 39, 325, 135  # archived display crop of the mask panels

    def evidence(labels, name):
        fig, axes = plt.subplots(2 * len(labels), 2, figsize=(W, 3.35 * len(labels)), squeeze=False,
                                 gridspec_kw={'height_ratios': sum(([1., .72] for _ in labels), [])},
                                 layout='constrained')
        for i, label in enumerate(labels):
            folder = F / 'e3_native' / label
            r = metrics[label]
            rgb = [np.asarray(Image.open(folder / 'before.png')), np.asarray(Image.open(folder / 'after.png'))]
            roi = np.asarray(Image.open(folder / 'roi_before.png')) > 0
            occ = np.asarray(Image.open(folder / 'final_occlusion_mask_aligned.png')) > 0
            mask = [np.asarray(Image.open(folder / 'initial_ink_mask.png')) > 0,
                    np.asarray(Image.open(folder / 'final_ink_mask_aligned.png')) > 0]
            for j in range(2):
                ax = axes[2 * i, j]
                ax.imshow(rgb[j], interpolation='nearest'); ax.axis('off')
                ax.set_title(f'{label}: ' + ('RGB before' if j == 0 else 'RGB after'), pad=3)
                ax = axes[2 * i + 1, j]
                # White background with exact black ink pixels supports grayscale print.
                ax.imshow(~mask[j][y0:y1, x0:x1], cmap='gray', vmin=0, vmax=1,
                          interpolation='nearest', extent=[x0, x1, y1, y0])
                ax.contour(roi[y0:y1, x0:x1], levels=[.5], colors=[MUTED], linewidths=.8,
                           linestyles='--', extent=[x0, x1, y1, y0], origin='upper')
                if j and occ.any():
                    ax.contourf(occ[y0:y1, x0:x1], levels=[.5, 1.5], colors=['none'], hatches=['////'],
                                extent=[x0, x1, y1, y0], origin='upper')
                count = int(mask[j].sum())
                title = ('Ink mask before' if j == 0 else 'Ink mask after') + f': {count} px'
                if j and r['A_after_px'] == '':
                    title = f'Ink mask after: whole area unavailable; visible {count} px'
                ax.set_title(title, pad=3, fontsize=8.5)
                ax.set_xticks([175, 225, 275, 325]); ax.set_yticks([40, 85, 130])
                ax.tick_params(labelsize=7); ax.grid(False)
                for spine in ax.spines.values():
                    spine.set_visible(True); spine.set_color('#9aa5b1')
        save(fig, name)

    evidence(['N-1', 'P1-1'], 'e3_first_index_evidence_np')
    evidence(['D1-1', 'D2-1'], 'e3_first_index_evidence_d')
    for label in ['D1-4', 'P2-1', 'D2-3']:
        evidence([label], f'e3_{label}_native_evidence')


if __name__ == '__main__':
    teaching_figures()
    e1_figures()
    e2_figures()
    e3_figures()
