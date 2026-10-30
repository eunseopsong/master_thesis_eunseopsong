#!/usr/bin/env python3
"""Package editable manuscript and compact evidence; omit caches and large inputs."""
from pathlib import Path
import zipfile
import re
P=Path(__file__).resolve().parents[1]
destination=P.parent/(P.name+'.zip')
skip_suffixes={'.aux','.log','.out','.toc','.lof','.lot','.blg','.pyc','.otf','.ttf','.pfb',
               '.pt','.pth','.ckpt','.hdf5','.h5','.webm','.mp4','.avi'}
count=0
with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(P.rglob('*')):
        if not p.is_file():continue
        rel=p.relative_to(P)
        if any(x.startswith('.') or x=='__pycache__' for x in rel.parts):continue
        if p.suffix.lower() in skip_suffixes and rel.parts[0]!='review':continue
        if rel.parts[0]=='review' and (len(rel.parts)>1 and rel.parts[1].startswith('final') or p.suffix.lower() in {'.png','.jpg'}):continue
        if rel.parts[0]=='figures' and p.suffix=='.png' and p.with_suffix('.pdf').exists():continue
        z.write(p,Path(P.name)/rel);count+=1
with zipfile.ZipFile(destination) as z:
    assert z.testzip() is None
    for required in ['ThesisMain.tex','ThesisMain.pdf','ThesisCover.pdf','Bibliography/ThesisRef.bib',
                     'old_to_new_map.md','evidence_map.md','figure_manifest.json','open_items.md']:
        assert P.name+'/'+required in z.namelist()
    # Check every directly used local figure and chapter/table input.
    active=[P/'ThesisMain.tex',P/'ThesisCover.tex',P/'abstract_eng.tex',P/'abstract_kr.tex',P/'titlepage.tex']+list((P/'chapters').glob('*.tex'))
    for f in active:
        s=f.read_text()
        used=re.findall(r'\\(?:input|include)\{([^}#]+)\}',s)
        figures=re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}#]+)\}',s)
        figures+=['figures/'+x for x in re.findall(r'\\figfull\{([^}]+)\}',s)]
        for name in used+figures:
            path=name if Path(name).suffix else name+'.tex'
            assert P.name+'/'+path in z.namelist(),path
print(f'{destination}\n{count} files; {destination.stat().st_size/1024/1024:.2f} MiB; ZIP integrity passed')
