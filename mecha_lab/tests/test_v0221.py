"""0.22.0 Detail Stamp: user presets (origin = bottom) saved in the config folder;
the detail sticks to the surface under the mouse (normal aligned, sunk a little),
a click places it and stamping continues; Right click / Esc stops."""
import math
import os
import sys
import types

from _harness import bpy, check, cube, fresh, summary
import bmesh
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, detail_stamp as ds

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
st = S.mch_detail

check('no presets in a fresh config', ds.preset_names() == [])
check('preset enum shows a hint when empty', ds._preset_items(st, C)[0][0] == 'NONE')

# a detail: a 0.2 x 0.2 x 0.1 box with its origin on the bottom
me = bpy.data.meshes.new('bolt')
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
for v in bm.verts:
    v.co = Vector((v.co.x * 0.2, v.co.y * 0.2, (v.co.z + 0.5) * 0.1))
bm.to_mesh(me)
bm.free()
bolt = bpy.data.objects.new('Bolt', me)
S.collection.objects.link(bolt)
bolt.scale = (2.0, 2.0, 2.0)
C.view_layer.objects.active = bolt
bolt.select_set(True)
st.new_name = 'Hex Bolt'
r = bpy.ops.mch.detail_preset_add()
check('add selected as preset', r == {'FINISHED'} and ds.preset_names() == ['Hex Bolt'], ds.preset_names())
check('preset file in the config folder', os.path.exists(ds.preset_path('Hex Bolt')))
check('preset chosen after adding', st.preset == 'Hex Bolt')
pm = ds.load_mesh('Hex Bolt')
check('preset mesh loads, scale baked, origin kept at the bottom',
      pm is not None and abs(ds.mesh_height(pm) - 0.2) < 1e-4 and abs(min(v.co.z for v in pm.vertices)) < 1e-5,
      ds.mesh_height(pm) if pm else None)
check('loading twice reuses the mesh', ds.load_mesh('Hex Bolt') == pm)
check('bad names are made safe', ds.safe_name('a/b:c*') == 'a_b_c_')

# placement math
m = ds.place_matrix((0, 0, 1), (0, 0, 1), (0, 1, 0), 0.0, 1.0, 0.1, 0.2)
check('place: on top, Z up, sunk 10 % of the height', (m.translation - Vector((0, 0, 0.98))).length < 1e-6
      and (m.to_3x3() @ Vector((0, 0, 1)) - Vector((0, 0, 1))).length < 1e-6)
m = ds.place_matrix((1, 0, 0), (1, 0, 0), (0, 0, 1), math.radians(90), 2.0, 0.0, 0.2)
z = m.to_3x3().normalized() @ Vector((0, 0, 1))
check('place: side wall, Z along the normal, scaled', (z - Vector((1, 0, 0))).length < 1e-6
      and abs(m.to_3x3().col[0].length - 2.0) < 1e-6)
m0 = ds.place_matrix((0, 0, 1), (0, 0, 1), (0, 1, 0), 0.0)
m1 = ds.place_matrix((0, 0, 1), (0, 0, 1), (0, 1, 0), math.radians(45))
check('place: turn around the normal', (m0.to_3x3().col[0] - m1.to_3x3().col[0]).length > 0.5)

# modal stamping on a box (ortho view straight down)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
box = cube('Box', 2.0)
VIEW = cg.OrthoProjector(Quaternion())
ds.make_projector = lambda region, rv3d: VIEW


class Area:
    type = 'VIEW_3D'

    def header_text_set(self, t):
        self.text = t


class Ctx:
    def __init__(self):
        self.area = Area()
        self.region = types.SimpleNamespace(width=1000, height=1000)
        self.region_data = object()
        self.window_manager = types.SimpleNamespace(modal_handler_add=lambda op: None)
        self.window = types.SimpleNamespace(cursor_modal_set=lambda c: None, cursor_modal_restore=lambda: None)

    scene = property(lambda self: bpy.context.scene)
    view_layer = property(lambda self: bpy.context.view_layer)

    def evaluated_depsgraph_get(self):
        return bpy.context.evaluated_depsgraph_get()


def ev(t, value='PRESS', x=500, y=500, ctrl=False, shift=False, alt=False):
    return types.SimpleNamespace(type=t, value=value, mouse_region_x=x, mouse_region_y=y, ctrl=ctrl, shift=shift,
                                 alt=alt)


class Op(ds.StampLogic):
    def __init__(self):
        self.reports = []
        self.preset = ''

    def report(self, kind, msg):
        self.reports.append(msg)


ctx, op = Ctx(), Op()
st.sink = 0.1
r = op.invoke(ctx, ev('MOUSEMOVE'))
prev = bpy.data.objects.get(op.preview_name)
check('stamp starts: preview follows the mouse', r == {'RUNNING_MODAL'} and prev is not None)
op.modal(ctx, ev('MOUSEMOVE', x=550, y=520))
t = prev.matrix_world.translation
check('preview sits on the top face, sunk a little', abs(t.z - (1.0 - 0.1 * 0.2)) < 1e-4
      and abs(t.x - 0.5) < 1e-3 and abs(t.y - 0.2) < 1e-3, tuple(round(x, 4) for x in t))
n0 = len(bpy.data.objects)
op.modal(ctx, ev('LEFTMOUSE', 'PRESS', x=550, y=520))
placed = [o for o in bpy.data.objects if o.name.startswith('Hex Bolt')]
check('click places it right there (no Apply), still stamping', len(placed) == 1 and op.count == 1
      and bpy.data.objects.get(op.preview_name) is not None, [o.name for o in bpy.data.objects])
check('placed detail is its own object in "Mecha Details"', placed and ds.COLL in [c.name for c in
                                                                                  placed[0].users_collection])
op.modal(ctx, ev('WHEELUPMOUSE', ctrl=True))
check('Ctrl+Wheel turns', abs(st.angle - math.radians(15)) < 1e-6)
op.modal(ctx, ev('WHEELUPMOUSE', shift=True))
check('Shift+Wheel sizes', abs(st.scale - 1.1) < 1e-6)
op.modal(ctx, ev('WHEELDOWNMOUSE', alt=True))
check('Alt+Wheel sinks less', abs(st.sink - 0.08) < 1e-6)
check('plain wheel = view zoom (pass through)', op.modal(ctx, ev('WHEELUPMOUSE')) == {'PASS_THROUGH'})
op.modal(ctx, ev('LEFTMOUSE', 'PRESS', x=420, y=430))
check('second click places a second one', op.count == 2)
op.modal(ctx, ev('MOUSEMOVE', x=10, y=10))
check('off the mesh: preview hidden, click does nothing', prev.hide_viewport and op.hit is None)
op.modal(ctx, ev('LEFTMOUSE', 'PRESS', x=10, y=10))
check('no placement in empty space', op.count == 2)
r = op.modal(ctx, ev('RIGHTMOUSE'))
check('right click stops, preview removed', r == {'FINISHED'} and not any(
    o.name.startswith(ds.PREVIEW_NAME) for o in bpy.data.objects))
check('box untouched', len(box.data.vertices) == 8)

# join to surface
st.join = True
st.angle, st.scale = 0.0, 1.0
ctx, op = Ctx(), Op()
op.invoke(ctx, ev('MOUSEMOVE'))
op.modal(ctx, ev('LEFTMOUSE', 'PRESS', x=500, y=500))
op.modal(ctx, ev('ESC'))
check('Join to Surface adds the detail into the box mesh', len(box.data.vertices) == 16, len(box.data.vertices))

# side face hit (view from the front)
VIEW = cg.OrthoProjector(Quaternion((1, 0, 0), math.radians(90)))
ds.make_projector = lambda region, rv3d: VIEW
st.join = False
ctx, op = Ctx(), Op()
op.invoke(ctx, ev('MOUSEMOVE'))
prev = bpy.data.objects.get(op.preview_name)
z = prev.matrix_world.to_3x3().normalized() @ Vector((0, 0, 1))
check('on a side face the detail turns to the face normal', abs(abs(z.y) - 1.0) < 1e-4, tuple(z))
op.modal(ctx, ev('ESC'))

r = bpy.ops.mch.detail_preset_delete('EXEC_DEFAULT')
check('delete preset removes the file', r == {'FINISHED'} and ds.preset_names() == [])
check('panel registered', 'bl_rna' in ds.MCH_PT_detail_stamp.__dict__)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
