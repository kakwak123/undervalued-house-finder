# Property Listing Models

Core data models for property listings with support for price and auction history tracking.

## Overview

This package provides:

- **Listing** - Core property listing model
- **ListingStatus** - Enum-based status tracking
- **PropertyType** - Property type enum
- **Address** - Address model
- **PriceHistory** - Price history tracking
- **AuctionHistory** - Auction history tracking

## Installation

```bash
cd models
poetry install
```

## Usage

```python
from models import Listing, ListingStatus, PropertyType, Address
from decimal import Decimal
from datetime import datetime

# Create a listing
listing = Listing(
    listing_id="149785064",
    address=Address(
        suburb="Dandenong North",
        state="Vic",
        postcode="3175",
        full_address="31 Aberdeen Drive, Dandenong North, Vic 3175"
    ),
    suburb="Dandenong North",
    property_type=PropertyType.HOUSE,
    bedrooms=6,
    bathrooms=2,
    land_size=Decimal("554"),
    status=ListingStatus.SCHEDULED,
    current_price=Decimal("750000"),
    auction_datetime=datetime(2024, 12, 20, 10, 0, 0)
)

# Add price history
listing.add_price_record(Decimal("800000"), datetime(2024, 11, 1))
listing.add_price_record(Decimal("750000"), datetime(2024, 12, 1))

# Add auction history
listing.add_auction_record(
    auction_datetime=datetime(2024, 12, 20, 10, 0, 0),
    status=ListingStatus.SCHEDULED,
    notes="Initial auction scheduled"
)
```

## Model Features

### Listing Model

- **Core Fields**: listing_id, address, suburb, property_type, bedrooms, bathrooms, land_size
- **Status**: Enum-based status (scheduled, cancelled, voided, etc.)
- **Pricing**: current_price, previous_price with automatic tracking
- **Auction**: auction_datetime with history tracking
- **History**: Built-in price_history and auction_history lists

### History Tracking

The model automatically:
- Updates `previous_price` when a new price is added
- Sorts history by timestamp (most recent first)
- Tracks both price and auction changes over time

## Acceptance Criteria Met

✅ **Model supports price & auction history** - PriceHistory and AuctionHistory models with automatic tracking  
✅ **Enum-based status** - ListingStatus enum with all required values

