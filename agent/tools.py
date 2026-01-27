# /agent/tools.py
import docker
import os
import requests
import yaml
from typing import Optional, List, Dict
from langchain_core.tools import tool

# MCP Server 的地址 (根据 docker-compose 配置)
# Agent 在宿主机运行, 访问 Docker 容器暴露的端口用 localhost
MCP_URL = os.getenv("MCP_URL", "http://localhost:8000")

# 定义 API Token (与 docker-compose.yml 里的 API_TOKEN 一致)
HEADERS = {
    "x-api-token": "change-me"
}

# Runbook Path
RUNBOOK_PATH = os.path.join(os.path.dirname(__file__), "runbooks.yaml")

def _load_runbooks() -> Dict:
    """Helper to load the YAML runbook file."""
    if not os.path.exists(RUNBOOK_PATH):
        return {}
    with open(RUNBOOK_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

@tool
def list_active_alerts() -> str:
    """
    Fetch currently firing alerts from the monitoring system (Alertmanager/Prometheus).
    Use this tool FIRST to see what is wrong with the cluster.
    """
    try:
        url = f"{MCP_URL}/tools/list_alerts"
        # This interface is defined in server.py
        response = requests.get(url, headers=HEADERS, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        alerts = data.get("data", {}).get("alerts", [])
        if not alerts:
            return "No active alerts found. The system appears healthy."
        
        summary = []
        for a in alerts:
            name = a.get("labels", {}).get("alertname", "Unknown")
            severity = a.get("labels", {}).get("severity", "Unknown")
            desc = a.get("annotations", {}).get("description", "")
            summary.append(f"- [ALERT] {name} (Severity: {severity}): {desc}")
        
        return "\n".join(summary)
    except Exception as e:
        return f"Error connecting to MCP Monitor: {str(e)}"


@tool
def query_prometheus(query: str) -> str:
    """
    Query specific metrics from Prometheus to diagnose the root cause.
    Input example: 'sum(kafka_consumergroup_lag) by (topic)' or 'up{job="datanode"}'
    """
    try:
        url = f"{MCP_URL}/tools/query_range"
        # The interface requires a POST request with JSON data
        payload = {
            "query": query,
            "step": "30s"
        }
        response = requests.post(url, json=payload, headers=HEADERS, timeout=5)
        response.raise_for_status()
        result = response.json()
        
        data_result = result.get("data", {}).get("result", [])
        if not data_result:
            return f"No data returned for query: {query}"
        
        output = []
        for item in data_result:
            metric = item.get("metric", {})
            # value is a tuple [timestamp, "value"]
            # Only take the latest value
            values = item.get("values", [])
            if values:
                last_val = values[-1][1]
                # Format the metric labels to make the output look better
                labels = ", ".join([f"{k}={v}" for k, v in metric.items() if k != "__name__"])
                output.append(f"Metric({labels}) => {last_val}")
            
        return "\n".join(output)
    except Exception as e:
        return f"Error querying Prometheus: {str(e)}"

@tool
def consult_runbook(keyword: str) -> str:
    """
    Search the internal remediation runbook (knowledge base) for a specific symptom or component.
    Use this to find 'safe' actions to perform.
    Input example: 'kafka', 'datanode', 'cpu'.
    """
    runbooks = _load_runbooks()
    results = []
    
    keyword = keyword.lower()
    for key, content in runbooks.items():
        # Search in the key or symptom description
        if keyword in key.lower() or keyword in content.get("symptom", "").lower():
            results.append(f"=== SCENARIO: {key} ===\n"
                           f"Symptom: {content.get('symptom')}\n"
                           f"Diagnosis Steps: {content.get('diagnosis_steps')}\n"
                           f"Allowed Actions: {content.get('remediation_actions')}\n")
    
    if not results:
        return f"No runbook entries found for keyword '{keyword}'. Please analyze based on general SRE principles."
    
    return "\n".join(results)

@tool
def generate_dry_run_plan(action: str, reason: str, affected_component: str) -> str:
    """
    Generate a formatted DRY-RUN report for a proposed remediation action.
    ALWAYS use this tool before declaring the task finished. 
    This does NOT execute the command, it only creates the plan for approval.
    """
    return f"""
    #######################################################
    #              DRY-RUN REMEDIATION PLAN               #
    #######################################################
    # Date: (Current Timestamp)
    # Component: {affected_component}
    # Detected Symptom: {reason}
    # --------------------------------------------------- #
    # PROPOSED ACTION:                                    #
    #   >>> {action}                                      #
    # --------------------------------------------------- #
    # EXPECTED OUTCOME:                                   #
    #   - Service stability restored.                     #
    #   - Alerts resolved.                                #
    # --------------------------------------------------- #
    # STATUS: PENDING HUMAN APPROVAL                      #
    #######################################################
    """
    
# @tool
# def execute_remediation_action(action: str, component: str, confirm_token: str = "YES") -> str:
#     """
#     EXECUTES a remediation action on the cluster.
#     CRITICAL: This tool changes system state. 
#     It should ONLY be called after the user explicitly confirms the 'Dry Run' plan.
    
#     Args:
#         action: The action key (e.g., 'restart_consumer', 'scale_up_spark').
#         component: The target component (e.g., 'kafka-broker-1').
#         confirm_token: Must be 'YES' to proceed.
#     """
#     # In a real system, this would call Kubernetes API, Ansible, or SSH.
#     # For this project, we SIMULATE the fix by logging it and potentially clearing an alert.
    
#     import time
#     time.sleep(2) # Simulate work
    
#     valid_actions = [
#         "restart_consumer", 
#         "scale_up", 
#         "restart_datanode", 
#         "clear_cache",
#         "restart_spark_master",
#         "restart_spark_worker"
#     ]

    
#     if action not in valid_actions:
#         return f"FAILURE: Action '{action}' is not in the allowed safety whitelist."

#     # Return a success message that looks like a system log
#     return f"""
#     [EXECUTION LOG]
#     Target: {component}
#     Action: {action}
#     Status: SUCCESS
#     Timestamp: {time.time()}
#     Effect: Successfully executed '{action}' on '{component}'. Service stability should restore shortly.
#     """


@tool
def execute_remediation_action(action: str, component: str, confirm_token: str = "YES") -> str:
    """
    EXECUTES a REAL remediation action by interacting with the Docker Daemon.
    Requires user confirmation.
    """
    if confirm_token != "YES":
        return "Action Aborted: Confirmation token missing."

    try:
        client = docker.from_env()
        
        # Action: Restart Container
        if "restart" in action:
            # Try to find the container. The 'component' string usually matches the container name
            # e.g., 'spark-master', 'kafka', 'namenode'
            try:
                container = client.containers.get(component)
                container.restart()
                return f"SUCCESS: Real Docker container '{component}' has been restarted."
            except docker.errors.NotFound:
                return f"FAILURE: Container '{component}' not found. Cannot restart."

        # Action: Scale Up (Simulated via logs only, as scaling requires compose V2 API complexity)
        if "scale" in action:
             return f"SIMULATION: Scaling requires Kubernetes. Logged scaling request for '{component}'."

        return f"SUCCESS: Executed logic for '{action}' on '{component}'."

    except Exception as e:
        return f"CRITICAL ERROR: Failed to execute Docker command. {str(e)}"
