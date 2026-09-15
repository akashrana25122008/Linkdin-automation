# LinkedIn AI (M0 foundation)

AI personal-brand platform for LinkedIn. M0 establishes the runnable
foundation only: backend + frontend + mock providers. No real integrations yet.

## Prerequisites

- Python 3.10+
- Node 24+ / npm 11+

## Setup

```powershell
Copy-Item .env.example .env
```

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

- Health: http://localhost:8000/health
- Docs: http://localhost:8000/docs

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

App: http://localhost:5173. The Overview page reads the backend
`/api/health` endpoint (override with `VITE_API_URL`).

## Mock mode (default)

No API keys needed. `AI_PROVIDER=mock`, `RESEARCH_PROVIDER=mock`,
`LINKEDIN_MODE=mock`. Mock outputs are labeled `mock` / `MOCK DATA` and the
mock LinkedIn client refuses to publish.

## Security boundaries

- Secrets live in `.env` (server-side only, never committed).
- The backend owns authorization; frontend `user_id` values are never trusted.
- Google OAuth lands in M1; `get_current_user()` returns 401 until then.

## What is NOT implemented yet

Google OAuth (M1), dashboard (M3), content generation (M4), real research
(M5), drafts/calendar/strategy (M6–M8), LinkedIn OAuth/publishing (M9–M10),
analytics/learning (M11–M12).

See `docs/ARCHITECTURE.md` for the M0 structure.
