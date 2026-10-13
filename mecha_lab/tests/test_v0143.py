"""0.14.3: ghost primitive handles (move arrows, size squares, rotate dials,
uniform dots), top/bottom size + bevel/chamfer, ghost undo, ghost hidden until
a shape is picked, station handle undo steps, Base Mesh Stick to Surface,
clickable icon tiles, icon sizes kept across restarts."""
import math
import os
import sys
import types

from _harness import bpy, bmesh, check, cube, fresh, non_manifold, select_only, sphere, summary, volume
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import (base_mesh as bm_, core_geometry as cg, primitive_place as pp, station_gizmos as sg,
                       station_primitive as sp, workspace_ui as wui)


def closed(verts, faces):
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in verts]
    for f in faces:
        bm.faces.new([vs[i] for i in f])
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    vol = bm.calc_volume(signed=True)
    bm.free()
    return nm, vol


# ---- top / bottom size per axis
a, b, h = 2.0, 1.0, 1.0
for tx, ty in ((0.5, 0.5), (0.3, 1.0), (1.0, 0.0), (1.5, 0.8)):
    v, f, _s = pp.ghost_geometry('BOX', (a, b, h), 8, (tx, ty))
    nm, vol = closed(v, f)
    tx_, ty_ = max(tx, 1e-3), max(ty, 1e-3)     # one axis at 0 = a sharp ridge (kept a hair wide)
    expect = h / 6 * (a * b + a * tx_ * b * ty_ + (a + a * tx_) * (b + b * ty_))
    check(f'box top {tx} x {ty}: closed, volume = prismatoid formula', nm == 0 and abs(vol - expect) < 1e-6,
          (nm, vol, expect))
v, f, _s = pp.ghost_geometry('BOX', (a, b, h), 8, (0.0, 0.0))
nm, vol = closed(v, f)
check('box top 0 x 0 = pyramid', nm == 0 and abs(vol - a * b * h / 3) < 1e-6)
v, f, _s = pp.ghost_geometry('PILL', (3, 1, 1), 32, (0.5, 0.5))
check('pill can taper too (closed)', closed(v, f)[0] == 0 and closed(v, f)[1] > 0)
check('Cone keeps its pointed default', pp.top_factors('CONE') == (0.0, 0.0) and pp.top_factors('BOX') == (1.0, 1.0))

# ---- bevel / chamfer edges
v0, f0, _ = pp.ghost_shape('BOX', (1, 1, 1))
vb, fb, sb = pp.ghost_shape('BOX', (1, 1, 1), edge='BEVEL', width=0.1, edge_segments=3)
vc, fc, sc = pp.ghost_shape('BOX', (1, 1, 1), edge='CHAMFER', width=0.1)
nmb, volb = closed(vb, fb)
nmc, volc = closed(vc, fc)
check('Bevel: closed, more faces, a bit less volume, rounded faces smooth',
      nmb == 0 and len(fb) > len(f0) and 0.9 < volb < 1.0 and len(sb) > 0, (nmb, len(fb), volb))
check('Chamfer: closed, one flat cut per edge (6 + 12 + 8 faces)', nmc == 0 and len(fc) == 26 and volc < volb,
      (nmc, len(fc)))
vs, fs, _ = pp.ghost_shape('SPHERE', (1, 1, 1), 16, edge='BEVEL', width=0.1)
check('Bevel leaves a sphere alone (no sharp edges)', len(fs) == len(pp.ghost_geometry('SPHERE', (1, 1, 1), 16)[1]))
vcy, fcy, _ = pp.ghost_shape('CYLINDER', (1, 1, 1), 24, edge='BEVEL', width=0.05, edge_segments=2)
check('Bevel rounds only the cap rims of a cylinder (closed)', closed(vcy, fcy)[0] == 0 and len(fcy) > 26)

# ---- handles
rot = Quaternion((0, 0, 1), math.radians(30))
loc, size = Vector((1, 2, 0.5)), (2.0, 1.0, 0.5)
h1 = pp.place_handles(loc, rot, size)
new_loc = pp.move_along(loc, rot, size, 0, 1.0 + loc.dot(rot @ Vector((1, 0, 0))) + 1.0)
check('move arrow X: moves only along the shape X axis',
      abs((new_loc - loc).dot(rot @ Vector((0, 1, 0)))) < 1e-5 and abs((new_loc - loc).length - 1.0) < 1e-5)
h2 = pp.place_handles(new_loc, rot, size)
check('move arrow origin does not move while dragging along its axis (stable drag)',
      (h1['MX'].translation - h2['MX'].translation).length < 1e-5)
tip = h1['MX'].translation + h1['MX'].col[2].to_3d() * (loc.dot(rot @ Vector((1, 0, 0))) + size[0] / 2)
check('move arrow sits on the +X face', (tip - (loc + rot @ Vector((1.0, 0, 0)))).length < 1e-5)
check('size squares still start on the opposite face', (h1['X+'].translation - (loc + rot @ Vector((-1.0, 0, 0)))).length < 1e-5)
s2 = pp.uniform_size(size, Vector(size).length)            # double the half diagonal
check('corner dot: whole shape grows by the same factor', all(abs(x - 2 * y) < 1e-5 for x, y in zip(s2, size)))
check('corner dot points to the corner', (h1['U0'].col[2].to_3d() - (rot @ Vector(size)).normalized()).length < 1e-5)
check('three rotation dials on the shape axes', all(k in h1 for k in ('RX', 'RY', 'RZ')) and
      (h1['RZ'].col[2].to_3d() - rot @ Vector((0, 0, 1))).length < 1e-5)

d = pp.DialSession()
q = Quaternion()
q1 = d.turn(2, 0.2, q, 10.0)
q2 = d.turn(2, 0.5, q1, 10.1)
check('dial drag: rotation = start @ turn(value) (no drift)',
      abs(q2.rotation_difference(Quaternion((0, 0, 1), 0.5)).angle) < 1e-6)
check('dial keeps its start frame while dragging', d.frame(10.2) is not None and d.frame(20.0) is None)
check('a new drag starts from 0', d.value(2, 20.0) == 0.0)
q3 = d.turn(2, 0.1, q2, 20.0)
check('second drag adds to the first', abs(q3.rotation_difference(Quaternion((0, 0, 1), 0.6)).angle) < 1e-6)
q4 = d.turn(2, 0.15, q3, 25.0)
check('a pause mid-drag does not jump (value close to the last)',
      abs(q4.rotation_difference(Quaternion((0, 0, 1), 0.65)).angle) < 1e-6)

# ---- in Blender
fresh()
mecha_lab.register()
C = bpy.context
st = C.window_manager.mch_place
check('ghost hidden until a shape is picked', st.show is False)
C.scene.mch_settings.mch_active_tool = 'SUBD'
wui.activate_mecha_tool(C, 'PRIMITIVE')
check('entering the Primitive tool does not show the ghost', st.show is False)
bpy.ops.mch.place_shape(kind='CYLINDER')
check('picking a shape shows it', st.show is True and st.kind == 'CYLINDER')

# ghost history
pp.history_reset(st)
st.location = (0, 0, 0)
pp.settle(st)
pp.note_change(st, clock=100.0)
st.location = (1, 0, 0)
pp.note_change(st, clock=100.1)
st.location = (2, 0, 0)          # same drag
pp.settle(st)
pp.HISTORY['last'] = -1e9
pp.note_change(st, clock=200.0)
st.rotation = Quaternion((0, 0, 1), 0.5)
pp.settle(st)
pp.HISTORY['last'] = -1e9
check('two edits recorded (a drag = one step)', len(pp.HISTORY['undo']) == 2, len(pp.HISTORY['undo']))
pp.ghost_undo(st)
check('Ctrl+Z: rotation undone, position kept', abs(Quaternion(st.rotation).angle) < 1e-6 and
      abs(st.location[0] - 2) < 1e-6)
pp.ghost_undo(st)
check('Ctrl+Z again: the whole drag undone', abs(st.location[0]) < 1e-6)
pp.ghost_redo(st)
check('Ctrl+Shift+Z: redo', abs(st.location[0] - 2) < 1e-6)
keys = {(k[1]['type'], k[1].get('shift', False)) for k in pp.TOOL_KEYMAP if k[0] == 'mch.place_undo_key'}
check('Primitive tool keys: Ctrl+Z / Ctrl+Shift+Z for the ghost', keys == {('Z', False), ('Z', True)})

# commit: outline only right after Enter, history starts fresh, live Base Mesh frozen
t = cube('T', 2.0)
t.mch_base.outline = '{"groups": []}'
t.mch_base.live = False
select_only(t)
st.kind, st.size, st.location, st.rotation = 'BOX', (1, 1, 1), (0, 0, 1), (1, 0, 0, 0)
st.top_x = st.top_y = 1.0
st.edge = 'NONE'
t['_dummy'] = 1
t.mch_base['live'] = True                       # pretend: live Base Mesh (no rebuild)
res = bpy.ops.mch.place_commit()
check('merging into a live Base Mesh freezes it (a rebuild would wipe the merge)',
      res == {'FINISHED'} and not t.mch_base.live)
check('right after Enter the ghost is drawn as an outline only', pp.ghost_fill_alpha(st) == 0.0)
check('ghost history starts fresh after Enter (Ctrl+Z = undo the merge)', not pp.HISTORY['undo'])
st.location = (0, 0, 2)
check('moving the ghost brings the fill back', pp.ghost_fill_alpha(st) > 0)

# bevel / taper reach the real mesh
fresh()
mecha_lab.register()
st = C.window_manager.mch_place
st.placed = True
st.show = True
st.kind, st.size, st.location = 'BOX', (1, 1, 1), (5, 0, 0)
st.edge, st.edge_width, st.edge_segments = 'BEVEL', 0.1, 2
st.top_x, st.top_y = 0.6, 0.6
bpy.ops.mch.place_commit()
ob = C.active_object
check('new object gets the bevel and the taper (closed)', non_manifold(ob) == 0 and len(ob.data.polygons) > 6 and
      volume(ob) < 1.0 * 0.9, (len(ob.data.polygons), volume(ob)))

# station primitive: creating it hides the ghost; handle edits make undo steps
bpy.ops.mch.station_create(preset='PANEL')
check('creating a Station Primitive hides the ghost', st.show is False)
sg.UNDO['pending'] = False
get, set_ = sg.make_accessors(C.active_object.name, 1, 'length')
set_(get() + 0.2)
check('a handle drag marks an undo step', sg.UNDO['pending'])
check('no undo step while the drag goes on', sg.flush_handle_undo(now=sg.UNDO['last'] + 0.1) is False)
check('undo step pushed when the drag pauses / ends', sg.flush_handle_undo(now=sg.UNDO['last'] + 1.0) is True)

# ---- Base Mesh: Stick to Surface
TOP = cg.OrthoProjector(Quaternion())
fresh()
mecha_lab.register()
S = C.scene
slope = cube('Slope', 4.0)
slope.rotation_euler = (math.radians(30), 0, 0)
C.view_layer.update()
S.mch_base.profile, S.mch_base.height = 'FLAT', 0.2
rect = [[(450, 450), (550, 450), (550, 550), (450, 550)]]
msg = bm_.perform_base(C, rect, TOP)
ob = C.active_object
n = ob.matrix_world.col[2].to_3d().normalized()
face_n = slope.matrix_world.to_3x3() @ Vector((0, 0, 1))
check('drawn on a slope: the solid turns to the surface normal', n.dot(face_n.normalized()) > 0.999, n)
check('Stick to Surface sinks the bottom a little (no gap, no z-fighting)', ob.mch_base.embed > 0, ob.mch_base.embed)
dg = C.evaluated_depsgraph_get()
low = [ob.matrix_world @ v.co for v in ob.data.vertices if v.co.z < 0]
inside = 0
for p in low:
    hit, loc, nrm, _i, hob, _m = S.ray_cast(dg, p + n * 0.5, -n)
    if hit and hob.name == 'Slope' and (p - loc).dot(n) <= 1e-6:
        inside += 1
check('every bottom corner reaches into the surface', low and inside == len(low), (inside, len(low)))
check('still a closed live solid', non_manifold(ob) == 0 and ob.mch_base.live)
ob.mch_base.height = 0.3
check('embed survives live rebuilds', min(v.co.z for v in ob.data.vertices) < 0)
ball = sphere('Ball', loc=(10, 0, 0))
ball.scale = (2, 2, 2)
C.view_layer.update()
TOP2 = cg.OrthoProjector(Quaternion(), center=Vector((10, 0, 0)))
bm_.perform_base(C, [[(430, 430), (570, 430), (570, 570), (430, 570)]], TOP2)
ob2 = C.active_object
check('on a round surface the bottom sinks deeper (covers the curve)', ob2.mch_base.embed > 0.05, ob2.mch_base.embed)
S.mch_base.surface_align = False
bm_.perform_base(C, rect, TOP)
ob3 = C.active_object
check('Stick to Surface off: faces the view like before, no sink',
      ob3.matrix_world.col[2].to_3d().normalized().dot(Vector((0, 0, 1))) > 0.999 and ob3.mch_base.embed == 0)
S.mch_base.surface_align = True
bm_.perform_base(C, [[(50, 50), (100, 50), (100, 100), (50, 100)]], TOP)
check('nothing under the outline: faces the view', C.active_object.mch_base.embed == 0)

# ---- clickable icon tiles + left tool menu grid


class L:
    def __init__(self, log):
        self.log = log
        self.scale_y = 1.0

    def _c(self, *a, **k):
        if 'columns' in k:
            self.log.append(('grid', k['columns']))
        return L(self.log)
    row = column = box = grid_flow = _c

    def label(self, **k):
        pass

    def separator(self, **k):
        pass

    def operator(self, idname, **k):
        self.log.append(('op', idname, k.get('text'), 'icon_value' in k))
        return types.SimpleNamespace()

    def template_icon(self, **k):
        self.log.append(('picture',))


log = []
ops = wui.icon_tile(L(log), 'cut', 'MOD_BOOLEAN', 'mch.set_tool', 'Cut', 2.0)
has_icon = bool(wui.icon_id('cut'))
check('icon tile: the icon itself is a button (and the name too)',
      (len(ops) == 2 and ('op', 'mch.set_tool', '', True) in log) if has_icon else len(ops) == 1, log)
log.clear()
wui.MCH_PT_tool_list.draw(types.SimpleNamespace(layout=L(log)), C)
check('left tool menu = grid of tiles (columns follow the width)', ('grid', 0) in log and
      not any(e[0] == 'picture' for e in log), log[:4])

# ---- icon sizes kept across restarts (own small file, Blender prefs untouched)
fake = types.SimpleNamespace(icon_scale=1.7, toolbar_scale=1.3, handle_scale=2.2)
check('icon sizes saved to the add-on file', wui.save_sizes(fake) and os.path.isfile(wui.sizes_path()))
fake2 = types.SimpleNamespace(icon_scale=1.0, toolbar_scale=1.0, handle_scale=1.0)
check('icon sizes loaded back after a restart', wui.load_sizes(fake2) and abs(fake2.icon_scale - 1.7) < 1e-9 and
      abs(fake2.handle_scale - 2.2) < 1e-9)
check('the size file is in the user config folder, not Blender\'s preference file',
      os.path.basename(wui.sizes_path()) == 'ui_sizes.json' and 'mecha_lab' in wui.sizes_path())
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
