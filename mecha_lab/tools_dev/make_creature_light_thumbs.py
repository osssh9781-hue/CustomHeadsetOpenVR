"""The Creature Light previews (0.24.147): every set-up rendered on a textured creature head over the Fade Floor.

    <blender python> make_creature_light_thumbs.py <out dir> [size]

Writes <add-on>/icons/creature_light/<ident>.png (96 x 72, the Render tab's tiles) and <out dir>/<ident>.png (bigger),
and <out dir>/sheet.png (all 30 with their names) when Pillow is there.
"""
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'addon'))
import mecha_lab  # noqa: E402

OUT = sys.argv[-2] if len(sys.argv) > 2 and sys.argv[-1].isdigit() else sys.argv[-1]
BIG = int(sys.argv[-1]) if sys.argv[-1].isdigit() else 240
os.makedirs(OUT, exist_ok=True)
mecha_lab.register()
from mecha_lab import creature_light as cl  # noqa: E402

ICON_DIR = os.path.join(HERE, '..', 'addon', 'mecha_lab', 'icons', 'creature_light')
os.makedirs(ICON_DIR, exist_ok=True)
C = bpy.context
sc = C.scene
for o in list(sc.objects):
    bpy.data.objects.remove(o)


def creature_material():
    mat = bpy.data.materials.new('Creature Skin')
    nt = mat.node_tree
    pb = nt.nodes.get('Principled BSDF')
    vor = nt.nodes.new('ShaderNodeTexVoronoi')
    vor.inputs['Scale'].default_value = 9.0
    noi = nt.nodes.new('ShaderNodeTexNoise')
    noi.inputs['Scale'].default_value = 3.0
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.05, (0.08, 0.12, 0.05, 1)
    els[1].position, els[1].color = 0.55, (0.42, 0.36, 0.2, 1)
    mixn = nt.nodes.new('ShaderNodeMix')
    mixn.data_type = 'RGBA'
    mixn.blend_type = 'MULTIPLY'
    fac = next(x for x in mixn.inputs if x.name == 'Factor' and x.type == 'VALUE')
    fac.default_value = 0.6
    cols = [x for x in mixn.inputs if x.type == 'RGBA']
    nt.links.new(vor.outputs['Distance'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], cols[0])
    nt.links.new(noi.outputs['Color'], cols[1])
    nt.links.new(next(x for x in mixn.outputs if x.type == 'RGBA'), pb.inputs['Base Color'])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.35
    nt.links.new(vor.outputs['Distance'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], pb.inputs['Normal'])
    pb.inputs['Roughness'].default_value = 0.42
    return mat


bpy.ops.mesh.primitive_monkey_add(size=1.6, location=(0, 0, 0.9))
head = C.object
head.rotation_euler = (0.25, 0, 0)
mod = head.modifiers.new('sub', 'SUBSURF')
mod.levels = mod.render_levels = 2
bpy.ops.object.shade_smooth()
head.data.materials.append(creature_material())
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.lens = 60
cam.location = (2.6, -5.6, 2.1)
cam.rotation_euler = (1.33, 0, 0.43)
sc.world = bpy.data.worlds.new('Before')
st = cl.settings(sc)
cl.apply(sc, cl.ORDER[0])
st.floor = 'FADE'
sc.render.engine = 'CYCLES'
sc.cycles.samples = 24
sc.cycles.use_denoising = True
sc.cycles.device = 'CPU'
sc.render.resolution_x, sc.render.resolution_y = BIG, BIG * 3 // 4
sc.render.image_settings.file_format = 'PNG'
for ident in cl.ORDER:
    cl.apply(sc, ident)
    sc.render.filepath = os.path.join(OUT, ident + '.png')
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(sc.render.filepath)
    img.scale(96, 72)
    img.filepath_raw = os.path.join(ICON_DIR, ident + '.png')
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    print('thumb', ident, flush=True)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
if Image is not None:
    cols, w, h, lab = 6, BIG, BIG * 3 // 4, 22
    rows = (len(cl.ORDER) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * w, rows * (h + lab)), (24, 24, 26))
    dr = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
    except OSError:
        font = ImageFont.load_default()
    for i, ident in enumerate(cl.ORDER):
        x, y = (i % cols) * w, (i // cols) * (h + lab)
        sheet.paste(Image.open(os.path.join(OUT, ident + '.png')).convert('RGB'), (x, y))
        dr.text((x + 6, y + h + 3), f'{i + 1}. {cl.BY_ID[ident][1]}', fill=(220, 220, 220), font=font)
    sheet.save(os.path.join(OUT, 'sheet.png'))
    print('sheet', os.path.join(OUT, 'sheet.png'))
