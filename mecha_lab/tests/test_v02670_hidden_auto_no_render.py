"""0.24.270 (user: "눈 꺼 놓은 거는 렌더할 때 끌 수 있게 해 달라고 했는데 왜 계속 켜져 있어" - a hair with its eye off but
its camera on rendered): Auto (on by default) - turning an eye off turns the camera off too, the eye on again turns it
back; a folder's eye too; a camera turned on again by hand while the eye stays off is left on; a hidden part another
part's modifier reads (a radial / boolean source) still works in the render; counted in the real render."""
import math

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import render_hidden as rh  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
for o in list(S.objects):
    bpy.data.objects.remove(o)


def tick():
    C.view_layer.update()
    rh._on_update(S, C.evaluated_depsgraph_get())


bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0)); a = C.active_object; a.name = 'A'
bpy.ops.mesh.primitive_cube_add(location=(3, 0, 0)); hair_like = C.active_object; hair_like.name = 'HairLike'
bpy.ops.mesh.primitive_uv_sphere_add(location=(-3, 0, 0)); src = C.active_object; src.name = 'Source'
tick()
check('Auto is on by default', S.mch_hidden_auto is True)
hair_like.hide_set(True); tick()
check('eye off -> camera off at once', hair_like.hide_render and hair_like.get(rh.MARK))
hair_like.hide_set(False); tick()
check('eye on again -> camera back on', not hair_like.hide_render and not hair_like.get(rh.MARK))
# a folder's eye
col = bpy.data.collections.new('Folder'); S.collection.children.link(col)
col.objects.link(a); S.collection.objects.unlink(a)
lc = C.view_layer.layer_collection.children['Folder']
lc.hide_viewport = True; tick()
check("a folder's eye off -> its parts' cameras off", a.hide_render)
lc.hide_viewport = False; tick()
check('... on again -> back', not a.hide_render)
# your own choice while the eye stays off is kept
hair_like.hide_set(True); tick()
hair_like.hide_render = False; tick()
check('a camera turned on by hand while the eye stays off: left on', not hair_like.hide_render)
hair_like.hide_set(False); tick()
# an object you turned out of renders yourself (camera off, eye on): showing / hiding the eye leaves it off
a.hide_render = True; tick()
a.hide_set(True); tick(); a.hide_set(False); tick()
check('a camera you turned off yourself stays off after eye off / on', a.hide_render)
a.hide_render = False
# a hidden source read by another part's modifier still works in the render
bpy.ops.mesh.primitive_plane_add(location=(0, 4, 0)); carrier = C.active_object; carrier.name = 'Carrier'
ng = bpy.data.node_groups.new('read', 'GeometryNodeTree')
ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
gi, go = ng.nodes.new('NodeGroupInput'), ng.nodes.new('NodeGroupOutput')
oi = ng.nodes.new('GeometryNodeObjectInfo'); oi.inputs['Object'].default_value = src
ng.links.new(oi.outputs['Geometry'], go.inputs[0])
carrier.modifiers.new('read', 'NODES').node_group = ng
src.hide_set(True); tick()
check('the source hidden: its camera off', src.hide_render)
COUNT = {}


def grab(scene, d=None):
    if d is not None and d.mode == 'RENDER':
        names = {i.object.name for i in d.object_instances}
        COUNT['names'] = names
        COUNT['carrier'] = len(scene.objects['Carrier'].evaluated_get(d).data.vertices)


bpy.app.handlers.frame_change_post.append(grab)
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); S.collection.objects.link(cam)
cam.location = (0, -12, 0); cam.rotation_euler = (math.pi / 2, 0, 0); S.camera = cam
hair_like.hide_set(True); tick()
S.render.engine = 'CYCLES'; S.cycles.samples = 1; S.cycles.device = 'CPU'
S.render.resolution_x = S.render.resolution_y = 16
bpy.ops.render.render()
check(f'F12 render: the hidden parts left out ({sorted(COUNT.get("names", []))})',
      'HairLike' not in COUNT.get('names', ()) and 'Source' not in COUNT.get('names', ()) and 'A' in COUNT.get('names', ()))
check(f'... the part reading the hidden source still gets it in the render ({COUNT.get("carrier")} points = the sphere)',
      COUNT.get('carrier') == len(src.data.vertices))
# Auto off: the ones it turned off back on, and hiding no longer touches the camera
S.mch_hidden_auto = False
check('Auto off: what it turned off is back in renders', not hair_like.hide_render and not src.hide_render)
hair_like.hide_set(False); tick(); hair_like.hide_set(True); tick()
check('... and an eye off no longer turns the camera off', not hair_like.hide_render)
S.mch_hidden_auto = True
check('Auto on again: the parts hidden now go out of renders', hair_like.hide_render and src.hide_render)
cells = rh.toolbar_cells(C)
check('the Layers window row: Auto, No Render, Render Again', len(cells) == 3 and cells[0][1][1] == 'mch.hidden_auto')
summary()
