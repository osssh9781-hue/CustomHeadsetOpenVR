"""0.24.181 (user: "플레이트 디테일 되게 맘에 들어서 다른 프리셋도 좀 많이 만들어 주라 - 크리쳐 작업할 때 디테일 넣으려구 -
그리고 거기에 썸네일도 좀 만들어 줘, 그 다른 스케일 관련이나 깃털 같은 것도"): Plate Detail 4 has 15 creature presets
more (28), every preset, feather and scale its own picture (128 px, made by tools_dev/make_thumbs181.py), and the
pickers show them as picture tiles: Plate Detail 4's presets, the Fur window's Feathers / Scales, Scale Line / Feather
Line."""
import os
import struct

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import creature_shapes as cs, greeble_line as gl, panel_capture as pc, plate_detail as pd  # noqa
from mecha_lab import plate_rough as pr, skin_cover as sc  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
new = ('CROC', 'TURTLE', 'RHINO', 'ELEPHANT', 'LIZARD', 'SNAKE', 'CHITIN', 'SHARK', 'BONE', 'BARNACLE', 'DRAGON', 'FROG',
       'SCAR', 'ARMADILLO', 'CORAL')
check(f'Plate Detail 4: {len(pr.PRESETS)} presets - the 15 creature ones in ({all(p in pr.PRESET_IDS for p in new)})',
      len(pr.PRESETS) == 28 and all(p in pr.PRESET_IDS for p in new))


def png_size(path):
    with open(path, 'rb') as f:
        head = f.read(24)
    return struct.unpack('>II', head[16:24]) if head[:8] == b'\x89PNG\r\n\x1a\n' else None


missing, sizes, total = [], set(), 0
for kind, ids in (('rough', pr.PRESET_IDS), ('feather', [f[0] for f in cs.FEATHERS]), ('scale', [s[0] for s in cs.SCALES])):
    for sid in ids:
        path, _icon = pc.thumb(kind, sid)
        if not path:
            missing.append(f'{kind}_{sid}')
            continue
        sizes.add(png_size(path))
        total += os.path.getsize(path)
check(f'a picture for every preset / feather / scale ({28 + len(cs.FEATHERS) + len(cs.SCALES)}; missing {missing}), '
      f'128 px ({sizes}), small ({total // 1024} KB all)', not missing and sizes == {(128, 128)} and total < 900 * 1024)


def tiles_of(drawer):
    root = pc.capture(drawer, C)
    for n in pc.walk(root):
        if n.kind == 'tiles':
            return n.opts.get('tiles', ())
    return ()


t = tiles_of(lambda l_, c_: pd._draw_rough_presets(l_, 'CROC'))
check(f'Plate Detail 4\'s window: the presets as picture tiles ({len(t)}, each with its picture: '
      f'{all(e[1] for e in t)}; the one in use lit: {[e[0] for e in t if e[3]]})',
      len(t) == 28 and all(e[1] for e in t) and [e[0] for e in t if e[3]] == ['Croc Osteoderm']
      and all(e[4] == 'mch.pdetail_rough_preset' for e in t))
S.mch_cover.grow = 'FEATHERS'
tf = tiles_of(sc.draw)
S.mch_cover.grow = 'SCALES'
ts_ = tiles_of(sc.draw)
check(f'the Fur window\'s Feathers / Scales tabs: picture tiles ({len(tf)} / {len(ts_)})',
      len(tf) == len(cs.FEATHERS) and len(ts_) == len(cs.SCALES) and all(e[1] for e in tf + ts_))
tl_s = tiles_of(lambda l_, c_: gl.draw(l_, c_, kind='CREATURE'))
tl_f = tiles_of(lambda l_, c_: gl.draw(l_, c_, kind='FEATHER'))
check(f'Scale Line / Feather Line: picture tiles ({len(tl_s)} / {len(tl_f)})',
      len(tl_s) == len(cs.SCALES) and len(tl_f) == len(cs.FEATHERS) and all(e[1] for e in tl_s + tl_f))
r = bpy.ops.mch.pdetail_rough_preset(preset='DRAGON')
check(f'a tile\'s click (the preset\'s operator): Dragon Hide for the next plate ({r})',
      r == {'FINISHED'} and pd._fractions(S).get('r_preset') == 'DRAGON')
summary()
