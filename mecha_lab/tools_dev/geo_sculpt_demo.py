"""Demo for the user: a rough clay pod, lines drawn on it (Edge Line x5, Panel Line x3, as far as drawn) -> before
(lines in orange) / after; a box with Flat and Flat+Alt (a raised pad) + Clay Buildup.  Shaded + wireframe."""
import math, os, sys
sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import bpy, bmesh
import numpy as np
from mathutils import Vector, noise
from mathutils.bvhtree import BVHTree
bpy.ops.wm.read_factory_settings(use_empty=True)
from mecha_lab import geo_sculpt as gs
OUT = os.path.dirname(os.path.abspath(__file__))
S = bpy.context.scene; C = bpy.context

def pod(name, loc):
    me = bpy.data.meshes.new(name); bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=5, radius=1.0)
    for v in bm.verts:
        p = v.co.copy(); p.x *= 1.45; p.y *= 0.95; p.z *= 0.78
        p += p.normalized() * (0.045 * noise.noise(p * 2.2) + 0.015 * noise.noise(p * 6.0))
        v.co = p
    bm.to_mesh(me); bm.free(); me.shade_smooth()
    ob = bpy.data.objects.new(name, me); S.collection.objects.link(ob); ob.location = loc
    return ob

A = pod('Pod', (1.7, 0, 0))
before = pod('PodBefore', (-1.7, 0, 0)); before.data = A.data.copy()
bvh = BVHTree.FromObject(A, C.evaluated_depsgraph_get())        # (local space)

def ray_line(origins, dirs):
    pts, ns = [], []
    for o, d in zip(origins, dirs):
        loc, n, _i, _d = bvh.ray_cast(Vector(o), Vector(d).normalized())
        if loc is not None:
            pts.append(tuple(loc)); ns.append(tuple(n))
    return pts, ns
lines = []
xs = np.linspace(-0.85, 0.85, 90)
for y0 in (0.42, -0.42):                                  # two lengthwise edges on top (Edge Line)
    lines.append(('EDGE', 0.22, 0.6) + ray_line(np.c_[xs, np.full_like(xs, y0), np.full_like(xs, 3)], np.c_[0 * xs, 0 * xs, -1 + 0 * xs]))
t = np.linspace(-1.0, 1.0, 60)                            # two partial rings round the ends (Edge Line, as far as drawn)
for x0 in (0.95,):
    ang = t * 1.2
    lines.append(('EDGE', 0.22, 0.6) + ray_line(np.c_[np.full_like(ang, x0), 3 * np.sin(ang), 3 * np.cos(ang)], np.c_[0 * ang, -np.sin(ang), -np.cos(ang)]))
zz = np.linspace(-0.45, 0.45, 50)                         # a slanted edge on the front side (Edge Line)
lines.append(('EDGE', 0.2, 0.6) + ray_line(np.c_[0.55 - 0.9 * (zz + 0.45) / 0.9, np.full_like(zz, -3), zz], np.c_[0 * zz, 1 + 0 * zz, 0 * zz]))
ys = np.linspace(-0.4, 0.4, 40)                           # panel lines across the top strip (Panel Line)
for x0 in (-0.35, 0.2):
    lines.append(('PANEL', 0.045, 0.6) + ray_line(np.c_[np.full_like(ys, x0), ys, np.full_like(ys, 3)], np.c_[0 * ys, 0 * ys, -1 + 0 * ys]))
xs2 = np.linspace(-0.6, 0.3, 40)                          # a panel line on the front side
lines.append(('PANEL', 0.045, 0.6) + ray_line(np.c_[xs2, np.full_like(xs2, -3), np.full_like(xs2, -0.1)], np.c_[0 * xs2, 1 + 0 * xs2, 0 * xs2]))
for kind, r, k, P, N in lines:
    gs.add_stroke(A, kind, P, N, r, k)
gs.set_input(gs.layer(A), 'Detail', 0.006)
# the box: Flat (pressed), Flat + Alt (a pad pops out), Clay Buildup
me = bpy.data.meshes.new('Box'); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=2.0)
bmesh.ops.bevel(bm, geom=list(bm.verts) + list(bm.edges), offset=0.1, segments=1, affect='EDGES', profile=0.5, clamp_overlap=True)
bm.to_mesh(me); bm.free()
B = bpy.data.objects.new('Box', me); S.collection.objects.link(B); B.location = (5.6, 0, -0.1); B.scale = (0.8, 0.8, 0.8)
up = (0, 0, 1)
def seg(p0, p1, n=16):
    return [tuple(np.array(p0) + (np.array(p1) - np.array(p0)) * j / (n - 1)) for j in range(n)]
gs.add_stroke(B, 'STANDARD', [(-0.45, -0.4, 1.0)], [up], 0.38, 1.4)                    # a hill ...
gs.add_stroke(B, 'FLAT', seg((-0.7, -0.4, 1.12), (-0.2, -0.4, 1.12), 8), [up] * 8, 0.3, 1.0)   # ... pressed flat
gs.add_stroke(B, 'FLAT', seg((0.2, -0.45, 1.0), (0.65, -0.45, 1.0), 10), [up] * 10, 0.28, -1.0)  # Flat + Alt: a pad
for j, yy in enumerate((0.25, 0.4, 0.55)):                                             # Clay Buildup x3
    gs.add_stroke(B, 'BUILDUP', seg((-0.7, yy, 1.0), (0.6, yy + 0.05, 1.0), 20), [up] * 20, 0.16, 1.0)
gs.add_stroke(B, 'PANEL', seg((-0.95, -1.0, 0.1), (0.95, -1.0, 0.1), 30), [(0, -1, 0)] * 30, 0.04, 0.6)  # a panel line
gs.set_input(gs.layer(B), 'Detail', 0.01)
dg = C.evaluated_depsgraph_get()
for o in (A, B):
    print(o.name, 'base faces', len(o.data.polygons), 'evaluated', len(o.evaluated_get(dg).data.polygons))
# the drawn lines on the "before"
cu = bpy.data.curves.new('Lines', 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 0.008
for kind, r, k, P, N in lines:
    sp = cu.splines.new('POLY'); sp.points.add(len(P) - 1)
    for j, p_ in enumerate(P):
        sp.points[j].co = (*(np.array(p_) * 1.003), 1.0)
lob = bpy.data.objects.new('LinesOb', cu); lob.location = before.location; S.collection.objects.link(lob)
lm = bpy.data.materials.new('Orange'); lm.use_nodes = True
pb = lm.node_tree.nodes['Principled BSDF']
pb.inputs['Base Color'].default_value = (1.0, 0.35, 0.02, 1); pb.inputs['Emission Color'].default_value = (1.0, 0.35, 0.02, 1)
pb.inputs['Emission Strength'].default_value = 1.5
cu.materials.append(lm)
mat = bpy.data.materials.new('Metal'); mat.use_nodes = True
b_ = mat.node_tree.nodes['Principled BSDF']
b_.inputs['Base Color'].default_value = (0.36, 0.37, 0.4, 1); b_.inputs['Roughness'].default_value = 0.38; b_.inputs['Metallic'].default_value = 0.45
for o in (A, before, B):
    o.data.materials.append(mat)
wmat = bpy.data.materials.new('WireM'); wmat.use_nodes = True
wmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.01, 0.01, 0.015, 1)
wires = []
dg = C.evaluated_depsgraph_get()
for o in (A, before, B):
    wm_ = bpy.data.meshes.new_from_object(o.evaluated_get(dg)); wo = bpy.data.objects.new(o.name + 'W', wm_)
    wo.matrix_world = o.matrix_world; S.collection.objects.link(wo)
    md = wo.modifiers.new('W', 'WIREFRAME'); md.thickness = 0.0025; md.use_replace = True; md.use_even_offset = False
    wm_.materials.clear(); wm_.materials.append(wmat); wires.append(wo)
cam_d = bpy.data.cameras.new('C'); cam_d.lens = 36; cam = bpy.data.objects.new('C', cam_d); S.collection.objects.link(cam); S.camera = cam
cam.location = (2.0, -9.6, 6.0)
cam.rotation_euler = (Vector((2.0, 0, -0.15)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
for loc, e, sz in (((-3, -5, 6), 1500, 6), ((6, -3, 3), 900, 5), ((2, 6, 5), 900, 6)):
    ld = bpy.data.lights.new('L', 'AREA'); ld.energy = e; ld.size = sz
    lo = bpy.data.objects.new('L', ld); lo.location = loc; S.collection.objects.link(lo)
    lo.rotation_euler = (Vector((2, 0, 0)) - lo.location).to_track_quat('-Z', 'Y').to_euler()
w = bpy.data.worlds.new('W'); S.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.045, 0.045, 0.05, 1)
S.render.engine = 'CYCLES'; S.cycles.samples = 64; S.cycles.device = 'CPU'
S.render.resolution_x, S.render.resolution_y = 2200, 780
for name, wire in (('demo_shaded', False), ('demo_wire', True)):
    for wo in wires:
        wo.hide_render = not wire
    S.render.filepath = os.path.join(OUT, name + '.png'); bpy.ops.render.render(write_still=True)
print('DONE')
