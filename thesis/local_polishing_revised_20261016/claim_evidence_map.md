# 최종 주장과 표·그림·근거

| 최종 주장 | 원고 근거 | 직접 자료와 경계 |
|---|---|---|
| 인간 영역 지정과 시간 대응 동작–힘 교시를 연결한다. | 3–5장, 교시·좌표·정책 구조도 | 기존 검증된 source/dataset/model provenance 재사용. 새 알고리즘 우위 주장 아님. |
| 관측 조건부 Flow가 생성한 스킬을 공통 실행·기존 접촉 제어로 실행한다. | 6장, 7장 E1 결과·전체 힘/경로 | 10/15 원 C1–C5 포함15회. pass_height_ref_v2/received_observations_v2. |
| 고정 NOMINAL에서 R/T/C 모두 이번5회 절차 완료. | `tab:e1_primary`, `fig:e1_primary_metrics`, `tab:e1_all` | 원 보고서 input_manifest의15 run_id와 계획 슬롯. 일반 성공률100%·성능 동등성을 뜻하지 않음. |
| T의 평균 시간·시간SD는 C보다 작고, C의 평균 J_excess는 더 큼. | 같은 표·그림, `fig:e1_force_all` | `data/e1_summary.csv`; 원 실제 수신 기록에서 기존 적분 재현. Q95는 경험적 분석 기준. |
| 원 C5를 유지하며 C6는 별도 추가 진단. | `tab:e1_c5_c6`, `fig:e1_c5_c6` | 두 run의 원 outcome·수신 시계열. `data/cohort_manifest`에서 primary/diagnostic 분리. 모델 개선·원인 해결 주장 없음. |
| E2 A4는 이탈 전환 미완료·작업자 중단; A 완료4/5. | `tab:e2_times`, `tab:e2_all`, `fig:e2_transition_cases` | 사용자 현장 확인을 `data/e2_operator_correction.json`에 기록. 원 operator_finish/normal_completion 변경 없음. |
| A 완료시간은 n4, 전체시도 구간·힘·거리는 n5. | `tab:e2_times`, `tab:e2_force_travel`, `fig:e2_primary_metrics` | `data/e2_runs_corrected.csv`, `data/e2_summary_corrected.csv`. A4 성공시간 null. |
| C의 B 대비 평균 작업자 기준 시간은 약2.98초·15.8% 짧음. | `eq:bc_time_difference`, `tab:e2_times`, 초록·8·9장 | `data/results_summary.json`, 비율=(mean_B−mean_C)/mean_B×100. 기술통계이며 생산성·동일 제거량·단일 입력의 인과 효과 아님. |
| A→B→C의 모든 지표가 단조 개선되지는 않음. | `tab:e2_times`, `tab:e2_force_travel`, 8장 | C peak 평균≥A, C 시간SD≥B. 단일 학습 seed, 소표본, E2의 A→B→C 순서와 작업자 종료 한계. |
| 평가 범위는 고정 NOMINAL 접촉 절차. | RQ1/RQ2, 8장 범위, 9장 | LOW/HIGH·참조오프셋·일반화·품질·force tracking은 평가 성과로 주장하지 않음. 추가 시험이 원고 완성 조건은 아님. |
| 과거 E1과 높이 재생은 개발 이력. | 부록 B의 역사 표·그림 | 10/14 원3/5·4/5·5/5 및 같은 로그의 높이-only5/5. 주표본과 합산하지 않음. |

`data/results_summary.json`은 새 표·본문 수치의 공통 집계다. `provenance/results_20261016/analysis_scope.json`은 재계산과 기존 검증 인용을 구분하며, `source_files.json`은 이번에 실제 읽은 원 파일의 경로·hash를 기록한다.
