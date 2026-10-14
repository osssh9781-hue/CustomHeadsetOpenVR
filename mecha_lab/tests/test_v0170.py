"""0.17.0 Random Panels: seeded layout of armour plates (clean new faces),
density / panel size / gap, edge pieces option, Mirror (Mecha Mirror), HUD."""
import json
import random
import sys

from _harness import bpy, check, cube, fresh, non_manifold, select_only, sphere, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import random_panels as rp

# ---- pure helpers
rng = random.Random(3)
centres = [Vector((x, y, 0)) for x in range(10) for y in range(10)]
areas = [1.0] * 100
seeds = rp.sample_seeds(centres, areas, 6, rng)
check('seeds picked from the surface', len(seeds) == 6 and all(s in centres for s in seeds))
relaxed = rp.lloyd(centres, areas, seeds, 3)
owner = rp.assign(centres, relaxed)
sizes = [owner.count(i) for i in range(6)]
check('Lloyd steps make the cells similar in size', max(sizes) <= 3 * max(1, min(sizes)), sizes)
square = [(x / 10.0, 0.0) for x in range(10)] + [(1.0, y / 10.0) for y in range(10)] + \
         [(1.0 - x / 10.0, 1.0) for x in range(10)] + [(0.0, 1.0 - y / 10.0) for y in range(10)]
out = rp.panel_outline(square, 0.02, 0.1)
check('panel outline: simplified to the corners, inset by half the gap',
      out is not None and len(out) == 4 and abs(min(p[0] for p in out) - 0.05) < 1e-6)
check('a gap bigger than the panel leaves nothing', rp.panel_outline(square, 0.02, 1.5) is None)
loop = [Vector((i, 0, 0)) for i in range(20)]
pieces = rp.edge_pieces(loop, [Vector((0, 0, 1))] * 20, random.Random(1), 0.5, 2.5)
check('edge pieces: short open chains along the border', pieces and all(2 <= len(p[0]) <= 5 for p in pieces))

# ---- in Blender
fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
box = cube('Hull', 4.0)                  # 6 faces only: the working copy is refined
select_only(box)
nv = len(box.data.vertices)
st = S.mch_random
st.seed, st.density, st.panel_size, st.gap = 7, 1.0, 0.25, 0.12
res = bpy.ops.mch.random_panels()
data = rp.session(C)
parts = [bpy.data.objects[n] for n in data['objects']]
check('Generate on a 6-face box: many separate plates, the box unchanged',
      res == {'FINISHED'} and len(parts) >= 8 and len(box.data.vertices) == nv, len(parts))
check('every plate is a closed live part', all(non_manifold(p) == 0 and p.mch_extract.is_part for p in parts))
check('plates are made of new faces (more than the box has)',
      sum(len(p.mch_extract.region.polygons) for p in parts) / len(parts) > 12)
check('mixed profiles: not all the same', len({(round(p.mch_extract.chamfer_width, 5), round(p.mch_extract.bevel_width, 5))
                                                for p in parts}) > 1)
layout_a = sorted(tuple(round(c, 3) for c in p.mch_extract.region.vertices[0].co) for p in parts)
n_full = len(parts)
st.density = 0.5
parts = [bpy.data.objects[n] for n in rp.session(C)['objects']]
check('Density 50 %: about half of the plates', 0.3 * n_full <= len(parts) <= 0.7 * n_full, (len(parts), n_full))
check('old plates removed when the layout is rebuilt', len([o for o in bpy.data.objects if o.name.startswith('Hull_Plate')])
      == len(parts))
st.density = 1.0
layout_b = sorted(tuple(round(c, 3) for c in bpy.data.objects[n].mch_extract.region.vertices[0].co)
                  for n in rp.session(C)['objects'])
check('same seed = same layout', layout_a == layout_b)
bpy.ops.mch.random_reroll()
layout_c = sorted(tuple(round(c, 3) for c in bpy.data.objects[n].mch_extract.region.vertices[0].co)
                  for n in rp.session(C)['objects'])
check('Reroll = next seed, new layout', st.seed == 8 and layout_c != layout_b)
st.panel_size = 0.12
check('smaller Panel Size: more plates', len(rp.session(C)['objects']) > n_full)
st.panel_size = 0.25
st.edges = True
objs = [bpy.data.objects[n] for n in rp.session(C)['objects']]
mold = [o for o in objs if getattr(o, 'mch_molding', None) and o.mch_molding.is_molding]
check('Edge Pieces option: one trim object with short pieces', len(mold) == 1 and len(mold[0].data.polygons) > 0)
st.edges = False
S.mch_mirror.x, S.mch_mirror.y, S.mch_mirror.z = True, False, False
S.mch_mirror.space = 'LOCAL'
st.mirror = True
objs = [bpy.data.objects[n] for n in rp.session(C)['objects']]
check('Mirror: every plate gets the Mecha Mirror modifier', objs and all(
    any(m.type == 'MIRROR' for m in o.modifiers) for o in objs))
check('Mirror: plates are made on one side only', all(
    all(v.co.x >= -1e-4 for v in o.mch_extract.region.vertices) for o in objs))
st.mirror = False
n = len(rp.session(C)['objects'])
res = bpy.ops.mch.random_finish(keep=True)
check('Apply: plates kept, layout closed', res == {'FINISHED'} and rp.session(C) is None and
      len([o for o in bpy.data.objects if o.name.startswith('Hull_Plate')]) == n)
bpy.ops.mch.random_panels()
k = len(rp.session(C)['objects'])
bpy.ops.mch.random_finish(keep=False)
check('Cancel: this layout removed, the applied plates stay',
      rp.session(C) is None and len([o for o in bpy.data.objects if o.name.startswith('Hull_Plate')]) == n and k > 0)

# Edit Mode faces only
fresh()
mecha_lab.register()
S = C.scene
box = cube('Hull', 4.0)
select_only(box)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='DESELECT')
bpy.ops.object.mode_set(mode='OBJECT')
top = max(box.data.polygons, key=lambda p: p.center.z)
top.select = True
bpy.ops.object.mode_set(mode='EDIT')
S.mch_random.density, S.mch_random.panel_size = 1.0, 0.25
bpy.ops.mch.random_panels()
objs = [bpy.data.objects[n] for n in rp.session(C)['objects']]
check('Edit Mode: panels only on the selected faces (the top)', objs and C.mode == 'OBJECT' and
      all(all(abs(v.co.z - 2.0) < 1e-3 for v in o.mch_extract.region.vertices) for o in objs))
rp.finish(C, keep=False)

# curved surface
ball = sphere('Ball', loc=(10, 0, 0))
ball.scale = (3, 3, 3)
C.view_layer.update()
select_only(ball)
S.mch_random.panel_size = 0.3
bpy.ops.mch.random_panels()
objs = [bpy.data.objects[n] for n in rp.session(C)['objects']]
check('sphere: plates follow the round surface, all closed', len(objs) >= 5 and all(non_manifold(o) == 0 for o in objs),
      len(objs))
lay = rp.hud_layout([(400, 300), (600, 500)], 1600, 900)
check('HUD right of the mesh: Reroll, Apply, Cancel, Edge Pieces, Mirror, then two sliders',
      lay['reroll'][0] > 600 and lay['reroll'][1] > lay['apply'][1] > lay['cancel'][1] > lay['mirror'][1] >
      lay['slider_density'][1] > lay['slider_panel_size'][1])
spec = rp.slider_spec(C, 'density')
spec[4](40)
check('slider sets the density (and rebuilds)', abs(S.mch_random.density - 0.4) < 1e-6 and rp.session(C) is not None)
check('HUD registered', 'bl_rna' in rp.MCH_GGT_random_hud.__dict__ and 'bl_rna' in rp.MCH_GT_random_slider.__dict__)
rp.finish(C, keep=False)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
