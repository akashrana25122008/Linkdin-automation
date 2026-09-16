# Architecture (M11)

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
  confirm delete; per-row status select validated server-side
  (disabled for scheduled rows); Schedule action for approved rows.
- **Calendar** (`src/pages/Calendar.tsx`, `src/components/ScheduleModal.tsx`,
  `src/time.ts`): month grid (42 cells, Sunday start) + week view with a
  mobile agenda fallback; bounded `GET /api/studio/scheduled` ranges with
  encoded ISO params; local scheduling only (never LinkedIn). Scheduling
  stores UTC + IANA zone (`scheduled_at`/`scheduled_tz` on `content_items`,
  approval gate + past-time + tz validation server-side); one modal drives
  schedule/reschedule from Calendar, Studio, and Drafts; Intl-based
  zone conversion, no date library.
- **Dashboard** (`app/dashboard.py`, `src/pages/Overview.tsx`): one
  authenticated `GET /api/dashboard` powers the Overview — user-scoped
  `content_items` pipeline counts + upcoming, mock-AI brief/recommendations
  (labeled), mock research signals, and a metrics-free `not_connected`
  performance state. Frontend renders skeleton/empty/error states with no
  fabricated data.
- **Strategy** (`app/strategy.py`, `src/pages/Strategy.tsx`): one
  `user_strategies` row per user (scalars + JSON list columns); GET returns
  defaults without creating a row, PUT merges and validates (frequency,
  days, HH:MM times, content types, IANA timezone, length caps).
  `get_user_strategy()` + `strategy_context_text()` are the user-scoped
  context source for future AI integration (no agents wired yet).
  Form has 6 anchored sections, chip inputs, day/content-type toggles,
  explicit Save, and `useBlocker` + `beforeunload` guards.
- **LinkedIn OAuth** (`app/linkedin_oauth.py`, `src/pages/Settings.tsx`):
  Google session owns the account; LinkedIn OAuth authorizes the member
  account. DB-backed single-use 10-minute states bound to the session user;
  code exchanged + userinfo fetched server-side via httpx; tokens
  Fernet-encrypted at rest (key from `LINKEDIN_TOKEN_ENCRYPTION_KEY`,
  missing key refuses real connections); one `linkedin_accounts` row per
  user, status exposes metadata only. Mock mode offers a clearly-fake local
  connection for UI testing and never calls LinkedIn.
- **LinkedIn publishing** (`app/publishing.py`, studio publish endpoint,
  Studio/Drafts publish UI): text-only ugcPosts with server-side decrypted
  token and `w_member_social` scope check; published only on HTTP 201 with
  `X-RestLi-Id`, persisted as status/`linkedin_post_id`/`published_at`;
  failures keep `failed` + `publish_error`, timeouts leave status untouched;
  already-published blocks repeat posts. Mock mode returns `mock:` IDs and
  never calls LinkedIn.
- **Analytics** (`app/analytics.py`, `src/pages/Analytics.tsx`): application
  publishing data only (source `APPLICATION_DATA`) — no new tables, no
  LinkedIn calls. LinkedIn engagement is NOT AVAILABLE through the member
  integration (OIDC + `w_member_social`; ugcPosts returns an ID only) and is
  reported `unavailable`, never estimated. Overview (counts, frequency,
  buckets, type distribution) + posts history with 7/30/90/all ranges;
  strategy timezone respected. Overview Performance panel shows real
  published totals with an analytics link.
- **Shell** (`src/App.tsx`, `src/nav.ts`, `src/components/`): 9-route
  collapsible sidebar (drawer on mobile, preference in localStorage),
  topbar with route title, ⌘K command menu, honest empty notifications,
  real LinkedIn flag from `/api/status`, and the M1 user menu. Unbuilt
  pages share one honest `ComingSoon` placeholder. Motion is CSS-only and
  globally disabled under `prefers-reduced-motion`.

## M12+ entry points

- Real AI → `app/ai.py::get_ai_provider` (studio needs no changes)
- Real research → `app/research.py::get_research_provider` (API needs no changes)
- Learning loop → consumes `/api/analytics` application data (M12)
