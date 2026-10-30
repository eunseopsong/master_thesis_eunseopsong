# 얼룩 중심·방향 상대좌표 블록 다이어그램

PPT 삽입용 16:9 구현 개념도다. 논문 원고나 로봇 구현은 변경하지 않았다.

- `stain_relative_frame_block_diagram.png`: 3840×2160, 흰색 배경. PPT 그림 삽입에 바로 사용한다.
- `stain_relative_frame_block_diagram.svg`: 확대 가능한 벡터. 한글 폰트 의존성을 없애기 위해 글자를 경로로 저장했다.
- `stain_relative_frame_block_diagram.pdf`: 16:9 벡터 PDF.
- `stain_relative_frame_block_diagram_source.py`: 문구·색·배치를 수정할 수 있는 생성 코드.
- `stain_relative_frame_block_diagram_provenance.json`: 직접 읽은 구현 파일·함수·SHA-256 및 그림 출력 hash.

## 표시한 로직

1. 작업 영상의 표식 검출점을 평면 homography로 로봇 base XY에 사상한다. 강건 중심 추정과 SVD로 중심 `c_live`와 주축 `theta_live`를 구하고 episode 동안 고정한다.
2. 교시 데이터의 관측·행동 XY에서 `c_demo`를 빼 중심 상대좌표로 학습한다. 데이터 변환 자체는 회전 정렬을 하지 않는다. `theta_ref`는 교시 기준 방향의 설정값이며 정책이 추정한 출력이 아니다.
3. 온라인 입력은 `u = R(alpha)(p_xy - c_live)`, `alpha = wrap_pi(theta_ref - theta_live)`로 교시 기준 방향에 정렬한다. 옵션으로 RGB를 TCP-ROI 중심에 대해 회전한다. 입력 정규화 후 Flow 정책이 동작·목표 힘을 생성하고 행동 역정규화를 적용한다.
4. 생성 XY는 `p_xy_cmd = R(-alpha) u_hat + c_live`로 복원한 뒤 기존 공통 실행 계층으로 전달한다.

`wrap_pi(delta) = ((delta + pi/2) mod pi) - pi/2`다. 주축은 시작/끝이 정해진 벡터가 아니라 180도 주기의 축이다. `p_xy`, `c_live`, `c_demo`, `u`는 평면 위치(mm), 각도는 rad, `rho`는 공구 rotation vector, `f_tar`는 정책 목표 힘이다. `R`은 2차원 회전 행렬이다.

Z·공구 자세·힘 채널은 이 XY 좌표 어댑터가 회전하거나 이동하지 않는다. 해당 채널의 기존 좌표 규약과 별도 전처리/정규화는 유지한다. 영상 회전은 XY 위치 회전과 별도 처리이며 이미지 좌표 부호 설정을 사용한다. 등록한 각도는 실행 중 매 순간 다시 검출하지 않는다.

방향 정렬이 꺼졌거나 유효한 각도가 없거나 설정 각도 범위를 넘으면 `alpha=0`으로 중심 상대좌표만 사용한다. E1/E2 비교에서는 방향 정렬이 꺼져 있었다. 이 그림은 구현 경로를 설명하며 새로운 위치·방향 일반화 성능이나 실험 결과를 주장하지 않는다.

## 재생성

Matplotlib와 NumPy가 있는 기존 Python 환경을 사용한다. 새 패키지 설치는 필요하지 않았다.

```bash
python3 stain_relative_frame_block_diagram_source.py --output-dir .
```

원 코드의 출처 hash를 다시 기록하려면 필요에 따라 `--repo /home/eunseop/nrs_imitation`을 지정한다. 생성기는 코드·로그·데이터셋을 수정하지 않으며 ROS·로봇·학습을 실행하지 않는다. PNG를 시각 검토해 한글·수식·화살표·블록의 잘림과 겹침이 없는지 확인했다. 기존 논문 프로젝트의 LaTeX·PDF는 이번 그림 제작에서 수정하지 않았다.
