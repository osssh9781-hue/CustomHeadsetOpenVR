"""0.24.350 (user: "라이브 스택 밴드에도 나이프 메쉬 메뉴 똑같은 거 넣어 줘"): the Live Stack's Bend card has Silhouette
Move's Knife Mesh row (Cuts + Knife Mesh): a low-poly part sliced evenly first bends smoothly, its shape unchanged."""
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bend_any as ba, live_stack as ls, panel_capture as pc

fresh()
mecha_lab.register()
C = bpy.context
bpy.ops.mesh.primitive_cube_add(size=1.0)
ob = C.active_object
ob.scale = (4.0, 0.5, 0.2)
bpy.ops.object.transform_apply(scale=True)


def card():
    tree = pc.capture(lambda lay, ctx: ls.draw(lay, ctx), C)
    nodes = list(pc.walk(tree))
    return ({n.prop for n in nodes if n.kind == 'prop'},
            [getattr(n, 'op', None) or n.opts.get('idname') or n.prop for n in nodes if n.kind == 'op'], nodes)


props, ops, nodes = card()
check('the Bend card (no bend yet): Cuts and Knife Mesh, as in Silhouette Move', 'knife_cuts' in props
      and any('knife_grid' in str(o) for o in ops), (sorted(props), ops))
bpy.ops.mch.bend_add()
props, ops, nodes = card()
check('... still there once the part is bent', 'knife_cuts' in props and any('knife_grid' in str(o) for o in ops))
ob.mch_bend.up = 60.0
C.view_layer.update()


def bent_verts():
    dg = C.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).to_mesh()
    n = len(me.vertices)
    ob.evaluated_get(dg).to_mesh_clear()
    return n


n0, f0 = bent_verts(), len(ob.data.polygons)
co0 = np.array([v.co for v in ob.data.vertices])
C.scene.mch_concept.knife_cuts = 16
r = bpy.ops.mch.knife_grid()
co1 = np.array([v.co for v in ob.data.vertices])
lo0, hi0, lo1, hi1 = co0.min(0), co0.max(0), co1.min(0), co1.max(0)
check('Knife Mesh on the bent part: many more faces, the same shape (box unchanged)', r == {'FINISHED'}
      and len(ob.data.polygons) > 4 * f0 and np.allclose(lo0, lo1, atol=1e-6) and np.allclose(hi0, hi1, atol=1e-6),
      (f0, len(ob.data.polygons)))
check('... the bend stays on and now has the points to bend smoothly', ba.has(ob) and bent_verts() > 4 * n0,
      (n0, bent_verts()))
summary()
