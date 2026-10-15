#!/usr/bin/env bash
# M1 player FSM skeleton. Does not replace main.tscn or the idle/slash --verify path.
# Play:  ./run_m1.sh
# Check: ./run_m1.sh --headless -- --m1-check
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"
LOCAL_GODOT_HOME="$SCRIPT_DIR/.godot_user"
mkdir -p "$LOCAL_GODOT_HOME/data" "$LOCAL_GODOT_HOME/config" "$LOCAL_GODOT_HOME/cache"
export XDG_DATA_HOME="$LOCAL_GODOT_HOME/data"
export XDG_CONFIG_HOME="$LOCAL_GODOT_HOME/config"
export XDG_CACHE_HOME="$LOCAL_GODOT_HOME/cache"
GODOT_BIN="$REPO_ROOT/tools/godot-4.7.2/Godot_v4.7.2-stable_linux.x86_64"
if [ ! -x "$GODOT_BIN" ]; then
    GODOT_BIN="$(cd -- "$SCRIPT_DIR/../../../.." && pwd)/tools/godot-4.7.2/Godot_v4.7.2-stable_linux.x86_64"
fi
if [ ! -d "$SCRIPT_DIR/godot/.godot/imported" ]; then
    "$GODOT_BIN" --path "$SCRIPT_DIR/godot" --headless --editor --import --quit
fi
exec "$GODOT_BIN" --path "$SCRIPT_DIR/godot" res://player_m1.tscn "$@"
