"""0.24.230 (user: "클로스는 마스크 할 때 뒷면까지 그린 것도 잔주름 잘 나오게"): Drape Mask on a mask that goes ROUND
the body - the cloth is an even grid of QUADS unrolled round the body's axis (it was uneven triangles: broad folds),
for a band all the way round and for a wrap with an opening; a front patch is the flat grid as before."""
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import cloth_drape as cd, mesh_io as mio, wrinkle_lines as wl  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
st = cd.settings(C)
bpy.ops.mesh.primitive_uv_sphere_add(segments=256, ring_count=128, radius=1.0)
body = C.active_object
body.scale = (0.8, 0.6, 1.4)                      # (a torso-like body: not round, taller than wide)
bpy.ops.object.transform_apply(scale=True)
co = mio.read_co(body.data)
ang = np.degrees(np.arctan2(co[:, 1], co[:, 0]))


def patch(mask, points):
    att = body.data.attributes.get('.sculpt_mask') or body.data.attributes.new('.sculpt_mask', 'FLOAT', 'POINT')
    att.data.foreach_set('value', mask.astype(np.float32))
    faces = cd.masked_faces(body.data)
    me = cd.faces_mesh(body.data, faces)
    cd.smooth_rim(me)
    st.mask_points = points
    return me, cd.mask_patch(me, body, st)


def quality(new, me):
    from mathutils.bvhtree import BVHTree
    import bmesh
    bm = bmesh.new(); bm.from_mesh(me); tree = BVHTree.FromBMesh(bm)
    nc = mio.read_co(new)
    off = max(tree.find_nearest(tuple(p))[3] for p in nc[::7])
    bm.free()
    sides = np.array([len(p.vertices) for p in new.polygons])
    ev = mio.read_edge_verts(new)
    el = np.linalg.norm(nc[ev[:, 0]] - nc[ev[:, 1]], axis=1)
    return float((sides == 4).mean()), off, float(np.percentile(el, 95) / max(np.percentile(el, 5), 1e-9)), len(nc)


band = (np.abs(co[:, 2]) < 0.5)
me, new = patch(band, 6000)
chart = cd.wrap_chart(me, body)
q, off, ratio, n = quality(new, me)
loops = cd.rim_loops_idx(new)
check(f'a band all the way round: unrolled round the upright axis (axis z {abs(chart["a"][2]):.3f}, no opening), a closed '
      f'grid - {q * 100:.0f} % quads, {n} points for 6000 asked, 2 rims, on the body (off by {off:.4f}), even cells '
      f'(longest / shortest edge {ratio:.2f})',
      chart is not None and abs(chart['a'][2]) > 0.99 and chart['cut'] is None and q > 0.99 and 4000 < n < 9000
      and len(loops) == 2 and off < 0.02 and ratio < 2.6)
nc = mio.read_co(new)
check('... the band reaches its two rims (top and bottom of the mask)',
      abs(float(nc[:, 2].max()) - 0.5) < 0.05 and abs(float(nc[:, 2].min()) + 0.5) < 0.05)
bpy.data.meshes.remove(new); bpy.data.meshes.remove(me)

wrap = band & (np.abs(ang) < 130)                 # front and both sides, open at the back
me, new = patch(wrap, 3000)
chart = cd.wrap_chart(me, body)
q, off, ratio, n = quality(new, me)
nc = mio.read_co(new)
a2 = np.degrees(np.arctan2(nc[:, 1], nc[:, 0]))
cdir = chart['e1'] * np.cos(chart['cut']) + chart['e2'] * np.sin(chart['cut'])        # (where the cut is, in the body)
cdeg = float(np.degrees(np.arctan2(cdir[1], cdir[0])))
check(f'a wrap with an opening (260 deg): one sheet unrolled, the cut in the middle of the opening '
      f'({cdeg:.0f} deg: the back) - {q * 100:.0f} % quads, {n} points for 3000 asked, 1 rim, on the body ({off:.4f}), '
      f'it covers {a2.min():.0f} .. {a2.max():.0f} deg',
      chart['cut'] is not None and abs(abs(cdeg) - 180) < 12 and q > 0.75 and 2000 < n < 4500
      and len(cd.rim_loops_idx(new)) == 1 and off < 0.02 and a2.min() < -120 and a2.max() > 120)
bpy.data.meshes.remove(new); bpy.data.meshes.remove(me)

front = band & (np.abs(ang) < 40)
me, new = patch(front, 1200)
q, off, ratio, n = quality(new, me)
check(f'a front patch: the flat grid as before ({q * 100:.0f} % quads, {n} points)', q > 0.75 and off < 0.02)
q_front = q
bpy.data.meshes.remove(new); bpy.data.meshes.remove(me)

# a sleeve: the axis lies down (an arm along X)
bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=0.3, depth=3.0, rotation=(0.0, np.pi / 2, 0.0))
arm = C.active_object
bpy.ops.object.transform_apply(rotation=True)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.subdivide(number_cuts=40); bpy.ops.object.mode_set(mode='OBJECT')
body = arm
co = mio.read_co(body.data)
me, new = patch((np.abs(co[:, 0]) < 0.6) & (np.hypot(co[:, 1], co[:, 2]) > 0.29), 800)
chart = cd.wrap_chart(me, body)
q, off, ratio, n = quality(new, me)
check(f'a sleeve round an arm lying along X: the axis is the arm ({abs(chart["a"][0]):.3f}), a closed band of quads '
      f'({q * 100:.0f} %, {n} points)', abs(chart['a'][0]) > 0.99 and q > 0.99 and off < 0.02)
bpy.data.meshes.remove(new); bpy.data.meshes.remove(me)
summary()
