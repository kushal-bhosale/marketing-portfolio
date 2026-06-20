#!/bin/bash
set -e

echo "Setting up LinkedIn Bot..."

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (Chromium only)
playwright install chromium

echo ""
echo "Setup complete! To start:"
echo "  source venv/bin/activate"
echo "  python main.py"
echo ""
echo "Then open http://localhost:8000 in your browser."
echo ""
echo "First run: click 'Open Browser', log into LinkedIn, then click 'Save Session'."
