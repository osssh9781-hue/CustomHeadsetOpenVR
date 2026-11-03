"""0.24.95 The Shapes page's thumbnails (user: "쉐입 페이지에서 썸네일도 보여 주라, 그거 선택하고 변경 가능하게"): one
small picture per Polygon kind, Curved kind and Real Part - the shape on transparent, lit like the material balls
(Cycles, the Mech Shader's lookdev HDRI) - into addon/mecha_lab/shape_icons/<poly|curve>_<KIND>.png and
ref_<VEHICLE>_<PART>.png.

    <python with bpy> tools_dev/make_shape_icons.py [px] [samples]
"""
import os
import random
import sys

import bpy  # (first: the bpy module brings bmesh)
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'addon'))
import make_random_shapes_preview as base  # noqa: E402
import make_real_parts_preview as rpv  # noqa: E402
import mecha_lab  # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), 'addon', 'mecha_lab', 'shape_icons')


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    size = int(args[0]) if args else 104
    spp = int(args[1]) if len(args) > 1 else 24
    mecha_lab.register()
    from mecha_lab import random_shapes as rs, ref_parts as rp
    bpy.ops.wm.read_factory_settings(use_empty=True)
    cam, lab = base.scene_setup(size, spp)
    bpy.data.objects.remove(lab)                         # (no name under a thumbnail)
    body = base.flat_material('body', (0.5, 0.54, 0.6))
    os.makedirs(OUT, exist_ok=True)
    jobs = []
    for i, kind in enumerate(rs.KIND_IDS):
        jobs.append((f'poly_{kind}', rs.poly_params(random.Random(11 + i), kind, 2, 0.4, 0.3, i % 2 == 1), 'FRONT'))
    for i, kind in enumerate(rs.CURVE_IDS):
        jobs.append((f'curve_{kind}', rs.curve_params(random.Random(31 + i), kind, 2, True), 'FRONT'))
    for v in rp.PART_IDS:
        for j, part in enumerate(rp.PART_IDS[v]):
            jobs.append((f'ref_{v}_{part}', rp.ref_params(random.Random(1000 + j), v, part, 0.05),
                         rpv.PART_VIEW.get((v, part), 'FRONT')))
    for name, p, view in jobs:
        me, _k = rs.new_mesh(p, 32, 2.0)
        me.materials.append(body)
        ob = bpy.data.objects.new('icon', me)
        bpy.context.scene.collection.objects.link(ob)
        bpy.context.view_layer.update()
        pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        ctr = sum(pts, Vector()) / 8
        rad = max((q - ctr).length for q in pts)
        d = Vector(rpv.VIEWS[view]).normalized()
        cam.location = ctr + d * (rad * 6 + 2)
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        cam.data.ortho_scale = rad * 2.15
        base.render(os.path.join(OUT, name + '.png'))
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
        print('ICON', name, flush=True)
    print('ICONS DONE', len(jobs), flush=True)


if __name__ == '__main__':
    main()
