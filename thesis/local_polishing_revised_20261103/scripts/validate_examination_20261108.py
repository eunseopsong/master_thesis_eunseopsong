#!/usr/bin/env python3
"""Check the current manuscript, run denominators, statistics, and preservation."""
from pathlib import Path
import csv
import hashlib
import json
import re
import statistics as st
import subprocess
import xml.etree.ElementTree as ET
import tarfile

P = Path(__file__).resolve().parents[1]
checks = []


def check(name, passed, detail=None):
    checks.append(dict(check=name, passed=bool(passed), detail=detail))


def csvrows(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    (P/'review/20261108').mkdir(parents=True,exist_ok=True)
    summary = json.loads((P/'data/results_summary_20261108.json').read_text())
    a, b, e3, manifest = [csvrows(P/name) for name in [
        'data/e1_runs.csv','data/e2_runs_corrected.csv','data/e3_source_area_runs.csv','results_manifest_20261108.csv']]
    check('E1 original planned15 identities',len(a)==15 and len({r['run_id'] for r in a})==15)
    check('E1 original C5 retained',next(r for r in a if r['label']=='C5')['run_id']=='E1_CT_NOMINAL_C_r5_20261015T230120_b45d2f021b')
    check('C6 excluded from original C',summary['C6']['run_id'] not in {r['run_id'] for r in a})
    frozen=json.loads((P/'provenance/results_20261108/manuscript_invariants.json').read_text())
    check('original E1 membership agrees with inherited frozen report',set(r['run_id'] for r in a)==set(frozen['e1_original_run_ids']))
    check('original E1 planned slots retained',sorted(int(r['plan_index']) for r in a)==list(range(1,16)))
    for c,t,sd,j,jsd in [('R',29.537,.075,0.,0.),('T',12.897,.041,.125,.254),('C',13.420,2.630,1.440,2.785),('Rstar',24.840,1.321,0.,0.)]:
        s=summary['E1'][c]
        check('E1 '+c+' published precision',tuple(f'{s[k][field]:.3f}' for k,field in [('time_s','mean'),('time_s','sd'),('J_excess_Ns','mean'),('J_excess_Ns','sd')])==tuple(f'{x:.3f}' for x in [t,sd,j,jsd]))
        check('E1 '+c+' five completed',s['attempted']==s['completed']==5)
    rs=[r for r in manifest if r['cohort']=='Rstar_additional_20261019']
    check('Rstar original IDs recovered',len(rs)==5 and len({r['run_id'] for r in rs})==5 and all(r['run_id'].startswith('E1_CT_NOMINAL_R_') for r in rs))
    check('Rstar feed is peak parameter',summary['E1_processing_peak_feed_mm_s']==14.940779233290927 and abs(summary['E1_source_processing_mean_mm_s']-7.968415591088494)<1e-12)
    a4=next(r for r in b if r['label']=='A4')
    check('A4 null completion and original interruption',a4['completion_time_corrected_s']=='' and float(a4['execution_duration_s'])==28.750087346 and 'incomplete' in a4['task_outcome'])
    for c,n,t,sd,peak,psd in [('A',4,17.65,1.20,31.02,1.46),('B',5,18.81,.40,32.42,.76),('C',5,15.83,.56,31.26,1.66)]:
        s=summary['E2'][c]
        check('E2 '+c+' completion/peak denominators',s['attempted']==5 and s['time_s']['n']==n and s['peak_Fz_N']['n']==5)
        check('E2 '+c+' corrected rounded results',[f'{s[k][f]:.2f}' for k,f in [('time_s','mean'),('time_s','sd'),('peak_Fz_N','mean'),('peak_Fz_N','sd')]]==[f'{x:.2f}' for x in [t,sd,peak,psd]])
    check('E2 B-C difference',f'{summary["E2_B_minus_C_s"]:.2f}'=='2.98' and f'{summary["E2_B_to_C_percent"]:.1f}'=='15.8')
    check('61 manifest rows',len(manifest)==61)
    check('E3 archive25/main20/image19',len(e3)==25 and sum(r['main_condition']=='True' for r in e3)==20 and sum(r['image_evaluable']=='True' for r in e3)==19)
    check('E3 25 distinct original IDs',len(set(r['run_id'] for r in e3))==25)
    for r in e3:
        if r['image_evaluable']=='True':
            v=100*(int(r['A_before_px'])-int(r['A_after_px']))/int(r['A_before_px'])
            check('E3 exact integer ratio '+r['display_label'],abs(v-float(r['removal_percent']))<1e-12)
        else:
            check('E3 null retained '+r['display_label'],r['A_after_px']==r['removal_percent']=='' and r['final_tool_occlusion']=='True')
    for c,n,mean,sd in [('N',5,100.,0.),('P1',5,97.55,2.49),('D1',4,98.12,3.75),('D2',5,93.67,6.60)]:
        vals=[float(r['removal_percent']) for r in e3 if r['condition']==c and r['image_evaluable']=='True']
        s=summary['E3'][c]['removal_percent']
        check('E3 '+c+' ddof1 statistics',len(vals)==n and abs(st.mean(vals)-s['mean'])<1e-12 and abs(st.stdev(vals)-s['sd'])<1e-12 and f'{s["mean"]:.2f}'==f'{mean:.2f}' and f'{s["sd"]:.2f}'==f'{sd:.2f}')
    check('P2 archive only all five occluded',all(r['main_condition']=='False' and r['image_evaluable']=='False' for r in e3 if r['condition']=='P2'))
    check('D1-4 main but image null and manual_abort',all(next(r for r in e3 if r['display_label']=='D1-4')[k]==v for k,v in [('main_condition','True'),('image_evaluable','False'),('original_stop_reason','manual_abort')]))
    check('D2-3 minimum not hidden',abs(float(next(r for r in e3 if r['display_label']=='D2-3')['removal_percent'])-83.87909319899245)<1e-12)
    native=json.loads((P/'provenance/results_20261108/e3_display_manifest.json').read_text())
    check('seven native display pairs match original hashes',len(native)==7 and all(
        digest(P/'figures/e3_native'/r['label']/'before.png')==r['before_sha256'] and
        digest(P/'figures/e3_native'/r['label']/'after.png')==r['after_sha256'] for r in native))
    src=json.loads((P/'provenance/results_20261108/source_validation.json').read_text())
    check('source verification passed',src['passed']==350 and src['failures']==0)
    masks=csvrows(P/'provenance/results_20261108/e3_mask_comparison.csv')
    check('75 reproduced arrays pixel-identical',len(masks)==75 and all(r['identical']=='True' and r['different_pixels']=='0' for r in masks))
    snapshot=P/'submission_20261108/preservation/manuscript_before_20261108.tar.gz'
    if snapshot.exists():
        with tarfile.open(snapshot) as t:
            prefix=P.name+'/'
            previous={x.name[len(prefix):]:t.extractfile(x).read() for x in t.getmembers()
                if x.isfile() and x.name.startswith(prefix) and x.name.endswith(('.tex','.sty','.bst','.bib','.cls'))}
        for name in ['Bibliography/ThesisRef.bib','XThesis_skku_eng.sty','IEEEtran.cls','IEEEtran.bst','notebook.sty']:
            check('protected file unchanged '+name,(P/name).read_bytes()==previous[name])
        inherited='\n'.join(v.decode() for k,v in previous.items() if k.startswith('chapters/') or k in ['ThesisMain.tex','abstract_eng.tex','abstract_kr.tex'])
    else:
        # Portable source package carries hash/label/equation invariants, not the backup.
        invariants=json.loads((P/'provenance/results_20261108/manuscript_invariants.json').read_text())
        for name,h in invariants['protected_sha256'].items():check('protected file unchanged '+name,digest(P/name)==h)
        inherited='' 
    main=(P/'ThesisMain.tex').read_text()
    check('equal official 38mm vertical and 30mm horizontal margins',all(x in main for x in ['top=38mm','bottom=38mm','left=30mm','right=30mm']))
    active=[P/'ThesisMain.tex',P/'abstract_eng.tex',P/'abstract_kr.tex']+list((P/'chapters').glob('*.tex'))
    active_text='\n'.join(p.read_text() for p in active)
    labels=lambda s:set(re.findall(r'\\label\{([^}]+)\}',s)+re.findall(r'\\figfull\{[^}]+\}\{[^\n]*\}\{([^}]+)\}',s))
    original_labels=labels(inherited) if inherited else set(invariants['original_labels'])
    check('original review labels preserved',original_labels<=labels(active_text),sorted(original_labels-labels(active_text)))
    equations=lambda text:{re.search(r'\\label\{([^}]+)\}',x).group(1):re.sub(r'\s+',' ',x).strip() for x in re.findall(r'\\begin\{equation\}(.*?)\\end\{equation\}',text,re.S) if re.search(r'\\label\{([^}]+)\}',x)}
    check('all original method equations unchanged',(equations(inherited) if inherited else invariants['original_equations'])==equations(active_text))
    check('no obsolete E3 planned/unexecuted claims',not re.search(r'E3.{0,80}(?:remains planned|not run|unexecuted|entirely untested)',active_text,re.I))
    check('no assertion removal entirely unmeasured',not re.search(r'(?:thesis|experiments).{0,80}(?:no removal (?:measurement|evaluation)|removal was not measured)',active_text,re.I))
    check('B target force explicitly retained','retains their force-action targets' in active_text and 'replaced by zeros' in active_text)
    check('current E3 table excludes P2','P2 &' not in (P/'tables/e3_main_results.tex').read_text())
    log=(P/'ThesisMain.log').read_text()
    coverlog=(P/'ThesisCover.log').read_text()
    check('full main and cover output PDFs exist',(P/'ThesisMain.pdf').stat().st_size>100_000 and (P/'ThesisCover.pdf').stat().st_size>10_000)
    check('no LaTeX errors',not re.search(r'^!|Fatal error',log+'\n'+coverlog,re.M))
    check('references and citations resolved',not re.search(r'undefined|multiply defined|Rerun to get cross-references',log,re.I))
    check('no overfull boxes','Overfull' not in log+coverlog)
    check('no missing glyph warnings','Missing character' not in log+coverlog)
    check('bibliography compiled',len(re.findall(r'\\bibitem',(P/'ThesisMain.bbl').read_text()))==13)
    text=(P/'review/pdf_text.txt').read_text()
    check('no manuscript placeholders or draft watermark',not re.search(r'\b(?:TODO|TBD|placeholder)\b|\?\?|Revised Draft|Author and submission information',text,re.I))
    check('no PC-specific absolute paths in PDF',not re.search(r'/home/|/mnt/data|/tmp/|on this PC|were not accessible',text,re.I))
    check('Korean summary extractable','국문요약' in text and '국소' in text and '\ufffd' not in text)
    check('PDF includes all three studies','Spatial Transfer of the Learned Skill' in text and 'Force-Information Ablation' in text and 'Strategy Comparison' in text)
    xml=subprocess.run(['pdftotext','-bbox',str(P/'ThesisMain.pdf'),'-'],capture_output=True,text=True,check=True).stdout
    xml=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',xml)
    outside=[];pages=0
    for page in ET.fromstring(xml).iter():
        if not page.tag.endswith('page'):continue
        pages+=1;w=float(page.get('width'));h=float(page.get('height'))
        for word in page.iter():
            if word.tag.endswith('word') and (float(word.get('xMin'))<0 or float(word.get('yMin'))<0 or float(word.get('xMax'))>w+.5 or float(word.get('yMax'))>h+.5):
                outside.append(dict(page=pages,text=word.text,box=word.attrib))
    check('PDF text inside physical page bounds',not outside,outside[:8])
    warnings=re.findall(r'^(?:LaTeX|Package [^\n]+) Warning:[^\n]*',log,re.M)
    warnings += [re.sub(r'\s+',' ',x) for x in re.findall(r'^pdfTeX warning[^\n]*(?:\n[^\n]*duplicate ignored)?',log,re.M)]
    report={'all_passed':all(c['passed'] for c in checks),'pages':pages,'checks':checks,'unresolved_warnings':warnings,
        'main_pdf_sha256':digest(P/'ThesisMain.pdf'),'figures':(P/'ThesisMain.lof').read_text().count('\\contentsline'),
        'tables':(P/'ThesisMain.lot').read_text().count('\\contentsline'),
        'source_limitations':['No new physical calibration, evaluator rerun, or independent semantic annotation validation; these are outside the manuscript claims'],
        'new_robot_experiments':False,'new_model_training_or_inference':False,'new_segmentation_or_thresholds':False,'raw_RGB_reproduction':True}
    (P/'review/20261108/validation_20261108.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (P/'review/20261108/unresolved_warnings_20261108.md').write_text('# 실제 잔여 빌드 경고\n\n'+ ('\n'.join('- `'+x+'`' for x in warnings) if warnings else '없음.')+'\n\n이 목록은 최종 main 로그에서 추출했다. 원자료 접근 및 형식 상태는 FINAL_CHECKLIST_20261108.md에 별도로 기록했다.\n')
    print(json.dumps({k:report[k] for k in ['all_passed','pages','figures','tables','unresolved_warnings']},ensure_ascii=False))
    if not report['all_passed']:
        print(json.dumps([c for c in checks if not c['passed']],ensure_ascii=False,indent=2))
        raise SystemExit(1)


if __name__=='__main__':main()
