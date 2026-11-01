"""0.24.95 Sphere icons for the Mech Shader presets (user: "메테리얼 창도 아이콘으로 보이게 해 줄래? 구 형태로").

Every material preset and every Edge Wear preset on a shader ball - a panelled sphere (two grooves round it, four
from top to bottom, like a mech part's panel lines), so the edge wear (the grooves' lips) and the crevice layers (their
bottoms) show too - lit by the interior HDRI (as the lookdev sheet), Cycles, 128 px, transparent background:
    addon/mecha_lab/mech_icons/mat_<PRESET>.png      the material presets
    addon/mecha_lab/mech_icons/wear_<PRESET>.png     the Edge Wear presets, on Chipped Paint
    addon/mecha_lab/mech_icons/hdri_<name>.png       previews of Blender's own HDRIs (256 x 128; the user's
                                                     HDRIs get theirs in Blender, ``mech_shader.hdri_icon``)

    <python with bpy> tools_dev/make_mech_preset_icons.py [mat|wear|hdri|all] [PRESET ...]
"""
import math
import os
import sys
import time

import bpy  # (first: the bpy module brings bmesh)
import bmesh  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.join(os.path.dirname(HERE), 'addon')
sys.path.insert(0, ADDON)
import mecha_lab  # noqa: E402

OUT = os.environ.get('MCH_ICON_OUT') or os.path.join(ADDON, 'mecha_lab', 'mech_icons')
SIZE = 128
SPP = 48
GROOVE_HALF, GROOVE_DEPTH, GROOVE_LIP = 0.07, 0.08, 0.035   # (wider than the edge measure (2.5 % of the size): its lips read as edges)
RINGS = (0.3, -0.4)                       # grooves round the ball (height)
MERIDIANS = (20.0, 110.0, 200.0, 290.0)   # grooves from top to bottom (degrees round z)


def _groove(off):
    return GROOVE_DEPTH if off <= 0 else GROOVE_DEPTH * max(0.0, 1.0 - off / GROOVE_LIP)


def ball():
    """A panelled sphere (radius 1): flat-bottomed grooves round it and from top to bottom (pushed in along the
    radius), an even icosphere so the grooves are crisp everywhere."""
    me = bpy.data.meshes.new('ball')
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=7, radius=1.0)
    planes = [(-math.sin(math.radians(a)), math.cos(math.radians(a))) for a in MERIDIANS]
    for v in bm.verts:
        x, y, z = v.co
        d = 0.0
        for z0 in RINGS:
            d = max(d, _groove(abs(z - z0) - GROOVE_HALF))
        for nx, ny in planes:
            d = max(d, _groove(abs(x * nx + y * ny) - GROOVE_HALF) if (x * -ny + y * nx) > 0 else 0.0)
        if d > 0:
            v.co *= (1.0 - d)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new('ball', me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def edges(me):
    """The ball's edges / crevices: the add-on's own measure (0.24.95: it holds a sharp edge on a dense mesh - before,
    this ball's groove lips read 0.24 of an edge, so the icons were made with a spread of their own)."""
    from mecha_lab import mech_shader as ms
    ms.store_curvature(me)


def scene_setup():
    sc = bpy.context.scene
    cam_data = bpy.data.cameras.new('cam')
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 2.3
    cam = bpy.data.objects.new('cam', cam_data)
    sc.collection.objects.link(cam)
    cam.location = (0.0, -6.0, 2.2)
    d = -cam.location.normalized()
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = SPP
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 6
    sc.cycles.sample_clamp_indirect = 3.0
    sc.cycles.blur_glossy = 0.7
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = SIZE
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = -0.25
    sc.mch_mech_hdri = 'interior.exr'                      # (the lookdev's lighting)
    sc.mch_mech_hdri_rot = math.radians(90)
    assert bpy.ops.mch.mech_hdri(action='SET') == {'FINISHED'}


def render(path):
    sc = bpy.context.scene
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    args = [a for a in sys.argv[sys.argv.index('--') + 1:]] if '--' in sys.argv else sys.argv[1:]
    which = args[0] if args else 'all'
    only = set(args[1:])
    mecha_lab.register()
    from mecha_lab import mech_shader as ms
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(OUT, exist_ok=True)
    if which in {'hdri', 'all'}:
        for f in ms.hdri_files():
            out = os.path.join(OUT, 'hdri_' + os.path.splitext(f)[0] + '.png')
            ms.make_hdri_thumb(os.path.join(ms.hdri_dir(), f), out)
            print('HDRI', f, '->', out, flush=True)
        if which == 'hdri':
            print('ICONS DONE', flush=True)
            return
    scene_setup()
    ob = ball()
    C = bpy.context
    C.view_layer.objects.active = ob
    ob.select_set(True)
    jobs = []
    if which in {'mat', 'all'}:
        jobs += [('mat', k, None) for k, _n, _s in ms.PRESETS]
    if which in {'wear', 'all'}:
        jobs += [('wear', 'PRESET', None)] + [('wear', k, None) for k, _n, _s in ms.WEAR_PRESETS]
    for kind, ident, _x in jobs:
        if only and ident not in only:
            continue
        t0 = time.time()
        old = ob.active_material
        if kind == 'mat':
            mat = ms.new_material(ident)
        else:
            mat = ms.new_material('CHIPPED')
            ms.apply_wear(mat, ident)
        ms.assign(C, [ob], mat, edges=False)
        edges(ob.data)
        if old is not None and old.users == 0:
            bpy.data.materials.remove(old)
        st = mat.mch_mech                                  # (glass / see-through: refraction is noisy - more samples)
        bpy.context.scene.cycles.samples = SPP * 6 if (st.glass > 0.0 or st.alpha < 1.0) else SPP
        path = os.path.join(OUT, f'{kind}_{ident}.png')
        render(path)
        print(f'ICON {kind} {ident} {time.time() - t0:.1f} s', flush=True)
    print('ICONS DONE', flush=True)


if __name__ == '__main__':
    main()
