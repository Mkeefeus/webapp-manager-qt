#!/bin/bash
# Development runner script for webapp-manager-qt
#
# Usage:
#   ./run-dev.sh              # Run with system default language
#   ./run-dev.sh --lang es    # Run with Spanish
#   ./run-dev.sh --lang fr    # Run with French
#   etc.

# Activate virtual environment
source .venv/bin/activate

# Add the library path to PYTHONPATH
export PYTHONPATH="$PWD/usr/lib/webapp-manager:$PYTHONPATH"

# Parse language argument
LANG_CODE=""
ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --lang|-l)
            LANG_CODE="$2"
            shift 2
            ;;
        *)
            ARGS+=("$1")
            shift
            ;;
    esac
done

# Set language if specified
if [ -n "$LANG_CODE" ]; then
    export LANGUAGE="${LANG_CODE}"
    export LC_ALL="${LANG_CODE}.UTF-8"
    export LANG="${LANG_CODE}.UTF-8"
    echo "Running with language: $LANG_CODE"
fi

# Run the application
python3 usr/lib/webapp-manager/webapp-manager.py "${ARGS[@]}"
