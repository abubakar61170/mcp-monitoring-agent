"""
Scenario coverage — every alert has a runbook, every runbook has an alert.
"""
import pytest
from helpers import load_runbooks, get_all_alert_names


class TestScenarioCoverage:

    def test_every_alert_has_runbook(self):
        alert_names = get_all_alert_names()
        runbook_keys = set(load_runbooks().keys())
        missing = [a for a in alert_names if a not in runbook_keys]
        assert len(missing) == 0, f"Alerts missing runbooks: {missing}"

    def test_every_runbook_has_alert(self):
        alert_names = set(get_all_alert_names())
        runbook_keys = load_runbooks().keys()
        orphaned = [k for k in runbook_keys if k not in alert_names]
        assert len(orphaned) == 0, f"Orphaned runbooks: {orphaned}"

    def test_coverage_count_matches(self):
        assert len(get_all_alert_names()) == len(load_runbooks())