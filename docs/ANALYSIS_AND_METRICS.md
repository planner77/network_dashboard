# AGV/AMR–ACS 무선 네트워크 상태 수집 항목 조사 및 사전 감지·사후 분석 설계서

> **참조 안내**: 본 문서는 `AGENTS.md`에서 지정한 네트워크 도메인 분석 및 수집 지표 정의 표준 문서입니다. 백엔드 시뮬레이터 데이터 생성, 수집 항목 상세 설명 페이지 구현, 사전 감지/사후 원인 분석 알고리즘 구현 시 본 문서를 기준으로 삼습니다.

---

## 1. 현황 문제점 분석 및 수집 아키텍처 합리화

### 1.1 기존 30초 주기 소켓 상태 보고의 한계 (불합리성 진단)
- **현상**: AGV/AMR이 ACS와 TCP 소켓으로 연결되어 30초 주기로 상태(위치, 배터리, 작업 상태 등)를 보고함.
- **한계점 1 — 사전 감지(Pre-detection) 불가**:
  - 이동 중인 AGV가 물리적 전파 음영지역에 진입하거나 AP 간 로밍(Handover)을 수행할 때 신호 감쇠 및 패킷 재전송 급증은 **수백 ms ~ 수 초(3~15초)** 사이에 발생합니다.
  - 30초 주기 스냅샷만으로는 단절 직전의 급격한 무선 품질 저하(RSSI 급락, SNR 악화, TCP 재전송 폭발)를 포착하기 전에 이미 연결이 끊어집니다.
- **한계점 2 — 사후 원인 분석(Post-mortem RCA)의 블랙박스 현상**:
  - 소켓 연결이 끊어졌을 때, 그것이 **① AP 로밍 실패** 때문인지, **② 철제 구조물/간섭에 의한 전파 음영** 때문인지, **③ 동일 채널 AP 과부하** 때문인지, 아니면 **④ AGV 내부 OS/애플리케이션 소켓 블로킹(Hang)** 때문인지 30초 전의 정상 보고 데이터만으로는 구분할 수 없습니다.

### 1.2 합리화된 해결안: 3단계 하이브리드 수집 아키텍처 (Hybrid Telemetry Model)
네트워크 대역폭과 AGV CPU 부하를 최소화하면서도 1초 단위의 정밀한 가시성을 확보하기 위해 아래 3단계 하이브리드 수집 모델을 적용합니다.

1. **Stage 1 — AGV 로컬 경량 고주파 수집 (1초~5초 주기, Ring Buffer)**:
   - AGV 내부 에이전트가 커널 가상 파일시스템(`/proc/net/wireless`, `nl80211`, `ss -ti`)에서 **1초 주기**로 지표를 읽어 메모리 내 **고정 크기 링버퍼(최근 5분치, 약 150KB 미만)**에 보관합니다. (외부 네트워크 전송 없음 → 무선 부하 0%).
2. **Stage 2 — 평시 30초 상태 보고 피기백 (Statistical Piggyback)**:
   - 기존 30초 주기 ACS 상태 보고 패킷에 지난 30초간의 **핵심 통계 요약치(`RSSI min/avg/std`, `SNR min`, `TCP Retransmit delta`, `Gateway RTT avg/max`, `Roaming count`)** 약 **64~128 Bytes**를 피기백(첨부)하여 전송합니다.
3. **Stage 3 — 조기 경보 푸시(Early Warning) & 재연결 후 블랙박스 덤프(Post-mortem Dump)**:
   - **사전 감지 조기 경보**: 로컬 1초 수집 중 위험 스코어(Anomaly Score ≥ 70)가 임계치를 넘으면 30초 주기를 기다리지 않고 즉시 **경량 사전 경보 패킷(Early Warning Alert)**을 ACS로 전송하여 AGV 감속·대기 또는 우회 제어를 유도합니다.
   - **사후 분석 블랙박스 덤프**: 만약 통신 단절이 발생했다가 재연결되면, 단절 전후 **±60초 구간의 1초 단위 고해상도 링버퍼 데이터**를 압축 전송하여 정확한 근본 원인(Root Cause)을 자동 판별합니다.

---

## 2. 수집 항목 전수 조사 및 상세 명세 (18개 핵심 지표)

수집 지표는 **L1/L2 무선 물리·데이터링크 계층(8개)**, **L3/L4 네트워크·전송 계층(6개)**, **L7 응용·시스템 계층(4개)**으로 분류됩니다.

### 2.1 L1/L2 무선 물리 및 MAC 계층 지표 (Wi-Fi Physical & Data Link Layer)

| ID | 수집 항목 (영문/약어) | 설명 | 단위 및 기준 임계치 | 수집 위치 | 권장 주기 | 수집 부하 | 수집 방법 (Linux/표준) | 사전 감지 및 사후 분석 활용법 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **M01** | **수신 신호 강도**<br>`RSSI` | AGV 무선 랜카드가 수신하는 연결 AP의 전파 신호 세기 | `dBm`<br>• 정상: `≥ -67`<br>• 주의: `-68 ~ -74`<br>• 위험: `≤ -75` | AGV/AMR | 로컬 `1s`<br>(보고 `30s`) | **매우 낮음**<br>(CPU <0.1%, 커널 메모리 조회) | `/proc/net/wireless` 또는 `nl80211` (`iw dev wlan0 link`) | **[사전 감지]** 이동 경로상 RSSI의 기울기(`d(RSSI)/dt ≤ -2.5 dBm/s`)로 음영지역 진입 및 로밍 임박을 단절 10~20초 전에 사전 감지 |
| **M02** | **신호 대 잡음비**<br>`SNR` | 배경 잡음(Noise Floor) 대비 유효 신호 강도의 비율 | `dB`<br>• 정상: `≥ 25`<br>• 주의: `18 ~ 24`<br>• 위험: `≤ 17` | AGV/AMR,<br>AP/WLC | 로컬 `1s`<br>(보고 `30s`) | **매우 낮음**<br>(CPU <0.1%) | `RSSI - Noise_Floor` (`nl80211` survey dump) | **[사전/사후]** RSSI가 양호(`-62dBm`)한데도 연결이 끊길 때, 고주파 설비·인버터에 의한 **전자기파 간섭(EMI)** 원인 규명 |
| **M03** | **배경 잡음 준위**<br>`Noise Floor` | 해당 무선 채널의 기저 잡음 및 비-Wi-Fi 간섭 에너지 수준 | `dBm`<br>• 정상: `≤ -90`<br>• 주의: `-89 ~ -85`<br>• 위험: `≥ -84` | AGV/AMR,<br>AP/WLC | 로컬 `5s`<br>(보고 `30s`) | **낮음**<br>(인터페이스 Survey 읽기) | `iw dev wlan0 survey dump` / AP SNMP MIB | **[사후 분석]** 특정 구역/시간대에 용접기·모터 가동으로 발생하는 광대역 노이즈 유입 여부 판별 |
| **M04** | **물리 계층 전송 속도**<br>`Tx/Rx PHY Rate` | MCS(Modulation and Coding Scheme) 인덱스에 따른 실제 무선 링크 협상 속도 | `Mbps`<br>• 정상: `≥ 100`<br>• 주의: `24 ~ 99`<br>• 위험: `≤ 18` | AGV/AMR | 로컬 `1s`<br>(보고 `30s`) | **매우 낮음**<br>(CPU <0.1%) | `nl80211` `NL80211_ATTR_STA_INFO` (`tx_bitrate`, `rx_bitrate`) | **[사전 감지]** 패킷 유실이 일어나기 직전 와이파이 칩셋이 변조 방식을 낮추는 **Dynamic Rate Fallback** 현상을 포착하여 조기 경보 |
| **M05** | **802.11 MAC 재전송률**<br>`L2 Retry Rate` | 무선 프레임 전송 실패(ACK 미수신)로 인해 MAC 계층에서 재시도한 비율 | `%`<br>• 정상: `< 8%`<br>• 주의: `8 ~ 20%`<br>• 위험: `> 20%` | AGV/AMR,<br>AP/WLC | 로컬 `1s`<br>(보고 `30s`) | **낮음**<br>(드라이버 카운터 조회) | `ethtool -S wlan0` 또는 `nl80211` `tx_retries / tx_packets` | **[사전 감지]** TCP 계층 타임아웃이 발생하기 전 L2 무선 충돌 및 프레임 손실 징후를 가장 먼저 나타내는 핵심 선행 지표 |
| **M06** | **비콘 프레임 손실 수**<br>`Beacon Loss Count` | AP가 주기적(보통 102.4ms)으로 브로드캐스트하는 비콘을 놓친 횟수 | `count/s`<br>• 정상: `0 ~ 1`<br>• 주의: `2 ~ 4`<br>• 위험: `≥ 5` | AGV/AMR | 로컬 `1s`<br>(보고 `30s`) | **매우 낮음**<br>(커널 카운터) | `nl80211` `NL80211_STA_INFO_BEACON_LOSS` | **[사전/사후]** 연속 비콘 유실은 곧 L2 Deauth/Disassoc 발생 직전 상태를 의미하며, 은폐 노드(Hidden Node) 및 로밍 임계 상태 진단 |
| **M07** | **AP 로밍 소요 시간 및 횟수**<br>`Roaming Latency & BSSID` | 현재 연결된 AP의 MAC(BSSID) 변경 이벤트 및 핸드오버(Auth+Assoc+802.1X) 소요 시간 | `ms`<br>• 정상: `< 50ms`<br>• 주의: `50 ~ 150ms`<br>• 위험: `> 200ms` | AGV/AMR,<br>WLC | 이벤트 즉시<br>(로컬 `1s` 감시) | **매우 낮음**<br>(`wpa_supplicant` 이벤트 구독) | `wpa_cli` 컨트롤 소켓 이벤트(`CTRL-EVENT-CONNECTED` 등) 타임스탬프 차이 | **[사후 분석]** **Sticky Client(기존 AP를 놓지 않음)** 현상이나 802.11r 미적용/RADIUS 인증 지연으로 인한 로밍 중 소켓 끊김을 정확히 판별 |
| **M08** | **무선 채널 점유율**<br>`Channel Utilization` | 현재 주파수 채널에서 총 시간 대비 전송/수신/간섭으로 사용 중인 시간 비율 (CCA Busy) | `%`<br>• 정상: `< 40%`<br>• 주의: `40 ~ 65%`<br>• 위험: `> 65%` | AP/WLC,<br>AGV/AMR | `5s`<br>(보고 `30s`) | **낮음**<br>(Survey 카운터 비율 계산) | `iw survey dump` (`busy_time / active_time`) 및 WLC RRM 지표 | **[사후 분석]** 신호 세기(RSSI)와 SNR이 모두 정상인데도 통신이 지연·단절될 때, **동일 채널 과밀(Co-channel Contention) 및 AP 과부하**를 증명 |

---

### 2.2 L3/L4 네트워크 및 전송 계층 지표 (Network & Transport Layer)

| ID | 수집 항목 (영문/약어) | 설명 | 단위 및 기준 임계치 | 수집 위치 | 권장 주기 | 수집 부하 | 수집 방법 (Linux/표준) | 사전 감지 및 사후 분석 활용법 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **M09** | **게이트웨이 ICMP 왕복 지연**<br>`Gateway RTT` | AGV에서 기본 게이트웨이(L3 스위치)까지의 순수 무선 구간 Ping 왕복 시간 | `ms`<br>• 정상: `< 10ms`<br>• 주의: `10 ~ 40ms`<br>• 위험: `> 50ms` | AGV/AMR | 로컬 `2s`<br>(보고 `30s`) | **낮음**<br>(2초당 64B ICMP 패킷 1개) | Raw ICMP 소켓 또는 경량 `fping` / 비동기 ICMP 프로브 | **[사전/사후]** ACS 서버 응답 지연이 발생했을 때 **무선 구간(AGV↔GW) 문제인지 유선 백본/ACS 서버(GW↔ACS) 문제인지 경계를 분리** |
| **M10** | **네트워크 지터**<br>`RTT Jitter` | 연속된 패킷 왕복 지연 시간(RTT)의 편차(변동성) | `ms`<br>• 정상: `< 5ms`<br>• 주의: `5 ~ 20ms`<br>• 위험: `> 20ms` | AGV/AMR,<br>ACS | 로컬 `2s`<br>(보고 `30s`) | **매우 낮음**<br>(RTT 이동 표준편차 계산) | `mean(\|RTT_i - RTT_{i-1}\|)` 계산 | **[사전 감지]** 평균 RTT가 아직 낮더라도 스파이크성 지터가 급증하면 무선 큐잉(Bufferbloat)이나 로밍 탐색이 시작되었음을 사전 감지 |
| **M11** | **TCP 세그먼트 재전송 수**<br>`TCP Retransmits` | ACS 소켓 세션에서 ACK를 받지 못해 L4 TCP가 재전송한 세그먼트 수 | `count/s`<br>• 정상: `0`<br>• 주의: `1 ~ 3`<br>• 위험: `≥ 4` | AGV/AMR,<br>ACS | 로컬 `1s`<br>(보고 `30s`) | **매우 낮음**<br>(`NETLINK_INET_DIAG` 조회) | `ss -ti dst <ACS_IP>` 또는 Linux `tcp_info` 구조체의 `tcpi_total_retrans` | **[사전 감지 핵심]** TCP Exponential Backoff(재전송 타이머 지수 증가)에 빠져 30초 보고가 멈추기 직전 상태를 직접 포착 |
| **M12** | **TCP 회전율 추정 RTT**<br>`TCP Smoothed RTT (srtt)` | 커널 TCP 스택이 실제 통신 패킷으로 측정한 AGV↔ACS 종단 간 RTT | `ms`<br>• 정상: `< 15ms`<br>• 주의: `15 ~ 60ms`<br>• 위험: `> 60ms` | AGV/AMR,<br>ACS | 로컬 `1s`<br>(보고 `30s`) | **매우 낮음**<br>(추가 패킷 없이 커널 소켓 조회) | `tcp_info` 구조체의 `tcpi_rtt` / `tcpi_rttvar` | **[사전/사후]** 별도 Ping 패킷 없이도 실제 제어/보고 소켓이 겪고 있는 종단 간 지연 시간을 무부하로 추출 |
| **M13** | **소켓 송신 대기 큐 크기**<br>`Socket Send-Q` | 애플리케이션이 `send()` 했으나 상대방 ACK를 받지 못해 커널 송신 버퍼에 쌓여 있는 바이트 수 | `Bytes`<br>• 정상: `0`<br>• 주의: `1B ~ 4KB`<br>• 위험: `> 4KB` | AGV/AMR,<br>ACS | 로컬 `1s`<br>(보고 `30s`) | **매우 낮음**<br>(커널 소켓 버퍼 상태 조회) | `ss -tnp` (`Send-Q`) 또는 `ioctl(SIOCOUTQ)` | **[사전 감지]** 30초 보고는 아직 안 끊겼지만 `Send-Q`가 0으로 비워지지 않고 누적되면 수 초 내 소켓 Write Timeout이 발생할 것임을 100% 예고 |
| **M14** | **소켓 수신 대기 큐 크기**<br>`Socket Recv-Q` | 커널이 패킷은 수신했으나 AGV 또는 ACS 애플리케이션이 `recv()`로 읽어가지 못한 바이트 수 | `Bytes`<br>• 정상: `0`<br>• 주의: `1B ~ 2KB`<br>• 위험: `> 2KB` | AGV/AMR,<br>ACS | 로컬 `1s`<br>(보고 `30s`) | **매우 낮음**<br>(커널 소켓 버퍼 조회) | `ss -tnp` (`Recv-Q`) 또는 `ioctl(SIOCINQ)` | **[사후 분석 핵심]** 네트워크(Wi-Fi)는 멀쩡한데 **ACS 서버 워커 스레드 병목이나 AGV 제어 프로세스 데드락(Hang)**으로 보고/제어가 안 된 경우를 명확히 감별 |

---

### 2.3 L7 응용 및 시스템 계층 지표 (Application & Host System Layer)

| ID | 수집 항목 (영문/약어) | 설명 | 단위 및 기준 임계치 | 수집 위치 | 권장 주기 | 수집 부하 | 수집 방법 (Linux/표준) | 사전 감지 및 사후 분석 활용법 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **M15** | **ACS 상태 보고 도착 간격**<br>`Heartbeat Interval Delta` | ACS 서버가 실제로 AGV 상태 보고 패킷을 수신한 시간 간격 (기준: 30.0초) | `sec`<br>• 정상: `29.5 ~ 30.5s`<br>• 주의: `31 ~ 38s`<br>• 단절: `> 45s` | ACS 서버 | 매 보고 수신 시 및 `1s` 타임아웃 워치독 | **매우 낮음**<br>(ACS 인메모리 타임스탬프 비교) | ACS 소켓 수신 핸들러 타임스탬프 차분(`T_now - T_last`) | **[사전/사후]** 보고 간격이 `30.0s → 31.8s → 35.4s`로 흔들리는 현상(Arrival Drift)을 통해 완전 단절 전 불안정 AGV를 식별 |
| **M16** | **TCP Keepalive / 재연결 횟수**<br>`Socket Reconnect Count` | 소켓 세션이 끊어져 `SYN`부터 다시 맺은 횟수 및 `RST`/`FIN` 종료 사유 코드 | `count/hr`<br>• 정상: `0`<br>• 주의: `1 ~ 2`<br>• 위험: `≥ 3` | AGV/AMR,<br>ACS | 이벤트 즉시 | **매우 낮음**<br>(소켓 라이프사이클 로깅) | 애플리케이션 소켓 래퍼 및 eBPF `inet_sock_set_state` | **[사후 분석]** 단절이 정상 종료(`FIN`)인지, 강제 리셋(`RST`)인지, 무응답 타임아웃(`ETIMEDOUT`)인지 구분 |
| **M17** | **AGV CPU 및 SoftIRQ 부하**<br>`Host CPU & NET_RX SoftIRQ` | AGV 온보드 컴퓨터(IPC/SBC)의 CPU 사용률 및 네트워크 인터럽트 처리 지연 | `%`<br>• 정상: `< 60%`<br>• 주의: `60 ~ 85%`<br>• 위험: `> 85%` | AGV/AMR | 로컬 `5s`<br>(보고 `30s`) | **매우 낮음**<br>(`/proc/stat`, `/proc/softirqs`) | `/proc/stat` 및 `/proc/softirqs` 조회 | **[사후 분석]** SLAM 라이다 연산 폭주로 인해 AGV CPU가 100%에 도달하여 네트워크 스레드가 스케줄링되지 못한 **내부 자원 고갈 장애** 감별 |
| **M18** | **AGV 주행 좌표 및 속도**<br>`AGV Pose (X, Y) & Velocity` | 네트워크 지표 수집 시점의 AGV 공장 맵 내 좌표 `(x, y)` 및 주행 속도 | `m`, `m/s` | AGV/AMR | 로컬 `1s`<br>(보고 `30s`) | **없음**<br>(기존 주행 제어 데이터 참조) | ROS/내비게이션 스택 토픽 메모리 공유 | **[공간 상관 분석]** 네트워크 품질 저하 지표를 `(X, Y)` 좌표에 매핑하여 **공장 내 상습 음영 구역(Dead Zone) 히트맵** 자동 생성 |

---

## 3. 사전 감지(Pre-detection) 및 사후 분석(Post-mortem RCA) 방법론

### 3.1 실시간 사전 감지(Pre-Detection) 멀티-메트릭 위험도 스코어링
단일 지표(예: RSSI 하나)만으로는 오탐(False Positive)이 발생할 수 있으므로, L1/L2/L4 선행 지표를 결합한 **가중 지수이동평균(EWMA) 위험도 점수(`Anomaly Score`, 0~100점)**를 1초마다 계산합니다.

$$\text{RiskScore}(t) = w_1 \cdot S_{\text{RSSI\_drop}}(t) + w_2 \cdot S_{\text{SNR}}(t) + w_3 \cdot S_{\text{L2\_Retry}}(t) + w_4 \cdot S_{\text{TCP\_Retrans}}(t) + w_5 \cdot S_{\text{SendQ}}(t)$$

- **가중치 배분**:
  - $w_1 (0.25)$: RSSI 절대값(`<-72dBm`) 및 5초간 하락 기울기(`d(RSSI)/dt`)
  - $w_2 (0.15)$: SNR 저하(` < 20dB`)
  - $w_3 (0.20)$: L2 Retry Rate 급증(`> 15%`) 및 PHY Rate 급락
  - $w_4 (0.25)$: TCP Retransmits 발생(`≥ 2/s`) 및 Gateway RTT 상승
  - $w_5 (0.15)$: Socket `Send-Q` 잔류 바이트 누적(`> 0 Bytes` 3초 이상 지속)
- **사전 감지 동작 흐름**:
  - `RiskScore < 45`: **정상 (Normal / Emerald)** — 평시 30초 보고 유지.
  - `45 ≤ RiskScore < 70`: **주의 (Caution)** — 내부 링버퍼 고해상도 스냅샷 잠금(Lock).
  - `RiskScore ≥ 70`: **사전 감지 경보 (Pre-Disconnect Warning / Amber)** — **소켓이 실제로 끊어지기 평균 12~22초 전에 ACS로 조기 경보 패킷 즉시 푸시** → ACS는 해당 AGV에 안전 감속 또는 AP 강제 로밍(802.11v BSS Transition) 명령 하달.

### 3.2 사후 원인 분석(Post-mortem RCA) 4대 핵심 장애 시나리오 판별 매트릭스

단절 발생 후 수집된 고해상도 시계열 패턴(시그니처)을 비교하여 아래 4가지 근본 원인을 자동 분류합니다.

| 시나리오 ID | 장애 유형 | 핵심 시계열 시그니처 (사후 분석 판별 조건) | 권장 해결 및 조치 방안 |
| :--- | :--- | :--- | :--- |
| **SCN-01** | **AP 로밍 실패 / Sticky Client** | • AGV 이동 중 `RSSI`가 `-78dBm` 이하로 완만히 하락<br>• 인접 구역 진입에도 `BSSID`가 바뀌지 않다가 뒤늦게 변경 시도<br>• 로밍 순간 `Roaming Latency > 250ms` 및 `Beacon Loss` 급증 후 TCP 단절 | • AGV 무선 드라이버 Roaming Threshold를 `-70dBm`으로 상향 조정<br>• AP/WLC에 **802.11k/v/r (Fast BSS Transition)** 활성화 |
| **SCN-02** | **물리적 음영지역 및 전자기 간섭 (Dead Zone / EMI)** | • 특정 좌표 `(X, Y)` 진입 시 `RSSI` 급락(`≤ -82dBm`) 또는 고주파 설비 가동 시 `Noise Floor` 급상승(`≥ -82dBm`, `SNR ≤ 12dB`)<br>• `L2 Retry Rate > 35%`, `PHY Rate`가 `6Mbps`까지 급락 | • 히트맵에 표시된 음영 좌표에 지향성 안테나/보조 AP 증설<br>• 2.4GHz 대역 사용 배제 및 5GHz DFS/비간섭 채널로 고정 |
| **SCN-03** | **AP 과부하 및 동일 채널 혼잡 (Channel Contention)** | • **`RSSI`와 `SNR`은 양호(`-60dBm`, `28dB`)함에도 불구하고** `Channel Utilization > 75%` 기록<br>• `Gateway RTT` 및 `Jitter`가 100ms 이상 치솟으며 `TCP Retransmits` 다발 | • 해당 AP에 집중된 클라이언트를 인접 AP로 로드밸런싱<br>• 20MHz 채널 폭 최적화 및 불필요한 멀티캐스트/브로드캐스트 차단 |
| **SCN-04** | **AGV/ACS 소켓 블로킹 및 시스템 병목 (Socket Hang)** | • **`RSSI`, `SNR`, `Gateway ICMP RTT`는 모두 정상(`-58dBm`, `4ms`)**<br>• 그러나 ACS 측 또는 AGV 측 `Socket Recv-Q`가 급증하고 `AGV CPU > 92%` 기록 후 30초 보고 타임아웃 발생 | • 네트워크 문제가 아닌 **애플리케이션/OS 병목**으로 판정 (무선 공사 불필요)<br>• AGV 내비게이션(SLAM) 스레드와 네트워크 보고 스레드 간 CPU 코어 분리(`taskset`) 및 비동기 논블로킹 소켓 적용 |
