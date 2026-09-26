#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
WORKSPACE_ROOT="$(cd -- "$SCRIPT_DIR/../../../.." && pwd)"
LOCAL_GODOT_HOME="$SCRIPT_DIR/.godot_user"
mkdir -p "$LOCAL_GODOT_HOME/data" "$LOCAL_GODOT_HOME/config" "$LOCAL_GODOT_HOME/cache"
export XDG_DATA_HOME="$LOCAL_GODOT_HOME/data"
export XDG_CONFIG_HOME="$LOCAL_GODOT_HOME/config"
export XDG_CACHE_HOME="$LOCAL_GODOT_HOME/cache"
GODOT_BIN="$WORKSPACE_ROOT/tools/godot-4.7.2/Godot_v4.7.2-stable_linux.x86_64"
if [ ! -d "$SCRIPT_DIR/godot/.godot/imported" ]; then
    "$GODOT_BIN" --path "$SCRIPT_DIR/godot" --headless --editor --import --quit
fi
exec "$GODOT_BIN" --path "$SCRIPT_DIR/godot" "$@"
