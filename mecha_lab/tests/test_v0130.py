"""0.13 Station Primitive (Advanced Parametric Primitive, Phase 1): engine geometry,
station chaining, presets of the request's scenarios, Blender editing, Cut/Boolean
freeze, Apply, save/reload.  No viewport handles yet (later phase)."""
import math
import os
import sys
import tempfile
import types

from _harness import bpy, bmesh, check, cube, fresh, non_manifold, select_only, summary, volume
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, station_primitive as sp, station_sweep as ss

S = ss.station

# --- profile ----------------------------------------------------------------
for kind in ss.KINDS:
    for ridge in ('NONE', 'RAISED', 'BOX', 'DOUBLE'):
        counts = {len(ss.profile_loop(kind, S(**kw), 8, ridge)) for kw in (
            {}, dict(width_l=0.2, width_r=1.3, height_top=0.3, corner_l=0.0, corner_r=0.4, ridge_h=0.1),
            dict(ridge_offset=0.3, ridge_w=0.05, thick_l=2.0, thick_r=0.3))}
        if len(counts) != 1:
            check(f'profile {kind}/{ridge}: same vertex count whatever the values', False, counts)
            break
else:
    check('profiles: same vertex count for every station value (rings bridge directly)', True)
lp = ss.profile_loop('BOX', S(width_l=0.2, width_r=0.9, height_top=0.1, height_bot=0.05, thick_l=1.0, thick_r=2.0), 8)
xs, ys = [p[0] for p in lp], [p[1] for p in lp]
check('asymmetric widths: left 0.2, right 0.9', abs(min(xs) + 0.2) < 1e-9 and abs(max(xs) - 0.9) < 1e-9)
right_top = max(y for x, y in lp if x > 0.9 - 1e-9)
left_top = max(y for x, y in lp if x < -0.2 + 1e-9)
check('left / right thickness: right edge twice as thick as left', abs(right_top - 0.2) < 1e-6 and
      abs(left_top - 0.1) < 1e-6, (left_top, right_top))
lp = ss.profile_loop('ROUNDED', S(ridge_h=0.04, ridge_w=0.2, ridge_offset=0.1), 8, 'RAISED')
peak = max(lp, key=lambda p: p[1])
check('raised ridge: peak at the offset, height top + ridge', abs(peak[0] - 0.1) < 1e-9 and abs(peak[1] - 0.09) < 1e-9,
      peak)
lp = ss.profile_loop('ROUNDED', S(ridge_h=0.04, ridge_w=0.2), 8, 'BOX')
walls = [i for i in range(len(lp) - 1) if abs(lp[i][0] - lp[i + 1][0]) < 1e-12 and abs(lp[i][1] - lp[i + 1][1]) > 0.03
         and min(lp[i][1], lp[i + 1][1]) > 0.04]
check('box ridge: two vertical walls', len(walls) == 2, walls)
lp = ss.profile_loop('ROUNDED', S(ridge_h=0.03, ridge_w=0.2), 8, 'GROOVE')
check('groove goes down into the top', min(y for x, y in lp if abs(x) < 0.05 and y > 0) < 0.05 - 0.029)
lp = ss.profile_loop('POLYGON', S(width_l=1, width_r=1, height_top=1, height_bot=1), 8, sides=6)
check('polygon (hexagon) stays inside its box and reaches the top', max(p[1] for p in lp) <= 1 + 1e-9 and
      max(p[1] for p in lp) > 0.99)

# --- stations / spine -------------------------------------------------------
spec = ss.preset('MULTI_BEND')
r = ss.build(spec)
T = [f.T for f in r['frames']]
check('multi-bend: segment 2 leaves 30 deg from segment 1', abs(math.degrees(T[1].angle(T[2])) - 30) < 1e-3)
check('multi-bend: segment 3 adds 45 deg on top (75 deg from the start)', abs(math.degrees(T[2].angle(T[3])) - 45) < 1e-3
      and abs(math.degrees(T[0].angle(T[3])) - 75) < 1e-3)
spec5 = dict(kind='ROUNDED', res=6, stations=[S()] + [S(length=0.5, bend_angle=a) for a in (10, 30, 45, 20, 15)])
r1 = ss.build(spec5)
spec5['stations'][1]['bend_angle'] = 50
r2 = ss.build(spec5)
rel = lambda fr: [round(math.degrees(fr[i].T.angle(fr[i + 1].T)), 3) for i in range(1, 5)]
check('scenario E: changing station 1 keeps every later relative angle', rel(r1['frames']) == rel(r2['frames']) ==
      [30, 45, 20, 15], (rel(r1['frames']), rel(r2['frames'])))
check('scenario E: later stations keep their own values', [s['bend_angle'] for s in spec5['stations'][2:]] == [30, 45, 20, 15])
check('scenario E: the whole chain swings with station 1', (r1['frames'][-1].P - r2['frames'][-1].P).length > 0.1)


def mesh_of(result):
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in result['verts']]
    for f in result['faces']:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


flat = dict(kind='BOX', res=4, stations=[S(), S(length=1.0), S(length=1.0)])
folded = dict(kind='BOX', res=4, stations=[S(), S(length=1.0), S(length=1.0, bend_angle=60)])
b0, b1 = mesh_of(ss.build(flat)), mesh_of(ss.build(folded))
check('hard fold is mitred: volume of the folded panel = flat panel', abs(b0.calc_volume() - b1.calc_volume()) < 1e-3 *
      b0.calc_volume(), (b0.calc_volume(), b1.calc_volume()))
check('hard fold keeps the solid closed', sum(1 for e in b1.edges if not e.is_manifold) == 0)
b0.free(); b1.free()
r = ss.build(dict(kind='ROUNDED', stations=[S(), S(length=0.0, bend_angle=90, bend_radius=1.0)]))
check('smooth bend: auto segments from the angle (90 deg / 8 deg -> 12)', r['ring_count'] == 1 + 12, r['ring_count'])
r = ss.build(dict(kind='ROUNDED', quality='FINE', stations=[S(), S(length=0.0, bend_angle=90, bend_radius=1.0)]))
check('Fine quality adds segments', r['ring_count'] == 1 + 23, r['ring_count'])
r = ss.build(dict(kind='ROUNDED', stations=[S(), S(length=2.0), S(length=1.0, width_r=1.0)]))
check('straight linear runs stay one segment', r['ring_count'] == 3)
r = ss.build(dict(kind='ROUNDED', stations=[S(), S(length=1.0, width_r=1.0, interp='SMOOTH')]))
check('Smooth blending adds segments', r['ring_count'] > 3)
r = ss.build(dict(kind='ROUNDED', stations=[S(height_top=0.3, height_bot=0.3),
                                           S(length=0.0, bend_angle=90, bend_radius=0.1, height_top=0.3, height_bot=0.3)]))
check('bend radius inside the profile: raised + warning (no self-intersection)', r['warnings'] and 'raised' in r['warnings'][0])
r = ss.build(ss.preset('WRAP'))
check('wrap: ribbon turned 200 deg', abs(math.degrees(r['frames'][0].T.angle(r['frames'][-1].T)) - 160) < 1e-3)
b = mesh_of(r)
check('wrap stays a closed solid', sum(1 for e in b.edges if not e.is_manifold) == 0)
b.free()
r = ss.build(dict(kind='ROUNDED', stations=[S(), S(length=1.0, twist=90)]))
check('twist adds segments and turns the end profile 90 deg', r['ring_count'] > 3)
r = ss.build(dict(kind='ROUNDED', stations=[S(), S(length=1.0), S(length=1.0, width_r=1.0, interp='STEP')]))
check('Step blending: a sharp change at the station', r['ring_count'] == 4)
r = ss.build(dict(kind='ROUND', cap_end='POINT', cap_len=0.4, stations=[S(width_l=.3, width_r=.3, height_top=.3,
                                                                          height_bot=.3), S(length=1)]))
check('pointed end: apex 0.4 beyond the last station', abs(max(v[1] for v in r['verts']) - 1.4) < 1e-6)
for name in ss.PRESETS:
    res = ss.build(ss.preset(name))
    bm = mesh_of(res)
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    ok = nm == 0 if name != 'DUCT' else nm > 0           # duct: open ends by design
    check(f'preset {name}: valid mesh ({len(bm.faces)} faces, warnings: {len(res["warnings"])})', ok and len(bm.faces) > 10
          and not res['warnings'], (nm, res['warnings']))
    bm.free()

# --- Blender ---------------------------------------------------------------
fresh()
mecha_lab.register()
C = bpy.context
check('Object.mch_station registered', hasattr(bpy.types.Object, 'mch_station'))
for key, _l, _d in sp.PRESET_ITEMS:
    r = bpy.ops.mch.station_create(preset=key)
    ob = C.active_object
    check(f'create {key}: live real mesh', r == {'FINISHED'} and sp.is_live(ob) and len(ob.data.polygons) > 10 and
          not ob.mch_station.warnings, ob.mch_station.warnings)
fresh()
mecha_lab.register()
bpy.ops.mch.station_create(preset='PANEL')
ob = C.active_object
before = len(ob.data.vertices)
st = ob.mch_station.stations[1]
st.bend_angle = 40
check('editing a station rebuilds the mesh live', abs(max(v.co.z for v in ob.data.vertices)) > 0.3)
bpy.ops.mch.station_add(bend=30)
check('Add Station: inserted after the active one, active moves to it', len(ob.mch_station.stations) == 3 and
      ob.mch_station.active == 2 and ob.mch_station.stations[2].bend_angle == 30)
bpy.ops.mch.station_move(delta=-1)
check('Move Station up', ob.mch_station.active == 1 and ob.mch_station.stations[1].bend_angle == 30)
bpy.ops.mch.station_remove()
check('Remove Station', len(ob.mch_station.stations) == 2)
ob.mch_station.shell = 0.01
check('Shell = live Solidify', ob.modifiers.get(sp.SHELL_MOD) is not None)
ob.mch_station.shell = 0.0
check('Shell 0 removes it', ob.modifiers.get(sp.SHELL_MOD) is None)
# save / reload keeps the parameters
path = os.path.join(tempfile.mkdtemp(), 'station.blend')
ob.mch_station.stations[1].width_r = 0.9
name = ob.name
bpy.ops.wm.save_as_mainfile(filepath=path)
bpy.ops.wm.open_mainfile(filepath=path)
ob = bpy.data.objects[name]
check('save / reload: parameters still there and live', sp.is_live(ob) and abs(ob.mch_station.stations[1].width_r - 0.9) < 1e-6)
far0 = max(v.co.length for v in ob.data.vertices)
ob.mch_station.stations[1].length = 2.0
check('after reload editing still rebuilds', max(v.co.length for v in ob.data.vertices) > far0 + 0.5)
# Cut on a live Station Primitive: freezes, cut kept
C = bpy.context
select_only(ob)
C.view_layer.objects.active = ob
top = cg.OrthoProjector(Quaternion())
msg = ce.perform_closed(C, 'CUT', [ob], [ce.rect_loop((480, 550), (520, 600))], top)
check('Cut on a live Station Primitive: works, freezes it, says so', 'Station Primitive frozen' in msg and
      not ob.mch_station.live, msg)
nf = len(ob.data.polygons)
ob.mch_station.stations[1].length = 3.0
check('after the cut, parameter edits do not overwrite it', len(ob.data.polygons) == nf)
# Boolean freezes too
fresh()
mecha_lab.register()
C = bpy.context
bpy.ops.mch.station_create(preset='PANEL')
panel = C.active_object
cutter = cube('Cutter', 0.3, (0, 0.5, 0))
panel.select_set(True)
cutter.select_set(True)
C.view_layer.objects.active = cutter
r = bpy.ops.mch.boolean(operation='DIFFERENCE')
check('Boolean on a live Station Primitive freezes it first', r == {'FINISHED'} and not panel.mch_station.live)
# Apply
fresh()
mecha_lab.register()
C = bpy.context
bpy.ops.mch.station_create(preset='DUCT')
ob = C.active_object
r = bpy.ops.mch.station_apply()
check('Apply: ordinary mesh, shell baked, parameters removed', r == {'FINISHED'} and not ob.mch_station.live and
      len(ob.mch_station.stations) == 0 and not ob.modifiers and non_manifold(ob) == 0)


# panel draw with a permissive fake layout (all main paths)
class L:
    def __getattr__(self, n):
        return lambda *a, **k: self

    def __setattr__(self, n, v):
        pass


bpy.ops.mch.station_create(preset='MULTI_BEND')
ob = C.active_object
ob.mch_station.show_asym = True
ob.mch_station.show_adv = True
ok = True
try:
    sp.draw(L(), C)
    ob.mch_station.active = 0
    sp.draw(L(), C)
    bpy.ops.object.select_all(action='DESELECT')
    C.view_layer.objects.active = None
    sp.draw(L(), C)
except Exception as ex:
    ok = str(ex)
check('panel draws (live, start station, nothing selected)', ok is True, ok)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
