# Hybrid Surface Finishing Thesis LaTeX Project

This project uses the Sungkyunkwan University thesis template and is organized by chapter.

## Main files
- `ThesisMain.tex`: complete thesis document
- `ThesisCover.tex`: separate cover document
- `Bibliography/ThesisRef.bib`: BibTeX database
- `abstract_eng.tex`: English abstract
- `abstract_kr.tex`: Korean summary

## Chapter structure
1. Introduction
2. System Overview and Problem Formulation
3. Tool-Footprint-Aware Full-Coverage Path Planning on CAD Surfaces
4. Reinforcement Learning for Adaptive Sliding-Velocity Optimization
5. Force-Aware Imitation Learning for Local Difficult Regions
6. Feature Masking for Object-Centric and Predictive Visual Representation
7. Experimental Design
8. Conclusions and Future Work

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
