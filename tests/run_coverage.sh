#!/usr/bin/env bash
# Run integration tests with coverage measurement.
# Requires: Konecty at http://localhost:3000, credentials in ~/.konecty/.env
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if ! command -v coverage >/dev/null 2>&1; then
    echo "Installing coverage.py..."
    pip install --user coverage
fi

echo "=== Clearing previous coverage data ==="
coverage erase

echo ""
echo "=== Running integration tests ==="
coverage run \
    --source="skills/konecty-data/scripts,skills/konecty-meta/scripts" \
    --omit="*/__pycache__/*,*/auth.py" \
    -m unittest discover \
    -s tests/integration \
    -p "test_*.py" \
    -v

echo ""
echo "=== Coverage Report ==="
coverage report --show-missing | tee tests/coverage_report.txt

echo ""
echo "=== Generating HTML report ==="
coverage html -d tests/coverage_html
coverage xml -o tests/coverage.xml

echo ""
echo "Text report : tests/coverage_report.txt"
echo "HTML report : tests/coverage_html/index.html"
echo "XML report  : tests/coverage.xml"
