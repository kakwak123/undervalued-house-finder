# Issue 2 Implementation Summary

## Core Listing Data Model

This document summarizes the implementation of Issue 2: Define core listing data model.

### ✅ Acceptance Criteria Met

1. **Model supports price & auction history**
   - `PriceHistory` model tracks price changes with timestamps
   - `AuctionHistory` model tracks auction events with timestamps
   - `Listing` model includes `price_history` and `auction_history` lists
   - Automatic history tracking via `add_price_record()` and `add_auction_record()` methods

2. **Enum-based status**
   - `ListingStatus` enum with all required values:
     - `SCHEDULED` - Auction is scheduled
     - `CANCELLED` - Auction was cancelled
     - `VOIDED` - Auction was voided
     - `SOLD` - Property has been sold
     - `WITHDRAWN` - Listing withdrawn from market
     - `ACTIVE` - Active listing (no auction scheduled)
     - `UNDER_OFFER` - Property is under offer
     - `UNKNOWN` - Status unknown or not specified

### Required Fields Implemented

All fields from the milestone specification are implemented:

- ✅ `listing_id` - Unique listing identifier (string)
- ✅ `address` - Address model with full address details
- ✅ `suburb` - Suburb name (string)
- ✅ `property_type` - PropertyType enum
- ✅ `bedrooms` - Number of bedrooms (optional int)
- ✅ `bathrooms` - Number of bathrooms (optional int)
- ✅ `land_size` - Land size in square meters (optional Decimal)
- ✅ `status` - ListingStatus enum
- ✅ `auction_datetime` - Next scheduled auction (optional datetime)
- ✅ `current_price` - Current listing price (optional Decimal)
- ✅ `previous_price` - Previous listing price (optional Decimal)

### Additional Features

Beyond the requirements, the implementation includes:

- `building_size` - Building size tracking
- `property_link` - URL to listing
- `description` - Property description
- `created_at` / `updated_at` - Timestamp tracking
- `source` - Data source identifier
- `PropertyType` enum with string normalization
- Normalizer functions for scraper data conversion

### Model Structure

```
models/
├── src/models/
│   ├── __init__.py          # Package exports
│   ├── enums.py             # ListingStatus, PropertyType
│   ├── address.py           # Address model
│   ├── listing.py           # Core Listing model
│   └── normalizers.py       # Scraper data normalization
├── tests/
│   └── test_models.py       # Comprehensive tests
├── examples/
│   └── basic_usage.py       # Usage examples
├── pyproject.toml           # Package configuration
└── README.md                # Documentation
```

### Usage Example

```python
from models import Listing, ListingStatus, PropertyType, Address
from decimal import Decimal
from datetime import datetime

# Create listing
listing = Listing(
    listing_id="149785064",
    address=Address(suburb="Dandenong North", state="Vic", postcode="3175"),
    suburb="Dandenong North",
    property_type=PropertyType.HOUSE,
    bedrooms=6,
    bathrooms=2,
    land_size=Decimal("554"),
    status=ListingStatus.SCHEDULED,
    current_price=Decimal("750000"),
)

# Track price changes
listing.add_price_record(Decimal("800000"), datetime(2024, 11, 1))
listing.add_price_record(Decimal("750000"), datetime(2024, 12, 1))
# Now: current_price=750000, previous_price=800000

# Track auction events
listing.add_auction_record(
    auction_datetime=datetime(2024, 12, 20, 10, 0, 0),
    status=ListingStatus.SCHEDULED,
)
```

### Testing

Comprehensive test suite covers:
- Listing creation and validation
- Price history tracking
- Auction history tracking
- Enum functionality
- JSON serialization
- Property type normalization

Run tests with:
```bash
cd models
poetry install
poetry run pytest
```

