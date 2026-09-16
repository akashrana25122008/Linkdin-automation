# LinkedIn AI

AI personal-brand platform for LinkedIn: research topics, write with AI
assistance, manage drafts, schedule on a calendar, publish to LinkedIn,
and learn from your own publishing history.

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
- Tests: `python -m pytest` (115 tests)

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

App: http://localhost:5173. Unauthenticated visits redirect to `/login`
(Continue with Google); the shell has Dashboard, Research, Studio, Drafts,
Calendar, Published (coming soon), Analytics, Learning, Strategy, and
Settings with the signed-in user and logout.

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

## LinkedIn

Connect in Settings. Without credentials the app reports
`LinkedIn OAuth: NOT CONFIGURED`; with `LINKEDIN_MODE=mock` a clearly
labeled development connection is available for UI testing.

Real publishing requires `w_member_social` in `LINKEDIN_SCOPES`
(reconnect after adding it) plus `LINKEDIN_TOKEN_ENCRYPTION_KEY`
(generate with `python -c "from cryptography.fernet import Fernet;
print(Fernet.generate_key().decode())"`). Tokens are Fernet-encrypted
server-side and never reach the frontend.

## Mock mode (default)

No API keys needed. `AI_PROVIDER=mock`, `RESEARCH_PROVIDER=mock`,
`LINKEDIN_MODE=mock`. Mock outputs are labeled `mock` / `MOCK DATA`.
Mock publishing returns `mock:` IDs and never contacts LinkedIn.

## Analytics honesty

Analytics shows application publishing data only (`APPLICATION_DATA`).
LinkedIn engagement metrics (impressions, reactions, comments, shares)
are unavailable through the member integration and are never estimated.
Learning derives patterns from your own history with explicit
minimum-data gates — never from invented performance.

## Security boundaries

- Secrets live in `.env` (server-side only, never committed).
- The backend owns authorization; frontend `user_id` values are never trusted.
- Sessions are DB-backed tokens in HTTP-only `SameSite=Lax` cookies
  (`Secure` in production); nothing auth-related lives in localStorage.
- OAuth state is validated on every callback; ID tokens are verified
  against Google with an audience check.
- See `docs/SECURITY.md` for the M13 audit and production requirements
  (HTTPS, `APP_ENV=production`, real credentials, encryption key).

See `docs/ARCHITECTURE.md` for the system structure.
