"""0.24.342 Project to Original (user: "쿼드 플로우나 리토포 하고 원본 메쉬에 프로젝트 하는 기능" -> "표면에 딱
붙이기만", "자동"): the low's points snapped onto the high's surface (along their normals, else the nearest point),
evened out along the surface; face count / flow unchanged.  Also As One (No High Poly, several meshes -> one set of
maps, one joined copy)."""
import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import retopo_project as rp

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene

# the original: a bumpy sphere (radius ~1 +- 0.08); the retopo: a coarse quad sphere of radius 0.8 off it
bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=1.0)
hi = C.active_object
hi.name = 'Orig'
tex = bpy.data.textures.new('T', 'CLOUDS')
tex.noise_scale = 0.4
m = hi.modifiers.new('D', 'DISPLACE')
m.texture, m.strength = tex, 0.16
bpy.ops.mesh.primitive_cube_add(size=1.6)
lo = C.active_object
lo.name = 'Retopo'
sub = lo.modifiers.new('S', 'SUBSURF')
sub.levels = 3
bpy.ops.object.modifier_apply(modifier='S')
cast = lo.modifiers.new('C', 'CAST')
cast.factor = 1.0
bpy.ops.object.modifier_apply(modifier='C')
nf = len(lo.data.polygons)
for o in S.objects:
    o.select_set(False)
hi.select_set(True)
lo.select_set(True)
C.view_layer.objects.active = lo
tg = rp.targets(C)
check(f'the pair found: low {tg[0][0].name if tg else None} onto {[h.name for h in tg[0][1]] if tg else None}',
      bool(tg) and tg[0][0] is lo and tg[0][1] == [hi])

tree = rp._high_tree(C, [hi])


def offs():
    M = lo.matrix_world
    return np.array([tree.find_nearest(M @ v.co)[3] for v in lo.data.vertices])


before = offs()
r = bpy.ops.mch.retopo_project(relax=2)
after = offs()
check(f'Project to Original runs ({r})', r == {'FINISHED'})
check(f'every point on the surface (largest gap {after.max():.5f}, before {before.mean():.3f} on average)',
      after.max() < 1e-3 and before.mean() > 0.1)
check(f'the face count / flow unchanged ({len(lo.data.polygons)} faces)', len(lo.data.polygons) == nf)
# evenness: edge lengths do not bunch (the longest / shortest edge as before, roughly)
co = np.array([v.co[:] for v in lo.data.vertices])
E = np.array([e.vertices[:] for e in lo.data.edges])
el = np.linalg.norm(co[E[:, 0]] - co[E[:, 1]], axis=1)
check(f'the points stay evened out (edge length spread {el.std() / el.mean():.3f})', el.std() / el.mean() < 0.35)
# the high is untouched
check('the original is not changed', len(hi.modifiers) == 1 and hi.modifiers[0].type == 'DISPLACE')

# a thin wall: a point near a plate's top must not jump through to the bottom face
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(5, 0, 0), scale=(2, 2, 0.02))
plate = C.active_object
bpy.ops.object.transform_apply(scale=True)
bpy.ops.mesh.primitive_plane_add(size=3.0, location=(5, 0, 0.05))
pl = C.active_object
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=6)
bpy.ops.object.mode_set(mode='OBJECT')
res = rp.project(C, pl, [plate], relax=0)
zs = np.array([(pl.matrix_world @ v.co).z for v in pl.data.vertices])
inside = np.array([abs((pl.matrix_world @ v.co).x - 5) < 0.95 and abs((pl.matrix_world @ v.co).y) < 0.95
                   for v in pl.data.vertices])
check(f'a thin plate: the points land on its near side (top z {zs[inside].min():.4f}..{zs[inside].max():.4f})',
      np.allclose(zs[inside], 0.01, atol=1e-4))
summary()
