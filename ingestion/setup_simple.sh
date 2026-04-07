#!/bin/bash
# Simple setup script that doesn't require Poetry

set -e

echo "Setting up ingestion system..."

# Check Python version
python3 --version

# Install dependencies
echo "Installing dependencies..."
pip3 install -r requirements.txt

# Verify installation
echo "Verifying installation..."
python3 -c "import supabase; import pydantic; print('✅ Dependencies installed successfully')"

echo ""
echo "Setup complete! You can now run:"
echo "  python3 setup_database.py"
echo "  python3 -m ingestion.cli ../testdata/search.json"

