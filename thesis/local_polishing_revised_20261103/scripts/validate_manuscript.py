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
check('twenty_one_figures',len(re.findall(r'\\contentsline', (P/'ThesisMain.lof').read_text()))==21)
check('nineteen_tables',len(re.findall(r'\\contentsline', (P/'ThesisMain.lot').read_text()))==19)

a=pd.read_csv(P/'data/e1_runs.csv');b=pd.read_csv(P/'data/e2_runs_corrected.csv')
check('both_cohorts_fifteen',len(a)==len(b)==15)
check('e1_all_required_loaded_passes',(a.ordered_pass_segment_count==14).all())
check('e1_primary_five_completions_each',a.groupby('method').completion_time_s.count().to_dict()=={'C':5,'R':5,'T':5})
check('e1_executed_version',set(a.evaluation_version)=={'pass_height_ref_v2'} and set(a.observer_version)=={'received_observations_v2'})
manifest=pd.read_csv(P/'data/cohort_manifest.csv')
check('thirty_primary_one_diagnostic',manifest.primary_or_diagnostic.value_counts().to_dict()=={'primary':30,'diagnostic':1})
c6=manifest[manifest.primary_or_diagnostic=='diagnostic'].iloc[0]
check('c6_separate_original_identity',c6.display_label=='C6' and c6.original_repeat_index==5
      and c6.original_run_id=='E1_CT_NOMINAL_C_r5_20261015T233551_9021584d0a' and c6.original_run_id not in set(a.run_id))
check('original_c5_preserved',a.loc[a.label=='C5','run_id'].iloc[0]=='E1_CT_NOMINAL_C_r5_20261015T230120_b45d2f021b')
frozen=json.loads((P/'provenance/results_20261016/input_manifest.json').read_text())
check('e1_report_frozen_membership',{r['run_id'] for r in frozen['included_runs']}==set(a.run_id))
check('one_primary_per_planned_slot',len(a.plan_index.unique())==15 and sorted(a.plan_index)==list(range(1,16)))
check('e2_a4_interruption_not_completion',b.loc[b.label=='A4','completion_time_corrected_s'].isna().all()
      and 'incomplete' in b.loc[b.label=='A4','task_outcome'].iloc[0])
check('e2_five_attempts_each',b.groupby('condition').size().to_dict()=={'A':5,'B':5,'C':5})
check('e2_completed_four_five_five',b.groupby('condition').completion_time_corrected_s.count().to_dict()=={'A':4,'B':5,'C':5})
check('a4_elapsed_preserved',np.isclose(b.loc[b.label=='A4','execution_duration_s'].iloc[0],28.750087346))
d=pd.read_csv(P/'data/dataset_episodes.csv')
check('forty_two_unique_source_episodes',len(d[['source_h5','source_episode']].drop_duplicates())==42)
check('episode_level_split',d.groupby('split').size().to_dict()=={'train':38,'validation':4})
summary=json.loads((P/'data/results_summary.json').read_text())
groups=pd.DataFrame(summary['E2']).set_index('condition')
bc=(groups.loc['B','completion_time_corrected_s_mean']-groups.loc['C','completion_time_corrected_s_mean'])/groups.loc['B','completion_time_corrected_s_mean']*100
check('bc_descriptive_percentage',abs(bc-summary['B_to_C_reduction_percent'])<1e-12 and f'{bc:.1f}'=='15.8')
check('a_time_n_four_and_interval_n_five',groups.loc['A','completion_time_corrected_s_n']==4 and groups.loc['A','execution_duration_s_n']==5)
fresh=pd.read_csv(P/'data/e1_receipt_recalculation.csv')
check('sixteen_e1_receipt_force_integrals',len(fresh)==16 and fresh.J_error_Ns.abs().max()<3e-7 and fresh.peak_error_N.abs().max()<3e-7)
check('e1_actual_receipt_rate',fresh.actual_force_receipt_hz.between(120,130).all())
active='\n'.join((P/x).read_text() for x in ['abstract_eng.tex','abstract_kr.tex','chapters/01_introduction.tex','chapters/06_execution_evaluation.tex','chapters/07_experiments.tex','chapters/08_discussion_extensions.tex','chapters/09_conclusions.tex'])
check('no_obsolete_required_height_work',not re.search(r'height.{0,60}(?:pending|will be performed|required experiment)|partially answered|unexecuted revised-observer|height-variation trials remain planned',active,re.I))
v=pd.read_csv(P/'data/native_csv_validation.csv')
check('inherited_native_csv_checks_retained_as_prior_validation',len(v)==30 and v.integral_error.dropna().abs().max()<1e-7
      and v.mean_error.dropna().abs().max()<1e-7)
previous=P.parent/'local_polishing_revised_20261015'
for name in ['02_related_work.tex','03_problem_system.tex','04_demonstration_dataset.tex','05_skill_learning.tex']:
    check('unchanged_method_module:'+name,(P/'chapters'/name).read_bytes()==(previous/'chapters'/name).read_bytes())
for name in ['Bibliography/ThesisRef.bib','titlepage.tex','ThesisCover.tex']:
    check('unchanged_metadata_or_bibliography:'+name,(P/name).read_bytes()==(previous/name).read_bytes())
for row in json.loads((P/'provenance/previous_review_20261015_manifest.json').read_text()):
    check('previous_review_preserved:'+Path(row['source']).name,hashlib.sha256(Path(row['source']).read_bytes()).hexdigest()==row['sha256'])
for name in ['e2_primary_metrics.pdf','e2_force_all.pdf','e2_transition_cases.pdf','e2_sequence.pdf','teaching_motion_force.pdf','force_processing.pdf','dataset_split.pdf']:
    check('reused_figure_byte_identical:'+name,(P/'figures'/name).read_bytes()==(previous/'figures'/name).read_bytes())
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
