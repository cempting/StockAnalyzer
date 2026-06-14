#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Felix Prehn Analysis System – First-Time Setup & Run
# Run from the Analyzer directory: bash setup_and_run.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e
cd "$(dirname "$0")"

echo ""
echo "══════════════════════════════════════════════════"
echo "  Felix Prehn Weekend Analysis – Setup"
echo "══════════════════════════════════════════════════"
echo ""

# Create dirs
mkdir -p reports data logs

# Python venv
if [ ! -d ".venv" ]; then
    echo "→ Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "→ Installing dependencies (this takes ~2 min first time)..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo ""
echo "══════════════════════════════════════════════════"
echo "  Running analysis (universe: focused)"
echo "  ETA: 5–15 min depending on network speed"
echo "══════════════════════════════════════════════════"
echo ""

python run_analysis.py --universe focused

echo ""
echo "✓ Done! Open the report in your browser:"
ls -1t reports/*.html | head -1
