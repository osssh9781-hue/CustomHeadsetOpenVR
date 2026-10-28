#!/bin/sh
# Real-window smoke test: a real Blender (window, mouse, drawn UI) on a virtual screen (Xvfb).
#   sh tests/gui/run_gui.sh [5.2.3] [scratch dir]
# Needs the network to reach download.blender.org (the cloud environment's Allowed domains) and Xvfb.
# Downloads blender-<ver>-linux-x64.tar.xz once into the scratch dir, starts Xvfb :99 (1920x1080) and runs
# tests/gui/gui_smoke.py inside Blender.  Screenshots and the log land in tests/gui/out/.
set -e
VER="${1:-5.2.3}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
SCRATCH="${2:-${CLAUDE_SCRATCHPAD:-/tmp}/blender_gui}"
mkdir -p "$SCRATCH" "$HERE/out"
TAR="$SCRATCH/blender-$VER-linux-x64.tar.xz"
DIR="$SCRATCH/blender-$VER-linux-x64"
if [ ! -x "$DIR/blender" ]; then
  MAJOR="$(echo "$VER" | cut -d. -f1,2)"
  [ -f "$TAR" ] || curl -fL --retry 3 -o "$TAR" "https://download.blender.org/release/Blender$MAJOR/blender-$VER-linux-x64.tar.xz"
  tar -xJf "$TAR" -C "$SCRATCH"
fi
ZIP="$(ls -t "$ROOT"/dist/mecha_lab-*.zip | head -1)"
export MCH_GUI_ZIP="$ZIP" MCH_GUI_OUT="$HERE/out" MCH_GUI_ROOT="$ROOT"
# (Blender's own config in a temp dir: the user's settings are never touched)
export BLENDER_USER_CONFIG="$SCRATCH/cfg" BLENDER_USER_SCRIPTS="$SCRATCH/scripts" BLENDER_USER_EXTENSIONS="$SCRATCH/ext"
if ! pgrep -f "Xvfb :99" >/dev/null; then
  Xvfb :99 -screen 0 1920x1080x24 >/dev/null 2>&1 &
fi
for _i in $(seq 1 40); do [ -S /tmp/.X11-unix/X99 ] && break; sleep 0.25; done   # (X up before Blender: else it tries
sleep 1                                                                            #  Wayland and dies)
export DISPLAY=:99
export LIBGL_ALWAYS_SOFTWARE=1 MESA_LOADER_DRIVER_OVERRIDE=llvmpipe GALLIUM_DRIVER=llvmpipe
unset WAYLAND_DISPLAY
# (a Unix socket path may be 108 bytes at most: the runtime dir must be short, so not under the scratch dir)
export XDG_RUNTIME_DIR="/tmp/mch_xdg_$$"; mkdir -p "$XDG_RUNTIME_DIR"; chmod 700 "$XDG_RUNTIME_DIR"
"$DIR/blender" --window-geometry 0 0 1920 1080 --python "$HERE/gui_smoke.py" -- "$@" 2>&1 | tee "$HERE/out/gui_log.txt"
