#!/usr/bin/env python3
"""Export the manuscript's editable E2 TikZ diagram as PDF/SVG/PNG."""
from pathlib import Path
import shutil
import subprocess
import tempfile

P=Path(__file__).resolve().parents[1]
s=(P/'chapters/05_skill_learning.tex').read_text()
label=s.index('\\label{fig:e2_information_flow}')
a=s.rfind('\\begin{tikzpicture}',0,label)
b=s.index('\\end{tikzpicture}',a)+len('\\end{tikzpicture}')
main=(P/'ThesisMain.tex').read_text()
style_start=main.index('\\tikzset{')
style_end=main.index('\\newcommand{\\thesistitle}',style_start)
styles=main[style_start:style_end]
source=('\\documentclass[12pt,border=3pt]{standalone}\n\\usepackage{tikz}\n'
        '\\usetikzlibrary{arrows.meta,positioning,fit,calc,shapes.geometric}\n'
        +styles+'\\begin{document}\n'+s[a:b]+'\n\\end{document}\n')
target=P/'figures/e2_information_flow.tex'
target.write_text('% Generated from the editable manuscript diagram.\n'+source)
with tempfile.TemporaryDirectory(prefix='thesis-e2-diagram-') as d:
    work=Path(d);shutil.copy2(target,work/target.name)
    result=subprocess.run(['pdflatex','-halt-on-error','-interaction=nonstopmode',target.name],cwd=work,capture_output=True,text=True)
    if result.returncode:
        print(result.stdout[-5000:]);raise SystemExit(result.returncode)
    shutil.copy2(work/'e2_information_flow.pdf',P/'figures/e2_information_flow.pdf')
subprocess.run(['pdftocairo','-svg',str(P/'figures/e2_information_flow.pdf'),str(P/'figures/e2_information_flow.svg')],check=True)
subprocess.run(['pdftoppm','-scale-to','1800','-singlefile','-png',str(P/'figures/e2_information_flow.pdf'),str(P/'figures/e2_information_flow')],check=True)
print('Exported manuscript E2 diagram to editable TeX and PDF/SVG/PNG.')
