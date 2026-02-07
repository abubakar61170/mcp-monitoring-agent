"""
Shared helpers for all test files.
"""
import os
import yaml

# --- Path resolution ---
# Priority: /rules/alerts.yml > local copy in tests/ > host relative path
_PATHS = [
    "/rules/alerts.yml",
    os.path.join(os.path.dirname(__file__), "alerts.yml"),
    os.path.join(os.path.dirname(__file__), "..", "..", "monitoring", "prometheus", "rules", "alerts.yml"),
]
RULES_PATH = next((p for p in _PATHS if os.path.exists(p)), _PATHS[-1])

RUNBOOK_PATH = os.path.join(os.path.dirname(__file__), "..", "runbooks.yaml")


def load_rules():
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_runbooks():
    with open(RUNBOOK_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_all_rules():
    data = load_rules()
    rules = []
    for group in data.get("groups", []):
        for rule in group.get("rules", []):
            rules.append((group["name"], rule))
    return rules


def get_all_alert_names():
    return [rule["alert"] for _, rule in get_all_rules()]


def normalize(s: str) -> str:
    return s.lower().replace("_", "").replace("-", "").replace(" ", "")


def search_runbook(keyword: str, runbooks: dict) -> list:
    results = []
    keyword_norm = normalize(keyword)
    for key, content in runbooks.items():
        key_norm = normalize(key)
        symptom_norm = normalize(content.get("symptom", ""))
        if (keyword_norm == key_norm or
            keyword_norm in key_norm or
            keyword_norm in symptom_norm or
            key_norm in keyword_norm):
            results.append(key)
    return results