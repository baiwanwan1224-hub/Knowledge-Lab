#!/usr/bin/env bash
# Knowledge Lab Vault Backup — run before server start or via cron
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VAULT_DIR="$ROOT_DIR/vault"
BACKUP_DIR="$VAULT_DIR/_backup"
SNAP_DIR="$BACKUP_DIR/snapshots"
DAILY_DIR="$BACKUP_DIR/daily"
TS=$(date +%Y%m%d_%H%M%S)
TODAY=$(date +%Y%m%d)

mkdir -p "$SNAP_DIR" "$DAILY_DIR"
log() { echo "[$(date +%H:%M:%S)] backup: $*"; }

# ── Snapshot ──
log "Creating snapshot..."
tar -cf "$SNAP_DIR/snap-$TS.tar" \
    --exclude='_backup' \
    --exclude='.vault-meta/.lock' \
    -C "$VAULT_DIR" . 2>/dev/null || log "WARN: snapshot failed (non-fatal)"

# Keep last 30 snapshots
ls -1t "$SNAP_DIR"/snap-*.tar 2>/dev/null | tail -n +31 | xargs -r rm -f

# ── Daily archive ──
DAILY="$DAILY_DIR/vault-$TODAY.tar.gz"
if [[ ! -f "$DAILY" ]]; then
    log "Creating daily archive..."
    tar -czf "$DAILY" \
        --exclude='_backup' \
        --exclude='.vault-meta/.lock' \
        -C "$VAULT_DIR" . 2>/dev/null
    log "Daily: $DAILY"
    # Clean 30+ days
    find "$DAILY_DIR" -name 'vault-*.tar.gz' -mtime +30 -delete 2>/dev/null
else
    log "Daily already exists, skip."
fi

log "Backup complete."
