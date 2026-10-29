"""0.24.89 Belt Maker: the report says the loop size and the width as a share of it (a thin strap or a small loop
says why), Defaults resets the remembered settings (the next belt starts with the last belt's values) and a live
belt, the panel has the button; the loop is the part's size over a plate / an applied belt / a scaled or mirrored
body (the sizes measured while chasing "the belt keeps coming out small")."""
import math

from _harness import bpy, check, fresh, summary
from mathutils import Euler, Matrix, Vector

import mecha_lab
from mecha_lab import armor_plate as ap, belt_maker as bmk, core_geometry as cg

mecha_lab.register()
fresh()
C = bpy.context
proj = cg.OrthoProjector(Euler((math.radians(90), 0, 0)).to_quaternion(), center=Vector((0, 0, 0)),
                         pixels_per_unit=200.0, size=(1000, 1000))
scr = lambda x, z: (500 + x * 200, 500 + z * 200)


def size(ob):
    P = [ob.matrix_world @ v.co for v in ob.data.vertices]
    return max(max(p[k] for p in P) - min(p[k] for p in P) for k in range(3))


def only(*obs):
    for x in C.scene.objects:
        x.select_set(False)
    for x in obs:
        x.select_set(True)
    C.view_layer.objects.active = obs[-1] if obs else None


def body(name, loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=1.0, location=loc)
    b = C.active_object
    b.name = name
    return b


b = body('Body')
line = [scr(-1.3, 0.1), scr(0, 0.1), scr(1.3, 0.1)]
C.scene.mch_belt.width = 0.02
msg = bmk.perform(C, line, proj)
belt = C.active_object
check('the report says the loop size and the width as a share of it', 'loop 1.99' in msg and 'width 0.02 = 1 %' in msg, msg)
check('a thin belt is remembered for the next one (as before)', abs(C.scene.mch_belt.width - 0.02) < 1e-6)
r = bpy.ops.mch.belt_defaults()
check('Defaults: the live belt and the next-belt settings back to the factory width 0.15',
      r == {'FINISHED'} and abs(belt.mch_belt.width - 0.15) < 1e-6 and abs(C.scene.mch_belt.width - 0.15) < 1e-6)
check('... the live belt rebuilt with it', abs(size(belt) - 2.06) < 0.05 and 'width 0.15 = 8 %' in bmk.size_note(belt), bmk.size_note(belt))
src = open(bmk.__file__).read()
check('the panel: Defaults next to "Settings for the next belt" and next to Apply, the size line on a live belt',
      src.count("operator('mch.belt_defaults'") == 2 and "box.label(text=note[3:]" in src)
# the loop stays the part's size whatever lies under the line
bpy.ops.mch.belt_apply()
msg2 = bmk.perform(C, line, proj)
b2 = C.active_object
check('a belt drawn across an applied belt: still the part-sized loop', abs(size(b2) - 2.06) < 0.05, (msg2, size(b2)))
bpy.data.objects.remove(b2)
bpy.data.objects.remove(belt)
only(b)
C.scene.mch_settings.mch_active_tool = 'PLATE'
ap.perform_plate(C, [[scr(-0.5, -0.3), scr(0.5, -0.3), scr(0.5, 0.5), scr(-0.5, 0.5)]], proj)
msg3 = bmk.perform(C, line, proj)
b3 = C.active_object
check('a belt drawn across an armor plate: around the body, part-sized', 'around Body' in msg3 and abs(size(b3) - 2.06) < 0.05, (msg3, size(b3)))
bpy.data.objects.remove(b3)
half = body('Half', loc=(0, 0, -6))
import bmesh
bm = bmesh.new(); bm.from_mesh(half.data)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.x < -1e-6], context='VERTS')
bm.to_mesh(half.data); bm.free()
half.modifiers.new('Mirror', 'MIRROR')
only(half)
msg4 = bmk.perform(C, [scr(-1.3, -5.9), scr(0, -5.9), scr(1.3, -5.9)], proj)
b4 = C.active_object
check('a half body with a Mirror modifier: the loop goes round both halves', abs(size(b4) - 2.06) < 0.05, (msg4, size(b4)))
summary()
