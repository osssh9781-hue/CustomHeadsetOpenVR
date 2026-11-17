"""0.24.186 the user's one-piece body (user: "그전에 보냈던 붙어 있는 모델로 만들어 줘, 이건 예시 모델이잖아"): body02.fbx made
light and stored whole - one mesh; its joints are the part-split human kit's (the same sculpt).

    <blender python> body_whole_build.py <body02.fbx>

writes addon/mecha_lab/body_kits/human_whole.npz: Body_Q / Body_box (16-bit points), Body_N, Body_L, 'meta' (the human
kit's parts: pivot, end, parent - the bones).
"""
import json
import os
import sys

import bpy
import bmesh  # noqa: E402
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'addon', 'mecha_lab', 'body_kits')
FACES = 40000
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=args[0])
ob = max((o for o in bpy.data.objects if o.type == 'MESH'), key=lambda o: len(o.data.vertices))
tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
md = ob.modifiers.new('D', 'DECIMATE')
md.ratio = FACES / tris
dg = bpy.context.evaluated_depsgraph_get()
me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
bm = bmesh.new()
bm.from_mesh(me)
bm.transform(ob.matrix_world)
V = np.array([v.co[:] for v in bm.verts])
lo, hi = V.min(0), V.max(0)
H = hi[2] - lo[2]
V = (V - np.array([(lo[0] + hi[0]) / 2, 0.0, lo[2]])) / H            # (as the kits: 1 tall, the feet on 0)
bm.verts.index_update()
N = np.array([len(f.verts) for f in bm.faces], np.uint8)
L = np.array([v.index for f in bm.faces for v in f.verts], np.int32)
with np.load(os.path.join(OUT, 'human.npz'), allow_pickle=False) as z:
    meta = json.loads(str(z['meta']))
meta = {'kit': 'human_whole', 'parts': [{k: p[k] for k in ('name', 'slot', 'side', 'parent', 'pivot', 'end')}
                                         for p in meta['parts']]}
blo, bhi = V.min(0), V.max(0)
np.savez_compressed(os.path.join(OUT, 'human_whole.npz'), meta=np.array(json.dumps(meta)),
                    Body_Q=np.round((V - blo) / (bhi - blo) * 65535).astype(np.uint16),
                    Body_box=np.array([blo, bhi], np.float32), Body_N=N, Body_L=L)
print('saved', len(N), 'faces', 'bounds', np.round(blo, 3), np.round(bhi, 3))
