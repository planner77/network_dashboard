"""FastAPI 엔트리포인트: .env 설정 로더 + TSDB 시드 + 1초 시뮬레이터 + REST API + 정적 프론트엔드 서빙."""
from __future__ import annotations

import time
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import simulator as sim_mod
from .tsdb import TSDB, load_env

APP_CONFIG = load_env()

from . import metrics_catalog as mc_mod  # domain-analyst 소유 모듈

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_HTML = STATIC_DIR / "index.html"
START_TIME = time.time()


def _catalog_attr(name: str, default: Any):
    return getattr(mc_mod, name, default)


class TriggerRequest(BaseModel):
    agv_id: str
    scenario_code: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = load_env()
    app.state.config = cfg
    db = TSDB(cfg["tsdb_path"])
    sim = sim_mod.Simulator(db)
    app.state.db = db
    app.state.sim = sim
    app.state.seed_result = db.seed_initial_data(sim, seconds=cfg["tsdb_seed_history_sec"])
    sim.last_ts_ms = int(time.time()) * 1000
    sim.start()
    try:
        yield
    finally:
        await sim.stop()
        db.close()


app = FastAPI(title="AGV/AMR-ACS Network Telemetry Dashboard", version="1.1.5", lifespan=lifespan)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _db() -> TSDB:
    return app.state.db


def _sim() -> sim_mod.Simulator:
    return app.state.sim


def _cfg() -> dict[str, Any]:
    return getattr(app.state, "config", None) or load_env()


@app.get("/", include_in_schema=False)
def index():
    if INDEX_HTML.is_file():
        return FileResponse(str(INDEX_HTML), media_type="text/html")
    return JSONResponse({"detail": "frontend not built: app/static/index.html missing"}, status_code=404)


@app.get("/api/config")
def get_config():
    return _cfg()


@app.get("/api/action-plan")
def get_action_plan():
    plans = _catalog_attr("ROLE_ACTION_PLANS", None)
    if plans:
        return plans
    spec = _catalog_attr("HYBRID_ARCHITECTURE_SPEC", {})
    if isinstance(spec, dict) and "role_action_plans" in spec:
        return spec["role_action_plans"]
    return {
        "agv_owner": {
            "role": "AGV/AMR 담당자",
            "summary": "AGV 내부 1초 단위 상시 기록장(최근 5분 순환 보관), 30초 정기 보고 시 요약 데이터 동봉 전송, 사전 경고 알림 및 재연결 후 상세 기록 전송 구현",
        },
        "acs_owner": {
            "role": "ACS 담당자",
            "summary": "30초 요약 데이터 수신 및 시계열 데이터베이스(TSDB) 구축, ACS 자체 지표(M10~M16) 기록, 조기 경보 연동 제어 및 4대 원인 자동 판별 리포트 구성",
        },
    }


@app.get("/api/health")
def health():
    stats = _db().get_tsdb_stats()
    sim = _sim()
    cfg = _cfg()
    age = (time.time() * 1000 - stats["latest_ts"]) / 1000.0 if stats["latest_ts"] else None
    healthy = bool(sim.running) and age is not None and age < 15
    return {
        "status": "ok" if healthy else "degraded",
        "service": "network_dashboard",
        "version": "1.1.5",
        "uptime_sec": round(time.time() - START_TIME, 1),
        "server_time_ms": int(time.time() * 1000),
        "config": cfg,
        "simulator": {"running": bool(sim.running), "ticks": sim.ticks, "agv_count": len(sim.agvs),
                      "last_tick_ts": sim.last_ts_ms, "latest_data_age_sec": round(age, 1) if age is not None else None},
        "tsdb": {"engine": stats["engine"], "journal_mode": stats["journal_mode"],
                 "telemetry_1s_rows": stats["telemetry_1s_rows"],
                 "acs_reports_30s_rows": stats["acs_reports_30s_rows"],
                 "incident_events_rows": stats["incident_events_rows"],
                 "total_rows": stats["total_rows"], "db_size_kb": stats["db_size_kb"]},
    }


@app.get("/api/overview")
def overview():
    db, sim, cfg = _db(), _sim(), _cfg()
    now_ms = int(time.time() * 1000)
    latest = db.get_fleet_latest()
    fleet = latest["fleet"]
    active = {a["agv_id"]: a for a in sim.active_scenarios(now_ms)}
    for a in fleet:
        sc = active.get(a["agv_id"])
        a["active_scenario"] = sc
        a["data_age_sec"] = round((now_ms - a["ts"]) / 1000.0, 1)
    states = Counter(a["conn_state"] for a in fleet)
    kin = db.get_kpi_inputs(600)
    tot = kin["reports_total"]
    success = round(100.0 * (kin["reports_ok"] + kin["reports_delayed"]) / tot, 1) if tot else 100.0
    on_time = round(100.0 * kin["reports_ok"] / tot, 1) if tot else 100.0
    stats = db.get_tsdb_stats()
    kpis = {
        "total_agv": len(fleet),
        "connected_count": states.get("CONNECTED", 0),
        "pre_warning_count": states.get("PRE_WARNING", 0),
        "disconnected_count": states.get("DISCONNECTED", 0),
        "avg_rssi_dbm": round(sum(a["rssi"] for a in fleet) / len(fleet), 1) if fleet else None,
        "avg_risk_score": round(sum(a["risk_score"] for a in fleet) / len(fleet), 1) if fleet else None,
        "report_success_rate_pct": success,
        "report_on_time_rate_pct": on_time,
        "avg_hb_interval_sec": kin["avg_hb_interval_sec"],
        "reports_10min": {"total": tot, "ok": kin["reports_ok"], "delayed": kin["reports_delayed"],
                          "timeout_missed": kin["reports_missed"]},
        "avg_lead_time_sec": kin["avg_lead_time_sec"],
        "incident_count": kin["incident_count"],
        "active_scenario_count": len(active),
        "tsdb_total_rows": stats["total_rows"],
        "tsdb_write_rate": stats["write_rate"],
        "tsdb_write_rate_rows_per_sec": stats["write_rate_rows_per_sec"],
    }
    return {
        "config": cfg,
        "fleet": fleet,
        "kpis": kpis,
        "aps": latest["aps"],
        "floor_map_zones": latest["zones"],
        "floor_size": {"width_m": sim_mod.FLOOR_W, "height_m": sim_mod.FLOOR_H},
        "agv_paths": {k: [list(p) for p in v] for k, v in sim_mod.AGV_PATHS.items()},
        "active_scenarios": list(active.values()),
        "tsdb_stats": stats,
        "recent_incidents": db.get_incidents(10),
        "recent_reports_30s": db.get_recent_acs_reports(40),
        "server_time_ms": now_ms,
    }


@app.get("/api/agv/{agv_id}/timeseries")
def agv_timeseries(agv_id: str, window_sec: int = Query(180, ge=5, le=3600)):
    if agv_id not in sim_mod.AGV_PATHS:
        raise HTTPException(status_code=404, detail=f"unknown agv_id: {agv_id}")
    res = _db().get_agv_timeseries(agv_id, window_sec)
    res["server_time_ms"] = int(time.time() * 1000)
    res["active_scenario"] = next((a for a in _sim().active_scenarios() if a["agv_id"] == agv_id), None)
    return res


@app.get("/api/scenarios")
def scenarios():
    sc_map = _catalog_attr("FAILURE_SCENARIOS", {})
    items = list(sc_map.values())
    return {"count": len(items), "scenario_codes": list(sc_map.keys()), "scenarios": items,
            "active": _sim().active_scenarios()}


@app.get("/api/scenarios/{scenario_code}")
def scenario_detail(scenario_code: str):
    sc_map = _catalog_attr("FAILURE_SCENARIOS", {})
    sc = sc_map.get(scenario_code.upper())
    if sc is None:
        raise HTTPException(status_code=404, detail=f"unknown scenario_code: {scenario_code}")
    return sc


@app.post("/api/scenarios/trigger")
def scenario_trigger(req: TriggerRequest):
    try:
        return _sim().trigger_scenario(req.agv_id, req.scenario_code.upper())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/scenarios/reset")
def scenario_reset():
    return _sim().reset_scenarios()


@app.get("/api/metrics-catalog")
def metrics_catalog():
    catalog = _catalog_attr("METRICS_CATALOG", [])
    by_layer = Counter(m.get("layer_code", m.get("layer")) for m in catalog)
    by_loc = Counter()
    for m in catalog:
        for loc in str(m.get("collection_location", "")).split(","):
            if loc.strip():
                by_loc[loc.strip()] += 1
    return {
        "total": len(catalog),
        "summary": {"by_layer": dict(by_layer),
                    "by_layer_name": dict(Counter(m.get("layer") for m in catalog)),
                    "by_location": dict(by_loc)},
        "metrics": catalog,
    }


@app.get("/api/hybrid-architecture")
def hybrid_architecture():
    spec = dict(_catalog_attr("HYBRID_ARCHITECTURE_SPEC", {}) or {})
    plans = _catalog_attr("ROLE_ACTION_PLANS", None)
    if plans and "role_action_plans" not in spec:
        spec["role_action_plans"] = plans
    return spec


@app.get("/api/incidents")
def incidents(limit: int = Query(20, ge=1, le=200)):
    items = _db().get_incidents(limit)
    return {"count": len(items), "incidents": items, "server_time_ms": int(time.time() * 1000)}
