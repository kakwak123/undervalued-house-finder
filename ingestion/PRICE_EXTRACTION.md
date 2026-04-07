# Price Extraction Fix

## Issue
Listings were being ingested without price information (`current_price` was null).

## Root Cause
The realestate.com.au scraper JSON data doesn't include a direct `price` field. Price information is embedded in the `description` text as text like:
- "PRICE GUIDE $760,000 - $820,000"
- "$760,000"
- "Offers over $500,000"

## Solution
Updated `models/src/models/normalizers.py` to extract prices from description text using regex patterns:

1. **Remove HTML tags** from description
2. **Search for price patterns** like `$760,000` or `$760000`
3. **Extract numeric value** and validate it's a reasonable property price (10k - 100M)
4. **Store as Decimal** in `current_price` field

## Testing

To test the fix:

```bash
cd ingestion
# Re-ingest the data (will update existing listings)
python3 ingest.py ../testdata/search.json
```

Then verify prices are populated:

```bash
python3 verify_ingestion.py
```

Or check in Supabase dashboard - listings should now have `current_price` values populated.

## Notes

- Price extraction takes the **first price found** in the description
- If there's a price range (e.g., "$760,000 - $820,000"), it takes the **lower value**
- Only prices between $10,000 and $100,000,000 are accepted (filters out invalid matches)
- Some listings may still not have prices if:
  - Price isn't mentioned in description
  - Price format is unusual
  - Listing says "Contact Agent" or "Auction" without price

