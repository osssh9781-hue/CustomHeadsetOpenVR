"""A big-armed kaiju as one lump (test asset for Auto Creature, 0.24.246): two huge arms rising high and coming down to
the ground far out, two hind legs, two small arms off the ground, a tail off the ground, a head - a skin over a
stick figure, smoothed and voxel-remeshed into one mesh.  ``SKELETON`` keeps the stick figure (the truth)."""
import bpy

SKELETON = {'pelvis': (0, 0.25, 1.55), 'chest': (0, -0.15, 2.35), 'neck': (0, -0.5, 2.7), 'head': (0, -0.9, 2.65)}
for s, x in (('L', 1), ('R', -1)):
    SKELETON.update({
        f'shoulder.{s}': (0.55 * x, -0.25, 2.45), f'elbow.{s}': (1.7 * x, -0.45, 3.25), f'wrist.{s}': (2.7 * x, -0.65, 1.0),
        f'hand.{s}': (2.85 * x, -0.75, 0.05),
        f'hip.{s}': (0.35 * x, 0.3, 1.45), f'knee.{s}': (0.5 * x, -0.15, 0.8), f'ankle.{s}': (0.55 * x, 0.2, 0.12),
        f'toe.{s}': (0.58 * x, -0.15, 0.03),
        f'sarm.{s}': (0.3 * x, -0.5, 2.05), f'selbow.{s}': (0.6 * x, -0.8, 1.7), f'shand.{s}': (0.45 * x, -1.0, 1.4)})
SKELETON.update({'tail1': (0, 0.9, 1.15), 'tail2': (0, 1.7, 0.8), 'tail3': (0, 2.5, 0.75), 'tail4': (0, 3.1, 0.95)})
EDGES = [('pelvis', 'chest'), ('chest', 'neck'), ('neck', 'head'), ('pelvis', 'tail1'), ('tail1', 'tail2'),
         ('tail2', 'tail3'), ('tail3', 'tail4')]
for s in 'LR':
    EDGES += [('chest', f'shoulder.{s}'), (f'shoulder.{s}', f'elbow.{s}'), (f'elbow.{s}', f'wrist.{s}'), (f'wrist.{s}', f'hand.{s}'),
              ('pelvis', f'hip.{s}'), (f'hip.{s}', f'knee.{s}'), (f'knee.{s}', f'ankle.{s}'), (f'ankle.{s}', f'toe.{s}'),
              ('chest', f'sarm.{s}'), (f'sarm.{s}', f'selbow.{s}'), (f'selbow.{s}', f'shand.{s}')]
RADIUS = {'pelvis': 0.42, 'chest': 0.5, 'neck': 0.22, 'head': 0.26, 'tail1': 0.22, 'tail2': 0.15, 'tail3': 0.1, 'tail4': 0.05}


def make(context, name='Kaiju', voxel=0.045):
    names = list(SKELETON)
    idx = {n: i for i, n in enumerate(names)}
    me = bpy.data.meshes.new(name)
    me.from_pydata([SKELETON[n] for n in names], [(idx[a], idx[b]) for a, b in EDGES], [])
    ob = bpy.data.objects.new(name, me)
    context.scene.collection.objects.link(ob)
    sk = ob.modifiers.new('Skin', 'SKIN')
    for i, n in enumerate(names):
        r = RADIUS.get(n)
        if r is None:
            base = n.split('.')[0]
            r = {'shoulder': 0.24, 'elbow': 0.2, 'wrist': 0.14, 'hand': 0.11, 'hip': 0.22, 'knee': 0.17, 'ankle': 0.12,
                 'toe': 0.08, 'sarm': 0.08, 'selbow': 0.07, 'shand': 0.05}[base]
        me.skin_vertices[0].data[i].radius = (r, r)
    me.skin_vertices[0].data[idx['pelvis']].use_root = True
    ob.modifiers.new('Sub', 'SUBSURF').levels = 2
    rm = ob.modifiers.new('Lump', 'REMESH')
    rm.mode, rm.voxel_size = 'VOXEL', voxel
    for o in list(context.selected_objects):
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    bpy.ops.object.convert(target='MESH')
    ob = context.active_object
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob
