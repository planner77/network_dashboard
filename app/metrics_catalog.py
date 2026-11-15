"""
metrics_catalog.py — AGV/AMR ↔ ACS 무선 네트워크 텔레메트리 도메인 모듈
=========================================================================

Owner : domain-analyst (Domain & Telemetry Analyst)
Spec  : docs/ANALYSIS_AND_METRICS.md (18 metrics, risk scoring, 4 RCA scenarios)
        docs/ARCHITECTURE.md        (telemetry_1s columns, /api/metrics-catalog,
                                     /api/scenarios payloads)

Pure Python, standard library only (math, random, json, struct, typing).
All data below is deterministic (seeded) and computed once at import time.

Exported symbols
----------------
METRICS_CATALOG            list[dict]   18 metric specs (M01..M18)
METRICS_BY_ID / METRICS_BY_KEY          lookup dicts
LAYERS                     list[dict]   layer filter metadata (L1_L2 / L3_L4 / L7_SYS)
evaluate_metric(key, value) -> "normal" | "warning" | "critical" | "unknown"
compute_risk_score(sample, prev_score=None, alpha=None) -> dict
classify_rca(samples_window) -> dict
FAILURE_SCENARIOS          dict[str, dict]  SCN-01..SCN-04 (120-pt timelines)
HYBRID_ARCHITECTURE_SPEC   dict         3-stage hybrid telemetry spec + comparison
RISK_WEIGHTS / RISK_THRESHOLDS / TIMELINE_FIELDS / ACS_REPORT_STATUSES
"""

from __future__ import annotations

import json
import math
import random
import struct
from typing import Any, Dict, List, Optional

__all__ = [
    "METRICS_CATALOG",
    "METRICS_BY_ID",
    "METRICS_BY_KEY",
    "LAYERS",
    "RISK_WEIGHTS",
    "RISK_THRESHOLDS",
    "TIMELINE_FIELDS",
    "ACS_REPORT_STATUSES",
    "evaluate_metric",
    "compute_risk_score",
    "classify_rca",
    "FAILURE_SCENARIOS",
    "HYBRID_ARCHITECTURE_SPEC",
    "phy_rate_from_snr",
]

# ---------------------------------------------------------------------------
# 0. Layer metadata
# ---------------------------------------------------------------------------
LAYER_L12 = "L1/L2 무선 물리·MAC"
LAYER_L34 = "L3/L4 네트워크·전송"
LAYER_L7 = "L7 응용·시스템"

LAYERS: List[Dict[str, Any]] = [
    {"layer_code": "L1_L2", "layer": LAYER_L12, "name_en": "Wi-Fi Physical & Data Link Layer", "count": 8,
     "metric_ids": ["M01", "M02", "M03", "M04", "M05", "M06", "M07", "M08"]},
    {"layer_code": "L3_L4", "layer": LAYER_L34, "name_en": "Network & Transport Layer", "count": 6,
     "metric_ids": ["M09", "M10", "M11", "M12", "M13", "M14"]},
    {"layer_code": "L7_SYS", "layer": LAYER_L7, "name_en": "Application & Host System Layer", "count": 4,
     "metric_ids": ["M15", "M16", "M17", "M18"]},
]

_LOAD_VERY_LOW = "매우 낮음"
_LOAD_LOW = "낮음"


def _load(level: str, net: str, detail: str, cpu: str = "< 0.1%") -> Dict[str, Any]:
    return {
        "level": level,
        "score": 1 if level == _LOAD_VERY_LOW else 2,
        "cpu_overhead": cpu,
        "network_overhead": net,
        "detail": detail,
    }


# ---------------------------------------------------------------------------
# 1. METRICS_CATALOG — 18 telemetry metrics
#    `threshold_levels` is a machine-readable companion of `thresholds`
#    (direction "higher_is_better" | "lower_is_better"; warning/critical bounds)
# ---------------------------------------------------------------------------
METRICS_CATALOG: List[Dict[str, Any]] = [
    # ======================= L1/L2 — Wi-Fi PHY & MAC =======================
    {
        "id": "M01",
        "key": "rssi",
        "name_ko": "수신 신호 강도",
        "name_en": "Received Signal Strength Indicator (RSSI)",
        "abbr": "RSSI",
        "layer": LAYER_L12,
        "layer_code": "L1_L2",
        "description": (
            "AGV 무선 랜카드가 현재 연결(Associated)된 AP로부터 수신하는 전파 신호의 세기입니다. "
            "AGV는 이동체이므로 AP와의 거리, 철제 랙·설비에 의한 차폐, 다중경로 페이딩에 따라 RSSI가 초 단위로 변합니다. "
            "RSSI가 -75dBm 이하로 떨어지면 칩셋이 고차 변조(MCS)를 유지하지 못해 재전송이 폭증하고, "
            "로밍 임계값에 도달하기 전까지 기존 AP를 붙잡는 Sticky Client 현상이 발생하여 ACS 소켓 단절의 1차 원인이 됩니다."
        ),
        "unit": "dBm",
        "thresholds": {"normal": "≥ -67 dBm", "warning": "-68 ~ -74 dBm", "critical": "≤ -75 dBm"},
        "threshold_levels": {"direction": "higher_is_better", "warning": -67.5, "critical": -74.5},
        "display_range": [-95, -40],
        "collection_location": "AGV/AMR",
        "interval_local": "1s",
        "interval_report": "30s 요약 피기백",
        "recommended_interval": "로컬 1s (링버퍼) / 보고 30s (피기백: rssi_min·avg·std)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (로컬 전용, 30s 피기백 6 Bytes)",
                             "커널 무선 통계(/proc/net/wireless) 메모리 조회만 수행하며 무선 송신이 발생하지 않음"),
        "collection_method": {
            "interface": "/proc/net/wireless, nl80211 (NL80211_CMD_GET_STATION → NL80211_STA_INFO_SIGNAL)",
            "command": "iw dev wlan0 link | grep signal   # 또는 cat /proc/net/wireless",
            "code_snippet": (
                "def read_rssi(ifname='wlan0'):\n"
                "    with open('/proc/net/wireless') as f:\n"
                "        for line in f.readlines()[2:]:\n"
                "            if line.strip().startswith(ifname + ':'):\n"
                "                cols = line.split()\n"
                "                return float(cols[3].rstrip('.'))  # level (dBm)\n"
                "    return None"
            ),
            "detail": "1초마다 signal level을 읽어 링버퍼에 적재하고, 직전 5초 값으로 d(RSSI)/dt 기울기를 함께 계산합니다.",
        },
        "analysis_usage": {
            "pre_detection": "RSSI 절대값(< -72dBm)과 5초 하락 기울기(d(RSSI)/dt ≤ -2.5 dBm/s)로 음영지역 진입·로밍 임박을 단절 10~20초 전에 감지 (Risk 가중치 w1=0.25).",
            "post_mortem": "단절 직전 RSSI 곡선의 형태(완만한 하락 → SCN-01 Sticky Client, 급락 → SCN-02 음영지역)로 원인을 구분하고, M18 좌표와 결합해 음영 히트맵을 생성.",
            "weight": 0.25,
        },
    },
    {
        "id": "M02",
        "key": "snr",
        "name_ko": "신호 대 잡음비",
        "name_en": "Signal-to-Noise Ratio (SNR)",
        "abbr": "SNR",
        "layer": LAYER_L12,
        "layer_code": "L1_L2",
        "description": (
            "배경 잡음(Noise Floor) 대비 유효 신호 강도의 비율(SNR = RSSI − Noise Floor)입니다. "
            "실제 복조 성공률과 협상 가능한 MCS는 RSSI가 아니라 SNR이 결정합니다. "
            "RSSI가 양호(-62dBm)해도 용접기·인버터·고주파 유도가열 설비가 광대역 잡음을 방출하면 SNR이 12dB 이하로 붕괴하여 "
            "프레임 오류율이 급증하므로, 전자기 간섭(EMI)형 단절을 규명하는 핵심 지표입니다."
        ),
        "unit": "dB",
        "thresholds": {"normal": "≥ 25 dB", "warning": "18 ~ 24 dB", "critical": "≤ 17 dB"},
        "threshold_levels": {"direction": "higher_is_better", "warning": 24.5, "critical": 17.5},
        "display_range": [0, 50],
        "collection_location": "AGV/AMR, AP/WLC",
        "interval_local": "1s",
        "interval_report": "30s 요약 피기백",
        "recommended_interval": "로컬 1s (링버퍼) / 보고 30s (피기백: snr_min)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (로컬 계산, 피기백 1 Byte)",
                             "RSSI와 Noise Floor의 단순 차분 연산으로 추가 I/O가 없음"),
        "collection_method": {
            "interface": "nl80211 survey dump (NL80211_SURVEY_INFO_NOISE) + STA_INFO_SIGNAL",
            "command": "iw dev wlan0 survey dump | grep -A1 'in use' ; iw dev wlan0 link",
            "code_snippet": (
                "snr_db = rssi_dbm - noise_floor_dbm   # 예: -62 - (-95) = 33 dB\n"
                "ring.append({'ts': now, 'snr': snr_db})"
            ),
            "detail": "AP/WLC 측에서는 클라이언트별 SNR(SNMP: bsnMobileStationSnr 등)을 교차 수집하여 업/다운링크 비대칭을 확인합니다.",
        },
        "analysis_usage": {
            "pre_detection": "SNR < 20dB 진입 시 위험 점수에 가산 (w2=0.15). RSSI 정상 + SNR 급락 조합은 EMI 간섭 조기 경보.",
            "post_mortem": "RSSI는 정상인데 SNR만 붕괴한 단절 → 전자기 간섭(SCN-02 EMI 변형)으로 판정하여 무선 AP 증설이 아닌 채널/대역 변경 조치를 유도.",
            "weight": 0.15,
        },
    },
    {
        "id": "M03",
        "key": "noise_floor",
        "name_ko": "배경 잡음 준위",
        "name_en": "Noise Floor",
        "abbr": "Noise",
        "layer": LAYER_L12,
        "layer_code": "L1_L2",
        "description": (
            "해당 무선 채널에서 측정되는 기저 잡음 및 비-Wi-Fi 간섭 에너지 수준입니다. "
            "정상 공장 환경의 5GHz 대역은 -95 ~ -92dBm 수준이지만, 아크 용접·모터 드라이브·전자레인지형 가열 장비 가동 시 "
            "-85dBm 이상으로 상승하여 모든 클라이언트의 SNR을 동시에 끌어내립니다. 특정 구역·시간대 상관 분석에 유용합니다."
        ),
        "unit": "dBm",
        "thresholds": {"normal": "≤ -90 dBm", "warning": "-89 ~ -85 dBm", "critical": "≥ -84 dBm"},
        "threshold_levels": {"direction": "lower_is_better", "warning": -89.5, "critical": -84.5},
        "display_range": [-100, -70],
        "collection_location": "AGV/AMR, AP/WLC",
        "interval_local": "5s",
        "interval_report": "30s 요약 피기백",
        "recommended_interval": "로컬 5s (링버퍼) / 보고 30s (피기백: noise_max)",
        "system_load": _load(_LOAD_LOW, "0 B/s (로컬 survey 조회)",
                             "드라이버 survey 카운터 읽기가 1s 대비 약간 무거워 5초 주기를 권장 (오프채널 스캔 없음)"),
        "collection_method": {
            "interface": "nl80211 NL80211_CMD_GET_SURVEY / AP SNMP MIB (dot11 noise, WLC RRM noise report)",
            "command": "iw dev wlan0 survey dump | awk '/in use/{f=1} f&&/noise/{print $2; exit}'",
            "code_snippet": (
                "import subprocess, re\n"
                "out = subprocess.run(['iw','dev','wlan0','survey','dump'],capture_output=True,text=True).stdout\n"
                "blk = out.split('[in use]')[1]\n"
                "noise = float(re.search(r'noise:\\s+(-?\\d+)', blk).group(1))"
            ),
            "detail": "AGV 측 값과 AP 측 RRM 노이즈 리포트를 시간축으로 정렬하면 간섭원이 AGV 경로상 국소인지 AP 셀 전체인지 구분됩니다.",
        },
        "analysis_usage": {
            "pre_detection": "Noise Floor가 5초 내 6dB 이상 상승하면 SNR 붕괴 전 단계로 간주하여 RF 위험 점수에 반영.",
            "post_mortem": "용접기·모터 가동 스케줄과 Noise Floor 상승 시점을 대조하여 광대역 EMI 유입을 증명 (SCN-02).",
            "weight": 0.05,
        },
    },
    {
        "id": "M04",
        "key": "phy_rate",
        "name_ko": "물리 계층 전송 속도",
        "name_en": "Tx/Rx PHY Rate (MCS Link Rate)",
        "abbr": "PHY Rate",
        "layer": LAYER_L12,
        "layer_code": "L1_L2",
        "description": (
            "MCS(Modulation and Coding Scheme) 인덱스·공간 스트림 수·채널 폭에 따라 무선 칩셋이 실제로 협상한 링크 속도입니다. "
            "칩셋의 Rate Control(예: Minstrel)은 프레임 손실을 감지하면 즉시 낮은 변조 방식으로 강등(Dynamic Rate Fallback)하므로, "
            "PHY Rate 급락은 패킷 유실·TCP 재전송이 표면화되기 직전의 매우 이른 선행 신호입니다."
        ),
        "unit": "Mbps",
        "thresholds": {"normal": "≥ 100 Mbps", "warning": "24 ~ 99 Mbps", "critical": "≤ 18 Mbps"},
        "threshold_levels": {"direction": "higher_is_better", "warning": 99.5, "critical": 18.5},
        "display_range": [0, 450],
        "collection_location": "AGV/AMR",
        "interval_local": "1s",
        "interval_report": "30s 요약 피기백",
        "recommended_interval": "로컬 1s (링버퍼) / 보고 30s (피기백: phy_min)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (로컬 전용)",
                             "STA_INFO 속성 1회 조회로 tx/rx bitrate를 동시에 획득"),
        "collection_method": {
            "interface": "nl80211 NL80211_ATTR_STA_INFO (NL80211_STA_INFO_TX_BITRATE / RX_BITRATE)",
            "command": "iw dev wlan0 station dump | grep -E 'tx bitrate|rx bitrate'",
            "code_snippet": (
                "out = subprocess.run(['iw','dev','wlan0','station','dump'],capture_output=True,text=True).stdout\n"
                "tx = float(re.search(r'tx bitrate:\\s+([\\d.]+)', out).group(1))  # Mbps"
            ),
            "detail": "tx/rx 중 낮은 값을 링크 품질 대표값으로 사용하며, MCS 인덱스와 GI/채널폭을 함께 기록하면 사후 분석 정확도가 향상됩니다.",
        },
        "analysis_usage": {
            "pre_detection": "PHY Rate가 5초 내 50% 이상 강등되면 Dynamic Rate Fallback으로 판단하여 MAC 위험 점수에 가산 (w3 보조 지표).",
            "post_mortem": "단절 직전 PHY Rate가 6Mbps(최저 MCS)까지 내려갔다면 RF 링크 자체 붕괴(SCN-02), 높게 유지되었다면 RF 외 원인(SCN-03/04).",
            "weight": 0.05,
        },
    },
    {
        "id": "M05",
        "key": "l2_retry_rate",
        "name_ko": "802.11 MAC 재전송률",
        "name_en": "802.11 L2 MAC Retry Rate",
        "abbr": "L2 Retry",
        "layer": LAYER_L12,
        "layer_code": "L1_L2",
        "description": (
            "무선 프레임 전송 후 ACK를 받지 못해 MAC 계층에서 재시도한 프레임의 비율(tx_retries / tx_packets)입니다. "
            "802.11 MAC은 최대 7~15회까지 자동 재시도를 수행하므로 TCP는 손실을 즉시 알지 못합니다. "
            "따라서 L2 재전송률은 TCP 타임아웃·소켓 단절보다 수 초 앞서 무선 충돌·감쇠·은폐 노드 문제를 드러내는 핵심 선행 지표입니다."
        ),
        "unit": "%",
        "thresholds": {"normal": "< 8 %", "warning": "8 ~ 20 %", "critical": "> 20 %"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 8.0, "critical": 20.0},
        "display_range": [0, 70],
        "collection_location": "AGV/AMR, AP/WLC",
        "interval_local": "1s",
        "interval_report": "30s 요약 피기백",
        "recommended_interval": "로컬 1s (링버퍼) / 보고 30s (피기백: l2_retry_max)",
        "system_load": _load(_LOAD_LOW, "0 B/s (로컬 전용)",
                             "드라이버 통계 카운터 조회 후 1초 델타 비율 계산 (ethtool ioctl 1회)"),
        "collection_method": {
            "interface": "nl80211 STA_INFO (TX_RETRIES, TX_PACKETS, TX_FAILED) / ethtool -S",
            "command": "iw dev wlan0 station dump | grep -E 'tx packets|tx retries|tx failed'",
            "code_snippet": (
                "d_retry = cur['tx_retries'] - prev['tx_retries']\n"
                "d_pkts  = cur['tx_packets'] - prev['tx_packets']\n"
                "retry_pct = 100.0 * d_retry / max(d_pkts, 1)"
            ),
            "detail": "누적 카운터이므로 반드시 1초 델타로 비율을 계산하며, 카운터 리셋(재연결) 시 음수 델타는 버립니다.",
        },
        "analysis_usage": {
            "pre_detection": "L2 Retry > 15% 급증 시 위험 점수 w3=0.20 가산. TCP 재전송보다 평균 3~6초 먼저 상승하는 선행 지표.",
            "post_mortem": "Retry 35% 이상 + RSSI 급락 → 음영(SCN-02), Retry 상승 + RSSI/SNR 양호 + 채널 점유율 과다 → 채널 혼잡(SCN-03).",
            "weight": 0.20,
        },
    },
    {
        "id": "M06",
        "key": "beacon_loss",
        "name_ko": "비콘 프레임 손실 수",
        "name_en": "Beacon Loss Count",
        "abbr": "Beacon Loss",
        "layer": LAYER_L12,
        "layer_code": "L1_L2",
        "description": (
            "AP가 주기적으로(기본 102.4ms, 초당 약 10개) 브로드캐스트하는 비콘 프레임을 AGV가 수신하지 못한 횟수입니다. "
            "비콘이 연속 유실되면 드라이버는 링크 손실(Beacon Loss Event)로 판단해 연결 해제(Disassoc) 및 재스캔을 시작합니다. "
            "즉, 비콘 손실 급증은 L2 연결이 끊기기 직전 상태를 직접적으로 나타냅니다."
        ),
        "unit": "count/s",
        "thresholds": {"normal": "0 ~ 1 count/s", "warning": "2 ~ 4 count/s", "critical": "≥ 5 count/s"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 1.5, "critical": 4.5},
        "display_range": [0, 12],
        "collection_location": "AGV/AMR",
        "interval_local": "1s",
        "interval_report": "30s 요약 피기백",
        "recommended_interval": "로컬 1s (링버퍼) / 보고 30s (피기백: beacon_loss_sum)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (로컬 전용)", "커널 카운터(beacon loss / beacon rx) 단순 조회"),
        "collection_method": {
            "interface": "nl80211 NL80211_STA_INFO_BEACON_LOSS / NL80211_STA_INFO_BEACON_RX",
            "command": "iw dev wlan0 station dump | grep -E 'beacon loss|beacon rx'",
            "code_snippet": (
                "bl_delta = cur['beacon_loss'] - prev['beacon_loss']\n"
                "expected = 1000 / 102.4  # ≈ 9.77 beacons/s\n"
                "beacon_rx_ratio = (cur['beacon_rx'] - prev['beacon_rx']) / expected"
            ),
            "detail": "드라이버에 따라 beacon loss 이벤트만 제공되는 경우 beacon_rx 기대치(9.77개/s) 대비 수신률로 환산합니다.",
        },
        "analysis_usage": {
            "pre_detection": "초당 2회 이상 비콘 유실이 3초 이상 지속되면 L2 Disassoc 임박으로 MAC 위험 점수에 가산.",
            "post_mortem": "로밍 직전 비콘 손실 폭증 + BSSID 미변경 → Sticky Client(SCN-01). 은폐 노드(Hidden Node) 진단에도 활용.",
            "weight": 0.05,
        },
    },
    {
        "id": "M07",
        "key": "roaming_ms",
        "name_ko": "AP 로밍 소요 시간 및 횟수",
        "name_en": "Roaming Latency & BSSID Change",
        "abbr": "Roaming",
        "layer": LAYER_L12,
        "layer_code": "L1_L2",
        "description": (
            "현재 연결된 AP의 MAC(BSSID)이 변경되는 핸드오버 이벤트와 그 소요 시간(Probe → Auth → Assoc → 802.1X/4-Way Handshake)입니다. "
            "802.11r(Fast BSS Transition)이 적용되면 50ms 이내로 완료되지만, 미적용 상태에서 RADIUS 전체 재인증을 수행하면 "
            "수백 ms~수 초가 소요되어 그 사이 TCP 세그먼트가 유실·지수 백오프에 빠지고 ACS 소켓이 끊어집니다."
        ),
        "unit": "ms",
        "thresholds": {"normal": "< 50 ms", "warning": "50 ~ 150 ms", "critical": "> 200 ms"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 50.0, "critical": 200.0},
        "display_range": [0, 1600],
        "collection_location": "AGV/AMR, AP/WLC",
        "interval_local": "Event 즉시",
        "interval_report": "30s 요약 피기백",
        "recommended_interval": "이벤트 즉시 감지 (로컬 1s 감시) / 보고 30s (피기백: roaming_count·roaming_max_ms)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (이벤트 구독, 폴링 없음)",
                             "wpa_supplicant 컨트롤 소켓 이벤트를 구독하므로 평시 CPU/네트워크 사용이 사실상 0"),
        "collection_method": {
            "interface": "wpa_supplicant control socket (wpa_ctrl) 이벤트: CTRL-EVENT-CONNECTED / CTRL-EVENT-DISCONNECTED / SME: Trying to authenticate",
            "command": "wpa_cli -i wlan0 -a /usr/local/bin/roam_hook.sh   # 이벤트 액션 스크립트",
            "code_snippet": (
                "# roam_hook.sh 에서 호출되는 Python 핸들러\n"
                "if ev.startswith('SME: Trying to authenticate'):\n"
                "    t_start = time.monotonic()\n"
                "elif ev.startswith('CTRL-EVENT-CONNECTED'):\n"
                "    roaming_ms = (time.monotonic() - t_start) * 1000\n"
                "    bssid = re.search(r'to ([0-9a-f:]{17})', ev).group(1)"
            ),
            "detail": "WLC 측 클라이언트 로밍 로그(이전/이후 AP, 사유 코드)와 BSSID·타임스탬프로 조인하면 로밍 실패 원인(인증 지연 vs 스캔 지연)이 분리됩니다.",
        },
        "analysis_usage": {
            "pre_detection": "RSSI가 로밍 임계 근처(-72dBm 이하)인데 BSSID가 바뀌지 않는 상태가 지속되면 Sticky Client 위험으로 표시.",
            "post_mortem": "단절 시점 Roaming Latency > 200ms(특히 1초 이상) + 비콘 손실 급증 → AP 로밍 실패(SCN-01) 확정 근거.",
            "weight": 0.05,
        },
    },
    {
        "id": "M08",
        "key": "channel_util",
        "name_ko": "무선 채널 점유율",
        "name_en": "Channel Utilization (CCA Busy)",
        "abbr": "Ch. Util",
        "layer": LAYER_L12,
        "layer_code": "L1_L2",
        "description": (
            "현재 주파수 채널에서 전체 관측 시간 대비 송신·수신·간섭으로 매체가 사용 중(CCA Busy)이었던 시간의 비율입니다. "
            "Wi-Fi는 CSMA/CA 기반 공유 매체이므로 점유율이 65%를 넘으면 신호 세기와 무관하게 전송 기회(TXOP)를 얻지 못해 "
            "대기 지연·충돌·재전송이 폭증합니다. 동일 채널 AP 중첩(Co-channel Interference)이나 다수 단말 밀집을 증명합니다."
        ),
        "unit": "%",
        "thresholds": {"normal": "< 40 %", "warning": "40 ~ 65 %", "critical": "> 65 %"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 40.0, "critical": 65.0},
        "display_range": [0, 100],
        "collection_location": "AP/WLC",
        "interval_local": "5s",
        "interval_report": "30s 요약 피기백",
        "recommended_interval": "로컬 5s (AGV survey + WLC RRM) / 보고 30s (피기백: channel_util_max)",
        "system_load": _load(_LOAD_LOW, "0 B/s (AGV 로컬) / WLC SNMP 폴링 수백 B/5s",
                             "busy_time / active_time 누적 카운터의 5초 델타 비율 계산"),
        "collection_method": {
            "interface": "nl80211 survey (NL80211_SURVEY_INFO_TIME, TIME_BUSY) / WLC RRM·SNMP (Channel Utilization, QBSS Load IE)",
            "command": "iw dev wlan0 survey dump | grep -A6 'in use' | grep -E 'active time|busy time'",
            "code_snippet": (
                "util_pct = 100.0 * (busy_t - busy_prev) / max(active_t - active_prev, 1)\n"
                "# 또는 비콘의 QBSS Load IE (channel utilization / 255) 파싱"
            ),
            "detail": "AP가 비콘에 실어 보내는 QBSS Load IE를 AGV가 파싱하면 AP 관점의 점유율과 접속 단말 수를 무부하로 얻을 수 있습니다.",
        },
        "analysis_usage": {
            "pre_detection": "점유율 65% 초과가 10초 이상 지속되면 MAC 경합 위험 점수에 가산 (L2 Retry와 결합).",
            "post_mortem": "RSSI·SNR 양호 + 점유율 75% 초과 + RTT/Jitter 급증 → AP 과부하·동일 채널 혼잡(SCN-03) 판정 핵심 증거.",
            "weight": 0.10,
        },
    },
    # ======================= L3/L4 — Network & Transport =======================
    {
        "id": "M09",
        "key": "gw_rtt_ms",
        "name_ko": "게이트웨이 ICMP 왕복 지연",
        "name_en": "Gateway ICMP RTT",
        "abbr": "GW RTT",
        "layer": LAYER_L34,
        "layer_code": "L3_L4",
        "description": (
            "AGV에서 기본 게이트웨이(L3 스위치/WLC SVI)까지의 ICMP Echo 왕복 시간으로, 사실상 무선 구간(AGV↔AP↔유선 첫 홉)만의 지연을 측정합니다. "
            "ACS 응답 지연이 발생했을 때 이 값이 정상이면 문제는 유선 백본·ACS 서버 측, 이 값이 높으면 무선 구간 측이라는 "
            "명확한 책임 경계(Demarcation)를 제공합니다."
        ),
        "unit": "ms",
        "thresholds": {"normal": "< 10 ms", "warning": "10 ~ 40 ms", "critical": "> 50 ms"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 10.0, "critical": 50.0},
        "display_range": [0, 320],
        "collection_location": "AGV/AMR",
        "interval_local": "2s",
        "interval_report": "30s 요약 피기백",
        "recommended_interval": "로컬 2s (비동기 ICMP 프로브) / 보고 30s (피기백: gw_rtt_avg·max)",
        "system_load": _load(_LOAD_LOW, "약 64 B/s (2초당 64B Echo Request + Reply)",
                             "유일하게 능동 패킷을 발생시키는 지표이나 2초당 64Byte로 무선 점유 영향은 0.001% 미만. 타임아웃 300ms로 응답 없음은 300으로 기록"),
        "collection_method": {
            "interface": "Raw ICMP socket (SOCK_RAW / SOCK_DGRAM ICMP), fping",
            "command": "fping -c1 -t300 -q $(ip route | awk '/default/{print $3}')",
            "code_snippet": (
                "sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_ICMP)\n"
                "t0 = time.perf_counter(); sock.sendto(echo_pkt, (gw_ip, 0))\n"
                "sock.settimeout(0.3); sock.recv(64)\n"
                "gw_rtt_ms = (time.perf_counter() - t0) * 1000"
            ),
            "detail": "asyncio 기반 비동기 프로브로 구현하여 보고 스레드를 블로킹하지 않으며, 300ms 타임아웃 시 손실로 집계합니다.",
        },
        "analysis_usage": {
            "pre_detection": "GW RTT가 이동 평균 대비 3배 이상 상승하면 무선 구간 큐잉/재전송 진행 중으로 판단 (w4 보조 지표).",
            "post_mortem": "GW RTT 정상(< 10ms) + ACS 보고 지연 → 무선이 아닌 AGV/ACS 애플리케이션 병목(SCN-04) 판정 근거.",
            "weight": 0.05,
        },
    },
    {
        "id": "M10",
        "key": "jitter_ms",
        "name_ko": "네트워크 지터",
        "name_en": "RTT Jitter",
        "abbr": "Jitter",
        "layer": LAYER_L34,
        "layer_code": "L3_L4",
        "description": (
            "연속된 왕복 지연(RTT) 측정값 간 편차의 평균(mean |RTT_i − RTT_{i-1}|)입니다. "
            "평균 RTT가 아직 낮더라도 지터가 급증하면 무선 매체 경합(백오프), 드라이버 큐 적체(Bufferbloat), "
            "백그라운드 로밍 스캔(Off-channel Scan)이 시작되었음을 의미하며, 실시간 제어 명령의 도착 시간 불확실성을 키웁니다."
        ),
        "unit": "ms",
        "thresholds": {"normal": "< 5 ms", "warning": "5 ~ 20 ms", "critical": "> 20 ms"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 5.0, "critical": 20.0},
        "display_range": [0, 150],
        "collection_location": "AGV/AMR, ACS Server",
        "interval_local": "2s",
        "interval_report": "30s 요약 피기백",
        "recommended_interval": "로컬 2s (RTT 이동 편차) / 보고 30s (피기백: jitter_max)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (M09/M12 측정값 재사용)", "기존 RTT 샘플의 이동 편차 계산만 수행"),
        "collection_method": {
            "interface": "M09 ICMP RTT 샘플 및 M12 tcpi_rttvar 재사용",
            "command": "ss -ti dst <ACS_IP> | grep -o 'rtt:[0-9.]*/[0-9.]*'   # rtt/rttvar",
            "code_snippet": (
                "diffs = [abs(a - b) for a, b in zip(rtts[1:], rtts[:-1])]\n"
                "jitter_ms = sum(diffs) / max(len(diffs), 1)   # RFC 3550 스타일 단순화"
            ),
            "detail": "ACS 서버 측에서는 보고 패킷 도착 간격의 편차로 응용 계층 지터를 별도로 계산하여 교차 검증합니다.",
        },
        "analysis_usage": {
            "pre_detection": "지터 > 20ms 스파이크가 반복되면 평균 RTT 상승 이전에 경합·로밍 탐색 시작을 감지.",
            "post_mortem": "지터 100ms 이상 + 채널 점유율 과다 → 채널 혼잡(SCN-03), 지터 정상 + 소켓 정체 → 시스템 병목(SCN-04).",
            "weight": 0.05,
        },
    },
    {
        "id": "M11",
        "key": "tcp_retrans",
        "name_ko": "TCP 세그먼트 재전송 수",
        "name_en": "TCP Retransmits",
        "abbr": "TCP Retx",
        "layer": LAYER_L34,
        "layer_code": "L3_L4",
        "description": (
            "ACS 소켓 세션에서 ACK를 받지 못해 커널 TCP 스택이 재전송한 세그먼트 수(초당 증분)입니다. "
            "TCP는 재전송 타이머(RTO)를 200ms → 400ms → 800ms … 로 지수 증가(Exponential Backoff)시키므로, "
            "재전송이 연속되면 수 초 만에 응용 계층 Write/Read 타임아웃에 도달해 30초 보고가 멈춥니다. 단절 직전 상태를 직접 포착하는 핵심 지표입니다."
        ),
        "unit": "count/s",
        "thresholds": {"normal": "0 count/s", "warning": "1 ~ 3 count/s", "critical": "≥ 4 count/s"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 0.5, "critical": 3.5},
        "display_range": [0, 10],
        "collection_location": "AGV/AMR, ACS Server",
        "interval_local": "1s",
        "interval_report": "30s 요약 피기백",
        "recommended_interval": "로컬 1s (링버퍼) / 보고 30s (피기백: tcp_retrans_delta)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (커널 소켓 정보 조회)",
                             "NETLINK_INET_DIAG 1회 질의로 대상 소켓의 tcp_info 구조체 전체를 획득"),
        "collection_method": {
            "interface": "getsockopt(TCP_INFO) → tcpi_total_retrans / NETLINK_INET_DIAG (ss -ti)",
            "command": "ss -ti dst <ACS_IP>:<PORT> | grep -oE 'retrans:[0-9]+/[0-9]+'",
            "code_snippet": (
                "import socket, struct\n"
                "raw = sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_INFO, 232)\n"
                "total_retrans = struct.unpack_from('I', raw, 100)[0]  # tcpi_total_retrans\n"
                "retrans_per_s = total_retrans - prev_total_retrans"
            ),
            "detail": "애플리케이션이 직접 보유한 ACS 소켓 FD에 TCP_INFO를 질의하면 외부 명령 없이 마이크로초 단위로 조회됩니다.",
        },
        "analysis_usage": {
            "pre_detection": "TCP 재전송 ≥ 2/s 발생 시 위험 점수 w4=0.25 가산. 지수 백오프 진입 = 수 초 내 보고 정지를 직접 예고.",
            "post_mortem": "단절 직전 재전송이 없었다면 무선 손실이 아닌 응용 블로킹(SCN-04), 재전송 폭증이면 무선 계층(SCN-01~03) 원인.",
            "weight": 0.25,
        },
    },
    {
        "id": "M12",
        "key": "tcp_srtt_ms",
        "name_ko": "TCP 평활 왕복 지연",
        "name_en": "TCP Smoothed RTT (srtt)",
        "abbr": "TCP sRTT",
        "layer": LAYER_L34,
        "layer_code": "L3_L4",
        "description": (
            "커널 TCP 스택이 실제 ACS 통신 세그먼트와 ACK의 시간차로 측정·평활화한 종단 간(AGV↔ACS) 왕복 지연입니다. "
            "별도 Ping 없이 실제 제어/보고 소켓이 체감하는 지연을 그대로 반영하므로, GW RTT(무선 구간)와 비교하면 "
            "지연이 무선 구간·유선 백본·서버 처리 중 어디에서 누적되는지 분리할 수 있습니다."
        ),
        "unit": "ms",
        "thresholds": {"normal": "< 15 ms", "warning": "15 ~ 60 ms", "critical": "> 60 ms"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 15.0, "critical": 60.0},
        "display_range": [0, 400],
        "collection_location": "AGV/AMR, ACS Server",
        "interval_local": "1s",
        "interval_report": "30s 요약 피기백",
        "recommended_interval": "로컬 1s (링버퍼) / 보고 30s (피기백: tcp_srtt_max)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (추가 패킷 없음)", "M11과 동일한 tcp_info 조회 결과를 재사용"),
        "collection_method": {
            "interface": "getsockopt(TCP_INFO) → tcpi_rtt / tcpi_rttvar (μs)",
            "command": "ss -ti dst <ACS_IP> | grep -oE 'rtt:[0-9.]+/[0-9.]+'",
            "code_snippet": (
                "tcpi_rtt_us, tcpi_rttvar_us = struct.unpack_from('II', raw, 68)\n"
                "tcp_srtt_ms = tcpi_rtt_us / 1000.0"
            ),
            "detail": "srtt − gw_rtt 차이가 크면 유선/서버 구간 지연, 둘 다 크면 무선 구간 지연으로 해석합니다.",
        },
        "analysis_usage": {
            "pre_detection": "srtt가 RTO 하한(200ms)에 근접하면 재전송 타이머 만료 위험이 커지므로 전송 위험 점수에 가산.",
            "post_mortem": "GW RTT 정상 + srtt 급등 → 수신측 지연 ACK(소프트IRQ 기아) 또는 서버 처리 지연(SCN-04).",
            "weight": 0.05,
        },
    },
    {
        "id": "M13",
        "key": "send_q_bytes",
        "name_ko": "소켓 송신 대기 큐 크기",
        "name_en": "Socket Send-Q",
        "abbr": "Send-Q",
        "layer": LAYER_L34,
        "layer_code": "L3_L4",
        "description": (
            "애플리케이션이 send()로 커널에 넘겼으나 상대방 ACK를 아직 받지 못해 커널 송신 버퍼에 남아 있는 바이트 수입니다. "
            "정상 상태에서는 수 ms 내 0으로 비워지지만, 무선 손실로 ACK가 오지 않으면 30초 보고 패킷과 후속 데이터가 계속 쌓입니다. "
            "Send-Q가 0으로 돌아오지 않고 누적되는 패턴은 수 초 내 소켓 Write Timeout이 발생할 것을 거의 확정적으로 예고합니다."
        ),
        "unit": "Bytes",
        "thresholds": {"normal": "0 B", "warning": "1 B ~ 4 KB", "critical": "> 4 KB"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 1.0, "critical": 4096.0},
        "display_range": [0, 16384],
        "collection_location": "AGV/AMR, ACS Server",
        "interval_local": "1s",
        "interval_report": "30s 요약 피기백",
        "recommended_interval": "로컬 1s (링버퍼) / 보고 30s (피기백: send_q_max)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (커널 버퍼 상태 조회)", "ioctl(SIOCOUTQ) 1회 호출"),
        "collection_method": {
            "interface": "ioctl(fd, SIOCOUTQ) / NETLINK_INET_DIAG (ss -tn Send-Q 컬럼)",
            "command": "ss -tn dst <ACS_IP> | awk 'NR>1{print $3}'   # Send-Q",
            "code_snippet": (
                "import fcntl, termios, array\n"
                "buf = array.array('i', [0])\n"
                "fcntl.ioctl(sock.fileno(), termios.TIOCOUTQ, buf)  # == SIOCOUTQ\n"
                "send_q_bytes = buf[0]"
            ),
            "detail": "단일 샘플보다 '0이 아닌 상태의 지속 시간'이 중요하므로 연속 3초 이상 잔류 여부를 함께 기록합니다.",
        },
        "analysis_usage": {
            "pre_detection": "Send-Q > 0 Bytes가 3초 이상 지속되면 위험 점수 w5=0.15 가산 (소켓 Write Timeout 직접 예고).",
            "post_mortem": "단절 직전 Send-Q 누적 + TCP 재전송 → 무선 경로 손실, Send-Q 0 + Recv-Q 누적 → 응용 행(SCN-04).",
            "weight": 0.15,
        },
    },
    {
        "id": "M14",
        "key": "recv_q_bytes",
        "name_ko": "소켓 수신 대기 큐 크기",
        "name_en": "Socket Recv-Q",
        "abbr": "Recv-Q",
        "layer": LAYER_L34,
        "layer_code": "L3_L4",
        "description": (
            "커널이 패킷을 정상 수신했으나 AGV(또는 ACS) 애플리케이션이 recv()로 읽어가지 못해 쌓여 있는 바이트 수입니다. "
            "이 값이 증가한다는 것은 네트워크(Wi-Fi)는 데이터를 제대로 전달하고 있는데 수신 프로세스가 멈춰 있음을 의미합니다. "
            "제어 프로세스 데드락, GC 정지, CPU 기아로 인한 스레드 미스케줄링을 무선 문제와 명확히 구분하는 핵심 판별 지표입니다."
        ),
        "unit": "Bytes",
        "thresholds": {"normal": "0 B", "warning": "1 B ~ 2 KB", "critical": "> 2 KB"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 1.0, "critical": 2048.0},
        "display_range": [0, 20000],
        "collection_location": "AGV/AMR, ACS Server",
        "interval_local": "1s",
        "interval_report": "30s 요약 피기백",
        "recommended_interval": "로컬 1s (링버퍼) / 보고 30s (피기백: recv_q_max)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (커널 버퍼 상태 조회)", "ioctl(SIOCINQ/FIONREAD) 1회 호출"),
        "collection_method": {
            "interface": "ioctl(fd, SIOCINQ / FIONREAD) / NETLINK_INET_DIAG (ss -tn Recv-Q 컬럼)",
            "command": "ss -tnp dst <ACS_IP> | awk 'NR>1{print $2}'   # Recv-Q",
            "code_snippet": (
                "buf = array.array('i', [0])\n"
                "fcntl.ioctl(sock.fileno(), termios.FIONREAD, buf)  # == SIOCINQ\n"
                "recv_q_bytes = buf[0]"
            ),
            "detail": "수집 스레드는 보고 스레드와 분리된 별도 경량 스레드(또는 외부 ss 질의)로 동작해야 보고 스레드가 행에 걸린 상황에서도 값을 기록할 수 있습니다.",
        },
        "analysis_usage": {
            "pre_detection": "Recv-Q가 2KB를 넘어 계속 증가하면 응용 계층 행으로 소켓 버퍼가 가득 차기(Zero Window) 전에 경보.",
            "post_mortem": "RSSI/SNR/GW RTT 정상 + Recv-Q 급증 + CPU > 92% → AGV/ACS 소켓 블로킹·시스템 병목(SCN-04) 확정.",
            "weight": 0.10,
        },
    },
    # ======================= L7 — Application & Host System =======================
    {
        "id": "M15",
        "key": "hb_delta_sec",
        "name_ko": "ACS 상태 보고 도착 간격",
        "name_en": "Heartbeat Interval Delta",
        "abbr": "HB Δ",
        "layer": LAYER_L7,
        "layer_code": "L7_SYS",
        "description": (
            "ACS 서버가 실제로 AGV 상태 보고 패킷을 수신한 시간 간격(기준 30.0초)이며, 다음 보고가 오지 않는 동안에는 "
            "마지막 수신 이후 경과 시간(워치독)으로 갱신됩니다. 보고 간격이 30.0s → 31.8s → 35.4s처럼 흔들리는 도착 드리프트(Arrival Drift)는 "
            "완전 단절 이전의 불안정 AGV를 식별하는 ACS 측 유일한 레거시 관측 수단입니다."
        ),
        "unit": "sec",
        "thresholds": {"normal": "29.5 ~ 30.5 s", "warning": "31 ~ 38 s", "critical": "> 45 s (단절 판정)"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 30.5, "critical": 45.0},
        "display_range": [0, 60],
        "collection_location": "ACS Server",
        "interval_local": "1s",
        "interval_report": "매 보고 시",
        "recommended_interval": "매 보고 수신 시 기록 + ACS 1s 타임아웃 워치독",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (ACS 인메모리 타임스탬프 비교)", "AGV당 타임스탬프 1개 비교, AGV 1,000대에서도 무시 가능"),
        "collection_method": {
            "interface": "ACS 소켓 수신 핸들러 타임스탬프 (T_now − T_last)",
            "command": "(ACS 애플리케이션 내부) on_report(agv_id) → hb_delta = now - last_rx[agv_id]",
            "code_snippet": (
                "def on_report(agv_id, now):\n"
                "    hb_delta_sec = now - last_rx.get(agv_id, now)\n"
                "    last_rx[agv_id] = now\n"
                "def watchdog_1s(now):\n"
                "    for agv, t in last_rx.items():\n"
                "        if now - t > 45: mark_disconnected(agv)"
            ),
            "detail": "워치독은 1초 주기로 경과 시간을 갱신하여 31s 초과 시 DELAYED, 45s 초과 시 DISCONNECTED로 판정합니다.",
        },
        "analysis_usage": {
            "pre_detection": "보고 간격 드리프트(> 30.5s)가 2회 연속 발생한 AGV를 불안정 후보로 표시 (레거시 관측의 유일한 단서).",
            "post_mortem": "레거시 관점에서 단절이 언제 '인지'되었는지 기준선 제공 — 하이브리드 조기 경보 선행 시간(Lead Time) 산정의 기준.",
            "weight": 0.0,
        },
    },
    {
        "id": "M16",
        "key": "reconnect_count",
        "name_ko": "TCP Keepalive / 재연결 횟수",
        "name_en": "Socket Reconnect Count & Close Reason",
        "abbr": "Reconnect",
        "layer": LAYER_L7,
        "layer_code": "L7_SYS",
        "description": (
            "ACS 소켓 세션이 끊어진 뒤 SYN부터 다시 맺은 횟수(시간당)와 종료 사유 코드(FIN 정상 종료 / RST 강제 리셋 / ETIMEDOUT 무응답 타임아웃)입니다. "
            "재연결 빈도는 만성적인 무선 불안정 AGV·구역을 찾아내는 지표이며, 종료 사유는 단절 주체(AGV·ACS·네트워크)를 가리키는 결정적 단서입니다."
        ),
        "unit": "count/hr",
        "thresholds": {"normal": "0 count/hr", "warning": "1 ~ 2 count/hr", "critical": "≥ 3 count/hr"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 0.5, "critical": 2.5},
        "display_range": [0, 10],
        "collection_location": "AGV/AMR, ACS Server",
        "interval_local": "Event 즉시",
        "interval_report": "이벤트 발생 시",
        "recommended_interval": "이벤트 즉시 기록 / 재연결 직후 보고 (종료 사유 + 블랙박스 덤프 트리거)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (평시) / 재연결 시 수십 Bytes", "소켓 라이프사이클 콜백 또는 eBPF tracepoint 이벤트 기반"),
        "collection_method": {
            "interface": "애플리케이션 소켓 래퍼 / eBPF tracepoint sock:inet_sock_set_state",
            "command": "bpftrace -e 'tracepoint:sock:inet_sock_set_state /args->newstate==7/ { printf(\"%d %d\\n\", args->oldstate, args->dport); }'",
            "code_snippet": (
                "try:\n"
                "    sock.sendall(report)\n"
                "except (ConnectionResetError) as e:  reason = 'RST'\n"
                "except (TimeoutError, socket.timeout): reason = 'ETIMEDOUT'\n"
                "reconnect_log.append({'ts': now, 'reason': reason}); reconnect_count += 1"
            ),
            "detail": "재연결 직후 첫 보고에 종료 사유·단절 지속 시간을 담고, ±60초 링버퍼 블랙박스 덤프 업로드를 트리거합니다.",
        },
        "analysis_usage": {
            "pre_detection": "최근 1시간 재연결 3회 이상 AGV는 동일 경로 재진입 시 사전 경보 민감도를 높임 (적응형 임계치).",
            "post_mortem": "ETIMEDOUT → 무선/경로 손실, RST → 상대측 소켓 강제 종료(ACS 워커 재시작 등), FIN → 정상/계획 종료로 구분.",
            "weight": 0.0,
        },
    },
    {
        "id": "M17",
        "key": "cpu_load",
        "name_ko": "AGV CPU 및 SoftIRQ 부하",
        "name_en": "Host CPU & NET_RX SoftIRQ Load",
        "abbr": "CPU",
        "layer": LAYER_L7,
        "layer_code": "L7_SYS",
        "description": (
            "AGV 온보드 컴퓨터(IPC/SBC)의 CPU 사용률과 네트워크 수신 인터럽트(NET_RX SoftIRQ) 처리 비중입니다. "
            "SLAM·라이다 포인트클라우드 연산이 폭주해 CPU가 100%에 도달하면 네트워크 보고 스레드와 SoftIRQ가 스케줄링되지 못해 "
            "Wi-Fi가 정상이어도 소켓 수신 큐가 쌓이고 보고가 멈춥니다. 내부 자원 고갈형 장애를 네트워크 장애와 구분합니다."
        ),
        "unit": "%",
        "thresholds": {"normal": "< 60 %", "warning": "60 ~ 85 %", "critical": "> 85 %"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 60.0, "critical": 85.0},
        "display_range": [0, 100],
        "collection_location": "AGV/AMR",
        "interval_local": "5s",
        "interval_report": "30s 요약 피기백",
        "recommended_interval": "로컬 5s (위험 구간 1s 가속) / 보고 30s (피기백: cpu_max)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (로컬 전용)", "/proc/stat, /proc/softirqs 텍스트 파일 2개 읽기"),
        "collection_method": {
            "interface": "/proc/stat (user/system/iowait/softirq jiffies), /proc/softirqs (NET_RX 행)",
            "command": "head -1 /proc/stat ; grep NET_RX /proc/softirqs",
            "code_snippet": (
                "def cpu_pct(prev, cur):\n"
                "    idle_d = (cur[3] + cur[4]) - (prev[3] + prev[4])\n"
                "    tot_d  = sum(cur) - sum(prev)\n"
                "    return 100.0 * (1 - idle_d / max(tot_d, 1))\n"
                "cur = list(map(int, open('/proc/stat').readline().split()[1:]))"
            ),
            "detail": "softirq_pct는 /proc/stat의 softirq jiffies 비중으로 함께 기록하며, 코어별 편중(특정 코어 100%) 여부도 확인합니다.",
        },
        "analysis_usage": {
            "pre_detection": "CPU > 85%가 10초 이상 지속되고 Recv-Q가 증가하면 소켓 행 위험 경보 (소켓 버퍼 위험 점수에 가산).",
            "post_mortem": "CPU > 92% + Recv-Q 급증 + 무선 지표 정상 → 내부 자원 고갈(SCN-04). 무선 공사 대신 코어 분리(taskset) 조치.",
            "weight": 0.10,
        },
    },
    {
        "id": "M18",
        "key": "pose_xy",
        "name_ko": "AGV 주행 좌표 및 속도",
        "name_en": "AGV Pose (X, Y) & Velocity",
        "abbr": "Pose",
        "layer": LAYER_L7,
        "layer_code": "L7_SYS",
        "description": (
            "네트워크 지표를 수집한 시점의 AGV 공장 맵 내 좌표(x, y)와 주행 속도입니다. 그 자체는 네트워크 지표가 아니지만, "
            "모든 무선 품질 샘플에 위치를 태깅하면 '어디에서' 품질이 나빠지는지 공간 상관 분석이 가능해져 "
            "상습 음영 구역(Dead Zone) 히트맵 자동 생성, AP 증설 위치 선정, 경로별 사전 감속 정책 수립의 근거가 됩니다."
        ),
        "unit": "m, m/s",
        "thresholds": {"normal": "음영 구역 외 정상 주행 (0.5 ~ 1.5 m/s)",
                       "warning": "상습 음영 히트맵 셀(최근 24h 위험 점수 ≥ 45) 진입",
                       "critical": "음영 구역 내 정지·저속 체류 (단절 반복 셀)"},
        "threshold_levels": None,
        "display_range": None,
        "collection_location": "AGV/AMR",
        "interval_local": "1s",
        "interval_report": "30s 요약 피기백",
        "recommended_interval": "로컬 1s (링버퍼, 지표와 동일 타임스탬프) / 보고 30s (기존 위치 보고 재사용)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (기존 주행 제어 데이터 재사용)",
                             "내비게이션 스택이 이미 계산한 pose를 공유 메모리에서 참조할 뿐 추가 연산이 없음", cpu="≈ 0%"),
        "collection_method": {
            "interface": "ROS /amcl_pose 또는 /odom 토픽, 내비게이션 스택 공유 메모리",
            "command": "rostopic echo -n1 /amcl_pose   # ROS1 / ros2 topic echo --once /amcl_pose",
            "code_snippet": (
                "def on_pose(msg):\n"
                "    latest_pose.update(x=msg.pose.pose.position.x,\n"
                "                       y=msg.pose.pose.position.y)\n"
                "# 1초 샘플링 시 ring.append({**net_metrics, **latest_pose, 'v': odom_speed})"
            ),
            "detail": "히트맵은 1m×1m 그리드 셀별 RSSI 최소값·위험 점수 최대값·단절 횟수를 롤업하여 생성합니다.",
        },
        "analysis_usage": {
            "pre_detection": "상습 음영 셀 진입 3~5초 전 경로 예측으로 선제 감속·802.11v 로밍 유도 (위치 기반 예측 경보).",
            "post_mortem": "단절 좌표를 누적해 음영 히트맵을 생성하고, SCN-02(물리적 음영) 판정 시 반복 발생 좌표를 증거로 제시.",
            "weight": 0.0,
        },
    },
]

METRICS_BY_ID: Dict[str, Dict[str, Any]] = {m["id"]: m for m in METRICS_CATALOG}
METRICS_BY_KEY: Dict[str, Dict[str, Any]] = {m["key"]: m for m in METRICS_CATALOG}


def evaluate_metric(key: str, value: Optional[float]) -> str:
    """Classify a metric value into "normal" | "warning" | "critical" ("unknown" if n/a)."""
    meta = METRICS_BY_KEY.get(key)
    if meta is None or value is None or not meta.get("threshold_levels"):
        return "unknown"
    lv = meta["threshold_levels"]
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if lv["direction"] == "higher_is_better":
        if v < lv["critical"]:
            return "critical"
        if v < lv["warning"]:
            return "warning"
        return "normal"
    if v > lv["critical"]:
        return "critical"
    if v >= lv["warning"]:
        return "warning"
    return "normal"


# ---------------------------------------------------------------------------
# 2. Pre-detection multi-metric risk scoring
# ---------------------------------------------------------------------------
# Doc weights (ANALYSIS_AND_METRICS.md §3.1): w1 RSSI 0.25, w2 SNR 0.15,
# w3 L2 Retry 0.20, w4 TCP Retrans 0.25, w5 Send-Q 0.15.
# They are grouped into 4 diagnostic components:
#   rf_signal      = w1 + w2  (0.40)   RSSI level/slope, SNR
#   mac_contention = w3       (0.20)   L2 retry, channel util, PHY fallback, beacon loss
#   transport_tcp  = w4       (0.25)   TCP retrans, GW RTT, jitter, srtt
#   socket_buffer  = w5       (0.15)   Send-Q, Recv-Q, CPU, heartbeat drift
#
# Final score = max(linear weighted sum, noisy-OR fusion). The noisy-OR term
# prevents a single saturated domain (e.g. socket hang with perfect RF) from
# being diluted by the healthy domains — a pure linear sum would cap a
# CPU/socket-only failure at 15 points and never warn.
RISK_WEIGHTS: Dict[str, float] = {
    "rf_signal": 0.40,
    "mac_contention": 0.20,
    "transport_tcp": 0.25,
    "socket_buffer": 0.15,
}
_NOISY_OR_GAIN: Dict[str, float] = {
    "rf_signal": 0.92,
    "mac_contention": 0.82,
    "transport_tcp": 0.90,
    "socket_buffer": 0.88,
}
RISK_THRESHOLDS: Dict[str, Any] = {
    "CONNECTED": "< 45",
    "PRE_WARNING": "45 ~ 84.9",
    "DISCONNECTED": ">= 85",
    "pre_warning": 45.0,
    "early_warning_push": 70.0,
    "disconnected": 85.0,
}


def _num(sample: Dict[str, Any], key: str, default: Optional[float] = None) -> Optional[float]:
    v = sample.get(key, default)
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _ramp(x: Optional[float], lo: float, hi: float) -> float:
    """Linear severity 0..100 between lo (0) and hi (100)."""
    if x is None:
        return 0.0
    if hi == lo:
        return 100.0 if x >= hi else 0.0
    return max(0.0, min(100.0, (x - lo) / (hi - lo) * 100.0))


def _fuse(subs: List[float]) -> float:
    """Dominant-weighted fusion of sub-severities (0..100)."""
    subs = [s for s in subs if s is not None]
    if not subs:
        return 0.0
    return min(100.0, 0.85 * max(subs) + 0.15 * (sum(subs) / len(subs)))


def _components(sample: Dict[str, Any]) -> Dict[str, float]:
    rssi = _num(sample, "rssi")
    slope = _num(sample, "rssi_slope", 0.0)
    snr = _num(sample, "snr")
    noise = _num(sample, "noise_floor")
    if snr is None and rssi is not None and noise is not None:
        snr = rssi - noise

    # --- RF signal (RSSI level, RSSI 5s slope, SNR) ---
    rssi_sev = _ramp(-rssi, 67.0, 85.0) if rssi is not None else 0.0
    snr_sev = _ramp(-snr, -25.0, -8.0) if snr is not None else 0.0
    slope_sev = _ramp(-(slope or 0.0), 0.8, 4.0)
    base = max(rssi_sev, snr_sev)
    rf = min(100.0, 0.85 * base + 0.15 * min(rssi_sev, snr_sev) + 0.30 * slope_sev)

    # --- MAC contention (L2 retry, channel util, PHY fallback, beacon loss) ---
    mac = _fuse([
        _ramp(_num(sample, "l2_retry_rate"), 8.0, 40.0),
        _ramp(_num(sample, "channel_util"), 40.0, 85.0),
        _ramp(-_num(sample, "phy_rate"), -100.0, -6.0) if _num(sample, "phy_rate") is not None else 0.0,
        _ramp(_num(sample, "beacon_loss"), 1.0, 7.0),
    ])

    # --- Transport / TCP (retrans, GW RTT, jitter, srtt) ---
    transport = _fuse([
        _ramp(_num(sample, "tcp_retrans"), 0.0, 6.0),
        _ramp(_num(sample, "gw_rtt_ms"), 10.0, 150.0),
        _ramp(_num(sample, "jitter_ms"), 5.0, 60.0),
        _ramp(_num(sample, "tcp_srtt_ms"), 15.0, 300.0),
    ])

    # --- Socket buffer & host (Send-Q, Recv-Q, CPU, heartbeat drift) ---
    socket_buf = _fuse([
        _ramp(_num(sample, "send_q_bytes"), 0.0, 8192.0),
        _ramp(_num(sample, "recv_q_bytes"), 0.0, 4096.0),
        _ramp(_num(sample, "cpu_load"), 60.0, 98.0),
        _ramp(_num(sample, "hb_delta_sec"), 31.0, 45.0),
    ])
    return {
        "rf_signal": round(rf, 1),
        "mac_contention": round(mac, 1),
        "transport_tcp": round(transport, 1),
        "socket_buffer": round(socket_buf, 1),
    }


def _conn_state(score: float) -> str:
    if score >= RISK_THRESHOLDS["disconnected"]:
        return "DISCONNECTED"
    if score >= RISK_THRESHOLDS["pre_warning"]:
        return "PRE_WARNING"
    return "CONNECTED"


def _predicted_issue(sample: Dict[str, Any], comps: Dict[str, float], score: float) -> str:
    if score < RISK_THRESHOLDS["pre_warning"]:
        if score >= 30:
            return "경미한 품질 변동 — 링버퍼 감시 강화"
        return "정상 — 이상 징후 없음"
    rssi = _num(sample, "rssi", -60.0)
    snr = _num(sample, "snr")
    if snr is None:
        nf = _num(sample, "noise_floor")
        snr = (rssi - nf) if nf is not None else 30.0
    slope = _num(sample, "rssi_slope", 0.0) or 0.0
    util = _num(sample, "channel_util", 0.0) or 0.0
    cpu = _num(sample, "cpu_load", 0.0) or 0.0
    recv_q = _num(sample, "recv_q_bytes", 0.0) or 0.0
    gw = _num(sample, "gw_rtt_ms", 0.0) or 0.0
    roaming = _num(sample, "roaming_ms", 0.0) or 0.0
    rf_ok = rssi >= -68 and snr >= 22

    if rf_ok and gw < 15 and (recv_q > 1024 or cpu > 85):
        return "AGV 시스템 병목·소켓 행 의심 (CPU/Recv-Q 급증, 무선 정상)"
    if rf_ok and util > 65:
        return "AP 채널 혼잡 의심 (CCA 점유율 과다, RTT·지터 급증)"
    if roaming > 200:
        return "AP 로밍 지연·실패 (핸드오버 > 200ms)"
    if rssi >= -70 and snr < 18:
        return "전자기 간섭(EMI) 의심 — 잡음 상승으로 SNR 붕괴"
    if slope <= -2.5 or rssi <= -80:
        return "물리적 음영지역 진입 — RSSI 급락"
    if rssi <= -70:
        return "Sticky Client 의심 — 로밍 임계 미도달 상태로 신호 약화"
    dominant = max(comps, key=comps.get)
    return {
        "rf_signal": "무선 신호 품질 저하",
        "mac_contention": "무선 매체 경합·재전송 증가",
        "transport_tcp": "TCP 재전송 폭증 — 소켓 타임아웃 임박",
        "socket_buffer": "소켓 버퍼 적체 — 보고 지연 임박",
    }[dominant]


def compute_risk_score(sample: Dict[str, Any], prev_score: Optional[float] = None,
                       alpha: Optional[float] = None) -> Dict[str, Any]:
    """Multi-metric pre-detection risk score (0..100) from one 1-second sample.

    sample keys (all optional, missing → treated as healthy): rssi, rssi_slope
    (dBm/s over 5s), snr, noise_floor, phy_rate, l2_retry_rate, beacon_loss,
    channel_util, tcp_retrans, gw_rtt_ms, jitter_ms, tcp_srtt_ms, send_q_bytes,
    recv_q_bytes, cpu_load, hb_delta_sec, roaming_ms.

    If prev_score is given, EWMA smoothing is applied:
        score = alpha * raw + (1 - alpha) * prev_score   (alpha default 0.6)

    Returns {risk_score, conn_state, components{rf_signal, mac_contention,
    transport_tcp, socket_buffer}, predicted_issue, raw_score, linear_score,
    dominant_component, early_warning}.
    """
    sample = sample or {}
    comps = _components(sample)
    linear = sum(RISK_WEIGHTS[k] * comps[k] for k in comps)
    prod = 1.0
    for k, v in comps.items():
        prod *= (1.0 - _NOISY_OR_GAIN[k] * v / 100.0)
    noisy_or = 100.0 * (1.0 - prod)
    raw = max(0.0, min(100.0, max(linear, noisy_or)))
    score = raw
    if prev_score is not None:
        a = 0.6 if alpha is None else float(alpha)
        score = a * raw + (1.0 - a) * float(prev_score)
    score = round(max(0.0, min(100.0, score)), 1)
    return {
        "risk_score": score,
        "conn_state": _conn_state(score),
        "components": comps,
        "predicted_issue": _predicted_issue(sample, comps, score),
        "raw_score": round(raw, 1),
        "linear_score": round(linear, 1),
        "dominant_component": max(comps, key=comps.get),
        "early_warning": score >= RISK_THRESHOLDS["early_warning_push"],
    }


# ---------------------------------------------------------------------------
# 3. Post-mortem RCA classifier (signature matching over a sample window)
# ---------------------------------------------------------------------------
SCENARIO_TITLES: Dict[str, str] = {
    "SCN-01": "AP 로밍 실패 / Sticky Client",
    "SCN-02": "물리적 음영지역 및 전자기 간섭 (Dead Zone / EMI)",
    "SCN-03": "AP 과부하 및 동일 채널 혼잡 (Channel Contention)",
    "SCN-04": "AGV/ACS 소켓 블로킹 및 시스템 병목 (Socket Hang)",
    "NORMAL": "정상 — 장애 시그니처 없음",
}

_SCENARIO_ACTIONS: Dict[str, List[str]] = {
    "SCN-01": [
        "AGV 무선 드라이버 Roaming Trigger Threshold를 -75dBm → -70dBm으로 상향하고 백그라운드 스캔 주기를 단축",
        "AP/WLC에 802.11k(Neighbor Report)·802.11v(BSS Transition)·802.11r(Fast BSS Transition) 활성화하여 핸드오버 < 50ms 확보",
        "ACS가 사전 경보(Risk ≥ 70) 수신 시 802.11v BTM 요청으로 인접 AP 강제 로밍 유도 + 로밍 구간 AGV 감속",
    ],
    "SCN-02": [
        "히트맵 상 음영 좌표에 지향성 안테나 또는 보조 AP(Mesh/유선 백홀) 증설, 철제 랙 주변 AP 높이·각도 재조정",
        "2.4GHz 대역 사용 배제 및 5GHz 비간섭 채널 고정, 용접·인버터 설비에 차폐/필터 적용 및 가동 스케줄 상관 관리",
        "음영 구간 진입 전 AGV가 ACS 명령을 선 수신(버퍼링)하고 구간 통과 후 보고하는 경로 기반 통신 정책 적용",
    ],
    "SCN-03": [
        "해당 AP에 집중된 클라이언트(핸디 스캐너·태블릿 등)를 인접 AP로 로드밸런싱하고 AGV 전용 SSID/QoS(WMM AC_VO) 분리",
        "채널 폭 20MHz 최적화 및 동일 채널 AP 재배치(RRM)로 Co-channel Interference 해소",
        "불필요한 멀티캐스트·브로드캐스트(mDNS, SSDP, ARP 폭주) 차단 및 최저 기본 전송률(Basic Rate) 12Mbps 이상 상향",
    ],
    "SCN-04": [
        "네트워크가 아닌 애플리케이션/OS 병목으로 판정 — 무선 공사·AP 증설 불필요, AGV 소프트웨어 팀으로 이관",
        "SLAM/내비게이션 스레드와 네트워크 보고 스레드의 CPU 코어 분리(taskset/cgroups cpuset) 및 보고 스레드 실시간 우선순위 부여",
        "보고 소켓을 비동기 논블로킹(epoll/asyncio)으로 전환하고 Recv-Q 워치독(> 2KB 5초 지속 시 프로세스 자가 복구) 적용",
    ],
    "NORMAL": [
        "조치 불필요 — 평시 30초 보고 및 1초 링버퍼 감시 유지",
        "주기적 히트맵 리뷰로 잠재 음영 구역 추적",
        "임계치(Risk 45/70/85) 오탐률 월간 점검",
    ],
}


def _vals(window: List[Dict[str, Any]], key: str) -> List[float]:
    out = []
    for s in window:
        v = s.get(key)
        if v is None:
            continue
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def _window_stats(window: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    def mn(k):
        v = _vals(window, k)
        return min(v) if v else None

    def mx(k):
        v = _vals(window, k)
        return max(v) if v else None

    rssi = _vals(window, "rssi")
    snr_vals = _vals(window, "snr")
    if not snr_vals:
        nf = _vals(window, "noise_floor")
        snr_vals = [a - b for a, b in zip(rssi, nf)]
    steepest = None
    if len(rssi) >= 6:
        steepest = min((rssi[i] - rssi[i - 5]) / 5.0 for i in range(5, len(rssi)))
    elif "rssi_slope" in (window[0] if window else {}):
        sv = _vals(window, "rssi_slope")
        steepest = min(sv) if sv else None
    return {
        "rssi_min": mn("rssi"),
        "rssi_max": mx("rssi"),
        "snr_min": min(snr_vals) if snr_vals else None,
        "noise_max": mx("noise_floor"),
        "phy_min": mn("phy_rate"),
        "l2_retry_max": mx("l2_retry_rate"),
        "beacon_loss_max": mx("beacon_loss"),
        "roaming_max_ms": mx("roaming_ms"),
        "channel_util_max": mx("channel_util"),
        "gw_rtt_max": mx("gw_rtt_ms"),
        "jitter_max": mx("jitter_ms"),
        "tcp_retrans_max": mx("tcp_retrans"),
        "tcp_srtt_max": mx("tcp_srtt_ms"),
        "send_q_max": mx("send_q_bytes"),
        "recv_q_max": mx("recv_q_bytes"),
        "cpu_max": mx("cpu_load"),
        "risk_max": mx("risk_score"),
        "rssi_steepest_slope": round(steepest, 2) if steepest is not None else None,
        "samples": len(window),
    }


def _chk(label: str, value: Any, threshold: str, passed: bool, weight: float) -> Dict[str, Any]:
    if isinstance(value, float):
        value = round(value, 1)
    return {"check": label, "value": value, "threshold": threshold, "matched": bool(passed), "weight": weight}


def _g(st: Dict[str, Optional[float]], k: str, default: float) -> float:
    v = st.get(k)
    return default if v is None else v


def _signature_checks(st: Dict[str, Optional[float]]) -> Dict[str, List[Dict[str, Any]]]:
    rssi_min = _g(st, "rssi_min", -60)
    snr_min = _g(st, "snr_min", 35)
    noise_max = _g(st, "noise_max", -95)
    phy_min = _g(st, "phy_min", 300)
    retry = _g(st, "l2_retry_max", 0)
    bl = _g(st, "beacon_loss_max", 0)
    roam = _g(st, "roaming_max_ms", 0)
    util = _g(st, "channel_util_max", 20)
    gw = _g(st, "gw_rtt_max", 3)
    jit = _g(st, "jitter_max", 1)
    rtx = _g(st, "tcp_retrans_max", 0)
    rq = _g(st, "recv_q_max", 0)
    cpu = _g(st, "cpu_max", 40)
    slope = _g(st, "rssi_steepest_slope", 0)
    return {
        "SCN-01": [
            _chk("로밍 핸드오버 지연 (Roaming Latency)", roam, "> 200 ms", roam > 200, 0.35),
            _chk("비콘 손실 급증 (Beacon Loss)", bl, "≥ 5 /s", bl >= 5, 0.20),
            _chk("RSSI 로밍 임계 이하 하락", rssi_min, "≤ -76 dBm", rssi_min <= -76, 0.20),
            _chk("배경 잡음 정상 (EMI 없음)", noise_max, "≤ -88 dBm", noise_max <= -88, 0.15),
            _chk("채널 점유율 정상 (혼잡 없음)", util, "< 65 %", util < 65, 0.10),
        ],
        "SCN-02": [
            _chk("RSSI 급락 또는 SNR 붕괴", f"{rssi_min:.0f} dBm / {snr_min:.0f} dB",
                 "RSSI ≤ -82 dBm 또는 SNR ≤ 12 dB", rssi_min <= -82 or snr_min <= 12, 0.25),
            _chk("L2 재전송률 폭증", retry, "> 35 %", retry > 35, 0.20),
            _chk("PHY Rate 최저 MCS 강등", phy_min, "≤ 12 Mbps", phy_min <= 12, 0.15),
            _chk("배경 잡음 상승 (EMI)", noise_max, "≥ -88 dBm", noise_max >= -88, 0.15),
            _chk("로밍 이벤트 없음 (동일 AP 유지)", roam, "< 200 ms", roam < 200, 0.15),
            _chk("RSSI 급격 하락 기울기", slope, "≤ -2.5 dBm/s", slope <= -2.5, 0.10),
        ],
        "SCN-03": [
            _chk("RSSI 양호 유지", rssi_min, "≥ -68 dBm", rssi_min >= -68, 0.20),
            _chk("SNR 양호 유지", snr_min, "≥ 22 dB", snr_min >= 22, 0.10),
            _chk("채널 점유율 과다 (CCA Busy)", util, "> 75 %", util > 75, 0.30),
            _chk("GW RTT / 지터 급증", f"{gw:.0f} ms / {jit:.0f} ms", "RTT ≥ 80 ms 또는 Jitter ≥ 40 ms",
                 gw >= 80 or jit >= 40, 0.25),
            _chk("TCP 재전송 다발", rtx, "≥ 3 /s", rtx >= 3, 0.15),
        ],
        "SCN-04": [
            _chk("RSSI·SNR 정상", f"{rssi_min:.0f} dBm / {snr_min:.0f} dB", "RSSI ≥ -66 dBm, SNR ≥ 25 dB",
                 rssi_min >= -66 and snr_min >= 25, 0.20),
            _chk("GW ICMP RTT 정상 (무선 구간 정상)", gw, "< 15 ms", gw < 15, 0.20),
            _chk("소켓 Recv-Q 적체", rq, "> 2048 Bytes", rq > 2048, 0.30),
            _chk("AGV CPU 포화", cpu, "> 92 %", cpu > 92, 0.30),
        ],
    }


def _decision_tree(st: Dict[str, Optional[float]], code: str) -> List[Dict[str, Any]]:
    """4-step RCA decision tree. PASS = layer healthy, FAIL = anomaly found."""
    rssi_min = _g(st, "rssi_min", -60)
    snr_min = _g(st, "snr_min", 35)
    noise_max = _g(st, "noise_max", -95)
    roam = _g(st, "roaming_max_ms", 0)
    bl = _g(st, "beacon_loss_max", 0)
    util = _g(st, "channel_util_max", 20)
    gw = _g(st, "gw_rtt_max", 3)
    jit = _g(st, "jitter_max", 1)
    rq = _g(st, "recv_q_max", 0)
    cpu = _g(st, "cpu_max", 40)

    rf_pass = rssi_min > -75 and snr_min > 17
    roam_pass = roam <= 150 and bl < 5
    ch_pass = util <= 65 and gw <= 50
    host_pass = cpu <= 85 and rq <= 2048

    impl = {
        1: ("RF 링크 정상 → 물리적 음영·EMI 가능성 배제, 상위 계층(MAC 경합·호스트)으로 탐색 진행"
            if rf_pass else
            ("RSSI는 유지되나 잡음 상승으로 SNR 붕괴 → 전자기 간섭(EMI) 후보" if rssi_min > -75 else
             "RSSI 임계 이하 → 음영지역(SCN-02) 또는 로밍 실패(SCN-01) 후보, Step 2에서 로밍 이벤트로 분기")),
        2: ("로밍 정상/미발생 → Sticky Client·핸드오버 실패 배제"
            if roam_pass else
            "핸드오버 지연·비콘 연속 손실 → 기존 AP 고착 후 뒤늦은 로밍 실패 (SCN-01 시그니처)"),
        3: ("채널 점유율·GW RTT 정상 → AP 과부하·동일 채널 혼잡 배제"
            if ch_pass else
            ("RF 정상인데 점유율·RTT 급증 → AP 과부하·동일 채널 혼잡 (SCN-03 시그니처)" if rf_pass else
             "RF 저하에 따른 2차 지연 증가 (재전송 누적 결과) — 근본 원인은 하위 계층")),
        4: ("호스트 자원·소켓 큐 정상 → 애플리케이션 병목 배제"
            if host_pass else
            ("무선·GW 정상인데 CPU 포화·Recv-Q 적체 → 소켓 행/시스템 병목 (SCN-04 시그니처)"
             if (rf_pass and ch_pass) else "호스트 지표 이상 동반 — 네트워크 원인과 복합 여부 확인 필요")),
    }
    steps = [
        {"step": 1, "question": "RF 신호 품질(RSSI > -75dBm, SNR > 17dB)이 유지되었는가?",
         "observation": f"RSSI min {rssi_min:.0f} dBm, SNR min {snr_min:.0f} dB, Noise max {noise_max:.0f} dBm",
         "result": "PASS" if rf_pass else "FAIL", "implication": impl[1]},
        {"step": 2, "question": "AP 로밍(BSSID 변경)이 150ms 이내 완료되고 비콘 손실이 없었는가?",
         "observation": f"Roaming max {roam:.0f} ms, Beacon Loss max {bl:.0f} /s",
         "result": "PASS" if roam_pass else "FAIL", "implication": impl[2]},
        {"step": 3, "question": "채널 점유율(≤ 65%)과 게이트웨이 RTT(≤ 50ms)가 정상이었는가?",
         "observation": f"Channel Util max {util:.0f} %, GW RTT max {gw:.0f} ms, Jitter max {jit:.0f} ms",
         "result": "PASS" if ch_pass else "FAIL", "implication": impl[3]},
        {"step": 4, "question": "AGV 호스트 자원(CPU ≤ 85%)과 소켓 Recv-Q(≤ 2KB)가 정상이었는가?",
         "observation": f"CPU max {cpu:.0f} %, Recv-Q max {rq:.0f} Bytes",
         "result": "PASS" if host_pass else "FAIL", "implication": impl[4]},
    ]
    return steps


def classify_rca(samples_window: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Classify the root cause of an anomaly/disconnection from a telemetry window.

    samples_window: list of 1-second sample dicts (telemetry_1s rows or scenario
    timeline points), typically ±60 s around the disconnection.

    Returns {scenario_code ("SCN-01".."SCN-04" | "NORMAL"), title, confidence
    (0..1), scores{code: 0..1}, evidence[...], decision_tree[4 steps],
    root_cause_summary, recommended_actions[3], stats{...}, anomaly_detected}.
    """
    window = [s for s in (samples_window or []) if isinstance(s, dict)]
    if not window:
        return {
            "scenario_code": "NORMAL", "title": SCENARIO_TITLES["NORMAL"], "confidence": 0.0,
            "scores": {}, "evidence": [], "decision_tree": [], "anomaly_detected": False,
            "root_cause_summary": "분석할 샘플이 없습니다.", "recommended_actions": _SCENARIO_ACTIONS["NORMAL"],
            "stats": {},
        }
    st = _window_stats(window)

    # anomaly gate — any risk >= 45, any non-CONNECTED state, or any critical metric
    anomaly = False
    if _g(st, "risk_max", 0) >= RISK_THRESHOLDS["pre_warning"]:
        anomaly = True
    if any(s.get("conn_state") in ("PRE_WARNING", "DISCONNECTED") for s in window):
        anomaly = True
    if not anomaly:
        crit_keys = ["rssi", "snr", "l2_retry_rate", "tcp_retrans", "send_q_bytes",
                     "recv_q_bytes", "cpu_load", "channel_util", "gw_rtt_ms", "roaming_ms"]
        for s in window:
            if any(evaluate_metric(k, s.get(k)) == "critical" for k in crit_keys):
                anomaly = True
                break
        if not anomaly:
            r = compute_risk_score(window[-1])
            anomaly = r["risk_score"] >= RISK_THRESHOLDS["pre_warning"]

    checks = _signature_checks(st)
    scores = {code: round(sum(c["weight"] for c in lst if c["matched"]) /
                          sum(c["weight"] for c in lst), 3) for code, lst in checks.items()}
    best = max(scores, key=scores.get)
    if not anomaly or scores[best] < 0.55:
        code = "NORMAL"
        conf = round(1.0 - (scores[best] if anomaly else 0.0) * 0.5, 2) if not anomaly else round(scores[best], 2)
        summary = ("윈도우 내 위험 점수와 핵심 지표가 모두 정상 범위입니다." if not anomaly else
                   "이상 징후는 있으나 4대 장애 시그니처와 충분히 일치하지 않습니다 (판정 보류, 추가 데이터 필요).")
        evidence: List[Dict[str, Any]] = checks[best] if anomaly else []
    else:
        code = best
        conf = scores[best]
        evidence = checks[best]
        summary = _root_cause_summary(code, st)

    return {
        "scenario_code": code,
        "title": SCENARIO_TITLES[code],
        "confidence": conf,
        "scores": scores,
        "evidence": evidence,
        "decision_tree": _decision_tree(st, code),
        "root_cause_summary": summary,
        "recommended_actions": _SCENARIO_ACTIONS[code],
        "stats": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in st.items()},
        "anomaly_detected": anomaly,
    }


def _root_cause_summary(code: str, st: Dict[str, Optional[float]]) -> str:
    f = lambda k, d=0.0: _g(st, k, d)  # noqa: E731
    if code == "SCN-01":
        return (f"RSSI가 {f('rssi_max', -58):.0f} → {f('rssi_min'):.0f} dBm으로 하락하는 동안 기존 AP에 고착(Sticky)되었고, "
                f"뒤늦은 로밍 시도에서 핸드오버가 {f('roaming_max_ms'):.0f} ms 소요(비콘 손실 최대 {f('beacon_loss_max'):.0f}/s)되어 "
                f"TCP 지수 백오프 후 소켓이 단절되었습니다. 잡음·채널 점유율은 정상으로 RF 간섭·혼잡은 배제됩니다.")
    if code == "SCN-02":
        return (f"음영/간섭 구역 진입으로 RSSI {f('rssi_min'):.0f} dBm, SNR {f('snr_min'):.0f} dB(잡음 최대 {f('noise_max'):.0f} dBm)까지 "
                f"급락하여 PHY Rate가 {f('phy_min'):.0f} Mbps로 강등되고 L2 재전송률이 {f('l2_retry_max'):.0f}%까지 폭증했습니다. "
                f"로밍 이벤트 없이 동일 AP 링크가 물리적으로 붕괴한 음영지역/EMI 장애입니다.")
    if code == "SCN-03":
        return (f"RSSI({f('rssi_min'):.0f} dBm)·SNR({f('snr_min'):.0f} dB)은 양호했으나 채널 점유율이 {f('channel_util_max'):.0f}%까지 "
                f"치솟아 전송 기회를 얻지 못했고, GW RTT {f('gw_rtt_max'):.0f} ms·지터 {f('jitter_max'):.0f} ms·TCP 재전송 "
                f"{f('tcp_retrans_max'):.0f}/s로 소켓이 타임아웃되었습니다. AP 과부하·동일 채널 혼잡 장애입니다.")
    if code == "SCN-04":
        return (f"RSSI {f('rssi_min'):.0f} dBm·GW RTT {f('gw_rtt_max'):.1f} ms로 무선 구간은 정상이었으나 AGV CPU가 "
                f"{f('cpu_max'):.0f}%로 포화되어 보고 스레드가 스케줄링되지 못했고, 소켓 Recv-Q가 {f('recv_q_max'):.0f} Bytes까지 적체되어 "
                f"30초 보고가 타임아웃되었습니다. 네트워크가 아닌 AGV 애플리케이션/OS 병목입니다.")
    return "정상"


# ---------------------------------------------------------------------------
# 4. Failure scenario timeline synthesis (deterministic, seeded)
# ---------------------------------------------------------------------------
TIMELINE_FIELDS: List[str] = [
    "offset_sec", "rssi", "snr", "noise_floor", "phy_rate", "l2_retry_rate", "beacon_loss",
    "roaming_ms", "channel_util", "gw_rtt_ms", "jitter_ms", "tcp_retrans", "tcp_srtt_ms",
    "send_q_bytes", "recv_q_bytes", "cpu_load", "softirq_pct", "hb_delta_sec", "risk_score",
    "conn_state", "is_30s_report_tick", "acs_report_status", "annotation",
    # extras
    "rssi_slope", "phase", "predicted_issue", "early_warning_sent", "pos_x", "pos_y", "velocity",
    "bssid", "piggyback_summary",
]
# NONE = no report expected/arrived this second
ACS_REPORT_STATUSES: List[str] = ["NONE", "OK", "DELAYED", "TIMEOUT_MISSED"]

TIMELINE_START = -89
TIMELINE_END = 30
REPORT_TICK_PHASE = 6           # ticks at offsets ≡ 6 (mod 30): -84, -54, -24, +6
RECOVERY_OFFSET = 18
ICMP_TIMEOUT_MS = 300.0         # GW probe timeout → recorded as 300 ms (loss)
SEND_Q_CAP = 16384              # kernel send buffer saturation in this demo

_PHY_TABLE = [  # (SNR dB, PHY Mbps) — 802.11ac 2SS 40MHz approximate MCS ladder
    (2, 6.0), (6, 6.0), (9, 13.5), (12, 27.0), (15, 54.0), (18, 81.0), (20, 108.0),
    (23, 162.0), (26, 216.0), (29, 243.0), (32, 270.0), (35, 324.0), (38, 360.0), (42, 400.0),
]


def phy_rate_from_snr(snr: float) -> float:
    """Approximate negotiated PHY rate (Mbps) from SNR via an MCS ladder."""
    if snr <= _PHY_TABLE[0][0]:
        return _PHY_TABLE[0][1]
    for (s0, r0), (s1, r1) in zip(_PHY_TABLE, _PHY_TABLE[1:]):
        if snr <= s1:
            return r0 + (r1 - r0) * (snr - s0) / (s1 - s0)
    return _PHY_TABLE[-1][1]


_BASE: Dict[str, float] = {
    "rssi": -58.0, "noise_floor": -95.0, "l2_retry_rate": 3.0, "beacon_loss": 0.0,
    "roaming_ms": 0.0, "channel_util": 28.0, "gw_rtt_ms": 3.5, "jitter_ms": 1.2,
    "tcp_retrans": 0.0, "tcp_srtt_ms": 6.5, "send_q_bytes": 0.0, "recv_q_bytes": 0.0,
    "cpu_load": 42.0, "softirq_pct": 3.0,
}
_NOISE_SIGMA: Dict[str, tuple] = {   # (absolute sigma, relative sigma)
    "rssi": (0.8, 0.0), "noise_floor": (0.6, 0.0), "l2_retry_rate": (0.7, 0.05),
    "channel_util": (1.8, 0.02), "gw_rtt_ms": (0.4, 0.07), "jitter_ms": (0.3, 0.08),
    "tcp_srtt_ms": (0.5, 0.05), "cpu_load": (2.2, 0.0), "softirq_pct": (0.4, 0.04),
    "send_q_bytes": (0.0, 0.04), "recv_q_bytes": (0.0, 0.03),
}
_INT_KEYS = ("beacon_loss", "tcp_retrans", "send_q_bytes", "recv_q_bytes")
_RISK_INPUT_KEYS = ("rssi", "rssi_slope", "snr", "noise_floor", "phy_rate", "l2_retry_rate", "beacon_loss",
                    "channel_util", "tcp_retrans", "gw_rtt_ms", "jitter_ms", "tcp_srtt_ms",
                    "send_q_bytes", "recv_q_bytes", "cpu_load", "roaming_ms")


def _clampv(k: str, v: float) -> float:
    lims = {
        "rssi": (-95, -30), "noise_floor": (-100, -70), "l2_retry_rate": (0, 90), "beacon_loss": (0, 10),
        "roaming_ms": (0, 5000), "channel_util": (0, 100), "gw_rtt_ms": (0.5, ICMP_TIMEOUT_MS),
        "jitter_ms": (0.1, 200), "tcp_retrans": (0, 20), "tcp_srtt_ms": (0.5, 400),
        "send_q_bytes": (0, SEND_Q_CAP), "recv_q_bytes": (0, 20000), "cpu_load": (1, 100),
        "softirq_pct": (0, 60),
    }
    lo, hi = lims.get(k, (-1e9, 1e9))
    return max(lo, min(hi, v))


class _ScenarioCfg:
    def __init__(self, code, seed, onset, lead, base_over, targets, shapes, disc_fn,
                 phy_factor=None, path=None, bssids=("AP-01", "AP-01"), events=None, notes=None):
        self.code = code
        self.seed = seed
        self.onset = onset
        self.lead = lead
        self.base = dict(_BASE, **(base_over or {}))
        self.targets = targets
        self.shapes = shapes
        self.disc_fn = disc_fn
        self.phy_factor = phy_factor or (lambda s: 1.0)
        self.path = path or ((10.0, 10.0), (1.2, 0.0))
        self.bssids = bssids
        self.events = events or {}
        self.notes = notes or {}


def _degrade_values(cfg: _ScenarioCfg, s: float) -> Dict[str, float]:
    out = {}
    for k, b in cfg.base.items():
        tgt = cfg.targets.get(k, b)
        sh = cfg.shapes.get(k, 1.0)
        out[k] = b + (tgt - b) * (max(0.0, s) ** sh)
    return out


def _derive(cfg: _ScenarioCfg, vals: Dict[str, float], s: float) -> Dict[str, float]:
    vals["snr"] = max(1.0, vals["rssi"] - vals["noise_floor"])
    if "phy_rate_override" in vals:
        vals["phy_rate"] = vals.pop("phy_rate_override")
    else:
        vals["phy_rate"] = max(6.0, phy_rate_from_snr(vals["snr"]) * cfg.phy_factor(s))
    return vals


def _envelope(t: float, onset: float, gamma: float) -> float:
    if t < onset:
        return 0.0
    if t >= 0:
        return 1.0
    return ((t - onset) / (0.0 - onset)) ** gamma


def _calibrate_gamma(cfg: _ScenarioCfg, target_risk: float = 49.0) -> float:
    """Bisection on envelope gamma so that noise-free risk at T-lead ≈ target_risk."""
    pre = -cfg.lead

    def risk_at_pre(gamma: float) -> float:
        v_now = _derive(cfg, _degrade_values(cfg, _envelope(pre, cfg.onset, gamma)), 0)
        v_prev = _derive(cfg, _degrade_values(cfg, _envelope(pre - 5, cfg.onset, gamma)), 0)
        v_now["rssi_slope"] = (v_now["rssi"] - v_prev["rssi"]) / 5.0
        return compute_risk_score({k: v_now.get(k) for k in _RISK_INPUT_KEYS})["raw_score"]

    lo, hi = 0.25, 12.0   # small gamma → high risk at pre ; large gamma → low risk
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if risk_at_pre(mid) > target_risk:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _report_ticks() -> List[int]:
    return [t for t in range(TIMELINE_START, TIMELINE_END + 1) if (t - REPORT_TICK_PHASE) % 30 == 0]


def _build_timeline(cfg: _ScenarioCfg) -> Dict[str, Any]:
    rng = random.Random(cfg.seed)
    gamma = _calibrate_gamma(cfg)
    pre = -cfg.lead
    ticks = set(_report_ticks())
    raw_rows: List[Dict[str, float]] = []
    disc_end: Dict[str, float] = {}

    # ---- pass 1: metric values ----
    for t in range(TIMELINE_START, TIMELINE_END + 1):
        if t < 0:
            s = _envelope(t, cfg.onset, gamma)
            v = _degrade_values(cfg, s)
        elif t < RECOVERY_OFFSET:
            s = 1.0
            v = dict(cfg.base)
            v.update(cfg.disc_fn(t, _degrade_values(cfg, 1.0), cfg.base))
            disc_end = dict(v)
        else:
            s = 0.0
            k = t - RECOVERY_OFFSET
            decay = math.exp(-(k + 1) / 1.2)
            v = {}
            for key, b in cfg.base.items():
                e = disc_end.get(key, b)
                v[key] = b + (e - b) * decay
            v["send_q_bytes"] = 0.0 if k >= 1 else min(disc_end.get("send_q_bytes", 0) * 0.08, 900)
            v["recv_q_bytes"] = 0.0 if k >= 1 else min(disc_end.get("recv_q_bytes", 0) * 0.05, 600)
            v["tcp_retrans"] = 0.0
            v["roaming_ms"] = 0.0
            v["beacon_loss"] = 0.0
            v["gw_rtt_ms"] = cfg.base["gw_rtt_ms"] + (min(disc_end.get("gw_rtt_ms", 3.5), 40) - cfg.base["gw_rtt_ms"]) * decay
            v["tcp_srtt_ms"] = cfg.base["tcp_srtt_ms"] + 25.0 * decay
        if t in cfg.events:
            v.update(cfg.events[t])
        # sensor noise
        for key, (a_sig, r_sig) in _NOISE_SIGMA.items():
            if key in v:
                sig = a_sig + r_sig * abs(v[key])
                if key in ("send_q_bytes", "recv_q_bytes") and v[key] <= 0:
                    continue
                v[key] += rng.gauss(0.0, sig)
        for key in list(v.keys()):
            v[key] = _clampv(key, v[key])
        v = _derive(cfg, v, s)
        raw_rows.append(v)

    # ---- pass 2: derived/analysis fields ----
    rows: List[Dict[str, Any]] = []
    last_rx = TIMELINE_START - ((TIMELINE_START - REPORT_TICK_PHASE) % 30) - 30  # previous tick before window
    last_interval = 30.0
    clamp_log: List[tuple] = []
    first_70 = None
    (x0, y0), (vx, vy) = cfg.path
    for i, t in enumerate(range(TIMELINE_START, TIMELINE_END + 1)):
        v = raw_rows[i]
        prev5 = raw_rows[i - 5]["rssi"] if i >= 5 else raw_rows[0]["rssi"]
        slope = (v["rssi"] - prev5) / 5.0 if i >= 5 else 0.0
        risk_in = {k: v.get(k) for k in _RISK_INPUT_KEYS if k != "rssi_slope"}
        risk_in["rssi_slope"] = slope
        r = compute_risk_score(risk_in)
        score = r["risk_score"]
        if t < pre:
            phase = "NORMAL" if t < cfg.onset else "DEGRADING"
            adj = min(score, 44.9)
        elif t < 0:
            phase = "PRE_WARNING"
            adj = max(45.0, min(score, 84.9))
        elif t < RECOVERY_OFFSET:
            phase = "DISCONNECTED"
            adj = max(score, 85.0)
        else:
            phase = "RECOVERED"
            adj = min(score, 44.9)
        if abs(adj - score) > 0.05:
            clamp_log.append((t, score, adj))
        score = round(adj, 1)
        conn_state = _conn_state(score)
        if first_70 is None and score >= RISK_THRESHOLDS["early_warning_push"] and t < 0:
            first_70 = t

        # ACS 30-second report / heartbeat watchdog (legacy view)
        is_tick = False
        status = "NONE"
        if t in ticks and t < 0:
            is_tick, status = True, "OK"
            last_interval = round(30.0 + rng.uniform(-0.15, 0.15), 2)
            last_rx = t
        elif t in ticks and 0 <= t < RECOVERY_OFFSET:
            is_tick, status = True, "TIMEOUT_MISSED"
        elif t == RECOVERY_OFFSET:
            is_tick, status = True, "DELAYED"
            last_interval = float(t - last_rx)
            last_rx = t
        elif t in ticks:
            is_tick, status = True, "OK"
            last_interval = round(30.0 + rng.uniform(-0.15, 0.15), 2)
            last_rx = t
        elapsed = t - last_rx
        hb = float(elapsed) if elapsed > 30.5 else last_interval

        row: Dict[str, Any] = {
            "offset_sec": t,
            "rssi": round(v["rssi"], 1),
            "snr": round(v["snr"], 1),
            "noise_floor": round(v["noise_floor"], 1),
            "phy_rate": round(v["phy_rate"], 1),
            "l2_retry_rate": round(v["l2_retry_rate"], 1),
            "beacon_loss": int(round(v["beacon_loss"])),
            "roaming_ms": round(v["roaming_ms"], 0),
            "channel_util": round(v["channel_util"], 1),
            "gw_rtt_ms": round(v["gw_rtt_ms"], 1),
            "jitter_ms": round(v["jitter_ms"], 1),
            "tcp_retrans": int(round(v["tcp_retrans"])),
            "tcp_srtt_ms": round(v["tcp_srtt_ms"], 1),
            "send_q_bytes": int(round(v["send_q_bytes"])),
            "recv_q_bytes": int(round(v["recv_q_bytes"])),
            "cpu_load": round(v["cpu_load"], 1),
            "softirq_pct": round(v["softirq_pct"], 1),
            "hb_delta_sec": round(hb, 2),
            "risk_score": score,
            "conn_state": conn_state,
            "is_30s_report_tick": is_tick,
            "acs_report_status": status,
            "annotation": "",
            "rssi_slope": round(slope, 2),
            "phase": phase,
            "predicted_issue": r["predicted_issue"] if t < RECOVERY_OFFSET else "정상 — 재연결 완료",
            "early_warning_sent": t == pre,
            "pos_x": round(x0 + vx * (t - TIMELINE_START), 2),
            "pos_y": round(y0 + vy * (t - TIMELINE_START), 2),
            "velocity": round(math.hypot(vx, vy), 2),
            "bssid": cfg.bssids[0] if t < RECOVERY_OFFSET - 3 or cfg.code != "SCN-01" else cfg.bssids[1],
            "piggyback_summary": None,
        }
        rows.append(row)

    # piggyback summaries at successful report ticks (stats of the preceding 30 s)
    prev_tick_idx = 0
    for i, row in enumerate(rows):
        if row["acs_report_status"] in ("OK", "DELAYED"):
            seg = rows[max(0, prev_tick_idx + 1 if prev_tick_idx else max(0, i - 29)): i + 1]
            row["piggyback_summary"] = _piggyback(seg)
            prev_tick_idx = i

    # annotations
    notes = {
        cfg.onset: "품질 저하 시작 — 1초 링버퍼에는 기록되지만 30초 보고에는 드러나지 않음",
        pre: f"사전 감지 경보 (Risk ≥ 45) — 링버퍼 고해상도 스냅샷 잠금, 단절 {cfg.lead}초 전 조기 경보",
        0: "ACS 소켓 단절 — 보고·제어 불가 (TCP 지수 백오프 → 연결 해제)",
        REPORT_TICK_PHASE: "정기 30초 보고 누락 (TIMEOUT_MISSED) — 레거시 관점 최초 이상 인지",
        RECOVERY_OFFSET: f"소켓 재연결 + ±60초 블랙박스 덤프 업로드 → 자동 RCA (레거시는 보고 간격 {RECOVERY_OFFSET - (REPORT_TICK_PHASE - 30)}s 'DELAYED' 1건만 기록)",
    }
    for t in sorted(ticks):
        if t < 0 and t not in notes:
            notes[t] = "정기 30초 상태 보고 (OK) — 레거시 관점 정상"
    if first_70 is not None and first_70 not in notes:
        notes[first_70] = "Risk ≥ 70 — ACS로 조기 경보 패킷 즉시 푸시 (감속/802.11v 로밍 유도 가능 시점)"
    notes.update(cfg.notes)
    for row in rows:
        if row["offset_sec"] in notes:
            row["annotation"] = notes[row["offset_sec"]]

    return {"timeline": rows, "gamma": round(gamma, 3), "clamps": clamp_log, "first_risk70_offset": first_70}


def _piggyback(seg: List[Dict[str, Any]]) -> Dict[str, Any]:
    rs = [r["rssi"] for r in seg]
    avg = sum(rs) / len(rs)
    std = math.sqrt(sum((x - avg) ** 2 for x in rs) / len(rs))
    return {
        "rssi_min": round(min(rs), 1),
        "rssi_avg": round(avg, 1),
        "rssi_std": round(std, 1),
        "snr_min": round(min(r["snr"] for r in seg), 1),
        "l2_retry_max": round(max(r["l2_retry_rate"] for r in seg), 1),
        "tcp_retrans_sum": int(sum(r["tcp_retrans"] for r in seg)),
        "gw_rtt_avg": round(sum(r["gw_rtt_ms"] for r in seg) / len(seg), 1),
        "gw_rtt_max": round(max(r["gw_rtt_ms"] for r in seg), 1),
        "roaming_count": int(sum(1 for r in seg if r["roaming_ms"] > 0)),
        "max_risk_score": round(max(r["risk_score"] for r in seg), 1),
    }


# ---- per-scenario disconnection-phase models (0 <= t < RECOVERY_OFFSET) ----
def _disc_scn01(t: int, worst: Dict[str, float], base: Dict[str, float]) -> Dict[str, float]:
    if t < 15:   # roam failed → disassociated, scanning; socket in RTO backoff
        return {
            "rssi": -83.0, "noise_floor": -95.0, "l2_retry_rate": 48.0, "beacon_loss": 10.0,
            "roaming_ms": 1480.0 if t == 0 else 0.0, "channel_util": 30.0, "gw_rtt_ms": ICMP_TIMEOUT_MS,
            "jitter_ms": 90.0, "tcp_retrans": 6.0, "tcp_srtt_ms": 300.0,
            "send_q_bytes": min(SEND_Q_CAP, worst["send_q_bytes"] + 650.0 * (t + 1)),
            "recv_q_bytes": 0.0, "cpu_load": 44.0, "softirq_pct": 5.0,
        }
    # re-associated to neighbor AP (full 802.1X re-auth); TCP still backing off until +18
    return {
        "rssi": -57.0, "noise_floor": -95.0, "l2_retry_rate": 4.0, "beacon_loss": 0.0,
        "roaming_ms": 310.0 if t == 15 else 0.0, "channel_util": 29.0, "gw_rtt_ms": 4.2,
        "jitter_ms": 2.5, "tcp_retrans": 2.0, "tcp_srtt_ms": 300.0, "send_q_bytes": float(SEND_Q_CAP),
        "recv_q_bytes": 0.0, "cpu_load": 44.0, "softirq_pct": 4.0,
    }


def _disc_scn02(t: int, worst: Dict[str, float], base: Dict[str, float]) -> Dict[str, float]:
    q = max(0.0, min(1.0, (t - 8) / 8.0))        # AGV exits the dead/EMI zone from +8 to +16
    rf = {k: worst[k] + (base[k] - worst[k]) * q for k in ("rssi", "noise_floor", "l2_retry_rate", "channel_util")}
    rf["rssi"] = min(rf["rssi"], -84.0 + 26.0 * q)
    return dict(rf, **{
        "beacon_loss": 9.0 if t < 8 else max(0.0, 9.0 * (1 - q)),
        "roaming_ms": 0.0,
        "gw_rtt_ms": ICMP_TIMEOUT_MS if t < 12 else 8.0,
        "jitter_ms": 95.0 if t < 12 else 6.0,
        "tcp_retrans": 7.0 if t < 12 else 2.0,
        "tcp_srtt_ms": 300.0,
        "send_q_bytes": min(SEND_Q_CAP, worst["send_q_bytes"] + 500.0 * (t + 1)),
        "recv_q_bytes": 0.0, "cpu_load": 46.0, "softirq_pct": 5.0,
    })


def _disc_scn03(t: int, worst: Dict[str, float], base: Dict[str, float]) -> Dict[str, float]:
    q = max(0.0, min(1.0, (t - 11) / 6.0))       # broadcast storm stops / WLC load-balances from +11
    return {
        "rssi": -60.0, "noise_floor": -95.0,
        "channel_util": 95.0 + (40.0 - 95.0) * q,
        "l2_retry_rate": 42.0 + (5.0 - 42.0) * q,
        "beacon_loss": 3.0 if q < 0.5 else 0.0,
        "roaming_ms": 0.0,
        "gw_rtt_ms": ICMP_TIMEOUT_MS if t < 7 else 230.0 + (6.0 - 230.0) * q,
        "jitter_ms": 140.0 + (4.0 - 140.0) * q,
        "tcp_retrans": 6.0 if t < 12 else 3.0,
        "tcp_srtt_ms": 340.0,
        "send_q_bytes": min(SEND_Q_CAP, worst["send_q_bytes"] + 550.0 * (t + 1)),
        "recv_q_bytes": 0.0, "cpu_load": 44.0, "softirq_pct": 6.0,
        "phy_rate_override": 54.0 + (300.0 - 54.0) * q,
    }


def _disc_scn04(t: int, worst: Dict[str, float], base: Dict[str, float]) -> Dict[str, float]:
    cpu = 98.5 if t < 16 else (93.0 if t == 16 else 88.0)
    return {
        "rssi": -57.0, "noise_floor": -95.0, "l2_retry_rate": 3.5, "beacon_loss": 0.0, "roaming_ms": 0.0,
        "channel_util": 29.0, "gw_rtt_ms": 6.8, "jitter_ms": 4.5, "tcp_retrans": 0.0,
        "tcp_srtt_ms": 220.0 + 6.0 * t, "send_q_bytes": 1400.0,
        "recv_q_bytes": 16384.0 + 120.0 * t,          # zero-window: kernel buffer full, app never reads
        "cpu_load": cpu, "softirq_pct": 30.0 if t < 16 else 18.0,
    }


_SCENARIO_CFGS: Dict[str, _ScenarioCfg] = {
    "SCN-01": _ScenarioCfg(
        code="SCN-01", seed=101, onset=-55, lead=18,
        base_over={"rssi": -58.0},
        targets={"rssi": -80.0, "l2_retry_rate": 30.0, "beacon_loss": 8.0, "gw_rtt_ms": 70.0, "jitter_ms": 38.0,
                 "tcp_retrans": 5.0, "tcp_srtt_ms": 210.0, "send_q_bytes": 9200.0, "channel_util": 30.0,
                 "cpu_load": 44.0, "softirq_pct": 5.0},
        shapes={"rssi": 0.85, "l2_retry_rate": 1.3, "beacon_loss": 1.6, "gw_rtt_ms": 1.7, "jitter_ms": 1.4,
                "tcp_retrans": 1.7, "tcp_srtt_ms": 1.8, "send_q_bytes": 2.0},
        disc_fn=_disc_scn01,
        path=((52.0, 14.0), (0.55, 0.0)),            # ZONE-A → ZONE-B corridor, AP-01 → AP-02 boundary
        bssids=("AP-01 (a4:5e:60:11:01:0a)", "AP-02 (a4:5e:60:11:02:0b)"),
        events={-3: {"roaming_ms": 0.0}},
        notes={-6: "RSSI -76dBm 도달에도 BSSID 미변경 (로밍 임계 -80dBm, Sticky Client)",
               -2: "뒤늦은 로밍 시도 시작 (SME: Trying to authenticate → AP-02, 802.11r 미적용)",
               15: "인접 AP-02 재연결 완료 (802.1X 전체 재인증 310ms) — TCP 재전송 백오프로 소켓 복구는 +18s"},
    ),
    "SCN-02": _ScenarioCfg(
        code="SCN-02", seed=202, onset=-34, lead=16,
        base_over={"rssi": -60.0},
        targets={"rssi": -83.0, "noise_floor": -87.0, "l2_retry_rate": 55.0, "beacon_loss": 7.0,
                 "channel_util": 50.0, "gw_rtt_ms": 130.0, "jitter_ms": 60.0, "tcp_retrans": 7.0,
                 "tcp_srtt_ms": 280.0, "send_q_bytes": 11000.0, "cpu_load": 46.0, "softirq_pct": 5.0},
        shapes={"rssi": 1.3, "noise_floor": 0.9, "l2_retry_rate": 1.2, "beacon_loss": 1.5, "gw_rtt_ms": 1.6,
                "jitter_ms": 1.4, "tcp_retrans": 1.6, "tcp_srtt_ms": 1.7, "send_q_bytes": 1.9},
        disc_fn=_disc_scn02,
        path=((18.0, 40.0), (0.9, 0.12)),            # ZONE-C press/welding line between steel racks
        bssids=("AP-03 (a4:5e:60:11:03:0c)", "AP-03 (a4:5e:60:11:03:0c)"),
        notes={-10: "용접 로봇 셀 가동 + 철제 랙 차폐 구간 진입 — Noise Floor 상승·RSSI 급락 동시 발생",
               -5: "PHY Rate 최저 MCS(6~13Mbps) 강등, L2 재전송률 40% 돌파 — 로밍 대상 AP 없음",
               12: "음영/간섭 구역 이탈 — RF 지표 회복 시작, TCP는 백오프 대기 중"},
    ),
    "SCN-03": _ScenarioCfg(
        code="SCN-03", seed=303, onset=-46, lead=15,
        base_over={"rssi": -60.0, "channel_util": 34.0},
        targets={"rssi": -60.0, "channel_util": 93.0, "l2_retry_rate": 38.0, "beacon_loss": 3.0,
                 "gw_rtt_ms": 185.0, "jitter_ms": 115.0, "tcp_retrans": 6.0, "tcp_srtt_ms": 320.0,
                 "send_q_bytes": 10500.0, "softirq_pct": 6.0, "cpu_load": 44.0},
        shapes={"channel_util": 0.8, "l2_retry_rate": 1.1, "beacon_loss": 1.5, "gw_rtt_ms": 1.5,
                "jitter_ms": 1.3, "tcp_retrans": 1.6, "tcp_srtt_ms": 1.6, "send_q_bytes": 1.9},
        disc_fn=_disc_scn03,
        phy_factor=lambda s: 1.0 - 0.55 * (s ** 1.2),  # Minstrel rate fallback on collisions
        path=((24.0, 12.0), (0.35, 0.05)),           # ZONE-A shipping dock, AP-01 shared with 40+ handhelds
        bssids=("AP-01 (a4:5e:60:11:01:0a)", "AP-01 (a4:5e:60:11:01:0a)"),
        notes={-30: "출하 도크 교대 시간 — 핸디 스캐너 40여 대 동시 접속 + 동일 채널(CH 36) 인접 AP 중첩",
               -8: "RSSI -60dBm·SNR 35dB 양호에도 채널 점유율 85% 초과, RTT·지터 100ms 돌파",
               11: "WLC 로드밸런싱/브로드캐스트 폭주 종료 — 점유율 하락 시작"},
    ),
    "SCN-04": _ScenarioCfg(
        code="SCN-04", seed=404, onset=-40, lead=14,
        base_over={"rssi": -57.0, "cpu_load": 45.0},
        targets={"cpu_load": 98.0, "softirq_pct": 28.0, "recv_q_bytes": 16384.0, "send_q_bytes": 1400.0,
                 "tcp_srtt_ms": 190.0, "gw_rtt_ms": 6.5, "jitter_ms": 4.0, "tcp_retrans": 0.0,
                 "l2_retry_rate": 3.5, "channel_util": 29.0},
        shapes={"cpu_load": 0.7, "softirq_pct": 0.9, "recv_q_bytes": 2.0, "send_q_bytes": 2.5,
                "tcp_srtt_ms": 1.6, "gw_rtt_ms": 1.5, "jitter_ms": 1.5},
        disc_fn=_disc_scn04,
        path=((78.0, 46.0), (0.25, 0.0)),            # ZONE-D complex SLAM area (dense pallets), slow
        bssids=("AP-04 (a4:5e:60:11:04:0d)", "AP-04 (a4:5e:60:11:04:0d)"),
        notes={-30: "SLAM 루프 클로저 + 라이다 포인트클라우드 폭주 — CPU 사용률 급상승 시작",
               -8: "CPU 95% 초과, NET_RX SoftIRQ 기아 — Recv-Q 적체 (무선 RSSI -57dBm·GW RTT 5ms 정상)",
               17: "systemd 워치독이 보고 프로세스 재기동 (Recv-Q 해소)"},
    ),
}

_SCENARIO_TEXT: Dict[str, Dict[str, Any]] = {
    "SCN-01": {
        "title": "AP 로밍 실패 / Sticky Client",
        "subtitle": "AP 경계 구간에서 기존 AP를 놓지 않다가 뒤늦은 로밍(802.1X 전체 재인증)으로 소켓 단절",
        "target_agv": "AGV-02",
        "zone": "ZONE-A → ZONE-B 경계 통로 (AP-ZONE-A ↔ AP-ZONE-B 핸드오버 구간)",
        "legacy_30s_view": (
            "ACS는 T-24s 정기 보고를 '정상(OK)'으로 수신했습니다(피기백 없는 레거시 보고에는 위치·배터리·작업 상태만 존재). "
            "이후 T+6s 예정 보고가 누락되어 처음으로 이상을 인지하지만, 45초 워치독 단절 판정(T+21s) 이전인 T+18s에 소켓이 재연결되어 "
            "'보고 간격 42초 지연(DELAYED)' 1건만 남습니다. 단절 직전 RSSI 하락·비콘 손실·1.5초 로밍 지연은 30초 스냅샷 사이에서 발생해 "
            "기록이 전혀 없으므로 원인은 '일시적 네트워크 불량'으로 종결되고 동일 지점에서 재발합니다."
        ),
        "hybrid_1s_view": (
            "1초 링버퍼는 T-55s부터 RSSI가 -58 → -80dBm으로 완만히 하락하는데도 BSSID가 바뀌지 않는 Sticky 패턴을 기록합니다. "
            "T-18s에 L2 재전송·비콘 손실·TCP 재전송·Send-Q가 동시 상승하며 위험 점수가 45를 넘어 사전 감지 경보가 발생하고(링버퍼 잠금), "
            "Risk ≥ 70 시점에 ACS로 조기 경보가 푸시되어 802.11v BSS Transition 요청·감속 지시가 가능합니다. "
            "재연결 직후 ±60초 블랙박스 덤프로 '로밍 1,480ms + 비콘 손실 10/s + 잡음·점유율 정상' 시그니처가 자동 판정됩니다."
        ),
        "root_cause": (
            "AGV 무선 드라이버의 로밍 트리거 임계값이 -80dBm으로 너무 낮게 설정되어, 인접 AP-ZONE-B 신호(-57dBm)가 훨씬 강한데도 "
            "약해진 AP-ZONE-A(-76 ~ -80dBm)에 고착(Sticky Client)되었습니다. 비콘 연속 손실로 링크가 붕괴 직전에서야 로밍을 시작했고, "
            "WLC에 802.11r(FT)·OKC가 적용되지 않아 802.1X/EAP 전체 재인증에 1.48초가 소요되었습니다. 그 사이 TCP 세그먼트가 연속 유실되어 "
            "RTO 지수 백오프(200→400→800ms…)에 진입했고 ACS 소켓이 단절되었으며, 무선 재연결(+15s) 후에도 백오프 대기로 소켓 복구는 +18s에 이루어졌습니다."
        ),
    },
    "SCN-02": {
        "title": "물리적 음영지역 및 전자기 간섭 (Dead Zone / EMI)",
        "subtitle": "용접 셀·철제 랙 구간 진입 시 RSSI 급락과 Noise Floor 상승이 겹쳐 RF 링크 자체가 붕괴",
        "target_agv": "AGV-05",
        "zone": "ZONE-C 프레스·용접 라인 (철제 랙 차폐 + 아크 용접 EMI 구역, AP-ZONE-C 셀 가장자리)",
        "legacy_30s_view": (
            "T-24s 정기 보고 시점에는 AGV가 아직 음영 구역 밖이라 '정상(OK)'으로 기록됩니다. 구역 진입 후 약 20초 만에 링크가 붕괴했으나 "
            "30초 보고에는 그 과정이 전혀 담기지 않고, T+6s 보고 누락과 T+18s 재연결 '지연 보고(42s)'만 남습니다. "
            "같은 증상이 SCN-01(로밍 실패)·SCN-03(혼잡)과 구분되지 않아 AP 추가·설정 변경 등 엉뚱한 조치가 반복됩니다."
        ),
        "hybrid_1s_view": (
            "1초 링버퍼가 RSSI의 급격한 하락 기울기(≤ -2.5dBm/s)와 Noise Floor 동반 상승(SNR 붕괴), PHY Rate 6Mbps 강등, L2 재전송 50%대 폭증을 "
            "좌표(M18)와 함께 기록합니다. T-16s에 위험 점수 45를 넘어 사전 감지 경보가 발생하며, 위치 기반 히트맵으로 동일 좌표 반복 단절이 확인됩니다. "
            "로밍 이벤트가 없다는 점(동일 AP 유지)이 SCN-01과의 결정적 차이로 자동 판정됩니다."
        ),
        "root_cause": (
            "ZONE-C의 3단 철제 랙 사이 통로는 AP-ZONE-C의 커버리지 가장자리이며 금속 차폐로 신호가 -83dBm까지 감쇠합니다. 동시에 인접 아크 용접 로봇 셀이 "
            "가동되면서 광대역 잡음이 유입되어 Noise Floor가 -95 → -87dBm으로 상승, SNR이 5dB 이하로 붕괴했습니다. "
            "칩셋은 최저 MCS(6Mbps)까지 강등했지만 프레임 손실을 막지 못했고(L2 재전송 > 50%), 로밍 가능한 대체 AP가 없어 "
            "링크가 물리적으로 끊긴 상태로 TCP 재전송 타임아웃이 발생했습니다."
        ),
    },
    "SCN-03": {
        "title": "AP 과부하 및 동일 채널 혼잡 (Channel Contention)",
        "subtitle": "RSSI·SNR은 양호하지만 채널 점유율 90% 초과로 전송 기회를 얻지 못해 소켓 타임아웃",
        "target_agv": "AGV-03",
        "zone": "ZONE-B 출하 도크 (AP-ZONE-B, 핸디 스캐너 40여 대 + 동일 채널 인접 AP 중첩)",
        "legacy_30s_view": (
            "레거시 보고는 RSSI만 보면 -60dBm으로 '신호 양호'이므로, 단절 원인을 무선으로 의심조차 하지 않습니다. "
            "T-24s 보고는 정상(OK)이었고 T+6s 누락·T+18s 지연 보고만 남아 ACS 서버나 AGV 소프트웨어 문제로 오인되어 "
            "엉뚱한 부서로 이관됩니다. 교대 시간대마다 반복되는 패턴은 30초 스냅샷으로는 상관 분석이 불가능합니다."
        ),
        "hybrid_1s_view": (
            "1초 링버퍼에는 RSSI(-60dBm)·SNR(35dB)이 양호한 가운데 채널 점유율이 34% → 93%로 상승하고, L2 재전송·GW RTT·지터가 "
            "동반 급증하는 '신호는 좋은데 통신은 안 되는' 시그니처가 기록됩니다. T-15s 사전 감지 경보 후 ACS는 해당 AGV를 혼잡이 덜한 AP로 "
            "유도(802.11v)할 수 있으며, 사후 분석에서 GW RTT 급증으로 무선 구간 책임이 명확히 분리됩니다."
        ),
        "root_cause": (
            "출하 도크 교대 시간에 핸디 스캐너·태블릿 40여 대가 AP-ZONE-B에 동시 접속하고, 동일 채널(CH 40, 80MHz)을 쓰는 인접 AP가 "
            "중첩되어 CCA Busy가 93%에 달했습니다. CSMA/CA 백오프 경합으로 전송 기회를 얻지 못한 AGV 프레임은 충돌·재시도가 누적되어 "
            "(L2 재전송 38%, Minstrel 속도 강등) GW RTT가 185ms, 지터가 115ms까지 치솟았고, TCP 재전송이 연속 발생해 소켓 Write Timeout으로 단절되었습니다. "
            "신호 세기 문제가 아니므로 AP 증설이 아닌 부하 분산·채널 재설계가 필요합니다."
        ),
    },
    "SCN-04": {
        "title": "AGV/ACS 소켓 블로킹 및 시스템 병목 (Socket Hang)",
        "subtitle": "무선은 완벽하지만 SLAM 연산 폭주로 CPU 포화 → 보고 스레드 기아 → Recv-Q 적체 → 보고 타임아웃",
        "target_agv": "AGV-04",
        "zone": "ZONE-D 고밀도 팔레트 적치 구역 (AP-ZONE-D 셀 중심부, 복잡 SLAM 환경)",
        "legacy_30s_view": (
            "레거시 관점에서는 SCN-01~03과 완전히 동일하게 'T+6s 보고 누락 → T+18s 지연 보고'로만 보이므로, 현장은 이를 무선 장애로 판단하여 "
            "AP 추가 설치·채널 변경 등 불필요한 무선 공사를 진행합니다. 실제로는 AGV 내부 문제이므로 무선 투자 후에도 장애가 그대로 재발합니다."
        ),
        "hybrid_1s_view": (
            "1초 링버퍼는 RSSI -57dBm·SNR 38dB·GW RTT 5ms로 무선 구간이 완벽히 정상인 동안 CPU가 45% → 98%로 포화되고 "
            "NET_RX SoftIRQ 비중 증가·소켓 Recv-Q 적체·TCP srtt 증가(지연 ACK)가 진행되는 것을 기록합니다. T-14s 사전 감지 경보가 발생하며, "
            "사후 분석은 '무선 정상 + Recv-Q > 2KB + CPU > 92%' 시그니처로 네트워크가 아닌 애플리케이션/OS 병목으로 즉시 판정해 무선 공사를 막습니다."
        ),
        "root_cause": (
            "고밀도 팔레트 구역에서 SLAM 루프 클로저와 라이다 포인트클라우드 정합 연산이 폭주해 4코어 IPC의 CPU 사용률이 98%에 도달했습니다. "
            "네트워크 보고 스레드가 SLAM 스레드와 동일 코어·동일 우선순위로 스케줄링되어 기아(Starvation) 상태에 빠졌고, recv()를 호출하지 못해 "
            "ACS 명령 패킷이 소켓 Recv-Q에 16KB 이상 적체(Zero Window)되었습니다. 블로킹 소켓 구조로 송신 경로까지 정지하면서 30초 보고가 타임아웃되었고, "
            "systemd 워치독이 보고 프로세스를 재기동한 +18s에야 복구되었습니다."
        ),
    },
}


def _signature_strings(code: str, st: Dict[str, Any]) -> List[str]:
    g = lambda k: st.get(k) if st.get(k) is not None else 0  # noqa: E731
    if code == "SCN-01":
        return [
            f"RSSI 완만 하락: {g('rssi_max'):.0f} → {g('rssi_min'):.0f} dBm (BSSID 미변경, 로밍 임계 미도달)",
            f"로밍 지연: 최대 {g('roaming_max_ms'):.0f} ms (> 200 ms, 802.11r 미적용 전체 재인증)",
            f"비콘 손실: 최대 {g('beacon_loss_max'):.0f} /s (≥ 5 /s → L2 연결 해제 임박)",
            f"Noise Floor 최대 {g('noise_max'):.0f} dBm · 채널 점유율 최대 {g('channel_util_max'):.0f}% (간섭·혼잡 배제)",
            f"TCP 재전송 최대 {g('tcp_retrans_max'):.0f}/s · Send-Q 최대 {g('send_q_max'):.0f} Bytes (RTO 지수 백오프)",
        ]
    if code == "SCN-02":
        return [
            f"RSSI 급락: 최저 {g('rssi_min'):.0f} dBm, 최대 하락 기울기 {g('rssi_steepest_slope'):.1f} dBm/s",
            f"Noise Floor 상승: 최대 {g('noise_max'):.0f} dBm → SNR 최저 {g('snr_min'):.0f} dB (EMI)",
            f"PHY Rate 최저 {g('phy_min'):.0f} Mbps (최저 MCS 강등) · L2 재전송 최대 {g('l2_retry_max'):.0f}%",
            f"로밍 이벤트 없음 (최대 {g('roaming_max_ms'):.0f} ms) — 대체 AP 부재, 동일 AP 링크 붕괴",
            f"TCP 재전송 최대 {g('tcp_retrans_max'):.0f}/s · GW RTT 타임아웃({ICMP_TIMEOUT_MS:.0f} ms)",
        ]
    if code == "SCN-03":
        return [
            f"RSSI 최저 {g('rssi_min'):.0f} dBm · SNR 최저 {g('snr_min'):.0f} dB — 신호 양호 유지",
            f"채널 점유율(CCA Busy) 최대 {g('channel_util_max'):.0f}% (> 75%)",
            f"GW RTT 최대 {g('gw_rtt_max'):.0f} ms · 지터 최대 {g('jitter_max'):.0f} ms (무선 구간 큐잉·경합)",
            f"L2 재전송 최대 {g('l2_retry_max'):.0f}% · TCP 재전송 최대 {g('tcp_retrans_max'):.0f}/s",
            f"Send-Q 최대 {g('send_q_max'):.0f} Bytes — ACK 지연으로 송신 버퍼 적체",
        ]
    return [
        f"RSSI 최저 {g('rssi_min'):.0f} dBm · SNR 최저 {g('snr_min'):.0f} dB — 무선 정상",
        f"GW ICMP RTT 최대 {g('gw_rtt_max'):.1f} ms — 무선 구간 정상 (< 15 ms)",
        f"AGV CPU 최대 {g('cpu_max'):.0f}% (> 92%) · NET_RX SoftIRQ 기아",
        f"소켓 Recv-Q 최대 {g('recv_q_max'):.0f} Bytes (> 2KB, Zero Window) — 애플리케이션 미수신",
        f"TCP 재전송 최대 {g('tcp_retrans_max'):.0f}/s (손실 없음) · srtt 최대 {g('tcp_srtt_max'):.0f} ms (지연 ACK)",
    ]


def _build_scenarios() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for code, cfg in _SCENARIO_CFGS.items():
        built = _build_timeline(cfg)
        tl = built["timeline"]
        # RCA window: blackbox dump ±60 s around disconnection (here -60..+17)
        window = [p for p in tl if -60 <= p["offset_sec"] < RECOVERY_OFFSET]
        rca = classify_rca(window)
        st = rca["stats"]
        text = _SCENARIO_TEXT[code]
        out[code] = {
            "code": code,
            "title": text["title"],
            "subtitle": text["subtitle"],
            "target_agv": text["target_agv"],
            "zone": text["zone"],
            "severity": "CRITICAL",
            "lead_time_sec": cfg.lead,
            "pre_detect_offset_sec": -cfg.lead,
            "early_warning_push_offset_sec": built["first_risk70_offset"],
            "disconnect_offset_sec": 0,
            "recovery_offset_sec": RECOVERY_OFFSET,
            "degradation_onset_offset_sec": cfg.onset,
            "legacy_first_notice_offset_sec": REPORT_TICK_PHASE,
            "legacy_watchdog_declare_offset_sec": (REPORT_TICK_PHASE - 30) + 45,
            "outage_duration_sec": RECOVERY_OFFSET,
            "legacy_30s_view": text["legacy_30s_view"],
            "hybrid_1s_view": text["hybrid_1s_view"],
            "root_cause": text["root_cause"],
            "signature_metrics": _signature_strings(code, st),
            "decision_tree": rca["decision_tree"],
            "recommended_actions": _SCENARIO_ACTIONS[code],
            "rca_result": {k: rca[k] for k in ("scenario_code", "title", "confidence", "scores", "evidence",
                                               "root_cause_summary")},
            "report_ticks": [p["offset_sec"] for p in tl if p["is_30s_report_tick"]],
            "timeline": tl,
        }
    return out


FAILURE_SCENARIOS: Dict[str, Dict[str, Any]] = _build_scenarios()


# ---------------------------------------------------------------------------
# 5. Hybrid telemetry architecture specification
# ---------------------------------------------------------------------------
_PIGGYBACK_FIELDS: List[Dict[str, Any]] = [
    # key, source metric, JSON example, binary type, bytes, scale, description
    {"key": "rs", "metric": "M01 rssi", "agg": "[min, avg, std]", "bin_type": "int8,int16,uint8", "bytes": 4,
     "scale": "avg·std ×10", "desc": "30초간 RSSI 최소/평균/표준편차 (변동성 = 이동 중 음영 통과 흔적)"},
    {"key": "sn", "metric": "M02 snr", "agg": "min", "bin_type": "uint8", "bytes": 1, "scale": "1 dB",
     "desc": "30초간 SNR 최소값"},
    {"key": "nf", "metric": "M03 noise_floor", "agg": "max", "bin_type": "int8", "bytes": 1, "scale": "1 dBm",
     "desc": "30초간 Noise Floor 최대값 (EMI 흔적)"},
    {"key": "ph", "metric": "M04 phy_rate", "agg": "min", "bin_type": "uint16", "bytes": 2, "scale": "1 Mbps",
     "desc": "30초간 최저 PHY Rate"},
    {"key": "l2", "metric": "M05 l2_retry_rate", "agg": "max", "bin_type": "uint8", "bytes": 1, "scale": "0.5 %",
     "desc": "30초간 L2 재전송률 최대값"},
    {"key": "bl", "metric": "M06 beacon_loss", "agg": "sum", "bin_type": "uint8", "bytes": 1, "scale": "1",
     "desc": "30초간 비콘 손실 합계"},
    {"key": "ro", "metric": "M07 roaming_ms", "agg": "[count, max_ms]", "bin_type": "uint8,uint16", "bytes": 3,
     "scale": "1 ms", "desc": "30초간 로밍 횟수 및 최대 핸드오버 시간"},
    {"key": "cu", "metric": "M08 channel_util", "agg": "max", "bin_type": "uint8", "bytes": 1, "scale": "1 %",
     "desc": "30초간 채널 점유율 최대값"},
    {"key": "rt", "metric": "M09 gw_rtt_ms", "agg": "[avg, max]", "bin_type": "uint16,uint16", "bytes": 4,
     "scale": "×10", "desc": "게이트웨이 RTT 평균/최대"},
    {"key": "jt", "metric": "M10 jitter_ms", "agg": "max", "bin_type": "uint16", "bytes": 2, "scale": "×10",
     "desc": "지터 최대값"},
    {"key": "tx", "metric": "M11 tcp_retrans", "agg": "delta", "bin_type": "uint16", "bytes": 2, "scale": "1",
     "desc": "30초간 TCP 재전송 증분"},
    {"key": "sr", "metric": "M12 tcp_srtt_ms", "agg": "max", "bin_type": "uint16", "bytes": 2, "scale": "×10",
     "desc": "TCP srtt 최대값"},
    {"key": "sq", "metric": "M13 send_q_bytes", "agg": "max", "bin_type": "uint16", "bytes": 2, "scale": "1 B (sat. 65535)",
     "desc": "Send-Q 최대값"},
    {"key": "rq", "metric": "M14 recv_q_bytes", "agg": "max", "bin_type": "uint16", "bytes": 2, "scale": "1 B (sat. 65535)",
     "desc": "Recv-Q 최대값"},
    {"key": "cp", "metric": "M17 cpu_load", "agg": "max", "bin_type": "uint8", "bytes": 1, "scale": "1 %",
     "desc": "CPU 사용률 최대값"},
    {"key": "rk", "metric": "risk_score", "agg": "max", "bin_type": "uint8", "bytes": 1, "scale": "1 pt",
     "desc": "30초간 최대 위험 점수"},
]
_PB_STRUCT = "<BB" + "bhB" + "B" + "b" + "H" + "B" + "B" + "BH" + "B" + "HH" + "H" + "H" + "H" + "H" + "H" + "B" + "B"
_PB_BINARY_BYTES = struct.calcsize(_PB_STRUCT)   # incl. 2-byte header (version, flags)


def _example_piggyback() -> Dict[str, Any]:
    tl = FAILURE_SCENARIOS["SCN-01"]["timeline"]
    seg = [p for p in tl if -53 <= p["offset_sec"] <= -24]
    rs = [p["rssi"] for p in seg]
    avg = sum(rs) / len(rs)
    std = math.sqrt(sum((x - avg) ** 2 for x in rs) / len(rs))
    return {
        "rs": [round(min(rs)), round(avg, 1), round(std, 1)],
        "sn": round(min(p["snr"] for p in seg)),
        "nf": round(max(p["noise_floor"] for p in seg)),
        "ph": round(min(p["phy_rate"] for p in seg)),
        "l2": round(max(p["l2_retry_rate"] for p in seg), 1),
        "bl": sum(p["beacon_loss"] for p in seg),
        "ro": [sum(1 for p in seg if p["roaming_ms"] > 0), round(max(p["roaming_ms"] for p in seg))],
        "cu": round(max(p["channel_util"] for p in seg)),
        "rt": [round(sum(p["gw_rtt_ms"] for p in seg) / len(seg), 1), round(max(p["gw_rtt_ms"] for p in seg), 1)],
        "jt": round(max(p["jitter_ms"] for p in seg), 1),
        "tx": sum(p["tcp_retrans"] for p in seg),
        "sr": round(max(p["tcp_srtt_ms"] for p in seg), 1),
        "sq": max(p["send_q_bytes"] for p in seg),
        "rq": max(p["recv_q_bytes"] for p in seg),
        "cp": round(max(p["cpu_load"] for p in seg)),
        "rk": round(max(p["risk_score"] for p in seg)),
    }


def _build_hybrid_spec() -> Dict[str, Any]:
    pb = _example_piggyback()
    pb_json = json.dumps({"pb": pb}, separators=(",", ":"), ensure_ascii=False)
    pb_json_bytes = len(pb_json.encode("utf-8"))
    legacy_report = {"agv": "AGV-03", "seq": 18421, "ts": 1763180040, "x": 61.4, "y": 14.0, "bat": 78,
                     "state": "MOVING", "task": "T-55821"}
    legacy_bytes = len(json.dumps(legacy_report, separators=(",", ":")).encode("utf-8"))
    hybrid_report = dict(legacy_report, pb=pb)
    hybrid_json = json.dumps(hybrid_report, separators=(",", ":"), ensure_ascii=False)

    ring_seconds = 300
    ring_fields = 24
    ring_bytes = ring_seconds * (ring_fields * 4 + 8)   # float32 per field + int64 timestamp
    dump_seconds = 121                                 # ±60 s around disconnection
    dump_raw = dump_seconds * (ring_fields * 4 + 8)
    dump_compressed = int(dump_raw * 0.38)              # zlib on slowly-varying float series ≈ 35~40%
    ew_packet = {"type": "EARLY_WARNING", "agv": "AGV-03", "ts": 1763180071, "risk": 72.4,
                 "dom": "rf_signal", "issue": "STICKY_CLIENT", "rssi": -73.2, "slope": -1.1,
                 "l2": 18.5, "tx": 2, "sq": 2920, "bssid": "a4:5e:60:11:01:0a", "x": 77.5, "y": 14.0}
    ew_bytes = len(json.dumps(ew_packet, separators=(",", ":")).encode("utf-8"))
    icmp_bps = (64 + 64) / 2.0      # 64 B request + 64 B reply every 2 s
    piggyback_bps = pb_json_bytes / 30.0

    return {
        "title": "3단계 하이브리드 텔레메트리 아키텍처 (Hybrid Telemetry Model)",
        "summary": (
            "AGV 로컬에서 1초 고주파 수집(링버퍼, 무선 전송 0) → 평시 30초 보고에 통계 요약 피기백(+~"
            f"{pb_json_bytes}B) → 위험 시 조기 경보 즉시 푸시 + 재연결 후 ±60초 블랙박스 덤프. "
            "기존 30초 소켓 보고 구조와 프로토콜을 그대로 유지하면서 사전 감지(평균 15.75초 선행)와 사후 원인 자동 판별을 동시에 달성합니다."
        ),
        "problem_statement": [
            "무선 품질 붕괴(RSSI 급락·재전송 폭증)는 3~15초 사이에 진행되어 30초 스냅샷 사이에 숨어버림 → 사전 감지 불가",
            "단절 후 남는 데이터는 30초 전 '정상' 보고뿐 → 로밍 실패·음영·혼잡·소켓 행 4대 원인 구분 불가 (블랙박스 현상)",
            "ACS는 45초 워치독으로만 단절을 판정 → 18초 내 자가 복구된 단절은 '지연 보고' 1건으로만 남아 통계에서 누락",
        ],
        "stages": [
            {
                "stage": 1,
                "name": "Stage 1 — AGV 로컬 경량 고주파 수집 (1s Ring Buffer)",
                "location": "AGV/AMR 온보드 에이전트",
                "interval": "1s (M03·M08·M17은 5s, M09·M10은 2s, M07·M16은 이벤트)",
                "data_source": "/proc/net/wireless, nl80211(iw), TCP_INFO/ss -ti, ioctl(SIOCINQ/SIOCOUTQ), /proc/stat, ROS pose",
                "buffer": {
                    "type": "고정 크기 순환 버퍼 (Ring Buffer, 메모리 상주)",
                    "retention_sec": ring_seconds,
                    "fields_per_sample": ring_fields,
                    "bytes_per_sample": ring_fields * 4 + 8,
                    "total_bytes": ring_bytes,
                    "total_kb": round(ring_bytes / 1024, 1),
                    "note": f"float32 × {ring_fields} 필드 + int64 타임스탬프 = {ring_fields * 4 + 8} B/샘플 × {ring_seconds}초 = 약 {round(ring_bytes / 1024, 1)} KB (< 150 KB 목표)",
                },
                "network_overhead": "0 B/s (무선 전송 없음, 단 M09 ICMP 프로브 약 64 B/s)",
                "cpu_overhead": "< 0.5% (1초당 커널 조회 약 6회, 각 수십 μs)",
                "local_logic": [
                    "매 1초 compute_risk_score() 실행 (RSSI 5초 기울기 + 4개 컴포넌트 융합)",
                    "Risk ≥ 45: 링버퍼 스냅샷 잠금(Lock) — 단절 전후 데이터 덮어쓰기 방지",
                    "Risk ≥ 70: Stage 3 조기 경보 즉시 송신",
                ],
            },
            {
                "stage": 2,
                "name": "Stage 2 — 평시 30초 상태 보고 통계 피기백 (Statistical Piggyback)",
                "location": "AGV → ACS (기존 30초 보고 소켓 재사용)",
                "interval": "30s (기존 보고 주기 유지, 프로토콜 하위 호환: 미지원 ACS는 'pb' 필드 무시)",
                "packet_schema": {
                    "container_field": "pb",
                    "fields": _PIGGYBACK_FIELDS,
                    "example_json": pb,
                    "example_full_report": hybrid_report,
                },
                "byte_size": {
                    "legacy_report_bytes": legacy_bytes,
                    "piggyback_json_bytes": pb_json_bytes,
                    "piggyback_binary_bytes": _PB_BINARY_BYTES,
                    "binary_struct_format": _PB_STRUCT,
                    "hybrid_report_bytes": len(hybrid_json.encode("utf-8")),
                    "overhead_bps_json": round(piggyback_bps, 2),
                    "overhead_bps_binary": round(_PB_BINARY_BYTES / 30.0, 2),
                    "calculation": (
                        f"압축 JSON 피기백 {pb_json_bytes} B ÷ 30 s = {piggyback_bps:.1f} B/s/AGV "
                        f"(바이너리 패킹 시 {_PB_BINARY_BYTES} B ÷ 30 s = {_PB_BINARY_BYTES / 30.0:.2f} B/s). "
                        f"AGV 100대 기준 JSON {piggyback_bps * 100 / 1024:.2f} KB/s — 무선 채널 용량(수백 Mbps) 대비 무시 가능"
                    ),
                },
                "acs_storage": "acs_reports_30s.piggyback_summary_json (TSDB) — 30초 해상도 장기 추세·히트맵 롤업",
            },
            {
                "stage": 3,
                "name": "Stage 3 — 조기 경보 푸시(Early Warning) & 재연결 후 블랙박스 덤프(Post-mortem Dump)",
                "location": "AGV → ACS (이벤트 기반)",
                "early_warning": {
                    "trigger": "로컬 Risk Score ≥ 70 (최초 1회 + 10초 쿨다운, 상위 컴포넌트 변경 시 재송신)",
                    "packet_example": ew_packet,
                    "packet_bytes": ew_bytes,
                    "acs_actions": [
                        "해당 AGV 안전 감속 또는 위험 구간 진입 전 대기 지시",
                        "802.11v BSS Transition Management 요청으로 인접 AP 강제 로밍 유도",
                        "관제 화면 Amber 경보 + 사전 감지 이벤트(incident_events) 기록",
                    ],
                    "lead_time_sec": {code: s["lead_time_sec"] for code, s in FAILURE_SCENARIOS.items()},
                    "lead_time_avg_sec": round(sum(s["lead_time_sec"] for s in FAILURE_SCENARIOS.values()) / 4.0, 2),
                },
                "blackbox_dump": {
                    "trigger": "소켓 재연결 직후 (M16 reconnect 이벤트) 또는 ACS 요청 시",
                    "window": "단절 시점 기준 ±60초, 1초 해상도",
                    "samples": dump_seconds,
                    "raw_bytes": dump_raw,
                    "compressed_bytes": dump_compressed,
                    "compression": "zlib (deflate) — 완만히 변하는 float 시계열 압축률 약 35~40%",
                    "transfer": "재연결 후 저우선순위 청크(1KB) 분할 전송, 실시간 보고 트래픽 우선",
                    "acs_processing": "classify_rca() 시그니처 매칭 → SCN-01~04 자동 판정 → incident_events 저장",
                },
            },
        ],
        "bandwidth_per_agv": {
            "stage1_icmp_probe_bps": icmp_bps,
            "stage2_piggyback_bps": round(piggyback_bps, 2),
            "stage3_early_warning_bytes_per_event": ew_bytes,
            "stage3_blackbox_bytes_per_incident": dump_compressed,
            "total_steady_state_bps": round(icmp_bps + piggyback_bps, 1),
            "note": "평시 추가 트래픽은 AGV당 약 70 B/s 수준 (대부분 GW ICMP 프로브), 장애 시에만 수 KB 단발 전송",
        },
        "comparison_table": [
            {"aspect": "관측 해상도", "legacy": "30초 스냅샷 (위치·배터리·작업 상태)",
             "hybrid": "1초 로컬 링버퍼 18개 지표 + 30초 통계 요약", "improvement": "30배 시간 해상도"},
            {"aspect": "사전 감지 (Pre-detection)", "legacy": "불가 — 다음 보고 누락(T+6s) 후에야 인지",
             "hybrid": "단절 14~18초 전 경보 (평균 15.75초)", "improvement": "인지 시점 약 22초 앞당김"},
            {"aspect": "단절 판정", "legacy": "45초 워치독 (T+21s), 18초 내 자가 복구 시 '지연 보고'로만 기록",
             "hybrid": "로컬 1초 감지 + 재연결 즉시 단절 사유(ETIMEDOUT/RST) 보고", "improvement": "단절 누락 0건"},
            {"aspect": "사후 원인 분석 (RCA)", "legacy": "불가 — 30초 전 정상 데이터뿐 (블랙박스)",
             "hybrid": "±60초 1초 해상도 덤프 → 4대 시나리오 자동 판정", "improvement": "원인 판별 가능"},
            {"aspect": "책임 경계 분리", "legacy": "무선/서버/AGV SW 구분 불가 → 엉뚱한 부서 이관",
             "hybrid": "GW RTT vs srtt vs Recv-Q/CPU로 무선·백본·호스트 분리", "improvement": "불필요한 무선 공사 방지"},
            {"aspect": "추가 무선 대역폭", "legacy": "0 B/s",
             "hybrid": f"약 {icmp_bps + piggyback_bps:.0f} B/s/AGV (ICMP 64 B/s + 피기백 {piggyback_bps:.1f} B/s)",
             "improvement": "채널 용량 대비 0.001% 미만"},
            {"aspect": "AGV CPU / 메모리", "legacy": "-", "hybrid": f"CPU < 0.5% / 링버퍼 약 {round(ring_bytes / 1024)} KB",
             "improvement": "임베디드 IPC에서도 무시 가능"},
            {"aspect": "단절 중 데이터 보존", "legacy": "단절 구간 데이터 소실",
             "hybrid": "로컬 링버퍼가 단절 중에도 계속 기록 → 재연결 후 업로드", "improvement": "단절 구간 완전 가시화"},
            {"aspect": "ACS 서버 부하", "legacy": "보고 1건/30s/AGV",
             "hybrid": "보고 1건/30s/AGV (동일) + 이벤트성 경보·덤프", "improvement": "프로토콜·주기 변경 없음"},
        ],
        "risk_model": {
            "weights": RISK_WEIGHTS,
            "doc_weights": {"w1_rssi": 0.25, "w2_snr": 0.15, "w3_l2_retry": 0.20, "w4_tcp_retrans": 0.25,
                            "w5_send_q": 0.15},
            "fusion": "max(가중 선형합, noisy-OR 융합) — 단일 영역 포화(예: CPU/소켓 행) 시 희석 방지",
            "thresholds": RISK_THRESHOLDS,
            "states": [
                {"state": "CONNECTED", "range": "< 45", "action": "평시 30초 보고 유지", "color": "--status-ok"},
                {"state": "PRE_WARNING", "range": "45 ~ 84.9",
                 "action": "링버퍼 잠금, Risk ≥ 70 시 조기 경보 푸시", "color": "--status-warn"},
                {"state": "DISCONNECTED", "range": "≥ 85", "action": "보고·제어 불가 — 재연결 후 블랙박스 덤프",
                 "color": "--status-crit"},
            ],
        },
    }


HYBRID_ARCHITECTURE_SPEC: Dict[str, Any] = _build_hybrid_spec()


if __name__ == "__main__":  # pragma: no cover — quick self-check
    print(len(METRICS_CATALOG), list(FAILURE_SCENARIOS.keys()))
    for c, sc in FAILURE_SCENARIOS.items():
        tl = sc["timeline"]
        print(c, len(tl), "rca=", sc["rca_result"]["scenario_code"], sc["rca_result"]["confidence"],
              "ew70=", sc["early_warning_push_offset_sec"])
