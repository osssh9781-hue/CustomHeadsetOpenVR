"""0.24.154 (user: "방금 만든 그 툴에다가 내가 쉬프트 누르고 라쏘로 그리면 그 스탬프 베이스로 만들어 줄 수 있어? 그리블이랑
크리쳐 둘 다"): in Greeble Line and Scale Line, Shift + draw (the shared lasso shapes) makes a part from the outline -
a live Base Mesh (Flat / Chamfer / Bevel / Dome) or Creature Base Mesh (Puff / Ridge / Pillow) of it, as big as drawn,
beside the model, in the tool's parts list and ticked.  The outline given here in screen pixels through a fixed
front-view projector (the real Shift + drag: tests/gui/greeble_stamp_real_window.py)."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Euler

import mecha_lab
from mecha_lab import base_mesh, core_geometry as cg, cut_engine as ce, greeble_line as gl, tool_state as ts  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
body = C.active_object
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)   # 200 px = 1


def outline(points, cx=500, cy=500):
    return [[(cx + x, cy + y) for x, y in points]]


L_SHAPE = [(-40, -30), (40, -30), (40, -5), (0, -5), (0, 30), (-40, 30)]       # 0.4 x 0.3 on the sphere's front
mech, crea = gl.settings(S, 'MECH'), gl.settings(S, 'CREATURE')

# the stroke and the tools
items = {i.identifier for i in bpy.ops.mch.cut_stroke.get_rna_type().properties['mode'].enum_items}
km = {}
for tool_cls, mode in ((gl.MCH_TOOL_greeble, 'GREEBLE'), (gl.MCH_TOOL_scale_line, 'CGREEBLE')):
    km[mode] = [it for it in tool_cls.bl_keymap if it[0] == 'mch.cut_stroke' and it[1].get('shift')
                and dict(it[2]['properties']).get('mode') == mode]
check('Shift + left drag in Greeble Line / Scale Line = the shared lasso stroke in its own mode (the tool\'s lasso '
      'shapes remembered per tool)', {'GREEBLE', 'CGREEBLE'} <= items and all(len(v) == 1 for v in km.values())
      and {'GREEBLE', 'CGREEBLE'} <= ts.DRAW_TOOLS and {'GREEBLE', 'CGREEBLE'} <= ce.STAMP_MODES)

before = set(bpy.data.objects)
ob, msg = gl.make_stamp(C, outline(L_SHAPE), FRONT, 'MECH')
d = ob.dimensions
bm_ = __import__('bmesh').new()
bm_.from_mesh(ob.data)
closed = all(e.is_manifold for e in bm_.edges)
bm_.free()
check(f'Greeble Line stamp: the L drawn 0.4 x 0.3 -> a Chamfer Base Mesh {d.x:.3f} x {d.y:.3f}, {d.z:.3f} high (Stamp '
      f'Height 0.3 x the short side), closed', abs(d.x - 0.4) < 2e-3 and abs(d.y - 0.3) < 2e-3
      and abs(d.z - 0.09) < 1e-3 and closed and ob.mch_base.profile == 'CHAMFER' and set(bpy.data.objects) - before == {ob}, msg)
bb = [ob.matrix_world @ __import__('mathutils').Vector(c) for c in ob.bound_box]
check('... a live part (its sliders rebuild it) standing beside the model in "Greeble Stamps", its bottom flat on its '
      'own z = 0, the selection as it was', ob.mch_base.live and gl.is_stamp(ob)
      and [c.name for c in ob.users_collection] == ['Greeble Stamps'] and min(v.x for v in bb) > 1.0
      and abs(min(v.co.z for v in ob.data.vertices)) < 1e-6 and C.view_layer.objects.active == body
      and ob.name not in S.get(base_mesh.SESSION_KEY, []))
check('... in Greeble Line\'s parts list, ticked alone (Use Only the New Stamp); not in Scale Line\'s',
      gl.picked(mech) == [ob] and not any(it.ob == ob for it in crea.parts))

# every profile of each tool
shapes = {}
for kind, profiles in gl.STAMP_PROFILES.items():
    st = gl.settings(S, kind)
    for prof in profiles:
        st.stamp_profile = prof
        o, _m = gl.make_stamp(C, outline(L_SHAPE), FRONT, kind)
        bm_ = __import__('bmesh').new()
        bm_.from_mesh(o.data)
        ok = all(e.is_manifold for e in bm_.edges)
        bm_.free()
        shapes[(kind, prof)] = (o.mch_base.profile, round(o.dimensions.z, 4), len(o.data.polygons), ok)
mech_ok = all(shapes[('MECH', p)][0] == p and abs(shapes[('MECH', p)][1] - 0.09) < 1e-3 and shapes[('MECH', p)][3]
              for p in gl.STAMP_PROFILES['MECH'])
crea_ok = all(shapes[('CREATURE', p)][0] == p and 0.14 < shapes[('CREATURE', p)][1] < 0.19 and shapes[('CREATURE', p)][3]
              and shapes[('CREATURE', p)][2] < 4000 for p in gl.STAMP_PROFILES['CREATURE'])
check('every profile, closed: Greeble Line Flat / Chamfer / Bevel / Dome 0.09 high; Scale Line Puff / Ridge / Pillow '
      'a lump 0.09 each side of its middle, under 4000 faces (Resolution at most 12 for a part laid many times)',
      mech_ok and crea_ok, shapes)
st_c = gl.settings(S, 'CREATURE')
st_c.stamp_profile = 'CHAMFER'
check('a profile of the other tool falls back to the tool\'s own (Scale Line + Chamfer -> Puff)',
      gl.stamp_profile(st_c, 'CREATURE') == 'PUFF' and gl.stamp_profile(mech, 'MECH') == 'DOME')
coll = bpy.data.collections['Greeble Stamps']
zs = sorted(o.location.z for o in coll.objects)
check(f'stamps stand one above the other beside the model ({len(zs)} in "Greeble Stamps", none overlapping)',
      len(zs) == 5 and all(b - a > 0.09 for a, b in zip(zs, zs[1:])), [round(z, 3) for z in zs])

allst = [o for o in S.objects if gl.is_stamp(o)]
C.view_layer.update()


def box(o):
    bb = [o.matrix_world @ __import__('mathutils').Vector(c) for c in o.bound_box]
    return [min(v[i] for v in bb) for i in range(3)], [max(v[i] for v in bb) for i in range(3)]


hits = [(a_.name, b_.name) for i, a_ in enumerate(allst) for b_ in allst[i + 1:]
        if all(box(a_)[0][k] < box(b_)[1][k] and box(b_)[0][k] < box(a_)[1][k] for k in range(3))]
check(f'Greeble Line\'s and Scale Line\'s stamps ({len(allst)}) share the spot beside the model, one above the other, '
      f'none inside another (a Puff reaches below its middle too)', len(allst) == 8 and not hits, hits)

# mixing: Use Only the New Stamp off
mech.stamp_profile = 'BEVEL'
mech.stamp_alone = False
for it in mech.parts:
    it.use = True
n_before = len(gl.picked(mech))
o2, _m = gl.make_stamp(C, outline([(-30, -30), (30, -30), (30, 30), (-30, 30)]), FRONT, 'MECH')
check('Use Only the New Stamp off: the new stamp ticked with the others', len(gl.picked(mech)) == n_before + 1
      and gl.picked(mech)[-1] == o2)
mech.stamp_alone = True

# a line with a stamp; the stamp changed -> the line follows
for it in mech.parts:
    it.use = it.ob == ob
caster = gl._caster(C, body)
pts, nrm = [], []
for x in np.linspace(-0.7, 0.7, 70):
    h = caster.ray_cast((x, -3.0, 0.1), (0.0, 1.0, 0.0))
    if h:
        pts.append(tuple(h[0]))
        nrm.append(tuple(h[1]))
line = gl.new_line(C, body, np.array(pts), np.array(nrm), gl.picked(mech), mech)
n = gl.rebuild(line, C, caster)


def inst_heights(ln):
    dg = C.evaluated_depsgraph_get()
    return [round(i.object.dimensions.z, 4) for i in dg.object_instances if i.is_instance and i.parent
            and i.parent.original == ln]


h0 = inst_heights(line)
ob.mch_base.height = 0.18
from mecha_lab import live_queue  # noqa: E402
live_queue.flush()
C.view_layer.update()
h1 = inst_heights(line)
check(f'a Greeble Line with the stamp: {n} along 1.4 (a 0.4 part, Gap 0.1); the stamp\'s Height 0.09 -> 0.18: every one '
      f'on the line follows', gl.line_parts(line) == [ob] and n >= 3 and h0 and all(abs(v - 0.09) < 1e-3 for v in h0)
      and h1 and all(abs(v - 0.18) < 1e-3 for v in h1), (h0[:3], h1[:3]))
for o in C.selected_objects:
    o.select_set(False)
line.select_set(True)
C.view_layer.objects.active = line
r = bpy.ops.mch.greeble_apply()
check(f'Apply: real geometry ({len(line.data.polygons)} faces), the stamp kept', 'FINISHED' in r
      and not gl.is_line(line) and len(line.data.polygons) == n * len(ob.data.polygons) and ob.name in bpy.data.objects)

# too small / not closed
msgs = []
n_obs = len(bpy.data.objects)
for tiny in ([(0, 0), (1, 0), (1, 1)], [(0, 0), (5, 0), (5, 5), (0, 5)]):     # (a dot; 5 x 5 px)
    try:
        gl.make_stamp(C, outline(tiny), FRONT, 'MECH')
        msgs.append(None)
    except cg.CutError as ex:
        msgs.append(str(ex))
check('an outline too small to make a part (a dot, 5 x 5 px): a message, nothing made', all(msgs)
      and len(bpy.data.objects) == n_obs, msgs)
summary()
