"""0.24.95 A look at the Shapes page's vehicle parts: Car parts (Lamborghini-like, polygon), Car parts (Porsche-like,
curved), Tank parts (polygon and cast), kinked plates, then a kinked skirt with four Variations - real edges drawn on
each (the same set-up as ``make_random_shapes_preview``).

    <python with bpy> tools_dev/make_vehicle_shapes_preview.py <out.jpg> [tile px] [samples]
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

    def part_of(p):
        d = p.get('d') if isinstance(p.get('d'), dict) else {}
        return p.get('part') or d.get('part')

    def pick(fam, kind, plate, want, base, sym=True):
        """parameters of the next seeds from ``base`` whose part is ``want`` (in order)"""
        out, sd = [], base
        for w in want:
            while True:
                sd += 1
                rng = random.Random(sd)
                p = (rs.poly_params(rng, kind, 2, 0.3, 0.3, sym, plate=plate) if fam == 'POLY'
                     else rs.curve_params(rng, kind, 2, True, plate))
                if part_of(p) == w:
                    out.append(p)
                    break
        return out
    for p in pick('POLY', 'CAR', 0.0, ['scoop', 'spoiler', 'lamp', 'scoop', 'spoiler'], 1000):
        jobs.append((f"Car {part_of(p)} (wedge)", p))
    for p in pick('POLY', 'CAR', 0.04, ['door', 'fender', 'fender', 'fin', 'door'], 1100):
        jobs.append((f"Car {part_of(p)} plate (wedge)", p))
    for p in pick('CURVE', 'CAR', 0.0, ['lamp', 'mirror', 'bumper'], 1200) + \
            pick('CURVE', 'CAR', 0.04, ['fender', 'hood'], 1300):
        jobs.append((f"Car {part_of(p)} (curved)", p))
    for p in pick('POLY', 'TANK', 0.0, ['era', 'cheek', 'mantlet', 'box'], 1400) + \
            pick('POLY', 'TANK', 0.04, ['skirt'], 1500):
        jobs.append((f"Tank {part_of(p)}", p))
    for p in pick('POLY', 'TANK', 0.04, ['skirt', 'guard'], 1600) + pick('CURVE', 'TANK', 0.0, ['mantlet', 'cupola'], 1700) + \
            pick('CURVE', 'TANK', 0.04, ['guard'], 1800):
        jobs.append((f"Tank {part_of(p)}" + (' (cast)' if p['family'] == 'CURVE' else ''), p))
    p = pick('POLY', 'TANK', 0.04, ['skirt'], 1900)[0]
    jobs.append(('Tank skirt: the one you like', p))
    vr = random.Random(1913)
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
