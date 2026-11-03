# 2026-10-15 중심·방향 기준 상대위치 구현 보완

사용자 요청에 따라 얼룩 중심과 방향을 이용한 정책 일반화 구현을 방법에 추가했다. 원고 전체를 다시 쓰거나 실험 수치를 다시 산출하지 않았다.

## 실제 데이터 흐름

1. 교시 observation/action의 XY에서 얼룩 중심을 차감하여 local position을 학습한다. 저장 데이터의 `rotation_aligned=false`는 이 단계의 속성이다.
2. 온라인 등록은 영상의 dark cloud를 각 영상의 homography로 base XY에 투영·통합하고, robust center와 SVD 주축 방향을 구해 episode 동안 고정한다. 수동 live angle도 지원한다.
3. 활성화된 방향 변환은 `alpha=wrap_pi(theta_ref-theta_live)`로 중심 상대 XY와 single-camera 정책 영상을 학습 기준 방향에 맞춘다. pose normalization은 XY 변환 뒤에 적용된다.
4. action denormalization 뒤 예측 XY를 `R(-alpha)`로 회전하고 live center를 더한다. demo start에도 같은 역변환을 사용한다.
5. Z·tool rotation vector·force observation/action은 회전하지 않는다. 영상은 TCP ROI 중심 기준 bilinear/reflect warp이며 완전한 perspective 정규화는 아니다.
6. 현재 기본값은 enable=false, reference=132도, max relative angle=65도이다. 학습 데이터 이름의 90deg와 base reference angle을 동일시하지 않는다. 각도 부재/범위 초과 시 원 코드가 translation-only로 동작한다.

## 구현과 실험의 구분

방향 전이 경로는 실제 구현이다. 9/10–11 `flow_canon_*` 개발 CSV도 있으나, 이 CSV의 열만으로 활성 파라미터·live angle·완료 기준을 확정하지 않는다. 이를 새로운 정량 성능표로 만들거나 October E1/E2에 합치지 않았다. E1/E2는 실제 runtime에서 방향 정규화 OFF이다. 따라서 이 비교의 결과를 방향 일반화 성능이라고 바꾸지 않는다.

근거 원본 경로·함수·행과 SHA-256은 `provenance/stain_relative_generalization_20261015/manifest.json`과 해당 폴더의 작은 발췌 파일에 기록한다. 이는 원 레포를 읽은 자료이며 로봇 실행이나 정책 시험을 추가한 것이 아니다.

## 변경 범위

- 핵심 변경: 3장에 전용 절과 수식 3개, 4장 기존 좌표 처리 그림과 데이터 설명.
- 직접 연동: 기호표, 영문 Abstract·국문요약, 1장 기여/범위, 5·6장 입출력 좌표 설명, 8장 해석, 9장 결론, 부록 좌표 정의.
- 기록: evidence_map, figure_manifest, open_items와 README.
- 실험 표·실측 그래프·수치, 기존 bibliography·학교 style은 재사용한다.
- 전체 문서 컴파일 후 해당 문장·수식·그림과 재배치된 페이지를 검토한다. 전체 데이터 추출·모델 로딩·도표 생성은 반복하지 않는다.

향후에도 같은 범위 제한을 적용하도록 상위 `AGENTS.md`에 후속 수정 원칙을 기록했다.
