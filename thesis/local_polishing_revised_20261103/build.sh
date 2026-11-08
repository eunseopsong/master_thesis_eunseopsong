#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
mkdir -p review
pdflatex -recorder -halt-on-error -interaction=nonstopmode ThesisMain.tex > review/latex_pass1.log
if command -v bibtex >/dev/null 2>&1 && bibtex --version >/dev/null 2>&1; then
  bibtex ThesisMain > review/bibtex.log
elif command -v bibtex.original >/dev/null 2>&1; then
  bibtex.original ThesisMain > review/bibtex.log
else
  echo 'BibTeX is unavailable.' >&2
  exit 1
fi
pdflatex -recorder -halt-on-error -interaction=nonstopmode ThesisMain.tex > review/latex_pass2.log
pdflatex -recorder -halt-on-error -interaction=nonstopmode ThesisMain.tex > review/latex_pass3.log
pdflatex -recorder -halt-on-error -interaction=nonstopmode ThesisCover.tex > review/cover_build.log
pdftotext -layout ThesisMain.pdf review/pdf_text.txt
{
  printf 'Main pass 1\n'
  cat review/latex_pass1.log
  printf '\nBibTeX\n'
  cat review/bibtex.log
  printf '\nMain pass 2\n'
  cat review/latex_pass2.log
  printf '\nMain pass 3\n'
  cat review/latex_pass3.log
  printf '\nCover\n'
  cat review/cover_build.log
} > review/full_build.log
echo 'Built ThesisMain.pdf and ThesisCover.pdf'
