# Contributing to Undervalued House Finder

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Poetry (for Python dependency management)
- Node.js 18+ and npm/yarn (for future React webapp development)
- Git

### Initial Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd undervalued-house-finder
   ```

2. **Install root-level dependencies**
   ```bash
   poetry install --no-root
   ```

3. **Install scraper dependencies**
   ```bash
   cd scaper/realestatecom-scraper
   poetry install
   
   cd ../domaincom-scraper
   poetry install
   ```

4. **Verify setup**
   ```bash
   cd ../..
   make help
   ```

## Development Workflow

### Code Quality

- **Format code**: `make format`
- **Lint code**: `make lint`
- **Run tests**: `make test` (when tests are available)

### Branch Naming

- `feature/issue-<number>-<short-description>` - For new features
- `fix/issue-<number>-<short-description>` - For bug fixes
- `chore/issue-<number>-<short-description>` - For maintenance tasks

### Commit Messages

Follow conventional commits format:
- `feat: add property detail API endpoint`
- `fix: correct price calculation logic`
- `chore: update dependencies`
- `docs: update README with setup instructions`

## Project Structure

This is a monorepo containing:

- **scaper/** - Web scraping modules (realestate.com.au, domain.com.au)
- **docs/** - Project documentation
- **testdata/** - Test data files
- **api/** - Backend API (planned)
- **webapp/** - React web application (planned)

## Running Scrapers

### Realestate.com.au Scraper

```bash
cd scaper/realestatecom-scraper
export SCRAPFLY_KEY="your-api-key"
poetry run python run.py
```

### Domain.com.au Scraper

```bash
cd scaper/domaincom-scraper
export SCRAPFLY_KEY="your-api-key"
poetry run python run.py
```

## Submitting Changes

1. Create a feature branch from `main`
2. Make your changes
3. Ensure code is formatted and linted (`make format && make lint`)
4. Write/update tests if applicable
5. Update documentation if needed
6. Submit a pull request with a clear description

## Code Style

- **Python**: Follow PEP 8, use Black for formatting (line length: 120)
- **TypeScript/React**: Follow ESLint rules, use Prettier (when webapp is added)
- **Documentation**: Use clear, concise language

## Questions?

Feel free to open an issue for questions or discussions about the project.

