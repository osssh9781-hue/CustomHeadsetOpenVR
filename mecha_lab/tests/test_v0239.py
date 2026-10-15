"""0.23.9: Panel Cloth presets (padding + cloth families), the generated surface as the collider,
Sim right after the Cloth Plate lasso, redo with another preset, random per split piece, Seam split,
Remove Faces."""
import math
import sys

_src = open(__file__.replace('test_v0239.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
import numpy as np

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
from mecha_lab import cloth_sim as cs, cloth_wrinkle as cw, last_used
last_used.forget('wrinkle')
check('presets: padding family + cloth family', {'PADDING', 'PUFFER', 'PILLOW', 'QUILT'} <= set(cs.PRESET_IDS) and
      {'CLOTH', 'SILK', 'CANVAS', 'LEATHER', 'CRUMPLE'} <= set(cs.PRESET_IDS))
pv = cs.preset_values
check('padding presets puff (pressure), cloth presets do not puff and fold (shrink < 0)',
      all(pv(p)['pressure'] >= 7 for p in ('PADDING', 'PUFFER', 'PILLOW', 'QUILT')) and
      all(pv(p)['pressure'] <= 1.5 and pv(p)['shrink'] < 0 for p in ('CLOTH', 'SILK', 'CANVAS', 'LEATHER', 'CRUMPLE')))
check('padding stronger than 0.23.8 (pressure 4)', pv('PADDING')['pressure'] > 4.0 * 2)
check('Sim toggle + preset on the Cloth Plate settings', hasattr(S.mch_wrinkle, 'sim_after') and
      S.mch_wrinkle.sim_after is False and S.mch_wrinkle.sim_preset == 'PADDING')

# ---- lasso -> cloth plate -> Panel Cloth right away, the generated surface as collider
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
S.mch_settings.mch_active_tool = 'WRINKLE'
box = cube('Box', 4.0)
S.mch_wrinkle.sim_after = True
S.mch_wrinkle.sim_preset = 'PUFFER'
n_obj = len(bpy.data.objects)
r, m = lasso([(330, 330), (670, 330), (670, 670), (330, 670)])
pc = C.active_object
check('Sim after lasso: a baked _PCloth, the cloth layer hidden', r == {'FINISHED'} and cs.is_pcloth(pc) and
      'Panel Cloth (Puffer)' in m and pc.get('mch_pcloth_preset') == 'PUFFER', m)
src = bpy.data.objects[pc['mch_pcloth']]
check('the source cloth plate is kept (hidden)', cw.is_wrinkle(src) and src.hide_get() and src.hide_render)
check('the temporary region collider is gone, the body untouched', not any(o.name.endswith('_Collider')
                                                                            for o in bpy.data.objects)
      and not any(md.type == 'COLLISION' for md in box.modifiers) and len(bpy.data.objects) == n_obj + 2)
z = np.array([(pc.matrix_world @ v.co).z for v in pc.data.vertices])
check('puffed up above the box top, nothing sunk into it', z.max() > 2.15 and z.min() > 1.99,
      (round(float(z.min()), 3), round(float(z.max()), 3)))
h_puffer = z.max() - 2.0
# redo with a cloth preset
res = bpy.ops.mch.panel_cloth_redo(preset='CLOTH')
pc2 = C.active_object
z2 = np.array([(pc2.matrix_world @ v.co).z for v in pc2.data.vertices])
check('redo: the same source baked again with another preset (one cloth object, not two)',
      res == {'FINISHED'} and pc2.get('mch_pcloth_preset') == 'CLOTH' and
      len([o for o in bpy.data.objects if cs.is_pcloth(o)]) == 1)
check('Cloth preset: flatter than Puffer (folds, no puff)', z2.max() - 2.0 < h_puffer * 0.6,
      (round(float(z2.max() - 2.0), 3), round(float(h_puffer), 3)))
S.mch_wrinkle.sim_after = False

# ---- split + random per piece (quilt): every piece puffs on its own
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 20, 0))
cb = C.active_object
for o in C.selected_objects:
    o.select_set(False)
cb.select_set(True)
out = cs.panel_cloth(C, [cb], frames=8, pressure=6.0, cuts=2, split='ANGLE', angle=30.0, random_islands=True,
                     shrink=-0.05, shrink_max=-0.15, variation=0.5, collider='NONE', hide_source=False)
q = out[0]
import bmesh as _bm
bmq = _bm.new()
bmq.from_mesh(q.data)
seen, isl = set(), 0
for f0 in bmq.faces:
    if f0 in seen:
        continue
    isl += 1
    st_ = [f0]
    seen.add(f0)
    while st_:
        f = st_.pop()
        for e in f.edges:
            for g in e.link_faces:
                if g not in seen:
                    seen.add(g)
                    st_.append(g)
bmq.free()
check('Split Angle: a cube becomes 6 separate pieces', isl == 6, isl)
check('random per piece: the shrink / pressure groups are cleaned up after the bake',
      q.vertex_groups.get(cs.SHRINK_GROUP) is None and q.vertex_groups.get(cs.PRESSURE_GROUP) is None)
# seam split
bpy.ops.mesh.primitive_grid_add(x_subdivisions=8, y_subdivisions=8, size=2.0, location=(0, 30, 0))
gr = C.active_object
for e in gr.data.edges:
    a, b = (gr.data.vertices[i].co for i in e.vertices)
    if abs(a.x) < 1e-4 and abs(b.x) < 1e-4:
        e.use_seam = True
me, border, corners, w = cs.build_cloth_mesh([cs._world_faces_from_object(gr)], 0, 'SEAM')
nb = len(border)
me2, border2, _c, _w = cs.build_cloth_mesh([cs._world_faces_from_object(gr)], 0, 'NONE')
check('Split Seam: the marked seam opens (more border points)', nb > len(border2), (nb, len(border2)))
# remove faces (edit mode)
bpy.ops.mesh.primitive_grid_add(x_subdivisions=6, y_subdivisions=6, size=1.0, location=(0, 40, 0))
g = C.active_object
nf = len(g.data.polygons)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
res = bpy.ops.mch.panel_cloth(frames=4, cuts=1, collider='NONE', remove_faces=True)
check('Remove Faces: the selected faces leave the source mesh', res == {'FINISHED'} and len(g.data.polygons) == 0
      and nf > 0)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
