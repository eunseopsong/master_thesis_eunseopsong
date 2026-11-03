# 국소 로봇 폴리싱 석사학위논문 수정 검토본 — 2026-11-03

**Human-Guided Local Robotic Polishing via Joint Motion–Force Representation and Force-Conditioned Imitation Learning**

현재 진입점은 `ThesisMain.tex` / `ThesisMain.pdf`, 별도 표지는 `ThesisCover.pdf`다. 출발점인 `../local_polishing_revised_20261016/`와 이전 ZIP은 그대로 보존했다. 사용자 승인 전 검토본이며 새 FIXED 모듈을 지정하지 않았다.

- E1: 10/19 추가 R* 5회와 10/15 원 T/C 각5회를 최신 표로 제시. 원 R 5회와 원 C5, 별도 C6를 보존한다.
- E2: 원15시도, A4 접촉 해제 미완료·28.750초 중단 정정을 유지. 완료시간 n=4/5/5, 힘 peak n=5/5/5다.
- E3: 보존된25회에서 본문 N/P1/D1/D2 20회, 영상 유효19회. P2 5회는 실행됐지만 최종 가림으로 주 결과에서 제외한다. D1-4는 D1에 남기고 제거율만 null이다.

## 재생성과 빌드

pdfLaTeX/KoTeX/BibTeX와 기존 학교 양식을 사용한다. 원래 `build.sh`는 변경하지 않았다.

```bash
cd /home/eunseop1/master_thesis_eunseopsong/thesis/local_polishing_revised_20261103
python3 scripts/update_results_20261103.py
python3 scripts/export_information_diagram_20261103.py
bash build.sh
python3 scripts/validate_revision_20261103.py
python3 scripts/render_revision_20261103.py
python3 scripts/package_project.py
```

이 PC의 임시 TeX 환경을 이용할 때는 빌드 전에 `source /tmp/thesis-revision-20261103/tex-env.bash`를 실행한다. 임시 환경 준비 절차는 `review/build_environment_20261103.md`에 기록했다. 정상 설치된 TeX 환경에서는 필요 없다. 수치·도표 재생성은 Python 표준 라이브러리, numpy, matplotlib, Pillow, Poppler를 사용하며 pandas·ROS·학습 모델은 필요 없다. 캐시 경로가 필요하면 `MPLCONFIGDIR=/tmp/thesis-revision-20261103/matplotlib`을 지정한다.

`update_results_20261103.py`는 동봉 E1/E2 정밀 CSV와 원보고서 사본만 읽는다. E3 보고서의 정수 면적에서 제거율을 계산하며 새 분할·주석·임계값 변경을 하지 않는다. R* 주표는 보고서의 확정 집계값을 사용하고, 개별 점은 인쇄된 소수3자리값임을 명시한다. 과거 `collect_*`, `plot_results_20261016.py`, `make_tables.py`, `validate_manuscript.py`는 이력이며 이번 진입점이 아니다.

## 출처와 실제 미확인 사항

지정된 네 PDF와 기존 원고의 정밀 CSV는 읽었다. `/home/eunseop1/nrs_imitation` 및 과거 `/home/eunseop/nrs_imitation`은 현재 PC에 없었다. R* 원CSV/run_id/template 및 E3 image_pair_manifest·annotations·원본RGB/mask·원25쪽 실행 보고서는 직접 재확인하지 못했다. 보고서의 원본 영상·ROI·mask 근거 패널을 그대로 추출해 사용하며, 독립 원본 대조를 수행했다고 쓰지 않는다. E3 등록값과 동일 체크포인트·종료 구현 정보는 사용자가 확정한 지시와 보고서의 해당 이력을 함께 출처로 표시한다.

- `revision_summary_20261103.md`: 장·절·표·그림 변경과 보존 범위.
- `claim_evidence_map_20261103.md`: 보고서 페이지·데이터·주장 대응 및 출처 수준.
- `results_manifest_20261103.csv`: E1 original15/R*5/C6, E2 corrected15, E3 archive25/main20/image19의61행.
- `data/results_summary_20261103.json`, `data/results_precision_20261103.csv`, `tables/result_numbers.tex`: 단일 수치 기준과 본문 매크로.
- `provenance/results_20261103/`: 원보고서 사본·입력 hash·25개 E3 근거 패널·분석 정의.
- `review/`: 실제 빌드/수치 검증/렌더·시각 검토 기록과 잔여 경고.

전달 ZIP에는 편집 가능한 원고·서지·학교 양식·필수 도표·수치·코드·PDF·압축 근거만 포함하며 폰트파일·체크포인트·전체 원로그·대용량 영상은 제외한다.
