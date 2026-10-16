"""0.24.1 Sketch for Plate Detail 1 / 2 and Box Hide (draw several outlines, Enter applies once); Lift slider on
both details; Detail 2 edge Round (grows out of the surface) / Chamfer."""
import sys

_src = open(__file__.replace('test_v0241.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
import bmesh
import numpy as np

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
from mecha_lab import plate_detail as pd, lasso_sketch as ls, workspace_ui as wui

check('Detail 1 / 2 / Box Hide get the sketch keys', all(any(k[0] == 'mch.lasso_sketch_key' for k in wui._tool_keymap(m))
                                                         for m in ('DETAIL', 'DETAIL2', 'HIDE')))
MODE[0], NATIVE[0] = 'DETAIL', 'mecha.plate_detail'
S.mch_settings.mch_active_tool = 'DETAIL'
b = cube('B', 4.0)
ls.set_on(C, True)
lasso([(350, 350), (550, 350), (550, 550), (350, 550)])
lasso([(450, 450), (650, 450), (650, 650), (450, 650)])
check('Detail + sketch: outlines collected, no detail yet', not any(pd.is_detail(o) for o in bpy.data.objects) and
      len(ls.data(S)['items']) == 2)
res = bpy.ops.mch.lasso_sketch_commit()
d = C.active_object
check('Enter: one detail from the combined outline', res == {'FINISHED'} and pd.is_detail(d) and ls.data(S) is None)
co = np.array([v.co[:] for v in d.mch_pdetail.region.vertices])
check('... L-shaped union (covers both squares, not their bounding box)', co[:, 0].min() < -0.5 and co[:, 0].max() > 0.5)
z0 = max(v.co.z for v in d.data.vertices)
d.mch_pdetail.lift = 0.05
pd.rebuild(d)
pd._PENDING.clear()
check('Lift moves the detail along the normal', abs(max(v.co.z for v in d.data.vertices) - z0 - 0.05) < 1e-4)
d.mch_pdetail.lift = -0.01
pd.rebuild(d)
pd._PENDING.clear()
check('negative Lift sinks it', abs(max(v.co.z for v in d.data.vertices) - z0 + 0.01) < 1e-4)

# ---- Detail 2 with a sketch, Round / Chamfer
for o in list(bpy.data.objects):
    if o is not b:
        bpy.data.objects.remove(o)
MODE[0], NATIVE[0] = 'DETAIL2', 'mecha.plate_detail2'
S.mch_settings.mch_active_tool = 'DETAIL2'
lasso([(330, 330), (670, 330), (670, 670), (330, 670)])
lasso([(450, 450), (550, 450), (550, 550), (450, 550)], alt=True)
res = bpy.ops.mch.lasso_sketch_commit()
r = C.active_object
q = r.mch_pdetail
check('Detail 2 + sketch with a hole subtracted', res == {'FINISHED'} and pd.is_detail(r) and q.kind == 'RISE' and
      q.profile == 'ROUND')
t = np.linspace(0, 1, 11)
rc = pd.rise_curve(t, 'ROUND')
check('Round: flat at the foot and at the top (grows out of the surface)', rc[1] < 0.02 and rc[-2] > 0.98 and
      abs(rc[5] - 0.5) < 1e-6)
check('Chamfer: straight', np.allclose(pd.rise_curve(t, 'CHAMFER'), t))
me = r.data
foot_sharp = sum(1 for e in me.edges if e.use_edge_sharp)
check('foot edge kept sharp from the skirt (no dark seam)', foot_sharp > 0, foot_sharp)
q.profile = 'CHAMFER'
pd.rebuild(r)
pd._PENDING.clear()
check('Chamfer builds', len(r.data.polygons) > 0)
bpy.ops.mch.pdetail_rise_preset(preset='VERTICAL')
check('Vertical preset: chamfer, slope tiny next to the height', q.profile == 'CHAMFER' and q.ramp <= q.height * 0.05
      and len(r.data.polygons) > 0)
bpy.ops.mch.pdetail_rise_preset(preset='SLANT')
check('Slanted preset: chamfer, slope about a third of the height', q.profile == 'CHAMFER' and
      abs(q.ramp - q.height * 0.36) < 1e-6)
bpy.ops.mch.pdetail_rise_preset(preset='ROUND')
check('Round preset back', q.profile == 'ROUND')
pd._PENDING.clear()

# ---- Box Hide with a sketch
for o in list(bpy.data.objects):
    if o is not b:
        bpy.data.objects.remove(o)
MODE[0], NATIVE[0] = 'HIDE', 'mecha.box_hide'
S.mch_settings.mch_active_tool = 'HIDE'
lasso([(350, 350), (550, 350), (550, 550), (350, 550)])
lasso([(450, 450), (650, 450), (650, 650), (450, 650)])
n_mod = len(b.modifiers)
res = bpy.ops.mch.lasso_sketch_commit()
check('Box Hide + sketch: Enter hides once', res == {'FINISHED'} and len(b.modifiers) > n_mod and ls.data(S) is None)
ls.set_on(C, False)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
