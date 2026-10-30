# E2 C blending — current nrsgene controller, 20261013

실행 순서는 **E2 C inference → 정상 종료 및 툴 이격 확인 → inference 히트맵 창 표시 → 5초 대기 → blending path 1회 → 정지/이격 확인 → inference only / blending path only / combined 히트맵 표시**다. 마지막 세 지도는 같은 창의 세 패널에 같은 좌표 격자와 색상 범위로 표시한다.

## 현재 제어기 적용

nrsgene의 `/home/nrs_forcecon/dev_ws/src/y2_ur10skku_control`에서 `b2435fa` 및 20261013 접촉 안정화 작업을 포함한 소스를 기준으로 준비했다. `robot_command.hpp`, `robot_command.cpp`, `singleArm_cmd.cpp`만 수정했고 해당 PC의 `singleArm_cmd` 빌드까지 완료했다. 기존 소스는 `*.before_e2_blending_20261013`에 백업했다. 실제 로봇 가공은 실행하지 않았다.

- `CmdContinue9D v2`는 현재 제어기 설정, Force mode, force frame, signed base-Fz 접촉 기준 및 전환 시간을 `/singleArm_cmd/continue9d_info`로 제공한다.
- 정상축 접촉 전환이 켜져 있으면 replay는 유효한 원래 힘 목표를 전달하고, motion controller가 접촉 확인과 Position/Force handover를 수행한다. replay에서 순간적인 force dip을 다시 zero-force 목표로 바꾸지 않는다. 전환이 꺼진 경우의 기존 replay gate도 `abs(Fz)` 대신 signed base Fz를 사용한다.
- Mode 5/6/7 또는 NRS 평가 환경의 inline replay는 시작 전에 거부한다. 일반 PTP, TxtLoad, NRS trajectory scheduler 및 PTP9D stream 경로는 그대로 사용한다.
- 현재 0.5초 전환, 0.024초 접촉 확인 및 0.080초 capture stop에 맞춰 load 뒤 최소 0.604초, release 뒤 최소 0.5초를 경로와 시간 예산에 포함한다. 실행 전 capability에서 더 긴 전환 시간을 받으면 대기를 늘린다. 실제 측정 지도에 계획의 예측 dose를 더하지 않는다.
- 최초 히트맵은 frame ID와 ROS stamp로 식별한다. viewer가 해당 이미지를 창에 그린 뒤 acknowledgement를 보내며, executor가 이를 받은 시점부터 5초를 센다. 오래된/중복 응답은 무시한다. 15초 동안 표시 확인이 없으면 blending을 시작하지 않는다.

제어기 YAML, 기존 force-control 구현, 20261013 접촉 안정화 및 평가 기능에 대한 기존 수정은 유지했다. 실제 읽어온 파일 해시는 `validation.json`에 있다. 예전 20261007 소스 전체를 현재 제어기에 덮어쓰지 않는다. 적용 스크립트의 기본 대상도 이 폴더의 해시 검증 패치로 갱신했다.

## 실행

nrsgene에서 평소 제어 환경을 먼저 실행하고 **새 바이너리의 singleArm_cmd**를 사용한다. 이미 떠 있으면 해당 터미널에서 종료 후 다시 실행한다. 명령 노드만 실행할 때는 다음과 같다. motion/FT/robot-driver 환경은 평소 방식으로 함께 켠다.

```bash
source /opt/ros/humble/setup.bash
source ~/dev_ws/install/setup.bash
export ROS_DOMAIN_ID=30 ROS_LOCALHOST_ONLY=0 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ros2 run Y2RobMotion singleArm_cmd --ros-args \
  -p setup_file:="$HOME/dev_ws/src/y2_ur10skku_control/Y2RobMotion/config/setup_parameters.yaml"
```

nrs3에서:

```bash
cd ~/nrs_imitation
source scripts/e2_c_blending_20261013_env.sh
ros2 launch nrs_imitation e2_c_blending.launch.py mode:=run session:="$E2_SESSION"
```

기본 C 정책은 현재 force-cleanup 재학습 모델의 `policy_best.ckpt`다. manifest는 `experiments/e2_force_cleanup_20261012/model_manifest.json`이며 checkpoint와 normalizer 해시를 검사한다. 기존 C 모델을 명시적으로 선택하려면 `model_manifest:=''`를 지정할 수 있다.

원하는 시점에 inference를 끝내면 나머지 순서가 자동으로 진행된다. 별도 nrs3 터미널에서:

```bash
source ~/nrs_imitation/scripts/e2_c_blending_20261013_env.sh
ros2 service call /e2_executor/finish std_srvs/srv/Trigger '{}'
```

15초 inference 후 자동 진행하려면 launch에 `initial_inference_sec:=15.0`을 추가한다. 시간은 실제 inference 실행 시작부터 센다.

```bash
ros2 launch nrs_imitation e2_c_blending.launch.py mode:=run \
  session:="$E2_SESSION" initial_inference_sec:=15.0
```

중단:

```bash
ros2 service call /e2_executor/abort std_srvs/srv/Trigger '{}'
```

설정만 확인하는 `mode:=check`는 제어/GUI 노드를 시작하지 않는다.

```bash
ros2 launch nrs_imitation e2_c_blending.launch.py mode:=check
```

`show_heatmap:=false`는 화면 표시 acknowledgement를 생략하는 명시적 headless 모드다. 이 경우 이미지 publish 후 5초를 세며, 요청한 화면 표시 순서는 기본값 `show_heatmap:=true`에서 적용한다.

## 기록 및 검증

`results/YYYYMMDD/E2_C_blending/<session>/blending/`에 최초 지도, native 8 ms 경로, 실제 측정 CSV, 최종 세 지도 및 summary를 저장한다. `effective_blending_config.json`에는 실제 capability와 이를 반영한 대기 시간이 저장되고 executor 이벤트에는 `/ur10skku/contactTransition`도 기록한다. 단위는 기존과 같이 미보정 relative Preston dose이며 measured depth가 아니다.

최종 관련 회귀 실행 78개, 기존 blending geometry/uniformity·E2 ABC/force-cleanup/return-home 회귀, nrs3 패키지 빌드, nrsgene native 빌드, 실제 재빌드 바이너리의 ROS Domain 213 분리 capability 조회 및 offscreen Qt 표시를 확인했다. 자세한 검증 범위는 `validation.json`에 있다. 20261009 실제 기록으로 새 경로를 계산한 오프라인 결과는 `preview_20261009/`이며 7,924개 경로점, 63.384초다. 새 실기 가공 결과는 아니다.
