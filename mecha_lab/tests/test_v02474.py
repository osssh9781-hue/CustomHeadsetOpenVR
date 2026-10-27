"""0.24.54 Path Move Extend, Area Brush (the viewport default): only the surface under the brush is pulled out (the
faces round the grab are cut to the brush - Ball = octagon, Box = square - and that patch runs along the path);
Area Section is the old whole cross-section.  The middle-click gate never holds up a 3D mouse / trackpad."""
import inspect
import json

from _harness import bpy, check, fresh, non_manifold, summary
import bmesh
import numpy as np
from mathutils import Vector

import mecha_lab
from mecha_lab import concept_move as cm, mecha_menu as mm, path_sweep as ps

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene


def plate(name, cuts, loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = C.active_object
    o.name = name
    o.scale = (2, 1, 0.3)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if cuts:
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide(number_cuts=cuts)
        bpy.ops.object.mode_set(mode='OBJECT')
    return o


def volume(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    v = bm.calc_volume(signed=True)
    bm.free()
    return v


OFFS = [[0, 0, 0.05 * i] for i in range(8)] + [[0.05 * i, 0, 0.35] for i in range(1, 6)]
check('Path Move has Area Brush (default) / Section; the operator keeps Section for scripts',
      S.mch_concept.path_area == 'BRUSH' and bpy.ops.mch.concept_path.get_rna_type().properties['area'].default == 'SECTION')
check('Brush outline: 8 sides square to the drag across the surface; pulled straight out it lines up with the axes',
      len(ps.brush_planes(Vector((0, 0, 1)), Vector((1, 0, 0.3)), 0.1)) == 8
      and abs(ps.brush_planes(Vector((0, 0, 1)), Vector((0, 0, 1)), 0.1, 4)[0][1].dot(Vector((1, 0, 0)))) > 0.999)

for cuts, shape in ((0, 'SPHERE'), (12, 'SPHERE'), (30, 'BOX')):
    o = plate(f'P{cuts}', cuts)
    v0 = volume(o)
    res = bpy.ops.mch.concept_path('EXEC_DEFAULT', method='EXTEND', area='BRUSH', shape=shape,
                                   objects=json.dumps([o.name]), grab_point=(0.2, 0.1, 0.15), grab_normal=(0, 0, 1),
                                   offsets=json.dumps(OFFS), radius=0.1, size=1.0)
    co = cm.read_coords(o.data)
    up = co[co[:, 2] > 0.16]
    check(f'{cuts} cuts, {shape}: only a brush-wide column comes up (closed, outward, along the path)',
          res == {'FINISHED'} and non_manifold(o) == 0 and volume(o) > v0 and len(up)
          and abs(np.ptp(up[:, 1]) - 0.2) < 0.01 and co[:, 2].max() > 0.5,
          (non_manifold(o), round(volume(o) - v0, 4), float(np.ptp(up[:, 1])) if len(up) else None))
    rest = co[(co[:, 2] <= 0.16) & (np.abs(co[:, 0] - 0.2) > 0.3)]
    check(f'{cuts} cuts: the rest of the plate stays where it was', len(rest) and np.abs(rest[:, 2]).max() <= 0.1501)

o = plate('Sec', 12, (5, 0, 0))
info_b = ps.analyse(o.data, Vector((0.2, 0.1, 0.15)), Vector((0, 0, 1)), 0.1)
info_s = ps.analyse(o.data, Vector((0.2, 0.0, 0.0)), Vector((1, 0, 0)))     # a plane across the plate
span = lambda info: max((Vector(q) - info['centre']).length for q in info['loop'])
check('The drag preview reads the same patch (Brush) - much smaller than the section', info_b['area'] == 'BRUSH'
      and info_s['area'] == 'SECTION' and span(info_b) < 0.2 and span(info_s) > 0.5, (span(info_b), span(info_s)))
res = bpy.ops.mch.concept_path('EXEC_DEFAULT', method='EXTEND', area='BRUSH', objects=json.dumps(['Sec']),
                               grab_point=(0.2, 0.1, 0.15), grab_normal=(0, 0, 1), offsets=json.dumps(OFFS),
                               radius=0.1, size=1.0, auto_apply=False)
rec = cm.recorded_moves(o)
check('Auto Apply off: the brush size is remembered for the replay', res == {'FINISHED'} and len(rec) == 1
      and abs(rec[0]['radius'] - 0.1) < 1e-6, (res, rec[:1]))
cm.drop_base(o)
src = inspect.getsource(cm.MCH_OT_concept_path.modal)
check('From the viewport: the scene Area, the shape and the brush (in the part\'s own size) go to Extend',
      'self.area, self.shape = st.path_area, st.shape' in src and 'local_radius' in src)

# 0.24.55 the whole-section way close at hand
import types
from mecha_lab import key_legend as kl, quick_hud as qh
S.mch_concept.path_area = 'BRUSH'
dropped = []
fake = types.SimpleNamespace(info={'loop': []}, _drop_preview=lambda: dropped.append(1), _header=lambda c: None,
                             _preview=lambda c: None)
cm.MCH_OT_concept_path._toggle_area(fake, C)
check('Tab while dragging: Brush <-> Whole, the grab is read again', S.mch_concept.path_area == 'SECTION'
      and fake.info is None and dropped == [1])
cm.MCH_OT_concept_path._toggle_area(fake, C)
check('... and back', S.mch_concept.path_area == 'BRUSH')
check('The old way is called Whole; Tab is in the modal', bpy.types.MCH_PG_concept.bl_rna.properties['path_area']
      .enum_items['SECTION'].name == 'Whole' if hasattr(bpy.types, 'MCH_PG_concept') else
      dict((i[0], i[1]) for i in cm.AREA_ITEMS)['SECTION'] == 'Whole')
S.mch_settings.mch_active_tool = 'CPATH'
check('Quick HUD / Mecha Menu settings: Brush / Whole next to the method; the key legend tells Tab',
      ('path_area' in [p for _d, p in qh.items(C)]) and any('Tab' in ln for ln in kl.lines('CPATH'))
      and "'TAB'" in inspect.getsource(cm.MCH_OT_concept_path.modal))

# the middle-click gate passes a 3D mouse on
gate = mm.MCH_OT_mecha_mmb_gate.modal
fake = lambda t, v='NOTHING': type('E', (), {'type': t, 'value': v, 'mouse_x': 0, 'mouse_y': 0})()
op = type('Op', (), {'x0': 0, 'y0': 0, 'limit': 5})()
check('Middle-click gate: a 3D mouse (NDOF) or trackpad event ends it and goes on; other events pass through',
      gate(op, C, fake('NDOF_MOTION')) == {'FINISHED', 'PASS_THROUGH'}
      and gate(op, C, fake('TRACKPADPAN')) == {'FINISHED', 'PASS_THROUGH'}
      and gate(op, C, fake('A', 'PRESS')) == {'PASS_THROUGH'})
summary()
