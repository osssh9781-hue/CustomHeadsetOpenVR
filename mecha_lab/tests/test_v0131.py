"""0.13.1 Station Primitive: left/right bending, Tight / Fold / Band styles, profile per
station (morph), Left = Right, station handles (placement + value accessors), insert,
direction buttons, Mirror on a live Station Primitive."""
import math
import sys

from _harness import bpy, bmesh, check, fresh, non_manifold, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import mirror_tools as mt, station_gizmos as sg, station_primitive as sp, station_sweep as ss

S = ss.station


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
    return bm


# --- sideways bending ------------------------------------------------------
r = ss.build(dict(kind='ROUNDED', stations=[S(), S(length=1.0), S(length=1.0, bend_angle=60, bend_dir=90)]))
T = r['frames'][-1].T
check('bend direction 90 = sideways: the path turns right in the panel plane', abs(T.z) < 1e-6 and T.x > 0.8, tuple(T))
check('sideways bend keeps the panel flat', max(abs(v[2]) for v in r['verts']) < 0.051)
r = ss.build(dict(kind='ROUNDED', stations=[S(), S(length=1.0), S(length=1.0, bend_angle=60, bend_dir=-90)]))
check('bend direction -90 = left', r['frames'][-1].T.x < -0.8)
bm = mesh_of(r)
check('sideways fold stays a closed solid', sum(1 for e in bm.edges if not e.is_manifold) == 0)
bm.free()

# --- bend styles ---------------------------------------------------------------
up = ss.build(dict(kind='BOX', stations=[S(), S(length=1.0), S(length=1.0, bend_angle=90, bend_style='TIGHT')]))
z_max = max(v[2] for v in up['verts'])
check('Tight up-bend: almost a right angle (inner radius = thickness, no warning)', not up['warnings'] and
      up['ring_count'] > 4 and 0.99 < z_max < 1.2, (up['warnings'], z_max))
side = ss.build(dict(kind='BOX', stations=[S(), S(length=1.0), S(length=0.5, bend_angle=90, bend_dir=90,
                                                                       bend_style='TIGHT')]))
check('Tight sideways bend: radius = half the width (smallest without self-overlap)', not side['warnings'])
fold = ss.build(dict(kind='BOX', stations=[S(), S(length=1.0), S(length=1.0, bend_angle=90, bend_radius=0.5,
                                                                       bend_style='FOLD')]))
check('Fold style = sharp crease even if a radius is set', fold['ring_count'] == 4)
band = ss.build(dict(kind='BOX', stations=[S(), S(length=1.0), S(length=1.0, bend_angle=90, bend_radius=0.5,
                                                                       bend_style='BAND')]))
check('Band style = smooth arc with the radius', band['ring_count'] > 10)

# --- profile per station -------------------------------------------------------
counts = {len(ss.profile_loop(k, S(), 8, 'RAISED', 6)) for k in ss.KINDS}
check('every profile kind has the same vertex count (they can morph)', len(counts) == 1, counts)
spec = dict(kind='ROUNDED', res=8, stations=[S(), S(length=1.0), S(length=1.0, profile='ROUND', height_top=0.3,
                                                                      height_bot=0.3, interp='SMOOTH')])
r = ss.build(spec)
bm = mesh_of(r)
check('box at the start, round at the end: one closed solid', sum(1 for e in bm.edges if not e.is_manifold) == 0)
bm.free()
mid = ss.ring_loop('ROUNDED', dict(S(), _ka='BOX', _kb='ROUND', _kt=0.5), 8)
a = ss.profile_loop('BOX', S(), 8)
b = ss.profile_loop('ROUND', S(), 8)
check('the segment morphs: halfway ring = average of both profiles', all(abs(m[1] - (p[1] + q[1]) / 2) < 1e-9
                                                                         for m, p, q in zip(mid, a, b)))
r = ss.build(dict(kind='ROUNDED', stations=[S(), S(length=1.0, profile='POLYGON'), S(length=1.0)]))
check('polygon station between rounded ones builds', r['ring_count'] >= 3 and not r['warnings'])

# --- Blender -----------------------------------------------------------------
fresh()
mecha_lab.register()
C = bpy.context
bpy.ops.mch.station_create(preset='PANEL')
ob = C.active_object
p = ob.mch_station
p.active = 1
bpy.ops.mch.station_bend_dir(direction=-90.0)
st = p.stations[1]
check('Bend to Left button: direction -90 and a starting angle', st.bend_dir == -90.0 and st.bend_angle == 30.0)
check('...and the mesh bends left (stays flat)', min(v.co.x for v in ob.data.vertices) < -0.55 and
      max(abs(v.co.z) for v in ob.data.vertices) < 0.06)
st.bend_style = 'TIGHT'
st.bend_angle = 90
check('Tight 90 sideways: no warning', not p.warnings, p.warnings)
p.sym_lr = True
st.width_l = 0.3
xs = [v.co.x for v in ob.data.vertices]
check('Left = Right: right width follows the left value', p.warnings == '' and len(xs) > 0)
p.sym_lr = False
st.profile = 'ROUND'
check('profile per station rebuilds as one mesh', non_manifold(ob) == 0)
st.profile = 'INHERIT'
st.bend_style = 'AUTO'
st.bend_angle = 0
# insert keeps the shape (linear blending)
fresh()
mecha_lab.register()
C = bpy.context
bpy.ops.mch.station_create(preset='MULTI_BEND')
ob = C.active_object
end0 = Vector(sp.station_frames(ob)[-1][0])
n0 = len(ob.mch_station.stations)
bpy.ops.mch.station_insert(index=2)
end1 = Vector(sp.station_frames(ob)[-1][0])
check('Insert station (+ on a segment): one more station, the shape end stays put', len(ob.mch_station.stations) == n0 + 1
      and (end0 - end1).length < 1e-4 and ob.mch_station.active == 2, (end0, end1))
# handles
ob.mch_station.active = 3
h = sg.station_handles(ob)
check('handles: a dot per station, a + per segment, dials and arrows for the active one',
      len(h['dots']) == len(ob.mch_station.stations) and len(h['plus']) == len(ob.mch_station.stations) - 1 and
      all(k in h for k in ('bend', 'dir', 'length', 'width_r', 'width_l', 'height')))
fr = sp.station_frames(ob)
st = ob.mch_station.stations[3]
tip = h['length'].translation + h['length'].col[2].xyz.normalized() * st.length
check('length arrow: starts at the straight run, its value reaches the station', (tip - Vector(fr[3][0])).length < 1e-4)
bend_axis = h['bend'].col[2].xyz
check('bend dial turns around an axis across the path', abs(bend_axis.dot(Vector(fr[2][2]))) < 1e-6)
get, set_ = sg.make_accessors(ob.name, 3, 'bend_angle')
set_(math.radians(60))
check('bend dial value is in radians, stored in degrees', abs(st.bend_angle - 60) < 1e-4 and abs(get() - math.radians(60)) < 1e-6)
get, set_ = sg.make_accessors(ob.name, 3, 'bend_dir')
set_(math.radians(90))
check('direction dial sets the bend direction', abs(st.bend_dir - 90) < 1e-4)
ob.mch_station.sym_lr = True
get, set_ = sg.make_accessors(ob.name, 3, 'width_r')
set_(0.7)
check('Left = Right: the right width handle edits the shared value', abs(st.width_l - 0.7) < 1e-6)
ob.mch_station.sym_lr = False
check('station handle gizmo group registered', 'bl_rna' in sg.MCH_GGT_station_handles.__dict__)
# mirror on a live station primitive
fresh()
mecha_lab.register()
C = bpy.context
bpy.ops.mch.station_create(preset='MULTI_BEND')
ob = C.active_object
C.scene.mch_mirror.space = 'LOCAL'
mod = mt.setup_mirror(ob, C.scene.mch_mirror, C.scene, (True, False, False), (False, False, False))
ob.mch_station.stations[2].bend_angle = 40
check('Mirror stays live on a Station Primitive while its stations are edited', ob.modifiers.get(mt.MOD_NAME) is not None
      and sp.is_live(ob))
r = bpy.ops.mch.mesh_mirror_apply()
check('Apply Mirror freezes the Station Primitive (the mirrored half is kept)', r == {'FINISHED'} and
      not sp.is_live(ob) and mt.MOD_NAME not in ob.modifiers)
n = len(ob.data.vertices)
ob.mch_station.stations[2].bend_angle = 10
check('...later edits no longer rebuild over it', len(ob.data.vertices) == n)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
