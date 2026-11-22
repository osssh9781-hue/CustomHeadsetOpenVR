"""0.24.295 (user: "아머플레이트도 프레스 컷처럼 대각선으로 잘리는 버튼" / "베이스 메쉬 옵션 - 만든 모양대로 옆면 쪽에 몰딩처럼
튀어나오게, 두께랑 개수"): Armor Plate Alt carve Wall Angle; Base Mesh Side Molding (count, thickness)."""
import math

import bmesh
from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import armor_plate as ap, base_mesh as bm_, core_geometry as cg, ramp_edit as re_

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
LOOP = [(500 + 55 * math.cos(a), 500 + 55 * math.sin(a)) for a in (2 * math.pi * k / 64 for k in range(64))]


def depth(x, y=0.0):
    C.view_layer.update()
    r = S.ray_cast(C.evaluated_depsgraph_get(), Vector((x, y, 5)), Vector((0, 0, -1)))
    return 1.0 - r[1].z if r[0] else None


def carve(angle):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    S.mch_plate.preset = 'FLAT'
    S.mch_plate.carve_depth = 0.2
    S.mch_plate.carve_wall = angle
    ap.perform_plate_carve(C, [LOOP], TOP, live=False)
    return C.active_object if C.active_object else bpy.data.objects[0]


cube = carve(0.0)
d_mid0, d_rim0 = depth(0.0), depth(0.5)
cube = carve(math.radians(30))
d_mid, d_rim = depth(0.0), depth(0.5)
nm = non_manifold(bpy.data.objects['Cube'])
check('Alt carve Wall Angle 30: the middle as deep as before (0.2), near the opening\'s edge shallower (slanted wall)',
      abs(d_mid - 0.2) < 0.01 and abs(d_rim0 - 0.2) < 0.01 and d_rim < 0.15 and nm == 0,
      (d_mid0, d_rim0, d_mid, d_rim, nm))
# the expected slant: at r = 0.5 (0.05 in from the 0.55 opening) the floor edge is 0.2*tan30 = 0.115 in -> wall here
# is 0.05 / tan30 = 0.087 deep
check('... the wall leans at about 30 deg (depth near the rim ~ 0.05 / tan 30)', abs(d_rim - 0.05 / math.tan(math.radians(30))) < 0.03,
      d_rim)
S.mch_plate.carve_wall = 0.0
S.mch_plate.carve_depth = 0.0
check('Wall Angle default 0 (straight walls as before) and in the Alt Carve group of the top bar',
      S.mch_plate.bl_rna.properties['carve_wall'].default == 0.0
      and "prop='carve_wall'" in open(__import__('mecha_lab.top_bar', fromlist=['x']).__file__).read())

# ---- Base Mesh Side Molding
p = S.mch_base
sq = [(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]
sq = [tuple(q) for q in cg.reres_loop(sq, 1.0)] if hasattr(cg, 'reres_loop') else sq


def build(**kw):
    for k, v in kw.items():
        setattr(p, k, v)
    b = bm_.build_bmesh([(sq, [])], p)
    me = bpy.data.meshes.new('t')
    b.to_mesh(me)
    b.free()
    return me


p.profile = 'FLAT'
p.height = 0.6
me0 = build(mold_count=0)
me = build(mold_count=3, mold_thick=0.05, mold_shape='SQUARE')
xs = [v.co.x for v in me.vertices]
ob = bpy.data.objects.new('m', me)
S.collection.objects.link(ob)
zs_out = sorted({round(v.co.z, 4) for v in me.vertices if v.co.x > 1.04})
check('Side Molding 3 x 0.05 Square: the wall stands out 0.05 (x 1.05), the plain part still at 1.0, closed',
      abs(max(xs) - 1.05) < 1e-4 and non_manifold(ob) == 0 and len(me.polygons) > len(me0.polygons)
      and abs(min(v.co.z for v in me.vertices)) < 1e-6 and abs(max(v.co.z for v in me.vertices) - 0.6) < 1e-6,
      (max(xs), len(me0.polygons), len(me.polygons)))
check('... three bands up the side (6 band edges standing out)', len(zs_out) == 6, zs_out)
for shape in ('CHAMFER', 'ROUND'):
    me2 = build(mold_count=2, mold_thick=0.04, mold_shape=shape)
    o2 = bpy.data.objects.new('m2', me2)
    S.collection.objects.link(o2)
    check(f'{shape} molding: closed, stands out 0.04', non_manifold(o2) == 0
          and abs(max(v.co.x for v in me2.vertices) - 1.04) < 1e-3, max(v.co.x for v in me2.vertices))
for prof in ('BEVEL', 'CHAMFER'):
    p.bevel_sides = 'BOTH'
    me3 = build(profile=prof, mold_count=2, mold_thick=0.03, mold_shape='CHAMFER', bevel_width=0.08)
    o3 = bpy.data.objects.new('m3', me3)
    S.collection.objects.link(o3)
    check(f'{prof} (both rims) + molding: closed, the bands below the rims', non_manifold(o3) == 0
          and abs(max(v.co.x for v in me3.vertices) - 1.03) < 1e-3, len(me3.polygons))
p.profile = 'FLAT'
p.mold_count = 0
# a live Base Mesh from a lasso: change the count after - it rebuilds
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
p.sketch = False
p.surface_align = False
bm_.perform_base(C, [[(400, 400), (600, 400), (600, 600), (400, 600)]], TOP)
live = C.active_object
n0 = len(live.data.polygons)
live.mch_base.mold_count = 4
check('a live Base Mesh: Side Molding 4 set after drawing rebuilds it (more faces, closed)',
      len(live.data.polygons) > n0 and non_manifold(live) == 0, (n0, len(live.data.polygons)))
live.mch_base.mold_count = 0
check('... back to 0: as it was', len(live.data.polygons) == n0)
check('Side Molding default 0 (Base Mesh as before)', p.bl_rna.properties['mold_count'].default == 0)
summary()
