"""0.24.95 Tire & Wheel (user: "타이어 만드는 제너레이터도 만들어 줘, 내가 디자인할 수 있게 - 바퀴에 맞는 비율의 원기둥을
소환하고 거기에 어레이로 내가 그 타이어 위에 그린 메쉬를 돌려 주고, 휠 부분을 따로 또 같은 방식으로"):

* Summon Tire: a tire-proportioned ring at the 3D cursor (its axle X): the preset's diameter / width, the rim hole, a
  closed surface; the sliders change the selected tire at once; presets
* Summon Wheel (the tire selected): fits its rim hole, put in it (a child of it); Barrel = an open rim + a hub, Disc
* Array Around: a piece drawn on the tread repeated round the axle - Count copies spread all round, the piece where
  it was drawn; an edit of the piece shows on every copy; Count live; Mirror Across + Stagger (the other half turned
  round the axle: left / right alternating, live, its faces the right way out); the tire moved / turned: they go
  with it, still round the axle; a spoke on the wheel the same; Apply (real mesh), Remove
* the Shapes page: the Tire & Wheel section"""
import math

import numpy as np
from _harness import bmesh, bpy, check, fresh, summary
from mathutils import Vector  # noqa: E402

import mecha_lab
from mecha_lab import random_shapes as rs, tire_gen as tg

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
st = S.mch_tire
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)


def ev_co(ob):
    """The evaluated mesh's points in the world (the modifiers on)."""
    dg = C.evaluated_depsgraph_get()
    e = ob.evaluated_get(dg)
    me = e.to_mesh()
    out = np.array([(ob.matrix_world @ v.co)[:] for v in me.vertices])
    e.to_mesh_clear()
    return out


def closed(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    ok = all(len(e.link_faces) == 2 for e in bm.edges)
    bm.free()
    return ok


S.cursor.location = (0.0, 0.0, 0.0)
st.preset = 'CAR'
r = bpy.ops.mch.tire_add(kind='TIRE')
tire = C.active_object
co = np.array([v.co[:] for v in tire.data.vertices])
rad = np.hypot(co[:, 1], co[:, 2])
D, W, rr = tg.PRESETS['CAR'][1:4]
check('Summon Tire (Car): a ring at the 3D cursor, its axle X - the diameter / width of the preset, the rim hole in '
      'it, a closed surface', r == {'FINISHED'} and tg.kind_of(tire) == 'TIRE' and abs(rad.max() * 2 - D) < 1e-3
      and abs(np.ptp(co[:, 0]) - W * D) < 1e-3 and abs(rad.min() - rr * D / 2) < 1e-3 and closed(tire),
      [round(float(x), 3) for x in (rad.max() * 2, np.ptp(co[:, 0]), rad.min())])
st.diameter = 0.9
co = np.array([v.co[:] for v in tire.data.vertices])
check('... the Diameter slider changes the selected tire at once', abs(np.hypot(co[:, 1], co[:, 2]).max() * 2 - 0.9)
      < 1e-3)
st.preset = 'BIKE'
co = np.array([v.co[:] for v in tire.data.vertices])
check('... a preset (Bike): thin, the proportions at once', np.ptp(co[:, 0]) < 0.1 * np.ptp(co[:, 1]),
      round(float(np.ptp(co[:, 0]) / np.ptp(co[:, 1])), 3))
st.preset = 'CAR'

st.wheel_style = 'BARREL'
r = bpy.ops.mch.tire_add(kind='WHEEL')
wheel = C.active_object
wc = np.array([(tire.matrix_world.inverted() @ (wheel.matrix_world @ v.co))[:] for v in wheel.data.vertices])
wr = np.hypot(wc[:, 1], wc[:, 2])
check('Summon Wheel (the tire selected): fits its rim hole (its flange just over it), in the tire (a child of it); '
      'Barrel: an open rim + a hub', r == {'FINISHED'} and tg.kind_of(wheel) == 'WHEEL' and wheel.parent == tire
      and abs(wr.max() - rr * D / 2 * 1.05) < 2e-3 and np.ptp(wc[:, 0]) < W * D
      and ((wr > rr * D / 2 * 0.3) & (wr < rr * D / 2 * 0.85)).sum() == 0,
      [round(float(wr.max()), 3), round(rr * D / 2, 3)])

# a tread block drawn on the tread (top of the tire)
bpy.ops.object.select_all(action='DESELECT')
R = D / 2
bpy.ops.mesh.primitive_cube_add(size=0.04, location=(0.05, 0.0, R + 0.01))
piece = C.active_object
before = ev_co(piece).mean(0)
tire.select_set(True)
C.view_layer.objects.active = tire
piece.select_set(True)
st.count = 24
st.mirror = False
r = bpy.ops.mch.tire_array()
pts = ev_co(piece)
ang = np.degrees(np.arctan2(pts[:, 2], pts[:, 1])) % 360
groups = sorted({round(a / 15) % 24 for a in ang})
first = pts[:8].mean(0)
check('Array Around: the tread block 24 times round the axle (copies all round, each 15 degrees on), the block where '
      'it was drawn, a child of the tire', r == {'FINISHED'} and len(pts) == 24 * 8 and len(groups) == 24
      and np.linalg.norm(first - before) < 1e-4 and piece.parent == tire and piece.get(tg.ARR) == tire.name,
      (len(pts), len(groups), round(float(np.linalg.norm(first - before)), 6)))
for v in piece.data.vertices:                     # (an edit of the piece: taller)
    if v.co.z > 0:
        v.co.z += 0.02
piece.data.update()
pts2 = ev_co(piece)
r2 = np.hypot(pts2[:, 1], pts2[:, 2])
check('... an edit of the piece shows on every copy at once (all 24 taller)', abs(r2.max() - (R + 0.03 + 0.02)) < 2e-3
      and np.allclose(np.sort(r2)[-24:], r2.max(), atol=2e-3), round(float(r2.max()), 4))
st.count = 12
pts = ev_co(piece)
check('... Count 12: twelve copies, 30 degrees apart (live)', len(pts) == 12 * 8, len(pts))
st.mirror = True
pts = ev_co(piece)
check('... Mirror Across: the other half too (its mirror image across the middle of the tire)', len(pts) == 24 * 8
      and abs(pts[:, 0].min() + pts[:, 0].max()) < 1e-3, round(float(pts[:, 0].min() + pts[:, 0].max()), 5))


def offsets():
    """(the mirrored blocks' turn from the nearest drawn block, in degrees; faces pointing out on every block)"""
    dg = C.evaluated_depsgraph_get()
    e = piece.evaluated_get(dg)
    me = e.to_mesh()
    mw = piece.matrix_world
    vs = np.array([(mw @ v.co)[:] for v in me.vertices])
    blocks = vs.reshape(-1, 8, 3)
    cen = blocks.mean(1)
    ang = np.degrees(np.arctan2(cen[:, 2], cen[:, 1])) % 360
    right, left = ang[cen[:, 0] > 0], ang[cen[:, 0] < 0]
    off = [min(((x - y) % 360, (y - x) % 360) for y in right)[0] for x in left]
    out = 0
    for f in me.polygons:
        b = f.vertices[0] // 8
        n = (mw.to_3x3() @ f.normal).normalized()
        c = mw @ f.center
        out += n.dot(c - Vector(cen[b])) > 0
    ok = out == len(me.polygons)
    e.to_mesh_clear()
    return off, ok


off, ok = offsets()
check('... Stagger 0.5 (default): the other half turned half a step - left and right alternating (15 degrees on at '
      'Count 12), its faces pointing out (not inside out)', len(off) == 12 and all(abs(o - 15.0) < 0.05 for o in off)
      and ok, (sorted({round(o, 2) for o in off}), ok))
st.stagger = 0.0
off0, ok0 = offsets()
st.stagger = 0.2
off2, ok2 = offsets()
check('... the Stagger slider, live: 0 side by side (0 degrees), 0.2 a little on (6 degrees)',
      all(abs(o) < 0.05 for o in off0) and all(abs(o - 6.0) < 0.05 for o in off2) and ok0 and ok2,
      (sorted({round(o, 2) for o in off0}), sorted({round(o, 2) for o in off2})))
st.stagger = 0.5
st.count = 16
offc, _ok = offsets()
check('... Count 16 with the Stagger 0.5: still half a step (11.25 degrees)', all(abs(o - 11.25) < 0.05 for o in offc),
      sorted({round(o, 2) for o in offc}))
st.count = 12
st.mirror = False
tire.location = (1.0, 2.0, 0.5)
tire.rotation_euler = (0.0, 0.0, math.radians(30))
C.view_layer.update()
pts = ev_co(piece)
c, a = tg.axle(tire)
d = pts - np.array(c[:])
along = d @ np.array(a[:])
radial = np.linalg.norm(d - np.outer(along, np.array(a[:])), axis=1)
check('... the tire moved and turned: the copies go with it, still round its axle', abs(radial.max() - (R + 0.05))
      < 2e-3 and np.abs(along).max() < W * D / 2, round(float(radial.max()), 4))

# a spoke on the wheel, 5 round
bpy.ops.object.select_all(action='DESELECT')
wm = wheel.matrix_world
bpy.ops.mesh.primitive_cube_add(size=1.0, location=wm @ Vector((0.03, 0.0, rr * D / 4)))
spoke = C.active_object
spoke.scale = (0.02, 0.03, rr * D / 2 * 0.62)
spoke.rotation_euler = tire.rotation_euler
wheel.select_set(True)
C.view_layer.objects.active = wheel
spoke.select_set(True)
st.count = 5
r = bpy.ops.mch.tire_array()
pts = ev_co(spoke)
check('A spoke drawn on the wheel, Array Around (5): five spokes round the wheel\'s axle', r == {'FINISHED'}
      and len(pts) == 5 * 8 and spoke.parent == wheel, len(pts))

bpy.ops.object.select_all(action='DESELECT')
piece.select_set(True)
C.view_layer.objects.active = piece
st.mirror = True                                  # (with the other half, staggered)
r = bpy.ops.mch.tire_array_apply()
check('Apply: the copies real mesh - both halves (no modifier, the step and mirror empties, the node tree gone)',
      r == {'FINISHED'} and len(piece.data.vertices) == 24 * 8 and not piece.modifiers and not piece.get(tg.ARR)
      and not [o for o in piece.children if o.get(tg.STEP) or o.get(tg.MIRROR_KEY)]
      and not [g for g in bpy.data.node_groups if g.name.startswith('MCH Tire Mirror')])
st.mirror = False
bpy.ops.object.select_all(action='DESELECT')
spoke.select_set(True)
C.view_layer.objects.active = spoke
r = bpy.ops.mch.tire_array_remove()
check('Remove: the repeat taken away, the spoke as it was drawn', r == {'FINISHED'} and not spoke.modifiers
      and len(spoke.data.vertices) == 8 and len(ev_co(spoke)) == 8)

st.wheel_style = 'DISC'
bpy.ops.object.select_all(action='DESELECT')
S.cursor.location = (4.0, 0.0, 0.0)
r = bpy.ops.mch.tire_add(kind='WHEEL')
disc = C.active_object
check('Summon Wheel with no tire selected: a Disc wheel at the 3D cursor (the sliders\' rim size), one closed body',
      r == {'FINISHED'} and disc.parent is None and closed(disc)
      and abs(disc.matrix_world.translation.x - 4.0) < 1e-6)

its, _h = rs.page(C, 0.0, 276.0, 1.0)
heads = [i.label for i in its if i.kind == 'shead']
labels = [i.label for i in its if i.kind == 'tbtn']
check('The Shapes page: the Tire & Wheel section (presets, Summon Tire, Barrel / Disc, Summon Wheel, Array Around, '
      'Apply, Remove)', any(h.startswith('TIRE & WHEEL') for h in heads)
      and {'Car', 'Mech', 'Summon Tire', 'Summon Wheel', 'Barrel', 'Disc', 'Array Around', 'Apply', 'Remove'}
      <= set(labels), heads)
summary()
