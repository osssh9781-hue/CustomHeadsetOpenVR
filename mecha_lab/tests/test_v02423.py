"""0.24.23 Alt engraving: Creature Plate Alt + draw with no live plate under it (and Alt+Enter on a Creature Plate
sketch) takes the plate shape out of the mesh, only as deep as the plate would be thick; Creature Base Mesh Alt
does the same with its lump (regular Base Mesh still cuts through).  [ / ] Line Width in Object Mode (before
Blender's select parent / child), G in Sculpt Mode = back to Select / Move."""
import math

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import base_mesh as bm_mod, core_geometry as cg, creature_plate as cpl, lasso_sketch as ls
from mecha_lab import live_subtract as lsub, tool_state as ts

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOPP = cg.OrthoProjector(Quaternion())


def body():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=3, segments=64, ring_count=32, location=(0, 0, -2.6))
    return C.active_object


def top_z(ob, xy):
    o, d = TOPP.ray(xy)
    hit, loc, _n, _i, hob, _m = C.scene.ray_cast(C.evaluated_depsgraph_get(), Vector(o), Vector(d))
    return (loc.z if hit else None), (hob.name if hit else None)


def volume(ob):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    v = bm.calc_volume()
    bm.free()
    return v


SQ = [[(450, 450), (550, 450), (550, 550), (450, 550)]]

# Creature Plate Alt over a plain mesh = engrave
ob = body()
z0, _ = top_z(ob, (500, 500))
zout, _ = top_z(ob, (300, 500))
v0 = volume(ob)
S.mch_cplate.peak = 0.0
n_obj = len(bpy.data.objects)
msg = lsub.perform(C, 'CPLATE', SQ, TOPP)
z1, name = top_z(ob, (500, 500))
check('Creature Plate Alt with no live plate: engraves into the mesh (no error)', 'Engraved' in msg, msg)
check('no new object is made', len(bpy.data.objects) == n_obj)
check('the middle sits lower than before (a pocket)', name == ob.name and z1 < z0 - 1e-4, (z0, z1))
check('only as deep as the plate is thick (not through the mesh)', z1 > -2.6, z1)
check('outside the outline the surface is untouched', abs(top_z(ob, (300, 500))[0] - zout) < 1e-6)
check('volume went down a little', 0 < v0 - volume(ob) < v0 * 0.2, (v0, volume(ob)))
check('the mesh stays closed', non_manifold(ob) == 0, non_manifold(ob))
deep_auto = z0 - z1
ob = body()
S.mch_cplate.peak = 0.4
S.mch_cplate.edge_thickness = 0.0
lsub.perform(C, 'CPLATE', SQ, TOPP)
z2, _ = top_z(ob, (500, 500))
check('Height sets the depth (deeper with a bigger Height)', z0 - z2 > 0.3 and z0 - z2 < 0.5, z0 - z2)
S.mch_cplate.peak = 0.0

# over a live plate it still cuts that plate (0.24.21)
ob = body()
cpl.perform(C, [[(300, 300), (700, 300), (700, 700), (300, 700)]], TOPP)
plate = C.active_object
v_body = volume(ob)
lsub.perform(C, 'CPLATE', SQ, TOPP)
check('over a live Creature Plate: the hole goes into the plate, the body is untouched',
      len(lsub.records(plate)) == 1 and abs(volume(ob) - v_body) < 1e-9)

# Alt+Enter on a Creature Plate sketch
ob = body()
ls.clear(S)
ls.add(C, 'CPLATE', SQ, TOPP)
v0 = volume(ob)
msg = ls.commit(C, alt=True)
check('Creature Plate sketch Alt+Enter: engraves (nothing new made)', 'Engraved' in msg and volume(ob) < v0
      and len(bpy.data.objects) == 1, msg)
check('the sketch is cleared after', ls.data(S) is None)
ls.add(C, 'CPLATE', SQ, TOPP)
msg = ls.commit(C, alt=False)
check('Enter (no Alt) still makes a Creature Plate', len(bpy.data.objects) == 2 and 'Creature plate' in msg, msg)

# Creature Base Mesh Alt = engrave as deep as the lump
ob = body()
ts_tool = S.mch_settings.mch_active_tool
S.mch_settings.mch_active_tool = 'CBASE'
check('Creature Base Mesh tool picks its own settings', bm_mod.scene_defaults(C) == S.mch_cbase)
S.mch_cbase.profile = 'PUFF'
v0 = volume(ob)
z0, _ = top_z(ob, (500, 500))
for o in C.selected_objects:
    o.select_set(False)
msg = bm_mod.perform_base(C, SQ, TOPP, cutter=True)
z1, _ = top_z(ob, (500, 500))
check('Creature Base Mesh Alt: engraves into the mesh (Puff is allowed now)', 'Engraved' in msg and v0 > volume(ob), msg)
check('a pocket, not a hole through', z0 - 1.0 < z1 < z0 - 1e-4, (z0, z1))
check('the mesh stays closed', non_manifold(ob) == 0)
check('no new object', len(bpy.data.objects) == 1)
ob = body()
v0 = volume(ob)
S.mch_cbase.sketch = True
bm_mod.sketch_add(C, SQ, TOPP)
msg = bm_mod.sketch_commit(C, cutter=True)
check('Creature Base Mesh sketch Alt+Enter: engraves too', 'Engraved' in msg and volume(ob) < v0
      and len(bpy.data.objects) == 1, msg)
S.mch_cbase.sketch = False
S.mch_settings.mch_active_tool = 'BASE'
check('regular Base Mesh Alt still cuts through (unchanged)', bm_mod.scene_defaults(C) == S.mch_base
      and S.mch_base.profile not in bm_mod.CREATURE_PROFILES)
S.mch_settings.mch_active_tool = ts_tool

# keys
import types
from mecha_lab import workspace_ui as wsui
kc = C.window_manager.keyconfigs.addon
om = [(i.idname, i.type, round(i.properties.factor, 3)) for i in kc.keymaps['Object Mode'].keymap_items
      if i.idname == 'mch.line_width_key']
check('[ / ] are in Object Mode too (Line Width smaller / bigger)',
      ('mch.line_width_key', 'LEFT_BRACKET', round(1 / 1.15, 3)) in om and ('mch.line_width_key', 'RIGHT_BRACKET', 1.15) in om, om)
sc = [(i.idname, i.type) for i in kc.keymaps['Sculpt'].keymap_items]
check('G in Sculpt Mode = back to Select / Move', ('mch.sculpt_back', 'G') in sc, sc)
def fake(tid):
    tools = types.SimpleNamespace(from_space_view3d_mode=lambda mode, create=False: types.SimpleNamespace(idname=tid))
    return types.SimpleNamespace(workspace=types.SimpleNamespace(tools=tools), area=types.SimpleNamespace(type='VIEW_3D'),
                                 scene=S)
check('[ / ] work in a Mecha drawing tool', wsui.MCH_OT_line_width_key.poll(fake('mecha.creature_plate')))
check('...not in Blender\'s own tools (its select parent / child stays)', not wsui.MCH_OT_line_width_key.poll(fake('builtin.select_box')))
check('...not in Screw Stamp / Primitive', not wsui.MCH_OT_line_width_key.poll(fake('mecha.screw_stamp')))
w0 = S.mch_brush.line_width
r = bpy.ops.mch.line_width_step(factor=1.15)
check('the step makes the line wider', abs(S.mch_brush.line_width - w0 * 1.15) < 1e-6, (w0, S.mch_brush.line_width))
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add()
check('sculpt_back waits for Sculpt Mode', not wsui.MCH_OT_sculpt_back.poll(C))
bpy.ops.object.mode_set(mode='SCULPT')
check('...and is ready there', wsui.MCH_OT_sculpt_back.poll(C))
bpy.ops.object.mode_set(mode='OBJECT')

# Cut / Split Bevel / Chamfer on a dense triangulated mesh (an FBX): the Boolean slivers no longer clamp it to nothing
from mecha_lab import cut_engine as ce
import bmesh as _bm
s_cut = S.mch_cut
S.mch_settings.auto_apply = True
s_cut.depth_mode, s_cut.targets = 'THROUGH', 'ACTIVE'
for op, mode in (('CUT', 'BEVEL'), ('CUT', 'CHAMFER'), ('SPLIT', 'BEVEL')):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=1.5)
    t = C.active_object
    b = _bm.new(); b.from_mesh(t.data)
    _bm.ops.triangulate(b, faces=b.faces[:]); b.to_mesh(t.data); b.free()
    s_cut.edge_finish, s_cut.finish_width = mode, 0.05
    s_cut.side_a_finish = s_cut.side_b_finish = mode
    s_cut.side_a_width = s_cut.side_b_width = 0.05
    msg = ce.perform_closed(C, op, [t], [[(487, 300), (513, 300), (513, 700), (487, 700)]], TOPP)
    parts = [o for o in bpy.data.objects if o.type == 'MESH']
    check(f'{op} {mode} on a dense triangle mesh: full width (not limited by slivers)', 'limited' not in msg
          and mode.lower() in msg.lower(), msg)
    check(f'{op} {mode}: closed mesh', all(non_manifold(o) == 0 for o in parts), [non_manifold(o) for o in parts])
summary()
