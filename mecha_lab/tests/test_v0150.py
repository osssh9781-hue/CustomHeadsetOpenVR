"""0.15.0: icon tiles back to pictures, floating side tool list, Station Up/Down +
Left/Right + Twist with ghost-style handles, dials follow the mouse, Polygon
Prism (sides, edge bevel / chamfer, segments at the ends, fold dot), primitive
HUD (+ / - / Apply / slider), coplanar-face warning."""
import math
import sys
import types

from _harness import bpy, bmesh, check, cube, fresh, non_manifold, select_only, summary, volume
from mathutils import Matrix, Quaternion, Vector

import mecha_lab
from mecha_lab import (bottom_bar as bb, primitive_hud as hud, primitive_place as pp, station_gizmos as sg,
                       station_primitive as sp, station_sweep as ss, tool_state as ts, workspace_ui as wui)

S = ss.station

# ---- engine: Up / Down + Left / Right at one station
old = ss.build(dict(kind='BOX', res=2, stations=[S(), S(length=1.0, bend_angle=40, bend_dir=90)]))
new = ss.build(dict(kind='BOX', res=2, stations=[S(), S(length=1.0, bend_side=40)]))
check('Left / Right 40 = the older "40 deg toward 90"', max((Vector(a) - Vector(b)).length
                                                            for a, b in zip(old['verts'], new['verts'])) < 1e-6)
both = ss.build(dict(kind='BOX', res=2, stations=[S(), S(length=1.0, bend_up=30, bend_side=30)]))
T = Vector(both['frames'][-1].T)
check('up AND sideways at the same station: the end points up and to the side', T.z > 0.3 and T.x > 0.3, T)
tw = ss.build(dict(kind='BOX', res=2, stations=[S(), S(length=1.0, twist=90)]))
check('twist turns the profile along the axis', abs(Vector(tw['frames'][-1].X).dot(Vector((0, 0, 1)))) > 0.99)

# ---- dials follow the mouse
check('a dial whose axis points away from the viewer is flipped', sg.facing(Vector((0, 0, 1)), Vector((0, 0, 1))) == -1.0
      and sg.facing(Vector((0, 0, 1)), Vector((0, 0, -1))) == 1.0)
d = pp.DialSession()
d.signs[2] = -1.0
q = d.turn(2, 0.3, Quaternion(), 5.0)
check('flipped ghost dial: the same mouse turn rotates the shape the other way round its axis',
      abs(q.rotation_difference(Quaternion((0, 0, 1), -0.3 * wui.dial_factor())).angle) < 1e-6)
F = wui.dial_factor()
d2 = pp.DialSession()
q_plain = d2.turn(2, 0.3, Quaternion(), 5.0)
check('0.18.2: a dial facing the viewer turns the shape the opposite way to the dial value (follows the mouse)',
      F == -1.0 and abs(q_plain.rotation_difference(Quaternion((0, 0, 1), -0.3)).angle) < 1e-6)
d.update_signs(Quaternion(), Vector((0, 0, -1)), 100.0)
check('ghost dial signs follow the view (Z faces a top view)', d.signs[2] == 1.0)
h = pp.place_handles(Vector(), Quaternion(), (1, 1, 1), signs={2: -1.0})
check('ghost Z dial drawn with its axis toward the viewer', h['RZ'].col[2].to_3d().z < -0.99)

# ---- side tool list: removed in 0.19.1 (user request)
check('side tool list removed', not hasattr(bb, 'side_tools'))
check('tooltips: any tool shows its name', bb.bar_tip('EXTRACT') == ts.TOOL_BY_ID['EXTRACT'][1])

fresh()
mecha_lab.register()
C = bpy.context
check('side tool list gone (0.19.1): no gizmo group, no preference', not hasattr(bb, 'MCH_GGT_side_toolbar') and
      'side_toolbar' not in wui.MCH_AddonPreferences.bl_rna.properties)
check('old left MECHA LAB TOOLS list folded', 'DEFAULT_CLOSED' in wui.MCH_PT_tool_list.bl_options)


class L:
    def __init__(self, log):
        self.log = log
        self.scale_y = 1.0

    def _c(self, *a, **k):
        return L(self.log)
    row = column = box = grid_flow = _c

    def operator(self, idname, **k):
        self.log.append(('op', idname, k.get('text'), 'icon_value' in k))
        return types.SimpleNamespace()

    def template_icon(self, **k):
        self.log.append(('picture', k.get('scale')))


log = []
ops = wui.icon_tile(L(log), 'cut', 'MOD_BOOLEAN', 'mch.set_tool', 'Cut', 2.0)
if wui.icon_id('cut'):
    check('icon tile: big picture + name button (no tall empty icon button)',
          len(ops) == 1 and log[0][0] == 'picture' and log[1] == ('op', 'mch.set_tool', 'Cut', False), log)
else:
    check('icon tile without icons: one button', len(ops) == 1)

# ---- Station: migrate, panel ops, Polygon Prism
bpy.ops.mch.station_create(preset='MULTI_BEND')
ob = C.active_object
p = ob.mch_station
check('presets use Up / Down now (older bend migrated, same shape)',
      all(abs(st.bend_angle) < 1e-9 for st in p.stations) and abs(p.stations[2].bend_up - 30) < 1e-6)
ref = ss.build(ss.preset('MULTI_BEND'))
check('migrated preset builds the identical shape', max((Vector(a) - Vector(b)).length for a, b in
                                                        zip(ref['verts'], ss.build(sp.spec_of(ob))['verts'])) < 1e-6)

bpy.ops.mch.station_create(preset='PRISM')
pr = C.active_object
pp_ = pr.mch_station
f0 = sp.station_frames(pr)
end_w = pr.matrix_world @ Vector(f0[-1][0])
start_w = pr.matrix_world @ Vector(f0[0][0])
check('Polygon Prism: square, standing up, closed', pp_.kind == 'NGON' and pp_.sides == 4 and
      end_w.z - start_w.z > 0.9 and non_manifold(pr) == 0)
n4 = len(pr.data.polygons)
pp_.sides = 64
check('Sides 64: almost a cylinder (closed)', non_manifold(pr) == 0 and len(pr.data.polygons) > n4)
pp_.sides = 6
nf = len(pr.data.polygons)
pp_.corner_finish, pp_.corner_width, pp_.corner_segments = 'BEVEL', 0.04, 3
check('side edges bevelled (closed, more faces)', non_manifold(pr) == 0 and len(pr.data.polygons) > nf + 6,
      (nf, len(pr.data.polygons)))
nb = len(pr.data.polygons)
pp_.cap_finish, pp_.cap_width = 'CHAMFER', 0.03
check('end edges chamfered too (closed)', non_manifold(pr) == 0 and len(pr.data.polygons) > nb)
pp_.corner_finish = pp_.cap_finish = 'NONE'
check('edge tags: along = side edge, ring rim = end edge',
      sp.edge_tag(3, 3 + 10, 10, 4) == sp.TAG_SIDE and sp.edge_tag(1, 2, 10, 4) == sp.TAG_END and
      sp.edge_tag(11, 12, 10, 4) == 0)
end0 = pr.matrix_world @ Vector(sp.station_frames(pr)[-1][0])
start0 = pr.matrix_world @ Vector(sp.station_frames(pr)[0][0])
bpy.ops.mch.station_segment(where='END', action='ADD')
end1 = pr.matrix_world @ Vector(sp.station_frames(pr)[-1][0])
check('+ at the end (top): one more segment, the end moves up, the start stays',
      len(pp_.stations) == 3 and end1.z > end0.z + 0.5 and
      (pr.matrix_world @ Vector(sp.station_frames(pr)[0][0]) - start0).length < 1e-5)
bpy.ops.mch.station_segment(where='START', action='ADD')
s1 = pr.matrix_world @ Vector(sp.station_frames(pr)[0][0])
check('+ at the start (bottom): the start moves down, the top stays', len(pp_.stations) == 4 and
      s1.z < start0.z - 0.5 and (pr.matrix_world @ Vector(sp.station_frames(pr)[-1][0]) - end1).length < 1e-5)
bpy.ops.mch.station_segment(where='START', action='REMOVE')
bpy.ops.mch.station_segment(where='END', action='REMOVE')
check('- at both ends: back to the first shape', len(pp_.stations) == 2 and
      (pr.matrix_world @ Vector(sp.station_frames(pr)[-1][0]) - end0).length < 1e-5 and
      (pr.matrix_world @ Vector(sp.station_frames(pr)[0][0]) - start0).length < 1e-5)
bpy.ops.mch.station_segment(where='END', action='ADD')
st = pp_.stations[2]
st.bend_up = 90
hh = sg.station_handles(pr)
check('a bent station gets a fold dot on the outside', [i for i, _m in hh['folds']] == [2])
levels = []
for _ in range(4):
    bpy.ops.mch.station_bend_cycle(index=2)
    levels.append(sp.bend_level(st))
check('fold dot: right angle -> soft -> rounder -> roundest -> right angle', sp.BEND_LEVELS and
      levels == [1, 2, 3, 0], levels)
check('the inside of the fold stays one closed piece at every level', non_manifold(pr) == 0)
st.bend_side = 40
check('fold up and sideways at once (closed)', non_manifold(pr) == 0 and not pp_.warnings, pp_.warnings)
bad = []
for n in (3, 4, 5, 6, 8, 12, 16, 33, 64):
    pp_.sides = n
    for lvl in range(4):
        bpy.ops.mch.station_bend_cycle(index=2)
        pp_.corner_finish = 'BEVEL' if lvl % 2 else 'NONE'
        if non_manifold(pr):
            bad.append((n, sp.bend_level(st), pp_.corner_finish))
pp_.corner_finish = 'NONE'
check('every number of sides x every fold shape (+ bevel) stays closed', not bad, bad)

# ---- HUD
lay = hud.hud_layout([(400, 300), (500, 300), (400, 400), (500, 400)], 1600, 900,
                     ends=((450, 250), (450, 450)))
check('HUD column right of the shape: + above - above Apply, slider under Apply',
      lay['add'][0] > 500 and lay['add'][1] > lay['sub'][1] > lay['apply'][1] > lay['slider'][1])
check('segment buttons outside the top and bottom ends', lay['end_add'][1] > 450 and lay['start_add'][1] < 250)
lay2 = hud.hud_layout([(1590, 450), (1600, 460)], 1600, 900)
check('HUD stays inside the viewport', lay2['add'][0] < 1600 - hud.SLIDER_W)
check('slider: whole steps, clamped', hud.slider_value(6, 3 * hud.STEP_PX, lo=3, hi=64) == 9 and
      hud.slider_value(6, -999, lo=3, hi=64) == 3)
spec = hud.slider_spec(C, 'STATION', pr)
check('slider on a polygon prism = Sides', spec[0] == 'Sides' and spec[2] == 3 and spec[3] == 64)
spec[4](12)
check('slider sets the sides', pp_.sides == 12 and non_manifold(pr) == 0)
st_ = pp.state(C)
st_.kind = 'CYLINDER'
check('slider on round ghost shapes = Segments', hud.slider_spec(C, 'GHOST', None)[0] == 'Segments')
st_.kind = 'BOX'
check('box ghost: no slider unless bevelled', hud.slider_spec(C, 'GHOST', None) is None)
check('HUD gizmos registered', 'bl_rna' in hud.MCH_GGT_prim_hud.__dict__ and
      'bl_rna' in hud.MCH_GT_hud_slider.__dict__)

# ---- Station Apply: + merges into the mesh, - carves out
fresh()
mecha_lab.register()
hull = cube('Hull', 2.0)
bpy.ops.mch.station_create(preset='PRISM')
pr = C.active_object
pr.location = (0, 0, 0.5)
C.view_layer.update()
v0 = volume(hull)
msg = hud.commit_station(C, pr, subtract=False)
check('Station Apply (+): merged into the mesh it touches, primitive gone',
      volume(hull) > v0 + 0.1 and 'Hull' in msg and 'MCH_Prism' not in [o.name for o in bpy.data.objects]
      and non_manifold(hull) == 0, (msg, volume(hull)))
bpy.ops.mch.station_create(preset='PRISM')
pr = C.active_object
pr.location = (0, 0, -0.5)
C.view_layer.update()
v1 = volume(hull)
hud.commit_station(C, pr, subtract=True)
check('Station Apply (-): carved out', volume(hull) < v1 - 0.1 and non_manifold(hull) == 0)
bpy.ops.mch.station_create(preset='PRISM')
pr = C.active_object
pr.location = (10, 0, 0)
C.view_layer.update()
msg = hud.commit_station(C, pr, subtract=False)
check('touching nothing: just applied', not sp.is_live(pr) and 'applied' in msg)
try:
    bpy.ops.mch.station_create(preset='PRISM')
    pr2 = C.active_object
    pr2.location = (20, 0, 0)
    C.view_layer.update()
    hud.commit_station(C, pr2, subtract=True)
    ok = False
except Exception as ex:
    ok = 'does not touch' in str(ex)
check('subtract touching nothing: clear message, nothing changed', ok and sp.is_live(pr2))

# ---- HUD mode: Enter / Apply subtract in - mode
fresh()
mecha_lab.register()
t = cube('T', 2.0)
select_only(t)
st_ = pp.state(C)
st_.placed = st_.show = True
st_.kind, st_.size, st_.location = 'BOX', (0.6, 0.6, 0.6), (0, 0, 1.0)
v0 = volume(t)
bpy.ops.mch.hud_mode(subtract=True)
bpy.ops.mch.place_commit(subtract=st_.mode_sub)
check('- mode: Apply carves', volume(t) < v0 - 0.05)

# ---- coplanar warning
m = Matrix.Identity(4)
verts, faces, smooth = pp.ghost_shape('BOX', (2, 2, 2))
from mathutils.bvhtree import BVHTree
dg = C.evaluated_depsgraph_get()
fresh()
mecha_lab.register()
same = cube('Same', 2.0)
bvh = pp._bvh_world(same, C.evaluated_depsgraph_get())[0]
bad = hud.coplanar_faces(m, verts, faces, smooth, [bvh], tol=0.008)
check('same-size box: every face lies on the mesh (warning)', len(bad) == 6, bad)
v2, f2, s2 = pp.ghost_shape('BOX', (2.2, 2.2, 2.2))
check('a bit bigger: no warning', hud.coplanar_faces(m, v2, f2, s2, [bvh], tol=0.008) == [])
v3, f3, s3 = pp.ghost_shape('BOX', (2.0, 2.0, 3.0))
check('same width, taller: only the four side faces warn', len(hud.coplanar_faces(m, v3, f3, s3, [bvh], tol=0.008)) == 4)
st_ = pp.state(C)
st_.placed = st_.show = True
st_.kind, st_.size, st_.location, st_.rotation = 'BOX', (2, 2, 2), (0, 0, 0), (1, 0, 0, 0)
check('cached check for the ghost finds the overlap', len(hud.coplanar_cached(C, st_, now=1e6)) == 6)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
