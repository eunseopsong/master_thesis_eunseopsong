#!/usr/bin/env python3
"""Render complete PDF contact sheets and details of changed result/method pages."""
from pathlib import Path
import hashlib
import json
import subprocess
from PIL import Image, ImageDraw

P=Path(__file__).resolve().parents[1]
pdf=P/'ThesisMain.pdf'
h=hashlib.sha256(pdf.read_bytes()).hexdigest()
R=P/'review'/('render_'+h[:12]);R.mkdir(exist_ok=True)
subprocess.run(['pdftoppm','-scale-to','500','-png',str(pdf),str(R/'page')],check=True)
files=sorted(R.glob('page-*.png'))
for start in range(0,len(files),16):
    canvas=Image.new('RGB',(1360,2000),'#dedede');draw=ImageDraw.Draw(canvas)
    for j,f in enumerate(files[start:start+16]):
        im=Image.open(f);im.thumbnail((328,465));x=(j%4)*340+6;y=(j//4)*500+26
        canvas.paste(im,(x,y));draw.text((x,y-18),'PDF '+str(int(f.stem.split('-')[-1])),fill='black')
    canvas.save(R/f'contact_{start//16+1:02d}.jpg',quality=90)
pages=(P/'review/pdf_text.txt').read_text().split('\f')
tags=['Information contracts for three','Explanatory information-flow diagram','Latest E1 summary:',
      'Original R and separate additional','E2 results with A4','Main E3 conditions:',
      'Main E3 removal results','All 19 evaluable','First-index examples','All 20 main selected',
      'Unchanged report-embedded D1-4','Unchanged P2-1 report evidence','국문요약']
selected={}
for tag in tags:
    found=[i+1 for i,page in enumerate(pages) if tag in page]
    if found:selected[tag]=found[-1]
numbers=set(selected.values())|{1}
# Abstract, method table/diagram, E1--E3 main results and summaries in readable form.
for i,page in enumerate(pages):
    if any(t in page for t in ['Three evaluations examine','Chapter 7\n','Chapter 9\n']):numbers.add(i+1)
for n in sorted(numbers):
    subprocess.run(['pdftoppm','-f',str(n),'-l',str(n),'-scale-to','1600','-singlefile','-png',str(pdf),str(R/f'detail_{n:03d}')],check=True)
index=dict(pages=len(files),directory=str(R.relative_to(P)),pdf_sha256=h,selected=selected,detail_pages=sorted(numbers))
(P/'review/render_index_20261103.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(index,ensure_ascii=False))
