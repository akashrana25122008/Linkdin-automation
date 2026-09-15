# Architecture (M0)

## Layout

```text
D:\LinkedInAI
├── backend/app        FastAPI: main, config, database, models,
│                      security, ai, research, linkedin
├── backend/tests      pytest foundation
├── frontend/src       React shell + routing + backend health wiring
├── docs               this file
├── .env.example       placeholders only
└── README.md          setup guide
```

## Request flow (M0)

```text
Vite (:5173) → GET /api/health, /api/status → FastAPI (:8000) → SQLite
```

## Key decisions

- **Config** (`app/config.py`): pydantic-settings, `.env`-driven. Only
  `public_summary()` (no secrets) reaches `/health` and logs.
- **Database** (`app/database.py`, `app/models.py`): SQLite via SQLAlchemy.
  Only the `users` table exists; `UserOwnedMixin` defines the `user_id` FK
  pattern every future user-owned table must follow.
- **Auth boundary** (`app/security.py`): `get_current_user()` raises 401
  until M1 Google OAuth + server sessions exist. `assert_user_scope()`
  enforces backend-derived ownership checks.
- **AI** (`app/ai.py`): `AIProvider` protocol + working `MockAIProvider`.
  Named real providers raise `NOT CONFIGURED` instead of fabricating output.
- **Research** (`app/research.py`): same pattern; mock items carry
  `"mock": True` and no fake URLs.
- **LinkedIn** (`app/linkedin.py`): mock client only. `publish()` raises —
  mock mode can never publish or claim success.
- **Status honesty**: `/api/status` reports `MOCK` / `NOT CONFIGURED`;
  nothing claims real integrations.

## M1 entry points

- Google OAuth → `app/security.py`, `app/models.py::User`
- Real AI → `app/ai.py::get_ai_provider`
- Real research → `app/research.py::get_research_provider`
- LinkedIn OAuth/publish → `app/linkedin.py`
