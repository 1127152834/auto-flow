#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$script_dir/.."
bash "$script_dir/environment.sh"
docker compose config --quiet
docker compose up --build -d --wait --wait-timeout 120
echo 'Demo: http://localhost:8080 — Windows uses WSL localhost forwarding.'
echo 'If Windows cannot connect, check WSL localhostForwarding; do not publish the service to the LAN.'
