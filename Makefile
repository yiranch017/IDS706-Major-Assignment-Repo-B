# Thin wrappers around the canonical commands; no logic lives here.
IMAGE ?= asheville-airbnb-analysis

.PHONY: install run test docker-build docker-run

install:
	python -m pip install -r requirements.txt

run:
	python main.py

test:
	python -m pytest -v

docker-build:
	docker build -t $(IMAGE) .

docker-run:
	docker run --rm \
	  -v "$(CURDIR)/data/raw:/app/data/raw:ro" \
	  -v "$(CURDIR)/outputs:/app/outputs" \
	  $(IMAGE)
