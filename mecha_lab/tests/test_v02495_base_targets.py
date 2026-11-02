"""0.24.95 Base Mesh Alt (subtract) follows the Targets setting (user: "베이스 메시 컷을 셀렉트로 하는데 왜 다 잘려?"):
Alt with Like Cut found every mesh under the shape (Auto Target) whatever Targets said - now Selected cuts only the
selected meshes, Active only the active one, Auto every mesh under the shape (as before); a shape over none of the
allowed meshes cuts nothing (a message).  The carve modes (Height, Through) too: Active with two selected - the active
one only."""
from _harness import bpy, check, cube, fresh, summary
from mathutils import Quaternion  # noqa: E402  (after bpy)

import mecha_lab
from mecha_lab import base_mesh as bm_, core_geometry as cg, cut_engine as ce

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_settings.auto_apply = True
pr = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)


def scene_two():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    a = cube('A', size=2.0, loc=(-1.2, 0, 0))
    b = cube('B', size=2.0, loc=(1.2, 0, 0))
    return a, b


def loop(x0, x1):
    p0, p1 = pr.to_screen((x0, -0.4, 1.0))[:2], pr.to_screen((x1, 0.4, 1.0))[:2]
    return ce.rect_loop((min(p0[0], p1[0]), min(p0[1], p1[1])), (max(p0[0], p1[0]), max(p0[1], p1[1])))


def select(*obs, active=None):
    for o in C.selected_objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    C.view_layer.objects.active = active or (obs[-1] if obs else None)


def run(mode, alt, sel, active=None, span=(-1.6, 1.6)):
    a, b = scene_two()
    S.mch_cut.targets = mode
    bm_.scene_defaults(C).alt_mode = alt
    select(*[{'A': a, 'B': b}[n] for n in sel], active={'A': a, 'B': b}.get(active))
    try:
        msg = bm_.perform_base(C, [loop(*span)], pr, cutter=True)
    except cg.CutError as ex:
        msg = 'ERR ' + str(ex)
    return len(a.data.polygons) > 6, len(b.data.polygons) > 6, msg


got = run('SELECTED', 'CUT', 'A')
check('Targets Selected, Alt Like Cut over two meshes, A selected: only A cut (B was cut too)', got[:2] == (True, False),
      got)
got = run('AUTO', 'CUT', 'A')
check('... Targets Auto: every mesh under the shape, as before', got[:2] == (True, True), got)
got = run('ACTIVE', 'CUT', 'AB', active='B')
check('... Targets Active, both selected, B active: only B', got[:2] == (False, True), got)
got = run('SELECTED', 'CUT', 'A', span=(0.6, 1.8))
check('... Selected, the shape only over B (not selected): nothing cut, a message saying why',
      got[:2] == (False, False) and 'not over a selected mesh' in got[2], got)
got = run('ACTIVE', 'HEIGHT', 'AB', active='A')
check('Carve (Height), Targets Active, both selected, A active: only A', got[:2] == (True, False), got)
got = run('SELECTED', 'THROUGH', 'B')
check('... Through, Selected B: only B', got[:2] == (False, True), got)
summary()
