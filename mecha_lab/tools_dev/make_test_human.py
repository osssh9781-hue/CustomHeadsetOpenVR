"""A test human body (0.24.151, user: "인간 바디 + 하이폴리곤으로 테스트"): a skeleton of points with radii -> Skin
modifier -> Subdivision, applied: one smooth closed mesh of a standing figure (A-pose, about 1.8 tall, feet on z = 0).

    <blender python> make_test_human.py <out .blend> [subdivision levels, default 4]

Levels 4 gives about 0.5 M faces, 5 about 2 M.  The mesh is applied (no modifiers) - a plain high-poly part like a
ZBrush import.  For tests only (not shipped)."""
import os
import sys

import bpy
from mathutils import Vector

# (name, position, (radius across x, radius front-back y)), and the bones between them
J = {
    'pelvis': ((0.0, 0.0, 0.98), (0.17, 0.115)),
    'waist': ((0.0, 0.0, 1.10), (0.145, 0.10)),
    'belly': ((0.0, -0.005, 1.22), (0.16, 0.105)),
    'chest': ((0.0, -0.01, 1.36), (0.19, 0.125)),
    'upchest': ((0.0, 0.0, 1.46), (0.19, 0.11)),
    'neck': ((0.0, 0.01, 1.56), (0.062, 0.062)),
    'jaw': ((0.0, -0.01, 1.62), (0.07, 0.075)),
    'head': ((0.0, 0.0, 1.70), (0.085, 0.10)),
    'crown': ((0.0, 0.01, 1.79), (0.07, 0.08)),
}
for s, side in ((1, 'R'), (-1, 'L')):
    J.update({
        f'clav{side}': ((s * 0.09, 0.0, 1.47), (0.07, 0.065)),
        f'shoulder{side}': ((s * 0.2, 0.0, 1.44), (0.08, 0.075)),
        f'upperarm{side}': ((s * 0.265, 0.01, 1.31), (0.062, 0.06)),
        f'elbow{side}': ((s * 0.33, 0.02, 1.18), (0.048, 0.046)),
        f'forearm{side}': ((s * 0.38, 0.02, 1.06), (0.05, 0.042)),
        f'wrist{side}': ((s * 0.42, 0.03, 0.95), (0.03, 0.022)),
        f'hand{side}': ((s * 0.45, 0.035, 0.86), (0.042, 0.016)),
        f'fingers{side}': ((s * 0.47, 0.04, 0.78), (0.035, 0.012)),
        f'hip{side}': ((s * 0.1, 0.0, 0.93), (0.105, 0.105)),
        f'thigh{side}': ((s * 0.11, 0.0, 0.75), (0.092, 0.092)),
        f'knee{side}': ((s * 0.115, -0.005, 0.52), (0.062, 0.062)),
        f'calf{side}': ((s * 0.115, 0.012, 0.36), (0.068, 0.066)),
        f'ankle{side}': ((s * 0.115, 0.015, 0.09), (0.035, 0.035)),
        f'heel{side}': ((s * 0.115, 0.03, 0.04), (0.035, 0.035)),
        f'toe{side}': ((s * 0.125, -0.13, 0.03), (0.04, 0.022)),
    })
BONES = [('pelvis', 'waist'), ('waist', 'belly'), ('belly', 'chest'), ('chest', 'upchest'), ('upchest', 'neck'),
         ('neck', 'jaw'), ('jaw', 'head'), ('head', 'crown')]
for side in 'RL':
    BONES += [('upchest', f'clav{side}'), (f'clav{side}', f'shoulder{side}'), (f'shoulder{side}', f'upperarm{side}'),
              (f'upperarm{side}', f'elbow{side}'), (f'elbow{side}', f'forearm{side}'), (f'forearm{side}', f'wrist{side}'),
              (f'wrist{side}', f'hand{side}'), (f'hand{side}', f'fingers{side}'),
              ('pelvis', f'hip{side}'), (f'hip{side}', f'thigh{side}'), (f'thigh{side}', f'knee{side}'),
              (f'knee{side}', f'calf{side}'), (f'calf{side}', f'ankle{side}'), (f'ankle{side}', f'heel{side}'),
              (f'ankle{side}', f'toe{side}')]

def build(levels=4, clear=True):
    """The test human as one applied mesh object 'Human' (Subdivision ``levels`` on the skinned skeleton)."""
    if clear:
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
    names = list(J)
    me = bpy.data.meshes.new('Human')
    me.from_pydata([J[n][0] for n in names], [(names.index(a), names.index(b)) for a, b in BONES], [])
    ob = bpy.data.objects.new('Human', me)
    bpy.context.scene.collection.objects.link(ob)
    sk = ob.modifiers.new('Skin', 'SKIN')
    sk.use_smooth_shade = True
    sv = me.skin_vertices[0].data
    for i, n in enumerate(names):
        sv[i].radius = J[n][1]
        sv[i].use_root = n == 'pelvis'
    ob.modifiers.new('Smooth', 'SUBSURF').levels = 1
    dg = bpy.context.evaluated_depsgraph_get()
    base = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    ob.modifiers.clear()
    ob.data = base
    bpy.data.meshes.remove(me)
    sub = ob.modifiers.new('Hi', 'SUBSURF')
    sub.levels = sub.render_levels = levels
    dg = bpy.context.evaluated_depsgraph_get()
    hi = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    ob.modifiers.clear()
    ob.data = hi
    hi.name = 'Human'
    for p in hi.polygons:
        p.use_smooth = True
    bpy.data.meshes.remove(base)
    zs = [v.co.z for v in hi.vertices]
    print('human', len(hi.vertices), 'verts', len(hi.polygons), 'faces', 'height', round(max(zs) - min(zs), 3))
    return ob


if __name__ == '__main__':
    OUT = sys.argv[-2] if sys.argv[-1].isdigit() else sys.argv[-1]
    build(int(sys.argv[-1]) if sys.argv[-1].isdigit() else 4)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(OUT))
    print('saved', OUT)
