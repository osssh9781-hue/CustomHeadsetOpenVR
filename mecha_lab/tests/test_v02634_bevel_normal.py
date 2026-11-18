"""0.24.234 (user: "토글 버튼으로 전체 메쉬에 베벨 노말 두께 내가 정한 걸로 … 중앙 메뉴에, 두께는 슬라이더로" / "선택한 거
베벨 노말 지우는 것도"): Bevel Normal on every mesh (Cycles' Bevel node in front of each material's shader Normal, its
Radius = the slider x the object's own switch), off for the selected only, made-later meshes get it, off takes it all
out again - the links back as they were; the meshes themselves never change; the dock has the toggle, the slider and
Remove Selected.  A real Cycles render: the rounded edges show (the edge's pixels change), the faces do not."""
import os

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bevel_normal as bn, mesh_io as mio  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
for o in list(S.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
a = C.active_object
m1 = bpy.data.materials.new('Paint'); m1.use_nodes = True
nt = m1.node_tree
bump = nt.nodes.new('ShaderNodeBump')
bsdf = nt.nodes['Principled BSDF']
nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
a.data.materials.append(m1)
bpy.ops.mesh.primitive_cube_add(location=(3, 0, 0))
b = C.active_object
b.data.materials.append(m1)                               # (the same material as a)
bpy.ops.mesh.primitive_cube_add(location=(6, 0, 0))
c = C.active_object                                       # (no material)
co0 = {o.name: mio.read_co(o.data).copy() for o in (a, b, c)}
S.mch_bevel_normal_radius = 0.1
S.mch_bevel_normal = True
bev = nt.nodes.get(bn.NODE)
check('on: the material got the Bevel Normal in front of its shader, the bump kept under it',
      bev is not None and bsdf.inputs['Normal'].links[0].from_node == bev
      and bev.inputs['Normal'].links[0].from_node == bump)
check('... Radius = the slider x the object\'s switch (an Object attribute), every mesh switched on',
      abs(nt.nodes[bn.VALUE].outputs[0].default_value - 0.1) < 1e-6
      and nt.nodes[bn.SWITCH].attribute_type == 'OBJECT' and all(o.get(bn.PROP) == 1.0 for o in (a, b, c)))
check('a mesh with no material: the plain base material (marked as ours)',
      c.data.materials and c.data.materials[0].name == bn.BASE_MAT and c.get(bn.ADDED)
      and c.data.materials[0].node_tree.nodes.get(bn.NODE) is not None)
S.mch_bevel_normal_radius = 0.03
check('the slider changes the radius at once', abs(nt.nodes[bn.VALUE].outputs[0].default_value - 0.03) < 1e-6)
for o in S.objects:
    o.select_set(o is b)
C.view_layer.objects.active = b
bpy.ops.mch.bevel_normal_remove()
check('Remove Selected: only b is off (its switch 0), a with the same material keeps it',
      b[bn.PROP] == 0.0 and a[bn.PROP] == 1.0 and nt.nodes.get(bn.NODE) is not None)
bpy.ops.mesh.primitive_cylinder_add(location=(9, 0, 0))
d = C.active_object
C.view_layer.update()
bn._new_meshes(S, C.evaluated_depsgraph_get())
check('a mesh made later gets it too; b stays off', d.get(bn.PROP) == 1.0 and b[bn.PROP] == 0.0
      and d.data.materials and d.data.materials[0].node_tree.nodes.get(bn.NODE) is not None)
check('the meshes are never changed', all(np.allclose(mio.read_co(o.data), co0[o.name]) for o in (a, b, c)))

# a real Cycles render: the edge rounded where it is on, not on b
S.render.engine = 'CYCLES'
S.cycles.samples = 16
S.cycles.device = 'CPU'
S.render.resolution_x, S.render.resolution_y = 160, 120
S.render.film_transparent = True
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); S.collection.objects.link(cam); S.camera = cam
from mathutils import Vector  # noqa: E402
cam.location = (1.5, -4.0, 2.2)
cam.rotation_euler = (Vector((1.5, 0, 0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN')); S.collection.objects.link(sun)
sun.rotation_euler = (0.7, 0.2, 0.5)
for o in (c, d):
    o.hide_render = True
S.mch_bevel_normal_radius = 0.15


def render():
    S.render.filepath = os.path.join(bpy.app.tempdir or '.', 'mch_bn.png')
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(S.render.filepath, check_existing=False)
    px = np.array(im.pixels[:]).reshape(im.size[1], im.size[0], 4)[:, :, :3].copy()
    bpy.data.images.remove(im)
    return px


on_a_b = render()
b[bn.PROP] = 1.0
b.update_tag()
both = render()
diff = np.abs(both - on_a_b).mean(axis=2)
half = on_a_b.shape[1] // 2
right = diff[:, half:]
check(f'a real Cycles render: switching b on changes only b\'s side of the picture (b: {right.max():.3f}, a: '
      f'{diff[:, :half - 10].max():.3f})', right.max() > 0.05 and diff[:, :half - 10].max() < 0.02)
S.mch_bevel_normal = False
check('off: every node out, the bump linked to the shader again, the base material gone, the switches gone',
      nt.nodes.get(bn.NODE) is None and nt.nodes.get(bn.VALUE) is None
      and bsdf.inputs['Normal'].links[0].from_node == bump and not c.data.materials
      and bpy.data.materials.get(bn.BASE_MAT) is None and all(bn.PROP not in o for o in (a, b, c, d)))
from mecha_lab import ui_bars as ub  # noqa: E402
import inspect  # noqa: E402
src = inspect.getsource(ub.dock_items)
check('the dock (the bar with Select) has BEVEL: the toggle, the Radius slider, Remove Selected',
      "'BEVEL'" in src and 'mch_bevel_normal_radius' in src and 'mch.bevel_normal_remove' in src)
summary()
