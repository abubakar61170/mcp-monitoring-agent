# MCP Monitoring & Remediation Agent

An **AI-powered SRE Agent** that monitors a Big Data cluster (Kafka, HDFS, Spark, ClickHouse), detects incidents via Prometheus alerting, diagnoses root causes using PromQL queries, consults internal runbooks, and executes safe remediation actions — all through a conversational Streamlit UI.

Built with **LangGraph** (ReAct agent), **MCP-Monitor** (Model Context Protocol server), **Prometheus**, **Alertmanager**, **Grafana**, and **Docker Compose**.

> **Course**: Big Data & Machine Learning — [ITMO University](https://itmo.ru/)  
> **Semester**: 3

### Authors

| Name | GitHub |
|------|--------|
| Abu Bakar | [@abubakar61170](https://github.com/abubakar61170) |
| Shiwei Zhang | [@Neko-v](https://github.com/Neko-v) |

---

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Components](#components)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Agent UI](#agent-ui)
  - [Incident Simulation](#incident-simulation)
  - [Health Check](#health-check)
- [Alert Rules](#alert-rules)
- [Runbooks](#runbooks)
- [Testing](#testing)
- [Makefile Reference](#makefile-reference)
- [Web Interfaces](#web-interfaces)
- [Troubleshooting](#troubleshooting)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Docker Compose Stack                         │
│                                                                     │
│  ┌──────────┐    ┌────────────┐    ┌─────────────┐                 │
│  │ Kafka    │    │ HDFS       │    │ Spark       │                 │
│  │ Broker   │    │ NameNode   │    │ Master +    │                 │
│  │          │    │            │    │ Worker      │                 │
│  └────┬─────┘    └─────┬──────┘    └──────┬──────┘                 │
│       │                │                  │                         │
│  ┌────┴─────┐    ┌─────┴──────┐    ┌──────┴──────┐  ┌───────────┐ │
│  │ Kafka    │    │ JMX        │    │ Spark       │  │ClickHouse │ │
│  │ Exporter │    │ Exporter   │    │ Metrics     │  │ Exporter  │ │
│  └────┬─────┘    └─────┬──────┘    └──────┬──────┘  └─────┬─────┘ │
│       │                │                  │               │        │
│       └────────────────┼──────────────────┼───────────────┘        │
│                        │                  │                         │
│  ┌─────────────────────┴──────────────────┴─────────────────────┐  │
│  │                      Prometheus                               │  │
│  │              (Scraping + Alert Rules + SLO)                   │  │
│  └──────────┬───────────────────────────────────┬───────────────┘  │
│             │                                   │                   │
│  ┌──────────┴──────────┐             ┌──────────┴──────────┐       │
│  │    Alertmanager     │             │      Grafana        │       │
│  │  (routing, inhibit) │             │   (dashboards)      │       │
│  └──────────┬──────────┘             └─────────────────────┘       │
│             │                                                       │
│  ┌──────────┴──────────┐                                           │
│  │    MCP-Monitor      │◄── REST API (FastAPI)                     │
│  │  (Model Context     │    /tools/list_alerts                     │
│  │   Protocol Server)  │    /tools/query_range                     │
│  └──────────┬──────────┘    /tools/create_alert                    │
│             │                                                       │
│  ┌──────────┴──────────┐                                           │
│  │    SRE Agent        │◄── LangGraph ReAct Agent                  │
│  │  (LLM + Tools +    │    Streamlit UI on :8501                   │
│  │   Runbooks)         │                                            │
│  └───────────────────��─┘                                            │
└─────────────────────────────────────────────────────────────────────┘
```

### Agent Workflow (ReAct Loop)

```
User Prompt → list_active_alerts → query_prometheus → consult_runbook
                                                          │
                                              generate_dry_run_plan
                                                          │
                                              Ask User: "Execute? (yes/no)"
                                                          │
                                        execute_remediation_action (Docker API)
                                                          │
                                                  Report Result
```

---

## Project Structure

```
mcp-monitoring-agent/
├── docker-compose.yml              # All 14 services
├── Makefile                         # Lifecycle, tests, incident simulation
├── .env                             # LLM API keys (not committed)
│
├── agent/                           # SRE Remediation Agent
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── streamlit_app.py             # Streamlit chat UI
│   ├── agents.py                    # LangGraph ReAct agent setup
│   ├── graph.py                     # Graph entry point
│   ├── prompts.py                   # System prompt with container name mapping
│   ├── tools.py                     # 5 LangChain tools (alerts, PromQL, runbooks, dry-run, execute)
│   ├── runbooks.yaml                # 28 remediation runbooks (1:1 with alert rules)
│   └── tests/                       # 260 pytest tests
│       ├── conftest.py              # sys.path setup
│       ├── helpers.py               # Shared test utilities
│       ├── test_alert_rules.py      # Alert rule validation (labels, annotations, expr)
│       ├── test_runbook_lookup.py   # Runbook matching logic tests
│       ├── test_dry_run.py          # Dry-run plan generation tests
│       ├── test_mcp_endpoints.py    # MCP server integration tests
│       ├── test_judge.py            # LLM safety judge (action whitelist)
│       └── test_scenario_coverage.py # 1:1 alert ↔ runbook coverage matrix
│
├── mcp-monitor/                     # MCP Server (FastAPI)
│   ├── Dockerfile
│   └── app/
│       └── server.py                # REST API: /tools/list_alerts, /tools/query_range, etc.
│
└── monitoring/                      # Monitoring stack configuration
    ├── alertmanager/
    │   └── alertmanager.yml         # Routes, receivers, inhibition rules
    ├── prometheus/
    │   ├── prometheus.yml           # Scrape configs for all exporters
    │   └── rules/
    │       └── alerts.yml           # 28 alert rules across 8 groups
    ├── grafana/
    │   ├── provisioning/
    │   │   ├── datasources/         # Prometheus datasource auto-provisioning
    │   │   └── dashboards/          # Dashboard provisioning config
    │   └── dashboards/              # Pre-built JSON dashboards
    ├── jmx/                         # JMX exporter config for HDFS
    └── spark/
        └── metrics.properties       # Spark metrics sink configuration
```

---

## Components

### Monitored Services (Big Data Cluster)

| Service | Container | Port | Exporter |
|---------|-----------|------|----------|
| **Kafka** (KRaft) | `kafka` | 9092 | `kafka-exporter` → :9308 |
| **HDFS NameNode** | `namenode` | 9870 | JMX Exporter → :9981 |
| **Spark Master** | `spark-master` | 8080, 7077 | Built-in metrics |
| **Spark Worker** | `spark-worker` | 8082 | Built-in metrics |
| **ClickHouse** | `clickhouse` | 8123 | `clickhouse-exporter` → :9116 |

### Monitoring Stack

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| **Prometheus** | `prometheus` | 9090 | Metrics collection + alerting |
| **Alertmanager** | `alertmanager` | 9093 | Alert routing + inhibition |
| **Grafana** | `grafana` | 3000 | Dashboards + visualization |
| **cAdvisor** | `cadvisor` | 8080 | Container-level metrics |
| **Node Exporter** | `node-exporter` | 9100 | Host-level metrics |

### Agent Stack

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| **MCP-Monitor** | `mcp-monitor` | 8000 | REST API bridge to Prometheus/Alertmanager |
| **SRE Agent** | `sre-agent` | 8501 | LLM-powered remediation agent (Streamlit) |

---

## Prerequisites

- **Docker** ≥ 24.0 and **Docker Compose** ≥ 2.20
- **LLM API Key** — one of:
  - Alibaba Cloud DashScope (Qwen) API key, or
  - OpenAI API key, or
  - Any OpenAI-compatible API endpoint
- **~8 GB RAM** recommended (14 containers)
- **Windows / macOS / Linux** (Docker Desktop or Docker Engine)

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/abubakar61170/mcp-monitoring-agent.git
cd mcp-monitoring-agent
```

### 2. Configure LLM credentials

Create a `.env` file in the project root:

```env
CUSTOM_MODEL_NAME=qwen-plus
CUSTOM_MODEL_API_KEY=your-dashscope-api-key-here
CUSTOM_MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

> **Alternatively**, to use OpenAI:
> ```env
> CUSTOM_MODEL_NAME=gpt-4o
> CUSTOM_MODEL_API_KEY=sk-your-openai-key-here
> CUSTOM_MODEL_BASE_URL=https://api.openai.com/v1
> ```

### 3. Start the full stack

```bash
docker-compose up -d --build
```

Wait ~30 seconds for all services to initialize.

### 4. Verify everything is running

```bash
docker-compose ps
```

All 14 containers should show `running` status.

### 5. Open the SRE Agent

Navigate to **http://localhost:8501** in your browser.

Type:
```
Check the cluster health. What alerts are firing?
```

---

## Configuration

### Environment Variables (`.env`)

| Variable | Description | Example |
|----------|-------------|---------|
| `CUSTOM_MODEL_NAME` | LLM model name | `qwen-plus`, `gpt-4o` |
| `CUSTOM_MODEL_API_KEY` | API key for the LLM provider | `sk-...` |
| `CUSTOM_MODEL_BASE_URL` | OpenAI-compatible API endpoint | `https://api.openai.com/v1` |

### MCP-Monitor Server

| Variable | Default | Description |
|----------|---------|-------------|
| `API_TOKEN` | `change-me` | Auth token for MCP API requests |
| `PROMETHEUS_URL` | `http://prometheus:9090` | Prometheus endpoint |
| `ALERTMANAGER_URL` | `http://alertmanager:9093` | Alertmanager endpoint |
| `GRAFANA_URL` | `http://grafana:3000` | Grafana endpoint |

---

## Usage

### Agent UI

Open **http://localhost:8501** and interact with the SRE agent:

```
You: Check the cluster health. What alerts are firing? Diagnose the issue and propose a fix.

Agent: [Calls list_active_alerts]
       [Calls query_prometheus for deeper analysis]
       [Calls consult_runbook to find the playbook]
       [Calls generate_dry_run_plan]
       
       The dry-run plan proposes restarting the Kafka container...
       Do you want me to execute this plan? (yes/no)

You: yes

Agent: SUCCESS: Real Docker container 'kafka' has been restarted.
```

### Incident Simulation

Simulate real incidents to test the agent's response:

```bash
# Stop Kafka broker → triggers KafkaBrokerDown alert
make incident SCENARIO=kafka

# Stop Spark Master → triggers SparkMasterDown alert
make incident SCENARIO=spark

# Stop HDFS NameNode → triggers HDFSNameNodeDown alert
make incident SCENARIO=hdfs

# Stop ClickHouse → triggers ClickHouseDown alert
make incident SCENARIO=clickhouse

# Flood Kafka with messages → triggers KafkaConsumerLagDetected
make incident SCENARIO=kafka-lag

# CPU stress test on Spark Worker → triggers SparkWorkerCPUHigh
make incident SCENARIO=cpu
```

Recover from incidents:

```bash
make incident-stop SCENARIO=kafka
make incident-stop SCENARIO=spark
make incident-stop SCENARIO=hdfs
make incident-stop SCENARIO=clickhouse
```

> **On Windows (without `make`)**, use Docker directly:
> ```powershell
> docker stop kafka          # Simulate
> docker start kafka         # Recover
> ```

### Health Check

```bash
make health
```

This checks: container status, Prometheus rules, scrape targets, Alertmanager, MCP-Monitor, and firing alerts.

---

## Alert Rules

28 alert rules organized in 8 groups across all monitored components:

| Group | Alerts | Examples |
|-------|--------|---------|
| **base-alerts** | 1 | `MonitoringTargetDown` |
| **infra** | 6 | `NodeCPUHigh`, `NodeMemoryHigh`, `NodeDiskAlmostFull`, `ContainerRestarting`, `ContainerCPUHigh`, `ContainerMemoryHigh` |
| **kafka** | 5 | `KafkaBrokerDown`, `KafkaConsumerLagDetected`, `KafkaConsumerLagHigh`, `KafkaUnderReplicatedPartitions`, `KafkaTopicCountDrop` |
| **hdfs** | 4 | `HDFSNameNodeDown`, `HDFSNameNodeHighHeap`, `HDFSNameNodeGCPause`, `HDFSNameNodeThreadsHigh` |
| **spark** | 4 | `SparkMasterDown`, `SparkWorkerDown`, `SparkWorkerCPUHigh`, `SparkMasterCPUHigh` |
| **clickhouse** | 4 | `ClickHouseDown`, `ClickHouseTooManyConnections`, `ClickHouseSlowInserts`, `ClickHouseReplicasMaxAbsoluteDelay` |
| **monitoring** | 1 | `MonitoringPartialOutage` |
| **slo-sla** | 3 | `SLOHighErrorRate`, `SLOKafkaLagBudgetBurn`, `SLOHighLatencyP99` |

Every alert has:
- `severity` label (`warning` or `critical`)
- `priority` label (`P1`, `P2`, or `P3`)
- `summary` and `description` annotations
- `for` duration (pending period)

### Alertmanager Routing

| Severity | Route | Behavior |
|----------|-------|----------|
| `critical` | `critical-alerts` | Immediate (group_wait: 10s) |
| `warning` | `warning-alerts` | Batched (group_wait: 30s) |

**Inhibition**: Critical alerts suppress warnings for the same `alertname`.

---

## Runbooks

28 remediation runbooks in `agent/runbooks.yaml` — one for each alert, with 1:1 mapping:

```yaml
KafkaBrokerDown:
  symptom: "Kafka broker/exporter is unreachable"
  diagnosis_steps:
    - "Check 'up{job=\"kafka-exporter\"}' metric."
    - "Check Kafka container logs: docker logs kafka"
    - "Verify network connectivity between kafka and kafka-exporter."
  remediation_actions:
    - action: "restart_container"
      description: "Restart the Kafka broker container."
      safety: "SAFE - single-node will cause brief downtime."
      component: "kafka"
```

Every runbook entry contains:
- **Symptom** — human-readable description
- **Diagnosis steps** — PromQL queries and log checks
- **Remediation actions** — safe actions with safety classification and target component

---

## Testing

The test suite contains **260 tests** covering 7 test modules:

```bash
# Run all tests inside the agent container
make test
```

Or manually:

```bash
docker exec sre-agent rm -rf /app/tests
docker cp agent/tests sre-agent:/app/
docker cp monitoring/prometheus/rules/alerts.yml sre-agent:/app/tests/alerts.yml
docker exec sre-agent python -m pytest /app/tests/ -v
```

### Test Modules

| Module | Tests | What it validates |
|--------|-------|-------------------|
| `test_alert_rules.py` | 155 | Every alert has severity, priority, summary, description, expr, for |
| `test_runbook_lookup.py` | 42 | Alertname→runbook matching, keyword search, snake_case compatibility |
| `test_dry_run.py` | 11 | Dry-run plan contains component, action, reason, approval status |
| `test_judge.py` | 25 | Safe actions allowed, forbidden actions blocked, confirmation tokens |
| `test_mcp_endpoints.py` | 7 | MCP health, auth (valid/invalid token), list_alerts, query_range |
| `test_scenario_coverage.py` | 3 | 1:1 alert↔runbook mapping, no orphans, count match |
| **Total** | **260** | |

### Safety Whitelist (LLM Judge)

Only these actions are permitted:

| Action | Status |
|--------|--------|
| `restart_container` | SAFE |
| `restart_consumer` | SAFE |
| `scale_up_consumer` | SAFE |
| `clear_logs` | SAFE |
| `delete_data` | BLOCKED |
| `drop_table` | BLOCKED |
| `rm -rf` | BLOCKED |
| `format_disk` | BLOCKED |

---

## Makefile Reference

| Command | Description |
|---------|-------------|
| `make up` | Start all 14 containers with build |
| `make down` | Stop and remove containers |
| `make restart` | Full restart (down + up) |
| `make build` | Rebuild agent + mcp-monitor images |
| `make ps` | Show container status |
| `make health` | Full health check (rules, targets, alerts, MCP) |
| `make test` | Run 260 pytest tests inside container |
| `make incident SCENARIO=kafka` | Simulate incident (kafka/spark/hdfs/clickhouse/kafka-lag/cpu) |
| `make incident-stop SCENARIO=kafka` | Recover from incident |
| `make logs SVC=prometheus` | Tail logs for a specific service |
| `make clean` | Remove all containers + volumes |

---

## Web Interfaces

| Service | URL | Credentials |
|---------|-----|-------------|
| **SRE Agent (Streamlit)** | http://localhost:8501 | — |
| **Grafana** | http://localhost:3000 | admin / admin |
| **Prometheus** | http://localhost:9090 | — |
| **Alertmanager** | http://localhost:9093 | — |
| **MCP-Monitor API** | http://localhost:8000 | Token: `change-me` |
| **Spark Master UI** | http://localhost:8080 | — |
| **HDFS NameNode UI** | http://localhost:9870 | — |
| **ClickHouse HTTP** | http://localhost:8123 | default / admin |

---

## Troubleshooting

### Agent can't connect to MCP-Monitor

```bash
docker logs mcp-monitor --tail 20
docker exec sre-agent python -c "import requests; print(requests.get('http://mcp-monitor:8000/health', headers={'x-api-token':'change-me'}).json())"
```

### No alerts are firing

Alerts require the `for` duration to pass (typically 1–5 minutes). Check pending alerts:

```bash
curl -s http://localhost:9090/api/v1/alerts | python3 -m json.tool
```

### Agent returns empty responses

Check that LLM credentials are configured:

```bash
docker exec sre-agent python -c "import os; print('KEY:', 'SET' if os.getenv('CUSTOM_MODEL_API_KEY') else 'NOT SET')"
```

### Container name not found during remediation

The agent uses a container name normalization map. If a container name isn't recognized, add it to `CONTAINER_NAME_MAP` in `agent/tools.py`.

### Port conflicts

If ports 8080, 9090, or 3000 are already in use, modify the port mappings in `docker-compose.yml`:

```yaml
ports: ["9091:9090"]  # Map to a different host port
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **LLM Agent** | LangGraph, LangChain, ChatOpenAI (Qwen/GPT-4o) |
| **Agent UI** | Streamlit |
| **MCP Server** | FastAPI (Python) |
| **Monitoring** | Prometheus, Alertmanager, Grafana |
| **Exporters** | kafka-exporter, JMX exporter, cAdvisor, node-exporter, clickhouse-exporter |
| **Big Data** | Apache Kafka (KRaft), HDFS (Hadoop 3.2), Apache Spark 3.4, ClickHouse |
| **Infrastructure** | Docker, Docker Compose |
| **Testing** | pytest (260 tests) |

---

## License

---

## Authors

| Name | GitHub | Contribution |
|------|--------|-------------|
| **Abu Bakar** | [@abubakar61170](https://github.com/abubakar61170) | Agent, Monitoring stack, alert rules, runbooks, MCP server, testing, deployment |
| **Shiwei Zhang** | [@Neko-v](https://github.com/Neko-v) | Agent, testing, Dashboards |

## Course

This project was developed as part of the **Big Data & Machine Learning** program at **[ITMO University](https://itmo.ru/)** (Semester 3).

## License


This project is for educational purposes as part of the ITMO Big Data & ML curriculum.

