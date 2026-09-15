# Architecture (M6)

## Layout

```text
D:\LinkedInAI
├── backend/app        FastAPI: main, config, database, models,
│                      security, auth, ai, research, research_api,
│                      dashboard, studio, linkedin
├── backend/tests      pytest foundation (incl. auth tests)
├── frontend/src       React shell + routing + auth + backend wiring
│                      (nav, components/Topbar/CommandPalette/PageHeader/
│                      ComingSoon/StatusBadge)
├── docs               this file
├── .env.example       placeholders only
└── README.md          setup guide
```

## Request flow (M1)

```text
Vite (:5173) → GET /api/health, /api/status → FastAPI (:8000) → SQLite
Login → backend /api/auth/google/login → Google → callback →
  session cookie (HTTP-only) → /api/auth/me → SQLite
```

## Key decisions

- **Config** (`app/config.py`): pydantic-settings, `.env`-driven. Only
  `public_summary()` (no secrets) reaches `/health` and logs.
- **Database** (`app/database.py`, `app/models.py`): SQLite via SQLAlchemy.
  `users` + `sessions` (token SHA-256 hash, user FK, expiry); `UserOwnedMixin`
  defines the `user_id` FK pattern every future user-owned table must follow.
- **Auth** (`app/auth.py`, `app/security.py`): Google OAuth code flow with
  state-cookie CSRF check; ID token verified against Google server-side;
  user found/created by `google_subject_id`. Sessions are DB-backed, 7-day
  expiry, HTTP-only `SameSite=Lax` cookies (`Secure` in production).
  `get_current_user()` resolves identity from the session; frontend `user_id`
  is never trusted. Without Google credentials the app starts and every
  OAuth route reports `NOT CONFIGURED`.
- **AI** (`app/ai.py`): `AIProvider` protocol + working `MockAIProvider`.
  Named real providers raise `NOT CONFIGURED` instead of fabricating output.
- **Research** (`app/research.py`): same pattern; mock items carry
  `"mock": True` and no fake URLs.
- **LinkedIn** (`app/linkedin.py`): mock client only. `publish()` raises —
  mock mode can never publish or claim success.
- **Status honesty**: `/api/status` reports `MOCK` / `NOT CONFIGURED`;
  nothing claims real integrations.
- **Research** (`app/research.py`, `app/research_api.py`,
  `src/pages/Research.tsx`): transient provider search with heuristic
  scoring note; `research_items` persists only explicitly saved items
  (status saved/ignored), 404 for missing and foreign rows. Mock returns 3
  query-derived items with no outlet names, URLs, or dates. Angles go
  through the AI provider. Discover/Saved tabs; “Use in Content Studio”
  saves (if needed) and hands the id to `/studio`, which prefills
  topic/notes from the owned item.
- **Studio** (`app/studio.py`, `src/pages/Studio.tsx`): user-owned content
  CRUD (`body` + `content_type` on `content_items`; studio writes only
  idea/draft/approved), one `POST /api/studio/ai` for generate + 10 rewrite
  actions through the configured provider, and `POST /api/studio/review`
  with deterministic heuristic dimensions (factual verification never
  claimed). Missing and foreign items both return 404. The 3-panel UI
  previews AI output before Apply, never overwrites silently, and guards
  unsaved work with `useBlocker` + `beforeunload`. Opens `/studio?id=`
  deep links from Drafts.
- **Drafts** (`src/pages/Drafts.tsx`, studio item endpoints): reuses
  `content_items` — list now carries preview + created_at, plus
  duplicate/delete endpoints (404 for foreign rows). Client-side
  search/status/type filters over the backend-ordered list; inline
  confirm delete; per-row status select validated server-side.
- **Dashboard** (`app/dashboard.py`, `src/pages/Overview.tsx`): one
  authenticated `GET /api/dashboard` powers the Overview — user-scoped
  `content_items` pipeline counts + upcoming, mock-AI brief/recommendations
  (labeled), mock research signals, and a metrics-free `not_connected`
  performance state. Frontend renders skeleton/empty/error states with no
  fabricated data.
- **Shell** (`src/App.tsx`, `src/nav.ts`, `src/components/`): 9-route
  collapsible sidebar (drawer on mobile, preference in localStorage),
  topbar with route title, ⌘K command menu, honest empty notifications,
  real LinkedIn flag from `/api/status`, and the M1 user menu. Unbuilt
  pages share one honest `ComingSoon` placeholder. Motion is CSS-only and
  globally disabled under `prefers-reduced-motion`.

## M7+ entry points

- Real AI → `app/ai.py::get_ai_provider` (studio needs no changes)
- Real research → `app/research.py::get_research_provider` (API needs no changes)
- LinkedIn OAuth/publish → `app/linkedin.py`
