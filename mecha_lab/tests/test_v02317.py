"""0.23.17 Box Hide: fast (no Exact boolean - Manifold / Float, Open = delete inside), the Cut Depth / Targets
menu, orange outline."""
import sys
import time

_src = open(__file__.replace('test_v02317.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import box_hide as bh
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
MODE[0], NATIVE[0] = 'HIDE', 'mecha.box_hide'
S.mch_settings.mch_active_tool = 'HIDE'
check('outline is orange like Cut (also with Alt)', ce.stroke_color('HIDE', False) == ce.stroke_color('CUT', False) ==
      ce.stroke_color('HIDE', True))
g = bh.build_group()
check('no Exact boolean in the hide group', not any(n.bl_idname == 'GeometryNodeMeshBoolean' and n.solver == 'EXACT'
                                                      for n in g.nodes))
bpy.ops.mesh.primitive_uv_sphere_add(radius=2, segments=400, ring_count=250)
heavy = C.active_object
check('heavy test mesh (100k faces)', len(heavy.data.polygons) >= 99000, len(heavy.data.polygons))
S.mch_cut.targets = 'AUTO'


def timed_eval(ob):
    t0 = time.time()
    dg = C.evaluated_depsgraph_get()
    dg.update()
    me = ob.evaluated_get(dg).to_mesh()
    n = len(me.polygons)
    ob.evaluated_get(dg).to_mesh_clear()
    return time.time() - t0, n


r, m = lasso([(420, 420), (580, 420), (580, 580), (420, 580)])
for cap in (True, False):
    bh.set_cap(heavy, cap)
    heavy.data.update()
    dt, n = timed_eval(heavy)
    check(f'100k faces, Cap {"on" if cap else "off"}: evaluates in under 3 s (was 46 s with Exact)',
          dt < 3.0 and 0 < n < len(heavy.data.polygons), (round(dt, 2), n))
bpy.ops.mch.box_hide_show_all()
# Targets menu shared with Cut: Selected Only touches only the selected mesh
a = cube('A', 2.0)
a.location.x = -2.5
b = cube('B', 2.0)
b.location.x = 2.5
bpy.data.objects.remove(heavy)
C.view_layer.update()
S.mch_cut.targets = 'SELECTED'
select_only(a)
r, m = lasso([(100, 400), (900, 400), (900, 600), (100, 600)])          # over both cubes
check('Selected Only: only the selected mesh is hidden', bh.is_hidden(a) and not bh.is_hidden(b), (r, m))
bpy.ops.mch.box_hide_show_all()
S.mch_cut.targets = 'AUTO'
r, m = lasso([(100, 400), (900, 400), (900, 600), (100, 600)])
check('Auto Target: every mesh the shape covers', bh.is_hidden(a) and bh.is_hidden(b), (r, m))
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
