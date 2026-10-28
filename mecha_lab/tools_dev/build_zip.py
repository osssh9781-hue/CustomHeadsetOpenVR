"""Build the installable Blender extension ZIP: python tools_dev/build_zip.py"""
import os
import sys
import tomllib
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'addon', 'mecha_lab')
with open(os.path.join(SRC, 'blender_manifest.toml'), 'rb') as f:
    version = tomllib.load(f)['version']
# 0.24.82 the file name carries the build time, so two builds of one version are never mistaken for each other;
# the same stamp goes into the zip (build_stamp.txt) and shows in Preferences next to the version
import datetime
stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M')
out = os.path.join(ROOT, 'dist', f'mecha_lab-{version}_{stamp}.zip')
os.makedirs(os.path.dirname(out), exist_ok=True)
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    z.writestr('build_stamp.txt', f'{version} build {stamp}\n')
    for base, dirs, files in os.walk(SRC):
        dirs[:] = sorted(d for d in dirs if d != '__pycache__' and not d.startswith('.'))
        for fn in sorted(files):
            if fn.endswith('.pyc') or fn.startswith('.'):
                continue
            full = os.path.join(base, fn)
            z.write(full, os.path.relpath(full, SRC))
print(out, os.path.getsize(out), 'bytes')
sys.exit(0)
