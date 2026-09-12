"""
backend/routes/resources.py
===========================
REST API Endpoints for Resource Booking in MultiSeat-WorkSpace.

Endpoints implemented:
1. GET    /api/resources/availability?date=YYYY-MM-DD -> 200 OK (returns slots for date)
2. POST   /api/resources/hold                         -> 201 Created / 409 Conflict / 422 Quota
3. POST   /api/resources/confirm                      -> 200 OK / 404 Not Found / 410 Gone / 403 Forbidden
4. DELETE /api/resources/cancel/<slot_id>             -> 200 OK / 404 Not Found
5. GET    /api/resources/status                       -> 200 OK (Blueprint check)

Database Architecture:
- Primary: Supabase PostgreSQL (Cloud Database with atomic place_hold RPC).
- Fallback: Thread-Safe In-Memory Mock Database (mock_db).
"""

from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from config import supabase_client
from mock_db import mock_db

# Create the resources blueprint with prefix '/api/resources'
resources_bp = Blueprint("resources", __name__, url_prefix="/api/resources")


@resources_bp.route("/status", methods=["GET"])
def resource_status():
    """
    Sanity check endpoint to verify that the resources blueprint is mounted and active.
    Also reports whether Supabase or MockDB is the active data engine.
    """
    mode = "Supabase PostgreSQL (Cloud)" if supabase_client else "In-Memory Mock Store"
    return jsonify({
        "success": True,
        "message": "Resources blueprint is registered and active",
        "data_mode": mode
    }), 200


# ----------------------------------------------------------------------------
# 1. AVAILABILITY ENDPOINT
# ----------------------------------------------------------------------------
@resources_bp.route("/availability", methods=["GET"])
def get_availability():
    """
    GET /api/resources/availability?date=YYYY-MM-DD

    Retrieves all slots for the requested date.
    Releases any expired 90-second holds back to 'AVAILABLE' before returning.
    """
    date_str = request.args.get("date", "").strip()

    # 1. Validate that date parameter was provided
    if not date_str:
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": "Missing required query parameter: 'date' (expected format: YYYY-MM-DD)"
        }), 400

    # 2. Validate date format (YYYY-MM-DD)
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": "Invalid date format. Expected YYYY-MM-DD (e.g. 2026-09-13)"
        }), 400

    # 3. Fetch from Supabase if connected
    if supabase_client:
        try:
            # Query bookings for given date
            res = (
                supabase_client.table("bookings")
                .select("*")
                .eq("booking_date", date_str)
                .order("resource_name")
                .order("time_slot")
                .execute()
            )
            raw_slots = res.data or []

            # Check and normalize expired holds
            now_utc = datetime.now(timezone.utc)
            expired_ids = []
            normalized_slots = []

            for slot in raw_slots:
                # Rename 'id' to 'slot_id' if needed for API consistency
                slot_dict = dict(slot)
                if "slot_id" not in slot_dict:
                    slot_dict["slot_id"] = slot_dict.get("id")

                if slot_dict.get("status") == "HELD" and slot_dict.get("hold_expires_at"):
                    try:
                        exp_str = slot_dict["hold_expires_at"].replace("Z", "+00:00")
                        exp_dt = datetime.fromisoformat(exp_str)
                        if exp_dt.tzinfo is None:
                            exp_dt = exp_dt.replace(tzinfo=timezone.utc)

                        if exp_dt <= now_utc:
                            # Revert expired hold in response
                            slot_dict["status"] = "AVAILABLE"
                            slot_dict["user_id"] = None
                            slot_dict["hold_expires_at"] = None
                            slot_dict["agenda"] = None
                            slot_dict["collaborators"] = []
                            expired_ids.append(slot["id"])
                    except Exception:
                        pass

                normalized_slots.append(slot_dict)

            # Persist expiration cleanup to Supabase database
            if expired_ids:
                supabase_client.table("bookings").update({
                    "status": "AVAILABLE",
                    "user_id": None,
                    "hold_expires_at": None,
                    "agenda": None,
                    "collaborators": []
                }).in_("id", expired_ids).execute()

            return jsonify({
                "success": True,
                "date": date_str,
                "count": len(normalized_slots),
                "slots": normalized_slots
            }), 200

        except Exception as e:
            print(f"[WARNING] Supabase query failed: {e}. Falling back to mock_db.")

    # Fallback: Retrieve slots from in-memory store
    slots = mock_db.get_availability(date_str)
    return jsonify({
        "success": True,
        "date": date_str,
        "count": len(slots),
        "slots": slots
    }), 200


# ----------------------------------------------------------------------------
# 2. HOLD ENDPOINT (90-second soft-lock)
# ----------------------------------------------------------------------------
@resources_bp.route("/hold", methods=["POST"])
def place_hold():
    """
    POST /api/resources/hold
    Body:
    {
        "resource_name": "Meeting Room 1",
        "date": "2026-09-13",
        "time_slot": "09:00-10:00",
        "user_id": "user_alice"
    }

    Enforces:
    - Field validation (400)
    - 3-hour daily user quota (422)
    - Concurrency conflict protection (409)
    - 90-second TTL on success (201)
    """
    data = request.get_json(silent=True) or {}

    # 1. Validate required fields
    required_fields = ["resource_name", "date", "time_slot", "user_id"]
    missing = [field for field in required_fields if not data.get(field)]
    if missing:
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": f"Missing required fields: {', '.join(missing)}"
        }), 400

    resource_name = str(data["resource_name"]).strip()
    date_str = str(data["date"]).strip()
    time_slot = str(data["time_slot"]).strip()
    user_id = str(data["user_id"]).strip()

    # 2. Validate date format
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": "Invalid date format. Expected YYYY-MM-DD"
        }), 400

    # Clean time slot to start hour format (e.g. "09:00-10:00" -> "09:00")
    clean_time = time_slot.split("-")[0].strip()

    # 3. Call Supabase RPC place_hold if connected
    if supabase_client:
        try:
            rpc_res = supabase_client.rpc("place_hold", {
                "p_resource_name": resource_name,
                "p_booking_date": date_str,
                "p_time_slot": clean_time,
                "p_user_id": user_id
            }).execute()

            result = rpc_res.data or {}
            code = result.get("code")

            if code == "QUOTA_EXCEEDED":
                return jsonify({
                    "success": False,
                    "error": "Quota Exceeded",
                    "message": result.get("message", "Daily quota limit of 3 hours exceeded for this user.")
                }), 422

            if code == "SLOT_TAKEN":
                return jsonify({
                    "success": False,
                    "error": "Conflict",
                    "message": result.get("message", "The requested slot is already held or booked.")
                }), 409

            if code == "HOLD_ACQUIRED":
                return jsonify({
                    "success": True,
                    "message": "Hold placed successfully. Confirm within 90 seconds.",
                    "slot_id": result.get("slot_id"),
                    "expires_in": result.get("expires_in", 90),
                    "slot": result
                }), 201

        except Exception as e:
            err_str = str(e)
            # Handle user foreign key violation gracefully
            if "23503" in err_str or "violates foreign key constraint" in err_str:
                return jsonify({
                    "success": False,
                    "error": "Bad Request",
                    "message": f"User '{user_id}' does not exist in the database. Available users: user_alice, user_bob, user_charlie."
                }), 400
            print(f"[WARNING] Supabase RPC failed: {e}. Falling back to mock_db.")

    # Fallback: In-memory store
    result, slot, expires_in = mock_db.place_hold(resource_name, date_str, time_slot, user_id)

    if result == "QUOTA_EXCEEDED":
        return jsonify({
            "success": False,
            "error": "Quota Exceeded",
            "message": "Daily quota limit of 3 hours exceeded for this user."
        }), 422

    if result == "SLOT_TAKEN":
        return jsonify({
            "success": False,
            "error": "Conflict",
            "message": "The requested slot is already held or booked."
        }), 409

    if result == "NOT_FOUND":
        return jsonify({
            "success": False,
            "error": "Not Found",
            "message": f"No slot found for '{resource_name}' at '{time_slot}' on '{date_str}'."
        }), 404

    return jsonify({
        "success": True,
        "message": "Hold placed successfully. Confirm within 90 seconds.",
        "slot_id": slot["slot_id"],
        "expires_in": expires_in,
        "slot": slot
    }), 201


# ----------------------------------------------------------------------------
# 3. CONFIRM ENDPOINT
# ----------------------------------------------------------------------------
@resources_bp.route("/confirm", methods=["POST"])
def confirm_booking():
    """
    POST /api/resources/confirm
    Body:
    {
        "slot_id": "...",
        "user_id": "user_alice",
        "agenda": "Team meeting",
        "collaborators": ["user_bob"]
    }

    Finalizes a held slot into 'CONFIRMED'.
    - Returns 404 if slot does not exist.
    - Returns 410 if 90-second hold expired.
    - Returns 403 if hold belongs to another user.
    - Returns 200 on success.
    """
    data = request.get_json(silent=True) or {}

    # Validate required fields
    if not data.get("slot_id") or not data.get("user_id"):
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": "Both 'slot_id' and 'user_id' are required to confirm a booking."
        }), 400

    slot_id = str(data["slot_id"]).strip()
    user_id = str(data["user_id"]).strip()
    agenda = str(data.get("agenda", "")).strip()

    collaborators = data.get("collaborators", [])
    if not isinstance(collaborators, list):
        collaborators = [str(collaborators)]

    # Supabase execution
    if supabase_client:
        try:
            slot_res = supabase_client.table("bookings").select("*").eq("id", slot_id).execute()
            if not slot_res.data:
                return jsonify({
                    "success": False,
                    "error": "Not Found",
                    "message": f"Slot with ID '{slot_id}' was not found."
                }), 404

            slot = slot_res.data[0]

            # Check if hold expired
            if slot.get("status") != "HELD":
                return jsonify({
                    "success": False,
                    "error": "Hold Expired",
                    "message": "The 90-second hold on this slot has expired and been reset to AVAILABLE."
                }), 410

            if slot.get("hold_expires_at"):
                exp_str = slot["hold_expires_at"].replace("Z", "+00:00")
                exp_dt = datetime.fromisoformat(exp_str)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if exp_dt <= datetime.now(timezone.utc):
                    # Reset back to AVAILABLE
                    supabase_client.table("bookings").update({
                        "status": "AVAILABLE",
                        "user_id": None,
                        "hold_expires_at": None,
                        "agenda": None,
                        "collaborators": []
                    }).eq("id", slot_id).execute()
                    return jsonify({
                        "success": False,
                        "error": "Hold Expired",
                        "message": "The 90-second hold on this slot has expired and been reset to AVAILABLE."
                    }), 410

            # Verify authorization
            if slot.get("user_id") and slot["user_id"] != user_id:
                return jsonify({
                    "success": False,
                    "error": "Forbidden",
                    "message": "Only the user who placed the hold can confirm this booking."
                }), 403

            # Finalize booking
            update_res = supabase_client.table("bookings").update({
                "status": "CONFIRMED",
                "hold_expires_at": None,
                "agenda": agenda,
                "collaborators": collaborators,
                "confirmed_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", slot_id).execute()

            confirmed_slot = update_res.data[0] if update_res.data else slot
            return jsonify({
                "success": True,
                "message": "Booking confirmed successfully",
                "slot": confirmed_slot
            }), 200

        except Exception as e:
            print(f"[WARNING] Supabase confirm failed: {e}. Falling back to mock_db.")

    # Fallback: In-memory store
    result, slot = mock_db.confirm_booking(slot_id, user_id, agenda, collaborators)

    if result == "NOT_FOUND":
        return jsonify({
            "success": False,
            "error": "Not Found",
            "message": f"Slot with ID '{slot_id}' was not found."
        }), 404

    if result == "HOLD_EXPIRED":
        return jsonify({
            "success": False,
            "error": "Hold Expired",
            "message": "The 90-second hold on this slot has expired and been reset to AVAILABLE."
        }), 410

    if result == "UNAUTHORIZED":
        return jsonify({
            "success": False,
            "error": "Forbidden",
            "message": "Only the user who placed the hold can confirm this booking."
        }), 403

    return jsonify({
        "success": True,
        "message": "Booking confirmed successfully",
        "slot": slot
    }), 200


# ----------------------------------------------------------------------------
# 4. CANCEL ENDPOINT
# ----------------------------------------------------------------------------
@resources_bp.route("/cancel/<slot_id>", methods=["DELETE"])
def cancel_booking(slot_id: str):
    """
    DELETE /api/resources/cancel/<slot_id>

    Releases a held slot or cancels a confirmed booking.
    Resets status back to 'AVAILABLE' and clears all booking metadata.
    """
    if not slot_id or not slot_id.strip():
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": "slot_id path parameter is required."
        }), 400

    clean_slot_id = slot_id.strip()

    # Supabase execution
    if supabase_client:
        try:
            slot_res = supabase_client.table("bookings").select("*").eq("id", clean_slot_id).execute()
            if not slot_res.data:
                return jsonify({
                    "success": False,
                    "error": "Not Found",
                    "message": f"Slot with ID '{clean_slot_id}' was not found."
                }), 404

            cancel_res = supabase_client.table("bookings").update({
                "status": "AVAILABLE",
                "user_id": None,
                "hold_expires_at": None,
                "agenda": None,
                "collaborators": [],
                "confirmed_at": None
            }).eq("id", clean_slot_id).execute()

            cancelled_slot = cancel_res.data[0] if cancel_res.data else {}
            return jsonify({
                "success": True,
                "message": "Booking or hold cancelled successfully. Slot is now AVAILABLE.",
                "slot": cancelled_slot
            }), 200

        except Exception as e:
            print(f"[WARNING] Supabase cancel failed: {e}. Falling back to mock_db.")

    # Fallback: In-memory store
    result, slot = mock_db.cancel_booking(clean_slot_id)

    if result == "NOT_FOUND":
        return jsonify({
            "success": False,
            "error": "Not Found",
            "message": f"Slot with ID '{clean_slot_id}' was not found."
        }), 404

    return jsonify({
        "success": True,
        "message": "Booking or hold cancelled successfully. Slot is now AVAILABLE.",
        "slot": slot
    }), 200
