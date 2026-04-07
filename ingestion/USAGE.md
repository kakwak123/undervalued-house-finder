# Usage Guide

## Running the Ingestion System

### Method 1: Direct Script (Recommended)

The easiest way to run ingestion is using the `ingest.py` script:

```bash
cd ingestion
python3 ingest.py ../testdata/search.json
```

This script automatically handles Python path setup.

### Method 2: Example Script

```bash
cd ingestion
python3 examples/ingest_testdata.py
```

### Method 3: With PYTHONPATH

If you want to use the module syntax, set PYTHONPATH first:

```bash
cd ingestion
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src:$(pwd)/../models/src"
python3 -m ingestion.cli ../testdata/search.json
```

## Common Issues

### ModuleNotFoundError: No module named 'ingestion'

**Solution**: Use the `ingest.py` script instead:
```bash
python3 ingest.py ../testdata/search.json
```

### ModuleNotFoundError: No module named 'models'

**Solution**: Make sure you're in the `ingestion` directory and the `models` package exists:
```bash
# Check if models exists
ls ../models/src/models

# The ingest.py script should handle this automatically
```

### ModuleNotFoundError: No module named 'supabase'

**Solution**: Install dependencies:
```bash
pip3 install -r requirements.txt
```

## Command Options

```bash
# Basic usage
python3 ingest.py <json-file>

# Specify source type
python3 ingest.py <json-file> --source realestate
python3 ingest.py <json-file> --source domain
python3 ingest.py <json-file> --source auto  # Auto-detect

# Override Supabase credentials
python3 ingest.py <json-file> --supabase-url <url> --supabase-key <key>
```

## Examples

```bash
# Ingest test data
python3 ingest.py ../testdata/search.json

# Ingest realestate.com.au scraper output
python3 ingest.py ../scaper/realestatecom-scraper/results/search.json --source realestate

# Ingest domain.com.au scraper output
python3 ingest.py ../scaper/domaincom-scraper/results/search.json --source domain
```

