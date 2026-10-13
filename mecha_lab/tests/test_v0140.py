"""0.14.0: ghost primitive placement (Enter = merge, Alt+Enter = subtract),
Pill Cylinder, stamp cursor at the mouse, toolbar names, Primitive panel grid."""
import math
import sys

from _harness import bpy, bmesh, check, cube, fresh, non_manifold, select_only, summary, volume
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import bottom_bar, core_geometry as cg, cut_engine, primitive_place as pp, tool_state as ts


def closed(verts, faces):
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in verts]
    for f in faces:
        bm.faces.new([vs[i] for i in f])
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    bm.normal_update()
    vol = bm.calc_volume(signed=True)
    bm.free()
    return nm, vol


SIZE = (2.0, 1.0, 0.6)
for kind in pp.KINDS:
    v, f, smooth = pp.ghost_geometry(kind, SIZE, 24, 0.4 if kind == 'CONE' else None)
    nm, vol = closed(v, f)
    ext = [max(p[i] for p in v) - min(p[i] for p in v) for i in range(3)]
    check(f'{kind}: closed shell with outward faces (volume {vol:.3f})', nm == 0 and vol > 0, (nm, vol))
    check(f'{kind}: extents follow the size {tuple(round(e, 3) for e in ext)}',
          all(abs(e - s) < 0.02 * s + 1e-6 for e, s in zip(ext, SIZE)), ext)
nm, vol = closed(*pp.ghost_geometry('CONE', SIZE, 24, 0.0)[:2])
check('pointed cone (Top Size 0) is closed', nm == 0 and vol > 0)

# Pill Cylinder: a cylinder whose round face is stretched
v, f, _s = pp.ghost_geometry('PILL', (3.0, 1.0, 0.5), 64)
_nm, vol = closed(v, f)
expect = ((3.0 - 1.0) * 1.0 + math.pi * 0.25) * 0.5
check('Pill Cylinder volume = straight middle + two half circles', abs(vol - expect) / expect < 0.01, (vol, expect))
loop = pp.stadium(32, 3.0, 1.0)
check('pill outline: straight sides at +-width/2 between the half circles',
      any(abs(y - 0.5) < 1e-9 and abs(x) <= 1.0 + 1e-9 for x, y in loop) and
      max(abs(y) for x, y in loop) <= 0.5 + 1e-9)
loop_y = pp.stadium(32, 1.0, 3.0)
check('pill also works the other way round (long side on Y)',
      abs(max(y for x, y in loop_y) - 1.5) < 1e-2 and abs(max(x for x, y in loop_y) - 0.5) < 1e-9)
v1, f1, _ = pp.ghost_geometry('PILL', (1.0, 1.0, 1.0), 32)
_nm, vol1 = closed(v1, f1)
check('pill with equal sides = round cylinder', abs(vol1 - math.pi * 0.25) < 0.02, vol1)
_v, _f, smooth = pp.ghost_geometry('CYLINDER', SIZE, 24)
check('cylinder: round side smooth, caps flat', len(smooth) == 24 and 0 not in smooth and 1 not in smooth)

# asymmetric resize: the dragged face moves, the opposite face stays
rot = Quaternion((0, 0, 1), math.radians(90))
loc, size = pp.resize_face((1, 2, 3), rot, (2, 1, 1), 0, 1, 3.0)
fixed_before = Vector((1, 2, 3)) + rot @ Vector((-1.0, 0, 0))
fixed_after = loc + rot @ Vector((-size[0] / 2, 0, 0))
check('resize +X: the -X face stays put (rotated ghost)', (fixed_before - fixed_after).length < 1e-6,
      (fixed_before, fixed_after))
check('resize +X: size grows to the dragged value', abs(size[0] - 3.0) < 1e-9 and size[1:] == [1, 1])
loc2, size2 = pp.resize_face((0, 0, 0), Quaternion(), (1, 1, 1), 2, -1, 0.0)
check('resize never goes below a minimum', size2[2] >= 1e-3 and loc2.z > 0)
h = pp.place_handles((1, 0, 0), Quaternion(), (2, 1, 1))
tip = h['X+'].translation + h['X+'].col[2].to_3d() * 2.0
check('X+ arrow starts on the -X face, its value (= size) reaches the +X face',
      (h['X+'].translation - Vector((0, 0, 0))).length < 1e-6 and (tip - Vector((2, 0, 0))).length < 1e-6)
check('Z- arrow points down from the top face',
      abs(h['Z-'].translation.z - 0.5) < 1e-6 and h['Z-'].col[2].to_3d().z < -0.99)
q = pp.align_rotation((0, 1, 0))
check('Align to Surface: Z axis follows the hit normal', (q @ Vector((0, 0, 1)) - Vector((0, 1, 0))).length < 1e-6)

# stamp cursor: drawn exactly at the mouse
check('PNG / built-in stamp preview is centred on the mouse (no region offset)',
      cut_engine.stamp_cursor_point((640, 360)) == (640.0, 360.0))

# toolbar tooltips = button names
check('toolbar tooltip is the button name + key', bottom_bar.bar_tip('CUT') == 'Cut  (C)' and
      bottom_bar.bar_tip('SPLIT') == 'Split' and bottom_bar.bar_tip('SELECT') == 'Select  (F)')

fresh()
mecha_lab.register()
C = bpy.context
wm = C.window_manager
from mecha_lab import workspace_ui as wui
check('names under the toolbar icons: on by default',
      wui.MechaLabPreferences.bl_rna.properties['toolbar_labels'].default is True
      if hasattr(wui, 'MechaLabPreferences') else
      any(getattr(c, 'bl_idname', '') == 'mecha_lab' or 'toolbar_labels' in getattr(c, '__annotations__', {})
          for c in vars(wui).values() if isinstance(c, type)))
check('toolbar operator describes itself by name', bpy.types.MCH_OT_bar_tool.description(C, type(
    'P', (), {'tool': 'BOOLEAN'})()) == 'Boolean  (B)')
check('Primitive is a real tool now (clicks / Enter reach the ghost)',
      ts.TOOL_BY_ID['PRIMITIVE'][5] == 'mecha.primitive' and ts.NATIVE_TO_TOOL.get('mecha.primitive') == 'PRIMITIVE')
keys = {(k[1]['type'], k[1].get('alt', False)): k for k in pp.TOOL_KEYMAP if k[0] == 'mch.place_key'}
check('Enter = add, Alt+Enter = subtract', ('RET', False) in keys and keys[('RET', True)][2]['properties'] ==
      [('subtract', True)])
st = wm.mch_place
check('ghost state on the WindowManager (not in the user file); hidden until a shape is picked',
      st is not None and st.kind == 'BOX' and st.show is False)

# ---- Enter: no mesh touched -> new object
st.location = (10, 0, 0)
st.placed = True
st.show = True
st.size = (1, 1, 1)
before = set(bpy.data.objects)
res = bpy.ops.mch.place_commit(subtract=False)
new = [o for o in bpy.data.objects if o not in before]
check('Enter on empty space: a new object, ghost kept', res == {'FINISHED'} and len(new) == 1 and
      non_manifold(new[0]) == 0 and abs(volume(new[0]) - 1.0) < 1e-4 and st.show)
check('no temporary cutter left behind', not [o for o in bpy.data.objects if o.name.startswith('MCH_Cutter')])

# ---- Enter: overlaps a cube -> merged into it (no new object)
fresh()
mecha_lab.register()
st = C.window_manager.mch_place
target = cube('Target', size=2.0)
select_only(target)
v0 = volume(target)
st.placed = True
st.kind = 'CYLINDER'
st.size = (1.0, 1.0, 1.0)
st.segments = 24
st.location = (0, 0, 1.0)            # half sunk into the top face
n_obj = len(bpy.data.objects)
res = bpy.ops.mch.place_commit(subtract=False)
v1 = volume(target)
check('Enter: merged into the mesh it overlaps (same object, more volume)',
      res == {'FINISHED'} and len(bpy.data.objects) == n_obj and v1 > v0 + 0.3 and non_manifold(target) == 0,
      (v0, v1))
# ---- Alt+Enter: subtract
st.kind = 'PILL'
st.size = (1.2, 0.5, 1.0)
st.location = (0, 0, -1.0)
v2 = volume(target)
res = bpy.ops.mch.place_commit(subtract=True)
v3 = volume(target)
expect = ((1.2 - 0.5) * 0.5 + math.pi * 0.0625) * 0.5
check('Alt+Enter: the pill is carved out (volume drops by the sunk half)',
      res == {'FINISHED'} and abs((v2 - v3) - expect) / expect < 0.05 and non_manifold(target) == 0,
      (v2 - v3, expect))
st.location = (20, 0, 0)
v4 = volume(target)
res = bpy.ops.mch.place_commit(subtract=True)
check('Alt+Enter touching nothing: nothing changes, clear message', res == {'CANCELLED'} and
      abs(volume(target) - v4) < 1e-9)
check('subtract flag resets after Enter', st.subtract is False)

# ---- union target choice: the active object first
fresh()
mecha_lab.register()
st = C.window_manager.mch_place
a = cube('A', size=2.0, loc=(-0.9, 0, 0))
b = cube('B', size=2.0, loc=(0.9, 0, 0))
select_only(b)
st.placed = True
st.kind = 'BOX'
st.size = (0.5, 0.5, 3.0)
st.location = (0, 0, 0)
cands = pp.overlapping_meshes(C, pp.ghost_matrix(st.location, st.rotation),
                              *pp.ghost_geometry('BOX', st.size)[:2])
check('both overlapping cubes are found', set(cands) == {a, b})
check('union goes into the ACTIVE object when it is touched', pp.pick_union_target(C, cands, (0, 0, 0)) == b)
inside = cube('Big', size=10.0, loc=(30, 0, 0))
st.location = (30, 0, 0)
cands = pp.overlapping_meshes(C, pp.ghost_matrix(st.location, st.rotation),
                              *pp.ghost_geometry('BOX', st.size)[:2])
check('a ghost fully inside a mesh still counts as overlapping', cands == [inside])

# ---- chamfer seam: only the new seam is bevelled
fresh()
mecha_lab.register()
st = C.window_manager.mch_place
hard = cube('Hard', size=2.0)
soft = cube('Soft', size=2.0, loc=(5, 0, 0))
st.placed = True
st.kind = 'BOX'
st.size = (1, 1, 1)
for ob, merge in ((hard, 'HARD'), (soft, 'CHAMFER')):
    select_only(ob)
    st.merge = merge
    st.finish_width = 0.05
    st.location = ob.location + Vector((0, 0, 1.0))
    bpy.ops.mch.place_commit(subtract=False)
check('Chamfer seam adds faces only along the seam (closed result)',
      len(soft.data.polygons) > len(hard.data.polygons) and non_manifold(soft) == 0,
      (len(hard.data.polygons), len(soft.data.polygons)))
check('cutter flag removed from the result', soft.data.attributes.get(cg.CUTTER_ATTR) is None)

# ---- live Station Primitive is frozen before merging
from mecha_lab import station_primitive as sp
bpy.ops.mch.station_create(preset='PANEL')
live = C.active_object
st.merge = 'HARD'
st.location = live.matrix_world @ Vector(live.bound_box[6])
res = bpy.ops.mch.place_commit(subtract=True)
check('subtract from a live Station Primitive freezes it first', res == {'FINISHED'} and not sp.is_live(live))

# ---- panel / picker draw without errors (layout API used correctly)
import types


class L:
    def __init__(self):
        self.calls = []
        self.scale_y = 1.0

    def _c(self, *a, **k):
        return L()
    row = column = box = grid_flow = _c

    def label(self, **k):
        pass

    def prop(self, data, name, **k):
        assert name in data.bl_rna.properties, name

    def operator(self, idname, **k):
        mod, op = idname.split('.')
        assert hasattr(getattr(bpy.ops, mod), op), idname
        return types.SimpleNamespace()

    def template_icon(self, **k):
        pass

    def separator(self, **k):
        pass

    def menu(self, *a, **k):
        pass

    def template_list(self, *a, **k):
        pass


try:
    pp.draw(L(), C)
    pp.draw_shape_grid(L(), 'mch.place_shape', 'PILL')
    bpy.types.MCH_PT_place_shapes.draw(types.SimpleNamespace(layout=L()), C)
    ok = True
except Exception as ex:
    import traceback
    traceback.print_exc()
    ok = False
check('ghost panel, shape grid and sidebar shapes panel draw', ok)
check('pill icon exists', bool(__import__('os').path.isfile(
    __import__('os').path.join(__import__('os').path.dirname(pp.__file__), 'icons', 'primitive_pill.png'))))
mecha_lab.unregister()
check('unregister removes the ghost state', not hasattr(bpy.types.WindowManager, 'mch_place'))
sys.exit(1 if summary() else 0)
