# Advisor Console

A web-based advisor console built with FastAPI, Vite + React, and Supabase Postgres.

## Tech Stack
* **Backend:** FastAPI, Python, SQLAlchemy 2.0, Alembic
* **Frontend:** Vite, React, TypeScript, Tailwind CSS v4, React Router
* **Database:** Supabase (PostgreSQL)

---

## Quickstart Guide

### 1. Repository Setup
```bash
git clone https://github.com/RedGla/Eskwelabs-Advisor-Console.git
cd Eskwelabs-Advisor-Console
git checkout dev
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv

# Activate Virtual Environment (Windows CMD)
.\venv\Scripts\activate

# Install Dependencies
pip install -r requirements.txt
```

Create a `.env` file inside `backend/`:
```env
DATABASE_URL="postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres"
```

Start the server:
```bash
uvicorn main:app --reload
```
Backend runs at: `http://localhost:8000/health`

### 3. Frontend Setup
In a new terminal:
```bash
cd frontend
npm install
npm run dev
```
Frontend runs at: `http://localhost:5173`

---

## Project Structure
```text
Eskwelabs-Advisor-Console/
├── backend/          # FastAPI server, SQLAlchemy models, Alembic migrations
├── frontend/         # Vite + React + TypeScript application
└── README.md
```
