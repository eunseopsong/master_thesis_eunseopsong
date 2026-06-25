@echo off
pdflatex -interaction=nonstopmode ThesisMain.tex
if errorlevel 1 exit /b 1
bibtex ThesisMain
if errorlevel 1 exit /b 1
pdflatex -interaction=nonstopmode ThesisMain.tex
if errorlevel 1 exit /b 1
pdflatex -interaction=nonstopmode ThesisMain.tex
if errorlevel 1 exit /b 1
pdflatex -interaction=nonstopmode ThesisCover.tex
