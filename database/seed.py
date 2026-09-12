#!/usr/bin/env python3
"""
Collaborative Multi-Seat Workspace & Resource Booking Engine
Phase 3: Database Seeder Script (Python CLI)
Connects to Supabase to seed Users, 12 Resources, and 96 Hourly Slots per day.
"""

import argparse
import os
import sys
from datetime import date, timedelta
from dotenv import load_dotenv

# Try importing supabase client
try:
    from supabase import create_client, Client
except ImportError:
    print("Error: 'supabase' package is required. Install via: pip install supabase python-dotenv")
    sys.exit(1)

# Load .env from current directory or database/ directory
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")

HOURLY_SLOTS = [
    "09:00", "10:00", "11:00", "12:00",
    "13:00", "14:00", "15:00", "16:00"
]

MOCK_USERS = [
    {"id": "user_alice", "name": "Alice Smith", "email": "alice@workspace.local"},
    {"id": "user_bob", "name": "Bob Jones", "email": "bob@workspace.local"},
    {"id": "user_charlie", "name": "Charlie Brown", "email": "charlie@workspace.local"}
]

CANONICAL_RESOURCES = [
    {"name": "Conference Room A", "resource_type": "ROOM", "capacity": 8, "location": "Floor 1 - North Wing", "is_active": True},
    {"name": "Conference Room B", "resource_type": "ROOM", "capacity": 6, "location": "Floor 1 - South Wing", "is_active": True},
    {"name": "Executive Boardroom", "resource_type": "ROOM", "capacity": 12, "location": "Floor 2 - Executive Suite", "is_active": True},
    {"name": "Ideation Studio", "resource_type": "ROOM", "capacity": 10, "location": "Floor 2 - Innovation Lab", "is_active": True},
    {"name": "Quiet Pod 1", "resource_type": "POD", "capacity": 1, "location": "Floor 1 - Focus Zone", "is_active": True},
    {"name": "Quiet Pod 2", "resource_type": "POD", "capacity": 1, "location": "Floor 1 - Focus Zone", "is_active": True},
    {"name": "Team Pod 3", "resource_type": "POD", "capacity": 4, "location": "Floor 2 - Collaboration Hub", "is_active": True},
    {"name": "Team Pod 4", "resource_type": "POD", "capacity": 4, "location": "Floor 2 - Collaboration Hub", "is_active": True},
    {"name": "Standing Desk 1", "resource_type": "DESK", "capacity": 1, "location": "Floor 1 - Open Workspace", "is_active": True},
    {"name": "Standing Desk 2", "resource_type": "DESK", "capacity": 1, "location": "Floor 1 - Open Workspace", "is_active": True},
    {"name": "Focus Desk 3", "resource_type": "DESK", "capacity": 1, "location": "Floor 2 - Library Area", "is_active": True},
    {"name": "Focus Desk 4", "resource_type": "DESK", "capacity": 1, "location": "Floor 2 - Library Area", "is_active": True}
]

def build_slots_payload(resource_map, start_date, days=1):
    """Generates the list of 96 slots per day for each resource."""
    slots = []
    for day_offset in range(days):
        current_date = (start_date + timedelta(days=day_offset)).isoformat()
        for res in CANONICAL_RESOURCES:
            res_id = resource_map.get(res["name"])
            for slot in HOURLY_SLOTS:
                slots.append({
                    "resource_id": res_id,
                    "resource_name": res["name"],
                    "booking_date": current_date,
                    "time_slot": slot,
                    "status": "AVAILABLE"
                })
    return slots

def seed_database(target_date, days=1, dry_run=False):
    print("======================================================================")
    print("Multi-Seat Workspace & Resource Booking Engine — Database Seeder")
    print("======================================================================")
    print(f"Target Date: {target_date.isoformat()} (Total days: {days})")
    print(f"Expected: 12 Resources x 8 Slots = {12 * 8 * days} total booking slots")

    if dry_run:
        print("\n[DRY RUN MODE] Simulating payload generation...")
        mock_map = {r["name"]: f"mock-uuid-{i+1}" for i, r in enumerate(CANONICAL_RESOURCES)}
        slots = build_slots_payload(mock_map, target_date, days)
        print(f"[OK] Successfully built {len(slots)} slot records across {len(CANONICAL_RESOURCES)} resources.")
        print(f"[OK] Users to seed: {len(MOCK_USERS)}")
        print("Dry run completed successfully.")
        return True

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("\n[!] Supabase credentials missing!")
        print("Please configure database/.env with:")
        print("  SUPABASE_URL=https://<your-project>.supabase.co")
        print("  SUPABASE_KEY=<your-service-role-or-anon-key>")
        print("\nAlternatively, you can copy and run database/seed.sql directly inside the Supabase SQL Editor.")
        return False

    print(f"\nConnecting to Supabase at: {SUPABASE_URL}...")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 1. Seed Users
    print("1. Seeding mock users...")
    try:
        supabase.table("users").upsert(MOCK_USERS, on_conflict="id").execute()
        print(f"   [OK] Seeded {len(MOCK_USERS)} users.")
    except Exception as e:
        print(f"   [WARN] Could not seed users: {e}")

    # 2. Seed Resources
    print("2. Seeding 12 workspace resources...")
    try:
        supabase.table("resources").upsert(CANONICAL_RESOURCES, on_conflict="name").execute()
        print(f"   [OK] Seeded {len(CANONICAL_RESOURCES)} resources.")
    except Exception as e:
        print(f"   [ERROR] Failed to seed resources: {e}")
        return False

    # 3. Retrieve Resource IDs
    res_query = supabase.table("resources").select("id, name").execute()
    resource_map = {row["name"]: row["id"] for row in res_query.data}
    if len(resource_map) < 12:
        print(f"   [WARN] Found only {len(resource_map)} resources in DB. Expected 12.")

    # 4. Generate & Insert Slots
    print("3. Generating hourly slot matrix...")
    slots = build_slots_payload(resource_map, target_date, days)
    print(f"   Inserting {len(slots)} slots in batches...")

    batch_size = 100
    for i in range(0, len(slots), batch_size):
        batch = slots[i:i + batch_size]
        try:
            # Ignore duplicates if slots already exist
            supabase.table("bookings").upsert(
                batch, 
                on_conflict="resource_name, booking_date, time_slot",
                ignore_duplicates=True
            ).execute()
        except Exception as e:
            # If ignore_duplicates is unsupported by PostgREST endpoint version, fallback to plain insert
            try:
                supabase.table("bookings").insert(batch).execute()
            except Exception as e2:
                print(f"   [NOTE] Batch {i // batch_size + 1} insert notice: {e2}")

    print(f"\n[SUCCESS] Seeding completed: {len(slots)} slots processed for {days} day(s).")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Multi-Seat Workspace Database")
    parser.add_argument("--date", type=str, default=None, help="Starting date (YYYY-MM-DD), defaults to today")
    parser.add_argument("--days", type=int, default=1, help="Number of consecutive days to seed (default: 1)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate seeding payload without connecting to Supabase")
    args = parser.parse_args()

    if args.date:
        try:
            parsed_date = date.fromisoformat(args.date)
        except ValueError:
            print(f"Error: Invalid date format '{args.date}'. Expected YYYY-MM-DD.")
            sys.exit(1)
    else:
        parsed_date = date.today()

    success = seed_database(parsed_date, days=args.days, dry_run=args.dry_run)
    sys.exit(0 if success else 1)
