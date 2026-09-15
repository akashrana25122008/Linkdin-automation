# LinkedIn AI (M1: Google authentication)

AI personal-brand platform for LinkedIn. M1 adds Google OAuth sign-in with
server-side sessions. No other integrations yet.

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

App: http://localhost:5173. Unauthenticated visits redirect to `/login`
(Continue with Google); the sidebar shows the signed-in user with logout.

## Google OAuth

Add credentials to `.env` (never commit it):

```text
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
```

The redirect URI must also be registered in the Google Cloud console.
Without credentials the app still starts; `/login` and `/api/status`
report `GOOGLE OAUTH: NOT CONFIGURED` and no login is faked.

## Mock mode (default)

No API keys needed. `AI_PROVIDER=mock`, `RESEARCH_PROVIDER=mock`,
`LINKEDIN_MODE=mock`. Mock outputs are labeled `mock` / `MOCK DATA` and the
mock LinkedIn client refuses to publish.

## Security boundaries

- Secrets live in `.env` (server-side only, never committed).
- The backend owns authorization; frontend `user_id` values are never trusted.
- Sessions are DB-backed tokens in HTTP-only `SameSite=Lax` cookies
  (`Secure` in production); nothing auth-related lives in localStorage.
- OAuth state is validated on every callback; ID tokens are verified
  against Google with an audience check.

## What is NOT implemented yet

Dashboard (M3), content generation (M4), real research (M5),
drafts/calendar/strategy (M6–M8), LinkedIn OAuth/publishing (M9–M10),
analytics/learning (M11–M12).

See `docs/ARCHITECTURE.md` for the M1 structure.
