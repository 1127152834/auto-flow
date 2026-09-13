#!/bin/zsh
set -eu
repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
workspace_dir="${1:-$repo_dir/.local/android-handoff-workspace}"
app_binary="$repo_dir/apps/desktop/dist/mac-arm64/AutoFlow.app/Contents/MacOS/AutoFlow"
if [[ ! -x "$app_binary" || ! -f "$workspace_dir/.autoflow-workspace.json" ]]; then
  print -u2 '请先按 docs/migration/android-workflow-handoff-validation.md 构建应用并准备测试工作区。'
  exit 1
fi
exec "$app_binary" --user-data-dir="$workspace_dir"
