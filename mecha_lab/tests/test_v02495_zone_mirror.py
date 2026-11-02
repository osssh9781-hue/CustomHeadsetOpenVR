"""0.24.95 Zones: Mirror, Through, the line's width / depth, a texture per zone (user: "왜 미러가 안 돼?", "뒷면도 같이
페인트 칠해지는 옵션도 넣어 줘", "라인 범프 두께랑 깊이 훨씬 더 두껍게 보일 수 있게 조절 기능", "존마다 베이스 컬러
텍스처도 선택할 수 있게"):

* a part with a live Mirror (Mecha Lab's symmetry, X across the world): a Paint Zone drawn on one half shows on the
  mirrored half too (rendered); the part moved: the copy follows; Mirror X + Y: 3 copies; Mirror off: none
* a Split Zone drawn over the mirrored half: the faces it mirrors get the zone's material (the Mirror shows them there)
* Through (the top bar): a Paint Zone on the back faces too (rendered from behind; off: not); a Split Zone: the back
  faces too
* the line: Line Width up to 40 % (bar 15), Line Height up to +-10 (bar +-3); a wider line as much deeper (its
  steepness kept); a line wider than the fine distance field reads the coarse one (the mask's green, made with it)
* a texture per zone: a Mech zone picks from the Mech Shader's base maps (Camo ...), a creature's from its colour maps"""
import math
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, mech_shader as ms, mech_shader_ui as mu, symmetry as sy, top_bar, zones as zn

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
RW = RH = 1000
PX = 160


def no_bisect(ob):
    m = sy.mirror_mod(ob)
    for i in range(3):
        m.use_bisect_axis[i] = False


def camera(loc, rot):
    cd = bpy.data.cameras.new('Cam')
    cd.lens = 35
    cam = bpy.data.objects.new('Cam', cd)
    S.collection.objects.link(cam)
    cam.location, cam.rotation_euler = loc, rot
    S.camera = cam
    C.view_layer.update()
    return cam, cam.matrix_world.inverted(), cam.calc_matrix_camera(C.evaluated_depsgraph_get(), x=RW, y=RH)


def to_px(vm, wm, co):
    v = wm @ vm @ Vector((*co, 1.0))
    return ((v.x / v.w * 0.5 + 0.5) * RW, (v.y / v.w * 0.5 + 0.5) * RH)


def render():
    p = os.path.join(tempfile.mkdtemp(), 'r.png')
    S.render.filepath = p
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(p)
    a = np.array(img.pixels[:]).reshape(PX, PX, 4)[..., :3]
    bpy.data.images.remove(img)
    return a


def at(a, vm, wm, co):
    x, y = to_px(vm, wm, co)
    return a[int(y * PX / RH), int(x * PX / RW)]


def blue(c):
    return c[2] > c[0] * 1.6


w = bpy.data.worlds.new('W')
w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.8, 0.8, 0.8, 1.0)
S.world = w
S.render.engine = 'CYCLES'
S.cycles.samples = 8
S.cycles.use_denoising = False
S.render.resolution_x = S.render.resolution_y = PX

# ---- a part on the -X side, mirrored across the world X plane (Mecha Lab's Mirror), no Bisect
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(-1.5, 0.0, 0.0))
part = C.active_object
part.name = 'Part'
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=15)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.mch.mech_shader_apply(preset='PAINTED')
mat = part.active_material
st = mat.mch_mech
st.edge_wear = st.scratches = st.dirt = st.rust = 0.0
st.paint_color = (0.6, 0.6, 0.6)
sy.set_mode(C, part, 'MIRROR')
no_bisect(part)
C.view_layer.update()
cam, vm, wm = camera((0.0, -9.0, 0.0), (math.radians(90), 0.0, 0.0))
ring = [to_px(vm, wm, (-1.5 + 0.5 * math.cos(t), -1.0, 0.5 * math.sin(t))) for t in
        [k * 2 * math.pi / 40 for k in range(40)]]
z = zn.add_paint_zone(C, part, ring, vm, wm, True, RW, RH, color=(0.05, 0.15, 0.7))
z.line_height = 0.0
check('A Paint Zone on a part with Mirror X: one mirror copy in its nodes', len(zn.mirror_maps(z)) == 1
      and mat.node_tree.nodes.get('mchz:0:v1:mask') is not None and mat.get(zn.SYM_KEY) == zn.sym_key(mat))
a = render()
L, R, mid = at(a, vm, wm, (-1.5, -1, 0)), at(a, vm, wm, (1.5, -1, 0)), at(a, vm, wm, (1.5, -1, 0.75))
check('... rendered: drawn on the left half - blue there and on the mirrored right half; the rest of the right half '
      'the part\'s grey', blue(L) and blue(R) and not blue(mid), (np.round(L, 2).tolist(), np.round(R, 2).tolist(),
                                                                 np.round(mid, 2).tolist()))
part.location.x = -2.0
C.view_layer.update()
a = render()
R2 = at(a, vm, wm, (2.0, -1, 0))
check('... the part moved (the Mirror across the world: the right half moves the other way): the copy follows',
      mat.get(zn.SYM_KEY) == zn.sym_key(mat) and blue(R2) and blue(at(a, vm, wm, (-2.0, -1, 0))),
      np.round(R2, 2).tolist())
part.location.x = -1.5
sy.toggle_axis(C, part, 1)
no_bisect(part)
C.view_layer.update()
check('... Mirror X + Y: 3 copies (X, Y, XY)', len(zn.mirror_maps(z)) == 3
      and mat.node_tree.nodes.get('mchz:0:v3:mask') is not None)
sy.set_mode(C, part, 'OFF')
C.view_layer.update()
check('... Mirror off: no copies left', not zn.mirror_maps(z) and mat.node_tree.nodes.get('mchz:0:v1:mask') is None
      and mat.node_tree.nodes.get('mchz:0:mask') is not None)

# ---- a Split Zone drawn over the mirrored half
sy.set_mode(C, part, 'MIRROR')
no_bisect(part)
C.view_layer.update()
sq = [to_px(vm, wm, c) for c in ((1.1, -1, -0.4), (1.9, -1, -0.4), (1.9, -1, 0.4), (1.1, -1, 0.4))]
zmat, n = zn.split_zone(C, part, sq, vm, wm, True, RW, RH)
idx = len(part.material_slots) - 1
cent = [part.matrix_world @ p.center for p in part.data.polygons if p.material_index == idx]
check('A Split Zone drawn over the mirrored half: the faces it mirrors (on the real half, front) get its material',
      n > 0 and all(-1.95 < c.x < -1.05 and abs(c.y + 1.0) < 1e-3 and abs(c.z) < 0.45 for c in cent),
      (n, [tuple(round(v, 2) for v in c) for c in cent[:3]]))
part.active_material_index = 0
sy.set_mode(C, part, 'OFF')
C.view_layer.update()

# ---- Through
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 4.0))
box = C.active_object
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=11)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.mch.mech_shader_apply(preset='PAINTED')
bm_ = box.active_material
bm_.mch_mech.edge_wear = bm_.mch_mech.scratches = bm_.mch_mech.dirt = bm_.mch_mech.rust = 0.0
bm_.mch_mech.paint_color = (0.6, 0.6, 0.6)
front = cg.OrthoProjector(Quaternion((1, 0, 0), math.radians(90)), Vector((0, 0, 4)), 100.0, (1000, 1000))
c0 = front.to_screen(Vector((0.0, -1.0, 4.0)))
loop = [(c0[0] + 45 * math.cos(t), c0[1] + 45 * math.sin(t)) for t in [k * 2 * math.pi / 32 for k in range(32)]]
S.mch_brush.through_mode = False
zn.perform(C, [loop], front, 'PAINT')
S.mch_brush.through_mode = True
zn.perform(C, [loop], front, 'PAINT')
z1, z2 = bm_.mch_zones[0], bm_.mch_zones[1]
check('Through (the top bar): the zone drawn with it on is Through, the one before not',
      not z1.through and z2.through and bm_.node_tree.nodes['mchz:1:through'].outputs[0].default_value == 1.0)
z1.color, z2.color = (0.05, 0.15, 0.7), (0.05, 0.15, 0.7)
z1.line_height = z2.line_height = 0.0
z2.opacity = 0.0
cam2, vm2, wm2 = camera((0.0, 9.0, 4.0), (math.radians(90), 0.0, math.radians(180)))
a = render()
back_off = at(a, vm2, wm2, (0.0, 1.0, 4.0))
z1.opacity, z2.opacity = 0.0, 1.0
a = render()
back_on = at(a, vm2, wm2, (0.0, 1.0, 4.0))
check('... rendered from behind: Through - the back face blue under the zone; without it - the part\'s grey',
      blue(back_on) and not blue(back_off), (np.round(back_on, 2).tolist(), np.round(back_off, 2).tolist()))
S.mch_brush.through_mode = True
zn.perform(C, [loop], front, 'SPLIT')
idx = len(box.material_slots) - 1
ys = sorted({round((box.matrix_world @ p.center).y, 3) for p in box.data.polygons if p.material_index == idx})
check('... a Split Zone with Through: the front and the back faces under it', ys and ys[0] == -1.0 and ys[-1] == 1.0,
      ys)
S.mch_brush.through_mode = False
box.active_material_index = 0
gs = [(g[0], [c['label'] for c in g[1]]) for g in top_bar.groups(C, 'ZONE')]
check('... the top bar of the Lasso Zone tool: Through', any('Through' in cells for _t, cells in gs), gs)

# ---- the line
rna = zn.MCH_PG_Zone.bl_rna.properties
check('Line Width up to 40 % (the bar to 15), Line Height +-10 (the bar +-3)', rna['line_width'].hard_max == 40.0
      and rna['line_width'].soft_max == 15.0 and rna['line_height'].hard_min == -10.0
      and rna['line_height'].hard_max == 10.0 and rna['line_height'].soft_max == 3.0)
z1.line_height, z1.line_width = -1.0, 0.6
nd = bm_.node_tree.nodes
h06 = nd['mchz:0:lh'].outputs[0].default_value
z1.line_width = 6.0
h6 = nd['mchz:0:lh'].outputs[0].default_value
check('... a line 10 x wider: 10 x deeper (its steepness kept); at 0.6 % (and below) as before', abs(h06 + 1.0) < 1e-6
      and abs(h6 + 10.0) < 1e-5, (h06, h6))
zoom = cg.OrthoProjector(Quaternion((1, 0, 0), math.radians(90)), Vector((0, 0, 4)), 450.0, (1000, 1000))
zn.perform(C, [[(500 + 120 * math.cos(t), 500 + 120 * math.sin(t)) for t in [k * 2 * math.pi / 32 for k in range(32)]]],
           zoom, 'PAINT')
zz = bm_.mch_zones[-1]
zi = len([q for q in bm_.mch_zones if q.projector is not None and q.mask is not None]) - 1
zz.line_width = 6.0
hw_fine, sel_fine = zn.line_px(zz)
zz.line_width = 35.0
hw_wide, sel_wide = zn.line_px(zz)
check('... drawn zoomed in (the part 900 px wide): a 35 % line is wider than the fine distance field reaches (96 '
      'px) - it reads the coarse one (480 px); 6 % the fine one', sel_fine == 0.0 and sel_wide == 1.0
      and hw_wide > 96.0 and hw_wide <= 0.95 * zn.SDF_R2
      and nd[f'mchz:{zi}:lsel'].outputs[0].default_value == 1.0
      and abs(nd[f'mchz:{zi}:lw'].outputs[0].default_value - hw_wide) < 1e-3, (round(hw_fine, 1), round(hw_wide, 1)))
img = z1.mask
iw, ih = img.size
px_ = np.empty(iw * ih * 4, np.float32)
img.pixels.foreach_get(px_)
px_ = px_.reshape(ih, iw, 4)
far = (int(c0[1] * ih / 1000), int((c0[0] + 45 + 200) * iw / 1000))
check('... the mask holds both: red the fine field (0 200 px out), green the coarse one (still falling there)',
      px_[far][0] < 0.01 and abs(px_[far][1] - (0.5 - 200 / 960)) < 0.03, (round(float(px_[far][0]), 3),
                                                                           round(float(px_[far][1]), 3)))
z1.reach2 = 0.0
check('... a zone made before (no coarse field): never reads it, the line no wider than the fine one',
      zn.line_px(z1)[1] == 0.0 and zn.line_px(z1)[0] <= 0.95 * z1.reach)
z1.reach2 = zn.SDF_R2

# ---- a texture per zone
items = [i[0] for i in zn._tex_enum(z1, C)]
check('A texture per zone: a Mech zone picks from the Mech Shader\'s base maps (Flat = none)',
      items[0] == 'FLAT' and 'CAMO' in items and 'CARBON' in items and len(items) == len(ms.MAPS['base'][3]))
z1.tex = 'CAMO'
check('... Camo: its picture in the zone\'s nodes, the colour grey (the texture as it is)',
      nd.get('mchz:0:tex') is not None and nd['mchz:0:tex'].image.name.startswith('CAMO')
      and tuple(round(c, 3) for c in z1.color) == (0.5, 0.5, 0.5))
for o in C.selected_objects:
    o.select_set(False)
box.select_set(True)
C.view_layer.objects.active = box
its, _h = mu.content(C, 0.0, 276.0, 1.0)
check('... the Mech page: the zone\'s Texture and its scale', {'tex', 'tex_scale'} <= {getattr(i, 'prop', '')
                                                                                        for i in its})
bpy.ops.mesh.primitive_uv_sphere_add(location=(0.0, 0.0, 8.0))
crea = C.active_object
bpy.ops.mch.creature_apply(skin='HUMAN', condition='CLEAN')
cz = zn.add_paint_zone(C, crea, loop, vm, wm, True, RW, RH)
citems = [i[0] for i in zn._tex_enum(cz, C)]
check('... a creature\'s zone: its colour maps as before', citems == [i[0] for i in zn._tex_items()]
      and 'CAMO' not in citems)
summary()
