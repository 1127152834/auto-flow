#!/usr/bin/env bash
set -euo pipefail
# This must run on the same WSL/Linux host as the mounted Docker socket.
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
  echo 'FAIL: requires Linux x86_64; use Windows x64 + WSL2 Ubuntu 24.04 or Linux amd64.' >&2
  exit 1
fi
for command_name in docker python3; do
  command -v "$command_name" >/dev/null || { echo "FAIL: missing $command_name" >&2; exit 1; }
done
if [[ -n "${DOCKER_HOST:-}" && "$DOCKER_HOST" != unix:///var/run/docker.sock ]]; then
  echo 'FAIL: DOCKER_HOST must use the local /var/run/docker.sock; remote daemons are not supported.' >&2
  exit 1
fi
context_name="$(docker context show)"
endpoint="$(docker context inspect "$context_name" --format '{{.Endpoints.docker.Host}}')"
if [[ -z "${DOCKER_HOST:-}" && "$endpoint" != unix:///var/run/docker.sock ]]; then
  echo "FAIL: context $context_name uses $endpoint, not the local Engine. Select the WSL Engine explicitly." >&2
  exit 1
fi
[[ -S /var/run/docker.sock ]] || { echo 'FAIL: local Docker Engine socket does not exist.' >&2; exit 1; }
docker info --format '{{json .}}' | python3 -c '
import json, sys
info=json.load(sys.stdin)
print("Docker:", info.get("OperatingSystem"), info.get("Architecture"), "kernel", info.get("KernelVersion"))
if info.get("OSType") != "linux" or info.get("Architecture") not in ("x86_64", "amd64"):
    sys.exit("FAIL: Docker daemon must be Linux amd64")
if "docker desktop" in str(info.get("OperatingSystem", "")).lower():
    sys.exit("FAIL: Docker Desktop is not the supported baseline; use Docker Engine inside WSL")
'
docker compose version
# A binderfs-capable kernel can work without creating /dev/binder before redroid starts.
if [[ -d /sys/module/binder_linux ]] || [[ -c /dev/binder ]] || [[ -e /dev/binderfs/binder-control ]] || grep -qw binder /proc/filesystems; then
  echo 'PASS: host has a binder/binderfs signal; actual Android boot remains to be tested.'
else
  echo 'FAIL: no binder/binderfs signal. Configure the WSL kernel using the documented redroid requirements.' >&2
  echo 'https://github.com/remote-android/redroid-doc/blob/master/deploy/wsl.md' >&2
  exit 1
fi
if ! docker image inspect redroid/redroid:13.0.0-latest >/dev/null 2>&1; then
  echo 'FAIL: default image is not cached. Run: docker pull --platform linux/amd64 redroid/redroid:13.0.0-latest' >&2
  exit 1
fi
echo 'PASS: local preflight checks completed. The API also checks the actual daemon and Android readiness.'
