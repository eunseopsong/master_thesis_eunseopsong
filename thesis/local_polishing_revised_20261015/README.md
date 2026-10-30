# 국소 로봇 폴리싱 석사학위논문 1차 수정본

**Human-Guided Local Robotic Polishing via Joint Motion–Force Representation and Force-Conditioned Imitation Learning**

인간의 영역 지정 → 동작·힘·시간 교시 → 작업 상대 표현 → 관측 조건부 Flow 생성 → 공통 실행·기존 접촉 제어 → E1/E2 평가의 흐름으로 9개 장을 재작성했다. 영문 본문·Abstract, 국문요약, 실제 사진·교시 RGB·실측 그래프·개별 시행 결과를 포함한다. 후속 수정으로 얼룩 중심 상대위치 학습과 방향 정렬·경로 역변환 구현을 3장에 추가하고 관련 문장을 맞췄다.

원본 thesis의 PDF/LaTeX와 nrs 프로젝트는 보존했다. 이 폴더가 독립적인 편집·빌드 대상이다. 학교 style/class/bst 파일은 원본 그대로다. 원본 표지는 저자·제출 정보가 미정이었으므로 새 정보·서명·승인 페이지를 만들지 않았다.

## 주요 파일

- `ThesisMain.pdf`, `ThesisMain.tex`: 전체 논문과 편집 진입점
- `ThesisCover.pdf`, `ThesisCover.tex`: 별도 초안 표지
- `chapters/`, `abstract_eng.tex`, `abstract_kr.tex`: 전체 원고
- `Bibliography/ThesisRef.bib`: 실제 사용한 13개 확인 문헌
- `figures/`, `tables/`, `data/`: 실제 그림·사진·도표 원자료 추출 및 집계
- `old_to_new_map.md`, `evidence_map.md`, `figure_manifest.json`, `open_items.md`
- `notes/writing_notes.md`, `notes/literature_verification.md`: 충돌 처리·원문 대조
- `provenance/`: 원본 해시, 보존 원고, 실제 모델·run/config 근거, 작은 source snapshot
- `review/`: 최종 빌드 로그·PDF 텍스트·렌더 검토·잔여 경고

## 빌드

기존 Ubuntu pdfLaTeX·KoTeX·BibTeX 환경을 사용한다.

```bash
cd /home/eunseop/master_thesis_eunseopsong/thesis/local_polishing_revised_20261015
bash build.sh
```

원 CSV를 다시 읽지 않고 동봉된 논문용 추출 자료로 도표와 결과표를 재생성할 수 있다.

```bash
python3 scripts/plot_figures.py
python3 scripts/make_tables.py
bash build.sh
```

도표 재생성에는 Python 3, numpy, pandas, matplotlib가 필요하다. 원 로컬 자료에서 추출·수치 검산까지 다시 수행하려면 h5py, scipy, Pillow와 ffmpeg/ffprobe를 포함한 기존 환경에서 다음 명령을 쓴다. 로봇·ROS·학습 명령을 실행하지 않는다.

```bash
python3 scripts/collect_evidence.py --repo /home/eunseop/nrs_imitation
python3 scripts/plot_figures.py
python3 scripts/make_tables.py
bash build.sh
```

그림·표·데이터 추출 스크립트는 수정본 폴더에만 쓴다. 독립 빌드와 동봉 데이터 기반 도표 재생성에는 원 데이터셋·checkpoint·영상이 필요하지 않다. 원본 재추출에는 manifest에 적힌 로컬 원 파일이 필요하다.

## 결과 해석과 다음 업데이트

E1은 10/14 nominal development15실행을 사용한다. 구형 exit criterion과 높이 기준만 바꾼 offline replay를 구분한다. 보완 NOMINAL/LOW/HIGH는 실제 시행이 없으므로 not_run이다. E2는10/13 A/B/C15시행이며 A4를 접촉 해제 미완료로 반영하고 A의 완료4/5와 전체5시도 통계를 분리한다. 중심·방향 기준 위치 일반화는 구현된 방법으로 설명하되, 방향 정규화 OFF인 E1/E2로 그 성능을 입증했다고 쓰지 않는다. surface quality·tracking RMSE·곡면 일반화 성과는 주장하지 않는다.

새 실험은 7장의 해당 질문별 절에 session/version을 분리해 추가한다. 표면 계측·확장 검증은8장, 재현·설정·개별 시행은 부록과 `data/`에 추가한다. 원고 논리와 초록·결론도 새 결과 범위에 맞춰 함께 수정한다.

## 후속 수정 원칙

수정 요청의 대상과 직접 연결되는 문장·캡션·참조·근거 기록만 작업한다. 기존 자료를 재사용하고 해당 도표만 재생성한다. 전체 LaTeX 빌드는 유지하되 PDF 시각 검토는 변경·재배치된 페이지에 집중한다. 구체적인 필요가 없으면 원자료 일괄 재추출, 전체 도표 재생성, 모델 재검산을 반복하지 않는다. 같은 원칙을 상위 `AGENTS.md`에도 기록했다.
