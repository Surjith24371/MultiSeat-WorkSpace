# Division 1: Database Guide (Member 1)

## 🎯 Role & Responsibilities
As **Member 1 (Database Lead)**, you are responsible for setting up and managing the data layer using **Supabase (PostgreSQL)**. Your primary goal is to ensure zero double-allocation and enforce quota limits at the database level.

---

## 📋 Required Deliverables
You will create and manage the following items inside this `database/` directory:

1. **`schema.sql`**:
   - Table name: `bookings`
   - Fields:
     - `id` (UUID, Primary Key)
     - `resource_name` (TEXT, e.g., 'Conference Room A', 'Pod 1')
     - `booking_date` (DATE, e.g., 'YYYY-MM-DD')
     - `time_slot` (TEXT, e.g., '09:00', '10:00')
     - `status` (TEXT: `'AVAILABLE'`, `'HELD'`, `'CONFIRMED'`)
     - `user_id` (TEXT, e.g., 'user_alice')
     - `hold_expires_at` (TIMESTAMPTZ, expiration for the 90s soft-lock)
     - `agenda` (TEXT)
     - `collaborators` (JSONB array of emails)
   - **Crucial Constraint:** `UNIQUE(resource_name, booking_date, time_slot)` to prevent duplicate entries physically.

2. **`rpc_place_hold.sql`**:
   - Create a PostgreSQL stored procedure `place_hold(p_resource_name, p_booking_date, p_time_slot, p_user_id)`:
     - Check daily quota: Ensure the user has not exceeded **3 cumulative hours** (`CONFIRMED` + active `HELD`). If $\ge 3$, return `'QUOTA_EXCEEDED'`.
     - Atomic conditional update: Set `status = 'HELD'`, `hold_expires_at = NOW() + INTERVAL '90 seconds'` only if the slot is `'AVAILABLE'` or its previous hold expired (`hold_expires_at <= NOW()`).
     - If no row updated, return `'SLOT_TAKEN'`.
     - If updated, return `'HOLD_ACQUIRED'` with slot ID and expiration.

3. **`seed.py`**:
   - Python script connecting to Supabase to seed **12 resources $\times$ 8 hourly blocks (09:00 to 17:00) = 96 slots** for the current date.

---

## 🚀 Execution Steps
1. Create a project at [supabase.com](https://supabase.com).
2. Run your `schema.sql` and `rpc_place_hold.sql` in the Supabase **SQL Editor**.
3. Share the `SUPABASE_URL` and `SUPABASE_KEY` with Member 2 (Backend).
4. Run `python seed.py` to populate initial slots.
