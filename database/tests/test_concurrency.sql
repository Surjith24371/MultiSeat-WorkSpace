-- =============================================================================
-- Collaborative Multi-Seat Workspace & Resource Booking Engine
-- Phase 4: Database Concurrency & RPC Test Script
-- Run this directly inside the Supabase SQL Editor
-- =============================================================================

DO $$
DECLARE
    v_res JSONB;
    v_slot_id UUID;
    v_test_date DATE := CURRENT_DATE;
    v_room TEXT := 'Conference Room A';
BEGIN
    RAISE NOTICE '======================================================================';
    RAISE NOTICE 'STARTING DATABASE RPC & CONCURRENCY VERIFICATION SUITE';
    RAISE NOTICE '======================================================================';

    -- -------------------------------------------------------------------------
    -- SETUP: Ensure clean baseline for testing on Conference Room A
    -- -------------------------------------------------------------------------
    UPDATE bookings 
    SET status = 'AVAILABLE', user_id = NULL, hold_expires_at = NULL, agenda = NULL, confirmed_at = NULL
    WHERE resource_name = v_room AND booking_date = v_test_date;

    -- -------------------------------------------------------------------------
    -- TEST 1: Normal Hold Acquisition (Alice holds 09:00)
    -- Expected: code = 'HOLD_ACQUIRED', success = true
    -- -------------------------------------------------------------------------
    v_res := place_hold(v_room, v_test_date, '09:00', 'user_alice');
    IF (v_res->>'code') != 'HOLD_ACQUIRED' THEN
        RAISE EXCEPTION 'TEST 1 FAILED: Expected HOLD_ACQUIRED, got %', v_res;
    END IF;
    v_slot_id := (v_res->>'slot_id')::uuid;
    RAISE NOTICE '[PASS] TEST 1: Standard Hold Acquired (Slot ID: %)', v_slot_id;

    -- -------------------------------------------------------------------------
    -- TEST 2: Zero Double-Allocation Race (Bob attempts to hold same 09:00 slot)
    -- Expected: code = 'SLOT_TAKEN', success = false
    -- -------------------------------------------------------------------------
    v_res := place_hold(v_room, v_test_date, '09:00', 'user_bob');
    IF (v_res->>'code') != 'SLOT_TAKEN' THEN
        RAISE EXCEPTION 'TEST 2 FAILED: Expected SLOT_TAKEN, got %', v_res;
    END IF;
    RAISE NOTICE '[PASS] TEST 2: Competing Hold Blocked with SLOT_TAKEN (Zero Double-Allocation Verified)';

    -- -------------------------------------------------------------------------
    -- TEST 3: Cumulative 3-Hour Quota Enforcement
    -- Alice holds 10:00 (Hour 2) and 11:00 (Hour 3) -> Both must succeed.
    -- Alice attempts to hold 12:00 (Hour 4) -> Must fail with QUOTA_EXCEEDED.
    -- -------------------------------------------------------------------------
    v_res := place_hold(v_room, v_test_date, '10:00', 'user_alice');
    IF (v_res->>'code') != 'HOLD_ACQUIRED' THEN
        RAISE EXCEPTION 'TEST 3a FAILED: Expected HOLD_ACQUIRED for Hour 2, got %', v_res;
    END IF;

    v_res := place_hold(v_room, v_test_date, '11:00', 'user_alice');
    IF (v_res->>'code') != 'HOLD_ACQUIRED' THEN
        RAISE EXCEPTION 'TEST 3b FAILED: Expected HOLD_ACQUIRED for Hour 3, got %', v_res;
    END IF;

    -- 4th hour attempt
    v_res := place_hold(v_room, v_test_date, '12:00', 'user_alice');
    IF (v_res->>'code') != 'QUOTA_EXCEEDED' THEN
        RAISE EXCEPTION 'TEST 3c FAILED: Expected QUOTA_EXCEEDED for Hour 4, got %', v_res;
    END IF;
    RAISE NOTICE '[PASS] TEST 3: 3-Hour Daily Quota Strictly Enforced (4th Hour Rejected)';

    -- -------------------------------------------------------------------------
    -- TEST 4: Confirmation within TTL
    -- Alice confirms 09:00 slot -> Expected: code = 'CONFIRMED'
    -- -------------------------------------------------------------------------
    v_res := confirm_hold(v_slot_id, 'user_alice', 'Hackathon Strategy', '["bob@workspace.local"]'::jsonb);
    IF (v_res->>'code') != 'CONFIRMED' THEN
        RAISE EXCEPTION 'TEST 4 FAILED: Expected CONFIRMED, got %', v_res;
    END IF;
    RAISE NOTICE '[PASS] TEST 4: Hold Confirmed Successfully within TTL';

    -- -------------------------------------------------------------------------
    -- TEST 5: Expired Hold & Takeover
    -- Manually expire Alice's 10:00 hold (set hold_expires_at to 10 seconds ago)
    -- Alice should fail to confirm (HOLD_EXPIRED)
    -- Bob should succeed in holding the slot (HOLD_ACQUIRED)
    -- -------------------------------------------------------------------------
    UPDATE bookings 
    SET hold_expires_at = clock_timestamp() - INTERVAL '10 seconds'
    WHERE resource_name = v_room AND booking_date = v_test_date AND time_slot = '10:00'
    RETURNING id INTO v_slot_id;

    -- Alice tries to confirm expired hold
    v_res := confirm_hold(v_slot_id, 'user_alice');
    IF (v_res->>'code') != 'HOLD_EXPIRED' THEN
        RAISE EXCEPTION 'TEST 5a FAILED: Expected HOLD_EXPIRED, got %', v_res;
    END IF;

    -- Bob takes over expired slot
    v_res := place_hold(v_room, v_test_date, '10:00', 'user_bob');
    IF (v_res->>'code') != 'HOLD_ACQUIRED' THEN
        RAISE EXCEPTION 'TEST 5b FAILED: Expected Bob to take over expired slot, got %', v_res;
    END IF;
    RAISE NOTICE '[PASS] TEST 5: Expired Hold Correctly Refused and Reallocated to New User';

    -- -------------------------------------------------------------------------
    -- TEST 6: Cancellation & Quota Release
    -- Alice cancels 09:00 confirmed booking -> Expected: CANCELLED
    -- Alice should now have capacity to book 12:00 slot!
    -- -------------------------------------------------------------------------
    SELECT id INTO v_slot_id 
    FROM bookings 
    WHERE resource_name = v_room AND booking_date = v_test_date AND time_slot = '09:00';

    v_res := cancel_booking(v_slot_id, 'user_alice');
    IF (v_res->>'code') != 'CANCELLED' THEN
        RAISE EXCEPTION 'TEST 6a FAILED: Expected CANCELLED, got %', v_res;
    END IF;

    -- Now Alice has 1 hour (11:00) held, so 12:00 should succeed
    v_res := place_hold(v_room, v_test_date, '12:00', 'user_alice');
    IF (v_res->>'code') != 'HOLD_ACQUIRED' THEN
        RAISE EXCEPTION 'TEST 6b FAILED: Expected quota to be restored after cancellation, got %', v_res;
    END IF;
    RAISE NOTICE '[PASS] TEST 6: Cancellation Released Slot and Restored User Quota';

    -- -------------------------------------------------------------------------
    -- CLEANUP: Reset test slots back to AVAILABLE
    -- -------------------------------------------------------------------------
    UPDATE bookings 
    SET status = 'AVAILABLE', user_id = NULL, hold_expires_at = NULL, agenda = NULL, confirmed_at = NULL
    WHERE resource_name = v_room AND booking_date = v_test_date;

    RAISE NOTICE '======================================================================';
    RAISE NOTICE 'ALL 6 DATABASE TESTS PASSED WITH ZERO ERRORS!';
    RAISE NOTICE '======================================================================';
END;
$$;
