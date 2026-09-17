# LinkedIn AI — VPS deployment

> Status: NOT VERIFIED UNTIL REAL DEPLOYMENT. These are configuration files
> and instructions for a future Linux VPS. Nothing here has been executed
> against a server. Do not claim the deployment succeeded.

Target: one small Linux VPS (Debian/Ubuntu), Caddy as the HTTPS edge,
systemd supervising Uvicorn, SQLite on persistent disk, secrets in a
server-side environment file.

```
Internet
  ↓ HTTPS (:443, Caddy + automatic Let's Encrypt)
Caddy
  ├─ / ................ frontend dist/ (/var/www/linkedin-ai/dist)
  └─ /api/* ........... reverse proxy → 127.0.0.1:8000
FastAPI/Uvicorn (systemd, user `linkedin`)
  ↓
SQLite (/var/lib/linkedin-ai/data/app.db)
```

## 0. Prerequisites (on the VPS)

- Debian 12+ / Ubuntu 24.04+, root or sudo access
- A DNS A/AAAA record pointing YOUR_DOMAIN at the server
- Ports 80 + 443 reachable (Caddy needs :80 for ACME challenges)
- Python 3.10+, Node 24+, Caddy, sqlite3, git

## 1. Create the service user and layout

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin linkedin
sudo mkdir -p /opt/linkedin-ai /var/www/linkedin-ai /var/lib/linkedin-ai/data \
  /var/backups/linkedin-ai /etc/linkedin-ai
sudo chown -R linkedin:linkedin /opt/linkedin-ai /var/www/linkedin-ai \
  /var/lib/linkedin-ai /var/backups/linkedin-ai
```

## 2. Install the backend

```bash
sudo -u linkedin git clone <repo-url> /opt/linkedin-ai
cd /opt/linkedin-ai/backend
sudo -u linkedin python3 -m venv .venv
sudo -u linkedin .venv/bin/pip install --upgrade pip
sudo -u linkedin .venv/bin/pip install -r requirements.txt
```

## 3. Install the frontend build

On any machine with Node 24:

```powershell
cd frontend
$env:VITE_API_URL = "https://YOUR_DOMAIN"
npm install
npm run build
```

Copy the resulting `frontend/dist/` to `/var/www/linkedin-ai/dist` on the
server (owned by `linkedin`). Rebuild and re-copy whenever the frontend
changes — `VITE_API_URL` is baked in at build time.

## 4. Configure the environment

```bash
sudo install -o root -g linkedin -m 640 /dev/null /etc/linkedin-ai/.env
sudoedit /etc/linkedin-ai/.env   # fill from deployment/.env.production.example
```

Required production values: `APP_ENV=production`,
`FRONTEND_URL=https://YOUR_DOMAIN`, absolute `DATABASE_URL`, OAuth
credentials with callback URIs registered as
`https://YOUR_DOMAIN/api/auth/google/callback` and
`https://YOUR_DOMAIN/api/linkedin/callback`, plus
`LINKEDIN_TOKEN_ENCRYPTION_KEY`. `DOCS_ENABLED=false` keeps `/docs`
and `/redoc` disabled.

## 5. Start the backend

```bash
sudo cp deployment/linkedin-ai.service /etc/systemd/system/linkedin-ai.service
sudo systemctl daemon-reload
sudo systemctl enable --now linkedin-ai
systemctl status linkedin-ai
```

No `--reload`, no debug flags; binds loopback only; restarts on failure.

## 6. Start Caddy

Replace `YOUR_DOMAIN` in `deployment/Caddyfile`, install it as the Caddy
configuration, and reload Caddy. Certificates are automatic.

## 7. Backups

```bash
sudo apt install -y sqlite3
# Daily, e.g. systemd timer or cron as root:
DATA_FILE=/var/lib/linkedin-ai/data/app.db \
BACKUP_DIR=/var/backups/linkedin-ai \
  /opt/linkedin-ai/deployment/backup.sh
```

Keeps the newest 7 daily backups; rotation never deletes the live file.
Restore procedure is documented at the top of `backup.sh`.

## 8. Deployment verification (on the server)

```bash
curl -fsS http://127.0.0.1:8000/health            # expect HTTP 200
curl -fsS https://YOUR_DOMAIN/api/health          # expect HTTP 200 (Caddy proxies /api/* only)
curl -s -o /dev/null -w "%{http_code}\n" https://YOUR_DOMAIN/docs  # expect 404
```

Then in a browser: login → dashboard → strategy save → research → studio
generate → drafts → calendar schedule → settings LinkedIn status →
logout. Real Google/LinkedIn hops must be re-verified with real
credentials; mock mode first.

## 9. Rollback basics

- Backend: `git -C /opt/linkedin-ai log --oneline -3`, then
  `git -C /opt/linkedin-ai checkout <previous-commit>` as `linkedin`
  (or redeploy the previous tree), reinstall requirements if changed,
  `systemctl restart linkedin-ai`.
- Frontend: keep the previous `dist/` tarball; re-copy it on failure.
- Database: schema changes are additive (`create_all`); restore from a
  backup only per the procedure in `backup.sh`.

## 10. What this milestone does NOT do

No actual deployment, no real OAuth credentials, no real LinkedIn
connection or publishing, no AI/research provider setup, no database
migration, no Docker/CI. Those are separate, explicitly authorized steps.
