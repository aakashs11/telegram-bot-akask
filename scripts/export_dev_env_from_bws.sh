#!/usr/bin/env bash
# One-time export: write .env and service_account.json from Bitwarden Secrets Manager.
# After this, developers run ./start_devtest.sh normally (no bws required).
#
# Usage:
#   export BWS_ACCESS_TOKEN='<machine-account-token>'
#   export BWS_PROJECT_ID='33403fe4-c585-4a77-ace7-b4510082ad50'   # or your project id
#   ./scripts/export_dev_env_from_bws.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$PATH:$HOME/.local/bin"
PROJECT_ID="${BWS_PROJECT_ID:-}"

if [[ -z "${BWS_ACCESS_TOKEN:-}" ]]; then
  echo "❌ Set BWS_ACCESS_TOKEN (machine account with read access to the dev project)."
  exit 1
fi

if [[ -z "$PROJECT_ID" ]]; then
  echo "❌ Set BWS_PROJECT_ID (from: bws project list --output table)"
  exit 1
fi

if ! command -v bws >/dev/null 2>&1; then
  echo "❌ bws not found. Install: curl -fsSL https://bws.bitwarden.com/install | sh"
  exit 1
fi

cd "$ROOT"

echo "📥 Exporting env vars to .env ..."
bws secret list "$PROJECT_ID" --output env | grep -v '^SERVICE_ACCOUNT_JSON_B64=' > .env
chmod 600 .env

if bws secret list "$PROJECT_ID" --output env | grep -q '^SERVICE_ACCOUNT_JSON_B64='; then
  echo "📥 Writing service_account.json ..."
  bws secret list "$PROJECT_ID" --output env | python3 -c "
import sys
for line in sys.stdin:
    if line.startswith('SERVICE_ACCOUNT_JSON_B64='):
        val = line.split('=', 1)[1].strip().strip('\"')
        import base64, pathlib
        pathlib.Path('service_account.json').write_bytes(base64.b64decode(val))
        break
"
  chmod 600 service_account.json
else
  echo "⚠️  SERVICE_ACCOUNT_JSON_B64 not in project — service_account.json not created."
fi

echo ""
echo "✅ Wrote:"
echo "   $ROOT/.env"
echo "   $ROOT/service_account.json (if secret exists)"
echo ""
echo "Confirm SHEET_ID is present:"
grep -E '^SHEET_ID=' .env || echo "   ⚠️  Missing SHEET_ID — add manually."
