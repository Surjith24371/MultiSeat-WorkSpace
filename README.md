# Multi-Seat Workspace & Resource Booking Engine

A collaborative, real-time resource reservation system engineered for co-working spaces, conference rooms, and computing clusters. Features strict isolation against double-allocation, a **90-second soft-lock TTL ("Hold & Confirm")**, and a **3-hour daily user quota**.

---

## 👥 Team Breakdown & Branch Strategy

This project is divided into three isolated folders so each team member can work independently on GitHub:

| Folder | Assigned Member | Responsibilities | Git Branch |
| :--- | :--- | :--- | :--- |
| **`database/`** | **Member 1 (Database Lead)** | Supabase schema, `place_hold` atomic stored procedure, data seeder. | `feat/database` |
| **`backend/`** | **Member 2 (API Lead)** | Flask REST API (`/availability`, `/hold`, `/confirm`, `/cancel`), Supabase client, concurrency tests. | `feat/backend` |
| **`frontend/`** | **Member 3 (UI & Integration Lead)** | Vanilla HTML/CSS/JS, visual matrix, 90-second countdown modal, 5s auto-polling, end-to-end integration. | `feat/frontend` |

Refer to each folder's individual README for detailed execution guides:
- [database/README.md](file:///c:/Users/SURJITH%20S/OneDrive/Desktop/MultiSeat%20WorkSpace/database/README.md)
- [backend/README.md](file:///c:/Users/SURJITH%20S/OneDrive/Desktop/MultiSeat%20WorkSpace/backend/README.md)
- [frontend/README.md](file:///c:/Users/SURJITH%20S/OneDrive/Desktop/MultiSeat%20WorkSpace/frontend/README.md)

---

## 🚀 GitHub Setup & Workflow

1. Initialize Git and commit this scaffold:
   ```bash
   git init
   git add .
   git commit -m "Scaffold project structure with member guides"
   git remote add origin <your-github-repo-url>
   git branch -M main
   git push -u origin main
   ```

2. Each member creates their own branch:
   ```bash
   # Member 1:
   git checkout -b feat/database

   # Member 2:
   git checkout -b feat/backend

   # Member 3:
   git checkout -b feat/frontend
   ```

3. Develop independently inside your assigned directory and push feature branches to GitHub!
