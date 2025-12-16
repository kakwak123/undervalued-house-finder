# 🗺️ GitHub Milestones

## Overview

This document outlines the development milestones for the Undervalued House Finder project. Each milestone builds upon the previous one, creating a comprehensive system for identifying and tracking undervalued property listings.

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

### Issue 4: Listing ingestion (CSV → DB)

- **Type:** Feature
- **Description:**
  Ingest sample property listings from CSV.
- **Acceptance Criteria:**
  - Idempotent ingestion
  - Detect price/status changes
  - Generate events automatically

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

## Milestone 4 — User-Facing Experience

**Goal:** Clear, explainable insights and usable UI.

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

### Issue 13: Listing detail timeline view

- **Type:** Feature
- **Description:**
  Show chronological events for a listing.
- **Acceptance Criteria:**
  - Correct ordering
  - Human-readable descriptions

### Issue 14: Filters & alerts (MVP)

- **Type:** Feature
- **Description:**
  Filter listings by undervaluation threshold.
- **Acceptance Criteria:**
  - Threshold configurable
  - Filter applied server-side

---

## 🧩 Optional Stretch Milestones (Later)

### Milestone 5 — Smarter Valuations

- Comparable sales model
- Confidence score
- Suburb trend adjustment

### Milestone 6 — Notifications

- Watchlist
- Email / push alerts on price drop or auction failure

---

## 🏷️ GitHub Labels

Create the following labels in GitHub:

- `feature`
- `chore`
- `signal`
- `valuation`
- `auction`
- `priority-high`

