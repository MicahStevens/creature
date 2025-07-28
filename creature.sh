#!/bin/bash

# Creature Browser System Launcher
# This script launches the Creature Browser from /usr/local/bin/

set -e  # Exit on any error

# Hardcoded path to the Creature Browser installation
CREATURE_DIR="~/Code/browser"
CREATURE_PY="$CREATURE_DIR/creature.py"

# Check if creature.py exists
if [[ ! -f "$CREATURE_PY" ]]; then
    echo "Error: creature.py not found at $CREATURE_PY" >&2
    exit 1
fi

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed or not in PATH" >&2
    echo "Please install uv: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi

# Change to the Creature Browser directory to ensure relative paths work correctly
cd "$CREATURE_DIR"

# Launch Creature Browser with all passed arguments
exec uv run python creature.py "$@"
