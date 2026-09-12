#!/usr/bin/env bash
set -euo pipefail
# This must run on the same WSL/Linux host as the mounted Docker socket.
host_arch="$(uname -m)"
if [[ "$(uname -s)" != Linux || ! "$host_arch" =~ ^(x86_64|amd64|aarch64|arm64)$ ]]; then
  echo 'FAIL: requires native Linux amd64/arm64; use a Linux VM on macOS or WSL2 on Windows.' >&2
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
normalize={"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get
print("Docker:", info.get("OperatingSystem"), info.get("Architecture"), "kernel", info.get("KernelVersion"))
if info.get("OSType") != "linux" or normalize(info.get("Architecture")) != normalize(sys.argv[1]):
    sys.exit("FAIL: Docker daemon must match the native Linux amd64/arm64 host")
if "docker desktop" in str(info.get("OperatingSystem", "")).lower() or "docker-desktop" in str(info.get("Name", "")).lower():
    sys.exit("FAIL: Docker Desktop is not supported; use Docker Engine inside the Linux VM/WSL")
' "$host_arch"
docker compose version
# A binderfs-capable kernel can work without creating /dev/binder before redroid starts.
if [[ -d /sys/module/binder_linux ]] || [[ -c /dev/binder ]] || [[ -e /dev/binderfs/binder-control ]] || grep -qw binder /proc/filesystems; then
  echo 'PASS: host has a binder/binderfs signal; actual Android boot remains to be tested.'
else
  echo 'FAIL: no binder/binderfs signal. Configure the WSL kernel using the documented redroid requirements.' >&2
  echo 'https://github.com/remote-android/redroid-doc/blob/master/deploy/wsl.md' >&2
  exit 1
fi
default_image="${REDROID_IMAGES:-redroid/redroid:13.0.0-latest}"
default_image="${default_image%%,*}"
default_image="${default_image#"${default_image%%[![:space:]]*}"}"
default_image="${default_image%"${default_image##*[![:space:]]}"}"
if ! docker image inspect "$default_image" >/dev/null 2>&1; then
  echo "FAIL: default image is not cached. Run on this Engine: docker pull $default_image" >&2
  exit 1
fi
docker image inspect "$default_image" | python3 -c '
import json, sys
image=json.load(sys.stdin)[0]
normalize={"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get
if image.get("Os") != "linux" or normalize(image.get("Architecture")) != normalize(sys.argv[1]):
    sys.exit("FAIL: default image must match the native Linux host architecture")
print("PASS: cached image matches Linux", normalize(sys.argv[1]))
' "$host_arch"
echo 'PASS: local preflight checks completed. The API also checks the actual daemon and Android readiness.'
