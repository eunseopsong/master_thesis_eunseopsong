# Local Robotic Polishing — Examination Manuscript

**Human-Guided Local Robotic Polishing via Joint Motion–Force Representation and Force-Conditioned Imitation Learning**

Eunseop Song (송은섭), Department of Intelligent Robotics, Sungkyunkwan University.

Scheduled submission: **18 November 2026**. Scheduled examination: **25 November 2026**. Expected degree award: **February 2027**. The formal claim month is **October 2026**, following the university form dated 16 October 2026.

## Build

```bash
bash build.sh
```

Outputs: `ThesisMain.pdf` and `ThesisCover.pdf`. The source bundle builds with pdfLaTeX, KoTeX, BibTeX, standard TeX Live packages, and Poppler. ROS, CUDA, a robot connection, training data, and checkpoints are unnecessary for document construction. No font binaries are distributed.

## Numerical and figure regeneration

```bash
python3 scripts/update_results_20261108.py
python3 scripts/prepare_e3_assets_20261108.py
bash build.sh
python3 scripts/validate_examination_20261108.py
```

These commands use the compact numerical inputs and selected original figure assets included in the source package. The full E3 RGB-level reproduction is a separate, read-only operation against the research archive; see `REPRODUCIBILITY_20261108.md`.

- `data/results_summary_20261108.json`: current numerical authority; unrounded values retained.
- `data/results_precision_20261108.csv`: precision aggregates.
- `results_manifest_20261108.csv`: 61 original/additional/archive run records.
- `thesis_metadata.tex`: confirmed identity, committee, and scheduled dates.
- `CHANGELOG_20261108.md`: actual revisions from the 119-page review manuscript.
- `FINAL_CHECKLIST_20261108.md`: content, format, build, visual, and package verification.
- `claim_evidence_map_20261108.md`: claim-to-source mapping.

The manuscript preserves original E1 R/T/C and C5; R* is a separate five-run additional diagnostic and C6 is diagnostic only. E2 retains A4's interrupted attempt with null completion time. E3 keeps archive25/main20/image19, including P2's exclusion and D1-4's occlusion. Mean ± SD denotes run-level arithmetic mean and sample SD.

The examination PDF and deliverables are in `submission_20261108/` in the working project. Historical projects and the local preservation backup are outside the submission source bundle.
