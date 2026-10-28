"""0.24.81 "Sometimes Cut / Box Hide shows a yellow manifold warning and nothing is cut": a part that is not one
clean solid (open sides, edges shared by 3+ faces - most ZBrush / FBX parts) made the Boolean fail, and the only way
on was Fix Mesh by hand.  Cut / Split / line cut / Box Hide now run Fix Mesh on such a part by themselves first
(Preferences > Auto Fix Mesh before Cut, on) and say so; off: the warning as before."""
_src = open(__file__.replace('test_v02500_autofix.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
import bmesh
from mathutils import Quaternion
from mecha_lab import box_hide as bh, core_geometry as cg, cut_engine as ce, mesh_fix, workspace_ui as wu

S.mch_settings.auto_apply = True
S.mch_cut.targets = 'AUTO'
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)


def broken_part():
    """A cube with an inside wall (a face doubled inside: 4 edges shared by 3 faces) and one side face gone (an
    open rim) - the kind of part a Boolean refuses."""
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    ob = C.active_object
    ob.name = 'Body'
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=3, use_grid_fill=True)
    bm.faces.ensure_lookup_table()
    mid = [v for v in bm.verts if abs(v.co.x) < 1e-6]
    if len(mid) >= 4:                                   # an inside wall across the middle
        ring = sorted(mid, key=lambda v: (v.co.y, v.co.z))
        try:
            bmesh.ops.contextual_create(bm, geom=[e for e in bm.edges if e.verts[0] in mid and e.verts[1] in mid])
        except ValueError:
            pass
    top = max(bm.faces, key=lambda f: f.calc_center_median().z)
    bm.faces.remove(top)                                # an open side
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    C.view_layer.update()
    return ob


ob = broken_part()
counts0 = cg.overlap_edges(ob)
check('The test part is broken (edges shared by 3+ faces, open edges)', any(counts0), counts0)
square = [(450, 450), (700, 450), (700, 700), (450, 700)]          # x -0.5 .. 2 (the right part)
n0 = len(ob.data.polygons)
msg = ce.perform_closed(C, 'CUT', [ob], [square], TOP, False)
check('Cut on it: Fix Mesh runs first by itself, the cut goes through, the message says so',
      'Fix Mesh first' in msg and 'WARNING' not in msg and len(ob.data.polygons) != n0
      and not any(v.co.x > -0.45 and v.co.y > -0.45 for v in ob.data.vertices)
      and cg.non_manifold_edge_count(ob.data) == 0, msg[:160])

ob = broken_part()
msg = ce.perform_line(C, 'CUT', [ob], [(500, 300), (500, 700)], TOP, (300, 500), False)
xs = [v.co.x for v in ob.data.vertices]
check('A line cut on it too (one side kept, closed)', 'Fix Mesh first' in msg and (max(xs) < 0.01 or min(xs) > -0.01)
      and cg.non_manifold_edge_count(ob.data) == 0, (msg[:120], round(min(xs), 2), round(max(xs), 2)))

ob = broken_part()
S.mch_hide.cap = True
S.mch_hide.follow_symmetry = True
MODE[0], NATIVE[0] = 'HIDE', 'mecha.box_hide'
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
S.mch_settings.mch_active_tool = 'HIDE'
r, m = lasso([(550, 300), (700, 300), (700, 700), (550, 700)])
dg = C.evaluated_depsgraph_get()
dg.update()
me = ob.evaluated_get(dg).data
check('Box Hide on it: repaired first, something is hidden', bh.is_hidden(ob) and 'Fix Mesh first' in m
      and len(me.polygons) > 0 and max(v.co.x for v in me.vertices) < 0.6, (m[:120], len(me.polygons)))

real_pref = wu.pref
wu.pref = lambda name, default=True: False if name == 'auto_fix_mesh' else real_pref(name, default)
ob = broken_part()
try:
    msg = ce.perform_closed(C, 'CUT', [ob], [square], TOP, False)
except cg.CutError as ex:
    msg = 'CutError: ' + str(ex)
check('Preferences > Auto Fix Mesh off: not repaired (the warning / failure as before)', 'Fix Mesh first' not in msg
      and ('WARNING' in msg or 'CutError' in msg) and any(cg.overlap_edges(ob)), msg[:160])
wu.pref = real_pref
props = wu.MCH_AddonPreferences.bl_rna.properties
check('The preference exists, on by default', 'auto_fix_mesh' in props and props['auto_fix_mesh'].default is True)
summary()
