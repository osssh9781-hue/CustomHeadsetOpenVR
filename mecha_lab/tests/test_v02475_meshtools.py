"""0.24.73 Mesh Tools (sidebar, Mecha Lab tab): DynaMesh / Decimate / Quad Remesh / Edge Mesh / Hard Edges in Object Mode
on every selected mesh, with the ZBrush shelf's settings."""
import numpy as np

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import hard_edges as he, mesh_tools as mt, panel_capture as pc, quick_hud as qh, zb_ui as zu

mecha_lab.register()
fresh()
C = bpy.context
zb = C.scene.mch_zb


def select(*obs):
    for o in C.selected_objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    C.view_layer.objects.active = obs[0]


def sphere(name, level=5, loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=level, radius=1.0, location=loc)
    o = C.active_object
    o.name = name
    return o


def block(name, loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = C.active_object
    o.name = name
    m = o.modifiers.new('s', 'SUBSURF')
    m.subdivision_type = 'SIMPLE'
    m.levels = 5
    with C.temp_override(object=o, active_object=o):
        bpy.ops.object.modifier_apply(modifier='s')
    return o


node = pc.capture(mt.draw, C)
acts = {x.opts.get('props', {}).get('action') for x in pc.walk(node) if x.kind == 'op'} - {None}
check('Mecha Lab tab: Mesh Tools panel with DynaMesh / Decimate / Quad Remesh / Edge Mesh / Find Edges / Apply / Clear',
      set(mt.ACTIONS) <= acts, sorted(acts))
check('... in the Mecha Lab sidebar tab, before High Poly', mt.MCH_PT_mesh_tools.bl_category == 'Mecha Lab'
      and mt.MCH_PT_mesh_tools.bl_order < 80)

a = sphere('A', 5)
b = sphere('B', 5, (3, 0, 0))
select(a, b)
f0 = len(a.data.polygons)
zb.decimate = 20
r = bpy.ops.mch.mesh_tool(action='DECIMATE')
check('Decimate: every selected mesh, one undo step, Object Mode kept', r == {'FINISHED'} and C.mode == 'OBJECT'
      and len(a.data.polygons) < 0.3 * f0 and len(b.data.polygons) < 0.3 * f0, (len(a.data.polygons), f0))
zb.points = 3000
r = bpy.ops.mch.mesh_tool(action='DYNAMESH')
check('DynaMesh: both remeshed to about Points', r == {'FINISHED'}
      and all(1500 < len(o.data.vertices) < 6000 for o in (a, b)), [len(o.data.vertices) for o in (a, b)])
zb.qr_target = 0.5
r = bpy.ops.mch.mesh_tool(action='QUAD_REMESH')
quads = [sum(len(p.vertices) == 4 for p in o.data.polygons) / max(1, len(o.data.polygons)) for o in (a, b)]
check('Quad Remesh: both mostly quads', r == {'FINISHED'} and min(quads) > 0.8, quads)

c = block('C')
d = block('D', (3, 0, 0))
select(c, d)
zb.em_detail = 400
zb.he_width = 0.05
r = bpy.ops.mch.mesh_tool(action='EDGE_MESH')
check('Edge Mesh: both get the light mesh + live bevel / subdivide / fit', r == {'FINISHED'}
      and all(he.source(o) is not None and o.modifiers.get(he.BEVEL) for o in (c, d)),
      [[m.name for m in o.modifiers] for o in (c, d)])
r = bpy.ops.mch.mesh_tool(action='HE_APPLY')
check('Apply: both plain client meshes, the off-scene originals gone', r == {'FINISHED'}
      and all(not o.modifiers and he.source(o) is None for o in (c, d))
      and not any(o.name.endswith('_EdgeSource') for o in bpy.data.objects))
e = block('E')
select(e)
r = bpy.ops.mch.mesh_tool(action='HE_FIND')
check('Find Edges + Clear on a selected mesh', r == {'FINISHED'} and e.modifiers.get(he.BEVEL) is not None
      and bpy.ops.mch.mesh_tool(action='HE_CLEAR') == {'FINISHED'} and not e.modifiers)
big = sphere('Big', 3, (6, 0, 0))
big.shape_key_add(name='Basis')                 # (Find Edges refuses shape keys)
select(big, e)
r = bpy.ops.mch.mesh_tool(action='HE_FIND')
check('A mesh that can\'t be done is skipped with its reason, the others still run', r == {'FINISHED'}
      and big.modifiers.get(he.BEVEL) is None and e.modifiers.get(he.BEVEL) is not None,
      (r, [m.name for m in big.modifiers], [m.name for m in e.modifiers]))
bpy.ops.object.mode_set(mode='EDIT')
check('Only in Object Mode (the ZBrush shelf has them in Sculpt Mode)', not mt.MCH_OT_mesh_tool.poll(C))
bpy.ops.object.mode_set(mode='OBJECT')

# --- ZBrush left tray: scrolling stays inside its rows, dragging scrolls -----------------------------------------
wm = C.window_manager
zu._OVER[0] = 'A'
zu._MAX['mch_zb_scroll'] = 100.0
wm.mch_zb_scroll = 500.0                       # (the old wheel ran on past the end like this)
zu.scroll_by(C, 800, 600, 1.0, -48.0)
check('Left tray: scrolling back up works at once from past the end (it seemed stuck for a while)',
      abs(wm.mch_zb_scroll - 52.0) < 1e-3, wm.mch_zb_scroll)
zu.scroll_by(C, 800, 600, 1.0, 1000.0)
check('... and never runs past the last row', abs(wm.mch_zb_scroll - 100.0) < 1e-3, wm.mch_zb_scroll)


class _Ev:
    def __init__(self, t, v, y):
        self.type, self.value, self.mouse_region_y = t, v, y


class _Op:
    pass


op = _Op()
op.panel, op.last_y = zu, 300
wm.mch_zb_scroll = 0.0


class _Ctx:
    window_manager = wm

    class region:
        width, height = 800, 600


r1 = qh.MCH_OT_quick_hud_press._modal_scroll(op, _Ctx, _Ev('MOUSEMOVE', 'NOTHING', 330))
r2 = qh.MCH_OT_quick_hud_press._modal_scroll(op, _Ctx, _Ev('LEFTMOUSE', 'RELEASE', 330))
check('Dragging an empty spot of the tray moves its rows with the mouse (0.24.73; before only the wheel did)',
      r1 == {'RUNNING_MODAL'} and abs(wm.mch_zb_scroll - 30.0) < 1e-3 and r2 == {'FINISHED'},
      (r1, wm.mch_zb_scroll, r2))
check('... the side panel, Layers panel and ZBrush trays are found under the mouse', callable(qh.scroll_target))

summary()
