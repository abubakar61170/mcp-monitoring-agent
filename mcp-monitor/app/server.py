import os
import time
import requests
import yaml
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

PROM = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
ALERTM = os.getenv("ALERTMANAGER_URL", "http://alertmanager:9093")
GRAF = os.getenv("GRAFANA_URL", "http://grafana:3000")
API_TOKEN = os.getenv("API_TOKEN", "change-me")

GRAF_USER = os.getenv("GRAFANA_USER", "admin")
GRAF_PASS = os.getenv("GRAFANA_PASS", "admin")

app = FastAPI(title="MCP-Monitor (Task 3)", version="0.1.0")

def auth(x_api_token: str | None):
    if API_TOKEN and x_api_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API token")

@app.get("/health")
def health():
    return {"status": "ok", "time": time.time()}

class QueryRangeReq(BaseModel):
    query: str
    start: float | None = None
    end: float | None = None
    step: str = "30s"

@app.post("/tools/query_range")
def query_range(req: QueryRangeReq, x_api_token: str | None = Header(default=None)):
    auth(x_api_token)
    now = time.time()
    start = req.start or (now - 15 * 60)
    end = req.end or now
    r = requests.get(
        f"{PROM}/api/v1/query_range",
        params={"query": req.query, "start": start, "end": end, "step": req.step},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()

@app.get("/tools/list_alerts")
def list_alerts(x_api_token: str | None = Header(default=None)):
    auth(x_api_token)
    r = requests.get(f"{PROM}/api/v1/alerts", timeout=10)
    r.raise_for_status()
    return r.json()

RULES_FILE = Path("/rules/alerts.dynamic.yml")

class CreateAlertReq(BaseModel):
    alert_name: str
    expr: str
    duration: str = "1m"
    severity: str = "warning"
    priority: str = "P2"
    summary: str = ""
    description: str = ""

@app.post("/tools/create_alert")
def create_alert(req: CreateAlertReq, x_api_token: str | None = Header(default=None)):
    auth(x_api_token)

    group = {
        "name": "dynamic-alerts",
        "rules": [
            {
                "alert": req.alert_name,
                "expr": req.expr,
                "for": req.duration,
                "labels": {
                    "severity": req.severity,
                    "priority": req.priority
                },
                "annotations": {
                    "summary": req.summary or req.alert_name,
                    "description": req.description or f"Auto-generated alert: {req.alert_name}",
                },
            }
        ],
    }

    # Load existing rules (if any)
    if RULES_FILE.exists():
        data = yaml.safe_load(RULES_FILE.read_text()) or {}
    else:
        data = {}

    groups = data.get("groups", [])

    # Find or create the dynamic-alerts group
    dynamic_group = None
    for g in groups:
        if g.get("name") == "dynamic-alerts":
            dynamic_group = g
            break

    if dynamic_group is None:
        groups.append(group)
    else:
        dynamic_group.setdefault("rules", [])
        dynamic_group["rules"].append(group["rules"][0])

    data["groups"] = groups
    RULES_FILE.write_text(yaml.safe_dump(data, sort_keys=False))

    # Reload Prometheus configuration
    r = requests.post(f"{PROM}/-/reload", timeout=10)
    if r.status_code not in (200, 204):
        raise HTTPException(
            status_code=500,
            detail=f"Prometheus reload failed: {r.text}"
        )

    return {
        "status": "ok",
        "alert": req.alert_name,
        "rules_file": str(RULES_FILE)
    }


class SyncDashboardReq(BaseModel):
    dashboard_json: dict
    folderUid: str | None = None
    overwrite: bool = True

@app.post("/tools/sync_dashboard")
def sync_dashboard(
    req: SyncDashboardReq,
    x_api_token: str | None = Header(default=None)
):
    auth(x_api_token)

    payload = {
        "dashboard": req.dashboard_json,
        "folderUid": req.folderUid,
        "overwrite": req.overwrite,
    }

    r = requests.post(
        f"{GRAF}/api/dashboards/db",
        json=payload,
        auth=(GRAF_USER, GRAF_PASS),
        timeout=15,
    )

    if r.status_code not in (200, 202):
        raise HTTPException(status_code=500, detail=r.text)

    # safe JSON parsing
    try:
        parsed = r.json() if r.text else None
    except Exception:
        parsed = None

    return {
        "status_code": r.status_code,
        "json": parsed,
        "text": r.text,
    }


