"""
Tests for Prometheus alert rules — validates alerts.yml structure,
required labels, and annotation templates.
"""
import os
import pytest
from helpers import load_rules, get_all_rules, RULES_PATH


class TestAlertRulesFileStructure:

    def test_rules_file_exists(self):
        assert os.path.exists(RULES_PATH), f"alerts.yml not found at {RULES_PATH}"

    def test_rules_is_valid_yaml(self):
        data = load_rules()
        assert "groups" in data
        assert len(data["groups"]) > 0

    def test_expected_groups_exist(self):
        data = load_rules()
        group_names = [g["name"] for g in data["groups"]]
        expected = ["base-alerts", "infra", "kafka", "hdfs", "spark",
                     "clickhouse", "monitoring-partial-outage", "slo-sla"]
        for name in expected:
            assert name in group_names, f"Missing expected group: '{name}'"


class TestAlertRuleLabels:

    @pytest.mark.parametrize("group_name,rule", get_all_rules(),
                             ids=[f"{g}:{r['alert']}" for g, r in get_all_rules()])
    def test_alert_has_severity(self, group_name, rule):
        labels = rule.get("labels", {})
        assert "severity" in labels, f"Alert '{rule['alert']}' missing 'severity'"
        assert labels["severity"] in ("warning", "critical")

    @pytest.mark.parametrize("group_name,rule", get_all_rules(),
                             ids=[f"{g}:{r['alert']}" for g, r in get_all_rules()])
    def test_alert_has_priority(self, group_name, rule):
        labels = rule.get("labels", {})
        assert "priority" in labels, f"Alert '{rule['alert']}' missing 'priority'"
        assert labels["priority"] in ("P1", "P2", "P3")


class TestAlertRuleAnnotations:

    @pytest.mark.parametrize("group_name,rule", get_all_rules(),
                             ids=[f"{g}:{r['alert']}" for g, r in get_all_rules()])
    def test_alert_has_summary(self, group_name, rule):
        annotations = rule.get("annotations", {})
        assert "summary" in annotations, f"Alert '{rule['alert']}' missing 'summary'"

    @pytest.mark.parametrize("group_name,rule", get_all_rules(),
                             ids=[f"{g}:{r['alert']}" for g, r in get_all_rules()])
    def test_alert_has_description(self, group_name, rule):
        annotations = rule.get("annotations", {})
        assert "description" in annotations, f"Alert '{rule['alert']}' missing 'description'"


class TestAlertRuleExpressions:

    @pytest.mark.parametrize("group_name,rule", get_all_rules(),
                             ids=[f"{g}:{r['alert']}" for g, r in get_all_rules()])
    def test_alert_has_expr(self, group_name, rule):
        assert "expr" in rule, f"Alert '{rule['alert']}' missing 'expr'"
        assert len(str(rule["expr"]).strip()) > 0

    @pytest.mark.parametrize("group_name,rule", get_all_rules(),
                             ids=[f"{g}:{r['alert']}" for g, r in get_all_rules()])
    def test_alert_has_for_duration(self, group_name, rule):
        assert "for" in rule, f"Alert '{rule['alert']}' missing 'for' duration"