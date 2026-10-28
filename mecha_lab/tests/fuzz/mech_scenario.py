"""One random "build a mech" scenario (run by run_fuzz.py in its own Blender process):

    <python with bpy> mech_scenario.py <seed> <steps>

A body with details and THIN walls, then a random sequence of what a session does: sculpt-like deformation
(noise along the normals, DynaMesh, Divide), lasso tools through the real stroke logic (Cut, Split, Box Hide,
Armor Plate, Base Mesh, Plate Detail 1 / 2 / 3), Redo Last with a changed setting, symmetry (Mirror), Armor Shell,
Quad Remesh, Hard Edges, Decimate, Fix Mesh, groups + Shift+D, Live Stack moves / Apply All, an Export Quad Mesh
round trip, Ctrl+Z.  After every step the mesh is measured (``quality``): NaN, open edges on a part that was closed,
spikes, slivers / zero-area faces, faces on the same points, inconsistent normals, debris pieces - each one a BAD
line with the step.  A Python error is an ERROR line (the scenario goes on); the process dying is the CRASH
run_fuzz.py looks for.  View: an orthographic top view, screen = 500 + 100 * world (x, y)."""
import math  # noqa: E402,F401
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fuzz_common import *          # noqa: F401,F403,E402  (0.24.83 the shared part: driver, body, quality, step helpers)
from fuzz_common import _Scene     # noqa: F401,E402

STEPS = {
    'sculpt': lambda: (to_object(), noise(C.active_object, rng.choice([0.01, 0.03, 0.08]), rng.uniform(1, 6),
                                          region=(Vector(C.active_object.location) + Vector((rng.uniform(-1, 1),
                                                                                             rng.uniform(-1, 1),
                                                                                             rng.uniform(-1, 1))),
                                                  rng.uniform(0.3, 1.5)) if rng.random() < 0.7 else None), 'noise')[-1],
    'dynamesh': lambda: sculpt_act('DYNAMESH', points=rng.choice([4000, 15000, 40000])),
    'divide': lambda: sculpt_act('DIVIDE') if len(C.active_object.data.polygons) < 60000 else 'skip (big)',
    'decimate': lambda: sculpt_act('DECIMATE', decimate=rng.choice([10, 30, 60, 90]), dec_even=rng.random() < 0.5),
    'hard_edges': lambda: (sculpt_act('HE_FIND', he_angle=math.radians(rng.choice([20, 30, 45])),
                                      he_width=rng.choice([0.0, 0.01, 0.04]), he_segments=rng.randint(1, 4),
                                      he_subdiv=rng.randint(0, 1), he_client=rng.random() < 0.7),
                           sculpt_act('HE_APPLY') if rng.random() < 0.6 else 'live')[-1],
    'cut': stroke_step('CUT'),
    'cut_alt': stroke_step('CUT', alt=True),
    'cut_strip': stroke_step('CUT', 'strip'),
    'split': stroke_step('SPLIT'),
    'hide': stroke_step('HIDE'),
    'hide_strip': stroke_step('HIDE', 'strip'),
    'plate': stroke_step('PLATE'),
    'base': stroke_step('BASE', 'free'),
    'base_on': stroke_step('BASE', 'part'),
    'detail': lambda: tool(rng.choice(['DETAIL', 'DETAIL2', 'DETAIL3'])),
    'redo_last': redo_last,
    'mirror': mirror,
    'shell': shell,
    'quad': quad,
    'fix_mesh': fix_mesh,
    'group_dup': group_dup,
    'stack': stack,
    'export': export_roundtrip,
    'undo': undo,
    'thin': add_thin,
    'object_mode': lambda: (to_object(), 'object')[-1],
}
# undo: bpy without a window segfaults on Ctrl+Z after a Box Hide (seeds 4 / 30 / 39 of the first runs) while the
# real-window smoke test's Ctrl+Z after a Cut and after a Box Hide is fine - a harness artefact, so weight 0 unless
# MECH_UNDO=1
WEIGHTS = {'sculpt': 4, 'cut': 4, 'cut_strip': 2, 'split': 2, 'hide': 3, 'plate': 3, 'detail': 2, 'base': 2,
           'dynamesh': 2, 'quad': 2, 'hard_edges': 2, 'redo_last': 2, 'mirror': 2,
           'undo': 2 if os.environ.get('MECH_UNDO') else 0, 'export': 1,
           'stack': 2, 'shell': 1, 'divide': 1, 'decimate': 1, 'fix_mesh': 1, 'group_dup': 1, 'thin': 1}
names = list(STEPS)
weights = [WEIGHTS.get(n, 1) for n in names]
parts = body()
to_object()
C.view_layer.objects.active = bpy.data.objects['Body']
log(f'SCENARIO {seed}: {parts} ({sum(len(o.data.polygons) for o in meshes()):,} faces)')
for o in meshes():
    q = quality(o)
    if any(q[k] for k in ('open', 'multi', 'flipped', 'twins', 'zero')):
        log(f'NOTE start {o.name}: {q}')
bpy.ops.ed.undo_push(message='start')
t_all = time.perf_counter()
for i in range(nsteps):
    name = rng.choices(names, weights)[0]
    ms = meshes()
    if not ms:
        log(f'STEP {i} no mesh left - new body')
        body()
        continue
    if C.active_object is None or C.active_object.type != 'MESH' or C.active_object not in ms or rng.random() < 0.3:
        to_object()
        C.view_layer.objects.active = rng.choice(ms)
    ob = C.active_object
    select_only(ob)
    before = {o.name: quality(o) for o in ms}
    log(f'STEP {i} {name} on {ob.name} ({len(ob.data.polygons):,} faces, {len(ms)} parts)')
    t = time.perf_counter()
    try:
        r = STEPS[name]()
        to_object()
        for o in meshes():
            if o.name in before:
                judge(i, name, o, before[o.name])
            else:
                q = quality(o)
                bads = {k: v for k, v in q.items() if k in ('nan', 'multi', 'spike', 'twins', 'flipped', 'zero', 'debris') and v}
                if bads:
                    log(f'BAD {i} {name}: new part {o.name} {bads}')
                    save_bad(i, name)
        log(f'  ok {time.perf_counter() - t:.2f}s {str(r)[:100]}')
        if os.environ.get('MECH_SAVE_STEP') == str(i):             # (a probe wants the scene after this step)
            to_object()
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.environ.get('MECH_SAVE_DIR', OUT),
                                                              f'step_{seed}_{i}.blend'), copy=True)
    except Exception as ex:
        log(f'ERROR {i} {name}: {type(ex).__name__}: {str(ex).splitlines()[0][:150] if str(ex) else ""}')
log(f'DONE {seed} in {time.perf_counter() - t_all:.1f}s')
