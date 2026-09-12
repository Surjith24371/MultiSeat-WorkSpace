# Division 3: Frontend + Integration Guide (Member 3)

## 🎯 Role & Responsibilities
As **Member 3 (Frontend & Integration Lead)**, you are responsible for building the single-page application using **Vanilla HTML, CSS, and JavaScript**, plus connecting frontend user interactions to the backend API.

---

## 📋 Required Deliverables
You will build and maintain the client UI inside this `frontend/` directory:

1. **`index.html`**:
   - Header with Date Picker and **User Switcher** (`User 1: Alice`, `User 2: Bob`, `User 3: Charlie`).
   - Matrix container for the 12 resources $\times$ 8 time slots grid.
   - Modal overlay container for the 90-second hold countdown.
   - Toast alert container for notifications.

2. **CSS Files (`css/`)**:
   - `base.css`: Global layout, typography, dark/light theme, and navigation styling.
   - `grid.css`: CSS Grid layout for Matrix. Status color indicators:
     - **Green**: Available
     - **Yellow**: Held (with padlock icon or countdown badge)
     - **Red**: Booked
   - `modal.css`: 90-second animated countdown timer bar, input forms, and toast notification popups.

3. **JavaScript Files (`js/`)**:
   - `api.js`: Centralized fetch calls for the 4 endpoints (`/availability`, `/hold`, `/confirm`, `/cancel`).
     - Includes a `const USE_MOCKS = true;` toggle for offline testing.
   - `grid.js`: DOM rendering of the matrix and a non-intrusive **5-second auto-polling loop** (`setInterval`).
   - `timer.js`: Visual 90-second countdown ticker and progress bar engine. Calls auto-expire when reaching 0.
   - `modal.js`: Opens/closes hold modal, extracts agenda and collaborator tags, and triggers toasts.
   - `main.js`: Main controller wiring slot clicks $\to$ API hold $\to$ modal opening $\to$ confirmation $\to$ grid refresh.

---

## 🚀 Execution Steps
1. Start with mock data: set `USE_MOCKS = true` in `js/api.js` to build and test the entire UI offline in any browser.
2. Verify visual color-coding, slot click behavior, the 90-second timer countdown, and toast error messages (e.g., 409 Conflict, 422 Quota).
3. Once Member 2 has the backend running, set `USE_MOCKS = false` in `js/api.js` to connect live.
