#!/bin/bash
# Real upstream tools; no security-policy changes or implicit firmware downloads.
set -euo pipefail
demo_dir="$(cd "$(dirname "$0")/.." && pwd)"
source_dir="$demo_dir/../vphone-cli"
export VPHONE_ROOT="${VPHONE_DEMO_ROOT:-$HOME/.vphone-autoflow-demo}"
export VPHONE_LIBRARY_ROOT="$VPHONE_ROOT/VMs"
binary="${VPHONE_DEMO_BIN:-$source_dir/.build/vphone-cli.app/Contents/MacOS/vphone-cli}"
action="${1:-check}"
case "$action" in
  build)
    cd "$source_dir"
    export HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1
    brew install gnu-tar ldid-procursus sshpass keystone
    zsh scripts/setup_tools.sh
    make build
    zsh scripts/build.sh
    ;;
  check)
    python3 "$demo_dir/demo.py" doctor
    VPHONE_CLI_BIN="$binary" zsh "$source_dir/scripts/boot_host_preflight.sh" --assert-bootable
    ;;
  create)
    name="${2:-af-ios-demo}"
    [[ "$name" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]{0,47}$ ]] || { echo 'Invalid device name' >&2; exit 2; }
    python3 "$demo_dir/demo.py" doctor
    [[ ! -e "$VPHONE_LIBRARY_ROOT/$name" ]] || { echo 'Device exists; refusing to overwrite it' >&2; exit 2; }
    exec "$binary" vm create "$name" --variant jb --library-root "$VPHONE_LIBRARY_ROOT" --root-popup
    ;;
  launch)
    name="${2:-af-ios-demo}"
    [[ "$name" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]{0,47}$ ]] || exit 2
    python3 "$demo_dir/demo.py" doctor
    exec "$binary" vm launch "$name" --library-root "$VPHONE_LIBRARY_ROOT"
    ;;
  *) echo 'Usage: bash scripts/runtime.sh build|check|create [name]|launch [name]' >&2; exit 2 ;;
esac
