E2 2026-10-13 report

PDF: /home/eunseop/nrs_imitation/results/20261013/E2_report_20261013.pdf
Layout reference: results/20260930/E2_report_20260930.pdf
The original report's fonts, A4 layout, colors, tables and 15-page section
order are reused. Original experiment records and the reference PDF are unchanged.

Scope and completion criterion:
- E2_force_cleanup_20261013: all 15 attempts, A/B/C five each.
- Completion time uses execution_start to the first operator_finish request.
- The operator reported that termination followed complete stain removal,
  contact-release/lift, and the beginning of a further descent. The exact
  statement and its after-run provenance are preserved in
  operator_completion_criterion.json.
- The same original event interval is interpreted as operator-confirmed task
  completion time and used for time-based processing efficiency comparison.
  It includes lift/reapproach and operator response time. The earliest actual
  erasure time was not separately measured; no delay correction is applied.
- All attempts are retained, including the longer A4. No raw event time or
  stop reason is changed. Operator observation and automatic stop flags are
  reported separately.

Conditions:
A: force observation OFF, pose-only policy, constant external target 23 N.
B: force observation OFF, learned pose and force output.
C: force observation/history ON, learned pose and force output.
The 2026-10-12 force-cleanup checkpoints and normalizers are verified against
the models named in each current run; older experiments are not pooled.

Files:
metrics.json / metrics_per_run.csv / metrics_summary.csv: individual results
and condition means with sample SD (n=5 each).
run_inventory.csv: all attempts, execution order and original stop reasons.
input_manifest.json / integrity.json: 807 original input files and SHA-256 checks.
logger_quality.json: all 30 loggers drained, CSV row counts and write/drop checks.
video_audit.json: B/C ten existing videos decode; A's five absent videos remain
reported as missing. All 30 initial/final photos and 15 heatmaps are retained.
numeric_validation.json: independent native CSV force ZOH, peaks, TCP XY
distance and original-event completion-time checks.
validation.json: page bounds, input preservation, model and layout checks.
visual_review.json / previews/ / contact_sheet_1/2.png: reviewed final PDF pages.
report_text.txt: text extracted from the generated PDF.

Reproduce (offline; starts no ROS node and sends no robot command):
cd /home/eunseop/nrs_imitation
source scripts/e2_force_cleanup_20261013_env.sh
python3 reports/20261013_E2_pdf_report/build_report.py

Analysis only:
python3 reports/20261013_E2_pdf_report/build_report.py --analysis-only

Measured robot_base Fz uses native receipt timestamps with ZOH and a maximum
gap of 0.2 s; TCP is interpolated only within recorded support. No external
resampling pretends to increase sensor recording frequency. No TCP target
force is subtracted from base Fz, and no duplicate gravity/zero correction is
applied. The existing 50 N diagnostic is not a new controller limit or a
valid-processing threshold. Legacy heatmaps remain an uncalibrated diagnostic,
not measured material-removal amount. No force or coverage criterion is fitted
to the observed results.
