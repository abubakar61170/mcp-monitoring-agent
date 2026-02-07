# ==============================================================================
# MCP Monitoring Agent — Makefile
# ==============================================================================
# Usage:
#   make up                          — Start all 14 containers
#   make down                        — Stop and remove all containers
#   make restart                     — Restart the full stack
#   make health                      — Run full health check
#   make test                        — Run 260 pytest tests inside container
#   make incident SCENARIO=kafka     — Simulate an incident (parameterized)
#   make incident-stop SCENARIO=kafka — Recover from a simulated incident
#   make logs SVC=prometheus         — Tail logs for a specific service
#   make clean                       — Remove containers + volumes
# ==============================================================================

.PHONY: up down restart health test incident incident-stop logs clean build ps

# --- Default scenario for incident simulation ---
SCENARIO ?= kafka

# ==============================================================================
# LIFECYCLE
# ==============================================================================

up:
	docker-compose up -d --build
	@echo ""
	@echo "	  Waiting 15s for services to initialize..."
	@sleep 15
	@echo ""
	@echo "   Stack is ready!"
	@echo "   Grafana:      http://localhost:3000  (admin/admin)"
	@echo "   Prometheus:   http://localhost:9090"
	@echo "   Alertmanager: http://localhost:9093"
	@echo "   MCP-Monitor:  http://localhost:8000"
	@echo "   SRE Agent:    http://localhost:8501"

down:
	docker-compose down

restart: down up

build:
	docker-compose build --no-cache agent mcp-monitor

ps:
	docker-compose ps

clean:
	docker-compose down -v --remove-orphans
	@echo "  All containers and volumes removed."

# ==============================================================================
# HEALTH CHECK
# ==============================================================================

health:
	@echo "=== Container Status ==="
	@docker-compose ps
	@echo ""
	@echo "=== Prometheus Rules ==="
	@docker exec prometheus wget -qO- http://localhost:9090/api/v1/rules 2>/dev/null \
		| python3 -c "\
import sys,json;\
d=json.load(sys.stdin);\
groups=d.get('data',{}).get('groups',[]);\
total=sum(len(g['rules']) for g in groups);\
print(f'  Groups: {len(groups)}, Rules: {total}');\
[print(f'    - {g[\"name\"]}: {len(g[\"rules\"])} rules') for g in groups]" \
		|| echo "   Prometheus not ready"
	@echo ""
	@echo "=== Scrape Targets ==="
	@docker exec prometheus wget -qO- http://localhost:9090/api/v1/targets 2>/dev/null \
		| python3 -c "\
import sys,json;\
d=json.load(sys.stdin);\
[print(f'  {t[\"labels\"].get(\"job\",\"?\"):25s} {t[\"health\"]}') for t in d.get('data',{}).get('activeTargets',[])]" \
		|| echo "   Prometheus not ready"
	@echo ""
	@echo "=== Alertmanager ==="
	@docker exec prometheus wget -qO- http://localhost:9090/api/v1/alertmanagers 2>/dev/null \
		| python3 -c "\
import sys,json;\
d=json.load(sys.stdin);\
ams=d.get('data',{}).get('activeAlertmanagers',[]);\
print(f'  Connected: {len(ams)}');\
[print(f'    - {a[\"url\"]}') for a in ams]" \
		|| echo "   Not connected"
	@echo ""
	@echo "=== MCP-Monitor ==="
	@docker exec sre-agent python -c "\
import requests;\
r=requests.get('http://mcp-monitor:8000/health',headers={'x-api-token':'change-me'},timeout=3);\
print(f'  Status: {r.json()[\"status\"]}')" 2>/dev/null \
		|| echo "   MCP not ready"
	@echo ""
	@echo "=== Firing Alerts ==="
	@docker exec prometheus wget -qO- http://localhost:9090/api/v1/alerts 2>/dev/null \
		| python3 -c "\
import sys,json;\
d=json.load(sys.stdin);\
alerts=[a for a in d.get('data',{}).get('alerts',[]) if a['state']=='firing'];\
print(f'  Firing: {len(alerts)}');\
[print(f'     {a[\"labels\"][\"alertname\"]} ({a[\"labels\"].get(\"severity\",\"?\")})') for a in alerts]" \
		|| echo "   Prometheus not ready"

# ==============================================================================
# TESTS
# ==============================================================================

test:
	@echo " Copying test files into agent container..."
	@docker exec sre-agent rm -rf /app/tests 2>/dev/null || true
	@docker cp agent/tests sre-agent:/app/
	@docker cp monitoring/prometheus/rules/alerts.yml sre-agent:/app/tests/alerts.yml
	@echo ""
	docker exec sre-agent python -m pytest /app/tests/ -v --tb=short
	@echo ""
	@echo " All tests passed!"

# ==============================================================================
# INCIDENT SIMULATION (parameterized)
# ==============================================================================
# Usage:
#   make incident SCENARIO=kafka           — Stop Kafka broker
#   make incident SCENARIO=spark           — Stop Spark Master
#   make incident SCENARIO=hdfs            — Stop HDFS NameNode
#   make incident SCENARIO=clickhouse      — Stop ClickHouse server
#   make incident SCENARIO=kafka-lag       — Flood Kafka to create consumer lag
#   make incident SCENARIO=cpu             — Stress-test a container CPU
#
#   make incident-stop SCENARIO=kafka      — Recover Kafka
#   make incident-stop SCENARIO=spark      — Recover Spark Master
#   make incident-stop SCENARIO=hdfs       — Recover HDFS NameNode
#   make incident-stop SCENARIO=clickhouse — Recover ClickHouse
#   make incident-stop SCENARIO=kafka-lag  — (no-op, lag clears on its own)
#   make incident-stop SCENARIO=cpu        — (no-op, stress stops on its own)
# ==============================================================================

incident:
ifeq ($(SCENARIO),kafka)
	@echo " [INCIDENT] Stopping Kafka broker..."
	docker stop kafka
	@echo " KafkaBrokerDown alert will fire in ~2 minutes."
	@echo "   Run 'make incident-stop SCENARIO=kafka' to recover."
else ifeq ($(SCENARIO),spark)
	@echo " [INCIDENT] Stopping Spark Master..."
	docker stop spark-master
	@echo " SparkMasterDown alert will fire in ~2 minutes."
	@echo "   Run 'make incident-stop SCENARIO=spark' to recover."
else ifeq ($(SCENARIO),hdfs)
	@echo " [INCIDENT] Stopping HDFS NameNode..."
	docker stop namenode
	@echo " HDFSNameNodeDown alert will fire in ~2 minutes."
	@echo "   Run 'make incident-stop SCENARIO=hdfs' to recover."
else ifeq ($(SCENARIO),clickhouse)
	@echo " [INCIDENT] Stopping ClickHouse..."
	docker stop clickhouse
	@echo " ClickHouseDown alert will fire in ~2 minutes."
	@echo "   Run 'make incident-stop SCENARIO=clickhouse' to recover."
else ifeq ($(SCENARIO),kafka-lag)
	@echo " [INCIDENT] Flooding Kafka to create consumer lag..."
	docker exec kafka kafka-topics --bootstrap-server localhost:9092 \
		--create --topic test-lag-topic --partitions 3 --replication-factor 1 \
		2>/dev/null || true
	docker exec kafka kafka-producer-perf-test \
		--topic test-lag-topic \
		--num-records 500000 \
		--record-size 1000 \
		--throughput 10000 \
		--producer-props bootstrap.servers=localhost:9092
	@echo " KafkaConsumerLagDetected alert may fire if consumers can't keep up."
else ifeq ($(SCENARIO),cpu)
	@echo " [INCIDENT] Stressing CPU on spark-worker for 120 seconds..."
	docker exec -d spark-worker bash -c \
		"for i in 1 2 3 4; do (timeout 120 dd if=/dev/urandom of=/dev/null bs=1M &); done"
	@echo " ContainerCPUHigh / SparkWorkerCPUHigh alert will fire in ~5 minutes."
	@echo "   Stress auto-stops after 120 seconds."
else
	@echo " Unknown scenario: $(SCENARIO)"
	@echo ""
	@echo "Available scenarios:"
	@echo "  make incident SCENARIO=kafka        — Stop Kafka broker"
	@echo "  make incident SCENARIO=spark        — Stop Spark Master"
	@echo "  make incident SCENARIO=hdfs         — Stop HDFS NameNode"
	@echo "  make incident SCENARIO=clickhouse   — Stop ClickHouse"
	@echo "  make incident SCENARIO=kafka-lag    — Flood Kafka (consumer lag)"
	@echo "  make incident SCENARIO=cpu          — CPU stress on spark-worker"
endif


incident-stop:
ifeq ($(SCENARIO),kafka)
	@echo " [RECOVERY] Starting Kafka broker..."
	docker start kafka
	@echo " Kafka recovered. Alert should resolve in ~2 minutes."
else ifeq ($(SCENARIO),spark)
	@echo " [RECOVERY] Starting Spark Master..."
	docker start spark-master
	@echo " Spark Master recovered. Alert should resolve in ~2 minutes."
else ifeq ($(SCENARIO),hdfs)
	@echo " [RECOVERY] Starting HDFS NameNode..."
	docker start namenode
	@echo " NameNode recovered. Alert should resolve in ~2 minutes."
else ifeq ($(SCENARIO),clickhouse)
	@echo " [RECOVERY] Starting ClickHouse..."
	docker start clickhouse
	@echo " ClickHouse recovered. Alert should resolve in ~2 minutes."
else ifeq ($(SCENARIO),kafka-lag)
	@echo "  Kafka lag clears automatically once consumers catch up."
else ifeq ($(SCENARIO),cpu)
	@echo "ℹCPU stress auto-stops after 120 seconds."
else
	@echo "Unknown scenario: $(SCENARIO)"
	@echo "   Available: kafka, spark, hdfs, clickhouse, kafka-lag, cpu"
endif

# ==============================================================================
# LOGS
# ==============================================================================

SVC ?= prometheus

logs:
	docker-compose logs --tail=50 -f $(SVC)