# 2026-10-16 결과 범위 갱신

현재 검토본은 E1의10/15 주15회와 E2의10/13 주15시도를 사용한다. 아래 번호 기록은10/15 초기 수정본 시점의 역사적 판단이다. 최신 상태는 `revision_summary.md`와 `claim_evidence_map.md`를 따른다.

- baseline_manifest의 준비 시점0회와 실제10/15 보고서의15회가 충돌한다. 실제 실행·고정 보고서 run_id를 채택했다.
- 이후16개가 된 attempts 목록은 보고서 고정 주15회+C6추가1회다. 원 repeat_index=5의 늦은 실행을 새 주 C5로 선정하지 않았다.
- A4의 현장 정정을 유지했다. E2 수치 자체와 원 stop reason을 덮어쓰지 않고 완료시간 n4/전체시도 n5를 분리했다.
- C6는 원 outcome 및 원 수신 시계열을 읽고 기존 적분을 확인했다. 화면 요약만 독립 검증한 것으로 쓰지 않았다.
- LOW/HIGH와 참조오프셋은 확정된 미평가 범위다. 이 원고의 필수 후속 실행으로 남기지 않았다.

---

# 작성 판단과 자료 충돌

## 채택한 기준

이번 사용자의 연구 범위·현장 정정 → 실제 실행의 runtime/frozen config/source → 원자료 및 재현 가능한 분석 → 현재 구현 → 과거 초안의 순서로 적용했다. 원본 PDF/LaTeX, nrs 구현·원 로그·교시·checkpoint는 수정하지 않았다.

## 주요 충돌과 처리

1. **옛 초록과 현재 구현**: FAIRE의 제거량·결함 심각도 판단, calibrated removal, residual RL 곡면 복원은 현재 검증 범위와 맞지 않는다. Ch.1–7은 국소 스킬 생성·실행으로 재작성했고 관련 자산은 Ch.8로 옮겼다.
2. **E2 A4**: 기존 `operator_completion_criterion.json`은 15회 전체 완료를 전제로 한다. 이번 현장 정정이 더 구체적이므로 A4만 접촉 해제 전환 미완료로 별도 outcome을 추가했다. 원 `operator_finish`/`normal_completion`과 28.750087346초는 변경하지 않았다. 완료시간 A=17.6474±1.2016초(n=4), 완료4/5와 함께 표기했다. 전체5시도의 평균 구간19.8680±5.0731초는 그대로다.
3. **E1 완료율**: 실행 버전의 최초 접촉 기준 높이 R3/T4/C5 완료와 별도 pass-height-only replay R5/T5/C5를 다른 표로 제시했다. old observer 기록에서 새 observer의 실제 수신 구간은 복원할 수 없으므로 15/15를 보완 평가기의 새 물리 결과로 쓰지 않았다.
4. **높이 시험**: `E1_CT_pass_height_v2_nominal_dev_20261014`, heights 개발 세션과 v2의 `attempts.json`이 모두 비어 있다. LOW/HIGH는 실제 시편 ±1mm 배치의 준비 상태이며 목표 Z 이동 시험으로 대체하지 않았다.
5. **E1 R5**: 원 보고서가 별도 보존한 19:15:08 미시작 등록과 19:18:42 재시도를 구분했다. 본문/부록에서 총16등록·15시작을 설명하고 완료율의 분모가 시작 시행임을 명시했다.
6. **R/T/C 공통 평활**: profile 내부의 구형 `C pose only` 설명보다 실제 frozen `rtc_pose_conditioning` wrapper와 `executor_settings`/`FinitePoseConditioner` 흐름을 채택했다. 실제 비교는 R/T/C 공통 pose 평활이다. R/T source force/time의 유지와 실제 TCP 속도의 동일성은 구분했다.
7. **힘축**: 최신 force 감사 v2의 `R_tool<-published=I`와 calibrated tool pose에 의한 base 회전을 채택했다. 구형 축 미확인 문구는 가져오지 않았다. 공통축 통계 계산과 controller-applied 목표의 실제 추종 검증은 다른 문제다.
8. **학습·온라인 force input convention**: training 데이터는 native published teaching 3축 force, archived inference는 `_extract_force3`로 로봇 base force를 읽어 normalize한다. 확인되지 않은 회전을 했다고 추가하지 않았다. 이 구현상의 제한은 Ch.4와 Ch.8 본문에도 명시했다.
9. **3축 예측과 실제 force 명령**: 9D B/C는 force3를 학습하지만 공통 executor는 tangential command를 zero한다. 3축 관측/예측을 3축 힘 추종 검증이라고 확대하지 않았다.
10. **학습값**: 500 epoch 설정과 best epoch39/42/42(0-based)를 별개로 적었다. normalizer의 실제 train38/val4 분할을 확인했다. A의 force OFF는 정책 입력/출력에 적용되며 offline phase sampler에는 force 정보가 쓰인다.
11. **시계**: flow time, 30 Hz reference, 120-step stride, 5 Hz timer, 125 Hz command, 약18 Hz CSV 기록률을 구분했다. 온라인 history30은 callback 표본 수이지 항상1초는 아니다.
12. **원 사진**: 명확한 전체 teaching rig 사진은 없었다. 실제 교시 RGB 프레임과 편집 가능한 좌표 개념도를 사용했다. 8/7 apparatus 사진은 실제 October run 사진으로 표시하지 않았다.
13. **영상**: 첫 E2 C WebM은 container duration이 없고 파일 끝이 조기 종료된다. 디코딩 가능한 프레임의 최종 timestamp로 추출 범위를 정했다. 캡션·부록에서 부분 영상임을 명시했고 성공 완료 인증에는 쓰지 않았다. A4 영상은 없다.
14. **확장**: 10/14 adaptive velocity의 실제 runtime5개는 서로 다른 버전의 online OFF development다. 이를 ON/OFF 성능 비교나 기존 E2 C 결과에 합치지 않았다. v7 offline 수정 확인을 새 물리 성공으로 쓰지 않았다.
15. **문헌**: 기존 Schneyer bib 저자명 오류와 Hogan Part I 표기를 원문으로 교정했다. DexForce는 force-informed position action을 사용하며 별도 force-vector command와 다르다. 직접 원문 확인이 불충분한 세부 수치는 새로 넣지 않았다.
16. **중심·방향 기준 일반화 구현 반영**: 후속 사용자 정정에 따라 `stain_relative_v1` 데이터 속성만으로 전체 구현을 평행이동 전용으로 설명했던 범위를 수정했다. 데이터 변환은 중심 차감이고, `inference_core`는 얼룩 주축을 학습 기준 방향에 맞추는 XY/영상 정렬과 출력 역회전을 구현한다. Ch.3에 수식·동작 범위를 추가하고 관련 절을 맞췄다. E1/E2의 실제 방향 정규화 OFF와 기존 결과 수치는 유지한다. 자세·힘까지 회전하는 완전한 frame 변환이나 정량 일반화 성과는 추가하지 않았다. 상세 발췌와 변경 범위는 `revision_stain_frame_20261015.md`에 기록한다.

## RA-L 자료 범위

지정된 10/05 RA-L 파일명·제목과 정확히 일치하는 파일은 현재 thesis, nrs의 paper/docs 관련 후보, Downloads의 관련 파일에서 찾지 못했다. `Downloads/RA_L_Polishing_Draft_20260928 (1).pdf`와 `Polishing_Paper_Draft_20260928.pdf`를 텍스트로 읽었다. 9월 수치와 구형 force-axis 유보를 최신 결과에 복사하지 않았다. 논리 구조는 이번 사용자 지시와 실제 October evidence를 따른다.
