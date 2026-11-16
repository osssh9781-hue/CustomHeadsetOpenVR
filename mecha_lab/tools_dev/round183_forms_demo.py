import sys, os, math, json, time
sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import bpy, bmesh
import numpy as np
from mathutils import Vector, Matrix
bpy.ops.wm.read_factory_settings(use_empty=True)
import mecha_lab
mecha_lab.register()
from mecha_lab import organic_mass as om, creature_light as cl
FBX, OUT = sys.argv[-2], sys.argv[-1]
bpy.ops.import_scene.fbx(filepath=FBX)
src = [o for o in bpy.data.objects if o.type == 'MESH'][0]
me = src.data
co = np.array([v.co for v in me.vertices]); c = co.mean(0)
_u, _s, vt = np.linalg.svd(co - c, full_matrices=False)
if np.linalg.det(vt) < 0: vt[2] *= -1
L = (co - c) @ vt.T
# the flat bottom: the side of the third axis where the most area faces
bm = bmesh.new(); bm.from_mesh(me); bm.normal_update()
ax = Vector(vt[2].tolist())
down = [f for f in bm.faces if f.normal.dot(ax) < -0.97]
up_ = [f for f in bm.faces if f.normal.dot(ax) > 0.97]
if sum(f.calc_area() for f in up_) > sum(f.calc_area() for f in down):
    vt[2] *= -1; vt[1] *= -1; L = (co - c) @ vt.T; ax = -ax; down = up_
from collections import Counter
cnt = Counter()
for f in down:
    for e in f.edges: cnt[e.index] += 1
bedges = [bm.edges[i] for i in range(len(bm.edges)) if False]
bm.edges.ensure_lookup_table()
be = [bm.edges[i] for i, k in cnt.items() if k == 1]
adj = {}
for e in be:
    a, b = e.verts[0].index, e.verts[1].index
    adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
loops = []; seen = set()
for start in adj:
    if start in seen: continue
    lp = [start]; seen.add(start); prev = None; cur = start
    while True:
        nxt = [x for x in adj[cur] if x != prev and x not in seen]
        if not nxt: break
        prev, cur = cur, nxt[0]; lp.append(cur); seen.add(cur)
    loops.append(lp)
import math as _m
rng = np.random.default_rng(3)
top = [(x, 0.42 + 0.18 * (x + 2.0) / 4.0 + 0.05 * _m.sin(x * 5.0) + 0.03 * rng.standard_normal()) for x in np.linspace(-2.0, 2.0, 46)]
bot = [(x, -0.38 - 0.1 * _m.cos(x * 1.3) + 0.04 * _m.sin(x * 7.0) + 0.03 * rng.standard_normal()) for x in np.linspace(2.0, -2.0, 46)]
P2 = np.array(top + [(2.12, 0.1), (2.15, -0.15)] + bot + [(-2.1, -0.15), (-2.12, 0.1)])
# (a lasso like the one drawn: long, a little wider at one end, its sides wandering)
S = bpy.context.scene
size = float(np.ptp(P2, axis=0).max())
kinds = ['SHARD', 'TERRACE', 'FACETS', 'CREST', 'PLATES', 'BLOCKS', 'FOLDS', 'TIERS']
gx, gy = size * 1.12, size * 0.42
objs = {}
for i, k in enumerate(kinds):
    off = Vector((((i % 2) - 0.5) * gx, (1.5 - i // 2) * gy, 0.0))
    mesh = bpy.data.meshes.new(k); ob = bpy.data.objects.new(k, mesh); S.collection.objects.link(ob)
    ob.location = off
    ob[om.KEY] = json.dumps(dict(outline=P2.round(6).tolist(), holes=[]))
    om._BUSY[0] = True
    pg = ob.mch_omass
    pg.kind = k
    for kk, v in om.KIND[k][4].items(): setattr(pg, kk, v)
    pg.color_a, pg.color_b = om.KIND[k][6]
    om._BUSY[0] = False
    t0 = time.time(); n = om.build(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    print(k, 'faces', len(ob.evaluated_get(dg).data.polygons), 'verts', len(ob.evaluated_get(dg).data.vertices), f'{time.time() - t0:.2f}s')
    objs[k] = ob
bpy.data.objects.remove(src)
mat = bpy.data.materials.new('Sample'); mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.62, 0.6, 0.56, 1)

S.render.engine = 'CYCLES'; S.cycles.samples = 40; S.cycles.device = 'CPU'; S.cycles.use_denoising = True
S.render.resolution_x, S.render.resolution_y = 1600, 1000
S.world = bpy.data.worlds.new('W'); cl.apply(S, 'soft_studio')
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN')); S.collection.objects.link(sun)
sun.data.energy = 2.6; sun.rotation_euler = (math.radians(48), 0, math.radians(-35))
S.view_settings.exposure = -1.2
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); S.collection.objects.link(cam); S.camera = cam
cam.location = Vector((size * 0.35, -size * 1.95, size * 1.55)); cam.rotation_euler = (Vector((0, -size * 0.05, 0)) - cam.location).to_track_quat('-Z', 'Y').to_euler(); cam.data.lens = 50
W = bpy.data.materials.new('Wire'); pb = W.node_tree.nodes['Principled BSDF']; pb.inputs['Base Color'].default_value = (1, .45, .05, 1); pb.inputs['Emission Color'].default_value = (1, .45, .05, 1); pb.inputs['Emission Strength'].default_value = 1.5
for wire in (False, True):
    made = []
    if wire:
        dg = bpy.context.evaluated_depsgraph_get()
        for k, o in objs.items():
            m2 = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)
            wo = bpy.data.objects.new(k + ' wire', m2); S.collection.objects.link(wo); wo.matrix_world = o.matrix_world
            md = wo.modifiers.new('W', 'WIREFRAME'); md.use_replace = True; md.use_even_offset = False; md.thickness = size * 0.0012
            m2.materials.clear(); m2.materials.append(W); made.append(wo); o.hide_render = True
    else:
        for o in objs.values(): o.hide_render = False
    S.render.filepath = os.path.join(OUT, f'forms_{"wire" if wire else "shaded"}.png')
    bpy.ops.render.render(write_still=True)
    for wo in made:
        bpy.data.objects.remove(wo)
print('done')
