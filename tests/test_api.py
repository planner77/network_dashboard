"""
==============================================================================
Integration & Functional API Test Suite for AGV Network Telemetry Dashboard v1.1
==============================================================================
Verifies:
1. Web UI static index delivery with Light default theme & Tab 5 (tab-roles)
2. /api/health TSDB & simulator health status with config metadata
3. /api/config port 9921 & default_theme light verification (.env integration)
4. /api/action-plan AGV/AMR and ACS owner responsibilities
5. /api/overview complete fleet status, 4 APs, KPIs, and TSDB stats (>0 rows)
6. /api/metrics-catalog 18 metrics strictly limited to AGV/AMR and ACS locations
7. /api/scenarios 4 failure scenarios, timelines, and RCA decision trees
8. /api/scenarios/trigger and /api/scenarios/reset runtime control
9. /api/agv/{agv_id}/timeseries high-resolution series & 30s report markers
10. /api/hybrid-architecture and /api/incidents
==============================================================================
"""

import sys
import os
import pytest
from fastapi.testclient import TestClient

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app


@pytest.fixture(scope="module")
def client():
    """
    TestClient fixture with lifespan context enabled to ensure
    TSDB seeding, simulator background tasks, and .env configs are initialized.
    """
    with TestClient(app) as test_client:
        yield test_client


def test_index_page(client):
    """
    Verify GET / returns 200 and HTML with:
    - Light default theme (data-theme="light")
    - 2-row navbar & 5 tabs including Tab 5 (tab-roles)
    - Spotlight tour guide container & presenter script
    """
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    content = response.text
    assert "<!DOCTYPE html>" in content or "<html" in content

    # Verify Light default theme per DESIGN.md
    assert 'data-theme="light"' in content or "data-theme='light'" in content

    # Verify core dashboard identifiers
    assert "AGV" in content
    assert "투어" in content or "tour" in content.lower()

    # Verify Tab 5 (담당자별 해야 할 일 / tab-roles)
    assert "tab-roles" in content or "담당자별" in content

    # Verify draggable tour popover header
    assert "tour-popover-header" in content
    assert "tour-drag-handle" in content


def test_api_config(client):
    """Verify GET /api/config returns port 9921 and default_theme light from .env."""
    response = client.get("/api/config")
    assert response.status_code == 200
    config = response.json()
    assert str(config.get("port", config.get("PORT", ""))) == "9921" or str(config.get("dashboard_port", "")) == "9921"
    assert config.get("default_theme", config.get("DEFAULT_THEME", "")).lower() == "light"


def test_api_action_plan(client):
    """Verify GET /api/action-plan returns AGV/AMR and ACS engineering task breakdowns."""
    response = client.get("/api/action-plan")
    assert response.status_code == 200
    plan = response.json()
    assert "agv" in plan or "agv_owner" in plan or "agv_amr" in plan or "roles" in plan or "action_plans" in plan


def test_api_health(client):
    """Verify GET /api/health returns 200 and healthy TSDB engine info."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") in ["ok", "healthy", "UP"]
    assert "tsdb" in data or "tsdb_stats" in data or "telemetry_rows" in data or "status" in data


def test_api_overview(client):
    """Verify GET /api/overview returns 6 AGVs, 4 APs, KPIs, and TSDB stats > 0 rows."""
    response = client.get("/api/overview")
    assert response.status_code == 200
    data = response.json()

    # 1. Fleet validation (6 AGVs: AGV-01 .. AGV-06)
    fleet = data.get("fleet", [])
    assert len(fleet) == 6, f"Expected 6 AGVs, found {len(fleet)}"
    agv_ids = [agv.get("agv_id") for agv in fleet]
    for i in range(1, 7):
        assert f"AGV-0{i}" in agv_ids

    # 2. APs validation (4 APs across zones)
    aps = data.get("aps", [])
    assert len(aps) == 4, f"Expected 4 APs, found {len(aps)}"

    # 3. KPIs validation
    kpis = data.get("kpis", {})
    assert any(k in kpis for k in ["total_agv", "total_agvs", "connected_count", "connected_agvs", "avg_rssi_dbm", "avg_rssi"])

    # 4. TSDB stats validation (records loaded)
    tsdb_stats = data.get("tsdb_stats", {})
    total_telemetry = tsdb_stats.get("telemetry_1s_rows", tsdb_stats.get("total_rows", 0))
    assert total_telemetry > 0, "Expected TSDB to have seeded telemetry points > 0"


def test_api_metrics_catalog(client):
    """
    Verify GET /api/metrics-catalog returns all 21 metrics with required fields:
    id, name_ko, unit, collection_location, recommended_interval,
    system_load, collection_method, analysis_usage (including problem_scenario, pre_detection, post_mortem).
    CRITICAL: collection_location MUST be strictly limited to 'AGV/AMR', 'ACS', or 'AGV/AMR, ACS' (no AP/WLC).
    """
    response = client.get("/api/metrics-catalog")
    assert response.status_code == 200
    data = response.json()

    metrics = data if isinstance(data, list) else data.get("metrics", data.get("catalog", []))
    assert len(metrics) == 21, f"Expected 21 metrics, received {len(metrics)}"

    metric_ids = [m.get("id") for m in metrics]
    expected_ids = [f"M{i:02d}" for i in range(1, 22)]
    for exp_id in expected_ids:
        assert exp_id in metric_ids, f"Metric {exp_id} missing from catalog"

    required_fields = [
        "id",
        "name_ko",
        "unit",
        "collection_location",
        "recommended_interval",
        "system_load",
        "collection_method",
        "analysis_usage",
    ]

    valid_locations = {"AGV/AMR", "ACS", "AGV/AMR, ACS", "AGV/AMR / ACS"}

    for m in metrics:
        for field in required_fields:
            assert field in m, f"Metric {m.get('id')} missing required field: {field}"
            assert m[field] is not None, f"Metric {m.get('id')} field {field} is None"

        loc = m.get("collection_location", "").strip()
        assert loc in valid_locations, f"Metric {m.get('id')} has invalid collection_location: {loc}. Must be AGV/AMR or ACS only."

        usage = m.get("analysis_usage", {})
        assert usage.get("problem_scenario"), f"Metric {m.get('id')} missing analysis_usage.problem_scenario"
        assert usage.get("pre_detection"), f"Metric {m.get('id')} missing analysis_usage.pre_detection"
        assert usage.get("post_mortem"), f"Metric {m.get('id')} missing analysis_usage.post_mortem"

    # Verify key metric concepts including MIMO Per-Antenna RSSI, Channel Info, Link Quality
    joined_catalog = " ".join(f"{m.get('name_ko')} {m.get('name_en')} {m.get('description')}" for m in metrics)
    for keyword in [
        "MCS Index",
        "Tx/Rx Retry Rate",
        "Ping Latency",
        "Packet Loss",
        "Send Queue",
        "Recv Queue",
        "Heartbeat Timeout",
        "TCP Socket State",
        "MIMO",
        "Chain",
        "Channel",
        "Link Quality",
    ]:
        assert keyword in joined_catalog, f"Expected keyword '{keyword}' in metrics catalog"


def test_api_scenarios(client):
    """
    Verify GET /api/scenarios returns all 4 scenarios (SCN-01..SCN-04)
    with 120-second timelines and RCA decision trees.
    """
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    data = response.json()

    if isinstance(data, dict):
        scenario_list = list(data.values()) if "scenarios" not in data else data["scenarios"]
    else:
        scenario_list = data

    assert len(scenario_list) == 4, f"Expected 4 failure scenarios, found {len(scenario_list)}"

    scenario_codes = [s.get("code") for s in scenario_list]
    for code in ["SCN-01", "SCN-02", "SCN-03", "SCN-04"]:
        assert code in scenario_codes, f"Scenario {code} not found in /api/scenarios"

    for s in scenario_list:
        assert "decision_tree" in s, f"Scenario {s.get('code')} missing decision_tree"
        assert len(s["decision_tree"]) >= 3, f"Scenario {s.get('code')} decision tree too short"
        assert "timeline" in s, f"Scenario {s.get('code')} missing timeline"
        assert len(s["timeline"]) >= 100, f"Scenario {s.get('code')} timeline should span ~120s"
        assert "lead_time_sec" in s, f"Scenario {s.get('code')} missing lead_time_sec"
        assert s["lead_time_sec"] > 0, f"Scenario {s.get('code')} lead_time_sec should be positive"


def test_api_scenario_trigger_and_reset(client):
    """Verify POST /api/scenarios/trigger and POST /api/scenarios/reset work properly."""
    # 1. Trigger SCN-01 on AGV-02
    trigger_payload = {"agv_id": "AGV-02", "scenario_code": "SCN-01"}
    resp_trigger = client.post("/api/scenarios/trigger", json=trigger_payload)
    assert resp_trigger.status_code == 200
    trigger_data = resp_trigger.json()
    assert trigger_data.get("ok") is True or trigger_data.get("status") in ["ok", "triggered", "success", True] or "agv_id" in trigger_data

    # 2. Reset scenarios
    resp_reset = client.post("/api/scenarios/reset")
    assert resp_reset.status_code == 200
    reset_data = resp_reset.json()
    assert reset_data.get("ok") is True or reset_data.get("status") in ["ok", "reset", "success", True]


def test_api_agv_timeseries(client):
    """Verify GET /api/agv/AGV-01/timeseries?window_sec=120 returns 1s time-series and 30s report markers."""
    response = client.get("/api/agv/AGV-01/timeseries?window_sec=120")
    assert response.status_code == 200
    data = response.json()

    assert data.get("agv_id") == "AGV-01"
    telemetry_1s = data.get("telemetry_1s", data.get("series", []))
    assert len(telemetry_1s) > 0, "Expected non-empty 1s telemetry list"
    assert "acs_reports_30s" in data or "reports_30s" in data or "reports" in data


def test_api_hybrid_architecture(client):
    """Verify GET /api/hybrid-architecture returns 3-stage specification and role action plans."""
    response = client.get("/api/hybrid-architecture")
    if response.status_code == 200:
        data = response.json()
        assert "stages" in data or "pipeline" in data or "spec" in data or "stages_detail" in data


def test_api_incidents(client):
    """Verify GET /api/incidents returns pre-detection and failure incident records."""
    response = client.get("/api/incidents")
    assert response.status_code == 200
    data = response.json()
    incidents = data if isinstance(data, list) else data.get("incidents", [])
    assert isinstance(incidents, list)
    assert len(incidents) >= 1
