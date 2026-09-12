#!/usr/bin/env python3
"""
Automated Test Suite for Phase 1: Database Schema & Architecture Verification
Validates DDL specifications, constraints, indexing strategies, and view semantics.
"""

import os
import re
import sqlite3
import unittest
from datetime import datetime, timezone, timedelta

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "schema.sql")

class TestPhase1SchemaStatic(unittest.TestCase):
    """Static and structural validation of database/schema.sql."""

    def setUp(self):
        self.assertTrue(os.path.exists(SCHEMA_PATH), f"Missing schema file at {SCHEMA_PATH}")
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            self.sql_content = f.read()

    def test_tables_defined(self):
        """Verify all 3 core architectural tables are defined."""
        self.assertRegex(self.sql_content, r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?users\b", "Missing 'users' table")
        self.assertRegex(self.sql_content, r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?resources\b", "Missing 'resources' table")
        self.assertRegex(self.sql_content, r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?bookings\b", "Missing 'bookings' table")

    def test_zero_double_allocation_unique_constraint(self):
        """Verify the physical unicity constraint preventing duplicate slots."""
        pattern = r"CONSTRAINT\s+uq_resource_date_slot\s+UNIQUE\s*\(\s*resource_name\s*,\s*booking_date\s*,\s*time_slot\s*\)"
        self.assertRegex(self.sql_content, pattern, "Missing composite UNIQUE(resource_name, booking_date, time_slot) constraint!")

    def test_check_constraints_defined(self):
        """Verify data integrity check constraints."""
        # Status constraint
        self.assertIn("'AVAILABLE', 'HELD', 'CONFIRMED'", self.sql_content, "Status check constraint missing or invalid")
        # Time slots (8 hourly blocks 09:00 - 16:00)
        for slot in ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00']:
            self.assertIn(f"'{slot}'", self.sql_content, f"Missing time slot definition for {slot}")
        # Semantic checks
        self.assertIn("chk_held_state", self.sql_content, "Missing chk_held_state constraint")
        self.assertIn("chk_confirmed_state", self.sql_content, "Missing chk_confirmed_state constraint")

    def test_performance_indexes_defined(self):
        """Verify index declarations for fast 5s polling and instant quota queries."""
        self.assertRegex(self.sql_content, r"CREATE\s+INDEX\s+(IF\s+NOT\s+EXISTS\s+)?idx_bookings_grid\b", "Missing grid index")
        self.assertRegex(self.sql_content, r"CREATE\s+INDEX\s+(IF\s+NOT\s+EXISTS\s+)?idx_bookings_user_quota\b", "Missing quota index")
        self.assertRegex(self.sql_content, r"CREATE\s+INDEX\s+(IF\s+NOT\s+EXISTS\s+)?idx_bookings_hold_expiry\b", "Missing hold expiry index")

    def test_dynamic_availability_view_defined(self):
        """Verify dynamic view normalizing expired holds to 'AVAILABLE'."""
        self.assertRegex(self.sql_content, r"CREATE\s+(OR\s+REPLACE\s+)?VIEW\s+v_resource_availability\b", "Missing availability view")
        self.assertIn("hold_expires_at > NOW()", self.sql_content, "View must evaluate hold_expires_at against current time")


class TestPhase1SchemaBehavior(unittest.TestCase):
    """Behavioral and constraint simulation using an in-memory SQL engine."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("PRAGMA foreign_keys = ON;")
        cursor = self.conn.cursor()

        # Build SQLite-compatible test replica of schema.sql
        cursor.executescript("""
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE resources (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                resource_type TEXT NOT NULL CHECK (resource_type IN ('ROOM', 'POD', 'DESK')),
                capacity INT NOT NULL DEFAULT 1 CHECK (capacity > 0),
                location TEXT NOT NULL DEFAULT 'Main Level',
                is_active BOOLEAN NOT NULL DEFAULT 1
            );

            CREATE TABLE bookings (
                id TEXT PRIMARY KEY,
                resource_id TEXT NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
                resource_name TEXT NOT NULL,
                booking_date TEXT NOT NULL,
                time_slot TEXT NOT NULL CHECK (time_slot IN ('09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00')),
                status TEXT NOT NULL DEFAULT 'AVAILABLE' CHECK (status IN ('AVAILABLE', 'HELD', 'CONFIRMED')),
                user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
                hold_expires_at TIMESTAMP,
                agenda TEXT,
                collaborators TEXT DEFAULT '[]',
                confirmed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_resource_date_slot UNIQUE (resource_name, booking_date, time_slot),
                CONSTRAINT chk_held_state CHECK (status != 'HELD' OR (user_id IS NOT NULL AND hold_expires_at IS NOT NULL)),
                CONSTRAINT chk_confirmed_state CHECK (status != 'CONFIRMED' OR (user_id IS NOT NULL AND confirmed_at IS NOT NULL))
            );

            CREATE VIEW v_resource_availability AS
            SELECT 
                b.id,
                b.resource_id,
                b.resource_name,
                b.booking_date,
                b.time_slot,
                b.user_id,
                b.hold_expires_at,
                b.status AS raw_status,
                CASE 
                    WHEN b.status = 'CONFIRMED' THEN 'CONFIRMED'
                    WHEN b.status = 'HELD' AND b.hold_expires_at > datetime('now') THEN 'HELD'
                    ELSE 'AVAILABLE'
                END AS status
            FROM bookings b;
        """)
        self.conn.commit()

        # Seed 1 user and 1 resource
        cursor.execute("INSERT INTO users (id, name, email) VALUES ('user_alice', 'Alice', 'alice@test.local');")
        cursor.execute("INSERT INTO resources (id, name, resource_type) VALUES ('res-1', 'Conference Room A', 'ROOM');")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_zero_double_allocation_prevention(self):
        """Simulate two simultaneous insertions for the same slot; verify unique constraint rejects duplicate."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO bookings (id, resource_id, resource_name, booking_date, time_slot, status)
            VALUES ('slot-1', 'res-1', 'Conference Room A', '2026-09-15', '10:00', 'AVAILABLE');
        """)
        self.conn.commit()

        # Second attempt for identical slot MUST fail with IntegrityError
        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO bookings (id, resource_id, resource_name, booking_date, time_slot, status)
                VALUES ('slot-2', 'res-1', 'Conference Room A', '2026-09-15', '10:00', 'AVAILABLE');
            """)
            self.conn.commit()

    def test_check_constraint_held_state(self):
        """Verify status='HELD' requires user_id and hold_expires_at."""
        cursor = self.conn.cursor()
        # Missing user_id and hold_expires_at
        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO bookings (id, resource_id, resource_name, booking_date, time_slot, status)
                VALUES ('slot-fail', 'res-1', 'Conference Room A', '2026-09-15', '11:00', 'HELD');
            """)
            self.conn.commit()

    def test_check_constraint_confirmed_state(self):
        """Verify status='CONFIRMED' requires user_id and confirmed_at."""
        cursor = self.conn.cursor()
        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO bookings (id, resource_id, resource_name, booking_date, time_slot, status, user_id)
                VALUES ('slot-fail2', 'res-1', 'Conference Room A', '2026-09-15', '12:00', 'CONFIRMED', 'user_alice');
            """)
            self.conn.commit()

    def test_availability_view_ttl_logic(self):
        """Verify view calculates dynamic status correctly for ACTIVE vs EXPIRED holds."""
        cursor = self.conn.cursor()
        now = datetime.now(timezone.utc)
        active_expiry = (now + timedelta(seconds=90)).strftime("%Y-%m-%d %H:%M:%S")
        past_expiry = (now - timedelta(seconds=10)).strftime("%Y-%m-%d %H:%M:%S")

        # Slot 1: Active Hold (90s in future)
        cursor.execute("""
            INSERT INTO bookings (id, resource_id, resource_name, booking_date, time_slot, status, user_id, hold_expires_at)
            VALUES ('slot-active', 'res-1', 'Conference Room A', '2026-09-15', '09:00', 'HELD', 'user_alice', ?);
        """, (active_expiry,))

        # Slot 2: Expired Hold (10s in past)
        cursor.execute("""
            INSERT INTO bookings (id, resource_id, resource_name, booking_date, time_slot, status, user_id, hold_expires_at)
            VALUES ('slot-expired', 'res-1', 'Conference Room A', '2026-09-15', '10:00', 'HELD', 'user_alice', ?);
        """, (past_expiry,))

        # Slot 3: Confirmed
        cursor.execute("""
            INSERT INTO bookings (id, resource_id, resource_name, booking_date, time_slot, status, user_id, confirmed_at)
            VALUES ('slot-confirmed', 'res-1', 'Conference Room A', '2026-09-15', '11:00', 'CONFIRMED', 'user_alice', CURRENT_TIMESTAMP);
        """)
        self.conn.commit()

        # Query dynamic view
        cursor.execute("SELECT id, status FROM v_resource_availability ORDER BY time_slot;")
        results = dict(cursor.fetchall())

        self.assertEqual(results['slot-active'], 'HELD', "Active hold must project as 'HELD'")
        self.assertEqual(results['slot-expired'], 'AVAILABLE', "Expired hold must automatically project as 'AVAILABLE'")
        self.assertEqual(results['slot-confirmed'], 'CONFIRMED', "Confirmed slot must project as 'CONFIRMED'")


if __name__ == "__main__":
    print("======================================================================")
    print("Running Automated Tests for Phase 1: Database Schema & Integrity")
    print("======================================================================")
    unittest.main(verbosity=2)
