"""0.24.95 A look at the Shapes page's Jet / Tank shapes (one angle repeated): Jet bodies, Jet wings / fins, Tank
turrets / hulls, Tank armour plates, then a Jet body with four Variations - real edges drawn on each (the same set-up
as ``make_random_shapes_preview``).

    <python with bpy> tools_dev/make_design_shapes_preview.py <out.jpg> [tile px] [samples]
"""
import os
import random
import sys
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'addon'))
sys.path.insert(0, HERE)
import mecha_lab  # noqa: E402
import make_random_shapes_preview as base  # noqa: E402


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    out = args[0]
    size = int(args[1]) if len(args) > 1 else 300
    spp = int(args[2]) if len(args) > 2 else 48
    mecha_lab.register()
    from mecha_lab import random_shapes as rs
    bpy.ops.wm.read_factory_settings(use_empty=True)
    cam, lab = base.scene_setup(size, spp)
    body = base.flat_material('body', (0.42, 0.46, 0.52))
    dark = base.flat_material('edges', (0.02, 0.02, 0.025), 0.8)
    tmp = os.path.splitext(out)[0] + '_tiles'
    os.makedirs(tmp, exist_ok=True)
    jobs = []
    for sd in range(1, 6):
        jobs.append(('Jet body', rs.poly_params(random.Random(500 + sd), 'JET', 2, 0.3, 0.3, True)))
    for sd in range(1, 6):
        p = rs.poly_params(random.Random(600 + sd), 'JET', 2, 0.3, 0.3, sd % 2 == 0, plate=0.04)
        jobs.append((f"Jet wing: {p['d']['style']}" + (' (pair)' if p['sym'] else ''), p))
    want, sd = ['turret', 'turret', 'turret', 'hull', 'hull'], 700   # (both forms shown)
    while want:
        sd += 1
        p = rs.poly_params(random.Random(sd), 'TANK', 2, 0.3, 0.3, True)
        if p['d']['form'] in want:
            want.remove(p['d']['form'])
            jobs.append((f"Tank {p['d']['form']}", p))
    for sd in range(1, 6):
        p = rs.poly_params(random.Random(800 + sd), 'TANK', 2, 0.3, 0.3, False, plate=0.04)
        jobs.append(('Tank armour' + (' (lip bent)' if p.get('folds') else ''), p))
    p = rs.poly_params(random.Random(503), 'JET', 2, 0.3, 0.3, True)
    jobs.append(('Jet body: the one you like', p))
    vr = random.Random(503 * 13)
    for v in range(4):
        jobs.append((f'... variation {v + 1} (Amount 0.4)', rs.vary(p, 0.4, vr)))
    tiles = []
    for n, (label, p) in enumerate(jobs):
        t0 = time.time()
        me, _k = rs.new_mesh(p, 32, 2.0)
        me.materials.append(body)
        ob = bpy.data.objects.new('shape', me)
        bpy.context.scene.collection.objects.link(ob)
        bpy.context.view_layer.update()
        rad = max((Vector(c) - sum((Vector(q) for q in ob.bound_box), Vector()) / 8).length for c in ob.bound_box)
        wob = base.add_wire(ob, rad, dark)
        base.frame(cam, lab, ob, label)
        path = os.path.join(tmp, f'{n:02d}.png')
        base.render(path)
        tiles.append((label, path))
        bpy.data.objects.remove(wob)
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
        print('TILE', n, label, f'{time.time() - t0:.1f} s', flush=True)
    base.sheet(tiles, out, size)
    print('PREVIEW DONE', out, flush=True)


if __name__ == '__main__':
    main()
