"""0.24.95 A look at the Shapes page's Real Parts (user: "실제로 내가 말한 차랑 비행기 탱크를 자료 서치해서 부품을 그대로
만들어볼래?"): every part of every vehicle (Lambo, 911, F-22, Tank) as a summon makes it - each tile one part, its real
edges drawn on it (a Wireframe modifier copy), its name under it, seen from the side that shows it best (Cycles, the
Mech Shader's lookdev HDRI).  Writes a contact sheet.

    <python with bpy> tools_dev/make_real_parts_preview.py <out.jpg> [tile px] [samples] [seed] [vehicles ...]
"""
import os
import random
import sys
import time

import bpy  # (first: the bpy module brings bmesh)
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'addon'))
import make_random_shapes_preview as base  # noqa: E402
import mecha_lab  # noqa: E402

VIEWS = {                                       # (where the camera looks from, toward the part's middle)
    'SIDE': (1.0, 0.45, 0.5), 'TOP': (0.55, 0.75, 1.0), 'FRONT': (0.75, 1.0, 0.62), 'REAR': (0.8, -1.0, 0.55),
    'FIN': (1.0, 0.7, 0.35)}
PART_VIEW = {('LAMBO', 'DOOR'): 'SIDE', ('LAMBO', 'FENDER'): 'SIDE', ('LAMBO', 'INTAKE'): 'FRONT',
             ('P911', 'FENDER_F'): 'SIDE', ('P911', 'FENDER_R'): 'SIDE', ('P911', 'DUCKTAIL'): 'REAR',
             ('P911', 'MIRROR'): 'REAR', ('F22', 'WING'): 'TOP', ('F22', 'STAB'): 'TOP', ('F22', 'FIN'): 'FIN',
             ('F22', 'NOZZLE'): 'REAR', ('F22', 'CANOPY'): 'SIDE', ('F22', 'NOSE'): 'FRONT',
             ('MBT', 'SKIRT'): 'SIDE', ('MBT', 'WHEEL'): 'SIDE', ('MBT', 'TURRET'): 'FRONT',
             ('HMECH', 'SHOULDER'): 'SIDE', ('HMECH', 'HIP'): 'SIDE', ('HMECH', 'VENT'): 'FRONT',
             ('CARBOT', 'SHOULDER'): 'SIDE', ('CARBOT', 'DOOR_WING'): 'SIDE', ('CARBOT', 'WHEEL'): 'SIDE',
             ('CARBOT', 'SHIN'): 'SIDE', ('CARBOT', 'FOREARM'): 'SIDE'}
PART_VIEW.update({('ARMORED', k): 'SIDE' for k in ('H_CREST', 'C_HATCH', 'A_UPPER', 'A_FORE_L', 'A_FORE_H',
                                                   'A_SHOULDER', 'A_ELBOW', 'L_THIGH', 'L_KNEE', 'L_SHIN', 'L_FOOT',
                                                   'L_ANKLE', 'R_THIGH', 'R_SHIN', 'R_FOOT',
                                                   'Q_LEG', 'T_TREAD', 'W_RIFLE', 'W_SHOTGUN', 'W_GATLING',
                                                   'W_BAZOOKA', 'W_GRENADE', 'W_BLADE', 'W_PILE', 'W_SNIPER',
                                                   'U_CANNON')})
PART_VIEW.update({('ARMORED', k): 'REAR' for k in ('B_BACK', 'B_NOZZLE', 'B_SIDE', 'B_OVERED')})
PART_VIEW.update({('ARMORED', 'B_WING'): 'TOP'})


def frame(cam, lab, ob, text, view):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    ctr = sum(pts, Vector()) / 8
    rad = max((p - ctr).length for p in pts)
    d = Vector(VIEWS[view]).normalized()
    cam.location = ctr + d * (rad * 6 + 2)
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    cam.data.ortho_scale = rad * 2.6
    lab.data.body = text
    lab.data.size = rad * 0.17
    lab.location = (0.0, -rad * 1.18, -0.5)


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    out = args[0]
    size = int(args[1]) if len(args) > 1 else 300
    spp = int(args[2]) if len(args) > 2 else 48
    seed = int(args[3]) if len(args) > 3 else 1
    mecha_lab.register()
    from mecha_lab import random_shapes as rs, ref_parts as rp
    bpy.ops.wm.read_factory_settings(use_empty=True)
    cam, lab = base.scene_setup(size, spp)
    body = base.flat_material('body', (0.42, 0.46, 0.52))
    dark = base.flat_material('edges', (0.02, 0.02, 0.025), 0.8)
    tmp = os.path.splitext(out)[0] + '_tiles'
    os.makedirs(tmp, exist_ok=True)
    jobs = []
    only = [a for a in args[4:]]                        # (vehicles to show: all when none named)
    for i, v in enumerate(rp.PART_IDS):
        if only and v not in only:
            continue
        for j, part in enumerate(rp.PART_IDS[v]):
            jobs.append((rp.label(v, part), rp.ref_params(random.Random(seed * 1000 + i * 50 + j), v, part, 0.05),
                         PART_VIEW.get((v, part), 'FRONT')))
    tiles = []
    for n, (label, p, view) in enumerate(jobs):
        t0 = time.time()
        me, _k = rs.new_mesh(p, 32, 2.0)
        me.materials.append(body)
        ob = bpy.data.objects.new('part', me)
        bpy.context.scene.collection.objects.link(ob)
        bpy.context.view_layer.update()
        rad = max((Vector(c) - sum((Vector(q) for q in ob.bound_box), Vector()) / 8).length for c in ob.bound_box)
        wob = base.add_wire(ob, rad, dark)
        frame(cam, lab, ob, label, view)
        path = os.path.join(tmp, f'{n:02d}.png')
        base.render(path)
        tiles.append((label, path))
        bpy.data.objects.remove(wob)
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
        print('TILE', n, label, f'level {rs.LAST["level"]}', f'{time.time() - t0:.1f} s', flush=True)
    base.sheet(tiles, out, size)
    print('PREVIEW DONE', out, flush=True)


if __name__ == '__main__':
    main()
