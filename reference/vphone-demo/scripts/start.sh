#!/bin/bash
set -euo pipefail
demo_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$demo_dir/frontend"
if [[ ! -d node_modules ]]; then npm ci; fi
npm run build
cd "$demo_dir"
exec python3 demo.py serve
