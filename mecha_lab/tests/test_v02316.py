"""0.23.16 Box Hide: draw over meshes to hide inside (non-destructive), Alt = show again, Cap / Open, Mirror X,
Show All, Apply."""
import sys

_src = open(__file__.replace('test_v02316.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
import bmesh

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import box_hide as bh, tool_state as ts
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
MODE[0], NATIVE[0] = 'HIDE', 'mecha.box_hide'
S.mch_settings.mch_active_tool = 'HIDE'
check('Box Hide is a tool (list, native tool, shapes)', 'HIDE' in ts.TOOL_BY_ID and ts.TOOL_BY_ID['HIDE'][5] == 'mecha.box_hide'
      and 'HIDE' in ts.SHAPE_TOOLS)


def ev_stats(ob):
    dg = C.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    v, nm, nf = bm.calc_volume(), sum(1 for e in bm.edges if not e.is_manifold), len(bm.faces)
    bm.free()
    ev.to_mesh_clear()
    return v, nm, nf


SQ = [(400, 400), (600, 400), (600, 600), (400, 600)]            # 2 x 2 through the 4-unit cube
b = cube('B', 4.0)
nv0 = len(b.data.vertices)
r, m = lasso(SQ)
v, nm, _nf = ev_stats(b)
check('hide: the part inside is gone, the cut is capped (closed)', r == {'FINISHED'} and abs(v - 48.0) < 1e-3 and nm == 0,
      (r, m, round(v, 3), nm))
check('... non-destructive: the mesh data is untouched, a hidden volume object holds the shape',
      len(b.data.vertices) == nv0 and bh.volume_of(b) is not None and not bh.volume_of(b).visible_get())
bpy.ops.mch.box_hide_cap(value=False)
v, nm, _nf = ev_stats(b)
check('Open (cap off): an open hole', nm > 0, nm)
bpy.ops.mch.box_hide_cap(value=True)
r, m = lasso(SQ, alt=True)
check('Alt + draw over the same place: shown again (nothing hidden left -> modifier removed)',
      r == {'FINISHED'} and not bh.is_hidden(b) and abs(ev_stats(b)[0] - 64.0) < 1e-3, (r, m))
r, m = lasso(SQ)
r, m = lasso([(300, 470), (700, 470), (700, 530), (300, 530)], alt=True)     # show a band again
v, nm, _nf = ev_stats(b)
check('Alt over part of the hidden area: only that part comes back', bh.is_hidden(b) and 48.0 + 1e-3 < v < 64.0 - 1e-3 and nm == 0,
      round(v, 3))
lasso([(500, 300), (700, 300), (700, 500), (500, 500)])                     # overlaps the first hide
v, nm, _nf = ev_stats(b)
check('two overlapping hides add up (the overlap counted once)', bh.is_hidden(b) and v < 52.8 - 1e-3 and nm == 0, round(v, 3))
bpy.ops.mch.box_hide_show_all()
check('Show All: everything back, the hide volume removed', not bh.is_hidden(b) and abs(ev_stats(b)[0] - 64.0) < 1e-3 and
      not any(o.get(bh.VOL_KEY) for o in bpy.data.objects))
S.mch_hide.mirror = True
r, m = lasso([(550, 400), (650, 400), (650, 600), (550, 600)])               # x 0.5 .. 1.5
v, nm, _nf = ev_stats(b)
check('Mirror X: the same part hidden on the other side too', abs(v - (64.0 - 2 * 8.0)) < 1e-3 and 'Mirror' in m, (round(v, 3), m))
S.mch_hide.mirror = False
res = bpy.ops.mch.box_hide_apply()
check('Apply: the hiding becomes real geometry, modifier and volume gone',
      res == {'FINISHED'} and not bh.is_hidden(b) and abs(volume(b) - 48.0) < 1e-3 and non_manifold(b) == 0 and
      not any(o.get(bh.VOL_KEY) for o in bpy.data.objects), round(volume(b), 3))
r, m = lasso([(10, 10), (60, 10), (60, 60), (10, 60)])
check('drawing over empty space: nothing changes, a clear message', r != {'FINISHED'} or 'nothing' in m.lower() or
      'cover' in m.lower(), (r, m))
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
