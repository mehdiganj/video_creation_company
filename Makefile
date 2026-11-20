.PHONY: setup doctor test preview lint

setup:
	python3 -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install -r requirements-dev.txt
	.venv/bin/pip install -e .
	@echo "Run: source .venv/bin/activate"

doctor:
	.venv/bin/videogen doctor

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check videogen tests

preview:
	.venv/bin/videogen preview $(PROJECT)
