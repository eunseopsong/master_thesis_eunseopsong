# 1차 수정본 인계

1. 제목은 **Human-Guided Local Robotic Polishing via Joint Motion–Force Representation and Force-Conditioned Imitation Learning**이다. 인간의 영역 지정→동작·힘·시간 교시→상대 표현→관측 조건부 생성→공통 실행→E1/E2 평가의 흐름으로 구성했다.
2. 기존 1–9장을 모두 재구성했다. 일반 multitask loss, 6축 wrench 정책, 제거 완료 판단, 속도 보존, calibrated removal 등의 가정을 실제 구현 범위로 교체했다.
3. 98쪽, 9개 본문 장과 3개 부록, English Abstract와 국문요약, 그림20개·표18개·문헌13개를 포함한다. E1 15실행과 E2 15시행의 원 CSV 수치를 검산했고 원래 R5 미시작 등록도 구분했다.
4. 보완 NOMINAL/LOW/HIGH는 not_run으로, dose·blending·adaptive execution은 상태를 적은 확장으로, high-level residual RL과 곡면/표면 계측 검증은 향후 범위로 분리했다. C의 보편적 우위를 주장하지 않았다.
5. PDF·전체 LaTeX·class/style/bib·그림·표·논문용 CSV·재생성 코드·변경/근거 기록을 함께 제공한다. `bash build.sh`로 전체를 빌드한다. 동봉 자료 기반 도표 재생성은 `python3 scripts/plot_figures.py`, `python3 scripts/make_tables.py`다.
6. 실제 새 결과는7장, 확장·표면 계측은8장, 신호/설정/run 자료는 부록과 data에 session/version별로 추가한다. `open_items.md`에 저자·제출 정보 등 남은 항목을 모았다.

원본 PDF·LaTeX와 nrs 코드·데이터·checkpoint·로그는 변경하지 않았다. 빌드/검산33항목이 통과했고 잔여 경고는 기존 KoTeX/microtype font patch와 PDF page.1 destination2건이다.

후속 수정: 얼룩 중심 상대위치 학습과 방향 정렬·출력 역변환 구현을 3.5절에 수식으로 추가했다. 4장 좌표 그림과 직접 연동되는 초록·서론·방법·논의·결론·부록을 수정했다. 방향 정규화가 꺼진 E1/E2의 결과는 재해석하거나 변경하지 않았다. 변경·인접26쪽만 렌더해 재검토했으며 원자료 재추출·도표 일괄 재생성을 반복하지 않았다. 향후에도 요청 범위와 직접 연결되는 내용만 수정한다.
