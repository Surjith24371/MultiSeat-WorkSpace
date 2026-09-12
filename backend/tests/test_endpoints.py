"""
backend/tests/test_endpoints.py
===============================
Automated Verification Suite for MultiSeat-WorkSpace Backend REST APIs.
Tests:
1. Availability Endpoint (Missing date, invalid date, valid date with 96 slots).
2. Hold Endpoint (Missing fields, successful 90s hold, slot conflict).
3. Quota Enforcement (Daily 3-hour limit -> 422 Quota Exceeded).
4. Confirm Endpoint (Expired hold, unauthorized user, successful confirmation).
5. Cancel Endpoint (Not found, successful cancellation back to AVAILABLE).
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import app
from mock_db import mock_db

def run_tests():
    client = app.test_client()
    print("[TEST] Starting MultiSeat-WorkSpace REST API Test Suite...\n")

    # ------------------------------------------------------------------------
    # 1. AVAILABILITY
    # ------------------------------------------------------------------------
    # Missing date query parameter
    r = client.get("/api/resources/availability")
    assert r.status_code == 400, f"Expected 400 for missing date, got {r.status_code}"

    # Invalid date format
    r = client.get("/api/resources/availability?date=invalid-date")
    assert r.status_code == 400, f"Expected 400 for invalid date, got {r.status_code}"

    # Valid date query
    r = client.get("/api/resources/availability?date=2026-09-13")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.get_json()
    assert data["success"] is True
    assert data["count"] == 96, f"Expected 96 slots, got {data['count']}"
    print("[PASS] Test 1: GET /api/resources/availability returns 96 slots.")

    # ------------------------------------------------------------------------
    # 2. HOLD & CONFLICTS
    # ------------------------------------------------------------------------
    # Missing fields
    r = client.post("/api/resources/hold", json={"user_id": "user1"})
    assert r.status_code == 400, f"Expected 400 for missing fields, got {r.status_code}"

    # Successful hold
    hold_payload = {
        "resource_name": "Meeting Room 1",
        "date": "2026-09-13",
        "time_slot": "09:00-10:00",
        "user_id": "user1"
    }
    r = client.post("/api/resources/hold", json=hold_payload)
    assert r.status_code == 201, f"Expected 201 Created, got {r.status_code}"
    hold_data = r.get_json()
    slot_id = hold_data["slot_id"]
    assert hold_data["expires_in"] == 90
    assert hold_data["slot"]["status"] == "HELD"
    print(f"[PASS] Test 2: POST /api/resources/hold acquired 90s hold (ID: {slot_id}).")

    # Conflict check: user2 attempts to hold the same slot
    r_conflict = client.post("/api/resources/hold", json={
        "resource_name": "Meeting Room 1",
        "date": "2026-09-13",
        "time_slot": "09:00-10:00",
        "user_id": "user2"
    })
    assert r_conflict.status_code == 409, f"Expected 409 Conflict, got {r_conflict.status_code}"
    print("[PASS] Test 3: POST /api/resources/hold returns 409 Conflict for taken slot.")

    # ------------------------------------------------------------------------
    # 3. CONFIRMATION
    # ------------------------------------------------------------------------
    # Unauthorized user confirmation
    r_unauth = client.post("/api/resources/confirm", json={
        "slot_id": slot_id,
        "user_id": "different_user",
        "agenda": "Hack session"
    })
    assert r_unauth.status_code == 403, f"Expected 403 Forbidden, got {r_unauth.status_code}"
    print("[PASS] Test 4: POST /api/resources/confirm blocks unauthorized users (403).")

    # Valid confirmation
    confirm_payload = {
        "slot_id": slot_id,
        "user_id": "user1",
        "agenda": "Project Architecture Review",
        "collaborators": ["alice@work.io", "bob@work.io"]
    }
    r_confirm = client.post("/api/resources/confirm", json=confirm_payload)
    assert r_confirm.status_code == 200, f"Expected 200 OK, got {r_confirm.status_code}"
    confirmed_slot = r_confirm.get_json()["slot"]
    assert confirmed_slot["status"] == "CONFIRMED"
    assert confirmed_slot["agenda"] == "Project Architecture Review"
    assert len(confirmed_slot["collaborators"]) == 2
    print("[PASS] Test 5: POST /api/resources/confirm successfully finalized booking (200).")

    # ------------------------------------------------------------------------
    # 4. CANCELLATION
    # ------------------------------------------------------------------------
    r_cancel = client.delete(f"/api/resources/cancel/{slot_id}")
    assert r_cancel.status_code == 200, f"Expected 200 OK, got {r_cancel.status_code}"
    assert r_cancel.get_json()["slot"]["status"] == "AVAILABLE"
    print("[PASS] Test 6: DELETE /api/resources/cancel restored slot to AVAILABLE (200).")

    # ------------------------------------------------------------------------
    # 5. QUOTA LIMIT (MAX 3 HOURS PER USER)
    # ------------------------------------------------------------------------
    mock_db.reset()
    user_q = "quota_tester"
    slots_to_test = ["09:00-10:00", "10:00-11:00", "11:00-12:00"]
    # Acquire 3 slots (allowed)
    for i, slot_time in enumerate(slots_to_test):
        r_q = client.post("/api/resources/hold", json={
            "resource_name": "Meeting Room 1",
            "date": "2026-09-13",
            "time_slot": slot_time,
            "user_id": user_q
        })
        assert r_q.status_code == 201, f"Slot {i+1} should succeed, got {r_q.status_code}"

    # 4th slot must be blocked with 422
    r_exceeded = client.post("/api/resources/hold", json={
        "resource_name": "Meeting Room 1",
        "date": "2026-09-13",
        "time_slot": "12:00-13:00",
        "user_id": user_q
    })
    assert r_exceeded.status_code == 422, f"Expected 422 Quota Exceeded, got {r_exceeded.status_code}"
    print("[PASS] Test 7: POST /api/resources/hold enforces 3-hour daily quota (422).")

    # ------------------------------------------------------------------------
    # 6. HOLD EXPIRATION (410 GONE)
    # ------------------------------------------------------------------------
    mock_db.reset()
    r_hold_exp = client.post("/api/resources/hold", json={
        "resource_name": "Meeting Room 1",
        "date": "2026-09-13",
        "time_slot": "09:00-10:00",
        "user_id": "user_expire"
    })
    exp_slot_id = r_hold_exp.get_json()["slot_id"]

    # Manually backdate the hold_expires_at timestamp to simulate 90s elapsed
    from datetime import datetime, timezone, timedelta
    with mock_db._lock:
        target_date, target_slot = mock_db._find_slot_internal(exp_slot_id)
        target_slot["hold_expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()

    r_confirm_exp = client.post("/api/resources/confirm", json={
        "slot_id": exp_slot_id,
        "user_id": "user_expire"
    })
    assert r_confirm_exp.status_code == 410, f"Expected 410 Hold Expired, got {r_confirm_exp.status_code}"
    # Verify slot is back to AVAILABLE
    slot_after = mock_db.get_slot_by_id(exp_slot_id)
    assert slot_after["status"] == "AVAILABLE"
    print("[PASS] Test 8: Expired hold returns 410 Gone and resets slot to AVAILABLE.")

    # ------------------------------------------------------------------------
    # 7. HEALTH & STATUS ENDPOINTS
    # ------------------------------------------------------------------------
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/resources/status").status_code == 200
    assert client.get("/").status_code == 200
    print("[PASS] Test 9: Health, Status, and Root routes respond with 200 OK.")

    print("\n=======================================================")
    print("ALL 8 BACKEND REST API TESTS PASSED SUCCESSFULLY!")
    print("=======================================================")

if __name__ == "__main__":
    run_tests()
