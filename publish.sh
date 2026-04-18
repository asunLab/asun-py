#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "=== asun (PyPI) publish ==="

# 1. Clean
rm -rf dist build *.egg-info

# 2. Test
echo "▸ Running tests..."
python -m pytest tests -v

# 3. Build sdist + wheel
echo "▸ Building..."
python -m build

# 4. Check
echo "▸ Twine check:"
python -m twine check dist/*

# 5. Confirm
read -rp "Publish to PyPI? [y/N] " ans
if [[ "$ans" != "y" && "$ans" != "Y" ]]; then
  echo "Aborted."
  exit 1
fi

# 6. Upload
python -m twine upload dist/*
echo "✅ Published asun to PyPI"
