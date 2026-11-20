"""0.24.268 (user: "뷰포트에서 디자인 맞췄으니까 렌더에서 그거에 맞게 - 렌더 돌리면 너무 빵빵해져", "나 사이클만 써"):
Render Like Viewport on Hair in Shape and Fur - each strand as wide as the viewport draws it (half a pixel of the render
at its distance from the camera), and the Viewport % share in the render too.  The look against the viewport itself
(the viewport's own picture vs Cycles): tests/gui - measured in the real window, coverage 0.173 viewport / 0.223 before
/ 0.179 with the switch."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import bmesh  # noqa: E402
import mecha_lab
from mecha_lab import hair_shape as hs  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
head = C.active_object


def tube(name, centre, rad_fn, ring=24):
    bm = bmesh.new()
    rings = []
    for i, c in enumerate(centre):
        t = i / (len(centre) - 1)
        tan = (centre[min(i + 1, len(centre) - 1)] - centre[max(i - 1, 0)]).normalized()
        u = tan.orthogonal().normalized()
        v = tan.cross(u)
        rings.append([bm.verts.new(c + (u * math.cos(a) + v * math.sin(a)) * rad_fn(t))
                      for a in np.linspace(0, 2 * math.pi, ring, endpoint=False)])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(ring):
            bm.faces.new((a[k], a[(k + 1) % ring], b[(k + 1) % ring], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    S.collection.objects.link(ob)
    return ob



import math as _m
from mecha_lab import hair_view_width as hvw, creature_fur as cf  # noqa: E402
cen = [Vector((0.0, -0.2, 1.0)).lerp(Vector((0.0, -1.2, -0.8)), i / 40) for i in range(41)]
lock = tube('Lock', cen, lambda t: 0.25 * (1 - 0.7 * t))
for o in C.selected_objects:
    o.select_set(False)
lock.select_set(True); C.view_layer.objects.active = lock
hair, msg = hs.make(C, lock, None)
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); S.collection.objects.link(cam)
cam.location = (1.6, -0.6, 0.6); cam.rotation_euler = (_m.radians(90), 0, _m.radians(90)); S.camera = cam
S.render.resolution_x = S.render.resolution_y = 1000; S.render.resolution_percentage = 100
check('Hair in Shape: the switch there, off by default (as before: no modifier of ours)',
      hasattr(hair.mch_hshape, 'display_render') and not hair.mch_hshape.display_render and hair.modifiers.get(hvw.MOD) is None)
C.view_layer.update()
r0 = np.empty(len(hair.evaluated_get(C.evaluated_depsgraph_get()).data.points), np.float32)
hair.evaluated_get(C.evaluated_depsgraph_get()).data.attributes['radius'].data.foreach_get('value', r0)
hair.mch_hshape.display_render = True
C.view_layer.update()
dg = C.evaluated_depsgraph_get()
ev = hair.evaluated_get(dg).data
n = len(ev.points)
rad = np.empty(n, np.float32); ev.attributes['radius'].data.foreach_get('value', rad)
pos = np.empty(n * 3, np.float32); ev.attributes['position'].data.foreach_get('vector', pos); pos = pos.reshape(-1, 3)
M = np.array(hair.matrix_world)
wp = pos @ M[:3, :3].T + M[:3, 3]
dist = np.linalg.norm(wp - np.array(cam.location), axis=1)
pix = 36.0 / 50.0 / 1000.0
want = 0.5 * pix * dist
check(f'on: every strand half a render pixel wide at its distance (radius {rad.min()*1000:.3f}..{rad.max()*1000:.3f} mm, '
      f'was {r0.min()*1000:.3f}..{r0.max()*1000:.3f})', hair.modifiers.get(hvw.MOD) is not None
      and np.allclose(rad, want, rtol=1e-3, atol=1e-7))
cam.data.lens = 100
hvw._render_pre(S)
C.view_layer.update()
ev = hair.evaluated_get(C.evaluated_depsgraph_get()).data
rad2 = np.empty(n, np.float32); ev.attributes['radius'].data.foreach_get('value', rad2)
check(f'the lens changed (100 mm): set again before the render - the strands half as wide ({rad2.max()*1000:.3f} mm)',
      np.allclose(rad2, want / 2, rtol=1e-3, atol=1e-7))
cam.data.lens = 50
# 0.24.269 (user: "좀 더 얇게 할 수 없어?") Render Thickness
hair.mch_hshape.display_width = 0.4
C.view_layer.update()
ev = hair.evaluated_get(C.evaluated_depsgraph_get()).data
rad3 = np.empty(n, np.float32); ev.attributes['radius'].data.foreach_get('value', rad3)
check(f'Render Thickness 0.4: the strands 0.4 as wide ({rad3.max()*1000:.3f} mm)', np.allclose(rad3, want * 0.4, rtol=1e-3, atol=1e-8))
hair.mch_hshape.display_width = 1.0
# the Viewport % share in the render too
hair.mch_hshape.display = 0.2
hs.rebuild(hair, C) if hasattr(hs, 'rebuild') else None
COUNT = []


def grab(scene, d=None):
    if d is not None and d.mode == 'RENDER':
        COUNT.append(len(scene.objects[hair.name].evaluated_get(d).data.curves))


bpy.app.handlers.frame_change_post.append(grab)
S.render.engine = 'CYCLES'; S.cycles.samples = 1; S.cycles.device = 'CPU'
S.render.resolution_x = S.render.resolution_y = 32
for o in (head, lock):
    o.hide_render = True


def rendered():
    COUNT.clear()
    bpy.ops.render.render()
    return COUNT[-1] if COUNT else None


C.view_layer.update()
view = len(hair.evaluated_get(C.evaluated_depsgraph_get()).data.curves)
on = rendered()
hair.mch_hshape.display_render = False
off = rendered()
check(f'Viewport % 20: the render keeps the same share with the switch ({on}; viewport {view}), all without ({off})',
      on == view and off > view * 3 and hair.modifiers.get(hvw.MOD) is None)
# Fur: the same switch also thins the strands
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32, location=(5, 0, 0))
from mecha_lab import core_geometry as cg
from mathutils import Euler
FRONT = cg.OrthoProjector(Euler((_m.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)
S.mch_fur.density = 3000.0
cf.perform(C, [[(1500 + 100 * _m.cos(a), 500 + 80 * _m.sin(a)) for a in [i * _m.tau / 32 for i in range(32)]]], FRONT)
fur = C.active_object
fur.mch_fur.display_render = True
cf.push(fur)
check('Fur: the switch puts the same width modifier on it', cf.is_fur(fur) and fur.modifiers.get(hvw.MOD) is not None)
fur.mch_fur.display_width = 0.3
cf.push(fur)
from mecha_lab import geo_sculpt as gs_
m_ = fur.modifiers.get(hvw.MOD)
h_, pr_ = gs_._input(m_, 'Width')
wv = h_.value if pr_ == 'value' else m_[gs_._socket_ident(m_.node_group, 'Width')]
check(f'Fur: Render Thickness 0.3 reaches it ({wv})', wv is not None and abs(wv - 0.15) < 1e-6)
fur.mch_fur.display_render = False
cf.push(fur)
check('... off: gone', fur.modifiers.get(hvw.MOD) is None)
summary()
