# Issue 4 Implementation Summary

## Listing Ingestion (JSON → DB)

This document summarizes the implementation of Issue 4: Listing ingestion system.

### ✅ Acceptance Criteria Met

1. **Idempotent ingestion**
   - Uses Supabase `upsert` operations with `listing_id` as primary key
   - Can re-run ingestion without creating duplicates
   - Updates existing listings when data changes

2. **Detect price/status changes**
   - Compares new listing data with existing database records
   - Detects price drops (new price < existing price)
   - Detects status changes (e.g., SCHEDULED → CANCELLED)
   - Detects auction rescheduling (auction_datetime changes)

3. **Generate events automatically**
   - Automatically creates `PRICE_DROPPED` events when price decreases
   - Automatically creates `AUCTION_CANCELLED` events when status changes to CANCELLED
   - Automatically creates `AUCTION_VOIDED` events when status changes to VOIDED
   - Automatically creates `AUCTION_RESCHEDULED` events when auction datetime changes

4. **Support both scraper formats**
   - `RealestateReader` for realestate.com.au JSON format
   - `DomainReader` for domain.com.au JSON format
   - Auto-detection of format from file path or content
   - Uses existing normalizers from models package

### Implementation Details

#### Architecture

```
ingestion/
├── src/ingestion/
│   ├── database.py      # SupabaseRepository - database operations
│   ├── readers.py      # JSON file readers (RealestateReader, DomainReader)
│   ├── ingester.py     # Ingester - main ingestion logic
│   └── cli.py          # Command-line interface
├── examples/
│   └── ingest_testdata.py  # Example usage
├── supabase_schema.sql      # Database schema
└── README.md                # Documentation
```

#### Key Components

1. **SupabaseRepository**
   - Handles all database operations
   - `get_listing()` - Retrieve existing listing
   - `upsert_listing()` - Insert or update listing (idempotent)
   - `add_event()` - Store events
   - `get_listing_events()` - Query events for a listing

2. **JSON Readers**
   - `RealestateReader` - Reads realestate.com.au format
   - `DomainReader` - Reads domain.com.au format
   - Auto-detection based on file path or content

3. **Ingester**
   - Main ingestion orchestration
   - Change detection logic
   - Event generation
   - Statistics tracking

#### Change Detection Logic

```python
# Price change detection
if existing_price and new_price and new_price < existing_price:
    # Generate PRICE_DROPPED event
    # Calculate drop amount and percentage

# Status change detection
if existing_status != new_status:
    # Generate appropriate event based on new status
    # (AUCTION_CANCELLED, AUCTION_VOIDED, etc.)

# Auction rescheduling detection
if existing_auction != new_auction and status == SCHEDULED:
    # Generate AUCTION_RESCHEDULED event
```

#### Database Schema

Two main tables:

1. **listings** - Stores listing data
   - Primary key: `listing_id`
   - JSONB fields for address, price_history, auction_history
   - Timestamps for created_at and updated_at

2. **events** - Stores events
   - Auto-generated UUID primary key
   - Foreign key: `listing_id`
   - JSONB field for metadata
   - Indexed for efficient querying

### Usage Examples

#### Command Line

```bash
# Ingest test data
poetry run python -m ingestion.cli ../testdata/search.json

# Specify source type
poetry run python -m ingestion.cli ../scaper/realestatecom-scraper/results/search.json --source realestate
```

#### Python API

```python
from ingestion import SupabaseRepository, Ingester
from pathlib import Path

repository = SupabaseRepository(supabase_url, supabase_key)
ingester = Ingester(repository)

# Ingest file
ingester.ingest_file(Path("../testdata/search.json"))

# Get statistics
stats = ingester.get_stats()
```

### Integration with Existing Systems

- Uses `models` package for data models and normalizers
- Integrates with `EventTimeline` for event management
- Compatible with scraper outputs from `scaper/` directory
- Works with test data from `testdata/` directory

### Statistics Tracking

The ingester tracks:
- `processed` - Total listings processed
- `created` - New listings created
- `updated` - Existing listings updated
- `events_generated` - Events automatically generated
- `errors` - Errors encountered

### Next Steps

1. Run the Supabase schema SQL to create tables
2. Test ingestion with test data
3. Set up environment variables for Supabase credentials
4. Integrate with scraper workflows for automated ingestion

