#!/bin/sh
# ─────────────────────────────────────────────────────────────────────────────
# backup.sh – Konsistentes SQLite- + Upload-Backup (Prod-Backup-Container)
#
# Läuft stündlich im backup-Service von docker-compose.prod.yml.
#
# Konsistenz: KEIN `cp` der Live-DB. Unter WAL hat die DB begleitende
# -wal/-shm-Dateien; ein simples cp kann eine inkonsistente/korrupte Kopie
# ziehen. Stattdessen die Online-Backup-API von SQLite über `.backup` — die
# ist auch bei laufenden Schreibern konsistent.
#
# WICHTIG: Das /data-Volume muss READ-WRITE gemountet sein. SQLite kann eine
# WAL-DB nicht von einem read-only-Mount öffnen (das -shm braucht Schreib-
# zugriff) — empirisch verifiziert 2026-07-13: bei :ro schlägt `.backup` mit
# "unable to open database file" fehl. `.backup` verändert den DB-INHALT nicht,
# nur die WAL-/shm-Koordination.
#
# Zwei Stufen (bounded Disk trotz stündlichem Lauf):
#   • hourly/  – stündlicher DB-Snapshot, Retention HOURLY_RETENTION_HOURS (48h)
#   • daily/   – täglicher DB-Snapshot + Upload-Tar zur DAILY_HOUR,
#                Retention BACKUP_RETENTION_DAYS (30 Tage, RA-Schatz-Default)
#
# RA-MICRO ist read-only und wird hier NICHT angefasst — nur die SQLite-DB.
# ─────────────────────────────────────────────────────────────────────────────
set -e

DB_PATH="${DB_PATH:-/data/unfallakten.db}"
UPLOADS_DIR="${UPLOADS_DIR:-/uploads}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
HOURLY_RETENTION_HOURS="${BACKUP_HOURLY_RETENTION_HOURS:-48}"
DAILY_HOUR="${BACKUP_DAILY_HOUR:-02}"

STAMP="$(date +%Y%m%d_%H%M%S)"
HOUR="$(date +%H)"
HOURLY_DIR="${BACKUP_DIR}/hourly"
DAILY_DIR="${BACKUP_DIR}/daily"

log() { echo "[backup] $(date +%Y-%m-%dT%H:%M:%S) $*"; }

mkdir -p "$HOURLY_DIR" "$DAILY_DIR"

if [ ! -f "$DB_PATH" ]; then
  log "FEHLER: DB nicht gefunden: $DB_PATH"
  exit 1
fi

# ── Stündlicher DB-Snapshot (online-konsistent via .backup) ──────────────────
HOURLY_DB="${HOURLY_DIR}/unfallakten_${STAMP}.db"
log "Sichere DB -> ${HOURLY_DB}"
sqlite3 "$DB_PATH" ".backup '${HOURLY_DB}'"
log "DB-Snapshot fertig ($(du -h "$HOURLY_DB" | cut -f1))"

# ── Täglich: DB-Snapshot + Upload-Archiv ─────────────────────────────────────
if [ "$HOUR" = "$DAILY_HOUR" ]; then
  DAILY_DB="${DAILY_DIR}/unfallakten_${STAMP}.db"
  log "Täglicher DB-Snapshot -> ${DAILY_DB}"
  sqlite3 "$DB_PATH" ".backup '${DAILY_DB}'"

  if [ -d "$UPLOADS_DIR" ]; then
    UPLOADS_TAR="${DAILY_DIR}/uploads_${STAMP}.tar.gz"
    log "Sichere Uploads -> ${UPLOADS_TAR}"
    tar -czf "$UPLOADS_TAR" -C "$UPLOADS_DIR" . 2>/dev/null || \
      log "WARNUNG: Upload-Archiv unvollständig"
  else
    log "Uploads-Verzeichnis fehlt ($UPLOADS_DIR) — überspringe"
  fi
fi

# ── Retention ────────────────────────────────────────────────────────────────
# Stündliche Snapshots: älter als HOURLY_RETENTION_HOURS (in Minuten) löschen.
HOURLY_MIN=$((HOURLY_RETENTION_HOURS * 60))
find "$HOURLY_DIR" -type f -name "unfallakten_*.db" -mmin "+${HOURLY_MIN}" -print -delete \
  | sed 's/^/[backup] entferne (hourly) /' || true

# Tägliche Snapshots + Upload-Tars: älter als RETENTION_DAYS löschen.
find "$DAILY_DIR" -type f \( -name "unfallakten_*.db" -o -name "uploads_*.tar.gz" \) \
  -mtime "+${RETENTION_DAYS}" -print -delete \
  | sed 's/^/[backup] entferne (daily) /' || true

log "Backup-Lauf abgeschlossen."
