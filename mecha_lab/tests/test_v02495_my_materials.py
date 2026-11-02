"""0.24.95 My Materials (user: "기존에 만들어 놓은 재질도 프리셋으로 등록 가능한가? 가능하게 해 줘"):

* any material of the file - here a hand-made node material on no part at all, and a Mech material with a Paint Zone -
  saved whole under a name: a .blend + a ball picture (rendered in a scene of its own) + index.json, in a folder made
  only when saving (here a temp folder, never the user's)
* the Mech material's Zones stay behind (no projector objects in the saved file)
* a ball clicked: a copy on the selected meshes (their active slot); a Mech one has the part's edges measured
* the user's own materials, objects, scenes as they were; Delete removes the files
* the Mech and Creature pages: a My Materials section, a ball each with its picture"""
import math
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import mech_shader as ms, mech_shader_ui as mu, my_materials as mm, zones as zn
from mathutils import Vector

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TMP = tempfile.mkdtemp()
mm.DIR[0] = os.path.join(TMP, 'my_materials')          # (never the user's own folder)


def select(*obs):
    for o in C.selected_objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    C.view_layer.objects.active = obs[0]


def heads(its):
    return {i.label.split('   ')[0]: i for i in its if i.kind == 'shead'}


# a hand-made material (the user's own nodes), on no part
own = bpy.data.materials.new('My Red Enamel')
own.use_nodes = True
bsdf = own.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.7, 0.04, 0.03, 1.0)
bsdf.inputs['Roughness'].default_value = 0.2
noise = own.node_tree.nodes.new('ShaderNodeTexNoise')
own.node_tree.links.new(noise.outputs['Fac'], bsdf.inputs['Coat Weight'])
check('Nothing saved yet: no folder written, no names', not os.path.exists(mm.DIR[0]) and mm.names() == [])
counts = (len(bpy.data.materials), len(bpy.data.objects), len(bpy.data.scenes), len(bpy.data.meshes),
          len(bpy.data.worlds), len(bpy.data.cameras), len([i for i in bpy.data.images if i.type != 'RENDER_RESULT']))
e = mm.save(own, 'Red Enamel')
blend, icon = os.path.join(mm.DIR[0], e['file']), os.path.join(mm.DIR[0], e['icon'])
check('Save a hand-made material that is on no part: its .blend + a ball picture + the index', os.path.isfile(blend)
      and os.path.isfile(icon) and mm.names() == ['Red Enamel'] and e['kind'] == 'other')
img = bpy.data.images.load(icon)
px = np.array(img.pixels[:]).reshape(img.size[1], img.size[0], 4)
mid, corner = px[img.size[1] // 2, img.size[0] // 2], px[2, 2]
bpy.data.images.remove(img)
check('... the ball picture: 128 px, the ball red in the middle, the background clear', tuple(e and (128, 128))
      == (128, 128) and mid[0] > mid[2] * 2.5 and mid[3] > 0.99 and corner[3] < 0.01,
      (np.round(mid, 3).tolist(), round(float(corner[3]), 3)))
now = (len(bpy.data.materials), len(bpy.data.objects), len(bpy.data.scenes), len(bpy.data.meshes),
       len(bpy.data.worlds), len(bpy.data.cameras), len([i for i in bpy.data.images if i.type != 'RENDER_RESULT']))
check('... nothing left behind in this file (no copies, objects, scenes, worlds, cameras, pictures added - only '
      'Blender\'s own Render Result buffer)',
      now == counts and own.name == 'My Red Enamel', (now, counts))

# a Mech material with a Paint Zone on a part
bpy.ops.mesh.primitive_cube_add(size=2.0)
part = C.active_object
bpy.ops.mch.mech_shader_apply(preset='CHIPPED')
mmat = part.active_material
mmat.mch_mech.edge_wear = 0.66
cd = bpy.data.cameras.new('Cam')
cam = bpy.data.objects.new('Cam', cd)
S.collection.objects.link(cam)
cam.location, cam.rotation_euler = (0.0, -6.0, 0.0), (math.radians(90), 0.0, 0.0)
C.view_layer.update()
vm = cam.matrix_world.inverted()
wm = cam.calc_matrix_camera(C.evaluated_depsgraph_get(), x=1000, y=1000)


def px_of(co):
    v = wm @ vm @ Vector((*co, 1.0))
    return ((v.x / v.w * 0.5 + 0.5) * 1000, (v.y / v.w * 0.5 + 0.5) * 1000)


zn.add_paint_zone(C, part, [px_of(c) for c in ((-0.5, -1, -0.5), (0.5, -1, -0.5), (0.5, -1, 0.5), (-0.5, -1, 0.5))],
                  vm, wm, True, 1000, 1000)
e2 = mm.save(mmat, 'Worn Chips')
with bpy.data.libraries.load(os.path.join(mm.DIR[0], e2['file'])) as (src, dst):
    lib_objects, lib_mats = list(src.objects), list(src.materials)
check('Save a Mech material with a Paint Zone: a Mech one (kind mech), its zone left behind (no objects in the file)',
      e2['kind'] == 'mech' and lib_objects == [] and lib_mats == ['Worn Chips'] and len(mmat.mch_zones) == 1)

# put them on
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(4, 0, 0))
other = C.active_object
bpy.ops.mesh.primitive_uv_sphere_add(location=(8, 0, 0))
ball = C.active_object
select(other, ball)
r = bpy.ops.mch.my_material_apply(name='Worn Chips')
got = other.active_material
check('A ball clicked (Worn Chips): a copy on both selected meshes - a Mech material with its settings (Chipped '
      'Paint, Edge Wear 0.66), no zones, the parts\' edges measured', r == {'FINISHED'} and ms.is_mech(got)
      and ball.active_material == got and got.mch_mech.preset == 'CHIPPED' and abs(got.mch_mech.edge_wear - 0.66)
      < 1e-6 and len(got.mch_zones) == 0 and other.data.attributes.get(ms.CURV) is not None
      and not got.use_fake_user and got != mmat)
select(ball)
r = bpy.ops.mch.my_material_apply(name='Red Enamel')
got2 = ball.active_material
b2 = got2.node_tree.nodes['Principled BSDF']
check('... Red Enamel (the hand-made one) on the ball: its own nodes as saved (red, roughness 0.2, the noise into the '
      'coat)', r == {'FINISHED'} and abs(b2.inputs['Base Color'].default_value[0] - 0.7) < 1e-6
      and abs(b2.inputs['Roughness'].default_value - 0.2) < 1e-6 and b2.inputs['Coat Weight'].is_linked
      and got2 != own and other.active_material == got)

# the pages
select(part)
its, _h = mu.content(C, 0.0, 276.0, 1.0)
hd = heads(its)
tiles = [i for i in its if i.kind == 'mtile' and i.action[:2] == ('op', 'mch.my_material_apply')]
check('The Mech page: My Materials (open, 2) - Save Material... / Delete..., a ball each with its picture',
      'MY MATERIALS' in hd and hd['MY MATERIALS'].on and sorted(t.label for t in tiles) == ['Red Enamel', 'Worn Chips']
      and all(t.icon.startswith('file:') and os.path.isfile(t.icon[5:]) for t in tiles)
      and {'Save Material...', 'Delete...'} <= {i.label for i in its if i.kind == 'tbtn'})
select(ball)
its, _h = mu.content(C, 0.0, 276.0, 1.0)
check('... on the Mech page of a part with a non-Mech material too',
      any(i.kind == 'mtile' and i.action[:2] == ('op', 'mch.my_material_apply') for i in its))
its, _h = mu.creature_page(C, 0.0, 276.0, 1.0)
check('... and on the Creature page', any(i.kind == 'mtile' and i.action[:2] == ('op', 'mch.my_material_apply')
                                          for i in its))
e3 = mm.save(own, 'Red Enamel')
check('Saving again under the same name replaces it (one entry, the same file)', mm.names() == ['Red Enamel',
                                                                                              'Worn Chips']
      and e3['file'] == e['file'])
r = bpy.ops.mch.my_material_delete(name='Red Enamel')
check('Delete: its .blend and picture gone, the index without it', r == {'FINISHED'} and mm.names() == ['Worn Chips']
      and not os.path.exists(blend) and not os.path.exists(icon))
summary()
