"""Build the installable Blender extension ZIP: python tools_dev/build_zip.py"""
import os
import sys
import tomllib
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'addon', 'mecha_lab')
with open(os.path.join(SRC, 'blender_manifest.toml'), 'rb') as f:
    version = tomllib.load(f)['version']
out = os.path.join(ROOT, 'dist', f'mecha_lab-{version}.zip')
os.makedirs(os.path.dirname(out), exist_ok=True)
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for base, dirs, files in os.walk(SRC):
        dirs[:] = sorted(d for d in dirs if d != '__pycache__' and not d.startswith('.'))
        for fn in sorted(files):
            if fn.endswith('.pyc') or fn.startswith('.'):
                continue
            full = os.path.join(base, fn)
            z.write(full, os.path.relpath(full, SRC))
print(out, os.path.getsize(out), 'bytes')
sys.exit(0)
