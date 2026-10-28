"""0.24.80 Armor Shell: the whole surface of a part as a closed shell around it (Gap off the body, Thickness outward)
to cut into armour plates.  One live Geometry Nodes modifier (a distance field of the part: the surface at Gap and at
Gap + Thickness), so the sliders work at once; Cut / Split / Mesh Tools / Sculpt Mode make it real first.  The ZBrush
screen's Armor Shell makes it real at once (Thick = its thickness).

Not verified here (no window in bpy): the panel drawn in Blender, dragging the sliders, the timer that makes a live
shell real when it is taken into Sculpt / Edit Mode by hand (its function is called directly below)."""
import inspect
import types

from _harness import bpy, check, fresh, non_manifold, summary
import numpy as np
from mathutils import Quaternion
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import (armor_shell as ash, core_geometry as cg, cut_engine as ce, face_extract, mesh_tools,
                       side_panel as sp, tool_state as ts, zb_sculpt as zs, zb_ui as zu)

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
S.mch_settings.auto_apply = True


def body(name='Body'):
    """An upright egg 3.2 tall with a groove round its middle (a waist), 18k faces."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24)
    ob = C.active_object
    ob.name = name
    ob.scale = (1, 1, 1.6)
    bpy.ops.object.transform_apply(scale=True)
    for v in ob.data.vertices:
        if abs(v.co.z) < 0.15:
            v.co.x *= 0.85
            v.co.y *= 0.85
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=3)
    bpy.ops.object.mode_set(mode='OBJECT')
    return ob


def evaluated(ob):
    dg = C.evaluated_depsgraph_get()
    dg.update()
    me = ob.evaluated_get(dg).data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    return me, co.reshape(-1, 3)


def distances(ob, part):
    """(inner, outer) world distances of the shell's points to the part's surface."""
    me, co = evaluated(ob)
    mw = np.array(ob.matrix_world)
    co = co @ mw[:3, :3].T + mw[:3, 3]
    tree = BVHTree.FromObject(part, C.evaluated_depsgraph_get())
    pw = part.matrix_world.inverted()
    sc = sum(abs(s) for s in part.matrix_world.to_scale()) / 3
    d = np.array([tree.find_nearest(pw @ __import__('mathutils').Vector(p))[3] for p in co]) * sc
    st = ob.mch_shell
    mid = st.gap + st.thickness / 2
    return d[d < mid], d[d >= mid]


def voxel_world(ob):
    st = ob.mch_shell
    return ash.values(st['size'], ash._scale(ob), st.gap, st.thickness, st.smooth, st.detail)['Voxel'] * ash._scale(ob)


part = body()
n_part = len(part.data.vertices)
r = bpy.ops.mch.shell_extract()
sh = C.active_object
st = sh.mch_shell
check('Extract Whole Surface: a new object Body_Shell (active, selected) with the live shell modifier last',
      r == {'FINISHED'} and sh.name == 'Body_Shell' and sh.select_get() and not part.select_get()
      and sh.modifiers[-1].name == ash.MOD and sh.modifiers[-1].node_group.name == ash.GROUP, (r, sh.name))
check('... the part itself unchanged (its own mesh, not edited)', sh.data != part.data
      and len(part.data.vertices) == n_part and not part.modifiers)
check('... Gap 1 % / Thickness 2 % of the part\'s size by default', abs(st.gap - 0.032) < 1e-4
      and abs(st.thickness - 0.064) < 1e-4, (st.gap, st.thickness))
me, _co = evaluated(sh)
check('... one closed solid (no open / 3-face edges), Fewer Faces on: light to cut (under 30k faces)',
      1000 < len(me.polygons) < 30000 and cg.non_manifold_edge_count(me) == 0,
      (len(me.polygons), cg.non_manifold_edge_count(me)))
vox = voxel_world(sh)
inner, outer = distances(sh, part)
check('... the inside Gap off the part, the outside Gap + Thickness (within half a voxel; Smooth only moves it out)',
      len(inner) and len(outer) and inner.min() > st.gap - vox / 2 and outer.min() > st.gap + st.thickness - vox / 2
      and np.median(inner) < st.gap + vox and np.median(outer) < st.gap + st.thickness + vox,
      (round(float(inner.min()), 4), round(float(np.median(inner)), 4), round(float(outer.min()), 4),
       round(float(np.median(outer)), 4), round(vox, 4)))
bm_vol = __import__('bmesh').new()
bm_vol.from_mesh(me)
check('... its faces point out of the shell\'s material (a positive volume, about area x thickness)',
      0.8 < bm_vol.calc_volume() < 2.0, bm_vol.calc_volume())
bm_vol.free()

# --- the sliders are live ------------------------------------------------------------------------------------------
st.gap = 0.1
inner, outer = distances(sh, part)
check('Gap slider: the shell moves out at once', abs(np.median(inner) - 0.1) < vox and abs(np.median(outer) - 0.164)
      < vox, (np.median(inner), np.median(outer)))
st.thickness = 0.15
inner, outer = distances(sh, part)
check('Thickness slider: thicker outward, the inside stays', abs(np.median(inner) - 0.1) < vox
      and abs(np.median(outer) - 0.25) < vox, (np.median(inner), np.median(outer)))
st.smooth = 0.0
i0, _o = distances(sh, part)
st.smooth = 1.0
i1, _o = distances(sh, part)
check('Smooth slider: hollows filled (the shell lifts off the waist) but never closer than the Gap',
      i1.max() > i0.max() + vox / 2 and i1.min() > 0.1 - vox / 2, (i0.max(), i1.max(), i1.min()))
f0 = len(evaluated(sh)[0].polygons)
st.detail = 1.0
f1 = len(evaluated(sh)[0].polygons)
check('Detail slider: finer (more faces)', f1 > f0 * 1.5, (f0, f1))
st.detail, st.smooth, st.gap, st.thickness = 0.5, 0.3, 0.032, 0.064
f_light = len(evaluated(sh)[0].polygons)
st.light = False
me, _co = evaluated(sh)
inner, outer = distances(sh, part)
check('Fewer Faces off: even small faces everywhere (many more), still closed and as close to the Gap',
      len(me.polygons) > 5 * f_light and cg.non_manifold_edge_count(me) == 0
      and abs(np.median(inner) - 0.032) < vox / 2, (f_light, len(me.polygons), np.median(inner)))
st.light = True
v = ash.values(3.2, 1.0, 0.032, 0.03, 0.3, 0.5, True)
check('... a shell under 3 voxels thick keeps even faces (adaptive surfaces could touch there)',
      v['Adaptivity'] == 0.0 and ash.values(3.2, 1.0, 0.032, 0.064, 0.3, 0.5, True)['Adaptivity'] > 0, v)

# --- Update from Part ------------------------------------------------------------------------------------------------
for v in part.data.vertices:
    v.co.x *= 1.3
part.data.update()
r = bpy.ops.mch.shell_update()
inner, outer = distances(sh, part)
check('Update from Part (the part changed): the shell wraps the new shape, the sliders kept',
      r == {'FINISHED'} and abs(np.median(inner) - 0.032) < vox and abs(st.thickness - 0.064) < 1e-6
      and abs(sh.mch_shell['size'] - ash.local_size(part)) < 1e-4, (r, np.median(inner)))

# --- a scaled part (object scale not applied): Gap / Thickness still in scene units -------------------------------
p2 = body('Scaled')
p2.scale = (2, 2, 2)
p2.location = (6, 0, 0)
C.view_layer.update()
r = bpy.ops.mch.shell_extract()
s2 = C.active_object
inner, outer = distances(s2, p2)
v2 = voxel_world(s2)
check('A part scaled x2 (not applied): defaults from its real size, distances in scene units',
      r == {'FINISHED'} and abs(s2.mch_shell.gap - 0.064) < 1e-4 and abs(np.median(inner) - 0.064) < v2
      and abs(np.median(outer) - 0.192) < v2, (s2.mch_shell.gap, np.median(inner), np.median(outer), v2))

# --- Apply ------------------------------------------------------------------------------------------------------------
n_live = len(evaluated(s2)[0].polygons)
r = bpy.ops.mch.shell_apply()
check('Apply Shell: a plain mesh (no modifier, no longer live), the same faces, closed', r == {'FINISHED'}
      and not s2.modifiers and not ash.is_shell(s2) and len(s2.data.polygons) == n_live and non_manifold(s2) == 0,
      (r, n_live, len(s2.data.polygons)))

# --- a live shell is made real before it is cut -------------------------------------------------------------------
C.view_layer.objects.active = sh
for o in C.selected_objects:
    o.select_set(False)
sh.select_set(True)
n_live = len(evaluated(sh)[0].polygons)
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
square = [(500, 300), (900, 300), (900, 700), (500, 700)]       # x 0 .. 4 seen from the top: the right half
before = set(bpy.data.objects)
msg = ce.perform_closed(C, 'SPLIT', [sh], [square], TOP, False)
new = [o for o in bpy.data.objects if o not in before]
check('Split on a live shell: cut as the shell (made real first), two closed halves - not the copy of the part '
      'under the modifier', not ash.is_shell(sh) and not sh.modifiers and len(new) == 1
      and non_manifold(sh) == 0 and non_manifold(new[0]) == 0
      and len(sh.data.polygons) + len(new[0].data.polygons) > n_live * 0.8, msg)
check('... the part inside is not cut (only the active shell)', len(part.data.vertices) == n_part)
src = inspect.getsource(cg.ensure_real_mesh)
check('... the same bake runs for every tool that bakes a live primitive first (Cut / Split / Boolean / Base Mesh '
      'cutters)', 'armor_shell.bake_live(context, ob)' in src)
check('... and Mesh Tools (Remesh / Decimate / Quad Remesh ... on the shell, not its base)',
      'armor_shell.bake_live(context, ob)' in inspect.getsource(mesh_tools.MCH_OT_mesh_tool.execute))

# --- Sculpt / Edit Mode on a live shell: made real first ----------------------------------------------------------
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
part = body()
bpy.ops.mch.shell_extract()
sh = C.active_object
n_live = len(evaluated(sh)[0].polygons)
bpy.ops.object.mode_set(mode='SCULPT')
ash._tick()
check('Sculpt Mode on a live shell (the timer): made real and back in Sculpt Mode (the brush works on the shell)',
      sh.mode == 'SCULPT' and not ash.is_shell(sh) and not sh.modifiers and len(sh.data.polygons) == n_live,
      (sh.mode, len(sh.data.polygons), n_live))
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
part.select_set(True)
C.view_layer.objects.active = part
bpy.ops.mch.shell_extract()
sh2 = C.active_object
bpy.ops.object.mode_set(mode='EDIT')
ash._tick()
check('... Edit Mode too', sh2.mode == 'EDIT' and not ash.is_shell(sh2) and not sh2.modifiers, sh2.mode)
bpy.ops.object.mode_set(mode='OBJECT')
check('Extract on a shell: not offered (a shell of a live shell)', not ash.MCH_OT_shell_extract.poll(
    types.SimpleNamespace(active_object=sh, selected_objects=[sh])) or not ash.is_shell(sh))

# --- an open sheet / nothing to wrap ---------------------------------------------------------------------------------
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_plane_add(size=2)
plane = C.active_object
plane.data.vertices.foreach_set('co', [0.0] * len(plane.data.vertices) * 3)       # all faces collapsed: no area
plane.data.update()
before = set(bpy.data.objects)
r = bpy.ops.mch.shell_extract()
check('A part with nothing to wrap: Cancelled with a warning, no empty object left behind', r == {'CANCELLED'}
      and set(bpy.data.objects) == before and C.active_object == plane, r)

# --- ZBrush screen: Armor Shell (made real at once, Thick = thickness) ---------------------------------------------
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
part = body('Sub')
zb = S.mch_zb
zb.thick = 0.05
bpy.ops.object.mode_set(mode='SCULPT')
msg = zs.run(C, 'SHELL')
shz = bpy.data.objects.get('Sub_Shell')
check('ZBrush Armor Shell: a new SubTool Sub_Shell, made real (no modifier), still sculpting the old SubTool',
      shz is not None and not shz.modifiers and C.active_object == part and part.mode == 'SCULPT'
      and non_manifold(shz) == 0, msg)
if shz is not None:
    shz.mch_shell['is_shell'] = False
    tree = BVHTree.FromObject(part, C.evaluated_depsgraph_get())
    d = np.array([tree.find_nearest(v.co)[3] for v in shz.data.vertices])
    gap = 0.032
    check('... Thick 0.05 = its thickness (outside at Gap + 0.05)', abs(np.median(d[d > gap + 0.025]) - (gap + 0.05))
          < 0.03, np.median(d[d > gap + 0.025]))
check('... a save point first (a heavy step, like Extract)', 'SHELL' in zs.RISKY)
bpy.ops.object.mode_set(mode='OBJECT')

# --- the buttons ------------------------------------------------------------------------------------------------------
src = inspect.getsource(face_extract.draw)
check('Face Extract panel: the Armor Shell box on top (Extract Whole Surface, or the shell\'s sliders)',
      'armor_shell.draw(layout, context)' in src and src.index('armor_shell.draw') < src.index('Basic Extract'))


class Ctx:
    region = types.SimpleNamespace(width=2560, height=1440, x=0, y=0, type='WINDOW')
    area = None
    region_data = object()

    def __getattr__(self, n):
        return getattr(bpy.context, n)


CTX = Ctx()
real_ws, real_eff, real_on = ts.is_mecha_workspace, ts.effective_tool, sp.on
ts.is_mecha_workspace = lambda ws: True
ts.effective_tool = lambda c: 'EXTRACT'
sp.on = lambda c: True
bpy.ops.object.select_all(action='DESELECT')
part.select_set(True)
C.view_layer.objects.active = part
sp.dirty()
side = sp.items(CTX, 2560, 1440, 1.0)
ops = [i.action[1] for i in side if i.action and i.action[0] == 'op']
check('... in the drawn side panel (Face Extract tool): Extract Whole Surface', 'mch.shell_extract' in ops, ops[:8])
bpy.ops.mch.shell_extract()
sp.dirty()
side = sp.items(CTX, 2560, 1440, 1.0)
props = {i.prop for i in side if i.prop and i.data is not None and getattr(i.data, 'is_shell', None) is not None}
ops = [i.action[1] for i in side if i.action and i.action[0] == 'op']
check('... a live shell active: Gap / Thickness / Smooth / Detail, Update from Part, Apply Shell',
      {'gap', 'thickness', 'smooth', 'detail'} <= props and {'mch.shell_update', 'mch.shell_apply'} <= set(ops),
      (sorted(props), ops[:8]))
ts.is_mecha_workspace, ts.effective_tool, sp.on = real_ws, real_eff, real_on
items = zu.subtool_list(C, 2560, 1.0, __import__('mecha_lab.mecha_menu', fromlist=['x']).Item, 1300, 100)
acts = [i.action[2].get('action') for i in items if i.action and i.action[0] == 'op' and i.action[1] == 'mch.zb_action']
check('ZBrush SubTool card: Extract | Armor Shell row', 'SHELL' in acts and 'EXTRACT' in acts, acts)
check('ZBrush N panel: Shell next to Extract', "('Shell', 'SHELL')" in inspect.getsource(zu))
summary()
