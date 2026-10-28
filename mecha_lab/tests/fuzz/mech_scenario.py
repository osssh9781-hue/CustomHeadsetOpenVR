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
import math
import os
import random
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.dirname(HERE)
sys.path.insert(0, TESTS)
from _harness import bpy, fresh  # noqa: E402

import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import mecha_lab  # noqa: E402
from mecha_lab import core_geometry as cg, tool_state as ts, zb_sculpt as zs  # noqa: E402

# the headless stroke driver (fake context / view) of the lasso tests
_src = open(os.path.join(TESTS, 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])      # noqa: S102  (Ctx, Op, E, MODE, NATIVE, VIEW)

seed, nsteps = int(sys.argv[-2]), int(sys.argv[-1])
rng = random.Random(seed)
fresh()
mecha_lab.register()
C = bpy.context


class _Scene:
    def __getattr__(self, k):
        return getattr(bpy.context.scene, k)


S = _Scene()
zs.on = lambda c: getattr(c, 'mode', '') == 'SCULPT'
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
S.mch_brush.line_mode = False
S.mch_cut.targets = 'AUTO'
OUT = tempfile.mkdtemp(prefix='mech_fuzz_')


def log(msg):
    sys.stdout.write(msg + '\n')
    sys.stdout.flush()


def sx(v):
    return 500.0 + 100.0 * v


def to_object():
    if C.mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except RuntimeError:
            pass


def meshes():
    return [o for o in C.view_layer.objects if o.type == 'MESH' and len(o.data.polygons)
            and not o.name.startswith('MCH_')]


def select_only(ob):
    to_object()
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob


# --- the part ---------------------------------------------------------------------------------------------------------
def thin_plate(name, size, thick, loc, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
    ob = C.active_object
    ob.scale = (size, size * rng.uniform(0.4, 1.0), thick)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    ob.name = name
    return ob


def body():
    """A chunky core with bolt holes + two thin plates + a detailed knob: 3 - 4 parts in view (world -3 .. 3)."""
    s = rng.uniform(0.8, 1.6)
    bpy.ops.mesh.primitive_cube_add(size=2 * s, location=(0, 0, 0))
    ob = C.active_object
    ob.name = 'Body'
    for _i in range(rng.randint(1, 3)):                        # holes / unions through it
        bpy.ops.mesh.primitive_cylinder_add(radius=s * rng.uniform(0.08, 0.35), depth=5 * s,
                                            location=(rng.uniform(-s, s) * 0.7, rng.uniform(-s, s) * 0.7, 0),
                                            rotation=(rng.choice([0, math.pi / 2]), 0, rng.uniform(0, 3)),
                                            vertices=rng.choice([8, 16, 32]))
        cut = C.active_object
        m = ob.modifiers.new('b', 'BOOLEAN')
        m.object, m.operation, m.solver = cut, rng.choice(['DIFFERENCE', 'DIFFERENCE', 'UNION']), 'EXACT'
        with C.temp_override(object=ob, active_object=ob):
            bpy.ops.object.modifier_apply(modifier='b')
        bpy.data.objects.remove(cut)
    if rng.random() < 0.7:                                       # a bevelled edge on the core
        m = ob.modifiers.new('bv', 'BEVEL')
        m.width, m.segments = s * rng.choice([0.02, 0.05, 0.1]), rng.choice([1, 2, 3])
        with C.temp_override(object=ob, active_object=ob):
            bpy.ops.object.modifier_apply(modifier='bv')
    thin_plate('PlateA', s * 1.4, rng.uniform(0.01, 0.06), (0, 0, s + 0.1))
    thin_plate('PlateB', s * 0.9, rng.uniform(0.005, 0.03), (s * 1.6, 0, 0), (0, math.pi / 2, 0))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=s * 0.35, segments=32, ring_count=16, location=(-s * 1.6, s, 0))
    knob = C.active_object
    knob.name = 'Knob'
    noise(knob, 0.08, 3.0)                                       # a detailed knob (sculpted look)
    return ['Body', 'PlateA', 'PlateB', 'Knob']


def noise(ob, amount, freq, region=None):
    """Sculpt-like deformation: a smooth random field along the normals (a region of the part or all of it)."""
    me = ob.data
    n = len(me.vertices)
    if n == 0:
        return
    co = np.empty(n * 3, np.float64)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    nm = np.empty(n * 3, np.float64)
    me.vertices.foreach_get('normal', nm)
    nm = nm.reshape(-1, 3)
    ph = np.array([rng.uniform(0, 6.3) for _ in range(3)])
    f = np.sin(co[:, 0] * freq + ph[0]) * np.sin(co[:, 1] * freq * 1.3 + ph[1]) * np.cos(co[:, 2] * freq * 0.7 + ph[2])
    if region is not None:
        c, r = region
        w = np.clip(1.0 - np.linalg.norm(co - c, axis=1) / r, 0.0, 1.0)
        f = f * w * w
    size = float(np.linalg.norm(co.max(0) - co.min(0))) or 1.0
    co = co + nm * (f * amount * size)[:, None]
    me.vertices.foreach_set('co', co.ravel())
    me.update()


# --- quality ----------------------------------------------------------------------------------------------------------
def quality(ob):
    """What is wrong with a mesh: counts per kind (all zero = clean)."""
    me = ob.data
    out = dict(nan=0, open=0, multi=0, zero=0, sliver=0, spike=0, twins=0, flipped=0, loose=0, debris=0,
               faces=len(me.polygons))
    if not len(me.vertices):
        return out
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    if not np.isfinite(co).all():
        out['nan'] = int((~np.isfinite(co)).sum())
        return out
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    lens = np.array([e.calc_length() for e in bm.edges]) if len(bm.edges) else np.zeros(0)
    med = float(np.median(lens)) if len(lens) else 0.0
    # a spike: a point whose shortest edge is 8x longer than the typical edge around its neighbours (local, so a
    # low-poly part with big flat faces next to a dense bevel is not a spike)
    for v in bm.verts:
        if len(v.link_edges) < 2 or not v.link_faces:
            continue
        mine = min(e.calc_length() for e in v.link_edges)
        around = [e2.calc_length() for e in v.link_edges for e2 in e.other_vert(v).link_edges if e2 is not e]
        if not around or mine <= 8.0 * float(np.median(around)):
            continue
        # ... and every face at the point is a needle there (a boolean cap n-gon next to dense triangles is not)
        angles = []
        for f in v.link_faces:
            vs = f.verts
            i = [x.index for x in vs].index(v.index)
            a, b = vs[i - 1].co - v.co, vs[(i + 1) % len(vs)].co - v.co
            angles.append(a.angle(b) if a.length > 0 and b.length > 0 else 0.0)
        if angles and max(angles) < math.radians(4.0):
            out['spike'] += 1
    for e in bm.edges:
        n = len(e.link_faces)
        if n == 0:
            continue
        if n == 1:
            out['open'] += 1
        elif n > 2:
            out['multi'] += 1
        elif n == 2:
            l1, l2 = e.link_loops[0], e.link_loops[1]
            if l1.vert == l2.vert:                       # both faces walk the edge the same way: one is flipped
                out['flipped'] += 1
    out['loose'] = sum(1 for v in bm.verts if not v.link_edges)
    seen = {}
    for f in bm.faces:
        a = f.calc_area()
        if a < 1e-12:
            out['zero'] += 1
        elif len(f.verts) == 3:
            vs = [v.co for v in f.verts]
            l = sorted(((vs[1] - vs[0]).length, (vs[2] - vs[1]).length, (vs[0] - vs[2]).length))
            if l[0] > 0 and l[2] > 0 and 2 * a / (l[2] * l[2]) < 0.0005:   # the smallest height over the longest side
                out['sliver'] += 1
        key = tuple(sorted(v.index for v in f.verts))
        if key in seen:
            out['twins'] += 1
        seen[key] = 1
    # debris: tiny separate pieces
    seen_v = set()
    for v in bm.verts:
        if v.index in seen_v or not v.link_faces:
            continue
        stack, comp = [v], 0
        while stack:
            x = stack.pop()
            if x.index in seen_v:
                continue
            seen_v.add(x.index)
            comp += 1
            stack.extend(e.other_vert(x) for e in x.link_edges)
        if comp < 6:
            out['debris'] += 1
    bm.free()
    return out


def judge(step, name, ob, before):
    """BAD lines for what a step made worse."""
    after = quality(ob)
    bad = []
    if after['nan']:
        bad.append(f'NaN positions ({after["nan"]})')
    if before['open'] == 0 and after['open'] > 0 and name not in OPEN_OK:
        bad.append(f'closed part now has {after["open"]} open edges')
    for k, label in (('multi', 'edges with 3+ faces'), ('spike', 'spikes'), ('twins', 'faces on the same points'),
                     ('flipped', 'flipped faces'), ('zero', 'zero-area faces'), ('debris', 'debris pieces'),
                     ('loose', 'loose points')):
        if after[k] > before[k]:
            bad.append(f'{label} {before[k]} -> {after[k]}')
    if after['sliver'] > max(before['sliver'], 0.01 * after['faces']):
        bad.append(f'slivers {before["sliver"]} -> {after["sliver"]}')
    for b in bad:
        log(f'BAD {step} {name} on {ob.name}: {b}')
    if bad:
        save_bad(step, name)
    return after


def save_bad(step, name):
    if os.environ.get('MECH_SAVE_BAD') and (step, name) not in SAVED:
        SAVED.add((step, name))
        path = os.path.join(os.environ.get('MECH_SAVE_DIR', OUT), f'bad_{seed}_{step}_{name}.blend')
        to_object()
        bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
        log(f'  saved {path}')


SAVED = set()


OPEN_OK = {'split'}         # (nothing here should open a closed part; Split pieces are closed too)


# --- strokes through the real stroke logic --------------------------------------------------------------------------
def lasso(points, alt=False):
    ctx, op = Ctx(), Op()
    op.invoke(ctx, E('LEFTMOUSE', 'PRESS', *points[0], alt=alt))
    op.modal(ctx, E('LEFTMOUSE', 'RELEASE', *points[0], alt=alt))
    for x, y in points[1:]:
        op.modal(ctx, E('LEFTMOUSE', 'PRESS', x, y, alt=alt))
        op.modal(ctx, E('LEFTMOUSE', 'RELEASE', x, y, alt=alt))
    r = op.modal(ctx, E('RET', alt=alt))
    return r, (op.reports[-1][1] if op.reports else '')


def screen_box(ob):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return (sx(min(p.x for p in pts)), sx(min(p.y for p in pts)), sx(max(p.x for p in pts)), sx(max(p.y for p in pts)))


def random_outline(ob, kind='part'):
    """A closed outline over part of the active part (kind 'part'), beside it ('free') or a thin strip ('strip')."""
    x0, y0, x1, y1 = screen_box(ob)
    w, h = max(40.0, x1 - x0), max(40.0, y1 - y0)
    if kind == 'free':
        cx, cy = rng.uniform(150, 850), rng.uniform(150, 850)
        rw, rh = rng.uniform(40, 160), rng.uniform(40, 160)
    elif kind == 'strip':
        cx, cy = rng.uniform(x0, x1), rng.uniform(y0, y1)
        rw, rh = (w * 1.2, rng.uniform(4, 14)) if rng.random() < 0.5 else (rng.uniform(4, 14), h * 1.2)
    else:
        cx, cy = rng.uniform(x0 + w * 0.2, x1 - w * 0.2), rng.uniform(y0 + h * 0.2, y1 - h * 0.2)
        rw, rh = w * rng.uniform(0.2, 0.7), h * rng.uniform(0.2, 0.7)
    n = rng.choice([4, 4, 5, 7, 12])
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n + rng.uniform(-0.2, 0.2)
        r = rng.uniform(0.7, 1.0)
        pts.append((cx + rw / 2 * r * math.cos(a), cy + rh / 2 * r * math.sin(a)))
    return pts


def tool(mode, kind='part', alt=False):
    ob = C.active_object
    MODE[0], NATIVE[0] = mode, ts.TOOL_BY_ID[mode][5]
    S.mch_settings.mch_active_tool = mode
    to_object()
    r, m = lasso(random_outline(ob, kind), alt=alt)
    return f'{r} {m[:80]}'


def stroke_step(mode, kind='part', alt=False):
    return lambda: tool(mode, kind, alt)


def redo_last():
    from mecha_lab import last_op
    if not last_op.available(C):
        return 'skip (nothing to redo)'
    rec = last_op.record()
    if rec['mode'] == 'PLATE':
        S.mch_plate.spacing = rng.choice([40, 80, 160])
    elif rec['mode'] in {'BASE', 'CBASE'}:
        from mecha_lab import base_mesh
        p = base_mesh.scene_defaults(C)
        p.height = rng.uniform(0.05, 0.6)
    to_object()
    return str(bpy.ops.mch.last_redo())


def sculpt_act(name, **settings):
    for k, v in settings.items():
        setattr(S.mch_zb, k, v)
    if C.mode != 'SCULPT':
        bpy.ops.object.mode_set(mode='SCULPT')
    return str(bpy.ops.mch.zb_action(action=name))


def shell():
    to_object()
    ob = C.active_object
    select_only(ob)
    if not bpy.ops.mch.shell_extract.poll():
        return 'skip (shell poll: ' + ('a shell already' if ob.modifiers.get('MCH_ArmorShell') else 'no') + ')'
    return str(bpy.ops.mch.shell_extract())


def mirror():
    from mecha_lab import symmetry
    to_object()
    return str(symmetry.set_mode(C, C.active_object, rng.choice(['MIRROR', 'MIRROR', 'OFF'])))


def quad():
    from mecha_lab import quad_field as qf
    to_object()
    ob = C.active_object
    if not qf.available():
        return 'skip (no engine)'
    if len(ob.data.polygons) > 150000:
        return 'skip (big)'
    target = int(max(60, len(ob.data.polygons) * rng.choice([0.1, 0.3, 1.0])))
    return qf.remesh_object(ob, target, all_quads=rng.random() < 0.4, crease_deg=30.0)[:100]


def group_dup():
    from mecha_lab import groups
    to_object()
    ms = meshes()
    if len(ms) < 2:
        return 'skip'
    pick = rng.sample(ms, 2)
    for o in C.selected_objects:
        o.select_set(False)
    for o in pick:
        o.select_set(True)
    C.view_layer.objects.active = pick[0]
    g = groups.create(C, pick, 'G')
    select_only(g)
    r = bpy.ops.mch.duplicate(move=False)
    h = C.active_object
    C.view_layer.objects.active = pick[0]
    return f'{r} {h.name if h else ""}'


def stack():
    to_object()
    ob = C.active_object
    select_only(ob)
    if not ob.modifiers:
        return 'skip (nothing live)'
    if rng.random() < 0.5 and len(ob.modifiers) > 1:
        m = rng.choice(list(ob.modifiers))
        return 'move ' + str(bpy.ops.mch.stack_move(name=m.name, step=rng.choice([-1, 1])))
    return 'apply all ' + str(bpy.ops.mch.stack_apply_all())


def export_roundtrip():
    from mecha_lab import zbrush_bridge as zb
    to_object()
    ms = meshes()
    if sum(len(o.data.polygons) for o in ms) > 200000:
        return 'skip (big)'
    for o in C.selected_objects:
        o.select_set(False)
    for o in ms:
        o.select_set(True)
    C.view_layer.objects.active = ms[0]
    path = os.path.join(OUT, f'rt_{rng.randint(0, 9999)}.obj')
    r = bpy.ops.mch.export_mesh(filepath=path, scope='SELECTED', file_format='OBJ', quad_mesh=True, quad_size=1.5,
                                client_look=rng.random() < 0.3, client_subdiv=1)
    if not os.path.isfile(path):
        return f'{r} no file'
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=path)
    new = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    notes = []
    for o in new:
        q = quality(o)
        bads = {k: v for k, v in q.items() if k in ('nan', 'multi', 'spike', 'twins', 'flipped', 'zero') and v}
        if bads:
            notes.append(f'{o.name}: {bads}')
        bpy.data.objects.remove(o)
    for o in ms:
        if o.name not in bpy.data.objects:
            continue
    if notes:
        log('BAD export round trip: ' + '; '.join(notes))
        save_bad('export', 'export')
    C.view_layer.objects.active = ms[0]
    return f'{r} {len(new)} parts back'


def undo():
    to_object()
    if os.environ.get('MECH_NO_HANDLERS'):             # (bisect: the add-on's handlers / timers off for this undo)
        for hl in (bpy.app.handlers.undo_pre, bpy.app.handlers.undo_post, bpy.app.handlers.redo_pre,
                   bpy.app.handlers.redo_post, bpy.app.handlers.depsgraph_update_post,
                   bpy.app.handlers.depsgraph_update_pre):
            hl[:] = [f for f in hl if 'mecha_lab' not in getattr(f, '__module__', '')]
        if os.environ.get('MECH_NO_HANDLERS') == '2':
            import mecha_lab as _ml
            for name in list(sys.modules):
                m = sys.modules[name]
                if name.startswith('mecha_lab') and hasattr(m, '_tick') and bpy.app.timers.is_registered(m._tick):
                    bpy.app.timers.unregister(m._tick)
    try:
        return str(bpy.ops.ed.undo())
    except RuntimeError as ex:
        return 'undo: ' + str(ex)[:40]


def fix_mesh():
    from mecha_lab import mesh_fix
    to_object()
    return str(mesh_fix.fix_mesh(C.active_object.data, fill='SMALL'))[:100]


def add_thin():
    to_object()
    thin_plate(f'Thin{rng.randint(0, 99)}', rng.uniform(0.3, 1.5), rng.uniform(0.004, 0.05),
               (rng.uniform(-2.5, 2.5), rng.uniform(-2.5, 2.5), rng.uniform(-1, 1)),
               (rng.uniform(0, 3), rng.uniform(0, 3), 0))
    return 'thin plate added'


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
