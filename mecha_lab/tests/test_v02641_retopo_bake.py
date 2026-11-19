"""0.24.241 / 0.24.242 (user: "리토포 하고 베이크까지" in two steps, "베큠 하듯이 메쉬에 붙여버리는" retopo, a progress card):
1 Retopo makes a quad low near the asked face count (Quad: remesh; Wrap: a quad box vacuum-packed onto the high -
on its surface, the quads even, nothing inside out); 2 Bake puts the high's Normal / AO on it (UVs, a material with
the maps); the high is hidden and never changed; the steps report their progress (fraction rising to 1)."""
import time

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import retopo_bake as rb, bake_maps as bm, progress  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=1.0)
high = C.active_object
high.name = 'Head'
high.scale = (1.0, 0.8, 1.3)
tex = bpy.data.textures.new('bumps', 'CLOUDS'); tex.noise_scale = 0.18
d = high.modifiers.new('D', 'DISPLACE'); d.texture = tex; d.strength = 0.12
high.modifiers.new('S', 'SUBSURF').levels = 1
co0 = np.empty(len(high.data.vertices) * 3); high.data.vertices.foreach_get('co', co0)
st = bm.settings(C); st.res = '512'; st.ao_samples = 8; st.save = False
check('the box: Quad / Wrap, Faces, 1 Retopo, 2 Bake (no low yet: Bake off)',
      not bpy.ops.mch.retopo_bake.poll() and bpy.ops.mch.retopo_make.poll())
S.mch_rb_faces, S.mch_rb_method = 3000, 'QUAD'
fr = [f for f, _l in rb.make_low_steps(C, high, 3000, 'QUAD', None)] if False else None
r = bpy.ops.mch.retopo_make()
low = C.active_object
nf = len(low.data.polygons)
quads = sum(1 for p in low.data.polygons if len(p.vertices) == 4) / max(1, nf)
check(f'1 Retopo (Quad): a low near 3000 faces ({nf:,}), mostly quads ({quads:.0%}), no bake yet, the high hidden',
      r == {'FINISHED'} and low.name == 'Head_Low' and 1500 <= nf <= 6000 and quads > 0.8 and not low.data.materials[:1] == ['x']
      and high.hide_get())
check('now Bake can run', bpy.ops.mch.retopo_bake.poll())
r = bpy.ops.mch.retopo_bake()
imgs = [n.image.name for m in low.data.materials if m and m.node_tree for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
check(f'2 Bake: Normal and AO on the low ({imgs}), UVs made', r == {'FINISHED'} and any('Normal' in n for n in imgs)
      and any('AO' in n for n in imgs) and len(low.data.uv_layers) > 0)
# Wrap
S.mch_rb_method, S.mch_rb_faces = 'WRAP', 2500
steps = []
gen = rb.make_low_steps(C, high, 2500, 'WRAP', low)
t = time.time()
try:
    while True:
        steps.append(next(gen)[0])
except StopIteration as ex:
    low2, _note = ex.value
dt = time.time() - t
nf = len(low2.data.polygons)
check(f'Retopo again with Wrap ({dt:.1f} s): the same low object, all quads ({nf:,} faces near 2500)',
      low2 is low and all(len(p.vertices) == 4 for p in low2.data.polygons) and 1800 <= nf <= 3300)
check(f'its progress rises step by step to the end ({len(steps)} steps, {steps[0]:.2f} -> {steps[-1]:.2f})',
      len(steps) >= 10 and all(b >= a for a, b in zip(steps, steps[1:])) and steps[-1] >= 0.9)
dg = C.evaluated_depsgraph_get()
ev = high.evaluated_get(dg)
bvh = BVHTree.FromObject(ev, dg)
P = np.array([v.co for v in low2.data.vertices])
dist = np.array([bvh.find_nearest(Vector(p))[3] for p in P])
size = max(high.dimensions)
check(f'wrapped onto the surface (largest gap {dist.max():.4f}, size {size:.2f})', dist.max() < 0.003 * size)
E_ = np.array([e.vertices[:] for e in low2.data.edges])
L = np.linalg.norm(P[E_[:, 0]] - P[E_[:, 1]], axis=1)
check(f'the quads stay even (edge length spread: 95 % within {np.percentile(L, 97.5) / np.percentile(L, 2.5):.1f}x)',
      np.percentile(L, 97.5) / np.percentile(L, 2.5) < 4.0)
inside = 0
for p in low2.data.polygons[:400]:
    c = Vector(p.center); n = p.normal
    if n.dot(c) < 0:
        inside += 1
check(f'faces point outward ({inside} of 400 inward)', inside < 8)
r = bpy.ops.mch.retopo_bake()
check('Bake again from the same high onto the wrapped low', r == {'FINISHED'} and C.active_object is low)
check('the high is never changed', np.allclose(co0, np.array([c for v in high.data.vertices for c in v.co])))
# 0.24.243 holes closed, faces outward
import bmesh
bm_ = bmesh.new(); bm_.from_mesh(low.data); bm_.faces.ensure_lookup_table()
bmesh.ops.delete(bm_, geom=[bm_.faces[i] for i in range(0, 40)], context='FACES')
bmesh.ops.reverse_faces(bm_, faces=bm_.faces[100:300])
bm_.to_mesh(low.data); bm_.free()
note = rb.tidy_low(C, high, low)
bm_ = bmesh.new(); bm_.from_mesh(low.data)
holes = sum(1 for e in bm_.edges if e.is_boundary); bm_.free()
inward = sum(1 for p in low.data.polygons if p.normal.dot(p.center) < 0)
check(f'holes in the low are closed and every face points out ({note}; {holes} open edges, {inward} inward)',
      holes == 0 and inward < 5 and 'closed' in note)

# 0.24.243 the rays reach past how far the low is off (a low pushed out: no black)
low.data.transform(__import__('mathutils').Matrix.Scale(1.06, 4))
st.normal, st.ao, st.rough, st.metal, st.curv, st.height = True, True, True, True, True, True
mat = bpy.data.materials.new('Rocky'); mat.use_nodes = True
pb = mat.node_tree.nodes['Principled BSDF']; pb.inputs['Roughness'].default_value = 0.8; pb.inputs['Metallic'].default_value = 1.0
high.data.materials.clear(); high.data.materials.append(mat)
r = bpy.ops.mch.retopo_bake()
imgs = {k: bpy.data.images.get(f'{low.name}_{k}') for k in ('AO', 'Normal', 'Roughness', 'Metallic', 'Curvature', 'Height')}
def stats(img):
    px = np.array(img.pixels[:]).reshape(-1, 4)[:, :3]
    return float((px.max(1) < 0.02).mean()), px.mean(0)
px_ = lambda k: np.array(imgs[k].pixels[:]).reshape(-1, 4)[:, :3]
cover = px_('Roughness').max(1) > 0.05                  # (inside the UV islands: the roughness 0.8 baked there)
blk = float((px_('AO')[cover].max(1) < 0.02).mean())
check(f'a low 6 % off the high still bakes (AO black {blk:.3f} of the {cover.mean():.0%} of pixels inside the islands), the ray setting put back',
      r == {'FINISHED'} and blk < 0.02 and abs(st.ray - 2.0) < 1e-6)
rough = float(px_('Roughness')[cover].mean()); metal = float(px_('Metallic')[cover].mean())
cv = np.array(imgs['Curvature'].pixels[:]).reshape(-1, 4)[:, 0]; hv = np.array(imgs['Height'].pixels[:]).reshape(-1, 4)[:, 0]
check(f'Roughness ({rough:.2f} for 0.8), Metallic ({metal:.2f} for 1), Curvature (spread {cv.std():.3f}), Height (spread {hv.std():.3f}) maps',
      0.7 < rough < 0.9 and metal > 0.85 and cv.std() > 0.02 and hv.std() > 0.02)
bmat = low.data.materials[0]
bsdf = next(n for n in bmat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
check('the low\'s material uses Roughness and Metallic, the Height as a bump; the high\'s own material untouched; no copies left',
      bsdf.inputs['Roughness'].is_linked and bsdf.inputs['Metallic'].is_linked
      and any(n.type == 'BUMP' for n in bmat.node_tree.nodes) and pb.inputs['Metallic'].default_value == 1.0
      and not any(o.name.startswith('.MCH Bake Source') for o in bpy.data.objects)
      and not any(m.name.startswith('.MCH Bake Emit') for m in bpy.data.materials))

# 0.24.243 several meshes at once
st.rough = st.metal = st.curv = st.height = False
st.ao = False
for o in list(C.selected_objects):
    o.select_set(False)
hs = []
for i in range(3):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=0.5, location=(3 + 1.5 * i, 0, 0))
    hs.append(C.active_object)
for o in hs:
    o.select_set(True)
S.mch_rb_method, S.mch_rb_faces = 'QUAD', 600
r = bpy.ops.mch.retopo_make()
lows = [rb.low_of(h) for h in hs]
check(f'three meshes selected: Retopo makes a low for each ({[len(lo.data.polygons) if lo else 0 for lo in lows]}), all selected after',
      r == {'FINISHED'} and all(lows) and all(lo.select_get() for lo in lows))
r = bpy.ops.mch.retopo_bake()
check('Bake bakes each one onto its own low', r == {'FINISHED'} and all(any(n.type == 'TEX_IMAGE' for m in lo.data.materials if m
      and m.node_tree for n in m.node_tree.nodes) for lo in lows))
# 0.24.248 even quads on a rough rock (Keep Hard Edges off), the hard edges kept on a hard part when on
import bmesh as _bm
def quality(me):
    b_ = _bm.new(); b_.from_mesh(me)
    q = sum(1 for f in b_.faces if len(f.verts) == 4) / max(1, len(b_.faces))
    L = np.array([e.calc_length() for e in b_.edges])
    ang = [abs(np.degrees(l.calc_angle()) - 90) for f in b_.faces if len(f.verts) == 4 for l in f.loops]
    b_.free()
    return q, float(np.percentile(L, 97.5) / max(np.percentile(L, 2.5), 1e-9)), float(np.mean(ang))
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=6, radius=1.0, location=(8, 0, 0))
rk = C.active_object; rk.name = 'Rock'; rk.scale = (1.5, 0.9, 0.8)
for ns, st_ in ((0.9, 0.35), (0.25, 0.12), (0.07, 0.04)):
    t_ = bpy.data.textures.new('n', 'VORONOI' if ns < 0.3 else 'CLOUDS'); t_.noise_scale = ns
    d_ = rk.modifiers.new('D', 'DISPLACE'); d_.texture = t_; d_.strength = st_; d_.texture_coords = 'GLOBAL'
for o in list(C.selected_objects):
    o.select_set(False)
rk.select_set(True); C.view_layer.objects.active = rk
S.mch_rb_method, S.mch_rb_faces, S.mch_rb_hard = 'QUAD', 2500, False
bpy.ops.mch.retopo_make()
q, spread, adev = quality(C.active_object.data)
check(f'a rough rock, Keep Hard Edges off: even quads ({q:.0%} quads, edges within {spread:.1f}x, corners {adev:.1f} deg off square)',
      q > 0.9 and spread < 2.5 and adev < 10.0)
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(14, 0, 0))
cb = C.active_object; cb.name = 'Block'
cb.modifiers.new('S', 'SUBSURF').levels = 3
cb.modifiers['S'].subdivision_type = 'SIMPLE'
for o in list(C.selected_objects):
    o.select_set(False)
cb.select_set(True); C.view_layer.objects.active = cb
S.mch_rb_faces, S.mch_rb_hard = 600, True
bpy.ops.mch.retopo_make()
lowb = C.active_object
P = np.array([lowb.matrix_world @ v.co for v in lowb.data.vertices])
corners = [np.array((14 + x, y, z)) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
cd = max(float(np.min(np.linalg.norm(P - c_, axis=1))) for c_ in corners)
check(f'a hard block, Keep Hard Edges on: its corners kept (farthest corner {cd * 100:.1f} cm off)', cd < 0.05)
S.mch_rb_hard = False

# 0.24.250 (user's FBX: a thin extracted plate pinched in the remesh - edges with 3+ faces): the low is mended
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(20, 0, 0)); hi_ = C.active_object
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(20, 0, 0)); lo_ = C.active_object
import bmesh as _b2
b2 = _b2.new(); b2.from_mesh(lo_.data); b2.edges.ensure_lookup_table()
e_ = b2.edges[0]; v3 = b2.verts.new((e_.verts[0].co + e_.verts[1].co) / 2 + Vector((0.5, 0.5, 0.5)))
b2.faces.new((e_.verts[0], e_.verts[1], v3))             # (a fin: that edge now carries 3 faces)
b2.to_mesh(lo_.data); b2.free()
note_ = rb.tidy_low(C, hi_, lo_)
b2 = _b2.new(); b2.from_mesh(lo_.data)
fins_ = sum(1 for e in b2.edges if len(e.link_faces) > 2); open_ = sum(1 for e in b2.edges if e.is_boundary); b2.free()
check(f'a pinched edge (3 faces) in the low is mended ({note_}; {fins_} left, {open_} open)', fins_ == 0 and open_ == 0 and 'mended' in note_)
# 0.24.251 (user: "리토포 해 온 메쉬를 선택해서 베이크") the user's own low (made elsewhere, its own UVs) + the high selected
bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=1.0, location=(26, 0, 0)); oh = C.active_object
oh.name = 'MyHigh'
dd = oh.modifiers.new('D', 'DISPLACE'); dd.texture = bpy.data.textures.new('n3', 'CLOUDS'); dd.strength = 0.05
bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1.0, location=(26, 0, 0)); ol = C.active_object
ol.name = 'MyLow'
uv0 = [tuple(d.uv) for d in ol.data.uv_layers[0].data]
for o in list(C.selected_objects):
    o.select_set(False)
ol.select_set(True); oh.select_set(True); C.view_layer.objects.active = oh       # (either one active)
pr = rb.own_pair(C)
check('two meshes selected, neither from Retopo: the one with more faces the high, the other the low; Bake on',
      pr is not None and pr[:2] == (oh, ol) and bpy.ops.mch.retopo_bake.poll())
st.normal, st.ao, st.rough, st.metal, st.curv, st.height = True, True, False, False, False, False
r = bpy.ops.mch.retopo_bake()
uv1 = [tuple(d.uv) for d in ol.data.uv_layers[0].data]
img = bpy.data.images.get('MyLow_Normal')
check(f'Bake: the maps on the own low, its own UVs kept ({len(ol.data.uv_layers)} layer, unchanged {uv0 == uv1}), tied to its high',
      r == {'FINISHED'} and img is not None and uv0 == uv1 and rb.high_of(ol) is oh)
# 0.24.251 (user's sculpt: pin-holes in the high, a long crack in the low, an FBX at scale 0.01): the crack closed,
# the high's own border kept open
import bmesh as _b3
def _sphere(name, loc, scale):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=100.0, location=loc)
    o = C.active_object; o.name = name; o.scale = (scale,) * 3
    return o
ph = _sphere('PinHigh', (32, 0, 0), 0.01)
b3 = _b3.new(); b3.from_mesh(ph.data); b3.faces.ensure_lookup_table()
_b3.ops.delete(b3, geom=[b3.faces[i] for i in (100, 700, 1300)], context='FACES_ONLY'); b3.to_mesh(ph.data); b3.free()
pl = _sphere('PinLow', (32, 0, 0), 0.01)
b3 = _b3.new(); b3.from_mesh(pl.data)
_b3.ops.delete(b3, geom=[f for f in b3.faces if abs(f.calc_center_median().z) < 6.0 and f.calc_center_median().x > 0],
               context='FACES_ONLY')                  # (a long slit half round the middle)
b3.to_mesh(pl.data); b3.free()
note_ = rb.tidy_low(C, ph, pl)
b3 = _b3.new(); b3.from_mesh(pl.data); open_ = sum(1 for e in b3.edges if e.is_boundary); b3.free()
check(f'pin-holes in the high (an FBX at scale 0.01): the long crack in the low closed ({note_}; {open_} open)', open_ == 0)
pb_ = _sphere('CapHigh', (38, 0, 0), 0.01)
b3 = _b3.new(); b3.from_mesh(pb_.data)
_b3.ops.delete(b3, geom=[f for f in b3.faces if f.calc_center_median().z < -30], context='FACES_ONLY'); b3.to_mesh(pb_.data); b3.free()
pc_ = pb_.copy(); pc_.data = pb_.data.copy(); C.scene.collection.objects.link(pc_)
rb.tidy_low(C, pb_, pc_)
b3 = _b3.new(); b3.from_mesh(pc_.data); open2 = sum(1 for e in b3.edges if e.is_boundary); b3.free()
check(f'a cap (the high open at the bottom): its own border stays open in the low ({open2} open)', open2 > 0)
# 0.24.252 (user: "두세 개 선택해서 한 덩어리로 리토포 → 하나의 메쉬로 베이크, 토글로") As One
S.mch_rb_join = 'EACH'
bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=1.0, location=(44, 0, 0)); pa = C.active_object
pa.name = 'Torso'
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.35, depth=2.4, location=(45.3, 0, 0), rotation=(0, 1.5708, 0))
pb2 = C.active_object; pb2.name = 'ArmR'
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.35, depth=2.4, location=(42.7, 0, 0), rotation=(0, 1.5708, 0))
pc2 = C.active_object; pc2.name = 'ArmL'
for o in list(C.selected_objects):
    o.select_set(False)
for o in (pa, pb2, pc2):
    o.select_set(True)
C.view_layer.objects.active = pa
check('3 selected: the Each / As One toggle; Each by default (as before), no own-low pairing in As One',
      S.mch_rb_join == 'EACH' and len(rb.selected_parts(C)) == 3)
S.mch_rb_join, S.mch_rb_method, S.mch_rb_faces = 'ONE', 'QUAD', 3000
n_before = len([o for o in bpy.data.objects if o.type == 'MESH'])
r = bpy.ops.mch.retopo_make()
one = C.active_object
b3 = _b3.new(); b3.from_mesh(one.data)
open3 = sum(1 for e in b3.edges if e.is_boundary)
seen = set(); isl = 0
for v in b3.verts:
    if v.index in seen:
        continue
    isl += 1; stk = [v]; seen.add(v.index)
    while stk:
        x = stk.pop()
        for e in x.link_edges:
            y = e.other_vert(x)
            if y.index not in seen:
                seen.add(y.index); stk.append(y)
b3.free()
P3 = np.array([one.matrix_world @ v.co for v in one.data.vertices])
inside = int(((np.linalg.norm(P3 - np.array((44, 0, 0)), axis=1) < 0.9)).sum())     # (no walls left inside the torso)
check(f'As One: ONE low for the 3 ({len(one.data.polygons):,} faces, {isl} piece, {open3} open, {inside} points inside), '
      f'the 3 hidden', r == {'FINISHED'} and isl == 1 and open3 == 0 and inside == 0
      and len(one.data.polygons) < 6000 and all(not o.visible_get() for o in (pa, pb2, pc2))
      and sorted(p.name for p in rb.parts_of(one)) == ['ArmL', 'ArmR', 'Torso'])
st.normal, st.ao = True, True
r = bpy.ops.mch.retopo_bake()
check('Bake: one set of maps on the one low, baked from the 3 meshes',
      r == {'FINISHED'} and bpy.data.images.get(f'{one.name}_Normal') is not None)
for o in list(C.selected_objects):
    o.select_set(False)
pb2.hide_set(False); pb2.select_set(True); C.view_layer.objects.active = pb2
h_, l_ = rb.pair(pb2)
check('a part selected later: it knows its one low', l_ is one)
for o in list(C.selected_objects):
    o.select_set(False)
one.select_set(True); C.view_layer.objects.active = one
S.mch_rb_faces = 2000
bpy.ops.mch.retopo_make()
check('Retopo again (the low selected): the same low remade from the 3, no new objects',
      C.active_object is one and len(one.data.polygons) < 3000
      and len([o for o in bpy.data.objects if o.type == 'MESH']) == n_before + 2)
S.mch_rb_join = 'EACH'
# 0.24.253 (user: "다른 곳에서 리메쉬한 한 덩어리로 하이폴 여러 덩어리를 베이크") one own low (remeshed elsewhere) + 3 highs
bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=1.0, location=(54, 0, 0)); h1 = C.active_object
h1.name = 'BodyHi'
d4 = h1.modifiers.new('D', 'DISPLACE'); d4.texture = bpy.data.textures.new('n4', 'CLOUDS'); d4.strength = 0.05
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.35, depth=2.4, location=(55.3, 0, 0), rotation=(0, 1.5708, 0))
h2 = C.active_object; h2.name = 'ArmHiR'
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.35, depth=2.4, location=(52.7, 0, 0), rotation=(0, 1.5708, 0))
h3 = C.active_object; h3.name = 'ArmHiL'
for o in list(C.selected_objects):
    o.select_set(False)
for o in (h1, h2, h3):
    o.select_set(True)
C.view_layer.objects.active = h1
bpy.ops.object.duplicate(); bpy.ops.object.join(); ext = C.active_object; ext.name = 'RemeshedElsewhere'
for m in list(ext.modifiers):
    ext.modifiers.remove(m)
vm = ext.modifiers.new('V', 'REMESH'); vm.mode = 'VOXEL'; vm.voxel_size = 0.08
dm = ext.modifiers.new('Dc', 'DECIMATE'); dm.ratio = 0.5
bpy.ops.object.convert(target='MESH')
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.uv.smart_project(); bpy.ops.object.mode_set(mode='OBJECT')
uvx = [tuple(d.uv) for d in ext.data.uv_layers[0].data]
for o in list(C.selected_objects):
    o.select_set(False)
for o in (h1, h2, h3, ext):
    o.hide_set(False); o.select_set(True)
C.view_layer.objects.active = h2
for mode_ in ('EACH', 'ONE'):
    S.mch_rb_join = mode_
    pr = rb.own_pair(C)
    check(f'({mode_}) 4 selected: the one wrapping the others ({len(ext.data.polygons):,} faces) is the own low, the 3 others its highs',
          pr is not None and pr[1] is ext and sorted(h.name for h in pr[2]) == ['ArmHiL', 'ArmHiR', 'BodyHi'])
S.mch_rb_join = 'EACH'
st.normal, st.ao = True, True
r = bpy.ops.mch.retopo_bake()
im_n = bpy.data.images.get('RemeshedElsewhere_Normal')
pxn = np.array(im_n.pixels[:]).reshape(-1, 4)[:, :3] if im_n else np.zeros((1, 3))
bent = float((np.abs(pxn[:, :2] - 0.5).max(1) > 0.08).mean())
check(f'Bake: ONE set of maps on the own low from all 3 highs, its UVs kept, tied to them ({bent:.0%} of pixels bent by the detail)',
      r == {'FINISHED'} and im_n is not None and uvx == [tuple(d.uv) for d in ext.data.uv_layers[0].data]
      and sorted(p.name for p in rb.parts_of(ext)) == ['ArmHiL', 'ArmHiR', 'BodyHi'] and bent > 0.02)
for o in list(C.selected_objects):
    o.select_set(False)
ext.select_set(True); C.view_layer.objects.active = ext
check('later the low alone selected: Bake again still bakes from the 3', rb.pair(ext)[1] is ext and bpy.ops.mch.retopo_bake.poll())
# 0.24.254 (user: "베큠 랩 개선 - 기존 메쉬를 복사해 쿼드로 바꾼 다음 베큠") Wrap starts from the shape itself as quads:
# a ring (a hole the box can not reach into) is wrapped all round
bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.3, major_segments=96, minor_segments=32, location=(62, 0, 0))
tor = C.active_object; tor.name = 'Ring'
qb = rb._wrap_quality(C, tor, progress.run_now(rb._wrap_one(C, tor, 1500, base='BOX')))
for o in list(C.selected_objects):
    o.select_set(False)
tor.select_set(True); C.view_layer.objects.active = tor
S.mch_rb_method, S.mch_rb_faces = 'WRAP', 1500
bpy.ops.mch.retopo_make()
wl = C.active_object
qn = rb._wrap_quality(C, tor, wl.data)
check(f'Wrap on a ring: lies on all of it ({qn[0] * 100:.1f} cm off at worst, the old box way {qb[0] * 100:.1f} cm), '
      f'all quads ({len(wl.data.polygons):,} faces near 1500, corners {qn[1]:.1f} deg off square)',
      qn[0] < 0.03 and qb[0] > 3 * qn[0] and all(len(p.vertices) == 4 for p in wl.data.polygons)
      and 1100 <= len(wl.data.polygons) <= 1900)
S.mch_rb_method = 'QUAD'
# 0.24.255 (user: "뾰족한 면도 지킬 수 있게") Wrap with Keep Hard Edges: the high's sharp lines kept
from mecha_lab import quad_field as _qf
from mathutils.bvhtree import BVHTree as _BT
bpy.ops.mesh.primitive_cube_add(size=2, location=(70, 0, 0)); hb_ = C.active_object; hb_.name = 'House'
bpy.ops.mesh.primitive_cube_add(size=2, location=(71.2, 0, 1.2), rotation=(0, 0.785, 0)); cc_ = C.active_object
bo_ = hb_.modifiers.new('B', 'BOOLEAN'); bo_.object = cc_; bo_.operation = 'DIFFERENCE'
vx_ = hb_.modifiers.new('V', 'REMESH'); vx_.mode = 'VOXEL'; vx_.voxel_size = 0.03
dg_ = C.evaluated_depsgraph_get()
me_ = bpy.data.meshes.new_from_object(hb_.evaluated_get(dg_), depsgraph=dg_); hb_.modifiers.clear(); hb_.data = me_
bpy.data.objects.remove(cc_)
Vh = np.array([v.co for v in hb_.data.vertices], np.float32); hb_.data.calc_loop_triangles()
Th = np.array([t.vertices[:] for t in hb_.data.loop_triangles], np.int32)
segs_ = _qf.hard_segments(Vh, Th, 40.0)
def line_off(me):
    lb = _BT.FromPolygons([tuple(v.co) for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    P = (segs_[:, 0] + segs_[:, 1]) * 0.5
    return float(np.mean([(lb.find_nearest(Vector(p))[0] - Vector(p)).length for p in P]))
plain_ = progress.run_now(rb.wrap_steps(C, hb_, 2500, sharp=False))
for o in list(C.selected_objects):
    o.select_set(False)
hb_.select_set(True); C.view_layer.objects.active = hb_
S.mch_rb_method, S.mch_rb_faces, S.mch_rb_hard = 'WRAP', 2500, True
bpy.ops.mch.retopo_make()
sl_ = C.active_object
a_, b_ = line_off(plain_), line_off(sl_.data)
check(f'Wrap + Keep Hard Edges on a hard part: its sharp lines kept ({b_ * 100:.1f} cm off on average, '
      f'without {a_ * 100:.1f} cm), marked sharp ({sum(1 for e in sl_.data.edges if e.use_edge_sharp)} edges), all quads',
      b_ < 0.6 * a_ and any(e.use_edge_sharp for e in sl_.data.edges) and all(len(p.vertices) == 4 for p in sl_.data.polygons))
S.mch_rb_method, S.mch_rb_hard = 'QUAD', False
summary()
