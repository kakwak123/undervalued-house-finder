-- Supabase database schema for listings and events
-- Run this in your Supabase SQL editor to create the required tables

-- Create listings table
CREATE TABLE IF NOT EXISTS listings (
    listing_id TEXT PRIMARY KEY,
    suburb TEXT NOT NULL,
    property_type TEXT NOT NULL,
    bedrooms INTEGER,
    bathrooms INTEGER,
    land_size TEXT,
    building_size TEXT,
    status TEXT NOT NULL DEFAULT 'unknown',
    current_price TEXT,
    previous_price TEXT,
    auction_datetime TIMESTAMPTZ,
    property_link TEXT,
    description TEXT,
    source TEXT,
    address JSONB,
    price_history JSONB DEFAULT '[]'::jsonb,
    auction_history JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create events table
CREATE TABLE IF NOT EXISTS events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    event_type TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    listing_id TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_listings_suburb ON listings(suburb);
CREATE INDEX IF NOT EXISTS idx_listings_status ON listings(status);
CREATE INDEX IF NOT EXISTS idx_listings_source ON listings(source);
CREATE INDEX IF NOT EXISTS idx_events_listing_id ON events(listing_id);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);

-- Enable Row Level Security (RLS) if needed
-- ALTER TABLE listings ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE events ENABLE ROW LEVEL SECURITY;

-- Create policies for public access (adjust as needed for your security requirements)
-- CREATE POLICY "Allow public read access" ON listings FOR SELECT USING (true);
-- CREATE POLICY "Allow public insert/update" ON listings FOR ALL USING (true);
-- CREATE POLICY "Allow public read access" ON events FOR SELECT USING (true);
-- CREATE POLICY "Allow public insert" ON events FOR INSERT WITH CHECK (true);


-- ---------------------------------------------------------------------------
-- Migration: Milestone 2 + 3 valuation and signal columns
-- Safe to run on an existing database (IF NOT EXISTS / idempotent).
-- ---------------------------------------------------------------------------

-- M2-1/M2-2: valuation engine outputs
ALTER TABLE listings ADD COLUMN IF NOT EXISTS estimated_price TEXT;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS undervalue_score FLOAT;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS valuation_classification TEXT;

-- M3-3: distress signal flag
ALTER TABLE listings ADD COLUMN IF NOT EXISTS distress_signal BOOLEAN DEFAULT FALSE;

-- M4-2: persisted opportunity score (cached from scoring engine)
ALTER TABLE listings ADD COLUMN IF NOT EXISTS opportunity_score FLOAT;

-- Indexes for new query-path columns
CREATE INDEX IF NOT EXISTS idx_listings_undervalue_score ON listings(undervalue_score DESC);
CREATE INDEX IF NOT EXISTS idx_listings_distress_signal ON listings(distress_signal);
CREATE INDEX IF NOT EXISTS idx_listings_opportunity_score ON listings(opportunity_score DESC);

