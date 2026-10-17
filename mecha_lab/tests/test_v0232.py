"""0.23.2: Mirror button uses the lean gesture (kept live), gesture at the bottom centre;
V = tool pie; Cloth Plate Gravity; Mesh Curve = the Tube tool (old one hidden), linked
Repeat object with Count / Distance spacing; Nomad-style point gizmos + button bar."""
import math
import sys

from _harness import bpy, check, cube, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import bottom_bar as bb, cloth_wrinkle as cw, curve_tube as ct, tool_state as ts

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene

# keys / tools
kc = C.window_manager.keyconfigs.addon
keys = [(ki.idname, ki.type, ki.shift) for km in kc.keymaps for ki in km.keymap_items]
check('V = tool pie, Q = toggle', ('mch.tool_pie', 'V', False) in keys and ('mch.toggle_last_tool', 'Q', False) in keys)
check('Mesh Curve = the new curve tool, old one hidden', ts.TOOL_BY_ID['TUBE'][1] == 'Mesh Curve'
      and 'DRAW' in ts.HIDDEN_TOOLS and all(t[0] != 'DRAW' for t in ts.VISIBLE_TOOLS))
check('mirror button = lean gesture kept live', "start_mirror(context, self.action == 'MIRROR'" in open(bb.__file__).read()
      and 'keep_live' in {p.identifier for p in bpy.ops.mch.mirror_lean.get_rna_type().properties})

# cloth gravity
check('Cloth Plate Gravity input + HUD slider', any(n == 'Gravity' for n, *_r in cw.INPUTS)
      and any(k[0] == 'gravity' for k in cw.SLIDERS) and cw.build_group()['mch_version'] == cw.VERSION)

# repeat spacing + link
pts = [Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((2, 0, 0))]
sm = ct.path_samples(pts, [1, 1, 1], False, 'LINEAR', 10)
sv, sf = ct.sphere_source()
v, f = ct.repeat_mesh(sm, dict(radius=0.05, spacing_mode='DISTANCE', spacing=0.25), sv, sf)
check('Distance spacing: a copy every 0.25 on a 2 m curve = 9', len(v) == 9 * len(sv), len(v) // len(sv))
ob = ct.new_tube(C, Vector((0, 0, 0)))
ob.mch_tube.live = False
ct.set_points(ob, [(p, 1.0) for p in pts])
ob.mch_tube.live = True
tb = ob.mch_tube
src = cube('Bolt', 0.1, loc=(0, 3, 0))
tb.mode = 'REPEAT'
tb.source = src
tb.spacing_mode = 'DISTANCE'
tb.spacing = 0.5
check('Repeat linked object every 0.5', len(ob.data.vertices) == 5 * 8, len(ob.data.vertices))
tb.spacing = 0.25
check('Spacing slider', len(ob.data.vertices) == 9 * 8)
mod = src.modifiers.new('sub', 'SUBSURF')
mod.levels = 1
C.view_layer.update()
check('linked: editing the source object updates the curve', len(ob.data.vertices) == 9 * 26,
      len(ob.data.vertices))
tb.spacing_mode = 'COUNT'
tb.count = 3
check('Count spacing still works', len(ob.data.vertices) == 3 * 26)

# gizmos + bar
check('point / radius gizmo group and button bar registered', 'bl_rna' in ct.MCH_GGT_tube_points.__dict__
      and 'bl_rna' in ct.MCH_GGT_tube_bar.__dict__)
C.view_layer.objects.active = ob
for opt, prop, before in (('MODE', 'mode', 'REPEAT'), ('CLOSED', 'closed', False), ('SPLINE', 'spline', 'SMOOTH'),
                          ('PROFILE', 'profile', 'ROUND'), ('CAP', 'cap', 'ROUND'), ('SPACING', 'spacing_mode',
                                                                                     'COUNT')):
    setattr(tb, prop, before)
    bpy.ops.mch.tube_toggle(option=opt)
    check(f'bar button {opt}', getattr(tb, prop) != before)
lay = ct.tube_bar_layout(1600, 900)
check('bar: every button and slider placed at the bottom centre', all(n in lay for n, *_r in ct.TUBE_BUTTONS)
      and all('slider_' + k in lay for k, *_r in ct.TUBE_SLIDERS) and all(p[1] < 300 for p in lay.values()))
for key, *_r in ct.TUBE_SLIDERS:
    spec = ct.tube_slider_spec(ob, key)
    if len(spec) != 6:
        check(f'slider spec {key}', False)
        break
else:
    check('all bar slider specs valid', True)
spec = ct.tube_slider_spec(ob, 'radius')
spec[4](120)
check('Radius slider sets the radius', abs(tb.radius - 0.12) < 1e-6)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
