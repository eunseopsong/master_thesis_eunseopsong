# Reproducibility — 2026-11-08

## Two distinct operations

The source ZIP rebuilds the thesis using included document assets. Repeating the original experimental analyses additionally requires the separately retained research archive. A document rebuild does not perform an experiment or claim to reproduce physical robot behavior.

## Standalone document build

Extract `Thesis_Source_20261108.zip`, enter `Thesis_Source_20261108/`, and run:

```bash
bash build.sh
```

The script performs three main pdfLaTeX passes, BibTeX, and a separate cover build, then extracts searchable PDF text. Per-pass logs and the combined `review/full_build.log` are generated locally. `ThesisMain.fls` and `ThesisCover.fls` record actual document inputs.

Required system programs: `pdflatex`, `bibtex`, `pdftotext`; a TeX Live installation with KoTeX, newtx text, TikZ, and the standard packages named in `ThesisMain.tex`. `pdftoppm`, `pdfinfo`, and `pdffonts` support PDF inspection. The original school style/class/bibliography-style files are bundled unchanged. No robot software or GPU is required. Font files are system dependencies and are not shipped.

## Regenerate affected numbers and panels

```bash
python3 scripts/update_results_20261108.py
python3 scripts/prepare_e3_assets_20261108.py
bash build.sh
python3 scripts/validate_examination_20261108.py
python3 scripts/render_examination_20261108.py
```

The first command reads bundled source-derived E1/E2 rows, the unrounded additional R* CSV, the E3 native-pixel reproduction CSV, and the saved placement mapping. It writes the single result JSON/precision CSV, editable LaTeX tables, prose macros, and affected plots. The second command uses seven selected original RGB pairs and unchanged masks in `figures/e3_native/`. It writes five photographic evidence panels. It applies one common native-coordinate crop, preserves aspect and individual pixels, and adds only vector ROI/occlusion annotations. It does not segment images or recover occlusion.

The current result authority is `data/results_summary_20261108.json`; `tables/result_numbers.tex` is generated from it. All displayed ± values are sample SD, not confidence intervals. Historical PDF-derived transcriptions remain separate in the local preservation archive and are not the inputs to the current result generator.

## Full source verification on the research PC

Research archive: `/home/eunseop/nrs_imitation`.
Active manuscript: `/home/eunseop/master_thesis_eunseopsong/thesis/local_polishing_revised_20261103`.

```bash
python3 scripts/reconnect_sources_20261108.py --research-root /home/eunseop/nrs_imitation
```

This verifier reads original files and writes only inside the manuscript project. It never imports ROS nodes, runs launch/service commands, trains or loads a policy, or writes into the research repository. The original E3 analyzer was inspected before use: its report-writing entry point is not executed. Only its five pure array/registration functions are extracted verbatim, with the original script hash recorded in `scripts/e3_segmentation_frozen.py`. Recomputed masks are written under `provenance/results_20261108/recomputed_masks/`.

The frozen E3 pair manifest contains original absolute paths and hashes. If the research archive is moved, remap a copy of that manifest under a separate analysis output directory while retaining the original hashes and recording the mapping. Never edit the frozen manifest or silently select files by basename.

## Exact source mapping

| Evidence | Research-relative location | Verification performed |
|---|---|---|
| Original E1 nominal report / membership / precision | `results/20261015/E1_report_20261015_nominal_pass_height_v2.pdf`; `reports/20261015_E1_nominal_pass_height_v2_pdf_report/` | Frozen 15 IDs and saved configs; precision CSV rows matched. Original C5 retained. |
| Additional R* five runs | `results/20261019/E1_report_20261019_R_dataset_mean_feed_5runs.pdf`; `reports/20261019_E1_R_dataset_mean_feed_pdf_report/` | Five original IDs, unrounded CSV, two configuration IDs, input manifest, and common frozen template SHA-256. |
| R* template | `experiments/E1_R_dataset_mean_feed_20261019/templates/rule_dataset_mean_feed.npz` | SHA-256 `1616a9f1bbb68df6a5178d994ffd48e239958cdef8f139b4925f85d873c20083`. |
| E1 preparation manifest | `reports/E1_contact_task_pass_height_v2/baseline_manifest.json` | Read as preparation/version history; completed frozen run evidence takes precedence over earlier unstarted fields. |
| E2 original results | `results/20261013/E2_report_20261013.pdf`; `reports/20261013_E2_pdf_report/metrics_per_run.csv` | All 15 precision rows matched; A4 original events reopened; field correction preserved. |
| E3 image outcome | `reports/20261023_E3_image_removal_report/` | 39-page report, pair manifests, config, annotations, occlusion CSV, 50 original RGB hashes, 75 stored arrays, 25 initial/19 evaluable final areas. |
| E3 execution and selection | `results/20261023/E3_report_20261023.pdf`; `reports/20261023_E3_pdf_report/` | 25-page report, frozen selected IDs, per-run config/registration, C checkpoint and normalizer hashes, HOME/PTP/command-release distinctions. |

`provenance/results_20261108/source_inputs.json` records the 370 opened source files, sizes, and SHA-256 values. `source_validation.json` records 350 source checks. `e3_mask_comparison.csv` records all 75 pixel-identity comparisons. `e3_run_config_mapping.csv` preserves full-precision registration values, retry links, and timing settings. Additional targeted checks document C6 and eleven inherited photographic assets. The current claim map states the verification level for each result.

## Reproduction levels and fixed analysis choices

- E1/E2: source precision rows and frozen membership/config correspondence were checked. The original task evaluator was not rerun or changed. Previously documented force-axis, zero, gravity, and mounting audits were reused.
- R*: source precision replaces the former printed-value transcription. Original R and R* are never pooled; C6 never replaces C5.
- E3: original RGB → unchanged annotations/support/ROI → gray ≤45/255 → native masks/areas was recomputed. All 75 compared masks/ROIs are pixel-identical. The 19 evaluable pairs use identity registration; six occluded pairs retain null whole-stain values and visible residual diagnostics. This is computational reproduction, not independent relabeling or physical material-removal calibration.
- Gray-40/50 sensitivity aggregates are retained from the archived report, separately from the fresh primary-threshold reproduction. No threshold optimization, pixel-fragment deletion, sample substitution, or new success cutoff was introduced.
- The 3.5 s E3 replanning value is a configured plan-age threshold (120/30 − 0.5), not a measured inference-call interval. It is distinct from the 5 Hz callback timer and 125 Hz command publication.

## Recorded environment

| Component | Version |
|---|---|
| Python | 3.10.20 (main, Mar 11 2026, 17:46:40) [GCC 14.3.0] |
| NumPy / Matplotlib | 2.2.6 / 3.10.9 |
| OpenCV / Pillow | 4.10.0 / 12.2.0 |
| pdfLaTeX | pdfTeX 3.141592653-2.6-1.40.22 (TeX Live 2022/dev/Debian) |
| BibTeX | BibTeX 0.99d (TeX Live 2022/dev/Debian) |
| Poppler | pdftotext version 22.02.0 |

No packages were installed into or upgraded in the original Python/ROS/CUDA environment. Optional photograph checks opened four existing HDF5 image frames read-only. Original RGB, reports, logs, checkpoints, and frozen manifests remain separate from the document bundle. The ZIP contains neither an entire research repository/dataset nor checkpoint, video, experiment-log, or font binaries.
