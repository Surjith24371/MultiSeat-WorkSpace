"""
backend/tests/test_concurrency.py
=================================
Deliverable 4: Multi-Threaded Concurrency Test for MultiSeat-WorkSpace.

Demonstrates and verifies that when two users simultaneously fire a hold request
for the EXACT same slot at the EXACT same millisecond:
- Thread 1 receives: HTTP 201 Created (Hold Acquired)
- Thread 2 receives: HTTP 409 Conflict (Slot Taken)
- Zero double-allocation occurs.
"""

import sys
import threading
from pathlib import Path

# Add backend root to Python path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import app
from mock_db import mock_db

def test_concurrent_holds():
    print("=============================================================")
    print("Starting Multi-Threaded Concurrency Test (Anti-Double Booking)")
    print("=============================================================")

    client = app.test_client()
    mock_db.reset()

    target_slot = {
        "resource_name": "Executive Boardroom",
        "date": "2026-09-13",
        "time_slot": "10:00-11:00"
    }

    # Barrier to synchronize threads so both fire at the exact same instant
    barrier = threading.Barrier(2)
    results = []
    lock = threading.Lock()

    def attempt_hold(user_id):
        # Wait for both threads to reach the starting gate
        barrier.wait()
        
        # Fire request
        response = client.post("/api/resources/hold", json={
            "resource_name": target_slot["resource_name"],
            "date": target_slot["date"],
            "time_slot": target_slot["time_slot"],
            "user_id": user_id
        })
        
        with lock:
            results.append({
                "user_id": user_id,
                "status_code": response.status_code,
                "data": response.get_json()
            })

    # Spawn 2 concurrent worker threads
    t1 = threading.Thread(target=attempt_hold, args=("user_alice",))
    t2 = threading.Thread(target=attempt_hold, args=("user_bob",))

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    # Analyze results
    print(f"\nRequests Completed: {len(results)}")
    for res in results:
        print(f"- User: {res['user_id']} | Status: {res['status_code']} | Response: {res['data'].get('message')}")

    status_codes = [r["status_code"] for r in results]

    # Exactly one 201 Created and one 409 Conflict
    assert 201 in status_codes, "Failure: One thread must receive HTTP 201 Created!"
    assert 409 in status_codes, "Failure: One thread must receive HTTP 409 Conflict!"
    assert len(status_codes) == 2, "Failure: Expected exactly 2 responses!"

    print("\n[SUCCESS] Concurrency Test Passed!")
    print("Zero double-allocation achieved: Exactly one 201 Created and one 409 Conflict.")
    print("=============================================================\n")

if __name__ == "__main__":
    test_concurrent_holds()
