"""
Tests for runbook lookup — verifies matching logic works for all alert names.
"""
import os
import pytest
from helpers import load_runbooks, search_runbook, RUNBOOK_PATH


class TestRunbookFileStructure:

    def test_runbook_file_exists(self):
        assert os.path.exists(RUNBOOK_PATH)

    def test_runbook_is_valid_yaml(self):
        runbooks = load_runbooks()
        assert isinstance(runbooks, dict)
        assert len(runbooks) > 0

    def test_every_entry_has_required_fields(self):
        runbooks = load_runbooks()
        for key, content in runbooks.items():
            assert "symptom" in content, f"'{key}' missing 'symptom'"
            assert "diagnosis_steps" in content, f"'{key}' missing 'diagnosis_steps'"
            assert "remediation_actions" in content, f"'{key}' missing 'remediation_actions'"

    def test_every_entry_has_nonempty_fields(self):
        runbooks = load_runbooks()
        for key, content in runbooks.items():
            assert len(content["symptom"]) > 0, f"'{key}' has empty symptom"
            assert len(content["diagnosis_steps"]) > 0, f"'{key}' has empty diagnosis_steps"
            assert len(content["remediation_actions"]) > 0, f"'{key}' has empty remediation_actions"


class TestRunbookLookupByAlertName:

    ALL_ALERT_NAMES = [
        "MonitoringTargetDown", "NodeMemoryHigh", "NodeCPUHigh",
        "NodeDiskAlmostFull", "ContainerRestarting", "ContainerCPUHigh",
        "ContainerMemoryHigh", "KafkaBrokerDown", "KafkaConsumerLagDetected",
        "KafkaConsumerLagHigh", "KafkaUnderReplicatedPartitions",
        "KafkaTopicCountDrop", "HDFSNameNodeDown", "HDFSNameNodeHighHeap",
        "HDFSNameNodeGCPause", "HDFSNameNodeThreadsHigh", "SparkMasterDown",
        "SparkWorkerDown", "SparkWorkerCPUHigh", "SparkMasterCPUHigh",
        "ClickHouseDown", "ClickHouseTooManyConnections",
        "ClickHouseSlowInserts", "ClickHouseReplicasMaxAbsoluteDelay",
        "MonitoringPartialOutage", "SLOHighErrorRate",
        "SLOKafkaLagBudgetBurn", "SLOHighLatencyP99",
    ]

    @pytest.fixture
    def runbooks(self):
        return load_runbooks()

    @pytest.mark.parametrize("alert_name", ALL_ALERT_NAMES)
    def test_alert_has_matching_runbook(self, runbooks, alert_name):
        results = search_runbook(alert_name, runbooks)
        assert len(results) > 0, f"Alert '{alert_name}' has NO matching runbook"


class TestRunbookLookupByKeyword:

    @pytest.fixture
    def runbooks(self):
        return load_runbooks()

    @pytest.mark.parametrize("keyword,expected_min", [
        ("kafka", 3), ("hdfs", 3), ("spark", 3), ("clickhouse", 3),
        ("slo", 2), ("cpu", 2), ("memory", 2), ("down", 4),
    ])
    def test_keyword_returns_results(self, runbooks, keyword, expected_min):
        results = search_runbook(keyword, runbooks)
        assert len(results) >= expected_min, f"'{keyword}' returned {len(results)}, expected >= {expected_min}"

    def test_snake_case_still_matches(self, runbooks):
        results = search_runbook("kafka_broker_down", runbooks)
        assert len(results) > 0

    def test_nonexistent_keyword_returns_empty(self, runbooks):
        results = search_runbook("zzz_nonexistent_xyz", runbooks)
        assert len(results) == 0