"""AGV/AMR 무선 텔레메트리 실시간 시뮬레이터 (6 AGV, 4 AP, 4대 장애 시나리오).

- 100m x 60m 공장 플로어, AP 4기, 물리적 음영구역(철제 랙 통로), EMI 용접 구역
- 1초 주기 telemetry_1s 행, 30초 주기(AGV별 위상) acs_reports_30s 행 생성
- trigger_scenario(): 45초 동안 정상 -> 열화(PRE_WARNING) -> DISCONNECTED -> 자동 복구
  후 incident_events 기록
- 이 모듈은 DB에 직접 의존하지 않는다 (db 객체는 duck-typing 으로만 사용).
"""
from __future__ import annotations

import asyncio
import json
import math
import random
import threading
import time
from collections import deque
from typing import Any, Optional

FLOOR_W = 100.0
FLOOR_H = 60.0

APS = [
    {"ap_id": "AP-ZONE-A", "zone_id": "ZONE-A", "bssid": "02:AC:00:00:00:A1", "x": 20.0, "y": 15.0, "channel": 36},
    {"ap_id": "AP-ZONE-B", "zone_id": "ZONE-B", "bssid": "02:AC:00:00:00:B1", "x": 75.0, "y": 15.0, "channel": 40},
    {"ap_id": "AP-ZONE-C", "zone_id": "ZONE-C", "bssid": "02:AC:00:00:00:C1", "x": 75.0, "y": 45.0, "channel": 44},
    {"ap_id": "AP-ZONE-D", "zone_id": "ZONE-D", "bssid": "02:AC:00:00:00:D1", "x": 20.0, "y": 45.0, "channel": 48},
]
BSSID_TO_AP = {a["bssid"]: a for a in APS}

SHADOW_CENTER = (50.0, 15.0)   # 철제 랙 통로 (물리적 음영)
SHADOW_SIGMA = 6.0
EMI_CENTER = (80.0, 40.0)      # 용접 구역 (고주파 노이즈)
EMI_SIGMA = 8.0

FLOOR_MAP_ZONES = [
    {"id": "ZONE-A", "type": "ap_zone", "name": "Zone A (AP-ZONE-A 커버리지)", "shape": "rect",
     "x": 0, "y": 0, "w": 50, "h": 30, "ap_id": "AP-ZONE-A", "description": "좌상단 구역"},
    {"id": "ZONE-B", "type": "ap_zone", "name": "Zone B (AP-ZONE-B 커버리지)", "shape": "rect",
     "x": 50, "y": 0, "w": 50, "h": 30, "ap_id": "AP-ZONE-B", "description": "우상단 구역"},
    {"id": "ZONE-C", "type": "ap_zone", "name": "Zone C (AP-ZONE-C 커버리지)", "shape": "rect",
     "x": 50, "y": 30, "w": 50, "h": 30, "ap_id": "AP-ZONE-C", "description": "우하단 구역"},
    {"id": "ZONE-D", "type": "ap_zone", "name": "Zone D (AP-ZONE-D 커버리지)", "shape": "rect",
     "x": 0, "y": 30, "w": 50, "h": 30, "ap_id": "AP-ZONE-D", "description": "좌하단 구역"},
    {"id": "SHADOW-RACK", "type": "shadow", "name": "물리적 음영구역 (철제 랙 통로)", "shape": "circle",
     "cx": 50, "cy": 15, "r": 8, "x": 44, "y": 8, "w": 12, "h": 14,
     "description": "철제 랙이 AP-A/AP-B 사이 전파를 차폐 (RSSI -6 dB 상시, SCN-02 시 급락)"},
    {"id": "EMI-WELD", "type": "emi", "name": "EMI 고노이즈 용접 구역", "shape": "circle",
     "cx": 80, "cy": 40, "r": 8, "x": 72, "y": 32, "w": 16, "h": 16,
     "description": "용접기/인버터 광대역 노이즈 (Noise Floor 상승, SNR 저하)"},
]

# AGV 폐루프 경로 (m 좌표)
AGV_PATHS: dict[str, list[tuple[float, float]]] = {
    "AGV-01": [(8, 8), (92, 8), (92, 22), (8, 22)],
    "AGV-02": [(10, 10), (90, 10), (90, 50), (10, 50)],
    "AGV-03": [(62, 10), (88, 10), (88, 50), (62, 50)],
    "AGV-04": [(8, 36), (50, 36), (50, 52), (8, 52)],
    "AGV-05": [(8, 8), (45, 8), (45, 52), (8, 52)],
    "AGV-06": [(20, 26), (80, 26), (80, 36), (20, 36)],
}
AGV_SPEED = {"AGV-01": 1.6, "AGV-02": 1.8, "AGV-03": 1.4, "AGV-04": 1.3, "AGV-05": 1.5, "AGV-06": 1.2}
AGV_START_FRAC = {"AGV-01": 0.05, "AGV-02": 0.35, "AGV-03": 0.1, "AGV-04": 0.5, "AGV-05": 0.7, "AGV-06": 0.2}
AGV_IDS = list(AGV_PATHS.keys())

SCENARIO_DURATION_SEC = 45
DISCONNECT_HOLD_SEC = 10
# 시나리오별 단절 시점(주입 후 경과 초) -> 사전 경보 리드타임 ~14~18초
SCENARIO_T_DISCONNECT = {"SCN-01": 26.0, "SCN-02": 24.0, "SCN-03": 23.0, "SCN-04": 22.0}

SCENARIO_META = {
    "SCN-01": {
        "title": "AP 로밍 실패 / 기지국 전환 지연",
        "root_cause": "AGV가 기존 AP에 고착되어 수신 신호(RSSI)가 -78dBm 이하로 하락했음에도 기지국(BSSID) 변경이 지연됨. "
                      "뒤늦은 로밍 시 전환 소요 시간 250ms 초과 + 비콘 신호 유실 급증으로 소켓 연결 단절.",
        "action": "AGV 무선 드라이버 로밍 탐색 시작 기준을 -70dBm으로 상향하고 802.11k/v/r 고속 로밍 옵션 활성화.",
    },
    "SCN-02": {
        "title": "물리적 음영 구역 / 설비 전파 간섭",
        "root_cause": "철제 랙 전파 차폐 및 용접 설비 잡음으로 수신 신호 급락(-82dBm 이하) 및 주변 잡음 상승(SNR 12dB 이하), "
                      "무선 재시도율 35% 초과, 무선 연결 속도 6Mbps 급락 후 소켓 단절.",
        "action": "상습 음영 좌표에 보조 AP/지향성 안테나 증설, 2.4GHz 배제 및 5GHz 비간섭 채널 고정.",
    },
    "SCN-03": {
        "title": "무선 채널 과부하 / 동일 채널 혼잡",
        "root_cause": "수신 신호 및 신호대잡음비는 양호(-60dBm, 28dB)하나 무선 채널 혼잡도 75% 초과로 게이트웨이 응답 시간/흔들림 폭이 100ms 이상 치솟고 "
                      "소켓 재전송 다발 후 연결 단절.",
        "action": "인접 채널/AP로 접속 분산, 20MHz 채널폭 최적화, 불필요한 브로드캐스트 트래픽 차단.",
    },
    "SCN-04": {
        "title": "통신 프로그램 일시 멈춤 (응답 지연) / 시스템 병목",
        "root_cause": "무선 신호/잡음/게이트웨이 응답 시간은 모두 정상이나 소켓 수신 대기 데이터(Recv-Q) 급증 및 AGV CPU 사용률 92% 초과로 "
                      "통신 프로그램이 일시 멈춤(응답 지연) 상태에 빠져 30초 정기 보고 타임아웃 발생 (무선 네트워크 문제 아님).",
        "action": "자율주행(SLAM) 연산 프로세스와 통신 보고 프로세스의 CPU 코어 분리(taskset) 및 비동기 소켓 처리 적용. 무선 설비 공사 불필요.",
    },
}


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def zone_of(x: float, y: float) -> str:
    if x < 50:
        return "ZONE-A" if y < 30 else "ZONE-D"
    return "ZONE-B" if y < 30 else "ZONE-C"


def _phy_from_rssi(rssi: float) -> float:
    pts = [(-90, 6.0), (-82, 12.0), (-75, 54.0), (-67, 144.0), (-58, 240.0), (-48, 300.0)]
    if rssi <= pts[0][0]:
        return pts[0][1]
    if rssi >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= rssi <= x1:
            return y0 + (y1 - y0) * (rssi - x0) / (x1 - x0)
    return 100.0


def compute_risk(rssi: float, rssi_slope: float, snr: float, l2_retry: float, phy: float, tcp_retrans: float,
                 gw_rtt: float, send_q: float, recv_q: float, cpu: float, channel_util: float) -> float:
    """다중 지표 위험도 점수 (0~100). 가중치: RSSI .25 / SNR .15 / L2 .20 / TCP .25 / Queue .15."""
    s_rssi = 0.7 * _clamp((-67 - rssi) / 18.0, 0, 1) + 0.3 * _clamp(-rssi_slope / 2.5, 0, 1)
    s_snr = _clamp((25 - snr) / 15.0, 0, 1)
    s_l2 = max(_clamp((l2_retry - 8) / 25.0, 0, 1), _clamp((channel_util - 50) / 40.0, 0, 1),
               _clamp((100 - phy) / 90.0, 0, 1) * 0.6)
    s_tcp = 0.7 * _clamp(tcp_retrans / 4.0, 0, 1) + 0.3 * _clamp((gw_rtt - 10) / 90.0, 0, 1)
    s_q = max(_clamp(send_q / 6000.0, 0, 1), _clamp(recv_q / 20000.0, 0, 1), _clamp((cpu - 80) / 15.0, 0, 1))
    total = 0.25 * s_rssi + 0.15 * s_snr + 0.20 * s_l2 + 0.25 * s_tcp + 0.15 * s_q
    return _clamp(total * 1.6 * 100.0, 0.0, 100.0)


class AgvState:
    def __init__(self, agv_id: str, idx: int):
        self.agv_id = agv_id
        self.idx = idx
        pts = AGV_PATHS[agv_id]
        self.pts = pts
        self.seg_len = []
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            self.seg_len.append(math.hypot(b[0] - a[0], b[1] - a[1]))
        self.total = sum(self.seg_len)
        self.s = AGV_START_FRAC[agv_id] * self.total
        self.base_speed = AGV_SPEED[agv_id]
        self.serving = 0
        self.serving_init = False
        self.risk = 5.0
        self.rssi_hist: deque = deque(maxlen=6)
        self.buf: deque = deque(maxlen=30)
        self.phase = idx * 5   # 30초 보고 위상(초)
        self.last_slot = -1
        self.scn: Optional[dict] = None
        self.last_state = "CONNECTED"
        self.cpu_base = 28 + idx * 3
        self.hb_delta = 30.0

    def pos(self) -> tuple[float, float]:
        s = self.s % self.total
        for i, ln in enumerate(self.seg_len):
            if s <= ln:
                a, b = self.pts[i], self.pts[(i + 1) % len(self.pts)]
                f = s / ln if ln else 0
                return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
            s -= ln
        return self.pts[0]


class Simulator:
    def __init__(self, db: Any = None, seed: int = 20260115):
        self.db = db
        self.rng = random.Random(seed)
        self.agvs: dict[str, AgvState] = {a: AgvState(a, i) for i, a in enumerate(AGV_IDS)}
        self.incident_seq = 0
        self.lock = threading.RLock()
        self.last_ts_ms = 0
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self.ticks = 0
        self.report_slot_fired = 0

    # ------------------------------------------------------------------ scenarios
    def trigger_scenario(self, agv_id: str, scenario_code: str, now_ms: Optional[int] = None) -> dict:
        if agv_id not in self.agvs:
            raise ValueError(f"unknown agv_id: {agv_id}")
        if scenario_code not in SCENARIO_T_DISCONNECT:
            raise ValueError(f"unknown scenario_code: {scenario_code}")
        now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
        with self.lock:
            st = self.agvs[agv_id]
            replaced = st.scn["code"] if st.scn else None
            st.scn = {
                "code": scenario_code, "t0": now_ms, "t_disc": SCENARIO_T_DISCONNECT[scenario_code],
                "detected_ts": None, "incident_id": None, "missed_logged": False,
                "recovered": False, "frozen_ap": st.serving,
            }
        return {
            "ok": True, "agv_id": agv_id, "scenario_code": scenario_code, "started_ts": now_ms,
            "duration_sec": SCENARIO_DURATION_SEC,
            "timeline": {"degrade_sec": [0, SCENARIO_T_DISCONNECT[scenario_code]],
                         "disconnect_sec": [SCENARIO_T_DISCONNECT[scenario_code],
                                            SCENARIO_T_DISCONNECT[scenario_code] + DISCONNECT_HOLD_SEC],
                         "recovery_sec": [SCENARIO_T_DISCONNECT[scenario_code] + DISCONNECT_HOLD_SEC,
                                          SCENARIO_DURATION_SEC]},
            "replaced_scenario": replaced,
        }

    def reset_scenarios(self) -> dict:
        with self.lock:
            cleared = []
            for st in self.agvs.values():
                if st.scn:
                    cleared.append({"agv_id": st.agv_id, "scenario_code": st.scn["code"]})
                st.scn = None
        return {"ok": True, "cleared": cleared, "cleared_count": len(cleared)}

    def active_scenarios(self, now_ms: Optional[int] = None) -> list[dict]:
        now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
        out = []
        with self.lock:
            for st in self.agvs.values():
                if st.scn:
                    t = (now_ms - st.scn["t0"]) / 1000.0
                    td = st.scn["t_disc"]
                    phase = ("DEGRADING" if t < td else "DISCONNECTED" if t < td + DISCONNECT_HOLD_SEC else "RECOVERING")
                    out.append({"agv_id": st.agv_id, "scenario_code": st.scn["code"],
                                "elapsed_sec": round(max(t, 0), 1), "phase": phase,
                                "remaining_sec": round(max(SCENARIO_DURATION_SEC - t, 0), 1),
                                "incident_id": st.scn.get("incident_id")})
        return out

    # ------------------------------------------------------------------ physics
    def _ap_rssis(self, x: float, y: float) -> tuple[list[float], float]:
        dshadow = math.hypot(x - SHADOW_CENTER[0], y - SHADOW_CENTER[1])
        shadow_pen = 6.0 * math.exp(-((dshadow / SHADOW_SIGMA) ** 2))
        out = []
        for ap in APS:
            d = max(math.hypot(x - ap["x"], y - ap["y"]), 1.0)
            out.append(-36.0 - 21.0 * math.log10(d) - shadow_pen)
        return out, shadow_pen

    def _step_agv(self, st: AgvState, ts_ms: int, ap_clients: list[int]):
        rng = self.rng
        # --- scenario phase
        scn = st.scn
        t = 0.0
        phase = "NORMAL"
        f = 0.0
        code = "NORMAL"
        if scn:
            t = (ts_ms - scn["t0"]) / 1000.0
            td = scn["t_disc"]
            code = scn["code"]
            if t >= SCENARIO_DURATION_SEC:
                st.scn = scn = None
                code = "NORMAL"
            elif t < td:
                phase = "DEGRADING"
                f = 1.0 - (1.0 - _clamp(t / td, 0, 1)) ** 2
            elif t < td + DISCONNECT_HOLD_SEC:
                phase = "DISCONNECTED"
                f = 1.0
            else:
                phase = "RECOVERING"
                rec_len = SCENARIO_DURATION_SEC - (td + DISCONNECT_HOLD_SEC)
                f = max(0.0, 1.0 - (t - td - DISCONNECT_HOLD_SEC) / rec_len)

        # --- motion
        speed = st.base_speed * (1.0 + 0.08 * math.sin(ts_ms / 7000.0 + st.idx))
        if phase == "DEGRADING" and f > 0.5:
            speed *= 0.6
        elif phase == "DISCONNECTED":
            speed *= 0.0
        elif phase == "RECOVERING":
            speed *= 0.5 + 0.5 * (1 - f)
        st.s += speed * 1.0
        x, y = st.pos()

        # --- RF baseline
        rssis, shadow_pen = self._ap_rssis(x, y)
        if not st.serving_init:
            st.serving = max(range(len(APS)), key=lambda i: rssis[i])
            st.serving_init = True
        roaming_ms = 0.0
        beacon = 0
        sticky = code == "SCN-01" and phase in ("DEGRADING", "DISCONNECTED")
        if sticky and scn:
            st.serving = scn["frozen_ap"]
        else:
            best = max(range(len(APS)), key=lambda i: rssis[i])
            if best != st.serving and rssis[best] > rssis[st.serving] + 6.0:
                st.serving = best
                roaming_ms = rng.uniform(32, 70)
                beacon = 1
            if code == "SCN-01" and scn and phase == "RECOVERING" and not scn["recovered"]:
                st.serving = best
                scn["recovered"] = True
                roaming_ms = rng.uniform(260, 320)
        ap = APS[st.serving]
        rssi = rssis[st.serving] + rng.gauss(0, 1.2)
        demi = math.hypot(x - EMI_CENTER[0], y - EMI_CENTER[1])
        emi_shift = 8.0 * math.exp(-((demi / EMI_SIGMA) ** 2))
        nf = -95.0 + emi_shift + rng.gauss(0, 0.6)
        chan_base = 10 + 8 * ap_clients[st.serving] + rng.gauss(0, 2.0)
        cpu = st.cpu_base + rng.gauss(0, 3)
        softirq = 3 + rng.gauss(0, 0.8)
        retry_extra = 0.0
        phy_scale = 1.0
        tcp = 0.0
        send_q = 0.0
        recv_q = 0.0
        rtt_add = 0.0
        jit_add = 0.0
        chan = chan_base
        srtt_add = 0.0
        force_phy_min = None
        hb_delta = 30.0 + rng.gauss(0, 0.15)

        if code != "NORMAL" and f > 0:
            late = _clamp((f - 0.4) / 0.6, 0, 1)
            if code == "SCN-01":
                rssi -= 21 * f
                beacon += int(round(6 * f * f + rng.random()))
                retry_extra = 28 * f
                tcp = 5 * late
                send_q = 8000 * f * f
                rtt_add = 55 * f * f
                jit_add = 22 * f * f
            elif code == "SCN-02":
                rssi -= 21 * f
                nf += 16 * f
                beacon += int(round(3.5 * f * f + rng.random() * 0.8))
                retry_extra = 38 * f
                tcp = 5 * late
                send_q = 6500 * f * f
                rtt_add = 38 * f * f
                jit_add = 18 * f * f
                force_phy_min = 6.0
            elif code == "SCN-03":
                rssi = -60.0 + rng.gauss(0, 1.5)
                nf = -92.0 + rng.gauss(0, 0.5)
                chan = chan_base + (93 - chan_base) * f
                retry_extra = 22 * f
                tcp = 5.5 * late + 0.5 * f
                send_q = 7000 * f
                rtt_add = 130 * f ** 1.5
                jit_add = 55 * f
                phy_scale = 1 - 0.4 * f
            elif code == "SCN-04":
                rssi = -58.0 + rng.gauss(0, 1.0)
                nf = -95.0 + rng.gauss(0, 0.5)
                cpu = cpu + (97 - cpu) * f
                softirq = 3 + 29 * f
                recv_q = 72000 * f * f
                send_q = 3000 * f * f
                tcp = 3.5 * _clamp((f - 0.5) / 0.5, 0, 1)
                srtt_add = 150 * f * f
            hb_delta = 30.0 + 6.0 * f * f + rng.gauss(0, 0.15)
            if phase == "DISCONNECTED":
                hb_delta = 30.0 + 2.5 * (t - scn["t_disc"]) + 1.5 + rng.gauss(0, 0.2)
                tcp = max(tcp, 4 + rng.random() * 3)
                send_q = max(send_q, 9000 + rng.random() * 4000) if code != "SCN-04" else send_q
        elif beacon == 0 and rssi < -72 and rng.random() < 0.2:
            beacon = 1

        rssi = _clamp(rssi, -95, -30)
        snr = _clamp(rssi - nf, 2, 60)
        phy = _phy_from_rssi(rssi) * phy_scale * (1 + rng.gauss(0, 0.03))
        if force_phy_min is not None and f > 0:
            phy = min(phy, 144 - (144 - 6) * f) if f < 1 else 6.0
            phy = max(phy, 6.0)
        phy = _clamp(phy, 6.0, 300.0)
        retry = 2.0 + max(0.0, -65 - rssi) * 0.8 + max(0.0, 25 - snr) * 0.6 + retry_extra + rng.gauss(0, 0.6)
        if code in ("SCN-03", "SCN-04") and f > 0:
            retry = (2.0 if code == "SCN-04" else 3.0) + retry_extra + rng.gauss(0, 0.5)
        retry = _clamp(retry, 0.0, 85.0)
        chan = _clamp(chan, 2, 99)
        gw_rtt = 2.5 + 0.12 * retry + rtt_add + abs(rng.gauss(0, 0.4))
        jitter = 0.5 + 0.03 * retry + jit_add + abs(rng.gauss(0, 0.3))
        if tcp == 0 and retry > 20 and rng.random() < 0.5:
            tcp = 1.0
        tcp_i = int(max(0, round(tcp + rng.gauss(0, 0.25) * (1 if tcp else 0))))
        srtt = gw_rtt * 1.8 + 4.0 + srtt_add + abs(rng.gauss(0, 0.8))
        send_i = int(max(0, send_q))
        recv_i = int(max(0, recv_q))
        cpu = _clamp(cpu, 3, 100)
        softirq = _clamp(softirq, 0.2, 60)

        st.rssi_hist.append(rssi)
        slope = (st.rssi_hist[-1] - st.rssi_hist[0]) / max(len(st.rssi_hist) - 1, 1) if len(st.rssi_hist) > 1 else 0.0
        raw = compute_risk(rssi, slope, snr, retry, phy, tcp_i, gw_rtt, send_i, recv_i, cpu, chan)
        st.risk = 0.55 * raw + 0.45 * st.risk
        risk = st.risk
        state = "CONNECTED"
        if phase == "DISCONNECTED":
            risk = 90.0 + rng.random() * 10.0
            st.risk = risk
            state = "DISCONNECTED"
        else:
            if phase == "DEGRADING" and scn and t >= scn["t_disc"] - 14:
                risk = max(risk, 46.0 + 8 * (t - (scn["t_disc"] - 14)) / 14.0)
            risk = min(risk, 84.0)
            state = "PRE_WARNING" if risk >= 45 else "CONNECTED"
        if state == "PRE_WARNING" and phase == "DEGRADING" and scn and scn["detected_ts"] is None:
            scn["detected_ts"] = ts_ms
        if phase != "DISCONNECTED" and state == "CONNECTED":
            hb_delta = min(hb_delta, 31.0) if phase == "NORMAL" else hb_delta

        row = {
            "ts": ts_ms, "agv_id": st.agv_id, "zone_id": zone_of(x, y), "bssid": ap["bssid"],
            "pos_x": round(x, 2), "pos_y": round(y, 2), "velocity": round(speed, 2),
            "rssi": round(rssi, 1), "snr": round(snr, 1), "noise_floor": round(nf, 1), "phy_rate": round(phy, 1),
            "l2_retry_rate": round(retry, 1), "beacon_loss": int(beacon), "roaming_ms": round(roaming_ms, 1),
            "channel_util": round(chan, 1), "gw_rtt_ms": round(gw_rtt, 1), "jitter_ms": round(jitter, 1),
            "tcp_retrans": tcp_i, "tcp_srtt_ms": round(srtt, 1), "send_q_bytes": send_i, "recv_q_bytes": recv_i,
            "cpu_load": round(cpu, 1), "softirq_pct": round(softirq, 1), "hb_delta_sec": round(hb_delta, 2),
            "risk_score": round(risk, 1), "conn_state": state, "scenario_code": code if phase != "NORMAL" else "NORMAL",
        }
        st.buf.append(row)
        st.hb_delta = hb_delta
        return row, phase, t

    def _summary(self, st: AgvState) -> dict:
        b = list(st.buf)
        if not b:
            return {}
        return {
            "rssi_min": min(r["rssi"] for r in b),
            "rssi_avg": round(sum(r["rssi"] for r in b) / len(b), 1),
            "snr_min": min(r["snr"] for r in b),
            "l2_retry_max": max(r["l2_retry_rate"] for r in b),
            "tcp_retrans_sum": sum(r["tcp_retrans"] for r in b),
            "gw_rtt_max": max(r["gw_rtt_ms"] for r in b),
            "roaming_count": sum(1 for r in b if r["roaming_ms"] > 0),
            "max_risk_score": max(r["risk_score"] for r in b),
            "samples": len(b),
        }

    def _evidence(self, st: AgvState, lead: float) -> dict:
        b = list(st.buf)
        return {
            "window_sec": len(b),
            "rssi_min": min(r["rssi"] for r in b),
            "snr_min": min(r["snr"] for r in b),
            "noise_floor_max": max(r["noise_floor"] for r in b),
            "phy_rate_min": min(r["phy_rate"] for r in b),
            "l2_retry_max": max(r["l2_retry_rate"] for r in b),
            "beacon_loss_max": max(r["beacon_loss"] for r in b),
            "roaming_ms_max": max(r["roaming_ms"] for r in b),
            "channel_util_max": max(r["channel_util"] for r in b),
            "gw_rtt_max": max(r["gw_rtt_ms"] for r in b),
            "jitter_max": max(r["jitter_ms"] for r in b),
            "tcp_retrans_sum": sum(r["tcp_retrans"] for r in b),
            "send_q_max": max(r["send_q_bytes"] for r in b),
            "recv_q_max": max(r["recv_q_bytes"] for r in b),
            "cpu_max": max(r["cpu_load"] for r in b),
            "risk_max": max(r["risk_score"] for r in b),
            "lead_time_sec": lead,
            "pos": [b[-1]["pos_x"], b[-1]["pos_y"]],
            "bssid": b[-1]["bssid"],
        }

    # ------------------------------------------------------------------ tick
    def tick(self, ts_ms: int) -> dict:
        """ts_ms 시점의 1초 행(6대) / 30초 보고 / 신규 incident 를 생성해 반환한다 (DB 기록은 호출자)."""
        with self.lock:
            clients = [0] * len(APS)
            for st in self.agvs.values():
                clients[st.serving] += 1
            rows, reports, incidents = [], [], []
            ts_sec = ts_ms // 1000
            for st in self.agvs.values():
                row, phase, t = self._step_agv(st, ts_ms, clients)
                rows.append(row)
                scn = st.scn
                # 단절 시작 -> incident 기록
                if scn and phase == "DISCONNECTED" and scn["incident_id"] is None:
                    detected = scn["detected_ts"] or ts_ms
                    lead = round((ts_ms - detected) / 1000.0, 1)
                    self.incident_seq += 1
                    iid = f"INC-2026-{self.incident_seq:02d}"
                    scn["incident_id"] = iid
                    meta = SCENARIO_META[scn["code"]]
                    incidents.append({
                        "incident_id": iid, "ts_detected": detected, "ts_disconnected": ts_ms,
                        "lead_time_sec": lead, "agv_id": st.agv_id, "scenario_code": scn["code"],
                        "title": meta["title"], "severity": "CRITICAL", "root_cause_summary": meta["root_cause"],
                        "evidence_metrics_json": json.dumps(self._evidence(st, lead), ensure_ascii=False),
                        "recommended_action": meta["action"],
                    })
                # 단절 중 TIMEOUT_MISSED 보고
                if scn and phase == "DISCONNECTED" and not scn["missed_logged"] and t - scn["t_disc"] >= 6:
                    scn["missed_logged"] = True
                    reports.append({"ts": ts_ms, "agv_id": st.agv_id, "report_status": "TIMEOUT_MISSED",
                                    "hb_interval_sec": round(row["hb_delta_sec"], 2),
                                    "piggyback_summary_json": json.dumps(self._summary(st))})
                # 복구 직후 지연 보고 (블랙박스 덤프 포함)
                if scn and phase == "RECOVERING" and not scn.get("reconnect_report"):
                    scn["reconnect_report"] = True
                    s = self._summary(st)
                    s["blackbox_dump"] = True
                    reports.append({"ts": ts_ms, "agv_id": st.agv_id, "report_status": "DELAYED",
                                    "hb_interval_sec": round(row["hb_delta_sec"] + 2.0, 2),
                                    "piggyback_summary_json": json.dumps(s)})
                # 정기 30초 보고
                if phase != "DISCONNECTED" and ts_sec % 30 == st.phase % 30 and st.last_slot != ts_sec:
                    st.last_slot = ts_sec
                    hb = row["hb_delta_sec"]
                    status = "OK" if hb < 31.0 else "DELAYED" if hb < 45 else "TIMEOUT_MISSED"
                    if row["conn_state"] == "PRE_WARNING" and status == "OK":
                        status = "DELAYED"
                        hb = round(30 + rng_u(self.rng, 1.5, 6.0), 2)
                    reports.append({"ts": ts_ms, "agv_id": st.agv_id, "report_status": status,
                                    "hb_interval_sec": round(hb, 2),
                                    "piggyback_summary_json": json.dumps(self._summary(st))})
            self.last_ts_ms = ts_ms
            self.ticks += 1
        return {"rows": rows, "reports": reports, "incidents": incidents}

    def generate_history(self, db: Any, now_ms: int, seconds: int = 600) -> dict:
        """과거 seconds 초 분량을 시뮬레이션하여 db 에 일괄 적재 (4개 과거 incident 포함)."""
        start = (now_ms // 1000 - seconds + 1) * 1000
        injections = {  # (경과 초 -> (agv, scn)) : 과거 4건
            start + 40_000: ("AGV-02", "SCN-01"),
            start + 170_000: ("AGV-05", "SCN-02"),
            start + 300_000: ("AGV-03", "SCN-03"),
            start + 430_000: ("AGV-04", "SCN-04"),
        }
        all_rows, all_reports, all_inc = [], [], []
        ts = start
        while ts <= now_ms // 1000 * 1000:
            if ts in injections:
                a, c = injections[ts]
                self.trigger_scenario(a, c, now_ms=ts)
            out = self.tick(ts)
            all_rows += out["rows"]
            all_reports += out["reports"]
            all_inc += out["incidents"]
            ts += 1000
        db.insert_telemetry(all_rows)
        db.insert_reports(all_reports)
        for inc in all_inc:
            db.insert_incident(inc)
        return {"rows": len(all_rows), "reports": len(all_reports), "incidents": len(all_inc)}

    # ------------------------------------------------------------------ live loop
    async def run(self):
        self.running = True
        retention_counter = 0
        try:
            while self.running:
                loop_start = time.time()
                ts_ms = int(loop_start) * 1000
                try:
                    self._live_tick(ts_ms)
                    retention_counter += 1
                    if retention_counter % 60 == 0 and self.db is not None:
                        self.db.purge_old()
                except Exception as exc:  # pragma: no cover - 방어적 로깅
                    print(f"[simulator] tick error: {exc!r}", flush=True)
                await asyncio.sleep(max(0.05, 1.0 - (time.time() - loop_start) + 0.001))
        except asyncio.CancelledError:
            pass
        finally:
            self.running = False

    def _live_tick(self, ts_ms: int):
        """직전 tick 이후 누락 초(최대 10초)를 보충하며 기록."""
        if self.last_ts_ms and ts_ms <= self.last_ts_ms:
            return
        first = ts_ms
        if self.last_ts_ms:
            first = max(self.last_ts_ms + 1000, ts_ms - 9000)
        t = first
        while t <= ts_ms:
            out = self.tick(t)
            if self.db is not None:
                self.db.insert_telemetry(out["rows"])
                self.db.insert_reports(out["reports"])
                for inc in out["incidents"]:
                    self.db.insert_incident(inc)
            t += 1000

    def start(self):
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self.run())

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


def rng_u(rng: random.Random, a: float, b: float) -> float:
    return rng.uniform(a, b)
