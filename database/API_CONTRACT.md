# Database & API Integration Contract

**Document Version:** 1.0  
**Target Audience:** Member 2 (Backend API Lead), Member 3 (Frontend & Integration Lead)  
**Author:** Member 1 (Database Lead)  
**Database Engine:** Supabase (PostgreSQL 15+)

---

## 1. Supabase Environment Configuration

Member 2 must configure their `backend/.env` with the credentials provided by Member 1:

```ini
SUPABASE_URL=https://<your-project-id>.supabase.co
SUPABASE_KEY=<your-service-role-or-anon-key>
FLASK_PORT=5000
```

Initialize the Supabase client in `backend/config.py`:
```python
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
```

---

## 2. Endpoint 1: Query Availability Matrix

### HTTP Route
`GET /api/resources/availability?date=YYYY-MM-DD`

### Underlying Database Entity
Query the real-time normalized view: **`v_resource_availability`**  
*(Note: Do NOT query `bookings` directly. The view dynamically normalizes expired holds to `'AVAILABLE'` with zero latency).*

### Python Supabase Snippet
```python
# Query all 96 slots for the requested date
response = supabase.table("v_resource_availability") \
    .select("*") \
    .eq("booking_date", request_date) \
    .order("time_slot") \
    .execute()

slots = response.data  # Returns list of 96 slot objects
```

### Response Object Fields
Each slot object in the array contains:
```json
{
  "id": "c1f7a0c8-4e89-4e0c-9a4f-7f8e3a2b1c0d",
  "resource_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
  "resource_name": "Conference Room A",
  "booking_date": "2026-09-15",
  "time_slot": "09:00",
  "status": "AVAILABLE",
  "user_id": null,
  "hold_expires_at": null,
  "agenda": null,
  "collaborators": []
}
```

* **Color-Coding Map for Member 3:**
  - `status == 'AVAILABLE'` $\to$ **Green**
  - `status == 'HELD'` $\to$ **Yellow** (countdown timer active)
  - `status == 'CONFIRMED'` $\to$ **Red** (booked)

---

## 3. Endpoint 2: Place 90-Second Soft Hold

### HTTP Route
`POST /api/resources/hold`

### Request Body
```json
{
  "resource_name": "Conference Room A",
  "date": "2026-09-15",
  "time_slot": "09:00",
  "user_id": "user_alice"
}
```

### Python Supabase Snippet
```python
data = request.get_json()
payload = {
    "p_resource_name": data["resource_name"],
    "p_booking_date": data["date"],
    "p_time_slot": data["time_slot"],
    "p_user_id": data["user_id"]
}

rpc_response = supabase.rpc("place_hold", payload).execute()
result = rpc_response.data
```

### Database Return Handling & HTTP Mapping

| DB `code` | Success? | Backend HTTP Status | Backend Response JSON |
| :--- | :--- | :--- | :--- |
| **`HOLD_ACQUIRED`** | `true` | **`HTTP 201 Created`** | `{"slot_id": result["slot_id"], "expires_in": 90, "expires_at": result["expires_at"]}` |
| **`SLOT_TAKEN`** | `false` | **`HTTP 409 Conflict`** | `{"error": "Slot taken", "message": result["message"]}` |
| **`QUOTA_EXCEEDED`**| `false` | **`HTTP 422 Unprocessable`**| `{"error": "Quota exceeded", "message": result["message"]}` |

---

## 4. Endpoint 3: Confirm Hold into Permanent Reservation

### HTTP Route
`POST /api/resources/confirm`

### Request Body
```json
{
  "slot_id": "c1f7a0c8-4e89-4e0c-9a4f-7f8e3a2b1c0d",
  "user_id": "user_alice",
  "agenda": "Q3 Planning Meeting",
  "collaborators": ["bob@workspace.local", "charlie@workspace.local"]
}
```

### Python Supabase Snippet
```python
data = request.get_json()
payload = {
    "p_slot_id": data["slot_id"],
    "p_user_id": data["user_id"],
    "p_agenda": data.get("agenda", ""),
    "p_collaborators": data.get("collaborators", [])
}

rpc_response = supabase.rpc("confirm_hold", payload).execute()
result = rpc_response.data
```

### Database Return Handling & HTTP Mapping

| DB `code` | Success? | Backend HTTP Status | Backend Response JSON |
| :--- | :--- | :--- | :--- |
| **`CONFIRMED`** | `true` | **`HTTP 200 OK`** | `{"success": true, "slot_id": result["slot_id"], "message": "Booking confirmed"}` |
| **`HOLD_EXPIRED`** | `false` | **`HTTP 410 Gone`** (or `409 Conflict`)| `{"error": "Hold expired", "message": result["message"]}` |

---

## 5. Endpoint 4: Cancel Reservation / Hold

### HTTP Route
`DELETE /api/resources/cancel/<slot_id>`

### Python Supabase Snippet
```python
payload = {
    "p_slot_id": slot_id,
    "p_user_id": request.args.get("user_id")  # Optional user ownership verification
}

rpc_response = supabase.rpc("cancel_booking", payload).execute()
result = rpc_response.data
```

### Database Return Handling & HTTP Mapping

| DB `code` | Success? | Backend HTTP Status | Backend Response JSON |
| :--- | :--- | :--- | :--- |
| **`CANCELLED`** | `true` | **`HTTP 200 OK`** | `{"success": true, "message": "Booking cancelled and slot released"}` |
| **`NOT_FOUND_OR_UNAUTHORIZED`** | `false` | **`HTTP 404 Not Found`** | `{"error": "Not found", "message": result["message"]}` |

---

## 6. Seeded Test Data Quick Reference

### Seeded Mock Users (Matching Member 3 User Switcher)
* `user_alice` (`Alice Smith`, `alice@workspace.local`)
* `user_bob` (`Bob Jones`, `bob@workspace.local`)
* `user_charlie` (`Charlie Brown`, `charlie@workspace.local`)

### 12 Seeded Workspace Resources
1. **Conference Rooms (Capacity 6–12):**
   - `Conference Room A`
   - `Conference Room B`
   - `Executive Boardroom`
   - `Ideation Studio`
2. **Workstation Pods (Capacity 1–4):**
   - `Quiet Pod 1`
   - `Quiet Pod 2`
   - `Team Pod 3`
   - `Team Pod 4`
3. **Desks (Capacity 1):**
   - `Standing Desk 1`
   - `Standing Desk 2`
   - `Focus Desk 3`
   - `Focus Desk 4`

### Fixed Hourly Blocks
* `09:00`, `10:00`, `11:00`, `12:00`, `13:00`, `14:00`, `15:00`, `16:00`
* Total: **12 resources $\times$ 8 hourly blocks = 96 slots per day**.

---

## 7. Concurrency & Reliability Guarantees
* **Zero Double-Allocation:** Enforced by PostgreSQL unique index `uq_resource_date_slot` and atomic conditional updates. Competing requests return `SLOT_TAKEN` with mathematical certainty.
* **Advisory Lock Quota Protection:** `pg_advisory_xact_lock(hashtext(user_id || booking_date))` prevents parallel requests from the same user from exceeding the cumulative 3-hour daily quota.
* **Automatic TTL Cleanup:** Dynamic view `v_resource_availability` treats slots where `hold_expires_at <= NOW()` as `AVAILABLE` immediately, eliminating the need for cron daemons.
