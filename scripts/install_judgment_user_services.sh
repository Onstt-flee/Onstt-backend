#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
SOURCE_DIR="$REPO_DIR/deployment/judgment-staging"
CONFIG_ROOT=${XDG_CONFIG_HOME:-"$HOME/.config"}
STATE_ROOT=${XDG_STATE_HOME:-"$HOME/.local/state"}
UNIT_DIR="$CONFIG_ROOT/systemd/user"
PRIVATE_CONFIG_DIR="$CONFIG_ROOT/stt-api"
STATE_DIR="$STATE_ROOT/stt-api-judgment-staging"
ENV_FILE="$PRIVATE_CONFIG_DIR/judgment-staging.env"
DATABASE_FILE="$STATE_DIR/stt_data.db"

install -d -m 0750 "$UNIT_DIR" "$PRIVATE_CONFIG_DIR" "$STATE_DIR"
install -m 0644 "$SOURCE_DIR/user/judgment-vllm.service" "$UNIT_DIR/judgment-vllm.service"
install -m 0644 "$SOURCE_DIR/user/stt-api-judgment-staging.service" "$UNIT_DIR/stt-api-judgment-staging.service"

if [[ ! -e "$ENV_FILE" ]]; then
    install -m 0600 "$SOURCE_DIR/judgment-staging.env.example" "$ENV_FILE"
    echo "created disabled environment: $ENV_FILE"
else
    echo "preserved existing environment: $ENV_FILE"
fi

if [[ ! -e "$DATABASE_FILE" ]]; then
    install -m 0600 "$REPO_DIR/stt_data.db" "$DATABASE_FILE"
    echo "created isolated database snapshot: $DATABASE_FILE"
else
    echo "preserved existing staging database: $DATABASE_FILE"
fi

systemctl --user daemon-reload
systemd-analyze --user verify \
    "$UNIT_DIR/judgment-vllm.service" \
    "$UNIT_DIR/stt-api-judgment-staging.service"

echo "installed without starting or enabling services"
echo "review $ENV_FILE and keep JUDGMENT_ENABLED=false until activation"
