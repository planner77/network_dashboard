/**
 * AGV/AMR–ACS 무선 네트워크 상태 관제 및 사전 감지·사후 분석 센터 (app.js v1.1)
 * 핵심 구현 사항:
 *  1. Light Enterprise 기본 테마 (data-theme="light") 및 다크 테마 즉시 전환
 *  2. 겹침 없는 2단 글로벌 내비게이션 헤더 및 5대 핵심 탭 전환
 *  3. 고시인성 8단계 인터랙티브 투어 가이드 (즉시 스크롤 동기화 + 대상 요소 직접 강조 + 실시간 좌표 추적)
 *  4. AGV/AMR 및 ACS 양단 전용 18종 수집 항목 백과사전 (상단 고정 헤더 Sticky Table)
 *  5. 평이한 한국어 표현 적용 (1초 상시 기록장, 30초 정기 보고 시 요약 동봉 전송, 장애 상황 가상 체험, 시계열 DB 필요성)
 *  6. Tab 5: AGV/AMR 담당자 및 ACS 담당자별 해야 할 일 명확화
 */

(function () {
  "use strict";

  // ==========================================================================
  // 1. Global Application State (Default Theme: Light Enterprise)
  // ==========================================================================
  const state = {
    theme: "light",
    userToggledTheme: false,
    activeTab: "tab-live",
    config: {
      port: 9921,
      default_theme: "light",
      agv_count: 6,
      acs_report_interval_sec: 30,
      local_record_interval_sec: 1,
      local_buffer_retention_sec: 300
    },

    // Tab 1: Live Fleet & 2D Map State
    selectedAgvId: "AGV-02",
    showHeatmap: true,
    showDangerZones: true,
    overview: null,
    agvTimeseries: {
      agv_id: "AGV-02",
      series: [],
      reports_30s: []
    },
    _renderedAgvHitboxes: [],

    // Tab 2: Pre-Detection & RCA Lab State
    scenariosMap: {},
    selectedScenarioCode: "SCN-01",
    rcaCursorOffset: -18,
    rcaPlaying: false,
    rcaPlayTimer: null,

    // Tab 3: Metrics Catalog State (AGV/AMR & ACS Only)
    metricsCatalog: [],
    selectedMetricId: "M01",
    catalogLayerFilter: "ALL",
    catalogLocFilter: "ALL",
    catalogSearchQuery: "",

    // Tab 4 & Tab 5: Architecture & Role Action Plans State
    hybridArchSpec: null,
    roleActionPlans: null,
    activePacketType: "piggyback",

    // High-Visibility Spotlight Guided Tour State (8 Steps)
    tourActive: false,
    tourStepIndex: 0
  };

  // ==========================================================================
  // 2. Built-in Fallback Data (1s Resolution Timelines & Plain Korean)
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
      let note = "정상 주행 및 AGV 내부 1초 상시 기록장 기록 중";

      if (code === "SCN-01") {
        // 기지국(AP) 변경 지연 및 실패
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
            note = "사전 감지 알림 발령! 신호 세기 급락(-76dBm) 및 기지국(AP) 변경 지연 감지";
          }
        } else if (t >= 0 && t < 16) {
          rssi = -84; snr = 11; phy = 6; l2Retry = 48; beaconLoss = 9; roamMs = 380;
          gwRtt = 280; jitter = 85; tcpRetrans = 11; sendQ = 14800; risk = 98;
          conn = "DISCONNECTED";
          note = "30초 정기 보고 끊김 발생! (기지국 변경 지연 340ms 초과로 소켓 연결 단절)";
        } else if (t >= 16) {
          rssi = -58; snr = 33; phy = 144; l2Retry = 2.8; roamMs = 18;
          gwRtt = 3.8; tcpRetrans = 0; sendQ = 0; risk = 14;
          conn = "CONNECTED";
          note = "새 기지국(ZONE-B) 연결 완료 및 끊김 전후 120초 상세 기록 ACS 전송 완료";
        }
      } else if (code === "SCN-02") {
        // 철제 랙 음영 구역 & 용접 설비 간섭
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
            note = "사전 감지 알림 발령! 철제 랙 음영 및 용접 잡음 유입으로 SNR 12dB 이하 급락";
          }
        } else if (t >= 0 && t < 15) {
          rssi = -85; noise = -75; snr = 10; l2Retry = 54; gwRtt = 310;
          tcpRetrans = 12; sendQ = 16200; risk = 99; conn = "DISCONNECTED";
          note = "물리적 전파 음영 + 설비 전파 간섭으로 무선 재시도 폭증 및 연결 끊김";
        }
      } else if (code === "SCN-03") {
        // 무선 채널 혼잡 (동시 접속 과부하)
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
            note = "사전 감지 알림 발령! 신호 세기(-60dBm)는 좋으나 무선 채널 혼잡도(82%) 포화 감지";
          }
        } else if (t >= 0 && t < 15) {
          rssi = -60; snr = 28; chanUtil = 94; l2Retry = 38; gwRtt = 340;
          tcpRetrans = 10; sendQ = 13500; risk = 96; conn = "DISCONNECTED";
          note = "동일 주파수 채널 혼잡 포화로 인한 응답 시간 초과 및 연결 끊김";
        }
      } else if (code === "SCN-04") {
        // 통신 프로그램 일시 멈춤 (CPU 과부하)
        if (t >= -25 && t < 0) {
          const p = (t + 25) / 25;
          rssi = -58; snr = 32; chanUtil = 25; gwRtt = 4.1; l2Retry = 2.5;
          cpu = Math.min(99, Math.round(42 + p * 57));
          recvQ = t >= -16 ? Math.round((t + 17) * 640) : 0;
          sendQ = t >= -14 ? Math.round((t + 15) * 490) : 0;
          risk = Math.min(90, Math.round((14 + Math.pow(p, 1.4) * 78) * 10) / 10);
          if (t >= -14) {
            conn = "PRE_WARNING";
            note = "사전 감지 알림 발령! 와이파이(신호/응답)는 정상이나 AGV CPU(95%) 및 수신 대기열 적체 감지";
          }
        } else if (t >= 0 && t < 14) {
          rssi = -58; snr = 32; gwRtt = 4.3; cpu = 99.2; recvQ = 18400; sendQ = 12400;
          risk = 97; conn = "DISCONNECTED";
          note = "AGV 자율주행 연산 CPU 독점으로 통신 프로그램이 일시 멈춰 30초 보고 누락";
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
      title: "기지국(AP) 변경 지연 및 실패 (로밍 실패)",
      subtitle: "구역 이동 중 멀어진 기존 AP(-81dBm)를 놓지 못해 새 AP 연결이 340ms 지연된 사례",
      target_agv: "AGV-02",
      zone: "ZONE-A → ZONE-B 이동 구간",
      lead_time_sec: 18,
      pre_detect_offset_sec: -18,
      disconnect_offset_sec: 0,
      recovery_offset_sec: 16,
      legacy_30s_view: "끊어지기 30초 전(-30초) 정기 보고에서는 신호 세기가 -66dBm으로 정상 보고되었습니다. 그 후 30초 사이에 AGV가 이동하며 신호가 급격히 약해지고 기지국 변경에 실패했으나 30초 주기 방식은 이를 전혀 알 수 없었고, 0초에 갑자기 연결 끊김이 발생했습니다.",
      hybrid_1s_view: "AGV 내부 1초 상시 기록장이 신호 세기 하락 속도(초당 -2.6dBm)와 무선 재시도 증가를 포착하여 소켓이 끊어지기 18초 전(-18초)에 위험 점수 70점을 돌파, ACS로 즉시 [사전 경고 알림]을 보내 AGV 감속을 유도합니다.",
      root_cause: "AGV 무선 랜카드의 기지국 변경 기준값이 너무 낮게(-80dBm) 설정되어 있어, 가까운 새 기지국(ZONE-B)으로 제때 갈아타지 못하고 기존 기지국을 붙잡고 있다가 뒤늦게 변경을 시도하며 340ms 동안 통신이 끊어진 현상입니다.",
      signature_metrics: [
        "신호 세기(RSSI): -61dBm → -84dBm 급락",
        "기지국 변경 시간: 340ms 소요 (정상 50ms 미만)",
        "기지국 신호 놓침: 초당 8회 발생",
        "무선 재시도 비율: 48.0% 치솟음"
      ],
      decision_tree: [
        { step: 1, question: "무선 수신 신호 세기(RSSI)가 정상(-67dBm 이상)인가?", observation: "신호 세기가 -84dBm까지 지속적으로 떨어짐", result: "FAIL", implication: "무선 전파 신호 약화 확인" },
        { step: 2, question: "주변 무선 잡음(Noise Floor) 상승에 의한 설비 간섭인가?", observation: "주변 잡음은 -91dBm으로 조용하고 일정하게 유지됨", result: "PASS", implication: "용접기 등 외부 설비 전파 간섭이 아님을 확인" },
        { step: 3, question: "이동 중 기지국(AP) 변경 지연이 발생했는가?", observation: "구역 경계 통과 후에도 기존 AP를 유지하다 뒤늦게 변경하며 340ms 지연 발생", result: "FAIL", implication: "AGV 무선 랜카드 기지국 변경(로밍) 기준값 미흡 확정" },
        { step: 4, question: "최종 원인 판정 결과", observation: "사례 1 (SCN-01): 기지국(AP) 변경 지연 및 실패 (정확도 98%)", result: "FAIL", implication: "AGV 로밍 탐색 기준을 -70dBm으로 상향 및 고속 로밍 설정 권고" }
      ],
      recommended_actions: [
        "AGV 담당자: 무선 랜카드 설정(wpa_supplicant)의 기지국 변경 탐색 기준을 -80dBm에서 -70dBm으로 조정",
        "AGV 담당자: 고속 기지국 변경 옵션(802.11k/v/r)을 활성화하여 변경 소요 시간을 50ms 이내로 단축",
        "ACS 담당자: 사전 감지 알림 수신 시 해당 AGV 이동 속도를 서행(0.5m/s)으로 제어하여 안전 확보"
      ],
      timeline: generateFallbackTimeline("SCN-01")
    },
    "SCN-02": {
      code: "SCN-02",
      title: "철제 랙 전파 음영 구역 & 용접 설비 간섭",
      subtitle: "철제 구조물 통로 진입 및 용접기 가동 잡음(-75dBm) 유입으로 신호 품질이 무너진 사례",
      target_agv: "AGV-03",
      zone: "ZONE-C 철제 랙 / 용접 구역",
      lead_time_sec: 16,
      pre_detect_offset_sec: -16,
      disconnect_offset_sec: 0,
      recovery_offset_sec: 15,
      legacy_30s_view: "30초 전 정기 보고는 정상이었으나, AGV가 철제 랙 통로와 용접 설비 근처를 지나는 15초 동안 통신이 끊겨 정기 보고가 누락되었습니다. 다시 연결된 뒤에는 이미 해당 구역을 벗어나 왜 끊겼는지 알 수 없습니다.",
      hybrid_1s_view: "AGV 내부 1초 기록장이 주변 잡음 급증(-91 → -75dBm)과 신호대잡음비 급락(10dB), 연결 속도 저하(144 → 6Mbps)를 포착해 끊김 16초 전에 사전 알림을 보내고, 주행 좌표(X,Y)와 결합해 2D 지도에 음영 구역을 자동 표시합니다.",
      root_cause: "철제 선반 구조물에 의해 전파가 가로막힌 상태에서 로봇 용접기가 가동되며 강한 전자기파 잡음(-75dBm)이 유입되어 신호대잡음비(SNR)가 10dB로 붕괴, 무선 데이터가 깨지며 연결이 끊어진 현상입니다.",
      signature_metrics: [
        "주변 잡음(Noise): -91dBm → -75dBm 급증",
        "신호대잡음비(SNR): 31dB → 10dB 붕괴",
        "무선 연결 속도: 144Mbps → 6Mbps 급락",
        "무선 재시도 비율: 54.0% 폭증"
      ],
      decision_tree: [
        { step: 1, question: "무선 신호 세기(RSSI)와 신호대잡음비(SNR)가 정상인가?", observation: "신호 세기 -85dBm, SNR 10dB로 전파 품질 심각하게 저하", result: "FAIL", implication: "물리적 무선 전파 환경 문제 확인" },
        { step: 2, question: "주변 무선 잡음 수치(Noise Floor)가 함께 치솟았는가?", observation: "주변 잡음이 -91dBm에서 -75dBm으로 16dB 급상승", result: "FAIL", implication: "용접기/모터 등 고주파 설비의 전파 방해 유입 확인" },
        { step: 3, question: "공장 지도상 특정 위치 좌표(X,Y)에서 반복 발생하는가?", observation: "철제 랙(50m, 15m) 및 용접 구역(80m, 40m) 통과 시 집중 발생", result: "FAIL", implication: "공장 내 물리적 전파 음영 및 간섭 구역 확정" },
        { step: 4, question: "최종 원인 판정 결과", observation: "사례 2 (SCN-02): 철제 랙 음영 구역 및 설비 전파 간섭 (정확도 97%)", result: "FAIL", implication: "AGV 안테나 상단 이설 및 ACS 음영 구역 우회 경로 지정 권고" }
      ],
      recommended_actions: [
        "AGV 담당자: AGV 무선 안테나를 차체 하단에서 상단(높이 1.8m 이상)으로 올려 철제 장애물 가림 최소화",
        "AGV 담당자: 전파 간섭에 취약한 2.4GHz 대역 대신 5GHz 전용 채널을 사용하도록 무선 카드 설정 고정",
        "ACS 담당자: 2D 지도에 표시된 상습 음영 구역 통과 전 AGV 사전 감속 또는 우회 주행 경로 부여"
      ],
      timeline: generateFallbackTimeline("SCN-02")
    },
    "SCN-03": {
      code: "SCN-03",
      title: "무선 채널 혼잡 (동시 접속 과부하)",
      subtitle: "신호 세기(-60dBm)는 매우 강하지만 같은 주파수 채널에 기기가 몰려 통로가 막힌 사례",
      target_agv: "AGV-04",
      zone: "ZONE-B 물류 집중 구역",
      lead_time_sec: 15,
      pre_detect_offset_sec: -15,
      disconnect_offset_sec: 0,
      recovery_offset_sec: 15,
      legacy_30s_view: "현장 점검 시 와이파이 안테나 눈금(신호 세기 -60dBm)이 꽉 차 있기 때문에, 기존 30초 보고만으로는 왜 자꾸 통신이 끊기는지 원인을 전혀 찾지 못하는 대표적인 미스터리 장애입니다.",
      hybrid_1s_view: "1초 기록 데이터에서 신호 세기(-60dBm)와 잡음(-90dBm)은 정상인데 유독 '무선 채널 혼잡도(94%)'와 '게이트웨이 응답 시간(340ms)'만 치솟는 것을 확인하여 끊김 15초 전에 채널 과부하임을 정확히 진단합니다.",
      root_cause: "특정 구역에 여러 대의 AGV와 작업자 단말기가 동시에 몰리면서 같은 무선 주파수 통로를 쓰기 위해 순서를 기다리는 현상(채널 혼잡도 94%)이 발생해 제시간에 보고 패킷이 전달되지 못한 사례입니다.",
      signature_metrics: [
        "신호 세기 / SNR: -60dBm / 28dB (신호는 매우 좋음!)",
        "무선 채널 혼잡도: 94% (위험 기준 65% 초과)",
        "게이트웨이 응답 시간: 4.2ms → 340ms 폭증",
        "응답 시간 흔들림: 56ms 발생"
      ],
      decision_tree: [
        { step: 1, question: "무선 수신 신호 세기(RSSI) 및 SNR이 정상인가?", observation: "신호 세기 -60dBm, SNR 28dB로 전파 세기는 매우 우수함", result: "PASS", implication: "음영 구역이나 거리 문제가 아님을 즉시 증명" },
        { step: 2, question: "AGV가 측정한 무선 채널 혼잡도(Channel Busy Ratio)가 정상인가?", observation: "채널 혼잡도가 94%에 달해 무선 통로가 완전히 꽉 막힘", result: "FAIL", implication: "동일 주파수 채널에 너무 많은 통신량이 몰린 과부하 확인" },
        { step: 3, question: "게이트웨이 응답 시간(RTT) 및 흔들림(Jitter)이 급증했는가?", observation: "게이트웨이 응답 시간이 340ms로 치솟고 소켓 재전송 초당 10회 발생", result: "FAIL", implication: "무선 통로 순서 대기로 인한 전송 지연 확정" },
        { step: 4, question: "최종 원인 판정 결과", observation: "사례 3 (SCN-03): 무선 채널 혼잡 및 동시 접속 과부하 (정확도 96%)", result: "FAIL", implication: "AGV 제어용 무선망 분리 및 구역별 동시 진입 대수 조절 권고" }
      ],
      recommended_actions: [
        "ACS 담당자: 특정 작업 구역(ZONE-B)에 동시에 진입하는 AGV 대수를 분산하는 트래픽 제어 적용",
        "AGV 담당자: 불필요한 대용량 로그/영상 전송을 제한하고 제어·보고 패킷에 최우선 전송 순위(QoS) 부여",
        "현장 네트워크 협의: AGV 제어 전용 와이파이 이름(SSID)과 일반 사내 업무용 와이파이 채널을 분리"
      ],
      timeline: generateFallbackTimeline("SCN-03")
    },
    "SCN-04": {
      code: "SCN-04",
      title: "통신 프로그램 일시 멈춤 (AGV/ACS CPU·버퍼 병목)",
      subtitle: "와이파이 신호와 네트워크 응답은 100% 정상이나 컴퓨터 과부하로 프로그램이 멈춘 사례",
      target_agv: "AGV-05",
      zone: "ZONE-D 정밀 작업 구역",
      lead_time_sec: 14,
      pre_detect_offset_sec: -14,
      disconnect_offset_sec: 0,
      recovery_offset_sec: 14,
      legacy_30s_view: "ACS 관제 화면에는 똑같이 '30초 보고 미수신(연결 끊김)'으로만 나타나기 때문에, 실제로는 프로그램이 멈춘 것인데도 '공장 와이파이가 나쁘다'고 오해하여 불필요한 무선 공사를 하게 됩니다.",
      hybrid_1s_view: "1초 기록에서 신호 세기(-58dBm), 채널 혼잡도(25%), 게이트웨이 응답 시간(4.1ms)이 모두 완벽히 정상인데도 AGV 컴퓨터 CPU(99.2%)와 소켓 수신 대기열(18.4KB)만 급증한 것을 포착해 '와이파이 문제가 아닌 프로그램 멈춤'임을 끊김 14초 전에 가려냅니다.",
      root_cause: "정밀 도킹 구간에서 AGV 자율주행(라이다 센서 계산) 프로그램이 컴퓨터 CPU를 99% 독점하면서 통신 프로그램이 실행 순서를 얻지 못해 멈췄고, 소켓 대기열에 데이터가 쌓여 30초 보고가 멈춘 소프트웨어 문제입니다.",
      signature_metrics: [
        "신호 세기 / 관문 응답: -58dBm / 4.1ms (무선 완벽 정상!)",
        "AGV 컴퓨터 CPU 사용률: 99.2% 치솟음",
        "소켓 수신 대기열(Recv-Q): 18,400 Bytes 쌓임",
        "소켓 송신 대기열(Send-Q): 12,400 Bytes 쌓임"
      ],
      decision_tree: [
        { step: 1, question: "무선 신호 세기(RSSI) 및 채널 혼잡도가 정상인가?", observation: "신호 세기 -58dBm, SNR 32dB, 혼잡도 25%로 완벽히 정상", result: "PASS", implication: "와이파이 전파 환경에는 아무런 문제가 없음" },
        { step: 2, question: "게이트웨이 왕복 응답 시간(Gateway Ping RTT)이 정상인가?", observation: "게이트웨이 응답 시간 4.1ms로 무선~유선 네트워크 구간 정상", result: "PASS", implication: "네트워크 통신망 자체는 100% 정상임을 증명!" },
        { step: 3, question: "소켓 대기열(Send-Q/Recv-Q) 및 컴퓨터 CPU 사용률이 정상인가?", observation: "AGV CPU 99.2% 과부하 및 수신 대기열 18.4KB 미처리 누적", result: "FAIL", implication: "컴퓨터 과부하로 통신 프로그램이 데이터를 읽지 못함 확인" },
        { step: 4, question: "최종 원인 판정 결과", observation: "사례 4 (SCN-04): 통신 프로그램 일시 멈춤 및 CPU 과부하 (정확도 99%)", result: "FAIL", implication: "무선 공사 불필요! 자율주행 연산과 통신 프로그램 CPU 코어 분리 권고" }
      ],
      recommended_actions: [
        "AGV 담당자: 자율주행(SLAM) 계산 프로세스와 ACS 통신 프로그램이 서로 다른 CPU 코어를 쓰도록 분리(CPU Affinity)",
        "AGV 및 ACS 담당자: 소켓 통신 처리 방식을 대기 없는 비동기 방식(Non-blocking)으로 개선하고 수신 대기열 감시 추가",
        "공통 사항: 와이파이 문제가 아니므로 불필요한 무선 기지국(AP) 공사나 안테나 교체 비용 지출 방지"
      ],
      timeline: generateFallbackTimeline("SCN-04")
    }
  };

  // ==========================================================================
  // 3. Protocol JSON Payload Templates for Tab 4
  // ==========================================================================
  const PACKET_EXAMPLES = {
    piggyback: {
      desc: "① 평시 30초 정기 보고 동봉 메시지: 기존에 30초마다 보내던 AGV 상태 보고 데이터 끝에 '지난 30초간의 통신 품질 요약표(net_summary_30s, 약 96 Bytes)'를 함께 담아 보냅니다.",
      payload: {
        message_type: "ACS_30S_STATUS_REPORT_WITH_SUMMARY",
        agv_id: "AGV-02",
        report_time: "2026-11-15T18:00:30Z",
        report_interval_sec: 30.0,
        agv_basic_status: {
          pos_x_m: 46.2,
          pos_y_m: 15.0,
          speed_mps: 1.4,
          battery_pct: 84,
          job_status: "MOVING_WITH_LOAD"
        },
        net_summary_30s_attached: {
          recorded_samples_1s: 30,
          connected_ap_zone: "ZONE-A",
          connected_ap_bssid: "00:1A:2B:3C:4D:01",
          rssi_dbm: { min: -68.0, avg: -61.4, drop_slope_per_sec: -0.4 },
          snr_db: { min: 24.0, avg: 29.5 },
          wifi_retry_rate_pct: { avg: 3.4, max: 7.8 },
          channel_busy_pct: { avg: 26.0, max: 34.0 },
          ap_roaming_count_30s: 0,
          gateway_rtt_ms: { avg: 4.3, max: 9.2, jitter_ms: 1.4 },
          tcp_retransmits_sum: 0,
          socket_queue_max_bytes: { send_q: 0, recv_q: 0 },
          agv_cpu_max_pct: 41.2,
          max_risk_score: 16.5,
          health_state: "CONNECTED"
        }
      }
    },
    early_warning: {
      desc: "② 사전 감지 긴급 경고 알림: AGV 내부 1초 기록 중 위험 점수가 70점을 넘으면(끊김 약 14~18초 전), 30초 정기 보고 시각을 기다리지 않고 즉시 ACS로 짧은 경고 메시지를 보냅니다.",
      payload: {
        message_type: "ACS_EARLY_WARNING_ALERT",
        alert_level: "PRE_DISCONNECT_WARNING",
        agv_id: "AGV-02",
        alert_time: "2026-11-15T18:00:42Z",
        estimated_seconds_before_drop: 18.0,
        current_pose: { pos_x_m: 48.5, pos_y_m: 15.0, speed_mps: 1.5 },
        risk_diagnosis: {
          risk_score: 74.8,
          alert_threshold: 70.0,
          predicted_cause_code: "SCN-01 (기지국 변경 지연 위험)",
          warning_evidences: [
            "수신 신호 세기(RSSI)가 -76.5 dBm으로 급락 (초당 -2.7 dBm 하락)",
            "무선 구간 재시도 비율이 26.4%로 급증",
            "소켓 송신 대기열(Send-Q)에 4,620 Bytes 미전송 데이터 누적"
          ]
        },
        requested_acs_action: {
          recommended_command: "SLOW_DOWN_AND_PREPARE_ROAMING",
          target_safe_speed_mps: 0.4
        }
      }
    },
    blackbox_dump: {
      desc: "③ 재연결 후 상세 기록 일괄 전송: 만약 통신이 끊어졌다가 다시 연결되면, AGV 내부 5분 기록장에 보관되어 있던 '끊김 전후 120초간의 1초 단위 상세 기록'을 보내 원인을 100% 밝혀냅니다.",
      payload: {
        message_type: "ACS_POST_DISCONNECT_DETAIL_DUMP",
        incident_id: "INC-2026-01",
        agv_id: "AGV-02",
        pre_warning_time: "2026-11-15T18:00:42Z",
        disconnected_time: "2026-11-15T18:01:00Z",
        reconnected_time: "2026-11-15T18:01:16Z",
        lead_time_sec: 18.0,
        auto_classified_cause: {
          scenario_code: "SCN-01",
          cause_title: "기지국(AP) 변경 지연 및 실패 (로밍 시간 340ms 소요)",
          confidence_pct: 98.0
        },
        recorded_1s_history_120s: {
          interval_sec: 1,
          range_description: "끊김 60초 전 ~ 끊김 60초 후 (총 120초 상세 기록)",
          columns: ["초(offset)", "X좌표", "Y좌표", "신호세기(dBm)", "SNR(dB)", "무선재시도(%)", "AP변경(ms)", "관문응답(ms)", "소켓재전송", "송신대기열", "수신대기열", "CPU(%)", "위험점수"],
          sample_rows: [
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
  // 4. 고시인성 8단계 인터랙티브 투어 가이드 (High-Visibility Spotlight Tour)
  // ==========================================================================
  const TOUR_STEPS = [
    {
      tab: "tab-live",
      targetSelector: "#welcome-tour-banner",
      title: "1단계: 왜 기존 '30초 주기 상태 보고'만으로는 부족할까요?",
      body: "AGV가 이동 중 기지국(AP)을 갈아타거나 철제 구조물 뒤쪽(음영 구역)에 들어갈 때 신호가 나빠지고 통신이 끊기는 현상은 불과 3~15초 사이에 일어납니다. 30초마다 한 번씩만 보고하면 끊어지기 직전의 위험 신호를 미리 알 수 없고, 다시 연결된 뒤에도 왜 끊겼는지 알 수 없습니다.",
      takeaway: "해결 방법: AGV 내부 1초 상시 기록장(최근 5분 블랙박스) + 30초 정기 보고 시 요약 데이터 동봉 전송 + 위험 시 조기 알림!"
    },
    {
      tab: "tab-live",
      targetSelector: "#live-kpi-row",
      title: "2단계: 전체 AGV 연결 상태 및 사전 감지 요약 현황판",
      body: "상단 4개 요약 카드는 현재 운행 중인 6대 AGV의 실시간 연결 상태, 30초 정기 보고 성공률 및 도착 간격, 끊김 전 평균 16.5초 앞서 알려주는 사전 감지 시간, 그리고 시계열 데이터 저장소(TSDB)에 쌓인 기록 현황을 한눈에 보여줍니다.",
      takeaway: "모든 숫자는 1초마다 실시간으로 갱신되더라도 글자가 흔들리지 않도록 고정폭 숫자로 설계되었습니다."
    },
    {
      tab: "tab-live",
      targetSelector: "#panel-floor-map",
      title: "3단계: 2D 스마트 팩토리 지도 & 전파 음영/간섭 구역 표시",
      body: "100m × 60m 공장 지도 위에 4개 구역(ZONE-A~D)의 무선 신호 범위와 철제 랙 전파 음영 구역, 용접 설비 간섭 구역을 표시합니다. AGV가 주행하면서 측정한 통신 품질을 위치 좌표(X,Y)와 합쳐 공장 내 어느 지점이 취약한지 바로 알 수 있습니다.",
      takeaway: "지도 위의 AGV 아이콘이나 우측 표의 AGV 행을 클릭하면 해당 AGV의 상세 차트로 즉시 바뀝니다."
    },
    {
      tab: "tab-live",
      targetSelector: "#panel-scenario-injector",
      title: "4단계: 4대 장애 상황 가상 체험 (시뮬레이션 실행)",
      body: "현장에서 가장 자주 겪는 4가지 끊김 상황(① 기지국 변경 지연, ② 음영 구역/설비 간섭, ③ 무선 채널 혼잡, ④ 통신 프로그램 일시 멈춤)을 원하는 AGV에 직접 실행해 볼 수 있습니다. 버튼을 누르면 끊어지기 14~18초 전에 [사전 감지 주의]가 먼저 켜지는 모습을 볼 수 있습니다.",
      takeaway: "투어가 끝난 뒤 가상 체험 버튼을 눌러 사전 감지와 자동 복구 과정을 직접 체험해 보세요."
    },
    {
      tab: "tab-rca",
      targetSelector: "#panel-rca-playback",
      title: "5단계: 기존 30초 단순 보고 vs 제안 1초 기록 방식 타임라인 비교",
      body: "2번 탭에서는 끊김 발생 전후 120초(-89초 ~ +30초) 동안의 1초 단위 기록을 시간 순서대로 재생하며 비교합니다. 기존 30초 방식이 놓쳤던 급격한 위험 징후를 AGV 내부 1초 기록장이 어떻게 끊김 18초 전에 미리 잡아내는지 직관적으로 비교할 수 있습니다.",
      takeaway: "아래 3단 차트에서 노란색 점선(사전 감지 시점)과 빨간색 실선(30초 보고 끊김 시점)의 시간 차이를 확인하세요."
    },
    {
      tab: "tab-rca",
      targetSelector: "#panel-rca-decision",
      title: "6단계: 왜 끊겼는지 자동으로 가려내는 4단계 원인 판별표",
      body: "단순히 '연결이 끊어졌다'만 보여주는 것이 아니라, ① 신호 세기 → ② 주변 잡음 → ③ 채널 혼잡도 및 관문 응답 시간 → ④ 컴퓨터 CPU 및 소켓 대기열 순서로 자동 점검하여 와이파이 문제인지 프로그램 멈춤(CPU 과부하) 문제인지 정확히 구분합니다.",
      takeaway: "특히 사례 4(SCN-04)는 와이파이가 정상인데 프로그램이 멈춘 경우로, 불필요한 무선 공사를 막아줍니다."
    },
    {
      tab: "tab-catalog",
      targetSelector: "#panel-catalog-table",
      title: "7단계: AGV/AMR과 ACS에서 수집하는 18종 상태 항목 백과사전",
      body: "3번 탭에는 별도의 무선 공유기(AP) 장비 접근 권한 없이도 오직 AGV/AMR과 ACS 서버 양단에서만 직접 수집할 수 있는 18가지 항목의 상세 설명, 정상/위험 기준값, 권장 주기, 시스템 부담, 실제 수집 명령어가 정리되어 있습니다.",
      takeaway: "일람표를 아래로 스크롤해도 상단 컬럼 제목 줄이 고정(Sticky Header)되어 편리하게 비교할 수 있습니다."
    },
    {
      tab: "tab-roles",
      targetSelector: "#panel-roles-split",
      title: "8단계: AGV/AMR 담당자와 ACS 담당자가 각각 해야 할 일",
      body: "마지막 5번 탭에는 현장에 이 체계를 적용하기 위해 AGV/AMR 담당자(1초 내부 기록장 구현, 30초 보고 시 요약 동봉, 사전 경고 발송, 로밍 기준 조정)와 ACS 담당자(시계열 DB 구축, 자체 지표 수집, 사전 감속 제어 연동)가 해야 할 일이 명확히 정리되어 있습니다.",
      takeaway: "이상으로 8단계 가이드 투어를 마칩니다. 상단 메뉴 탭을 클릭해 모든 기능을 자유롭게 살펴보세요!"
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
    // 0. Load .env runtime config (/api/config)
    const cfgData = await fetchJson("/api/config");
    if (cfgData && typeof cfgData === "object") {
      state.config = Object.assign({}, state.config, cfgData);
      if (!state.userToggledTheme && cfgData.default_theme) {
        applyTheme(cfgData.default_theme === "dark" ? "dark" : "light");
      }
    }

    // 1. Scenarios (/api/scenarios)
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
    ["SCN-01", "SCN-02", "SCN-03", "SCN-04"].forEach((code) => {
      if (!state.scenariosMap[code] || !Array.isArray(state.scenariosMap[code].timeline)) {
        state.scenariosMap[code] = FALLBACK_SCENARIOS[code];
      }
    });

    // 2. Metrics Catalog (18 metrics, strictly AGV/AMR & ACS)
    const catData = await fetchJson("/api/metrics-catalog");
    if (catData && Array.isArray(catData.metrics) && catData.metrics.length > 0) {
      state.metricsCatalog = catData.metrics;
    } else if (Array.isArray(catData) && catData.length > 0) {
      state.metricsCatalog = catData;
    } else {
      state.metricsCatalog = getFallbackMetricsCatalog();
    }

    // 3. Hybrid Architecture & Role Action Plans
    const [archData, roleData] = await Promise.all([
      fetchJson("/api/hybrid-architecture"),
      fetchJson("/api/action-plan")
    ]);
    if (archData && Object.keys(archData).length > 0) {
      state.hybridArchSpec = archData;
    }
    if (roleData && Object.keys(roleData).length > 0) {
      state.roleActionPlans = roleData;
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
  function formatConnStateKo(connState) {
    if (connState === "DISCONNECTED") return "연결 끊김";
    if (connState === "PRE_WARNING") return "사전 감지 주의";
    return "정상 연결";
  }

  function updateLiveKpisAndTables(ov) {
    const kpis = ov.kpis || {};
    const tsdb = ov.tsdb_stats || {};
    const fleet = ov.fleet || [];

    const totalRows = tsdb.total_rows || kpis.tsdb_total_rows || 3600;
    setText("nav-tsdb-count", `(${Number(totalRows).toLocaleString()} 건)`);

    // KPI 1: 운행 AGV 연결 상태
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
        fleetBadge.textContent = `연결 끊김 ${critCnt}대 발생`;
      } else if (warnCnt > 0) {
        fleetBadge.className = "badge badge-warn";
        fleetBadge.textContent = `사전 감지 주의 ${warnCnt}대`;
      } else {
        fleetBadge.className = "badge badge-ok";
        fleetBadge.textContent = `전수 정상 (${totalAgv}대)`;
      }
    }
    setText("kpi-avg-rssi", `평균 ${(kpis.avg_rssi_dbm || -60.5).toFixed(1)} dBm`);
    setText("kpi-cnt-normal", `${connCnt}대`);
    setText("kpi-cnt-warn", `${warnCnt}대`);
    setText("kpi-cnt-crit", `${critCnt}대`);

    // KPI 2: 30초 정기 보고 성공률
    const repRate = kpis.report_success_rate_pct !== undefined ? kpis.report_success_rate_pct : 99.2;
    setText("kpi-report-rate", `${Number(repRate).toFixed(1)}%`);
    const avgHb = kpis.avg_hb_interval_sec || 30.1;
    setText("kpi-hb-drift", `평균 ${Number(avgHb).toFixed(1)}s ± 0.4s`);

    // KPI 3: 사전 감지 조기 알림 시간
    const leadSec = kpis.avg_lead_time_sec || 16.5;
    setText("kpi-lead-time", `${Number(leadSec).toFixed(1)}초 전`);
    const activeScnCnt = kpis.active_scenario_count || warnCnt + critCnt || 0;
    setText("kpi-active-alerts", `진행 중 가상 체험 ${activeScnCnt}건`);
    setText("kpi-incident-total", `${kpis.incident_count || 4}건 기록됨`);

    // KPI 4: 시계열 데이터 저장소(TSDB) 현황
    const t1sRows = tsdb.telemetry_1s_rows || totalRows;
    setText("kpi-tsdb-rows", Number(t1sRows).toLocaleString());
    setText("kpi-tsdb-size", `${tsdb.db_size_kb || 420} KB`);
    setText("kpi-tsdb-reports", `${tsdb.acs_reports_30s_rows || 120}건`);

    // 구역별 무선 상태 바
    if (Array.isArray(ov.aps) && ov.aps.length > 0) {
      const apStrip = document.getElementById("ap-status-strip");
      if (apStrip) {
        apStrip.innerHTML = ov.aps.map((ap) => {
          const util = Math.round(ap.channel_util || 24);
          const badgeCls = util > 65 ? "badge-crit" : (util > 45 ? "badge-warn" : "badge-ok");
          return `
            <div class="ap-mini-card">
              <div class="ap-mini-header">
                <span>${escapeHtml(ap.zone_id || ap.ap_id)}</span>
                <span class="badge ${badgeCls} mono">채널 ${ap.channel || 36}</span>
              </div>
              <div class="ap-mini-meta mono">
                <span>접속 AGV: ${ap.client_count || 0}대</span>
                <span>혼잡도: ${util}%</span>
              </div>
            </div>
          `;
        }).join("");
      }
    }

    // 선택된 AGV 하단 상태 바
    const selAgv = fleet.find((a) => a.agv_id === state.selectedAgvId) || fleet[0];
    if (selAgv) {
      setText("map-selected-agv-pill", `선택됨: ${selAgv.agv_id}`);
      const detailBar = document.getElementById("map-agv-detail-bar");
      if (detailBar) {
        const scnTag = selAgv.scenario_code && selAgv.scenario_code !== "NORMAL"
          ? `<span class="badge badge-crit mono">${escapeHtml(selAgv.scenario_code)} 가상 체험 진행 중</span>`
          : `<span class="badge badge-ok mono">정상 운행 중</span>`;
        detailBar.innerHTML = `
          <span><strong>[${escapeHtml(selAgv.agv_id)}]</strong> 위치: (${Number(selAgv.pos_x).toFixed(1)}m, ${Number(selAgv.pos_y).toFixed(1)}m) | 속도: ${Number(selAgv.velocity).toFixed(2)} m/s | 구역: ${escapeHtml(selAgv.zone_id || selAgv.ap_id)} (${escapeHtml(selAgv.bssid || "")})</span>
          <span>${scnTag}</span>
        `;
      }
    }

    // AGV 실시간 상태 표
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

        let stateBadge = `<span class="badge badge-ok">정상 연결</span>`;
        if (agv.conn_state === "DISCONNECTED") {
          stateBadge = `<span class="badge badge-crit">연결 끊김</span>`;
        } else if (agv.conn_state === "PRE_WARNING") {
          stateBadge = `<span class="badge badge-warn">사전 감지 주의</span>`;
        }

        return `
          <tr class="${isSel ? "selected-row" : ""}" data-agv-row="${escapeHtml(agv.agv_id)}">
            <td class="text-left mono"><strong>${escapeHtml(agv.agv_id)}</strong></td>
            <td class="text-center mono">${escapeHtml(agv.zone_id || agv.ap_id)}</td>
            <td class="text-right num ${rssiCls}">${rssi} dBm</td>
            <td class="text-right num">${snr} dB</td>
            <td class="text-right num">${rtt} ms</td>
            <td class="text-right num ${retrans > 0 ? "color-warn" : ""}">${retrans} 회/s</td>
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

    // 최근 30초 정기 보고 & 동봉 요약 이력 표
    const repTbody = document.getElementById("recent-reports-tbody");
    if (repTbody && Array.isArray(ov.recent_reports_30s)) {
      repTbody.innerHTML = ov.recent_reports_30s.slice(0, 7).map((r) => {
        const pb = r.piggyback_summary || {};
        const dt = new Date(r.ts || Date.now());
        const timeStr = dt.toTimeString().split(" ")[0];
        let stBadge = `<span class="badge badge-ok">정상 수신</span>`;
        if (r.report_status === "TIMEOUT_MISSED") {
          stBadge = `<span class="badge badge-crit">미수신 (끊김)</span>`;
        } else if (r.report_status === "DELAYED") {
          stBadge = `<span class="badge badge-warn">도착 지연</span>`;
        }
        const maxRisk = pb.max_risk_score !== undefined ? Number(pb.max_risk_score).toFixed(1) : "14.0";
        const riskCls = maxRisk >= 70 ? "color-crit" : (maxRisk >= 45 ? "color-warn" : "color-ok");
        return `
          <tr>
            <td class="text-left mono">${timeStr}</td>
            <td class="text-left mono"><strong>${escapeHtml(r.agv_id)}</strong></td>
            <td class="text-center">${stBadge}</td>
            <td class="text-right num">${Number(r.hb_interval_sec || 30.0).toFixed(1)}초</td>
            <td class="text-right num">${pb.rssi_min !== undefined ? Number(pb.rssi_min).toFixed(1) : "-63.0"} dBm</td>
            <td class="text-right num">${pb.tcp_retrans_sum !== undefined ? pb.tcp_retrans_sum : 0}회</td>
            <td class="text-right num ${riskCls}"><strong>${maxRisk}점</strong></td>
          </tr>
        `;
      }).join("");
    }

    // 최근 사전 감지 및 사후 원인 분석 이력 표
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
            <td class="text-right num color-warn"><strong>끊김 ${Number(inc.lead_time_sec || 16.5).toFixed(1)}초 전 감지</strong></td>
            <td class="text-center"><button class="btn btn-sm btn-primary" type="button">파형 분석 보기 →</button></td>
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
      titleEl.textContent = `${agvId} 실시간 1초 기록 추이 & 30초 정기 보고 시점 (최근 180초)`;
    }
    pollLiveTelemetry();
  }

  // ==========================================================================
  // 7. High-DPI Canvas & Theme Color Helper
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
      textSecondary: isLight ? "#334155" : "#94A3B8",
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

    ctx.fillStyle = colors.bgCanvas;
    ctx.fillRect(0, 0, w, h);

    // 10m Grid Lines
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

    ctx.strokeStyle = state.theme === "light" ? "#94A3B8" : "#334155";
    ctx.lineWidth = 1.5;
    ctx.strokeRect(padL, padT, mapW, mapH);

    const ov = state.overview || {};
    const aps = Array.isArray(ov.aps) && ov.aps.length > 0 ? ov.aps : [
      { ap_id: "AP-ZONE-A", zone_id: "ZONE-A", x: 20, y: 15, channel: 36, channel_util: 24 },
      { ap_id: "AP-ZONE-B", zone_id: "ZONE-B", x: 75, y: 15, channel: 44, channel_util: 28 },
      { ap_id: "AP-ZONE-C", zone_id: "ZONE-C", x: 75, y: 45, channel: 149, channel_util: 36 },
      { ap_id: "AP-ZONE-D", zone_id: "ZONE-D", x: 20, y: 45, channel: 157, channel_util: 22 }
    ];

    if (state.showHeatmap) {
      aps.forEach((ap) => {
        const cx = toX(ap.x);
        const cy = toY(ap.y);
        const radius = (34 / 100) * mapW;
        const grad = ctx.createRadialGradient(cx, cy, 4, cx, cy, radius);
        grad.addColorStop(0, "rgba(2, 132, 199, 0.20)");
        grad.addColorStop(0.55, "rgba(5, 150, 105, 0.08)");
        grad.addColorStop(1, "rgba(5, 150, 105, 0.0)");
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.fill();
      });
    }

    if (state.showDangerZones) {
      const sx = toX(43), sy = toY(8), sw = (14 / 100) * mapW, sh = (14 / 60) * mapH;
      ctx.fillStyle = "rgba(225, 29, 72, 0.13)";
      ctx.fillRect(sx, sy, sw, sh);
      ctx.save();
      ctx.setLineDash([4, 3]);
      ctx.strokeStyle = "rgba(225, 29, 72, 0.75)";
      ctx.lineWidth = 1.5;
      ctx.strokeRect(sx, sy, sw, sh);
      ctx.restore();
      ctx.fillStyle = colors.rose;
      ctx.font = "700 10px 'Pretendard', sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("철제 랙 전파 음영 구역", sx + sw / 2, sy + sh / 2 - 4);
      ctx.fillText("(신호 ≤ -82dBm 급락)", sx + sw / 2, sy + sh / 2 + 9);

      const ex = toX(80), ey = toY(40), er = (9 / 100) * mapW;
      const emiGrad = ctx.createRadialGradient(ex, ey, 2, ex, ey, er);
      emiGrad.addColorStop(0, "rgba(217, 119, 6, 0.28)");
      emiGrad.addColorStop(1, "rgba(225, 29, 72, 0.05)");
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
      ctx.fillText("⚡ 용접 설비 전파 간섭 구역", ex, ey - er - 5);
    }

    if (ov.agv_paths) {
      ctx.save();
      ctx.strokeStyle = state.theme === "light" ? "rgba(100,116,139,0.25)" : "rgba(148,163,184,0.15)";
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

    aps.forEach((ap) => {
      const ax = toX(ap.x), ay = toY(ap.y);
      ctx.fillStyle = "rgba(2, 132, 199, 0.16)";
      ctx.strokeStyle = colors.sky;
      ctx.lineWidth = 1.6;
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

      const linkedAp = aps.find((a) => a.ap_id === agv.ap_id || a.zone_id === agv.zone_id);
      if (linkedAp) {
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(gx, gy);
        ctx.lineTo(toX(linkedAp.x), toY(linkedAp.y));
        ctx.strokeStyle = stColor;
        ctx.globalAlpha = isSelected ? 0.65 : 0.30;
        ctx.lineWidth = isSelected ? 1.8 : 1.0;
        ctx.setLineDash(agv.conn_state === "DISCONNECTED" ? [3, 5] : [4, 3]);
        ctx.stroke();
        ctx.restore();
      }

      if (isSelected || agv.conn_state !== "CONNECTED") {
        ctx.save();
        ctx.beginPath();
        ctx.arc(gx, gy, isSelected ? 17 : 14, 0, Math.PI * 2);
        ctx.strokeStyle = isSelected ? colors.sky : stColor;
        ctx.lineWidth = 2.2;
        ctx.stroke();
        ctx.restore();
      }

      ctx.fillStyle = stColor;
      ctx.beginPath();
      ctx.roundRect ? ctx.roundRect(gx - 10, gy - 7, 20, 14, 4) : ctx.rect(gx - 10, gy - 7, 20, 14);
      ctx.fill();
      ctx.strokeStyle = "#FFFFFF";
      ctx.lineWidth = 1.2;
      ctx.stroke();

      const labelTxt = `${agv.agv_id} (${Math.round(agv.rssi)}dBm)`;
      ctx.font = "600 10px 'JetBrains Mono', monospace";
      const tw = ctx.measureText(labelTxt).width + 10;
      ctx.fillStyle = state.theme === "light" ? "rgba(255,255,255,0.95)" : "rgba(15,23,42,0.92)";
      ctx.strokeStyle = stColor;
      ctx.lineWidth = 1;
      ctx.fillRect(gx - tw / 2, gy - 25, tw, 15);
      ctx.strokeRect(gx - tw / 2, gy - 25, tw, 15);

      ctx.fillStyle = colors.textPrimary;
      ctx.textAlign = "center";
      ctx.fillText(labelTxt, gx, gy - 14);

      state._renderedAgvHitboxes.push({ agv_id: agv.agv_id, x: gx, y: gy, r: 22 });
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
    const padL = 42, padR = 42, padT = 16, padB = 22;
    const cw = w - padL - padR;
    const ch = h - padT - padB;

    ctx.strokeStyle = colors.gridLine;
    ctx.lineWidth = 1;
    for (let i = 0; i <= 3; i++) {
      const y = padT + (i / 3) * ch;
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(padL + cw, y);
      ctx.stroke();
    }

    const yRisk70 = padT + (1 - 70 / 100) * ch;
    ctx.save();
    ctx.setLineDash([4, 3]);
    ctx.strokeStyle = colors.amber;
    ctx.beginPath();
    ctx.moveTo(padL, yRisk70);
    ctx.lineTo(padL + cw, yRisk70);
    ctx.stroke();
    ctx.restore();

    ctx.font = "500 9.5px 'JetBrains Mono', monospace";
    ctx.fillStyle = colors.sky;
    ctx.textAlign = "right";
    ctx.fillText("-50dBm", padL - 4, padT + 6);
    ctx.fillText("-90dBm", padL - 4, padT + ch);

    ctx.fillStyle = colors.amber;
    ctx.textAlign = "left";
    ctx.fillText("100점", padL + cw + 4, padT + 6);
    ctx.fillText("70(주의)", padL + cw + 4, yRisk70 + 3);
    ctx.fillText("0점", padL + cw + 4, padT + ch);

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

    ctx.strokeStyle = colors.sky;
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    series.forEach((pt, idx) => {
      const x = toX(idx), y = rssiToY(pt.rssi);
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    ctx.strokeStyle = colors.amber;
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    series.forEach((pt, idx) => {
      const x = toX(idx), y = riskToY(pt.risk_score);
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    series.forEach((pt, idx) => {
      if (idx % 30 === 0 || idx === n - 1) {
        const x = toX(idx);
        const y = riskToY(pt.risk_score);
        ctx.fillStyle = pt.conn_state === "DISCONNECTED" ? colors.rose : colors.emerald;
        ctx.beginPath();
        ctx.arc(x, y, 3.4, 0, Math.PI * 2);
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

    setText("rca-lab-header-title", `[${scn.code}] ${scn.title} — 기존 30초 보고의 사각지대 vs 1초 상시 기록장 사전 감지 비교`);
    setText("rca-legacy-desc", scn.legacy_30s_view || "");
    setText("rca-hybrid-desc", scn.hybrid_1s_view || "");
    setText("rca-hybrid-lead-badge", `끊김 ${leadSec}초 전 조기 알림!`);

    const jumpBtn = document.getElementById("btn-jump-predetect");
    if (jumpBtn) {
      jumpBtn.setAttribute("data-jump", String(-leadSec));
      jumpBtn.textContent = `${leadSec}초 전 (사전 감지 알림!)`;
    }

    setText("rca-verdict-code", `${scn.code} 자동 판정`);
    setText("rca-verdict-title", scn.title);
    setText("rca-verdict-lead", `끊김 ${leadSec}초 전 감지`);
    setText("rca-verdict-summary", scn.root_cause || "");

    const stepsEl = document.getElementById("rca-decision-steps");
    if (stepsEl && Array.isArray(scn.decision_tree)) {
      stepsEl.innerHTML = scn.decision_tree.map((st) => {
        const isFail = st.result === "FAIL";
        const badgeCls = isFail ? "badge-crit" : "badge-ok";
        const resKo = isFail ? "이상 확인 (FAIL)" : "정상 통과 (PASS)";
        return `
          <div class="decision-step-item ${isFail ? "step-fail" : ""}">
            <div class="step-top-row">
              <span>${st.step}단계. ${escapeHtml(st.question)}</span>
              <span class="badge ${badgeCls} mono">${resKo}</span>
            </div>
            <div class="step-obs mono">측정 결과: ${escapeHtml(st.observation)}</div>
            <div class="step-imp">진단 의미: ${escapeHtml(st.implication)}</div>
          </div>
        `;
      }).join("");
    }

    const pillsEl = document.getElementById("rca-signature-pills");
    if (pillsEl && Array.isArray(scn.signature_metrics)) {
      pillsEl.innerHTML = scn.signature_metrics.map((m) =>
        `<span class="evidence-pill">${escapeHtml(m)}</span>`
      ).join("");
    }

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
      const offStr = pt.offset_sec > 0 ? `+${pt.offset_sec}초` : `${pt.offset_sec}초`;
      const stateKo = formatConnStateKo(pt.conn_state);
      setText("rca-current-time-badge", `선택 시점: ${offStr} (${stateKo})`);
      setText("rca-cursor-annotation", `[${offStr}] ${pt.annotation || ""}`);
      setText("snap-offset", offStr);
      setText("snap-rf", `${Number(pt.rssi).toFixed(0)} dBm / ${Number(pt.snr).toFixed(0)} dB`);
      setText("snap-mac", `${Number(pt.channel_util).toFixed(0)}% / ${Number(pt.l2_retry_rate).toFixed(1)}%`);
      setText("snap-roam", `${Number(pt.roaming_ms || 0).toFixed(0)} ms`);
      setText("snap-rtt", `${Number(pt.gw_rtt_ms).toFixed(1)} ms / ${Number(pt.jitter_ms || 1).toFixed(0)} ms`);
      setText("snap-retrans", `${pt.tcp_retrans || 0} 회/s`);
      const sqKb = ((pt.send_q_bytes || 0) / 1024).toFixed(1);
      const rqKb = ((pt.recv_q_bytes || 0) / 1024).toFixed(1);
      setText("snap-queues", `${sqKb}K / ${rqKb}K`);

      const snapRiskEl = document.getElementById("snap-risk");
      if (snapRiskEl) {
        snapRiskEl.textContent = `${Number(pt.risk_score).toFixed(1)}점 (${stateKo})`;
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

    drawRcaLayerCanvas("rca-chart-l1", timeline, preOff, discOff, recOff, (ctx, toX, padT, ch, colors) => {
      plotSeriesLine(ctx, timeline, toX, (p) => padT + ((-48 - Math.max(-92, Math.min(-48, p.rssi))) / 44) * ch, colors.sky, 2.0, false);
      plotSeriesLine(ctx, timeline, toX, (p) => padT + (1 - Math.max(0, Math.min(45, p.snr)) / 45) * ch, colors.emerald, 1.6, false);
      plotSeriesLine(ctx, timeline, toX, (p) => padT + (1 - Math.max(0, Math.min(100, p.channel_util)) / 100) * ch, colors.amber, 1.6, false);
      plotSeriesLine(ctx, timeline, toX, (p) => padT + (1 - Math.max(0, Math.min(60, p.l2_retry_rate)) / 60) * ch, colors.rose, 1.5, true);
    });

    drawRcaLayerCanvas("rca-chart-l2", timeline, preOff, discOff, recOff, (ctx, toX, padT, ch, colors) => {
      plotSeriesLine(ctx, timeline, toX, (p) => padT + (1 - Math.max(0, Math.min(350, p.gw_rtt_ms)) / 350) * ch, colors.sky, 2.0, false);
      plotSeriesLine(ctx, timeline, toX, (p) => padT + (1 - Math.max(0, Math.min(18000, p.send_q_bytes || 0)) / 18000) * ch, colors.amber, 1.7, false);
      plotSeriesLine(ctx, timeline, toX, (p) => padT + (1 - Math.max(0, Math.min(20000, p.recv_q_bytes || 0)) / 20000) * ch, colors.indigo, 1.7, false);
      timeline.forEach((p, idx) => {
        if (p.tcp_retrans > 0) {
          const x = toX(idx);
          const bh = Math.min(ch, (p.tcp_retrans / 14) * ch);
          ctx.fillStyle = "rgba(225, 29, 72, 0.55)";
          ctx.fillRect(x - 2, padT + ch - bh, 4, bh);
        }
      });
    });

    drawRcaLayerCanvas("rca-chart-l3", timeline, preOff, discOff, recOff, (ctx, toX, padT, ch, colors, padL, cw) => {
      const y70 = padT + (1 - 0.7) * ch;
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = colors.amber;
      ctx.beginPath();
      ctx.moveTo(padL, y70);
      ctx.lineTo(padL + cw, y70);
      ctx.stroke();
      ctx.restore();

      plotSeriesLine(ctx, timeline, toX, (p) => padT + (1 - Math.max(0, Math.min(100, p.risk_score)) / 100) * ch, colors.indigo, 2.2, false);

      timeline.forEach((p, idx) => {
        if (p.offset_sec === -60 || p.offset_sec === -30 || p.offset_sec === 0 || p.offset_sec === 30) {
          const x = toX(idx);
          const y = padT + (1 - Math.max(0, Math.min(100, p.risk_score)) / 100) * ch;
          const isDrop = p.offset_sec === 0;
          ctx.fillStyle = isDrop ? colors.rose : colors.emerald;
          ctx.beginPath();
          ctx.arc(x, y, 5.5, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = "#FFFFFF";
          ctx.lineWidth = 1.5;
          ctx.stroke();

          ctx.font = "700 9.5px 'JetBrains Mono', monospace";
          ctx.fillStyle = isDrop ? colors.rose : colors.emerald;
          ctx.textAlign = "center";
          ctx.fillText(isDrop ? "30초 보고 끊김(X)" : "30초 정기보고(O)", x, Math.max(padT + 11, y - 9));
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

    const xDisc = toX(offToIdx(discOff));
    const xRec = toX(offToIdx(recOff));
    ctx.fillStyle = "rgba(225, 29, 72, 0.11)";
    ctx.fillRect(xDisc, padT, Math.max(4, xRec - xDisc), ch);

    const xPre = toX(offToIdx(preOff));
    ctx.fillStyle = "rgba(217, 119, 6, 0.09)";
    ctx.fillRect(xPre, padT, Math.max(4, xDisc - xPre), ch);

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
      ctx.fillText(tickOff > 0 ? `+${tickOff}초` : `${tickOff}초`, tx, padT + ch + 14);
    });

    customDrawFn(ctx, toX, padT, ch, colors, padL, cw);

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
    ctx.fillText(`★ 사전감지(${preOff}초)`, xPre - 4, padT + 10);

    ctx.strokeStyle = colors.rose;
    ctx.lineWidth = 2.0;
    ctx.beginPath();
    ctx.moveTo(xDisc, padT);
    ctx.lineTo(xDisc, padT + ch);
    ctx.stroke();
    ctx.fillStyle = colors.rose;
    ctx.textAlign = "left";
    ctx.fillText("✖ 30초 보고 끊김(0초)", xDisc + 4, padT + 10);

    const xCur = toX(offToIdx(state.rcaCursorOffset));
    ctx.strokeStyle = colors.sky;
    ctx.lineWidth = 1.6;
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
  // 11. Tab 3: 18-Metric Telemetry Encyclopedia (Strictly AGV/AMR & ACS Only)
  // ==========================================================================
  function matchesLocationFilter(locStr, filterCode) {
    const loc = (locStr || "").toUpperCase();
    if (filterCode === "ALL") return true;
    if (filterCode === "BOTH") return loc.includes("AGV") && loc.includes("ACS");
    if (filterCode === "AGV/AMR") return loc.includes("AGV");
    if (filterCode === "ACS") return loc.includes("ACS");
    return true;
  }

  function renderMetricsCatalog() {
    const allMetrics = state.metricsCatalog.length > 0 ? state.metricsCatalog : getFallbackMetricsCatalog();
    const q = state.catalogSearchQuery.trim().toLowerCase();

    const filtered = allMetrics.filter((m) => {
      if (state.catalogLayerFilter !== "ALL" && m.layer_code !== state.catalogLayerFilter) {
        return false;
      }
      if (!matchesLocationFilter(m.collection_location, state.catalogLocFilter)) {
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
        const layerNameShort = m.layer_code === "L1_L2" ? "무선 신호" : (m.layer_code === "L3_L4" ? "소켓 전송" : "관제·시스템");
        const loadBadge = (load.level || "").includes("매우") || (load.level || "").includes("없음") ? "badge-ok" : "badge-sky";

        return `
          <tr class="${isSel ? "selected-row" : ""}" data-metric-row="${escapeHtml(m.id)}">
            <td class="text-center mono"><strong>${escapeHtml(m.id)}</strong></td>
            <td class="text-center"><span class="badge ${layerBadge}">${layerNameShort}</span></td>
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
              <div>내부 ${escapeHtml(m.interval_local || "1s")}</div>
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

    const selMetric = allMetrics.find((m) => m.id === state.selectedMetricId) || filtered[0] || allMetrics[0];
    if (selMetric) {
      renderMetricDetailInspector(selMetric);
    }

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
                <span class="badge badge-sky mono">${escapeHtml(m.id)} • ${escapeHtml(m.collection_location)}</span>
                <span class="badge badge-ok mono">부하: ${escapeHtml(load.level || "매우 낮음")}</span>
              </div>
              <h3 class="text-h2" style="margin-bottom:4px;">${escapeHtml(m.name_ko)} <span class="text-caption mono">(${escapeHtml(m.name_en)})</span></h3>
              <p class="text-body" style="font-size:0.78rem; margin-bottom:8px;">${escapeHtml(m.description)}</p>
            </div>
            <div class="detail-section-box mono" style="font-size:0.72rem;">
              <div>• <strong>단위/기준</strong>: ${escapeHtml(m.unit)} (정상 ${escapeHtml(th.normal)} / 위험 ${escapeHtml(th.critical)})</div>
              <div>• <strong>수집위치/주기</strong>: ${escapeHtml(m.collection_location)} | ${escapeHtml(m.recommended_interval)}</div>
              <div>• <strong>수집방법</strong>: <code>${escapeHtml(method.command || method.interface || "")}</code></div>
              <div style="margin-top:4px; color:var(--accent-primary);">• <strong>활용법</strong>: ${escapeHtml(usage.pre_detection || usage.post_mortem || "")}</div>
            </div>
          </div>
        `;
      }).join("");

      gridEl.querySelectorAll("[data-metric-card]").forEach((card) => {
        card.addEventListener("click", () => {
          state.selectedMetricId = card.getAttribute("data-metric-card") || "M01";
          renderMetricsCatalog();
          document.getElementById("panel-catalog-detail")?.scrollIntoView({ behavior: "instant", block: "nearest" });
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
      <div class="detail-section-box">
        <div class="detail-section-label">
          <span>① 수집 항목명 &amp; ② 쉬운 상세 설명</span>
          <span class="badge badge-sky">${escapeHtml(m.layer)}</span>
        </div>
        <div class="text-h2" style="margin-bottom:4px;">${escapeHtml(m.name_ko)} <span class="mono text-caption">(${escapeHtml(m.name_en)})</span></div>
        <p class="text-body" style="font-size:0.8rem;">${escapeHtml(m.description)}</p>
      </div>

      <div class="detail-section-box">
        <div class="detail-section-label">
          <span>③ 측정 단위 및 정상 / 주의 / 위험 기준값</span>
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

      <div class="detail-section-box">
        <div class="detail-section-label">
          <span>④ 수집 위치 (AGV/AMR 및 ACS 전용) &amp; ⑤ 권장 수집 주기</span>
          <span class="badge badge-ok">${escapeHtml(m.collection_location)}</span>
        </div>
        <div class="mono" style="font-size:0.78rem; display:flex; flex-direction:column; gap:4px;">
          <div>• <strong>직접 수집 위치</strong>: ${escapeHtml(m.collection_location)} (AP/WLC 접근 불필요)</div>
          <div>• <strong>권장 수집 주기</strong>: <span class="color-accent">${escapeHtml(m.recommended_interval || `내부 기록 ${m.interval_local} / 정기 보고 ${m.interval_report}`)}</span></div>
        </div>
      </div>

      <div class="detail-section-box">
        <div class="detail-section-label">
          <span>⑥ 수집 시 AGV 또는 ACS에 미치는 부담(부하)</span>
          <span class="badge badge-ok">부담 수준: ${escapeHtml(load.level || "매우 낮음")}</span>
        </div>
        <div class="mono" style="font-size:0.76rem; margin-bottom:4px;">
          CPU 부담: <strong>${escapeHtml(load.cpu_overhead || "0.1% 미만")}</strong> | 평시 무선 통신 부담: <strong>${escapeHtml(load.network_overhead || "0 Bytes/s (내부 기록장 보관)")}</strong>
        </div>
        <p class="text-caption" style="color:var(--text-secondary);">${escapeHtml(load.detail || "")}</p>
      </div>

      <div class="detail-section-box">
        <div class="detail-section-label">
          <span>⑦ 실제 수집 방법 (OS 상태 조회 및 예시 코드)</span>
          <span class="mono text-caption">${escapeHtml(method.interface || "Linux OS")}</span>
        </div>
        <div class="mono" style="font-size:0.76rem; color:var(--accent-primary);">명령어/방식: <code>${escapeHtml(method.command || "")}</code></div>
        <pre class="code-snippet-box mono">${escapeHtml(method.code_snippet || method.detail || "")}</pre>
      </div>

      <div class="detail-section-box" style="border-left:4px solid var(--status-warn);">
        <div class="detail-section-label">
          <span>⑧ 사전 감지 및 사후 원인 분석 활용 방법</span>
          <span class="badge badge-warn mono">중요도 가중치: ${usage.weight !== undefined ? usage.weight : 0.15}</span>
        </div>
        <div style="font-size:0.78rem; display:flex; flex-direction:column; gap:6px;">
          <div><strong class="color-warn">[사전 감지 활용]</strong> ${escapeHtml(usage.pre_detection || "")}</div>
          <div><strong class="color-accent">[사후 분석 활용]</strong> ${escapeHtml(usage.post_mortem || "")}</div>
        </div>
      </div>
    `;
  }

  // ==========================================================================
  // 12. Tab 4: Packet Inspector & Fleet Overhead Calculator
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
    setText("calc-ring-sec-val", `${ringSec} 초 (최근 ${Math.round(ringSec / 60)}분)`);

    const ramKb = ((ringSec * 480) / 1024).toFixed(1);
    const totalBwKbps = ((agvCount * 32) / 1000).toFixed(2);
    const diskMb = (agvCount * 0.88 + 0.4).toFixed(1);

    setText("calc-out-cpu", "0.14 %");
    setText("calc-out-ram", `${ramKb} KB`);
    setText("calc-out-bw", `${totalBwKbps} kbps`);
    setText("calc-out-disk", `${diskMb} MB/일`);
  }

  // ==========================================================================
  // 13. 고시인성 인터랙티브 투어 가이드 (즉시 스크롤 + 직접 타깃 강조 + 실시간 좌표 보정)
  // ==========================================================================
  function clearTourActiveTargets() {
    document.querySelectorAll(".tour-active-target").forEach((el) => {
      el.classList.remove("tour-active-target");
    });
  }

  function updateTourSpotlightRect() {
    if (!state.tourActive) return;
    const step = TOUR_STEPS[state.tourStepIndex];
    if (!step) return;
    const target = document.querySelector(step.targetSelector);
    const ring = document.getElementById("tour-spotlight-ring");
    if (!target || !ring) return;

    const rect = target.getBoundingClientRect();
    ring.classList.add("active");
    ring.style.top = `${Math.max(6, rect.top - 6)}px`;
    ring.style.left = `${Math.max(6, rect.left - 6)}px`;
    ring.style.width = `${Math.max(40, rect.width + 12)}px`;
    ring.style.height = `${Math.max(32, rect.height + 12)}px`;

    const badge = document.getElementById("tour-spotlight-badge");
    if (badge) {
      badge.textContent = `📍 현재 설명 영역 — Step ${state.tourStepIndex + 1} / ${TOUR_STEPS.length}`;
    }
  }

  function startTour(stepIdx = 0) {
    state.tourActive = true;
    state.tourStepIndex = stepIdx;
    document.getElementById("tour-backdrop")?.classList.add("active");
    document.getElementById("tour-popover")?.classList.add("active");
    renderTourStep();
  }

  function closeTour() {
    state.tourActive = false;
    clearTourActiveTargets();
    document.getElementById("tour-backdrop")?.classList.remove("active");
    document.getElementById("tour-popover")?.classList.remove("active");
    document.getElementById("tour-spotlight-ring")?.classList.remove("active");
  }

  function renderTourStep() {
    if (!state.tourActive) return;
    const step = TOUR_STEPS[state.tourStepIndex];
    if (!step) return;

    clearTourActiveTargets();

    // 1. 대상 탭으로 즉시 전환
    if (state.activeTab !== step.tab) {
      switchTab(step.tab);
    }

    // 2. 환영 배너가 대상인 경우 숨김 해제
    if (step.targetSelector === "#welcome-tour-banner") {
      document.getElementById("welcome-tour-banner")?.classList.remove("hidden");
    }

    // 3. 팝오버 텍스트 갱신
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
      nextBtn.textContent = state.tourStepIndex === TOUR_STEPS.length - 1 ? "투어 완료 ✓" : "다음 설명 →";
    }

    // 4. 대상 요소 즉시 스크롤(behavior: "instant") 및 직접 강조 클래스(.tour-active-target) 부여 후 좌표 동기화
    const target = document.querySelector(step.targetSelector);
    if (target) {
      target.classList.add("tour-active-target");
      target.scrollIntoView({ behavior: "instant", block: "center" });
      requestAnimationFrame(() => {
        updateTourSpotlightRect();
        setTimeout(updateTourSpotlightRect, 60);
      });
    }
  }

  // ==========================================================================
  // 14. Theme & Tab Navigation & Event Listeners Binding
  // ==========================================================================
  function applyTheme(themeName) {
    state.theme = themeName === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", state.theme);
    setText("theme-icon", state.theme === "light" ? "🌙" : "☀️");
    setText("theme-label", state.theme === "light" ? "다크 테마로 전환" : "라이트 테마로 전환");
    drawFactoryFloorMap();
    drawLiveMiniChart();
    updateRcaCursorAndCharts();
  }

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
    // 1. 5대 핵심 메뉴 탭 전환
    document.querySelectorAll(".nav-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        const target = btn.getAttribute("data-tab");
        if (target) {
          switchTab(target);
          if (state.tourActive) updateTourSpotlightRect();
        }
      });
    });

    // 2. 라이트(기본) / 다크 테마 전환
    document.getElementById("btn-theme-toggle")?.addEventListener("click", () => {
      state.userToggledTheme = true;
      applyTheme(state.theme === "light" ? "dark" : "light");
    });

    // 3. 투어 가이드 실행 및 이동 컨트롤
    document.getElementById("btn-start-tour")?.addEventListener("click", () => startTour(0));
    document.getElementById("btn-welcome-start-tour")?.addEventListener("click", () => startTour(0));
    document.getElementById("btn-welcome-close")?.addEventListener("click", () => {
      document.getElementById("welcome-tour-banner")?.classList.add("hidden");
      if (state.tourActive) updateTourSpotlightRect();
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

    // 스크롤 및 창 크기 변경 시 투어 스포트라이트 좌표 실시간 재정렬
    window.addEventListener("scroll", () => {
      if (state.tourActive) updateTourSpotlightRect();
    }, true);

    // 4. Tab 1: 지도 표시 토글 및 AGV 클릭 선택
    document.getElementById("btn-toggle-heatmap")?.addEventListener("click", (e) => {
      state.showHeatmap = !state.showHeatmap;
      e.currentTarget.textContent = `무선 반경 표시: ${state.showHeatmap ? "켜짐" : "꺼짐"}`;
      drawFactoryFloorMap();
    });
    document.getElementById("btn-toggle-zones")?.addEventListener("click", (e) => {
      state.showDangerZones = !state.showDangerZones;
      e.currentTarget.textContent = `음영/간섭 구역: ${state.showDangerZones ? "켜짐" : "꺼짐"}`;
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

    // 5. Tab 1: 장애 상황 가상 체험(시뮬레이션 실행) 및 복구
    document.querySelectorAll(".btn-scenario-trigger").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const scnCode = btn.getAttribute("data-scn") || "SCN-01";
        const targetSelect = document.getElementById("injector-target-agv");
        const agvId = (targetSelect && targetSelect.value) || state.selectedAgvId;
        state.selectedAgvId = agvId;

        const msgBox = document.getElementById("injector-status-msg");
        if (msgBox) {
          msgBox.innerHTML = `<span class="color-warn">🚨 <strong>[${escapeHtml(agvId)}]</strong>에 <strong>${escapeHtml(scnCode)}</strong> 장애 상황 가상 체험을 시작했습니다! (사전 감지 주의 → 연결 끊김 → 자동 복구 진행 중)</span>`;
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
        msgBox.innerHTML = `<span class="color-ok">✅ 모든 AGV의 가상 체험 상태가 해제되어 정상 연결 상태로 복구되었습니다.</span>`;
      }
      await pollLiveTelemetry();
    });

    // 6. Tab 2: 장애 사례 선택, 타임라인 슬라이더 및 재생
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
        btn.textContent = "▶ 시간 순서대로 재생";
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
            btn.textContent = "▶ 시간 순서대로 재생";
          }
        }, 180);
      }
    });

    document.getElementById("btn-rca-reset-cursor")?.addEventListener("click", () => {
      state.rcaCursorOffset = -89;
      if (timeSlider) timeSlider.value = "-89";
      updateRcaCursorAndCharts();
    });

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

    // 7. Tab 3: 수집 항목 백과사전 필터 및 검색
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

    // 8. Tab 4: 전송 메시지 예시 탭 및 계산기 슬라이더
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
      if (state.tourActive) updateTourSpotlightRect();
    });
  }

  // ==========================================================================
  // 15. Built-in Fallback 18 Metrics Catalog (Strictly AGV/AMR & ACS Only)
  // ==========================================================================
  function getFallbackMetricsCatalog() {
    return [
      {
        id: "M01", key: "rssi", name_ko: "수신 신호 세기", name_en: "RSSI (Received Signal Strength)",
        layer: "무선 신호·전파 품질", layer_code: "L1_L2", unit: "dBm",
        description: "AGV 무선 랜카드가 받는 와이파이 신호의 강도입니다(0에 가까울수록 강함). 이동 경로상 전파 음영 구역 진입을 가장 먼저 보여줍니다.",
        thresholds: { normal: "-67 dBm 이상", warning: "-68 ~ -74 dBm", critical: "-75 dBm 이하" },
        collection_location: "AGV/AMR", interval_local: "1초", interval_report: "30초 정기 보고 시 요약 동봉",
        recommended_interval: "AGV 내부 기록 1초 / 정기 보고 30초",
        system_load: { level: "매우 낮음", cpu_overhead: "0.05% 미만", network_overhead: "평시 0 B/s (내부 기록장)", detail: "Linux 무선 상태 파일(/proc/net/wireless)을 메모리에서 바로 읽어 부담 없음" },
        collection_method: { interface: "/proc/net/wireless, nl80211", command: "iw dev wlan0 link | grep signal", code_snippet: "with open('/proc/net/wireless') as f:\n    rssi_dbm = float(f.readlines()[2].split()[3].rstrip('.'))" },
        analysis_usage: { weight: 0.25, pre_detection: "1초마다 신호가 얼마나 빠르게 떨어지는지 계산해 음영 구역 진입을 끊김 15~18초 전에 미리 감지", post_mortem: "끊긴 위치 좌표(X,Y)와 합쳐 철제 랙 음영(SCN-02)인지 채널 혼잡(SCN-03)인지 구분" }
      },
      {
        id: "M02", key: "snr", name_ko: "신호 대 잡음 비율", name_en: "SNR (Signal-to-Noise Ratio)",
        layer: "무선 신호·전파 품질", layer_code: "L1_L2", unit: "dB",
        description: "주변 전파 잡음 대비 실제 와이파이 신호가 얼마나 깨끗한지 나타내는 비율입니다.",
        thresholds: { normal: "25 dB 이상", warning: "18 ~ 24 dB", critical: "17 dB 이하" },
        collection_location: "AGV/AMR", interval_local: "1초", interval_report: "30초 정기 보고 시 요약 동봉",
        recommended_interval: "AGV 내부 기록 1초 / 정기 보고 30초",
        system_load: { level: "매우 낮음", cpu_overhead: "0.05% 미만", network_overhead: "평시 0 B/s", detail: "AGV에서 측정한 신호 세기(M01)에서 주변 잡음(M03)을 빼서 즉시 계산" },
        collection_method: { interface: "AGV 무선 드라이버 (RSSI - Noise)", command: "iw dev wlan0 survey dump", code_snippet: "snr_db = rssi_dbm - noise_floor_dbm" },
        analysis_usage: { weight: 0.15, pre_detection: "신호 세기가 강해도 SNR이 17dB 이하로 떨어지면 즉시 사전 경고 알림 발송", post_mortem: "용접기·모터 등 주변 설비 전파 간섭(SCN-02)임을 밝혀내는 핵심 지표" }
      },
      {
        id: "M03", key: "noise_floor", name_ko: "주변 무선 잡음 수치", name_en: "Noise Floor",
        layer: "무선 신호·전파 품질", layer_code: "L1_L2", unit: "dBm",
        description: "공장 내 용접기, 고주파 인버터 등에서 발생하는 바닥 전파 잡음 크기입니다.",
        thresholds: { normal: "-90 dBm 이하", warning: "-89 ~ -85 dBm", critical: "-84 dBm 이상" },
        collection_location: "AGV/AMR", interval_local: "5초", interval_report: "30초 정기 보고 시 요약 동봉",
        recommended_interval: "AGV 내부 기록 5초 / 정기 보고 30초",
        system_load: { level: "낮음", cpu_overhead: "0.1% 미만", network_overhead: "평시 0 B/s", detail: "AGV 무선 랜카드의 채널 상태 정보(Survey) 조회" },
        collection_method: { interface: "nl80211 survey dump", command: "iw dev wlan0 survey dump | grep noise", code_snippet: "noise_dbm = survey_info['noise']" },
        analysis_usage: { weight: 0.10, pre_detection: "특정 설비 가동 시 전파 방해 유입 추세 포착", post_mortem: "와이파이 기지국 고장이 아니라 공장 설비 잡음(SCN-02) 때문임을 증명" }
      },
      {
        id: "M04", key: "phy_rate", name_ko: "무선 연결 속도", name_en: "PHY Link Speed (Mbps)",
        layer: "무선 신호·전파 품질", layer_code: "L1_L2", unit: "Mbps",
        description: "AGV와 무선 기지국(AP) 사이에 현재 맺어진 실제 무선 전송 속도입니다.",
        thresholds: { normal: "100 Mbps 이상", warning: "24 ~ 99 Mbps", critical: "18 Mbps 이하" },
        collection_location: "AGV/AMR", interval_local: "1초", interval_report: "30초 정기 보고 시 요약 동봉",
        recommended_interval: "AGV 내부 기록 1초 / 정기 보고 30초",
        system_load: { level: "매우 낮음", cpu_overhead: "0.05% 미만", network_overhead: "평시 0 B/s", detail: "OS 커널 무선 링크 상태값 읽기" },
        collection_method: { interface: "nl80211 station info", command: "iw dev wlan0 link | grep 'tx bitrate'", code_snippet: "tx_bitrate_mbps = sta_info['tx_bitrate'] / 10.0" },
        analysis_usage: { weight: 0.10, pre_detection: "통신이 완전히 끊어지기 직전에 무선 랜카드가 속도를 단계적으로 낮추는 현상 포착", post_mortem: "속도가 최저(6Mbps)까지 떨어진 시점 확인" }
      },
      {
        id: "M05", key: "l2_retry_rate", name_ko: "무선 구간 재시도 비율", name_en: "Wi-Fi MAC Retry Rate",
        layer: "무선 신호·전파 품질", layer_code: "L1_L2", unit: "%",
        description: "무선 신호가 깨져서 와이파이 칩셋이 다시 보낸 비율입니다.",
        thresholds: { normal: "8% 미만", warning: "8 ~ 20%", critical: "20% 초과" },
        collection_location: "AGV/AMR", interval_local: "1초", interval_report: "30초 정기 보고 시 요약 동봉",
        recommended_interval: "AGV 내부 기록 1초 / 정기 보고 30초",
        system_load: { level: "낮음", cpu_overhead: "0.08% 미만", network_overhead: "평시 0 B/s", detail: "AGV 무선 드라이버 전송 카운터 비교" },
        collection_method: { interface: "nl80211 / ethtool -S wlan0", command: "iw dev wlan0 station dump | grep 'tx retries'", code_snippet: "retry_rate = (delta_tx_retries / max(1, delta_tx_packets)) * 100.0" },
        analysis_usage: { weight: 0.20, pre_detection: "소켓 통신이 끊어지기 수 초 전에 가장 먼저 치솟는 핵심 선행 위험 신호", post_mortem: "무선 전파 구간에서 손실이 있었는지 직접 확인" }
      },
      {
        id: "M06", key: "beacon_loss", name_ko: "기지국 확인 신호 놓침 수", name_en: "Beacon Loss Count",
        layer: "무선 신호·전파 품질", layer_code: "L1_L2", unit: "회/초",
        description: "무선 기지국(AP)이 0.1초마다 보내는 생존 확인 신호(비콘)를 AGV가 놓친 횟수입니다.",
        thresholds: { normal: "0 ~ 1 회/초", warning: "2 ~ 4 회/초", critical: "5 회/초 이상" },
        collection_location: "AGV/AMR", interval_local: "1초", interval_report: "30초 정기 보고 시 요약 동봉",
        recommended_interval: "AGV 내부 기록 1초 / 정기 보고 30초",
        system_load: { level: "매우 낮음", cpu_overhead: "0.05% 미만", network_overhead: "평시 0 B/s", detail: "커널 드라이버 카운터 조회" },
        collection_method: { interface: "nl80211 STA_INFO_BEACON_LOSS", command: "iw dev wlan0 station dump | grep 'beacon loss'", code_snippet: "beacon_loss_delta = sta_info['beacon_loss'] - prev_beacon_loss" },
        analysis_usage: { weight: 0.10, pre_detection: "연속으로 확인 신호를 놓치면 2~3초 내 기지국 연결이 끊어질 것임을 예고", post_mortem: "기지국 변경(로밍) 직전 신호 단절 상태 진단" }
      },
      {
        id: "M07", key: "roaming_ms", name_ko: "기지국(AP) 변경 소요 시간 및 주소", name_en: "Roaming Time & Connected AP ID",
        layer: "무선 신호·전파 품질", layer_code: "L1_L2", unit: "ms",
        description: "AGV가 이동하며 기존 AP에서 새 AP로 갈아타는 데 걸린 시간(ms)과 연결된 AP 주소입니다.",
        thresholds: { normal: "50 ms 미만", warning: "50 ~ 150 ms", critical: "200 ms 초과" },
        collection_location: "AGV/AMR", interval_local: "변경 즉시 (1초 감시)", interval_report: "30초 정기 보고 시 요약 동봉",
        recommended_interval: "AP 변경 발생 즉시 기록 / 정기 보고 30초",
        system_load: { level: "매우 낮음", cpu_overhead: "0.05% 미만", network_overhead: "평시 0 B/s", detail: "AGV wpa_supplicant 이벤트 시각 차이 측정" },
        collection_method: { interface: "wpa_supplicant control event", command: "wpa_cli -i wlan0 status", code_snippet: "roam_ms = (ts_connected - ts_disconnecting) * 1000.0" },
        analysis_usage: { weight: 0.15, pre_detection: "기지국 변경 지연 누적 감지", post_mortem: "기존 AP를 놓지 못하는 현상 및 기지국 변경 실패(SCN-01)를 100% 판별" }
      },
      {
        id: "M08", key: "channel_util", name_ko: "무선 채널 혼잡도", name_en: "Channel Busy Ratio (%)",
        layer: "무선 신호·전파 품질", layer_code: "L1_L2", unit: "%",
        description: "AGV 무선 랜카드가 감지한 현재 주파수 통로의 혼잡 비율입니다(별도 AP 장비 접근 없이 AGV에서 직접 측정).",
        thresholds: { normal: "40% 미만", warning: "40 ~ 65%", critical: "65% 초과" },
        collection_location: "AGV/AMR", interval_local: "5초", interval_report: "30초 정기 보고 시 요약 동봉",
        recommended_interval: "AGV 내부 기록 5초 / 정기 보고 30초",
        system_load: { level: "낮음", cpu_overhead: "0.1% 미만", network_overhead: "평시 0 B/s", detail: "AGV 무선 카드의 channel busy time / active time 비율 계산" },
        collection_method: { interface: "AGV nl80211 survey dump", command: "iw dev wlan0 survey dump | grep -E 'active|busy'", code_snippet: "chan_busy_pct = (delta_busy_time / max(1, delta_active_time)) * 100.0" },
        analysis_usage: { weight: 0.15, pre_detection: "신호 세기는 좋은데 통로가 막혀 통신 지연이 임박했음을 사전 감지", post_mortem: "신호 양호 시 발생하는 무선 채널 과부하(SCN-03)의 결정적 증거" }
      },
      {
        id: "M09", key: "gw_rtt_ms", name_ko: "게이트웨이 응답 시간", name_en: "Gateway Ping RTT",
        layer: "네트워크·소켓 전송", layer_code: "L3_L4", unit: "ms",
        description: "AGV에서 가장 가까운 유선 네트워크 관문(게이트웨이)까지 패킷이 왕복하는 시간입니다.",
        thresholds: { normal: "10 ms 미만", warning: "10 ~ 40 ms", critical: "50 ms 초과" },
        collection_location: "AGV/AMR", interval_local: "2초", interval_report: "30초 정기 보고 시 요약 동봉",
        recommended_interval: "AGV 내부 기록 2초 / 정기 보고 30초",
        system_load: { level: "낮음", cpu_overhead: "0.1% 미만", network_overhead: "2초당 작은 패킷 1개(64B)", detail: "AGV에서 게이트웨이 IP로 가벼운 Ping 측정" },
        collection_method: { interface: "ICMP Echo Probe", command: "ping -c 1 -W 1 <GATEWAY_IP>", code_snippet: "gw_rtt_ms = async_icmp_probe(gateway_ip, timeout=0.5)" },
        analysis_usage: { weight: 0.15, pre_detection: "무선 구간 응답 지연 상승 조기 포착", post_mortem: "무선 구간(AGV↔관문) 문제인지 사내 유선망/ACS 서버 문제인지 구간을 정확히 분리" }
      },
      {
        id: "M10", key: "jitter_ms", name_ko: "응답 시간 흔들림 폭", name_en: "RTT Jitter",
        layer: "네트워크·소켓 전송", layer_code: "L3_L4", unit: "ms",
        description: "통신 응답 시간이 일정하지 않고 들쭉날쭉하게 흔들리는 정도입니다.",
        thresholds: { normal: "5 ms 미만", warning: "5 ~ 20 ms", critical: "20 ms 초과" },
        collection_location: "AGV/AMR, ACS", interval_local: "2초", interval_report: "30초 정기 보고 시 요약 동봉",
        recommended_interval: "내부 기록 2초 / 정기 보고 30초",
        system_load: { level: "매우 낮음", cpu_overhead: "0.02% 미만", network_overhead: "0 B/s", detail: "연속 측정된 응답 시간의 차이 계산" },
        collection_method: { interface: "RTT Stream Difference", command: "ss -ti dst <TARGET_IP>", code_snippet: "jitter_ms = abs(rtt_now - rtt_prev)" },
        analysis_usage: { weight: 0.10, pre_detection: "평균 응답 시간은 낮아 보여도 흔들림 폭이 커지면 통신 불안정 사전 경고", post_mortem: "채널 혼잡(SCN-03)으로 인한 불규칙 지연 판별" }
      },
      {
        id: "M11", key: "tcp_retrans", name_ko: "소켓(TCP) 재전송 횟수", name_en: "TCP Retransmits",
        layer: "네트워크·소켓 전송", layer_code: "L3_L4", unit: "회/초",
        description: "AGV와 ACS 간 소켓 통신에서 상대방 확인 응답(ACK)을 못 받아 다시 보낸 횟수입니다.",
        thresholds: { normal: "0 회/초", warning: "1 ~ 3 회/초", critical: "4 회/초 이상" },
        collection_location: "AGV/AMR, ACS", interval_local: "1초", interval_report: "30초 정기 보고 시 요약 동봉",
        recommended_interval: "AGV 및 ACS 내부 1초 / 정기 보고 30초",
        system_load: { level: "매우 낮음", cpu_overhead: "0.05% 미만", network_overhead: "0 B/s", detail: "OS 커널 소켓 상태표(tcp_info) 직접 조회" },
        collection_method: { interface: "OS Kernel tcp_info", command: "ss -ti state established", code_snippet: "retrans_delta = tcpi_total_retrans - prev_retrans" },
        analysis_usage: { weight: 0.25, pre_detection: "재전송이 연속 발생하면 소켓이 끊어지기 직전 상태임을 직접 포착", post_mortem: "실제 소켓 통신 데이터 유실 정도 확인" }
      },
      {
        id: "M12", key: "tcp_srtt_ms", name_ko: "소켓 종단 간 왕복 시간", name_en: "TCP Smoothed RTT",
        layer: "네트워크·소켓 전송", layer_code: "L3_L4", unit: "ms",
        description: "AGV와 ACS 서버 사이 실제 소켓 통신이 왕복하는 데 걸리는 시간입니다.",
        thresholds: { normal: "15 ms 미만", warning: "15 ~ 60 ms", critical: "60 ms 초과" },
        collection_location: "AGV/AMR, ACS", interval_local: "1초", interval_report: "30초 정기 보고 시 요약 동봉",
        recommended_interval: "AGV 및 ACS 내부 1초 / 정기 보고 30초",
        system_load: { level: "매우 낮음", cpu_overhead: "0.03% 미만", network_overhead: "0 B/s (추가 패킷 없음)", detail: "별도 테스트 패킷 없이 OS 소켓 내부값 조회" },
        collection_method: { interface: "OS Kernel tcp_info (tcpi_rtt)", command: "ss -ti dst <ACS_IP>", code_snippet: "srtt_ms = tcpi_rtt_us / 1000.0" },
        analysis_usage: { weight: 0.10, pre_detection: "실제 제어·보고 소켓이 겪는 지연 상승 감지", post_mortem: "게이트웨이 응답 시간(M09)과 비교해 무선 vs 유선/서버 지연 구분" }
      },
      {
        id: "M13", key: "send_q_bytes", name_ko: "소켓 송신 대기 데이터양", name_en: "Socket Send-Q Bytes",
        layer: "네트워크·소켓 전송", layer_code: "L3_L4", unit: "Bytes",
        description: "프로그램이 보냈으나 상대방에게 전달되지 못해 출발지 버퍼 대기열에 쌓여 있는 데이터양입니다.",
        thresholds: { normal: "0 Bytes", warning: "1 B ~ 4 KB", critical: "4 KB 초과" },
        collection_location: "AGV/AMR, ACS", interval_local: "1초", interval_report: "30초 정기 보고 시 요약 동봉",
        recommended_interval: "AGV 및 ACS 내부 1초 / 정기 보고 30초",
        system_load: { level: "매우 낮음", cpu_overhead: "0.03% 미만", network_overhead: "0 B/s", detail: "OS 소켓 송신 버퍼 크기 조회" },
        collection_method: { interface: "ioctl(SIOCOUTQ) / ss -tnp", command: "ss -tnp | awk '{print $2}'", code_snippet: "send_q = fcntl.ioctl(sock.fileno(), termios.TIOCOUTQ, b'\\x00'*4)" },
        analysis_usage: { weight: 0.15, pre_detection: "송신 대기열이 3초 이상 0으로 비워지지 않고 쌓이면 수 초 내 통신 단절 100% 예고!", post_mortem: "통신 불통으로 송신이 막힌 정확한 시각 확인" }
      },
      {
        id: "M14", key: "recv_q_bytes", name_ko: "소켓 수신 대기 데이터양", name_en: "Socket Recv-Q Bytes",
        layer: "네트워크·소켓 전송", layer_code: "L3_L4", unit: "Bytes",
        description: "통신으로 도착은 했으나 AGV 또는 ACS 프로그램이 바빠서 아직 읽어가지 못한 데이터양입니다.",
        thresholds: { normal: "0 Bytes", warning: "1 B ~ 2 KB", critical: "2 KB 초과" },
        collection_location: "AGV/AMR, ACS", interval_local: "1초", interval_report: "30초 정기 보고 시 요약 동봉",
        recommended_interval: "AGV 및 ACS 내부 1초 / 정기 보고 30초",
        system_load: { level: "매우 낮음", cpu_overhead: "0.03% 미만", network_overhead: "0 B/s", detail: "OS 소켓 수신 버퍼 크기 조회" },
        collection_method: { interface: "ioctl(SIOCINQ) / ss -tnp", command: "ss -tnp | awk '{print $1}'", code_snippet: "recv_q = fcntl.ioctl(sock.fileno(), termios.FIONREAD, b'\\x00'*4)" },
        analysis_usage: { weight: 0.15, pre_detection: "통신 프로그램 처리 지연 조기 감지", post_mortem: "와이파이는 멀쩡한데 프로그램이 일시 멈춰서 끊긴 사례(SCN-04)를 가려내는 결정적 증거!" }
      },
      {
        id: "M15", key: "hb_delta_sec", name_ko: "30초 보고 도착 시간 간격", name_en: "Report Arrival Interval",
        layer: "상위 관제·시스템 상태", layer_code: "L7_SYS", unit: "초(sec)",
        description: "ACS 서버가 AGV로부터 정기 보고를 실제로 받은 시간 간격입니다(정상 기준: 30.0초).",
        thresholds: { normal: "29.5 ~ 30.5 초", warning: "31.0 ~ 38.0 초", critical: "45.0 초 초과 (끊김)" },
        collection_location: "ACS", interval_local: "매 보고 수신 시 & 1초 감시", interval_report: "매 보고 시 기록",
        recommended_interval: "ACS 서버 매 보고 수신 시 및 1초 타임아웃 감시",
        system_load: { level: "매우 낮음", cpu_overhead: "0.01% 미만", network_overhead: "0 B/s", detail: "ACS 서버 수신 시각 차이 계산" },
        collection_method: { interface: "ACS 수신 핸들러 타임스탬프", command: "T_arrival_now - T_arrival_prev", code_snippet: "hb_delta_sec = time.monotonic() - last_report_ts[agv_id]" },
        analysis_usage: { weight: 0.10, pre_detection: "보고 간격이 30초 → 33초 → 37초로 점점 밀리는 현상으로 불안정 AGV 조기 식별", post_mortem: "ACS 관점의 실제 끊김 시각 및 지속 시간 확정" }
      },
      {
        id: "M16", key: "reconnect_count", name_ko: "소켓 재연결 횟수 및 끊김 사유", name_en: "Reconnect Count & Reason Code",
        layer: "상위 관제·시스템 상태", layer_code: "L7_SYS", unit: "회/시간",
        description: "소켓 연결이 끊어져 다시 연결한 횟수와 끊어진 이유 코드(시간 초과, 강제 종료 등)입니다.",
        thresholds: { normal: "0 회/시간", warning: "1 ~ 2 회/시간", critical: "3 회/시간 이상" },
        collection_location: "AGV/AMR, ACS", interval_local: "발생 즉시", interval_report: "발생 시 즉시 기록",
        recommended_interval: "연결/끊김 이벤트 발생 즉시 기록",
        system_load: { level: "매우 낮음", cpu_overhead: "0.01% 미만", network_overhead: "0 B/s", detail: "소켓 연결/종료 이벤트 로그 기록" },
        collection_method: { interface: "AGV & ACS 소켓 이벤트 로그", command: "errno (ETIMEDOUT / ECONNRESET / EOF)", code_snippet: "log_socket_event(agv_id, errno=sock_err, state='RECONNECTED')" },
        analysis_usage: { weight: 0.05, pre_detection: "반복 재연결 AGV 집중 감시", post_mortem: "무선 단절에 의한 시간 초과(ETIMEDOUT)인지 프로그램 재시작(RST)인지 구분" }
      },
      {
        id: "M17", key: "cpu_load", name_ko: "AGV 컴퓨터(CPU) 사용률", name_en: "AGV Host CPU & System Load",
        layer: "상위 관제·시스템 상태", layer_code: "L7_SYS", unit: "%",
        description: "AGV 내부 컴퓨터의 연산 장치(CPU) 사용률 및 통신 인터럽트 처리 비중입니다.",
        thresholds: { normal: "60% 미만", warning: "60 ~ 85%", critical: "85% 초과" },
        collection_location: "AGV/AMR", interval_local: "5초", interval_report: "30초 정기 보고 시 요약 동봉",
        recommended_interval: "AGV 내부 기록 5초 / 정기 보고 30초",
        system_load: { level: "매우 낮음", cpu_overhead: "0.04% 미만", network_overhead: "0 B/s", detail: "Linux 기본 상태 파일(/proc/stat) 읽기" },
        collection_method: { interface: "/proc/stat, /proc/softirqs", command: "cat /proc/stat", code_snippet: "cpu_pct = 100.0 * (1.0 - delta_idle / delta_total)" },
        analysis_usage: { weight: 0.10, pre_detection: "자율주행(라이다) 연산 과부하로 통신 프로그램 멈춤이 임박했음을 감지", post_mortem: "와이파이 문제가 아닌 AGV 컴퓨터 과부하(SCN-04)임을 증명" }
      },
      {
        id: "M18", key: "pose_xy", name_ko: "AGV 주행 위치 좌표 및 속도", name_en: "AGV Position (X, Y) & Speed",
        layer: "상위 관제·시스템 상태", layer_code: "L7_SYS", unit: "m, m/s",
        description: "통신 상태를 측정한 순간의 AGV 공장 내 위치 좌표(X, Y) 및 주행 속도입니다.",
        thresholds: { normal: "정상 주행 구역", warning: "음영 구역 경계 접근", critical: "상습 단절 구역 진입" },
        collection_location: "AGV/AMR, ACS", interval_local: "1초", interval_report: "30초 정기 보고 시 요약 동봉",
        recommended_interval: "AGV 내부 기록 1초 / 정기 보고 30초",
        system_load: { level: "없음 (매우 낮음)", cpu_overhead: "0.0% (기존 좌표 참조)", network_overhead: "0 B/s (기존 보고에 포함)", detail: "기존 주행 제어 모듈의 현재 좌표값 그대로 활용" },
        collection_method: { interface: "AGV 주행 제어 공유 메모리", command: "get_current_pose()", code_snippet: "pos_x, pos_y, speed = nav_controller.get_pose()" },
        analysis_usage: { weight: 0.10, pre_detection: "상습 음영 구역 반경 5m 접근 시 사전 감속 준비", post_mortem: "통신 품질이 나빠진 위치를 공장 2D 지도에 표시하여 전파 음영 지도 자동 완성" }
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
    // 1. Apply Light Enterprise Default Theme immediately
    applyTheme("light");
    bindEvents();

    // 2. Render immediately with built-in fallback data (Zero Blank Screen)
    state.scenariosMap = Object.assign({}, FALLBACK_SCENARIOS);
    state.metricsCatalog = getFallbackMetricsCatalog();
    renderRcaScenarioView();
    renderMetricsCatalog();
    renderPacketInspector();
    updateBandwidthCalculator();
    drawFactoryFloorMap();
    drawLiveMiniChart();

    // 3. Fetch live backend data & start 1s polling loop
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
