"""0.24.95 (user: "hdri 도 미리 보기 넣어 줘 그리고 옷 패턴에 이거도 넣어 줘") HDRI previews in the HDRI page - Blender's own
come with the add-on (mech_icons/hdri_<name>.png), an HDRI in the user's folder gets its own once (made off the draw,
one at a time, in Blender's temporary folder); a click on one = that HDRI, on.  The user's burlap photo as the Weave
map Burlap, and a Cloth Burlap preset (with its sphere icon)."""
import os
import tempfile

from _harness import bpy, check, cube, fresh, summary

import mecha_lab
from mecha_lab import mech_shader as ms, mech_shader_ui as mu, ui_bars, workspace_ui

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
ob = cube('Part')
ob.select_set(True)
C.view_layer.objects.active = ob

its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
tiles = [i for i in its if i.kind == 'htile']
built = [f for f in ms.hdri_files()]
check('HDRI page: previews of the HDRIs (Blender\'s own: 8) - 6 on a page (0.24.95 "6 개씩만, 넘기면 되잖아"), two per '
      'row, 2 : 1 panoramas, ◀ Page 1 / 2 ▶',
      len(built) == 8 and len(tiles) == 6 and len({round(t.x) for t in tiles}) == 2 and all(t.w > t.h for t in tiles)
      and any(i.kind == 'tbtn' and i.label == 'Page 1 / 2' for i in its), (len(tiles), len(built)))
check('... Blender\'s own previews come with the add-on (no waiting)',
      all(t.icon.startswith('file:') and os.path.isfile(t.icon[5:]) for t in tiles))
forest = next(t for t in tiles if 'forest' in t.label.lower())
ui_bars.run(C, forest)
check('A click on a preview: that HDRI, and on (the scene\'s world)', S.mch_mech_hdri == 'forest.exr'
      and ms.hdri_world(S) is not None)
its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
check('... its preview blue', [t.label.lower() for t in its if t.kind == 'htile' and t.on] == ['forest'])

# an HDRI in the user's folder: its preview made once (off the draw)
d = tempfile.mkdtemp(prefix='mch_user_hdri_')
img = bpy.data.images.new('sky', 64, 32, float_buffer=True)
import numpy as np
px = np.zeros((32, 64, 4), np.float32)
px[16:] = (2.0, 2.5, 4.0, 1.0)                       # (a bright blue sky over a dark ground)
px[:16] = (0.2, 0.15, 0.1, 1.0)
img.pixels.foreach_set(px.ravel())
img.filepath_raw = os.path.join(d, 'my_sky.hdr')
img.file_format = 'HDR'
img.save()
bpy.data.images.remove(img)
real_pref = workspace_ui.pref
workspace_ui.pref = lambda name, default=True: d if name == 'hdri_folder' else real_pref(name, default)
try:
    first = ms.hdri_icon('U:my_sky.hdr')
    check('An HDRI in the user\'s folder: no preview yet - it is queued (made off the draw)',
          first == '' and any(q[0].endswith('my_sky.hdr') for q in ms._THUMB_QUEUE), first)
    ms._thumb_tick()                                   # (what the timer does)
    icon = ms.hdri_icon('U:my_sky.hdr')
    ok = icon.startswith('file:') and os.path.isfile(icon[5:])
    size = None
    if ok:
        t = bpy.data.images.load(icon[5:])
        size = tuple(t.size)
        top = list(t.pixels[(size[1] - 2) * size[0] * 4 + size[0] * 2:(size[1] - 2) * size[0] * 4 + size[0] * 2 + 3])
        bpy.data.images.remove(t)
    check('... made once: a 256 x 128 picture in Blender\'s temporary folder (the user\'s folder not touched), the '
          'sky blue', ok and size == (256, 128) and top[2] > top[0]
          and os.path.dirname(icon[5:]) == ms.thumb_dir() and sorted(os.listdir(d)) == ['my_sky.hdr'],
          (icon, size))
    its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
    mine = [t for t in its if t.kind == 'htile' and t.label.startswith('*')]
    check('... the user\'s HDRI first in the previews (marked *), with its picture', mine and mine[0].icon == icon
          and [t for t in its if t.kind == 'htile'][0] is mine[0])
finally:
    workspace_ui.pref = real_pref

# the user's burlap photo as a weave map
check('Weave maps: Burlap (the user\'s photo, tiles)', ('BURLAP', 'Burlap') in ms.MAPS['weave'][3]
      and ms.map_path('weave', 'BURLAP') is not None)
bpy.ops.mch.mech_shader_apply(preset='CLOTH_BURLAP')
st = ob.active_material.mch_mech
check('Cloth Burlap preset: the Burlap weave, cloth on, coarse (Map Scale 0.5), its sphere icon',
      st.weave_map == 'BURLAP' and st.cloth == 1.0 and abs(st.map_scale - 0.5) < 1e-6
      and ob.active_material.node_tree.nodes['mch:img:weave'].image is not None
      and 'BURLAP' in ob.active_material.node_tree.nodes['mch:img:weave'].image.name.upper()
      and mu.icon('mat', 'CLOTH_BURLAP').startswith('file:'))
summary()
