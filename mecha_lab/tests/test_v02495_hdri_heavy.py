"""0.24.95 A big HDRI folder made light (user: "hdri 뭉탱이로 불러왔더니 캐무거워"):

* the previews are made in a second Blender (``hdri_thumbs.py``): this Blender reads no HDRI for them; a file it
  cannot read gets a mark and is not tried again; the HDRI page says how many are left while it works
* the folder tree is walked again only when a folder changed (its change time), not every 2 s
* (user: "6 개씩만 불러오면 안 돼? 넘기면 되잖아") 6 previews on a page, ◀ Page n / m ▶: only the page's previews are
  drawn and asked for (and the next page's, ready); the page follows the HDRI in use; the page number = back to it
* the HDRI picked before is let go when another is picked (its pixels freed); an image the user had in the file stays
* the panel's pictures are read without making a Blender image (each one made and removed was a change to the file's
  data: the 3D view started its drawing again - Material Preview re-rendered - once per preview arriving)
* a scene that never picked an HDRI shows Blender's first one in the list (it was blank, a warning per look)"""
import os
import shutil
import tempfile
import time

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import mech_shader as ms, mech_shader_ui as mu, side_panel as sp, ui_bars, workspace_ui

fresh()
mecha_lab.register()
C = bpy.context
sc = C.scene
bpy.ops.mesh.primitive_cube_add()
bpy.ops.mch.mech_shader_apply(preset='PAINTED')

mine = tempfile.mkdtemp(prefix='mch_many_hdri_')
img = bpy.data.images.new('sky', 64, 32, float_buffer=True)
px = np.zeros((32, 64, 4), np.float32)
px[16:] = (2.0, 2.5, 4.0, 1.0)
px[:16] = (0.2, 0.15, 0.1, 1.0)
img.pixels.foreach_set(px.ravel())
img.file_format = 'HDR'
SRC = os.path.join(tempfile.mkdtemp(prefix='mch_src_'), 'sky.hdr')
img.filepath_raw = SRC
img.save()
bpy.data.images.remove(img)
NAMES = {'A': 12, 'B': 12, 'C': 6}
for g, n in NAMES.items():
    os.makedirs(os.path.join(mine, g))
    for i in range(n):
        shutil.copy(SRC, os.path.join(mine, g, f'{g.lower()}{i:02d}.hdr'))
with open(os.path.join(mine, 'C', 'broken.exr'), 'wb') as f:
    f.write(b'not an exr at all' * 50)

real_pref = workspace_ui.pref
workspace_ui.pref = lambda name, default=True: mine if name == 'hdri_folder' else real_pref(name, default)
try:
    ms.rescan()
    walks = [0]
    real_scan = ms._scan_user_hdris

    def counted(d):
        walks[0] += 1
        return real_scan(d)
    ms._scan_user_hdris = counted
    files = ms.user_hdri_files()
    ms._SCAN['time'] = 0.0                                 # (as 2 s later)
    again = ms.user_hdri_files()
    check('The folder tree walked once; 2 s later with no folder changed: not walked again (the same list)',
          len(files) == 31 and walks[0] == 1 and again is files, (len(files), walks[0]))
    shutil.copy(SRC, os.path.join(mine, 'C', 'c99.hdr'))
    os.utime(os.path.join(mine, 'C'), None)
    st = os.stat(os.path.join(mine, 'C'))
    os.utime(os.path.join(mine, 'C'), ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))   # (a coarse clock: moved on)
    ms._SCAN['time'] = 0.0
    listed = ms.user_hdri_files()
    check('... a file added to a folder: that folder changed - walked again, listed',
          walks[0] == 2 and 'C/c99.hdr' in listed, walks[0])
    ms._scan_user_hdris = real_scan

    # the HDRI page: 6 previews on a page, turned with ◀ ▶ (user: "6 개씩만 불러오면 안 돼? 넘기면 되잖아")
    sc.mch_mech_hdri = 'U:B/b03.hdr'
    bpy.ops.mch.mech_hdri(action='SET')
    ms._THUMB_QUEUE.clear()
    its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
    tiles = [i.label for i in its if i.kind == 'htile']
    btns = {i.label: i for i in its if i.kind == 'tbtn'}
    check('40 HDRIs: 6 previews on a page - the page with the HDRI in use (B\'s b03: page 3 of 7), ◀ Page 3 / 7 ▶',
          tiles == [f'b{i:02d}' for i in range(6)] and 'Page 3 / 7' in btns and '◀' in btns and '▶' in btns,
          (tiles, [k for k in btns if 'Page' in k]))
    check('... only those 6 previews asked for, and the next page\'s 6 (ready when it is turned)',
          sorted(os.path.basename(s) for s, _o in ms._THUMB_QUEUE) == [f'b{i:02d}.hdr' for i in range(12)],
          len(ms._THUMB_QUEUE))
    heads = [i.label for i in its if i.kind == 'pnote' and i.label.split('  (')[0] in ('A', 'B', 'C', 'Blender')]
    check('... the folder over its previews, with how many it has', heads == ['B  (12)'], heads)

    def pager(items, step):
        return next(i for i in items if i.kind == 'tbtn' and i.action[:2] == ('op', 'mch.mech_hdri_page')
                    and i.action[2].get('step') == step)
    ui_bars.run(C, pager(its, 1))
    its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
    tiles = [i.label for i in its if i.kind == 'htile']
    check('... ▶: the next 6 (b06 .. b11), Page 4 / 7, the HDRI in use not changed; the page after that asked for '
          '(folder C)', tiles == [f'b{i:02d}' for i in range(6, 12)] and sc.mch_mech_hdri == 'U:B/b03.hdr'
          and any(i.label == 'Page 4 / 7' for i in its) and any(s_.endswith('broken.exr') for s_, _o in ms._THUMB_QUEUE),
          tiles)
    for _k in range(4):
        ui_bars.run(C, pager(mu.hdri_content(C, 0.0, 276.0, 1.0)[0], 1))
    its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
    first = [i.label for i in its if i.kind == 'htile']
    check('... ▶ on the last page: back to the first', any(i.label == 'Page 1 / 7' for i in its)
          and first == [f'a{i:02d}' for i in range(6)], first)
    ui_bars.run(C, pager(its, 0))
    its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
    check('... the page number clicked: back to the page with the HDRI in use',
          any(i.label == 'Page 3 / 7' for i in its) and any(i.kind == 'htile' and i.on for i in its))
    sc.mch_mech_hdri = 'U:C/c03.hdr'
    its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
    check('... another HDRI picked (the arrows above, the list): the page follows it',
          any(i.label == 'Page 5 / 7' for i in its) and any(i.kind == 'htile' and i.on and i.label == 'c03' for i in its))
    sc.mch_mech_hdri = 'U:B/b03.hdr'
    its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)

    # the previews made in a second Blender
    os.environ['MECH_BG_FORCE'] = '1'
    inline = [0]
    real_make = ms.make_hdri_thumb

    def counted_make(*a, **k):
        inline[0] += 1
        return real_make(*a, **k)
    ms.make_hdri_thumb = counted_make
    n_img = len(bpy.data.images)
    t0 = time.perf_counter()
    first = ms._thumb_tick()
    started = time.perf_counter() - t0
    job = dict(ms._THUMB_JOB)
    its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
    note = [i.label for i in its if i.kind == 'pnote' and 'previews in the background' in i.label]
    check('The previews: a second Blender started (this one goes on at once - nothing read here), the page says how '
          'many are left', job.get('proc') is not None and first == 0.4 and started < 1.0 and inline[0] == 0
          and len(bpy.data.images) == n_img and note, (started, note))
    for _n in range(600):
        if ms._thumb_tick() is None:
            break
        time.sleep(0.1)
    shown = [ms.hdri_icon('U:B/' + f'b{i:02d}.hdr') for i in range(12)]
    ok = all(s.startswith('file:') and os.path.isfile(s[5:]) for s in shown)
    size = None
    if ok:
        t = bpy.data.images.load(shown[0][5:])
        size = tuple(t.size)
        bpy.data.images.remove(t)
    check('... done: every preview asked for there (256 x 128), none made in this Blender, the queue empty',
          ok and size == (256, 128) and inline[0] == 0 and not ms._THUMB_JOB and not ms._THUMB_QUEUE
          and ms.thumbs_pending() == 0, (ok, size, inline[0]))
    broken = os.path.join(mine, 'C', 'broken.exr')
    check('... a file it cannot read: marked, no preview, not asked for again; the user\'s folder untouched',
          ms.hdri_icon('U:C/broken.exr') == '' and broken in ms._THUMB_FAILED and not ms._THUMB_QUEUE
          and sorted(os.listdir(os.path.join(mine, 'C')))[:2] == ['broken.exr', 'c00.hdr']
          and all(f.endswith(('.hdr', '.exr')) for g in NAMES for f in os.listdir(os.path.join(mine, g))))
    ms.make_hdri_thumb = real_make
    del os.environ['MECH_BG_FORCE']

    # the HDRI picked before let go
    env = sc.world.node_tree.nodes['mch:env']
    before = env.image.name if env.image else None
    sc.mch_mech_hdri = 'U:A/a01.hdr'
    bpy.ops.mch.mech_hdri(action='SET')
    gone = before is not None and before not in [i.name for i in bpy.data.images]
    check('Another HDRI picked: the one before let go (removed - its pixels freed)', gone and env.image is not None
          and env.image.filepath.endswith('a01.hdr'), [i.name for i in bpy.data.images])
    mine_img = bpy.data.images.load(os.path.join(mine, 'A', 'a02.hdr'))          # (the user's own, in the file)
    sc.mch_mech_hdri = 'U:A/a02.hdr'
    bpy.ops.mch.mech_hdri(action='SET')
    sc.mch_mech_hdri = 'U:A/a03.hdr'
    bpy.ops.mch.mech_hdri(action='SET')
    check('... an image the user had in the file before: kept', mine_img.name in bpy.data.images
          and env.image.filepath.endswith('a03.hdr'))
finally:
    workspace_ui.pref = real_pref
    ms.cancel_thumbs()
    ms.rescan()

# the panel's pictures read without a Blender image (adding / removing one restarts the 3D view's drawing)
from mecha_lab import ui_gpu  # noqa: E402
p = os.path.join(tempfile.mkdtemp(), 'icon.png')
img = bpy.data.images.new('icon', 6, 4, alpha=True)
px = np.zeros((4, 6, 4), np.float32)
px[..., 3] = 1.0
px[0, 0] = (1.0, 0.0, 0.0, 1.0)
px[3, 5] = (0.0, 0.0, 1.0, 0.5)
img.pixels.foreach_set(px.ravel())
img.filepath_raw = p
img.file_format = 'PNG'
img.save()
bpy.data.images.remove(img)
n_img = len(bpy.data.images)
w, h, a, is_float = ui_gpu._pixels(p)
ref = bpy.data.images.load(p)
r = np.empty(len(ref.pixels), np.float32)
ref.pixels.foreach_get(r)
bpy.data.images.remove(ref)
check('The panel\'s pictures (previews, icons): read without a Blender image (the file\'s data untouched - the 3D view '
      'not started again), the same pixels as Blender\'s image, bottom row first',
      len(bpy.data.images) == n_img and (w, h) == (6, 4) and not is_float and np.allclose(a, r, atol=1 / 255)
      and np.allclose(a.reshape(4, 6, 4)[0, 0], (1, 0, 0, 1)))
fresh()
mecha_lab.register()
ms.rescan()
sc = bpy.context.scene
check('A scene that never picked an HDRI: the list shows Blender\'s first one (not a blank)',
      sc.mch_mech_hdri == ms.hdri_files()[0], sc.mch_mech_hdri)
summary()
