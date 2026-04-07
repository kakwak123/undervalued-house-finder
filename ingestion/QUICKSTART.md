# Quick Start Guide

## Setup Without Poetry

Since Poetry is not installed, use pip instead:

### Step 1: Install Dependencies

```bash
cd ingestion
pip3 install -r requirements.txt
```

Or use the setup script:

```bash
cd ingestion
bash setup_simple.sh
```

### Step 2: Set Up Database Tables

**Option A: Use Supabase Dashboard (Recommended)**

1. Go to https://supabase.com/dashboard
2. Select your project
3. Go to **SQL Editor**
4. Copy and paste the contents of `supabase_schema.sql`
5. Click **Run**

**Option B: Verify Tables Exist**

```bash
python3 setup_database.py
```

This will check if tables exist and provide instructions if they don't.

### Step 3: Test Ingestion

```bash
# Ingest test data (recommended - use the direct script)
python3 ingest.py ../testdata/search.json

# Or use the example script
python3 examples/ingest_testdata.py
```

## Installing Poetry (Optional)

If you want to use Poetry for dependency management:

```bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Add to PATH (add to ~/.zshrc or ~/.bashrc)
export PATH="$HOME/.local/bin:$PATH"

# Then use Poetry
cd ingestion
poetry install
poetry run python setup_database.py
```

## Troubleshooting

### Module Not Found Errors

If you get `ModuleNotFoundError`, make sure dependencies are installed:

```bash
pip3 install -r requirements.txt
```

### Python Path Issues

If you get import errors, make sure you're in the correct directory:

```bash
cd ingestion
python3 -m ingestion.cli ../testdata/search.json
```

### Supabase Connection Issues

Verify your Supabase credentials are set via `SUPABASE_URL` and `SUPABASE_KEY` env vars (or a `.env` file).
