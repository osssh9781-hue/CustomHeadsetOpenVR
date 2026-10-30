"""Render original vs BakeHP: shaded (glossy, smooth) and wire, same camera.  render.py blend NAME out_dir"""
import bpy, sys, os, math
from mathutils import Vector
BLEND, NAME, OUT = sys.argv[-3], sys.argv[-2], sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=BLEND)
C = bpy.context; S = C.scene
src, hp = bpy.data.objects[NAME], bpy.data.objects[NAME + '_BakeHP']


def mat(name, col, rough=0.3, metal=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = col; b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    return m


def pipe_group(radius):
    ng = bpy.data.node_groups.new('WirePipe', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    m2c = N.new('GeometryNodeMeshToCurve'); L.new(gi.outputs[0], m2c.inputs['Mesh'])
    circ = N.new('GeometryNodeCurvePrimitiveCircle'); circ.inputs['Resolution'].default_value = 3; circ.inputs['Radius'].default_value = radius
    c2m = N.new('GeometryNodeCurveToMesh'); L.new(m2c.outputs[0], c2m.inputs['Curve']); L.new(circ.outputs[0], c2m.inputs['Profile Curve'])
    L.new(c2m.outputs[0], go.inputs[0])
    return ng


pts = [src.matrix_world @ v.co for v in src.data.vertices]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
size = (hi - lo).length
pipe = pipe_group(size * 0.0006)
grey = mat('grey', (0.62, 0.64, 0.68, 1), 0.28, 0.1)
dark = mat('dark', (0.02, 0.02, 0.025, 1), 0.6)
wires = {}
for o in (src, hp):
    o.data.materials.clear(); o.data.materials.append(grey); o.data.shade_smooth(); o.hide_render = True
    w = bpy.data.objects.new('w_' + o.name, o.data.copy()); S.collection.objects.link(w); w.matrix_world = o.matrix_world.copy()
    w.data.materials.clear(); w.data.materials.append(dark)
    w.modifiers.new('w', 'NODES').node_group = pipe; w.hide_render = True
    wires[o.name] = w
S.render.engine = 'CYCLES'; S.cycles.samples = 20; S.cycles.device = 'CPU'
S.render.resolution_x, S.render.resolution_y = 900, 760
world = bpy.data.worlds.new('w'); S.world = world; world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (0.14, 0.15, 0.17, 1)
for rot, e in (((50, 0, 30), 3.0), ((60, 0, 200), 1.2), ((-40, 0, 90), 0.6)):
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); S.collection.objects.link(sun)
    sun.rotation_euler = tuple(math.radians(x) for x in rot); sun.data.energy = e
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); S.collection.objects.link(cam); S.camera = cam
cam.data.type = 'ORTHO'
c = (lo + hi) / 2; d = Vector((0.45, -1.0, 0.5)).normalized()
cam.location = c + d * size * 3; cam.data.clip_start = size * 0.01; cam.data.clip_end = size * 100
rot = (-d).to_track_quat('-Z', 'Y'); cam.rotation_euler = rot.to_euler()
right, up = rot @ Vector((1, 0, 0)), rot @ Vector((0, 1, 0))
xs = [(p - c).dot(right) for p in pts]; ys = [(p - c).dot(up) for p in pts]
full = max(max(xs) - min(xs), (max(ys) - min(ys)) * 900 / 760) * 1.1
# a close-up: a quarter of the frame, centred a bit above the middle (curved area)
views = [('zoom', full * 0.32, c - right * full * 0.24 - up * full * 0.02), ('zoom2', full * 0.22, c + right * full * 0.12 + up * full * 0.1)]
C.view_layer.update()
outs = []
for vname, scale, centre in views:
    cam.data.ortho_scale = scale; cam.location = centre + d * size * 3
    for label, o, w in (('orig', src, wires[src.name]), ('bakehp', hp, wires[hp.name])):
        for kind in ('shaded', 'wire'):
            for ob in list(wires.values()) + [src, hp]: ob.hide_render = True
            o.hide_render = False
            if kind == 'wire': w.hide_render = False
            f = os.path.join(OUT, f'{NAME}_{label}_{kind}_{vname}.png'); S.render.filepath = f
            bpy.ops.render.render(write_still=True); outs.append(f); print('OUT', f)
print('DONE')
