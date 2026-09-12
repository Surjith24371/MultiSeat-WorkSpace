-- =============================================================================
-- Collaborative Multi-Seat Workspace & Resource Booking Engine
-- Phase 1: Database Schema & Core Architecture
-- Author: Member 1 (Database Lead)
-- Target Platform: Supabase / PostgreSQL
-- =============================================================================

-- Enable required cryptographic and UUID extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- 1. USERS TABLE
-- Reference store for workspace members (matches Member 3 user switcher)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,                       -- e.g., 'user_alice', 'user_bob'
    name TEXT NOT NULL,                        -- e.g., 'Alice Smith'
    email TEXT NOT NULL UNIQUE,                -- e.g., 'alice@workspace.local'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 2. RESOURCES TABLE
-- Master catalog of the 12 bookable workspace physical assets
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,                 -- e.g., 'Conference Room A', 'Pod 1'
    resource_type TEXT NOT NULL CHECK (resource_type IN ('ROOM', 'POD', 'DESK')),
    capacity INT NOT NULL DEFAULT 1 CHECK (capacity > 0),
    location TEXT NOT NULL DEFAULT 'Main Level',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 3. BOOKINGS TABLE
-- The unified state-machine table for the 96 daily slots (12 resources x 8 hours)
-- Status lifecycle: AVAILABLE -> HELD (90s soft-lock) -> CONFIRMED
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id UUID NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    resource_name TEXT NOT NULL,               -- Denormalized for zero-join API query speed
    booking_date DATE NOT NULL,                -- Target date (YYYY-MM-DD)
    time_slot TEXT NOT NULL CHECK (
        time_slot IN ('09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00')
    ),
    status TEXT NOT NULL DEFAULT 'AVAILABLE' CHECK (
        status IN ('AVAILABLE', 'HELD', 'CONFIRMED')
    ),
    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    hold_expires_at TIMESTAMPTZ,               -- 90s TTL deadline for HELD slots
    agenda TEXT,                               -- Populated upon confirmation
    collaborators JSONB DEFAULT '[]'::jsonb,   -- Array of invited collaborator emails
    confirmed_at TIMESTAMPTZ,                  -- Confirmation timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- CRITICAL CONCURRENCY & INTEGRITY CONSTRAINT:
    -- Guarantees mathematically that no two entries can exist for the same slot
    CONSTRAINT uq_resource_date_slot UNIQUE (resource_name, booking_date, time_slot),

    -- Semantic validation constraints
    CONSTRAINT chk_held_state CHECK (
        status != 'HELD' OR (user_id IS NOT NULL AND hold_expires_at IS NOT NULL)
    ),
    CONSTRAINT chk_confirmed_state CHECK (
        status != 'CONFIRMED' OR (user_id IS NOT NULL AND confirmed_at IS NOT NULL)
    )
);

-- -----------------------------------------------------------------------------
-- 4. PERFORMANCE INDEXES
-- Optimized for 5-second polling, point-lookups, and user daily quota calculations
-- -----------------------------------------------------------------------------

-- Index for 5-second auto-polling availability matrix
CREATE INDEX IF NOT EXISTS idx_bookings_grid 
ON bookings (booking_date, resource_name, time_slot);

-- Partial index for instantaneous daily 3-hour user quota calculations
-- Only indexes active/confirmed bookings, completely ignoring 'AVAILABLE' slots
CREATE INDEX IF NOT EXISTS idx_bookings_user_quota 
ON bookings (user_id, booking_date) 
WHERE status IN ('CONFIRMED', 'HELD');

-- Partial index for active hold TTL evaluations
CREATE INDEX IF NOT EXISTS idx_bookings_hold_expiry 
ON bookings (hold_expires_at) 
WHERE status = 'HELD';

-- -----------------------------------------------------------------------------
-- 5. REAL-TIME AVAILABILITY NORMALIZATION VIEW
-- Dynamically derives availability without requiring background daemons or cron jobs.
-- If a hold is expired (hold_expires_at <= NOW()), it is logically reported as 'AVAILABLE'.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_resource_availability AS
SELECT 
    b.id,
    b.resource_id,
    b.resource_name,
    b.booking_date,
    b.time_slot,
    b.user_id,
    b.hold_expires_at,
    b.agenda,
    b.collaborators,
    b.status AS raw_status,
    CASE 
        WHEN b.status = 'CONFIRMED' THEN 'CONFIRMED'
        WHEN b.status = 'HELD' AND b.hold_expires_at > NOW() THEN 'HELD'
        ELSE 'AVAILABLE'
    END AS status
FROM bookings b;
