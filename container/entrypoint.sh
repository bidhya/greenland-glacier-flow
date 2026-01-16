#!/bin/bash
set -e

echo "=== Glacier Processing Container (Local) ==="

# Use pixi run for cleaner environment management
echo "Starting wrapper with Pixi..."
exec pixi run python3 wrapper.py "$@"

# OLD: Manual shell activation (commented out for reference)
# echo "Activating Pixi environment..."
# eval "$(pixi shell-hook --shell bash)"
# echo "Starting wrapper..."
# exec python3 wrapper.py "$@"