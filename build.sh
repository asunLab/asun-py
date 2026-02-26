#!/usr/bin/env bash
# build.sh — Build the ason C++ pybind11 extension
# Requires: g++ (C++17), python3-dev (Python.h)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detect Python include dir and its parent (for arch-specific pyconfig.h)
PYINC=$(python3 -c "import sysconfig; print(sysconfig.get_path('include'))" 2>/dev/null)
PYINC_PARENT=$(dirname "$PYINC")

# Check for Python dev headers
if [[ ! -f "${PYINC}/Python.h" ]]; then
    echo "[ason-py] Python.h not found at ${PYINC}/Python.h"
    echo "[ason-py] Installing python3-dev ..."
    sudo apt-get install -y python3-dev 2>/dev/null \
      || { echo "ERROR: Could not install python3-dev. Please run: sudo apt-get install python3-dev"; exit 1; }
fi

SUFFIX=$(python3 -c "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX'))")
TARGET="ason${SUFFIX}"

echo "[ason-py] Compiling ${TARGET} ..."
g++ -std=c++17 -O2 -Wall -fPIC -shared \
    -I vendor \
    -I "${PYINC}" \
    -I "${PYINC_PARENT}" \
    src/ason_py.cpp \
    -o "${TARGET}"

echo "[ason-py] Build complete: ${TARGET}"
echo "[ason-py] Run tests: python3 -m pytest tests/ -v"
