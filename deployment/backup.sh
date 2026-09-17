#!/usr/bin/env bash
# LinkedIn AI — SQLite backup routine (Linux VPS).
#
# Uses the SQLite online backup API via the sqlite3 CLI, which is safe
# against a live database (unlike a raw file copy). Keeps the newest
# KEEP_DAILY daily backups; never touches the live database file.
#
# Install:  apt install -y sqlite3
# Schedule: daily via systemd timer or cron (see deployment/README.md).
#
# Restore procedure (documented, destructive — read README first):
#   1. systemctl stop linkedin-ai
#   2. cp /var/lib/linkedin-ai/data/app.db /var/lib/linkedin-ai/data/app.db.before-restore
#   3. cp <chosen-backup> /var/lib/linkedin-ai/data/app.db
#   4. chown linkedin:linkedin /var/lib/linkedin-ai/data/app.db
#   5. systemctl start linkedin-ai
#   6. curl -fsS http://127.0.0.1:8000/health
set -euo pipefail

DATA_FILE="${DATA_FILE:-/var/lib/linkedin-ai/data/app.db}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/linkedin-ai}"
KEEP_DAILY="${KEEP_DAILY:-7}"

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "backup: sqlite3 CLI not found (apt install -y sqlite3)" >&2
  exit 1
fi
if [ ! -f "$DATA_FILE" ]; then
  echo "backup: live database not found at $DATA_FILE" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$BACKUP_DIR/app-$STAMP.db"

sqlite3 "$DATA_FILE" ".backup '$DEST'"
chmod 600 "$DEST"
echo "backup: wrote $DEST"

# Rotation: keep the newest $KEEP_DAILY backups, delete older ones only.
# The glob always matches at least $DEST (created above), so `ls` cannot
# fail here; `tail` prints nothing when there is nothing to rotate.
# shellcheck disable=SC2012
ls -1t "$BACKUP_DIR"/app-*.db | tail -n +"$((KEEP_DAILY + 1))" | while IFS= read -r old; do
  rm -f "$old"
  echo "backup: rotated $old"
done
