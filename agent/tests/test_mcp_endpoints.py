"""
Integration tests for MCP-Monitor server endpoints.
Requires the Docker stack to be running.
"""
import os
import pytest
import requests

MCP_URL = os.getenv("MCP_URL", "http://mcp-monitor:8000")
HEADERS = {"x-api-token": "change-me"}


def mcp_is_reachable():
    try:
        r = requests.get(f"{MCP_URL}/health", headers=HEADERS, timeout=3)
        return r.status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(not mcp_is_reachable(), reason="MCP server not running")
class TestMCPHealth:

    def test_health_endpoint(self):
        r = requests.get(f"{MCP_URL}/health", headers=HEADERS, timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"


@pytest.mark.skipif(not mcp_is_reachable(), reason="MCP server not running")
class TestMCPAuth:

    def test_invalid_token_rejected(self):
        r = requests.get(f"{MCP_URL}/tools/list_alerts",
                         headers={"x-api-token": "wrong-token"}, timeout=5)
        assert r.status_code == 401

    def test_missing_token_rejected(self):
        r = requests.get(f"{MCP_URL}/tools/list_alerts", timeout=5)
        assert r.status_code == 401


@pytest.mark.skipif(not mcp_is_reachable(), reason="MCP server not running")
class TestMCPListAlerts:

    def test_list_alerts_returns_200(self):
        r = requests.get(f"{MCP_URL}/tools/list_alerts", headers=HEADERS, timeout=5)
        assert r.status_code == 200

    def test_list_alerts_has_data_key(self):
        r = requests.get(f"{MCP_URL}/tools/list_alerts", headers=HEADERS, timeout=5)
        data = r.json()
        assert "data" in data


@pytest.mark.skipif(not mcp_is_reachable(), reason="MCP server not running")
class TestMCPQueryRange:

    def test_query_range_up_metric(self):
        payload = {"query": "up", "step": "30s"}
        r = requests.post(f"{MCP_URL}/tools/query_range",
                          json=payload, headers=HEADERS, timeout=10)
        assert r.status_code == 200

    def test_query_range_invalid_query(self):
        payload = {"query": "invalid_metric_xyz_123", "step": "30s"}
        r = requests.post(f"{MCP_URL}/tools/query_range",
                          json=payload, headers=HEADERS, timeout=10)
        assert r.status_code == 200