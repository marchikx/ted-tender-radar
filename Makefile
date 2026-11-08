.PHONY: verify install test lint

verify: test

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest -q
