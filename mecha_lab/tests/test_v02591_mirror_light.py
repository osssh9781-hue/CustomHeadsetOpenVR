"""0.24.177 (user: "플레이트 디테일4 할 때나 다른 것도 종종 미러가 개무거운데 이거 좀 더 가볍고 빠르게 못 하나"): the lean
mirror (Alt+X / Symmetry) sits last on a part, so each lean change re-made the whole part (Plate Detail 4: its Rough
Rim nodes, 196 k faces) and cut it on the plane - measured 0.35 - 0.5 s per change.  Now, while leaning:
- a part with other modifiers and a big result is shown by a still copy of itself (made once, the part hidden) that
  carries the mirror; the part gets its real mirror once, when the lean ends (Enter / click) - the same result as
  before; Esc: the part as it was, the copy gone;
- where the mirror cuts nothing (the part all on the kept side), the preview's mirrored copies are the same mesh
  placed reflected - a lean change only moves them; where it cuts, the copy carries the mirror;
- a light part (no other modifiers) is mirrored as before."""
import math
import time

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, light_copies as lc, mirror_tools as mt, plate_detail as pd  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)


class Reg:
    x = y = 0
    width, height = 1600, 900


def evaluated(ob):
    dg = C.evaluated_depsgraph_get()
    dg.update()
    me = lc.full(ob, dg).data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    P = co.reshape(-1, 3) @ np.array(ob.matrix_world.to_3x3()).T + np.array(ob.matrix_world.translation)
    return P, len(me.polygons)


def unselect():
    for o in C.selected_objects:
        o.select_set(False)


bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
hull = C.active_object
hull.name = 'Hull'
unselect()
loop = [[FRONT.to_screen(Vector((0.45 + 0.35 * math.cos(t), -3, 0.1 + 0.3 * math.sin(t))))
         for t in np.linspace(0, 2 * math.pi, 48, endpoint=False)]]
pd.perform(C, loop, FRONT, tool='DETAIL4')
det = C.active_object
_P, n_det = evaluated(det)
S.mch_mirror.bisect = True


def lean(keep, changes, cancel=False):
    """A lean on the selected parts: the X plane through the world centre, copies toward -X, then ``changes`` lean
    changes (Z, Y, back to X); its time and the number of times the part itself was re-made."""
    op = mt.MirrorLeanLogic()
    remade = [0]

    def count(_scene, depsgraph):
        for u in depsgraph.updates:
            if isinstance(u.id, bpy.types.Object) and u.id.original == keep and u.is_updated_geometry:
                remade[0] += 1
    bpy.app.handlers.depsgraph_update_post.append(count)
    t0 = time.perf_counter()
    try:
        op.start(C, Reg(), FRONT, (800, 450))
        op.point_at = lambda *_a: False                      # (the plain lean: not across the hull under the mouse)
        C.evaluated_depsgraph_get().update()
        for axes in ([False, False, True], [False, True, False], [True, False, False])[:changes]:
            op.axes, op.flips = list(axes), [False, False, False]
            op._apply_live(S)
            C.evaluated_depsgraph_get().update()
        lean_t = time.perf_counter() - t0
        if cancel:
            op.restore_all()
        else:
            op.finish_live(S)
        C.evaluated_depsgraph_get().update()
    finally:
        bpy.app.handlers.depsgraph_update_post.remove(count)
    return op, lean_t, remade[0]


unselect()
det.select_set(True)
C.view_layer.objects.active = det
keep_faces = mt.PREVIEW_FACES
mt.PREVIEW_FACES = 10 ** 12                                   # (the way it was: the mirror on the part all along)
_op, t_old, remade_old = lean(det, 3)
mt.PREVIEW_FACES = keep_faces
mt._restore(det, None)
op, t_new, remade = lean(det, 3)
P_new, n_new = evaluated(det)
bis = tuple(det.modifiers.get(mt.MOD_NAME).use_bisect_axis)
previews = [o for o in S.objects if o.get(mt.PREVIEW_KEY)]
check(f'Plate Detail 4 ({n_det:,} faces): leaned on a still copy - the detail itself re-made {remade} time(s) in the '
      f'lean and its end (start + 3 changes + the end: before {remade_old}), the lean {t_new:.2f} s (before {t_old:.2f} s); the copy gone '
      f'after ({len(previews)}), the detail shown and picked again', remade <= 2 and remade_old >= 4
      and t_new < t_old * 0.7 and not previews and not det.hide_viewport and det.select_get())
# the same result as the mirror set straight on the part (the way it was before)
mt._restore(det, None)
mt.setup_mirror(det, S.mch_mirror, S, (True, False, False), (False, False, False))
P_old, n_old = evaluated(det)
check(f'... its mirror the same as before ({n_new:,} faces, before {n_old:,}; the farthest point apart '
      f'{np.abs(np.sort(P_new, axis=0) - np.sort(P_old, axis=0)).max():.2e}), Bisect as set ({bis})',
      n_new == n_old and np.allclose(np.sort(P_new, axis=0), np.sort(P_old, axis=0), atol=1e-5)
      and bis == (True, False, False))
mt._restore(det, None)
# Esc: as it was
op, _t, _r = lean(det, 2, cancel=True)
_P, n_c = evaluated(det)
check(f'Esc: the detail as it was ({n_c:,} faces, no mirror: {det.modifiers.get(mt.MOD_NAME) is None}), its copy '
      f'gone, shown', n_c == n_det and det.modifiers.get(mt.MOD_NAME) is None and not det.hide_viewport
      and not [o for o in S.objects if o.get(mt.PREVIEW_KEY)])
# the preview: where nothing is cut, the same mesh placed reflected (a change only moves it); where it cuts, the mirror
info = mt.make_preview(C, det)
base = bpy.data.objects[info['base']]
mt.show_preview(C, info, det, S.mch_mirror, S, (True, False, False), (False, False, False))
twins = [bpy.data.objects[n] for n in info['twins']]
Pb, nb = evaluated(base)
Pt = [evaluated(t) for t in twins]
P_both = np.vstack([Pb] + [q for q, _n in Pt])
same = len(P_both) == len(P_old) and np.allclose(np.sort(P_both, axis=0), np.sort(P_old, axis=0), atol=1e-4)
shared = all(t.data == base.data for t in twins)
t0 = time.perf_counter()
for k in range(3):
    ax, fl = (((True, False, False), (False, False, False)), ((False, True, False), (False, True, False)),
              ((True, True, False), (False, True, False)))[k]          # (the detail: x > 0, y < 0 - nothing cut)
    mt.show_preview(C, info, det, S.mch_mirror, S, ax, fl)
    C.evaluated_depsgraph_get().update()
t_twin = (time.perf_counter() - t0) / 3
n_twins_xy = len(info['twins'])
mt.show_preview(C, info, det, S.mch_mirror, S, (True, False, False), (True, False, False))   # (keeps -X: cuts it all)
mb = base.modifiers.get(mt.MOD_NAME)
_P0, n_cut = evaluated(base)
check(f'the lean preview: nothing cut - the mirrored copy is the same mesh placed reflected ({len(twins)} copy, shares '
      f'the mesh: {shared}; together the same points as the mirror: {same}), a change {t_twin * 1000:.0f} ms (X+Y: '
      f'{n_twins_xy} copies); leaned the other way (it cuts it all): the mirror on the copy, Bisect kept '
      f'({mb and tuple(mb.use_bisect_axis)}, {n_cut} faces left, no copies {info["twins"]})',
      len(twins) == 1 and shared and same and t_twin < 0.05 and n_twins_xy == 3 and mb is not None
      and tuple(mb.use_bisect_axis) == (True, False, False) and n_cut == 0 and not info['twins'])
mt.drop_preview(info, det)
check('... the preview gone: its copies, its mesh, its pivot; the part shown',
      not [o for o in bpy.data.objects if o.get(mt.PREVIEW_KEY)] and 'MCH Mirror Preview' not in bpy.data.meshes
      and not [o for o in bpy.data.objects if o.get('_mch_world_pivot')] and not det.hide_viewport)
# a file saved in the middle of a lean (an autosave): its copies and the hidden part tidied when it is opened
info = mt.make_preview(C, det)
mt.show_preview(C, info, det, S.mch_mirror, S, (True, False, False), (False, False, False))
left_before = len([o for o in bpy.data.objects if o.get(mt.PREVIEW_KEY)])
mt.clean_previews()
check(f'a file saved mid-lean, opened: the lean\'s copies ({left_before}) gone, the part shown again '
      f'(the tidy-up runs when a file opens: {mt.clean_previews in bpy.app.handlers.load_post})',
      left_before == 2 and not [o for o in bpy.data.objects if o.get(mt.PREVIEW_KEY)] and not det.hide_viewport
      and mt.clean_previews in bpy.app.handlers.load_post)
# a light part (no other modifiers): as before, no copy
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(3.0, 0.0, 0.0))
cube = C.active_object
unselect()
cube.select_set(True)
C.view_layer.objects.active = cube
op = mt.MirrorLeanLogic()
op.start(C, Reg(), FRONT, (800, 450))
had = bool(getattr(op, 'previews', {}))
op.finish_live(S)
mc = cube.modifiers.get(mt.MOD_NAME)
check(f'a plain cube: mirrored on itself as before (a copy: {had}), its mirror live with Bisect as set',
      not had and mc is not None and mc.use_bisect_axis[0] == S.mch_mirror.bisect)
summary()
