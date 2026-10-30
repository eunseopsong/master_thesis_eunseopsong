# 힘 처리 경로 보완: 사용자 장착 정보 반영

이번 판정은 **A — 공통 base 평가축의 기록된 힘 기준을 계산할 수 있음**입니다. 사용자 확인으로 교시 센서의 공구 장착, +Z와 X/Y의 공구축 일치, 영점·중력 로직 유지가 확인됐습니다. 수집 전 git 소스·설정과 현재 파일의 동일성도 검산했습니다. 독립적인 물리 교정 시험을 새로 수행했다는 의미는 아닙니다.

고정 변환은 `R_tool<-published=I`이며, 자세 의존 변환은 `R_base<-tool(t)=Rotation.from_rotvec(pose[3:6])`입니다. 기존 중력 소스는 `R_pose.T @ g_base`로 local 중력을 계산하므로 반대 방향인 `R_pose @ f_tool`이 base 벡터입니다. Vive 원 tracker 자세를 센서 자세로 사용하지 않고, 이미 등록·공구 보정을 거쳐 HDF5에 발행된 calibrated_pose/tool 자세를 사용합니다. XY 상대좌표화나 episode별 XYZ translation을 힘 회전에 추가하지 않습니다.

교시 순서: 센서 decode·축/부호 설정·startup mean zero → 선택된 publisher filter → delta-gravity 보정 → /ftsensor/measured_Cvalue → image receipt clock에 동기화한 raw_ft/raw_position → native축 EMA(alpha=.2)와 기존 pose filter → native축 cleanup → 저장 learning force. 이번 진단은 **이 learning 3축 벡터를 paired stored pose로 base에 한 번 회전**합니다. `Contact_Sensor_sign`이나 `gravity_compensation_axis_sign`을 이미 보정된 벡터에 다시 곱하지 않습니다.

로봇 순서: FT input startup mean zero → MOV2 → fixed sensor->TCP diag(1,-1,-1) → delta-gravity TCP 보정 → TCP->base pose rotation → /ftdata → ft1data/currentF 복사 → executor/wrench.csv. CSV는 이미 base 힘이므로 다시 회전하지 않습니다. 토크 기준점이나 controller_applied_force는 Fz 비교의 필수 조건으로 추가하지 않습니다.

보관 launch는 VR_config.yaml을 읽는 nrsvr_ft_aq와 config.yaml을 읽는 nrs_ft_aq 두 경로입니다. 두 YAML의 raw ContactID/채널 reorder는 다릅니다. 따라서 원 packet을 임의로 재구성하지 않습니다. 저장된 post-decoder Wrench의 sensor/tool 대응은 사용자에게 설정값을 제시해 확인한 full-axis identity 관계를 적용합니다. 두 설정의 tracker_to_sensor_rpy와 중력 모델/적용 의미는 같습니다. 이 해석은 operator_evidence.json에 명시했습니다.

각 3축 표본을 회전한 뒤 기존 empirical left-inverse Q05/Q95를 계산했습니다. unique42개=38train+4validation, 기존 stored Z<=175 후보, episode동일질량과 표본 실제시간 가중은 보존했습니다. 소스 Fz Q95 한 숫자를 base로 복사하거나 native Fz만 cos으로 곱하지 않았습니다. source headerless force의 실제 취득 시각/zero epoch는 복원할 수 없지만 이미 보정·발행된 신호의 회전에 추가 영점/중력 보정이 필요하지 않습니다.

진단 변형을 분리했습니다. `cleanup_base`는 학습 필드와 paired filtered pose, `EMA_base`는 cleanup 이전 EMA와 같은 pose, `raw_base`는 raw_ft와 동기화된 raw_position pose, `cleanup_rawpose_base`는 자세 필터 영향 확인입니다. `rotate_then_EMA_base`는 처리 순서 차이의 보조 진단이며 학습 필드를 교체하지 않습니다. native축에서 clipping한 뒤 회전하는 것과 회전 후 clipping하는 것은 다릅니다. 음수를 복원하거나 양수 floor를 추가하지 않았습니다.

force_stats.csv, demo_force_base_samples.csv, processing_order_diagnostics.csv와 base_force_phase_stats.csv에 전체 표본·집합·단계별 검산을 저장했습니다. geometry와 dwell은 이전 감사 결과를 그대로 참조합니다. 이번 upper_excess는 공통축 상한이 계산되어 독립적으로 완성됐습니다. 범위 내 시간은 `range_qualified`로 명명하며 유효 접촉 또는 제거율을 확정하지 않습니다.
