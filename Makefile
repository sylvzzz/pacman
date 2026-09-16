PYTHON ?= python3
VENV ?= .venv
PY = $(VENV)/bin/python
CONFIG ?= config.json
# The assigned A-Maze-ing package (used as-is). Drop the wheel in vendor/
# or override:  make install MAZEGEN=/path/to/other-package
MAZEGEN ?= $(wildcard vendor/*.whl)

MYPY_FLAGS = --warn-return-any --warn-unused-ignores --ignore-missing-imports \
	--disallow-untyped-defs --check-untyped-defs

install:
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt
ifneq ($(strip $(MAZEGEN)),)
	$(PY) -m pip install "$(MAZEGEN)"
else
	@echo ">> Now install the assigned A-Maze-ing package into $(VENV):"
	@echo ">>   make install MAZEGEN=<path-or-name-of-the-package>"
endif

run:
	$(PY) pac-man.py $(CONFIG)

debug:
	$(PY) -m pdb pac-man.py $(CONFIG)

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .mypy_cache -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	find . -name "*.pyc" -delete
	rm -rf build dist

lint:
	$(PY) -m flake8 .
	$(PY) -m mypy . $(MYPY_FLAGS)

lint-strict:
	$(PY) -m flake8 .
	$(PY) -m mypy . --strict

test:
	$(PY) -m pytest -q

package:
	$(PY) -m pip install pyinstaller
	$(PY) -m PyInstaller --noconfirm pac-man.spec
	cp config.json packaging/INSTRUCTIONS.txt dist/pac-man/

.PHONY: install run debug clean lint lint-strict test package
