-- =============================================================================
-- Collaborative Multi-Seat Workspace & Resource Booking Engine
-- Stored Procedure: cancel_booking
-- Platform: Supabase / PostgreSQL
-- =============================================================================

CREATE OR REPLACE FUNCTION cancel_booking(
    p_slot_id UUID,
    p_user_id TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_cancelled_id UUID;
BEGIN
    -- -------------------------------------------------------------------------
    -- RESET SLOT BACK TO 'AVAILABLE'
    -- Clears user allocation, hold expiration, agenda, and collaborators.
    -- -------------------------------------------------------------------------
    UPDATE bookings
    SET status = 'AVAILABLE',
        user_id = NULL,
        hold_expires_at = NULL,
        agenda = NULL,
        collaborators = '[]'::jsonb,
        confirmed_at = NULL,
        updated_at = clock_timestamp()
    WHERE id = p_slot_id
      AND (p_user_id IS NULL OR user_id = p_user_id)
      AND status IN ('HELD', 'CONFIRMED')
    RETURNING id INTO v_cancelled_id;

    IF v_cancelled_id IS NULL THEN
        RETURN jsonb_build_object(
            'success', FALSE,
            'code', 'NOT_FOUND_OR_UNAUTHORIZED',
            'message', 'Slot is already available, not found, or not owned by this user.'
        );
    END IF;

    RETURN jsonb_build_object(
        'success', TRUE,
        'code', 'CANCELLED',
        'slot_id', v_cancelled_id,
        'message', 'Slot reservation successfully cancelled and released.'
    );
END;
$$;
