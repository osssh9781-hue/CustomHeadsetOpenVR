"""0.24.95 AC Style parts put together as one standing machine (user: "아머드 코어는 이런 실루엣이야
팔다리 쪽 봐 봐"): feet, ankles, shins (knee point, calf blade), thighs, hip skirts, a core, a head,
swept pauldrons, upper arms, elbow joints, gauntlets, fists - each part as a summon makes it, the left
side the right one mirrored - seen from the front, the side and the back, their real edges drawn on
them (Cycles, the Mech Shader's lookdev HDRI).

    <python with bpy> tools_dev/make_ac_figure_preview.py <out.jpg> [px per view] [samples]
"""
import math
import os
import random
import sys

import bpy  # (first: the bpy module brings bmesh)
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'addon'))
import make_random_shapes_preview as base  # noqa: E402
import mecha_lab  # noqa: E402

# (part, size (its longest side), the point of its box (0 - 1 each axis) put at ``at``, tilt round X in degrees);
# x > 0: a pair (the left one mirrored)
LAYOUT = [
    ('L_FOOT', 0.95, (0.5, 0.42, 0.0), (0.4, 0.06, 0.0), 0),
    ('L_ANKLE', 0.2, (0.5, 0.5, 0.5), (0.4, 0.0, 0.22), 0),
    ('L_SHIN', 1.6, (0.5, 0.5, 0.0), (0.4, 0.0, 0.17), -10),
    ('L_THIGH', 1.15, (0.5, 0.5, 0.0), (0.36, 0.24, 1.7), 12),
    ('L_SKIRT', 0.55, (0.5, 0.5, 0.5), (0.47, 0.0, 2.72), 0),
    ('C_MID', 1.1, (0.5, 0.5, 0.0), (0.0, 0.0, 2.86), 0),
    ('H_SENSOR', 0.34, (0.5, 0.5, 0.0), (0.0, 0.08, 3.86), 0),
    ('A_SHOULDER', 0.88, (0.0, 0.55, 0.0), (0.56, -0.02, 3.52), 0),
    ('A_UPPER', 0.82, (0.5, 0.5, 1.0), (0.88, -0.02, 3.6), 0),
    ('A_ELBOW', 0.22, (0.5, 0.5, 0.5), (0.88, -0.02, 2.76), 0),
    ('A_FORE_H', 1.0, (0.5, 0.5, 1.0), (0.9, 0.02, 2.84), -6),
    ('A_HAND', 0.26, (0.5, 0.5, 1.0), (0.9, 0.12, 1.86), 0),
]
VIEWS = (('front', (0.75, 1.0, 0.22)), ('side', (1.0, 0.1, 0.1)), ('back', (-0.7, -1.0, 0.3)))


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    out = args[0]
    px = int(args[1]) if len(args) > 1 else 520
    spp = int(args[2]) if len(args) > 2 else 48
    mecha_lab.register()
    from mecha_lab import random_shapes as rs, ref_parts as rp
    bpy.ops.wm.read_factory_settings(use_empty=True)
    cam, lab = base.scene_setup(px, spp)
    bpy.data.objects.remove(lab)
    body = base.flat_material('body', (0.42, 0.46, 0.52))
    dark = base.flat_material('edges', (0.02, 0.02, 0.025), 0.8)
    ids = rp.PART_IDS['ARMORED']
    obs = []
    for name, size, anchor, at, tilt in LAYOUT:
        p = rp.ref_params(random.Random(1000 + ids.index(name)), 'ARMORED', name, 0.05)
        for side in ((1, -1) if at[0] else (1,)):
            me, _k = rs.new_mesh(p, 32, size)
            me.materials.append(body)
            ob = bpy.data.objects.new(name, me)
            bpy.context.scene.collection.objects.link(ob)
            lo = Vector([min(v.co[i] for v in me.vertices) for i in range(3)])
            hi = Vector([max(v.co[i] for v in me.vertices) for i in range(3)])
            a = Vector([lo[i] + (hi[i] - lo[i]) * anchor[i] for i in range(3)])
            rot = Matrix.Rotation(math.radians(tilt), 3, 'X')
            ob.scale.x = side
            ob.rotation_euler.x = math.radians(tilt)
            ob.location = Vector((at[0] * side, at[1], at[2])) - rot @ Vector((a.x * side, a.y, a.z))
            bpy.context.view_layer.update()
            w = base.add_wire(ob, 1.6, dark)
            w.matrix_world = ob.matrix_world
            obs.append(ob)
    pts = [ob.matrix_world @ Vector(c) for ob in obs for c in ob.bound_box]
    ctr = sum(pts, Vector()) / len(pts)
    rad = max((q - ctr).length for q in pts)
    sc = bpy.context.scene
    sc.render.resolution_x = px
    sc.render.resolution_y = int(px * 1.3)
    tiles = []
    for nm, d in VIEWS:
        d = Vector(d).normalized()
        cam.location = ctr + d * (rad * 6 + 2)
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        cam.data.ortho_scale = rad * 2.05
        path = os.path.splitext(out)[0] + f'_{nm}.png'
        base.render(path)
        tiles.append(path)
        print('VIEW', nm, flush=True)
    import numpy as np                                  # (Blender's own image API: no Pillow in its Python)
    w, h = sc.render.resolution_x, sc.render.resolution_y
    canvas = np.full((h, w * len(tiles), 4), 0.11, np.float32)
    canvas[..., 3] = 1.0
    for i, t in enumerate(tiles):
        im = bpy.data.images.load(t)
        a = np.empty(w * h * 4, np.float32)
        im.pixels.foreach_get(a)
        a = a.reshape(h, w, 4)
        al = a[..., 3:4]
        part = canvas[:, i * w:(i + 1) * w, :3]
        canvas[:, i * w:(i + 1) * w, :3] = a[..., :3] * al + part * (1 - al)
        bpy.data.images.remove(im)
    img = bpy.data.images.new('figure', w * len(tiles), h)
    img.pixels.foreach_set(canvas.ravel())
    img.filepath_raw = out
    img.file_format = 'JPEG'
    img.save()
    for t in tiles:
        os.remove(t)
    print('FIGURE DONE', out, flush=True)


if __name__ == '__main__':
    main()
