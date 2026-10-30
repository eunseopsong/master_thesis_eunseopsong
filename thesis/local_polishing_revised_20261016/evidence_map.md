# 근거 대응표

경로의 기준은 `/home/eunseop/nrs_imitation/`이다. 장별 source 상세·hash·run 목록은 `provenance/`와 `data/`에 보존한다.

| 본문 주장/값 | 직접 근거 | 본문 |
|---|---|---|
| 원 학교 양식·동일 상하 25 mm 여백 | 원본 ThesisMain.tex, XThesis_skku_eng.sty, build.sh | 전체 |
| 교시 pose mm/rotvec rad·3축 force·RGB 동기화 | `behavior_ws/src/nrs_imitation/nrs_imitation/hdf5_recorder_base.py`; 실제 source merged HDF5 attrs/sync | 4장 |
| VR 등록·tracker/tool offset | `behavior_ws/src/vive_tracker_ros2/vive_tracker_ros2/vive_tracker_node.py`; `behavior_ws/src/vr_calibration/` | 4장 |
| 얼룩 중심 상대위치 학습 | `behavior_ws/src/stain_relative_frame/stain_relative_frame/relative_frame.py`의 `to_relative/to_absolute`; `dataset_relativize.py`의 `convert_episode`; `scripts/flow/run_90deg_rel_single_20260910.sh` | 1·3·4장 |
| 중심·방향 등록과 episode 고정 | 동일 패키지 `stain_detect.py`의 `dark_cloud_origin`; `stain_origin_node.py`의 `_resolve_dark/_publish_origin`; `inference_adapter.py`의 `_on_origin` | 3장 |
| 방향 정렬·입력 영상 회전·출력 역변환 | `behavior_ws/src/nrs_imitation/nrs_imitation/inference_core.py`의 `_canon_setup/_canon_obs_pose6/_canon_rotate_image/_canon_cmd_seq/_srf_command_seq`; 2026-10-15 읽기 전용 발췌·hash는 `provenance/stain_relative_generalization_20261015/manifest.json` | 3–6·8·9장 |
| 방향 변환의 적용 범위와 기본값 | 같은 소스 및 `launch/inference_clean_single_cam.launch.py`; XY만 회전, Z·자세·힘 유지; 기준132도·상대각65도는 기본 설정이지 검증 범위가 아님 | 3·8장 |
| E1/E2 방향 정규화 OFF·학습 데이터 rotation_aligned=false | 실제 각 run의 execution/runtime config, 기존 model manifest, `provenance/results_20261016/`의 실제 E1 설정과 E2 runtime 경로 | 3·4·7장 해석 |
| native→base 힘 회전, 중복 영점/중력 보정 없음 | `reports/20261014_E1_correspondence_audit_v2_force/force_pipeline.md`, `force_transform_evidence.json` | 4·6장 |
| Q95=30.812396273 N, Q05는 접촉 문턱 아님 | 동일 감사의 `force_stats.csv`, `audit_summary.md` | 6·7장 |
| cleanup와 train38/val4 | `experiments/e2_force_cleanup_20261012/dataset_manifest.json`; 실제 42 HDF5 | 4장 |
| DINOv3·3축 GRU30·6/9D·학습식 | 동일 실험 `snapshot/source/models/flow_core.py`, `source/data/dataset.py`, `training_configs.json` | 5장 |
| 500 epochs와 best epoch 39/42/42(0-based) | 동일 실험 `model_manifest.json`; 실제 checkpoint metadata | 5장 |
| 공통 provider/executor·conditioner·주기 | E1 frozen_config/frozen_source; E2 runtime_20261013/source_snapshot; 각 실행 runtime | 6장 |
| E1 주15회, R/T/C 각5/5 완료·시간·초과적분 | `reports/20261015_E1_nominal_pass_height_v2_pdf_report/input_manifest.json`, `numeric_per_run.csv`; 실제 receipt events | 6·7장 |
| 10/14 역사적 E1 원3/5·4/5·5/5와 높이-only replay5/5 | 이전 검증·역사적CSV·`baseline_replay_comparison.csv` | 부록 B |
| 실행한 observer v2와 E1약125Hz·E2약18Hz 구분 | 10/15 실제 수신 events·고정 task_evaluation과10/13 보관CSV | 6·7장·부록 A |
| 원 C5와 별도 C6 진단 | 두 원 run_id의 outcome·수신시계열; `data/e1_c5_c6.csv` | 7장 별도 표/패널 |
| E2 15회 수치와 A4 중단 | `reports/20261013_E2_pdf_report/metrics_per_run.csv`; 각 run 원 CSV; 현 사용자 지시 | 7장 |
| E2 옛 전체 정상 완료 해석의 충돌 | 동 보고서 operator_completion_criterion.json vs 이번 현장 정정 | notes/writing_notes.md |
| 표면 제거 heatmap은 a.u. | `polishing_removal_recorder.py`, E1/E2 분석 README | 8장 |

외부 문헌은 `notes/literature_verification.md`에 원문 URL·확인한 절·사용 범위를 기록한다. `.bib`에는 확인한 항목만 사용한다.

2026-10-15 후속 수정은 중심·방향 기준 일반화 구현에 해당하는 소스와 연결 문장만 대조했다. E1/E2 수치·도표·모델 검산을 다시 수행하거나 변경하지 않았다.

2026-10-16 결과 갱신: 위 최신 E1·C6 대응이 현재 본문을 지지한다. 이전10/15 후속 수정 기록은 당시 작업 이력이다. 최종 주장별 연결은 `claim_evidence_map.md`에, 재계산·기존 검증 재사용은 `provenance/results_20261016/analysis_scope.json`에 정리했다.
