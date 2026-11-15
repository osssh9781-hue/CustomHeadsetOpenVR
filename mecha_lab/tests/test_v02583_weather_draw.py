"""0.24.174 (user: "스노우랑 덜트들도 기본적으로 걍 아머플레이트처럼 내가 그리게 만들어 줘"): the Weathering tools draw by default -
the outline drawn (here in pixels through a fixed front view) made a plate on the surface as Armor Plate does (live
under it), and that plate made dirt / dust / leaves / snow at once; Click a Mesh (the old way) stays as an option;
Sketch mode too.  The real drawing: tests/gui/round174_real_window.py."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import cut_engine as ce, core_geometry as cg, lasso_sketch, tool_state as ts, weathering as wt  # noqa

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
modes = {i.identifier for i in bpy.ops.mch.cut_stroke.get_rna_type().properties['mode'].enum_items}
check('the four Weathering tools draw now (a lasso tool each, Draw by default; Click a Mesh as an option)',
      {'WDIRT', 'WDUST', 'WLEAF', 'WSNOW'} <= modes and {'WDIRT', 'WDUST', 'WLEAF', 'WSNOW'} <= ts.SHAPE_TOOLS
      and S.mch_weather_how == 'DRAW' and {i.identifier for i in S.bl_rna.properties['mch_weather_how'].enum_items}
      == {'DRAW', 'CLICK'} and all(any(k[0] == 'mch.cut_stroke' for k in t.bl_keymap) for t in wt.TOOLS))
bpy.ops.mesh.primitive_plane_add(size=6.0)
ground = C.active_object
ground.name = 'Ground'
TOP = cg.OrthoProjector(Euler((0, 0, 0)).to_quaternion(), pixels_per_unit=100.0)


def ring(cx, cy, r, n=48):
    return [[TOP.to_screen(Vector((cx + r * math.cos(a), cy + r * 0.7 * math.sin(a), 0.0)))
             for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]]


made = {}
for k, (kind, x) in enumerate((('DIRT', -1.8), ('DUST', -0.6), ('LEAVES', 0.6), ('SNOW', 1.8))):
    msg = wt.perform(C, ring(x, 0.0, 0.5), TOP, kind)
    ob = C.active_object
    made[kind] = ob
    bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    print(kind, msg, round(min(v.x for v in bb), 2), round(max(v.x for v in bb), 2))
ok = all(wt.kind_of(o) == k and o.modifiers.get(wt.MOD) is not None and o != ground for k, o in made.items())
xs = {k: (o.matrix_world @ Vector(o.bound_box[0])).x for k, o in made.items()}
check(f'drawn on the ground: a plate where each outline was, made Dirt / Dust / Leaves / Snow (live) - {list(made)}',
      ok and len({o.name for o in made.values()}) == 4)
dirt = made['DIRT']
mods = [m.name for m in dirt.modifiers]
check(f'the plate under it stays live (its modifiers: {mods}), the weathering last', mods[-1] == wt.MOD and len(mods) >= 1)
dg = C.evaluated_depsgraph_get()
ev = dirt.evaluated_get(dg)
n_ev = len(ev.data.polygons) if ev.type == 'MESH' else 0
check(f'it is dirt now (evaluated: {n_ev:,} faces)', n_ev > 0)
S.mch_brush.sketch_first = True
lasso_sketch.add(C, 'WSNOW', ring(0.0, 1.6, 0.4), TOP)
lasso_sketch.add(C, 'WSNOW', ring(0.5, 1.6, 0.4), TOP)
before = {o.name for o in bpy.data.objects}
msg = lasso_sketch.commit(C)
new = [o for o in bpy.data.objects if o.name not in before]
S.mch_brush.sketch_first = False
check(f'Sketch mode: two shapes, Enter: one snow plate from both ({msg[:60]}...)', 'WSNOW' in lasso_sketch.MODES
      and len([o for o in new if wt.kind_of(o) == 'SNOW']) == 1)
S.mch_weather_how = 'CLICK'
r = bpy.ops.mch.weather_click(kind='SNOW')            # (the old way on the selected mesh: execute = the active one)
check('Click a Mesh (the old way) still turns a mesh you made', r == {'FINISHED'} and wt.kind_of(C.active_object)
      == 'SNOW')
summary()
