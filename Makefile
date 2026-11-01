.PHONY: install lint test train api ui up down kind-up kind-down

VENV := .venv/bin
CLUSTER := mlops
COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo docker-compose)

install:
	python3 -m venv .venv
	$(VENV)/pip install -r requirements-dev.txt

lint:
	$(VENV)/ruff check .
	$(VENV)/ruff format --check .

test:
	$(VENV)/python -m pytest -q

train:
	PYTHONPATH=src $(VENV)/python -m mlapp.train --output artifacts

api: train
	PYTHONPATH=src $(VENV)/uvicorn mlapp.api:app --reload

ui:
	$(VENV)/streamlit run streamlit_app.py

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

kind-up:
	kind create cluster --name $(CLUSTER)
	docker build -t mlops-app:local .
	kind load docker-image mlops-app:local --name $(CLUSTER)
	kubectl create namespace mlops --dry-run=client -o yaml | kubectl apply -f -
	kubectl -n mlops create secret generic grafana-admin \
		--from-literal=admin-password=$${GRAFANA_ADMIN_PASSWORD:-admin} \
		--dry-run=client -o yaml | kubectl apply -f -
	kubectl apply -k k8s
	kubectl -n mlops rollout status deployment/api deployment/ui deployment/prometheus deployment/grafana --timeout=180s

kind-down:
	kind delete cluster --name $(CLUSTER)
