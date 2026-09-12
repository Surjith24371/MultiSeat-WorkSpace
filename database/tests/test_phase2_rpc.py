#!/usr/bin/env python3
"""
Automated Test Suite for Phase 2: Stored Procedures & Concurrency Logic
Validates PL/pgSQL RPC definitions and executes multithreaded simulations for:
- Zero double-allocation race conditions
- 90-second soft-lock TTL behavior
- Daily 3-hour user quota & simultaneous quota race prevention
- Confirmation and cancellation lifecycles
"""

import os
import re
import sqlite3
import threading
import time
import unittest
from datetime import datetime, timezone, timedelta

DIR = os.path.dirname(__file__)
RPC_HOLD_PATH = os.path.join(DIR, "..", "rpc_place_hold.sql")
RPC_CONFIRM_PATH = os.path.join(DIR, "..", "rpc_confirm_hold.sql")
RPC_CANCEL_PATH = os.path.join(DIR, "..", "rpc_cancel_booking.sql")

class TestPhase2RPCStatic(unittest.TestCase):
    """Verifies that all required PL/pgSQL functions match the team contract."""

    def test_rpc_files_exist(self):
        self.assertTrue(os.path.exists(RPC_HOLD_PATH), "rpc_place_hold.sql missing")
        self.assertTrue(os.path.exists(RPC_CONFIRM_PATH), "rpc_confirm_hold.sql missing")
        self.assertTrue(os.path.exists(RPC_CANCEL_PATH), "rpc_cancel_booking.sql missing")

    def test_place_hold_signature_and_codes(self):
        with open(RPC_HOLD_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("place_hold", content)
        self.assertIn("p_resource_name", content)
        self.assertIn("p_booking_date", content)
        self.assertIn("p_time_slot", content)
        self.assertIn("p_user_id", content)
        self.assertIn("pg_advisory_xact_lock", content, "Missing advisory lock for quota race protection")
        self.assertIn("'HOLD_ACQUIRED'", content)
        self.assertIn("'SLOT_TAKEN'", content)
        self.assertIn("'QUOTA_EXCEEDED'", content)

    def test_confirm_hold_signature_and_codes(self):
        with open(RPC_CONFIRM_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("confirm_hold", content)
        self.assertIn("p_slot_id", content)
        self.assertIn("p_user_id", content)
        self.assertIn("hold_expires_at > clock_timestamp()", content)
        self.assertIn("'CONFIRMED'", content)
        self.assertIn("'HOLD_EXPIRED'", content)

    def test_cancel_booking_signature_and_codes(self):
        with open(RPC_CANCEL_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("cancel_booking", content)
        self.assertIn("p_slot_id", content)
        self.assertIn("'CANCELLED'", content)


class BookingEngineSimulator:
    """
    Thread-safe database engine simulating the atomic stored procedures
    using SQLite with immediate transaction serialization.
    """
    def __init__(self, db_path):
        self.db_path = db_path
        self._user_locks = {}
        self._global_lock = threading.Lock()

    def get_user_lock(self, user_id, date):
        key = f"{user_id}:{date}"
        with self._global_lock:
            if key not in self._user_locks:
                self._user_locks[key] = threading.Lock()
            return self._user_locks[key]

    def place_hold(self, resource_name, booking_date, time_slot, user_id):
        # 1. Advisory lock per (user_id, date)
        user_lock = self.get_user_lock(user_id, booking_date)
        with user_lock:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                cursor.execute("BEGIN IMMEDIATE;")
                now = datetime.now(timezone.utc)
                now_str = now.strftime("%Y-%m-%d %H:%M:%S")

                # 2. Check Daily Quota (<= 3 hours)
                cursor.execute("""
                    SELECT COUNT(*) as active_count
                    FROM bookings
                    WHERE user_id = ?
                      AND booking_date = ?
                      AND (
                          status = 'CONFIRMED'
                          OR (status = 'HELD' AND hold_expires_at > ?)
                      );
                """, (user_id, booking_date, now_str))
                count = cursor.fetchone()["active_count"]

                if count >= 3:
                    conn.rollback()
                    return {"success": False, "code": "QUOTA_EXCEEDED", "active_count": count}

                # 3. Atomic Conditional Update
                expires_at = (now + timedelta(seconds=90)).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    UPDATE bookings
                    SET status = 'HELD',
                        user_id = ?,
                        hold_expires_at = ?
                    WHERE resource_name = ?
                      AND booking_date = ?
                      AND time_slot = ?
                      AND (
                          status = 'AVAILABLE'
                          OR (status = 'HELD' AND hold_expires_at <= ?)
                      );
                """, (user_id, expires_at, resource_name, booking_date, time_slot, now_str))

                if cursor.rowcount == 0:
                    conn.rollback()
                    return {"success": False, "code": "SLOT_TAKEN"}

                cursor.execute("""
                    SELECT id FROM bookings
                    WHERE resource_name = ? AND booking_date = ? AND time_slot = ?;
                """, (resource_name, booking_date, time_slot))
                slot_id = cursor.fetchone()["id"]

                conn.commit()
                return {"success": True, "code": "HOLD_ACQUIRED", "slot_id": slot_id, "expires_at": expires_at}
            finally:
                conn.close()

    def confirm_hold(self, slot_id, user_id, agenda="", collaborators="[]"):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE;")
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                UPDATE bookings
                SET status = 'CONFIRMED',
                    agenda = ?,
                    collaborators = ?,
                    confirmed_at = ?
                WHERE id = ?
                  AND user_id = ?
                  AND status = 'HELD'
                  AND hold_expires_at > ?;
            """, (agenda, collaborators, now_str, slot_id, user_id, now_str))

            if cursor.rowcount == 0:
                conn.rollback()
                return {"success": False, "code": "HOLD_EXPIRED"}

            conn.commit()
            return {"success": True, "code": "CONFIRMED", "slot_id": slot_id}
        finally:
            conn.close()

    def cancel_booking(self, slot_id, user_id):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE;")
            cursor.execute("""
                UPDATE bookings
                SET status = 'AVAILABLE',
                    user_id = NULL,
                    hold_expires_at = NULL,
                    agenda = NULL,
                    collaborators = '[]',
                    confirmed_at = NULL
                WHERE id = ?
                  AND (user_id = ? OR ? IS NULL)
                  AND status IN ('HELD', 'CONFIRMED');
            """, (slot_id, user_id, user_id))

            if cursor.rowcount == 0:
                conn.rollback()
                return {"success": False, "code": "NOT_FOUND"}

            conn.commit()
            return {"success": True, "code": "CANCELLED", "slot_id": slot_id}
        finally:
            conn.close()


class TestPhase2ConcurrencyAndRules(unittest.TestCase):
    """Multithreaded behavioral testing of concurrency and business rules."""

    def setUp(self):
        self.test_db = os.path.join(DIR, "test_sim.db")
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.executescript("""
            CREATE TABLE resources (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            );
            CREATE TABLE bookings (
                id TEXT PRIMARY KEY,
                resource_name TEXT NOT NULL,
                booking_date TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'AVAILABLE',
                user_id TEXT,
                hold_expires_at TIMESTAMP,
                agenda TEXT,
                collaborators TEXT DEFAULT '[]',
                confirmed_at TIMESTAMP,
                CONSTRAINT uq_slot UNIQUE (resource_name, booking_date, time_slot)
            );
            INSERT INTO resources VALUES ('res-1', 'Pod 1'), ('res-2', 'Room A');
            INSERT INTO bookings (id, resource_name, booking_date, time_slot)
            VALUES 
                ('b1', 'Pod 1', '2026-09-15', '09:00'),
                ('b2', 'Pod 1', '2026-09-15', '10:00'),
                ('b3', 'Pod 1', '2026-09-15', '11:00'),
                ('b4', 'Pod 1', '2026-09-15', '12:00'),
                ('b5', 'Room A', '2026-09-15', '09:00'),
                ('b6', 'Room A', '2026-09-15', '10:00');
        """)
        conn.commit()
        conn.close()
        self.engine = BookingEngineSimulator(self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_single_user_hold_success(self):
        res = self.engine.place_hold("Pod 1", "2026-09-15", "09:00", "user_alice")
        self.assertTrue(res["success"])
        self.assertEqual(res["code"], "HOLD_ACQUIRED")
        self.assertEqual(res["slot_id"], "b1")

    def test_concurrent_double_booking_race_condition(self):
        """Simulate two users clicking the exact same slot at the exact same millisecond."""
        results = []

        def worker(user_id):
            res = self.engine.place_hold("Pod 1", "2026-09-15", "10:00", user_id)
            results.append((user_id, res))

        t1 = threading.Thread(target=worker, args=("user_alice",))
        t2 = threading.Thread(target=worker, args=("user_bob",))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        codes = [r[1]["code"] for r in results]
        # Exactly ONE must succeed and ONE must receive SLOT_TAKEN
        self.assertEqual(codes.count("HOLD_ACQUIRED"), 1, f"Expected exactly 1 success, got {codes}")
        self.assertEqual(codes.count("SLOT_TAKEN"), 1, f"Expected exactly 1 conflict, got {codes}")

    def test_daily_3_hour_quota_enforcement(self):
        """User books 3 hours; attempt for 4th hour must be rejected."""
        self.engine.place_hold("Pod 1", "2026-09-15", "09:00", "user_alice")
        self.engine.place_hold("Pod 1", "2026-09-15", "10:00", "user_alice")
        self.engine.place_hold("Pod 1", "2026-09-15", "11:00", "user_alice")

        # 4th hour attempt
        res = self.engine.place_hold("Pod 1", "2026-09-15", "12:00", "user_alice")
        self.assertFalse(res["success"])
        self.assertEqual(res["code"], "QUOTA_EXCEEDED")

    def test_concurrent_quota_race_condition(self):
        """
        User Alice has 2 hours booked.
        Alice fires 2 requests simultaneously for 1 hour each.
        Only ONE must succeed. She must NOT be able to reach 4 hours.
        """
        self.engine.place_hold("Pod 1", "2026-09-15", "09:00", "user_alice")
        self.engine.place_hold("Pod 1", "2026-09-15", "10:00", "user_alice")

        results = []
        def worker(slot):
            res = self.engine.place_hold("Room A", "2026-09-15", slot, "user_alice")
            results.append(res)

        t1 = threading.Thread(target=worker, args=("09:00",))
        t2 = threading.Thread(target=worker, args=("10:00",))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        codes = [r["code"] for r in results]
        self.assertEqual(codes.count("HOLD_ACQUIRED"), 1, f"Expected 1 success, got {codes}")
        self.assertEqual(codes.count("QUOTA_EXCEEDED"), 1, f"Expected 1 quota block, got {codes}")

    def test_confirm_hold_and_expired_rejection(self):
        hold_res = self.engine.place_hold("Pod 1", "2026-09-15", "09:00", "user_alice")
        slot_id = hold_res["slot_id"]

        # Confirm within TTL
        conf_res = self.engine.confirm_hold(slot_id, "user_alice", "Sprint Planning", "['bob@team.local']")
        self.assertTrue(conf_res["success"])
        self.assertEqual(conf_res["code"], "CONFIRMED")

        # Expired confirm attempt on another slot
        conn = sqlite3.connect(self.test_db)
        past = (datetime.now(timezone.utc) - timedelta(seconds=10)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE bookings SET status = 'HELD', user_id = 'user_bob', hold_expires_at = ? WHERE id = 'b2';", (past,))
        conn.commit()
        conn.close()

        expired_res = self.engine.confirm_hold("b2", "user_bob")
        self.assertFalse(expired_res["success"])
        self.assertEqual(expired_res["code"], "HOLD_EXPIRED")

    def test_cancel_booking_releases_quota(self):
        hold = self.engine.place_hold("Pod 1", "2026-09-15", "09:00", "user_alice")
        self.engine.confirm_hold(hold["slot_id"], "user_alice")

        # Cancel
        cancel_res = self.engine.cancel_booking(hold["slot_id"], "user_alice")
        self.assertTrue(cancel_res["success"])
        self.assertEqual(cancel_res["code"], "CANCELLED")

        # Slot can now be re-booked
        rebook = self.engine.place_hold("Pod 1", "2026-09-15", "09:00", "user_bob")
        self.assertTrue(rebook["success"])
        self.assertEqual(rebook["code"], "HOLD_ACQUIRED")


if __name__ == "__main__":
    print("======================================================================")
    print("Running Automated Tests for Phase 2: Stored Procedures & Concurrency")
    print("======================================================================")
    unittest.main(verbosity=2)
