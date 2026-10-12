#!/usr/bin/env bash
set -euo pipefail

repo_dir="${STT_API_DIR:-$HOME/stt_api}"
source_dir="$repo_dir/deployment/judgment-pi5"
unit_dir="$HOME/.config/systemd/user"
env_dir="$HOME/.config/stt-api"

test -d "$source_dir/user"
mkdir -p "$unit_dir" "$env_dir"
install -m 0644 "$source_dir/user/"*.service "$source_dir/user/"*.timer "$unit_dir/"
if [[ ! -e "$env_dir/judgment-pi5.env" ]]; then
  install -m 0600 "$source_dir/pi5.env.example" "$env_dir/judgment-pi5.env"
  echo "Created $env_dir/judgment-pi5.env; replace every CHANGE_ME value."
fi
systemctl --user daemon-reload
echo "Units installed but not started or enabled. Follow deployment/judgment-pi5/README.md."

