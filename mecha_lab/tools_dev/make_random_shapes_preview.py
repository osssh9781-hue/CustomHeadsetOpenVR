"""0.24.95 A look at the Shapes page's random base shapes: Polygon shapes of every kind (solid, then plates), Curved
shapes of every kind (solid, then plates), then a shape with four Variations - each tile one shape, its real edges drawn on it (a Wireframe modifier
copy: the quads and n-gons as they are), its name under it
(Cycles, the Mech Shader's lookdev HDRI).  Writes a contact sheet.

    <python with bpy> tools_dev/make_random_shapes_preview.py <out.jpg> [tile px] [samples]
"""
import math
import os
import random
import sys
import time

import bpy  # (first: the bpy module brings bmesh)
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'addon'))
import mecha_lab  # noqa: E402


def flat_material(name, rgb, rough=0.55):
    mat = bpy.data.materials.new(name)
    bs = mat.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*rgb, 1.0)
    bs.inputs['Roughness'].default_value = rough
    return mat


def add_wire(ob, rad, mat):
    """The mesh's real edges (quads, n-gons - not the triangles a render makes of them): a copy with a thin
    Wireframe modifier, dark."""
    w = bpy.data.objects.new('wire', ob.data)
    bpy.context.scene.collection.objects.link(w)
    m = w.modifiers.new('wire', 'WIREFRAME')
    m.thickness = rad * 0.007
    m.use_even_offset = True
    m.use_replace = True
    w.material_slots[0].link = 'OBJECT'
    w.material_slots[0].material = mat
    return w


def label_material():
    mat = bpy.data.materials.new('label')
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (0.9, 0.9, 0.9, 1.0)
    em.inputs['Strength'].default_value = 1.0
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    return mat


def scene_setup(size, spp):
    sc = bpy.context.scene
    cam_data = bpy.data.cameras.new('cam')
    cam_data.type = 'ORTHO'
    cam_data.clip_start = 0.01
    cam = bpy.data.objects.new('cam', cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = spp
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.03
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = 0.2
    sc.mch_mech_hdri = 'interior.exr'
    sc.mch_mech_hdri_rot = math.radians(60)
    assert bpy.ops.mch.mech_hdri(action='SET') == {'FINISHED'}
    txt = bpy.data.curves.new('label', 'FONT')
    txt.align_x = 'CENTER'
    lab = bpy.data.objects.new('label', txt)
    sc.collection.objects.link(lab)
    lab.parent = cam
    txt.materials.append(label_material())
    return cam, lab


def frame(cam, lab, ob, text):
    """The camera looking at the shape's front (+Y) from the right and above; the name at the tile's foot."""
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    ctr = sum(pts, Vector()) / 8
    rad = max((p - ctr).length for p in pts)
    d = Vector((0.75, 1.0, 0.62)).normalized()
    cam.location = ctr + d * (rad * 6 + 2)
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    cam.data.ortho_scale = rad * 2.6
    lab.data.body = text
    lab.data.size = rad * 0.17
    lab.location = (0.0, -rad * 1.18, -0.5)


def render(path):
    sc = bpy.context.scene
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    out = args[0]
    size = int(args[1]) if len(args) > 1 else 300
    spp = int(args[2]) if len(args) > 2 else 48
    mecha_lab.register()
    from mecha_lab import random_shapes as rs
    bpy.ops.wm.read_factory_settings(use_empty=True)
    cam, lab = scene_setup(size, spp)
    body = flat_material('body', (0.42, 0.46, 0.52))
    dark = flat_material('edges', (0.02, 0.02, 0.025), 0.8)
    tmp = os.path.splitext(out)[0] + '_tiles'
    os.makedirs(tmp, exist_ok=True)
    names = dict((k[0], k[1]) for k in rs.KINDS + rs.CURVE_KINDS)
    jobs = []                                            # (label, parameters)
    for i, kind in enumerate(rs.KIND_IDS):               # Polygon, solid
        p = rs.poly_params(random.Random(100 + i * 7), kind, 2, 0.4, 0.3, i % 2 == 1)
        jobs.append((f'Polygon: {names[kind]}', p))
    for i, kind in enumerate(rs.KIND_IDS):               # Polygon, plate
        p = rs.poly_params(random.Random(200 + i * 7), kind, 2, 0.4, 0.3, i % 2 == 0, plate=0.05)
        jobs.append((f'Polygon plate: {names[kind]}', p))
    for kind, seeds in (('POD', (3, 4, 9)), ('TORSO', (2, 5, 8)), ('DOMECUT', (2, 5)), ('CAPSULE', (7,)),
                        ('SHELL', (1,))):
        for sd in seeds:
            jobs.append((f'Curved: {names[kind]}', rs.curve_params(random.Random(sd), kind, 2, True)))
    for kind, sd in (('POD', 21), ('TORSO', 22), ('DOMECUT', 23), ('CAPSULE', 24), ('SHELL', 25)):
        jobs.append((f'Curved plate: {names[kind]}', rs.curve_params(random.Random(sd), kind, 2, True, 0.05)))
    p = rs.curve_params(random.Random(31), 'TORSO', 2, True)
    jobs.append(('Torso: the one you like', p))
    vr = random.Random(31 * 13)
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
        wob = add_wire(ob, rad, dark)
        frame(cam, lab, ob, label)
        path = os.path.join(tmp, f'{n:02d}.png')
        render(path)
        tiles.append((label, path))
        bpy.data.objects.remove(wob)
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
        print('TILE', n, label, f'{time.time() - t0:.1f} s', flush=True)
    sheet(tiles, out, size)
    print('PREVIEW DONE', out, flush=True)


def sheet(tiles, out, size, cols=5):
    """The tiles on a dark grey sheet (Blender's own image API: no Pillow in its Python)."""
    import numpy as np
    rows = (len(tiles) + cols - 1) // cols
    pad = 6
    W, H = cols * (size + pad) + pad, rows * (size + pad) + pad
    canvas = np.full((H, W, 4), 0.12, np.float32)
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


if __name__ == '__main__':
    main()
