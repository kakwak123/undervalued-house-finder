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
├── docs/                    # Project documentation
│   ├── README.md           # Documentation index
│   └── milestones.md       # Development milestones and issues
├── scaper/                 # Web scraping modules
│   ├── realestatecom-scraper/  # realestate.com.au scraper
│   └── domaincom-scraper/      # domain.com.au scraper
├── testdata/               # Test data files
│   └── search.json         # Sample property listings
└── README.md               # This file
```

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Poetry (for dependency management)

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd undervalued-house-finder
   ```

2. **Install root-level dependencies** (for linting/formatting tools)
   ```bash
   poetry install --no-root
   ```

3. **Install dependencies** (for each scraper module)
   ```bash
   cd scaper/realestatecom-scraper
   poetry install
   
   cd ../domaincom-scraper
   poetry install
   ```

4. **Run linting/formatting**
   ```bash
   # Format code
   make format
   
   # Lint code
   make lint
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

[Add contribution guidelines here]

