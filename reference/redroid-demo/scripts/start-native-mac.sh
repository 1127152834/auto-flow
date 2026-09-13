#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
demo_dir="$(dirname "$script_dir")"
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || { echo 'Requires an Apple Silicon Mac.' >&2; exit 1; }
for tool in adb limactl curl; do
  command -v "$tool" >/dev/null || { echo "Missing $tool. See NATIVE_MAC_TEST.md." >&2; exit 1; }
done
[[ -x "$demo_dir/.venv/bin/python" ]] || { echo 'Create the demo .venv and install backend/requirements.txt first.' >&2; exit 1; }
curl --noproxy '*' --fail --silent --max-time 10 http://127.0.0.1:8081/api/jobs >/dev/null || {
  echo 'Start the existing VM demo first: bash scripts/start-mac.sh' >&2; exit 1;
}
vendor_dir="$demo_dir/.data/native-monitor/vendor"
archive_name=scrcpy-macos-aarch64-v3.3.4.tar.gz
archive_sha=8fef43520405dd523c74e1530ac68febcc5a405ea89712c874936675da8513dd
mkdir -p "$vendor_dir"
if [[ ! -f "$vendor_dir/$archive_name" ]]; then
  download_file="$(mktemp "$vendor_dir/download.XXXXXX")"
  trap 'rm -f "$download_file"' EXIT
  curl --fail --location --max-time 120 "https://github.com/Genymobile/scrcpy/releases/download/v3.3.4/$archive_name" -o "$download_file"
  actual_sha="$(shasum -a 256 "$download_file" | cut -d ' ' -f 1)"
  [[ "$actual_sha" == "$archive_sha" ]] || { echo 'scrcpy archive checksum mismatch.' >&2; exit 1; }
  mv "$download_file" "$vendor_dir/$archive_name"
  trap - EXIT
fi
"$demo_dir/.venv/bin/python" - "$vendor_dir/$archive_name" "$archive_sha" <<'PY'
from pathlib import Path
import hashlib, sys, tarfile
archive = Path(sys.argv[1])
if hashlib.sha256(archive.read_bytes()).hexdigest() != sys.argv[2]:
    raise SystemExit('scrcpy archive checksum mismatch')
with tarfile.open(archive) as source:
    source.extractall(archive.parent, filter='data')
PY
cd "$demo_dir/frontend"
npm run build
cd "$demo_dir"
exec .venv/bin/python scripts/native_monitor.py
