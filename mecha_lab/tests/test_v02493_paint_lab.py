"""0.24.93 Paint Lab: the pure maths (photo adjust, brightness mask, edge mask) - the workspace / brushes / masks
on a mesh follow below once the tab exists."""
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import paint_lab_core as pc

mecha_lab.register()
fresh()
C = bpy.context

# -- photo adjust (pure) -------------------------------------------------------------------------------------
rng = np.random.default_rng(1)
im = rng.random((64, 48, 4), np.float32)
check('adjust with nothing set is the identity (alpha kept)', np.array_equal(pc.adjust(im), im))
red = np.array([[[1.0, 0.0, 0.0, 1.0]]], np.float32)
h120 = pc.adjust(red, hue=120)[0, 0, :3]
check('Hue +120 turns red toward green (HSV direction)', h120[1] > 0.6 and h120[0] < 0.1 and h120[2] < 0.1, tuple(h120.round(3)))
check('Saturation 0 = the luminance grey (0.299 for red)', np.allclose(pc.adjust(red, saturation=0)[0, 0, :3], 0.299, atol=1e-3))
grey = np.array([[[0.6, 0.6, 0.6, 1.0]]], np.float32)
check('Contrast about mid grey: 0.6 -> 0.7 at x2, brightness +0.1 adds', abs(pc.adjust(grey, contrast=2)[0, 0, 0] - 0.7) < 1e-5
      and abs(pc.adjust(grey, brightness=0.1)[0, 0, 0] - 0.7) < 1e-5)
check('Clipped to 0..1, flips reverse the axes', pc.adjust(grey, brightness=5)[0, 0, 0] == 1.0
      and np.array_equal(pc.adjust(im, flip_x=True), im[:, ::-1]) and np.array_equal(pc.adjust(im, flip_y=True), im[::-1]))

# -- the masks (pure) ----------------------------------------------------------------------------------------
cols = np.array([[0, 0, 0, 1], [0.5, 0.5, 0.5, 1], [1, 1, 1, 1], [1, 0, 0, 1]])
check('value_mask: brightness 0..1 straight (red = 0.299), a black / white range, invert',
      np.allclose(pc.value_mask(cols), [0, 0.5, 1, 0.299], atol=1e-3) and np.allclose(pc.value_mask(cols, 0.25, 0.75), [0, 0.5, 1, 0.098], atol=1e-3)
      and np.allclose(pc.value_mask(cols, invert=True), [1, 0.5, 0, 0.701], atol=1e-3))
co = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], float)
faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
vi = np.array([i for f in faces for i in f]); start = np.arange(0, 24, 4); tot = np.full(6, 4)
check('edge_angles: every cube corner sits on 90-degree folds', np.allclose(pc.edge_angles(co, vi, start, tot, 8), 90.0))
g = np.array([[x, y, 0] for y in range(3) for x in range(3)], float)
gf = [(y * 3 + x, y * 3 + x + 1, (y + 1) * 3 + x + 1, (y + 1) * 3 + x) for y in range(2) for x in range(2)]
gvi = np.array([i for f in gf for i in f]); gs = np.arange(0, 16, 4); gt = np.full(4, 4)
check('... and a flat grid has none; edge_mask 1 on the cube, 0 on the grid, grow spreads one ring',
      pc.edge_angles(g, gvi, gs, gt, 9).max() == 0 and np.all(pc.edge_mask(co, vi, start, tot, 8) == 1)
      and np.all(pc.edge_mask(g, gvi, gs, gt, 9) == 0)
      and np.array_equal(pc.grow_mask(np.array([1, 0, 0, 0, 0, 0, 0, 0, 0.]), gvi, gs, gt, 9, 1), [1, 1, 0, 1, 0, 0, 0, 0, 0]))
check('corner_to_point averages corner colours onto points', np.allclose(pc.corner_to_point(np.ones((24, 4)) * 0.5, vi, 8), 0.5))

# -- the screen: Sculpt Mode in the MECHA LAB tab + the paint flag --------------------------------------------------
import inspect
import os
import types
from mecha_lab import paint_lab as pl, zb_sculpt as zs, zb_ui as zu, panel_capture as pcap, ui_bars as ub
zs.on = lambda c: getattr(c, 'mode', '') == 'SCULPT'          # (the test has no MECHA LAB tab)
fresh()
C = bpy.context
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
ob = C.active_object
r = bpy.ops.mch.zb_switch(target='PAINT')
check('zb_switch PAINT: Sculpt Mode, the paint flag on, the Paint brush, a colour attribute made on the mesh',
      'FINISHED' in r and C.mode == 'SCULPT' and pl.flag(C) and pl.on(C) and zs.zb_name(zs.brush(C)) == 'Paint'
      and pl.colour_attribute(ob.data) is not None, (C.mode, pl.flag(C), zs.zb_name(zs.brush(C))))
sh = C.scene.display.shading
check('... and the Paint look: Solid, studio light, colour attribute, no specular / cavity / shadow, Standard view transform',
      sh.light == 'STUDIO' and sh.color_type == 'VERTEX' and not sh.show_specular_highlight and not sh.show_cavity
      and C.scene.view_settings.view_transform in ('Standard', 'NONE'), (sh.light, sh.color_type, C.scene.view_settings.view_transform))
check('The paint brushes are in the brush table with icons', all(n in zs.BY_Z for n in pl.PAINT_BRUSHES)
      and all(os.path.isfile(os.path.join(os.path.dirname(pl.__file__), 'icons', zs.icon_stem(zs.BY_Z[n][1]) + '.png')) for n in pl.PAINT_BRUSHES))
# polypaint: a gradient, then the eyedropper reads the painted value (not a lit pixel)
bpy.ops.object.mode_set(mode='OBJECT')
att = pl.colour_attribute(ob.data)
n = len(att.data)
co = np.zeros(n * 3, np.float32)
ob.data.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
cols = np.zeros((n, 4), np.float32)
cols[:, 0] = (co[:, 2] + 1) / 2
cols[:, 1] = 0.2
cols[:, 2] = 1 - (co[:, 2] + 1) / 2
cols[:, 3] = 1
att.data.foreach_set('color', cols.ravel())
top = int(np.argmax(co[:, 2]))
f = next(p_ for p_ in ob.data.polygons if top in p_.vertices)
samp = pl.sample_polypaint(ob, f.index, co[top])
check('sample_polypaint: the top of the sphere reads (1, 0.2, 0) - the painted value', samp is not None and np.allclose(samp, (1, 0.2, 0), atol=1e-3), samp)
pl.set_brush_colour(C, samp)
check('... set as the brush colour', np.allclose(pl.brush_colour(C), samp, atol=1e-3), pl.brush_colour(C))
# masks
m = pl.mask_by_value(C, ob)
vals = pl.read_mask(ob.data)
bot = int(np.argmin(co[:, 2]))
check('mask_by_value: the mask IS the polypaint brightness (top (1, .2, 0) = 0.42, bottom (0, .2, 1) = 0.23)',
      m is not None and abs(vals[top] - 0.416) < 0.01 and abs(vals[bot] - 0.231) < 0.01 and 0.2 < m < 0.5, (m, vals[top], vals[bot]))
e = pl.mask_by_edges(C, ob)
check('mask_by_edges: a smooth sphere has no edges masked', e == 0.0, e)
bpy.ops.mesh.primitive_cube_add(size=1.0)
cube = C.active_object
e2 = pl.mask_by_edges(C, cube)
check('... every cube corner is', e2 == 1.0, e2)
bpy.data.objects.remove(cube)
C.view_layer.objects.active = ob
pl.mask_clear(C, ob)
check('mask_clear', pl.read_mask(ob.data).max() == 0.0)
# the photo: an adjusted, LINKED stencil texture on the brush (Essentials brushes take linked textures only)
st = C.scene.mch_paint
img = bpy.data.images.new('photo', 32, 16, alpha=True)
px = np.zeros((16, 32, 4), np.float32)
px[..., 0] = 1.0
px[..., 3] = 1.0
img.pixels.foreach_set(px.ravel())
st.photo = img
st.hue = 120.0
out = pl.rebake(C)
check('rebake: the red photo turned green by Hue +120, in the linked stencil image of the photo\'s size',
      out is not None and out.library is not None and tuple(out.size) == (32, 16) and out.pixels[1] > 0.6 and out.pixels[0] < 0.05,
      (out.size[:] if out else None, [round(v, 2) for v in out.pixels[:3]] if out else None))
bpy.ops.object.mode_set(mode='SCULPT')
pl.apply_mapping(C)
b = zs.brush(C)
check('apply_mapping: the stencil texture on the (linked) brush, plain view-plane mapping while Stencil is off',
      b.texture_slot.texture is not None and b.texture_slot.texture.name == pl.STENCIL_TEX and b.texture_slot.map_mode == 'VIEW_PLANE')
st.stencil_on = True
check('Stencil on (Q): STENCIL mapping', b.texture_slot.map_mode == 'STENCIL')
r = bpy.ops.mch.paint_stencil(action='TOGGLE')
check('mch.paint_stencil toggles it back', 'FINISHED' in r and not st.stencil_on and b.texture_slot.map_mode == 'VIEW_PLANE')
# the drawn screen
class Ctx:
    region = types.SimpleNamespace(width=2560, height=1440, x=0, y=0, type='WINDOW')
    area = None
    def __getattr__(self, name):
        return getattr(bpy.context, name)
CTX = Ctx()
items = zu.items(CTX, 2560, 1440, 1.0)
segs = [(i.label, i.on) for i in items if i.kind == 'seg' and i.label in ('MECHA', 'ZBRUSH', 'PAINT')]
check('The corner card has three screens, PAINT lit', segs == [('MECHA', False), ('ZBRUSH', False), ('PAINT', True)], segs)
tiles = [i.label for i in items if i.kind == 'sbtn']
check('The brush shelf shows the paint brushes (+ Mask / Smooth / Standard / Polygroupit)', all(n in tiles for n in pl.PAINT_BRUSHES) and 'MaskPen' in tiles
      and 'ClayBuildup' not in tiles)
node = pcap.capture(pl.draw_paint_shelf, C)
labels = [nd.opts.get('text', '') for nd in pcap.walk(node) if nd.kind == 'label']
check('The left shelf: Photo / Stencil, Color, Mask by Brightness, Mask by Edges / Cavity, Look boxes',
      all(t in labels for t in ('Photo / Stencil', 'Color', 'Mask by Brightness', 'Mask by Edges / Cavity', 'Look')), labels)
check('The key legend is the Paint Lab one', any(i.kind == 'glabel' and i.label == 'PAINT LAB KEYS' for i in items))
src = inspect.getsource(zs.MCH_OT_zb_press.invoke) + inspect.getsource(zs.MCH_OT_zb_gizmo.invoke) + inspect.getsource(zs.MCH_OT_zb_popup.invoke)
check('Alt + click the model = eyedropper, Q = stencil, right drag = stencil control (in the ZBrush press / Q / RMB handlers)',
      'paint_lab.eyedrop' in src and 'mch.paint_stencil' in src and 'brush.stencil_control' in src)
r = bpy.ops.mch.zb_switch(target='ZBRUSH')
check('Back to ZBRUSH: the flag off, the stencil mapping off the brush, the sculpt shelf again',
      'FINISHED' in r and not pl.flag(C) and b.texture_slot.map_mode == 'VIEW_PLANE'
      and 'ClayBuildup' in [i.label for i in zu.items(CTX, 2560, 1440, 1.0) if i.kind == 'sbtn'])
for kind in ('EXACT', 'MATERIAL', 'PAINT'):
    done = pl.apply_look(C, kind)
check('apply_look: Exact = flat, Material = Material Preview + neutral HDRI + the colour-attribute material, Paint back',
      sh.light == 'STUDIO' and sh.type == 'SOLID' and bpy.data.materials.get(pl.PAINT_MAT) is not None
      and any(m is not None and m.name == pl.PAINT_MAT for m in ob.data.materials), done)
summary()
