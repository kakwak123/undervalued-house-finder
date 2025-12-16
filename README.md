# 🏠 Undervalued House Finder

A comprehensive system for identifying and tracking undervalued property listings by analyzing price signals, auction events, and valuation comparisons.

## 📋 Scope

This project is a monorepo that combines:

1. **Data Collection** - Web scrapers for property listings (realestate.com.au, domain.com.au)
2. **Data Processing** - Ingestion, normalization, and event tracking system
3. **Valuation Engine** - Estimated price calculation and undervaluation detection
4. **Signal Intelligence** - Auction cancellation, price drops, and seller motivation signals
5. **Opportunity Ranking** - Scoring system to identify the best investment opportunities

### Core Capabilities

- **Listing Ingestion**: Import property listings from scraped data
- **Event Tracking**: Monitor auction cancellations, reschedules, price changes
- **Price Comparison**: Compare estimated vs. listing prices
- **Undervaluation Detection**: Identify properties priced below market value
- **Signal Analysis**: Detect weak demand and seller motivation indicators
- **Opportunity Scoring**: Rank listings by investment potential

## 🗺️ Roadmap

See [docs/milestones.md](./docs/milestones.md) for the complete development roadmap.

### Milestone 1 — MVP Foundations ✅ (In Progress)
- Repository setup and project structure
- Core listing data model
- Event timeline system
- Listing ingestion pipeline

### Milestone 2 — Valuation & Undervaluation Engine
- Baseline estimated price model
- Price comparison and classification
- Undervaluation threshold detection

### Milestone 3 — Auction & Price Signal Intelligence
- Auction cancellation/rescheduling handling
- Compound signal detection (voided auction + price drop)
- Opportunity scoring engine

### Milestone 4 — User-Facing Experience
- Opportunity summary API
- Listing detail timeline view
- Filters and alerts

## 📁 Project Structure

```
undervalued-house-finder/
├── docs/                           # Project documentation
│   ├── README.md                   # Documentation index
│   └── milestones.md               # Development milestones and issues
├── scaper/                         # Web scraping modules
│   ├── realestatecom-scraper/      # realestate.com.au scraper
│   │   ├── realestate.py           # Scraper implementation
│   │   ├── run.py                  # Scraper runner
│   │   ├── test.py                 # Scraper tests
│   │   ├── pyproject.toml          # Poetry dependencies
│   │   ├── README.md               # Scraper documentation
│   │   └── results/                # Scraper output (gitignored)
│   │       ├── search.json
│   │       └── properties.json
│   ├── domaincom-scraper/          # domain.com.au scraper
│   │   ├── domaincom.py            # Scraper implementation
│   │   ├── run.py                  # Scraper runner
│   │   ├── test.py                 # Scraper tests
│   │   ├── pyproject.toml          # Poetry dependencies
│   │   ├── README.md               # Scraper documentation
│   │   └── results/                # Scraper output (gitignored)
│   │       ├── search.json
│   │       └── properties.json
│   └── EXTRACTED_FIELDS.md         # Field extraction documentation
├── testdata/                       # Test data files
│   └── search.json                 # Sample property listings for testing
├── .gitignore                      # Git ignore rules
├── Makefile                        # Build and development commands
├── pyproject.toml                  # Root-level Poetry config (linting/formatting)
└── README.md                       # This file
```

### Future Structure (Planned)

```
undervalued-house-finder/
├── api/                            # Backend API (to be added)
│   ├── src/                        # API source code
│   ├── tests/                      # API tests
│   └── pyproject.toml              # API dependencies
├── webapp/                         # React web application (to be added)
│   ├── src/                        # React source code
│   ├── public/                     # Static assets
│   └── package.json                # Node dependencies
└── shared/                         # Shared utilities (to be added)
    └── models/                     # Shared data models
```

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Poetry (for dependency management)
- Git

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd undervalued-house-finder
   ```

2. **Verify setup** (optional but recommended)
   ```bash
   bash scripts/verify-setup.sh
   ```

3. **Install root-level dependencies** (for linting/formatting tools)
   ```bash
   poetry install --no-root
   ```

4. **Install dependencies** (for each scraper module)
   ```bash
   cd scaper/realestatecom-scraper
   poetry install
   
   cd ../domaincom-scraper
   poetry install
   ```

5. **Verify build**
   ```bash
   cd ../..
   make help        # View available commands
   make clean       # Clean build artifacts
   ```

## 🛠️ Development

### Code Quality

This project uses:
- **Black** - Code formatting (line length: 120)
- **Ruff** - Fast Python linter
- **Poetry** - Dependency management

### Building Locally

```bash
# Format all code
make format

# Lint all code
make lint

# Run tests (when available)
make test
```

## 📝 License

[Add your license here]

## 🤝 Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines on contributing to this project.

