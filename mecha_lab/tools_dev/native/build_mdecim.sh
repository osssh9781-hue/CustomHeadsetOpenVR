#!/bin/sh
# Build Mecha Lab's geometry engine: decimation (mdecim.c) + quad remesh (mquad.c), one library
# (plain C, no Python API: loaded with ctypes, any Blender / Python version).
#   Linux x64:    gcc            (needs pthreads)
#   Windows x64:  MinGW-w64 gcc  (Win32 threads; only KERNEL32 + msvcrt, no extra DLLs)
# Output: addon/mecha_lab/bin/
set -e
cd "$(dirname "$0")"
OUT=../../addon/mecha_lab/bin
mkdir -p "$OUT"
gcc -O2 -shared -fPIC -fvisibility=hidden -pthread -o "$OUT/mdecim_linux_x64.so" mdecim.c mquad.c -lm
x86_64-w64-mingw32-gcc -O2 -shared -static-libgcc -s -o "$OUT/mdecim_win_x64.dll" mdecim.c mquad.c
ls -l "$OUT"
