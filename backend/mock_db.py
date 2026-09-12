"""
backend/mock_db.py
==================
Temporary In-Memory Storage for MultiSeat-WorkSpace (Development Mode)

NOTE:
This module provides a thread-safe, in-memory mock database for resources,
slots, holds, and bookings. It is designed for development while Member 1
(Database Lead) finishes setting up Supabase PostgreSQL.

Features:
- 12 Workspace Resources.
- 8 Hourly blocks per resource (09:00 to 17:00) = 96 slots per day.
- Thread-safe locking (threading.Lock) to prevent race conditions / double-allocations.
- Strict 90-second hold TTL with automatic expiration normalization back to 'AVAILABLE'.
- 3-hour daily user quota enforcement.
"""

import threading
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple

# Configuration Constants
HOLD_DURATION_SECONDS = 90
DAILY_USER_QUOTA_HOURS = 3

DEFAULT_RESOURCES = [
    "Conference Room A",
    "Conference Room B",
    "Executive Boardroom",
    "Meeting Room 1",
    "Meeting Room 2",
    "Meeting Room 3",
    "Focus Pod 1",
    "Focus Pod 2",
    "Focus Pod 3",
    "Collaboration Hub",
    "Design Lab",
    "Quiet Study Pod",
]

DEFAULT_TIME_SLOTS = [
    "09:00-10:00",
    "10:00-11:00",
    "11:00-12:00",
    "12:00-13:00",
    "13:00-14:00",
    "14:00-15:00",
    "15:00-16:00",
    "16:00-17:00",
]


class MockDatabase:
    """
    Thread-safe in-memory store simulating Supabase 'bookings' table.
    """

    def __init__(self):
        self._lock = threading.Lock()
        # Storage schema: { date_str: { slot_id: slot_dict } }
        self._slots_by_date: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def _get_utc_now(self) -> datetime:
        """Returns the current timezone-aware UTC datetime."""
        return datetime.now(timezone.utc)

    def _parse_iso(self, iso_str: Optional[str]) -> Optional[datetime]:
        """Parses an ISO format timestamp string safely into a timezone-aware datetime."""
        if not iso_str:
            return None
        try:
            dt = datetime.fromisoformat(iso_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    def _initialize_date_slots(self, date_str: str) -> None:
        """
        Populates 96 slots (12 resources x 8 hourly slots) for a given date
        if they have not been created yet. Caller must hold self._lock.
        """
        if date_str in self._slots_by_date:
            return

        date_slots = {}
        for resource in DEFAULT_RESOURCES:
            for time_slot in DEFAULT_TIME_SLOTS:
                slot_id = str(uuid.uuid4())
                date_slots[slot_id] = {
                    "slot_id": slot_id,
                    "resource_name": resource,
                    "date": date_str,
                    "time_slot": time_slot,
                    "status": "AVAILABLE",
                    "user_id": None,
                    "hold_expires_at": None,
                    "agenda": None,
                    "collaborators": [],
                }
        self._slots_by_date[date_str] = date_slots

    def _normalize_expired_holds(self, date_str: str) -> None:
        """
        Scans all slots for the given date. If any slot is currently 'HELD'
        and its 90-second hold has expired, automatically reverts it to 'AVAILABLE'.
        Caller must hold self._lock.
        """
        if date_str not in self._slots_by_date:
            return

        now = self._get_utc_now()
        for slot in self._slots_by_date[date_str].values():
            if slot["status"] == "HELD":
                expires_at = self._parse_iso(slot.get("hold_expires_at"))
                if expires_at and expires_at <= now:
                    # Hold has expired -> Revert to AVAILABLE
                    slot["status"] = "AVAILABLE"
                    slot["user_id"] = None
                    slot["hold_expires_at"] = None
                    slot["agenda"] = None
                    slot["collaborators"] = []

    def get_user_active_hours(self, date_str: str, user_id: str, exclude_slot_id: Optional[str] = None) -> int:
        """
        Calculates cumulative active hours (CONFIRMED + active HELD)
        for a user on a given date. Caller must hold self._lock.
        """
        if date_str not in self._slots_by_date or not user_id:
            return 0

        self._normalize_expired_holds(date_str)
        count = 0
        for slot in self._slots_by_date[date_str].values():
            if exclude_slot_id and slot["slot_id"] == exclude_slot_id:
                continue
            if slot["user_id"] == user_id and slot["status"] in ("HELD", "CONFIRMED"):
                count += 1
        return count

    def get_availability(self, date_str: str) -> List[Dict[str, Any]]:
        """
        Retrieves all 96 slots for a specified date.
        Automatically normalizes expired holds before returning.
        """
        with self._lock:
            self._initialize_date_slots(date_str)
            self._normalize_expired_holds(date_str)
            # Return a copy of the list of slot dictionaries
            return [dict(slot) for slot in self._slots_by_date[date_str].values()]

    def place_hold(
        self, resource_name: str, date_str: str, time_slot: str, user_id: str
    ) -> Tuple[str, Optional[Dict[str, Any]], Optional[int]]:
        """
        Atomically attempts to place a 90-second hold on a slot.
        Thread-safe to prevent double allocation.

        Returns:
            (status_code_result, slot_data_dict, expires_in_seconds)
            Possible status_code_result values:
            - 'HOLD_ACQUIRED'
            - 'SLOT_TAKEN'
            - 'QUOTA_EXCEEDED'
            - 'NOT_FOUND'
        """
        with self._lock:
            self._initialize_date_slots(date_str)
            self._normalize_expired_holds(date_str)

            # 1. Enforce 3-hour daily user quota
            current_user_hours = self.get_user_active_hours(date_str, user_id)
            if current_user_hours >= DAILY_USER_QUOTA_HOURS:
                return "QUOTA_EXCEEDED", None, None

            # 2. Locate the targeted slot (support both "09:00" and "09:00-10:00")
            target_slot = None
            for slot in self._slots_by_date[date_str].values():
                name_matches = slot["resource_name"].strip().lower() == resource_name.strip().lower()
                time_matches = (
                    slot["time_slot"] == time_slot
                    or slot["time_slot"].startswith(time_slot)
                    or time_slot.startswith(slot["time_slot"].split("-")[0])
                )
                if name_matches and time_matches:
                    target_slot = slot
                    break

            if not target_slot:
                return "NOT_FOUND", None, None

            # 3. Check availability
            if target_slot["status"] != "AVAILABLE":
                return "SLOT_TAKEN", None, None

            # 4. Acquire the 90-second soft-lock
            now = self._get_utc_now()
            expires_at = now + timedelta(seconds=HOLD_DURATION_SECONDS)

            target_slot["status"] = "HELD"
            target_slot["user_id"] = user_id
            target_slot["hold_expires_at"] = expires_at.isoformat()
            target_slot["agenda"] = None
            target_slot["collaborators"] = []

            return "HOLD_ACQUIRED", dict(target_slot), HOLD_DURATION_SECONDS

    def confirm_booking(
        self, slot_id: str, user_id: str, agenda: Optional[str] = None, collaborators: Optional[List[str]] = None
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Atomically finalizes a held slot to 'CONFIRMED'.

        Returns:
            (status_code_result, slot_data_dict)
            Possible status_code_result values:
            - 'CONFIRMED'
            - 'HOLD_EXPIRED'
            - 'UNAUTHORIZED'
            - 'INVALID_STATE'
            - 'NOT_FOUND'
        """
    def _find_slot_internal(self, slot_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        Locates a slot across all dates. Supports:
        1. Exact UUID key match.
        2. Exact slot["slot_id"] match.
        3. Composite slug match (e.g., 'room1_2026-09-13_09:00' or '{resource}_{date}_{time}').
        Caller must hold self._lock.
        """
        # 1. Exact key match in _slots_by_date
        for date_str, slots in self._slots_by_date.items():
            if slot_id in slots:
                return date_str, slots[slot_id]
            for slot in slots.values():
                if slot["slot_id"] == slot_id:
                    return date_str, slot

        # 2. Composite ID / slug match
        clean_target = slot_id.replace("-", "").replace("_", "").replace(" ", "").lower()
        for date_str, slots in self._slots_by_date.items():
            for slot in slots.values():
                res_clean = slot["resource_name"].replace("-", "").replace("_", "").replace(" ", "").lower()
                date_clean = slot["date"].replace("-", "")
                time_clean = slot["time_slot"].replace("-", "").replace(":", "")
                combined = f"{res_clean}{date_clean}{time_clean}"
                if clean_target in combined or combined in clean_target:
                    return date_str, slot

        return None, None

    def confirm_booking(
        self, slot_id: str, user_id: str, agenda: Optional[str] = None, collaborators: Optional[List[str]] = None
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Atomically finalizes a held slot to 'CONFIRMED'.

        Returns:
            (status_code_result, slot_data_dict)
            Possible status_code_result values:
            - 'CONFIRMED'
            - 'HOLD_EXPIRED'
            - 'UNAUTHORIZED'
            - 'NOT_FOUND'
        """
        with self._lock:
            target_date, target_slot = self._find_slot_internal(slot_id)

            if not target_slot or not target_date:
                return "NOT_FOUND", None

            # Check if hold expired prior to normalization
            now = self._get_utc_now()
            expires_at = self._parse_iso(target_slot.get("hold_expires_at"))
            if target_slot["status"] == "HELD" and expires_at and expires_at <= now:
                # Reset to AVAILABLE immediately
                target_slot["status"] = "AVAILABLE"
                target_slot["user_id"] = None
                target_slot["hold_expires_at"] = None
                target_slot["agenda"] = None
                target_slot["collaborators"] = []
                return "HOLD_EXPIRED", None

            # Normalize holds for that date
            self._normalize_expired_holds(target_date)

            # Check if slot is currently held
            if target_slot["status"] != "HELD":
                return "HOLD_EXPIRED", None

            # Verify user authorization
            if target_slot.get("user_id") and target_slot["user_id"] != user_id:
                return "UNAUTHORIZED", None

            # Finalize booking
            target_slot["status"] = "CONFIRMED"
            target_slot["hold_expires_at"] = None
            target_slot["agenda"] = agenda or ""
            target_slot["collaborators"] = collaborators or []

            return "CONFIRMED", dict(target_slot)

    def cancel_booking(self, slot_id: str, user_id: Optional[str] = None) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Releases a hold or cancels a confirmed booking, returning the slot to 'AVAILABLE'.

        Returns:
            (status_code_result, slot_data_dict)
            Possible status_code_result values:
            - 'CANCELLED'
            - 'UNAUTHORIZED'
            - 'NOT_FOUND'
        """
        with self._lock:
            target_date, target_slot = self._find_slot_internal(slot_id)

            if not target_slot or not target_date:
                return "NOT_FOUND", None

            # Optional user verification
            if user_id and target_slot.get("user_id") and target_slot["user_id"] != user_id:
                return "UNAUTHORIZED", None

            # Reset slot back to AVAILABLE
            target_slot["status"] = "AVAILABLE"
            target_slot["user_id"] = None
            target_slot["hold_expires_at"] = None
            target_slot["agenda"] = None
            target_slot["collaborators"] = []

            return "CANCELLED", dict(target_slot)

    def get_slot_by_id(self, slot_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a slot by ID after normalizing expired holds."""
        with self._lock:
            for date_str, slots in self._slots_by_date.items():
                if slot_id in slots:
                    self._normalize_expired_holds(date_str)
                    return dict(slots[slot_id])
            return None

    def reset(self) -> None:
        """Clears all stored slots (useful for testing)."""
        with self._lock:
            self._slots_by_date.clear()


# Global in-memory mock database singleton instance
mock_db = MockDatabase()
