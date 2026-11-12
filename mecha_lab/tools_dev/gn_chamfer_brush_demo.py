import os, bpy, bmesh
import numpy as np
from mathutils import Vector
OUT = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.read_factory_settings(use_empty=True)
S = bpy.context.scene
me = bpy.data.meshes.new('Box'); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=2.0); bm.to_mesh(me); bm.free()
ob = bpy.data.objects.new('Box', me); S.collection.objects.link(ob)
def mark(pts_, width, kind, tol=0.08):
    P = np.array(pts_, float); a_, b_ = P[:-1], P[1:]
    def dist(x):
        d = b_ - a_; t = np.clip(((x - a_) * d).sum(1) / np.maximum((d * d).sum(1), 1e-12), 0, 1)
        return np.min(np.linalg.norm(a_ + d * t[:, None] - x, axis=1))
    name = 'mch_bevel_' + kind
    a = me.attributes.get(name) or me.attributes.new(name, 'FLOAT', 'EDGE')
    w = np.zeros(len(me.edges)); a.data.foreach_get('value', w)
    for e in me.edges:
        v1, v2 = (np.array(me.vertices[i].co) for i in e.vertices)
        if dist(v1) < tol and dist(v2) < tol:
            w[e.index] = width
    a.data.foreach_set('value', w)
mark([(-1, -1, 1), (1, -1, 1)], 0.12, 'chamfer')      # the top front: a thin chamfer
mark([(1, -1, 1), (1, 1, 1)], 0.20, 'chamfer')        # the top right: wider
mark([(-1, 1, 1), (1, 1, 1)], 0.30, 'chamfer')        # the top back: widest
mark([(1, -1, -1), (1, -1, 1)], 0.25, 'round')        # the front right: round, to compare
for kind, segs in (('chamfer', 1), ('round', 6)):
    a = me.attributes['mch_bevel_' + kind]; w = np.zeros(len(me.edges)); a.data.foreach_get('value', w)
    wmax = float(w.max()) or 1.0; a.data.foreach_set('value', w / wmax)
    m = ob.modifiers.new('MCH Bevel ' + kind.title(), 'BEVEL'); m.limit_method = 'WEIGHT'; m.edge_weight = 'mch_bevel_' + kind
    m.width = wmax; m.segments = segs; m.profile = 0.5
mat = bpy.data.materials.new('Clay'); mat.use_nodes = True
mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.42, 0.40, 0.37, 1)
mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.45
me.materials.append(mat)
ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
print('faces', len(me.polygons), '->', len(ev.data.polygons))
wme = bpy.data.meshes.new_from_object(ev); wob = bpy.data.objects.new('Wire', wme); S.collection.objects.link(wob)
wm = wob.modifiers.new('W', 'WIREFRAME'); wm.thickness = 0.006; wm.use_replace = True
wmat = bpy.data.materials.new('WireM'); wmat.use_nodes = True
wmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.01, 0.01, 0.015, 1)
wme.materials.clear(); wme.materials.append(wmat)
cam_d = bpy.data.cameras.new('C'); cam_d.lens = 60; cam = bpy.data.objects.new('C', cam_d); S.collection.objects.link(cam); S.camera = cam
cam.location = (4.2, -5.0, 4.4)
cam.rotation_euler = (Vector((0, 0, 0.1)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
for loc, e, sz in (((4, -2, 6), 1500, 4), ((-5, -4, 2), 500, 4), ((0, 6, 3), 700, 3)):
    ld = bpy.data.lights.new('L', 'AREA'); ld.energy = e; ld.size = sz
    lo = bpy.data.objects.new('L', ld); lo.location = loc; S.collection.objects.link(lo)
    lo.rotation_euler = (Vector((0, 0, 0)) - lo.location).to_track_quat('-Z', 'Y').to_euler()
w = bpy.data.worlds.new('W'); S.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.03, 0.03, 0.035, 1)
S.render.engine = 'CYCLES'; S.cycles.samples = 64; S.cycles.device = 'CPU'
S.render.resolution_x, S.render.resolution_y = 1000, 800
for name, wire in (('chamfer_shaded', False), ('chamfer_wire', True)):
    wob.hide_render = not wire
    S.render.filepath = os.path.join(OUT, name + '.png'); bpy.ops.render.render(write_still=True)
print('DONE')
