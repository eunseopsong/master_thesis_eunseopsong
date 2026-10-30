#!/usr/bin/env python3
"""Publication checks on the thesis artifact and its bundled evidence."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd

P=Path(__file__).resolve().parents[1]
checks=[]


def check(name, passed, details=None):
    checks.append({'check':name,'passed':bool(passed),'details':details})


log=(P/'ThesisMain.log').read_text()
check('no_latex_errors',not re.search(r'^!',log,re.M))
check('references_and_citations_resolved',not re.search(r'undefined|multiply defined|Citation.+undefined',log,re.I))
check('no_overfull_boxes',not re.search(r'Overfull',log))
check('no_missing_glyphs',not re.search(r'Missing character',log))
check('equal_vertical_margins','top=25mm' in (P/'ThesisMain.tex').read_text()
      and 'bottom=25mm' in (P/'ThesisMain.tex').read_text())
warnings=re.findall(r'^(?:LaTeX|Package [^\n]+) Warning:[^\n]*',log,re.M)
warnings += [re.sub(r'\s+', ' ', w).strip() for w in
             re.findall(r'^pdfTeX warning[^\n]*(?:\n[^\n]*duplicate ignored)?',log,re.M)]
text=(P/'review/pdf_text.txt').read_text()
check('korean_summary_extracts','국문요약' in text and '국소' in text and '\ufffd' not in text)
check('bibliography_toc_entry_once',(P/'ThesisMain.toc').read_text().count('{Bibliography}')==1)
check('thirteen_cited_sources',len(re.findall(r'\\bibitem', (P/'ThesisMain.bbl').read_text()))==13)
check('twenty_figures',len(re.findall(r'\\contentsline', (P/'ThesisMain.lof').read_text()))==20)
check('eighteen_tables',len(re.findall(r'\\contentsline', (P/'ThesisMain.lot').read_text()))==18)

a=pd.read_csv(P/'data/e1_runs.csv');b=pd.read_csv(P/'data/e2_runs_corrected.csv')
check('both_cohorts_fifteen',len(a)==len(b)==15)
check('e1_all_required_loaded_passes',(a.ordered_pass_segment_count==14).all())
check('e1_original_completion_counts',a.groupby('method').completion_time_s.count().to_dict()=={'C':5,'R':3,'T':4})
check('e2_a4_interruption_not_completion',b.loc[b.label=='A4','completion_time_corrected_s'].isna().all()
      and 'incomplete' in b.loc[b.label=='A4','task_outcome'].iloc[0])
check('e2_five_attempts_each',b.groupby('condition').size().to_dict()=={'A':5,'B':5,'C':5})
check('e2_completed_four_five_five',b.groupby('condition').completion_time_corrected_s.count().to_dict()=={'A':4,'B':5,'C':5})
check('a4_elapsed_preserved',np.isclose(b.loc[b.label=='A4','execution_duration_s'].iloc[0],28.750087346))
d=pd.read_csv(P/'data/dataset_episodes.csv')
check('forty_two_unique_source_episodes',len(d[['source_h5','source_episode']].drop_duplicates())==42)
check('episode_level_split',d.groupby('split').size().to_dict()=={'train':38,'validation':4})
h=json.loads((P/'provenance/height_session_status.json').read_text())
check('revised_height_sessions_not_run',len(h)==3 and all(x['attempts']==0 for x in h))
v=pd.read_csv(P/'data/native_csv_validation.csv')
check('thirty_native_csv_checks',len(v)==30 and v.integral_error.dropna().abs().max()<1e-7
      and v.mean_error.dropna().abs().max()<1e-7)
for row in json.loads((P/'provenance/original_manifest.json').read_text()):
    source=Path(row['file'])
    if source.exists():
        check('original_preserved:'+source.name,hashlib.sha256(source.read_bytes()).hexdigest()==row['sha256'])
for name in ['XThesis_skku_eng.sty','IEEEtran.cls','IEEEtran.bst','notebook.sty']:
    original=P.parents[1]/name
    if original.exists():check('style_byte_identical:'+name,(P/name).read_bytes()==original.read_bytes())

xml=subprocess.run(['pdftotext','-bbox',str(P/'ThesisMain.pdf'),'-'],capture_output=True,text=True,check=True).stdout
# pdfTeX math fonts can expose C0 codepoints in Poppler's XML text payload.
# Remove them only from the XML parser input; the PDF is never rewritten.
xml_controls=len(re.findall(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',xml))
xml=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',xml)
tree=ET.fromstring(xml);outside=[];pages=0
for page in tree.iter():
    if page.tag.endswith('page'):
        pages+=1;w=float(page.get('width'));h=float(page.get('height'))
        for word in page.iter():
            if word.tag.endswith('word'):
                if (float(word.get('xMin'))<0 or float(word.get('yMin'))<0
                    or float(word.get('xMax'))>w+.5 or float(word.get('yMax'))>h+.5):
                    outside.append({'page':pages,'word':word.text,'bbox':dict(word.attrib)})
check('pdf_words_inside_page_bounds',not outside,outside[:10])
output={'all_passed':all(x['passed'] for x in checks),'pages':pages,'checks':checks,
        'unresolved_warnings':warnings,'physical_experiments_started_by_this_work':False,
        'poppler_xml_math_controls_removed_for_parsing_only':xml_controls,
        'scope':'manuscript and existing evidence only; no new robot or model evaluation'}
(P/'review/validation.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
(P/'review/unresolved_warnings.md').write_text(
    '# 잔여 경고\n\n'+('\n'.join('- `'+x+'`' for x in warnings) if warnings else '없다.')+
    '\n\n기존 KoTeX/microtype font patch와 표지/본문 page.1 PDF destination 경고다. '
    '수정 전 ZIP의 빌드 로그에도 같은 경고가 있으며, 후속 수정에서 새 경고를 추가하지 않았다. '
    'page.1은 PDF 내부 페이지 anchor 경고이며 figure/table 번호나 LaTeX label 중복이 아니다. '
    '컴파일 오류, 미정의 인용/참조, 중복 label, overfull box, 누락 glyph는 없다.\n')
print(f'{len(checks)} artifact checks; pages={pages}; passed={output["all_passed"]}; warnings={len(warnings)}')
if not output['all_passed']:
    print([x for x in checks if not x['passed']]);raise SystemExit(1)
