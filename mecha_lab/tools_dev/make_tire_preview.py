"""0.24.95 A look at Tire & Wheel (user: "타이어 만드는 제너레이터도 만들어 줘 - 내가 디자인할 수 있게"): four tires made
the way the user would - Summon Tire (a preset), Summon Wheel (Barrel or Disc), one tread block / one spoke drawn
on it, Array Around (Count, Mirror Across) - then applied, their real edges drawn on them (Cycles, the Mech Shader's
lookdev HDRI).  Writes a contact sheet; the tile under each: its preset, tread count, spokes.

    <python with bpy> tools_dev/make_tire_preview.py <out.jpg> [tile px] [samples]
"""
import math
import os
import sys

import bpy  # (first: the bpy module brings bmesh)
import bmesh
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'addon'))
import make_random_shapes_preview as base  # noqa: E402
import mecha_lab  # noqa: E402

# (preset, wheel style, tread outline [(x across, t round)] of the tire's width / diameter, block height, count,
#  mirror, spokes (0: none), spoke width)
DEMOS = [
    ('CAR', 'BARREL', [(0.06, -0.035), (0.42, -0.02), (0.42, 0.02), (0.06, 0.035)], 0.03, 28, True, 5, 0.09),
    ('OFFROAD', 'DISC', [(0.0, -0.05), (0.45, -0.07), (0.48, 0.05), (0.08, 0.06)], 0.07, 14, True, 0, 0.0),
    ('MECH', 'BARREL', [(0.0, 0.0), (0.46, -0.08), (0.46, -0.03), (0.0, 0.05)], 0.06, 18, True, 6, 0.12),
    ('MOTO', 'BARREL', [(0.05, -0.03), (0.3, -0.07), (0.34, -0.05), (0.08, 0.0)], 0.02, 24, True, 3, 0.1),
]


def piece(name, outline, R, Wd, h):
    """A tread block on top of the tire: ``outline`` [(x, t)] (of the width / diameter) pushed out from the tread."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    lo, hi = [], []
    for x, t in outline:
        a = t * 2.0                                       # (t of the diameter round the tire: an angle)
        for r, lst in ((R - 0.004, lo), (R + h * 2 * R, hi)):
            lst.append(bm.verts.new((x * Wd, -r * math.sin(a), r * math.cos(a))))
    n = len(lo)
    bm.faces.new(list(reversed(lo)))
    bm.faces.new(hi)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def spoke(name, wheel, r0, r1, w, x):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(w * 0.5, w, r1 - r0), verts=list(bm.verts))
    bmesh.ops.translate(bm, vec=(x, 0.0, (r0 + r1) / 2), verts=list(bm.verts))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = wheel.matrix_world.copy()
    return ob


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    out = args[0]
    size = int(args[1]) if len(args) > 1 else 420
    spp = int(args[2]) if len(args) > 2 else 48
    mecha_lab.register()
    from mecha_lab import tire_gen as tg
    bpy.ops.wm.read_factory_settings(use_empty=True)
    C = bpy.context
    cam, lab = base.scene_setup(size, spp)
    body = base.flat_material('body', (0.035, 0.035, 0.04), 0.8)        # (rubber)
    rim_m = base.flat_material('rim', (0.75, 0.77, 0.8), 0.3)
    dark = base.flat_material('edges', (0.01, 0.01, 0.012), 0.8)
    tmp = os.path.splitext(out)[0] + '_tiles'
    os.makedirs(tmp, exist_ok=True)
    tiles = []
    st = C.scene.mch_tire
    for n, (preset, style, outline, h, count, mirror, spokes, sw) in enumerate(DEMOS):
        for o in list(bpy.data.objects):
            if o.type in {'MESH', 'EMPTY'}:
                bpy.data.objects.remove(o)
        C.scene.cursor.location = (0.0, 0.0, 0.0)
        st.preset = preset
        st.wheel_style = style
        bpy.ops.mch.tire_add(kind='TIRE')
        tire = C.active_object
        bpy.ops.mch.tire_add(kind='WHEEL')
        wheel = C.active_object
        p = tg.params(tire)
        R, Wd = p['D'] / 2, p['w'] * p['D']
        made = [tire, wheel]
        blk = piece('Tread', outline, R, Wd, h)
        for o in C.selected_objects:
            o.select_set(False)
        blk.select_set(True)
        tire.select_set(True)
        C.view_layer.objects.active = tire
        st.count, st.mirror = count, mirror
        bpy.ops.mch.tire_array()
        tg.apply_round(C, blk)
        made.append(blk)
        if spokes:
            Rw = p['rr'] * R
            sp = spoke('Spoke', wheel, 0.2 * Rw, 0.93 * Rw, sw * Rw, 0.12 * 0.84 * Wd)
            for o in C.selected_objects:
                o.select_set(False)
            sp.select_set(True)
            wheel.select_set(True)
            C.view_layer.objects.active = wheel
            st.count, st.mirror = spokes, False
            bpy.ops.mch.tire_array()
            tg.apply_round(C, sp)
            made.append(sp)
        C.view_layer.update()
        for ob in made:
            ob.data.materials.clear()
            ob.data.materials.append(rim_m if ob in (wheel,) or ob.name.startswith('Spoke') else body)
        wires = []
        for ob in made:
            w = base.add_wire(ob, R * 1.2, dark)
            w.matrix_world = ob.matrix_world
            wires.append(w)
        d = Vector((0.85, 0.75, 0.5)).normalized()
        cam.location = d * (R * 12 + 2)
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        cam.data.ortho_scale = R * 2.9
        label = f'{tg.PRESETS[preset][0]} - tread x{count}{" mirrored" if mirror else ""}' + \
                (f', {spokes} spokes' if spokes else ', disc wheel')
        lab.data.body = label
        lab.data.size = R * 0.15
        lab.location = (0.0, -R * 1.3, -0.5)                # (in the camera's space: under the tire)
        path = os.path.join(tmp, f'{n:02d}.png')
        base.render(path)
        tiles.append((label, path))
        print('TILE', n, label, flush=True)
    base.sheet(tiles, out, size, cols=len(tiles))
    print('TIRE PREVIEW DONE', out, flush=True)


if __name__ == '__main__':
    main()
