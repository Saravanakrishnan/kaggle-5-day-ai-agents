SHELL := /bin/bash

# Install dependencies (uv is preferred, fallback to pip)
install:
	@echo "Installing dependencies..."
	uv sync || pip install -e .
PLAYGROUND_PORT ?= 8081
# Launch the agents‑cli playground (default port 8081)
playground:
	@echo "Launching agents-cli playground on port $(PLAYGROUND_PORT)..."
	agents-cli playground --port $(PLAYGROUND_PORT) > playground.log 2>&1 &
	@echo "Playground started (check playground.log for details)"
