#!/usr/bin/env python3
"""Render every final PDF page and readable selected pages for visual review."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from PIL import Image,ImageDraw

P=Path(__file__).resolve().parents[1]
pdf_hash=hashlib.sha256((P/'ThesisMain.pdf').read_bytes()).hexdigest()
directory='review/final_'+pdf_hash[:12]
R=P/directory; R.mkdir(exist_ok=True)
subprocess.run(['pdftoppm','-scale-to','500','-png',str(P/'ThesisMain.pdf'),str(R/'page')],check=True)
files=sorted(R.glob('page-*.png'))
for batch in range((len(files)+15)//16):
    canvas=Image.new('RGB',(1360,2000),'#dedede');draw=ImageDraw.Draw(canvas)
    for i,f in enumerate(files[batch*16:(batch+1)*16]):
        im=Image.open(f);im.thumbnail((328,465));x=(i%4)*340+6;y=(i//4)*500+26
        canvas.paste(im,(x,y));draw.text((x,y-18),'PDF '+str(int(f.stem.split('-')[-1])),fill='black')
    canvas.save(R/f'contact_{batch+1}.jpg',quality=85)
pages=(P/'review/pdf_text.txt').read_text().split('\f')
selected={}
for tag in ['Figure 3.2:','Figure 5.1:','Figure 6.1:','Figure 7.5:','Figure 7.9:',
            'Table C.1:','Table C.2:']:
    n=next(i+1 for i,page in enumerate(pages) if tag in page)
    selected[tag]=n
for n in sorted(set(selected.values())|{1,len(files)-1,len(files)}):
    subprocess.run(['pdftoppm','-f',str(n),'-l',str(n),'-scale-to','1400','-singlefile','-png',
                    str(P/'ThesisMain.pdf'),str(R/f'detail_{n:03d}')],check=True)
(P/'review/render_index.json').write_text(json.dumps({'pages':len(files),'selected':selected,
                                                     'directory':directory,'pdf_sha256':pdf_hash},indent=2)+'\n')
print(json.dumps({'pages_rendered':len(files),'selected':selected}))
