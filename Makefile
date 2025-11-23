# Variables
PYTHON := python3
PIP := $(PYTHON) -m pip

# Install dependencies
install:
	$(PIP) install -r requirements.txt

# Format code using Black and isort
format:
	$(PYTHON) -m black .
	$(PYTHON) -m isort .

# Lint code using Pylint
lint:
	$(PYTHON) -m pylint main.py

# Clean up cache and temporary files
clean:
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -exec rm -r {} +

# Run all checks
check: clean format lint
