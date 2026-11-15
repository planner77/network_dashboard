"""
metrics_catalog.py — AGV/AMR ↔ ACS 무선 네트워크 텔레메트리 도메인 모듈 (v1.1)
================================================================================

Owner : domain-analyst (Domain & Telemetry Analyst)
Spec  : AGENTS.md (Golden Rules: 쉬운 한국어 용어 사용, AGV/AMR 및 ACS 전용 수집)
        docs/ANALYSIS_AND_METRICS.md (18종 수집 지표, 사전 감지·사후 분석, 담당자별 할 일)
        docs/ARCHITECTURE.md (시계열 DB 도입 필요성, 3단계 하이브리드 수집 모델, API 명세)

Pure Python, standard library only (math, random, json, struct, typing).
All data below is deterministic (seeded) and computed once at import time.

Exported symbols
----------------
METRICS_CATALOG            list[dict]   18 metric specs (M01..M18, AGV/AMR & ACS only)
METRICS_BY_ID / METRICS_BY_KEY          lookup dicts
LAYERS                     list[dict]   layer filter metadata (L1_L2 / L3_L4 / L7_SYS)
evaluate_metric(key, value) -> "normal" | "warning" | "critical" | "unknown"
compute_risk_score(sample, prev_score=None, alpha=None) -> dict
classify_rca(samples_window) -> dict
FAILURE_SCENARIOS          dict[str, dict]  SCN-01..SCN-04 (120-pt timelines)
ROLE_ACTION_PLANS          dict         AGV/AMR 담당자 & ACS 담당자 할 일 및 용어/TSDB 가이드
HYBRID_ARCHITECTURE_SPEC   dict         3단계 하이브리드 수집 구조 + 용어/TSDB/역할 분담 통합 명세
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
    "ROLE_ACTION_PLANS",
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
# 1. METRICS_CATALOG — 18 telemetry metrics (Strictly AGV/AMR & ACS Only)
#    - M01..M09, M17      -> "AGV/AMR"
#    - M10..M14, M16, M18 -> "AGV/AMR, ACS"
#    - M15                -> "ACS"
# ---------------------------------------------------------------------------
METRICS_CATALOG: List[Dict[str, Any]] = [
    # ======================= L1/L2 — Wi-Fi PHY & MAC (AGV/AMR 자체 수집 8종) =======================
    {
        "id": "M01",
        "key": "rssi",
        "name_ko": "수신 신호 세기 (RSSI)",
        "name_en": "Received Signal Strength Indicator (RSSI)",
        "abbr": "RSSI",
        "layer": LAYER_L12,
        "layer_code": "L1_L2",
        "description": (
            "AGV/AMR 무선 랜카드가 현재 연결된 무선 기지국(AP)으로부터 받는 와이파이 신호의 강도입니다 (0에 가까울수록 강함). "
            "AGV는 이동하며 작업하므로 기지국과의 거리나 철제 선반·설비 가림에 따라 신호가 초 단위로 변합니다. "
            "신호 세기가 -75dBm 이하로 약해지면 무선 재전송이 급증하고, 기존 기지국을 제때 놓지 못하는 현상(Sticky Client)이 발생해 "
            "ACS 소켓 통신 끊김의 가장 흔한 원인이 됩니다."
        ),
        "unit": "dBm",
        "thresholds": {"normal": "≥ -67 dBm", "warning": "-68 ~ -74 dBm", "critical": "≤ -75 dBm"},
        "threshold_levels": {"direction": "higher_is_better", "warning": -67.5, "critical": -74.5},
        "display_range": [-95, -40],
        "collection_location": "AGV/AMR",
        "interval_local": "1s",
        "interval_report": "30초 정기 보고 시 요약 데이터 동봉 전송",
        "recommended_interval": "AGV 내부 1초 단위 상시 기록장 (최근 5분 순환 보관) / 30초 정기 보고 시 요약 데이터 동봉 전송 (최저·평균·편차)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (AGV 내부 기록 전용, 30초 보고 시 요약 6 Bytes 동봉)",
                             "AGV 내부 OS 무선 상태 파일(/proc/net/wireless)만 읽으므로 추가 무선 전송이 전혀 없음"),
        "collection_method": {
            "interface": "AGV Linux /proc/net/wireless 또는 nl80211 (iw dev wlan0 link)",
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
            "detail": "AGV 내부에서 1초마다 신호 세기를 읽어 상시 기록장에 보관하고, 직전 5초 값으로 초당 하락 속도(기울기)를 함께 계산합니다.",
        },
        "analysis_usage": {
            "pre_detection": "신호 절대값(< -72dBm)과 5초간 하락 속도(초당 -2.5dBm 이상 급락)를 결합해 전파 음영 구역 진입을 끊김 15~18초 전에 미리 감지 (위험도 가중치 25%).",
            "post_mortem": "끊김 직전 신호 변화 모양(완만한 하락 → 기지국 전환 지연 SCN-01, 급격한 추락 → 전파 음영 구역 SCN-02)으로 원인을 구분하고, 주행 좌표(M18)와 결합해 음영 구역 지도를 생성.",
            "weight": 0.25,
        },
    },
    {
        "id": "M02",
        "key": "snr",
        "name_ko": "신호 대 잡음 비율 (SNR)",
        "name_en": "Signal-to-Noise Ratio (SNR)",
        "abbr": "SNR",
        "layer": LAYER_L12,
        "layer_code": "L1_L2",
        "description": (
            "주변 무선 잡음(Noise Floor) 대비 실제 통신 신호가 얼마나 깨끗한지 나타내는 비율(SNR = 신호 세기 − 잡음 수치)입니다. "
            "신호 세기(M01)가 -62dBm으로 강해 보여도 주변 용접기·인버터·고주파 모터에서 강한 전파 잡음이 발생하면 "
            "신호 대 잡음 비율이 12dB 이하로 떨어져 통신이 끊어지므로, 설비 전파 간섭(EMI) 여부를 가려내는 핵심 항목입니다."
        ),
        "unit": "dB",
        "thresholds": {"normal": "≥ 25 dB", "warning": "18 ~ 24 dB", "critical": "≤ 17 dB"},
        "threshold_levels": {"direction": "higher_is_better", "warning": 24.5, "critical": 17.5},
        "display_range": [0, 50],
        "collection_location": "AGV/AMR",
        "interval_local": "1s",
        "interval_report": "30초 정기 보고 시 요약 데이터 동봉 전송",
        "recommended_interval": "AGV 내부 1초 단위 상시 기록장 (최근 5분 순환 보관) / 30초 정기 보고 시 요약 데이터 동봉 전송 (최저 SNR)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (AGV 내부 계산, 30초 보고 시 1 Byte 동봉)",
                             "AGV가 측정한 수신 신호(M01)와 잡음 수치(M03)의 차이만 계산하므로 추가 부하가 없음"),
        "collection_method": {
            "interface": "AGV 무선 드라이버 정보 (RSSI − Noise Floor 자동 산출)",
            "command": "iw dev wlan0 survey dump | grep -A1 'in use' ; iw dev wlan0 link",
            "code_snippet": (
                "snr_db = rssi_dbm - noise_floor_dbm   # 예: -62 - (-95) = 33 dB\n"
                "local_record_book.append({'ts': now, 'snr': snr_db})"
            ),
            "detail": "AGV 무선 랜카드가 읽은 현재 채널 잡음 수치와 수신 신호 세기의 차이를 1초마다 계산해 내부 상시 기록장에 저장합니다.",
        },
        "analysis_usage": {
            "pre_detection": "SNR이 20dB 아래로 떨어지면 위험 점수를 높이고(가중치 15%), 신호 세기는 정상인데 SNR만 급락하면 설비 전파 간섭 조기 경보를 발송.",
            "post_mortem": "신호 세기(M01)는 좋은데 SNR만 무너진 끊김 → 용접기·모터 등 주변 설비 전파 간섭(SCN-02)으로 판정하여 기지국 증설이 아닌 채널 변경 조치를 안내.",
            "weight": 0.15,
        },
    },
    {
        "id": "M03",
        "key": "noise_floor",
        "name_ko": "주변 무선 잡음 수치 (Noise Floor)",
        "name_en": "Noise Floor",
        "abbr": "Noise",
        "layer": LAYER_L12,
        "layer_code": "L1_L2",
        "description": (
            "공장 내 용접기, 고주파 가열기, 대형 모터 인버터 등에서 발생하여 무선 채널에 깔려 있는 바닥 잡음의 크기입니다. "
            "평소 5GHz 무선 대역은 -95 ~ -92dBm 수준으로 조용하지만, 고주파 설비가 가동되면 -84dBm 이상으로 치솟아 "
            "주변을 지나는 AGV의 통신 품질을 동시에 떨어뜨립니다."
        ),
        "unit": "dBm",
        "thresholds": {"normal": "≤ -90 dBm", "warning": "-89 ~ -85 dBm", "critical": "≥ -84 dBm"},
        "threshold_levels": {"direction": "lower_is_better", "warning": -89.5, "critical": -84.5},
        "display_range": [-100, -70],
        "collection_location": "AGV/AMR",
        "interval_local": "5s",
        "interval_report": "30초 정기 보고 시 요약 데이터 동봉 전송",
        "recommended_interval": "AGV 내부 5초 주기 기록 (상시 기록장) / 30초 정기 보고 시 요약 데이터 동봉 전송 (최대 잡음)",
        "system_load": _load(_LOAD_LOW, "0 B/s (AGV 내부 무선 카드 채널 상태 읽기)",
                             "AGV 무선 랜카드의 현재 사용 채널 상태(survey dump)만 5초 주기로 읽음"),
        "collection_method": {
            "interface": "AGV nl80211 NL80211_CMD_GET_SURVEY (iw dev wlan0 survey dump)",
            "command": "iw dev wlan0 survey dump | awk '/in use/{f=1} f&&/noise/{print $2; exit}'",
            "code_snippet": (
                "import subprocess, re\n"
                "out = subprocess.run(['iw','dev','wlan0','survey','dump'],capture_output=True,text=True).stdout\n"
                "blk = out.split('[in use]')[1]\n"
                "noise = float(re.search(r'noise:\\s+(-?\\d+)', blk).group(1))"
            ),
            "detail": "AGV가 다른 채널을 탐색하지 않고 현재 연결된 채널([in use])의 잡음 값만 읽으므로 통신 끊김이나 지연이 전혀 없습니다.",
        },
        "analysis_usage": {
            "pre_detection": "잡음 수치가 5초 내 6dB 이상 급상승하면 전파 간섭 구역 진입으로 판단하여 사전 위험 점수에 반영.",
            "post_mortem": "특정 구역이나 설비 가동 시간대에 잡음 수치가 함께 치솟았는지 대조하여 전파 방해(SCN-02) 유입을 증명.",
            "weight": 0.05,
        },
    },
    {
        "id": "M04",
        "key": "phy_rate",
        "name_ko": "무선 연결 속도 및 변조 등급 (PHY Rate & MCS Index)",
        "name_en": "Tx/Rx PHY Rate & MCS Index",
        "abbr": "PHY/MCS",
        "layer": LAYER_L12,
        "layer_code": "L1_L2",
        "description": (
            "AGV 무선 랜카드와 기지국(AP) 사이에 현재 맺어진 실제 무선 전송 속도(Mbps)와 변조 등급(MCS Index, 0~11)입니다. "
            "MCS Index와 무선 전송 속도는 1:1로 연동되는 값으로, 전파 상태가 나빠지면 연결이 끊어지기 전에 스스로 MCS 등급과 속도를 단계적으로 낮추어(예: MCS 7 144Mbps → MCS 3 54Mbps → MCS 0 6Mbps) "
            "버티려 하므로, MCS Index 및 무선 연결 속도 급락은 통신 끊김 직전에 나타나는 매우 빠른 사전 징후입니다."
        ),
        "unit": "Mbps (MCS 0~11)",
        "thresholds": {"normal": "≥ 100 Mbps (MCS 5~11)", "warning": "24 ~ 99 Mbps (MCS 2~4)", "critical": "≤ 18 Mbps (MCS 0~1)"},
        "threshold_levels": {"direction": "higher_is_better", "warning": 99.5, "critical": 18.5},
        "display_range": [0, 450],
        "collection_location": "AGV/AMR",
        "interval_local": "1s",
        "interval_report": "30초 정기 보고 시 요약 데이터 동봉 전송",
        "recommended_interval": "AGV 내부 1초 단위 상시 기록장 (최근 5분 순환 보관) / 30초 정기 보고 시 요약 데이터 동봉 전송 (최저 속도·최저 MCS Index)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (AGV 내부 상태값 읽기)",
                             "AGV 커널 무선 상태 구조체에서 송수신 속도(PHY Rate)와 MCS Index 값을 1회 동시 조회"),
        "collection_method": {
            "interface": "AGV nl80211 NL80211_ATTR_STA_INFO (tx_bitrate / rx_bitrate / mcs)",
            "command": "iw dev wlan0 link | grep -E 'tx bitrate|rx bitrate'   # 속도(Mbps) 및 MCS Index 동시 출력",
            "code_snippet": (
                "out = subprocess.run(['iw','dev','wlan0','link'],capture_output=True,text=True).stdout\n"
                "tx = float(re.search(r'tx bitrate:\\s+([\\d.]+)', out).group(1))  # Mbps\n"
                "mcs_m = re.search(r'MCS\\s+(\\d+)', out)\n"
                "mcs_index = int(mcs_m.group(1)) if mcs_m else None"
            ),
            "detail": "iw dev wlan0 link 한 줄에서 송수신 속도(Mbps)와 MCS Index가 동시에 조회됩니다.",
        },
        "analysis_usage": {
            "pre_detection": "MCS Index가 2 이하로 떨어지거나 무선 연결 속도가 5초 내 절반 이하로 떨어지면 무선 품질 악화 징후로 판단하여 사전 위험 점수에 반영.",
            "post_mortem": "끊김 직전 속도가 최저 수준(MCS 0, 6~12Mbps)까지 떨어졌다면 전파 음영·간섭(SCN-02), 속도와 MCS는 높았는데 끊겼다면 프로그램 응답 지연(SCN-04) 등으로 구분.",
            "weight": 0.05,
        },
    },
    {
        "id": "M05",
        "key": "l2_retry_rate",
        "name_ko": "무선 구간 송수신 재시도 비율 (Tx/Rx Retry Rate)",
        "name_en": "Tx/Rx Retry Rate (802.11 Wi-Fi Retry & Rx Drop Rate)",
        "abbr": "Tx/Rx Retry",
        "layer": LAYER_L12,
        "layer_code": "L1_L2",
        "description": (
            "무선 신호가 깨지거나 충돌해서 AGV 와이파이 칩셋이 데이터를 다시 보낸 송신 재시도율(Tx Retry Rate)과 수신 프레임 오류·중복 비율(Rx Retry/Drop Rate)입니다. "
            "와이파이 칩셋이 내부적으로 수차례 재시도하는 동안에는 상위 프로그램(소켓)이 이상을 눈치채지 못하므로, "
            "Tx/Rx Retry Rate 급증은 소켓 통신이 끊어지기 수 초 전에 가장 먼저 치솟는 핵심 위험 신호입니다."
        ),
        "unit": "%",
        "thresholds": {"normal": "< 8 %", "warning": "8 ~ 20 %", "critical": "> 20 %"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 8.0, "critical": 20.0},
        "display_range": [0, 70],
        "collection_location": "AGV/AMR",
        "interval_local": "1s",
        "interval_report": "30초 정기 보고 시 요약 데이터 동봉 전송",
        "recommended_interval": "AGV 내부 1초 단위 상시 기록장 (최근 5분 순환 보관) / 30초 정기 보고 시 요약 데이터 동봉 전송 (최대 Tx/Rx 재시도율)",
        "system_load": _load(_LOAD_LOW, "0 B/s (AGV 내부 전송·수신 카운터 비교)",
                             "AGV 무선 드라이버의 누적 송수신·재시도 카운터를 1초 간격으로 비교하여 비율 산출"),
        "collection_method": {
            "interface": "AGV nl80211 STA_INFO (tx_retries, tx_packets, rx_drop_misc) 및 /proc/net/wireless",
            "command": "iw dev wlan0 station dump | grep -E 'tx packets|tx retries|tx failed|rx drop'",
            "code_snippet": (
                "d_retry = cur['tx_retries'] - prev['tx_retries']\n"
                "d_pkts  = cur['tx_packets'] - prev['tx_packets']\n"
                "tx_retry_pct = 100.0 * d_retry / max(d_pkts, 1)"
            ),
            "detail": "AGV 내부에서 직전 1초 동안의 전송 수 대비 재시도 비율(Tx Retry Rate)과 수신 드롭(Rx Drop)을 계산하여 상시 기록장에 남깁니다.",
        },
        "analysis_usage": {
            "pre_detection": "Tx/Rx Retry Rate가 15%를 넘으면 위험 점수를 크게 높임(가중치 20%). 소켓(TCP) 재전송보다 평균 3~6초 먼저 나타나는 선행 지표.",
            "post_mortem": "재시도 35% 이상 + 신호 급락 → 전파 음영(SCN-02), 재시도 상승 + 신호 양호 + 채널 혼잡도 과다 → 무선 채널 혼잡(SCN-03).",
            "weight": 0.20,
        },
    },
    {
        "id": "M06",
        "key": "beacon_loss",
        "name_ko": "기지국 확인 신호 놓침 수 (Beacon Loss)",
        "name_en": "Beacon Loss Count",
        "abbr": "Beacon Loss",
        "layer": LAYER_L12,
        "layer_code": "L1_L2",
        "description": (
            "무선 기지국(AP)이 0.1초마다 보내는 생존 확인 신호(비콘)를 AGV가 받지 못하고 놓친 횟수입니다. "
            "이 확인 신호를 연속으로 놓치면 AGV 무선 랜카드는 기지국과의 연결이 끊어진 것으로 판단해 연결을 해제하고 "
            "새 기지국 찾기를 시작하므로, 수 초 내 통신 단절이 일어날 것임을 직접 알려줍니다."
        ),
        "unit": "count/s",
        "thresholds": {"normal": "0 ~ 1 회/초", "warning": "2 ~ 4 회/초", "critical": "≥ 5 회/초"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 1.5, "critical": 4.5},
        "display_range": [0, 12],
        "collection_location": "AGV/AMR",
        "interval_local": "1s",
        "interval_report": "30초 정기 보고 시 요약 데이터 동봉 전송",
        "recommended_interval": "AGV 내부 1초 단위 상시 기록장 (최근 5분 순환 보관) / 30초 정기 보고 시 요약 데이터 동봉 전송 (30초 합계)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (AGV 내부 드라이버 카운터 조회)", "AGV 커널 무선 카운터(beacon_loss) 단순 조회"),
        "collection_method": {
            "interface": "AGV nl80211 NL80211_STA_INFO_BEACON_LOSS",
            "command": "iw dev wlan0 station dump | grep -E 'beacon loss|beacon rx'",
            "code_snippet": (
                "bl_delta = cur['beacon_loss'] - prev['beacon_loss']\n"
                "expected = 1000 / 102.4  # 초당 약 9.77개 비콘 수신 기대\n"
                "beacon_rx_ratio = (cur['beacon_rx'] - prev['beacon_rx']) / expected"
            ),
            "detail": "AGV 무선 드라이버에서 지난 1초 동안 놓친 비콘 횟수를 계산하여 내부 상시 기록장에 기록합니다.",
        },
        "analysis_usage": {
            "pre_detection": "초당 2회 이상 확인 신호를 놓치는 상태가 3초 이상 이어지면 기지국 연결 해제 임박으로 판단해 사전 경보 발송.",
            "post_mortem": "기지국 변경 직전 확인 신호 놓침 급증 + 기지국 주소(BSSID) 미변경 → 기존 기지국 고착 현상(SCN-01) 판별.",
            "weight": 0.05,
        },
    },
    {
        "id": "M07",
        "key": "roaming_ms",
        "name_ko": "기지국(AP) 변경 소요 시간 (Roaming Time)",
        "name_en": "Roaming Time & AP ID (BSSID)",
        "abbr": "Roaming",
        "layer": LAYER_L12,
        "layer_code": "L1_L2",
        "description": (
            "AGV가 이동하면서 기존 무선 기지국(AP)에서 다음 기지국으로 갈아타는(로밍) 데 걸린 시간과 기지국 주소(BSSID)입니다. "
            "고속 로밍 설정(802.11k/v/r)이 되어 있으면 50ms 이내에 매끄럽게 넘어가지만, 설정이 없으면 인증을 처음부터 다시 하느라 "
            "수백 ms~1초 이상 통신이 멈추고 그 사이 소켓 연결이 끊어집니다."
        ),
        "unit": "ms",
        "thresholds": {"normal": "< 50 ms", "warning": "50 ~ 150 ms", "critical": "> 200 ms"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 50.0, "critical": 200.0},
        "display_range": [0, 1600],
        "collection_location": "AGV/AMR",
        "interval_local": "Event 즉시",
        "interval_report": "30초 정기 보고 시 요약 데이터 동봉 전송",
        "recommended_interval": "기지국 변경 시 AGV 내부 즉시 기록 (1초 상시 감시) / 30초 정기 보고 시 요약 데이터 동봉 전송 (변경 횟수·최대 소요 시간)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (AGV 내부 이벤트 발생 시만 기록)",
                             "AGV 내부 무선 관리 프로그램(wpa_supplicant)의 연결 이벤트를 받아 시각 차이만 계산"),
        "collection_method": {
            "interface": "AGV wpa_supplicant 이벤트 소켓 (CTRL-EVENT-CONNECTED / SME: Trying to authenticate)",
            "command": "wpa_cli -i wlan0 -a /usr/local/bin/roam_hook.sh   # AGV 내부 이벤트 기록 스크립트",
            "code_snippet": (
                "# AGV 내부 wpa_cli 이벤트 핸들러\n"
                "if ev.startswith('SME: Trying to authenticate'):\n"
                "    t_start = time.monotonic()\n"
                "elif ev.startswith('CTRL-EVENT-CONNECTED'):\n"
                "    roaming_ms = (time.monotonic() - t_start) * 1000\n"
                "    bssid = re.search(r'to ([0-9a-f:]{17})', ev).group(1)"
            ),
            "detail": "별도 무선 장비(WLC) 권한 없이도 AGV 내부의 wpa_supplicant 이벤트 시각 차이만으로 기지국 변경 소요 시간과 이전·이후 AP 주소를 정확히 측정합니다.",
        },
        "analysis_usage": {
            "pre_detection": "신호가 -72dBm 이하로 약해졌는데도 기지국 주소(BSSID)가 바뀌지 않고 유지되면 기지국 고착(Sticky Client) 위험으로 사전 표시.",
            "post_mortem": "끊김 순간 기지국 변경 소요 시간 > 200ms + 확인 신호 놓침 급증 → 기지국 전환(로밍) 실패·지연(SCN-01)으로 확정.",
            "weight": 0.05,
        },
    },
    {
        "id": "M08",
        "key": "channel_util",
        "name_ko": "무선 채널 혼잡도 (Channel Busy Ratio)",
        "name_en": "Channel Busy Ratio (CCA Utilization)",
        "abbr": "Ch. Busy",
        "layer": LAYER_L12,
        "layer_code": "L1_L2",
        "description": (
            "AGV가 현재 사용 중인 무선 주파수 통로(채널)가 전체 시간 중 얼마나 붐비는지 나타내는 비율입니다. "
            "와이파이는 한 채널을 여러 기기가 나눠 쓰므로 혼잡도가 65%를 넘으면 신호 세기가 아무리 강해도 AGV가 데이터를 보낼 차례를 얻지 못해 "
            "응답 지연과 재시도가 급증합니다. 신호는 좋은데 통신이 안 되는 '채널 과부하' 원인을 밝혀냅니다."
        ),
        "unit": "%",
        "thresholds": {"normal": "< 40 %", "warning": "40 ~ 65 %", "critical": "> 65 %"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 40.0, "critical": 65.0},
        "display_range": [0, 100],
        "collection_location": "AGV/AMR",
        "interval_local": "5s",
        "interval_report": "30초 정기 보고 시 요약 데이터 동봉 전송",
        "recommended_interval": "AGV 내부 5초 주기 기록 (상시 기록장) / 30초 정기 보고 시 요약 데이터 동봉 전송 (최대 혼잡도)",
        "system_load": _load(_LOAD_LOW, "0 B/s (AGV 무선 카드 채널 사용 시간 비율 계산)",
                             "AGV 무선 랜카드가 측정한 채널 사용 시간(busy time / active time)을 5초 간격으로 계산"),
        "collection_method": {
            "interface": "AGV nl80211 survey dump (channel active time / busy time)",
            "command": "iw dev wlan0 survey dump | grep -A6 'in use' | grep -E 'active time|busy time'",
            "code_snippet": (
                "# AGV 무선 랜카드의 채널 사용 비율 직접 산출\n"
                "util_pct = 100.0 * (busy_t - busy_prev) / max(active_t - active_prev, 1)"
            ),
            "detail": "무선 컨트롤러(WLC) 장비에 접속하지 않고도 AGV 무선 랜카드의 survey 카운터(busy_time / active_time)만으로 현재 채널 혼잡도를 정확히 계산합니다.",
        },
        "analysis_usage": {
            "pre_detection": "채널 혼잡도가 65%를 넘어 10초 이상 지속되면 무선 통로 과밀 위험으로 사전 감지 점수에 반영.",
            "post_mortem": "신호 세기(M01)도 좋고 잡음(M03)도 없는데 혼잡도가 75%를 넘고 응답 시간이 급증한 경우 → 무선 채널 과부하(SCN-03)로 확정.",
            "weight": 0.10,
        },
    },
    # ======================= L3/L4 — Network & Transport (AGV/AMR 및 ACS 수집 6종) =======================
    {
        "id": "M09",
        "key": "gw_rtt_ms",
        "name_ko": "게이트웨이 Ping 응답 지연 및 패킷 손실률 (Ping Latency & Packet Loss)",
        "name_en": "Gateway Ping Latency (RTT) & Packet Loss (%)",
        "abbr": "Ping / Loss",
        "layer": LAYER_L34,
        "layer_code": "L3_L4",
        "description": (
            "AGV에서 가장 가까운 유선 네트워크 관문(기본 게이트웨이 스위치)까지 작은 확인 패킷(Ping)이 왕복하는 응답 지연 시간(Ping Latency)과 무응답 손실 비율(Packet Loss %)입니다. "
            "사실상 순수 무선 구간(AGV↔기지국)의 지연과 패킷 손실만을 뜻하므로, ACS 통신이 느려졌을 때 이 값이 정상이면 '사내 유선망 또는 ACS 서버 문제', "
            "이 값도 함께 치솟으면 '현장 무선 구간 문제'라고 책임 구간을 명확히 나눌 수 있습니다."
        ),
        "unit": "ms / %",
        "thresholds": {"normal": "< 10 ms (손실 0%)", "warning": "10 ~ 40 ms (손실 1~5%)", "critical": "> 50 ms (손실 > 5%)"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 10.0, "critical": 50.0},
        "display_range": [0, 320],
        "collection_location": "AGV/AMR",
        "interval_local": "2s",
        "interval_report": "30초 정기 보고 시 요약 데이터 동봉 전송",
        "recommended_interval": "AGV 내부 2초 주기 측정 (상시 기록장) / 30초 정기 보고 시 요약 데이터 동봉 전송 (평균·최대 Ping Latency 및 Packet Loss %)",
        "system_load": _load(_LOAD_LOW, "약 64 B/s (2초당 아주 작은 64B 확인 패킷 1개)",
                             "2초마다 64바이트 Ping 1개만 보내므로 무선 대역폭 영향은 0.001% 미만 (300ms 초과 시 Packet Loss 카운트)"),
        "collection_method": {
            "interface": "AGV 비동기 ICMP Ping (Ping Latency & Packet Loss 동시 측정)",
            "command": "fping -c1 -t300 -q $(ip route | awk '/default/{print $3}')   # Ping Latency 및 Packet Loss 측정",
            "code_snippet": (
                "sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_ICMP)\n"
                "t0 = time.perf_counter(); sock.sendto(echo_pkt, (gw_ip, 0))\n"
                "sock.settimeout(0.3)\n"
                "try:\n"
                "    sock.recv(64); gw_rtt_ms = (time.perf_counter() - t0) * 1000; pkt_loss = 0\n"
                "except socket.timeout:\n"
                "    gw_rtt_ms = 300.0; pkt_loss = 100"
            ),
            "detail": "AGV에서 기본 게이트웨이 IP로 비동기 Ping을 보내 응답 지연 시간(Ping Latency)과 패킷 손실률(Packet Loss)을 동시에 측정합니다.",
        },
        "analysis_usage": {
            "pre_detection": "Ping Latency가 평소보다 3배 이상 길어지거나 Packet Loss가 발생하면 무선 구간 지연·손실 누적으로 판단해 사전 위험 점수에 반영.",
            "post_mortem": "Ping Latency(< 10ms)와 Packet Loss(0%)가 모두 정상인데 ACS 보고만 멈춘 경우 → 무선이 아닌 통신 프로그램 일시 멈춤(SCN-04)으로 판정.",
            "weight": 0.05,
        },
    },
    {
        "id": "M10",
        "key": "jitter_ms",
        "name_ko": "응답 시간 흔들림 폭 (RTT Jitter)",
        "name_en": "RTT Jitter",
        "abbr": "Jitter",
        "layer": LAYER_L34,
        "layer_code": "L3_L4",
        "description": (
            "연속으로 측정한 통신 응답 시간(RTT)이 일정하지 않고 들쭉날쭉하게 흔들리는 변화 폭(|이번 RTT − 직전 RTT| 평균)입니다. "
            "평균 응답 시간은 아직 낮아 보여도 흔들림 폭이 먼저 커지면 무선 채널 경합이나 기지국 변경 탐색이 시작되었음을 뜻합니다."
        ),
        "unit": "ms",
        "thresholds": {"normal": "< 5 ms", "warning": "5 ~ 20 ms", "critical": "> 20 ms"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 5.0, "critical": 20.0},
        "display_range": [0, 150],
        "collection_location": "AGV/AMR, ACS",
        "interval_local": "2s",
        "interval_report": "30초 정기 보고 시 요약 데이터 동봉 전송",
        "recommended_interval": "AGV 및 ACS 내부 2초 주기 산출 / 30초 정기 보고 시 요약 데이터 동봉 전송 (최대 흔들림 폭)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (기존 응답 시간 측정값 차이 계산)", "M09·M12 응답 시간의 변화 폭만 계산"),
        "collection_method": {
            "interface": "AGV 및 ACS의 M09/M12 응답 시간 측정값 및 커널 tcpi_rttvar 참조",
            "command": "ss -ti dst <PEER_IP> | grep -o 'rtt:[0-9.]*/[0-9.]*'   # rtt/rttvar",
            "code_snippet": (
                "diffs = [abs(a - b) for a, b in zip(rtts[1:], rtts[:-1])]\n"
                "jitter_ms = sum(diffs) / max(len(diffs), 1)"
            ),
            "detail": "AGV와 ACS 양쪽에서 응답 시간의 변화 폭을 계산하여 무선 흔들림을 감시합니다.",
        },
        "analysis_usage": {
            "pre_detection": "흔들림 폭이 20ms를 넘어 반복되면 평균 응답 시간이 오르기 전에 통신 불안정 시작을 조기 감지.",
            "post_mortem": "흔들림 폭 100ms 이상 + 채널 혼잡도 과다 → 무선 채널 혼잡(SCN-03), 흔들림 정상 + 수신 대기열 적체 → 프로그램 일시 멈춤(SCN-04).",
            "weight": 0.05,
        },
    },
    {
        "id": "M11",
        "key": "tcp_retrans",
        "name_ko": "소켓(TCP) 재전송 횟수 (TCP Retransmits)",
        "name_en": "TCP Retransmits",
        "abbr": "TCP Retx",
        "layer": LAYER_L34,
        "layer_code": "L3_L4",
        "description": (
            "AGV와 ACS 간 소켓 통신에서 상대방 확인 응답(ACK)을 받지 못해 운영체제(OS)가 다시 보낸 횟수(초당)입니다. "
            "소켓 통신은 재전송이 연속되면 대기 시간을 0.2초 → 0.4초 → 0.8초로 두 배씩 늘리므로, "
            "재전송이 시작되면 불과 몇 초 안에 통신 시간 초과(Timeout)로 연결이 끊어집니다. 끊김 직전을 직접 포착하는 핵심 지표입니다."
        ),
        "unit": "count/s",
        "thresholds": {"normal": "0 회/초", "warning": "1 ~ 3 회/초", "critical": "≥ 4 회/초"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 0.5, "critical": 3.5},
        "display_range": [0, 10],
        "collection_location": "AGV/AMR, ACS",
        "interval_local": "1s",
        "interval_report": "30초 정기 보고 시 요약 데이터 동봉 전송",
        "recommended_interval": "AGV 및 ACS 내부 1초 단위 상시 기록 / 30초 정기 보고 시 요약 데이터 동봉 전송 (30초 재전송 합계)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (OS 소켓 상태표 읽기)",
                             "AGV와 ACS의 OS 커널 소켓 상태(tcp_info)를 메모리에서 바로 조회"),
        "collection_method": {
            "interface": "AGV 및 ACS OS 커널 getsockopt(TCP_INFO) → tcpi_total_retrans / ss -ti",
            "command": "ss -ti dst <PEER_IP>:<PORT> | grep -oE 'retrans:[0-9]+/[0-9]+'",
            "code_snippet": (
                "import socket, struct\n"
                "raw = sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_INFO, 232)\n"
                "total_retrans = struct.unpack_from('I', raw, 100)[0]  # tcpi_total_retrans\n"
                "retrans_per_s = total_retrans - prev_total_retrans"
            ),
            "detail": "AGV와 ACS 통신 프로그램이 열려 있는 소켓에서 직접 재전송 횟수를 1초마다 읽어 기록합니다.",
        },
        "analysis_usage": {
            "pre_detection": "초당 2회 이상 소켓 재전송 발생 시 위험 점수를 크게 높임(가중치 25%). 수 초 내 정기 보고 중단을 직접 예고.",
            "post_mortem": "끊김 직전 재전송이 전혀 없었다면 무선 손실이 아닌 통신 프로그램 일시 멈춤(SCN-04), 재전송이 급증했다면 무선 구간 문제(SCN-01~03).",
            "weight": 0.25,
        },
    },
    {
        "id": "M12",
        "key": "tcp_srtt_ms",
        "name_ko": "소켓 종단 간 왕복 시간 (TCP Smoothed RTT)",
        "name_en": "TCP Smoothed RTT (srtt)",
        "abbr": "TCP sRTT",
        "layer": LAYER_L34,
        "layer_code": "L3_L4",
        "description": (
            "AGV와 ACS 서버 사이의 실제 소켓 통신 패킷이 왕복하는 데 걸리는 평균 시간입니다. "
            "별도의 테스트 패킷을 보내지 않아도 OS가 실제 제어·보고 메시지로부터 자동 계산해 두는 값이며, "
            "게이트웨이 응답 시간(M09)과 비교하면 지연이 무선 구간에서 생겼는지 서버 처리에서 생겼는지 구분할 수 있습니다."
        ),
        "unit": "ms",
        "thresholds": {"normal": "< 15 ms", "warning": "15 ~ 60 ms", "critical": "> 60 ms"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 15.0, "critical": 60.0},
        "display_range": [0, 400],
        "collection_location": "AGV/AMR, ACS",
        "interval_local": "1s",
        "interval_report": "30초 정기 보고 시 요약 데이터 동봉 전송",
        "recommended_interval": "AGV 및 ACS 내부 1초 단위 상시 기록 / 30초 정기 보고 시 요약 데이터 동봉 전송 (최대 왕복 시간)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (추가 통신 없이 소켓 내부값 조회)", "M11 조회 시 같은 tcp_info 구조체에서 함께 읽음"),
        "collection_method": {
            "interface": "AGV 및 ACS OS 커널 getsockopt(TCP_INFO) → tcpi_rtt (μs)",
            "command": "ss -ti dst <PEER_IP> | grep -oE 'rtt:[0-9.]+/[0-9.]+'",
            "code_snippet": (
                "tcpi_rtt_us, tcpi_rttvar_us = struct.unpack_from('II', raw, 68)\n"
                "tcp_srtt_ms = tcpi_rtt_us / 1000.0"
            ),
            "detail": "소켓 왕복 시간(M12)에서 게이트웨이 응답 시간(M09)을 뺀 차이가 크면 유선망·프로그램 응답 지연으로 해석합니다.",
        },
        "analysis_usage": {
            "pre_detection": "소켓 왕복 시간이 60ms를 넘어 계속 증가하면 전송 계층 위험 점수에 반영.",
            "post_mortem": "게이트웨이 응답 시간(M09)은 정상인데 소켓 왕복 시간만 치솟은 경우 → 상대방 통신 프로그램 응답 지연(SCN-04).",
            "weight": 0.05,
        },
    },
    {
        "id": "M13",
        "key": "send_q_bytes",
        "name_ko": "소켓 송신 대기열 크기 (Send Queue / Socket Send-Q)",
        "name_en": "Socket Send Queue (Send-Q Bytes)",
        "abbr": "Send-Q",
        "layer": LAYER_L34,
        "layer_code": "L3_L4",
        "description": (
            "통신 프로그램이 데이터를 보냈으나 상대방에게 아직 전달(확인 응답 수신)되지 못해 출발지 OS 송신 대기열(Send Queue)에 쌓여 있는 데이터양(Bytes)입니다. "
            "정상일 때는 즉시 0으로 비워지지만, 무선 끊김 직전에는 보내지 못한 보고 데이터가 대기열에 계속 쌓이므로 "
            "수 초 내 통신 단절이 일어날 것을 확실하게 예고합니다."
        ),
        "unit": "Bytes",
        "thresholds": {"normal": "0 B", "warning": "1 B ~ 4 KB", "critical": "> 4 KB"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 1.0, "critical": 4096.0},
        "display_range": [0, 16384],
        "collection_location": "AGV/AMR, ACS",
        "interval_local": "1s",
        "interval_report": "30초 정기 보고 시 요약 데이터 동봉 전송",
        "recommended_interval": "AGV 및 ACS 내부 1초 단위 상시 기록 / 30초 정기 보고 시 요약 데이터 동봉 전송 (최대 송신 대기량)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (OS 소켓 버퍼 크기 조회)", "ioctl(SIOCOUTQ) 시스템 호출 1회"),
        "collection_method": {
            "interface": "AGV 및 ACS ioctl(fd, SIOCOUTQ) 또는 ss -tn (Send-Q 컬럼)",
            "command": "ss -tn dst <PEER_IP> | awk 'NR>1{print $3}'   # Send Queue (Send-Q)",
            "code_snippet": (
                "import fcntl, termios, array\n"
                "buf = array.array('i', [0])\n"
                "fcntl.ioctl(sock.fileno(), termios.TIOCOUTQ, buf)  # == SIOCOUTQ\n"
                "send_q_bytes = buf[0]"
            ),
            "detail": "송신 대기열(Send Queue)이 0으로 비워지지 않고 3초 이상 계속 남아 있는지 여부를 함께 감시합니다.",
        },
        "analysis_usage": {
            "pre_detection": "송신 대기열(Send Queue)에 데이터가 3초 이상 쌓여 있으면 위험 점수를 높임(가중치 15%). 통신 단절 직전 상태를 직접 포착.",
            "post_mortem": "송신 대기열 누적 + 소켓 재전송 증가 → 무선 경로 손실(SCN-01~03), 송신 대기열은 작고 수신 대기열만 급증 → 프로그램 일시 멈춤(SCN-04).",
            "weight": 0.15,
        },
    },
    {
        "id": "M14",
        "key": "recv_q_bytes",
        "name_ko": "소켓 수신 대기열 크기 (Recv Queue / Socket Recv-Q)",
        "name_en": "Socket Receive Queue (Recv-Q Bytes)",
        "abbr": "Recv-Q",
        "layer": LAYER_L34,
        "layer_code": "L3_L4",
        "description": (
            "네트워크를 통해 데이터가 정상적으로 도착했으나, AGV 또는 ACS 통신 프로그램이 다른 작업(예: 자율주행 연산 과부하)으로 바빠서 "
            "아직 읽어가지 못해 수신 대기열(Recv Queue)에 쌓여 있는 데이터양(Bytes)입니다. "
            "이 값이 커진다는 것은 '와이파이는 멀쩡한데 통신 프로그램이 일시 멈춤(응답 지연) 상태'라는 결정적 증거입니다."
        ),
        "unit": "Bytes",
        "thresholds": {"normal": "0 B", "warning": "1 B ~ 2 KB", "critical": "> 2 KB"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 1.0, "critical": 2048.0},
        "display_range": [0, 20000],
        "collection_location": "AGV/AMR, ACS",
        "interval_local": "1s",
        "interval_report": "30초 정기 보고 시 요약 데이터 동봉 전송",
        "recommended_interval": "AGV 및 ACS 내부 1초 단위 상시 기록 / 30초 정기 보고 시 요약 데이터 동봉 전송 (최대 수신 대기량)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (OS 소켓 버퍼 크기 조회)", "ioctl(SIOCINQ/FIONREAD) 시스템 호출 1회"),
        "collection_method": {
            "interface": "AGV 및 ACS ioctl(fd, SIOCINQ / FIONREAD) 또는 ss -tnp (Recv-Q 컬럼)",
            "command": "ss -tnp dst <PEER_IP> | awk 'NR>1{print $2}'   # Recv Queue (Recv-Q)",
            "code_snippet": (
                "buf = array.array('i', [0])\n"
                "fcntl.ioctl(sock.fileno(), termios.FIONREAD, buf)  # == SIOCINQ\n"
                "recv_q_bytes = buf[0]"
            ),
            "detail": "통신 스레드가 멈추더라도 값을 기록할 수 있도록 별도의 가벼운 감시 스레드에서 1초마다 조회합니다.",
        },
        "analysis_usage": {
            "pre_detection": "수신 대기열(Recv Queue)이 2KB를 넘어 계속 쌓이면 프로그램 응답 지연으로 통신이 막히기 전에 경보 발송.",
            "post_mortem": "무선 신호·게이트웨이 응답 정상 + 수신 대기열 급증 + CPU 과부하 → 통신 프로그램 일시 멈춤·시스템 병목(SCN-04)으로 확정.",
            "weight": 0.10,
        },
    },
    # ======================= L7 — Application & Host System (AGV/AMR 및 ACS 수집 4종) =======================
    {
        "id": "M15",
        "key": "hb_delta_sec",
        "name_ko": "30초 보고 도착 간격 및 응답 시간 초과 (Heartbeat Timeout & Interval)",
        "name_en": "Heartbeat Timeout & Report Arrival Interval",
        "abbr": "HB Timeout",
        "layer": LAYER_L7,
        "layer_code": "L7_SYS",
        "description": (
            "ACS 서버가 AGV로부터 정기 상태 보고(Heartbeat)를 실제로 받은 시간 간격(정상 기준: 30.0초) 및 응답 시간 초과(Heartbeat Timeout) 여부입니다. "
            "보고 간격이 30.0초 → 32.5초 → 36.8초처럼 점점 밀리는 현상을 통해 연결이 완전히 끊어지기 전에 불안정한 AGV를 식별하며, "
            "45초 초과 시 Heartbeat Timeout(단절)으로 판정합니다."
        ),
        "unit": "sec",
        "thresholds": {"normal": "29.5 ~ 30.5 초", "warning": "31 ~ 38 초 (지연)", "critical": "> 45 초 (Heartbeat Timeout)"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 30.5, "critical": 45.0},
        "display_range": [0, 60],
        "collection_location": "ACS",
        "interval_local": "1s",
        "interval_report": "매 보고 시",
        "recommended_interval": "ACS 서버에서 매 보고 수신 시 시각 차이 기록 + 1초 주기 Heartbeat Timeout 감시",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (ACS 서버 내부 수신 시각 비교)", "ACS 메모리에서 AGV별 마지막 수신 시각만 비교"),
        "collection_method": {
            "interface": "ACS 소켓 수신 핸들러 타임스탬프 및 1초 주기 Heartbeat Timeout 워치독",
            "command": "(ACS 서버 내부) on_report(agv_id) → hb_delta_sec = now - last_rx[agv_id]",
            "code_snippet": (
                "def on_report(agv_id, now):\n"
                "    hb_delta_sec = now - last_rx.get(agv_id, now)\n"
                "    last_rx[agv_id] = now\n"
                "def watchdog_1s(now):\n"
                "    for agv, t in last_rx.items():\n"
                "        if now - t > 45: mark_heartbeat_timeout(agv)"
            ),
            "detail": "ACS 서버가 1초마다 경과 시간을 확인하여 31초 초과 시 지연(DELAYED), 45초 초과 시 Heartbeat Timeout(DISCONNECTED)으로 판정합니다.",
        },
        "analysis_usage": {
            "pre_detection": "보고 도착 간격이 31초를 넘어 계속 밀리는 AGV를 Heartbeat Timeout 임박 대상으로 조기 표시.",
            "post_mortem": "기존 30초 방식에서 Heartbeat Timeout을 언제 인지했는지 보여주는 기준선으로, 1초 사전 감지가 얼마나 빨리 경보했는지(선행 시간) 비교.",
            "weight": 0.0,
        },
    },
    {
        "id": "M16",
        "key": "reconnect_count",
        "name_ko": "TCP 소켓 연결 상태 및 재연결 횟수 (TCP Socket State & Reconnect)",
        "name_en": "TCP Socket State & Reconnect Reason",
        "abbr": "Socket State",
        "layer": LAYER_L7,
        "layer_code": "L7_SYS",
        "description": (
            "AGV와 ACS 간 TCP 소켓의 현재 연결 상태(TCP Socket State: ESTABLISHED 정상 연결 / SYN_SENT 재연결 시도 / CLOSE_WAIT·TIME_WAIT·FIN_WAIT 종료 대기)와 "
            "다시 연결을 맺은 횟수(시간당) 및 끊김 사유 코드(ETIMEDOUT 응답 시간 초과 / ECONNRESET 강제 리셋)입니다. "
            "끊김 원인이 무선 시간 초과인지 프로그램 종료에 의한 상태 전환인지 구분합니다."
        ),
        "unit": "State / count/hr",
        "thresholds": {"normal": "ESTABLISHED (0회/시간)", "warning": "SYN_SENT / 재연결 1~2회", "critical": "CLOSE_WAIT·TIMEOUT (≥ 3회/시간)"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 0.5, "critical": 2.5},
        "display_range": [0, 10],
        "collection_location": "AGV/AMR, ACS",
        "interval_local": "Event 즉시",
        "interval_report": "이벤트 발생 시",
        "recommended_interval": "1초 주기 TCP Socket State 확인 및 연결 끊김·재연결 발생 즉시 AGV·ACS 양쪽 기록",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (평시) / 재연결 시 수십 Bytes", "커널 소켓 상태(tcpi_state) 및 연결·종료 에러 코드 기록"),
        "collection_method": {
            "interface": "AGV 및 ACS getsockopt(TCP_INFO) tcpi_state / ss -tnp 및 소켓 예외 코드",
            "command": "ss -tnp dst <PEER_IP> | awk 'NR>1{print $1}'   # TCP Socket State (ESTAB, SYN-SENT, CLOSE-WAIT 등)",
            "code_snippet": (
                "try:\n"
                "    sock.sendall(report)\n"
                "except ConnectionResetError: reason = 'ECONNRESET'\n"
                "except (TimeoutError, socket.timeout): reason = 'ETIMEDOUT'\n"
                "reconnect_log.append({'ts': now, 'state': tcp_state, 'reason': reason}); reconnect_count += 1"
            ),
            "detail": "TCP Socket State 변화(ESTABLISHED → SYN_SENT/CLOSED)와 끊김 사유 코드를 기록하고, 재연결 직후 끊김 전후 120초 상세 기록을 ACS로 일괄 전송합니다.",
        },
        "analysis_usage": {
            "pre_detection": "TCP Socket State가 CLOSE_WAIT에 머물거나 최근 1시간 내 재연결이 3회 이상 발생한 AGV는 사전 경보 기준을 더 민감하게 적용.",
            "post_mortem": "ETIMEDOUT + SYN_SENT 반복 → 무선 구간 단절, CLOSE_WAIT/ECONNRESET → 통신 프로그램 종료·강제 리셋으로 원인을 명확히 구분.",
            "weight": 0.0,
        },
    },
    {
        "id": "M17",
        "key": "cpu_load",
        "name_ko": "AGV 컴퓨터(CPU) 사용률 (AGV CPU & System Load)",
        "name_en": "AGV Host CPU & Communication Interrupt Load",
        "abbr": "CPU",
        "layer": LAYER_L7,
        "layer_code": "L7_SYS",
        "description": (
            "AGV 내부 온보드 컴퓨터의 연산 장치(CPU) 사용률과 네트워크 수신 처리(SoftIRQ) 부하입니다. "
            "자율주행(라이다·SLAM) 연산이 폭주해 CPU 사용률이 90%를 넘으면 통신 프로그램이 실행 순서를 얻지 못해 일시 멈춤(응답 지연) 상태에 빠지고, "
            "와이파이가 정상이어도 30초 보고가 끊깁니다. 로봇 내부 과부하와 무선 문제를 구분하는 핵심 지표입니다."
        ),
        "unit": "%",
        "thresholds": {"normal": "< 60 %", "warning": "60 ~ 85 %", "critical": "> 85 %"},
        "threshold_levels": {"direction": "lower_is_better", "warning": 60.0, "critical": 85.0},
        "display_range": [0, 100],
        "collection_location": "AGV/AMR",
        "interval_local": "5s",
        "interval_report": "30초 정기 보고 시 요약 데이터 동봉 전송",
        "recommended_interval": "AGV 내부 5초 주기 기록 (위험 시 1초) / 30초 정기 보고 시 요약 데이터 동봉 전송 (최대 CPU 사용률)",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (AGV 내부 OS 상태 파일 읽기)", "AGV의 /proc/stat 및 /proc/softirqs 텍스트 파일 2개만 읽음"),
        "collection_method": {
            "interface": "AGV Linux /proc/stat, /proc/softirqs (NET_RX 행)",
            "command": "head -1 /proc/stat ; grep NET_RX /proc/softirqs",
            "code_snippet": (
                "def cpu_pct(prev, cur):\n"
                "    idle_d = (cur[3] + cur[4]) - (prev[3] + prev[4])\n"
                "    tot_d  = sum(cur) - sum(prev)\n"
                "    return 100.0 * (1 - idle_d / max(tot_d, 1))\n"
                "cur = list(map(int, open('/proc/stat').readline().split()[1:]))"
            ),
            "detail": "전체 CPU 사용률과 통신 수신 처리(NET_RX SoftIRQ) 비중을 함께 기록하여 연산 과부하를 감시합니다.",
        },
        "analysis_usage": {
            "pre_detection": "CPU 사용률이 85%를 넘고 수신 대기열(M14)이 쌓이기 시작하면 통신 프로그램 일시 멈춤 사전 경보 발송.",
            "post_mortem": "CPU > 92% + 수신 대기열 급증 + 무선 신호 정상 → 통신 프로그램 일시 멈춤·시스템 과부하(SCN-04)로 확정 (불필요한 무선 공사 방지).",
            "weight": 0.10,
        },
    },
    {
        "id": "M18",
        "key": "pose_xy",
        "name_ko": "AGV 주행 위치 좌표 및 속도 (Position & Speed)",
        "name_en": "AGV Position (X, Y) & Speed",
        "abbr": "Position",
        "layer": LAYER_L7,
        "layer_code": "L7_SYS",
        "description": (
            "통신 상태를 측정한 순간의 AGV 공장 내 위치 좌표(X, Y)와 주행 속도(m/s)입니다. "
            "모든 무선 품질 기록에 위치 좌표를 함께 남겨 두면 '공장 어느 지점에서' 신호가 약해지고 끊기는지 지도 위에 바로 표시할 수 있어, "
            "상습 전파 음영 구역 지도(히트맵)를 자동으로 만들고 기지국 증설 위치를 정확히 선정할 수 있습니다."
        ),
        "unit": "m, m/s",
        "thresholds": {"normal": "일반 구역 정상 주행 (0.5 ~ 1.5 m/s)",
                       "warning": "상습 전파 음영·간섭 구역(위험 점수 ≥ 45) 진입",
                       "critical": "음영 구역 내 통신 끊김 반복 지점"},
        "threshold_levels": None,
        "display_range": None,
        "collection_location": "AGV/AMR, ACS",
        "interval_local": "1s",
        "interval_report": "30초 정기 보고 시 요약 데이터 동봉 전송",
        "recommended_interval": "AGV 내부 1초 단위 상시 기록장 (통신 지표와 함께 좌표 기록) / 30초 정기 보고 시 기존 위치 보고 활용",
        "system_load": _load(_LOAD_VERY_LOW, "0 B/s (기존 주행 제어 좌표 그대로 활용)",
                             "AGV 주행 제어 모듈이 이미 계산한 현재 좌표와 ACS가 수신한 위치 보고를 그대로 참조", cpu="≈ 0%"),
        "collection_method": {
            "interface": "AGV 주행 제어 모듈 공유 메모리 (ROS /amcl_pose, /odom) 및 ACS 위치 보고 테이블",
            "command": "rostopic echo -n1 /amcl_pose   # AGV 내부 주행 좌표 참조",
            "code_snippet": (
                "def on_pose(msg):\n"
                "    latest_pose.update(x=msg.pose.pose.position.x,\n"
                "                       y=msg.pose.pose.position.y)\n"
                "# 1초 기록 시 local_record_book.append({**net_metrics, **latest_pose})"
            ),
            "detail": "공장 바닥을 격자 구역으로 나누어 각 위치별 최저 신호 세기·최고 위험 점수를 집계하면 전파 음영 지도가 완성됩니다.",
        },
        "analysis_usage": {
            "pre_detection": "과거 통신 불안정이 반복된 상습 음영 좌표에 AGV가 접근하면 진입 전에 미리 감속 또는 기지국 전환 유도.",
            "post_mortem": "끊김 발생 좌표를 공장 2D 지도에 표시하여 전파 음영 구역(SCN-02) 위치를 정확히 특정.",
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
            return "경미한 통신 품질 변동 — AGV 내부 1초 상시 기록장 집중 감시"
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
        return "통신 프로그램 일시 멈춤(응답 지연) 및 CPU 과부하 의심 (무선 신호 정상)"
    if rf_ok and util > 65:
        return "무선 채널 혼잡·과부하 의심 (채널 사용률 과다, 응답 시간·흔들림 급증)"
    if roaming > 200:
        return "기지국(AP) 전환 지연·실패 (변경 소요 시간 > 200ms)"
    if rssi >= -70 and snr < 18:
        return "설비 전파 간섭(EMI) 의심 — 주변 잡음 상승으로 신호 품질 저하"
    if slope <= -2.5 or rssi <= -80:
        return "전파 음영 구역 진입 — 수신 신호 세기 급락"
    if rssi <= -70:
        return "기존 기지국 고착(Sticky Client) 의심 — 기지국 전환 기준 미도달로 신호 약화"
    dominant = max(comps, key=comps.get)
    return {
        "rf_signal": "무선 신호 품질 저하",
        "mac_contention": "무선 구간 재시도 및 채널 혼잡 증가",
        "transport_tcp": "소켓 재전송 급증 — 통신 시간 초과 임박",
        "socket_buffer": "소켓 대기열 적체 — 정기 보고 지연 임박",
    }[dominant]


def compute_risk_score(sample: Dict[str, Any], prev_score: Optional[float] = None,
                       alpha: Optional[float] = None) -> Dict[str, Any]:
    """Multi-metric pre-detection risk score (0..100) from one 1-second sample.

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
    "SCN-01": "기지국(AP) 전환 지연 / 기존 AP 고착 (Sticky Client)",
    "SCN-02": "물리적 전파 음영 구역 및 설비 전파 간섭 (Dead Zone / EMI)",
    "SCN-03": "기지국(AP) 과부하 및 동일 채널 혼잡 (Channel Contention)",
    "SCN-04": "통신 프로그램 일시 멈춤(응답 지연) 및 AGV CPU 과부하",
    "NORMAL": "정상 — 장애 징후 없음",
}

_SCENARIO_ACTIONS: Dict[str, List[str]] = {
    "SCN-01": [
        "AGV 무선 랜카드의 기지국 전환(로밍) 시작 기준값을 -75dBm → -70dBm으로 높여 신호가 너무 약해지기 전에 미리 갈아타도록 설정",
        "무선 기지국(AP)에 고속 로밍 기능(802.11k/v/r)을 켜서 기지국 변경 소요 시간을 50ms 이내로 단축",
        "ACS가 사전 경고 알림(위험 점수 ≥ 70)을 받으면 해당 구간 AGV에 감속 지시를 내리고 인접 기지국 전환을 유도",
    ],
    "SCN-02": [
        "공장 2D 음영 구역 지도에 표시된 철제 선반·구조물 구간에 보조 기지국(AP) 또는 지향성 안테나 추가 설치",
        "용접기·인버터 설비 주변에서는 간섭에 약한 2.4GHz 대신 5GHz 전용 채널로 고정하고 전파 차폐·필터 적용",
        "음영 구간 진입 전 AGV가 작업 명령을 미리 받아 두고 구간 통과 후 보고하도록 경로 기반 통신 제어 적용",
    ],
    "SCN-03": [
        "한 기지국(AP)에 몰려 있는 일반 업무용 단말(스캐너·태블릿 등)을 인접 기지국으로 분산하고 AGV 전용 무선망(SSID) 분리",
        "채널 폭을 20MHz로 최적화하고 인접 기지국끼리 서로 다른 채널을 쓰도록 재배치하여 채널 겹침 해소",
        "불필요한 전체 알림 패킷(브로드캐스트/멀티캐스트)을 줄이고 AGV 제어 트래픽에 최우선 순위(QoS) 부여",
    ],
    "SCN-04": [
        "무선 네트워크 문제가 아닌 'AGV/ACS 통신 프로그램 일시 멈춤(응답 지연)'으로 판정 — 불필요한 무선 기지국 공사 중단 및 S/W 담당자 이관",
        "AGV 자율주행(SLAM·라이다) 연산과 통신 보고 프로그램이 서로 다른 CPU 코어를 쓰도록 분리(taskset)하여 통신 멈춤 방지",
        "통신 소켓을 비동기(Non-blocking) 방식으로 개선하고 수신 대기열(Recv-Q)이 2KB 이상 쌓이면 즉시 복구하는 감시 로직 추가",
    ],
    "NORMAL": [
        "별도 조치 불필요 — 평시 30초 정기 보고 시 요약 데이터 동봉 전송 및 AGV 내부 1초 상시 기록 유지",
        "주기적으로 공장 2D 전파 음영 지도를 점검하여 품질 저하 구역 추이 확인",
        "사전 감지 위험 점수 기준값(45점 주의 / 70점 사전 경고 / 85점 단절) 월간 점검",
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
            _chk("기지국(AP) 변경 소요 시간 지연", roam, "> 200 ms", roam > 200, 0.35),
            _chk("기지국 확인 신호(비콘) 놓침 급증", bl, "≥ 5 회/초", bl >= 5, 0.20),
            _chk("수신 신호 세기 기준 이하 하락", rssi_min, "≤ -76 dBm", rssi_min <= -76, 0.20),
            _chk("주변 무선 잡음 정상 (전파 간섭 없음)", noise_max, "≤ -88 dBm", noise_max <= -88, 0.15),
            _chk("무선 채널 혼잡도 정상 (과부하 없음)", util, "< 65 %", util < 65, 0.10),
        ],
        "SCN-02": [
            _chk("수신 신호 급락 또는 신호대잡음비 붕괴", f"{rssi_min:.0f} dBm / {snr_min:.0f} dB",
                 "RSSI ≤ -82 dBm 또는 SNR ≤ 12 dB", rssi_min <= -82 or snr_min <= 12, 0.25),
            _chk("무선 구간 재시도 비율 폭증", retry, "> 35 %", retry > 35, 0.20),
            _chk("무선 연결 속도 최저 수준 강등", phy_min, "≤ 12 Mbps", phy_min <= 12, 0.15),
            _chk("주변 무선 잡음 상승 (설비 전파 간섭)", noise_max, "≥ -88 dBm", noise_max >= -88, 0.15),
            _chk("기지국 변경 없음 (동일 AP 유지)", roam, "< 200 ms", roam < 200, 0.15),
            _chk("신호 세기 급격한 하락 속도", slope, "≤ -2.5 dBm/초", slope <= -2.5, 0.10),
        ],
        "SCN-03": [
            _chk("수신 신호 세기 양호 유지", rssi_min, "≥ -68 dBm", rssi_min >= -68, 0.20),
            _chk("신호 대 잡음 비율 양호 유지", snr_min, "≥ 22 dB", snr_min >= 22, 0.10),
            _chk("무선 채널 혼잡도 과다 (채널 붐빔)", util, "> 75 %", util > 75, 0.30),
            _chk("게이트웨이 응답 시간 / 흔들림 급증", f"{gw:.0f} ms / {jit:.0f} ms", "응답 ≥ 80 ms 또는 흔들림 ≥ 40 ms",
                 gw >= 80 or jit >= 40, 0.25),
            _chk("소켓(TCP) 재전송 다발", rtx, "≥ 3 회/초", rtx >= 3, 0.15),
        ],
        "SCN-04": [
            _chk("무선 신호 세기·품질 정상", f"{rssi_min:.0f} dBm / {snr_min:.0f} dB", "RSSI ≥ -66 dBm, SNR ≥ 25 dB",
                 rssi_min >= -66 and snr_min >= 25, 0.20),
            _chk("게이트웨이 응답 시간 정상 (무선 구간 정상)", gw, "< 15 ms", gw < 15, 0.20),
            _chk("소켓 수신 대기열(Recv-Q) 데이터 쌓임", rq, "> 2048 Bytes", rq > 2048, 0.30),
            _chk("AGV 컴퓨터(CPU) 사용률 과부하", cpu, "> 92 %", cpu > 92, 0.30),
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
        1: ("무선 전파 신호 양호 → 전파 음영·설비 간섭 가능성 배제, 다음 단계(채널 혼잡·프로그램 멈춤) 확인"
            if rf_pass else
            ("신호 세기는 유지되나 잡음 상승으로 품질 저하 → 설비 전파 간섭(EMI) 후보" if rssi_min > -75 else
             "신호 세기 기준 이하 하락 → 전파 음영 구역(SCN-02) 또는 기지국 전환 지연(SCN-01) 후보, 2단계에서 구분")),
        2: ("기지국 변경 정상 또는 미발생 → 기지국 전환 지연 배제"
            if roam_pass else
            "기지국 변경 시간 초과·확인 신호 놓침 급증 → 기존 AP를 놓지 못하다 뒤늦게 전환 실패 (SCN-01 확정)"),
        3: ("무선 채널 혼잡도·게이트웨이 응답 정상 → 채널 과부하 배제"
            if ch_pass else
            ("신호는 좋은데 채널 혼잡도·응답 시간만 급증 → 동일 채널 기기 과밀·과부하 (SCN-03 확정)" if rf_pass else
             "전파 약화로 인한 재시도 누적 지연 — 근본 원인은 1~2단계의 전파·로밍 문제")),
        4: ("AGV 컴퓨터(CPU)·소켓 대기열 정상 → 통신 프로그램 문제 배제"
            if host_pass else
            ("무선 신호와 게이트웨이 응답은 완벽한데 CPU 과부하·수신 대기열(Recv-Q) 적체 발생 → 통신 프로그램 일시 멈춤 (SCN-04 확정, 무선 공사 불필요)"
             if (rf_pass and ch_pass) else "시스템 부하 동반 상승 — 무선 원인과 함께 점검 필요")),
    }
    steps = [
        {"step": 1, "question": "무선 전파 신호(신호 세기 > -75dBm, 신호대잡음비 > 17dB)가 양호했는가?",
         "observation": f"최저 신호 {rssi_min:.0f} dBm, 최저 SNR {snr_min:.0f} dB, 최대 잡음 {noise_max:.0f} dBm",
         "result": "PASS" if rf_pass else "FAIL", "implication": impl[1]},
        {"step": 2, "question": "기지국(AP) 변경이 150ms 이내에 끝나고 확인 신호 놓침이 없었는가?",
         "observation": f"기지국 변경 최대 {roam:.0f} ms, 확인 신호 놓침 최대 {bl:.0f} 회/초",
         "result": "PASS" if roam_pass else "FAIL", "implication": impl[2]},
        {"step": 3, "question": "무선 채널 혼잡도(≤ 65%)와 게이트웨이 응답 시간(≤ 50ms)이 정상이었는가?",
         "observation": f"채널 혼잡도 최대 {util:.0f} %, 게이트웨이 응답 최대 {gw:.0f} ms, 흔들림 최대 {jit:.0f} ms",
         "result": "PASS" if ch_pass else "FAIL", "implication": impl[3]},
        {"step": 4, "question": "AGV 컴퓨터(CPU ≤ 85%)와 소켓 수신 대기열(Recv-Q ≤ 2KB)이 정상이었는가?",
         "observation": f"CPU 최대 {cpu:.0f} %, 수신 대기열(Recv-Q) 최대 {rq:.0f} Bytes",
         "result": "PASS" if host_pass else "FAIL", "implication": impl[4]},
    ]
    return steps


def classify_rca(samples_window: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Classify the root cause of an anomaly/disconnection from a telemetry window."""
    window = [s for s in (samples_window or []) if isinstance(s, dict)]
    if not window:
        return {
            "scenario_code": "NORMAL", "title": SCENARIO_TITLES["NORMAL"], "confidence": 0.0,
            "scores": {}, "evidence": [], "decision_tree": [], "anomaly_detected": False,
            "root_cause_summary": "분석할 상세 기록이 없습니다.", "recommended_actions": _SCENARIO_ACTIONS["NORMAL"],
            "stats": {},
        }
    st = _window_stats(window)

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
        summary = ("구간 내 위험 점수와 18종 상태 항목이 모두 정상 범위입니다." if not anomaly else
                   "일부 이상 징후가 있으나 4대 장애 유형 기준에는 아직 도달하지 않았습니다.")
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
        return (f"신호 세기가 {f('rssi_max', -58):.0f} → {f('rssi_min'):.0f} dBm으로 약해지는 동안 기존 기지국(AP)을 놓지 못했고, "
                f"뒤늦은 기지국 변경 시도에서 {f('roaming_max_ms'):.0f} ms가 걸리며(확인 신호 놓침 최대 {f('beacon_loss_max'):.0f}회/초) "
                f"소켓 재전송 끝에 연결이 끊어졌습니다. 주변 잡음과 채널 혼잡도는 정상이어서 간섭·과부하는 아닌 것으로 판별됩니다.")
    if code == "SCN-02":
        return (f"철제 선반 음영 및 용접 설비 구역 진입으로 신호 세기가 {f('rssi_min'):.0f} dBm, 신호대잡음비가 {f('snr_min'):.0f} dB"
                f"(주변 잡음 최대 {f('noise_max'):.0f} dBm)까지 급락하여 연결 속도가 {f('phy_min'):.0f} Mbps로 떨어지고 "
                f"무선 재시도율이 {f('l2_retry_max'):.0f}%까지 폭증했습니다. 기지국 변경 없이 전파 자체가 막힌 음영·간섭 장애입니다.")
    if code == "SCN-03":
        return (f"수신 신호({f('rssi_min'):.0f} dBm)와 신호대잡음비({f('snr_min'):.0f} dB)는 양호했으나 무선 채널 혼잡도가 "
                f"{f('channel_util_max'):.0f}%까지 치솟아 전송 순서를 얻지 못했고, 게이트웨이 응답 {f('gw_rtt_max'):.0f} ms·"
                f"흔들림 {f('jitter_max'):.0f} ms·소켓 재전송 {f('tcp_retrans_max'):.0f}회/초가 이어져 연결이 끊어진 채널 과부하 장애입니다.")
    if code == "SCN-04":
        return (f"수신 신호 {f('rssi_min'):.0f} dBm·게이트웨이 응답 {f('gw_rtt_max'):.1f} ms로 무선 구간은 정상이었으나, "
                f"AGV 컴퓨터(CPU) 사용률이 {f('cpu_max'):.0f}%까지 치솟아 통신 프로그램이 일시 멈춤(응답 지연) 상태에 빠졌고 "
                f"소켓 수신 대기열(Recv-Q)에 {f('recv_q_max'):.0f} Bytes가 쌓여 30초 정기 보고가 중단되었습니다.")
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
_NOISE_SIGMA: Dict[str, tuple] = {
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
                 phy_factor=None, path=None, bssids=("AP-ZONE-A", "AP-ZONE-A"), events=None, notes=None):
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

    lo, hi = 0.25, 12.0
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
    last_rx = TIMELINE_START - ((TIMELINE_START - REPORT_TICK_PHASE) % 30) - 30
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

    prev_tick_idx = 0
    for i, row in enumerate(rows):
        if row["acs_report_status"] in ("OK", "DELAYED"):
            seg = rows[max(0, prev_tick_idx + 1 if prev_tick_idx else max(0, i - 29)): i + 1]
            row["piggyback_summary"] = _piggyback(seg)
            prev_tick_idx = i

    notes = {
        cfg.onset: "통신 품질 저하 시작 — AGV 내부 1초 단위 상시 기록장에는 남지만 30초 정기 보고에는 아직 드러나지 않음",
        pre: f"사전 감지 경보 (위험도 ≥ 45) — 상시 기록장 상세 구간 보존 잠금, 끊김 {cfg.lead}초 전 조기 감지",
        0: "ACS 소켓 연결 끊김 — 정기 보고·제어 중단 (재전송 시간 초과)",
        REPORT_TICK_PHASE: "정기 30초 상태 보고 누락 (TIMEOUT_MISSED) — 기존 30초 방식에서 처음 이상을 알아채는 시점",
        RECOVERY_OFFSET: (
            f"소켓 재연결 완료 + 끊김 전후 상세 기록(120초) 일괄 전송 → 4대 원인 자동 판별 "
            f"(기존 방식은 '보고 간격 {RECOVERY_OFFSET - (REPORT_TICK_PHASE - 30)}초 지연' 1건만 남음)"
        ),
    }
    for t in sorted(ticks):
        if t < 0 and t not in notes:
            notes[t] = "정기 30초 상태 보고 (OK) — 30초 요약 데이터 동봉 전송"
    if first_70 is not None and first_70 not in notes:
        notes[first_70] = "위험도 ≥ 70 — ACS로 [사전 경고 알림] 즉시 발송 (AGV 감속 및 기지국 전환 유도 가능 시점)"
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


def _disc_scn01(t: int, worst: Dict[str, float], base: Dict[str, float]) -> Dict[str, float]:
    if t < 15:
        return {
            "rssi": -83.0, "noise_floor": -95.0, "l2_retry_rate": 48.0, "beacon_loss": 10.0,
            "roaming_ms": 1480.0 if t == 0 else 0.0, "channel_util": 30.0, "gw_rtt_ms": ICMP_TIMEOUT_MS,
            "jitter_ms": 90.0, "tcp_retrans": 6.0, "tcp_srtt_ms": 300.0,
            "send_q_bytes": min(SEND_Q_CAP, worst["send_q_bytes"] + 650.0 * (t + 1)),
            "recv_q_bytes": 0.0, "cpu_load": 44.0, "softirq_pct": 5.0,
        }
    return {
        "rssi": -57.0, "noise_floor": -95.0, "l2_retry_rate": 4.0, "beacon_loss": 0.0,
        "roaming_ms": 310.0 if t == 15 else 0.0, "channel_util": 29.0, "gw_rtt_ms": 4.2,
        "jitter_ms": 2.5, "tcp_retrans": 2.0, "tcp_srtt_ms": 300.0, "send_q_bytes": float(SEND_Q_CAP),
        "recv_q_bytes": 0.0, "cpu_load": 44.0, "softirq_pct": 4.0,
    }


def _disc_scn02(t: int, worst: Dict[str, float], base: Dict[str, float]) -> Dict[str, float]:
    q = max(0.0, min(1.0, (t - 8) / 8.0))
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
    q = max(0.0, min(1.0, (t - 11) / 6.0))
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
        "recv_q_bytes": 16384.0 + 120.0 * t,
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
        path=((52.0, 14.0), (0.55, 0.0)),
        bssids=("AP-ZONE-A (02:AC:00:00:00:A1)", "AP-ZONE-B (02:AC:00:00:00:B1)"),
        events={-3: {"roaming_ms": 0.0}},
        notes={-6: "신호 세기 -76dBm까지 약해졌으나 기존 기지국(AP-ZONE-A)을 놓지 못함 (Sticky Client)",
               -2: "뒤늦은 기지국 변경 시도 시작 (AP-ZONE-B로 전환 시도, 고속 로밍 미적용)",
               15: "새 기지국(AP-ZONE-B) 연결 완료 (재인증 310ms 소요) — 소켓 복구는 +18s에 완료"},
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
        path=((18.0, 40.0), (0.9, 0.12)),
        bssids=("AP-ZONE-C (02:AC:00:00:00:C1)", "AP-ZONE-C (02:AC:00:00:00:C1)"),
        notes={-10: "용접 설비 가동 + 철제 선반 가림 구간 진입 — 주변 잡음 상승과 신호 급락 동시 발생",
               -5: "무선 연결 속도가 최저 수준(6~13Mbps)으로 떨어지고 무선 재시도율 40% 돌파",
               12: "음영·간섭 구역 통과 — 무선 신호 회복 시작"},
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
        phy_factor=lambda s: 1.0 - 0.55 * (s ** 1.2),
        path=((24.0, 12.0), (0.35, 0.05)),
        bssids=("AP-ZONE-B (02:AC:00:00:00:B1)", "AP-ZONE-B (02:AC:00:00:00:B1)"),
        notes={-30: "출하장 작업 교대 시간 — 주변 무선 단말 40여 대가 같은 채널을 동시에 사용하여 혼잡도 상승",
               -8: "신호 세기(-60dBm)는 좋은데 채널 혼잡도가 85%를 넘으며 응답 지연·흔들림 100ms 돌파",
               11: "주변 트래픽 분산 완료 — 채널 혼잡도 정상화 시작"},
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
        path=((78.0, 46.0), (0.25, 0.0)),
        bssids=("AP-ZONE-D (02:AC:00:00:00:D1)", "AP-ZONE-D (02:AC:00:00:00:D1)"),
        notes={-30: "자율주행(라이다·SLAM) 연산 폭주 — AGV 컴퓨터(CPU) 사용률 급상승 시작",
               -8: "CPU 95% 초과로 통신 프로그램 일시 멈춤(응답 지연) — 수신 대기열(Recv-Q) 급증 (무선 신호 -57dBm·응답 5ms 정상)",
               17: "감시 타이머가 멈춘 통신 프로그램을 자동 재시작하여 수신 대기열 해소"},
    ),
}

_SCENARIO_TEXT: Dict[str, Dict[str, Any]] = {
    "SCN-01": {
        "title": "기지국(AP) 전환 지연 / 기존 AP 고착 (Sticky Client)",
        "subtitle": "기지국 경계 구간에서 약해진 기존 AP를 놓지 않다가 뒤늦게 갈아타며 소켓 연결 끊김",
        "target_agv": "AGV-02",
        "zone": "ZONE-A → ZONE-B 경계 통로 (AP-ZONE-A ↔ AP-ZONE-B 전환 구간)",
        "legacy_30s_view": (
            "기존 30초 정기 보고 방식에서는 끊김 24초 전(T-24s) 보고가 '정상(OK)'으로 도착한 뒤, "
            "다음 예정 시각(T+6s)에 보고가 오지 않아서야 비로소 이상을 알아챕니다. 그마저도 T+18s에 다시 연결되면 "
            "'보고 간격 42초 지연' 1건으로만 남고, 그 사이 신호가 어떻게 약해졌는지·기지국 변경이 얼마나 걸렸는지 기록이 전혀 없어 "
            "원인을 알 수 없는 '일시적 통신 불량'으로 처리됩니다."
        ),
        "hybrid_1s_view": (
            "AGV 내부 1초 단위 상시 기록장(최근 5분 순환 보관)은 T-55s부터 신호 세기가 -58 → -80dBm으로 약해지는데도 "
            "기지국 주소(BSSID)가 바뀌지 않는 현상을 빠짐없이 기록합니다. 끊김 18초 전(T-18s)에 위험 점수가 45점을 넘어 사전 감지 경보가 켜지고, "
            "위험도 70점 돌파 시 ACS로 [사전 경고 알림]을 즉시 보내 감속 및 기지국 전환을 유도합니다. "
            "재연결 후에는 끊김 전후 120초 상세 기록을 보내 '기지국 변경 1,480ms 지연'이 원인임을 자동으로 밝혀냅니다."
        ),
        "root_cause": (
            "AGV 무선 랜카드의 기지국 전환 기준값이 -80dBm으로 너무 낮게 설정되어 있어, 옆 기지국(AP-ZONE-B, -57dBm) 신호가 훨씬 강한데도 "
            "멀어진 기존 기지국(AP-ZONE-A, -76 ~ -80dBm)을 끝까지 붙잡고 있었습니다. 결국 신호가 거의 끊긴 뒤에야 기지국을 갈아타려 했고, "
            "고속 로밍(802.11r)이 꺼져 있어 재인증에 1.48초가 걸리면서 그 사이 소켓 통신이 끊어졌습니다."
        ),
    },
    "SCN-02": {
        "title": "물리적 전파 음영 구역 및 설비 전파 간섭 (Dead Zone / EMI)",
        "subtitle": "철제 선반 가림 구간 진입과 용접 설비 가동이 겹치며 무선 신호가 급락해 통신 단절",
        "target_agv": "AGV-05",
        "zone": "ZONE-C 프레스·용접 라인 (철제 선반 통로 + 용접 전파 간섭 구역)",
        "legacy_30s_view": (
            "끊김 24초 전(T-24s) 정기 보고 때는 AGV가 아직 음영 구역 밖이어서 '정상'으로 보입니다. "
            "이후 철제 선반 사이로 들어가며 15초 만에 신호가 끊겼지만 30초 보고에는 아무 기록이 남지 않고, "
            "기지국 전환 실패(SCN-01)나 채널 혼잡(SCN-03)과 구분할 방법이 없어 엉뚱한 조치를 반복하게 됩니다."
        ),
        "hybrid_1s_view": (
            "AGV 내부 1초 단위 상시 기록장이 신호 세기의 급격한 추락(초당 -2.5dBm 이하), 주변 잡음 수치 상승(신호대잡음비 붕괴), "
            "연결 속도 6Mbps 강등, 무선 재시도율 50% 폭증을 주행 위치 좌표(M18)와 함께 기록합니다. 끊김 16초 전(T-16s)에 사전 경고를 발송하며, "
            "사후 분석 시 '기지국 변경 없이 특정 좌표에서 전파 자체가 막혔음'을 자동으로 판별해 2D 지도에 음영 구역으로 표시합니다."
        ),
        "root_cause": (
            "ZONE-C의 대형 철제 선반 통로가 기지국 전파를 가로막아 수신 신호가 -83dBm까지 급락했고, 동시에 옆 용접 로봇이 가동되면서 "
            "주변 무선 잡음 수치가 -95 → -87dBm으로 치솟아 신호대잡음비(SNR)가 무너졌습니다. 무선 랜카드가 최저 속도(6Mbps)까지 낮추며 "
            "재시도를 반복했으나(재시도율 50% 초과) 갈아탈 인접 기지국도 없어 결국 소켓 통신이 끊어졌습니다."
        ),
    },
    "SCN-03": {
        "title": "기지국(AP) 과부하 및 동일 채널 혼잡 (Channel Contention)",
        "subtitle": "무선 신호 세기는 좋지만 한 채널에 기기가 너무 많이 몰려(혼잡도 90% 초과) 응답 지연으로 단절",
        "target_agv": "AGV-03",
        "zone": "ZONE-B 출하장 도크 (AP-ZONE-B, 작업용 스캐너·태블릿 밀집 구역)",
        "legacy_30s_view": (
            "현장에서는 신호 안테나 세기(-60dBm)만 보고 '와이파이는 빵빵한데 왜 끊기지?'라며 원인을 찾지 못합니다. "
            "30초 정기 보고에는 채널이 얼마나 붐볐는지(혼잡도)나 응답 시간이 얼마나 흔들렸는지 정보가 없으므로, "
            "무선 문제가 아닌 ACS 서버 문제로 오해하여 엉뚱한 부서로 책임을 넘기게 됩니다."
        ),
        "hybrid_1s_view": (
            "AGV 내부 1초 단위 상시 기록장과 30초 정기 보고 시 요약 데이터 동봉 전송을 통해 '신호 세기(-60dBm)는 좋지만 무선 채널 혼잡도가 "
            "93%까지 치솟고 게이트웨이 응답 시간(185ms)과 흔들림(115ms)이 급증했다'는 사실을 명확히 보여줍니다. "
            "끊김 15초 전(T-15s)에 사전 경고를 보내 덜 붐비는 인접 기지국으로 전환하도록 유도할 수 있습니다."
        ),
        "root_cause": (
            "출하장 교대 시간에 작업자용 무선 스캐너·태블릿 40여 대가 한 기지국(AP-ZONE-B)과 동일 주파수 채널에 몰리면서 "
            "무선 통로 사용률(채널 혼잡도)이 93%에 달했습니다. 마치 꽉 막힌 도로처럼 AGV가 데이터를 보낼 차례를 얻지 못해 "
            "게이트웨이 응답 시간이 185ms까지 밀리고 소켓 재전송이 반복되다 연결이 끊어졌습니다. 기지국 추가가 아니라 채널 분산이 필요한 사례입니다."
        ),
    },
    "SCN-04": {
        "title": "통신 프로그램 일시 멈춤(응답 지연) 및 AGV CPU 과부하",
        "subtitle": "와이파이 신호와 무선 응답 시간은 100% 정상이지만 AGV CPU 폭주로 통신 프로그램이 멈춰 보고 중단",
        "target_agv": "AGV-04",
        "zone": "ZONE-D 고밀도 팔레트 정밀 주행 구역 (AP-ZONE-D 중심부)",
        "legacy_30s_view": (
            "기존 30초 방식에서는 ACS 화면에 그저 '30초 보고 미수신(연결 끊김)'으로만 뜨기 때문에, 현장에서는 무조건 "
            "'공장 와이파이가 또 끊겼다'고 판단하여 수천만 원짜리 무선 기지국(AP) 추가 공사를 벌입니다. "
            "하지만 실제 원인은 AGV 내부 프로그램 멈춤이므로 공사를 한 뒤에도 똑같은 끊김이 그대로 반복됩니다."
        ),
        "hybrid_1s_view": (
            "AGV 내부 1초 단위 상시 기록장을 확인하면 수신 신호(-57dBm)와 게이트웨이 응답 시간(5ms)이 처음부터 끝까지 완벽히 정상인데도, "
            "AGV 컴퓨터(CPU) 사용률이 98%로 치솟고 소켓 수신 대기열(Recv-Q)에 읽지 못한 데이터가 16KB 이상 쌓인 것이 한눈에 드러납니다. "
            "끊김 14초 전(T-14s)에 이를 사전 감지하며, 사후 분석에서도 '무선 문제가 아닌 통신 프로그램 일시 멈춤'으로 즉시 판정해 불필요한 무선 공사를 막아줍니다."
        ),
        "root_cause": (
            "복잡한 팔레트 구역에서 AGV 자율주행(라이다·SLAM) 연산량이 폭증해 온보드 컴퓨터의 CPU 사용률이 98%에 도달했습니다. "
            "그 여파로 통신 보고 프로그램이 CPU 실행 순서를 얻지 못해 일시 멈춤(응답 지연) 상태에 빠졌고, ACS가 보낸 데이터가 "
            "소켓 수신 대기열(Recv-Q)에 가득 쌓이면서 30초 정기 보고가 중단되었습니다. 무선 장비는 100% 정상이었으며, 자율주행 연산과 통신 프로그램의 CPU 코어를 분리해야 해결됩니다."
        ),
    },
}


def _signature_strings(code: str, st: Dict[str, Any]) -> List[str]:
    g = lambda k: st.get(k) if st.get(k) is not None else 0  # noqa: E731
    if code == "SCN-01":
        return [
            f"수신 신호 세기 완만 하락: {g('rssi_max'):.0f} → {g('rssi_min'):.0f} dBm (기존 기지국을 놓지 못함)",
            f"기지국(AP) 변경 소요 시간: 최대 {g('roaming_max_ms'):.0f} ms (> 200 ms 기준 초과, 고속 로밍 미적용)",
            f"기지국 확인 신호 놓침: 최대 {g('beacon_loss_max'):.0f} 회/초 (≥ 5 회/초 → 연결 해제 직전)",
            f"주변 잡음 최대 {g('noise_max'):.0f} dBm · 채널 혼잡도 최대 {g('channel_util_max'):.0f}% (전파 간섭·혼잡 아님)",
            f"소켓 재전송 최대 {g('tcp_retrans_max'):.0f}회/초 · 송신 대기열 최대 {g('send_q_max'):.0f} Bytes 누적",
        ]
    if code == "SCN-02":
        return [
            f"수신 신호 급락: 최저 {g('rssi_min'):.0f} dBm, 최대 하락 속도 {g('rssi_steepest_slope'):.1f} dBm/초",
            f"주변 잡음 상승: 최대 {g('noise_max'):.0f} dBm → 신호대잡음비(SNR) 최저 {g('snr_min'):.0f} dB (설비 간섭)",
            f"무선 연결 속도 최저 {g('phy_min'):.0f} Mbps 강등 · 무선 구간 재시도율 최대 {g('l2_retry_max'):.0f}%",
            f"기지국 변경 없음 (최대 {g('roaming_max_ms'):.0f} ms) — 갈아탈 인접 기지국 없이 전파 차단",
            f"소켓 재전송 최대 {g('tcp_retrans_max'):.0f}회/초 · 게이트웨이 응답 시간 초과({ICMP_TIMEOUT_MS:.0f} ms)",
        ]
    if code == "SCN-03":
        return [
            f"수신 신호 최저 {g('rssi_min'):.0f} dBm · 신호대잡음비 최저 {g('snr_min'):.0f} dB — 전파 세기는 양호 유지",
            f"무선 채널 혼잡도 최대 {g('channel_util_max'):.0f}% (> 75% 기준 초과, 동일 채널 기기 과밀)",
            f"게이트웨이 응답 최대 {g('gw_rtt_max'):.0f} ms · 흔들림 최대 {g('jitter_max'):.0f} ms (무선 구간 대기 지연)",
            f"무선 재시도율 최대 {g('l2_retry_max'):.0f}% · 소켓 재전송 최대 {g('tcp_retrans_max'):.0f}회/초",
            f"소켓 송신 대기열 최대 {g('send_q_max'):.0f} Bytes 누적",
        ]
    return [
        f"수신 신호 최저 {g('rssi_min'):.0f} dBm · 신호대잡음비 최저 {g('snr_min'):.0f} dB — 와이파이 신호 완벽 정상",
        f"게이트웨이 응답 시간 최대 {g('gw_rtt_max'):.1f} ms — 무선 네트워크 구간 정상 (< 15 ms)",
        f"AGV 컴퓨터(CPU) 사용률 최대 {g('cpu_max'):.0f}% (> 92%) — 자율주행 연산 과부하",
        f"소켓 수신 대기열(Recv-Q) 최대 {g('recv_q_max'):.0f} Bytes (> 2KB) — 통신 프로그램 일시 멈춤으로 미수신",
        f"소켓 재전송 최대 {g('tcp_retrans_max'):.0f}회/초 (무선 손실 없음) · 소켓 왕복 시간만 {g('tcp_srtt_max'):.0f} ms로 증가",
    ]


def _build_scenarios() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for code, cfg in _SCENARIO_CFGS.items():
        built = _build_timeline(cfg)
        tl = built["timeline"]
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
# 5. Terminology Guide, TSDB Necessity, and Role Action Plans (AGV vs ACS)
# ---------------------------------------------------------------------------
TERMINOLOGY_GUIDE: List[Dict[str, Any]] = [
    {
        "id": "TERM-01",
        "plain_term": "AGV 내부 1초 단위 상시 기록장 (최근 5분 순환 보관)",
        "dev_term_avoided": "1초 고주파 링버퍼 (Ring Buffer)",
        "analogy": "자동차 블랙박스 (최근 5분 자동 덮어쓰기)",
        "explanation": (
            "자동차 블랙박스처럼 AGV 내부 메모리에 작은 임시 기록장을 만들어 두고, 1초마다 무선 신호 세기·응답 시간 등을 "
            "빠짐없이 기록하는 방식입니다. 기록이 무한정 쌓이지 않도록 '최근 5분(300초) 분량'만 유지하고 5분이 지난 가장 오래된 기록 위에 "
            "새 기록을 덮어쓰므로 메모리(약 30KB)나 무선 통신에 부담을 전혀 주지 않습니다."
        ),
        "benefit": "무선 전송 부하 0%로 1초 단위의 정밀한 끊김 직전 징후 포착 및 사후 원인 규명 데이터 확보",
    },
    {
        "id": "TERM-02",
        "plain_term": "30초 정기 보고 시 요약 데이터 동봉 전송",
        "dev_term_avoided": "통계 피기백 (Statistical Piggyback)",
        "analogy": "정기 택배 상자 빈 공간에 한 줄 요약 메모지를 함께 넣어 보내기",
        "explanation": (
            "새로운 통신 연결을 따로 만들지 않고, 기존에 30초마다 ACS로 보내던 상태 보고 메시지 끝에 "
            "'지난 30초간의 통신 품질 요약표(최저 신호 세기, 평균 응답 시간, 재전송 횟수 등 약 120 Bytes)'를 살짝 덧붙여 함께 보내는 방식입니다."
        ),
        "benefit": "통신 횟수를 늘리지 않으면서도 ACS 서버가 각 AGV의 지난 30초 중 가장 나빴던 순간의 통신 상태를 정확히 파악",
    },
    {
        "id": "TERM-03",
        "plain_term": "시계열 데이터베이스(TSDB) 도입 및 시간대별 상태 이력 관리",
        "dev_term_avoided": "내장 시계열 DB (Embedded TSDB)",
        "analogy": "시간순 건강검진 변화 기록부 (단순 최종 상태표가 아닌 변화 추세 기록)",
        "explanation": (
            "일반 데이터베이스(RDB)는 '현재 AGV의 마지막 위치'처럼 최신 값 하나만 덮어쓰는 데 적합합니다. "
            "반면 무선 끊김을 사전 감지하거나 사후 분석하려면 '최근 10초 동안 신호가 얼마나 빠르게 떨어졌는지(기울기)'를 계산하고 "
            "수십 대 AGV의 시간순 이력을 빠르게 저장·압축·조회해야 하므로, 실제 운영 환경에서는 시간순 데이터 처리에 특화된 "
            "시계열 데이터베이스(Time-Series DB, 예: InfluxDB, TimescaleDB, VictoriaMetrics) 도입이 필수적입니다."
        ),
        "benefit": "시간 흐름에 따른 신호 하락 기울기 실시간 계산 및 장기 이력 자동 압축·보관(Retention)",
    },
    {
        "id": "TERM-04",
        "plain_term": "통신 프로그램 일시 멈춤 (응답 지연)",
        "dev_term_avoided": "소켓 행 (Socket Hang / Blocking)",
        "analogy": "전화선은 멀쩡한데 받는 사람이 다른 일로 바빠 수화기를 들지 못하는 상태",
        "explanation": (
            "와이파이 신호와 네트워크 장비는 100% 정상이지만, AGV 내부 자율주행(라이다·SLAM) 연산이 폭주해 CPU가 95% 이상 차면서 "
            "통신 프로그램이 데이터를 제때 읽지 못해 수신 대기열(Recv-Q)에 데이터가 쌓이고 30초 보고가 멈추는 현상입니다."
        ),
        "benefit": "무선 장애와 로봇 내부 소프트웨어 과부하를 명확히 구분하여 불필요한 무선 기지국(AP) 추가 공사 방지",
    },
    {
        "id": "TERM-05",
        "plain_term": "장애 상황 가상 체험 (시뮬레이션 실행)",
        "dev_term_avoided": "장애 시나리오 실시간 주입 (Fault Injection)",
        "analogy": "화재 대피 모의훈련",
        "explanation": (
            "실제 현장에서 자주 발생하는 4대 통신 끊김 상황(① 기지국 전환 지연, ② 전파 음영·설비 간섭, ③ 무선 채널 혼잡, "
            "④ 통신 프로그램 일시 멈춤)을 관제 화면에서 버튼 하나로 가상 실행해 보며 사전 감지 경보와 사후 원인 판별 과정을 체험하는 기능입니다."
        ),
        "benefit": "현장 적용 전 담당자와 관계자가 사전 감지(끊김 14~18초 전 알림)와 자동 원인 분류 효과를 직관적으로 검증",
    },
]

TSDB_NECESSITY_SPEC: Dict[str, Any] = {
    "title": "왜 실제 운영 환경에서 '시계열 데이터베이스(TSDB)' 도입이 필요한가요?",
    "summary": (
        "무선 끊김 사전 감지와 사후 원인 분석의 핵심은 '현재 값 하나'가 아니라 '시간의 흐름(1초·30초 단위)에 따라 "
        "신호 세기와 응답 지연이 어떻게 변했는지(추세·기울기)'를 다루는 것입니다. 실제 운영 환경에서는 시간순 데이터 저장·압축·구간 조회에 "
        "특화된 시계열 데이터베이스(Time-Series DB)를 구축해야 다수 AGV의 상태 이력을 서버 부담 없이 관리할 수 있습니다."
    ),
    "reasons": [
        {
            "no": 1,
            "title": "시간 흐름에 따른 변화 추세(기울기) 실시간 계산",
            "detail": (
                "현재 신호 세기가 -70dBm이라는 단편적 숫자만으로는 안전한지 위험한지 알 수 없습니다. "
                "'최근 5~10초 동안 초당 -2.5dBm씩 급격히 떨어지고 있다'는 시간별 변화 추세를 계산해야 끊김 15~18초 전에 사전 경고를 보낼 수 있습니다."
            ),
        },
        {
            "no": 2,
            "title": "끊김 전후 120초(1초 단위) 상세 파형의 고속 구간 조회",
            "detail": (
                "통신이 끊어졌다가 다시 연결되었을 때, 끊김 전후 120초 동안의 18종 상태 항목 변화를 시간축으로 나란히 비교해야 "
                "기지국 전환 지연(SCN-01)인지, 전파 음영(SCN-02)인지, 채널 혼잡(SCN-03)인지, 프로그램 일시 멈춤(SCN-04)인지 즉시 가려낼 수 있습니다."
            ),
        },
        {
            "no": 3,
            "title": "대용량 시간순 이력의 자동 압축 및 보관 주기(Retention) 관리",
            "detail": (
                "수십 대의 AGV가 30초마다 보내는 요약 데이터와 장애 시 보내는 1초 상세 기록은 하루에도 수십만 건씩 쌓입니다. "
                "시계열 DB는 시간 순서 데이터를 최대 90% 이상 고효율 압축하고, 보관 기간(예: 상세 7일, 요약 90일)이 지난 데이터를 자동으로 정리해 줍니다."
            ),
        },
    ],
    "rdb_vs_tsdb": [
        {"aspect": "주요 저장 대상", "general_rdb": "AGV의 '현재 마지막 상태' (덮어쓰기 중심)",
         "timeseries_db": "시간 흐름에 따른 모든 상태 변화 이력 (시간순 추가 중심)"},
        {"aspect": "사전 감지 기울기 계산", "general_rdb": "느림 (과거 이력 테이블 전체 검색 필요)",
         "timeseries_db": "초고속 (시간 인덱스 기반 최근 5~30초 이동 평균·기울기 즉시 계산)"},
        {"aspect": "오래된 데이터 정리", "general_rdb": "DELETE 쿼리 실행 시 테이블 잠금·성능 저하 발생",
         "timeseries_db": "보관 기간(Retention Policy) 설정만으로 시간 블록 단위 자동 삭제"},
        {"aspect": "저장 공간 효율", "general_rdb": "행 단위 저장으로 용량 급증",
         "timeseries_db": "시간열 압축 알고리즘으로 저장 용량 1/5 ~ 1/10 절감"},
        {"aspect": "실제 운영 권장 엔진", "general_rdb": "일반 업무 테이블(작업 지시·마스터 정보)에만 사용",
         "timeseries_db": "InfluxDB, TimescaleDB(PostgreSQL 확장), VictoriaMetrics 등 도입 권장"},
    ],
}

ROLE_ACTION_PLANS: Dict[str, Any] = {
    "title": "현장 적용을 위한 담당자별 해야 할 일 (AGV/AMR 담당자 & ACS 담당자)",
    "subtitle": (
        "별도의 무선 인프라(AP/WLC) 장비 접근 권한 없이, 오직 AGV/AMR과 ACS 양단에서 직접 수집·처리하기 위해 "
        "각 담당자가 개발·적용해야 할 핵심 과업과 체크리스트입니다."
    ),
    "terminology_guide": TERMINOLOGY_GUIDE,
    "tsdb_necessity": TSDB_NECESSITY_SPEC,
    "agv_amr_owner": {
        "role_code": "AGV_AMR_OWNER",
        "role": "AGV/AMR 담당자",
        "role_title": "AGV/AMR 담당자가 해야 할 일",
        "role_subtitle": "로봇 온보드 소프트웨어(통신 에이전트) 및 무선 랜카드 설정 담당",
        "owned_metric_ids": ["M01", "M02", "M03", "M04", "M05", "M06", "M07", "M08",
                             "M09", "M10", "M11", "M12", "M13", "M14", "M16", "M17", "M18"],
        "exclusive_metric_ids": ["M01", "M02", "M03", "M04", "M05", "M06", "M07", "M08", "M09", "M17"],
        "shared_metric_ids": ["M10", "M11", "M12", "M13", "M14", "M16", "M18"],
        "summary": (
            "AGV 내부에서 1초마다 무선·소켓·CPU·위치 상태(17종)를 읽어 최근 5분 상시 기록장에 보관하고, "
            "평소에는 30초 정기 보고 메시지에 요약 수치를 동봉해 보내며, 위험 시 조기 경고 알림 및 재연결 후 상세 기록 전송을 수행합니다."
        ),
        "tasks": [
            {
                "step": 1,
                "title": "1. AGV 내부 1초 단위 상시 기록장 (최근 5분 순환 보관) 기능 구현",
                "what_to_do": (
                    "로봇 내부에서 1초마다 무선 상태(M01~M08), 소켓 상태(M09~M14), 시스템·위치(M17~M18)를 읽어 "
                    "메모리 내 최근 300초(5분) 상시 기록장에 보관합니다."
                ),
                "how_to_implement": (
                    "Linux 기본 파일(/proc/net/wireless, /proc/stat)과 명령어(iw, ss -ti, ioctl SIOCOUTQ/SIOCINQ)를 "
                    "별도 경량 스레드에서 1초 주기로 실행하여 고정 길이 순환 배열(300칸, 약 30KB)에 기록 (평시 외부 전송 없음 → 무선 부하 0%)."
                ),
                "related_metrics": ["M01", "M02", "M03", "M04", "M05", "M06", "M07", "M08",
                                    "M09", "M10", "M11", "M12", "M13", "M14", "M17", "M18"],
                "expected_effect": "통신이 끊어지는 순간에도 로봇 내부에는 1초 단위 상태 변화가 빠짐없이 보존됨",
            },
            {
                "step": 2,
                "title": "2. 기존 30초 정기 보고 시 요약 데이터 동봉 전송 기능 추가",
                "what_to_do": (
                    "기존에 30초마다 ACS로 보내던 상태 보고 메시지 끝에 지난 30초간의 통신 품질 핵심 요약 수치를 함께 담아 전송합니다."
                ),
                "how_to_implement": (
                    "지난 30초 기록 중 최저 신호 세기(rssi_min), 평균 신호 세기(rssi_avg), 최저 신호대잡음비(snr_min), "
                    "최대 무선 재시도율(l2_retry_max), 소켓 재전송 합계(tcp_retrans_sum), 최대 게이트웨이 응답시간(gw_rtt_max), "
                    "기지국 변경 횟수(roaming_count), 최고 위험 점수(max_risk_score)를 JSON 필드(약 120 Bytes)로 덧붙여 전송."
                ),
                "related_metrics": ["M01", "M02", "M05", "M07", "M08", "M09", "M11", "M13", "M14", "M17"],
                "expected_effect": "새로운 소켓 연결이나 추가 통신 횟수 없이도 ACS가 30초 내 순간적인 품질 저하를 모두 파악",
            },
            {
                "step": 3,
                "title": "3. 이상 징후 포착 시 [사전 경고 알림] 즉시 전송 로직 구현",
                "what_to_do": (
                    "1초 기록 중 종합 위험 점수(Risk Score)가 70점 이상으로 치솟으면 30초 주기를 기다리지 않고 즉시 ACS로 짧은 사전 경고 알림을 발송합니다."
                ),
                "how_to_implement": (
                    "신호 세기 -75dBm 이하 급락(초당 -2.5dBm 이상 하락), 무선 재시도율 20% 초과, 또는 소켓 송신 대기열(Send-Q) 누적 감지 시 "
                    "즉시 경고 패킷(약 220 Bytes)을 보내고 내부 상시 기록장이 덮어써지지 않도록 잠금(Lock) 처리."
                ),
                "related_metrics": ["M01", "M02", "M05", "M11", "M13"],
                "expected_effect": "소켓이 완전히 끊어지기 평균 14~18초 전에 ACS가 미리 알고 감속·대기 제어를 내릴 수 있음",
            },
            {
                "step": 4,
                "title": "4. 재연결 직후 상세 기록(끊김 전후 120초) 일괄 전송 기능 구현",
                "what_to_do": (
                    "만약 통신이 끊어졌다가 다시 연결되면, 끊김 사유 코드(M16)와 함께 내부 상시 기록장에 보관되어 있던 "
                    "끊김 전후 120초간의 1초 단위 상세 기록을 ACS로 압축 전송합니다."
                ),
                "how_to_implement": (
                    "소켓 재연결 성공 직후, 잠가 두었던 120초 분량의 상세 기록을 압축(약 4.5KB)하여 일반 제어 메시지에 방해되지 않게 전송."
                ),
                "related_metrics": ["M16", "M18"],
                "expected_effect": "끊어져 있던 시간 동안 무슨 일이 있었는지 1초 단위로 복원하여 4대 원인 자동 판별 가능",
            },
            {
                "step": 5,
                "title": "5. 무선 랜카드 기지국 전환(로밍) 기준값 최적화 및 CPU 코어 분리",
                "what_to_do": (
                    "기존 기지국(AP) 신호가 너무 약해질 때까지 붙잡고 있지 않도록 무선 설정을 조정하고, "
                    "자율주행 연산 과부하로 통신 프로그램이 멈추지 않도록 CPU 코어를 분리합니다."
                ),
                "how_to_implement": (
                    "wpa_supplicant의 로밍 탐색 기준값(bgscan)을 -70dBm 수준으로 상향 및 802.11k/v/r 고속 로밍 옵션 활성화. "
                    "Linux taskset으로 자율주행(SLAM) 프로세스와 ACS 통신 프로세스의 실행 CPU 코어를 분리하고 비동기 소켓 적용."
                ),
                "related_metrics": ["M01", "M07", "M13", "M14", "M17"],
                "expected_effect": "기지국 고착(SCN-01) 및 자율주행 과부하에 의한 통신 프로그램 일시 멈춤(SCN-04) 원천 예방",
            },
        ],
        "checklist": [
            "AGV 내부에서 1초 주기로 17종 상태 항목을 읽어 최근 5분(300초) 상시 기록장에 보관하는가?",
            "통신 스레드가 멈춰도 수신 대기열(M14)과 CPU 사용률(M17)을 기록할 수 있도록 감시 스레드가 분리되어 있는가?",
            "30초 정기 보고 메시지에 지난 30초간의 요약 수치(최저 신호, 최대 응답시간, 재전송 합계 등)가 동봉되는가?",
            "위험 점수 70점 이상 시 30초 주기를 기다리지 않고 즉시 [사전 경고 알림]을 발송하는가?",
            "재연결 직후 끊김 사유(ETIMEDOUT/ECONNRESET)와 전후 120초 상세 기록을 ACS로 전송하는가?",
            "무선 랜카드 기지국 전환 기준값(-70dBm) 및 자율주행·통신 간 CPU 코어 분리가 적용되었는가?",
        ],
    },
    "acs_owner": {
        "role_code": "ACS_OWNER",
        "role": "ACS 담당자",
        "role_title": "ACS 담당자가 해야 할 일",
        "role_subtitle": "상위 관제 서버(ACS), 시계열 데이터베이스(TSDB) 및 관제 UI 담당",
        "owned_metric_ids": ["M10", "M11", "M12", "M13", "M14", "M15", "M16", "M18"],
        "exclusive_metric_ids": ["M15"],
        "shared_metric_ids": ["M10", "M11", "M12", "M13", "M14", "M16", "M18"],
        "summary": (
            "AGV가 30초 정기 보고에 동봉해 보낸 요약 데이터와 ACS 서버 자체 측정 지표(보고 도착 간격 M15 등)를 "
            "시계열 데이터베이스(TSDB)에 저장하고, 사전 경고 수신 시 AGV 감속·우회 제어를 내리며, 재연결 후 상세 기록으로 4대 원인을 자동 분류합니다."
        ),
        "tasks": [
            {
                "step": 1,
                "title": "1. 30초 정기 보고 수신 규격 확장 및 시계열 데이터베이스(TSDB) 구축",
                "what_to_do": (
                    "AGV가 30초마다 보내오는 정기 보고 메시지에서 '통신 품질 요약 데이터'를 추출하여 "
                    "시계열 데이터베이스(Time-Series DB)에 시간순으로 저장하고 보관 주기를 관리합니다."
                ),
                "how_to_implement": (
                    "기존 30초 보고 파서에 요약 데이터 필드(pb / net_telemetry_30s)를 추가(하위 호환 유지)하고, "
                    "InfluxDB·TimescaleDB·VictoriaMetrics 등 시계열 DB에 적재 (상세 이력 7~30일, 요약 이력 90일 자동 보관 설정)."
                ),
                "related_metrics": ["M01", "M02", "M05", "M07", "M08", "M09", "M11", "M18"],
                "expected_effect": "모든 AGV의 시간대별·구역별 통신 품질 추세를 서버 부하 없이 즉시 조회 및 차트화",
            },
            {
                "step": 2,
                "title": "2. ACS 서버 자체 수집 항목(M10~M16) 상시 측정 및 기록",
                "what_to_do": (
                    "ACS 서버 측에서도 각 AGV 소켓 연결의 보고 도착 간격(M15), 서버 측 송수신 대기열(M13, M14), "
                    "소켓 왕복 시간 및 재전송(M10~M12), 재연결 횟수 및 끊김 사유(M16)를 직접 측정해 기록합니다."
                ),
                "how_to_implement": (
                    "보고 수신 시각 차이(T_now − T_last)를 기록하고 1초 감시 타이머로 31초 초과(지연)·45초 초과(단절)를 판정하며, "
                    "ACS 서버 소켓의 Recv-Q(M14)를 감시해 ACS 서버 자체의 처리 지연 여부도 함께 점검."
                ),
                "related_metrics": ["M10", "M11", "M12", "M13", "M14", "M15", "M16"],
                "expected_effect": "문제가 AGV 측인지, 무선 구간인지, ACS 서버 측 처리 지연인지 양단 비교로 명확히 구분",
            },
            {
                "step": 3,
                "title": "3. [사전 경고 알림] 수신 시 선제적 안전 제어 연동",
                "what_to_do": (
                    "AGV로부터 사전 경고 알림(위험 점수 ≥ 70)을 받거나 30초 보고 도착 간격(M15)이 밀리기 시작하면, "
                    "연결이 완전히 끊어지기 전에 선제적으로 안전 제어 명령을 내립니다."
                ),
                "how_to_implement": (
                    "사전 경고 수신 즉시 해당 AGV에 주행 속도 감속(예: 1.5m/s → 0.4m/s) 또는 음영 구역 진입 전 안전 대기 명령을 내리고, "
                    "후속 AGV가 해당 혼잡·음영 구간으로 몰리지 않도록 우회 경로를 재할당."
                ),
                "related_metrics": ["M01", "M05", "M11", "M13", "M15", "M18"],
                "expected_effect": "무선 단절로 인한 AGV 비상 정지·물류 라인 멈춤 사고를 끊김 14~18초 전에 예방",
            },
            {
                "step": 4,
                "title": "4. 재연결 후 상세 기록 수신 및 4대 원인 자동 분류·2D 음영 지도 제공",
                "what_to_do": (
                    "재연결된 AGV가 보내온 120초 상세 기록을 분석하여 4대 원인 중 무엇인지 자동 판별하고, "
                    "관제 화면과 공장 2D 지도에 원인별 조치 가이드를 표시합니다."
                ),
                "how_to_implement": (
                    "4단계 자동 원인 판별 로직(classify_rca)을 실행해 ① 기지국 전환 지연(SCN-01), ② 전파 음영·설비 간섭(SCN-02), "
                    "③ 무선 채널 혼잡(SCN-03), ④ 통신 프로그램 일시 멈춤(SCN-04)으로 분류하고, 좌표(M18)별로 집계해 2D 전파 음영 히트맵 생성."
                ),
                "related_metrics": ["M01", "M02", "M03", "M07", "M08", "M09", "M14", "M17", "M18"],
                "expected_effect": "막연한 '와이파이 불량' 추측 대신 정확한 근거 데이터로 현장 조치 및 불필요한 공사 비용 절감",
            },
        ],
        "checklist": [
            "30초 정기 보고 수신 시 동봉된 통신 품질 요약 데이터를 파싱하여 시계열 DB(TSDB)에 저장하는가?",
            "ACS 서버에서 각 AGV의 보고 도착 시간 간격(M15)과 서버 소켓 대기열(M13, M14)을 상시 측정하는가?",
            "AGV로부터 [사전 경고 알림] 수신 시 감속·대기·우회 경로 제어 명령이 자동으로 연동되는가?",
            "재연결 후 수신한 120초 상세 기록으로 4대 장애 원인(SCN-01~04)을 자동 판별하여 화면에 표시하는가?",
            "주행 위치 좌표(M18)와 통신 품질을 결합해 공장 2D 전파 음영 구역 지도(히트맵)를 제공하는가?",
        ],
    },
    "interface_contract": [
        {
            "message_type": "① 평시 30초 정기 보고 (요약 데이터 동봉 전송)",
            "direction": "AGV/AMR → ACS",
            "period_or_trigger": "매 30초 정기 보고 시 (기존 소켓 연결 그대로 사용)",
            "added_size": "약 120 Bytes (JSON) / 32 Bytes (이진 압축)",
            "included_items": "최저·평균 신호세기(M01), 최저 SNR(M02), 최대 잡음(M03), 최저 연결속도(M04), 최대 무선재시도율(M05), 비콘놓침합계(M06), 기지국변경횟수·시간(M07), 최대 채널혼잡도(M08), 평균·최대 게이트웨이응답(M09), 최대 흔들림(M10), 소켓재전송합계(M11), 최대 송수신대기열(M13·M14), 최대 CPU(M17), 최고 위험점수",
        },
        {
            "message_type": "② 이상 징후 사전 경고 알림 (Early Warning)",
            "direction": "AGV/AMR → ACS (양방향 제어 연동)",
            "period_or_trigger": "1초 감시 중 위험 점수 ≥ 70 돌파 시 즉시 (끊김 14~18초 전)",
            "added_size": "약 220 Bytes (단발 전송)",
            "included_items": "경고 시각, AGV ID, 현재 좌표·속도(M18), 위험 점수, 예상 장애 유형(SCN-01~04), 주요 위험 지표(신호 세기·하락 속도·재시도율·송신 대기열) → ACS는 감속·대기 명령 응답",
        },
        {
            "message_type": "③ 재연결 후 상세 기록 일괄 전송 (120초 블랙박스 기록)",
            "direction": "AGV/AMR → ACS",
            "period_or_trigger": "통신 끊김 후 소켓 재연결 성공 직후 (M16 이벤트)",
            "added_size": "약 4.5 KB (zlib 압축, 120초 × 1초 상세 기록)",
            "included_items": "끊김 사유 코드(M16: ETIMEDOUT / ECONNRESET), 끊김·복구 시각, 끊김 전후 120초간의 1초 단위 18종 상태 기록 전체 → ACS가 4대 원인 자동 판별 리포트 생성",
        },
    ],
}
ROLE_ACTION_PLANS["agv_owner"] = ROLE_ACTION_PLANS["agv_amr_owner"]
ROLE_ACTION_PLANS["agv_amr"] = ROLE_ACTION_PLANS["agv_amr_owner"]
ROLE_ACTION_PLANS["agv"] = ROLE_ACTION_PLANS["agv_amr_owner"]
ROLE_ACTION_PLANS["acs"] = ROLE_ACTION_PLANS["acs_owner"]
ROLE_ACTION_PLANS["roles"] = [ROLE_ACTION_PLANS["agv_amr_owner"], ROLE_ACTION_PLANS["acs_owner"]]


# ---------------------------------------------------------------------------
# 6. Hybrid telemetry architecture specification (plain Korean + role plans)
# ---------------------------------------------------------------------------
_PIGGYBACK_FIELDS: List[Dict[str, Any]] = [
    {"key": "rs", "metric": "M01 rssi", "agg": "[min, avg, std]", "bin_type": "int8,int16,uint8", "bytes": 4,
     "scale": "avg·std ×10", "desc": "30초간 수신 신호 세기 최저/평균/편차 (이동 중 음영 구간 통과 흔적)"},
    {"key": "sn", "metric": "M02 snr", "agg": "min", "bin_type": "uint8", "bytes": 1, "scale": "1 dB",
     "desc": "30초간 신호 대 잡음 비율(SNR) 최저값"},
    {"key": "nf", "metric": "M03 noise_floor", "agg": "max", "bin_type": "int8", "bytes": 1, "scale": "1 dBm",
     "desc": "30초간 주변 무선 잡음 수치 최대값 (설비 전파 간섭 흔적)"},
    {"key": "ph", "metric": "M04 phy_rate", "agg": "min", "bin_type": "uint16", "bytes": 2, "scale": "1 Mbps",
     "desc": "30초간 최저 무선 연결 속도"},
    {"key": "l2", "metric": "M05 l2_retry_rate", "agg": "max", "bin_type": "uint8", "bytes": 1, "scale": "0.5 %",
     "desc": "30초간 무선 구간 재시도 비율 최대값"},
    {"key": "bl", "metric": "M06 beacon_loss", "agg": "sum", "bin_type": "uint8", "bytes": 1, "scale": "1",
     "desc": "30초간 기지국 확인 신호(비콘) 놓침 합계"},
    {"key": "ro", "metric": "M07 roaming_ms", "agg": "[count, max_ms]", "bin_type": "uint8,uint16", "bytes": 3,
     "scale": "1 ms", "desc": "30초간 기지국(AP) 변경 횟수 및 최대 소요 시간"},
    {"key": "cu", "metric": "M08 channel_util", "agg": "max", "bin_type": "uint8", "bytes": 1, "scale": "1 %",
     "desc": "30초간 무선 채널 혼잡도 최대값"},
    {"key": "rt", "metric": "M09 gw_rtt_ms", "agg": "[avg, max]", "bin_type": "uint16,uint16", "bytes": 4,
     "scale": "×10", "desc": "게이트웨이 응답 시간 평균/최대"},
    {"key": "jt", "metric": "M10 jitter_ms", "agg": "max", "bin_type": "uint16", "bytes": 2, "scale": "×10",
     "desc": "응답 시간 흔들림 폭 최대값"},
    {"key": "tx", "metric": "M11 tcp_retrans", "agg": "delta", "bin_type": "uint16", "bytes": 2, "scale": "1",
     "desc": "30초간 소켓(TCP) 재전송 횟수 합계"},
    {"key": "sr", "metric": "M12 tcp_srtt_ms", "agg": "max", "bin_type": "uint16", "bytes": 2, "scale": "×10",
     "desc": "소켓 종단 간 왕복 시간 최대값"},
    {"key": "sq", "metric": "M13 send_q_bytes", "agg": "max", "bin_type": "uint16", "bytes": 2, "scale": "1 B (sat. 65535)",
     "desc": "소켓 송신 대기열(Send-Q) 최대 데이터양"},
    {"key": "rq", "metric": "M14 recv_q_bytes", "agg": "max", "bin_type": "uint16", "bytes": 2, "scale": "1 B (sat. 65535)",
     "desc": "소켓 수신 대기열(Recv-Q) 최대 데이터양"},
    {"key": "cp", "metric": "M17 cpu_load", "agg": "max", "bin_type": "uint8", "bytes": 1, "scale": "1 %",
     "desc": "AGV 컴퓨터(CPU) 사용률 최대값"},
    {"key": "rk", "metric": "risk_score", "agg": "max", "bin_type": "uint8", "bytes": 1, "scale": "1 pt",
     "desc": "30초간 최고 사전 감지 위험 점수"},
]
_PB_STRUCT = "<BB" + "bhB" + "B" + "b" + "H" + "B" + "B" + "BH" + "B" + "HH" + "H" + "H" + "H" + "H" + "H" + "B" + "B"
_PB_BINARY_BYTES = struct.calcsize(_PB_STRUCT)


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
    legacy_report = {"agv": "AGV-02", "seq": 18421, "ts": 1763180040, "x": 61.4, "y": 14.0, "bat": 78,
                     "state": "MOVING", "task": "T-55821"}
    legacy_bytes = len(json.dumps(legacy_report, separators=(",", ":")).encode("utf-8"))
    hybrid_report = dict(legacy_report, pb=pb)
    hybrid_json = json.dumps(hybrid_report, separators=(",", ":"), ensure_ascii=False)

    ring_seconds = 300
    ring_fields = 24
    ring_bytes = ring_seconds * (ring_fields * 4 + 8)
    dump_seconds = 121
    dump_raw = dump_seconds * (ring_fields * 4 + 8)
    dump_compressed = int(dump_raw * 0.38)
    ew_packet = {"type": "EARLY_WARNING", "agv": "AGV-02", "ts": 1763180071, "risk": 72.4,
                 "dom": "rf_signal", "issue": "STICKY_CLIENT", "rssi": -73.2, "slope": -1.1,
                 "l2": 18.5, "tx": 2, "sq": 2920, "bssid": "02:AC:00:00:00:A1", "x": 77.5, "y": 14.0}
    ew_bytes = len(json.dumps(ew_packet, separators=(",", ":")).encode("utf-8"))
    icmp_bps = (64 + 64) / 2.0
    piggyback_bps = pb_json_bytes / 30.0

    return {
        "title": "3단계 하이브리드 수집 방식 및 시계열 데이터베이스(TSDB) 도입 구조",
        "summary": (
            "① AGV 내부 1초 단위 상시 기록장(최근 5분 순환 보관, 무선 전송 0) → "
            f"② 평시 30초 정기 보고 시 요약 데이터 동봉 전송(+약 {pb_json_bytes}B) → "
            "③ 이상 징후 시 사전 경고 즉시 알림 & 재연결 후 끊김 전후 120초 상세 기록 일괄 전송. "
            "기존 30초 정기 보고 체계를 그대로 유지하면서 사전 감지(평균 15.75초 선행)와 사후 4대 원인 자동 판별을 달성합니다."
        ),
        "problem_statement": [
            "무선 신호 급락과 재전송 폭증은 불과 3~15초 사이에 일어나므로 30초마다 한 번씩만 보고하면 끊김 전에 미리 알 수 없음 (사전 감지 불가)",
            "통신이 끊어진 뒤 다시 연결되어도 30초 전의 '정상' 보고만 남아 있어 기지국 전환 지연·음영·채널 혼잡·프로그램 멈춤을 구분할 수 없음 (사후 분석 불가)",
            "ACS는 45초 동안 보고가 안 와야 끊김으로 판정하므로, 18초 만에 다시 연결된 사고는 단순 '보고 지연'으로만 묻혀 반복 재발함",
        ],
        "terminology_guide": TERMINOLOGY_GUIDE,
        "tsdb_necessity": TSDB_NECESSITY_SPEC,
        "role_action_plans": ROLE_ACTION_PLANS,
        "stages": [
            {
                "stage": 1,
                "name": "1단계 — AGV 내부 1초 단위 상시 기록장 (최근 5분 순환 보관)",
                "location": "AGV/AMR 내부 통신 에이전트",
                "interval": "1초마다 기록 (잡음·채널혼잡도·CPU는 5초, 게이트웨이 응답은 2초, 기지국 변경·재연결은 즉시)",
                "data_source": "AGV Linux /proc/net/wireless, nl80211(iw), TCP_INFO(ss -ti), ioctl(SIOCINQ/SIOCOUTQ), /proc/stat, 주행 좌표",
                "buffer": {
                    "type": "AGV 내부 1초 단위 상시 기록장 (최근 5분 자동 덮어쓰기 블랙박스)",
                    "retention_sec": ring_seconds,
                    "fields_per_sample": ring_fields,
                    "bytes_per_sample": ring_fields * 4 + 8,
                    "total_bytes": ring_bytes,
                    "total_kb": round(ring_bytes / 1024, 1),
                    "note": (
                        f"1초마다 {ring_fields}개 항목({ring_fields * 4 + 8} B)을 기록하더라도 최근 5분({ring_seconds}초)치만 "
                        f"순환 보관하므로 메모리 사용량은 약 {round(ring_bytes / 1024, 1)} KB(< 150 KB)에 불과합니다."
                    ),
                },
                "network_overhead": "0 B/s (외부 무선 전송 없음, 게이트웨이 Ping 확인만 약 64 B/s)",
                "cpu_overhead": "0.5% 미만 (OS 메모리 상태값 읽기만 수행)",
                "local_logic": [
                    "매 1초마다 사전 감지 위험 점수(compute_risk_score) 자동 계산",
                    "위험 점수 ≥ 45점(주의): 상시 기록장이 덮어써지지 않도록 보호 잠금(Lock)",
                    "위험 점수 ≥ 70점(경고): 3단계 [사전 경고 알림]을 즉시 ACS로 발송",
                ],
            },
            {
                "stage": 2,
                "name": "2단계 — 평시 30초 정기 보고 시 요약 데이터 동봉 전송",
                "location": "AGV/AMR → ACS (기존 30초 정기 보고 소켓 그대로 사용)",
                "interval": "30초 (기존 정기 보고 주기 유지, 하위 호환 보장)",
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
                        f"30초 정기 보고에 동봉하는 요약 데이터는 JSON 기준 {pb_json_bytes} B "
                        f"(초당 환산 {piggyback_bps:.1f} B/s, 이진 압축 시 {_PB_BINARY_BYTES} B = 초당 {_PB_BINARY_BYTES / 30.0:.2f} B/s). "
                        f"AGV 100대가 동시에 운행해도 초당 {piggyback_bps * 100 / 1024:.2f} KB/s 수준으로 무선망 부담이 전혀 없습니다."
                    ),
                },
                "acs_storage": "ACS 시계열 데이터베이스(TSDB)의 30초 정기 보고 테이블에 시간순 저장 — 장기 추세 및 2D 전파 음영 지도 생성",
            },
            {
                "stage": 3,
                "name": "3단계 — 이상 징후 사전 경고 알림 & 재연결 후 120초 상세 기록 일괄 전송",
                "location": "AGV/AMR → ACS (이상 발생 시 즉시)",
                "early_warning": {
                    "trigger": "AGV 내부 1초 감시 중 위험 점수 ≥ 70점 도달 시 즉시 전송",
                    "packet_example": ew_packet,
                    "packet_bytes": ew_bytes,
                    "acs_actions": [
                        "해당 AGV에 주행 감속 또는 음영 구역 진입 전 안전 대기 지시",
                        "인접 무선 기지국(AP)으로 미리 갈아타도록 전환 유도",
                        "관제 화면에 사전 감지 경보 표시 및 시계열 DB에 사건 이력 기록",
                    ],
                    "lead_time_sec": {code: s["lead_time_sec"] for code, s in FAILURE_SCENARIOS.items()},
                    "lead_time_avg_sec": round(sum(s["lead_time_sec"] for s in FAILURE_SCENARIOS.values()) / 4.0, 2),
                },
                "blackbox_dump": {
                    "trigger": "통신 끊김 후 소켓 재연결 성공 직후 (M16 이벤트)",
                    "window": "끊김 시점 전후 60초씩 총 120초 구간 (1초 단위 상세 기록)",
                    "samples": dump_seconds,
                    "raw_bytes": dump_raw,
                    "compressed_bytes": dump_compressed,
                    "compression": "zlib 압축 전송 (약 4.5 KB)",
                    "transfer": "재연결 직후 일반 제어 보고에 방해되지 않게 분할 전송",
                    "acs_processing": "4단계 원인 판별(classify_rca) 실행 → 4대 장애 원인(SCN-01~04) 자동 판정 및 시계열 DB 기록",
                },
            },
        ],
        "bandwidth_per_agv": {
            "stage1_icmp_probe_bps": icmp_bps,
            "stage2_piggyback_bps": round(piggyback_bps, 2),
            "stage3_early_warning_bytes_per_event": ew_bytes,
            "stage3_blackbox_bytes_per_incident": dump_compressed,
            "total_steady_state_bps": round(icmp_bps + piggyback_bps, 1),
            "note": "평시 추가 통신량은 AGV 1대당 초당 약 70 Bytes 수준이며, 장애 발생 시에만 약 4.5 KB 상세 기록을 1회 전송합니다.",
        },
        "comparison_table": [
            {"aspect": "상태 확인 간격", "legacy": "30초마다 1번 (위치·배터리·작업 상태만 보고)",
             "hybrid": "AGV 내부 1초 단위 상시 기록(18종) + 30초 정기 보고 시 요약 데이터 동봉 전송", "improvement": "30배 정밀한 상태 파악"},
            {"aspect": "사전 감지 (끊김 전 알림)", "legacy": "불가능 — 다음 30초 보고가 빠진 뒤에야 이상 인지",
             "hybrid": "끊어지기 14~18초 전(평균 15.75초) 사전 경고 알림 발송", "improvement": "약 22초 먼저 위험 인지"},
            {"aspect": "짧은 끊김(18초) 감지", "legacy": "45초 기준 전 복구 시 단순 '보고 지연'으로 묻힘",
             "hybrid": "1초 상시 기록으로 짧은 끊김과 끊김 사유(시간초과/강제종료)까지 100% 기록", "improvement": "숨은 끊김 누락 0건"},
            {"aspect": "사후 원인 분석", "legacy": "불가능 — 30초 전의 정상 데이터만 남음",
             "hybrid": "끊김 전후 120초 상세 기록으로 4대 원인(로밍·음영·혼잡·프로그램 멈춤) 자동 판별", "improvement": "정확한 원인 규명"},
            {"aspect": "무선 vs 프로그램 문제 구분", "legacy": "구분 불가 → 무조건 와이파이 불량으로 오해",
             "hybrid": "게이트웨이 응답(M09)과 수신 대기열(M14)·CPU(M17)로 무선 문제와 프로그램 일시 멈춤을 즉시 분리", "improvement": "불필요한 무선 공사 방지"},
            {"aspect": "수집 장비 범위", "legacy": "별도 무선 장비(AP/WLC) 관리 권한 필요",
             "hybrid": "오직 AGV/AMR과 ACS 양단에서만 100% 직접 수집", "improvement": "외부 장비 의존성 없음"},
            {"aspect": "추가 무선 통신 부하", "legacy": "0 B/s",
             "hybrid": f"AGV 1대당 초당 약 {icmp_bps + piggyback_bps:.0f} Bytes (게이트웨이 확인 64B/s + 30초 요약 동봉 {piggyback_bps:.1f}B/s)",
             "improvement": "무선 대역폭 영향 0.001% 미만"},
            {"aspect": "데이터 보관 및 이력 관리", "legacy": "최신 상태만 덮어쓰기 (과거 추세 조회 불가)",
             "hybrid": "시계열 데이터베이스(TSDB)에 시간순 저장하여 신호 하락 기울기 및 2D 음영 지도 제공", "improvement": "시간대별 상태 이력 관리"},
        ],
        "risk_model": {
            "weights": RISK_WEIGHTS,
            "doc_weights": {"w1_rssi": 0.25, "w2_snr": 0.15, "w3_l2_retry": 0.20, "w4_tcp_retrans": 0.25,
                            "w5_send_q": 0.15},
            "fusion": "가중 합산과 단일 영역 급증 감지 결합 — 무선은 정상인데 통신 프로그램만 멈춘 경우(SCN-04)도 놓치지 않고 감지",
            "thresholds": RISK_THRESHOLDS,
            "states": [
                {"state": "CONNECTED", "range": "< 45", "action": "평시 30초 정기 보고 시 요약 데이터 동봉 전송 유지", "color": "--status-ok"},
                {"state": "PRE_WARNING", "range": "45 ~ 84.9",
                 "action": "상시 기록장 보호 잠금, 위험 점수 ≥ 70점 시 ACS로 [사전 경고 알림] 즉시 발송", "color": "--status-warn"},
                {"state": "DISCONNECTED", "range": "≥ 85", "action": "소켓 연결 끊김 — 재연결 직후 전후 120초 상세 기록 일괄 전송",
                 "color": "--status-crit"},
            ],
        },
    }


HYBRID_ARCHITECTURE_SPEC: Dict[str, Any] = _build_hybrid_spec()


if __name__ == "__main__":  # pragma: no cover — quick self-check
    print(len(METRICS_CATALOG), list(FAILURE_SCENARIOS.keys()))
    locs = sorted({m["collection_location"] for m in METRICS_CATALOG})
    print("locations:", locs)
    for c, sc in FAILURE_SCENARIOS.items():
        tl = sc["timeline"]
        print(c, len(tl), "rca=", sc["rca_result"]["scenario_code"], sc["rca_result"]["confidence"],
              "ew70=", sc["early_warning_push_offset_sec"])
