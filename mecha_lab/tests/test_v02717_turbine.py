"""0.24.317 (user, five photos: "터빈 메뉴도 만들어 줘"): the Turbine tool - Fan / Motor / Nozzle / Engine, closed parts, the
blades' count / twist live, Spin turning the rotor only."""
import math

import numpy as np
from _harness import bpy, bmesh, check, fresh, summary

import mecha_lab
from mecha_lab import tool_state as ts, turbine_gen as tg, ui_tool_settings as uts

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
check('Turbine: a tool of its own (Block-out, enum 97)', ts.TOOL_BY_ID['TURBINE'][5] == 'mecha.turbine_gen'
      and ts._ENUM_NUMBERS['TURBINE'] == 97 and 'TURBINE' in uts.DRAWERS and 'TURBINE' in dict(ts.TOOL_GROUPS)['Block-out'])
check('the enum numbers stay unique', len(set(ts._ENUM_NUMBERS.values())) == len(ts._ENUM_NUMBERS))


def open_edges(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n


def W(ob):
    C.view_layer.update()
    return np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])


st = S.mch_turbine
for style in ('FAN', 'MOTOR', 'NOZZLE', 'ENGINE'):
    for o in C.selected_objects:
        o.select_set(False)
    st.style = style
    S.cursor.location = (0, 0, 0)
    bpy.ops.mch.turbine_add()
    parts = tg.parts_of(S, tg.turbine_of(C.active_object))
    b, r = parts['BODY'], parts['ROTOR']
    op = (open_edges(b), open_edges(r))
    V = np.vstack([W(b)] + ([W(r)] if len(r.data.vertices) else []))   # (a nozzle: nothing turns)
    rad = np.hypot(V[:, 1], V[:, 2]).max()
    check(f'{style}: a body and a rotor (its child), closed {op}, about the diameter across ({rad:.3f})',
          r.parent == b and op == (0, 0) and 0.45 < rad < 0.7 and len(b.data.polygons) + len(r.data.polygons) > 200, op)
    for o in parts.values():
        bpy.data.objects.remove(o)
for o in C.selected_objects:
    o.select_set(False)
st.style, st.blades = 'FAN', 12
bpy.ops.mch.turbine_add()
parts = tg.parts_of(S, tg.turbine_of(C.active_object))
b, r = parts['BODY'], parts['ROTOR']
n12 = len(r.data.polygons)
st.blades = 24
check('Blade Count 24: more blades, live', len(r.data.polygons) > n12 * 1.6)
V0 = W(r)
st.twist_tip = 20.0
check('Twist Tip: the blades turn (live)', np.abs(W(r) - V0).max() > 0.02)
st.spin = 30.0
C.view_layer.update()
check('Spin 30: the rotor turns round X, the body stays, no rebuild',
      abs(math.degrees(r.matrix_world.to_euler().x) - 30) < 1e-3 and b.matrix_world.to_euler().x == 0)
st.spin = 0.0
st.casing = False
st.stators = False
check('Casing / Stator Vanes off: the body empty of them', len(b.data.polygons) == 0)
st.casing = True
check('... casing on again', len(b.data.polygons) > 0 and open_edges(b) == 0)
check('materials: metal, blade, copper, glow, dark', len(r.data.materials) == 5 and
      r.data.materials[3].node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value > 1)
bpy.ops.mch.turbine_plain()
check('Make Plain', not tg.turbine_of(b))
summary()
