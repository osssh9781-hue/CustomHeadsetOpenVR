"""0.24.307 (user: "실린더 메뉴 만들어주라 두께랑 그런거 수정하고 위아래 레이어 분리되게" / "연결 부위도 나사 박히는 부분 내가
사이즈 조정 가능하게"): Cylinder - a tool of its own; layers stacked as objects of their own, screwed together (a
threaded neck into a threaded hole a clearance wider); Wall hollows them; the sliders live."""
import math

import numpy as np
from _harness import bpy, bmesh, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import cylinder_gen as cy, tool_state as ts, ui_tool_settings as uts

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene

row = ts.TOOL_BY_ID.get('CYLGEN')
check('Cylinder is a tool of its own (Block-out, enum 93, workspace tool, its window)',
      row is not None and row[5] == 'mecha.cylinder_gen' and 'CYLGEN' in dict(ts.TOOL_GROUPS)['Block-out']
      and ts._ENUM_NUMBERS['CYLGEN'] == 93 and 'CYLGEN' in uts.DRAWERS)
check('the enum numbers stay unique', len(set(ts._ENUM_NUMBERS.values())) == len(ts._ENUM_NUMBERS))


def stats(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    vol = bm.calc_volume(signed=True)
    bm.free()
    return nm, vol


def world(ob):
    return np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])


st = S.mch_cylinder
st.diameter, st.height, st.wall, st.layers, st.split, st.gap = 1.0, 1.2, 0.0, 2, 0.5, 0.0
st.thread_size, st.thread_length, st.pitch, st.thread_depth, st.clearance = 0.6, 0.2, 0.06, 0.025, 0.004
S.cursor.location = (0, 0, 0)
bpy.ops.mch.cylinder_add()
obs = cy.layers_of(S, cy.stack_of(C.active_object))
check('Summon Cylinder: two layers, each an object of its own, selected', len(obs) == 2 and
      all(o.select_get() for o in obs) and obs[0] != obs[1])
for o in obs:
    nm, vol = stats(o)
    check(f'{o.name}: closed, right way out ({nm} open edges, volume {vol:.4f})', nm == 0 and vol > 0)
lo, up = obs
Wl, Wu = world(lo), world(up)
check('the layers meet at Split At (0.6): the lower one\'s shoulder, the upper one\'s bottom',
      abs(Wu[:, 2].min() - 0.6) < 1e-4 and abs(Wl[:, 2].min()) < 1e-4 and abs(Wu[:, 2].max() - 1.2) < 1e-4)
neck = Wl[Wl[:, 2] > 0.6 + 1e-4]
check('the lower layer: a threaded neck up into the upper one (Thread Length less the clearance)',
      len(neck) > 0 and abs(neck[:, 2].max() - (0.6 + 0.2 - 0.004)) < 1e-4)
rn = np.hypot(neck[:, 0], neck[:, 1])
rn = rn[rn > 0.1]                                # (its top's centre point aside)
check(f'... its thread: from the root to the root + Thread Depth (radius {rn.min():.4f} .. {rn.max():.4f})',
      abs(rn.max() - 0.3) < 2e-3 and abs(rn.min() - (0.3 - 0.025)) < 2e-3)
check('the volume adds up: two layers about a whole cylinder (the neck fills the hole)',
      abs(stats(lo)[1] + stats(up)[1] - math.pi * 0.25 * 1.2) < 0.01, stats(lo)[1] + stats(up)[1])

# the neck inside the hole: the two layers overlap nowhere (a boolean of the two: no volume)


def overlap(a, b):
    tmp = a.copy()
    tmp.data = a.data.copy()
    C.scene.collection.objects.link(tmp)
    m = tmp.modifiers.new('x', 'BOOLEAN')
    m.operation, m.solver, m.object = 'INTERSECT', 'EXACT', b
    dg = C.evaluated_depsgraph_get()
    bm = bmesh.new()
    bm.from_object(tmp, dg)
    v = abs(bm.calc_volume())
    bm.free()
    me = tmp.data
    bpy.data.objects.remove(tmp)
    bpy.data.meshes.remove(me)
    return v


ov = overlap(lo, up)
check(f'the screw fits: the neck and the hole overlap nowhere (overlap volume {ov:.6f})', ov < 1e-5, ov)
up.location.z -= 0.05                             # (screwed 5 cm too deep: the neck into the hole's end)
ov0 = overlap(lo, up)
up.location.z += 0.05
check(f'... (the check does see an overlap: the upper layer pushed down 5 cm overlaps {ov0:.5f})', ov0 > 1e-3)

# live
C.view_layer.objects.active = lo
st.thread_size = 0.4
rn = np.hypot(*world(lo)[world(lo)[:, 2] > 0.6 + 1e-4][:, :2].T)
check('Thread Size live: the neck thinner (both layers rebuilt)', abs(rn.max() - 0.2) < 2e-3 and stats(up)[0] == 0)
st.pitch = 0.1
st.thread_depth = 0.04
check('Pitch / Thread Depth live: still closed', stats(lo)[0] == 0 and stats(up)[0] == 0)
st.layers = 3
obs = cy.layers_of(S, cy.stack_of(lo))
check('Layers 3: a third layer added (the middle one: a hole below, a neck above)', len(obs) == 3 and
      all(stats(o)[0] == 0 and stats(o)[1] > 0 for o in obs))
st.wall = 0.06
nm_vol = [stats(o) for o in obs]
check(f'Wall 0.06: the layers hollow, still closed ({nm_vol})', all(n == 0 and v > 0 for n, v in nm_vol) and
      sum(v for _n, v in nm_vol) < math.pi * 0.25 * 1.2 * 0.8)
st.gap = 0.3
check('Gap: the layers pulled apart', abs(world(obs[1])[:, 2].min() - (0.4 + 0.3)) < 1e-4)
st.thread = False
rn = [np.hypot(*world(obs[0])[world(obs[0])[:, 2] > 0.4 + 1e-4][:, :2].T)]
check('Thread off: a plain peg (one radius)', np.ptp(rn[0][rn[0] > 0.19]) < 1e-4 and stats(obs[0])[0] == 0)
st.layers = 1
obs = cy.layers_of(S, cy.stack_of(obs[0]))
check('Layers 1: one cylinder (the other layers taken away)', len(obs) == 1 and stats(obs[0])[0] == 0)
bpy.ops.mch.cylinder_plain()
check('Make Plain: a plain mesh (no longer a cylinder stack)', not cy.stack_of(obs[0]))
st.diameter = 2.0
check('... the sliders leave it alone', abs(np.hypot(*world(obs[0])[:, :2].T).max() - 0.5) < 1e-3)
summary()
