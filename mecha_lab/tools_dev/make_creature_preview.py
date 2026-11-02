"""0.24.95 A look at the Creature Shader: every Skin Type and every Condition on one creature head (Blender's monkey,
subdivided - crevices, brows, ears), the Mech Shader's lookdev lighting (interior HDRI), Cycles; one tile shows the
mesh's wireframe.  Writes a contact sheet.

    <python with bpy> tools_dev/make_creature_preview.py <out.jpg> [tile px] [samples]
"""
import math
import os
import sys
import time

import bpy  # (first: the bpy module brings bmesh)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'addon'))
import mecha_lab  # noqa: E402


def head():
    bpy.ops.mesh.primitive_monkey_add(size=2.0)
    ob = bpy.context.active_object
    sub = ob.modifiers.new('s', 'SUBSURF')
    sub.levels = 3
    bpy.ops.object.convert(target='MESH')
    bpy.ops.object.shade_smooth()
    return ob


def polypaint(me):
    """A painted look (as ZBrush polypaint comes in): darker on the back and top, a pale front / chin, warm cheeks."""
    import numpy as np
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    front = np.clip(-co[:, 1] * 0.8 + 0.3, 0.0, 1.0)          # (the monkey looks down -y)
    low = np.clip(0.4 - co[:, 2], 0.0, 1.0)
    dark = np.array([0.16, 0.2, 0.1])
    pale = np.array([0.62, 0.58, 0.42])
    warm = np.array([0.55, 0.3, 0.22])
    t = np.clip(front * 0.7 + low * 0.5, 0.0, 1.0)[:, None]
    col = dark * (1 - t) + pale * t
    cheek = np.exp(-((np.abs(co[:, 0]) - 0.55) ** 2 + (co[:, 2] + 0.05) ** 2) / 0.05)[:, None] * (co[:, 1] < 0)[:, None]
    col = col * (1 - cheek * 0.6) + warm * cheek * 0.6
    att = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
    rgba = np.concatenate([col, np.ones((n, 1))], 1).astype(np.float32)
    att.data.foreach_set('color', rgba.ravel())
    me.color_attributes.active_color = att
    me.color_attributes.render_color_index = me.color_attributes.find('Col')


def scene_setup(size, spp):
    from mecha_lab import mech_shader as ms
    sc = bpy.context.scene
    cam_data = bpy.data.cameras.new('cam')
    cam_data.lens = 85
    cam = bpy.data.objects.new('cam', cam_data)
    sc.collection.objects.link(cam)
    cam.location = (2.6, -6.2, 1.3)
    d = (-cam.location.normalized())
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = spp
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.03
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 8
    sc.cycles.sample_clamp_indirect = 3.0
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = -0.25
    sc.mch_mech_hdri = 'interior.exr'
    sc.mch_mech_hdri_rot = math.radians(90)
    assert bpy.ops.mch.mech_hdri(action='SET') == {'FINISHED'}
    sc.world.node_tree.nodes  # (kept: the lookdev's world)
    return ms


def wire_material():
    mat = bpy.data.materials.new('wire')
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value = (0.5, 0.5, 0.52, 1.0)
    bs.inputs['Roughness'].default_value = 0.6
    wf = nt.nodes.new('ShaderNodeWireframe')
    wf.use_pixel_size = True
    wf.inputs['Size'].default_value = 0.6
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    nt.links.new(wf.outputs['Fac'], mix.inputs['Factor'])
    mix.inputs[6].default_value = (0.5, 0.5, 0.52, 1.0)
    mix.inputs[7].default_value = (0.02, 0.02, 0.02, 1.0)
    nt.links.new(mix.outputs[2], bs.inputs['Base Color'])
    nt.links.new(bs.outputs['BSDF'], out.inputs['Surface'])
    return mat


def render(path):
    sc = bpy.context.scene
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    out = args[0]
    size = int(args[1]) if len(args) > 1 else 300
    spp = int(args[2]) if len(args) > 2 else 64
    mecha_lab.register()
    from mecha_lab import creature_shader as cs
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene_setup(size, spp)
    ob = head()
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    tmp = os.path.splitext(out)[0] + '_tiles'
    os.makedirs(tmp, exist_ok=True)
    tiles = []
    # the wireframe first (the mesh the shader reads its crevices / ridges from)
    ob.data.materials.append(wire_material())
    p = os.path.join(tmp, '00_wire.png')
    render(p)
    tiles.append(('Mesh (wireframe)', p))
    # every Skin Type (no polypaint: each type's own colour)
    assert bpy.ops.mch.creature_apply(skin='HUMAN', condition='CLEAN') == {'FINISHED'}
    mat = ob.active_material
    st = mat.mch_creature
    for k, name, _s in cs.SKINS:
        t0 = time.time()
        st.skin_type = k
        p = os.path.join(tmp, f'skin_{k}.png')
        render(p)
        tiles.append((name, p))
        print('TILE', k, f'{time.time() - t0:.1f} s', flush=True)
    # every Condition on a polypainted head (Polypaint 1: the paint is the colour)
    polypaint(ob.data)
    st.skin_type = 'REPTILE'
    st.polypaint = 1.0
    for k, name, _s in cs.CONDITIONS:
        t0 = time.time()
        st.condition = k
        p = os.path.join(tmp, f'cond_{k}.png')
        render(p)
        tiles.append(('Reptile + polypaint: ' + name if k == 'CLEAN' else name, p))
        print('TILE', k, f'{time.time() - t0:.1f} s', flush=True)
    # the colour textures and Hue / Saturation / Value (0.24.95 user: "휴 · 세츄레이션 · 벨류로 조절")
    for label, kw in (('Mud Caked: Red Clay texture', dict(condition='MUD_CAKED', mud_tex='RED_CLAY')),
                      ('... Mud Hue -0.06, Value 0.6', dict(mud_hue=-0.06, mud_val=0.6)),
                      ('Moss: Lichen texture', dict(condition='MOSSY', moss_tex='LICHEN')),
                      ('Polypaint Hue +0.25', dict(condition='CLEAN', base_hue=0.25)),
                      ('Polypaint Saturation 0.3, Value 1.3', dict(base_hue=0.0, base_sat=0.3, base_val=1.3))):
        t0 = time.time()
        for k, val in kw.items():
            setattr(st, k, val)
        p = os.path.join(tmp, f'extra_{len(tiles):02d}.png')
        render(p)
        tiles.append((label, p))
        print('TILE', label, f'{time.time() - t0:.1f} s', flush=True)
    sheet(tiles, out, size)
    print('PREVIEW DONE', out, flush=True)


def sheet(tiles, out, size):
    """The tiles on a dark grey sheet, names under them (Blender's own image API: no Pillow in its Python)."""
    import numpy as np
    cols = 6
    rows = (len(tiles) + cols - 1) // cols
    pad = 6
    W, H = cols * (size + pad) + pad, rows * (size + pad) + pad
    canvas = np.full((H, W, 4), 0.11, np.float32)
    canvas[..., 3] = 1.0
    for i, (_name, p) in enumerate(tiles):
        im = bpy.data.images.load(p)
        a = np.empty(size * size * 4, np.float32)
        im.pixels.foreach_get(a)
        a = a.reshape(size, size, 4)
        r, c = divmod(i, cols)
        y0 = H - (r + 1) * (size + pad)
        x0 = pad + c * (size + pad)
        al = a[..., 3:4]
        canvas[y0:y0 + size, x0:x0 + size, :3] = a[..., :3] * al + canvas[y0:y0 + size, x0:x0 + size, :3] * (1 - al)
        bpy.data.images.remove(im)
    img = bpy.data.images.new('sheet', W, H)
    img.pixels.foreach_set(canvas.ravel())
    img.filepath_raw = out
    img.file_format = 'JPEG'
    img.save()
    with open(os.path.splitext(out)[0] + '_names.txt', 'w') as f:
        for i, (name, _p) in enumerate(tiles):
            f.write(f'{i}\t{name}\n')


if __name__ == '__main__':
    main()
