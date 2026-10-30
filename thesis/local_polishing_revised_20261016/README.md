# 국소 로봇 폴리싱 석사학위논문 검토본 — 2026-10-16

**Human-Guided Local Robotic Polishing via Joint Motion–Force Representation and Force-Conditioned Imitation Learning**

현재 검토본은 `ThesisMain.tex` / `ThesisMain.pdf`다. 이전 `../local_polishing_revised_20261015/`의 98쪽 초안과 ZIP을 보존하고, 최신 E1/E2와 직접 연결되는 부분만 수정했다. 최종 PDF는 99쪽, 그림 21개, 표 19개다. 사용자 승인 전 검토본이며 자동으로 FIXED 처리한 모듈은 없다.

## 확정된 분석 범위

- E1: 2026-10-15 NOMINAL 원 계획 R/T/C 각 5회, 총 15회. `pass_height_ref_v2`, `received_observations_v2`를 사용한 development 세션이다. 원 C5를 유지한다.
- E2: 2026-10-13 A/B/C 각 5시도, 총 15시도. A4는 사용자 현장 확인에 따라 미완료·중단으로 해석하며 완료시간은 null이다. 원 종료 이벤트는 보존한다.
- C6: E1 비교 종료 뒤 추가한 1회 진단이다. 원 repeat_index=5와 run_id를 보존하며 주 C 통계에 합치지 않는다.
- LOW/HIGH, 참조 Z 오프셋, 위치·방향·새 형상 일반화, 물리적 제거량·표면 품질은 이번 결과의 검증 범위에 포함하지 않는다. 방향 정렬과 확장 자산의 기존 구현 설명은 유지한다.

## 빌드와 도표 재생성

프로젝트 폴더에서 실행한다. 기존 학교 양식과 pdflatex/BibTeX 빌드 체인을 사용한다. 학교 style/class/bst와 표지 메타데이터를 변경하지 않았다.

```bash
python3 scripts/make_tables.py
python3 scripts/plot_results_20261016.py
bash build.sh
python3 scripts/validate_manuscript.py
python3 scripts/package_project.py
```

도표는 동봉한 논문용 CSV·프레임에서 다시 생성할 수 있다. 로컬 원자료를 다시 대조할 경우에만 다음 선택 명령을 사용한다.

```bash
python3 scripts/collect_results_20261016.py --repo /home/eunseop/nrs_imitation
```

선택 수집 명령은 기존 로그·보고서를 읽고 논문 출력만 갱신한다. 로봇·ROS·학습·시뮬레이션을 실행하지 않는다. 과거 `collect_evidence.py`, `plot_figures.py`는 이전 버전의 재현 이력으로 보존하며 이번 결과 갱신의 진입점으로 사용하지 않는다. 원본 레포 및 이전 초안 보존을 대조하는 검사는 해당 로컬 경로가 있는 환경에서 실행한다.

## 결과와 기록

- `data/results_summary.json`, `tables/result_numbers.tex`: 같은 정밀 집계에서 생성한 표·본문 수치.
- `data/cohort_manifest.csv/json`: E1 주15회·E2 주15시도·C6 진단의 run_id, 버전, 원 라벨, 포함 이유와 출처.
- `data/e2_operator_correction.json`: A4 현장 정정과 원 종료 기록의 구분.
- `data/e1_receipt_recalculation.csv`: E1 주15회와 C6의 기존 힘 지표 재계산 대조.
- `revision_summary.md`, `claim_evidence_map.md`, `evidence_map.md`, `figure_manifest.json`: 변경 범위와 주장·그림의 근거.
- `review/validation.json`, `review/visual_review.md`, `review/unresolved_warnings.md`: 전체 빌드·61개 산출물 검사와 시각 검토 기록.
- `open_items.md`: 남은 문서상 확인 사항. 추가 실험을 완료 조건으로 남기지 않는다.

ZIP은 상위 폴더에 `local_polishing_revised_20261016.zip`으로 생성한다. 편집 가능한 원고·서지·양식·그림·논문용 분석 출력·코드를 포함하며 폰트, 체크포인트, 전체 원 로그와 대용량 영상은 제외한다.
