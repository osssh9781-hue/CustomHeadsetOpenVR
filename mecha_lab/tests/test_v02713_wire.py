"""0.24.313 (user: "점 두 개 찍으면 생기는 전선도 ... 넓은 전선, 얇은 거 한 개, 얇은 거 여러 개, 두꺼운 거에 얇은 거 붙어 있는 거, 와이어
뭉쳐 있는 전선 ... 길이 늘릴 수 있고 z 축으로 아래로 흘러내리는 그래비티, 트위스트, 좌우 앞옆으로 휠 수 있는 슬라이더"): the Wire Harness
tool - a wire between two surface points, five styles, its sliders live."""
import numpy as np
from _harness import bpy, bmesh, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import tool_state as ts, ui_tool_settings as uts, wire_gen as wg

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
check('Wire Harness: a tool of its own (Curves, after Cable, enum 95), the Cable tool kept',
      ts.TOOL_BY_ID['WIRE'][5] == 'mecha.wire_gen' and ts._ENUM_NUMBERS['WIRE'] == 95 and 'WIRE' in uts.DRAWERS
      and dict(ts.TOOL_GROUPS)['Curves'].index('WIRE') == dict(ts.TOOL_GROUPS)['Curves'].index('CABLE') + 1
      and ts.TOOL_BY_ID.get('CABLE') is not None)
check('the enum numbers stay unique', len(set(ts._ENUM_NUMBERS.values())) == len(ts._ENUM_NUMBERS))


def W(ob):
    C.view_layer.update()
    return np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])


def islands(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    seen, n = set(), 0
    for v in bm.verts:
        if v.index in seen:
            continue
        n += 1
        stack = [v]
        while stack:
            x = stack.pop()
            if x.index in seen:
                continue
            seen.add(x.index)
            stack += [e.other_vert(x) for e in x.link_edges]
    open_ = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n, open_


bpy.ops.mesh.primitive_cube_add(size=2, location=(-3, 0, 0))
left = C.active_object
bpy.ops.mesh.primitive_cube_add(size=2, location=(3, 0, 0))
right = C.active_object
st = S.mch_wire
st.style, st.count, st.thick, st.length, st.gravity, st.twist, st.plugs = 'SINGLE', 1, 0.05, 1.0, 0.0, 0.0, False
st.bend_lr = st.bend_fb = 0.0
A = ((-2, 0, 0), (1, 0, 0), left)
B = ((2, 0, 0), (-1, 0, 0), right)
w = wg.make(C, A, B)
V = W(w)
check('Single Wire, no gravity, no slack: straight from one face to the other, closed',
      abs(V[:, 0].min() + 2) < 0.03 and abs(V[:, 0].max() - 2) < 0.03 and np.abs(V[:, 2]).max() < 0.03 and
      islands(w) == (1, 0), (V[:, 0].min(), V[:, 0].max(), np.abs(V[:, 2]).max(), islands(w)))
st.gravity = 0.5
z1 = W(w)[:, 2].min()
check(f'Gravity 0.5: it droops (lowest {z1:.3f}), the ends stay', z1 < -0.5 and abs(W(w)[:, 0].min() + 2) < 0.03)
st.length = 1.5
z2 = W(w)[:, 2].min()
check(f'Length 1.5: it hangs lower ({z2:.3f})', z2 < z1 - 0.3)
st.gravity, st.length = 0.0, 1.0
st.bend_lr = 0.5
Vb = W(w)
check('Bend Left / Right: out sideways (Y)', np.abs(Vb[:, 1]).max() > 0.6 and np.abs(Vb[:, 2]).max() < 0.05)
st.bend_lr, st.bend_fb = 0.0, 0.5
Vb = W(w)
check('Bend Front / Back: the other way (Z here)', np.abs(Vb[:, 2]).max() > 0.6 and np.abs(Vb[:, 1]).max() < 0.05)
st.bend_fb = 0.0
for style, n, want in (('THIN', 5, 5), ('LOOM', 12, 12), ('MAIN', 3, 4), ('RIBBON', 6, 1)):
    st.style, st.count = style, n
    st.ties = 3 if style == 'LOOM' else st.ties
    isl, op = islands(w)
    extra = 3 if style == 'LOOM' else 0
    check(f'{style}: {want} wire(s) (+ {extra} ties) - {isl} pieces, closed ({op} open edges)', isl == want + extra and op == 0)
st.style, st.count, st.twist = 'THIN', 3, 0.0
P0 = W(w)
st.twist = 2.0
P1 = W(w)
check('Twist: the wires turn round each other (the middle moves, the ends stay)',
      np.abs(P1 - P0).max() > 0.02 and abs(P1[:, 0].min() + 2) < 0.03)
st.plugs = True
check('End Plugs: a plug on each surface', islands(w)[0] == 3 + 2 and W(w)[:, 0].min() > -2.0 - 0.01, (islands(w), W(w)[:, 0].min()))
right.location.x += 1.0
C.view_layer.update()
st.gravity = 0.1
check('the mesh moved, a slider changed: its end follows', abs(W(w)[:, 0].max() - 3.0) < 0.03, W(w)[:, 0].max())
check('materials: rubber, colours, metal', len(w.data.materials) == 5 and len({p.material_index for p in w.data.polygons}) >= 3)
# 0.24.314 end finishes (user's photos: a hose clamp, a ribbed boot): five more, each closed, on the surface
st.style, st.count, st.plugs, st.gravity = 'SINGLE', 1, True, 0.2
right.location.x -= 1.0
C.view_layer.update()
st.thick = 0.1
for es in ('CLAMP', 'BOOT', 'FERRULE', 'HEX', 'FLANGE'):
    st.end_style = es
    bm = bmesh.new()
    bm.from_mesh(w.data)
    op = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    V = W(w)
    check(f'End Finish {es}: closed ({op} open edges), on the surfaces (nothing into them: {V[:, 0].min():.4f} / '
          f'{V[:, 0].max():.4f}), metal on it', op == 0 and V[:, 0].min() > -2.0 - 0.01 and V[:, 0].max() < 2.0 + 0.01
          and 2 in {p_.material_index for p_ in w.data.polygons})
st.end_style = 'PLUG'
bpy.ops.mch.wire_plain()
check('Make Plain: a plain mesh', not wg.is_wire(w))
summary()
