"""0.23.10: Panel Cloth sliders on the Cloth Plate panel (Gravity / Shrink / Pressure / Bend / Frames):
filled by the preset, used right after the lasso and by Re-bake; softer padding presets."""
import math
import sys

_src = open(__file__.replace('test_v02310.py', 'test_v0200.py')).read()
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
st = S.mch_wrinkle
check('sliders on the Cloth Plate settings', all(hasattr(st, k) for k in
      ('sim_gravity', 'sim_shrink', 'sim_pressure', 'sim_bend', 'sim_frames')))
st.sim_preset = 'CANVAS'
v = cs.preset_values('CANVAS')
check('picking a preset fills the sliders', abs(st.sim_gravity - v['gravity']) < 1e-6 and
      abs(st.sim_pressure - v['pressure']) < 1e-6 and st.sim_frames == v['frames'])
check('padding presets softer than 0.23.9', cs.preset_values('PADDING')['pressure'] <= 6.0 and
      cs.preset_values('PUFFER')['pressure'] <= 11.0)
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
S.mch_settings.mch_active_tool = 'WRINKLE'
box = cube('Box', 4.0)
st.sim_after = True
st.sim_preset = 'PADDING'


def top(o):
    return max((o.matrix_world @ v_.co).z for v_ in o.data.vertices) - 2.0


import time
t0 = time.time()
r, m = lasso([(330, 330), (670, 330), (670, 670), (330, 670)])
t_draft = time.time() - t0
pc = C.active_object
h1 = top(pc)
src = bpy.data.objects[pc['mch_pcloth']]
nf_draft = len(pc.data.polygons)
check('Sim on: the panel is made with bigger faces (Sim Face Size)', st.sim_face_px >= 20 and
      len(src.data.polygons) < 2500, len(src.data.polygons))
check('Detail 1 (Draft) by default: a light cloth', st.sim_detail == 1 and nf_draft <= cs.DETAIL_FACES[1] * 1.3,
      (nf_draft, round(t_draft, 1)))
st.sim_puff = 0.3
res = bpy.ops.mch.panel_cloth_redo(preset='PADDING', sliders=True)
pc2 = C.active_object
h2 = top(pc2)
check('Puff slider: 0.3 = much less puffed', res == {'FINISHED'} and h2 < h1 * 0.6, (round(h1, 3), round(h2, 3)))
st.sim_puff = 0.0
bpy.ops.mch.panel_cloth_redo(preset='PADDING', sliders=True)
check('Puff 0 = lies nearly flat', top(C.active_object) < h1 * 0.25, round(top(C.active_object), 3))
st.sim_puff = 1.0
st.sim_detail = 3
bpy.ops.mch.panel_cloth_redo(preset='PADDING', sliders=True)
nf3 = len(C.active_object.data.polygons)
check('raise Detail + Re-bake: finer cloth from the same source', nf3 > nf_draft * 2 and
      C.active_object.get('mch_pcloth_faces') == cs.DETAIL_FACES[3], (nf_draft, nf3))
res = bpy.ops.mch.panel_cloth_redo(preset='PUFFER')
check('a preset button fills the sliders from the preset, then bakes', res == {'FINISHED'} and
      st.sim_preset == 'PUFFER' and abs(st.sim_pressure - cs.preset_values('PUFFER')['pressure']) < 1e-6)
st.sim_detail = 1
# a too fine source is decimated down to the Detail budget
bpy.ops.mesh.primitive_grid_add(x_subdivisions=120, y_subdivisions=120, size=2.0, location=(0, 30, 0))
fine = C.active_object
out = cs.panel_cloth(C, [fine], frames=3, cuts=2, collider='NONE', max_faces=cs.DETAIL_FACES[1])
check('a fine source panel is decimated to the Detail budget', len(out[0].data.polygons) <= cs.DETAIL_FACES[1] * 1.2,
      len(out[0].data.polygons))
# faces face outward like the source (an open panel must not come out inside-out)
pcs = [o for o in bpy.data.objects if cs.is_pcloth(o) and o.name.startswith('Box')]
up = sum(p_.normal.z * p_.area for p_ in C.active_object.data.polygons) if pcs else 0
o = [o for o in bpy.data.objects if cs.is_pcloth(o)][0]
mw3 = o.matrix_world.to_3x3()
check('cloth on the box top faces up (outward), like its source', sum((mw3 @ p_.normal).z * p_.area
                                                                      for p_ in o.data.polygons) > 0)
import bmesh as _bm
bm = _bm.new()
_bm.ops.create_circle(bm, segments=24, radius=1.0)
bm.free()
# half cylinder, outward normals, but a winding recalc could flip it
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=1.0, depth=2.0, location=(0, 50, 0), end_fill_type='NOTHING')
hc = C.active_object
bmh = _bm.new()
bmh.from_mesh(hc.data)
_bm.ops.delete(bmh, geom=[f for f in bmh.faces if f.calc_center_median().y < 0], context='FACES')
bmh.to_mesh(hc.data)
bmh.free()
hc.data.update()
src_out = sum((p_.normal.y) * p_.area for p_ in hc.data.polygons)
out = cs.panel_cloth(C, [hc], frames=3, cuts=1, collider='NONE', pressure=0.0)
res_out = sum((out[0].matrix_world.to_3x3() @ p_.normal).y * p_.area for p_ in out[0].data.polygons)
check('open half cylinder: the cloth keeps the source orientation (outward)', src_out > 0 and res_out > 0,
      (round(src_out, 3), round(res_out, 3)))
st.sim_after = False
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
