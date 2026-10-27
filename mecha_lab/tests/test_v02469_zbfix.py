"""0.24.69 ZBrush screen fixes: Extract works (Blender's Mask Extract has no thickness setting - the thickness goes
on its Solidify), ClipCurve / TrimCurve / TrimLasso (and Move / Scale / Rotate) get the press (the ZBrush press made
a brush stroke of it), a stroke started just off the silhouette is still a stroke, Ctrl+Z after Decimate (or another
action that leaves Sculpt Mode) is one press and stays in Sculpt Mode."""
import inspect

import numpy as np

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import zb_sculpt as zs

mecha_lab.register()
fresh()
C = bpy.context
zs.on = lambda c: getattr(c, 'mode', '') == 'SCULPT'
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=32, ring_count=16)
ob = C.active_object
ob.name = 'Body'
bpy.ops.object.mode_set(mode='SCULPT')
zb = C.scene.mch_zb
check('Extract without a mask: says to paint one (nothing made)', 'mask first' in zs.run(C, 'EXTRACT')
      and len(bpy.data.objects) == 1)
me = ob.data
a = me.attributes.get('.sculpt_mask') or me.attributes.new('.sculpt_mask', 'FLOAT', 'POINT')
co = np.array([v.co[:] for v in me.vertices])
a.data.foreach_set('value', (co[:, 2] > 0.3).astype(np.float32))
zb.thick = 0.05
r = bpy.ops.mch.zb_action(action='EXTRACT')
new = bpy.data.objects.get('Body_Extract')
check('Extract: the masked part becomes a new SubTool (was an error every time: "thickness" unrecognized)',
      r == {'FINISHED'} and new is not None and len(new.data.polygons) > 0, [o.name for o in bpy.data.objects])
sol = [m for m in new.modifiers if m.type == 'SOLIDIFY'] if new else []
check('... Thick on its Solidify', sol and abs(sol[0].thickness - 0.05) < 1e-6, [m.type for m in new.modifiers])
check('... and you keep sculpting the SubTool you were on (ZBrush)', C.active_object == ob and C.mode == 'SCULPT')
check('ClipCurve / TrimCurve / TrimLasso / Move are not brushes: the ZBrush press lets Blender\'s tool take it',
      zs.tool_is_brush('builtin.brush') and zs.tool_is_brush('builtin_brush.Draw')
      and not any(zs.tool_is_brush(t) for t in ('builtin.line_project', 'builtin.line_trim', 'builtin.lasso_trim',
                                                 'builtin.move', 'builtin.box_mask'))
      and "return {'PASS_THROUGH'}" in inspect.getsource(zs.MCH_OT_zb_press.invoke)
      and inspect.getsource(zs.MCH_OT_zb_press.invoke).index('tool_is_brush')
      < inspect.getsource(zs.MCH_OT_zb_press.invoke).index('plan('))
import bl_ui.space_toolsystem_toolbar as tb
src_tb = open(tb.__file__, encoding='utf-8').read()
check('... the tiles name Blender\'s Sculpt tools that exist in this Blender (Line Project / Line Trim / Lasso Trim; '
      'switching tools itself needs a window)', all(f'idname="{zs.TOOLS[a]}"' in src_tb
                                                     for a in ('CLIP_CURVE', 'TRIM_CURVE', 'TRIM_LASSO')))

# every Blender operator call in the add-on uses settings that operator really has (Extract passed "thickness")
import glob
import os
import re
bad = []
for f in sorted(glob.glob(os.path.join(os.path.dirname(zs.__file__), '*.py'))):
    src = open(f, encoding='utf-8').read()
    for m in re.finditer(r"bpy\.ops\.(\w+)\.(\w+)\(", src):
        i, depth = m.end(), 1
        while i < len(src) and depth:
            depth += {'(': 1, ')': -1}.get(src[i], 0)
            i += 1
        kws = set(re.findall(r"(?:^|[,(\s])(\w+)\s*=(?!=)", src[m.end():i - 1]))
        try:
            props = {p.identifier for p in getattr(getattr(bpy.ops, m.group(1)), m.group(2)).get_rna_type().properties}
        except Exception:
            bad.append((os.path.basename(f), m.group(0), 'no such operator'))
            continue
        bad += [(os.path.basename(f), src[:m.start()].count('\n') + 1, m.group(0), k) for k in kws - props]
check('Every Blender operator call in the add-on only uses settings that operator has (in this Blender)', not bad, bad)

# --- the silhouette ----------------------------------------------------------------------------------------------
from types import SimpleNamespace
from mathutils import Matrix
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
if C.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24)
sph = C.active_object
view = Matrix.Translation((0, 0, -10))                       # top view, orthographic, 4 units across 1000 px
fake = SimpleNamespace(active_object=sph, region=SimpleNamespace(width=1000, height=1000),
                       region_data=SimpleNamespace(view_matrix=view, perspective_matrix=Matrix.Diagonal(
                           (0.5, 0.5, -0.05, 1.0)) @ view, is_perspective=False, view_perspective='ORTHO',
                           view_distance=10.0),
                       evaluated_depsgraph_get=C.evaluated_depsgraph_get)
real_px = zs.brush_px
zs.brush_px = lambda c: 50.0
check('A press 10 px off the silhouette with a 50 px brush: still on the model (the ZBrush press turned the view)',
      zs.near_model(fake, 760, 500) and zs.near_model(fake, 500, 762))
check('... 40 px off: the canvas (turns the view, as in ZBrush)', not zs.near_model(fake, 790, 500))
check('... far out on the canvas: no ray cast at all (screen box first)', not zs.near_model(fake, 990, 990))
zs.brush_px = real_px
src_press = inspect.getsource(zs.MCH_OT_zb_press.invoke)
check('... used for strokes (plain, Alt Zsub, Shift Smooth), not for Ctrl (mask lasso on the canvas)',
      src_press.count('near_model(') == 2 and "model in {'ZSUB', 'SMOOTH'}" in src_press)

# --- Ctrl+Z after Decimate ---------------------------------------------------------------------------------------
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5)
body = C.active_object
body.name = 'Undo'
bpy.ops.ed.undo_push(message='added')
bpy.ops.object.mode_set('EXEC_DEFAULT', True, mode='SCULPT')
n0 = len(body.data.polygons)
zb = C.scene.mch_zb
zb.decimate = 20
bpy.ops.mch.zb_action(action='DECIMATE')
n1 = len(bpy.data.objects['Undo'].data.polygons)
bpy.ops.ed.undo()
check('Decimate, Ctrl+Z once: the old mesh, still in Sculpt Mode (took two presses and came back in Object Mode)',
      C.mode == 'SCULPT' and len(bpy.data.objects['Undo'].data.polygons) == n0 and n1 < n0,
      (C.mode, n0, n1, len(bpy.data.objects['Undo'].data.polygons)))
bpy.ops.ed.redo()
check('... Ctrl+Shift+Z: decimated again, in Sculpt Mode', C.mode == 'SCULPT'
      and len(bpy.data.objects['Undo'].data.polygons) == n1, (C.mode, len(bpy.data.objects['Undo'].data.polygons)))
check('... no step marker left in the scene (only the two stored steps carry it)', zs.RESCULPT not in C.scene)
summary()
