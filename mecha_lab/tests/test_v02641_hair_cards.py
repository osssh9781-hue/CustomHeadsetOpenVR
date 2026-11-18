"""0.24.241 (user: "헤어도 헤어카드 되게" - "털 -> 카드 + 텍스처 아틀라스"): a fur turned into hair cards - about Cards
cards following the strands (each card's middle near its clump's strands, lying on the skin), UVs in the atlas strips,
a strand texture with alpha, the fur's colour kept, the material ready; the fur hidden; pressed again: the same
cards object made again."""
import math
import time

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Euler

import mecha_lab
from mecha_lab import core_geometry as cg, creature_fur as cf, hair_cards as hc  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=48)
body = C.active_object
me = body.data
ca = me.color_attributes.new('Polypaint', 'FLOAT_COLOR', 'POINT')
co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
ca.data.foreach_set('color', np.where((co[:, 0] < 0)[:, None], [[1, 0, 0, 1]], [[0, 0, 1, 1]]).astype(np.float32).ravel())
me.color_attributes.active_color = ca
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)
st = S.mch_fur
st.density, st.length = 6000.0, 0.25
cf.perform(C, [[(500 + 120 * math.cos(a), 500 + 90 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 64, endpoint=False)]], FRONT)
fur = C.active_object
R, cols = hc.read_strands(C, fur, k=9)
check(f'the fur\'s strands read ({len(R):,}, colours {"yes" if cols is not None else "no"})', len(R) > 500 and R.shape[1] == 9)
hs = S.mch_hair_cards
hs.cards, hs.segments, hs.res, hs.tiles = 120, 8, '512', 8
t = time.time()
r = bpy.ops.mch.hair_cards()
dt = time.time() - t
cards = C.active_object
check(f'the button makes the cards object ({dt:.1f} s)', r == {'FINISHED'} and hc.is_cards(cards) and cards.type == 'MESH'
      and cards.name == fur.name + '_Cards')
nf = len(cards.data.polygons)
check(f'about 120 cards x 8 segments ({nf} faces)', 100 * 8 <= nf <= 120 * 8)
dg = C.evaluated_depsgraph_get()
V = np.array([cards.matrix_world @ v.co for v in cards.data.vertices])
mids = V.reshape(-1, 9, 2, 3).mean(2)                       # (each card: its middle line)
roots = mids[:, 0]
from mathutils.bvhtree import BVHTree
from mathutils import Vector
bvh = BVHTree.FromObject(body.evaluated_get(dg), dg)
dist = np.array([bvh.find_nearest(Vector(p))[3] for p in roots])
check(f'the cards start on the skin (root distance median {np.median(dist):.4f})', np.median(dist) < 0.02)
tips = mids[:, -1]
allpts = R.reshape(-1, 3)
from mathutils.kdtree import KDTree
kd = KDTree(len(allpts))
for i, p in enumerate(allpts):
    kd.insert(p, i)
kd.balance()
dd = np.array([kd.find(Vector(p))[2] for p in mids.reshape(-1, 3)])
check(f'the cards follow the strands (median distance to a strand {np.median(dd):.4f}, length 0.25)', np.median(dd) < 0.03)
uv = np.empty(len(cards.data.loops) * 2, np.float32); cards.data.uv_layers[0].data.foreach_get('uv', uv)
check('UVs inside the atlas', uv.min() >= -1e-6 and uv.max() <= 1 + 1e-6)
mat = cards.data.materials[0]
img = next(n.image for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE')
px = np.array(img.pixels[:]).reshape(img.size[1], img.size[0], 4)
a = px[:, :, 3]
check(f'a strand texture with alpha ({img.size[0]}x{img.size[1]}, {(a > 0.5).mean():.0%} covered), packed',
      0.05 < (a > 0.5).mean() < 0.9 and img.packed_file is not None)
cc = np.empty(len(cards.data.vertices) * 4, np.float32); cards.data.color_attributes[hc.COL].data.foreach_get('color', cc)
cc = cc.reshape(-1, 4)
left = V[:, 0] < -0.15; right = V[:, 0] > 0.15
check('the fur\'s colour kept on the cards (red on the -X side, blue on +X)',
      cc[left, 0].mean() > cc[left, 2].mean() and cc[right, 2].mean() > cc[right, 0].mean())
check('the material reads the colour and the alpha, both sides drawn',
      any(n.type == 'ATTRIBUTE' and n.attribute_name == hc.COL for n in mat.node_tree.nodes)
      and not mat.use_backface_culling)
check('the fur is hidden (kept), the cards follow the body', fur.hide_get() and fur.name in bpy.data.objects and cards.parent == body)
hs.cross = True
r = bpy.ops.mch.hair_cards()
check('pressed again on the cards (Cross on): the same object made again with twice the strips',
      r == {'FINISHED'} and C.active_object is cards and len(cards.data.polygons) == 2 * nf
      and sum(1 for o in bpy.data.objects if hc.is_cards(o)) == 1)
summary()
