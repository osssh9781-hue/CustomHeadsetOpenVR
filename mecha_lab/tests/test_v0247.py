"""0.24.7 bulk image import: the stamp list is cached (no file reading / thumbnail work on a redraw when nothing
changed), big source images get a small list thumbnail, and old wheel stamp-size keymap items are cleaned up."""
import sys

_src = open(__file__.replace('test_v0247.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
import os, tempfile, time, builtins, json
from mecha_lab import cut_presets as cp

folder = cp.preset_folder()
d = tempfile.mkdtemp()
paths = []
for i in range(12):
    img = bpy.data.images.new(f'bulk{i}', 64, 64, alpha=False)
    px = []
    for y in range(64):
        for x in range(64):
            on = (x - 32) ** 2 + (y - 32) ** 2 < (10 + i) ** 2
            px += [1.0, 1.0, 1.0, 1.0] if on else [0.0, 0.0, 0.0, 1.0]
    img.pixels = px
    p = os.path.join(d, f'bulk_{i}.jpg')
    img.file_format = 'JPEG'
    img.filepath_raw = p
    img.save()
    bpy.data.images.remove(img)
    paths.append(p)

before = set(p.name for p in folder.glob('*.json'))
fake = types.SimpleNamespace(directory=d, files=[types.SimpleNamespace(name=os.path.basename(p)) for p in paths],
                             filepath=paths[0], shape_name='', mode='AUTO', threshold=0.5, invert=False,
                             simplify=0.8, smooth=1, min_area=4, reports=[])
fake.report = lambda kind, msg: fake.reports.append(msg)
calls = [0]
orig_refresh = cp._refresh_previews
def counting():
    calls[0] += 1
    orig_refresh()
cp._refresh_previews = counting
res = cp.MCH_OT_import_cut_png.execute(fake, C)
cp._refresh_previews = orig_refresh
new = sorted(set(p.name for p in folder.glob('*.json')) - before)
check('12 JPEGs imported in one go', res == {'FINISHED'} and len(new) == 12, (res, len(new), fake.reports[-1:]))
check('previews rebuilt once for the whole batch', calls[0] == 1, calls)

items = cp.preset_items(None, C)
check('enum lists the imported shapes', all(n[:-5] in {it[0] for it in items} for n in new))
opened = [0]
real_open = builtins.open
def spy(f, *a, **k):
    if str(f).endswith('.json'):
        opened[0] += 1
    return real_open(f, *a, **k)
builtins.open = spy
try:
    t = time.perf_counter()
    for _ in range(50):
        again = cp.preset_items(None, C)
        cp.list_presets()
    dt = time.perf_counter() - t
finally:
    builtins.open = real_open
check('redraws read no preset file (cached)', opened[0] == 0, opened)
check('cached list is the same object', again is items)
check('50 redraws are fast', dt < 1.0, round(dt, 3))

# a changed file is re-read; a deleted file drops out
st = new[0][:-5]
jp = folder / new[0]
data = json.loads(jp.read_text(encoding='utf-8'))
data['name'] = 'Renamed'
jp.write_text(json.dumps(data), encoding='utf-8')
os.utime(jp, (time.time() + 5, time.time() + 5))
check('changed preset name shows up', dict(cp.list_presets()).get(st) == 'Renamed')

# big source image -> small list thumbnail made once
big = folder / (st + '.png')
img = bpy.data.images.new('bigsrc', 1600, 1600, alpha=False)
import numpy as np
img.pixels.foreach_set(np.random.default_rng(1).random(1600 * 1600 * 4).astype(np.float32))
img.file_format = 'PNG'
img.filepath_raw = str(big)
img.save()
bpy.data.images.remove(img)
check('test source is big', big.stat().st_size > 120_000, big.stat().st_size)
cp._THUMBS.pop(st, None)
iid = cp.preset_icon(st)
small = big.with_name(big.stem + '_thumb.png')
check('big source gets a small _thumb.png', small.is_file() and small.stat().st_size < big.stat().st_size,
      small.is_file() and small.stat().st_size)
check('list icon uses the small thumbnail', cp._THUMBS.get(st) == str(small))

# imported library copies are small (thumbnail-size PNG)
src2 = folder / (new[1][:-5] + '.png')
im = bpy.data.images.load(str(src2))
check('library copy is at most 192 px', max(im.size) <= cp.THUMB_PX, tuple(im.size))
bpy.data.images.remove(im)

# delete removes json, source and thumb
S.mch_png_preset = st
fk = types.SimpleNamespace(report=lambda *a: None)
cp.MCH_OT_delete_cut_preset.execute(fk, C)
check('delete removes json, source and _thumb', not jp.exists() and not big.exists() and not small.exists())
check('deleted shape leaves the list', st not in dict(cp.list_presets()))

for n in new[1:]:
    (folder / n).unlink(missing_ok=True)
    (folder / (n[:-5] + '.png')).unlink(missing_ok=True)

# ---- stale wheel stamp-size keymap items from 0.24.5 are removed
from mecha_lab import workspace_ui as wui
check('cleanup helper exists', hasattr(wui, 'purge_stale_keymap_items'))
kc = bpy.context.window_manager.keyconfigs.addon
if kc is not None:
    km = kc.keymaps.new('Mecha Test Stale', space_type='EMPTY')
    km.keymap_items.new('mch.stamp_scale', 'WHEELUPMOUSE', 'PRESS')
    n = wui.purge_stale_keymap_items()
    check('stale mch.stamp_scale items removed', n >= 1 and not any(
        it.idname == 'mch.stamp_scale' for k in kc.keymaps for it in k.keymap_items), n)
    kc.keymaps.remove(km)
    wui.unregister_native_tools()       # the purge runs before the tools are registered (as in register())
    wui.register_native_tools()
    name = '3D View Tool: Object, ' + wui.MCH_TOOL_cut.bl_label
    tkm = kc.keymaps.get(name)
    check('Cut tool keymap exists', tkm is not None)
    if tkm is not None:
        tkm.keymap_items.new('mch.stamp_rotate', 'WHEELUPMOUSE', 'PRESS')     # an old item left from an update
        wui.unregister_native_tools()
        wui.purge_stale_keymap_items()
        wui.register_native_tools()
        tkm = kc.keymaps.get(name)
        check('tool keymap rebuilt from the current bindings (no old wheel item)', tkm is not None and not any(
            it.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'} for it in tkm.keymap_items) and any(
            it.idname == 'mch.stamp_rotate' for it in tkm.keymap_items), tkm and [(i.idname, i.type) for i in tkm.keymap_items])

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
