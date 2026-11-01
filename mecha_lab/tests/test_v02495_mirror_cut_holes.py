"""0.24.95 (user: "컷이나 그런 거 하다가 가끔 메쉬가 빵꾸가 나는데 그건 왜 그래? 미러를 해서 그런 건가?") Yes - a cut on a
part with the live Mirror whose wall ends ON the mirror plane or within the Mirror's Bisect distance (0.001) of it,
i.e. a cut drawn from the centre line: the base mesh stayed whole, but the Bisect threw that wall's points away and the
mirrored part showed a hole (6 - 8 open edges; a cut across the centre, or 1.5 mm clear of it, was fine).  Now such
a wall is moved just past the plane first (``core_geometry.cutter_past_mirror``) - the cut crosses the centre, the
Bisect cuts it cleanly, the mirrored part shows the cut up to the centre."""
from _harness import bmesh, bpy, check, fresh, summary
from mathutils import Quaternion

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, symmetry

mecha_lab.register()
fresh()
C = bpy.context
TOP = cg.OrthoProjector(Quaternion())


def open_edges(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n


def seen(ob):
    """Open edges of what is seen (the mirror applied) and its volume."""
    ev = ob.evaluated_get(C.evaluated_depsgraph_get())
    me = bpy.data.meshes.new_from_object(ev)
    bm = bmesh.new()
    bm.from_mesh(me)
    vol = bm.calc_volume()
    bm.free()
    n = open_edges(me)
    bpy.data.meshes.remove(me)
    return n, vol


def part(mirror=True):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    ob = C.active_object
    m = ob.modifiers.new('s', 'SUBSURF')
    m.subdivision_type, m.levels = 'SIMPLE', 2
    bpy.ops.object.convert(target='MESH')
    if mirror:
        symmetry.set_mode(C, ob, 'MIRROR')                    # (defaults: X, Bisect, Merge 0.001)
    return ob


def cut(ob, x0, x1, y0=-0.4, y1=0.4):
    px = lambda v: 500 + v * 100
    return ce.perform_closed(C, 'CUT', [ob], [ce.rect_loop((px(x0), px(y0)), (px(x1), px(y1)))], TOP)


ob = part()
m = symmetry.mirror_mod(ob)
check('The part\'s Mirror: X, Bisect on, Bisect distance 0.001 (Blender\'s default)',
      m is not None and m.use_axis[0] and m.use_bisect_axis[0] and abs(m.bisect_threshold - 0.001) < 1e-6)
results = []
for name, x0 in (('on the centre line', 0.0), ('0.5 mm from it', 0.0005), ('0.2 mm past it', -0.0002),
                 ('0.9 mm from it', 0.0009)):
    ob = part()
    cut(ob, x0, 0.3)
    n, vol = seen(ob)
    results.append((name, open_edges(ob.data), n, round(vol, 4)))
check('A cut whose wall ends on / within the Bisect distance of the mirror plane: the mirrored part is closed (before: '
      '6 - 8 open edges - a hole at the centre), and the cut is there on both sides (8 - 0.6 x 0.8 x 2)',
      all(b == 0 and s == 0 and abs(v - (8.0 - 0.48 * 2)) < 0.02 for _n, b, s, v in results), results)
ob = part()
cut(ob, -0.3, 0.3)
check('... a cut across the centre: closed, as before', seen(ob)[0] == 0)
ob = part()
cut(ob, 0.005, 0.3)
wall = sum(1 for v in ob.data.vertices if abs(v.co.x - 0.005) < 1e-5)
pushed = sum(1 for v in ob.data.vertices if -0.0101 < v.co.x < -0.0019 and abs(v.co.y) < 0.41)
n, vol = seen(ob)
check('... a wall 5 mm clear of the plane is left where it was drawn (a 1 cm rib stays in the middle)',
      n == 0 and wall >= 4 and pushed == 0, (n, wall, pushed))
# the cutter itself: moved only near the plane, only with a mirror
ob = part()
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.5, 0, 0))     # (x from 0 to 1: a wall on the plane)
cutter = C.active_object
moved = cg.cutter_past_mirror(ob, cutter)
xs = sorted({round(v.co.x + cutter.location.x, 4) for v in moved.vertices}) if moved else []
check('cutter_past_mirror: the wall on the plane goes just past it (2 x the Bisect distance), the far wall stays',
      moved is not None and xs == [-0.002, 1.0], xs)
if moved is not None:
    bpy.data.meshes.remove(moved)
plain = bpy.data.objects.new('plain', bpy.data.meshes.new('plain'))
C.scene.collection.objects.link(plain)
check('... a part without a mirror: the cutter is not touched', cg.cutter_past_mirror(plain, cutter) is None)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.05, 0, 0))   # (straddles the plane)
across = C.active_object
check('... a cutter across the plane: not touched', cg.cutter_past_mirror(ob, across) is None)
summary()
