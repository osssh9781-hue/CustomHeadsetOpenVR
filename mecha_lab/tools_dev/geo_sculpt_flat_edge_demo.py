"""Flat along corners: a sharp box and a rounded clay block, before / after Flat strokes drawn along their edges
(rays from the view onto the part, as the tool would land them).  Shaded + wireframe."""
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

def block(name, x, rounded):
    me = bpy.data.meshes.new(name); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=2.0)
    if rounded:
        bmesh.ops.bevel(bm, geom=list(bm.verts) + list(bm.edges), offset=0.35, segments=6, affect='EDGES', profile=0.5, clamp_overlap=True)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        for v in bm.verts:
            v.co += v.co.normalized() * 0.02 * noise.noise(v.co * 3.0)
    bm.to_mesh(me); bm.free()
    if rounded:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me); S.collection.objects.link(ob); ob.location = (x, 0, 0)
    return ob

def stroke_along(ob, a, b, toward, r, k=0.6, n=14):
    """A Flat stroke along the edge a -> b: rays from ``toward`` (the view side) onto the part."""
    bvh = BVHTree.FromObject(ob, C.evaluated_depsgraph_get())
    d = -Vector(toward).normalized()
    pts, ns = [], []
    for j in range(n):
        p = Vector(a).lerp(Vector(b), j / (n - 1))
        loc, nrm, _i, _dd = bvh.ray_cast(p - d * 4.0, d)
        if loc is not None:
            pts.append(tuple(loc)); ns.append(tuple(nrm))
    gs.add_stroke(ob, 'FLAT', pts, ns, r, k)
    return len(pts)

A0 = block('SharpBefore', -4.2, False)
A = block('SharpFlat', -1.6, False)
stroke_along(A, (-0.85, -1, 1), (0.85, -1, 1), (0, -1, 1), 0.3)          # top front edge: a wide facet
stroke_along(A, (1, -1, -0.85), (1, -1, 0.85), (1, -1, 0), 0.2)          # front right corner: a narrower one
stroke_along(A, (1, -0.85, 1), (1, 0.85, 1), (1, 0, 1), 0.12)            # top right edge: thin
B0 = block('RoundBefore', 1.3, True)
B = block('RoundFlat', 3.9, True)
for a, b, tw, r in (((-0.7, -1, 0.95), (0.7, -1, 0.95), (0, -1, 1), 0.38), ((1, -1, -0.7), (1, -1, 0.7), (1, -1, 0), 0.38),
                    ((1, -0.7, 0.95), (1, 0.7, 0.95), (1, 0, 1), 0.38), ((-1, -1, -0.7), (-1, -1, 0.7), (-1, -1, 0), 0.38)):
    stroke_along(B, a, b, tw, r)
# the flat faces too (top, front, right): flattened onto their planes
for a, b, tw in (((-0.5, 0.0, 1.2), (0.5, 0.0, 1.2), (0, 0, 1)), ((-0.5, -1.2, 0.0), (0.5, -1.2, 0.0), (0, -1, 0)),
                 ((1.2, -0.5, 0.0), (1.2, 0.5, 0.0), (1, 0, 0))):
    stroke_along(B, a, b, tw, 0.75)
for o in (A, B):
    gs.set_input(gs.layer(o), 'Detail', 0.008)
dg = C.evaluated_depsgraph_get()
for o in (A, B):
    print(o.name, 'strokes', gs.stroke_count(o), 'faces', len(o.evaluated_get(dg).data.polygons))
mat = bpy.data.materials.new('Metal'); mat.use_nodes = True
b_ = mat.node_tree.nodes['Principled BSDF']
b_.inputs['Base Color'].default_value = (0.36, 0.37, 0.4, 1); b_.inputs['Roughness'].default_value = 0.38; b_.inputs['Metallic'].default_value = 0.45
for o in (A0, A, B0, B):
    o.data.materials.append(mat)
wmat = bpy.data.materials.new('WireM'); wmat.use_nodes = True
wmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.01, 0.01, 0.015, 1)
wires = []
for o in (A0, A, B0, B):
    wm_ = bpy.data.meshes.new_from_object(o.evaluated_get(dg)); wo = bpy.data.objects.new(o.name + 'W', wm_)
    wo.matrix_world = o.matrix_world; S.collection.objects.link(wo)
    md = wo.modifiers.new('W', 'WIREFRAME'); md.thickness = 0.0025; md.use_replace = True; md.use_even_offset = False
    wm_.materials.clear(); wm_.materials.append(wmat); wires.append(wo)
for x, txt in ((-4.2, 'Before'), (-1.6, 'Flat along 3 edges'), (1.3, 'Before (rounded clay)'), (3.9, 'Flat along edges + faces')):
    cu = bpy.data.curves.new('T', 'FONT'); cu.body = txt; cu.size = 0.24; cu.align_x = 'CENTER'
    t = bpy.data.objects.new('T', cu); t.location = (x, -1.7, -1.25); t.rotation_euler = (math.radians(60), 0, 0)
    S.collection.objects.link(t)
    lm = bpy.data.materials.new('W'); lm.use_nodes = True
    lm.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (0.9, 0.9, 0.9, 1)
    lm.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.0
    cu.materials.append(lm)
cam_d = bpy.data.cameras.new('C'); cam_d.lens = 34; cam = bpy.data.objects.new('C', cam_d); S.collection.objects.link(cam); S.camera = cam
cam.location = (-0.15, -10.5, 6.2)
cam.rotation_euler = (Vector((-0.15, 0, -0.35)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
for loc, e, sz in (((-4, -4, 6), 1600, 6), ((6, -3, 4), 1000, 5), ((0, 6, 5), 900, 6)):
    ld = bpy.data.lights.new('L', 'AREA'); ld.energy = e; ld.size = sz
    lo = bpy.data.objects.new('L', ld); lo.location = loc; S.collection.objects.link(lo)
    lo.rotation_euler = (Vector((0, 0, 0)) - lo.location).to_track_quat('-Z', 'Y').to_euler()
w = bpy.data.worlds.new('W'); S.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.045, 0.045, 0.05, 1)
S.render.engine = 'CYCLES'; S.cycles.samples = 64; S.cycles.device = 'CPU'
S.render.resolution_x, S.render.resolution_y = 2200, 800
for name, wire in (('flatedge_shaded', False), ('flatedge_wire', True)):
    for wo in wires:
        wo.hide_render = not wire
    S.render.filepath = os.path.join(OUT, name + '.png'); bpy.ops.render.render(write_still=True)
print('DONE')
