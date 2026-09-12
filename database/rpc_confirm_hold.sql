-- =============================================================================
-- Collaborative Multi-Seat Workspace & Resource Booking Engine
-- Stored Procedure: confirm_hold
-- Platform: Supabase / PostgreSQL
-- =============================================================================

CREATE OR REPLACE FUNCTION confirm_hold(
    p_slot_id UUID,
    p_user_id TEXT,
    p_agenda TEXT DEFAULT NULL,
    p_collaborators JSONB DEFAULT '[]'::jsonb
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_updated_id UUID;
BEGIN
    -- -------------------------------------------------------------------------
    -- ATOMIC TRANSITION FROM 'HELD' TO 'CONFIRMED'
    -- Checks:
    -- 1. Matching slot_id
    -- 2. Matching user_id (only the holding user can confirm)
    -- 3. Current status must be 'HELD'
    -- 4. Hold TTL has NOT expired (hold_expires_at > clock_timestamp())
    -- -------------------------------------------------------------------------
    UPDATE bookings
    SET status = 'CONFIRMED',
        agenda = p_agenda,
        collaborators = COALESCE(p_collaborators, '[]'::jsonb),
        confirmed_at = clock_timestamp(),
        updated_at = clock_timestamp()
    WHERE id = p_slot_id
      AND user_id = p_user_id
      AND status = 'HELD'
      AND hold_expires_at > clock_timestamp()
    RETURNING id INTO v_updated_id;

    -- -------------------------------------------------------------------------
    -- EVALUATE IF UPDATE SUCCEEDED
    -- -------------------------------------------------------------------------
    IF v_updated_id IS NULL THEN
        RETURN jsonb_build_object(
            'success', FALSE,
            'code', 'HOLD_EXPIRED',
            'message', 'The hold has expired, was released, or belongs to another user.'
        );
    END IF;

    RETURN jsonb_build_object(
        'success', TRUE,
        'code', 'CONFIRMED',
        'slot_id', v_updated_id,
        'message', 'Reservation successfully confirmed.'
    );
END;
$$;
