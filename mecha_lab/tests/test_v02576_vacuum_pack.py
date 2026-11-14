"""0.24.171 Vacuum Pack (user: "클로스 드레이프에서 진공팩마냥 내가 선택한 거 감싸 주는 것도 만들어 주라"; on Wrap This Mesh's
result, small crumples all over and a ragged rim: "결과가 별로라네"; then "주름이 하나도 안 생기잖아!!" with a photo of shrink
film over a figure, "너무 무겁지 않아?"): the selected meshes sealed in one film - tight on them, taut over gaps
narrower than Hug allows, creases running out from the middle (strongest on the spans); a plain mesh made once (the
sliders remake it, Re-pack after moving a part; nothing follows the parts on its own).  Measured on the film."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import mech_shader as ms, vacuum_pack as vp  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)


def film_pts(film):
    C.view_layer.update()
    dg = C.evaluated_depsgraph_get()
    me = film.evaluated_get(dg).data
    P = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', P)
    M = np.array(film.matrix_world)
    return P.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3], me


def outside(film, parts):
    """How far out of the film each part point not enclosed by it is (ray parity, 3 directions, 2 of 3 say
    outside)."""
    P, me = film_pts(film)
    bvh = BVHTree.FromPolygons([tuple(p) for p in P], [tuple(p.vertices) for p in me.polygons])
    out = []
    for o in parts:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            k_out = 0
            for dv in ((0, 0, 1), (0.3, 0.2, 0.93), (-0.4, 0.1, 0.91)):
                d, o2, k = Vector(dv).normalized(), w.copy(), 0
                for _ in range(60):
                    h = bvh.ray_cast(o2, d)
                    if h[0] is None:
                        break
                    k += 1
                    o2 = h[0] + d * 1e-5
                k_out += (k % 2 == 0)
            if k_out >= 2:
                out.append(bvh.find_nearest(w)[3])
    return out


parts = []
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.45, segments=48, ring_count=24, location=(-0.55, 0, 0.45))
parts.append(C.active_object)
bpy.ops.mesh.primitive_torus_add(major_radius=0.35, minor_radius=0.12, location=(0.35, 0.1, 0.13))
parts.append(C.active_object)
bpy.ops.mesh.primitive_cone_add(radius1=0.25, depth=0.7, location=(0.25, -0.35, 0.35))
parts.append(C.active_object)
bpy.ops.mesh.primitive_cube_add(size=0.4, location=(-0.1, 0.45, 0.2))
parts.append(C.active_object)
for o in C.selected_objects:
    o.select_set(False)
check('nothing selected: Vacuum Pack waits', not bpy.ops.mch.vacuum_pack.poll())
for o in parts:
    o.select_set(True)
C.view_layer.objects.active = parts[0]
r = bpy.ops.mch.vacuum_pack()
film = C.active_object
P, me = film_pts(film)
check(f'Vacuum Pack Selected: one film round the 4 parts ({len(P):,} points), a plain mesh (no modifier working on the '
      f'parts - "너무 무겁지 않아?"), the parts untouched',
      r == {'FINISHED'} and vp.is_film(film) and len(vp.film_parts(film)) == 4 and 5000 < len(P) < 60000
      and all(not o.modifiers for o in parts) and not film.modifiers)
size = film['mch_vacuum_size']
gap = film.mch_vacuum.gap / 100.0 * size
nout = outside(film, parts)
vf = size / film.mch_vacuum.detail
check(f'every part sealed inside it - the cone\'s tip and the box\'s corners too ({len(nout)} of '
      f'{sum(len(o.data.vertices) for o in parts):,} part points outside, by at most {1000 * max(nout, default=0):.1f} mm: '
      f'- more than 1 mm: {sum(d > 0.001 for d in nout)}; a needle tip can show through by about one film step, '
      f'{1000 * vf:.1f} mm)', sum(d > 0.001 for d in nout) <= 3 and max(nout, default=0) < 1.1 * vf, nout)
top = P[np.linalg.norm(P[:, :2] - np.array([-0.55, 0.0]), axis=1) < 0.05, 2].max()
check(f'pulled tight onto them: over the ball\'s top {1000 * (top - 0.9):.1f} mm (Gap {1000 * gap:.1f} mm)',
      gap * 0.5 < top - 0.9 < gap + size / film.mch_vacuum.detail, (top, gap))


def hole_open():
    P, _me = film_pts(film)
    return not (np.linalg.norm(P - np.array([0.35, 0.1, 0.13]), axis=1) < 0.12).any()


film.mch_vacuum.hug = 0.85
o85 = hole_open()
film.mch_vacuum.hug = 0.15
o15 = hole_open()
check(f'Hug: 0.85 - the film into the torus\'s hole (open: {o85}); 0.15 - a loose bag across it (open: {o15})', o85 and not o15)
film.mch_vacuum.hug = 0.55
# a narrow gap between two balls: spanned at a low Hug, followed into at a high one
f2parts = []
for x in (-0.55, 0.55):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, segments=48, ring_count=24, location=(x, 3.0, 0.0))
    f2parts.append(C.active_object)
for o in C.selected_objects:
    o.select_set(False)
for o in f2parts:
    o.select_set(True)
film2, _msg = vp.perform(C)


def web_top():
    P, _me = film_pts(film2)
    sel = (np.abs(P[:, 0]) < 0.03) & (np.abs(P[:, 1] - 3.0) < 0.03)
    return float(P[sel, 2].max()) if sel.any() else -9.0


film2.mch_vacuum.hug = 0.3
w30 = web_top()
film2.mch_vacuum.hug = 1.0
w100 = web_top()
check(f'between two balls 0.1 apart: Hug 0.3 spans the gap (the film {w30:.2f} above their middle), Hug 1 goes down '
      f'into it ({w100:.2f})', w30 > 0.2 and w100 < w30 - 0.1, (w30, w100))
film2.mch_vacuum.hug = 0.55
# creases: where the film spans (Over Parts 0: not on the balls at all)
film2.mch_vacuum.over_parts = 0.0
film2.mch_vacuum.creases = 0.0
Pa, _ = film_pts(film2)
film2.mch_vacuum.creases = 1.0
Pb, _ = film_pts(film2)
moved = np.linalg.norm(Pb - Pa, axis=1) if len(Pa) == len(Pb) else np.zeros(1)
on_ball = np.abs(np.linalg.norm(Pa - np.array([0.55, 3.0, 0.0]), axis=1) - 0.5) < 0.02
on_ball |= np.abs(np.linalg.norm(Pa - np.array([-0.55, 3.0, 0.0]), axis=1) - 0.5) < 0.02
check(f'Creases: ridges on the span only ({int((moved > 1e-4).sum())} points moved, up to {1000 * moved.max():.1f} mm; '
      f'on the balls themselves {1000 * moved[on_ball].max():.2f} mm)', len(Pa) == len(Pb) and moved.max() > 0.002
      and moved[on_ball].max() < 1e-4, (moved.max(), moved[on_ball].max()))
me2 = film2.data
check('...the fine creases\' direction / strength / scale kept on the film for its material',
      all(n in me2.attributes for n in (vp.DIR_ATTR, vp.W_ATTR, vp.K_ATTR)))
film2.mch_vacuum.over_parts = 0.5
Pc, _ = film_pts(film2)
moved2 = np.linalg.norm(Pc - Pa, axis=1) if len(Pa) == len(Pc) else np.zeros(1)
check(f'...Creases Over Parts 0.5: they run on over the balls too (up to {1000 * moved2[on_ball].max():.1f} mm there)',
      len(Pa) == len(Pc) and moved2[on_ball].max() > 1e-3)
# a part moved: the film stays (nothing works on it while you move / sculpt) until Re-pack
f2parts[1].location.x += 0.4
P3, _ = film_pts(film2)
for o in C.selected_objects:
    o.select_set(False)
film2.select_set(True)
C.view_layer.objects.active = film2
r = bpy.ops.mch.vacuum_repack()
P4, _ = film_pts(film2)
check(f'a part moved: the film stays put ({P3[:, 0].max():.2f}); Re-pack: round the parts as they are now '
      f'({P4[:, 0].max():.2f})', abs(P3[:, 0].max() - Pc[:, 0].max()) < 1e-6 and r == {'FINISHED'}
      and P4[:, 0].max() > Pc[:, 0].max() + 0.35)
# the film's material: a Film preset; a Mech page preset on it
film2.mch_vacuum.film = 'BLACK'
mats = {m.name for m in film2.data.materials if m}
bl = bpy.data.materials.get('MCH Vacuum Film - Black Latex')
check(f'Film "Black Latex": its material ({mats}), the fine creases in it (a Bump from the film\'s attributes)',
      mats == {'MCH Vacuum Film - Black Latex'} and bl.node_tree.nodes.get('Creases') is not None
      and any(n.bl_idname == 'ShaderNodeAttribute' and n.attribute_name == vp.DIR_ATTR for n in bl.node_tree.nodes))
steel = ms.new_material('STEEL')
ms.assign(C, [film2], steel)
film2.mch_vacuum.creases = 0.7                                          # (a slider after it: remade, the material kept)
check(f'a Mech page preset on the selected film: the film takes it, and keeps it when a slider remakes the film '
      f'({ {m.name for m in film2.data.materials if m} })', {m.name for m in film2.data.materials if m} == {steel.name})
# Apply
for o in C.selected_objects:
    o.select_set(False)
film2.select_set(True)
C.view_layer.objects.active = film2
r = bpy.ops.mch.vacuum_apply()
from mecha_lab import workspace_ui as wu  # noqa: E402
check(f'Apply (Enter too): a plain mesh for good ({len(film2.data.polygons):,} faces) - its settings dropped, its material '
      f'kept, no node group left', r == {'FINISHED'} and not vp.is_film(film2) and not film2.modifiers
      and len(film2.data.polygons) > 1000 and [m.name for m in film2.data.materials] == [steel.name]
      and not any(g.name.startswith(vp.TREE) for g in bpy.data.node_groups)
      and 'vacuum_apply' in [o for o, _l in wu.ENTER_APPLY])
# the window
from mecha_lab import cloth_drape  # noqa: E402
check('the Cloth Drape window starts with the Vacuum Pack box', 'vacuum_pack.draw' in open(cloth_drape.__file__, encoding='utf-8').read())

mecha_lab.unregister()
summary()
