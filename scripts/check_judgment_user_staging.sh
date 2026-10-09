#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
CONFIG_ROOT=${XDG_CONFIG_HOME:-"$HOME/.config"}
STATE_ROOT=${XDG_STATE_HOME:-"$HOME/.local/state"}
ENV_FILE="$CONFIG_ROOT/stt-api/judgment-staging.env"
DATABASE_FILE="$STATE_ROOT/stt-api-judgment-staging/stt_data.db"

if [[ ! -r "$ENV_FILE" ]]; then
    echo "missing private environment: $ENV_FILE" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

exec "$REPO_DIR/venv/bin/python" -B -m scripts.check_judgment_staging \
    --database "$DATABASE_FILE" "$@"
