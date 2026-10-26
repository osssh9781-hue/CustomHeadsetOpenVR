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
