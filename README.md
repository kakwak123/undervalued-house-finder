# Undervalued House Finder

A system for identifying undervalued Melbourne properties by combining ML price modelling, auction signal tracking, and multi-source data scraping.

## Project Goal

Find properties priced below their estimated fair market value by:

- Building a regression/gradient-boosting model to predict expected prices
- Tracking failed auctions and properties with price reductions
- Scraping data from Domain and REA consistently over time
- Displaying everything in a clean, filterable web dashboard

## Undervalue Score

```
(Predicted Price - Listed Price) / Predicted Price × 100
```

- Score > 10% → potentially undervalued
- Score > 20% → significantly undervalued
- Score < 0% → overpriced relative to model

## Roadmap

See [docs/milestones.md](./docs/milestones.md) for the full roadmap.

### Milestone 1 — MVP Foundations (In Progress)

- [x] Repository setup and project structure
- [x] Core listing data model
- [x] Event timeline system
- [x] Listing ingestion pipeline

### Milestone 2 — Valuation & Undervaluation Engine

- [ ] Baseline estimated price model
- [ ] Price comparison and classification
- [ ] Undervaluation threshold detection

### Milestone 3 — Auction & Price Signal Intelligence

- [ ] Auction cancellation/rescheduling handling
- [ ] Compound signal detection (voided auction + price drop)
- [ ] Opportunity scoring engine

### Milestone 4 — User-Facing Experience

- [ ] Opportunity summary API
- [ ] Listing detail timeline view
- [ ] Filters and alerts

## Tech Stack

| Layer        | Technology                                                    |
| ------------ | ------------------------------------------------------------- |
| Data models  | Python + Pydantic v2                                          |
| Scraping     | Python (httpx + BeautifulSoup, Playwright for JS-heavy pages) |
| Data storage | Supabase (PostgreSQL)                                         |
| ML model     | scikit-learn → XGBoost / LightGBM                             |
| Backend API  | FastAPI                                                       |
| Frontend     | React + Tailwind CSS + Recharts                               |
| Scheduling   | APScheduler                                                   |

## Data Sources

| Source            | Data                                     | Method           |
| ----------------- | ---------------------------------------- | ---------------- |
| RealEstate.com.au | Listings, sold data, price drops         | Scraper          |
| Domain.com.au     | Listings, price history, auction results | Scraper          |
| REIV              | Auction clearance rates                  | Manual / scraper |
| ABS / data.gov.au | Suburb demographics, transport           | Public API       |

## Project Structure

```
undervalued-house-finder/
├── models/                         # Core data models (Pydantic)
│   ├── src/models/                 # Listing, Address, Event, enums, normalizers
│   ├── tests/
│   └── examples/
├── ingestion/                      # Scraper JSON → Supabase pipeline
│   ├── src/ingestion/              # Ingester, SupabaseRepository, readers
│   └── supabase_schema.sql
├── scaper/                         # Web scrapers
│   ├── realestatecom-scraper/
│   └── domaincom-scraper/
├── testdata/                       # Sample property listings for testing
├── docs/                           # Milestones and documentation
├── Makefile                        # Format, lint, test commands
└── pyproject.toml                  # Root-level black/ruff config
```

Planned additions: `api/` (FastAPI), `webapp/` (React), `model/` (ML pipeline), `notebooks/` (EDA).

## Getting Started

**Prerequisites:** Python 3.10+, Poetry, Git

```bash
git clone <repository-url>
cd undervalued-house-finder

# Install root-level dev tools (black, ruff)
poetry install --no-root

# Install per-package dependencies
cd models && poetry install && cd ..
cd ingestion && poetry install && cd ..
cd scaper/realestatecom-scraper && poetry install && cd ../..
cd scaper/domaincom-scraper && poetry install && cd ../..

# Verify
bash scripts/verify-setup.sh
make help
```

## Development

```bash
make format   # black (line-length 120)
make lint     # ruff
make test     # run tests

# Run model tests directly
cd models && poetry run pytest tests/
```

## Legal & Ethical Notes

- Scrapers must respect `robots.txt` and rate-limit requests (minimum 2s delay)
- Data is for personal/research use only — do not republish scraped data commercially
- Use official APIs where available

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).
