"""0.24.281 Quad Remesh follows the flow (user: "리메시를 흐름을 따라가면서", "엣지 감지 정도 조절 - 면 각도가 넓은
부분은 덜 잡히게", "서브디비전도 추가").  Flow 0 = the result before 0.24.281 (same points); Flow 1 on a cylinder with
rounded caps (no hard edge: every fold below the 30-degree Hard Edges) lines the quads up with its axis / rings; the
Subdivision setting adds a creased Subdivision Surface; the three settings are on every Quad Remesh panel."""
import math

import numpy as np

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import mesh_tools as mt, panel_capture as pc, quad_field as qf, quad_remesh as qr, zb_ui as zu

mecha_lab.register()
fresh()
C = bpy.context


def cyl():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.6, depth=2.0, vertices=64)
    o = C.active_object
    m = o.modifiers.new('b', 'BEVEL')
    m.width, m.segments, m.limit_method = 0.25, 8, 'ANGLE'
    bpy.ops.object.modifier_apply(modifier='b')
    o.data.remesh_voxel_size = 0.02
    bpy.ops.object.voxel_remesh()
    return o


def dev(o):
    """Each edge's angle off the nearest of: along the rings / across them (degrees)."""
    me = o.data
    V = np.array([v.co for v in me.vertices])
    E = np.array([e.vertices for e in me.edges])
    d = V[E[:, 1]] - V[E[:, 0]]
    d /= np.linalg.norm(d, axis=1)[:, None]
    mid = (V[E[:, 1]] + V[E[:, 0]]) / 2
    circ = np.stack([-mid[:, 1], mid[:, 0], 0 * mid[:, 0]], 1)
    circ /= np.maximum(np.linalg.norm(circ, axis=1), 1e-9)[:, None]
    c = np.abs((d * circ).sum(1))
    return np.degrees(np.minimum(np.arccos(np.clip(c, 0, 1)), np.arcsin(np.clip(c, 0, 1))))


def pts(o):
    return np.array([v.co for v in o.data.vertices], np.float32)


check('engine v3 loaded (flow)', qf.available() and qf.VERSION == 3)
o = cyl()
qf.remesh_object(o, 2500)
p_default = pts(o)
o = cyl()
qf.remesh_object(o, 2500, flow=0.0)
a0 = dev(o)
check('Flow 0 = the call without Flow (the result as before 0.24.281)', np.array_equal(p_default, pts(o)),
      (len(p_default), len(o.data.vertices)))
o = cyl()
msg = qf.remesh_object(o, 2500, flow=1.0)
a1 = dev(o)
quads = sum(1 for p in o.data.polygons if len(p.vertices) == 4) / len(o.data.polygons)
check('Flow 1: quads along the cylinder\'s rings / axis (mean angle off much smaller, many more within 5 degrees)',
      a1.mean() < 0.6 * a0.mean() and np.mean(a1 < 5) > np.mean(a0 < 5) + 0.25,
      (round(a0.mean(), 2), round(a1.mean(), 2), round(np.mean(a0 < 5), 2), round(np.mean(a1 < 5), 2)))
check('... still mostly quads, about the asked count', quads > 0.9 and 2000 < len(o.data.polygons) < 3200,
      (quads, len(o.data.polygons), msg))

zb = C.scene.mch_zb
check('defaults: Flow 1, Hard Edges 30 degrees (Subdivision its own button, 2 levels)', abs(zb.qr_flow - 1.0) < 1e-6
      and zb.qr_subd == 2 and abs(math.degrees(zb.qr_angle) - 30.0) < 1e-4)

# Subdivision (0.24.286: its own button, not part of Quad Remesh)
o = cyl()
for x in list(C.selected_objects):
    x.select_set(False)
o.select_set(True)
C.view_layer.objects.active = o
zb.qr_target = 1.0
msg = mt.run_one(C, o, zb, 'QUAD_REMESH')
check('Quad Remesh no longer adds a Subdivision', qf.subdiv_modifier(o) is None, msg)
r = bpy.ops.mch.quad_subdiv()
m = qf.subdiv_modifier(o)
check('Subdivision button: a Subdivision Surface (the setting\'s 2 levels, render 2, creases used)',
      r == {'FINISHED'} and m is not None and m.levels == 2 and m.render_levels == 2 and m.use_creases, m)
dg = C.evaluated_depsgraph_get()
nev = len(o.evaluated_get(dg).data.polygons)
check('... the shape is subdivided (16x the faces), the mesh itself stays the remesh', nev >= 15 * len(o.data.polygons),
      (nev, len(o.data.polygons)))
zb.qr_subd = 3
bpy.ops.mch.quad_subdiv()
check('... again with 3: the same modifier, 3 levels', qf.subdiv_modifier(o).levels == 3
      and sum(1 for x in o.modifiers if x.type == 'SUBSURF') == 1)
r = bpy.ops.mch.quad_subdiv(levels=0)
check('Subdivision 0: the modifier taken off', r == {'FINISHED'} and qf.subdiv_modifier(o) is None)
zb.qr_subd = 2
o.modifiers.new('Mine', 'SUBSURF')
qf.set_subdiv(o, 0)
check('... the user\'s own Subdivision is never touched', o.modifiers.get('Mine') is not None)

# in the background (a big part, the shelf's Background toggle): Flow and Subdivision go along
import os
import time
os.environ['MECH_BG_FORCE'] = '1'        # (headless Blender runs inline unless asked)
from mecha_lab import bg_jobs
if bg_jobs.can_run():
    o = cyl()
    o.name = 'BgCyl'
    zb.bg_jobs, zb.qr_target, zb.qr_flow = True, 2.5, 1.0
    msg = mt.run_one(C, o, zb, 'QUAD_REMESH')
    t = time.perf_counter()
    while bg_jobs.busy(o) and time.perf_counter() - t < 300:
        time.sleep(0.5)
    bg_jobs.poll()
    a_bg = dev(o)
    m = qf.subdiv_modifier(o)
    check('Background: the result follows the flow too (no Subdivision added)',
          'started in the background' in msg and a_bg.mean() < 0.6 * a0.mean() and m is None,
          (msg[:60], round(a_bg.mean(), 2), bg_jobs.last_message(o)[:120]))
    zb.bg_jobs = False
else:
    check('Background: the worker can run here', False)

# the panels
for name, drawer in (('right-click Quad Remesh', qr.draw), ('Mesh Tools', mt.draw)):
    root = pc.capture(drawer, C)
    props = {x.prop for x in pc.walk(root) if x.kind == 'prop'} if root is not None else set()
    check(f'{name} panel: Hard Edges, Flow (Subdivision not in Quad any more)', {'qr_angle', 'qr_flow'} <= props
          and 'qr_subd' not in props, sorted(props))
bpy.ops.object.mode_set(mode='SCULPT')
root = pc.capture(zu.draw_tool_shelf, C)
props = {x.prop for x in pc.walk(root) if x.kind == 'prop'} if root is not None else set()
check('ZBrush shelf: Hard Edges, Flow', {'qr_angle', 'qr_flow'} <= props, sorted(props))
bpy.ops.object.mode_set(mode='OBJECT')
summary()
