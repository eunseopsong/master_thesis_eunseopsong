# 주장–근거 대응 — 2026-11-03

페이지는 각 원보고서의 실제 PDF 쪽수다. 원PDF는 `provenance/results_20261103/reports/`에 byte 동일 사본으로 보존했다. 이번에 직접 읽은 내용과 이전 검사 재사용, 사용자 확정기록을 구분한다.

| 주장/정의 | 원보고서·페이지 또는 확인자료 | 논문·출력 | 출처 수준/경계 |
|---|---|---|---|
| 원E1 R/T/C 각5/5, 29.537/12.897/13.420초, J0/.125/1.440 | E1_report_20261015_nominal_pass_height_v2.pdf pp.1–4; 기존 data/e1_runs.csv와provenance/results_20261016/input_manifest.json·trial_plan.json | 7장 원R별도표·최신T/C, 부록원15회; data/results_summary_20261103.json | 직접보고서대조와동봉정밀CSV재집계. 원세션재탐색아님. |
| 최신 R* 5/5,24.840±1.321초,J0±0;원R보존 | E1_report_20261019_R_dataset_mean_feed_5runs.pdf pp.1,5,17 | tab:e1_primary,tab:e1_r_retiming,fig:e1_primary_metrics | 확정요약소수3자리. 개별CSV는보고서인쇄값;원정밀도/run_id미확인. |
| R* feed와평균속도구분,42교시,phase전용retiming,+18N유지 | 같은추가R보고서pp.2–4,8–9 | 7장E1추가진단;metric_definitions.json | 직접PDF내용. input_manifest/template원파일재확인못함. |
| R* 최초1회후4회,별도날짜,원R대비4.697초15.9% | 같은보고서pp.1,5,17 | 1·7·8·9장·초록 | 기술비교. 같은날새무작위블록/원R합산아님. |
| E1 v2완료·관측·창·Q95 | 원E1보고서pp.2,7–8;추가Rpp.2,17;기존task_definition/evaluation·force_stats | 6장,부록A/B | 기준정의와기존검증재사용. 재보정/평가기재감사안함. |
| 원C5보존,C6별도 | 기존 data/e1_runs.csv,data/e1_c6_diagnostic.csv,provenance/results_20261016/current_session_attempts.json | 부록C,fig:e1_c5_c6 | 동봉기존정밀자료. 원C5 run suffix b45d2f021b; C6 suffix9021584d0a. |
| A/B/C observation과target,하위실제힘피드백 | E2_report_20261013.pdf p.2;기존 provenance/training_configs.json·선택학습snapshot/flow_core.py·dataset.py | 5장tab:e2_information_contracts·fig:e2_information_flow | 기존학습근거읽기/재사용. 모델재로딩·재학습없음. |
| A4접촉해제미완료·작업자중단,완료null | 사용자현재현장정정; data/e2_operator_correction.json,data/e2_runs_corrected.csv | 7장E2·부록C | 원E2보고서p.1의모든완료해석보다정정우선. 원operator_finish/normal_completion유지. |
| E2완료4/5,5/5,5/5;시간17.65±1.20,18.81±.40,15.83±.56 | E2보고서pp.1,3+ A4정정;동봉정밀e2_runs_corrected.csv | tab:e2_times,초록·논의·결론 | 완료시간n4/5/5. A전체5구간19.87±5.07은별도. |
| E2 peak31.02±1.46,32.42±.76,31.26±1.66 | E2보고서pp.1,3;같은정밀CSV | tab:e2_times,tab:e2_force_travel | 각시행peak의평균,각n5·A4포함. C<Apeak/시간SD<C가B보다작음주장없음. |
| B대비C시간2.98초15.8%짧음 | 같은CSV의별도학습모델집계 | 7장eq:bc_time_difference·초록·8·9장 | 작업자기준기술통계;같은제거량생산성/일반인과효과아님. |
| E3주평가N/P1/D1/D2,25archive/20main/19image | E3_image_removal_report_20261023.pdf pp.1,5–9,35,38+ 사용자P2제외결정 | 1·6·7장·초록·부록D,results_manifest | 직접보고서25개원run_id복원. 원selection_manifest직접읽지못함. |
| E3제거율100±0,97.55±2.49,98.12±3.75,93.67±6.60 | 같은영상보고서pp.1,5–9의정수면적 | data/e3_report_area_runs.csv,results_summary_20261103.json,tab:e3_main_results,fig:e3_removal_metrics | 정확정수영역에서시행비율재계산·ddof1. 이미지자체재분할아님. |
| D2-3=83.87909319899245% | 같은보고서p.9: before794px,after128px;사진p.32 | 주그림과부록20행표 | 최솟값보존;93.67은조건평균하한. |
| D1-4최종가림·manual_abort, P2전부최종가림 | 같은보고서pp.4,7–8,20–24,28,35 | 부록D,fig:e3_d1_occlusion/fig:e3_p2_occlusion | null유지. D1-4는main20에유지. 숨은면적추정없음. |
| 원본424×240,gray45+수동가시경계,6px ROI,원좌표19회 | 같은보고서pp.3–4,36,39 | 6장eq:e3_removal·부록D | 분석정의를인용·재사용. annotations/mask/rawRGB는PC에없어재검증하지않음. |
| 40/45/50동일주석민감도 | 같은보고서p.36 | tab:e3_sensitivity | 인쇄된집계재사용. 새threshold최적화없음. |
| 4조건고정1회차RGB/ROI/mask근거 | 같은보고서pp.10,15,25,30 | fig:e3_first_index_evidence;25panelmanifest | lossless embeddedpanel추출후동일표시crop;새원본경로/가림복원없음. |
| 실제등록N(0,0,0),P1(+29.55,+21.80,0),D1(-1.06,-1.36,+42.17),D2(-.75,-3.53,-31.03) | 사용자2026-11-03확정기록 | tab:e3_placements,fig:e3_registered_layout,data/e3_registered_placements.csv | run_context가없어원등록파일독립대조는미완료. 계획예시값을사용하지않음. |
| 동일C/normalizer,XY·영상정렬/XY역변환,fullSE(3)아님 | 사용자확정기록+기존방향어댑터source발췌·model_manifest | 3·5·7·8·9장 | 기존구현근거재사용. E3체크포인트hash직접대조없음. |
| 조건별HOME/PTP/commanded-release차이,선택·retry이력 | 영상보고서pp.37–38+사용자확정기록 | 6·7·8장·부록D | E3원25쪽실행보고서/개별config미대조명시. |
| v2완료8/25,observation_unavailable17/25는보조 | 영상보고서p.37 | 부록D만 | 원25회라벨. main20결과나잉크성공률로변환하지않음. |
| 잉크면적감소와금속표면품질별도 | 영상보고서pp.3,36;측정변수범위 | 1·6·7·8·9장·초록 | 깊이·질량·거칠기·미세스크래치독립계측없음. E3를E1/E2품질로소급안함. |

현재원고는확보된보고서와동봉정밀자료로작성한부분개정검토본이다. 원연구repo부재로생긴문서출처미확인은`open_items.md`에모았으며추가물리실험이나재학습을원고완성조건으로두지않았다.
