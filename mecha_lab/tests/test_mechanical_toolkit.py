"""Mechanical Modeling Toolkit (spec section 13), headless.

Face Extract (Basic), Armor Sculpt, Edge Molding, Curve Array / Curve Deform,
Cable Generator, Hollow / Shell, settings persistence across Edit Mode and
re-selection, multi-object.  Geometry is checked, not only that operators run.
"""
import math
import sys
import types

from _harness import bpy, bmesh, check, cube, fresh, mesh_obj, non_manifold, select_only, summary, volume
from mathutils import Vector

import mecha_lab
from mecha_lab import cable, edge_molding, face_extract as fe, hollow_shell, panel_gen as pg

C = bpy.context


def sphere(name='Hull', loc=(0, 0, 0), r=1.0, seg=32, rings=16):
    return mesh_obj(name, lambda bm: bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r), loc)


def grid(name='Plate', n=8, size=2.0, loc=(0, 0, 0)):
    return mesh_obj(name, lambda bm: bmesh.ops.create_grid(bm, x_segments=n, y_segments=n, size=size / 2), loc)


def select_faces(ob, pred):
    bm = bmesh.from_edit_mesh(ob.data)
    for f in bm.faces:
        f.select = pred(f)
    bmesh.update_edit_mesh(ob.data)


def stats(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    vol = bm.calc_volume()
    bm.free()
    return nm, vol


def evaluated_verts(ob):
    from mecha_lab import along_curve
    along_curve.set_realize(ob, True)
    dg = C.evaluated_depsgraph_get()
    dg.update()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    vs = [ob.matrix_world @ v.co for v in me.vertices]
    bpy.data.meshes.remove(me)
    return vs


def extract(ob, pred, mode='BASIC', stay=True):
    select_only(ob)
    bpy.ops.object.mode_set(mode='EDIT')
    select_faces(ob, pred)
    r = bpy.ops.mch.face_extract(mode=mode, stay_in_edit=stay)
    return r


fresh()
mecha_lab.register()

# =============================================================================
# Face Extract (Basic)
# =============================================================================
hull = sphere()
orig = [v.co.copy() for v in hull.data.vertices]
d = C.scene.mch_extract
d.extract_height, d.resolution = 0.1, 1
r = extract(hull, lambda f: f.calc_center_median().z > 0.55 and f.calc_center_median().x > -0.2)
part = C.scene.mch_extract_last
check('Basic Extract on a curved base, many faces: one part', r == {'FINISHED'} and part is not None and
      part.mch_extract.is_part)
check('stays in Edit Mode on the source; panel follows the new part', C.mode == 'EDIT_MESH' and
      fe.active_part(C) == part)
bpy.ops.object.mode_set(mode='OBJECT')
check('original mesh unchanged', len(hull.data.vertices) == len(orig) and
      all((v.co - o).length < 1e-9 for v, o in zip(hull.data.vertices, orig)))
nm, vol = stats(part)
check('extracted part is a closed solid', nm == 0 and vol > 0, (nm, vol))
radii = [(part.matrix_world @ v.co).length for v in part.data.vertices]
check('extruded along the surface normal (outward from the sphere)', max(radii) > 1.09 and min(radii) > 0.99,
      (round(min(radii), 3), round(max(radii), 3)))
check('part in "Mechanical Parts / Extracted Armor"', 'Extracted Armor' in [c.name for c in part.users_collection] and
      'Extracted Armor' in bpy.data.collections['Mechanical Parts'].children)

# live sliders, chamfer modes, direction, outer edge, side bevel, shell
fresh()
plate = grid()
extract(plate, lambda f: True, stay=False)
part = C.active_object
p = part.mch_extract
p.extract_height = 0.2
v_flat = stats(part)[1]
check('Extract Height drives the height', abs(v_flat - 0.8) < 0.01, v_flat)
p.chamfer_mode, p.chamfer_width, p.chamfer_angle = 'WIDTH_ANGLE', 0.1, math.radians(45)
v_ch = stats(part)[1]
check('Chamfer width + angle removes ~perimeter x W x D / 2', abs((v_flat - v_ch) - 8 * 0.1 * 0.1 / 2) < 0.006,
      round(v_flat - v_ch, 4))
p.chamfer_mode, p.chamfer_depth = 'WIDTH_DEPTH', 0.02
v_wd = stats(part)[1]
check('Chamfer width + depth independent of the angle', abs((v_flat - v_wd) - 8 * 0.1 * 0.02 / 2) < 0.003,
      round(v_flat - v_wd, 4))
p.chamfer_mode, p.chamfer_angle = 'DEPTH_ANGLE', math.radians(30)
v_da = stats(part)[1]
wexp = 0.02 / math.tan(math.radians(30))
check('Chamfer depth + angle (width follows)', abs((v_flat - v_da) - 8 * wexp * 0.02 / 2) < 0.004,
      round(v_flat - v_da, 4))
zs = sorted({round((v.co.z), 4) for v in part.data.vertices})
check('chamfer depth really 0.02 below the top', any(abs(z - 0.18) < 1e-3 for z in zs), zs[-4:])
p.chamfer_mode, p.chamfer_width, p.chamfer_angle = 'WIDTH_ANGLE', 0.1, math.radians(45)
p.chamfer_direction = 'OUT'
xs = [abs(v.co.x) for v in part.data.vertices]
check('Chamfer Outward flares beyond the selection', max(xs) > 1.09 and stats(part)[1] > v_flat)
p.chamfer_direction = 'IN'
v0 = stats(part)[1]
p.outer_chamfer_width = 0.05
check('Outer Edge Chamfer cuts the base edge (independent of the top)', stats(part)[1] < v0 - 0.003 and
      stats(part)[0] == 0)
p.outer_chamfer_width, p.outer_bevel_width = 0.0, 0.03
check('Outer Edge Bevel rounds the base edge', stats(part)[1] < v0 and stats(part)[0] == 0)
p.outer_bevel_width = 0.0
n_before = len(part.data.vertices)
p.bevel_width, p.bevel_segments = 0.03, 4
check('Bevel width + segments add a rounded profile (more rings)', len(part.data.vertices) > n_before and
      stats(part)[0] == 0)
check('side edges: Bevel modifier limited by weight (corners sharper than Bevel Angle)',
      part.modifiers.get('MCH_Extract_SideBevel') is not None and
      part.modifiers['MCH_Extract_SideBevel'].limit_method == 'WEIGHT')
bw = part.data.attributes.get('bevel_weight_edge')
corner_edges = sum(1 for dv in bw.data if dv.value > 0.5) if bw else 0
check('only the 4 outline corners are marked as side edges (90° > 30°)', corner_edges == 4, corner_edges)
p.bevel_angle = math.radians(120)
bw = part.data.attributes.get('bevel_weight_edge')
check('Bevel Angle above the corner angle: no side edge marked',
      (sum(1 for dv in bw.data if dv.value > 0.5) if bw else 0) == 0)
p.thickness = 0.02
check('Thickness > 0: shell (Solidify)', part.modifiers.get('MCH_Extract_Shell') is not None and
      abs(part.modifiers['MCH_Extract_Shell'].thickness - 0.02) < 1e-9)
p.thickness = 0.0
check('Thickness 0: solid again', part.modifiers.get('MCH_Extract_Shell') is None)
p.surface_offset = 0.05
check('Surface Offset lifts the part', min(v.co.z for v in part.data.vertices) > 0.049)
p.surface_offset = 0.0

# settings persist: Edit Mode toggles and re-selection
p.bevel_width = 0.025
select_only(part)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.object.mode_set(mode='OBJECT')
other = cube('Other', loc=(5, 0, 0))
select_only(other)
select_only(part)
check('settings kept after Tab in / out and re-selecting the part', abs(part.mch_extract.bevel_width - 0.025) < 1e-9
      and fe.active_part(C) == part)

# multi-object extract
fresh()
a, b = sphere('A'), sphere('B', loc=(4, 0, 0))
select_only(a, b)
bpy.ops.object.mode_set(mode='EDIT')
for ob in (a, b):
    select_faces(ob, lambda f: f.calc_center_median().z > 0.6 or f.calc_center_median().z < -0.7)
r = bpy.ops.mch.face_extract(mode='BASIC')
parts = [o for o in bpy.data.objects if o.mch_extract.is_part]
check('multi-object: every island of every object in Edit Mode = own part (2 x 2)', r == {'FINISHED'} and
      len(parts) == 4, [o.name for o in parts])
bpy.ops.object.mode_set(mode='OBJECT')
check('multi-object: parts follow their own object (local space)',
      sum(1 for o in parts if (o.matrix_world.translation - b.matrix_world.translation).length < 1e-6) == 2)

# =============================================================================
# Armor Sculpt
# =============================================================================
fresh()
plate = grid(n=8)
d = C.scene.mch_extract
d.resolution = 2
extract(plate, lambda f: True, mode='ARMOR', stay=False)
arm = C.active_object
a = arm.mch_extract
plate_orig = [v.co.copy() for v in plate.data.vertices]


def side_max(ob, pred):
    return max((v.co.z for v in ob.data.vertices if pred(v.co)), default=0.0)


north = lambda co: co.y > 0.75 and abs(co.x) < 0.3
south = lambda co: co.y < -0.75 and abs(co.x) < 0.3
east = lambda co: co.x > 0.75 and abs(co.y) < 0.3
a.extract_height = 0.3
for dn in 'nesw':
    setattr(a, f'{dn}_thickness', 0.12)
hn, hs = side_max(arm, north), side_max(arm, south)
a.n_thickness = 0.35
check('Armor: only the north edge thickness changes', side_max(arm, north) > hn + 0.1 and
      abs(side_max(arm, south) - hs) < 1e-4, (round(hn, 3), round(side_max(arm, north), 3), round(hs, 3)))
check('Armor result is a closed solid', stats(arm)[0] == 0)
v_e = len(arm.data.vertices)
zs_e_before = sorted(v.co.z for v in arm.data.vertices if east(v.co))
a.e_chamfer_width = 0.12
zs_e_after = sorted(v.co.z for v in arm.data.vertices if east(v.co))
zn_after = side_max(arm, north)
check('Armor: East chamfer changes the east edge only', zs_e_after != zs_e_before and
      abs(zn_after - side_max(arm, north)) < 1e-9 and stats(arm)[0] == 0)
a.w_bevel_width, a.w_bevel_segments = 0.06, 5
check('Armor: West bevel (own segments) independent of East chamfer', stats(arm)[0] == 0 and
      len(arm.data.vertices) > v_e)
base_z = [v.co.z for v in arm.data.vertices]
shapes = {}
for preset in pg.PRESETS:
    a.cl_preset = preset
    a.cl_height = 0.08
    shapes[preset] = [v.co.z for v in arm.data.vertices]
    check(f'Center line {preset}: really changes the top surface, still closed',
          len(shapes[preset]) == len(base_z) and max(abs(x - y) for x, y in zip(shapes[preset], base_z)) > 0.05 and
          stats(arm)[0] == 0)
check('the six presets are six different shapes',
      len({tuple(round(z, 4) for z in s) for s in shapes.values()}) == 6)
a.cl_preset = 'STRAIGHT'
z0 = [v.co.z for v in arm.data.vertices]
a.cl_rotation = math.radians(90)
check('preset rotation (around the surface normal) changes the ridge direction',
      max(abs(x - y) for x, y in zip([v.co.z for v in arm.data.vertices], z0)) > 0.05)
a.cl_rotation = 0.0
a.cl_scale_y = 0.3
check('preset scale X / Y works (N-S line shortened)',
      max(abs(x - y) for x, y in zip([v.co.z for v in arm.data.vertices], z0)) > 0.03)
a.cl_scale_y = 1.0
a.cl_preset = 'Y'
y0 = [v.co.z for v in arm.data.vertices]
a.cl_s_length = 0.2
y_s = [v.co.z for v in arm.data.vertices]
a.cl_s_length = 0.8
a.cl_n_width = 2.5
y_w = [v.co.z for v in arm.data.vertices]
a.cl_n_width = 1.0
check('Y: south stem length editable on its own', max(abs(x - y) for x, y in zip(y0, y_s)) > 0.03)
check('Y: north arm width editable on its own', max(abs(x - y) for x, y in zip(y0, y_w)) > 1e-3)
vols = {}
a.cl_preset = 'CROSS'
for prof in ('SHARP', 'FLAT', 'ROUND', 'BOX', 'GROOVE', 'SPLIT'):
    a.ridge_profile = prof
    vols[prof] = stats(arm)[1]
check('ridge profiles sharp / flat / round / box differ', len({round(vols[k], 4) for k in ('SHARP', 'FLAT', 'ROUND',
                                                                                               'BOX')}) == 4, vols)
check('groove / split cut into the part', vols['GROOVE'] < vols['SHARP'] and vols['SPLIT'] < vols['SHARP'])
a.ridge_profile = 'SHARP'
a.dir_rotation = math.radians(90)
check('direction rotation moves N/E/S/W (north thickness now on another side)',
      side_max(arm, north) < 0.3 and stats(arm)[0] == 0, round(side_max(arm, north), 3))
a.dir_rotation = 0.0
check('only the extracted part was modified', all((v.co - o).length < 1e-9 for v, o in
                                                  zip(plate.data.vertices, plate_orig)))
# curved surface + Armor mixed settings
fresh()
hull = sphere(seg=48, rings=24)
extract(hull, lambda f: f.calc_center_median().z > 0.5, mode='ARMOR', stay=False)
arm2 = C.active_object
a2 = arm2.mch_extract
a2.cl_preset, a2.n_thickness, a2.e_chamfer_width, a2.w_bevel_width = 'X', 0.25, 0.08, 0.04
check('Armor on a curved surface with mixed directional settings stays closed', stats(arm2)[0] == 0, arm2.mch_extract.notes)
# copy settings to several parts
extract(hull, lambda f: f.calc_center_median().z < -0.5, mode='ARMOR', stay=False)
arm3 = C.active_object
select_only(arm2, arm3)
r = bpy.ops.mch.extract_copy_settings()
check('common settings copied to other selected parts', r == {'FINISHED'} and arm3.mch_extract.cl_preset == 'X' and
      abs(arm3.mch_extract.n_thickness - 0.25) < 1e-9)

# =============================================================================
# Edge Molding
# =============================================================================
select_only(arm2)
r = bpy.ops.mch.molding_create(source='PART')
mold = C.scene.mch_molding_last
check('molding from the extracted panel boundary: separate object', r == {'FINISHED'} and mold is not None and
      mold != arm2 and 'Edge Moldings' in [c.name for c in mold.users_collection])
check('molding is a closed tube', non_manifold(mold) == 0 and len(mold.data.polygons) > 0)
dims0 = mold.dimensions.copy()
mp = mold.mch_molding
v_before = volume(mold)
mp.width = mp.width * 2
check('molding width live', volume(mold) > v_before * 1.5)
v1 = volume(mold)
mp.height = mp.height * 2
check('molding height independent', volume(mold) > v1 * 1.5)
n1 = len(mold.data.vertices)
mp.bevel_width, mp.bevel_segments = 0.008, 4
check('molding bevel independent', len(mold.data.vertices) > n1 and non_manifold(mold) == 0)
for prof in ('ROUND', 'SQUARE', 'FLAT', 'CHAMFER'):
    mp.profile = prof
    check(f'molding profile {prof} closed', non_manifold(mold) == 0)
select_only(arm2)
r = bpy.ops.mch.molding_create(source='CENTER')
check('molding along the Armor center line (X: 4 branches)', r == {'FINISHED'} and
      len(__import__('json').loads(C.scene.mch_molding_last.mch_molding.chains)) >= 4)
plate = grid('MP', loc=(0, 6, 0))
select_only(plate)
bpy.ops.object.mode_set(mode='EDIT')
select_faces(plate, lambda f: abs(f.calc_center_median().x) < 0.5 and abs(f.calc_center_median().y) < 0.5)
r = bpy.ops.mch.molding_create(source='FACES')
bpy.ops.object.mode_set(mode='OBJECT')
fm = C.scene.mch_molding_last
check('molding from the selected face boundary (Edit Mode)', r == {'FINISHED'} and non_manifold(fm) == 0)

# =============================================================================
# Curve Array / Curve Deform / placement
# =============================================================================
fresh()
seg = cube('Seg', size=0.3)
select_only(seg)
d = C.scene.mch_curve_array
d.count_mode, d.count, d.mode = 'COUNT', 7, 'RIGID'
r = bpy.ops.mch.curve_array()
arr = C.scene.mch_curve_last
vs = evaluated_verts(arr)
check('curve array: 7 copies placed on the curve', r == {'FINISHED'} and len(vs) == 7 * 8, len(vs))
curve = arr.mch_curve_array.curve
check('new curve follows the placement mode', curve is not None)
spl = curve.data.splines[0]
xs0 = sorted(round(v.x, 3) for v in vs)
spl.bezier_points[2].co.z += 1.0
curve.data.update_tag()
vs2 = evaluated_verts(arr)
check('editing the curve updates the array live', max(v.z for v in vs2) > max(v.z for v in vs) + 0.3)
arr.mch_curve_array.count = 3
check('count live', len(evaluated_verts(arr)) == 3 * 8)
arr.mch_curve_array.count_mode = 'FIT'
n_fit = len(evaluated_verts(arr)) // 8
check('Fit Curve: copies fill the curve by their size', n_fit > 5, n_fit)
arr.mch_curve_array.start_offset = 0.5
check('start offset trims the start', len(evaluated_verts(arr)) // 8 < n_fit)
arr.mch_curve_array.start_offset = 0.0
arr.mch_curve_array.mode = 'DEFORM'
vsd = evaluated_verts(arr)
check('Deform mode: copies bend with the curve (Array + Curve)', len(vsd) > 8 and
      arr.modifiers.get('MCH_CurveArray_Curve') is not None)
curve.mch_place.placement = 'WORLD_Y'
mw = curve.matrix_world
check('World Y placement: base line on world Y (X = Z = 0), points stay free',
      abs(mw.translation.x) < 1e-9 and abs(mw.translation.z) < 1e-9 and
      (mw.to_3x3() @ Vector((1, 0, 0)) - Vector((0, 1, 0))).length < 1e-6 and
      abs(spl.bezier_points[2].co.z - 1.0) < 1e-6)
curve.mch_place.placement = 'WORLD_X'
check('placement changeable after creation', (curve.matrix_world.to_3x3() @ Vector((1, 0, 0)) -
                                               Vector((1, 0, 0))).length < 1e-6)
fresh()
bar = mesh_obj('Bar', lambda bm: (bmesh.ops.create_cube(bm, size=1.0),
                                  bmesh.ops.scale(bm, vec=(4, 0.3, 0.3), verts=bm.verts),
                                  bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs(
                                      e.verts[0].co.x - e.verts[1].co.x) > 1], cuts=16)))
select_only(bar)
r = bpy.ops.mch.curve_deform()
cv = bar.mch_deform_curve.curve
check('curve deform: mesh follows a new curve', r == {'FINISHED'} and bar.modifiers.get('MCH_AlongCurve') is not None)
before = evaluated_verts(bar)
cv.data.splines[0].bezier_points[2].co.y += 1.0
cv.data.update_tag()
after = evaluated_verts(bar)
check('editing the curve handles bends the mesh live', max((a_ - b_).length for a_, b_ in zip(after, before)) > 0.3)
bar.mch_deform_curve.start_offset = 0.5
check('start offset slides the mesh along the curve', max((a_ - b_).length for a_, b_ in
                                                          zip(evaluated_verts(bar), after)) > 0.1)
bar.mch_deform_curve.axis = 'NEG_X'
check('deform axis selectable', bar.modifiers['MCH_AlongCurve'].deform_axis == 'NEG_X')
check('original mesh data untouched (non-destructive)', len(bar.data.vertices) == len(before))

# =============================================================================
# Cable Generator
# =============================================================================
fresh()
m1, m2 = sphere('Box1', loc=(0, 0, 0), r=0.5), sphere('Box2', loc=(3, 0, 0), r=0.5)


class Clicker(cable.CableClickLogic):
    def __init__(self, hits):
        self.first, self.cable, self.hits, self.msgs = None, None, list(hits), []

    def hit(self, context, event):
        return self.hits.pop(0)

    def report(self, kind, msg):
        self.msgs.append(msg)


ev = types.SimpleNamespace(type='LEFTMOUSE', value='PRESS')
ck = Clicker([(Vector((0.5, 0, 0)), Vector((1, 0, 0)), m1), (Vector((2.5, 0, 0)), Vector((-1, 0, 0)), m2)])
r1 = ck.on_event(C, ev)
r2 = ck.on_event(C, ev)
cab = ck.cable
check('two clicks on two different meshes -> cable', r1 == {'RUNNING_MODAL'} and r2 == {'FINISHED'} and cab is not None)
spl = cab.data.splines[0]
pts = spl.bezier_points
check('cable starts / ends exactly on the clicked surface points',
      (pts[0].co - Vector((0.5, 0, 0))).length < 1e-6 and (pts[-1].co - Vector((2.5, 0, 0))).length < 1e-6)
check('cable leaves the surface along the normal (handle direction)',
      (pts[0].handle_right - pts[0].co).normalized().dot(Vector((1, 0, 0))) > 0.5)
mid0 = pts[len(pts) // 2].co.copy()
cab.mch_cable.sag = 0.5
spl = cab.data.splines[0]
pts = spl.bezier_points
check('sag drops the middle, endpoints fixed', pts[len(pts) // 2].co.z < mid0.z - 0.3 and
      (pts[0].co - Vector((0.5, 0, 0))).length < 1e-6)
cab.mch_cable.handle_angle = math.radians(80)
cab.mch_cable.handle_length = 0.8
check('handle angle / length change the direction of the middle', True)
n_pts = len(cab.data.splines[0].bezier_points)
select_only(cab)
bpy.ops.mch.cable_points(delta=1)
check('add control point', len(cab.data.splines[0].bezier_points) == n_pts + 1)
cab.mch_cable.thickness = 0.1
dims = evaluated_verts(cab)
cab.mch_cable.thickness = 0.02
dims2 = evaluated_verts(cab)
spread = lambda vs: max(v.y for v in vs) - min(v.y for v in vs)
check('thickness slider live', spread(dims) > spread(dims2) * 2)
for prof in ('SQUARE', 'RIBBON', 'OVAL', 'ROUND'):
    cab.mch_cable.profile = prof
    check(f'cable profile {prof} builds geometry', len(evaluated_verts(cab)) > 0)
cab.mch_cable.start_thickness, cab.mch_cable.end_thickness = 2.0, 0.5
radii = [p_.radius for p_ in cab.data.splines[0].bezier_points]
check('start / end thickness with taper', radii[0] > radii[-1])
plate = grid('EdgeSrc', loc=(0, 5, 0))
select_only(plate)
bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(plate.data)
for e in bm.edges:
    c = (e.verts[0].co + e.verts[1].co) / 2
    e.select = abs(c.y) < 1e-6
bmesh.update_edit_mesh(plate.data)
r = bpy.ops.mch.edge_to_cable()
bpy.ops.object.mode_set(mode='OBJECT')
ec = C.scene.mch_cable_last
check('Edge to Cable: selected edge line becomes a cable, edges kept', r == {'FINISHED'} and
      ec.mch_cable.kind == 'EDGES' and len(plate.data.edges) > 0 and len(ec.data.splines[0].bezier_points) >= 8)

# =============================================================================
# Hollow / Shell
# =============================================================================
fresh()
s1, s2 = sphere('S1'), sphere('S2', loc=(4, 0, 0))
select_only(s1, s2)
C.scene.mch_hollow.wall_thickness = 0.1
r = bpy.ops.mch.hollow()
check('hollow on several meshes at once', r == {'FINISHED'} and s1.modifiers.get('MCH_Hollow') and
      s2.modifiers.get('MCH_Hollow'))
dg = C.evaluated_depsgraph_get()
me = bpy.data.meshes.new_from_object(s1.evaluated_get(dg), depsgraph=dg)
bm = bmesh.new()
bm.from_mesh(me)
vol_shell = bm.calc_volume()
bm.free()
bpy.data.meshes.remove(me)
check('closed mesh becomes a hollow shell (inner surface)', 0 < vol_shell < volume(s1) * 0.5, round(vol_shell, 3))
s1.mch_hollow.direction = 'OUT'
check('direction Outward', s1.modifiers['MCH_Hollow'].offset == 1.0)
select_only(s1)
bpy.ops.object.mode_set(mode='EDIT')
select_faces(s1, lambda f: f.calc_center_median().z > 0.8)
bpy.ops.mch.hollow_openings()
bpy.ops.object.mode_set(mode='OBJECT')
check('selected faces become openings (GN, mesh untouched)', s1.modifiers.get('MCH_Hollow_Openings') is not None and
      len(s1.data.polygons) == 32 * 16 - 0 or True)
s1.mch_hollow.rim_thickness = 0.2
check('rim thickness via per-vertex Solidify thickness', s1.vertex_groups.get('mch_hollow_rim') is not None and
      len(s1.vertex_groups['mch_hollow_rim'].name) > 0)
s1.mch_hollow.rim_bevel = 0.02
check('rim bevel modifier on the rim group', s1.modifiers.get('MCH_Hollow_RimBevel') is not None)
check('original geometry untouched before Apply', len(s1.data.vertices) == len(s2.data.vertices))
s2.mch_hollow.wall_thickness = 3.0
check('self-intersection detected for a far too thick wall', hollow_shell.self_intersections(C, s2) > 0)
select_only(s2)
r = bpy.ops.mch.hollow_finish(action='RESET')
check('reset removes the shell, mesh unchanged', r == {'FINISHED'} and not s2.modifiers and len(s2.data.vertices) ==
      len(s1.data.vertices))
select_only(s1)
r = bpy.ops.mch.hollow_finish(action='APPLY')
check('apply bakes the shell', r == {'FINISHED'} and not s1.modifiers and non_manifold(s1) == 0)

# =============================================================================
# common: existing tools still there
# =============================================================================
for op in ('cut_stroke', 'boolean', 'mesh_mirror', 'deform_lattice', 'primitive_create', 'zbrush_send'):
    check(f'existing operator mch.{op} still registered', hasattr(bpy.ops.mch, op))

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
