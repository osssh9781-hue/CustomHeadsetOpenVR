"""v0.10.0 Deform tool: Lattice Cage + Bend Curve, point picking with falloff
Move / Rotate / Scale (headless).  The key requirement checked here: rotating or
scaling ONE control point around itself really deforms the surrounding mesh."""
import math
import sys

from _harness import bpy, bmesh, check, fresh, mesh_obj, select_only, summary
from mathutils import Euler, Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, deform_tools as dt

C = bpy.context


def bar(name='Bar', axis=0, loc=(0, 0, 0), rot=(0, 0, 0), length=4.0, cuts=24):
    def build(bm):
        bmesh.ops.create_cube(bm, size=1.0)
        s = [1.0, 1.0, 1.0]
        s[axis] = length
        bmesh.ops.scale(bm, vec=s, verts=bm.verts)
        long_edges = [e for e in bm.edges if abs(e.verts[0].co[axis] - e.verts[1].co[axis]) > 0.5]
        bmesh.ops.subdivide_edges(bm, edges=long_edges, cuts=cuts)
    ob = mesh_obj(name, build, loc)
    ob.rotation_euler = rot
    C.view_layer.update()
    return ob


def evaluated(ob):
    """Evaluated vertex positions in the object's LOCAL space."""
    dg = C.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    co = [v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return co


def max_err(a, b):
    return max((x - y).length for x, y in zip(a, b))


def world_points(lo):
    return [lo.matrix_world @ p.co_deform for p in lo.data.points]


def select_points(lo, indices):
    for i, p in enumerate(lo.data.points):
        p.select = i in indices


def lattice_index(lt, u, v, w):
    return u + v * lt.points_u + w * lt.points_u * lt.points_v


fresh()
mecha_lab.register()

# =============================================================================
# 1. Falloff math
# =============================================================================
check('weight 1 at the point', dt.falloff_weight(0.0, 1.0, 0.5) == 1.0)
check('weight 0 at the radius', dt.falloff_weight(1.0, 1.0, 0.5) == 0.0)
check('weight 0 beyond the radius', dt.falloff_weight(2.0, 1.0, 0.5) == 0.0)
lin, bell = dt.falloff_weight(0.25, 1.0, 0.0), dt.falloff_weight(0.25, 1.0, 1.0)
check('smoothness 0 = linear', abs(lin - 0.75) < 1e-9, lin)
check('smoothness 1 = smooth bell', abs(bell - 0.5 * (1 + math.cos(math.pi * 0.25))) < 1e-9, bell)
check('smoothness changes the curve', abs(lin - bell) > 0.05)
check('radius 0: only the point itself', dt.falloff_weight(0.01, 0.0, 0.5) == 0.0)
check('native falloff mapping', [dt.native_falloff(s) for s in (0.0, 0.3, 0.6, 1.0)] ==
      ['SHARP', 'LINEAR', 'SMOOTH', 'SPHERE'])

# =============================================================================
# 2. Lattice Cage: create, identity, resolution sliders
# =============================================================================
d = C.scene.mch_deform
ob = bar(loc=(1, 2, 3), rot=(0.2, 0.1, 0.3))
original = [v.co.copy() for v in ob.data.vertices]
select_only(ob)
d.res_x, d.res_y, d.res_z = 4, 4, 4
r = bpy.ops.mch.deform_add(kind='LATTICE', edit=False)
lo, _t = dt.controller(C)
check('lattice added', r == {'FINISHED'} and lo is not None and lo.type == 'LATTICE', r)
check('mesh got a Lattice modifier pointing at the cage',
      ob.modifiers.get(dt.MOD_LATTICE) is not None and ob.modifiers[dt.MOD_LATTICE].object == lo)
check('controller found from the mesh', dt.controller(C) == (lo, ob))
check('cage starts as identity', max_err(evaluated(ob), original) < 1e-4, max_err(evaluated(ob), original))
inv = lo.matrix_world.inverted() @ ob.matrix_world
inside = all(all(abs(c) <= 0.5 + 1e-6 for c in inv @ v.co) for v in ob.data.vertices)
check('cage encloses the mesh (rotated + offset object)', inside)
check('resolution 4x4x4', (lo.data.points_u, lo.data.points_v, lo.data.points_w) == (4, 4, 4))
p = lo.mch_deform
p.res_x = 6
check('Resolution X slider -> 6 points along X', lo.data.points_u == 6 and len(lo.data.points) == 6 * 4 * 4)
p.res_y = 3
check('Resolution Y slider independent', (lo.data.points_u, lo.data.points_v, lo.data.points_w) == (6, 3, 4))
p.res_z = 5
check('Resolution Z slider independent', (lo.data.points_u, lo.data.points_v, lo.data.points_w) == (6, 3, 5))
check('still identity after resolution changes', max_err(evaluated(ob), original) < 1e-4)

# =============================================================================
# 3. Edit Controller: native Proportional Editing synced and later restored
# =============================================================================
tsx = C.scene.tool_settings
tsx.use_proportional_edit = False
tsx.proportional_size = 3.21
tsx.proportional_edit_falloff = 'CONSTANT'
tsx.transform_pivot_point = 'BOUNDING_BOX_CENTER'
d.falloff_radius = 1.4
d.falloff_smoothness = 0.7
select_only(ob)
r = bpy.ops.mch.deform_edit()
check('Edit Controller -> lattice Edit Mode', r == {'FINISHED'} and C.mode == 'EDIT_LATTICE' and C.active_object == lo,
      C.mode)
check('proportional editing ON and synced', tsx.use_proportional_edit and abs(tsx.proportional_size - 1.4) < 1e-6
      and tsx.proportional_edit_falloff == 'SMOOTH' and tsx.transform_pivot_point == 'MEDIAN_POINT')
d.falloff_radius = 1.2
check('Falloff Radius slider updates Blender proportional size live', abs(tsx.proportional_size - 1.2) < 1e-6)
d.falloff_smoothness = 0.1
check('Falloff Smoothness slider updates Blender falloff live', tsx.proportional_edit_falloff == 'SHARP')
d.falloff_smoothness = 0.7

lt = lo.data
sel = lattice_index(lt, 5, 1, 4)    # +X end, middle in Y, top
far = lattice_index(lt, 0, 1, 0)    # -X end, bottom
radius = 1.2


def neighbours(pts, centre, rad):
    return [i for i, q in enumerate(pts) if 1e-6 < (q - centre).length < rad]


# --- single point ROTATE around itself --------------------------------------
select_points(lo, {sel})
before = world_points(lo)
mesh_before = evaluated(ob)
pivot = before[sel].copy()
r = bpy.ops.mch.deform_transform(mode='ROTATE', rot_axis=(0, 1, 0), angle=0.6, radius=radius, smoothness=0.7)
after = world_points(lo)
moved = [i for i in range(len(after)) if (after[i] - before[i]).length > 1e-6]
check('rotate single point: FINISHED', r == {'FINISHED'}, r)
check('rotate single point: the pivot point itself stays', (after[sel] - pivot).length < 1e-5)
nb = neighbours(before, pivot, radius)
check('rotate single point: neighbours inside the radius move', len(moved) > 0 and set(moved) <= set(nb),
      (len(moved), len(nb)))
check('rotate single point: points outside the radius do not move',
      all((after[i] - before[i]).length < 1e-6 for i in range(len(after)) if i not in nb))
check('rotate single point: neighbours keep their distance to the pivot (true rotation)',
      all(abs((after[i] - pivot).length - (before[i] - pivot).length) < 1e-5 for i in moved))
mesh_after = evaluated(ob)
moved_v = sum((a - b).length > 1e-5 for a, b in zip(mesh_after, mesh_before))
check('rotate single point: the MESH around it deforms', moved_v > 20, moved_v)
far_end = [i for i, v in enumerate(original) if v.x < -1.5]
check('rotate single point: far end of the mesh unchanged',
      max((mesh_after[i] - mesh_before[i]).length for i in far_end) < 1e-5)

# --- radius 0: a lone point rotating around itself changes nothing ---------
snap = dt.read_state(lo)
r = bpy.ops.mch.deform_transform(mode='ROTATE', rot_axis=(0, 1, 0), angle=0.6, radius=0.0, smoothness=0.7)
check('radius 0: single-point rotate has no effect (why falloff is needed)',
      max_err(world_points(lo), after) < 1e-6)

# --- single point SCALE around itself -----------------------------------------
before = world_points(lo)
mesh_before = evaluated(ob)
r = bpy.ops.mch.deform_transform(mode='SCALE', scale=(1.6, 1.6, 1.6), radius=radius, smoothness=0.7)
after = world_points(lo)
pivot = before[sel]
grown = [i for i in neighbours(before, pivot, radius)
         if (after[i] - pivot).length > (before[i] - pivot).length + 1e-5]
check('scale single point: pivot stays, neighbours pushed outward', (after[sel] - pivot).length < 1e-5 and grown,
      len(grown))
w_ok = True
for i in grown:
    w = dt.falloff_weight((before[i] - pivot).length, radius, 0.7)
    want = (before[i] - pivot).length * (1 + w * 0.6)
    w_ok &= abs((after[i] - pivot).length - want) < 1e-4
check('scale single point: displacement follows the falloff weight', w_ok)
check('scale single point: the MESH deforms', max_err(evaluated(ob), mesh_before) > 0.01)

# --- single point MOVE ---------------------------------------------------------
before = world_points(lo)
r = bpy.ops.mch.deform_transform(mode='MOVE', move=(0, 0, 0.4), radius=radius, smoothness=0.7)
after = world_points(lo)
check('move: selected point moves the full amount', abs((after[sel] - before[sel]).z - 0.4) < 1e-5)
ok = True
for i in neighbours(before, before[sel], radius):
    w = dt.falloff_weight((before[i] - before[sel]).length, radius, 0.7)
    ok &= abs((after[i] - before[i]).z - 0.4 * w) < 1e-5
check('move: neighbours move by weight x amount', ok)
check('move: far point untouched', (after[far] - before[far]).length < 1e-6)

# --- smoothness / radius are live (same op, different falloff) -----------------
state = dt.read_state(lo)
base_op = dt.op_from_settings(C, lo, state, 'MOVE')
base_op['move'] = (0, 0, 0.3)
results = {}
for s in (0.0, 1.0):
    dt.write_state(lo, state)
    dt.apply_falloff(lo, state, dict(base_op, radius=radius, smoothness=s))
    results[s] = world_points(lo)
dt.write_state(lo, state)
diff = max_err(results[0.0], results[1.0])
check('Falloff Smoothness changes the neighbours (live re-apply)', diff > 0.01, diff)
dt.apply_falloff(lo, state, dict(base_op, radius=radius * 2, smoothness=0.7))
wide = sum((a - b).length > 1e-6 for a, b in zip(world_points(lo), [lo.matrix_world @ c for c, _ in state['points']]))
dt.write_state(lo, state)
dt.apply_falloff(lo, state, dict(base_op, radius=radius * 0.5, smoothness=0.7))
narrow = sum((a - b).length > 1e-6 for a, b in zip(world_points(lo), [lo.matrix_world @ c for c, _ in state['points']]))
dt.write_state(lo, state)
check('Falloff Radius changes how many points follow', wide > narrow, (wide, narrow))
dt.apply_falloff(lo, state, dict(base_op, radius=radius, smoothness=0.7))
first = world_points(lo)
dt.write_state(lo, state)
dt.apply_falloff(lo, state, dict(base_op, radius=radius, smoothness=0.7))
check('re-applying from the same snapshot is deterministic (redo panel)', max_err(first, world_points(lo)) < 1e-9)
dt.write_state(lo, state)
check('snapshot restore (cancel) returns every point', max_err(world_points(lo),
      [lo.matrix_world @ c for c, _ in state['points']]) < 1e-9)

# --- several points at once ---------------------------------------------------
a_i, b_i = lattice_index(lt, 5, 0, 4), lattice_index(lt, 5, 2, 4)
select_points(lo, {a_i, b_i})
before = world_points(lo)
bpy.ops.mch.deform_transform(mode='MOVE', move=(0.3, 0, 0), radius=radius, smoothness=0.7)
after = world_points(lo)
check('multi-select move: both selected points move fully',
      all(abs((after[i] - before[i]).x - 0.3) < 1e-5 for i in (a_i, b_i)))
d.pivot = 'INDIVIDUAL'
before = world_points(lo)
bpy.ops.mch.deform_transform(mode='ROTATE', rot_axis=(1, 0, 0), angle=0.5, radius=radius, smoothness=0.7)
after = world_points(lo)
check('multi-select, pivot Each Point: each selected point rotates on itself (stays)',
      all((after[i] - before[i]).length < 1e-5 for i in (a_i, b_i)))
check('multi-select, pivot Each Point: neighbours move', max_err(after, before) > 1e-3)
d.pivot = 'MEDIAN'
before = world_points(lo)
bpy.ops.mch.deform_transform(mode='ROTATE', rot_axis=(1, 0, 0), angle=0.5, radius=radius, smoothness=0.7)
after = world_points(lo)
centre = (before[a_i] + before[b_i]) / 2
check('multi-select, pivot Selection Centre: selected points orbit their centre',
      all((after[i] - before[i]).length > 1e-3 and abs((after[i] - centre).length - (before[i] - centre).length) < 1e-5
          for i in (a_i, b_i)))

# --- step buttons -------------------------------------------------------------
select_points(lo, {sel})
before = world_points(lo)
d.step_angle = math.radians(15)
r = bpy.ops.mch.deform_step(mode='ROTATE', axis_index=2, sign=1)
check('step button Rotate Z+ deforms neighbours', r == {'FINISHED'} and max_err(world_points(lo), before) > 1e-3)
select_points(lo, set())
r = bpy.ops.mch.deform_step(mode='ROTATE', axis_index=2, sign=1)
check('nothing selected -> CANCELLED with a warning', r == {'CANCELLED'})

# --- Blender's own transform + Proportional Editing on a single point ----------
select_points(lo, {sel})
sync_size = tsx.proportional_size
before = world_points(lo)
mesh_before = evaluated(ob)
r = bpy.ops.transform.rotate(value=0.5, orient_axis='Z', orient_type='GLOBAL', center_override=before[sel],
                             use_proportional_edit=tsx.use_proportional_edit, proportional_size=sync_size,
                             proportional_edit_falloff=tsx.proportional_edit_falloff)
after = world_points(lo)
moved = [i for i in range(len(after)) if (after[i] - before[i]).length > 1e-6]
check('Blender rotate + proportional (synced size) on ONE point: neighbours rotate',
      r == {'FINISHED'} and moved and sel not in moved, (r, len(moved)))
check('Blender rotate + proportional: the mesh deforms', max_err(evaluated(ob), mesh_before) > 1e-3)
before = world_points(lo)
r = bpy.ops.transform.resize(value=(1.5, 1.5, 1.5), center_override=before[sel],
                             use_proportional_edit=True, proportional_size=sync_size,
                             proportional_edit_falloff=tsx.proportional_edit_falloff)
check('Blender scale + proportional on ONE point: neighbours scale', max_err(world_points(lo), before) > 1e-3)

# --- resolution change while editing keeps the shape ----------------------------
deformed = evaluated(ob)
amount = max_err(deformed, original)
p.res_x = 8
now = evaluated(ob)
check('resolution change in Edit Mode: back in Edit Mode, 8 points', C.mode == 'EDIT_LATTICE' and lt.points_u == 8)
check('resolution change keeps the deformation (re-sampled)', max_err(now, original) > 0.5 * amount and
      max_err(now, deformed) < 0.5 * amount, (round(max_err(now, original), 3), round(max_err(now, deformed), 3)))

# --- gizmo group poll -----------------------------------------------------------
select_points(lo, {sel})
d.gizmo_style = 'MECHA'
check('Mecha gizmo shows with a selected point', dt.MCH_GGT_deform.poll(C))
select_points(lo, set())
check('Mecha gizmo hidden without selection', not dt.MCH_GGT_deform.poll(C))
select_points(lo, {sel})
d.gizmo_style = 'BLENDER'
check('Mecha gizmo hidden in Blender gizmo style', not dt.MCH_GGT_deform.poll(C))
d.gizmo_style = 'MECHA'

# --- Done: settings restored, mesh still non-destructive ---------------------
r = bpy.ops.mch.deform_done()
check('Done Editing -> Object Mode, mesh active', r == {'FINISHED'} and C.mode == 'OBJECT' and C.active_object == ob)
check('your Proportional Editing settings are restored', not tsx.use_proportional_edit and
      abs(tsx.proportional_size - 3.21) < 1e-5 and tsx.proportional_edit_falloff == 'CONSTANT' and
      tsx.transform_pivot_point == 'BOUNDING_BOX_CENTER')
check('non-destructive: mesh data untouched', max_err([v.co for v in ob.data.vertices], original) < 1e-9)
kept = evaluated(ob)
r = bpy.ops.mch.deform_edit()
check('re-edit any time: back in Edit Mode, shape kept', r == {'FINISHED'} and C.mode == 'EDIT_LATTICE' and
      max_err(evaluated(ob), kept) < 1e-6)
bpy.ops.mch.deform_done()

# --- Apply ------------------------------------------------------------------------
final = evaluated(ob)
lt_name = lo.name
r = bpy.ops.mch.deform_apply()
check('Apply bakes exactly the evaluated shape', r == {'FINISHED'} and
      max_err([v.co for v in ob.data.vertices], final) < 1e-5)
check('Apply removes modifier and cage', ob.modifiers.get(dt.MOD_LATTICE) is None and lt_name not in bpy.data.objects)

# --- Remove (no apply) ---------------------------------------------------------
ob2 = bar('Bar2', loc=(0, 5, 0))
orig2 = [v.co.copy() for v in ob2.data.vertices]
select_only(ob2)
bpy.ops.mch.deform_add(kind='LATTICE', edit=True)
lo2 = C.active_object
select_points(lo2, {0})
bpy.ops.mch.deform_transform(mode='MOVE', move=(0, 0, -0.5), radius=1.0, smoothness=0.5)
check('add with "edit now" goes straight to Edit Mode', C.mode == 'EDIT_LATTICE')
r = bpy.ops.mch.deform_remove()
check('Remove: mesh back to original, cage gone', r == {'FINISHED'} and ob2.modifiers.get(dt.MOD_LATTICE) is None
      and max_err(evaluated(ob2), orig2) < 1e-6 and C.mode == 'OBJECT')

# --- one cage over several meshes --------------------------------------------
m1, m2 = bar('M1', loc=(0, 10, 0)), bar('M2', loc=(0, 12, 0))
select_only(m1, m2)
bpy.ops.mch.deform_add(kind='LATTICE', edit=False)
cage = m1.modifiers[dt.MOD_LATTICE].object
check('several selected meshes share one cage', cage is not None and m2.modifiers[dt.MOD_LATTICE].object == cage)
check('shared cage is identity for both', max_err(evaluated(m1), [v.co for v in m1.data.vertices]) < 1e-4 and
      max_err(evaluated(m2), [v.co for v in m2.data.vertices]) < 1e-4)

# =============================================================================
# 4. Bend Curve
# =============================================================================
for axis, rot in ((0, (0, 0, 0)), (1, (0, 0, 0)), (2, (0, 0, 0)), (0, (0.3, 0.5, 0.2))):
    o = bar(f'B{axis}', axis=axis, loc=(1, 2, 3), rot=rot)
    select_only(o)
    d.bend_axis = 'AUTO'
    d.bend_count = 5
    bpy.ops.mch.deform_add(kind='BEND', edit=False)
    err = max_err(evaluated(o), [v.co for v in o.data.vertices])
    check(f'Bend Curve identity on a mesh along {"XYZ"[axis]} (rot {rot})', err < 1e-4, err)

ob = bar('Twist', loc=(1, 2, 3), rot=(0.3, 0.5, 0.2), length=4.0, cuts=40)
orig = [v.co.copy() for v in ob.data.vertices]
select_only(ob)
bpy.ops.mch.deform_add(kind='BEND', edit=True)
cv = C.active_object
check('Bend Curve in Edit Mode', C.mode == 'EDIT_CURVE' and dt.role(cv) == 'BEND')
bps = cv.data.splines[0].bezier_points
check('5 control points', len(bps) == 5)
check('curve uses radius (scale = thickness) and keeps length', cv.data.use_radius and not cv.data.use_stretch)


def select_bend(indices):
    for i, bp in enumerate(bps):
        bp.select_control_point = bp.select_left_handle = bp.select_right_handle = i in indices


def section(co, x0, half=0.06):
    return [(i, c) for i, c in enumerate(co) if abs(orig[i].x - x0) < half]


def twist_angle(co, x0):
    """Mean rotation (degrees) of the cross-section at x0 around the bar axis."""
    angs = []
    for i, c in section(co, x0):
        o = orig[i]
        if math.hypot(o.y, o.z) < 0.3:
            continue
        a = math.atan2(c.z, c.y) - math.atan2(o.z, o.y)
        angs.append(math.degrees((a + math.pi) % (2 * math.pi) - math.pi))
    return sum(angs) / len(angs) if angs else 0.0


def half_width(co, x0):
    return max(math.hypot(c.y, c.z) for _i, c in section(co, x0))


d.falloff_radius = 1.5        # bar is 4 long, points 1 apart
d.falloff_smoothness = 0.7
d.pivot = 'MEDIAN'
d.orientation = 'AUTO'
mid = 2
select_bend({mid})
state = dt.read_state(cv)
basis = dt.orientation_basis(cv, state, 'AUTO')
tangent = dt.curve_tangent(cv, state, mid)
check('Auto orientation on a curve point: X = curve tangent', (basis.col[0] - tangent).length < 1e-5)

# --- rotate one point about the curve (X) = local twist -----------------------
d.step_angle = math.radians(40)
r = bpy.ops.mch.deform_step(mode='ROTATE', axis_index=0, sign=1)
co = evaluated(ob)
tilt = [round(math.degrees(bp.tilt), 2) for bp in bps]
check('rotate X on one Bend point: its tilt = +40°', r == {'FINISHED'} and abs(tilt[mid] - 40) < 1e-3, tilt)
check('neighbour tilts follow the falloff, ends 0', 0 < tilt[1] < 40 and 0 < tilt[3] < 40 and tilt[0] == tilt[4] == 0,
      tilt)
tw_mid, tw_end = twist_angle(co, 0.0), twist_angle(co, -1.95)
check('mesh cross-section at that point twists by ~40°', abs(tw_mid - 40) < 4, round(tw_mid, 2))
check('mesh end does not twist (local twist)', abs(tw_end) < 2, round(tw_end, 2))
check('twist keeps the section size', abs(half_width(co, 0.0) - half_width(orig, 0.0)) < 0.02)
bpy.ops.mch.deform_reset()
check('Reset Shape: straight again (identity)', max_err(evaluated(ob), orig) < 1e-4)

# --- rotate one point about a perpendicular axis = bend ---------------------------
select_bend({mid})
r = bpy.ops.mch.deform_step(mode='ROTATE', axis_index=2, sign=1)
co = evaluated(ob)
end_move = max((co[i] - orig[i]).length for i, _c in section(co, 1.95))
check('rotate Z on one Bend point: the mesh bends (end swings)', end_move > 0.2, round(end_move, 3))
check('bend rotation does not twist', abs(twist_angle(co, 0.0)) < 3)
bpy.ops.mch.deform_reset()

# --- scale one point = local thickness ---------------------------------------
select_bend({mid})
d.step_scale = 1.5
r = bpy.ops.mch.deform_step(mode='SCALE', axis_index=-1, sign=1)
co = evaluated(ob)
check('scale one Bend point: its radius = 1.5', abs(bps[mid].radius - 1.5) < 1e-4, bps[mid].radius)
check('mesh thicker at that point (~1.5x)', abs(half_width(co, 0.0) / half_width(orig, 0.0) - 1.5) < 0.08,
      round(half_width(co, 0.0) / half_width(orig, 0.0), 3))
check('mesh ends keep their thickness', abs(half_width(co, -1.95) / half_width(orig, -1.95) - 1.0) < 0.03)
bpy.ops.mch.deform_reset()

# --- move one point = bend with falloff -----------------------------------------
select_bend({mid})
up = cv.matrix_world.to_3x3() @ Vector((0, 0, 0.5))
bpy.ops.mch.deform_transform(mode='MOVE', move=up, radius=1.5, smoothness=0.7)
co = evaluated(ob)
mid_move = sum((co[i] - orig[i]).length for i, _c in section(co, 0.0)) / len(section(co, 0.0))
end_move = sum((co[i] - orig[i]).length for i, _c in section(co, -1.95)) / len(section(co, -1.95))
check('move one Bend point: middle of the mesh follows', mid_move > 0.3, round(mid_move, 3))
check('move one Bend point: ends move less', end_move < mid_move * 0.5, (round(end_move, 3), round(mid_move, 3)))

# --- resample the point count, shape kept ---------------------------------------
shape = evaluated(ob)
cv.mch_deform.bend_count = 9
check('Control Points slider -> 9 points (still Edit Mode)', len(cv.data.splines[0].bezier_points) == 9 and
      C.mode == 'EDIT_CURVE')
check('re-sampled curve keeps the bent shape', max_err(evaluated(ob), shape) < 0.08,
      round(max_err(evaluated(ob), shape), 4))
bps = cv.data.splines[0].bezier_points

# --- multi-select on the curve ----------------------------------------------------
select_bend({2, 6})
before = [cv.matrix_world @ bp.co for bp in bps]
bpy.ops.mch.deform_transform(mode='MOVE', move=(0, 0, 0.2), radius=0.6, smoothness=0.7)
after = [cv.matrix_world @ bp.co for bp in bps]
check('curve multi-select: both points move fully', all(abs((after[i] - before[i]).z - 0.2) < 1e-5 for i in (2, 6)))

# --- drag logic (simulated mouse, top view) -----------------------------------------
TOP = cg.OrthoProjector(Quaternion(), center=Vector((0, 0, 0)), pixels_per_unit=100.0)


class FakeDrag(dt.DragLogic):
    def to_screen(self, co):
        return Vector(TOP.to_screen(co))

    def view_toward(self):
        return Vector((0, 0, 1))

    def screen_delta_to_world(self, pivot, a, b):
        return Vector(((b[0] - a[0]) / 100.0, (b[1] - a[1]) / 100.0, 0.0))


bpy.ops.mch.deform_done()
q = bar('DragBar', loc=(0, 0, 0))
qo = [v.co.copy() for v in q.data.vertices]
select_only(q)
d.orientation = 'GLOBAL'
bpy.ops.mch.deform_add(kind='LATTICE', edit=True)
cage = C.active_object
k = lattice_index(cage.data, 3, 1, 3)
select_points(cage, {k})
pts0 = world_points(cage)
pv = pts0[k]
p2 = Vector(TOP.to_screen(pv))
drag = FakeDrag()
op = dt.op_from_settings(C, cage, dt.read_state(cage), 'ROTATE', 2)
op['radius'] = 1.5
check('drag begins on the selection', drag.drag_begin(cage, op, p2 + Vector((80, 0))))
drag.drag_update(p2 + Vector((0, 80)))
check('drag a quarter turn around the Z ring -> +90°', abs(math.degrees(drag.op['angle']) - 90) < 1e-3,
      math.degrees(drag.op['angle']))
pts1 = world_points(cage)
check('drag rotate: pivot point stays, neighbours rotate', (pts1[k] - pv).length < 1e-5 and max_err(pts1, pts0) > 0.01)
check('drag rotate: mesh deforms live', max_err(evaluated(q), qo) > 0.01)
drag.drag_cancel()
check('drag cancel (Esc/RMB): everything back', max_err(world_points(cage), pts0) < 1e-9 and
      max_err(evaluated(q), qo) < 1e-5)
op = dt.op_from_settings(C, cage, dt.read_state(cage), 'MOVE', 0)
op['radius'] = 1.5
drag.drag_begin(cage, op, p2)
drag.drag_update(p2 + Vector((50, 30)))
check('drag the X arrow 50 px -> move 0.5 along X only', abs((world_points(cage)[k] - pv).x - 0.5) < 1e-5 and
      abs((world_points(cage)[k] - pv).y) < 1e-6)
drag.drag_update(p2 + Vector((50, 30)), snap=True)
check('Ctrl snap while dragging', abs(Vector(drag.op['move']).x - 0.5) < 1e-6)
drag.drag_cancel()
op = dt.op_from_settings(C, cage, dt.read_state(cage), 'SCALE', -1)
op['radius'] = 1.5
drag.drag_begin(cage, op, p2 + Vector((40, 0)))
drag.drag_update(p2 + Vector((80, 0)))
check('drag the outer ring outward x2 -> uniform scale 2', all(abs(s - 2.0) < 1e-6 for s in drag.op['scale']))
check('drag scale on ONE point deforms the mesh', max_err(evaluated(q), qo) > 0.01)
drag.drag_cancel()
bpy.ops.mch.deform_done()

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
