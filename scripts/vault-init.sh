#!/usr/bin/env bash
# Knowledge Lab Vault Init — startup integrity check + .env recovery
# Run before starting the server

set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VAULT_DIR="$ROOT_DIR/vault"
META_DIR="$VAULT_DIR/.vault-meta"

log() { echo "[$(date +%H:%M:%S)] vault-init: $*"; }

# 1. Ensure .env exists (recover from template)
if [[ ! -f "$ROOT_DIR/.env" ]]; then
    log "WARNING: .env not found — recovering from .env.example..."
    if [[ -f "$ROOT_DIR/.env.example" ]]; then
        cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
        log "Created .env from template. You may need to add your API key."
    else
        echo 'LLM_API_KEY=sk-your-key-here' > "$ROOT_DIR/.env"
        echo 'LLM_PROVIDER=deepseek' >> "$ROOT_DIR/.env"
        log "Created minimal .env — add your API key."
    fi
fi

# 2. Create missing directories
for d in \
    "$VAULT_DIR/00_学习笔记/_active" \
    "$VAULT_DIR/00_学习笔记/_archive" \
    "$VAULT_DIR/00_学习笔记/_drafts" \
    "$VAULT_DIR/01_原始资料/url-imports" \
    "$VAULT_DIR/01_原始资料/whisper" \
    "$VAULT_DIR/01_原始资料/skill-decompositions" \
    "$VAULT_DIR/02_结构化输出/summaries" \
    "$VAULT_DIR/02_结构化输出/flashcards" \
    "$VAULT_DIR/03_附件/images" \
    "$VAULT_DIR/04_索引" \
    "$VAULT_DIR/_backup/snapshots" \
    "$VAULT_DIR/_backup/daily" \
    "$META_DIR/integrity" \
    "$ROOT_DIR/logs"; do
    mkdir -p "$d"
done

# 3. Count notes
NOTE_COUNT=$(find "$VAULT_DIR/00_学习笔记" -name '*.md' -not -name '模板_*' 2>/dev/null | wc -l)
log "Vault ready · $NOTE_COUNT notes · $VAULT_DIR"

# 4. Write integrity snapshot
INTEGRITY_FILE="$META_DIR/integrity/$(date +%Y%m%d_%H%M%S).json"
python3 -c "
import os, json, hashlib, sys
va = sys.argv[1]
out = sys.argv[2]
h = {}
for r, _, fs in os.walk(va):
    for f in fs:
        if f.endswith('.md') and '_backup' not in r and '.vault-meta' not in r:
            p = os.path.join(r, f)
            h[os.path.relpath(p, va)] = hashlib.sha256(open(p,'rb').read()).hexdigest()[:16]
json.dump({'timestamp': '$(date -Iseconds)', 'note_count': len([k for k in h if '模板_' not in k]), 'files': h}, open(out,'w'), indent=2)
print(f'Integrity snapshot: {len(h)} files')
" "$VAULT_DIR" "$INTEGRITY_FILE" 2>/dev/null || log "integrity snapshot skipped (python not available)"

log "Init complete."
