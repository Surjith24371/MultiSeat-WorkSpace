-- =============================================================================
-- Collaborative Multi-Seat Workspace & Resource Booking Engine
-- Phase 3: Database Seeder Script (Direct SQL)
-- Author: Member 1 (Database Lead)
-- Platform: Supabase / PostgreSQL
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. SEED MOCK USERS (Matching Member 3 Frontend User Switcher)
-- -----------------------------------------------------------------------------
INSERT INTO users (id, name, email) VALUES
    ('user_alice', 'Alice Smith', 'alice@workspace.local'),
    ('user_bob', 'Bob Jones', 'bob@workspace.local'),
    ('user_charlie', 'Charlie Brown', 'charlie@workspace.local')
ON CONFLICT (id) DO UPDATE 
SET name = EXCLUDED.name, email = EXCLUDED.email;

-- -----------------------------------------------------------------------------
-- 2. SEED 12 CANONICAL WORKSPACE RESOURCES
-- 4 Conference Rooms, 4 Workstation Pods, 4 Focus Desks
-- -----------------------------------------------------------------------------
INSERT INTO resources (name, resource_type, capacity, location, is_active) VALUES
    -- Conference Rooms
    ('Conference Room A', 'ROOM', 8, 'Floor 1 - North Wing', TRUE),
    ('Conference Room B', 'ROOM', 6, 'Floor 1 - South Wing', TRUE),
    ('Executive Boardroom', 'ROOM', 12, 'Floor 2 - Executive Suite', TRUE),
    ('Ideation Studio', 'ROOM', 10, 'Floor 2 - Innovation Lab', TRUE),
    
    -- Workstation Pods
    ('Quiet Pod 1', 'POD', 1, 'Floor 1 - Focus Zone', TRUE),
    ('Quiet Pod 2', 'POD', 1, 'Floor 1 - Focus Zone', TRUE),
    ('Team Pod 3', 'POD', 4, 'Floor 2 - Collaboration Hub', TRUE),
    ('Team Pod 4', 'POD', 4, 'Floor 2 - Collaboration Hub', TRUE),

    -- Desks
    ('Standing Desk 1', 'DESK', 1, 'Floor 1 - Open Workspace', TRUE),
    ('Standing Desk 2', 'DESK', 1, 'Floor 1 - Open Workspace', TRUE),
    ('Focus Desk 3', 'DESK', 1, 'Floor 2 - Library Area', TRUE),
    ('Focus Desk 4', 'DESK', 1, 'Floor 2 - Library Area', TRUE)
ON CONFLICT (name) DO UPDATE 
SET capacity = EXCLUDED.capacity, 
    location = EXCLUDED.location,
    resource_type = EXCLUDED.resource_type;

-- -----------------------------------------------------------------------------
-- 3. SEED 96 HOURLY SLOTS PER DAY (12 Resources x 8 Hours = 96 slots/day)
-- Generates slots for TODAY and the next 6 days (1 full week)
-- -----------------------------------------------------------------------------
INSERT INTO bookings (
    resource_id,
    resource_name,
    booking_date,
    time_slot,
    status
)
SELECT 
    r.id AS resource_id,
    r.name AS resource_name,
    d.slot_date AS booking_date,
    t.slot_time AS time_slot,
    'AVAILABLE' AS status
FROM resources r
CROSS JOIN (
    -- Generates today + next 6 days
    SELECT (CURRENT_DATE + i)::date AS slot_date
    FROM generate_series(0, 6) AS i
) d
CROSS JOIN (
    -- 8 Hourly blocks (09:00 to 17:00)
    VALUES 
        ('09:00'),
        ('10:00'),
        ('11:00'),
        ('12:00'),
        ('13:00'),
        ('14:00'),
        ('15:00'),
        ('16:00')
) AS t(slot_time)
ON CONFLICT (resource_name, booking_date, time_slot) DO NOTHING;

-- Verification output
SELECT 
    booking_date,
    COUNT(*) AS total_slots,
    COUNT(DISTINCT resource_name) AS distinct_resources
FROM bookings
GROUP BY booking_date
ORDER BY booking_date;
