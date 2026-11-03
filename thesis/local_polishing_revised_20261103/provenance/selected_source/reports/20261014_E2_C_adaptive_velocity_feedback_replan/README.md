# E2 C adaptive velocity: v6 정체 진단과 v7 재추론 수정

20:37:59 OFF 실행이 최초 접촉 후 멈춘 것은 새 adaptive reference-clock과 기존 제어기 힘 보호 판정 사이의 교착 때문이다. v5의 0 N 꼬리 구간 수정은 이번처럼 작은 **활성 힘 명령**이 남는 경우를 해결하지 못했다. v7은 기존 보호 판정을 유지하면서 그 정체 중에도 현재 관측으로 새 E2 C 예측을 받을 수 있게 한다. 실제 로봇은 실행하지 않았다.

## 기록에서 확인한 원인

원본 실행:
`results/20261014/E2_C_adaptive_velocity/E2_C_velocity_online_20261014_v6/E2_C_velocity_online_20261014_v6_online_off_r1_20261014T203759_e5f9e511ba/`.

실행 시작부터 Ctrl+C/manual_abort까지 34.824초 동안 provider는 경로를 1개만 만들었다. 경로 시계는 1.862530초에서 거의 진행하지 않았다. 기존 재계획 기준 3.5초에 도달하지 못해 재추론이 막혔다. controller 마지막 기록의 요청 TCP Fz는 0.833503 N, 실측 TCP 법선 힘의 절댓값은 2.105871 N이다. 기존 보호 조건 `|Fd| > 0.01 N && Fn > 1.6 * |Fd|`에서 기준 힘은 1.333604 N이므로 경로 진행 보호가 활성화됐다. tracking error는 4.137924 mm이고 fault는 0, command_fresh는 true였다. 전체 controller 4,358행 중 shield=1은 3,409행, fault는 전 행 0이다. 마지막 controller receipt는 첫 manual stop 요청보다 약 0.030초 뒤의 기록이며, 15·20·30초의 정체도 원본에서 따로 확인했다.

**Fn은 실측 base Fz를 그대로 부르는 값이 아니다.** 기존 제어기의 TCP 회전 기록으로 계산한 TCP 법선 성분의 절댓값이다. 같은 마지막 표본의 base Fz는 2.063814 N이다. 힘 신호에 새 영점·중력·부호·배율 보정을 적용하지 않았다. 이 기록만으로 잔류 힘이 기계적 접촉, 보정 잔차 또는 제어기 정상상태 오차 중 무엇에서 얼마나 기인했는지 분리할 수 없다. spindle 길이의 원인으로 단정하지 않는다.

자동 종료도 초기 비접촉을 확인하지 못했다. v6에는 `cycle_initial_noncontact_confirmed` 이벤트가 없었다. demo-start 정렬 이전의 HOME 정지 검증 구간에서는 0.4초 동안 기록된 9개 wrench 표본의 최대 |base Fz|가 0.357398 N으로, 기존 비접촉 기준 1.2 N 이내였다. 정렬 후의 힘 관측이 높아 실행 구간만 기다리던 v6의 초기 확인이 이 HOME 관측을 활용하지 못했다.

## 변경

- 온라인 source에서 fresh controller feedback이 실제 **힘 비율 보호**를 보고하면, 기존 3.5초 재계획 간격을 벽시계로도 판단해 새 예측을 받는다. 정상 경로 진행의 재계획은 기존 reference clock을 사용한다. frozen source와 기존 비adaptive 실행은 이 분기를 사용하지 않는다.
- 보호 중에 경로 시계를 강제로 진행하거나 힘 값을 늘리지 않는다. 모델이 새 힘 값을 예측하며 원래 force gate, 힘 변경률 30 N/s, 명령·가속도·작업 공간 제한을 계속 통과한다. 매 5 Hz 추론 tick마다 경로를 교체하지 않고 원래 간격을 유지한다.
- plan ID, 세션·설정·clock ID, controller freshness, command freshness, fault=0, tracking error <= 10 mm를 확인한다. stale feedback이나 다른 보호 판정을 새 추론으로 덮지 않는다. 기존 종료·timeout과 보호 임계값을 유지한다.
- 초기 비접촉 확인에는 기존 startup 정지 검증의 stationary HOME 구간에 기록된 힘을 활용한다. 같은 0.4초·1.2 N·0.2초 gap 기준과 ZOH를 사용하고 양 끝의 기록 지지를 요구한다. 관측이 없으면 실행 구간에서 확인하는 기존 절차를 유지한다. 힘 offset을 만들거나 센서를 tare하지 않는다.
- OFF/ON 모두 같은 비접촉 → 접촉 → 비접촉 확인, queue cancel·hold 검증, 실제 이탈 확인, HOME 복귀, controller selection 복원, launch 종료 절차를 사용한다. 같은 cohort의 첫 startup 실측 robot-base HOME을 공통 목표로 보존한다. 정상 완료 없이 timeout·오류·manual_abort가 발생하면 기존 verified hold를 수행하며 이를 자동 완료로 기록하지 않는다.

수정 파일은 `e2_adaptive_velocity.py`, `e2_adaptive_velocity_executor.py`, `e2_adaptive_cycle.py`, adaptive 분기에 한정한 `inference_core.py`, 전용 launch 및 별도 v7 설정이다. nrsgene 제어기, 기존 힘 보호 규칙, TCP 320 mm 설정, IL checkpoint·normalizer·RL actor를 이번 버전에서 수정하지 않았다. 설치된 Python package와 launch는 source symlink이므로 다음 launch에 적용되며, 이번 Python 변경을 위해 제어기를 재시작할 필요는 없다.

**이 수정은 보호 판정이 실제로 계속 유지되는 경우의 물리적 진행을 보장하지 않는다.** 새 예측도 저힘을 계속 요청하고 Fn이 비율 기준을 계속 넘으면 보호 hold를 유지한다. 그런 경우 기존 50초 작업 budget에서 timeout으로 남으며, 정체를 성공·정상 종료로 바꾸지 않는다. 실제 로봇의 전체 접촉 주기 및 가공량 개선은 추가 실행으로 확인해야 한다. 이미 확인할 수 없었던 Mode5 학습 환경의 실제 spindle 길이는 여전히 미확인이다.

## 검증과 산출물

ROS 초기화·로봇 명령 없이 실제 executor/controller callback과 실제 provider inference timer를 fake transport로 호출한 **146개 검사**가 통과했다. 두 arm의 low-force shield 상태, 새 경로 수신 전후의 reference clock 정지, 원래 힘 변경률, stale/fault/tracking 보호 구분, 초기 HOME 관측 지지, 자동 접촉 주기 및 복귀 순서를 검사했다. 기존 일반 inference/metrics 및 blending 재계획 검사도 통과했다. installed imports와 두 arm의 `mode:=check`를 확인했고, OFF/ON의 common settings hash가 같다.

현재 E2 C 실제 checkpoint를 CPU에서 strict load(누락/예상 외 key=0)하고, 마지막 저장 영상·실측 pose/force·기록된 force history로 실제 inference callback을 실행했다. 새 경로가 만들어졌으며 첫 힘은 0.499111 N, 전체 예측 힘 범위는 0.137642–26.757254 N이었다. 작은 첫 값도 그대로 보존한다. **이 예측은 당시 CUDA 실행의 정확한 재현이 아니며 보호 해제의 증거도 아니다.** 정확한 온라인 영상 안정화 상태, 모든 callback force history, CUDA 초기 FLOW 난수를 보존하지 못했다. CPU 난수 seed=0 및 마지막 30개 기록 표본을 사용한 오프라인 probe로 한계를 명시했다.

주요 파일:

- `recorded_run_diagnosis.json`: 원본 경로·SHA256·시간·힘 보호 수치·초기 HOME 힘 관측 근거.
- `recorded_progress_samples.csv`, `held_reference_clock.png`: 벽시계와 정체한 경로 시계, 힘 명령/실측/기존 비율 기준.
- `offline_prediction_check.json`, `offline_refreshed_prediction.npy`: 실제 checkpoint의 오프라인 새 예측 및 재현 한계.
- `python_tests.log`, `check_online_off.log`, `check_online_on.log`, `pair_definition_check.json`: 회귀 검사와 동일 설정 확인.
- `experiments/e2_c_adaptive_velocity_feedback_replan_20261014/`: 별도 설정 4개, source before/after, manifest, 재생성 명령.

## 사용 명령

기존 v6 세션·원본 로그·comparison.json·HOME 파일은 보존한다. 새 정의는 **v7 세션**에서 OFF/ON을 짝지어 실행한다. 카메라와 nrsgene singleArm_motion/single_cmd 실행은 이전과 같다. 첫 시도는 기존 운용대로 HOME에서 시작한다. 실행은 사용자만 진행한다.

```bash
cd ~/nrs_imitation
source scripts/e2_c_adaptive_velocity_env.sh
```

OFF:

```bash
ros2 launch nrs_imitation e2_c_adaptive_velocity.launch.py \
  mode:=run adaptive_velocity:=off source:=online \
  session:=E2_C_velocity_online_20261014_v7 repeat:=1
```

ON:

```bash
ros2 launch nrs_imitation e2_c_adaptive_velocity.launch.py \
  mode:=run adaptive_velocity:=on source:=online \
  session:=E2_C_velocity_online_20261014_v7 repeat:=1
```

동일 코드를 두 arm 사이에 수정하면 기존 pairing guard가 새 세션을 요구한다. 정상 완료는 자동으로 이탈·HOME 복귀·종료를 진행한다. 필요 시 등록된 `stop` alias는 기존 `/e2_executor/finish` 정상 finish 요청이다. Ctrl+C는 manual_abort로 구분한다.

오프라인 재생성:

```bash
cd ~/nrs_imitation
bash experiments/e2_c_adaptive_velocity_feedback_replan_20261014/regenerate.sh
```

이 재생성은 원본 CSV를 읽고 오프라인 모델·검사·`mode:=check`만 실행한다. run mode, 카메라, 제어기 또는 로봇 service call을 실행하지 않는다.
