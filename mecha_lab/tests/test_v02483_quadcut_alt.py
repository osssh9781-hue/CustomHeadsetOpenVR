"""0.24.76 Make Quad -> Cut -> Re-make Quad keeps the cut (Re-make used the hidden original: the cut was gone, as if
nothing happened); Quad Remesh (new engine) -> Cut -> Quad Remesh keeps it too.  Blender's Emulate 3 Button Mouse
(Alt+click arrives as a middle click, Alt taken off): the middle-click menu stays away and the panel / ZBrush key
legend say why Alt subtract cannot work.  Path Move Extend (Brush) on a quad remeshed part keeps it outward (one grab
turned the whole part inside out)."""
import types

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import (bottom_bar as bb, core_geometry as cg, cut_engine as ce, mecha_menu as mm, panel_capture as pc,
                       quad_field as qf, quad_remesh as qr, workspace_ui as wui, zb_sculpt as zs, zb_ui as zu)

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
S.mch_settings.auto_apply = True
cut = S.mch_cut
POCKET = [(400, 440), (600, 440), (600, 560), (400, 560)]


def part():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=1.0, scale=(3.0, 2.0, 0.5))
    ob = C.active_object
    bpy.ops.object.transform_apply(scale=True)
    m = ob.modifiers.new('b', 'BEVEL')
    m.width, m.segments = 0.3, 3
    bpy.ops.object.modifier_apply(modifier='b')
    return ob


def top():
    C.view_layer.update()
    hit, loc, *_r = S.ray_cast(C.evaluated_depsgraph_get(), Vector((0.1, 0.05, 5)), Vector((0, 0, -1)))
    return round(loc.z, 3) if hit else None


def do_cut(ob):
    cut.depth_mode, cut.depth, cut.gn_ramp, cut.gn_finish = 'SURFACE', 0.1, False, 'NONE'
    ce.perform_closed(C, 'CUT', [ob], [POCKET], TOP, False)


def select(ob):
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob


# --- Make Quad (old: Patch) -> Cut -> Re-make --------------------------------------------------------------------
ob = part()
qs = S.mch_quadremesh
qs.method, qs.faces = 'PATCH', 1500
select(ob)
bpy.ops.mch.quad_remesh()
q = C.active_object
check('Make Quad: the copy remembers how it was made (not changed yet)', qr.is_quad(q) and not qr.edited(q)
      and qr.SIG_KEY in q, q.keys())
do_cut(q)
check('Cut on the quad copy: a pocket, the copy counts as changed', top() == 0.15 and qr.edited(q), top())
r = bpy.ops.mch.quad_remesh()
q2 = C.active_object
check('Re-make Quad after the cut: the pocket stays (was: made again from the original - the cut gone)',
      r == {'FINISHED'} and q2 == q and top() == 0.15 and non_manifold(q2) == 0, (r, top(), non_manifold(q2)))
src = bpy.data.objects[q2[qr.SRC_KEY]]
check('... new quads, not "changed" any more; the changed mesh (with the cut) kept hidden as the new original',
      len(q2.data.polygons) > 500 and not qr.edited(q2) and src != ob and src.hide_get() and src.name.endswith('_Changed')
      and len(src.data.polygons) != len(q2.data.polygons), (len(q2.data.polygons), src.name))
check('... the first original still there, hidden, untouched', ob.name in bpy.data.objects and ob.hide_get()
      and len(ob.data.polygons) == 98, len(ob.data.polygons))
check('... its own Bevel modifier is not baked in (switched back on after)',
      q2.modifiers.get(qr.BEVEL) is None or q2.modifiers[qr.BEVEL].show_viewport)
n_before = len(q2.data.polygons)
qs.faces = 600
bpy.ops.mch.quad_remesh()
check('Re-make with other settings, nothing changed in between: still the pocket, fewer quads',
      top() == 0.15 and len(C.active_object.data.polygons) < n_before, (top(), len(C.active_object.data.polygons)))
ob = part()
qs.faces = 1500
select(ob)
bpy.ops.mch.quad_remesh()
q = C.active_object
n0 = len(q.data.polygons)
qs.faces = 600
bpy.ops.mch.quad_remesh()
check('Re-make on an unchanged copy: from the original as before (the Faces setting takes)',
      len(C.active_object.data.polygons) < n0 and top() == 0.25, (n0, len(C.active_object.data.polygons)))
del q[qr.SIG_KEY]
check('A quad copy made before 0.24.76 (no fingerprint) counts as changed: nothing done on it is lost', qr.edited(q))
bpy.ops.mch.quad_apply()
check('Apply: the fingerprint goes with the rest', qr.SIG_KEY not in C.active_object and not qr.is_quad(C.active_object))
tree = pc.capture(qr.draw, C)
check('Remesh panel draws', not tree.opts.get('error'), tree.opts.get('error'))

# --- Quad Remesh (new engine) -> Cut -> Quad Remesh ---------------------------------------------------------------
ob = part()
qf.remesh_object(ob, 1500)
do_cut(ob)
msg = qf.remesh_object(ob, 1500)
check('Quad Remesh -> Cut -> Quad Remesh (new engine, in place): the pocket stays, closed, quads',
      top() == 0.15 and non_manifold(ob) == 0 and 'Quad Remesh' in msg and len(ob.data.polygons) > 500, (top(), msg))

# --- Path Move on a quad remeshed part ----------------------------------------------------------------------------
import json
import bmesh


def signed_volume(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    v = bm.calc_volume(signed=True)
    bm.free()
    return v


for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=1)
pm = C.active_object
pm.scale = (2, 1, 0.3)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bev = pm.modifiers.new('b', 'BEVEL')
bev.width, bev.segments = 0.08, 2
bpy.ops.object.modifier_apply(modifier='b')
qf.remesh_object(pm, 2000)
v0 = signed_volume(pm)
UP = [[0, 0, 0.05 * i] for i in range(10)] + [[0.05 * i, 0, 0.45] for i in range(1, 6)]
r = bpy.ops.mch.concept_path('EXEC_DEFAULT', method='EXTEND', area='BRUSH', shape='SPHERE', objects=json.dumps([pm.name]),
                             grab_point=(0.6, 0.1, 0.15), grab_normal=(0, 0, 1), offsets=json.dumps(UP), radius=0.1, size=1.0)
pm = S.objects[pm.name]
check('Path Move Extend (Brush) on a quad remeshed part: pulled out, closed, still outward (was inside out here)',
      r == {'FINISHED'} and non_manifold(pm) == 0 and signed_volume(pm) > v0 > 0, (r, round(v0, 3), round(signed_volume(pm), 3)))

# --- Emulate 3 Button Mouse ---------------------------------------------------------------------------------------
inputs = C.preferences.inputs
was = inputs.use_mouse_emulate_3_button
real_ui, real_pref = bb.ui_active, wui.pref
bb.ui_active = lambda context: True
fake = types.SimpleNamespace(area=types.SimpleNamespace(type='VIEW_3D'), preferences=C.preferences)
try:
    inputs.use_mouse_emulate_3_button = False
    check('Middle click menu: on as before (Emulate 3 Button Mouse off)', mm.MCH_OT_mecha_mmb_gate.poll(fake)
          and not zs.emulate_3_button(C))
    legend = [i.label for i in zu.key_legend(C, 1.0, mecha_lab.mecha_menu.Item, 0, 0) if i.label]
    check('... the ZBrush key legend as before', not any('middle mouse' in t for t in legend))
    inputs.use_mouse_emulate_3_button = True
    check('Emulate 3 Button Mouse on (Alt+click = a middle click): the middle-click menu stays away',
          zs.emulate_3_button(C) and not mm.MCH_OT_mecha_mmb_gate.poll(fake))
    legend = [i.label for i in zu.key_legend(C, 1.0, mecha_lab.mecha_menu.Item, 0, 0) if i.label]
    check('... the ZBrush key legend says Alt is the middle mouse now and where to turn it off',
          any('middle mouse' in t for t in legend) and any('Preferences > Input > Mouse' in t for t in legend), legend[:5])
    tree = pc.capture(lambda lay, ctx: wui.MCH_PT_main.draw(types.SimpleNamespace(layout=lay), ctx), C)
    texts = [str(n.opts.get('text', '')) for n in pc.walk(tree)]
    check('... the Mecha Lab panel says so too', any('Emulate 3 Button Mouse' in t for t in texts),
          tree.opts.get('error') or texts[:6])
    check('Blender Preferences are only read, never changed', 'use_mouse_emulate_3_button =' not in
          __import__('inspect').getsource(zs))
finally:
    inputs.use_mouse_emulate_3_button = was
    bb.ui_active = real_ui

summary()
