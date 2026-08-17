.PHONY: test run clean dist

VENV := .venv
PY := $(VENV)/bin/python

test:
	$(PY) -m pytest tests/ -q

run:
	$(PY) -m videotool.cli berlin_wall --artifacts artifacts

# remove caches and throwaway environments before sharing the source
clean:
	rm -rf $(VENV) .pytest_cache
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete

# source-only archive: no venv, no caches, no generated artifacts
dist: clean
	rm -rf videotool/__pycache__ videotool/**/__pycache__ 2>/dev/null || true
	rm -f videotool-src.zip
	zip -r videotool-src.zip videotool tests docs pyproject.toml \
		README.md Makefile conftest.py .gitignore -x '*__pycache__*' '*.pyc'
	@echo "created videotool-src.zip (source only)"
