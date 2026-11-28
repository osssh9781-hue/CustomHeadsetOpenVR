"""Build the installable ZIP: python tools_dev/build_zip.py

0.24.150 (user: "이거 왜 안 깔리냥" - Blender's add-on installer: "ZIP packaged incorrectly; __init__.py should be in a
directory, not at top-level", with "System: Blender Extensions" switched off in their Preferences) everything goes in
one folder, mecha_lab/: the Extensions installer takes a ZIP whose manifest is in one folder, and the add-on installer
(Install from Disk with the Extensions system off) needs exactly that - one ZIP for both."""
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


def _lossless_jpeg(path):
    """0.24.349 (the zip at 99.7 of GitHub's 100 MB a file) a JPEG re-packed without loss by jpegtran (optimized
    Huffman tables, progressive): the same pixels, ~9 % fewer bytes.  None when jpegtran is missing or not smaller -
    the file goes in as it is.  The files in the add-on folder are not touched."""
    import shutil
    import subprocess
    import tempfile
    if not shutil.which('jpegtran'):
        return None
    with tempfile.TemporaryDirectory() as td:
        tmp = os.path.join(td, 'o.jpg')
        try:
            subprocess.run(['jpegtran', '-copy', 'all', '-optimize', '-progressive', '-outfile', tmp, path],
                           check=True, capture_output=True, timeout=60)
            data = open(tmp, 'rb').read()
        except (OSError, subprocess.SubprocessError):
            return None
    return data if 0 < len(data) < os.path.getsize(path) else None


with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    z.writestr('mecha_lab/build_stamp.txt', f'{version} build {stamp}\n')
    for base, dirs, files in os.walk(SRC):
        dirs[:] = sorted(d for d in dirs if d != '__pycache__' and not d.startswith('.'))
        for fn in sorted(files):
            if fn.endswith('.pyc') or fn.startswith('.'):
                continue
            full = os.path.join(base, fn)
            arc = 'mecha_lab/' + os.path.relpath(full, SRC).replace(os.sep, '/')
            small = _lossless_jpeg(full) if fn.lower().endswith(('.jpg', '.jpeg')) else None
            if small is not None:
                z.writestr(zipfile.ZipInfo.from_file(full, arc), small, zipfile.ZIP_STORED)
            else:
                z.write(full, arc)
print(out, os.path.getsize(out), 'bytes')
sys.exit(0)
