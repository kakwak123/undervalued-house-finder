# Listing Ingestion System

Ingestion system for importing property listings from JSON files into Supabase database.

## Features

- ✅ **Idempotent ingestion** - Can re-run without creating duplicates
- ✅ **Change detection** - Automatically detects price and status changes
- ✅ **Automatic event generation** - Generates events for price drops, auction cancellations, etc.
- ✅ **Multi-format support** - Supports both realestate.com.au and domain.com.au formats
- ✅ **Supabase integration** - Stores data in Supabase database

## Installation

### Option 1: Using Poetry (Recommended)

```bash
cd ingestion
poetry install
```

### Option 2: Using pip (No Poetry Required)

```bash
cd ingestion
pip3 install -r requirements.txt
```

Or use the setup script:

```bash
cd ingestion
bash setup_simple.sh
```

## Configuration

Set credentials via environment variables or a `.env` file in the `ingestion/` directory:

```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_KEY="your-anon-key"
```

Or copy `.env.example` to `.env` and fill in your credentials:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
```

## Usage

### Command Line

**Recommended: Use the direct script**

```bash
# Ingest test data
python3 ingest.py ../testdata/search.json

# Specify source type
python3 ingest.py ../scaper/realestatecom-scraper/results/search.json --source realestate

# Auto-detect source type
python3 ingest.py ../scaper/domaincom-scraper/results/search.json --source auto
```

**Alternative: Using module syntax (requires PYTHONPATH)**

```bash
# Set PYTHONPATH first
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src:$(pwd)/../models/src"

# Then run
python3 -m ingestion.cli ../testdata/search.json
```

### Python API

```python
from ingestion import SupabaseRepository, Ingester
from pathlib import Path

# Initialize
repository = SupabaseRepository(
    supabase_url="https://ouyqgtqlhxcpygkoplzx.supabase.co",
    supabase_key="your-api-key"
)
ingester = Ingester(repository)

# Ingest file
ingester.ingest_file(Path("../testdata/search.json"))

# Get statistics
stats = ingester.get_stats()
print(f"Processed: {stats['processed']}")
print(f"Created: {stats['created']}")
print(f"Updated: {stats['updated']}")
print(f"Events: {stats['events_generated']}")
```

## Database Setup

**Important**: Before using the ingestion system, you need to create the database tables in Supabase.

See [SETUP.md](./SETUP.md) for detailed setup instructions.

Quick setup:

1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Open SQL Editor
3. Run the SQL from `supabase_schema.sql`

Or verify tables exist:

```bash
# With Poetry:
poetry run python setup_database.py

# With pip:
python3 setup_database.py
```

## Database Schema

The system expects the following Supabase tables:

### `listings` table

- `listing_id` (text, primary key)
- `suburb` (text)
- `property_type` (text)
- `bedrooms` (integer)
- `bathrooms` (integer)
- `land_size` (text/decimal)
- `building_size` (text/decimal)
- `status` (text)
- `current_price` (text/decimal)
- `previous_price` (text/decimal)
- `auction_datetime` (timestamp)
- `property_link` (text)
- `description` (text)
- `source` (text)
- `address` (jsonb)
- `price_history` (jsonb)
- `auction_history` (jsonb)
- `created_at` (timestamp)
- `updated_at` (timestamp)

### `events` table

- `id` (uuid, primary key, auto-generated)
- `event_type` (text)
- `timestamp` (timestamp)
- `listing_id` (text)
- `metadata` (jsonb)
- `created_at` (timestamp, auto-generated)

## Acceptance Criteria Met

✅ **Idempotent ingestion** - Uses upsert operations, can re-run safely  
✅ **Detect price/status changes** - Compares new data with existing data  
✅ **Generate events automatically** - Creates events for detected changes  
✅ **Support both scraper formats** - Handles realestate.com.au and domain.com.au formats
