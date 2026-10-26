"""0.24.36 Box Hide draws with Line too (a band along the line is hidden); the Line button is greyed in tools where
it does nothing."""
_src = open(__file__.replace('test_v02451.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
import bmesh

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import box_hide as bh, lasso_line as ll
br = S.mch_brush
br.shape = 'LASSO'
br.line_open = False
MODE[0], NATIVE[0] = 'HIDE', 'mecha.box_hide'
S.mch_settings.mch_active_tool = 'HIDE'
check('Box Hide is a Line tool now', 'HIDE' in ll.MODES)


def ev_volume(ob):
    dg = C.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    v = bm.calc_volume()
    bm.free()
    ev.to_mesh_clear()
    return v


b = cube('B', 4.0)
br.line_mode = True
br.line_width = 0.5
br.line_caps = 'FLAT'
r, m = lasso([(300, 500), (700, 500)])
v = ev_volume(b)
check('Line: a 2-point line hides a band across the cube (Line Width 0.5 x 4 x 4 = 8 hidden)',
      'Hidden' in m and bh.is_hidden(b) and abs(v - (64.0 - 0.5 * 4 * 4)) < 1e-3, (r, m, round(v, 3)))
bpy.ops.mch.box_hide_show_all()
br.line_mode = False
summary()
