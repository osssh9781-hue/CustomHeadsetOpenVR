"""Base Mesh from Shape: profiles, silhouette fidelity, closed solids, live edit, failures."""
import math
import sys

from _harness import bpy, bmesh, check, cube, fresh, non_manifold, select_only, summary, volume
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import base_mesh as bm_mod, core_geometry as cg, cut_engine as ce

TOP = cg.OrthoProjector(Quaternion())
OBL = cg.OrthoProjector(Quaternion((1, 0, 0), math.radians(40)) @ Quaternion((0, 0, 1), math.radians(20)))
C = bpy.context
STAR = [(500 + 150 * math.cos(-math.pi / 2 + i * math.pi / 5) * (1 if i % 2 == 0 else 0.4),
         500 + 150 * math.sin(-math.pi / 2 + i * math.pi / 5) * (1 if i % 2 == 0 else 0.4)) for i in range(10)]
RECT = ce.rect_loop((420, 440), (580, 540))


def make(loops, profile, projector=TOP, **kw):
    s = C.scene.mch_base
    s.profile = profile
    for k, v in kw.items():
        setattr(s, k, v)
    before = set(bpy.data.objects)
    msg = bm_mod.perform_base(C, loops, projector)
    new = [o for o in bpy.data.objects if o not in before]
    return (new[0] if len(new) == 1 else None), msg


def local_z(ob):
    return [v.co.z for v in ob.data.vertices]


def outward(ob):
    b = bmesh.new()
    b.from_mesh(ob.data)
    v = b.calc_volume(signed=True)
    b.free()
    return v > 0


def reset():
    fresh()
    s = C.scene.mch_base
    s.height, s.wall, s.bevel_width, s.bevel_segments = 0.2, 0.03, 0.05, 4
    s.roundness, s.resolution, s.offset, s.bottom_too = 0.34, 28, 0.0, False
    C.scene.cursor.location = (0, 0, 0)


mecha_lab.register()

# 1. All profiles on convex + concave outlines, top and oblique views
for name, loop in (('rect', RECT), ('star (concave)', STAR)):
    for proj_name, proj in (('top', TOP), ('oblique', OBL)):
        shapes = {}
        for prof in ('FLAT', 'CHAMFER', 'BEVEL', 'DOME'):
            reset()
            ob, msg = make([loop], prof, proj)
            ok = ob is not None
            check(f'{name}/{proj_name} {prof}: one new object', ok, msg)
            if not ok:
                continue
            check(f'{name}/{proj_name} {prof}: closed manifold solid', non_manifold(ob) == 0)
            check(f'{name}/{proj_name} {prof}: outward normals, volume > 0', outward(ob) and volume(ob) > 1e-6)
            shapes[prof] = round(volume(ob), 5)
        if len(shapes) == 4:
            vols = shapes
            check(f'{name}/{proj_name}: profiles give different solids', len(set(vols.values())) == 4, vols)

# 2. Silhouette fidelity: FLAT seen from the drawing view == drawn rectangle
reset()
ob, _ = make([RECT], 'FLAT', TOP)
scr = [TOP.to_screen(ob.matrix_world @ v.co) for v in ob.data.vertices]
xs, ys = [p[0] for p in scr], [p[1] for p in scr]
check('silhouette matches drawn rectangle (<0.01 px)',
      max(abs(min(xs) - 420), abs(max(xs) - 580), abs(min(ys) - 440), abs(max(ys) - 540)) < 0.01,
      (min(xs), max(xs), min(ys), max(ys)))
check('flat thickness = Height', abs(max(local_z(ob)) - 0.2) < 1e-6 and abs(min(local_z(ob))) < 1e-6)
check('placed at 3D cursor plane when nothing is under the shape', abs((ob.matrix_world.translation).z) < 1e-6)

# 3. Dome is a real bulge, not a bevel
reset()
dome, _ = make([STAR], 'DOME', TOP, wall=0.03, height=0.25)
zs = local_z(dome)
check('dome peak = edge height + height', abs(max(zs) - 0.28) < 0.02, max(zs))
interior = [z for z in zs if 0.05 < z < 0.27]
check('dome has many intermediate heights (curved top, not flat + bevel)', len(interior) > 50, len(interior))
b = bmesh.new()
b.from_mesh(dome.data)
b.normal_update()
top_faces = [f for f in b.faces if f.calc_center_median().z > 0.031]
flipped = [f for f in top_faces if f.normal.z <= 0]
check('concave star dome: no flipped top faces (no centre-fan artefacts)', not flipped, len(flipped))
border = [v for v in b.verts if v.co.z <= 0.0301 and v.co.z > 0.0299]
check('dome meets the border at edge height', len(border) > 20, len(border))
b.free()
reset()
bevel, _ = make([STAR], 'BEVEL', TOP, height=0.28)
check('bevel keeps a flat top (differs from dome)', sum(1 for z in local_z(bevel) if abs(z - 0.28) < 1e-6) >= 10)
reset()
knife, _ = make([STAR], 'DOME', TOP, wall=0.0)
check('dome with edge height 0 is still closed', knife is not None and non_manifold(knife) == 0)
for r in (0.0, 1.0):
    reset()
    d, _ = make([RECT], 'DOME', TOP, roundness=r)
    check(f'dome roundness {r}: valid', d is not None and non_manifold(d) == 0)

# 4. Holes (PNG ring-like custom shape) and multiple islands
reset()
outer = ce.circle_loop((500, 500), (600, 500), 64)
hole = list(reversed(ce.circle_loop((500, 500), (550, 500), 48)))
island = ce.rect_loop((700, 700), (760, 760))
for prof in ('FLAT', 'BEVEL', 'DOME'):
    reset()
    ob, msg = make([outer, hole, island], prof, TOP)
    check(f'ring + island {prof}: closed', ob is not None and non_manifold(ob) == 0, msg)
    if ob is not None:
        centre = ob.matrix_world.inverted() @ Vector((0, 0, 0))
        hit = ob.ray_cast(Vector((centre.x, centre.y, 5)), Vector((0, 0, -1)))[0]
        check(f'ring {prof}: the hole is open', not hit)

# 5. Placement on a surface under the shape
reset()
c = cube('Floor', size=2.0)
v_cube = volume(c)
ob, _ = make([RECT], 'FLAT', TOP)
check('base sits on the surface under the shape (z = top face)', abs(ob.matrix_world.translation.z - 1.0) < 1e-4,
      ob.matrix_world.translation)
check('the surface mesh is untouched', abs(volume(c) - v_cube) < 1e-9 and len(c.data.vertices) == 8)
check('new object is selected and active', C.view_layer.objects.active == ob and ob.select_get() and not c.select_get())

# 6. Failure cases create nothing
reset()
n0 = len(bpy.data.objects)
for label, loops in (('self-intersecting', [[(400, 400), (600, 600), (600, 450), (400, 620)]]),
                     ('tiny', [[(500, 500), (501, 500), (501, 501)]]),
                     ('duplicate points only', [[(500, 500), (500, 500), (500, 500)]])):
    try:
        make(loops, 'DOME', TOP)
        check(f'{label} refused', False)
    except cg.CutError as ex:
        check(f'{label} outline refused with message', len(bpy.data.objects) == n0, ex)
reset()
noisy = [(500 + 120 * math.cos(a) + (3 if i % 2 else 0), 500 + 90 * math.sin(a))
         for i, a in enumerate([k * 2 * math.pi / 400 for k in range(400)])]
ob, msg = make([noisy], 'DOME', TOP, resolution=48)
check('high-resolution noisy outline (400 pts) dome closed', ob is not None and non_manifold(ob) == 0, msg)

# 7. Live re-edit
reset()
ob, _ = make([STAR], 'FLAT', TOP)
n_flat = len(ob.data.vertices)
ob.mch_base.profile = 'DOME'
check('live: profile change rebuilds the mesh', len(ob.data.vertices) > n_flat and non_manifold(ob) == 0)
ob.mch_base.height = 0.5
check('live: height change applied', abs(max(local_z(ob)) - (0.5 + ob.mch_base.wall)) < 0.03, max(local_z(ob)))
ob.mch_base.offset = 0.1
check('live: offset moves the solid along its normal', abs(min(local_z(ob)) - 0.1) < 1e-6)
select_only(ob)
r = bpy.ops.mch.set_profile(profile='CHAMFER')
check('RMB profile operator updates the selected live Base Mesh', r == {'FINISHED'} and
      ob.mch_base.profile == 'CHAMFER' and C.scene.mch_base.profile == 'CHAMFER')
r = bpy.ops.mch.base_freeze()
check('freeze stops live rebuilding', r == {'FINISHED'} and not ob.mch_base.live)
n = len(ob.data.vertices)
ob.mch_base.profile = 'DOME'
check('frozen object is not rebuilt', len(ob.data.vertices) == n)

# 8. Existing tools unaffected: Cut still works on a Base Mesh result
reset()
ob, _ = make([RECT], 'FLAT', TOP, height=0.4)
v0 = volume(ob)
ce.perform_closed(C, 'CUT', [ob], [ce.rect_loop((480, 470), (520, 510))], TOP)
check('Cut works on a Base Mesh object', volume(ob) < v0 and non_manifold(ob) == 0)

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
