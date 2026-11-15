"""내장형 SQLite3 WAL 시계열 DB(TSDB) 엔진.

테이블: telemetry_1s / acs_reports_30s / incident_events
기본 경로: <repo>/tsdb_data/network_telemetry.db (환경변수 TSDB_PATH 로 변경 가능)
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

from . import simulator as sim_mod

DEFAULT_DB_PATH = str(Path(__file__).resolve().parent.parent / "tsdb_data" / "network_telemetry.db")
RETENTION_SEC = 1800          # telemetry_1s 보존 30분
REPORT_RETENTION_SEC = 7200   # acs_reports_30s 보존 2시간
SEED_SECONDS = 600            # 시작 시 10분 분량 시드

TELEMETRY_COLS = [
    "ts", "agv_id", "zone_id", "bssid", "pos_x", "pos_y", "velocity", "rssi", "snr", "noise_floor", "phy_rate",
    "l2_retry_rate", "beacon_loss", "roaming_ms", "channel_util", "gw_rtt_ms", "jitter_ms", "tcp_retrans",
    "tcp_srtt_ms", "send_q_bytes", "recv_q_bytes", "cpu_load", "softirq_pct", "hb_delta_sec", "risk_score",
    "conn_state", "scenario_code",
]
INCIDENT_COLS = [
    "incident_id", "ts_detected", "ts_disconnected", "lead_time_sec", "agv_id", "scenario_code", "title",
    "severity", "root_cause_summary", "evidence_metrics_json", "recommended_action",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS telemetry_1s (
    ts INTEGER NOT NULL, agv_id TEXT NOT NULL, zone_id TEXT, bssid TEXT,
    pos_x REAL, pos_y REAL, velocity REAL,
    rssi REAL, snr REAL, noise_floor REAL, phy_rate REAL, l2_retry_rate REAL,
    beacon_loss INTEGER, roaming_ms REAL, channel_util REAL,
    gw_rtt_ms REAL, jitter_ms REAL, tcp_retrans INTEGER, tcp_srtt_ms REAL,
    send_q_bytes INTEGER, recv_q_bytes INTEGER,
    cpu_load REAL, softirq_pct REAL, hb_delta_sec REAL,
    risk_score REAL, conn_state TEXT, scenario_code TEXT
);
CREATE INDEX IF NOT EXISTS idx_telemetry_agv_ts ON telemetry_1s(agv_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON telemetry_1s(ts DESC);
CREATE TABLE IF NOT EXISTS acs_reports_30s (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, agv_id TEXT NOT NULL,
    report_status TEXT, hb_interval_sec REAL, piggyback_summary_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_reports_agv_ts ON acs_reports_30s(agv_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_reports_ts ON acs_reports_30s(ts DESC);
CREATE TABLE IF NOT EXISTS incident_events (
    incident_id TEXT PRIMARY KEY, ts_detected INTEGER, ts_disconnected INTEGER, lead_time_sec REAL,
    agv_id TEXT, scenario_code TEXT, title TEXT, severity TEXT,
    root_cause_summary TEXT, evidence_metrics_json TEXT, recommended_action TEXT
);
CREATE INDEX IF NOT EXISTS idx_incident_ts ON incident_events(ts_disconnected DESC);
"""


class TSDB:
    def __init__(self, path: Optional[str] = None):
        self.path = path or os.environ.get("TSDB_PATH") or DEFAULT_DB_PATH
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        with self.lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.executescript(SCHEMA)
        self._ins_sql = (f"INSERT INTO telemetry_1s ({','.join(TELEMETRY_COLS)}) "
                         f"VALUES ({','.join(':' + c for c in TELEMETRY_COLS)})")
        self._inc_sql = (f"INSERT OR REPLACE INTO incident_events ({','.join(INCIDENT_COLS)}) "
                         f"VALUES ({','.join(':' + c for c in INCIDENT_COLS)})")

    # ------------------------------------------------------------------ writes
    def insert_telemetry(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        with self.lock:
            self.conn.execute("BEGIN")
            try:
                self.conn.executemany(self._ins_sql, rows)
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise
        return len(rows)

    def insert_reports(self, reports: list[dict]) -> int:
        if not reports:
            return 0
        with self.lock:
            self.conn.execute("BEGIN")
            try:
                self.conn.executemany(
                    "INSERT INTO acs_reports_30s (ts, agv_id, report_status, hb_interval_sec, piggyback_summary_json) "
                    "VALUES (:ts, :agv_id, :report_status, :hb_interval_sec, :piggyback_summary_json)", reports)
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise
        return len(reports)

    def insert_incident(self, inc: dict) -> None:
        with self.lock:
            self.conn.execute(self._inc_sql, inc)

    def purge_old(self) -> None:
        now_ms = int(time.time() * 1000)
        with self.lock:
            self.conn.execute("DELETE FROM telemetry_1s WHERE ts < ?", (now_ms - RETENTION_SEC * 1000,))
            self.conn.execute("DELETE FROM acs_reports_30s WHERE ts < ?", (now_ms - REPORT_RETENTION_SEC * 1000,))

    def reset_all(self) -> None:
        with self.lock:
            for t in ("telemetry_1s", "acs_reports_30s", "incident_events"):
                self.conn.execute(f"DELETE FROM {t}")

    # ------------------------------------------------------------------ seeding
    def count_incidents(self) -> int:
        with self.lock:
            return self.conn.execute("SELECT COUNT(*) FROM incident_events").fetchone()[0]

    def seed_initial_data(self, simulator: Optional[sim_mod.Simulator] = None, force: bool = False,
                          seconds: int = SEED_SECONDS) -> dict:
        """DB가 비었거나 마지막 데이터가 2분 이상 오래되었으면 최근 `seconds`초(기본 10분)를 재생성한다.

        6 AGV x 600초 = 3,600행 + 30초 보고 + 4건 과거 incident(INC-2026-01~04)를 적재한다.
        """
        now_ms = int(time.time() * 1000)
        with self.lock:
            last = self.conn.execute("SELECT MAX(ts) FROM telemetry_1s").fetchone()[0]
        if not force and last is not None and last >= now_ms - 120_000:
            if simulator is not None:
                simulator.incident_seq = self.count_incidents()
            return {"seeded": False, "reason": "recent data present", "last_ts": last}
        self.reset_all()
        simulator = simulator or sim_mod.Simulator(self)
        simulator.incident_seq = 0
        res = simulator.generate_history(self, now_ms, seconds)
        res["seeded"] = True
        return res

    # ------------------------------------------------------------------ queries
    @staticmethod
    def _row(r: sqlite3.Row) -> dict:
        return {k: r[k] for k in r.keys()}

    def get_fleet_latest(self) -> dict:
        fleet = []
        with self.lock:
            for agv in sim_mod.AGV_IDS:
                r = self.conn.execute(
                    "SELECT * FROM telemetry_1s WHERE agv_id=? ORDER BY ts DESC LIMIT 1", (agv,)).fetchone()
                if r is None:
                    continue
                d = self._row(r)
                ap = sim_mod.BSSID_TO_AP.get(d["bssid"])
                d["ap_id"] = ap["ap_id"] if ap else None
                rep = self.conn.execute(
                    "SELECT ts, report_status, hb_interval_sec FROM acs_reports_30s WHERE agv_id=? "
                    "ORDER BY ts DESC LIMIT 1", (agv,)).fetchone()
                d["last_report"] = self._row(rep) if rep else None
                fleet.append(d)
        aps = []
        for ap in sim_mod.APS:
            clients = [a for a in fleet if a["bssid"] == ap["bssid"]]
            n = len(clients)
            util = round(sum(c["channel_util"] for c in clients) / n, 1) if n else None
            avg_rssi = round(sum(c["rssi"] for c in clients) / n, 1) if n else None
            worst = max((c["risk_score"] for c in clients), default=0.0)
            status = "OVERLOADED" if (util or 0) > 75 else "BUSY" if (util or 0) > 40 else "HEALTHY"
            aps.append({**ap, "client_count": n, "channel_util": util, "avg_client_rssi": avg_rssi,
                        "max_client_risk": worst, "status": status,
                        "clients": [c["agv_id"] for c in clients]})
        return {"fleet": fleet, "aps": aps, "zones": sim_mod.FLOOR_MAP_ZONES}

    def get_agv_timeseries(self, agv_id: str, window_sec: int = 180) -> dict:
        window_sec = max(5, min(int(window_sec), RETENTION_SEC))
        with self.lock:
            last = self.conn.execute("SELECT MAX(ts) FROM telemetry_1s WHERE agv_id=?", (agv_id,)).fetchone()[0]
            if last is None:
                return {"agv_id": agv_id, "window_sec": window_sec, "series": [], "reports_30s": [], "incidents": [],
                        "points": 0}
            since = last - window_sec * 1000
            rows = self.conn.execute(
                "SELECT * FROM telemetry_1s WHERE agv_id=? AND ts>=? ORDER BY ts ASC", (agv_id, since)).fetchall()
            reps = self.conn.execute(
                "SELECT * FROM acs_reports_30s WHERE agv_id=? AND ts>=? ORDER BY ts ASC", (agv_id, since)).fetchall()
            incs = self.conn.execute(
                "SELECT * FROM incident_events WHERE agv_id=? AND ts_disconnected>=? ORDER BY ts_disconnected ASC",
                (agv_id, since)).fetchall()
        return {
            "agv_id": agv_id, "window_sec": window_sec, "from_ts": since, "to_ts": last,
            "points": len(rows),
            "series": [self._row(r) for r in rows],
            "reports_30s": [self._report(r) for r in reps],
            "incidents": [self._incident(r) for r in incs],
        }

    @staticmethod
    def _report(r: sqlite3.Row) -> dict:
        d = {k: r[k] for k in r.keys()}
        try:
            d["piggyback_summary"] = json.loads(d.get("piggyback_summary_json") or "{}")
        except ValueError:
            d["piggyback_summary"] = {}
        return d

    @staticmethod
    def _incident(r: sqlite3.Row) -> dict:
        d = {k: r[k] for k in r.keys()}
        try:
            d["evidence_metrics"] = json.loads(d.get("evidence_metrics_json") or "{}")
        except ValueError:
            d["evidence_metrics"] = {}
        return d

    def get_recent_acs_reports(self, limit: int = 40) -> list[dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM acs_reports_30s ORDER BY ts DESC, report_id DESC LIMIT ?", (int(limit),)).fetchall()
        return [self._report(r) for r in rows]

    def get_incidents(self, limit: int = 20) -> list[dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM incident_events ORDER BY ts_disconnected DESC LIMIT ?", (int(limit),)).fetchall()
        return [self._incident(r) for r in rows]

    def get_kpi_inputs(self, window_sec: int = 600) -> dict:
        since = int(time.time() * 1000) - window_sec * 1000
        with self.lock:
            tot, ok, delayed, missed, avg_hb = self.conn.execute(
                "SELECT COUNT(*), SUM(report_status='OK'), SUM(report_status='DELAYED'), "
                "SUM(report_status='TIMEOUT_MISSED'), AVG(CASE WHEN report_status!='TIMEOUT_MISSED' "
                "THEN hb_interval_sec END) FROM acs_reports_30s WHERE ts>=?", (since,)).fetchone()
            avg_lead = self.conn.execute("SELECT AVG(lead_time_sec) FROM incident_events").fetchone()[0]
            inc_cnt = self.conn.execute("SELECT COUNT(*) FROM incident_events").fetchone()[0]
        return {"reports_total": tot or 0, "reports_ok": ok or 0, "reports_delayed": delayed or 0,
                "reports_missed": missed or 0, "avg_hb_interval_sec": round(avg_hb, 2) if avg_hb else None,
                "avg_lead_time_sec": round(avg_lead, 1) if avg_lead else None, "incident_count": inc_cnt}

    def get_tsdb_stats(self) -> dict:
        with self.lock:
            t = self.conn.execute("SELECT COUNT(*) FROM telemetry_1s").fetchone()[0]
            r = self.conn.execute("SELECT COUNT(*) FROM acs_reports_30s").fetchone()[0]
            i = self.conn.execute("SELECT COUNT(*) FROM incident_events").fetchone()[0]
            lo, hi = self.conn.execute("SELECT MIN(ts), MAX(ts) FROM telemetry_1s").fetchone()
        size = 0
        for suffix in ("", "-wal", "-shm"):
            p = self.path + suffix
            if os.path.exists(p):
                size += os.path.getsize(p)
        return {
            "telemetry_1s_rows": t, "acs_reports_30s_rows": r, "incident_events_rows": i,
            "total_rows": t + r + i,
            "db_size_kb": round(size / 1024.0, 1),
            "write_rate": "6 rows/s (1s stream) + 0.2 rows/s (30s report)",
            "write_rate_rows_per_sec": 6.2,
            "retention_window_sec": RETENTION_SEC,
            "oldest_ts": lo, "latest_ts": hi,
            "span_sec": round((hi - lo) / 1000.0) if lo and hi else 0,
            "engine": "SQLite3 WAL Time-Series Engine",
            "journal_mode": "WAL", "db_path": self.path,
        }

    def close(self) -> None:
        with self.lock:
            try:
                self.conn.close()
            except Exception:
                pass
