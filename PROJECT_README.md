# FAIRE Thesis LaTeX Project

This project uses the Sungkyunkwan University thesis template and is organized by chapter.

## Main files
- `ThesisMain.tex`: complete thesis document
- `ThesisCover.tex`: separate cover document
- `Bibliography/ThesisRef.bib`: BibTeX database
- `abstract_eng.tex`: English abstract
- `abstract_kr.tex`: Korean summary

## Chapter structure
1. Introduction
2. Related Work
3. Problem Formulation and FAIRE Overview
4. VR-Calibrated Motion--Force Demonstration Collection
5. Force-Aware Expert Imitation for Selective Defect Removal
6. Execution-Derived Material-Removal Estimation
7. CAD-Free Model-Based Blending with Residual RL
8. Experimental Evaluation
9. Conclusions and Future Work

Chapter sources are stored in the correspondingly numbered directories
(`1.Introduction` through `9.Conclusions`).

The working title is “FAIRE: Force-Aware Imitation with
Residual-Removal-Aware Blending for CAD-Free Robotic Surface Repair.”
Missing implementation details and quantitative results remain explicitly
marked as planned or TBD.

## Page layout
The thesis body uses equal top and bottom margins of 25 mm. Chapter headings start at the top of the text area rather than using the default `book`-class 50 pt vertical offset.

## Build on Ubuntu
```bash
chmod +x build.sh
./build.sh
```

The generated files are:
- `ThesisMain.pdf`
- `ThesisCover.pdf`

See `UBUNTU_GITHUB_CODEX_SETUP.md` for GitHub and Codex setup.
