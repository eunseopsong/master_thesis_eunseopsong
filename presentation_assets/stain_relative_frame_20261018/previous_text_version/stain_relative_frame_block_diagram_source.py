#!/usr/bin/env python3
"""Render the implemented stain-center / optional direction-transfer logic.

No robot, ROS, dataset, or checkpoint is imported or executed.
Run: python3 stain_relative_frame_block_diagram_source.py --output-dir .
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import tempfile
import warnings

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'stain_frame_diagram_mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parent
BASE = 'stain_relative_frame_block_diagram'
SOURCE_FILES = {
    'behavior_ws/src/stain_relative_frame/stain_relative_frame/stain_detect.py':
        ['dark_cloud_origin'],
    'behavior_ws/src/stain_relative_frame/stain_relative_frame/inference_adapter.py':
        ['_on_origin (one-shot frozen origin and optional angle)'],
    'behavior_ws/src/stain_relative_frame/stain_relative_frame/relative_frame.py':
        ['to_relative', 'to_absolute'],
    'behavior_ws/src/stain_relative_frame/stain_relative_frame/dataset_relativize.py':
        ['convert_episode'],
    'behavior_ws/src/nrs_imitation/nrs_imitation/inference_core.py':
        ['_wrap_axis_delta', '_canon_setup', '_canon_obs_pose6', '_canon_rotate_image',
         '_canon_cmd_seq', '_srf_observation_pose6', '_srf_command_seq'],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT)
    parser.add_argument('--repo', type=Path, default=Path.home() / 'nrs_imitation')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    font_path = next((p for p in (
        Path('/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf'),
        Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),
    ) if p.exists()), None)
    if font_path:
        fm.fontManager.addfont(str(font_path))
        font = fm.FontProperties(fname=font_path).get_name()
    else:
        font = 'sans-serif'
        warnings.warn('Install a Korean font if your machine lacks Hangul glyphs.')
    plt.rcParams.update({
        'font.family': font,
        'mathtext.fontset': 'dejavusans',
        'axes.unicode_minus': False,
        'svg.fonttype': 'path',  # portable vector text without a font dependency
        'pdf.fonttype': 42,
    })

    C = dict(ink='#13263B', muted='#526478', line='#CFD9E4', blue='#2764AF',
             teal='#137D78', purple='#6F48A9', amber='#B97617', pale='#F5F7FA')
    fig = plt.figure(figsize=(16, 9), facecolor='white')
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set(xlim=(0, 16), ylim=(9, 0))
    ax.axis('off')
    text_bounds = []

    def txt(x, y, s, size=15, color=None, weight='normal', ha='left', va='center'):
        t = ax.text(x, y, s, fontsize=size, color=color or C['ink'],
                    fontweight=weight, ha=ha, va=va, linespacing=1.48, zorder=4)
        text_bounds.append(t)
        return t

    def box(x, y, w, h, fill='white', edge=None, radius=.10, lw=1.0, zorder=1):
        p = FancyBboxPatch((x, y), w, h, boxstyle=f'round,pad=0,rounding_size={radius}',
                           facecolor=fill, edgecolor=edge or C['line'], linewidth=lw,
                           zorder=zorder)
        ax.add_patch(p)
        return p

    def arrow(points, color=None, dashed=False, width=1.5, head=12):
        color = color or C['muted']
        for i in range(len(points) - 1):
            if i == len(points) - 2:
                p = FancyArrowPatch(points[i], points[i+1], arrowstyle='-|>',
                                    mutation_scale=head, lw=width, color=color,
                                    linestyle=(0, (4, 3)) if dashed else '-', zorder=3,
                                    shrinkA=0, shrinkB=0)
                ax.add_patch(p)
            else:
                ax.plot([points[i][0], points[i+1][0]], [points[i][1], points[i+1][1]],
                        color=color, lw=width, linestyle=(0, (4, 3)) if dashed else '-',
                        zorder=3)

    def small_card(x, w, title, body, accent, equation=None):
        y, h = 2.22, 1.40
        box(x, y, w, h, edge='#CFD9E4')
        ax.plot([x+.16, x+w-.16], [y+.03, y+.03], color=accent, lw=3, zorder=2)
        txt(x+w/2, y+.37, title, size=16.0, weight='bold', ha='center')
        if equation:
            txt(x+w/2, y+.79, equation, size=16.0, ha='center', color=accent)
            txt(x+w/2, y+1.14, body, size=12.8, ha='center', color=C['muted'])
        else:
            txt(x+w/2, y+.94, body, size=14.0, ha='center', color=C['muted'])

    # Heading: the two operations are deliberately separate.
    txt(.5, .48, '얼룩 중심·방향 기준 상대좌표 로직', size=27, weight='bold')
    txt(.5, .99, '중심을 원점으로 이동 → 교시 방향에 정렬 → 정책 생성 → 실제 작업 좌표로 복원',
        size=15.2, color=C['muted'])
    ax.plot([.5, 15.5], [1.29, 1.29], color=C['line'], lw=1)

    # Registration and training are independent sources for the online path.
    box(.5, 1.52, 7.27, 2.77, fill='#F3F7FC', edge='#DFE8F3', radius=.12)
    box(8.12, 1.52, 7.38, 2.77, fill='#F1F8F6', edge='#D8EAE4', radius=.12)
    txt(.73, 1.84, '01  작업 중심·방향 등록', size=17.4, color=C['blue'], weight='bold')
    txt(8.35, 1.84, '02  중심 상대좌표로 교시 학습', size=17.4, color=C['teal'], weight='bold')

    small_card(.72, 2.00, '현재 작업 영상', '표식 영역 검출\n공구 영역 제외', C['blue'])
    small_card(3.02, 2.00, '평면 Homography', '영상의 검출점\n→ 로봇 base XY', C['blue'])
    small_card(5.32, 2.22, '강건 중심 + SVD', '중심과 주축 추정', C['blue'],
               equation=r'$c_{\mathrm{live}},\;\theta_{\mathrm{live}}$')
    for a, b in [(2.78, 2.96), (5.08, 5.26)]:
        arrow([(a, 2.92), (b, 2.92)], C['blue'], head=10)
    txt(4.135, 3.96, '등록한 중심·주축은 episode 동안 고정', size=14, ha='center', color=C['blue'])

    small_card(8.35, 1.95, '시간 대응 교시', '영상 · 위치·자세\n시간 대응 힘 신호', C['teal'])
    small_card(10.60, 2.15, '중심 기준 XY', '관측·행동에 동일 적용', C['teal'],
               equation=r'$p_{\mathrm{rel}}=p_{xy}-c_{\mathrm{demo}}$')
    small_card(13.05, 2.22, 'Flow Matching 학습', '동작·목표 힘 시퀀스\n체크포인트 저장', C['teal'])
    for a, b in [(10.36, 10.54), (12.81, 12.99)]:
        arrow([(a, 2.92), (b, 2.92)], C['teal'], head=10)
    txt(11.81, 3.96, r'데이터 변환은 중심 이동만 적용 · 교시 기준 방향 $\theta_{\mathrm{ref}}$는 설정값',
        size=12.8, ha='center', color=C['teal'])

    # Dashed links are registration/model dependencies, solid links are observations/commands.
    txt(.5, 4.76, '03  온라인 생성·복원', size=17.5, weight='bold')
    arrow([(4.45, 4.29), (4.45, 5.22)], C['blue'], dashed=True, head=13)
    txt(4.64, 4.62, r'$c_{\mathrm{live}},\;\theta_{\mathrm{live}}$', size=13.2, color=C['blue'])
    arrow([(10.90, 4.29), (10.90, 4.77), (7.525, 4.77), (7.525, 5.22)],
          C['teal'], dashed=True, head=13)
    txt(9.2, 4.55, '학습된 가중치', size=13.2, color=C['teal'], ha='center')

    y, h = 5.25, 2.05
    cards = [(.5, 2.10, C['blue']), (2.95, 3.00, C['blue']),
             (6.30, 2.45, C['purple']), (9.10, 3.00, C['amber']),
             (12.45, 3.05, C['teal'])]
    for x, w, accent in cards:
        fill = {'#2764AF':'#F5F8FD', '#6F48A9':'#F7F4FC',
                '#B97617':'#FEF9F0', '#137D78':'#F1F8F6'}[accent]
        box(x, y, w, h, fill=fill, edge=accent, lw=1.15)
    for a, b in [(2.66, 2.89), (6.01, 6.24), (8.81, 9.04), (12.16, 12.39)]:
        arrow([(a, 6.28), (b, 6.28)], head=12)

    txt(1.55, 5.63, '현재 관측', size=17.4, weight='bold', ha='center')
    txt(1.55, 6.42, 'TCP 위치·자세\nRGB 영상\n측정 힘·이력', size=15.0, ha='center')

    txt(4.45, 5.63, '중심·방향 정렬', size=17.4, weight='bold', ha='center')
    txt(4.45, 6.13, r'$u=R(\alpha)(p_{xy}-c_{\mathrm{live}})$', size=17.0, ha='center', color=C['blue'])
    txt(4.45, 6.59, r'$\alpha=\mathrm{wrap}_{\pi}(\theta_{\mathrm{ref}}-\theta_{\mathrm{live}})$',
        size=14.0, ha='center')
    txt(4.45, 7.02, 'RGB: TCP-ROI 중심 회전¹', size=13.1, ha='center', color=C['muted'])

    txt(7.525, 5.63, 'Flow 정책', size=18.2, weight='bold', ha='center', color=C['purple'])
    txt(7.525, 6.20, '정규화 → 조건부 생성\n→ 역정규화', size=14.0, ha='center')
    txt(7.525, 6.91, r'$\widehat{u},\;z,\;\rho,\;f^{\mathrm{tar}}$', size=17.5, ha='center', color=C['purple'])

    txt(10.60, 5.63, '작업 좌표로 복원', size=17.4, weight='bold', ha='center')
    txt(10.60, 6.30, r'$p_{xy}^{\mathrm{cmd}}=R(-\alpha)\widehat{u}+c_{\mathrm{live}}$',
        size=16.0, ha='center', color=C['amber'])
    txt(10.60, 6.90, '역회전 → 중심 더하기', size=14.3, ha='center')

    txt(13.975, 5.63, '공통 실행 계층', size=17.4, weight='bold', ha='center')
    txt(13.975, 6.42, '계획 연결·평활화\n기존 하위 힘제어\n로봇 동작', size=15.0, ha='center')

    # The transform pair shares the same frozen registration, rather than re-detection per step.
    ax.plot([4.45, 4.45, 10.60, 10.60], [7.38, 7.64, 7.64, 7.38],
            color=C['line'], lw=1.4, zorder=1)
    box(5.05, 7.45, 4.95, .38, fill='white', edge='white', radius=0, lw=0)
    txt(7.525, 7.64, '입력 정렬과 출력 복원에 같은 중심·각도 사용',
        size=13.1, ha='center', color=C['muted'])

    box(.5, 8.05, 15.0, .49, fill=C['pale'], edge=C['pale'], radius=.08)
    txt(8.0, 8.295, 'XY 위치만 이동·회전  |  Z·공구 자세·힘 채널의 좌표 규약은 유지',
        size=14.5, ha='center', weight='bold')
    txt(.5, 8.79, '¹ 영상 회전은 옵션이며 이미지 좌표 부호 설정을 사용한다. 방향 정렬 OFF이면 α=0. E1/E2에서는 방향 정렬 OFF.',
        size=11.7, color=C['muted'])
    txt(15.5, .48, 'IMPLEMENTED LOGIC', size=10.2, ha='right', color=C['muted'])

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    fig_bounds = fig.bbox
    for t in text_bounds:
        bb = t.get_window_extent(renderer)
        assert bb.x0 >= fig_bounds.x0 and bb.y0 >= fig_bounds.y0, t.get_text()
        assert bb.x1 <= fig_bounds.x1 and bb.y1 <= fig_bounds.y1, t.get_text()

    for ext in ('png', 'svg', 'pdf'):
        path = args.output_dir / (BASE + '.' + ext)
        fig.savefig(path, dpi=240, facecolor='white', metadata=(
            {'Title': 'Stain-centered and direction-aligned relative coordinates',
             'Description': 'Implemented logic schematic; not a measured generalization result.'}
            if ext == 'svg' else None))
        print(path)
    plt.close(fig)

    sources = []
    for relative, functions in SOURCE_FILES.items():
        p = args.repo / relative
        sources.append(dict(path=str(p), functions=functions,
                            sha256=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None))
    record = dict(date='2026-10-18', figure_id=BASE, kind='implementation block diagram',
                  aspect_ratio='16:9', png_pixels=[3840,2160],
                  sources=sources, scope='XY translation; optional inference-time XY/image alignment; inverse XY restoration',
                  not_claimed='No new generalization experiment or performance measurement.',
                  unmodified='Robot code, model, datasets, experiment logs, and thesis manuscript.',
                  outputs={ext:hashlib.sha256((args.output_dir/(BASE+'.'+ext)).read_bytes()).hexdigest()
                           for ext in ['png','svg','pdf']})
    (args.output_dir/(BASE+'_provenance.json')).write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    main()
