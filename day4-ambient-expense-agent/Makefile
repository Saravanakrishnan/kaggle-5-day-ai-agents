SHELL := /bin/bash

# Install dependencies (uv is preferred, fallback to pip)
install:
	@echo "Installing dependencies..."
	uv sync || pip install -e .

# Launch the agents‑cli playground in the background
playground:
	@echo "Launching agents‑cli playground..."
	agents-cli playground > playground.log 2>&1 &
	@echo "Playground started (check playground.log for details)"
