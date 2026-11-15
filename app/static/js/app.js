/**
 * AGV/AMR Network Telemetry & RCA Center — Frontend Application (app.js)
 * Implements:
 *  1. Live 1s/30s TSDB Telemetry Stream & KPI Dashboard
 *  2. Interactive High-DPI 2D Smart Factory Floor Plan & Coverage/Dead-Zone Heatmap
 *  3. Live Failure Scenario Injector (SCN-01 ~ SCN-04) & Real-Time Mini Time-Series
 *  4. Pre-Detection & Post-Mortem RCA Lab (3-Layer Synchronized Charts + Decision Tree)
 *  5. 18-Metric Telemetry Encyclopedia (8 Required Spec Fields, Layer/Location Filters)
 *  6. 3-Stage Hybrid Telemetry Architecture, Protocol JSON Inspector & Bandwidth Calculator
 *  7. 7-Step Interactive Spotlight Guided Tour & Dual Theme (Dark Slate / Light Enterprise)
 */

(function () {
  "use strict";

  // ==========================================================================
  // 1. Global Application State
  // ==========================================================================
  const state = {
    theme: "dark",
    activeTab: "tab-live",

    // Tab 1: Live Fleet & Map State
    selectedAgvId: "AGV-02",
    showHeatmap: true,
    showDangerZones: true,
    overview: null,
    agvTimeseries: {
      agv_id: "AGV-02",
      series: [],
      reports_30s: []
    },
    agvHoverId: null,

    // Tab 2: Pre-Detection & RCA Lab State
    scenariosMap: {},
    selectedScenarioCode: "SCN-01",
    rcaCursorOffset: -18,
    rcaPlaying: false,
    rcaPlayTimer: null,

    // Tab 3: Metrics Catalog State
    metricsCatalog: [],
    selectedMetricId: "M01",
    catalogLayerFilter: "ALL",
    catalogLocFilter: "ALL",
    catalogSearchQuery: "",

    // Tab 4: Hybrid Architecture State
    hybridArchSpec: null,
    activePacketType: "piggyback",

    // Spotlight Guided Tour State
    tourActive: false,
    tourStepIndex: 0
  };

  // ==========================================================================
  // 2. Built-in Fallback Data (Ensures Instant Zero-Latency Rendering)
  // ==========================================================================
  function generateFallbackTimeline(code) {
    const pts = [];
    for (let t = -89; t <= 30; t++) {
      let rssi = -59 + Math.sin(t * 0.15) * 1.5;
      let snr = 31;
      let noise = -91;
      let phy = 144;
      let l2Retry = 3.2;
      let beaconLoss = 0;
      let roamMs = 0;
      let chanUtil = 26;
      let gwRtt = 4.2;
      let jitter = 1.2;
      let tcpRetrans = 0;
      let sendQ = 0;
      let recvQ = 0;
      let cpu = 34;
      let risk = 12;
      let conn = "CONNECTED";
      let note = "정상 주행 및 1초 로컬 링버퍼 수집 중";

      if (code === "SCN-01") {
        // AP Roaming Failure (Sticky Client)
        if (t >= -35 && t < 0) {
          const p = (t + 35) / 35;
          rssi = Math.round((-60 - p * 23) * 10) / 10;
          snr = Math.round(30 - p * 16);
          phy = Math.max(12, Math.round(144 - p * 130));
          l2Retry = Math.round((4 + Math.pow(p, 1.6) * 38) * 10) / 10;
          beaconLoss = t >= -18 ? Math.min(8, Math.floor((t + 20) / 3)) : 0;
          roamMs = t >= -5 ? 340 : (t >= -12 ? 95 : 0);
          gwRtt = Math.round((4.5 + Math.pow(p, 2) * 145) * 10) / 10;
          jitter = Math.round((1.5 + Math.pow(p, 1.8) * 48) * 10) / 10;
          tcpRetrans = t >= -20 ? Math.min(9, Math.floor((t + 22) / 3)) : 0;
          sendQ = t >= -18 ? Math.round((t + 19) * 520) : 0;
          risk = Math.min(94, Math.round((15 + Math.pow(p, 1.35) * 82) * 10) / 10);
          if (t >= -18) {
            conn = "PRE_WARNING";
            note = "사전 감지 경보! RSSI 급락(-76dBm) 및 Sticky Client 로밍 지연 감지";
          }
        } else if (t >= 0 && t < 16) {
          rssi = -84; snr = 11; phy = 6; l2Retry = 48; beaconLoss = 9; roamMs = 380;
          gwRtt = 280; jitter = 85; tcpRetrans = 11; sendQ = 14800; risk = 98;
          conn = "DISCONNECTED";
          note = "30초 소켓 보고 타임아웃 단절! (802.1X 재인증 타임아웃)";
        } else if (t >= 16) {
          rssi = -58; snr = 33; phy = 144; l2Retry = 2.8; roamMs = 18;
          gwRtt = 3.8; tcpRetrans = 0; sendQ = 0; risk = 14;
          conn = "CONNECTED";
          note = "신규 AP(AP-ZONE-B) 로밍 완료 및 120초 블랙박스 링버퍼 덤프 전송";
        }
      } else if (code === "SCN-02") {
        // Physical Dead Zone & Welding EMI
        if (t >= -30 && t < 0) {
          const p = (t + 30) / 30;
          rssi = Math.round((-62 - p * 22) * 10) / 10;
          noise = Math.round(-91 + p * 16);
          snr = Math.max(8, Math.round(rssi - noise));
          l2Retry = Math.round((5 + p * 44) * 10) / 10;
          gwRtt = Math.round((5 + Math.pow(p, 2) * 160) * 10) / 10;
          tcpRetrans = t >= -16 ? Math.floor((t + 18) / 2.5) : 0;
          sendQ = t >= -16 ? (t + 17) * 480 : 0;
          risk = Math.min(93, Math.round((16 + Math.pow(p, 1.3) * 80) * 10) / 10);
          if (t >= -16) {
            conn = "PRE_WARNING";
            note = "사전 감지 경보! 철제 랙 음영 및 용접 EMI 노이즈로 SNR 12dB 이하 급락";
          }
        } else if (t >= 0 && t < 15) {
          rssi = -85; noise = -75; snr = 10; l2Retry = 54; gwRtt = 310;
          tcpRetrans = 12; sendQ = 16200; risk = 99; conn = "DISCONNECTED";
          note = "물리적 전파 음영 + 고주파 간섭으로 L2 프레임 유실 및 소켓 단절";
        }
      } else if (code === "SCN-03") {
        // Channel Congestion
        if (t >= -28 && t < 0) {
          const p = (t + 28) / 28;
          rssi = -60; snr = 29;
          chanUtil = Math.min(92, Math.round(32 + p * 58));
          l2Retry = Math.round((6 + p * 29) * 10) / 10;
          gwRtt = Math.round((5 + Math.pow(p, 2) * 195) * 10) / 10;
          jitter = Math.round((2 + p * 54) * 10) / 10;
          tcpRetrans = t >= -15 ? Math.floor((t + 16) / 2.5) : 0;
          sendQ = t >= -15 ? (t + 16) * 510 : 0;
          risk = Math.min(91, Math.round((18 + Math.pow(p, 1.35) * 76) * 10) / 10);
          if (t >= -15) {
            conn = "PRE_WARNING";
            note = "사전 감지 경보! RSSI(-60dBm) 양호하나 채널 점유율(CCA 82%) 포화 감지";
          }
        } else if (t >= 0 && t < 15) {
          rssi = -60; snr = 28; chanUtil = 94; l2Retry = 38; gwRtt = 340;
          tcpRetrans = 10; sendQ = 13500; risk = 96; conn = "DISCONNECTED";
          note = "동일 채널 CSMA/CA 경쟁 포화로 인한 TCP RTO 연속 타임아웃 단절";
        }
      } else if (code === "SCN-04") {
        // Socket Hang & CPU Bottleneck
        if (t >= -25 && t < 0) {
          const p = (t + 25) / 25;
          rssi = -58; snr = 32; chanUtil = 25; gwRtt = 4.1; l2Retry = 2.5;
          cpu = Math.min(99, Math.round(42 + p * 57));
          recvQ = t >= -16 ? Math.round((t + 17) * 640) : 0;
          sendQ = t >= -14 ? Math.round((t + 15) * 490) : 0;
          risk = Math.min(90, Math.round((14 + Math.pow(p, 1.4) * 78) * 10) / 10);
          if (t >= -14) {
            conn = "PRE_WARNING";
            note = "사전 감지 경보! 무선(RSSI/RTT) 정상이나 AGV CPU(95%) 및 소켓 Recv-Q 적체 감지";
          }
        } else if (t >= 0 && t < 14) {
          rssi = -58; snr = 32; gwRtt = 4.3; cpu = 99.2; recvQ = 18400; sendQ = 12400;
          risk = 97; conn = "DISCONNECTED";
          note = "AGV 내비게이션(SLAM) 스레드 CPU 독점으로 소켓 워커 블로킹 타임아웃";
        }
      }

      const is30s = (t === -60 || t === -30 || t === 0 || t === 30);
      const repStatus = t === 0 ? "TIMEOUT_MISSED" : (is30s ? "OK" : null);

      pts.push({
        offset_sec: t,
        rssi: rssi,
        snr: snr,
        noise_floor: noise,
        phy_rate: phy,
        l2_retry_rate: l2Retry,
        beacon_loss: beaconLoss,
        roaming_ms: roamMs,
        channel_util: chanUtil,
        gw_rtt_ms: gwRtt,
        jitter_ms: jitter,
        tcp_retrans: tcpRetrans,
        send_q_bytes: sendQ,
        recv_q_bytes: recvQ,
        cpu_load: cpu,
        risk_score: risk,
        conn_state: conn,
        is_30s_report_tick: is30s,
        acs_report_status: repStatus,
        annotation: note
      });
    }
    return pts;
  }

  const FALLBACK_SCENARIOS = {
    "SCN-01": {
      code: "SCN-01",
      title: "AP 로밍 실패 및 Sticky Client 현상",
      subtitle: "Zone-A에서 Zone-B 이동 중 기존 AP(-81dBm) 고착 및 802.1X 재인증 지연(340ms)",
      target_agv: "AGV-02",
      zone: "ZONE-A → ZONE-B 경계",
      lead_time_sec: 18,
      pre_detect_offset_sec: -18,
      disconnect_offset_sec: 0,
      recovery_offset_sec: 16,
      legacy_30s_view: "T-30s 정기 보고 시점에는 RSSI -66dBm으로 정상 보고되었습니다. 이후 30초 사이에 AGV가 이동하며 급격한 신호 감쇠와 로밍 실패가 일어났으나 30초 주기는 이를 전혀 볼 수 없었고 T=0s에 원인 불명의 Socket Timeout이 발생했습니다.",
      hybrid_1s_view: "AGV 온보드 1초 링버퍼가 RSSI 하락 기울기(-2.6 dBm/s)와 L2 재전송 상승을 포착하여 단절 18초 전(T-18s)에 EWMA 위험도 72점을 돌파, ACS로 즉시 조기 경보를 전송하여 감속 및 선제 로밍(802.11v)을 유도합니다.",
      root_cause: "AGV 무선 NIC 드라이버의 로밍 임계치가 너무 낮게(-80dBm) 설정되어 인접 AP(AP-ZONE-B)로 제때 핸드오버하지 않는 Sticky Client 현상이 발생했으며, 802.11r 미적용으로 EAP-TLS 인증에 340ms 이상 소요되어 TCP 세션이 단절됨.",
      signature_metrics: [
        "RSSI: -61dBm → -83dBm 급락",
        "Roaming Latency: 340ms (기준 <50ms)",
        "Beacon Loss: 8 count/s 급증",
        "L2 Retry Rate: 42.5% 돌파"
      ],
      decision_tree: [
        { step: 1, question: "L1 무선 수신 신호 강도(RSSI)가 정상(-67dBm 이상)인가?", observation: "RSSI가 -83dBm까지 지속 하락 (기울기 -2.6dBm/s)", result: "FAIL", implication: "무선 물리 계층 신호 감쇠 문제 확인" },
        { step: 2, question: "배경 잡음(Noise Floor) 상승에 의한 EMI 간섭인가?", observation: "Noise Floor는 -91dBm으로 일정 유지됨", result: "PASS", implication: "외부 전자기파 간섭(EMI) 배제" },
        { step: 3, question: "구역 이동 중 BSSID 전환 지연(Sticky Client)이 발생했는가?", observation: "X=48m 통과 후에도 기존 AP 고착 후 Roaming 340ms 발생", result: "FAIL", implication: "AP 로밍 임계치 미흡 및 802.11r 미작동 확정" },
        { step: 4, question: "최종 근본 원인 판정 (Automated RCA Verdict)", observation: "SCN-01: AP 로밍 실패 및 Sticky Client 장애 (신뢰도 98%)", result: "FAIL", implication: "802.11k/v/r 활성화 및 로밍 임계치 -70dBm 상향 권고" }
      ],
      recommended_actions: [
        "AGV wpa_supplicant 로밍 탐색 임계치(bgscan)를 -80dBm에서 -70dBm으로 상향 조정",
        "무선 컨트롤러(WLC)에 802.11k(이웃 AP 리스트), 802.11v(BSS Transition), 802.11r(Fast Roaming) 활성화",
        "사전 감지(Risk ≥ 70) 경보 수신 시 ACS에서 AGV 주행 속도를 0.5m/s로 감속 제어"
      ],
      timeline: generateFallbackTimeline("SCN-01")
    },
    "SCN-02": {
      code: "SCN-02",
      title: "물리적 전파 음영 구역 & 용접기 EMI 간섭",
      subtitle: "철제 고층 랙 통로 진입 및 로봇 용접 셀 고주파 노이즈(-75dBm) 유입",
      target_agv: "AGV-03",
      zone: "ZONE-C 용접/랙 구역",
      lead_time_sec: 16,
      pre_detect_offset_sec: -16,
      disconnect_offset_sec: 0,
      recovery_offset_sec: 15,
      legacy_30s_view: "T-30s 보고에서는 모든 상태가 정상이었으나, AGV가 철제 랙 음영 구역과 용접기 근처를 통과하는 15초 동안 신호가 끊겨 T=0s 보고가 누락되었습니다. 재연결 후에는 이미 음영 구역을 빠져나와 원인을 재현할 수 없습니다.",
      hybrid_1s_view: "1초 로컬 링버퍼가 Noise Floor 급상승(-91 → -75dBm)과 SNR 급락(10dB), PHY Rate Fallback(144 → 6Mbps)을 실시간 기록하여 단절 16초 전에 조기 경보를 발령하고, AGV 좌표(X,Y)와 결합해 음영 히트맵에 자동 마킹합니다.",
      root_cause: "철제 랙 구조물에 의한 다중경로 페이딩(Multipath Fading)과 스폿 용접기 가동 시 발생하는 광대역 전자기파 간섭(EMI)이 겹쳐 SNR이 10dB 이하로 붕괴, 802.11 프레임 CRC 에러 및 재전송률 54% 초과로 연결이 끊어짐.",
      signature_metrics: [
        "Noise Floor: -91dBm → -75dBm 급상승",
        "SNR: 31dB → 10dB 붕괴",
        "PHY Rate: 144Mbps → 6Mbps 급락",
        "L2 Retry Rate: 54.0% 폭증"
      ],
      decision_tree: [
        { step: 1, question: "무선 신호 품질(RSSI 및 SNR)이 정상 범위인가?", observation: "RSSI -85dBm, SNR 10dB로 심각한 물리 계층 품질 붕괴", result: "FAIL", implication: "L1 물리 전파 환경 문제 확인" },
        { step: 2, question: "배경 잡음 준위(Noise Floor)가 비정상적으로 상승했는가?", observation: "Noise Floor가 -91dBm에서 -75dBm으로 16dB 급상승", result: "FAIL", implication: "고주파 설비(용접기/인버터) EMI 간섭 유입 확인" },
        { step: 3, question: "특정 공장 좌표(X,Y) 구간에서 반복 발생하는가?", observation: "좌표 (50m, 15m) 철제 랙 및 (80m, 40m) 용접 셀 집중", result: "FAIL", implication: "공간적 전파 음영 및 간섭 구역(Dead Zone) 확정" },
        { step: 4, question: "최종 근본 원인 판정 (Automated RCA Verdict)", observation: "SCN-02: 물리적 음영 구역 및 광대역 EMI 간섭 (신뢰도 97%)", result: "FAIL", implication: "음영 좌표 지향성 AP 증설 및 5GHz 비간섭 채널 분리 권고" }
      ],
      recommended_actions: [
        "2D 히트맵에서 식별된 철제 랙 통로(X=45~58m) 상단에 지향성 패치 안테나 보조 AP 증설",
        "용접 셀 주변 2.4GHz 대역 사용을 전면 중단하고 5GHz UNII-2e/3 고출력 채널로 고정",
        "AGV 온보드 무선 안테나를 차체 하단에서 상단 마스트(높이 1.8m)로 이설하여 가시선(LoS) 확보"
      ],
      timeline: generateFallbackTimeline("SCN-02")
    },
    "SCN-03": {
      code: "SCN-03",
      title: "AP 과부하 및 동일 채널 혼잡 (Channel Contention)",
      subtitle: "RSSI(-60dBm)는 완벽히 정상이나 채널 점유율(CCA Busy 94%) 포화로 통신 마비",
      target_agv: "AGV-04",
      zone: "ZONE-B 물류 집결지",
      lead_time_sec: 15,
      pre_detect_offset_sec: -15,
      disconnect_offset_sec: 0,
      recovery_offset_sec: 15,
      legacy_30s_view: "현장 엔지니어가 전파 측정기로 확인하면 RSSI가 -60dBm으로 매우 강하게 잡히기 때문에 왜 30초 소켓 보고가 끊기는지 전혀 설명하지 못하는 대표적인 미스터리 장애입니다.",
      hybrid_1s_view: "1초 하이브리드 수집기가 RSSI(-60dBm)와 SNR(28dB)은 정상인 반면 Channel Utilization(94%)과 Gateway RTT(340ms), Jitter(56ms)만 단독 폭증하는 패턴을 포착해 단절 15초 전 조기 경보 및 채널 과밀 진단을 내립니다.",
      root_cause: "물류 피크 시간대 특정 구역(ZONE-B)에 AGV 및 작업자 단말이 몰리면서 동일 채널 CSMA/CA 매체 접근 대기(CCA Busy)가 90%를 초과, 무선 에어타임 고갈로 인해 TCP 패킷과 ACK가 지연되어 소켓 타임아웃 발생.",
      signature_metrics: [
        "RSSI / SNR: -60dBm / 28dB (정상 유지!)",
        "Channel Utilization: 94% (위험 >65%)",
        "Gateway RTT: 4.2ms → 340ms 폭증",
        "RTT Jitter: 56ms 스파이크"
      ],
      decision_tree: [
        { step: 1, question: "L1 무선 신호 강도(RSSI) 및 SNR이 정상인가?", observation: "RSSI -60dBm, SNR 28dB로 전파 세기는 매우 양호함", result: "PASS", implication: "음영 구역이나 로밍 실패가 아님을 즉시 증명" },
        { step: 2, question: "무선 채널 점유율(Channel Utilization / CCA)이 여유로운가?", observation: "Channel Utilization이 94%로 에어타임 완전 포화 상태", result: "FAIL", implication: "동일 채널 간섭 또는 과다 단말 접속에 의한 매체 경쟁 확인" },
        { step: 3, question: "게이트웨이 ICMP RTT 및 지터가 함께 상승했는가?", observation: "GW RTT가 340ms, TCP Retransmits가 10/s로 동반 급증", result: "FAIL", implication: "무선 MAC 큐잉 지연(Bufferbloat)에 의한 전송 계층 마비" },
        { step: 4, question: "최종 근본 원인 판정 (Automated RCA Verdict)", observation: "SCN-03: AP 과부하 및 동일 채널 혼잡 장애 (신뢰도 96%)", result: "FAIL", implication: "AP 채널 분산(20MHz), Client Load Balancing 및 멀티캐스트 제한" }
      ],
      recommended_actions: [
        "5GHz 대역 채널 본딩을 80MHz에서 20MHz로 축소하여 비중첩 채널 수를 확보하고 동일 채널 간섭(CCI) 제거",
        "WLC에서 AGV 전용 SSID와 일반 업무용/CCTV SSID의 무선 채널 및 대역을 물리적으로 분리",
        "AP당 최대 접속 클라이언트 수 제한(Load Balancing) 및 WMM(Wi-Fi Multimedia)에서 제어 패킷에 최고 우선순위(VO) 부여"
      ],
      timeline: generateFallbackTimeline("SCN-03")
    },
    "SCN-04": {
      code: "SCN-04",
      title: "AGV/ACS 소켓 블로킹 및 시스템 병목 (Socket Hang)",
      subtitle: "무선 네트워크(RSSI/RTT)는 100% 정상이나 AGV CPU 폭주 및 소켓 큐 적체로 단절",
      target_agv: "AGV-05",
      zone: "ZONE-D 정밀 도킹 구역",
      lead_time_sec: 14,
      pre_detect_offset_sec: -14,
      disconnect_offset_sec: 0,
      recovery_offset_sec: 14,
      legacy_30s_view: "ACS 화면에는 단순히 'AGV-05 30초 보고 미수신(연결 끊김)'으로만 표시되므로, 현장에서는 무조건 '공장 와이파이 문제'로 오인하여 불필요한 AP 공사나 안테나 교체 비용을 낭비하게 됩니다.",
      hybrid_1s_view: "1초 수집 데이터에서 RSSI(-58dBm), 채널 점유율(25%), 게이트웨이 Ping RTT(4.1ms)가 모두 완벽히 정상인데도 AGV CPU(99.2%)와 소켓 Recv-Q/Send-Q만 급증한 것을 확인하여 '무선 장애가 아닌 S/W 소켓 블로킹'임을 단절 14초 전에 판별합니다.",
      root_cause: "정밀 도킹 구간에서 AGV 온보드 라이다 SLAM 연산 스레드가 CPU 코어를 99% 독점하면서 네트워크 보고 스레드가 스케줄링되지 못했고, 커널 소켓 버퍼(Recv-Q 18.4KB, Send-Q 12.4KB)가 가득 차 30초 상태 보고가 멈춘 소프트웨어 장애.",
      signature_metrics: [
        "RSSI / GW RTT: -58dBm / 4.1ms (무선 완벽 정상!)",
        "AGV Host CPU: 99.2% (임계 >85%)",
        "Socket Recv-Q: 18,400 Bytes 적체",
        "Socket Send-Q: 12,400 Bytes 적체"
      ],
      decision_tree: [
        { step: 1, question: "L1/L2 무선 신호(RSSI/SNR) 및 채널 점유율이 정상인가?", observation: "RSSI -58dBm, SNR 32dB, Ch.Util 25%로 완벽히 정상", result: "PASS", implication: "Wi-Fi 물리/MAC 계층 이상 없음" },
        { step: 2, question: "L3 게이트웨이 ICMP Ping 왕복 지연(GW RTT)이 정상인가?", observation: "Gateway RTT 4.1ms, Jitter 1.1ms로 네트워크 경로 정상", result: "PASS", implication: "무선 및 유선 스위치 네트워크 구간 100% 정상 증명!" },
        { step: 3, question: "L4 소켓 버퍼(Send-Q/Recv-Q) 및 L7 호스트 CPU 부하가 정상인가?", observation: "AGV CPU 99.2% 폭주 및 소켓 Recv-Q 18.4KB 미처리 적체", result: "FAIL", implication: "애플리케이션 프로세스 데드락/스케줄링 기아(Starvation) 확인" },
        { step: 4, question: "최종 근본 원인 판정 (Automated RCA Verdict)", observation: "SCN-04: AGV/ACS 애플리케이션 소켓 블로킹 & CPU 병목 (신뢰도 99%)", result: "FAIL", implication: "무선 공사 불필요! SLAM 연산과 통신 스레드 CPU 코어 분리 권고" }
      ],
      recommended_actions: [
        "Linux taskset / cgroups를 사용해 AGV SLAM 내비게이션 프로세스와 ACS 통신 에이전트의 CPU 코어를 물리적으로 분리(CPU Affinity)",
        "AGV-ACS 통신 소켓을 블로킹(Blocking) I/O에서 비동기 epoll 논블로킹(Non-blocking) 아키텍처로 개선",
        "무선 인프라(AP)는 정상이므로 불필요한 무선 장비 증설/재배치 작업 즉시 중단"
      ],
      timeline: generateFallbackTimeline("SCN-04")
    }
  };

  // ==========================================================================
  // 3. Protocol JSON Payload Templates for Tab 4
  // ==========================================================================
  const PACKET_EXAMPLES = {
    piggyback: {
      desc: "Stage 2: 기존 30초 주기 ACS 상태 보고 패킷에 지난 30초간의 1초 링버퍼 핵심 통계 요약(`net_telemetry_30s`, 약 96 Bytes)을 피기백하여 추가 소켓 연결 없이 전송합니다.",
      payload: {
        msg_type: "ACS_AGV_STATUS_REPORT_30S",
        agv_id: "AGV-02",
        timestamp_ms: 1763182050000,
        hb_seq: 1428,
        hb_interval_sec: 30.02,
        agv_operation: {
          pose_x: 46.2,
          pose_y: 15.0,
          velocity_mps: 1.4,
          battery_pct: 84,
          mission_state: "CARRYING_PALLET"
        },
        net_telemetry_30s_piggyback: {
          window_samples: 30,
          bssid_current: "00:1A:2B:3C:4D:01",
          ap_zone: "ZONE-A",
          rssi_dbm: { min: -68.0, avg: -61.4, std: 2.1, slope_5s: -0.4 },
          snr_db: { min: 24.0, avg: 29.5 },
          l2_retry_pct: { avg: 3.4, max: 7.8 },
          channel_util_pct: { avg: 26.0, max: 34.0 },
          roaming_events_30s: 0,
          gw_rtt_ms: { avg: 4.3, max: 9.2, jitter: 1.4 },
          tcp_retrans_delta: 0,
          socket_q_max_bytes: { send_q: 0, recv_q: 0 },
          host_cpu_max_pct: 41.2,
          ewma_risk_score_max: 16.5,
          conn_health_verdict: "CONNECTED"
        }
      }
    },
    early_warning: {
      desc: "Stage 3-A: 1초 로컬 감시 중 EWMA 위험도가 70점을 돌파하면(단절 14~18초 전) 30초 주기를 기다리지 않고 즉시 ACS로 경량 조기 경보 패킷을 푸시하여 AGV 감속/선제 로밍을 유도합니다.",
      payload: {
        msg_type: "ACS_NET_EARLY_WARNING_PUSH",
        priority: "URGENT_PRE_DISCONNECT",
        agv_id: "AGV-02",
        timestamp_ms: 1763182062000,
        estimated_lead_time_sec: 18.0,
        pose: { x: 48.5, y: 15.0, velocity_mps: 1.5 },
        risk_assessment: {
          ewma_risk_score: 74.8,
          threshold: 70.0,
          conn_state: "PRE_WARNING",
          predicted_scenario: "SCN-01 (AP_ROAMING_STICKY_CLIENT)",
          primary_triggers: [
            "rssi_dbm dropped to -76.5 dBm (slope -2.7 dBm/s)",
            "l2_retry_rate spiked to 26.4%",
            "socket send_q_bytes accumulated to 4,620 Bytes"
          ]
        },
        recommended_acs_control: {
          action: "DECREASE_SPEED_AND_TRIGGER_80211V_ROAM",
          target_speed_mps: 0.4,
          candidate_target_ap: "AP-ZONE-B (00:1A:2B:3C:4D:02)"
        }
      }
    },
    blackbox_dump: {
      desc: "Stage 3-B: 불가피하게 통신 단절이 발생했다가 재연결된 직후, AGV 메모리 링버퍼에 보존된 단절 전후 ±60초(총 120초) 1초 해상도 시계열 블록을 압축 전송하여 근본 원인을 100% 규명합니다.",
      payload: {
        msg_type: "ACS_POST_MORTEM_BLACKBOX_DUMP",
        incident_id: "INC-2026-01",
        agv_id: "AGV-02",
        ts_pre_detected_ms: 1763182062000,
        ts_disconnected_ms: 1763182080000,
        ts_reconnected_ms: 1763182096000,
        actual_lead_time_sec: 18.0,
        automated_rca_verdict: {
          scenario_code: "SCN-01",
          root_cause: "AP Roaming Failure / Sticky Client (802.1X Auth 340ms)",
          confidence: 0.98
        },
        ring_buffer_1s_dump: {
          resolution_sec: 1,
          window_range_sec: "[-60s .. +60s]",
          total_points: 120,
          columns: ["offset_s", "x", "y", "rssi", "snr", "l2_retry", "roam_ms", "gw_rtt", "tcp_retrans", "send_q", "recv_q", "cpu", "risk"],
          sample_rows_around_drop: [
            [-18, 48.5, 15.0, -76.0, 16, 24.2,   0,  48.0, 4,  6400, 0, 38.0, 74.5],
            [ -5, 51.2, 15.0, -81.5, 12, 39.8,  95, 142.0, 8, 11200, 0, 41.0, 89.2],
            [  0, 52.0, 15.0, -84.0, 10, 48.5, 340, 280.0, 11, 14800, 0, 42.0, 98.0],
            [ 16, 55.4, 15.0, -58.5, 33,  2.8,  18,   3.8, 0,     0, 0, 35.0, 14.0]
          ]
        }
      }
    }
  };

  // ==========================================================================
  // 4. 7-Step Interactive Spotlight Guided Tour Script
  // ==========================================================================
  const TOUR_STEPS = [
    {
      tab: "tab-live",
      targetSelector: "#welcome-tour-banner",
      title: "1단계: 왜 30초 소켓 보고만으로는 불충분한가?",
      body: "AGV/AMR이 ACS와 30초 주기로만 상태를 주고받으면, 이동 중 3~15초 만에 진행되는 로밍 지연·음영 진입·소켓 버퍼 적체를 인지하기 전에 이미 연결이 끊어집니다. 또한 재연결 후에도 30초 전의 정상 데이터만 남아 원인을 알 수 없는 블랙박스가 됩니다.",
      takeaway: "해결책: 로컬 1초 고주파 링버퍼 + 평시 30초 요약 피기백 + 이상 시 조기 경보(T-18s) 및 사후 블랙박스 덤프 아키텍처 도입!"
    },
    {
      tab: "tab-live",
      targetSelector: "#live-kpi-row",
      title: "2단계: 실시간 시계열 DB(TSDB) 기반 통합 관제 KPI",
      body: "상단 4개 요약 카드는 내장 SQLite3 WAL 시계열 DB에 매 1초마다 적재되는 6대 AGV의 실시간 연결 상태, 30초 소켓 보고 성공률 및 주기 편차, 평균 16.5초 전 조기 감지 선행 시간(Lead Time), 그리고 TSDB 스트림 적재 현황을 보여줍니다.",
      takeaway: "모든 수치는 고정폭(Tabular Numerals) 폰트로 설계되어 1초 단위 갱신에도 화면 흔들림(Jitter)이 전혀 없습니다."
    },
    {
      tab: "tab-live",
      targetSelector: "#panel-floor-map",
      title: "3단계: 2D 스마트 팩토리 플로어 맵 & 음영/간섭 히트맵",
      body: "100m × 60m 공장 내 AP 4기(ZONE-A~D)의 전파 반경과 물리적 철제 랙 음영 구역, 용접기 전자기파(EMI) 간섭 구역을 시각화합니다. AGV 주행 좌표(M18)와 무선 지표를 매핑하여 어느 위치에서 품질이 저하되는지 공간적으로 즉시 파악합니다.",
      takeaway: "맵 위의 AGV를 직접 클릭하면 우측 시계열 차트가 해당 AGV로 즉시 연동됩니다."
    },
    {
      tab: "tab-live",
      targetSelector: "#panel-scenario-injector",
      title: "4단계: 4대 장애 시나리오 실시간 주입 및 재현 (Fault Injector)",
      body: "현장에서 가장 빈번한 4대 장애(① AP 로밍 실패, ② 음영/EMI 간섭, ③ 채널 과부하, ④ 소켓 블로킹)를 원하는 AGV에 실시간으로 주입해 볼 수 있습니다. 주입 즉시 위험도가 상승하며 [사전 감지 경보(Amber) → 단절(Rose) → 복구(Emerald)] 전 과정이 시계열 DB에 기록됩니다.",
      takeaway: "지금 시나리오 버튼을 눌러 실시간 사전 감지가 동작하는 모습을 직접 테스트해 보실 수 있습니다."
    },
    {
      tab: "tab-rca",
      targetSelector: "#panel-rca-playback",
      title: "5단계: 30초 보고 사각지대 vs 1초 하이브리드 사전 감지 타임라인 비교",
      body: "사전 감지 & 사후 분석 랩에서는 장애 전후 120초(T-89s ~ T+30s)의 1초 단위 블랙박스 파형을 재생합니다. 기존 30초 보고가 놓친 급격한 징후를 하이브리드 1초 수집 모델이 어떻게 단절 14~18초 전에 포착하는지 한눈에 비교합니다.",
      takeaway: "하단 3계층 동기화 차트(무선 L1/L2 · 전송 L3/L4 · 위험도)에서 T-18s 경보선(Amber)과 T=0s 단절선(Red)의 시간차를 확인하세요."
    },
    {
      tab: "tab-rca",
      targetSelector: "#panel-rca-decision",
      title: "6단계: 4단계 의사결정 트리 기반 자동 사후 원인 분석 (Automated RCA)",
      body: "단순히 '연결이 끊겼다'가 아니라, L1 신호 세기 → 노이즈 플로어 → 채널 점유율 → 게이트웨이 RTT → 소켓 큐 & CPU 부하 순으로 자동 대조하여 무선 음영 문제인지, AP 로밍 설정 문제인지, 아니면 AGV 내부 S/W 소켓 행(Hang)인지 100% 구분합니다.",
      takeaway: "특히 SCN-04(소켓 행)의 경우 무선 공사가 불필요한 S/W 병목임을 증명하여 잘못된 인프라 투자 비용을 예방합니다."
    },
    {
      tab: "tab-catalog",
      targetSelector: "#panel-catalog-detail",
      title: "7단계: 18종 수집 항목 백과사전 & 3단계 하이브리드 아키텍처",
      body: "마지막으로 탭 3과 탭 4에서는 L1~L7 18개 수집 지표의 8대 필수 명세(항목명, 설명, 단위/임계치, 수집 위치, 주기, 시스템 부하, Linux 수집 명령어/코드, 사전·사후 분석 활용법)와 30초 피기백 JSON 패킷 구조 및 대역폭 계산기를 모두 확인하실 수 있습니다.",
      takeaway: "이로써 현황 문제 진단부터 18종 지표 설계, 사전 감지·사후 분석 시연까지 완벽히 검증되었습니다!"
    }
  ];

  // ==========================================================================
  // 5. API Data Fetching & Synchronization
  // ==========================================================================
  async function fetchJson(url, options) {
    try {
      const res = await fetch(url, options);
      if (!res.ok) return null;
      return await res.json();
    } catch (_err) {
      return null;
    }
  }

  async function loadInitialReferenceData() {
    // 1. Scenarios
    const scnData = await fetchJson("/api/scenarios");
    if (scnData && Array.isArray(scnData.scenarios) && scnData.scenarios.length > 0) {
      scnData.scenarios.forEach((s) => {
        if (s && s.code) state.scenariosMap[s.code] = s;
      });
    } else if (scnData && typeof scnData === "object") {
      ["SCN-01", "SCN-02", "SCN-03", "SCN-04"].forEach((code) => {
        if (scnData[code]) state.scenariosMap[code] = scnData[code];
      });
    }
    // Ensure all 4 scenarios exist (merge with fallback if any missing)
    ["SCN-01", "SCN-02", "SCN-03", "SCN-04"].forEach((code) => {
      if (!state.scenariosMap[code] || !Array.isArray(state.scenariosMap[code].timeline)) {
        state.scenariosMap[code] = FALLBACK_SCENARIOS[code];
      }
    });

    // 2. Metrics Catalog (18 metrics)
    const catData = await fetchJson("/api/metrics-catalog");
    if (catData && Array.isArray(catData.metrics) && catData.metrics.length > 0) {
      state.metricsCatalog = catData.metrics;
    } else if (Array.isArray(catData) && catData.length > 0) {
      state.metricsCatalog = catData;
    } else {
      state.metricsCatalog = getFallbackMetricsCatalog();
    }

    // 3. Hybrid Architecture Spec
    const archData = await fetchJson("/api/hybrid-architecture");
    if (archData && Object.keys(archData).length > 0) {
      state.hybridArchSpec = archData;
    }

    renderRcaScenarioView();
    renderMetricsCatalog();
    renderPacketInspector();
    updateBandwidthCalculator();
  }

  async function pollLiveTelemetry() {
    const [overview, tsData] = await Promise.all([
      fetchJson("/api/overview"),
      fetchJson(`/api/agv/${encodeURIComponent(state.selectedAgvId)}/timeseries?window_sec=180`)
    ]);

    if (overview && Array.isArray(overview.fleet)) {
      state.overview = overview;
      updateLiveKpisAndTables(overview);
    }

    if (tsData && Array.isArray(tsData.series)) {
      state.agvTimeseries = tsData;
    }

    if (state.activeTab === "tab-live") {
      drawFactoryFloorMap();
      drawLiveMiniChart();
    }
  }

  // ==========================================================================
  // 6. Tab 1: Live KPIs, Fleet Table, Recent Reports & Incidents Rendering
  // ==========================================================================
  function updateLiveKpisAndTables(ov) {
    const kpis = ov.kpis || {};
    const tsdb = ov.tsdb_stats || {};
    const fleet = ov.fleet || [];

    // Nav TSDB counter
    const totalRows = tsdb.total_rows || kpis.tsdb_total_rows || 3600;
    const navCountEl = document.getElementById("nav-tsdb-count");
    if (navCountEl) navCountEl.textContent = `(${Number(totalRows).toLocaleString()} pts)`;

    // KPI 1: Fleet Connection Status
    const totalAgv = kpis.total_agv || fleet.length || 6;
    const connCnt = kpis.connected_count !== undefined ? kpis.connected_count : 6;
    const warnCnt = kpis.pre_warning_count || 0;
    const critCnt = kpis.disconnected_count || 0;

    const kpiConnVal = document.getElementById("kpi-connected-val");
    if (kpiConnVal) {
      kpiConnVal.textContent = `${connCnt} / ${totalAgv}`;
      kpiConnVal.className = "kpi-hero-value tabular-nums " +
        (critCnt > 0 ? "color-crit" : (warnCnt > 0 ? "color-warn" : "color-ok"));
    }
    const fleetBadge = document.getElementById("kpi-fleet-badge");
    if (fleetBadge) {
      if (critCnt > 0) {
        fleetBadge.className = "badge badge-crit";
        fleetBadge.textContent = `단절 ${critCnt}대 발생`;
      } else if (warnCnt > 0) {
        fleetBadge.className = "badge badge-warn";
        fleetBadge.textContent = `사전감지 경보 ${warnCnt}대`;
      } else {
        fleetBadge.className = "badge badge-ok";
        fleetBadge.textContent = `전수 정상 (${totalAgv}대)`;
      }
    }
    setText("kpi-avg-rssi", `평균 ${(kpis.avg_rssi_dbm || -60.5).toFixed(1)} dBm`);
    setText("kpi-cnt-normal", `${connCnt}대`);
    setText("kpi-cnt-warn", `${warnCnt}대`);
    setText("kpi-cnt-crit", `${critCnt}대`);

    // KPI 2: 30s Socket Report Rate
    const repRate = kpis.report_success_rate_pct !== undefined ? kpis.report_success_rate_pct : 99.2;
    setText("kpi-report-rate", `${Number(repRate).toFixed(1)}%`);
    const avgHb = kpis.avg_hb_interval_sec || 30.1;
    setText("kpi-hb-drift", `평균 ${Number(avgHb).toFixed(1)}s ± 0.4s`);

    // KPI 3: Pre-Detection Lead Time
    const leadSec = kpis.avg_lead_time_sec || 16.5;
    setText("kpi-lead-time", `${Number(leadSec).toFixed(1)}s`);
    const activeScnCnt = kpis.active_scenario_count || warnCnt + critCnt || 0;
    setText("kpi-active-alerts", `활성 시나리오 ${activeScnCnt}건`);
    setText("kpi-incident-total", `${kpis.incident_count || 4}건 완료`);

    // KPI 4: TSDB Status
    const t1sRows = tsdb.telemetry_1s_rows || totalRows;
    setText("kpi-tsdb-rows", Number(t1sRows).toLocaleString());
    setText("kpi-tsdb-size", `${tsdb.db_size_kb || 420} KB`);
    setText("kpi-tsdb-reports", `${tsdb.acs_reports_30s_rows || 120}건`);

    // AP 4-Zone Strip
    if (Array.isArray(ov.aps) && ov.aps.length > 0) {
      const apStrip = document.getElementById("ap-status-strip");
      if (apStrip) {
        apStrip.innerHTML = ov.aps.map((ap) => {
          const util = Math.round(ap.channel_util || 24);
          const badgeCls = util > 65 ? "badge-crit" : (util > 45 ? "badge-warn" : "badge-ok");
          return `
            <div class="ap-mini-card">
              <div class="ap-mini-header">
                <span>${escapeHtml(ap.ap_id)}</span>
                <span class="badge ${badgeCls} mono">CH ${ap.channel || 36}</span>
              </div>
              <div class="ap-mini-meta mono">
                <span>AGV: ${ap.client_count || 0}대</span>
                <span>CCA: ${util}%</span>
              </div>
            </div>
          `;
        }).join("");
      }
    }

    // Selected AGV Detail Bar under Map
    const selAgv = fleet.find((a) => a.agv_id === state.selectedAgvId) || fleet[0];
    if (selAgv) {
      setText("map-selected-agv-pill", `선택: ${selAgv.agv_id}`);
      const detailBar = document.getElementById("map-agv-detail-bar");
      if (detailBar) {
        const scnTag = selAgv.scenario_code && selAgv.scenario_code !== "NORMAL"
          ? `<span class="badge badge-crit mono">${escapeHtml(selAgv.scenario_code)} 진행중</span>`
          : `<span class="badge badge-ok mono">NORMAL</span>`;
        detailBar.innerHTML = `
          <span><strong>[${escapeHtml(selAgv.agv_id)}]</strong> 좌표: (${Number(selAgv.pos_x).toFixed(1)}m, ${Number(selAgv.pos_y).toFixed(1)}m) | 속도: ${Number(selAgv.velocity).toFixed(2)} m/s | AP: ${escapeHtml(selAgv.ap_id || selAgv.zone_id)} (${escapeHtml(selAgv.bssid || "")})</span>
          <span>${scnTag}</span>
        `;
      }
    }

    // Fleet Table Body
    const tbody = document.getElementById("fleet-table-body");
    if (tbody && fleet.length > 0) {
      tbody.innerHTML = fleet.map((agv) => {
        const isSel = agv.agv_id === state.selectedAgvId;
        const rssi = Number(agv.rssi).toFixed(1);
        const snr = Number(agv.snr).toFixed(0);
        const rtt = Number(agv.gw_rtt_ms).toFixed(1);
        const retrans = agv.tcp_retrans || 0;
        const risk = Number(agv.risk_score).toFixed(1);

        const rssiCls = agv.rssi <= -75 ? "color-crit" : (agv.rssi <= -68 ? "color-warn" : "");
        const riskCls = agv.risk_score >= 85 ? "color-crit" : (agv.risk_score >= 45 ? "color-warn" : "color-ok");

        let stateBadge = `<span class="badge badge-ok">CONNECTED</span>`;
        if (agv.conn_state === "DISCONNECTED") {
          stateBadge = `<span class="badge badge-crit">DISCONNECTED</span>`;
        } else if (agv.conn_state === "PRE_WARNING") {
          stateBadge = `<span class="badge badge-warn">PRE_WARNING</span>`;
        }

        return `
          <tr class="${isSel ? "selected-row" : ""}" data-agv-row="${escapeHtml(agv.agv_id)}">
            <td class="text-left mono"><strong>${escapeHtml(agv.agv_id)}</strong></td>
            <td class="text-center mono">${escapeHtml(agv.zone_id || agv.ap_id)}</td>
            <td class="text-right num ${rssiCls}">${rssi} dBm</td>
            <td class="text-right num">${snr} dB</td>
            <td class="text-right num">${rtt} ms</td>
            <td class="text-right num ${retrans > 0 ? "color-warn" : ""}">${retrans} /s</td>
            <td class="text-right num"><strong class="${riskCls}">${risk}</strong></td>
            <td class="text-center">${stateBadge}</td>
          </tr>
        `;
      }).join("");

      tbody.querySelectorAll("tr[data-agv-row]").forEach((row) => {
        row.addEventListener("click", () => {
          const id = row.getAttribute("data-agv-row");
          if (id) selectAgv(id);
        });
      });
    }

    // Recent 30s ACS Reports Table
    const repTbody = document.getElementById("recent-reports-tbody");
    if (repTbody && Array.isArray(ov.recent_reports_30s)) {
      repTbody.innerHTML = ov.recent_reports_30s.slice(0, 7).map((r) => {
        const pb = r.piggyback_summary || {};
        const dt = new Date(r.ts || Date.now());
        const timeStr = dt.toTimeString().split(" ")[0];
        let stBadge = `<span class="badge badge-ok">OK (정상)</span>`;
        if (r.report_status === "TIMEOUT_MISSED") {
          stBadge = `<span class="badge badge-crit">TIMEOUT (단절)</span>`;
        } else if (r.report_status === "DELAYED") {
          stBadge = `<span class="badge badge-warn">DELAYED (지연)</span>`;
        }
        const maxRisk = pb.max_risk_score !== undefined ? Number(pb.max_risk_score).toFixed(1) : "14.0";
        const riskCls = maxRisk >= 70 ? "color-crit" : (maxRisk >= 45 ? "color-warn" : "color-ok");
        return `
          <tr>
            <td class="text-left mono">${timeStr}</td>
            <td class="text-left mono"><strong>${escapeHtml(r.agv_id)}</strong></td>
            <td class="text-center">${stBadge}</td>
            <td class="text-right num">${Number(r.hb_interval_sec || 30.0).toFixed(1)}s</td>
            <td class="text-right num">${pb.rssi_min !== undefined ? Number(pb.rssi_min).toFixed(1) : "-63.0"} dBm</td>
            <td class="text-right num">${pb.tcp_retrans_sum !== undefined ? pb.tcp_retrans_sum : 0}건</td>
            <td class="text-right num ${riskCls}"><strong>${maxRisk}</strong></td>
          </tr>
        `;
      }).join("");
    }

    // Recent Pre-Detection & RCA Incidents Table
    const incTbody = document.getElementById("recent-incidents-tbody");
    if (incTbody && Array.isArray(ov.recent_incidents)) {
      incTbody.innerHTML = ov.recent_incidents.slice(0, 6).map((inc) => {
        const code = inc.scenario_code || "SCN-01";
        return `
          <tr data-inc-scn="${escapeHtml(code)}">
            <td class="text-left mono"><span class="color-accent">${escapeHtml(inc.incident_id)}</span></td>
            <td class="text-left mono"><strong>${escapeHtml(inc.agv_id)}</strong></td>
            <td class="text-center"><span class="badge badge-crit mono">${escapeHtml(code)}</span></td>
            <td class="text-left" style="max-width:220px; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(inc.title)}</td>
            <td class="text-right num color-warn"><strong>-${Number(inc.lead_time_sec || 16.5).toFixed(1)}s 전 감지</strong></td>
            <td class="text-center"><button class="btn btn-sm btn-tour" type="button">RCA 파형 보기 →</button></td>
          </tr>
        `;
      }).join("");

      incTbody.querySelectorAll("tr[data-inc-scn]").forEach((row) => {
        row.addEventListener("click", () => {
          const code = row.getAttribute("data-inc-scn") || "SCN-01";
          switchTab("tab-rca");
          selectRcaScenario(code);
        });
      });
    }
  }

  function selectAgv(agvId) {
    state.selectedAgvId = agvId;
    const selEl = document.getElementById("injector-target-agv");
    if (selEl) selEl.value = agvId;
    const titleEl = document.getElementById("selected-agv-chart-title");
    if (titleEl) {
      titleEl.textContent = `${agvId} 실시간 1초 시계열 & 30초 보고 마커 (최근 180s)`;
    }
    pollLiveTelemetry();
  }

  // ==========================================================================
  // 7. High-DPI Canvas Helper
  // ==========================================================================
  function setupHiDPICanvas(canvas) {
    if (!canvas) return null;
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const cssW = rect.width || canvas.width || 800;
    const cssH = rect.height || canvas.height || 300;
    if (canvas.width !== Math.round(cssW * dpr) || canvas.height !== Math.round(cssH * dpr)) {
      canvas.width = Math.round(cssW * dpr);
      canvas.height = Math.round(cssH * dpr);
    }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, w: cssW, h: cssH };
  }

  function getThemeColors() {
    const isLight = state.theme === "light";
    return {
      bgCanvas: isLight ? "#F8FAFC" : "#090D14",
      gridLine: isLight ? "rgba(71, 85, 105, 0.14)" : "rgba(148, 163, 184, 0.12)",
      textPrimary: isLight ? "#0F172A" : "#F8FAFC",
      textSecondary: isLight ? "#475569" : "#94A3B8",
      textMuted: isLight ? "#64748B" : "#64748B",
      sky: isLight ? "#0284C7" : "#38BDF8",
      indigo: isLight ? "#4F46E5" : "#818CF8",
      emerald: isLight ? "#059669" : "#10B981",
      amber: isLight ? "#D97706" : "#F59E0B",
      rose: isLight ? "#E11D48" : "#F43F5E"
    };
  }

  // ==========================================================================
  // 8. Tab 1: Interactive 2D Smart Factory Floor Plan & Wi-Fi Heatmap Canvas
  // ==========================================================================
  function drawFactoryFloorMap() {
    const canvas = document.getElementById("factory-map-canvas");
    const setup = setupHiDPICanvas(canvas);
    if (!setup) return;
    const { ctx, w, h } = setup;
    const colors = getThemeColors();

    const padL = 38, padR = 22, padT = 24, padB = 28;
    const mapW = w - padL - padR;
    const mapH = h - padT - padB;

    const toX = (mx) => padL + (mx / 100) * mapW;
    const toY = (my) => padT + (my / 60) * mapH;

    // 1. Background
    ctx.fillStyle = colors.bgCanvas;
    ctx.fillRect(0, 0, w, h);

    // 2. Factory 10m Grid Lines & Meter Coordinates
    ctx.strokeStyle = colors.gridLine;
    ctx.lineWidth = 1;
    ctx.font = "500 10px 'JetBrains Mono', monospace";
    ctx.fillStyle = colors.textMuted;

    for (let x = 0; x <= 100; x += 10) {
      const px = toX(x);
      ctx.beginPath();
      ctx.moveTo(px, padT);
      ctx.lineTo(px, padT + mapH);
      ctx.stroke();
      ctx.textAlign = "center";
      ctx.fillText(`${x}m`, px, padT + mapH + 16);
    }
    for (let y = 0; y <= 60; y += 10) {
      const py = toY(y);
      ctx.beginPath();
      ctx.moveTo(padL, py);
      ctx.lineTo(padL + mapW, py);
      ctx.stroke();
      ctx.textAlign = "right";
      ctx.fillText(`${y}m`, padL - 6, py + 3);
    }

    // Outer Factory Boundary
    ctx.strokeStyle = state.theme === "light" ? "#94A3B8" : "#334155";
    ctx.lineWidth = 1.5;
    ctx.strokeRect(padL, padT, mapW, mapH);

    const ov = state.overview || {};
    const aps = Array.isArray(ov.aps) && ov.aps.length > 0 ? ov.aps : [
      { ap_id: "AP-ZONE-A", x: 20, y: 15, channel: 36, channel_util: 24 },
      { ap_id: "AP-ZONE-B", x: 75, y: 15, channel: 44, channel_util: 28 },
      { ap_id: "AP-ZONE-C", x: 75, y: 45, channel: 149, channel_util: 36 },
      { ap_id: "AP-ZONE-D", x: 20, y: 45, channel: 157, channel_util: 22 }
    ];

    // 3. Wi-Fi Signal Coverage Radial Gradient Heatmap
    if (state.showHeatmap) {
      aps.forEach((ap) => {
        const cx = toX(ap.x);
        const cy = toY(ap.y);
        const radius = (34 / 100) * mapW;
        const grad = ctx.createRadialGradient(cx, cy, 4, cx, cy, radius);
        grad.addColorStop(0, "rgba(56, 189, 248, 0.22)");
        grad.addColorStop(0.55, "rgba(16, 185, 129, 0.09)");
        grad.addColorStop(1, "rgba(16, 185, 129, 0.0)");
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.fill();
      });
    }

    // 4. Physical Dead Zone (Metal Rack) & EMI Interference Zone (Welding Cell)
    if (state.showDangerZones) {
      // Shadow Zone around (43..57m, 8..22m)
      const sx = toX(43), sy = toY(8), sw = (14 / 100) * mapW, sh = (14 / 60) * mapH;
      ctx.fillStyle = "rgba(244, 63, 94, 0.14)";
      ctx.fillRect(sx, sy, sw, sh);
      ctx.save();
      ctx.setLineDash([4, 3]);
      ctx.strokeStyle = "rgba(244, 63, 94, 0.7)";
      ctx.lineWidth = 1.5;
      ctx.strokeRect(sx, sy, sw, sh);
      ctx.restore();
      ctx.fillStyle = colors.rose;
      ctx.font = "600 10px 'Inter', sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("철제 랙 전파 음영 구역", sx + sw / 2, sy + sh / 2 - 4);
      ctx.fillText("(Dead Zone: RSSI ≤ -82dBm)", sx + sw / 2, sy + sh / 2 + 9);

      // EMI High-Noise Welding Zone around (80, 40)
      const ex = toX(80), ey = toY(40), er = (9 / 100) * mapW;
      const emiGrad = ctx.createRadialGradient(ex, ey, 2, ex, ey, er);
      emiGrad.addColorStop(0, "rgba(245, 158, 11, 0.30)");
      emiGrad.addColorStop(1, "rgba(244, 63, 94, 0.06)");
      ctx.fillStyle = emiGrad;
      ctx.beginPath();
      ctx.arc(ex, ey, er, 0, Math.PI * 2);
      ctx.fill();
      ctx.save();
      ctx.setLineDash([3, 3]);
      ctx.strokeStyle = colors.amber;
      ctx.stroke();
      ctx.restore();
      ctx.fillStyle = colors.amber;
      ctx.fillText("⚡ 로봇 용접 EMI 간섭 구역", ex, ey - er - 5);
    }

    // 5. AGV Guide Paths (if present)
    if (ov.agv_paths) {
      ctx.save();
      ctx.strokeStyle = state.theme === "light" ? "rgba(100,116,139,0.22)" : "rgba(148,163,184,0.14)";
      ctx.setLineDash([2, 4]);
      ctx.lineWidth = 1;
      Object.values(ov.agv_paths).forEach((pts) => {
        if (!Array.isArray(pts) || pts.length < 2) return;
        ctx.beginPath();
        pts.forEach((pt, idx) => {
          const px = toX(pt[0]), py = toY(pt[1]);
          if (idx === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        });
        ctx.closePath();
        ctx.stroke();
      });
      ctx.restore();
    }

    // 6. Render 4 AP Towers
    aps.forEach((ap) => {
      const ax = toX(ap.x), ay = toY(ap.y);
      ctx.fillStyle = "rgba(56, 189, 248, 0.18)";
      ctx.strokeStyle = colors.sky;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(ax, ay, 11, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = colors.sky;
      ctx.beginPath();
      ctx.arc(ax, ay, 4, 0, Math.PI * 2);
      ctx.fill();

      ctx.font = "700 10px 'JetBrains Mono', monospace";
      ctx.fillStyle = colors.textPrimary;
      ctx.textAlign = "center";
      ctx.fillText(ap.ap_id, ax, ay - 15);
    });

    // 7. Render 6 Live AGVs + Wireless Link Lines + Telemetry Badges
    const fleet = Array.isArray(ov.fleet) && ov.fleet.length > 0 ? ov.fleet : [
      { agv_id: "AGV-01", pos_x: 22, pos_y: 15, rssi: -58, risk_score: 10, conn_state: "CONNECTED", ap_id: "AP-ZONE-A" },
      { agv_id: "AGV-02", pos_x: 48, pos_y: 15, rssi: -62, risk_score: 14, conn_state: "CONNECTED", ap_id: "AP-ZONE-A" },
      { agv_id: "AGV-03", pos_x: 74, pos_y: 22, rssi: -60, risk_score: 12, conn_state: "CONNECTED", ap_id: "AP-ZONE-B" },
      { agv_id: "AGV-04", pos_x: 78, pos_y: 42, rssi: -63, risk_score: 18, conn_state: "CONNECTED", ap_id: "AP-ZONE-C" },
      { agv_id: "AGV-05", pos_x: 42, pos_y: 45, rssi: -61, risk_score: 11, conn_state: "CONNECTED", ap_id: "AP-ZONE-D" },
      { agv_id: "AGV-06", pos_x: 18, pos_y: 36, rssi: -59, risk_score: 9, conn_state: "CONNECTED", ap_id: "AP-ZONE-D" }
    ];

    state._renderedAgvHitboxes = [];

    fleet.forEach((agv) => {
      const gx = toX(agv.pos_x);
      const gy = toY(agv.pos_y);
      const isSelected = agv.agv_id === state.selectedAgvId;

      let stColor = colors.emerald;
      if (agv.conn_state === "DISCONNECTED" || agv.risk_score >= 85) {
        stColor = colors.rose;
      } else if (agv.conn_state === "PRE_WARNING" || agv.risk_score >= 45) {
        stColor = colors.amber;
      }

      // Draw wireless link line to associated AP
      const linkedAp = aps.find((a) => a.ap_id === agv.ap_id || a.zone_id === agv.zone_id);
      if (linkedAp) {
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(gx, gy);
        ctx.lineTo(toX(linkedAp.x), toY(linkedAp.y));
        ctx.strokeStyle = stColor;
        ctx.globalAlpha = isSelected ? 0.65 : 0.28;
        ctx.lineWidth = isSelected ? 1.8 : 1.0;
        ctx.setLineDash(agv.conn_state === "DISCONNECTED" ? [3, 5] : [4, 3]);
        ctx.stroke();
        ctx.restore();
      }

      // Outer selection/alert halo
      if (isSelected || agv.conn_state !== "CONNECTED") {
        ctx.save();
        ctx.beginPath();
        ctx.arc(gx, gy, isSelected ? 17 : 14, 0, Math.PI * 2);
        ctx.strokeStyle = isSelected ? colors.sky : stColor;
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.restore();
      }

      // AGV Vehicle Body
      ctx.fillStyle = stColor;
      ctx.beginPath();
      ctx.roundRect ? ctx.roundRect(gx - 10, gy - 7, 20, 14, 4) : ctx.rect(gx - 10, gy - 7, 20, 14);
      ctx.fill();
      ctx.strokeStyle = "#0B0F17";
      ctx.lineWidth = 1.2;
      ctx.stroke();

      // Label pill above AGV
      const labelTxt = `${agv.agv_id} (${Math.round(agv.rssi)}dBm)`;
      ctx.font = "600 10px 'JetBrains Mono', monospace";
      const tw = ctx.measureText(labelTxt).width + 10;
      ctx.fillStyle = state.theme === "light" ? "rgba(255,255,255,0.92)" : "rgba(15,23,42,0.92)";
      ctx.strokeStyle = stColor;
      ctx.lineWidth = 1;
      ctx.fillRect(gx - tw / 2, gy - 25, tw, 15);
      ctx.strokeRect(gx - tw / 2, gy - 25, tw, 15);

      ctx.fillStyle = colors.textPrimary;
      ctx.textAlign = "center";
      ctx.fillText(labelTxt, gx, gy - 14);

      state._renderedAgvHitboxes.push({ agv_id: agv.agv_id, x: gx, y: gy, r: 20 });
    });
  }

  // ==========================================================================
  // 9. Tab 1: Selected AGV Live 1s Stream Mini Chart
  // ==========================================================================
  function drawLiveMiniChart() {
    const canvas = document.getElementById("live-mini-chart");
    const setup = setupHiDPICanvas(canvas);
    if (!setup) return;
    const { ctx, w, h } = setup;
    const colors = getThemeColors();

    ctx.fillStyle = colors.bgCanvas;
    ctx.fillRect(0, 0, w, h);

    const series = (state.agvTimeseries && state.agvTimeseries.series) || [];
    const padL = 38, padR = 36, padT = 16, padB = 22;
    const cw = w - padL - padR;
    const ch = h - padT - padB;

    // Horizontal grid lines
    ctx.strokeStyle = colors.gridLine;
    ctx.lineWidth = 1;
    for (let i = 0; i <= 3; i++) {
      const y = padT + (i / 3) * ch;
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(padL + cw, y);
      ctx.stroke();
    }

    // Risk = 70 Pre-detection warning threshold dashed line
    const yRisk70 = padT + (1 - 70 / 100) * ch;
    ctx.save();
    ctx.setLineDash([4, 3]);
    ctx.strokeStyle = "rgba(245, 158, 11, 0.55)";
    ctx.beginPath();
    ctx.moveTo(padL, yRisk70);
    ctx.lineTo(padL + cw, yRisk70);
    ctx.stroke();
    ctx.restore();

    // Axis labels
    ctx.font = "500 9.5px 'JetBrains Mono', monospace";
    ctx.fillStyle = colors.sky;
    ctx.textAlign = "right";
    ctx.fillText("-50dBm", padL - 4, padT + 6);
    ctx.fillText("-90dBm", padL - 4, padT + ch);

    ctx.fillStyle = colors.amber;
    ctx.textAlign = "left";
    ctx.fillText("Risk 100", padL + cw + 4, padT + 6);
    ctx.fillText("70(경보)", padL + cw + 4, yRisk70 + 3);
    ctx.fillText("0", padL + cw + 4, padT + ch);

    if (series.length < 2) return;

    const n = series.length;
    const toX = (i) => padL + (i / (n - 1)) * cw;
    const rssiToY = (v) => {
      const clamped = Math.max(-92, Math.min(-48, v));
      return padT + ((-48 - clamped) / 44) * ch;
    };
    const riskToY = (r) => {
      const clamped = Math.max(0, Math.min(100, r));
      return padT + (1 - clamped / 100) * ch;
    };

    // Plot RSSI Line (Sky Cyan)
    ctx.strokeStyle = colors.sky;
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    series.forEach((pt, idx) => {
      const x = toX(idx), y = rssiToY(pt.rssi);
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Plot Risk Score Line (Amber / Rose)
    ctx.strokeStyle = colors.amber;
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    series.forEach((pt, idx) => {
      const x = toX(idx), y = riskToY(pt.risk_score);
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Plot 30s ACS Report Markers every ~30 points
    series.forEach((pt, idx) => {
      if (idx % 30 === 0 || idx === n - 1) {
        const x = toX(idx);
        const y = riskToY(pt.risk_score);
        ctx.fillStyle = pt.conn_state === "DISCONNECTED" ? colors.rose : colors.emerald;
        ctx.beginPath();
        ctx.arc(x, y, 3.2, 0, Math.PI * 2);
        ctx.fill();
      }
    });
  }

  // ==========================================================================
  // 10. Tab 2: Pre-Detection & Post-Mortem RCA Lab Rendering
  // ==========================================================================
  function selectRcaScenario(code) {
    if (!state.scenariosMap[code]) return;
    state.selectedScenarioCode = code;
    const scn = state.scenariosMap[code];
    state.rcaCursorOffset = scn.pre_detect_offset_sec || -18;

    document.querySelectorAll("[data-scn-card]").forEach((card) => {
      card.classList.toggle("active", card.getAttribute("data-scn-card") === code);
    });

    const slider = document.getElementById("rca-time-slider");
    if (slider) slider.value = String(state.rcaCursorOffset);

    renderRcaScenarioView();
  }

  function renderRcaScenarioView() {
    const code = state.selectedScenarioCode;
    const scn = state.scenariosMap[code] || FALLBACK_SCENARIOS[code] || FALLBACK_SCENARIOS["SCN-01"];
    const leadSec = Math.abs(scn.pre_detect_offset_sec || scn.lead_time_sec || 18);

    setText("rca-lab-header-title", `[${scn.code}] ${scn.title} — 30초 주기 보고 사각지대 vs 1초 하이브리드 사전 감지 타임라인 비교`);
    setText("rca-legacy-desc", scn.legacy_30s_view || "");
    setText("rca-hybrid-desc", scn.hybrid_1s_view || "");
    setText("rca-hybrid-lead-badge", `단절 ${leadSec}초 전 조기 경보 발령!`);

    const jumpBtn = document.getElementById("btn-jump-predetect");
    if (jumpBtn) {
      jumpBtn.setAttribute("data-jump", String(-leadSec));
      jumpBtn.textContent = `T-${leadSec}s (사전감지 경보!)`;
    }

    // Right Column: RCA Decision Tree Verdict
    setText("rca-verdict-code", `${scn.code} 자동 판정`);
    setText("rca-verdict-title", scn.title);
    setText("rca-verdict-lead", `T-${leadSec}s 조기 감지`);
    setText("rca-verdict-summary", scn.root_cause || "");

    // Decision Tree Steps
    const stepsEl = document.getElementById("rca-decision-steps");
    if (stepsEl && Array.isArray(scn.decision_tree)) {
      stepsEl.innerHTML = scn.decision_tree.map((st) => {
        const isFail = st.result === "FAIL";
        const badgeCls = isFail ? "badge-crit" : "badge-ok";
        return `
          <div class="decision-step-item ${isFail ? "step-fail" : ""}">
            <div class="step-top-row">
              <span>Step ${st.step}. ${escapeHtml(st.question)}</span>
              <span class="badge ${badgeCls} mono">${escapeHtml(st.result)}</span>
            </div>
            <div class="step-obs mono">관측치: ${escapeHtml(st.observation)}</div>
            <div class="step-imp">판정: ${escapeHtml(st.implication)}</div>
          </div>
        `;
      }).join("");
    }

    // Signature Evidence Pills
    const pillsEl = document.getElementById("rca-signature-pills");
    if (pillsEl && Array.isArray(scn.signature_metrics)) {
      pillsEl.innerHTML = scn.signature_metrics.map((m) =>
        `<span class="evidence-pill">${escapeHtml(m)}</span>`
      ).join("");
    }

    // Remediation Actions
    const remEl = document.getElementById("rca-remediation-list");
    if (remEl && Array.isArray(scn.recommended_actions)) {
      remEl.innerHTML = scn.recommended_actions.map((act) =>
        `<li>${escapeHtml(act)}</li>`
      ).join("");
    }

    updateRcaCursorAndCharts();
  }

  function updateRcaCursorAndCharts() {
    const code = state.selectedScenarioCode;
    const scn = state.scenariosMap[code] || FALLBACK_SCENARIOS[code] || FALLBACK_SCENARIOS["SCN-01"];
    const timeline = Array.isArray(scn.timeline) ? scn.timeline : FALLBACK_SCENARIOS["SCN-01"].timeline;

    const pt = timeline.find((p) => p.offset_sec === state.rcaCursorOffset) || timeline[0];
    if (pt) {
      const offStr = pt.offset_sec > 0 ? `T+${pt.offset_sec}s` : `T${pt.offset_sec}s`;
      setText("rca-current-time-badge", `현재 커서: ${offStr} (${pt.conn_state})`);
      setText("rca-cursor-annotation", `[${offStr}] ${pt.annotation || ""}`);
      setText("snap-offset", offStr);
      setText("snap-rf", `${Number(pt.rssi).toFixed(0)} dBm / ${Number(pt.snr).toFixed(0)} dB`);
      setText("snap-mac", `${Number(pt.channel_util).toFixed(0)}% / ${Number(pt.l2_retry_rate).toFixed(1)}%`);
      setText("snap-roam", `${Number(pt.roaming_ms || 0).toFixed(0)} ms`);
      setText("snap-rtt", `${Number(pt.gw_rtt_ms).toFixed(1)} ms / ${Number(pt.jitter_ms || 1).toFixed(0)} ms`);
      setText("snap-retrans", `${pt.tcp_retrans || 0} /s`);
      const sqKb = ((pt.send_q_bytes || 0) / 1024).toFixed(1);
      const rqKb = ((pt.recv_q_bytes || 0) / 1024).toFixed(1);
      setText("snap-queues", `${sqKb}K / ${rqKb}K`);

      const snapRiskEl = document.getElementById("snap-risk");
      if (snapRiskEl) {
        snapRiskEl.textContent = `${Number(pt.risk_score).toFixed(1)} (${pt.conn_state})`;
        snapRiskEl.className = "snap-val " +
          (pt.risk_score >= 85 ? "color-crit" : (pt.risk_score >= 45 ? "color-warn" : "color-ok"));
      }
    }

    drawSynchronizedRcaCharts(scn, timeline);
  }

  function drawSynchronizedRcaCharts(scn, timeline) {
    if (!Array.isArray(timeline) || timeline.length < 2) return;
    const preOff = scn.pre_detect_offset_sec || -18;
    const discOff = scn.disconnect_offset_sec || 0;
    const recOff = scn.recovery_offset_sec || 16;

    // Layer 1: RSSI, SNR, Channel Util, L2 Retry
    drawRcaLayerCanvas("rca-chart-l1", timeline, preOff, discOff, recOff, (ctx, toX, padT, ch, colors) => {
      // RSSI (-90..-50 -> 0..1)
      plotSeriesLine(ctx, timeline, toX, (p) => padT + ((-48 - Math.max(-92, Math.min(-48, p.rssi))) / 44) * ch, colors.sky, 2.0, false);
      // SNR (0..45)
      plotSeriesLine(ctx, timeline, toX, (p) => padT + (1 - Math.max(0, Math.min(45, p.snr)) / 45) * ch, colors.emerald, 1.6, false);
      // Channel Util (0..100%)
      plotSeriesLine(ctx, timeline, toX, (p) => padT + (1 - Math.max(0, Math.min(100, p.channel_util)) / 100) * ch, colors.amber, 1.6, false);
      // L2 Retry (0..60%)
      plotSeriesLine(ctx, timeline, toX, (p) => padT + (1 - Math.max(0, Math.min(60, p.l2_retry_rate)) / 60) * ch, colors.rose, 1.5, true);
    });

    // Layer 2: Gateway RTT, TCP Retransmits, Send-Q, Recv-Q
    drawRcaLayerCanvas("rca-chart-l2", timeline, preOff, discOff, recOff, (ctx, toX, padT, ch, colors) => {
      // GW RTT (0..350ms)
      plotSeriesLine(ctx, timeline, toX, (p) => padT + (1 - Math.max(0, Math.min(350, p.gw_rtt_ms)) / 350) * ch, colors.sky, 2.0, false);
      // Send-Q (0..18000 B)
      plotSeriesLine(ctx, timeline, toX, (p) => padT + (1 - Math.max(0, Math.min(18000, p.send_q_bytes || 0)) / 18000) * ch, colors.amber, 1.7, false);
      // Recv-Q (0..20000 B)
      plotSeriesLine(ctx, timeline, toX, (p) => padT + (1 - Math.max(0, Math.min(20000, p.recv_q_bytes || 0)) / 20000) * ch, colors.indigo, 1.7, false);
      // TCP Retransmits bars
      timeline.forEach((p, idx) => {
        if (p.tcp_retrans > 0) {
          const x = toX(idx);
          const bh = Math.min(ch, (p.tcp_retrans / 14) * ch);
          ctx.fillStyle = "rgba(244, 63, 94, 0.55)";
          ctx.fillRect(x - 2, padT + ch - bh, 4, bh);
        }
      });
    });

    // Layer 3: Pre-Detection Risk Score (0..100) vs 30s ACS Report Markers
    drawRcaLayerCanvas("rca-chart-l3", timeline, preOff, discOff, recOff, (ctx, toX, padT, ch, colors, padL, cw) => {
      // Risk = 70 threshold horizontal line
      const y70 = padT + (1 - 0.7) * ch;
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = colors.amber;
      ctx.beginPath();
      ctx.moveTo(padL, y70);
      ctx.lineTo(padL + cw, y70);
      ctx.stroke();
      ctx.restore();

      // Risk Score area & line
      plotSeriesLine(ctx, timeline, toX, (p) => padT + (1 - Math.max(0, Math.min(100, p.risk_score)) / 100) * ch, colors.indigo, 2.2, false);

      // 30s ACS Socket Report Markers (-60s, -30s, 0s, +30s)
      timeline.forEach((p, idx) => {
        if (p.offset_sec === -60 || p.offset_sec === -30 || p.offset_sec === 0 || p.offset_sec === 30) {
          const x = toX(idx);
          const y = padT + (1 - Math.max(0, Math.min(100, p.risk_score)) / 100) * ch;
          const isDrop = p.offset_sec === 0;
          ctx.fillStyle = isDrop ? colors.rose : colors.emerald;
          ctx.beginPath();
          ctx.arc(x, y, 5.5, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = "#0B0F17";
          ctx.lineWidth = 1.5;
          ctx.stroke();

          ctx.font = "700 9.5px 'JetBrains Mono', monospace";
          ctx.fillStyle = isDrop ? colors.rose : colors.emerald;
          ctx.textAlign = "center";
          ctx.fillText(isDrop ? "30s 보고 TIMEOUT(X)" : "30s 보고(O)", x, Math.max(padT + 11, y - 9));
        }
      });
    });
  }

  function drawRcaLayerCanvas(canvasId, timeline, preOff, discOff, recOff, customDrawFn) {
    const canvas = document.getElementById(canvasId);
    const setup = setupHiDPICanvas(canvas);
    if (!setup) return;
    const { ctx, w, h } = setup;
    const colors = getThemeColors();

    const padL = 42, padR = 18, padT = 16, padB = 22;
    const cw = w - padL - padR;
    const ch = h - padT - padB;
    const n = timeline.length;
    const toX = (idx) => padL + (idx / (n - 1)) * cw;
    const offToIdx = (off) => Math.max(0, Math.min(n - 1, off - timeline[0].offset_sec));

    ctx.fillStyle = colors.bgCanvas;
    ctx.fillRect(0, 0, w, h);

    // Shaded Disconnection Zone (T=0s .. T+recOff)
    const xDisc = toX(offToIdx(discOff));
    const xRec = toX(offToIdx(recOff));
    ctx.fillStyle = "rgba(244, 63, 94, 0.12)";
    ctx.fillRect(xDisc, padT, Math.max(4, xRec - xDisc), ch);

    // Shaded Pre-Detection Lead Window (T-preOff .. T=0s)
    const xPre = toX(offToIdx(preOff));
    ctx.fillStyle = "rgba(245, 158, 11, 0.08)";
    ctx.fillRect(xPre, padT, Math.max(4, xDisc - xPre), ch);

    // Grid lines & X-axis labels
    ctx.strokeStyle = colors.gridLine;
    ctx.lineWidth = 1;
    for (let g = 0; g <= 3; g++) {
      const gy = padT + (g / 3) * ch;
      ctx.beginPath();
      ctx.moveTo(padL, gy);
      ctx.lineTo(padL + cw, gy);
      ctx.stroke();
    }

    ctx.font = "500 9.5px 'JetBrains Mono', monospace";
    ctx.fillStyle = colors.textMuted;
    ctx.textAlign = "center";
    [-80, -60, -40, -30, preOff, 0, 15, 30].forEach((tickOff) => {
      const tx = toX(offToIdx(tickOff));
      ctx.fillText(tickOff > 0 ? `+${tickOff}s` : `${tickOff}s`, tx, padT + ch + 14);
    });

    // Custom metric lines
    customDrawFn(ctx, toX, padT, ch, colors, padL, cw);

    // Vertical Amber Pre-Detection Line (T-18s)
    ctx.save();
    ctx.setLineDash([4, 3]);
    ctx.strokeStyle = colors.amber;
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    ctx.moveTo(xPre, padT);
    ctx.lineTo(xPre, padT + ch);
    ctx.stroke();
    ctx.restore();
    ctx.fillStyle = colors.amber;
    ctx.font = "700 9.5px 'JetBrains Mono', monospace";
    ctx.textAlign = "right";
    ctx.fillText(`★ 사전감지(T${preOff}s)`, xPre - 4, padT + 10);

    // Vertical Rose 30s Socket Disconnection Line (T=0s)
    ctx.strokeStyle = colors.rose;
    ctx.lineWidth = 2.0;
    ctx.beginPath();
    ctx.moveTo(xDisc, padT);
    ctx.lineTo(xDisc, padT + ch);
    ctx.stroke();
    ctx.fillStyle = colors.rose;
    ctx.textAlign = "left";
    ctx.fillText("✖ 30s 소켓 단절(T=0s)", xDisc + 4, padT + 10);

    // Current Interactive Cursor Scrubber Line
    const xCur = toX(offToIdx(state.rcaCursorOffset));
    ctx.strokeStyle = colors.sky;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(xCur, padT);
    ctx.lineTo(xCur, padT + ch);
    ctx.stroke();
  }

  function plotSeriesLine(ctx, timeline, toX, toYFn, color, width, dashed) {
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    if (dashed) ctx.setLineDash([3, 3]);
    ctx.beginPath();
    timeline.forEach((pt, idx) => {
      const x = toX(idx), y = toYFn(pt);
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.restore();
  }

  // ==========================================================================
  // 11. Tab 3: 18-Metric Telemetry Encyclopedia & 8-Requirement Inspector
  // ==========================================================================
  function renderMetricsCatalog() {
    const allMetrics = state.metricsCatalog.length > 0 ? state.metricsCatalog : getFallbackMetricsCatalog();
    const q = state.catalogSearchQuery.trim().toLowerCase();

    const filtered = allMetrics.filter((m) => {
      if (state.catalogLayerFilter !== "ALL" && m.layer_code !== state.catalogLayerFilter) {
        return false;
      }
      if (state.catalogLocFilter !== "ALL" && !(m.collection_location || "").includes(state.catalogLocFilter)) {
        return false;
      }
      if (q) {
        const hay = `${m.id} ${m.name_ko} ${m.name_en} ${m.description} ${(m.collection_method && m.collection_method.command) || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });

    setText("catalog-count-label", String(filtered.length));

    const tbody = document.getElementById("catalog-table-body");
    if (tbody) {
      tbody.innerHTML = filtered.map((m) => {
        const isSel = m.id === state.selectedMetricId;
        const th = m.thresholds || {};
        const load = m.system_load || {};
        const layerBadge = m.layer_code === "L1_L2" ? "badge-sky" : (m.layer_code === "L3_L4" ? "badge-indigo" : "badge-ok");
        const loadBadge = (load.level || "").includes("매우") ? "badge-ok" : "badge-sky";

        return `
          <tr class="${isSel ? "selected-row" : ""}" data-metric-row="${escapeHtml(m.id)}">
            <td class="text-center mono"><strong>${escapeHtml(m.id)}</strong></td>
            <td class="text-center"><span class="badge ${layerBadge}">${escapeHtml(m.layer_code)}</span></td>
            <td class="text-left">
              <div class="text-h3">${escapeHtml(m.name_ko)}</div>
              <div class="text-caption mono">${escapeHtml(m.name_en)}</div>
            </td>
            <td class="text-right mono">
              <div><strong>${escapeHtml(m.unit)}</strong></div>
              <div class="text-caption color-crit">위험: ${escapeHtml(th.critical || "-")}</div>
            </td>
            <td class="text-center"><span class="badge badge-neutral">${escapeHtml(m.collection_location)}</span></td>
            <td class="text-center mono">
              <div>로컬 ${escapeHtml(m.interval_local || "1s")}</div>
              <div class="text-caption">보고 30s</div>
            </td>
            <td class="text-center"><span class="badge ${loadBadge}">${escapeHtml(load.level || "매우 낮음")}</span></td>
          </tr>
        `;
      }).join("");

      tbody.querySelectorAll("tr[data-metric-row]").forEach((row) => {
        row.addEventListener("click", () => {
          state.selectedMetricId = row.getAttribute("data-metric-row") || "M01";
          renderMetricsCatalog();
        });
      });
    }

    // Render Right 8-Requirement Inspector for Selected Metric
    const selMetric = allMetrics.find((m) => m.id === state.selectedMetricId) || filtered[0] || allMetrics[0];
    if (selMetric) {
      renderMetricDetailInspector(selMetric);
    }

    // Render Bottom Full 18-Metric Cards Grid
    const gridEl = document.getElementById("catalog-cards-grid");
    if (gridEl) {
      gridEl.innerHTML = filtered.map((m) => {
        const th = m.thresholds || {};
        const load = m.system_load || {};
        const method = m.collection_method || {};
        const usage = m.analysis_usage || {};
        return `
          <div class="metric-summary-card" data-metric-card="${escapeHtml(m.id)}">
            <div>
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span class="badge badge-sky mono">${escapeHtml(m.id)} • ${escapeHtml(m.layer)}</span>
                <span class="badge badge-ok mono">부하: ${escapeHtml(load.level || "매우 낮음")}</span>
              </div>
              <h3 class="text-h2" style="margin-bottom:4px;">${escapeHtml(m.name_ko)} <span class="text-caption mono">(${escapeHtml(m.name_en)})</span></h3>
              <p class="text-body" style="font-size:0.78rem; margin-bottom:8px;">${escapeHtml(m.description)}</p>
            </div>
            <div class="detail-section-box mono" style="font-size:0.72rem;">
              <div>• <strong>단위/임계치</strong>: ${escapeHtml(m.unit)} (정상 ${escapeHtml(th.normal)} / 위험 ${escapeHtml(th.critical)})</div>
              <div>• <strong>수집위치/주기</strong>: ${escapeHtml(m.collection_location)} | ${escapeHtml(m.recommended_interval)}</div>
              <div>• <strong>수집방법</strong>: <code>${escapeHtml(method.command || method.interface || "")}</code></div>
              <div style="margin-top:4px; color:var(--accent-primary);">• <strong>분석활용</strong>: ${escapeHtml(usage.pre_detection || usage.post_mortem || "")}</div>
            </div>
          </div>
        `;
      }).join("");

      gridEl.querySelectorAll("[data-metric-card]").forEach((card) => {
        card.addEventListener("click", () => {
          state.selectedMetricId = card.getAttribute("data-metric-card") || "M01";
          renderMetricsCatalog();
          document.getElementById("panel-catalog-detail")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
        });
      });
    }
  }

  function renderMetricDetailInspector(m) {
    setText("detail-metric-id", `${m.id} • ${m.name_en}`);
    const box = document.getElementById("metric-detail-inspector");
    if (!box) return;

    const th = m.thresholds || {};
    const load = m.system_load || {};
    const method = m.collection_method || {};
    const usage = m.analysis_usage || {};

    box.innerHTML = `
      <!-- 1 & 2: Name & Detailed Description -->
      <div class="detail-section-box">
        <div class="detail-section-label">
          <span>① 수집 항목명 &amp; ② 상세 설명</span>
          <span class="badge badge-sky">${escapeHtml(m.layer)}</span>
        </div>
        <div class="text-h2" style="margin-bottom:4px;">${escapeHtml(m.name_ko)} <span class="mono text-caption">(${escapeHtml(m.name_en)})</span></div>
        <p class="text-body" style="font-size:0.8rem;">${escapeHtml(m.description)}</p>
      </div>

      <!-- 3: Unit & Thresholds -->
      <div class="detail-section-box">
        <div class="detail-section-label">
          <span>③ 측정 값 단위 및 기준 임계치</span>
          <span class="mono color-accent">단위: ${escapeHtml(m.unit)}</span>
        </div>
        <div class="threshold-tri-bar mono">
          <div class="thresh-cell ok">
            <span class="text-caption color-ok">정상 (Normal)</span>
            <strong>${escapeHtml(th.normal || "-")}</strong>
          </div>
          <div class="thresh-cell warn">
            <span class="text-caption color-warn">주의 (Warning)</span>
            <strong>${escapeHtml(th.warning || "-")}</strong>
          </div>
          <div class="thresh-cell crit">
            <span class="text-caption color-crit">위험 (Critical)</span>
            <strong>${escapeHtml(th.critical || "-")}</strong>
          </div>
        </div>
      </div>

      <!-- 4 & 5: Collection Location & Recommended Interval -->
      <div class="detail-section-box">
        <div class="detail-section-label">
          <span>④ 수집 위치 &amp; ⑤ 권장 수집 주기</span>
          <span class="badge badge-ok">${escapeHtml(m.collection_location)}</span>
        </div>
        <div class="mono" style="font-size:0.78rem; display:flex; flex-direction:column; gap:4px;">
          <div>• <strong>수집 주체 위치</strong>: ${escapeHtml(m.collection_location)}</div>
          <div>• <strong>권장 수집 주기</strong>: <span class="color-accent">${escapeHtml(m.recommended_interval || `로컬 ${m.interval_local} / 보고 ${m.interval_report}`)}</span></div>
        </div>
      </div>

      <!-- 6: System & Network Load Impact -->
      <div class="detail-section-box">
        <div class="detail-section-label">
          <span>⑥ 수집 시 수집 위치에 미치는 부하</span>
          <span class="badge badge-ok">부하 등급: ${escapeHtml(load.level || "매우 낮음")}</span>
        </div>
        <div class="mono" style="font-size:0.76rem; margin-bottom:4px;">
          CPU 오버헤드: <strong>${escapeHtml(load.cpu_overhead || "< 0.1%")}</strong> | 무선 네트워크 오버헤드: <strong>${escapeHtml(load.network_overhead || "0 Bytes/s (로컬 링버퍼)")}</strong>
        </div>
        <p class="text-caption" style="color:var(--text-secondary);">${escapeHtml(load.detail || "")}</p>
      </div>

      <!-- 7: Collection Method (Kernel Interface, Command, Code Snippet) -->
      <div class="detail-section-box">
        <div class="detail-section-label">
          <span>⑦ 실제 수집 방법 (커널 인터페이스 &amp; 명령어)</span>
          <span class="mono text-caption">${escapeHtml(method.interface || "Linux Kernel")}</span>
        </div>
        <div class="mono" style="font-size:0.76rem; color:var(--accent-primary);">명령어: <code>${escapeHtml(method.command || "")}</code></div>
        <pre class="code-snippet-box mono">${escapeHtml(method.code_snippet || method.detail || "")}</pre>
      </div>

      <!-- 8: Pre-Detection & Post-Mortem RCA Usage -->
      <div class="detail-section-box" style="border-left:3px solid var(--status-warn);">
        <div class="detail-section-label">
          <span>⑧ 사전 감지(Pre-Detection) 및 사후 원인 분석(RCA) 활용법</span>
          <span class="badge badge-warn mono">가중치: ${usage.weight !== undefined ? usage.weight : 0.15}</span>
        </div>
        <div style="font-size:0.78rem; display:flex; flex-direction:column; gap:6px;">
          <div><strong class="color-warn">[사전 감지 활용]</strong> ${escapeHtml(usage.pre_detection || "")}</div>
          <div><strong class="color-accent">[사후 분석 활용]</strong> ${escapeHtml(usage.post_mortem || "")}</div>
        </div>
      </div>
    `;
  }

  // ==========================================================================
  // 12. Tab 4: Hybrid Architecture JSON Inspector & Fleet Overhead Calculator
  // ==========================================================================
  function renderPacketInspector() {
    const pkt = PACKET_EXAMPLES[state.activePacketType] || PACKET_EXAMPLES.piggyback;
    setText("arch-pkt-desc", pkt.desc);
    const viewer = document.getElementById("arch-json-viewer");
    if (viewer) {
      viewer.textContent = JSON.stringify(pkt.payload, null, 2);
    }
  }

  function updateBandwidthCalculator() {
    const agvSlider = document.getElementById("calc-agv-count");
    const ringSlider = document.getElementById("calc-ring-sec");
    const agvCount = agvSlider ? Number(agvSlider.value) : 25;
    const ringSec = ringSlider ? Number(ringSlider.value) : 300;

    setText("calc-agv-count-val", `${agvCount} 대`);
    setText("calc-ring-sec-val", `${ringSec} 초 (${Math.round(ringSec / 60)}분)`);

    // 1 sample = 480 bytes in local ring buffer
    const ramKb = ((ringSec * 480) / 1024).toFixed(1);
    // 30s piggyback = 120 bytes per 30s = 4 bytes/s = 32 bps per AGV
    const totalBwKbps = ((agvCount * 32) / 1000).toFixed(2);
    // Daily TSDB storage (30s summaries + ~5 incidents/day)
    const diskMb = (agvCount * 0.88 + 0.4).toFixed(1);

    setText("calc-out-cpu", "0.14 %");
    setText("calc-out-ram", `${ramKb} KB`);
    setText("calc-out-bw", `${totalBwKbps} kbps`);
    setText("calc-out-disk", `${diskMb} MB/일`);
  }

  // ==========================================================================
  // 13. Interactive 7-Step Spotlight Guided Tour
  // ==========================================================================
  function startTour(stepIdx = 0) {
    state.tourActive = true;
    state.tourStepIndex = stepIdx;
    document.getElementById("tour-backdrop")?.classList.add("active");
    document.getElementById("tour-popover")?.classList.add("active");
    renderTourStep();
  }

  function closeTour() {
    state.tourActive = false;
    document.getElementById("tour-backdrop")?.classList.remove("active");
    document.getElementById("tour-popover")?.classList.remove("active");
    document.getElementById("tour-spotlight-ring")?.classList.remove("active");
  }

  function renderTourStep() {
    if (!state.tourActive) return;
    const step = TOUR_STEPS[state.tourStepIndex];
    if (!step) return;

    if (state.activeTab !== step.tab) {
      switchTab(step.tab);
    }

    // Unhide welcome banner if step 0 targets it
    if (step.targetSelector === "#welcome-tour-banner") {
      document.getElementById("welcome-tour-banner")?.classList.remove("hidden");
    }

    setText("tour-step-badge", `STEP ${state.tourStepIndex + 1} / ${TOUR_STEPS.length}`);
    setText("tour-step-title", step.title);
    setText("tour-step-body", step.body);
    setText("tour-step-takeaway", step.takeaway);

    const dotsEl = document.getElementById("tour-step-dots");
    if (dotsEl) {
      dotsEl.innerHTML = TOUR_STEPS.map((_, idx) =>
        `<span class="tour-dot ${idx === state.tourStepIndex ? "active" : ""}"></span>`
      ).join("");
    }

    const prevBtn = document.getElementById("btn-tour-prev");
    const nextBtn = document.getElementById("btn-tour-next");
    if (prevBtn) prevBtn.disabled = state.tourStepIndex === 0;
    if (nextBtn) {
      nextBtn.textContent = state.tourStepIndex === TOUR_STEPS.length - 1 ? "투어 완료 ✓" : "다음 단계 →";
    }

    setTimeout(() => {
      const target = document.querySelector(step.targetSelector);
      const ring = document.getElementById("tour-spotlight-ring");
      if (target && ring) {
        target.scrollIntoView({ behavior: "smooth", block: "center" });
        setTimeout(() => {
          const rect = target.getBoundingClientRect();
          ring.classList.add("active");
          ring.style.top = `${Math.max(4, rect.top - 6)}px`;
          ring.style.left = `${Math.max(4, rect.left - 6)}px`;
          ring.style.width = `${rect.width + 12}px`;
          ring.style.height = `${rect.height + 12}px`;
        }, 220);
      }
    }, 60);
  }

  // ==========================================================================
  // 14. Tab Navigation & Event Listeners Binding
  // ==========================================================================
  function switchTab(tabId) {
    state.activeTab = tabId;
    document.querySelectorAll(".nav-tab").forEach((btn) => {
      const active = btn.getAttribute("data-tab") === tabId;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-selected", active ? "true" : "false");
    });
    document.querySelectorAll(".tab-view").forEach((sec) => {
      sec.classList.toggle("active", sec.id === tabId);
    });

    if (tabId === "tab-live") {
      drawFactoryFloorMap();
      drawLiveMiniChart();
    } else if (tabId === "tab-rca") {
      updateRcaCursorAndCharts();
    }
  }

  function bindEvents() {
    // 1. Top Nav Tabs
    document.querySelectorAll(".nav-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        const target = btn.getAttribute("data-tab");
        if (target) switchTab(target);
      });
    });

    // 2. Theme Toggle (Dark Slate <-> Light Enterprise)
    document.getElementById("btn-theme-toggle")?.addEventListener("click", () => {
      state.theme = state.theme === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", state.theme);
      setText("theme-icon", state.theme === "dark" ? "☀️" : "🌙");
      setText("theme-label", state.theme === "dark" ? "Light 테마" : "Dark 테마");
      drawFactoryFloorMap();
      drawLiveMiniChart();
      updateRcaCursorAndCharts();
    });

    // 3. Welcome Banner & Guided Tour Controls
    document.getElementById("btn-start-tour")?.addEventListener("click", () => startTour(0));
    document.getElementById("btn-welcome-start-tour")?.addEventListener("click", () => startTour(0));
    document.getElementById("btn-welcome-close")?.addEventListener("click", () => {
      document.getElementById("welcome-tour-banner")?.classList.add("hidden");
    });
    document.getElementById("btn-tour-close")?.addEventListener("click", closeTour);
    document.getElementById("btn-tour-prev")?.addEventListener("click", () => {
      if (state.tourStepIndex > 0) {
        state.tourStepIndex--;
        renderTourStep();
      }
    });
    document.getElementById("btn-tour-next")?.addEventListener("click", () => {
      if (state.tourStepIndex < TOUR_STEPS.length - 1) {
        state.tourStepIndex++;
        renderTourStep();
      } else {
        closeTour();
      }
    });

    // 4. Tab 1: Map Toggles & Click-to-Select AGV
    document.getElementById("btn-toggle-heatmap")?.addEventListener("click", (e) => {
      state.showHeatmap = !state.showHeatmap;
      e.currentTarget.textContent = `전파 반경: ${state.showHeatmap ? "ON" : "OFF"}`;
      drawFactoryFloorMap();
    });
    document.getElementById("btn-toggle-zones")?.addEventListener("click", (e) => {
      state.showDangerZones = !state.showDangerZones;
      e.currentTarget.textContent = `음영/EMI 구역: ${state.showDangerZones ? "ON" : "OFF"}`;
      drawFactoryFloorMap();
    });

    const mapCanvas = document.getElementById("factory-map-canvas");
    if (mapCanvas) {
      mapCanvas.addEventListener("click", (ev) => {
        const rect = mapCanvas.getBoundingClientRect();
        const mx = ev.clientX - rect.left;
        const my = ev.clientY - rect.top;
        const boxes = state._renderedAgvHitboxes || [];
        for (const b of boxes) {
          const dist = Math.hypot(mx - b.x, my - b.y);
          if (dist <= b.r) {
            selectAgv(b.agv_id);
            break;
          }
        }
      });
    }

    // 5. Tab 1: Live Scenario Injector & Reset
    document.querySelectorAll(".btn-scenario-trigger").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const scnCode = btn.getAttribute("data-scn") || "SCN-01";
        const targetSelect = document.getElementById("injector-target-agv");
        const agvId = (targetSelect && targetSelect.value) || state.selectedAgvId;
        state.selectedAgvId = agvId;

        const msgBox = document.getElementById("injector-status-msg");
        if (msgBox) {
          msgBox.innerHTML = `<span class="color-warn">🚨 <strong>[${escapeHtml(agvId)}]</strong>에 <strong>${escapeHtml(scnCode)}</strong> 장애 시나리오를 실시간 주입했습니다! (사전 감지 경보 → 단절 → 복구 진행 중)</span>`;
        }

        await fetchJson("/api/scenarios/trigger", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ agv_id: agvId, scenario_code: scnCode })
        });
        await pollLiveTelemetry();
      });
    });

    document.getElementById("btn-scenario-reset")?.addEventListener("click", async () => {
      await fetchJson("/api/scenarios/reset", { method: "POST" });
      const msgBox = document.getElementById("injector-status-msg");
      if (msgBox) {
        msgBox.innerHTML = `<span class="color-ok">✅ 모든 AGV의 장애 시나리오가 초기화되어 정상(CONNECTED) 상태로 복구되었습니다.</span>`;
      }
      await pollLiveTelemetry();
    });

    // 6. Tab 2: Scenario Selector Cards, Timeline Slider & Playback
    document.querySelectorAll("[data-scn-card]").forEach((card) => {
      card.addEventListener("click", () => {
        const code = card.getAttribute("data-scn-card");
        if (code) selectRcaScenario(code);
      });
    });

    const timeSlider = document.getElementById("rca-time-slider");
    if (timeSlider) {
      timeSlider.addEventListener("input", () => {
        state.rcaCursorOffset = Number(timeSlider.value);
        updateRcaCursorAndCharts();
      });
    }

    document.querySelectorAll("[data-jump]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const off = Number(btn.getAttribute("data-jump") || -18);
        state.rcaCursorOffset = off;
        if (timeSlider) timeSlider.value = String(off);
        updateRcaCursorAndCharts();
      });
    });

    document.getElementById("btn-rca-play")?.addEventListener("click", (e) => {
      const btn = e.currentTarget;
      if (state.rcaPlaying) {
        state.rcaPlaying = false;
        clearInterval(state.rcaPlayTimer);
        btn.textContent = "▶ 타임라인 재생";
      } else {
        state.rcaPlaying = true;
        btn.textContent = "⏸ 일시정지";
        if (state.rcaCursorOffset >= 30) state.rcaCursorOffset = -89;
        state.rcaPlayTimer = setInterval(() => {
          if (state.rcaCursorOffset < 30) {
            state.rcaCursorOffset++;
            if (timeSlider) timeSlider.value = String(state.rcaCursorOffset);
            updateRcaCursorAndCharts();
          } else {
            state.rcaPlaying = false;
            clearInterval(state.rcaPlayTimer);
            btn.textContent = "▶ 타임라인 재생";
          }
        }, 180);
      }
    });

    document.getElementById("btn-rca-reset-cursor")?.addEventListener("click", () => {
      state.rcaCursorOffset = -89;
      if (timeSlider) timeSlider.value = "-89";
      updateRcaCursorAndCharts();
    });

    // Click/Drag on any of the 3 synchronized RCA chart canvases
    ["rca-chart-l1", "rca-chart-l2", "rca-chart-l3"].forEach((cid) => {
      const c = document.getElementById(cid);
      if (!c) return;
      const handleScrub = (ev) => {
        const rect = c.getBoundingClientRect();
        const padL = 42, padR = 18;
        const cw = rect.width - padL - padR;
        const relX = Math.max(0, Math.min(cw, ev.clientX - rect.left - padL));
        const ratio = relX / Math.max(1, cw);
        const off = Math.round(-89 + ratio * 119);
        state.rcaCursorOffset = Math.max(-89, Math.min(30, off));
        if (timeSlider) timeSlider.value = String(state.rcaCursorOffset);
        updateRcaCursorAndCharts();
      };
      c.addEventListener("mousedown", handleScrub);
      c.addEventListener("mousemove", (ev) => {
        if (ev.buttons === 1) handleScrub(ev);
      });
    });

    // 7. Tab 3: Metrics Catalog Filters & Search
    document.querySelectorAll("#catalog-layer-filters .filter-pill").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#catalog-layer-filters .filter-pill").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.catalogLayerFilter = btn.getAttribute("data-layer") || "ALL";
        renderMetricsCatalog();
      });
    });

    document.querySelectorAll("#catalog-loc-filters .filter-pill").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#catalog-loc-filters .filter-pill").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.catalogLocFilter = btn.getAttribute("data-loc") || "ALL";
        renderMetricsCatalog();
      });
    });

    document.getElementById("catalog-search-input")?.addEventListener("input", (e) => {
      state.catalogSearchQuery = e.target.value || "";
      renderMetricsCatalog();
    });

    // 8. Tab 4: Packet Inspector Tabs & Fleet Calculator Sliders
    document.querySelectorAll("#arch-packet-tabs button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#arch-packet-tabs button").forEach((b) => b.classList.remove("btn-primary"));
        btn.classList.add("btn-primary");
        state.activePacketType = btn.getAttribute("data-pkt") || "piggyback";
        renderPacketInspector();
      });
    });

    document.getElementById("calc-agv-count")?.addEventListener("input", updateBandwidthCalculator);
    document.getElementById("calc-ring-sec")?.addEventListener("input", updateBandwidthCalculator);

    window.addEventListener("resize", () => {
      if (state.activeTab === "tab-live") {
        drawFactoryFloorMap();
        drawLiveMiniChart();
      } else if (state.activeTab === "tab-rca") {
        updateRcaCursorAndCharts();
      }
      if (state.tourActive) renderTourStep();
    });
  }

  // ==========================================================================
  // 15. Built-in Fallback 18 Metrics Catalog (Matches docs/ANALYSIS_AND_METRICS.md)
  // ==========================================================================
  function getFallbackMetricsCatalog() {
    return [
      {
        id: "M01", key: "rssi", name_ko: "수신 신호 강도", name_en: "RSSI (Received Signal Strength Indicator)",
        layer: "L1/L2 무선 물리·MAC", layer_code: "L1_L2", unit: "dBm",
        description: "AGV 무선 랜카드가 수신하는 연결 AP의 전파 신호 세기. 이동 경로상 전파 감쇠 및 음영 구역 진입을 가장 직접적으로 나타냄.",
        thresholds: { normal: "≥ -67 dBm", warning: "-68 ~ -74 dBm", critical: "≤ -75 dBm" },
        collection_location: "AGV/AMR", interval_local: "1s", interval_report: "30s 요약 피기백",
        recommended_interval: "로컬 1s (링버퍼) / 보고 30s (피기백)",
        system_load: { level: "매우 낮음", cpu_overhead: "< 0.05%", network_overhead: "0 B/s (로컬)", detail: "커널 /proc/net/wireless 메모리 구조체 직접 읽기로 부하 없음" },
        collection_method: { interface: "/proc/net/wireless, nl80211", command: "iw dev wlan0 link | grep signal", code_snippet: "with open('/proc/net/wireless') as f:\n    rssi_dbm = float(f.readlines()[2].split()[3].rstrip('.'))" },
        analysis_usage: { weight: 0.25, pre_detection: "5초간 RSSI 기울기(d(RSSI)/dt ≤ -2.5 dBm/s)로 음영 진입을 단절 15~18초 전 감지", post_mortem: "단절 시점 좌표(X,Y)와 결합해 물리적 음영(SCN-02) vs 채널 혼잡(SCN-03) 구분" }
      },
      {
        id: "M02", key: "snr", name_ko: "신호 대 잡음비", name_en: "SNR (Signal-to-Noise Ratio)",
        layer: "L1/L2 무선 물리·MAC", layer_code: "L1_L2", unit: "dB",
        description: "배경 잡음(Noise Floor) 대비 유효 무선 신호 강도의 비율. 실제 심볼 복조 품질을 결정하는 핵심 지표.",
        thresholds: { normal: "≥ 25 dB", warning: "18 ~ 24 dB", critical: "≤ 17 dB" },
        collection_location: "AGV/AMR, AP/WLC", interval_local: "1s", interval_report: "30s 요약 피기백",
        recommended_interval: "로컬 1s (링버퍼) / 보고 30s (피기백)",
        system_load: { level: "매우 낮음", cpu_overhead: "< 0.05%", network_overhead: "0 B/s (로컬)", detail: "RSSI와 Noise Floor 차분 연산" },
        collection_method: { interface: "nl80211 survey dump", command: "iw dev wlan0 survey dump", code_snippet: "snr_db = rssi_dbm - noise_floor_dbm" },
        analysis_usage: { weight: 0.15, pre_detection: "RSSI가 양호해도 SNR이 18dB 이하로 급락하면 즉각 조기 경보 발령", post_mortem: "용접기/인버터 고주파 전자기 간섭(SCN-02 EMI) 원인 규명의 결정적 증거" }
      },
      {
        id: "M03", key: "noise_floor", name_ko: "배경 잡음 준위", name_en: "Noise Floor",
        layer: "L1/L2 무선 물리·MAC", layer_code: "L1_L2", unit: "dBm",
        description: "해당 무선 주파수 채널의 기저 열잡음 및 비-Wi-Fi 광대역 전자기 간섭 에너지 수준.",
        thresholds: { normal: "≤ -90 dBm", warning: "-89 ~ -85 dBm", critical: "≥ -84 dBm" },
        collection_location: "AGV/AMR, AP/WLC", interval_local: "5s", interval_report: "30s 요약 피기백",
        recommended_interval: "로컬 5s (링버퍼) / 보고 30s (피기백)",
        system_load: { level: "낮음", cpu_overhead: "< 0.1%", network_overhead: "0 B/s", detail: "NIC 채널 Survey 레지스터 조회" },
        collection_method: { interface: "nl80211 NL80211_CMD_GET_SURVEY", command: "iw dev wlan0 survey dump | grep noise", code_snippet: "# nl80211 survey attribute NL80211_SURVEY_INFO_NOISE\nnoise_dbm = survey_info['noise']" },
        analysis_usage: { weight: 0.10, pre_detection: "특정 설비 가동 시 기저 잡음 상승 추세 감지", post_mortem: "단절 원인이 AP 고장이 아닌 공장 내 고주파 용접/모터 노이즈(SCN-02)임을 입증" }
      },
      {
        id: "M04", key: "phy_rate", name_ko: "물리 계층 전송 속도", name_en: "Tx/Rx PHY Bitrate (MCS)",
        layer: "L1/L2 무선 물리·MAC", layer_code: "L1_L2", unit: "Mbps",
        description: "무선 칩셋이 현재 신호 품질에 맞춰 협상한 MCS(변조 및 코딩) 실제 물리 링크 속도.",
        thresholds: { normal: "≥ 100 Mbps", warning: "24 ~ 99 Mbps", critical: "≤ 18 Mbps" },
        collection_location: "AGV/AMR", interval_local: "1s", interval_report: "30s 요약 피기백",
        recommended_interval: "로컬 1s (링버퍼) / 보고 30s (피기백)",
        system_load: { level: "매우 낮음", cpu_overhead: "< 0.05%", network_overhead: "0 B/s", detail: "nl80211 station info 구조체 읽기" },
        collection_method: { interface: "nl80211 NL80211_ATTR_STA_INFO", command: "iw dev wlan0 link | grep 'tx bitrate'", code_snippet: "tx_bitrate_mbps = sta_info['tx_bitrate'] / 10.0" },
        analysis_usage: { weight: 0.10, pre_detection: "패킷 유실 전 무선 드라이버가 속도를 낮추는 Dynamic Rate Fallback 포착", post_mortem: "변조 방식이 6Mbps(BPSK)까지 떨어진 시점 확인" }
      },
      {
        id: "M05", key: "l2_retry_rate", name_ko: "802.11 MAC 재전송률", name_en: "L2 MAC Retry Rate",
        layer: "L1/L2 무선 물리·MAC", layer_code: "L1_L2", unit: "%",
        description: "무선 프레임 전송 후 AP로부터 802.11 ACK를 받지 못해 MAC 계층에서 재시도한 비율.",
        thresholds: { normal: "< 8 %", warning: "8 ~ 20 %", critical: "> 20 %" },
        collection_location: "AGV/AMR, AP/WLC", interval_local: "1s", interval_report: "30s 요약 피기백",
        recommended_interval: "로컬 1s (링버퍼) / 보고 30s (피기백)",
        system_load: { level: "낮음", cpu_overhead: "< 0.08%", network_overhead: "0 B/s", detail: "NIC 드라이버 하드웨어 카운터 차분 계산" },
        collection_method: { interface: "nl80211 / ethtool -S wlan0", command: "iw dev wlan0 station dump | grep 'tx retries'", code_snippet: "retry_rate = (delta_tx_retries / max(1, delta_tx_packets)) * 100.0" },
        analysis_usage: { weight: 0.20, pre_detection: "L4 TCP 재전송이 터지기 수 초 전에 가장 먼저 치솟는 핵심 선행 지표", post_mortem: "무선 구간 프레임 손실 여부 직접 판별" }
      },
      {
        id: "M06", key: "beacon_loss", name_ko: "비콘 프레임 손실 수", name_en: "Beacon Loss Count",
        layer: "L1/L2 무선 물리·MAC", layer_code: "L1_L2", unit: "count/s",
        description: "AP가 102.4ms 주기로 브로드캐스트하는 관리 비콘 프레임을 AGV가 놓친 횟수.",
        thresholds: { normal: "0 ~ 1 /s", warning: "2 ~ 4 /s", critical: "≥ 5 /s" },
        collection_location: "AGV/AMR", interval_local: "1s", interval_report: "30s 요약 피기백",
        recommended_interval: "로컬 1s (링버퍼) / 보고 30s (피기백)",
        system_load: { level: "매우 낮음", cpu_overhead: "< 0.05%", network_overhead: "0 B/s", detail: "nl80211 STA_INFO_BEACON_LOSS 카운터" },
        collection_method: { interface: "nl80211 STA_INFO_BEACON_LOSS", command: "iw dev wlan0 station dump | grep 'beacon loss'", code_snippet: "beacon_loss_delta = sta_info['beacon_loss'] - prev_beacon_loss" },
        analysis_usage: { weight: 0.10, pre_detection: "연속 비콘 유실 시 2~3초 내 L2 Deauth/Disassoc 발생 예고", post_mortem: "은폐 노드(Hidden Node) 및 로밍 임계 상태 진단" }
      },
      {
        id: "M07", key: "roaming_ms", name_ko: "AP 로밍 소요 시간 및 BSSID", name_en: "Roaming Handover Latency & BSSID",
        layer: "L1/L2 무선 물리·MAC", layer_code: "L1_L2", unit: "ms",
        description: "AGV가 인접 AP로 핸드오버할 때 채널 스캔 + 인증(802.1X) + 재연결에 소요된 무통신 시간.",
        thresholds: { normal: "< 50 ms", warning: "50 ~ 150 ms", critical: "> 200 ms" },
        collection_location: "AGV/AMR, AP/WLC", interval_local: "Event 즉시", interval_report: "30s 요약 피기백",
        recommended_interval: "이벤트 발생 즉시 (1s 감시) / 보고 30s",
        system_load: { level: "매우 낮음", cpu_overhead: "< 0.05%", network_overhead: "0 B/s", detail: "wpa_supplicant 컨트롤 소켓 이벤트 타임스탬프 비교" },
        collection_method: { interface: "wpa_supplicant control socket", command: "wpa_cli -i wlan0 status", code_snippet: "roam_ms = (ts_connected - ts_disconnecting) * 1000.0" },
        analysis_usage: { weight: 0.15, pre_detection: "잦은 핑퐁 로밍 및 로밍 지연 누적 감지", post_mortem: "Sticky Client 및 802.11r 미적용으로 인한 로밍 단절(SCN-01) 100% 판별" }
      },
      {
        id: "M08", key: "channel_util", name_ko: "무선 채널 점유율 (CCA Busy)", name_en: "Channel Utilization (CCA Busy %)",
        layer: "L1/L2 무선 물리·MAC", layer_code: "L1_L2", unit: "%",
        description: "현재 무선 주파수 채널에서 전체 시간 대비 프레임 송수신 및 간섭으로 매체가 사용 중인 비율.",
        thresholds: { normal: "< 40 %", warning: "40 ~ 65 %", critical: "> 65 %" },
        collection_location: "AP/WLC, AGV/AMR", interval_local: "5s", interval_report: "30s 요약 피기백",
        recommended_interval: "로컬 5s (링버퍼) / 보고 30s (피기백)",
        system_load: { level: "낮음", cpu_overhead: "< 0.1%", network_overhead: "0 B/s", detail: "Survey channel busy_time / active_time 비율 연산" },
        collection_method: { interface: "nl80211 survey / WLC RRM MIB", command: "iw dev wlan0 survey dump | grep -E 'active|busy'", code_snippet: "chan_util_pct = (delta_busy_time / max(1, delta_active_time)) * 100.0" },
        analysis_usage: { weight: 0.15, pre_detection: "신호 세기(RSSI)는 강하지만 채널 포화로 지연이 임박했음을 감지", post_mortem: "RSSI 양호 시 발생하는 동일 채널 과밀 장애(SCN-03) 핵심 증거" }
      },
      {
        id: "M09", key: "gw_rtt_ms", name_ko: "게이트웨이 ICMP 왕복 지연", name_en: "Gateway ICMP RTT",
        layer: "L3/L4 네트워크·전송", layer_code: "L3_L4", unit: "ms",
        description: "AGV에서 기본 L3 게이트웨이 스위치까지의 순수 무선 구간 Ping 왕복 지연 시간.",
        thresholds: { normal: "< 10 ms", warning: "10 ~ 40 ms", critical: "> 50 ms" },
        collection_location: "AGV/AMR", interval_local: "2s", interval_report: "30s 요약 피기백",
        recommended_interval: "로컬 2s (링버퍼) / 보고 30s (피기백)",
        system_load: { level: "낮음", cpu_overhead: "< 0.1%", network_overhead: "32 B/s (64B ICMP/2s)", detail: "비동기 Raw ICMP Echo 프로브" },
        collection_method: { interface: "ICMP Socket / fping", command: "ping -c 1 -W 1 192.168.10.1", code_snippet: "gw_rtt_ms = async_icmp_probe('192.168.10.1', timeout=0.5)" },
        analysis_usage: { weight: 0.15, pre_detection: "무선 구간 큐잉 지연 상승 조기 포착", post_mortem: "무선 구간(AGV↔GW) 장애인지 유선/ACS 서버(GW↔ACS) 장애인지 경계 분리" }
      },
      {
        id: "M10", key: "jitter_ms", name_ko: "네트워크 지연 편차 (지터)", name_en: "RTT Jitter",
        layer: "L3/L4 네트워크·전송", layer_code: "L3_L4", unit: "ms",
        description: "연속된 패킷 왕복 지연 시간(RTT)의 변동성. 무선 매체 경합 및 로밍 스캔 시 급증함.",
        thresholds: { normal: "< 5 ms", warning: "5 ~ 20 ms", critical: "> 20 ms" },
        collection_location: "AGV/AMR, ACS Server", interval_local: "2s", interval_report: "30s 요약 피기백",
        recommended_interval: "로컬 2s (링버퍼) / 보고 30s (피기백)",
        system_load: { level: "매우 낮음", cpu_overhead: "< 0.02%", network_overhead: "0 B/s", detail: "연속 RTT 측정값의 차분 이동평균" },
        collection_method: { interface: "RTT Stream Diff", command: "ss -ti dst <ACS_IP> (rttvar)", code_snippet: "jitter_ms = abs(rtt_now - rtt_prev)" },
        analysis_usage: { weight: 0.10, pre_detection: "평균 RTT가 낮아도 스파이크성 지터 발생 시 무선 불안정 사전 경고", post_mortem: "채널 경합(SCN-03)으로 인한 불규칙 전송 지연 판별" }
      },
      {
        id: "M11", key: "tcp_retrans", name_ko: "TCP 세그먼트 재전송 수", name_en: "TCP Retransmissions",
        layer: "L3/L4 네트워크·전송", layer_code: "L3_L4", unit: "count/s",
        description: "AGV-ACS TCP 소켓 세션에서 상대방 ACK를 받지 못해 커널 TCP 스택이 세그먼트를 재전송한 횟수.",
        thresholds: { normal: "0 /s", warning: "1 ~ 3 /s", critical: "≥ 4 /s" },
        collection_location: "AGV/AMR, ACS Server", interval_local: "1s", interval_report: "30s 요약 피기백",
        recommended_interval: "로컬 1s (링버퍼) / 보고 30s (피기백)",
        system_load: { level: "매우 낮음", cpu_overhead: "< 0.05%", network_overhead: "0 B/s", detail: "NETLINK_INET_DIAG tcp_info 커널 구조체 직접 조회" },
        collection_method: { interface: "NETLINK_INET_DIAG / tcp_info", command: "ss -ti state established dst <ACS_IP>", code_snippet: "tcp_info = sock.getsockopt(socket.SOL_TCP, socket.TCP_INFO, 104)\nretrans_delta = tcpi_total_retrans - prev_retrans" },
        analysis_usage: { weight: 0.25, pre_detection: "TCP Exponential Backoff(재전송 타이머 지수 증가)로 소켓이 멈추기 직전 포착", post_mortem: "L4 전송 계층 패킷 유실 강도 정량화" }
      },
      {
        id: "M12", key: "tcp_srtt_ms", name_ko: "TCP 평활 왕복 지연 (srtt)", name_en: "TCP Smoothed RTT (tcpi_rtt)",
        layer: "L3/L4 네트워크·전송", layer_code: "L3_L4", unit: "ms",
        description: "커널 TCP 스택이 실제 제어/보고 패킷과 ACK 시간차로 계산한 AGV↔ACS 종단 간 왕복 지연.",
        thresholds: { normal: "< 15 ms", warning: "15 ~ 60 ms", critical: "> 60 ms" },
        collection_location: "AGV/AMR, ACS Server", interval_local: "1s", interval_report: "30s 요약 피기백",
        recommended_interval: "로컬 1s (링버퍼) / 보고 30s (피기백)",
        system_load: { level: "매우 낮음", cpu_overhead: "< 0.03%", network_overhead: "0 B/s (추가 패킷 없음)", detail: "커널 소켓 tcp_info.tcpi_rtt 읽기" },
        collection_method: { interface: "Linux tcp_info (tcpi_rtt)", command: "ss -ti dst <ACS_IP>", code_snippet: "srtt_ms = tcpi_rtt_us / 1000.0" },
        analysis_usage: { weight: 0.10, pre_detection: "별도 Ping 없이 실제 소켓 종단 지연 상승 감지", post_mortem: "Gateway RTT와 비교하여 무선 vs 유선/서버 구간 지연 분리" }
      },
      {
        id: "M13", key: "send_q_bytes", name_ko: "소켓 송신 대기 큐 크기", name_en: "Socket Send-Q Bytes",
        layer: "L3/L4 네트워크·전송", layer_code: "L3_L4", unit: "Bytes",
        description: "애플리케이션이 send() 호출로 기록했으나 상대방 ACK를 받지 못해 커널 송신 버퍼에 쌓여 있는 미전송 바이트 수.",
        thresholds: { normal: "0 Bytes", warning: "1 B ~ 4 KB", critical: "> 4 KB" },
        collection_location: "AGV/AMR, ACS Server", interval_local: "1s", interval_report: "30s 요약 피기백",
        recommended_interval: "로컬 1s (링버퍼) / 보고 30s (피기백)",
        system_load: { level: "매우 낮음", cpu_overhead: "< 0.03%", network_overhead: "0 B/s", detail: "ioctl(SIOCOUTQ) 또는 netlink 소켓 큐 조회" },
        collection_method: { interface: "ioctl(SIOCOUTQ) / ss -tnp", command: "ss -tnp dst <ACS_IP> | awk '{print $2}'", code_snippet: "send_q = fcntl.ioctl(sock.fileno(), termios.TIOCOUTQ, b'\\x00'*4)" },
        analysis_usage: { weight: 0.15, pre_detection: "Send-Q가 3초 이상 0으로 비워지지 않고 누적되면 수 초 내 소켓 단절 100% 예고!", post_mortem: "네트워크 불통으로 송신 버퍼가 막힌 시점 증명" }
      },
      {
        id: "M14", key: "recv_q_bytes", name_ko: "소켓 수신 대기 큐 크기", name_en: "Socket Recv-Q Bytes",
        layer: "L3/L4 네트워크·전송", layer_code: "L3_L4", unit: "Bytes",
        description: "커널 네트워크 스택이 패킷을 정상 수신했으나 AGV 또는 ACS 애플리케이션이 recv()로 읽어가지 못한 바이트 수.",
        thresholds: { normal: "0 Bytes", warning: "1 B ~ 2 KB", critical: "> 2 KB" },
        collection_location: "AGV/AMR, ACS Server", interval_local: "1s", interval_report: "30s 요약 피기백",
        recommended_interval: "로컬 1s (링버퍼) / 보고 30s (피기백)",
        system_load: { level: "매우 낮음", cpu_overhead: "< 0.03%", network_overhead: "0 B/s", detail: "ioctl(SIOCINQ) 또는 ss Recv-Q 조회" },
        collection_method: { interface: "ioctl(SIOCINQ) / ss -tnp", command: "ss -tnp dst <ACS_IP> | awk '{print $1}'", code_snippet: "recv_q = fcntl.ioctl(sock.fileno(), termios.FIONREAD, b'\\x00'*4)" },
        analysis_usage: { weight: 0.15, pre_detection: "애플리케이션 워커 스레드 블로킹 조기 감지", post_mortem: "무선 네트워크는 멀쩡한데 S/W 데드락으로 끊긴 장애(SCN-04)를 가려내는 결정적 지표!" }
      },
      {
        id: "M15", key: "hb_delta_sec", name_ko: "ACS 상태 보고 도착 간격", name_en: "Heartbeat Arrival Interval Delta",
        layer: "L7 응용·시스템", layer_code: "L7_SYS", unit: "sec",
        description: "ACS 서버가 AGV로부터 실제로 30초 주기 상태 보고 패킷을 수신한 시간 간격 (기준: 30.0초).",
        thresholds: { normal: "29.5 ~ 30.5 s", warning: "31.0 ~ 38.0 s", critical: "> 45.0 s (Timeout)" },
        collection_location: "ACS Server", interval_local: "매 보고 수신 시", interval_report: "매 보고 시",
        recommended_interval: "매 보고 수신 시 & 1s 타임아웃 워치독",
        system_load: { level: "매우 낮음", cpu_overhead: "< 0.01%", network_overhead: "0 B/s", detail: "ACS 수신 핸들러 인메모리 타임스탬프 비교" },
        collection_method: { interface: "ACS Socket Handler Timestamp", command: "T_arrival_now - T_arrival_prev", code_snippet: "hb_delta_sec = time.monotonic() - last_report_ts[agv_id]" },
        analysis_usage: { weight: 0.10, pre_detection: "보고 간격이 30.0s → 32.4s → 36.1s로 흔들리는 Arrival Drift 포착", post_mortem: "실제 상위 시스템(ACS) 관점의 단절 시각 및 지속 시간 확정" }
      },
      {
        id: "M16", key: "reconnect_count", name_ko: "TCP 재연결 횟수 및 종료 코드", name_en: "Socket Reconnect Count & RST/FIN Reason",
        layer: "L7 응용·시스템", layer_code: "L7_SYS", unit: "count/hr",
        description: "소켓 세션이 끊어져 3-Way Handshake(SYN)부터 다시 맺은 횟수 및 종료 사유(ETIMEDOUT, ECONNRESET, EOF).",
        thresholds: { normal: "0 /hr", warning: "1 ~ 2 /hr", critical: "≥ 3 /hr" },
        collection_location: "AGV/AMR, ACS Server", interval_local: "Event 즉시", interval_report: "이벤트 발생 시",
        recommended_interval: "소켓 이벤트 발생 즉시 기록",
        system_load: { level: "매우 낮음", cpu_overhead: "< 0.01%", network_overhead: "0 B/s", detail: "소켓 상태 전환 이벤트 로깅" },
        collection_method: { interface: "Application Socket Wrapper / eBPF", command: "journalctl -u agv-acs-agent | grep RECONNECT", code_snippet: "log_event(errno=sock_err, state='RECONNECTING')" },
        analysis_usage: { weight: 0.05, pre_detection: "반복 재연결 AGV 집중 감시 대상 지정", post_mortem: "단절이 무응답 타임아웃(ETIMEDOUT)인지 상대방 강제 리셋(RST)인지 구분" }
      },
      {
        id: "M17", key: "cpu_load", name_ko: "AGV 온보드 CPU 및 SoftIRQ 부하", name_en: "Host CPU Load & NET_RX SoftIRQ",
        layer: "L7 응용·시스템", layer_code: "L7_SYS", unit: "%",
        description: "AGV 온보드 컴퓨터(IPC/SBC)의 전체 CPU 사용률 및 네트워크 패킷 수신 인터럽트(NET_RX) 처리 비중.",
        thresholds: { normal: "< 60 %", warning: "60 ~ 85 %", critical: "> 85 %" },
        collection_location: "AGV/AMR", interval_local: "5s", interval_report: "30s 요약 피기백",
        recommended_interval: "로컬 5s (링버퍼) / 보고 30s (피기백)",
        system_load: { level: "매우 낮음", cpu_overhead: "< 0.04%", network_overhead: "0 B/s", detail: "/proc/stat 및 /proc/softirqs 커널 카운터 읽기" },
        collection_method: { interface: "/proc/stat, /proc/softirqs", command: "mpstat 1 1 / cat /proc/stat", code_snippet: "cpu_pct = 100.0 * (1.0 - delta_idle / delta_total)" },
        analysis_usage: { weight: 0.10, pre_detection: "SLAM 연산 폭주로 통신 에이전트 스케줄링 지연이 임박했음을 감지", post_mortem: "무선 장애가 아닌 AGV 내부 CPU 고갈 장애(SCN-04) 판별" }
      },
      {
        id: "M18", key: "pose_xy", name_ko: "AGV 주행 좌표(X, Y) 및 속도", name_en: "AGV Spatial Pose (X, Y) & Velocity",
        layer: "L7 응용·시스템", layer_code: "L7_SYS", unit: "m, m/s",
        description: "네트워크 지표 수집 시점의 공장 도면 내 AGV 절대 좌표 (X, Y) 및 주행 속도(m/s).",
        thresholds: { normal: "정상 경로 내", warning: "음영 경계 진입", critical: "상습 단절 구역 진입" },
        collection_location: "AGV/AMR", interval_local: "1s", interval_report: "30s 요약 피기백",
        recommended_interval: "로컬 1s (링버퍼) / 보고 30s (피기백)",
        system_load: { level: "매우 낮음", cpu_overhead: "0.0% (공유 메모리)", network_overhead: "0 B/s (기존 보고에 포함)", detail: "주행 제어기(ROS/Navigation) 로컬 공유 메모리 참조" },
        collection_method: { interface: "ROS /amcl_pose or Shared Memory", command: "shm_read('/agv_nav_pose')", code_snippet: "pose_x, pose_y, vel = nav_shm.get_current_pose()" },
        analysis_usage: { weight: 0.10, pre_detection: "과거 단절 다발 좌표 반경 5m 접근 시 선제적 위험 가중치 부여", post_mortem: "모든 무선 지표를 공장 2D 맵 좌표에 매핑하여 상습 음영 히트맵 자동 구축" }
      }
    ];
  }

  // ==========================================================================
  // 16. Utilities & Application Initialization
  // ==========================================================================
  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function initApp() {
    bindEvents();
    // Initial immediate render with built-in fallback data so UI is never blank
    state.scenariosMap = Object.assign({}, FALLBACK_SCENARIOS);
    state.metricsCatalog = getFallbackMetricsCatalog();
    renderRcaScenarioView();
    renderMetricsCatalog();
    renderPacketInspector();
    updateBandwidthCalculator();
    drawFactoryFloorMap();
    drawLiveMiniChart();

    // Load live backend data & start 1s polling loop
    await loadInitialReferenceData();
    await pollLiveTelemetry();
    setInterval(pollLiveTelemetry, 1000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initApp);
  } else {
    initApp();
  }
})();
