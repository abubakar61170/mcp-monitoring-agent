.PHONY: monitoring-up incident-simulate test clean

monitoring-up:
	docker-compose up -d
	@echo "Waiting for Prometheus..."
	@sleep 10
	@echo "Monitoring stack is ready at localhost:3000 (Grafana)"

incident-simulate:
	@echo "Simulating Kafka Lag..."
	# Starts a producer that floods Kafka to cause lag
	docker-compose exec kafka kafka-producer-perf-test \
		--topic test-topic \
		--num-records 100000 \
		--record-size 1000 \
		--throughput 5000 \
		--producer-props bootstrap.servers=localhost:9092
	@echo "Incident started. Check Grafana or ask the Agent."

test:
	pytest tests/
	python test_judge.py

clean:
	docker-compose down -v
