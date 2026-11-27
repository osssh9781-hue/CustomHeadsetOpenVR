"""0.24.331 (user, cop_for_rig: "안되잖아" - Make Bevel Real left no bevel): Clamp Overlap shrinks the whole bevel to the
narrowest spot (on the user's fan-triangulated parts to nothing).  Now: no clamp, only the sharp edges beveled (our own
edge attribute), the edges that would spike or fold found and left sharp; the old way only when nothing is kept."""
import bmesh
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bevel_normal as bn

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
W = 0.08


def part(name, loc):
    """A 2 m box, triangulated, with a tiny step (0.01 tall - an eighth of the width) raised on its top: Clamp
    Overlap shrinks the whole bevel to that."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    top = [f for f in bm.faces if f.normal.z > 0.9][0]
    bmesh.ops.inset_individual(bm, faces=[top], thickness=0.6)
    r = bmesh.ops.extrude_face_region(bm, geom=[top])
    bmesh.ops.translate(bm, verts=[e for e in r['geom'] if isinstance(e, bmesh.types.BMVert)], vec=(0, 0, 0.01))
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='FIXED', ngon_method='EAR_CLIP')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    S.collection.objects.link(ob)
    ob.location = loc
    return ob


a = part('A', (0, 0, 0))
ua = a.data.attributes.new('bevel_weight_edge', 'FLOAT', 'EDGE')
ua.data.foreach_set('value', np.full(len(a.data.edges), 0.25, np.float32))
# the old way (clamped) on a copy: next to nothing
old = part('Old', (5, 0, 0))
m_old = bn.make_real(old, W, 3, C, weighted=False)
C.view_layer.update()
bm_ = bmesh.new()
bm_.from_object(old, C.evaluated_depsgraph_get())
v_old = abs(bm_.calc_volume(signed=True))
bm_.free()
old.modifiers[bn.REAL].show_viewport = False
C.view_layer.update()
bm_ = bmesh.new()
bm_.from_object(old, C.evaluated_depsgraph_get())
v_base = abs(bm_.calc_volume(signed=True))
bm_.free()
old.modifiers[bn.REAL].show_viewport = True

for o in S.objects:
    o.select_set(o is a)
C.view_layer.objects.active = a
S.mch_bevel_normal_radius = W
bpy.ops.mch.bevel_normal_real()
mod = a.modifiers.get(bn.REAL)
C.view_layer.update()
bm_ = bmesh.new()
bm_.from_object(a, C.evaluated_depsgraph_get())
v_new = abs(bm_.calc_volume(signed=True))
bm_.free()
kept = list(a.get(bn.KEPT, ()))
check(f'the old clamped way takes next to nothing off ({v_base - v_old:.5f} m³) - the bug',
      m_old is not None and v_base - v_old < 3e-3)
check(f'Make Real now: a live Bevel, by our edge weight, no clamp; it takes off a real bevel ({v_base - v_new:.4f} m³ - '
      f'a 2 m box\'s 12 edges at {W}: about 0.03); edges beveled / left sharp {kept}',
      mod is not None and mod.limit_method == 'WEIGHT' and mod.edge_weight == bn.EDGE_ATTR and not mod.use_clamp_overlap
      and v_base - v_new > 0.01 and v_base - v_new > (v_base - v_old) * 5 and len(kept) == 2 and kept[0] > 0)
far = bn.sticks_out(a, W, C)
check(f'no spike ({far / W:.2f} x width off the surface at most) and no fold', far <= W * bn.SPIKE and bn.clean(a, W, C))
w = np.empty(len(a.data.edges), np.float32)
a.data.attributes['bevel_weight_edge'].data.foreach_get('value', w)
check('the user\'s own Bevel Weight untouched; the checking attribute (face normals) gone again',
      np.allclose(w, 0.25) and a.data.attributes.get(bn.FACE_N) is None)
sharp = set(bn.sharp_edges(a.data))
on = np.empty(len(a.data.edges), np.float32)
a.data.attributes[bn.EDGE_ATTR].data.foreach_get('value', on)
check('only sharp edges (> 30°) carry the weight; the flat diagonals of the fan none',
      set(np.nonzero(on)[0].tolist()) <= sharp and on.sum() == kept[0])

# a spike / fold is found and its edges left sharp (the check made to see one edge as bad)
real_bad = bn._Check.bad
bad_edge = sorted(sharp)[0]


def fake_bad(self):
    at = self.ob.data.attributes[bn.EDGE_ATTR]
    v = np.empty(len(self.ob.data.edges), np.float32)
    at.data.foreach_get('value', v)
    self.n += 1
    self.spiked, self.folds = bool(v[bad_edge]), []
    return self.spiked


bn._Check.bad = fake_bad
b = part('B', (0, 5, 0))
mod_b = b.modifiers.new(bn.REAL, 'BEVEL')
mod_b.width = W
got = bn.weighted_real(b, mod_b, W, C)
on = np.empty(len(b.data.edges), np.float32)
b.data.attributes[bn.EDGE_ATTR].data.foreach_get('value', on)
bn._Check.bad = real_bad
check(f'an edge that spikes is found by halving and left sharp, the rest beveled ({got})',
      got is not None and got[1] >= 1 and on[bad_edge] == 0 and on.sum() == got[0] == len(sharp) - got[1])

# nothing sharp (a smooth sphere): the old way, as before
bpy.ops.mesh.primitive_uv_sphere_add(location=(0, -5, 0))
sp = C.active_object
for o in S.objects:
    o.select_set(o is sp)
bpy.ops.mch.bevel_normal_real()
ms = sp.modifiers.get(bn.REAL)
check('no sharp edge (a sphere): the old way (Angle, clamped), our attribute not left on it',
      (ms is None or ms.limit_method == 'ANGLE') and sp.data.attributes.get(bn.EDGE_ATTR) is None)
summary()
