#!/usr/bin/env bash
set -euo pipefail
pdflatex -interaction=nonstopmode ThesisMain.tex
if command -v bibtex >/dev/null 2>&1 && bibtex --version >/dev/null 2>&1; then
  bibtex ThesisMain
elif command -v bibtex.original >/dev/null 2>&1; then
  bibtex.original ThesisMain
else
  echo "BibTeX was not found. Install a TeX distribution with BibTeX." >&2
  exit 1
fi
pdflatex -interaction=nonstopmode ThesisMain.tex
pdflatex -interaction=nonstopmode ThesisMain.tex
pdflatex -interaction=nonstopmode ThesisCover.tex
