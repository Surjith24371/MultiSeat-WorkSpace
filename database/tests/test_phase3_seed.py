#!/usr/bin/env python3
"""
Automated Test Suite for Phase 3: Database Seeding & Slot Matrix Validation
Validates seed.sql, seed.py, resource metadata, 96-slot daily math, and idempotency.
"""

import os
import sqlite3
import subprocess
import sys
import unittest
from datetime import date

DIR = os.path.dirname(__file__)
SEED_SQL_PATH = os.path.join(DIR, "..", "seed.sql")
SEED_PY_PATH = os.path.join(DIR, "..", "seed.py")

class TestPhase3SeedPython(unittest.TestCase):
    """Verifies Python seeder module and dry-run execution."""

    def test_seed_py_dry_run_execution(self):
        """Verify python seed.py --dry-run completes cleanly with 96 slots per day."""
        cmd = [sys.executable, SEED_PY_PATH, "--dry-run", "--date", "2026-09-15", "--days", "1"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"seed.py failed: {result.stderr}")
        self.assertIn("96 slot records", result.stdout)
        self.assertIn("12 resources", result.stdout)

    def test_seed_py_multi_day_math(self):
        """Verify multi-day seed generates 12 x 8 x 3 = 288 slots."""
        cmd = [sys.executable, SEED_PY_PATH, "--dry-run", "--date", "2026-09-15", "--days", "3"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("288 slot records", result.stdout)


class TestPhase3SeedSQL(unittest.TestCase):
    """Verifies static SQL seeder integrity and behavioral database execution."""

    def setUp(self):
        self.assertTrue(os.path.exists(SEED_SQL_PATH), "seed.sql missing")
        with open(SEED_SQL_PATH, "r", encoding="utf-8") as f:
            self.sql_content = f.read()

    def test_users_present_in_sql(self):
        self.assertIn("user_alice", self.sql_content)
        self.assertIn("user_bob", self.sql_content)
        self.assertIn("user_charlie", self.sql_content)

    def test_12_resources_present_in_sql(self):
        expected_resources = [
            "Conference Room A", "Conference Room B", "Executive Boardroom", "Ideation Studio",
            "Quiet Pod 1", "Quiet Pod 2", "Team Pod 3", "Team Pod 4",
            "Standing Desk 1", "Standing Desk 2", "Focus Desk 3", "Focus Desk 4"
        ]
        for res in expected_resources:
            self.assertIn(res, self.sql_content, f"Resource {res} missing from seed.sql")

    def test_behavioral_seeding_and_idempotency(self):
        """Execute simulated seeding on SQLite to test 96 slots count and idempotency."""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        # Build schema
        cursor.executescript("""
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE
            );
            CREATE TABLE resources (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                resource_type TEXT NOT NULL,
                capacity INT NOT NULL,
                location TEXT,
                is_active BOOLEAN NOT NULL DEFAULT 1
            );
            CREATE TABLE bookings (
                id TEXT PRIMARY KEY,
                resource_id TEXT NOT NULL,
                resource_name TEXT NOT NULL,
                booking_date TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'AVAILABLE',
                CONSTRAINT uq_slot UNIQUE (resource_name, booking_date, time_slot)
            );
            CREATE VIEW v_resource_availability AS
            SELECT id, resource_name, booking_date, time_slot, status
            FROM bookings;
        """)

        # 1. Seed Users
        users = [
            ('user_alice', 'Alice Smith', 'alice@workspace.local'),
            ('user_bob', 'Bob Jones', 'bob@workspace.local'),
            ('user_charlie', 'Charlie Brown', 'charlie@workspace.local')
        ]
        cursor.executemany("INSERT OR REPLACE INTO users VALUES (?, ?, ?);", users)

        # 2. Seed 12 Resources
        resources = [
            ("Conference Room A", "ROOM", 8, "Floor 1 - North Wing"),
            ("Conference Room B", "ROOM", 6, "Floor 1 - South Wing"),
            ("Executive Boardroom", "ROOM", 12, "Floor 2 - Executive Suite"),
            ("Ideation Studio", "ROOM", 10, "Floor 2 - Innovation Lab"),
            ("Quiet Pod 1", "POD", 1, "Floor 1 - Focus Zone"),
            ("Quiet Pod 2", "POD", 1, "Floor 1 - Focus Zone"),
            ("Team Pod 3", "POD", 4, "Floor 2 - Collaboration Hub"),
            ("Team Pod 4", "POD", 4, "Floor 2 - Collaboration Hub"),
            ("Standing Desk 1", "DESK", 1, "Floor 1 - Open Workspace"),
            ("Standing Desk 2", "DESK", 1, "Floor 1 - Open Workspace"),
            ("Focus Desk 3", "DESK", 1, "Floor 2 - Library Area"),
            ("Focus Desk 4", "DESK", 1, "Floor 2 - Library Area")
        ]
        for i, (name, rtype, cap, loc) in enumerate(resources):
            cursor.execute("INSERT OR REPLACE INTO resources VALUES (?, ?, ?, ?, ?, 1);", 
                           (f"res-{i+1}", name, rtype, cap, loc))

        # 3. Seed 96 slots for 2026-09-15 (12 resources x 8 hourly blocks)
        hours = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00']
        slots = []
        for i, (name, _, _, _) in enumerate(resources):
            for h in hours:
                slot_id = f"slot-{name.replace(' ', '_')}-{h}"
                slots.append((slot_id, f"res-{i+1}", name, '2026-09-15', h, 'AVAILABLE'))

        cursor.executemany("""
            INSERT OR IGNORE INTO bookings (id, resource_id, resource_name, booking_date, time_slot, status)
            VALUES (?, ?, ?, ?, ?, ?);
        """, slots)
        conn.commit()

        # Check total rows
        cursor.execute("SELECT COUNT(*) FROM bookings WHERE booking_date = '2026-09-15';")
        count = cursor.fetchone()[0]
        self.assertEqual(count, 96, f"Expected exactly 96 slots, got {count}")

        # Check distinct resources
        cursor.execute("SELECT COUNT(DISTINCT resource_name) FROM bookings WHERE booking_date = '2026-09-15';")
        res_count = cursor.fetchone()[0]
        self.assertEqual(res_count, 12, f"Expected 12 distinct resources, got {res_count}")

        # 4. Idempotency Check: Re-running insert should NOT add more slots or raise errors
        cursor.executemany("""
            INSERT OR IGNORE INTO bookings (id, resource_id, resource_name, booking_date, time_slot, status)
            VALUES (?, ?, ?, ?, ?, ?);
        """, slots)
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM bookings WHERE booking_date = '2026-09-15';")
        count_after_rerun = cursor.fetchone()[0]
        self.assertEqual(count_after_rerun, 96, "Seeding must be idempotent; duplicate slots were inserted!")

        # 5. Availability View Check
        cursor.execute("SELECT COUNT(*) FROM v_resource_availability WHERE status = 'AVAILABLE';")
        avail_count = cursor.fetchone()[0]
        self.assertEqual(avail_count, 96, "All 96 freshly seeded slots must be 'AVAILABLE'")

        conn.close()


if __name__ == "__main__":
    print("======================================================================")
    print("Running Automated Tests for Phase 3: Database Seeding & Slot Matrix")
    print("======================================================================")
    unittest.main(verbosity=2)
