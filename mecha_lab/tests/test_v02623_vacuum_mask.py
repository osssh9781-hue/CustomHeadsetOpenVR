"""0.24.211 (user: "베큠팩도 마스크로 하게 해줘"): Vacuum Pack Mask - only the masked region of the active mesh gets the
film: its rim pinned on the mesh, the rest sucked on by Blender's cloth (Space / Enter / Esc as Vacuum Pack)."""
import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import cloth_drape as cd, mesh_io as mio, vacuum_pack as vp  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_monkey_add(size=1.0, location=(0.3, 0, 1.0))
body = C.active_object
body.modifiers.new('S', 'SUBSURF').levels = 2
bpy.ops.object.modifier_apply(modifier='S')
st = C.scene.mch_vacuum
st.points, st.frames = 2500, 40
r0 = bpy.ops.mch.vacuum_mask()
check('no mask painted: Vacuum Pack Mask says so and makes nothing', r0 == {'CANCELLED'} and not cd.sim_active())
co = mio.read_co(body.data)
att = body.data.attributes.new('.sculpt_mask', 'FLOAT', 'POINT')
att.data.foreach_set('value', (co[:, 1] < -0.05).astype(np.float32))        # the face side
n_body = len(body.data.vertices)
r = bpy.ops.mch.vacuum_mask()
film = C.active_object
me = film.data
vg = film.vertex_groups.get(vp.MASK_PIN)
rim = [v.index for v in me.vertices if any(g.group == vg.index for g in v.groups)] if vg else []
wco = np.array([film.matrix_world @ v.co for v in me.vertices])
bw = np.array([body.matrix_world @ v.co for v in body.data.vertices])
check(f'Vacuum Pack Mask: a film of the masked side only ({len(me.vertices):,} points, all on the face side: max y '
      f'{wco[:, 1].max():+.2f}), Blender\'s cloth on it, the mesh itself untouched ({len(body.data.vertices):,} points)',
      r == {'FINISHED'} and cd.SIM.get('mode') == 'VACUUM' and film.modifiers.get(vp.CLOTH_MOD) is not None
      and wco[:, 1].max() < 0.1 and len(body.data.vertices) == n_body and cd.SIM.get('parts') == [body.name])
body.data.calc_loop_triangles()
bvh = BVHTree.FromPolygons([tuple(p) for p in bw], [tuple(t.vertices) for t in body.data.loop_triangles])


def dist(ob):
    dg = C.evaluated_depsgraph_get()
    m = ob.evaluated_get(dg).data
    return np.array([bvh.find_nearest(ob.matrix_world @ v.co)[3] for v in m.vertices])


d0 = dist(film)
inner = np.ones(len(d0), bool)
inner[rim] = False
cs = film.modifiers[vp.CLOTH_MOD].settings
check(f'...its rim ({len(rim)} points) lies on the mesh ({1000 * d0[rim].max():.1f} thousandths off) and is pinned; the '
      f'rest starts lifted off it (median {1000 * np.median(d0[inner]):.0f})',
      len(rim) > 10 and d0[rim].max() < 0.01 and cs.vertex_group_mass == vp.MASK_PIN
      and np.median(d0[inner]) > 3 * max(d0[rim].max(), 1e-4))
rim0 = wco[rim].copy()
n = 0
while cd.step(C):
    n += 1
d1 = dist(film)
dg = C.evaluated_depsgraph_get()
ev = film.evaluated_get(dg).data
rim1 = np.array([film.matrix_world @ ev.vertices[i].co for i in rim])
check(f'Space: {n} frames, the film sucked onto the mesh (median {1000 * np.median(d0[inner]):.0f} -> '
      f'{1000 * np.median(d1[inner]):.0f} thousandths), the rim stayed (moved {np.abs(rim1 - rim0).max():.4f})',
      n == 40 and np.median(d1[inner]) < 0.6 * np.median(d0[inner]) and np.abs(rim1 - rim0).max() < 1e-3)
msg = cd.confirm(C)
check(f'Enter keeps it: one film object left, no cloth modifier, no collision copies ({msg[:50]}...)',
      not cd.sim_active() and film.modifiers.get(vp.CLOTH_MOD) is None and not vp.leftovers(C))
summary()
