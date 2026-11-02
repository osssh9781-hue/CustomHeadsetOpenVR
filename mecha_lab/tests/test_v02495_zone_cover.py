"""0.24.95 Paint Zones cover the material's own texture (user: "기존에 있던 텍스처가 안 사라져" - a yellow zone on carbon fibre
still showed the weave):

* inside a Paint Zone the Mech Shader's own texture - the Base map's pattern in the paint, the base / weave relief, the
  roughness map - is covered (a hub ``mch:zone_hide``, 1 where covered); the zone's **Base Texture** slider lets it
  through (0 covered .. 1 as before)
* rendered (Carbon Fibre, a yellow zone): inside the zone even (the weave gone); Base Texture 1 - the weave back;
  outside the zone the carbon as it was
* the Mech page: the zone's Base Texture row; a Mech material made before: made anew (version 14)
* (user: "셀렉트 모드로 했는데 다른 영역도 칠해져") another part sharing the material, inside the lasso: not painted
* (user: "뒤로 갔다 앞으로 다시 가면 생겨") a part numbered the first time is told it changed (the 3D view reads it)"""
import math
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import mech_shader as ms, mech_shader_ui as mu, zones as zn

fresh()
mecha_lab.register()
C = bpy.context
sc = C.scene
RW = RH = 1000
PX = 200

bpy.ops.mesh.primitive_cube_add(size=2.0)
part = C.active_object
bpy.ops.mch.mech_shader_apply(preset='CARBON')
mat = part.active_material
st = mat.mch_mech
st.edge_wear = st.scratches = st.dirt = st.rust = st.dust = 0.0
cd = bpy.data.cameras.new('Cam')
cam = bpy.data.objects.new('Cam', cd)
sc.collection.objects.link(cam)
cam.location, cam.rotation_euler = (0.0, -4.0, 0.0), (math.radians(90), 0.0, 0.0)
sc.camera = cam
C.view_layer.update()
vm = cam.matrix_world.inverted()
wm = cam.calc_matrix_camera(C.evaluated_depsgraph_get(), x=RW, y=RH)


def to_px(co):
    v = wm @ vm @ Vector((*co, 1.0))
    return ((v.x / v.w * 0.5 + 0.5) * RW, (v.y / v.w * 0.5 + 0.5) * RH)


z = zn.add_paint_zone(C, part, [to_px(c) for c in ((0.0, -1, -0.7), (0.8, -1, -0.7), (0.8, -1, 0.7), (0.0, -1, 0.7))],
                      vm, wm, True, RW, RH, color=(0.8, 0.55, 0.05))
z.line_height = 0.0
nt = mat.node_tree
check('A Paint Zone on a Mech material: its cover linked into the hub that hides the material\'s texture under the '
      'paint; Base Texture 0 (covered) to start', ms.VERSION >= 14 and nt.nodes['mch:zone_hide'].inputs[0].is_linked
      and z.base_through == 0.0 and nt.nodes.get('mchz:0:bthru') is not None)
w = bpy.data.worlds.new('W')
w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.7, 0.7, 0.7, 1.0)
sc.world = w
sun_d = bpy.data.lights.new('Sun', 'SUN')
sun_d.energy = 3.0
sun = bpy.data.objects.new('Sun', sun_d)
sc.collection.objects.link(sun)
sun.rotation_euler = (math.radians(60), 0.0, math.radians(20))
sc.render.engine = 'CYCLES'
sc.cycles.samples = 32
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


def patch(a, co, r=10):
    x, y = to_px(co)
    x, y = int(x * PX / RW), int(y * PX / RH)
    return a[y - r:y + r, x - r:x + r].mean(axis=2)


covered = render()
z.base_through = 1.0
through = render()
z.base_through = 0.0
inside_c, inside_t = patch(covered, (0.4, -1, 0.0)), patch(through, (0.4, -1, 0.0))
out_c, out_t = patch(covered, (-0.5, -1, 0.0)), patch(through, (-0.5, -1, 0.0))
check('Rendered (Carbon Fibre, a yellow zone): inside the zone even - the weave covered; Base Texture 1 - the weave '
      'back (much less even); outside the zone the carbon the same both times',
      inside_c.std() < inside_t.std() * 0.5 and abs(out_c.std() - out_t.std()) < 0.02 and out_c.std() > inside_c.std(),
      [round(float(v), 4) for v in (inside_c.std(), inside_t.std(), out_c.std(), out_t.std())])
check('... the zone still its yellow (red / green over blue)', covered[PX // 2, int(to_px((0.4, -1, 0))[0] * PX / RW)][0]
      > covered[PX // 2, int(to_px((0.4, -1, 0))[0] * PX / RW)][2] * 2)
# another part sharing the material, right beside the zone's, inside the same lasso (user: "셀렉트 모드로 했는데 다른 영역도
# 칠해져")
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(1.6, -0.5, 0.0))
other = C.active_object
other.data.materials.append(mat)
cd3 = bpy.data.cameras.new('Wide')
cam3 = bpy.data.objects.new('Wide', cd3)
sc.collection.objects.link(cam3)
cam3.location, cam3.rotation_euler = (0.8, -8.0, 0.0), (math.radians(90), 0.0, 0.0)
C.view_layer.update()
vm3 = cam3.matrix_world.inverted()
wm3 = cam3.calc_matrix_camera(C.evaluated_depsgraph_get(), x=RW, y=RH)


def px3(co):
    v = wm3 @ vm3 @ Vector((*co, 1.0))
    return ((v.x / v.w * 0.5 + 0.5) * RW, (v.y / v.w * 0.5 + 0.5) * RH)


lasso_wide = [px3(c) for c in ((0.2, -1, -0.4), (2.3, -1, -0.4), (2.3, -1, 0.4), (0.2, -1, 0.4))]
for o in C.selected_objects:
    o.select_set(False)
part.select_set(True)
C.view_layer.objects.active = part
z2 = zn.add_paint_zone(C, part, lasso_wide, vm3, wm3, True, RW, RH, color=(0.05, 0.2, 0.8))
z2.line_height = 0.0
sc.camera = cam3
img = render()
sc.camera = cam


def at3(co):
    x, y = px3(co)
    return img[int(y * PX / RH), int(x * PX / RW)]


col_part, col_other = at3((0.6, -1.0, 0.0)), at3((1.6, -1.0, 0.0))
check('Another part sharing the material, inside the same lasso: the zone paints its own part only (each part a number '
      '- the zone\'s nodes check it)', col_part[2] > col_part[0] * 2 and not col_other[2] > col_other[0] * 1.5
      and int(part.get(zn.ZONE_ID, 0)) > 0 and int(other.get(zn.ZONE_ID, 0) or 0) != int(part[zn.ZONE_ID]),
      (np.round(col_part, 3).tolist(), np.round(col_other, 3).tolist()))
# (user: "또 안 돼 - 뒤로 갔다 앞으로 다시 가면 생겨": the part's number, set the first time a zone goes on it, did not
#  reach the 3D view's copy of the part - nothing painted until an undo / redo)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 3.0, 0.0))
fresh_part = C.active_object
fresh_part.data.materials.append(mat)
C.view_layer.update()
seen = []


def _seen(scene, dg):
    seen.extend(u.id.name for u in dg.updates if isinstance(u.id, bpy.types.Object) and u.is_updated_transform)


bpy.app.handlers.depsgraph_update_post.append(_seen)
pid = zn.part_id(fresh_part)
C.view_layer.update()
bpy.app.handlers.depsgraph_update_post.remove(_seen)
check('A part numbered the first time (its zones\' nodes check the number): the part told it changed, so the 3D view '
      'reads the number at once (it showed only after an undo / redo)', pid > 0 and fresh_part.name in seen, seen)
zn.remove_zone(mat, len(mat.mch_zones) - 1)
for o in C.selected_objects:
    o.select_set(False)
part.select_set(True)
C.view_layer.objects.active = part
its, _h = mu.content(C, 0.0, 276.0, 1.0)
check('The Mech page: the zone\'s Base Texture row', any(getattr(i, 'prop', '') == 'base_through' for i in its))
mat['mch_mech'] = 13
nt.nodes.remove(nt.nodes['mch:zone_hide'])
z.roughness = 0.5
check('A Mech material made before (no hub): made anew on the next change, the zone linked into it again',
      mat.get('mch_mech') == ms.VERSION and mat.node_tree.nodes['mch:zone_hide'].inputs[0].is_linked)
summary()
