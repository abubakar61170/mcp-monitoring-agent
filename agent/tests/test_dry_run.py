"""
Tests for the dry-run plan generation tool.
"""
import pytest
from tools import generate_dry_run_plan


class TestDryRunPlanGeneration:

    def test_plan_contains_component(self):
        result = generate_dry_run_plan.invoke({
            "action": "restart_container",
            "reason": "Kafka broker is down",
            "affected_component": "kafka"
        })
        assert "kafka" in result

    def test_plan_contains_action(self):
        result = generate_dry_run_plan.invoke({
            "action": "restart_container",
            "reason": "Spark Master unreachable",
            "affected_component": "spark-master"
        })
        assert "restart_container" in result

    def test_plan_contains_reason(self):
        result = generate_dry_run_plan.invoke({
            "action": "restart_container",
            "reason": "NameNode heap above 80%",
            "affected_component": "namenode"
        })
        assert "NameNode heap above 80%" in result

    def test_plan_contains_approval_status(self):
        result = generate_dry_run_plan.invoke({
            "action": "restart_container",
            "reason": "test",
            "affected_component": "test"
        })
        assert "PENDING HUMAN APPROVAL" in result

    def test_plan_contains_dry_run_header(self):
        result = generate_dry_run_plan.invoke({
            "action": "restart_container",
            "reason": "test",
            "affected_component": "test"
        })
        assert "DRY-RUN" in result

    @pytest.mark.parametrize("component", [
        "kafka", "namenode", "spark-master", "spark-worker",
        "clickhouse", "prometheus"
    ])
    def test_plan_works_for_all_components(self, component):
        result = generate_dry_run_plan.invoke({
            "action": "restart_container",
            "reason": f"{component} is unhealthy",
            "affected_component": component
        })
        assert component in result
        assert "DRY-RUN" in result