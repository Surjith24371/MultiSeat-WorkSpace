-- =============================================================================
-- Collaborative Multi-Seat Workspace & Resource Booking Engine
-- Stored Procedure: place_hold
-- Platform: Supabase / PostgreSQL
-- =============================================================================

CREATE OR REPLACE FUNCTION place_hold(
    p_resource_name TEXT,
    p_booking_date DATE,
    p_time_slot TEXT,
    p_user_id TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_active_hours INT;
    v_slot_id UUID;
    v_expires_at TIMESTAMPTZ;
BEGIN
    -- -------------------------------------------------------------------------
    -- 1. CONCURRENCY SHIELD: USER-LEVEL TRANSACTION ADVISORY LOCK
    -- Serializes quota evaluations for the same user on the same date.
    -- Prevents two concurrent requests from simultaneously passing the 3-hour check.
    -- -------------------------------------------------------------------------
    PERFORM pg_advisory_xact_lock(hashtext(p_user_id || p_booking_date::text));

    -- -------------------------------------------------------------------------
    -- 2. DAILY 3-HOUR USER QUOTA CHECK
    -- Count of CONFIRMED hours + active HELD hours (where hold_expires_at > clock_timestamp())
    -- -------------------------------------------------------------------------
    SELECT COUNT(*) INTO v_active_hours
    FROM bookings
    WHERE user_id = p_user_id
      AND booking_date = p_booking_date
      AND (
          status = 'CONFIRMED'
          OR (status = 'HELD' AND hold_expires_at > clock_timestamp())
      );

    IF v_active_hours >= 3 THEN
        RETURN jsonb_build_object(
            'success', FALSE,
            'code', 'QUOTA_EXCEEDED',
            'message', 'Daily quota of 3 cumulative hours reached for this user on this date.'
        );
    END IF;

    -- -------------------------------------------------------------------------
    -- 3. ATOMIC CONDITIONAL ROW-LEVEL UPDATE
    -- Updates slot to 'HELD' only if 'AVAILABLE' or if previous hold has expired.
    -- In PostgreSQL, UPDATE acquires an exclusive row lock, guaranteeing zero double-allocation.
    -- -------------------------------------------------------------------------
    v_expires_at := clock_timestamp() + INTERVAL '90 seconds';

    UPDATE bookings
    SET status = 'HELD',
        user_id = p_user_id,
        hold_expires_at = v_expires_at,
        updated_at = clock_timestamp()
    WHERE resource_name = p_resource_name
      AND booking_date = p_booking_date
      AND time_slot = p_time_slot
      AND (
          status = 'AVAILABLE'
          OR (status = 'HELD' AND hold_expires_at <= clock_timestamp())
      )
    RETURNING id INTO v_slot_id;

    -- -------------------------------------------------------------------------
    -- 4. EVALUATE ROW-COUNT RESULT
    -- -------------------------------------------------------------------------
    IF v_slot_id IS NULL THEN
        RETURN jsonb_build_object(
            'success', FALSE,
            'code', 'SLOT_TAKEN',
            'message', 'This time slot is currently occupied or actively held by another user.'
        );
    END IF;

    -- -------------------------------------------------------------------------
    -- 5. RETURN SUCCESS PAYLOAD
    -- -------------------------------------------------------------------------
    RETURN jsonb_build_object(
        'success', TRUE,
        'code', 'HOLD_ACQUIRED',
        'slot_id', v_slot_id,
        'resource_name', p_resource_name,
        'booking_date', p_booking_date,
        'time_slot', p_time_slot,
        'user_id', p_user_id,
        'expires_at', v_expires_at,
        'expires_in', 90
    );
END;
$$;
