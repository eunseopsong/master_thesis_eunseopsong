#!/usr/bin/env bash
# Build ThesisMain.pdf (thesis) and ThesisCover.pdf (cover and spine for binding).
set -euo pipefail
cd -- "$(dirname -- "$0")"
# User-space TeX Live, if present.
[ -d "$HOME/texlive/bin/x86_64-linux" ] && PATH="$HOME/texlive/bin/x86_64-linux:$PATH"
mkdir -p build
run() { pdflatex -halt-on-error -interaction=nonstopmode "$1" > "build/$2.log" || { tail -n 40 "build/$2.log"; exit 1; }; }
run ThesisMain.tex main_pass1
bibtex ThesisMain > build/bibtex.log || { cat build/bibtex.log; exit 1; }
run ThesisMain.tex main_pass2
run ThesisMain.tex main_pass3
run ThesisMain.tex main_pass4
run ThesisCover.tex cover
echo "Built ThesisMain.pdf ($(pdfinfo ThesisMain.pdf | awk '/^Pages/{print $2}') pages) and ThesisCover.pdf"
grep -E "undefined|multiply defined|Overfull" ThesisMain.log | sort | uniq -c || true
