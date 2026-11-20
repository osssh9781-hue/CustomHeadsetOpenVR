"""0.24.266 (user: "지정해 놓은 HDRI 를 카메라 쪽에 고정, 렌더 탭에서 돌리면서 렌더 - 각도 슬라이더, 원점으로", "라이팅을 픽하면 그것도
같이 돌아가면"): HDRI Rotation / Follow Camera / Back to Start / Turn Selected Lights Too on the Render page."""
import math
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import hdri_turn as ht, side_panel as sp  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
for o in list(S.objects):
    bpy.data.objects.remove(o)
# an HDRI the user's own add-on could have made: a dark sky with one bright spot, Mapping -> Environment
W, H = 128, 64
img = bpy.data.images.new('spot', W, H, float_buffer=True)
px = np.full((H, W, 4), 0.02, np.float32); px[..., 3] = 1
px[28:36, 30:34, :3] = 400.0
img.pixels.foreach_set(px.ravel())
w = bpy.data.worlds.new('UserHDRI'); S.world = w; w.use_nodes = True
nt = w.node_tree; nt.nodes.clear()
tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping'); mp.name = 'their map'
env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = img
bg = nt.nodes.new('ShaderNodeBackground'); out = nt.nodes.new('ShaderNodeOutputWorld')
nt.links.new(tc.outputs['Generated'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], env.inputs['Vector'])
nt.links.new(env.outputs['Color'], bg.inputs['Color']); nt.links.new(bg.outputs['Background'], out.inputs['Surface'])

bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24); ball = C.active_object
bpy.ops.object.shade_smooth()
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); S.collection.objects.link(cam)
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 2.4; cam.location = (0, 0, 10); S.camera = cam

S.mch_hdri_turn.turn = math.radians(90)
check('the slider puts our Mapping in front of their HDRI (theirs kept, linked through ours)',
      len(ht.turn_nodes(S)) == 1 and env.inputs['Vector'].links[0].from_node.name == ht.NODE
      and ht.turn_nodes(S)[0].inputs['Vector'].links[0].from_node == mp)
dg = C.evaluated_depsgraph_get(); dg.update()


def lit_angle():
    S.render.engine = 'CYCLES'; S.cycles.samples = 8; S.cycles.device = 'CPU'
    S.render.resolution_x = S.render.resolution_y = 48; S.render.resolution_percentage = 100
    S.render.film_transparent = True
    f = os.path.join(tempfile.gettempdir(), 'mch_turn.png'); S.render.filepath = f
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(f); a = np.array(im.pixels[:]).reshape(48, 48, 4); bpy.data.images.remove(im)
    lum = a[..., :3].sum(-1) * a[..., 3]
    ys, xs = np.mgrid[0:48, 0:48]
    wgt = lum ** 4
    cx, cy = (wgt * xs).sum() / wgt.sum() - 23.5, (wgt * ys).sum() / wgt.sum() - 23.5
    return math.degrees(math.atan2(cy, cx))


S.mch_hdri_turn.turn = 0.0
check('back to 0 and nothing else on: our node out, their link back', not ht.turn_nodes(S)
      and env.inputs['Vector'].links[0].from_node == mp)
a0 = lit_angle()
S.mch_hdri_turn.turn = math.radians(90)
a1 = lit_angle()
d = (a1 - a0 + 180) % 360 - 180
check(f'HDRI Rotation 90: the light on the ball turns +90 (rendered: {d:.0f})', abs(d - 90) < 20)
bpy.ops.mch.hdri_turn_reset()
check('Back to Start: 0', S.mch_hdri_turn.turn == 0.0)

# Follow Camera: the camera turns 90 about Z (round the model) -> the HDRI turns with it
S.mch_hdri_turn.follow = True
lamp = bpy.data.objects.new('Key', bpy.data.lights.new('Key', 'AREA')); S.collection.objects.link(lamp)
lamp.location = (3, 0, 2)
for o in list(C.selected_objects):
    o.select_set(False)
lamp.select_set(True); C.view_layer.objects.active = lamp
bpy.ops.mch.hdri_turn_lights()
C.view_layer.update()
check('Turn Selected Lights Too: the light hangs on the turning pivot, where it was',
      ht.lights(S) == [lamp] and (lamp.matrix_world.translation - __import__('mathutils').Vector((3, 0, 2))).length < 1e-4)
cam.rotation_euler = (0, 0, math.radians(90)); C.view_layer.update()
dg = C.evaluated_depsgraph_get(); dg.update()
lw = lamp.evaluated_get(dg).matrix_world.translation
check(f'Follow Camera: the camera turns 90 -> the light turns 90 too ({tuple(round(v, 2) for v in lw)})',
      abs(lw.x) < 1e-3 and abs(lw.y - 3) < 1e-3)
ang = ht.turn_nodes(S)[0].inputs['Rotation'].default_value[2]
check('... and the HDRI driver follows the camera', 'cam' in [v.name for v in
      S.world.node_tree.animation_data.drivers[0].driver.variables])
bpy.ops.mch.hdri_turn_lights(release=True)
C.view_layer.update()
check('Release Lights: stays where it is, no pivot left', lamp.parent is None and bpy.data.objects.get(ht.PIVOT) is None
      and abs(lamp.matrix_world.translation.y - 3) < 1e-3)
# the world rebuilt (another HDRI picked in the user's add-on): our node comes back
nt.links.new(mp.outputs['Vector'], env.inputs['Vector'])
for n in ht.turn_nodes(S):
    nt.nodes.remove(n)
ht._check(S)
ht.ensure(S)
check('another HDRI picked: turned again', len(ht.turn_nodes(S)) >= 1)
S.mch_hdri_turn.follow = False
C.window_manager.mch_side_page = 'HDRI'
sp.OPENED.discard('MATERIAL:r_hdri_turn')
items, _h = sp.content(C, 'CUT', 0, 300, 1.0)
L = [getattr(i, 'label', '') for i in items]
check('the Render page: Follow Camera, HDRI Rotation, Back to Start, Turn Selected Lights Too',
      all(x in L for x in ('Follow Camera', 'HDRI Rotation', 'Back to Start', 'Turn Selected Lights Too')))
summary()
