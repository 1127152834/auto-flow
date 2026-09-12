#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$script_dir/.."
docker compose down
echo 'Manager stopped. Dynamically created redroid instances and their data volumes were preserved.'
echo 'To remove them, start the manager again and explicitly delete the selected Demo instances.'
