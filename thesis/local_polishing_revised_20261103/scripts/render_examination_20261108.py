#!/usr/bin/env python3
"""Render every current PDF page and build numbered contact sheets for review."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import subprocess
from PIL import Image, ImageDraw, ImageFont

P=Path(__file__).resolve().parents[1]
OUT=P/'review/20261108/visual'


def main():
    global OUT
    pdf=P/'ThesisMain.pdf'
    # Separate render generations so shorter builds never inherit stale pages.
    OUT=OUT/hashlib.sha256(pdf.read_bytes()).hexdigest()[:12]
    OUT.mkdir(parents=True,exist_ok=True)
    pages=OUT/'pages';pages.mkdir(exist_ok=True)
    subprocess.run(['pdftoppm','-r','95','-png',str(pdf),str(pages/'page')],check=True)
    files=sorted(pages.glob('page-*.png'))
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
    sheets=[]
    for first in range(0,len(files),12):
        canvas=Image.new('RGB',(1280,1450),'#cbd0d5');d=ImageDraw.Draw(canvas)
        for j,f in enumerate(files[first:first+12]):
            im=Image.open(f).convert('RGB');im.thumbnail((300,425))
            x=15+(j%4)*320;y=30+(j//4)*480
            canvas.paste(im,(x+(300-im.width)//2,y))
            d.text((x+100,y+435),f'PDF {first+j+1:03d}',font=font,fill='black')
        path=OUT/f'contact_{first+1:03d}_{min(first+12,len(files)):03d}.png'
        canvas.save(path);sheets.append(path.name)
    # Cover and a grayscale copy of all primary result/photographic pages.
    subprocess.run(['pdftoppm','-singlefile','-r','135','-png',str(P/'ThesisCover.pdf'),str(OUT/'cover')],check=True)
    text=subprocess.check_output(['pdftotext','-layout',str(pdf),'-'],text=True).split('\f')
    focus=[]
    for i,t in enumerate(text):
        if i>=len(files):continue
        if (i<3 or 'Table 7.' in t or 'Figure 7.' in t or 'Table D.' in t or 'Figure D.' in t
            or ('Abstract' in t and 'Local surface rework' in t) or '국문요약' in t and 'Cartesian' in t):
            focus.append(i+1)
    for n in focus:
        subprocess.run(['pdftoppm','-f',str(n),'-l',str(n),'-singlefile','-r','145','-png',
            str(pdf),str(OUT/f'focus_{n:03d}')],check=True)
        im=Image.open(OUT/f'focus_{n:03d}.png')
        if 'Figure 7.' in text[n-1] or 'Figure D.' in text[n-1]:
            im.convert('L').save(OUT/f'gray_{n:03d}.png')
    index=dict(pdf_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),page_count=len(files),output_directory=str(OUT.relative_to(P)),
        all_page_resolution_dpi=95,focused_resolution_dpi=145,focused_pdf_pages=focus,
        contact_sheets=sheets,rendered_pages=[str(f.relative_to(P)) for f in files],
        review_status='rendered; human-model visual observations recorded separately after inspection')
    (OUT/'render_index.json').write_text(json.dumps(index,indent=2)+'\n')
    (OUT.parent/'current_render_index.json').write_text(json.dumps(index,indent=2)+'\n')
    print(json.dumps({k:index[k] for k in ['pdf_sha256','page_count','focused_pdf_pages','contact_sheets']}))


if __name__=='__main__':main()
