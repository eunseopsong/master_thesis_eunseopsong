# 2026-10-16 E1/E2 최종 범위 반영 검토본

기준 원고는 `../local_polishing_revised_20261015/`의 98쪽 수정본이다. 원고·PDF·ZIP을 보존하고 이 별도 프로젝트에서 결과 의존 부분만 수정했다. 사용자 승인 전 검토본이며 모듈을 자동 FIXED로 지정하지 않았다. 현 프로젝트·상위 지침 및 발견 가능한 파일 목록에서 별도 module_status/승인 레지스트리는 확인되지 않았다.

## 수정 범위

| 위치 | 변경과 이유 |
|---|---|
| 영문 Abstract·국문요약 | 10/15 E1 주15회와 10/13 E2 정정 결과로 교체. 미실행 NOMINAL·필수 높이 시험 표현 제거. |
| 1장 RQ·기여·범위 | 고정 인간 지정 작업의 완료·시간·힘 사용 비교와 힘 구성별 실행 차이로 RQ를 확정했다. 배경 전체는 유지했다. |
| 6장 완료·관측·시계 | 실제 pass_height_ref_v2, received_observations_v2, 첫 성공 통과의 시간가중 Z 기준과 OFF·상승0.2초를 주 방법으로 설명한다. E1 실제 수신 약125Hz와 E2 CSV 약18Hz를 분리했다. |
| 7장 E1 | 원 계획 슬롯15회로 교체. 각 방법5/5, 완료시간과 J_excess, 전체 힘·경로·사진을 갱신했다. 원 C5 포함, 후속 C6는 별도 표·패널에 둔다. |
| 7장 E2 | A4 완료시간 null, A 완료4/5·시간 n4, 전체시도 n5를 유지했다. B–C 약2.98초·15.8%를 작업자 기준 시간의 기술통계로 명시했다. 유효한 E2 실측 그림은 재사용했다. |
| 8·9장 | T의 강한 NOMINAL 기준선, C의 실행 가능성, E2 B–C 시간 차이와 A4를 연결했다. 추가 실험을 원고 완료의 조건으로 두지 않았다. |
| 부록 | 10/14 E1 원 평가와 높이-only replay를 역사적 자료로 이동했다. 주30회+추가진단1회의 provenance와 A4 정정을 정리했다. |

## 유지한 부분

- 제목·표지·학생/학교/학위 관련 메타데이터, class/style/bst와 동일 상하 여백.
- 2장 관련 연구 및 3–5장 문제 정의·장치·좌표·동작–힘 데이터·Flow 학습 설명은 바이트 단위로 유지한다.
- 얼룩 중심·방향 정렬 구현, native 학습 힘/온라인 힘/평가 힘의 규약, 3축 예측과 실제 성분 선택, 학습 history와 callback 이력의 시간 의미를 유지한다.
- 기존 교시·정책·실행 구조도, 교시 그래프, E2 실측 그래프·영상 프레임, 확인된 확장 상태를 재사용한다.
- 앞서 제시한 추가 후보 1–12번은 이번 결과 갱신의 승인으로 간주하지 않고 추가하지 않았다.

## 표본과 자료 충돌 처리

- E1: `E1_CT_pass_height_v2_nominal_dev_20261015`, `e1ct_46de718a23a2a7cf`, 원 보고서의 계획 슬롯과15 run_id를 사용했다.
- C5: `E1_CT_NOMINAL_C_r5_20261015T230120_b45d2f021b`는 주5회에 남긴다.
- C6: `E1_CT_NOMINAL_C_r5_20261015T233551_9021584d0a`는 원 repeat_index=5·retry_of를 보존하고 표시명만 C6로 둔다. 주 비교 종료 뒤 추가된 실행이며 원 C5를 대체하지 않는다.
- 보고서 고정 목록은15개, 이후 session attempts는16개다. 최신 repeat_index만 고르는 방식은 사용하지 않았다.
- baseline_manifest의 준비 시점 not_run/zero-attempt 문구는 실제 실행 보고서·원 기록보다 우선하지 않는다. 원 파일은 변경하지 않았다.
- E2 원 보고서의 전체 완료 해석은 A4에 한해 현장 정정으로 대체한다. 원 종료 이벤트·28.750087346초는 유지한다.

## 재계산과 기존 검증의 재사용

- 재계산: E1 주15회와 C6의 기존 J_excess·초과시간·관측 peak를 원 수신 이벤트에서 확인하고, 주15회 평균·표본SD를 집계했다. E2 원 per-run 정밀값으로 A4 정정 통계와 B–C 차이를 재집계했다. 원 start/stop 이벤트도 대조했다.
- 재사용: 힘 대응 감사 v2, E1 완료 상태기계·Z 중앙값·온라인/오프라인 일치 및 저장 검증, E2 기존 native 힘·경로 검산. 교정·전체 파일 감사·모델 로딩을 반복하지 않았다.
- 출력: `data/results_summary.json`, `data/cohort_manifest.csv/json`, `data/e1_receipt_recalculation.csv`, `data/e2_operator_correction.json`, `provenance/results_20261016/`.
- 표와 본문 숫자는 `scripts/make_tables.py`가 같은 정밀 집계에서 생성한다. 본문은 `tables/result_numbers.tex`를 참조한다.

## 재현 명령

```bash
cd /home/eunseop/master_thesis_eunseopsong/thesis/local_polishing_revised_20261016
# 원 로컬 기록에서 필요한 결과만 다시 읽는 선택 명령
python3 scripts/collect_results_20261016.py --repo /home/eunseop/nrs_imitation
# 동봉된 추출 자료에서 갱신한 표·그림을 재생성
python3 scripts/make_tables.py
python3 scripts/plot_results_20261016.py
bash build.sh
python3 scripts/validate_manuscript.py
python3 scripts/package_project.py
```

위 명령은 로봇·ROS·학습·시뮬레이션을 실행하지 않는다. 최종 빌드와 PDF 검토 결과는 `review/validation.json`, `review/visual_review.md`, `review/unresolved_warnings.md`에 기록한다.

부록 끝의 반복적인 소스 보존 안내는 작성 기록으로 모아 소수 문장만 별도 페이지에 남는 부분을 정리했다. 학습·실행·힘 대응·교정·제어기 근거와 새 주 E1의 실제 설정/동결 소스는 `provenance/`에 보존한다.
