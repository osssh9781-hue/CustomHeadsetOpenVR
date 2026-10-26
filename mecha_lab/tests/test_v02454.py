"""0.24.37 Alt + draw carves INTO the mesh as deep as the shape's Height: Base Mesh (Alt: Carve Height, the
default; Alt: Like Cut = the 0.24.5 Cut-tool way) and Surface Draw on a plain mesh (a groove along the line / a
pocket with Fill Area; over a live drawing Alt still cuts the drawing)."""
import math

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Euler, Vector
import bmesh

import mecha_lab
from mecha_lab import base_mesh as bm_, core_geometry as cg, surface_draw as sd

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
FRONT = cg.OrthoProjector(Euler((math.radians(90), 0, 0)).to_quaternion(), center=Vector((0, 0, 0)),
                          pixels_per_unit=200.0, size=(1000, 1000))          # looking +Y: the front face is y = -1
scr = lambda x, z: (500 + x * 200, 500 + z * 200)


def volume(o):
    b = bmesh.new()
    b.from_mesh(o.data)
    v = b.calc_volume()
    b.free()
    return v


def cube():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    return C.active_object


p = bm_.scene_defaults(C)
p.sketch, p.profile, p.height, p.surface_align = False, 'FLAT', 0.5, True
SQ = [[scr(-0.3, -0.3), scr(0.3, -0.3), scr(0.3, 0.3), scr(-0.3, 0.3)]]
check('Base Mesh Alt: Carve Height is the default', p.alt_mode == 'HEIGHT')
t = cube()
msg = bm_.perform_base(C, SQ, FRONT, cutter=True)
v = volume(t)
check('Alt (Carve Height): a pocket as deep as Height (0.6 x 0.6 x 0.5), closed, nothing else made',
      abs(v - (8.0 - 0.36 * 0.5)) < 0.02 and non_manifold(t) == 0 and len(bpy.data.objects) == 1, (msg, v))
ys = sorted({round((t.matrix_world @ q.co).y, 3) for q in t.data.vertices if abs(q.co.x) < 0.31 and abs(q.co.z) < 0.31})
check('... the pocket floor is Height behind the front face (y = -0.5)', ys[0] == -1.0 and any(abs(y + 0.5) < 0.01 for y in ys), ys)
p.invert_height = True
t = cube()
bm_.perform_base(C, SQ, FRONT, cutter=True)
check('... Invert on does not turn the carve outward', abs(volume(t) - (8.0 - 0.36 * 0.5)) < 0.02, volume(t))
p.invert_height = False
p.alt_mode = 'CUT'
S.mch_cut.depth_mode = 'THROUGH'
t = cube()
bm_.perform_base(C, SQ, FRONT, cutter=True)
check('Alt: Like Cut = the Cut tool (Through All: a hole right through)', abs(volume(t) - (8.0 - 0.36 * 2)) < 0.02,
      volume(t))
p.alt_mode = 'HEIGHT'
t = cube()
band = [[scr(0.5, 0.05), scr(3.0, 0.05), scr(3.0, -0.05), scr(0.5, -0.05)]]   # a line running off the cube
bm_.perform_base(C, band, FRONT, cutter=True)
check('Alt with a line half off the mesh: still finds it and carves (0.5 x 0.1 x 0.5)',
      abs(volume(t) - (8.0 - 0.5 * 0.1 * 0.5)) < 0.01 and non_manifold(t) == 0, volume(t))

# on a curved surface the carve follows it: the pocket floor stays Height below the surface everywhere
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
ball = C.active_object
p.height = 0.1
BIG = [[scr(-0.5, -0.5), scr(0.5, -0.5), scr(0.5, 0.5), scr(-0.5, 0.5)]]
msg = bm_.perform_base(C, BIG, FRONT, cutter=True)
floor = [(ball.matrix_world @ q.co).length for q in ball.data.vertices
         if abs(q.co.x) < 0.4 and abs(q.co.z) < 0.4 and q.co.y < 0 and (ball.matrix_world @ q.co).length < 0.97]
check('Alt on a ball: the pocket follows the surface (floor Height = 0.1 below it everywhere, not flat)',
      floor and max(floor) - min(floor) < 0.02 and abs(sum(floor) / len(floor) - 0.9) < 0.015 and non_manifold(ball) == 0,
      (msg, floor and (round(min(floor), 3), round(max(floor), 3))))
p.height = 0.5
# Carve Depth: carve less deep than Height (a thin part made with the same Height is not cut through)
t = cube()
p.carve_depth = 0.2
bm_.perform_base(C, SQ, FRONT, cutter=True)
check('Carve Depth 0.2 (Height 0.5): the pocket is 0.2 deep', abs(volume(t) - (8.0 - 0.36 * 0.2)) < 0.02, volume(t))
p.carve_depth = 0.0
# Through: a window right through the part, whatever Height says (the rest stays as a frame)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=1.0, scale=(1.0, 0.15, 1.0))          # a plate 0.15 thick, faces at y = +-0.075
plate = C.active_object
bpy.ops.object.transform_apply(scale=True, location=False, rotation=False)
p.alt_mode, p.height = 'THROUGH', 0.02
msg = bm_.perform_base(C, SQ, FRONT, cutter=True)
b = bmesh.new()
b.from_mesh(plate.data)
v = b.calc_volume()
b.free()
check('Alt: Through = a window right through the plate (0.6 x 0.6 hole in a 0.15 plate), Height ignored',
      abs(v - (0.15 - 0.36 * 0.15)) < 0.005 and non_manifold(plate) == 0 and 'through' in msg, (msg, v))
ok, *_r = plate.ray_cast(Vector((0, -5, 0)), Vector((0, 1, 0)))
check('... you can see through it', not ok)
# Inside: a channel in the middle of the thickness - front and back stay, windows open on the side walls
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=1.0, scale=(1.0, 0.2, 1.0))           # 0.2 thick, faces at y = +-0.1
plate = C.active_object
bpy.ops.object.transform_apply(scale=True, location=False, rotation=False)
p.alt_mode, p.inside_skin = 'INSIDE', 0.25
band = [[scr(-0.8, 0.05), scr(0.8, 0.05), scr(0.8, -0.05), scr(-0.8, -0.05)]]   # crosses both side walls (x = +-0.5)
msg = bm_.perform_base(C, band, FRONT, cutter=True)
b = bmesh.new()
b.from_mesh(plate.data)
v = b.calc_volume()
b.free()
C.view_layer.update()
hit_front = plate.ray_cast(Vector((0, -5, 0)), Vector((0, 1, 0)))
hit_side = plate.ray_cast(Vector((5, 0, 0)), Vector((-1, 0, 0)))      # the channel runs right across: see-through
hit_side_off = plate.ray_cast(Vector((5, 0, 0.2)), Vector((-1, 0, 0)))  # above the channel: the wall
check('Alt: Inside = a channel in the middle (1 x 0.1 x 0.1 out of 0.2), the front face stays closed',
      abs((0.2 - v) - 1.0 * 0.1 * 0.1) < 0.003 and hit_front[0] and abs(hit_front[1].y + 0.1) < 1e-4
      and non_manifold(plate) == 0 and 'inside' in msg, (msg, 0.2 - v, hit_front[1], tuple(plate.location)))
check('... it opens as windows on the side walls (see right through it from the side; the wall above stays)',
      not hit_side[0] and hit_side_off[0] and abs(hit_side_off[1].x - 0.5) < 1e-4, (hit_side, hit_side_off[1]))
p.alt_mode, p.height = 'HEIGHT', 0.5
st = S.mch_sdraw
st.width, st.height, st.profile = 0.1, 0.05, 'SQUARE'
t = cube()
msg = sd.engrave(C, [scr(-0.6 + 0.06 * i, 0.0) for i in range(21)], FRONT)
v = volume(t)
check('Surface Draw Alt on a plain mesh: a groove as deep as Height along the line (about 1.2 x 0.1 x 0.05)',
      0.004 < 8.0 - v < 0.009 and non_manifold(t) == 0 and len(bpy.data.objects) == 1 and 'Carved' in msg, (msg, 8 - v))
zs = [(t.matrix_world @ q.co) for q in t.data.vertices if abs(q.co.x) < 0.5 and abs(q.co.z) < 0.04]
check('... the groove floor is Height behind the surface', any(abs(w.y + 0.95) < 0.005 for w in zs))
t = cube()
st.fill_res = 15
sd.engrave(C, None, FRONT, loops=SQ)
v = volume(t)
check('Surface Draw Alt with Fill Area: a pocket (0.6 x 0.6 x 0.05)', abs((8.0 - v) - 0.36 * 0.05) < 0.004
      and non_manifold(t) == 0, 8 - v)
try:
    sd.engrave(C, [scr(4, 4), scr(4.5, 4)], FRONT)
    ok = False
except cg.CutError:
    ok = True
check('Alt where there is no mesh: tells, changes nothing', ok)
from mecha_lab import cut_engine as ce
check('the stroke engine: Surface Draw Alt keeps the line (a band, not an area)',
      'engrave' in ce.MCH_OT_cut_stroke._execute_closed.__code__.co_names)
summary()
