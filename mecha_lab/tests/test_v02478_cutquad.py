"""0.24.75 Quad Remesh of low-poly parts (made with Base Mesh + Cut, or decimated): laid out as even triangles first
(its points and edges kept, every face filled on its own plane), its own edges as the quads' fixed lines, finer while a
groove narrower than a quad leaves holes, what is still open closed - an open plate's own border stays open."""
import math
import time

import numpy as np

from _harness import bmesh, bpy, check, fresh, summary
from mathutils import Quaternion, Vector
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import base_mesh as bmm, core_geometry as cg, cut_engine as ce, fast_decimate as fd, quad_field as qf

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
S.mch_settings.auto_apply = True
PPU = 400.0
TOP = cg.OrthoProjector(Quaternion(), center=Vector((0, 0, 0)), pixels_per_unit=PPU)
FRONT = cg.OrthoProjector(Quaternion((1, 0, 0), math.radians(90)), center=Vector((0, 0, 0)), pixels_per_unit=PPU)
cut = S.mch_cut
cut.targets = 'ACTIVE'


def P(x, y):
    return (500 + x * PPU, 500 + y * PPU)


def rect(cx, cy, w, h):
    return ce.rect_loop(P(cx - w / 2, cy - h / 2), P(cx + w / 2, cy + h / 2))


def select(ob):
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob


def apply_all(ob):
    dg = C.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)


def cut_part(name, profile='CHAMFER', slot=None):
    """A Base Mesh block (rounded corners, chamfered top) with a pocket, a round hole and a side notch cut in.
    (The scene is emptied first: a Base Mesh drawn over another part is built on it.)"""
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    s = S.mch_base
    s.profile, s.height, s.bevel_width, s.bevel_segments, s.bevel_sides, s.offset = profile, 0.25, 0.04, 3, 'TOP', 0.0
    lp = ce.round_corners(rect(0, 0, 1.0, 0.6), 0.1 * PPU, 'ROUND', 6)
    before = set(bpy.data.objects)
    bmm.perform_base(C, [lp], TOP)
    ob = [o for o in bpy.data.objects if o not in before][0]
    ob.name = name
    select(ob)
    apply_all(ob)
    cut.gn_finish, cut.gn_ramp = 'NONE', False
    cut.depth_mode, cut.depth = 'SURFACE', 0.1
    ce.perform_closed(C, 'CUT', [ob], [rect(-0.15, 0.0, 0.35, 0.25)], TOP)
    ce.perform_closed(C, 'CUT', [ob], [ce.circle_loop(P(0.3, 0.05), P(0.38, 0.05), 24)], TOP)
    if slot is not None:
        ce.perform_closed(C, 'CUT', [ob], [rect(0.0, -0.22, 0.7, slot)], TOP)
    select(ob)
    apply_all(ob)
    return ob


def stats(ob, ref_me):
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    open_ = sum(1 for e in bm.edges if not e.is_manifold)
    quads = sum(1 for f in bm.faces if len(f.verts) == 4) / max(1, len(bm.faces))
    ref = bmesh.new()
    ref.from_mesh(ref_me)
    bvh = BVHTree.FromBMesh(ref)
    size = max(ob.dimensions)
    dev = max(bvh.find_nearest(v.co)[3] for v in bm.verts) / size
    ref.free()
    bm.free()
    return open_, quads, dev


def sharp_kept(ref_me, ob, deg=30.0, h=None):
    """Part of the original's sharp edges (longer than 2 quads, away from corners) that the result's marked hard
    edges run along."""
    bm = bmesh.new()
    bm.from_mesh(ref_me)
    bm.normal_update()
    res = ob.data
    hard = res.attributes.get('.mch_he_hard') or res.attributes.get('sharp_edge')
    vals = [False] * len(res.edges)
    if hard is not None:
        hard.data.foreach_get('value', vals)
    from mathutils.kdtree import KDTree
    pts = []
    for e, v in zip(res.edges, vals):
        if v:
            a, b = res.vertices[e.vertices[0]].co, res.vertices[e.vertices[1]].co
            pts += [a.lerp(b, t / 4) for t in range(5)]
    kd = KDTree(max(1, len(pts)))
    for k, p in enumerate(pts):
        kd.insert(p, k)
    kd.balance()
    tot = hit = 0.0
    for e in bm.edges:
        if len(e.link_faces) != 2 or e.calc_length() < 2 * h:
            continue
        if math.degrees(e.link_faces[0].normal.angle(e.link_faces[1].normal, 0.0)) < deg + 10:
            continue
        a, b = e.verts[0].co, e.verts[1].co
        n = max(2, int(e.calc_length() / (0.25 * h)))
        for t in range(1, n):
            f = t / n
            if min(f, 1 - f) * e.calc_length() < h:          # (corners: the grid turns there)
                continue
            q = a.lerp(b, f)
            tot += 1
            if pts and kd.find(q)[2] < 0.3 * h:
                hit += 1
    bm.free()
    return hit / max(1.0, tot)


# --- a Base Mesh + Cut part ---------------------------------------------------------------------------------------
src = cut_part('Part')
ref = src.data.copy()
src.data.calc_loop_triangles()
check('The test part is a low-poly cut part (n-gons): it takes the new way',
      qf.is_cut_mesh(src.data, 1500) and len(src.data.polygons) < 600, len(src.data.polygons))
old = src.copy()
old.data = src.data.copy()
S.collection.objects.link(old)
real = qf.is_cut_mesh
qf.is_cut_mesh = lambda me, t: False
qf.remesh_object(old, 1500)
qf.is_cut_mesh = real
o_open, o_quads, o_dev = stats(old, ref)
t0 = time.perf_counter()
msg = qf.remesh_object(src, 1500)
dt = time.perf_counter() - t0
n_open, n_quads, n_dev = stats(src, ref)
check('Message says the part\'s own edges were kept', 'own edges kept' in msg, msg)
check('Closed: no open sides (0.24.83: the old way is guarded the same now - a closed part comes back closed)',
      n_open == 0 and o_open == 0, (n_open, o_open))
check('Mostly quads: at least 90 % (old way on the same part less)', n_quads >= 0.9 and n_quads > o_quads,
      (round(n_quads, 3), round(o_quads, 3)))
check('On the original surface: every point within 1 % of the part size', n_dev < 0.01, round(n_dev, 5))
nf = len(src.data.polygons)
check('About the asked count (1,500; up to 4x when it had to go finer)', 1000 <= nf <= 1500 * 4 * 1.4, nf)
st_h = math.sqrt(sum(p.area for p in ref.polygons) / nf)
kept = sharp_kept(ref, src, h=st_h)
check('The cut edges become marked hard edges (at least 85 % of their length away from corners)', kept >= 0.85,
      round(kept, 3))
check('Fast: under 5 s', dt < 5.0, round(dt, 2))
twin = cut_part('Twin')
twin2 = twin.copy()
twin2.data = twin.data.copy()
S.collection.objects.link(twin2)
qf.remesh_object(twin, 1500)
qf.remesh_object(twin2, 1500)
check('Same mesh, same result (deterministic)', len(twin.data.polygons) == len(twin2.data.polygons)
      and len(twin.data.vertices) == len(twin2.data.vertices), (len(twin.data.polygons), len(twin2.data.polygons)))

# --- materials, polygroup-like face attribute, mask come along ---------------------------------------------------
mp = cut_part('Painted')
m0, m1 = bpy.data.materials.new('a'), bpy.data.materials.new('b')
mp.data.materials.append(m0)
mp.data.materials.append(m1)
for p in mp.data.polygons:
    p.material_index = 1 if p.center.x > 0.2 else 0
mask = mp.data.attributes.new('.sculpt_mask', 'FLOAT', 'POINT')
mask.data.foreach_set('value', [1.0 if v.co.x < -0.3 else 0.0 for v in mp.data.vertices])
pref = mp.data.copy()
pbm0 = bmesh.new()
pbm0.from_mesh(pref)
pbvh = BVHTree.FromBMesh(pbm0)
pmat = [f.material_index for f in pbm0.faces]
pbm0.free()
pmask = [1.0 if v.co.x < -0.3 else 0.0 for v in pref.vertices]
from mathutils.kdtree import KDTree
pkd = KDTree(len(pref.vertices))
for v in pref.vertices:
    pkd.insert(v.co, v.index)
pkd.balance()
qf.remesh_object(mp, 1500)
same = [pmat[pbvh.find_nearest(p.center)[2]] == p.material_index for p in mp.data.polygons]
check('Materials come along: each face has the material of the input face under it (95 %+)',
      sum(same) / len(same) > 0.95 and len(mp.data.materials) >= 2 and len(set(pmat)) == 2, round(sum(same) / len(same), 3))
mk = mp.data.attributes.get('.sculpt_mask')
mv = [0.0] * len(mp.data.vertices)
if mk is not None:
    mk.data.foreach_get('value', mv)
msame = [abs(m - pmask[pkd.find(v.co)[1]]) < 1e-6 for m, v in zip(mv, mp.data.vertices)]
check('Mask comes along (each point: the mask of the nearest input point)',
      mk is not None and sum(msame) / len(msame) > 0.98 and 0 < sum(mv) < len(mv), round(sum(msame) / len(msame), 3))

# --- a slot narrower than a quad: finer, still closed --------------------------------------------------------------
sp = cut_part('Slot', slot=0.012)
sref = sp.data.copy()
msg = qf.remesh_object(sp, 800)
s_open, s_quads, s_dev = stats(sp, sref)
check('A slot narrower than a quad: closed, on the surface', s_open == 0 and s_dev < 0.01, (s_open, round(s_dev, 5), msg))

# --- All Quads ----------------------------------------------------------------------------------------------------
aq = cut_part('AllQuads')
aref = aq.data.copy()
qf.remesh_object(aq, 1500, all_quads=True)
a_open, a_quads, a_dev = stats(aq, aref)
check('All Quads on a cut part: closed, (almost) all quads', a_open == 0 and a_quads >= 0.98, (a_open, round(a_quads, 3)))

# --- an open low-poly plate keeps its border ----------------------------------------------------------------------
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=3, y_segments=2, size=1.0)
pm = bpy.data.meshes.new('Plate')
bm.to_mesh(pm)
bm.free()
plate = bpy.data.objects.new('Plate', pm)
S.collection.objects.link(plate)
pm.calc_loop_triangles()
msg = qf.remesh_object(plate, 400)
pbm = bmesh.new()
pbm.from_mesh(plate.data)
border = [e for e in pbm.edges if e.is_boundary]
blen = sum(e.calc_length() for e in border)
inner_open = [e for e in pbm.edges if e.is_boundary and max(abs(c) for c in ((e.verts[0].co + e.verts[1].co) * 0.5).xy) < 0.95]
pbm.free()
check('An open low-poly plate: its border stays open (not capped), no extra rounds, no holes inside',
      abs(blen - 8.0) < 0.05 and not inner_open and 'finer' not in msg and 'closed' not in msg,
      (round(blen, 3), len(inner_open), msg))

# --- a decimated part (DynaMesh + Decimate) still fine ------------------------------------------------------------
dp = cut_part('Dyn')
dp.data.remesh_voxel_size = 0.01
with C.temp_override(object=dp, active_object=dp, selected_objects=[dp], selected_editable_objects=[dp]):
    bpy.ops.object.voxel_remesh()
dref = dp.data.copy()
fd.decimate_object(dp, 8.0)
dp.data.calc_loop_triangles()
low = qf.is_cut_mesh(dp.data, 1500)
qf.remesh_object(dp, 1500)
d_open, d_quads, d_dev = stats(dp, dref)
check('A decimated part also takes the new way: closed, 90 %+ quads, on the surface',
      low and d_open == 0 and d_quads >= 0.9 and d_dev < 0.01, (low, d_open, round(d_quads, 3), round(d_dev, 5)))

# --- a dense part keeps the old way -------------------------------------------------------------------------------
big = cut_part('Dense')
big.data.remesh_voxel_size = 0.006
with C.temp_override(object=big, active_object=big, selected_objects=[big], selected_editable_objects=[big]):
    bpy.ops.object.voxel_remesh()
big.data.calc_loop_triangles()
check('A dense (DynaMesh) part keeps the sampled way (not the low-poly one)', not qf.is_cut_mesh(big.data, 1500),
      len(big.data.loop_triangles))

summary()
