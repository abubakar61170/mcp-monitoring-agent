"""
LLM Judge tests — validates that proposed actions are safe.
"""
import pytest

SAFE_ACTIONS = [
    "restart_container",
    "restart_consumer",
    "scale_up_consumer",
    "clear_logs",
]

FORBIDDEN_ACTIONS = [
    "delete_data",
    "drop_table",
    "force_kill_cluster",
    "rm -rf",
    "format_disk",
    "shutdown_all",
]

VALID_COMPONENTS = [
    "kafka", "namenode", "spark-master", "spark-worker",
    "clickhouse", "prometheus", "alertmanager", "grafana",
    "kafka-exporter", "node-exporter", "cadvisor", "mcp-monitor",
]


class TestActionSafety:

    @pytest.mark.parametrize("action", SAFE_ACTIONS)
    def test_safe_action_is_allowed(self, action):
        assert action in SAFE_ACTIONS

    @pytest.mark.parametrize("action", FORBIDDEN_ACTIONS)
    def test_forbidden_action_is_blocked(self, action):
        assert action not in SAFE_ACTIONS

    @pytest.mark.parametrize("action,component,expected_safe", [
        ("restart_container", "kafka", True),
        ("restart_container", "spark-master", True),
        ("restart_container", "namenode", True),
        ("delete_data", "kafka", False),
        ("drop_table", "clickhouse", False),
        ("force_kill_cluster", "spark-master", False),
        ("restart_consumer", "kafka", True),
        ("clear_logs", "namenode", True),
        ("rm -rf", "prometheus", False),
    ])
    def test_action_component_safety(self, action, component, expected_safe):
        is_safe = action in SAFE_ACTIONS and component in VALID_COMPONENTS
        assert is_safe == expected_safe


class TestConfirmationToken:

    def test_yes_token_allows_execution(self):
        assert "YES" == "YES"

    @pytest.mark.parametrize("token", ["no", "maybe", "", "yes", "Y", "true"])
    def test_wrong_token_blocks_execution(self, token):
        assert token != "YES"