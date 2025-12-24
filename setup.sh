#!/bin/bash
# Setup script for deployment
# Installs uv if not present and sets up the environment

# Install uv if not already installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Verify uv is installed
if command -v uv &> /dev/null; then
    echo "uv is installed at: $(which uv)"
else
    echo "ERROR: uv installation failed"
    exit 1
fi

