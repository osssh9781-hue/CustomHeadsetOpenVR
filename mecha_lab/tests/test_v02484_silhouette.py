"""0.24.76 Silhouette Move: a tool of its own - Path Move that always pulls the whole part (the cut section where you
grab follows the drag, the part stretches out and bends: the Path Move of before 0.24.54, Whole without Tab).
Select (F / bottom bar / Q) is Blender's Select Box (was the Move tool with its gizmo)."""
import inspect
import json
import os
import types

from _harness import bpy, check, fresh, non_manifold, summary
import bmesh

import mecha_lab
from mecha_lab import (bottom_bar as bb, concept_move as cm, key_legend as kl, panel_capture as pc, quick_hud as qh,
                       target_rules as tr, tool_state as ts, ui_tool_settings as uts, workspace_ui as wui)

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
st = S.mch_concept

# --- the tool --------------------------------------------------------------------------------------------------------
row = ts.TOOL_BY_ID.get('SMOVE')
check('Silhouette Move is a tool: name, own icon, Blender tool', row is not None and row[1] == 'Silhouette Move'
      and os.path.isfile(os.path.join(os.path.dirname(cm.__file__), 'icons', row[3] + '.png'))
      and row[5] == 'mecha.silhouette_move', row)
check('... in the Move group next to Path Move, its own saved number',
      any(name == 'Move' and 'SMOVE' in ids for name, ids in ts.TOOL_GROUPS)
      and dict((t[0], t[4]) for t in ts.TOOL_ENUM_ITEMS)['SMOVE'] == 56)
check('... in the bottom bar list and the V pie (under Move / Path)', any(t[0] == 'SMOVE' for t in bb.BAR_TOOLS)
      and 'SMOVE' in bb.PIE_SHARED['PRIMITIVE'])
km = cm.MCH_TOOL_silhouette_move.bl_keymap[0]
check('... its press starts Path Move with Silhouette on', km[0] == 'mch.concept_path' and
      ('silhouette', True) in km[2]['properties'])
check('... key legend says what it does', any('whole part' in ln for ln in kl.lines('SMOVE')), kl.lines('SMOVE'))
items = [p for _d, p in qh.items(C, 'SMOVE')]
check('... Quick HUD: size, hardness, taper (no Method / Area to pick)', 'path_area' not in items
      and 'path_method' not in items and 'radius_px' in items and 'path_taper' in items, items)
tree = pc.capture(uts.DRAWERS['SMOVE'], C)
props = [n.prop for n in pc.walk(tree) if n.kind == 'prop']
check('... panel: no Method / Area / Back Mask, the size and the taper are there', not tree.opts.get('error')
      and 'path_area' not in props and 'path_method' not in props and 'path_back_mask' not in props
      and 'path_taper' in props, (tree.opts.get('error'), props))
check('... like Path Move: its own row of options (Targets not shown)', 'SMOVE' in tr.OWN_ROW)

# --- the drag: always Whole ------------------------------------------------------------------------------------------
fake = types.SimpleNamespace(silhouette=True, method_now=None, info=None, _header=lambda c: None,
                             _preview=lambda c: None, _drop_preview=lambda: None)
st.path_area, st.path_method = 'BRUSH', 'STRETCH'
check('Silhouette Move: Whole and Extend whatever Path Move is set to', cm.MCH_OT_concept_path._area(fake, C) == 'SECTION'
      and cm.MCH_OT_concept_path._method(fake, C) == 'EXTEND')
cm.MCH_OT_concept_path._toggle_area(fake, C)
check('... Tab changes nothing (and leaves Path Move\'s own setting alone)', st.path_area == 'BRUSH')
fake.silhouette = False
check('Path Move itself: as set', cm.MCH_OT_concept_path._area(fake, C) == 'BRUSH'
      and cm.MCH_OT_concept_path._method(fake, C) == 'STRETCH')
st.path_method = 'EXTEND'
src = inspect.getsource(cm.MCH_OT_concept_path.modal)
check('The drag reads Brush / Whole and the method through the tool (not the Path Move setting)',
      'self.area, self.shape = self._area(context), st.shape' in src and 'not self.silhouette' in src)


def plate():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = C.active_object
    o.scale = (2, 1, 0.3)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=12)
    bpy.ops.object.mode_set(mode='OBJECT')
    return o


def volume(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    v = bm.calc_volume(signed=True)
    bm.free()
    return v


o = plate()
v0 = volume(o)
SIDE = [[0.05 * i, 0, 0] for i in range(10)] + [[0.45, 0, 0.05 * i] for i in range(1, 6)]
r = bpy.ops.mch.concept_path('EXEC_DEFAULT', method='EXTEND', area='SECTION', shape='SPHERE', objects=json.dumps([o.name]),
                             grab_point=(0.6, 0.1, 0.15), grab_normal=(1, 0, 0), offsets=json.dumps(SIDE), radius=0.1,
                             size=1.0)
o = S.objects[o.name]
co = [v.co for v in o.data.vertices]
xs, zs = [c.x for c in co], [c.z for c in co]
check('What it does: the whole part from the grab on follows the drag - longer and bent up, closed, outward',
      r == {'FINISHED'} and non_manifold(o) == 0 and volume(o) > v0 + 0.1 and max(xs) - min(xs) > 2.15
      and max(zs) > 0.6, (r, round(volume(o) - v0, 3), round(max(xs) - min(xs), 2), round(max(zs), 2)))

# --- Select = Select Box ---------------------------------------------------------------------------------------------
check('Select (F / bottom bar / Q) switches to Blender\'s Select Box, not the Move tool',
      wui.SELECT_TOOL == 'builtin.select_box' and 'set_native_tool(context, SELECT_TOOL)' in
      inspect.getsource(wui.MCH_OT_select_move.execute) and 'builtin.move' not in
      inspect.getsource(wui.MCH_OT_select_move.execute))
try:
    r = bpy.ops.mch.select_move()
    check('... and it does (where a 3D view is open)', r == {'FINISHED'} and ts.native_tool_id(C) == 'builtin.select_box',
          (r, ts.native_tool_id(C)))
except RuntimeError as ex:
    print('(no 3D view to switch here:', ex, ')')

summary()
