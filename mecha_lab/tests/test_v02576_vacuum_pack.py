"""0.24.171 Vacuum Pack (user: "클로스 드레이프에서 진공팩마냥 내가 선택한 거 감싸 주는 것도 만들어 주라"; on Wrap This Mesh's
result: "결과가 별로라네"; "주름이 하나도 안 생기잖아!!"; "왜 시뮬을 안 하고 이렇게 해?" with a photo of a cloth pulled tight
over a face): the selected meshes in one bag, the air sucked out by Blender's own cloth simulation - run a frame at a
time by Cloth Drape's Space, kept by Enter, dropped by Esc; the parts themselves untouched (copies collide).
Measured on the meshes."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import cloth_drape as cd, vacuum_pack as vp  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
parts = []
bpy.ops.mesh.primitive_monkey_add(size=0.5, location=(0, 0, 1.0))
mk = C.active_object
mk.modifiers.new('S', 'SUBSURF').levels = 1
parts.append(mk)
bpy.ops.mesh.primitive_cylinder_add(radius=0.09, depth=0.4, location=(0, 0.04, 0.66))
parts.append(C.active_object)
for o in C.selected_objects:
    o.select_set(False)
check('nothing selected: Vacuum Pack waits', not bpy.ops.mch.vacuum_pack.poll())
for o in parts:
    o.select_set(True)
C.view_layer.objects.active = parts[0]
st = S.mch_vacuum
st.points, st.frames = 3000, 45
mods0 = [[m.name for m in o.modifiers] for o in parts]
frame0 = S.frame_current
r = bpy.ops.mch.vacuum_pack()
film = C.active_object
cols = [bpy.data.objects.get(n) for n in cd.SIM.get('colliders', ())]
check(f'Vacuum Pack Selected: one bag round the 2 parts ({len(film.data.vertices):,} points) with Blender\'s cloth, '
      f'copies of the parts collide ({len(cols)}), the parts untouched',
      r == {'FINISHED'} and cd.SIM.get('mode') == 'VACUUM' and film.modifiers.get(vp.CLOTH_MOD) is not None
      and len(cols) == 2 and all(c is not None and c.modifiers.get('Collision') for c in cols)
      and [[m.name for m in o.modifiers] for o in parts] == mods0)
cs = film.modifiers[vp.CLOTH_MOD].settings
check(f'...the air sucked out: the bag\'s pressure below zero ({cs.uniform_pressure_force:.0f}), stiff to stretch / soft '
      f'to squeeze ({cs.tension_stiffness:.0f} / {cs.compression_stiffness:.0f}), Tightness = shrink '
      f'{cs.shrink_min:.2f}', cs.use_pressure and cs.uniform_pressure_force < 0
      and cs.tension_stiffness > cs.compression_stiffness and abs(cs.shrink_min - st.tight / 100) < 1e-6)
# the distance from the cloth to the parts, before / after
dg = C.evaluated_depsgraph_get()
tris, verts = [], []
for o in parts:
    me = o.evaluated_get(dg).to_mesh()
    me.calc_loop_triangles()
    off = len(verts)
    verts += [o.matrix_world @ v.co for v in me.vertices]
    tris += [tuple(off + i for i in t.vertices) for t in me.loop_triangles]
    o.evaluated_get(dg).to_mesh_clear()
bvh = BVHTree.FromPolygons(verts, tris)


def dist_out(ob):
    dg = C.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).data
    P = [ob.matrix_world @ v.co for v in me.vertices]
    return np.array([bvh.find_nearest(p)[3] for p in P])


d0 = dist_out(film)
n = 0
while cd.step(C):
    n += 1
d1 = dist_out(film)
check(f'Space (its steps): {n} frames, the cloth sucked in onto the parts (median {1000 * np.median(d0):.0f} -> '
      f'{1000 * np.median(d1):.0f} thousandths off them)', n == 45 and cd.SIM.get('done') and np.median(d1) < 0.35 * np.median(d0),
      (np.median(d0), np.median(d1)))
_P = film.evaluated_get(C.evaluated_depsgraph_get()).data


def dihedral(me):
    """the mean angle between neighbouring faces (degrees): 0 for a smooth sheet, more with folds"""
    me.calc_loop_triangles()
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    a = [math.degrees(e.calc_face_angle(0.0)) for e in bm.edges if len(e.link_faces) == 2]
    bm.free()
    return float(np.mean(a))


bag_angle = dihedral(bpy.data.meshes.get(film.data.name))
r_msg = cd.confirm(C)
kept_angle = dihedral(film.data)
check(f'Enter: kept as a plain mesh ({r_msg}) - no cloth, no key, the colliders gone, the frame back ({S.frame_current})',
      not film.modifiers and film.data.shape_keys is None and not vp.is_film(film)
      and not [o for o in bpy.data.objects if 'vacuum collider' in o.name] and S.frame_current == frame0
      and not cd.sim_active() and bpy.data.collections.get(vp.COLL) is None)
check(f'...the cloth folded as it was sucked in (the angle between neighbouring faces {bag_angle:.1f} -> {kept_angle:.1f} '
      f'degrees on average)', kept_angle > bag_angle * 1.5, (bag_angle, kept_angle))
check(f'...the parts untouched ({[[m.name for m in o.modifiers] for o in parts]})', [[m.name for m in o.modifiers] for o in parts] == mods0)
# Esc drops it; a slider while it is out starts it again; a picked gather point; Thickness on Enter
for o in C.selected_objects:
    o.select_set(False)
for o in parts:
    o.select_set(True)
st.gather, st.gather_point = 'PICKED', (0.0, 0.3, 1.0)
cd.settings(C).thickness = 0.5
vp.perform(C)
f2 = bpy.data.objects[cd.SIM['ob']]
g = f2.vertex_groups.get('MCH Gather')
check(f'a picked gather point: the cloth round it pinned ({len([v for v in f2.data.vertices if v.groups])} points) and '
      f'drawn in by a keyed shape', g is not None and f2.data.shape_keys is not None
      and f2.modifiers[vp.CLOTH_MOD].settings.vertex_group_mass == 'MCH Gather')
cd.step(C)
cd.step(C)
st.folds = 30.0
check(f'a slider while it is out: back to frame 0 with it ({cd.SIM["sess"]["frame"]}), the bending '
      f'{f2.modifiers[vp.CLOTH_MOD].settings.bending_stiffness:.2f}', cd.SIM['sess']['frame'] == 0
      and abs(f2.modifiers[vp.CLOTH_MOD].settings.bending_stiffness - 0.03 ** 0.3) < 1e-4)
for _i in range(5):
    cd.step(C)
r_msg = cd.confirm(C)
check(f'Enter with Cloth Drape\'s Thickness: its Solidify ({r_msg}), the gather\'s pin group gone',
      f2.modifiers.get('MCH Cloth Thickness') is not None and f2.vertex_groups.get('MCH Gather') is None)
cd.settings(C).thickness = 0.0
st.gather = 'NONE'
vp.perform(C)
f3 = cd.SIM['ob']
r_msg = cd.cancel(C)
check(f'Esc: dropped ({r_msg}) - no cloth, no colliders left', bpy.data.objects.get(f3) is None
      and not [o for o in bpy.data.objects if 'vacuum collider' in o.name] and not cd.sim_active())
from mecha_lab import cloth_drape as _cd  # noqa: E402
check('the Cloth Drape window starts with the Vacuum Pack box', 'vacuum_pack.draw' in open(_cd.__file__, encoding='utf-8').read())

mecha_lab.unregister()
summary()
