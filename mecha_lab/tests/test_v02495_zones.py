"""0.24.95 Lasso Zones on Mech parts (user: "메카닉 할 때 내가 라쏘로 그은 영역 색이랑 재질 다르게 할 수 있나?" -> both ways):

* Paint Zone: the lasso projected from the view onto the part (a hidden projector parented to it); inside, the paint is
  the zone's (colour, roughness, metallic, coverage) - rendered: the zone's colour inside, the part's outside, not on
  the back; it moves with the part; sliders at once; it survives the Mech tree being made anew; Delete
* Split Zone: edges cut along the lasso (the mesh stays one piece, closed), the faces inside - only on the side seen -
  get a second Mech material of their own (a lasso inside one big face, and one over a corner)
* the Mech page: a Zones section (Paint Zone / Split Zone, each zone's sliders, the part's materials to switch)
* the wear (user: "엣지 까짐이랑 긁힘 때 녹은 분리된 색이랑 다르게 - 똑같이 넣는 거랑 다르게 넣는 거 옵션으로"): a Paint
  Zone's Own Wear (its own Edge Wear / Scratches / Dirt / Rust - rendered: its own rust inside only); a Split Zone's
  Same Wear as the Part (follows the part's material, off: its own)
* the boundary line (user: "컬러 다르게 한 경계에 라인으로 경계 범프, 헤이트값 조절 가능하게"): the mask a signed distance
  field (0.5 on the outline); Line Height / Line Width into the bump - rendered with a side light: the boundary
  changes, the middle does not; a Split Zone's line in both materials, kept in step, removed together"""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import mech_shader as ms, mech_shader_ui as mu, zones as zn

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
RW = RH = 1000


def camera(loc, rot):
    cd = bpy.data.cameras.new('Cam')
    cam = bpy.data.objects.new('Cam', cd)
    S.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = rot
    S.camera = cam
    C.view_layer.update()
    return cam


def view_of(cam):
    dg = C.evaluated_depsgraph_get()
    return cam.matrix_world.inverted(), cam.calc_matrix_camera(dg, x=RW, y=RH)


def to_px(vm, wm, co):
    v = wm @ vm @ Vector((*co, 1.0))
    return ((v.x / v.w * 0.5 + 0.5) * RW, (v.y / v.w * 0.5 + 0.5) * RH)


def render(cam, px=60):
    S.camera = cam
    S.render.engine = 'CYCLES'
    S.cycles.samples = 4
    S.cycles.use_denoising = False
    S.render.resolution_x = S.render.resolution_y = px
    S.render.resolution_percentage = 100
    S.render.film_transparent = False
    import os
    import tempfile
    path = os.path.join(tempfile.mkdtemp(), 'z.png')
    S.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)
    a = np.array(img.pixels[:]).reshape(px, px, 4)[..., :3]
    bpy.data.images.remove(img)
    return a


def world():
    w = bpy.data.worlds.new('W')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.8, 0.8, 0.8, 1.0)
    S.world = w


world()
bpy.ops.mesh.primitive_cube_add(size=2.0)
part = C.active_object
part.name = 'Part'
bpy.ops.mch.mech_shader_apply(preset='PAINTED')
mat = part.active_material
st = mat.mch_mech
st.edge_wear = 0.0
st.scratches = st.dirt = st.rust = 0.0
st.paint_color = (0.6, 0.6, 0.6)
front = camera((0.0, -6.0, 0.0), (math.radians(90), 0.0, 0.0))
vm, wm = view_of(front)
square = [to_px(vm, wm, c) for c in ((-0.5, -1.0, -0.5), (0.5, -1.0, -0.5), (0.5, -1.0, 0.5), (-0.5, -1.0, 0.5))]

# ---- Paint Zone
check('The Mech Shader has the zone hubs (mask, cover, rough, metal, colour; own wear; height) and is version 11',
      ms.VERSION >= 11 and mat.node_tree.nodes.get('mch:zone_own') is not None
      and mat.node_tree.nodes.get('mch:zone_height') is not None and all(mat.node_tree.nodes.get('mch:zone_' + k) is not None
                              for k in ('mask', 'cover', 'rough', 'metal', 'color')))
own = sorted(n.name for n in mat.node_tree.nodes)
z = zn.add_paint_zone(C, part, square, vm, wm, True, RW, RH, color=(0.8, 0.35, 0.0))
proj = z.projector
check('Paint Zone: a projector parented to the part (hidden, no render), a packed mask picture of the lasso',
      proj is not None and proj.parent == part and proj.hide_get() and proj.hide_render and z.mask.packed_file
      is not None and z.mask.size[0] == 1000 and z.mask.size[1] == 1000)
mpx = np.array(z.mask.pixels[:]).reshape(1000, 1000, 4)[..., 0]
cx, cy = int(sum(p[0] for p in square) / 4), int(sum(p[1] for p in square) / 4)
ins = mpx > 0.5
edge_v = mpx[cy, int(round(square[0][0]))]
check('... the mask: a distance field of the lasso - 1 deep inside, 0 outside, 0.5 on the outline, the inside as big '
      'as the square', mpx[cy, cx] > 0.99 and mpx[5, 5] < 0.01 and abs(edge_v - 0.5) < 0.03
      and abs(ins.sum() - (square[1][0] - square[0][0]) * (square[2][1] - square[1][1])) < 2500,
      (round(float(edge_v), 3), int(ins.sum())))
nodes = mat.node_tree.nodes
check('... linked into the Mech Shader (the hubs fed by the zone\'s nodes)',
      nodes['mch:zone_mask'].inputs[0].is_linked and nodes['mch:zone_color'].inputs[6].is_linked
      or any(sk.is_linked for sk in nodes['mch:zone_color'].inputs))
img = render(front)
mid, side = img[30, 30], img[30, 11]
check('Rendered from the front: the zone\'s orange in the middle, the part\'s grey beside it',
      mid[0] > mid[2] * 2.2 and mid[0] > 0.2 and abs(side[0] - side[2]) < 0.08,   # (0.24.95 the zone covers the base map: 2.5)
      (np.round(mid, 3).tolist(), np.round(side, 3).tolist()))
back = camera((0.0, 6.0, 0.0), (math.radians(90), 0.0, math.radians(180)))
img = render(back)
check('... from the back: grey (only the faces that faced the view are painted)',
      abs(img[30, 30][0] - img[30, 30][2]) < 0.08, np.round(img[30, 30], 3).tolist())
z.through = True
img = render(back)
check('... Through on: the back painted too', img[30, 30][0] > img[30, 30][2] * 2.0,
      np.round(img[30, 30], 3).tolist())
z.through = False
z.color = (0.05, 0.2, 0.8)
check('Sliders at once (Color -> the zone\'s RGB node)',
      abs(nodes['mchz:0:color'].outputs[0].default_value[2] - 0.8) < 1e-6)
part.location.x = 3.0
front.location.x = 3.0
C.view_layer.update()
img = render(front)
check('The part moved (and the camera with it): the zone moved with it (blue in the middle)',
      img[30, 30][2] > img[30, 30][0] * 2.0, np.round(img[30, 30], 3).tolist())
part.location.x = 0.0
front.location.x = 0.0
C.view_layer.update()
ms.build(mat)
ms.sync(mat)
check('The Mech tree made anew (a new version / Reset): the zone is linked back in',
      mat.node_tree.nodes['mch:zone_mask'].inputs[0].is_linked and mat.node_tree.nodes.get('mchz:0:mask') is not None)
# ---- the boundary line: Line Height / Line Width in the bump
check('A Paint Zone has a boundary line from the start (Line Height -0.35: a groove), linked into the bump',
      abs(z.line_height + 0.35) < 1e-6 and mat.node_tree.nodes['mch:zone_height'].inputs[0].is_linked
      and abs(mat.node_tree.nodes['mchz:0:lh'].outputs[0].default_value + 0.35) < 1e-6)
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
sun.data.energy = 4.0
sun.rotation_euler = (math.radians(70), 0.0, math.radians(-70))
S.collection.objects.link(sun)
z.color = tuple(st.paint_color)
z.line_width = 6.0
z.line_height = 0.0
la = render(front, 120)
z.line_height = -1.0
lb = render(front, 120)
bx = int(round(square[0][0] * 120 / RW))
d_edge = max(float(np.abs(lb[60, x] - la[60, x]).sum()) for x in range(bx - 2, bx + 3))
d_mid = float(np.abs(lb[60, 60] - la[60, 60]).sum())
check('... rendered (a side light): Line Height -1 changes the boundary, not the middle (Line Width 6 %)',
      d_edge > 0.05 and d_mid < 0.01, (round(d_edge, 3), round(d_mid, 4)))
z.line_height = 0.0
check('... Line Height 0: no line (its node 0)', mat.node_tree.nodes['mchz:0:lh'].outputs[0].default_value == 0.0)
z.line_width, z.line_height = 0.6, -0.35
bpy.data.objects.remove(sun)
z.color = (0.05, 0.2, 0.8)

# ---- the wear: the part's (default) or the zone's own
st.rust = 0.0
z.own_wear = True
check('Own Wear on: the zone starts from the part\'s amounts (Rust 0), on in its nodes, the hubs linked',
      z.rust == 0.0 and mat.node_tree.nodes['mchz:0:own'].outputs[0].default_value == 1.0
      and mat.node_tree.nodes['mch:zone_own'].inputs[0].is_linked
      and mat.node_tree.nodes['mch:zone_w_rust'].inputs[0].is_linked)
img0 = render(front)
z.rust = 1.0
img1 = render(front)
dm, ds = float(np.abs(img1[30, 30] - img0[30, 30]).sum()), float(np.abs(img1[30, 11] - img0[30, 11]).sum())
check('... the zone\'s own Rust 1.0: rendered rusty in the zone, beside it (the part, Rust 0) as before',
      dm > 0.08 and ds < 0.03, (round(dm, 3), round(ds, 3)))
z.own_wear = False
img2 = render(front)
check('... Own Wear off: the part\'s again (no rust in the zone)', float(np.abs(img2[30, 30] - img0[30, 30]).sum())
      < 0.03, np.round(img2[30, 30], 3).tolist())
z.own_wear = True
bpy.ops.object.select_all(action='DESELECT')
part.select_set(True)
C.view_layer.objects.active = part
its, _h = mu.content(C, 0.0, 276.0, 1.0)
props = {getattr(i, 'prop', '') for i in its if getattr(i, 'data', None) is not None}
heads = {i.label.split('   ')[0]: i for i in its if i.kind == 'shead'}
check('The Mech page: Zones (open) - Paint Zone / Split Zone, the zone\'s colour, roughness, metallic, paint, '
      'opacity, Through, Delete', 'ZONES' in heads and heads['ZONES'].on
      and {'color', 'roughness', 'metallic', 'cover', 'opacity', 'through', 'own_wear', 'edge_wear', 'scratches',
           'dirt', 'dirt_top', 'dirt_low', 'rust', 'line_height', 'line_width'} <= props
      and {'Paint Zone', 'Split Zone', 'Delete'} <= {i.label for i in its if i.kind == 'tbtn'})
r = bpy.ops.mch.zone_remove(index=0)
check('Delete: the zone, its projector and its picture gone, the hubs empty, the Mech Shader\'s own nodes all there',
      r == {'FINISHED'} and len(mat.mch_zones) == 0 and 'Zone 1 (Part)' not in bpy.data.objects
      and not mat.node_tree.nodes['mch:zone_mask'].inputs[0].is_linked
      and len(mat.node_tree.nodes) == len(own), (len(mat.node_tree.nodes), len(own)))

# ---- Split Zone
me = part.data
nf = len(me.polygons)
zmat, n = zn.split_zone(C, part, square, vm, wm, True, RW, RH)
area = sum(p.area for p in me.polygons if p.material_index == 1)
ys = [p.center.y for p in me.polygons if p.material_index == 1]
check('Split Zone (a lasso inside the one big front face): new edges along it, the square inside its own material '
      '(area 1.0, all on the front)', n >= 1 and abs(area - 1.0) < 0.02 and all(abs(y + 1.0) < 1e-4 for y in ys)
      and len(me.polygons) > nf, (n, round(area, 4), len(me.polygons)))
ec = np.zeros(len(me.edges), int)
for p in me.polygons:
    for k in p.edge_keys:
        pass
from collections import Counter  # noqa: E402
cnt = Counter(k for p in me.polygons for k in p.edge_keys)
check('... the mesh still one closed piece (every edge between two faces), the back untouched (4 points at y = +1)',
      all(v == 2 for v in cnt.values()) and sum(1 for v in me.vertices if abs(v.co.y - 1.0) < 1e-5) == 4)
lz = [zz for zz in mat.mch_zones if zz.kind == 'LINE']
tz = [zz for zz in zmat.mch_zones if zz.kind == 'LINE']
check('... its boundary line on both sides: a line-only zone in the part\'s material and in the zone\'s (one '
      'projector), both in the bump', len(lz) == 1 and len(tz) == 1 and lz[0].projector == tz[0].projector
      and mat.node_tree.nodes['mch:zone_height'].inputs[0].is_linked
      and zmat.node_tree.nodes['mch:zone_height'].inputs[0].is_linked
      and not mat.node_tree.nodes['mch:zone_mask'].inputs[0].is_linked)
lz[0].line_height = 0.6
check('... kept in step (Line Height 0.6 on the part\'s -> the zone\'s too)', abs(tz[0].line_height - 0.6) < 1e-6
      and abs(zmat.node_tree.nodes['mchz:0:lh'].outputs[0].default_value - 0.6) < 1e-6)
check('... the zone\'s material: a Mech copy of the part\'s, its own slot (active - its settings on the Mech page), '
      'painted', ms.is_mech(zmat) and zmat != mat and part.material_slots[1].material == zmat
      and part.active_material_index == 1 and zmat.mch_mech.paint >= 1.0)
zmat.mch_mech.preset = 'GUNMETAL'
check('... any preset on it, the part\'s own material left as it was', zmat.mch_mech.preset == 'GUNMETAL'
      and mat.mch_mech.preset == 'PAINTED')
check('Same Wear as the Part (on for a new Split Zone): its wear the part\'s, even after its own preset',
      zmat.mch_zone_follow and zmat.mch_zone_parent == mat
      and all(getattr(zmat.mch_mech, k) == getattr(mat.mch_mech, k) for k in ('edge_wear', 'dirt', 'rust', 'chip_map')))
mat.mch_mech.edge_wear = 0.55
check('... the part\'s Edge Wear 0.55 -> the zone\'s too', abs(zmat.mch_mech.edge_wear - 0.55) < 1e-6)
zmat.mch_zone_follow = False
mat.mch_mech.dirt = 0.7
zmat.mch_mech.dirt = 0.1
check('... off: its own (the part\'s Dirt 0.7, the zone\'s 0.1)', abs(zmat.mch_mech.dirt - 0.1) < 1e-6
      and abs(mat.mch_mech.dirt - 0.7) < 1e-6)
zmat.mch_zone_follow = True
check('... on again: the part\'s again (Dirt 0.7)', abs(zmat.mch_mech.dirt - 0.7) < 1e-6)
part.active_material_index = 1
its, _h = mu.content(C, 0.0, 276.0, 1.0)
check('... the zone material\'s page: the "Same Wear as the Part" switch',
      any(getattr(i, 'prop', '') == 'mch_zone_follow' for i in its))
its, _h = mu.content(C, 0.0, 276.0, 1.0)
slot_btns = [i for i in its if i.kind == 'tbtn' and i.action[:2] == ('op', 'mch.zone_slot')]
check('... the Mech page lists the part\'s 2 materials (the zone\'s on), a click switches',
      len(slot_btns) == 2 and slot_btns[1].on and not slot_btns[0].on)
bpy.ops.mch.zone_slot(index=0)
check('... (the part\'s own again)', ms.active_mech(C) == mat)
# a lasso over the front-top corner: the faces it covers on the side seen
top = camera((0.0, -6.0, 4.0), (math.radians(55), 0.0, 0.0))
vm2, wm2 = view_of(top)
corner = [to_px(vm2, wm2, c) for c in ((0.6, -1.0, 0.3), (0.95, -1.0, 0.3), (0.95, -0.4, 1.0), (0.6, -0.4, 1.0))]
part.active_material_index = 0
zmat2, n2 = zn.split_zone(C, part, corner, vm2, wm2, True, RW, RH)
f2 = [p for p in me.polygons if p.material_index == 2]
cnt = Counter(k for p in me.polygons for k in p.edge_keys)
check('A lasso over the front-top edge (seen from above): the faces on both the front and the top inside it, the '
      'mesh still closed', n2 >= 2 and any(abs(p.center.y + 1.0) < 1e-4 for p in f2)
      and any(abs(p.center.z - 1.0) < 1e-4 for p in f2) and all(v == 2 for v in cnt.values()),
      (n2, [tuple(round(c, 2) for c in p.center) for p in f2][:6]))
proj_name = lz[0].projector.name
part.active_material_index = 0
idx = next(i for i, zz in enumerate(mat.mch_zones) if zz.projector is not None and zz.projector.name == proj_name)
r = bpy.ops.mch.zone_remove(index=idx)
check('Remove Line: the Split Zone\'s line gone from both materials and its projector (the split itself stays)',
      r == {'FINISHED'} and proj_name not in bpy.data.objects
      and not any(zz.projector is not None and zz.projector.name == proj_name for zz in zmat.mch_zones)
      and part.material_slots[1].material == zmat)


# a material made by an earlier build (user: "근데 페인트 존이 안 먹혀" - its tree had no zone hubs)
def older(m, key, ver):
    m[key] = ver
    for nd in [n for n in m.node_tree.nodes if n.name.startswith('mch:zone_')]:
        m.node_tree.nodes.remove(nd)


square = [to_px(vm, wm, c) for c in ((-0.4, -1.0, -0.4), (0.4, -1.0, -0.4), (0.4, -1.0, 0.4), (-0.4, -1.0, 0.4))]
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
old_part = C.active_object
bpy.ops.mch.mech_shader_apply(preset='STEEL')
om = old_part.active_material
om.mch_mech.edge_wear = 0.37
older(om, 'mch_mech', 8)
oz = zn.add_paint_zone(C, old_part, square, vm, wm, True, RW, RH, color=(0.3, 0.35, 0.1))
hub = om.node_tree.nodes.get('mch:zone_mask')
check('A Mech material made by an earlier build (version 8, no zone hubs): a Paint Zone makes its tree anew - the '
      'zone linked in, its settings kept (Edge Wear 0.37)', om.get('mch_mech') == ms.VERSION and hub is not None
      and hub.inputs[0].is_linked and abs(om.mch_mech.edge_wear - 0.37) < 1e-6 and len(om.mch_zones) == 1)
older(om, 'mch_mech', 8)                    # (a zone already on such a material, saved by the earlier build)
oz.roughness = 0.6
hub = om.node_tree.nodes.get('mch:zone_mask')
check('... a zone already on such a material: any of its sliders makes the tree anew, the zone linked in',
      om.get('mch_mech') == ms.VERSION and hub is not None and hub.inputs[0].is_linked)
from mecha_lab import creature_shader as cs
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
old_body = C.active_object
bpy.ops.mch.creature_apply(skin='HUMAN', condition='CLEAN')
ocm = old_body.active_material
older(ocm, cs.KEY, 2)
zn.add_paint_zone(C, old_body, square, vm, wm, True, RW, RH)
hub = ocm.node_tree.nodes.get('mch:zone_mask')
check('... a Creature material made by an earlier build (version 2): the same, the marking linked in',
      ocm.get(cs.KEY) == cs.VERSION and hub is not None and hub.inputs[0].is_linked)
summary()
