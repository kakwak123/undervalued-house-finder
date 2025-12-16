# 🗺️ GitHub Milestones

## Overview

This document outlines the development milestones for the Undervalued House Finder project. Each milestone builds upon the previous one, creating a comprehensive system for identifying and tracking undervalued property listings.

---

## Milestone 0 — Data Collection (Completed ✅)

**Goal:** Collect property listing data from major Australian real estate websites.

### Web Scrapers

The project includes two production-ready web scrapers:

- **realestate.com.au scraper** (`scaper/realestatecom-scraper/`)
  - Scrapes property search results and individual property pages
  - Extracts: property details, images, videos, floorplans, auction info, agent data
  - Uses Scrapfly API for anti-scraping bypass
  - Outputs structured JSON data

- **domain.com.au scraper** (`scaper/domaincom-scraper/`)
  - Scrapes property search results and individual property pages
  - Extracts: property details, images, schools info, suburb insights, agent data
  - Uses Scrapfly API for anti-scraping bypass
  - Outputs structured JSON data

Both scrapers are fully functional and can be used to collect property listing data for ingestion into the system.

---

## Milestone 1 — MVP Foundations

**Goal:** App can ingest listings, track auction/price events, and compare estimated vs real price.

### Issue 1: Initialize repository & project structure

- **Type:** Chore
- **Description:**
  - Set up monorepo structure
  - Add README with scope + roadmap
  - Configure linting / formatting
- **Acceptance Criteria:**
  - Repo builds locally
  - Clear folder structure committed

### Issue 2: Define core listing data model

- **Type:** Feature
- **Description:**
  Create schema for property listings.
  
  **Fields:**
  - `listing_id`
  - `address`
  - `suburb`
  - `property_type`
  - `bedrooms`, `bathrooms`, `land_size`
  - `status` (scheduled/cancelled/voided/etc)
  - `auction_datetime`
  - `current_price`
  - `previous_price`
- **Acceptance Criteria:**
  - Model supports price & auction history
  - Enum-based status

### Issue 3: Event timeline system

- **Type:** Feature
- **Description:**
  Implement event logging for listing changes.
  
  **Events:**
  - `AUCTION_CANCELLED`
  - `AUCTION_RESCHEDULED`
  - `AUCTION_VOIDED`
  - `PRICE_DROPPED`
- **Acceptance Criteria:**
  - Events stored with timestamp + metadata
  - Events queryable per listing

### Issue 4: Listing ingestion (JSON → DB)

- **Type:** Feature
- **Description:**
  Ingest property listings from scraper JSON output.
  
  **Input Sources:**
  - Scraper JSON files (realestate.com.au, domain.com.au)
  - Test data from `testdata/search.json`
- **Acceptance Criteria:**
  - Idempotent ingestion
  - Detect price/status changes
  - Generate events automatically
  - Support both scraper formats

---

## Milestone 2 — Valuation & Undervaluation Engine

**Goal:** Reliable estimated price, undervaluation classification, and ranking.

### Issue 5: Implement baseline estimated price model

- **Type:** Feature
- **Description:**
  Estimate property value using suburb medians + adjustments.
  
  **Logic:**
  - Suburb median
  - Bedrooms weighting
  - Property type multiplier
- **Acceptance Criteria:**
  - Estimated price stored per listing
  - Recomputed on data change

### Issue 6: Compare estimated price vs listing price

- **Type:** Feature
- **Description:**
  Compute undervaluation metrics.
  
  **Outputs:**
  - absolute difference
  - percentage difference
  - classification (undervalued / fair / overvalued)
- **Acceptance Criteria:**
  - Correct classification thresholds
  - Stored comparison result

### Issue 7: Undervaluation threshold detection

- **Type:** Feature
- **Description:**
  Detect when listing crosses valuation thresholds.
- **Acceptance Criteria:**
  - Emits `UNDERVALUED_THRESHOLD_CROSSED` event
  - Only fires on state change

---

## Milestone 3 — Auction & Price Signal Intelligence

**Goal:** Detect weak demand, seller motivation, and timing signals.

### Issue 8: Auction cancellation signal handling

- **Type:** Feature
- **Description:**
  Handle auction cancellation and timing reset.
- **Acceptance Criteria:**
  - Countdown stops
  - Event logged
  - Listing flagged for re-auction

### Issue 9: Re-auction & timing extension detection

- **Type:** Feature
- **Description:**
  Detect auction rescheduling.
- **Acceptance Criteria:**
  - Auction date updated
  - Countdown restarted
  - Event logged

### Issue 10: Auction voided + price drop compound signal

- **Type:** Feature
- **Description:**
  Identify motivated seller signal.
  
  **Logic:**
  - Auction voided
  - Price drop within N days
- **Acceptance Criteria:**
  - `DISTRESS_SIGNAL` tag applied
  - Ranking boost applied

### Issue 11: Opportunity scoring engine

- **Type:** Feature
- **Description:**
  Rank listings using valuation + signals.
  
  **Inputs:**
  - undervaluation %
  - auction failures
  - price drops
  - days on market
- **Acceptance Criteria:**
  - Deterministic score
  - Listings sortable by score

---

## Milestone 4 — Backend API

**Goal:** Expose data and insights via REST API.

### Issue 12: Opportunity summary API

- **Type:** Feature
- **Description:**
  Expose ranked listings with explanation.
  
  **Returns:**
  - Estimated vs listing price
  - % undervalued
  - Active signals
  - Score breakdown
- **Acceptance Criteria:**
  - Fast response
  - Clear JSON structure
  - RESTful endpoints

### Issue 13: Listing detail API

- **Type:** Feature
- **Description:**
  Expose detailed listing information with timeline.
  
  **Returns:**
  - Full listing details
  - Chronological events
  - Price history
  - Auction timeline
- **Acceptance Criteria:**
  - Correct event ordering
  - Human-readable event descriptions
  - Complete listing metadata

### Issue 14: Filters & search API

- **Type:** Feature
- **Description:**
  Filter and search listings via API.
  
  **Filters:**
  - Undervaluation threshold
  - Suburb
  - Property type
  - Price range
  - Active signals
- **Acceptance Criteria:**
  - Threshold configurable
  - Filter applied server-side
  - Pagination support

---

## Milestone 5 — React Web Application

**Goal:** Modern, responsive web interface for browsing and analyzing undervalued properties.

### Issue 15: React app setup & project structure

- **Type:** Chore
- **Description:**
  Initialize React application with modern tooling.
  
  **Tech Stack:**
  - React 18+
  - TypeScript
  - Vite (or Create React App)
  - React Router
  - State management (Zustand/Redux)
- **Acceptance Criteria:**
  - App builds and runs locally
  - Clear component structure
  - Routing configured

### Issue 16: Opportunity listing page

- **Type:** Feature
- **Description:**
  Display ranked list of undervalued properties.
  
  **Features:**
  - Sortable table/list view
  - Property cards with key metrics
  - Undervaluation percentage display
  - Score visualization
  - Quick filters (suburb, type, threshold)
- **Acceptance Criteria:**
  - Responsive design
  - Fast loading
  - Clear visual hierarchy

### Issue 17: Property detail page

- **Type:** Feature
- **Description:**
  Show comprehensive property details and timeline.
  
  **Features:**
  - Property information display
  - Image gallery
  - Price vs estimated comparison chart
  - Event timeline visualization
  - Active signals display
  - Score breakdown
- **Acceptance Criteria:**
  - All data displayed clearly
  - Timeline chronologically ordered
  - Mobile-friendly

### Issue 18: Filters & search UI

- **Type:** Feature
- **Description:**
  Interactive filtering and search interface.
  
  **Features:**
  - Filter sidebar/panel
  - Undervaluation threshold slider
  - Suburb autocomplete
  - Property type checkboxes
  - Price range inputs
  - Signal filters
  - URL-based filter state
- **Acceptance Criteria:**
  - Filters update results in real-time
  - Filter state persists in URL
  - Clear visual feedback

### Issue 19: Dashboard & analytics view

- **Type:** Feature
- **Description:**
  Overview dashboard with key metrics.
  
  **Features:**
  - Total opportunities count
  - Average undervaluation %
  - Top suburbs by opportunity
  - Signal distribution charts
  - Recent price drops
- **Acceptance Criteria:**
  - Real-time data updates
  - Clear visualizations
  - Responsive layout

### Issue 20: Responsive design & polish

- **Type:** Feature
- **Description:**
  Ensure excellent UX across all devices.
  
  **Features:**
  - Mobile-first responsive design
  - Loading states
  - Error handling
  - Accessibility (WCAG compliance)
  - Performance optimization
- **Acceptance Criteria:**
  - Works on mobile, tablet, desktop
  - Fast page loads
  - Accessible to screen readers
  - Smooth interactions

---

## 🧩 Optional Stretch Milestones (Later)

### Milestone 6 — Smarter Valuations

- Comparable sales model
- Confidence score
- Suburb trend adjustment

### Milestone 7 — Notifications

- Watchlist
- Email / push alerts on price drop or auction failure

### Milestone 8 — Advanced Web Features

- User accounts & saved searches
- Property comparison tool
- Export to CSV/PDF
- Map view with property markers
- Advanced analytics & charts

---

## 🏷️ GitHub Labels

Create the following labels in GitHub:

- `feature`
- `chore`
- `signal`
- `valuation`
- `auction`
- `frontend`
- `backend`
- `api`
- `scraper`
- `priority-high`


