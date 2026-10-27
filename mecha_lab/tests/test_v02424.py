"""0.24.24 Mech Ridge (Armor Plate profile): every outline edge slopes up to crisp ridge lines (a box = a hip roof),
Max Height = flat top, Edge Patterns (Hip / Gable / Every Other / Half Hip / Corner / Shed / Custom per edge) + Turn, Chamfer / Bevel on the ridge lines and the outer edge, live sliders, Apply.  Cut / Split
Crisp Shading: the bevel band has sharp borders, a chamfer is flat, imported custom normals are dropped; the rim
cleanup keeps the rim on the cut (no zigzag)."""
import math

from _harness import bpy, bmesh, check, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import armor_plate as ap, core_geometry as cg, cut_engine as ce, mech_ridge as mr

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion())

# pure helpers
sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
check('ccw keeps a counter-clockwise outline, flips a clockwise one', mr.ccw(sq) == [tuple(map(float, q)) for q in sq]
      and mr.signed_area(mr.ccw(sq[::-1])) > 0)
wobbly = [(x, 0.3 * math.sin(x)) for x in range(0, 41)] + [(40, 20), (0, 20)]
simple = mr.simplify_closed(wobbly, 2.0)
check('Straighten: a wobbly free-drawn side becomes one straight edge', len(simple) == 4, simple)
pl = mr.wedge_planes(mr.ccw(sq), 0, math.tan(math.radians(45)), 1.0)
inside_above = Vector((5, 1, 5))
check('wedge of the bottom edge: a point above its slope near it is cut', all(a.dot(inside_above) + d >= 0 for a, d in pl))
check('...a point below its slope is kept', not all(a.dot(Vector((5, 3, 2))) + d >= 0 for a, d in pl))


def body(kind='cube'):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    if kind == 'cube':
        bpy.ops.mesh.primitive_cube_add(size=8, location=(0, 0, -4))
    else:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=6, segments=64, ring_count=32, location=(0, 0, -5.6))
    return C.active_object


def up_normals(ob):
    mw = ob.matrix_world.to_3x3()
    ob.data.update()
    return {tuple(round(c, 2) for c in (mw @ p.normal).normalized()) for p in ob.data.polygons
            if (mw @ p.normal).z > 0.3}


BOX = [[(380, 420), (620, 420), (620, 580), (380, 580)]]
st = S.mch_mridge
S.mch_plate.preset = 'MRIDGE'
st.ridge_finish = st.edge_finish = 'NONE'
st.angle, st.height = math.radians(25), 0.0
body()
msg = ap.perform_plate(C, BOX, TOP)
ob = C.active_object
check('Armor Plate profile Mech Ridge makes a live Mech Ridge plate', mr.live_plate(C) == ob and 'Mech Ridge' in msg, msg)
check('closed mesh', non_manifold(ob) == 0, non_manifold(ob))
check('a box = a hip roof: exactly 4 flat sloped facets (crisp, no rounding)', len(up_normals(ob)) == 4, up_normals(ob))
check('every facet rises at the Slope angle', all(abs(math.degrees(math.acos(n[2])) - 25) < 1.5 for n in up_normals(ob)),
      up_normals(ob))
zs = [(ob.matrix_world @ v.co).z for v in ob.data.vertices]
wall, sink = 0.03 * math.hypot(2.4, 1.6), 0.02 * math.hypot(2.4, 1.6)
want = wall + 0.8 * math.tan(math.radians(25)) - sink
check('ridge height = edge wall + half width x tan(Slope)', abs(max(zs) - want) < 0.03, (max(zs), want))
check('the bottom sits in the surface (Sink)', min(zs) < 0)
ob.mch_mridge.height = 0.2
zs = [(ob.matrix_world @ v.co).z for v in ob.data.vertices]
check('Max Height: cut flat (a mesa top), live', abs(max(zs) - (0.2 - sink)) < 0.02 and
      (0.0, 0.0, 1.0) in up_normals(ob), max(zs))
ob.mch_mridge.height = 0.0
n0 = len(ob.data.polygons)
ob.mch_mridge.ridge_finish = 'CHAMFER'
n1 = len(ob.data.polygons)
check('Ridge Chamfer adds flat strips on the ridge lines', n1 > n0 and len(up_normals(ob)) > 4, (n0, n1))
ob.mch_mridge.ridge_finish = 'BEVEL'
ob.mch_mridge.ridge_segments = 4
check('Ridge Bevel (4 segments): more faces, shaded round', len(ob.data.polygons) > n1
      and any(p.use_smooth for p in ob.data.polygons))
sharp = ob.data.attributes.get('sharp_edge')
n_sharp = sum(1 for v in sharp.data if v.value) if sharp else 0
check('...the creases (chamfer / bevel borders, walls) are marked sharp (crisp), the bevel steps are not',
      n_sharp > 8 and n_sharp < len(ob.data.edges) // 2, (n_sharp, len(ob.data.edges)))
ob.mch_mridge.edge_finish = 'CHAMFER'
ob.mch_mridge.edge_width = 0.05
check('Outer Edge Chamfer works too, still closed', non_manifold(ob) == 0 and ob.mch_mridge.last_error == '',
      ob.mch_mridge.last_error)
check('the next plate starts with these settings', S.mch_mridge.ridge_finish == 'BEVEL' and S.mch_mridge.edge_finish == 'CHAMFER')
# 0.24.25 Edge Pattern + Turn + per-edge toggles
ob.mch_mridge.ridge_finish = ob.mch_mridge.edge_finish = 'NONE'
mw = ob.matrix_world


def ridge_span(o):
    top = max((mw @ v.co).z for v in o.data.vertices)
    xs = [(mw @ v.co).x for v in o.data.vertices if (mw @ v.co).z > top - 1e-3]
    return min(xs), max(xs)


ob.mch_mridge.pattern = 'LONG'
ups = up_normals(ob)
check('Gable (long side): only the 2 long slopes (no sloped end triangles)', len(ups) == 2
      and all(abs(n[0]) < 0.01 for n in ups), ups)
lo_x, hi_x = ridge_span(ob)
check('...the ridge reaches both ends of the plate', lo_x < -1.15 and hi_x > 1.15, (lo_x, hi_x))
check('...closed mesh', non_manifold(ob) == 0)
check('the panel knows which edges slope (mask per edge)', sorted(ob[mr.MASK_KEY]) == ['0', '0', '1', '1'], ob.get(mr.MASK_KEY))
bpy.ops.mch.mridge_turn(step=1)
ups = up_normals(ob)
check('Turn: the gable runs across instead', ob.mch_mridge.turn == 1 and len(ups) == 2
      and all(abs(n[1]) < 0.01 for n in ups), ups)
ob.mch_mridge.turn = 0
ob.mch_mridge.pattern = 'SHED'
ups = up_normals(ob)
check('Shed: one single slope', len(ups) == 1, ups)
check('...closed, rising to the upright far side', non_manifold(ob) == 0)
first = ups
bpy.ops.mch.mridge_turn(step=1)
check('Turn moves the Shed slope to the next edge', up_normals(ob) != first and len(up_normals(ob)) == 1)
ob.mch_mridge.pattern = 'HALF'
check('Half Hip: 3 slopes (one upright end)', len(up_normals(ob)) == 3, up_normals(ob))
ob.mch_mridge.pattern = 'CORNER'
check('Corner: 2 neighbouring slopes', len(up_normals(ob)) == 2 and non_manifold(ob) == 0, up_normals(ob))
ob.mch_mridge.pattern = 'ALTERNATE'
check('Every Other Edge: 2 opposite slopes on a box', len(up_normals(ob)) == 2, up_normals(ob))
ob.mch_mridge.pattern, ob.mch_mridge.turn = 'HIP', 0
r = bpy.ops.mch.mridge_edge_toggle(index=0)
check('an edge button makes that edge upright and switches to Custom', 'FINISHED' in r and ob.mch_mridge.pattern == 'CUSTOM'
      and ob.mch_mridge.custom == '0111' and len(up_normals(ob)) == 3, (ob.mch_mridge.custom, up_normals(ob)))
for i in (1, 2, 3):
    if ob.mch_mridge.custom[i] == '1' and ob.mch_mridge.custom.count('1') > 1:
        bpy.ops.mch.mridge_edge_toggle(index=i)
check('the last sloped edge cannot be turned off', ob.mch_mridge.custom.count('1') == 1)
check('sloped_edges: a hexagon with Every Other Edge', mr.sloped_edges([(0, 0)] * 6, 'ALTERNATE', 1) == {1, 3, 5})
check('end_edges: a long box has its 2 short sides as ends', mr.end_edges(mr.ccw([(0, 0), (40, 0), (40, 10), (0, 10)])) == {1, 3})
ob.mch_mridge.pattern = 'HIP'
check('Hip again: 4 facets', len(up_normals(ob)) == 4)
r = bpy.ops.mch.mridge_apply()
check('Apply: plain mesh', 'FINISHED' in r and mr.SRC_KEY not in ob and not ob.mch_mridge.live)

# L-shaped (concave) outline and a curved body
body('sphere')
st.ridge_finish = st.edge_finish = 'CHAMFER'
L = [[(400, 400), (600, 400), (600, 500), (500, 500), (500, 600), (400, 600)]]
msg = ap.perform_plate(C, L, TOP)
ob = C.active_object
check('L-shaped outline on a sphere: closed plate', non_manifold(ob) == 0, (msg, non_manifold(ob)))
o, d = TOP.ray((450, 450))
hit, loc, _n, _i, hob, _m = S.ray_cast(C.evaluated_depsgraph_get(), Vector(o), Vector(d))
check('it sits on the curved surface (the plate is hit first, above the sphere)', hit and hob.name == ob.name)
S.mch_plate.preset = 'CHAMFER'
body()
ap.perform_plate(C, BOX, TOP)
check('other profiles still make the usual Armor Plate', mr.live_plate(C) is None and ap.pending_plate(C) is not None)

# 0.24.26 every straight-lasso polygon: pentagon, hexagon ... 24-gon, irregular and concave (star), all patterns
import time
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=20, location=(0, 0, -10))
S.mch_plate.preset = 'MRIDGE'
st.ridge_finish = st.edge_finish = 'CHAMFER'
st.height = 0.0


def ngon(n, r=150, star=False):
    return [(500 + (r if not star or i % 2 == 0 else r * 0.5) * math.cos(0.1 + 2 * math.pi * i / n),
             500 + (r if not star or i % 2 == 0 else r * 0.5) * math.sin(0.1 + 2 * math.pi * i / n)) for i in range(n)]


check('a clicked polygon keeps every corner (24-gon: 24 edges; free draw is still straightened)',
      len(mr.simplify_closed(ngon(24), 6.0)) == 24 and len(mr.simplify_closed(wobbly, 2.0)) == 4)
for n, star in ((5, False), (6, False), (8, False), (12, False), (20, False), (24, False), (12, True), (16, True)):
    bad, slow = [], 0.0
    for pat in ('HIP', 'LONG', 'ALTERNATE', 'HALF', 'CORNER', 'SHED'):
        st.pattern, st.turn = pat, 1
        t0 = time.time()
        try:
            ap.perform_plate(C, [ngon(n, star=star)], TOP)
            o = C.active_object
            slow = max(slow, time.time() - t0)
            if non_manifold(o) or len(o.get(mr.MASK_KEY, '')) != n:
                bad.append(pat)
            bpy.data.objects.remove(o)
        except Exception as ex:
            bad.append(f'{pat}: {ex}')
    label = f'{n}-point star' if star else f'{n}-gon'
    check(f'{label}: every Edge Pattern gives a closed plate with all {n} edges (chamfered)', not bad, bad)
    check(f'{label}: quick (under 3 s each)', slow < 3.0, round(slow, 2))
st.pattern, st.turn = 'HIP', 0
o = None
for k in (5, 6, 8):
    ap.perform_plate(C, [ngon(k)], TOP)
    o = C.active_object
    check(f'{k}-gon Hip: {k} sloped facets (pyramid roof)', len([1 for nn in up_normals(o) if nn[2] < 0.999]) >= k, up_normals(o))
    bpy.data.objects.remove(o)

# 0.24.26 Plate Detail + Alt
from mecha_lab import live_subtract as lsub, plate_detail as pdm


def vol(o):
    b = bmesh.new(); b.from_mesh(o.data); v = b.calc_volume(); b.free()
    return v


for tool in ('DETAIL', 'DETAIL2', 'DETAIL3'):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=8, location=(0, 0, -4))
    cube_ob = C.active_object
    v0 = vol(cube_ob)
    msg = lsub.perform(C, 'DETAIL', [[(400, 400), (600, 400), (600, 600), (400, 600)]], TOP, tool=tool)
    check(f'{tool}: Alt over a plain mesh engraves the detail into it (no error, no new object)',
          'Engraved' in msg and len(bpy.data.objects) == 1 and vol(cube_ob) < v0, msg)
    check(f'{tool}: ...only a shallow recess (as deep as the detail is tall), closed mesh',
          v0 - vol(cube_ob) < 0.1 * 4 and non_manifold(cube_ob) == 0, (v0 - vol(cube_ob), non_manifold(cube_ob)))
# a live detail cut with Alt keeps its own shading, the cut walls are flat with sharp borders
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=8, location=(0, 0, -4))
pdm.perform(C, [[(380, 300), (460, 300), (460, 700), (380, 700)]], TOP, 'DETAIL3')
det = C.active_object
for poly in det.data.polygons:
    poly.use_smooth = True
before_smooth = sum(1 for q in det.data.polygons if q.use_smooth)
lsub.perform(C, 'DETAIL', [[(430, 450), (500, 450), (500, 520), (430, 520)]], TOP, tool='DETAIL3')
me = det.data
flat = [q for q in me.polygons if not q.use_smooth]
sharp = me.attributes.get('sharp_edge')
n_sharp = sum(1 for d in sharp.data if d.value) if sharp else 0
check('Alt on a live detail: the cut walls are flat (no dark smear), the rest stays as it was',
      flat and any(q.use_smooth for q in me.polygons), (len(flat), before_smooth))
check('...with sharp borders around the cut', n_sharp >= 4, n_sharp)

# Cut / Split crisp shading
S.mch_settings.auto_apply = True
cut = S.mch_cut
cut.depth_mode, cut.targets = 'THROUGH', 'ACTIVE'
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.5, segments=48, ring_count=24)
t = C.active_object
bpy.ops.object.shade_smooth()
cut.edge_finish, cut.finish_width, cut.finish_crisp = 'CHAMFER', 0.05, True
ce.perform_closed(C, 'CUT', [t], [[(470, 300), (530, 300), (530, 700), (470, 700)]], TOP)
me = t.data
sharp = me.attributes.get('sharp_edge')
n_sharp = sum(1 for v in sharp.data if v.value) if sharp else 0
check('Crisp Shading: the chamfer band has sharp borders', n_sharp > 20, n_sharp)
check('...the chamfer strip and the cut walls are flat, the body stays smooth',
      any(not p.use_smooth for p in me.polygons) and any(p.use_smooth for p in me.polygons))
check('...closed mesh', non_manifold(t) == 0)
# custom normals (an imported FBX) are dropped
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.5, segments=48, ring_count=24)
t = C.active_object
t.data.normals_split_custom_set_from_vertices([v.normal for v in t.data.vertices])
had = t.data.has_custom_normals
ce.perform_closed(C, 'CUT', [t], [[(470, 300), (530, 300), (530, 700), (470, 700)]], TOP)
check('custom normals (FBX) are dropped so they do not smear over the cut', had and not t.data.has_custom_normals,
      (had, t.data.has_custom_normals))
cut.finish_crisp = False
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.5, segments=48, ring_count=24)
t = C.active_object
t.data.normals_split_custom_set_from_vertices([v.normal for v in t.data.vertices])
ce.perform_closed(C, 'CUT', [t], [[(470, 300), (530, 300), (530, 700), (470, 700)]], TOP)
check('Crisp Shading off: custom normals are kept (old behaviour)', t.data.has_custom_normals)
cut.finish_crisp = True

# the rim stays on the cut after the sliver cleanup (dense triangle mesh)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=1.5)
t = C.active_object
b = bmesh.new(); b.from_mesh(t.data); bmesh.ops.triangulate(b, faces=b.faces[:]); b.to_mesh(t.data); b.free()
cut.edge_finish = 'NONE'
ce.perform_closed(C, 'CUT', [t], [[(487, 300), (513, 300), (513, 700), (487, 700)]], TOP)
b = bmesh.new(); b.from_mesh(t.data)
lay = b.faces.layers.int.new(cg.CUTTER_ATTR) if False else None
b.free()
# re-run the finish on a fresh cut with a probe on the rim
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=1.5)
t = C.active_object
b = bmesh.new(); b.from_mesh(t.data); bmesh.ops.triangulate(b, faces=b.faces[:]); b.to_mesh(t.data); b.free()
orig = cg.tidy_rim
seen = {}


def probe(bm, width, passes=6):
    out = orig(bm, width, passes)
    layer = cg._face_flag_layer(out)
    rim = {v for e in cg._rim_edges(out, layer) for v in e.verts}
    # the cut walls are the planes x = +-0.13 (26 px wide strip, 1 px = 0.01)
    seen['off'] = max(abs(abs(v.co.x) - 0.13) for v in rim)
    return out


cg.tidy_rim = probe
cut.edge_finish = 'BEVEL'
ce.perform_closed(C, 'CUT', [t], [[(487, 300), (513, 300), (513, 700), (487, 700)]], TOP)
cg.tidy_rim = orig
check('dense triangles: the bevel is carved along the border (0.24.56, no sliver tidy-up), closed; if the old '
      'tidy-up runs, every rim point stays on the cut wall', ('off' not in seen and non_manifold(t) == 0)
      or seen.get('off', 1) < 1e-4, (seen, non_manifold(t)))
summary()
