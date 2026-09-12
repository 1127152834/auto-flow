#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
demo_dir="$(dirname "$script_dir")"
vm=autoflow-redroid
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || { echo 'Requires an Apple Silicon Mac.' >&2; exit 1; }
command -v limactl >/dev/null || { echo 'Install Lima first: brew install lima' >&2; exit 1; }
case "${1:-start}" in
  stop) limactl stop "$vm"; exit ;;
  check) limactl shell --workdir=/tmp "$vm" bash -c 'sudo env REDROID_IMAGES=redroid/redroid:13.0.0_64only-latest bash "$HOME/redroid-demo/scripts/environment.sh"'; exit ;;
  start) ;;
  *) echo 'Usage: bash scripts/start-mac.sh [start|check|stop]' >&2; exit 1 ;;
esac
if limactl list --format '{{.Name}}' | grep -qx "$vm"; then
  limactl start --tty=false "$vm"
else
  limactl start --name="$vm" --tty=false "$script_dir/lima-mac.yaml"
fi
archive="$(mktemp -t autoflow-redroid)"
trap 'rm -f "$archive"' EXIT
COPYFILE_DISABLE=1 tar --no-xattrs --no-acls -czf "$archive" --exclude=.data --exclude=.venv --exclude=node_modules \
  --exclude=dist --exclude=coverage --exclude=__pycache__ --exclude=.ruff_cache --exclude=.git -C "$demo_dir" .
limactl copy "$archive" "$vm:/tmp/autoflow-redroid-demo.tgz"
limactl shell --workdir=/tmp "$vm" bash -c '
  set -euo pipefail
  mkdir -p "$HOME/redroid-demo"
  tar -xzf /tmp/autoflow-redroid-demo.tgz -C "$HOME/redroid-demo"
  cd "$HOME/redroid-demo"
  base=redroid/redroid:13.0.0_64only-latest
  sudo docker image inspect "$base" >/dev/null 2>&1 || sudo docker pull --platform linux/arm64 "$base"
  sudo env REDROID_IMAGES="$base" bash scripts/environment.sh
  sudo env REDROID_IMAGES="$base,autoflow/redroid:13-magisk" docker compose up -d --build --wait --wait-timeout 120
'
guest_session="$(limactl shell --workdir=/tmp "$vm" python3 -c 'import json, urllib.request; opener = urllib.request.build_opener(urllib.request.ProxyHandler({})); print(json.load(opener.open("http://127.0.0.1:8080/api/jobs", timeout=5))["session_id"])')"
[[ "$guest_session" =~ ^[0-9a-f]{32}$ ]] || { echo 'FAIL: guest API returned an invalid session ID.' >&2; exit 1; }
for attempt in {1..10}; do
  response="$(curl --noproxy '*' --fail --silent --connect-timeout 2 --max-time 3 http://127.0.0.1:8081/api/jobs || true)"
  host_session="$(printf '%s' "$response" | sed -nE 's/.*"session_id"[[:space:]]*:[[:space:]]*"([0-9a-f]{32})".*/\1/p')"
  if [[ "$host_session" == "$guest_session" ]]; then
    echo 'Mac demo: http://127.0.0.1:8081 (Lima guest port 8080; API session verified)'
    exit 0
  fi
  sleep 1
done
echo 'FAIL: Mac port 8081 did not reach this VM API session; check port conflicts and Lima forwarding.' >&2
exit 1
