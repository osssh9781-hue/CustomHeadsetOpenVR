"""0.24.95 Zones turned inside out (user: "이거 스플릿 페인트 반전은 못 해?"):

* a Paint Zone's **Invert**: everything outside the lasso painted instead of inside (the boundary line stays where it
  is; another part sharing the material stays unpainted); a switch - no re-making, the zone's nodes follow
* a Split Zone's **Invert (inside / outside)**: the faces that had the zone's material get the part's and the other
  way round (the cut and the boundary line stay); again: back as it was
* the Mech page: the Invert switch on a Paint Zone, the Invert button on a Split Zone's boundary-line row"""
import math
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import mech_shader_ui as mu, zones as zn

fresh()
mecha_lab.register()
C = bpy.context
sc = C.scene
RW = RH = 1000
PX = 160

bpy.ops.mesh.primitive_cube_add(size=2.0)
part = C.active_object
bpy.ops.mch.mech_shader_apply(preset='PAINTED')
mat = part.active_material
st = mat.mch_mech
st.edge_wear = st.scratches = st.dirt = st.rust = st.dust = 0.0
st.paint_color = (0.6, 0.6, 0.6)
bpy.ops.mesh.primitive_cube_add(size=0.8, location=(2.0, -0.6, 0.0))      # (another part, the same material)
other = C.active_object
other.data.materials.append(mat)
cd = bpy.data.cameras.new('Cam')
cam = bpy.data.objects.new('Cam', cd)
sc.collection.objects.link(cam)
cam.location, cam.rotation_euler = (0.9, -7.0, 0.0), (math.radians(90), 0.0, 0.0)
sc.camera = cam
C.view_layer.update()
vm = cam.matrix_world.inverted()
wm = cam.calc_matrix_camera(C.evaluated_depsgraph_get(), x=RW, y=RH)


def to_px(co):
    v = wm @ vm @ Vector((*co, 1.0))
    return ((v.x / v.w * 0.5 + 0.5) * RW, (v.y / v.w * 0.5 + 0.5) * RH)


for o in C.selected_objects:
    o.select_set(False)
part.select_set(True)
C.view_layer.objects.active = part
lasso = [to_px(c) for c in ((-0.6, -1, -0.5), (0.4, -1, -0.5), (0.4, -1, 0.5), (-0.6, -1, 0.5))]
z = zn.add_paint_zone(C, part, lasso, vm, wm, True, RW, RH, color=(0.9, 0.6, 0.02))
z.line_height = 0.0
w = bpy.data.worlds.new('W')
w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.7, 0.7, 0.7, 1.0)
sc.world = w
sc.render.engine = 'CYCLES'
sc.cycles.samples = 16
sc.cycles.use_denoising = False
sc.render.resolution_x = sc.render.resolution_y = PX
sc.view_settings.view_transform = 'Standard'


def render():
    p = os.path.join(tempfile.mkdtemp(), 'r.png')
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(p)
    a = np.array(img.pixels[:]).reshape(PX, PX, 4)[..., :3]
    bpy.data.images.remove(img)
    return a


def at(a, co):
    x, y = to_px(co)
    return a[int(y * PX / RH), int(x * PX / RW)]


def orange(c):
    return c[0] > c[2] * 2.5


IN, OUT, OTHER = (-0.1, -1, 0.0), (0.8, -1, 0.0), (2.0, -1.0, 0.0)
plain = render()
check('A Paint Zone: inside the lasso orange, outside it and the other part not',
      orange(at(plain, IN)) and not orange(at(plain, OUT)) and not orange(at(plain, OTHER)),
      [list(np.round(at(plain, c), 2)) for c in (IN, OUT, OTHER)])
nodes_before = len(mat.node_tree.nodes)
z.invert = True
check('... Invert: a switch (the zone\'s nodes follow, nothing made anew)',
      mat.node_tree.nodes['mchz:0:inv'].outputs[0].default_value == 1.0 and len(mat.node_tree.nodes) == nodes_before)
inv = render()
check('... rendered: outside the lasso orange, inside not; the other part sharing the material still not painted',
      not orange(at(inv, IN)) and orange(at(inv, OUT)) and not orange(at(inv, OTHER)),
      [list(np.round(at(inv, c), 2)) for c in (IN, OUT, OTHER)])
z.invert = False
check('... off again: as at first', orange(at(render(), IN)))
its, _h = mu.content(C, 0.0, 276.0, 1.0)
check('... the Mech page: the zone\'s Invert switch', any(getattr(i, 'prop', '') == 'invert' for i in its))

# a Split Zone
z.invert = False
zn.remove_zone(mat, 0)
zmat, n_in = zn.split_zone(C, part, lasso, vm, wm, True, RW, RH)
me = part.data
zi = list(me.materials).index(zmat)
pi = list(me.materials).index(mat)


def counts():
    idx = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get('material_index', idx)
    return int((idx == zi).sum()), int((idx == pi).sum()), idx.copy()


nz, np_, before = counts()
part.active_material_index = pi
its, _h = mu.content(C, 0.0, 276.0, 1.0)
btn = next((i for i in its if i.kind == 'tbtn' and i.label.startswith('Invert (inside')), None)
check('A Split Zone: the Invert button on its boundary-line row (the part\'s material shown)',
      btn is not None and btn.action[:2] == ('op', 'mch.zone_split_invert') and btn.action[2]['material'] == zmat.name,
      btn and btn.action)
r = bpy.ops.mch.zone_split_invert(material=zmat.name)
nz2, np2, after = counts()
check('... Invert: the faces swap - the zone\'s faces the part\'s, the part\'s the zone\'s (none lost)',
      r == {'FINISHED'} and nz2 == np_ and np2 == nz and nz > 0 and np_ > 0
      and np.all((before == zi) == (after == pi)), (nz, np_, nz2, np2))
check('... the cut and the boundary line stay (the same faces, both line zones)',
      len(me.polygons) == len(before) and all(any(q.kind == 'LINE' for q in zn.zones_of(m)) for m in (mat, zmat)))
bpy.ops.mch.zone_split_invert(material=zmat.name)
check('... again: back as it was', np.array_equal(counts()[2], before))
summary()
