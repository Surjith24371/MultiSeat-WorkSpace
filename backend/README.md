# Division 2: Backend API Guide (Member 2)

## 🎯 Role & Responsibilities
As **Member 2 (Backend API Lead)**, you are responsible for building the **Python Flask REST API** connecting to Supabase. Your code will handle HTTP requests, serialize responses, and return strict HTTP status codes.

---

## 📋 Required Deliverables
You will build and maintain the backend inside this `backend/` directory:

1. **`requirements.txt`**:
   - `flask`, `flask-cors`, `supabase`, `python-dotenv`, `requests`

2. **`config.py`**:
   - Load environment variables (`SUPABASE_URL`, `SUPABASE_KEY`, `FLASK_PORT`).
   - Initialize the `supabase` client.

3. **`routes/resources.py` (Core Endpoints)**:
   - `GET /api/resources/availability?date=YYYY-MM-DD`
     - Returns all slots for that date.
     - Normalize expired holds (`status == 'HELD'` and `hold_expires_at <= NOW()`) to return as `'AVAILABLE'`.
   - `POST /api/resources/hold`
     - Body: `{ resource_name, date, time_slot, user_id }`
     - Calls Supabase `rpc('place_hold', ...)`:
       - Success $\to$ **`HTTP 201 Created`** (`{ slot_id, expires_in: 90 }`)
       - Slot taken $\to$ **`HTTP 409 Conflict`**
       - Quota exceeded $\to$ **`HTTP 422 Unprocessable Entity`**
   - `POST /api/resources/confirm`
     - Body: `{ slot_id, user_id, agenda, collaborators }`
     - Checks if hold is still active (`hold_expires_at > NOW()`).
     - Updates status to `'CONFIRMED'` $\to$ **`HTTP 200 OK`**.
     - If hold has expired $\to$ **`HTTP 410 Gone`** (or `409 Conflict`).
   - `DELETE /api/resources/cancel/<slot_id>`
     - Resets slot back to `'AVAILABLE'` $\to$ **`HTTP 200 OK`**.

4. **`tests/test_concurrency.py`**:
   - Multi-threaded script firing two simultaneous hold requests for the same slot to verify that one receives `201` and the other receives `409`.

---

## 🚀 Execution Steps
1. Create a virtual environment and install dependencies:
   ```bash
   pip install flask flask-cors supabase python-dotenv requests
   ```
2. Configure your `.env` with Supabase keys provided by Member 1.
3. Start the Flask server:
   ```bash
   python app.py
   ```
   *Runs at `http://localhost:5000`.*
