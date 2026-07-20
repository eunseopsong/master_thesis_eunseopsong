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
3. FAIRE Overview and Problem Formulation
4. VR-Calibrated Motion--Force Demonstration Collection
5. Force-History Imitation and Admittance Execution
6. Residual Reinforcement Learning for Precision Correction
7. Experimental Evaluation
8. Conclusions and Future Work

The thesis content is derived from the FAIRE review manuscript. Missing
implementation details and quantitative results remain explicitly marked as
planned or TBD.

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
