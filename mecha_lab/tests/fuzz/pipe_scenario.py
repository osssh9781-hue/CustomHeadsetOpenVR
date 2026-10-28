"""One random "ZBrush pipeline" scenario (run by run_fuzz.py in its own Blender process):

    <python with bpy> pipe_scenario.py <seed> <steps>

The way the user works, with the tools they reported as the most error-prone (0.24.83): a part is DynaMeshed,
sculpted (noise), Decimated, Quad Remeshed (Mostly / All Quads, random targets) and then worked on again with Cut in
every flavour - plain (Through / From Surface), Edge Finish Bevel / Chamfer, GN Edge Chamfer / Bevel, Cut Ramp,
Alt (keep inside), open-line cuts - and Box Hide (cap on / off, strips, Alt restore, Show All, Apply, Split Off).

On top of the mesh checks of ``fuzz_common.quality`` / ``judge`` every stroke is checked for doing something:
    NOOP   the tool said it finished but the evaluated mesh of the part under the shape did not change
           (only when the drawn shape is over the part: ray casts from the view at points inside the shape hit it)
    RAMP   a Cut Ramp on a flat top: the floor is about Cut Depth deep at the deep side, rising to the surface at
           the far side, and never deeper than Cut Depth
    FAIL   the tool refused (a CutError) - counted so the frequent refusals show up
A Python error is an ERROR line; the process dying is the CRASH run_fuzz.py looks for.

Probes (environment): MECH_SAVE_BAD=1 + MECH_SAVE_DIR saves the scene after a BAD step, MECH_SAVE_STEP=n (or 'pre')
the scene before step n, MECH_LOG_PTS=1 logs the stroke points / Cut settings / ZBrush settings of every step (the
scratch replay.py re-runs one on the saved scene), MECH_SKIP_STEPS=a,b skips step kinds, MECH_DECIMATE_BLENDER=1
uses Blender's Decimate modifier instead of the C engine, MECH_DUMP_SWEEP=path writes the mesh handed to the GN rim
sweep (path.obj + path.json), MECH_HANG_DUMP=seconds prints the stack after that long (a hang)."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fuzz_common import *          # noqa: F401,F403,E402  (bpy, C, S, rng, seed, nsteps, helpers, the stroke driver)
from fuzz_common import _Scene     # noqa: F401,E402

from mecha_lab import box_hide as bh  # noqa: E402

cut = S.mch_cut
hide = S.mch_hide
if os.environ.get('MECH_HANG_DUMP'):                # (a probe: where a step hangs - the stack after n seconds)
    import faulthandler
    faulthandler.dump_traceback_later(int(os.environ['MECH_HANG_DUMP']), exit=True)
if os.environ.get('MECH_DUMP_SWEEP'):               # (a probe: the mesh handed to the GN rim sweep, written first)
    from mecha_lab import rim_sweep as _rs, core_geometry as _cg
    _orig_finish = _rs.finish

    def _dump_finish(mesh, mode='CHAMFER', width=0.01, segments=3):
        import json as _json
        path = os.environ['MECH_DUMP_SWEEP']
        with open(path + '.obj', 'w') as f:
            for v in mesh.vertices:
                f.write(f'v {v.co.x:.9g} {v.co.y:.9g} {v.co.z:.9g}\n')
            for p_ in mesh.polygons:
                f.write('f ' + ' '.join(str(i + 1) for i in p_.vertices) + '\n')
        attr = mesh.attributes.get(_cg.CUTTER_ATTR)
        flags = [bool(d.value) for d in attr.data] if attr is not None else []
        _json.dump({'mode': mode, 'width': width, 'segments': segments, 'flags': flags,
                    'smooth': [p_.use_smooth for p_ in mesh.polygons]}, open(path + '.json', 'w'))
        log(f'  sweep dump {mode} {width} {segments} faces {len(mesh.polygons)} -> {path}.obj')
        return _orig_finish(mesh, mode, width, segments)
    _rs.finish = _dump_finish


# --- measuring what a stroke did ---------------------------------------------------------------------------------
def eval_sig(ob):
    """A signature of the evaluated mesh (modifiers included): counts + a coordinate checksum + bounding box."""
    dg = C.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).data
    n = len(me.vertices)
    if not n:
        return (0, 0, 0.0, ())
    co = np.empty(n * 3, np.float64)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    return (n, len(me.polygons), round(float(np.abs(co).sum()), 4), tuple(np.round(co.min(0), 4)) + tuple(np.round(co.max(0), 4)))


def hits(ob, pts):
    """Heights (world z) of the evaluated part under the screen points of the view (None where nothing is hit)."""
    dg = C.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    inv = ob.matrix_world.inverted()
    out = []
    for x, y in pts:
        origin = inv @ Vector(((x - 500.0) / 100.0, (y - 500.0) / 100.0, 100.0))
        d = (inv.to_3x3() @ Vector((0, 0, -1))).normalized()
        ok, loc, _nrm, _idx = ev.ray_cast(origin, d)
        out.append((ob.matrix_world @ loc).z if ok else None)
    return out


def inside_points(pts):
    """Sample points inside a drawn outline: the centroid and half-way to every corner."""
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return [(cx, cy)] + [((cx + x) / 2, (cy + y) / 2) for x, y in pts]


def stroke(mode, pts, alt=False, line=False, side=None):
    """One stroke of ``mode`` through the stroke logic; returns (result set, message)."""
    MODE[0], NATIVE[0] = mode, ts.TOOL_BY_ID[mode][5]
    S.mch_settings.mch_active_tool = mode
    S.mch_brush.line_open = bool(line)
    to_object()
    if os.environ.get('MECH_LOG_PTS'):                 # (a probe replays the same stroke on a saved scene)
        log(f'  pts {mode} alt={alt} line={line} side={side} {[(round(x, 1), round(y, 1)) for x, y in pts]}')
        if mode == 'CUT':
            log('  cut ' + ' '.join(f'{k}={getattr(cut, k)!r}' for k in (
                'depth_mode', 'depth', 'edge_finish', 'finish_width', 'finish_segments', 'finish_clamp', 'gn_finish',
                'gn_width', 'gn_segments', 'gn_ramp', 'gn_ramp_length', 'gn_ramp_soft', 'gn_ramp_steep', 'gn_ramp_res',
                'solver', 'hole_tolerant')))
        if mode == 'HIDE':
            log(f'  hide cap={hide.cap} mirror={hide.mirror} follow_symmetry={hide.follow_symmetry}')
    try:
        return lasso(pts, alt=alt, side=side)
    finally:
        S.mch_brush.line_open = False


def refused(msg):
    m = (msg or '').lower()
    return any(k in m for k in ('could not', 'nothing', 'draw over', 'no mesh', 'failed', 'too small', 'crosses itself',
                                'empty', 'kept as it was', 'at least one clear edge'))


def check_noop(step, name, ob, pts, before_sig, r, msg):
    """BAD NOOP when a finished stroke over the part changed nothing; FAIL when the tool refused."""
    if r != {'FINISHED'} or refused(msg):
        log(f'FAIL {step} {name} on {ob.name}: {r} {msg[:120]}')
        return False
    if ob.name not in bpy.data.objects:
        return True
    if eval_sig(ob) != before_sig:
        return True
    hs = [h for h in hits(ob, inside_points(pts)) if h is not None]
    if hs:
        log(f'BAD {step} {name} on {ob.name}: NOOP - finished ({msg[:60]}) but the part did not change '
            f'({len(hs)} of {len(pts) + 1} points inside the shape are over it)')
        save_bad(step, name)
        return False
    return True


# --- the Cut family ----------------------------------------------------------------------------------------------
def reset_cut():
    cut.depth_mode, cut.depth = 'THROUGH', 0.1
    cut.edge_finish, cut.finish_width, cut.finish_segments = 'NONE', 0.01, 3
    cut.gn_finish, cut.gn_width, cut.gn_segments = 'NONE', 0.01, 4
    cut.gn_ramp, cut.gn_ramp_length, cut.gn_ramp_soft, cut.gn_ramp_steep, cut.gn_ramp_res = False, 1.0, 0.5, 'EVEN', 20
    cut.solver, cut.hole_tolerant = 'AUTO', False
    cut.finish_clamp, cut.finish_crisp = True, True


def part_size(ob):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return max(max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3))


def cut_settings(flavour, ob):
    """The Cut settings for this flavour; the live last cut (if any) is cut again with them, as the UI's timer
    would (0.24.83: never inside the property update - that crashed)."""
    from mecha_lab import ramp_edit as _re
    _cut_settings(flavour, ob)
    _re.flush()


def _cut_settings(flavour, ob):
    reset_cut()
    size = part_size(ob)
    cut.depth_mode = rng.choice(['THROUGH', 'THROUGH', 'SURFACE'])
    cut.depth = size * rng.choice([0.05, 0.1, 0.2, 0.4])
    if flavour == 'bevel':
        cut.edge_finish = rng.choice(['BEVEL', 'CHAMFER'])
        cut.finish_width = size * rng.choice([0.005, 0.01, 0.03, 0.08])
        cut.finish_segments = rng.choice([1, 2, 3, 6])
        cut.finish_clamp = rng.random() < 0.7
    elif flavour == 'gn':
        cut.gn_finish = rng.choice(['CHAMFER', 'BEVEL'])
        cut.gn_width = size * rng.choice([0.005, 0.01, 0.03, 0.08])
        cut.gn_segments = rng.choice([1, 2, 4, 8])
    elif flavour == 'ramp':
        cut.gn_ramp = True
        cut.depth_mode = 'SURFACE'
        cut.gn_finish = rng.choice(['NONE', 'NONE', 'CHAMFER', 'BEVEL'])
        cut.gn_width = size * rng.choice([0.01, 0.03])
        cut.gn_ramp_length = rng.choice([1.0, 1.0, 0.6, 0.3])
        cut.gn_ramp_soft = rng.choice([0.0, 0.5, 1.0])
        cut.gn_ramp_steep = rng.choice(['EVEN', 'LIMIT'])
        cut.gn_ramp_res = rng.choice([8, 20, 60])
    if rng.random() < 0.15:
        cut.solver = rng.choice(['EXACT', 'MANIFOLD'])
        cut.hole_tolerant = rng.random() < 0.5


def rect_outline(ob, frac=(0.25, 0.6)):
    """An axis-aligned rectangle over part of the active part, corners in drawing order (the first side = deep side)."""
    x0, y0, x1, y1 = screen_box(ob)
    w, h = max(40.0, x1 - x0), max(40.0, y1 - y0)
    rw, rh = w * rng.uniform(*frac), h * rng.uniform(*frac)
    cx = rng.uniform(x0 + rw / 2 + w * 0.05, x1 - rw / 2 - w * 0.05) if w > rw * 1.2 else (x0 + x1) / 2
    cy = rng.uniform(y0 + rh / 2 + h * 0.05, y1 - rh / 2 - h * 0.05) if h > rh * 1.2 else (y0 + y1) / 2
    pts = [(cx - rw / 2, cy - rh / 2), (cx + rw / 2, cy - rh / 2), (cx + rw / 2, cy + rh / 2), (cx - rw / 2, cy + rh / 2)]
    k = rng.randint(0, 3)
    pts = pts[k:] + pts[:k]
    if rng.random() < 0.5:
        pts = [pts[0]] + pts[1:][::-1]
    return pts


def solid_depth(ob, pt):
    """How much solid is under screen point ``pt`` from the first surface down: (top z, solid thickness there) -
    the exit of the ray through the part (a bolt hole / tunnel under the top makes it thin).  (None, 0) = no hit."""
    inv = ob.matrix_world.inverted()
    d = (inv.to_3x3() @ Vector((0, 0, -1))).normalized()
    origin = inv @ Vector(((pt[0] - 500.0) / 100.0, (pt[1] - 500.0) / 100.0, 100.0))
    ok, loc, _n, _i = ob.ray_cast(origin, d)
    if not ok:
        return None, 0.0
    top = (ob.matrix_world @ loc).z
    ok2, loc2, _n, _i = ob.ray_cast(loc + d * 1e-5, d)
    if not ok2:
        return top, 0.0
    return top, top - (ob.matrix_world @ loc2).z


def ramp_samples(pts):
    """Screen points of the ramp check: just inside the deep side, just inside the far side, the centre, a 4 x 4 grid."""
    (ax, ay), (bx, by), (cx, cy), (dx, dy) = pts
    mid_deep = ((ax + bx) / 2, (ay + by) / 2)
    mid_far = ((cx + dx) / 2, (cy + dy) / 2)
    centre = ((ax + cx) / 2, (ay + cy) / 2)
    frac = 0.15
    deep = (mid_deep[0] + (centre[0] - mid_deep[0]) * frac, mid_deep[1] + (centre[1] - mid_deep[1]) * frac)
    far = (mid_far[0] + (centre[0] - mid_far[0]) * frac, mid_far[1] + (centre[1] - mid_far[1]) * frac)
    grid = [((ax + cx) / 2 + (bx - ax) * u / 2 + (dx - ax) * v / 2, (ay + cy) / 2 + (by - ay) * u / 2 + (dy - ay) * v / 2)
            for u in (-0.6, -0.2, 0.2, 0.6) for v in (-0.6, -0.2, 0.2, 0.6)]
    return [deep, far, centre] + grid


def ramp_before(ob, pts):
    """(top z, [solid thickness per sample]) when the part is flat under every sample of the ramp check, else None."""
    got = [solid_depth(ob, p) for p in ramp_samples(pts)]
    if any(t is None for t, _s in got):
        return None
    tops = [t for t, _s in got]
    if max(tops) - min(tops) > 1e-3 * max(1.0, part_size(ob)):
        return None
    return tops[0], [s for _t, s in got]


def ramp_check(step, ob, pts, before):
    """Cut Ramp on a flat top: deep at the first side, up to the surface at the far side, never deeper than asked.
    A sample over a hollow (a bolt hole under the top) or a part thinner than the depth is left out."""
    if before is None:
        return
    top, solid = before
    depth = cut.depth
    h = hits(ob, ramp_samples(pts))
    through = [z is None and depth >= 0.9 * s for z, s in zip(h, solid)]
    if h[0] is None or h[1] is None:
        if through[0] or through[1]:
            log(f'  ramp through: {depth:.4f} deep on a part {min(solid[:2]):.4f} thick there (no floor to measure)')
            return
        log(f'BAD {step} cut_ramp on {ob.name}: RAMP - the floor is gone under the shape (deep {h[0]}, far {h[1]}, '
            f'solid {solid[0]:.4f} / {solid[1]:.4f}, {depth:.4f} asked)')
        save_bad(step, 'cut_ramp')
        return
    d_deep, d_far = top - h[0], top - h[1]
    drops = [top - z for z, s in zip(h, solid) if z is not None and s >= top - z - 1e-3]   # (not into a hollow)
    bad = []
    if d_deep < 0.4 * depth and solid[0] >= depth:
        bad.append(f'deep side only {d_deep:.4f} down (asked {depth:.4f})')
    if cut.gn_ramp_length >= 1.0 and d_far > 0.6 * depth:
        bad.append(f'far side still {d_far:.4f} down (should rise to the surface)')
    if d_deep < d_far - 0.05 * depth:
        bad.append(f'the slope runs the wrong way (deep {d_deep:.4f} < far {d_far:.4f})')
    if drops and max(drops) > 1.15 * depth + 1e-4:
        bad.append(f'deeper than asked: {max(drops):.4f} > {depth:.4f}')
    if drops and min(drops) < -1e-3:
        bad.append(f'raised above the surface by {-min(drops):.4f}')
    for b in bad:
        log(f'BAD {step} cut_ramp on {ob.name}: RAMP - {b}')
    if bad:
        save_bad(step, 'cut_ramp')
    else:
        log(f'  ramp ok: deep {d_deep:.4f} far {d_far:.4f} of {depth:.4f} (length {cut.gn_ramp_length}, soft '
            f'{cut.gn_ramp_soft}, {cut.gn_ramp_steep}, {cut.gn_finish})')


def cut_step(flavour):
    ob = C.active_object
    if flavour == 'ramp' and rng.random() < 0.5 and bpy.data.objects.get('Block') in meshes():
        ob = bpy.data.objects['Block']               # (the flat block: where the ramp slope can be measured)
        select_only(ob)
    cut_settings(flavour, ob)
    name = f'cut_{flavour}'
    alt = flavour == 'alt' or (flavour in {'plain', 'bevel', 'gn'} and rng.random() < 0.15)
    if flavour == 'line':
        x0, y0, x1, y1 = screen_box(ob)
        n = rng.choice([2, 2, 3, 5])
        if rng.random() < 0.5:
            y = rng.uniform(y0 + (y1 - y0) * 0.2, y1 - (y1 - y0) * 0.2)
            pts = [(x0 - 30 + (x1 - x0 + 60) * i / (n - 1), y + rng.uniform(-15, 15) * (i % 2)) for i in range(n)]
        else:
            x = rng.uniform(x0 + (x1 - x0) * 0.2, x1 - (x1 - x0) * 0.2)
            pts = [(x + rng.uniform(-15, 15) * (i % 2), y0 - 30 + (y1 - y0 + 60) * i / (n - 1)) for i in range(n)]
        if rng.random() < 0.5:
            cut.edge_finish = rng.choice(['BEVEL', 'CHAMFER'])
            cut.finish_width = part_size(ob) * rng.choice([0.01, 0.03])
        inside = pts
    elif flavour == 'ramp':
        pts = rect_outline(ob)
        inside = pts
    else:
        pts = random_outline(ob, rng.choice(['part', 'part', 'part', 'strip']))
        inside = pts
    sig = eval_sig(ob)
    before = ramp_before(ob, pts) if flavour == 'ramp' else None
    side = None
    if flavour == 'line':
        (ax, ay), (bx, by) = pts[0], pts[-1]
        nx, ny = -(by - ay), bx - ax
        ln = max(1e-6, math.hypot(nx, ny))
        off = rng.choice([-1, 1]) * rng.uniform(20, 60)
        side = ((ax + bx) / 2 + nx / ln * off, (ay + by) / 2 + ny / ln * off)
    r, msg = stroke('CUT', pts, alt=alt, line=flavour == 'line', side=side)
    ok = check_noop(STEP[0], name, ob, inside, sig, r, msg)
    if ok and flavour == 'ramp' and ob.name in bpy.data.objects:
        ramp_check(STEP[0], ob, pts, before)
    return f'{r} {msg[:90]}'


# --- Box Hide ----------------------------------------------------------------------------------------------------
def hide_step(kind):
    ob = C.active_object
    hide.cap = rng.random() < 0.7
    hide.mirror = rng.random() < 0.15
    hide.follow_symmetry = rng.random() < 0.7
    if kind == 'restore':
        if not bh.is_hidden(ob):
            return 'skip (nothing hidden)'
        pts = random_outline(ob, 'part')
        sig = eval_sig(ob)
        r, msg = stroke('HIDE', pts, alt=True)
        check_noop(STEP[0], 'hide_restore', ob, pts, sig, r, msg)
        return f'{r} {msg[:90]}'
    if kind in {'show_all', 'apply', 'split'}:
        if not bh.is_hidden(ob):
            return 'skip (nothing hidden)'
        select_only(ob)
        op = {'show_all': bpy.ops.mch.box_hide_show_all, 'apply': bpy.ops.mch.box_hide_apply,
              'split': bpy.ops.mch.box_hide_split}[kind]
        if not bh.get_cap(ob):
            OPEN_OK.add(f'hide_{kind}')              # (Open = no cap: an open part is what was asked)
        r = op()
        if kind == 'show_all' and bh.is_hidden(ob):
            log(f'BAD {STEP[0]} hide_show_all on {ob.name}: still hidden after Show All')
        if kind == 'apply' and (bh.is_hidden(ob) or ob.modifiers.get(bh.MOD)):
            log(f'BAD {STEP[0]} hide_apply on {ob.name}: the hide modifier is still there after Apply')
        return str(r)
    pts = random_outline(ob, 'strip' if kind == 'strip' else 'part')
    sig = eval_sig(ob)
    r, msg = stroke('HIDE', pts)
    if check_noop(STEP[0], f'hide_{kind}', ob, pts, sig, r, msg) and not bh.is_hidden(ob):
        log(f'BAD {STEP[0]} hide_{kind} on {ob.name}: finished but the part is not marked hidden')
    return f'{r} {msg[:90]}'


# --- the ZBrush pipeline -----------------------------------------------------------------------------------------
def pipe_dynamesh():
    return sculpt_act('DYNAMESH', points=rng.choice([6000, 15000, 40000, 80000]))


def pipe_decimate():
    if len(C.active_object.data.polygons) < 200:
        return 'skip (light)'
    ratio, even = rng.choice([5, 10, 20, 40]), rng.random() < 0.5
    if os.environ.get('MECH_DECIMATE_BLENDER'):        # (bisect: Blender's own Decimate modifier, not the C engine)
        to_object()
        ob = C.active_object
        m = ob.modifiers.new('dec', 'DECIMATE')
        m.ratio = ratio / 100.0
        with C.temp_override(object=ob, active_object=ob):
            bpy.ops.object.modifier_apply(modifier='dec')
        return f'blender decimate {ratio} %'
    return sculpt_act('DECIMATE', decimate=ratio, dec_even=even)


def pipe_quad():
    from mecha_lab import quad_field as qf
    to_object()
    ob = C.active_object
    if not qf.available():
        return 'skip (no engine)'
    n = len(ob.data.polygons)
    if n > 150000:
        return 'skip (big)'
    target = int(max(100, n * rng.choice([0.03, 0.05, 0.1, 0.2])))
    sig = eval_sig(ob)
    msg = qf.remesh_object(ob, target, all_quads=rng.random() < 0.4, crease_deg=rng.choice([20.0, 30.0, 45.0]))
    kept = 'kept as' in msg.lower() or 'could not' in msg.lower() or 'no result' in msg.lower()
    if eval_sig(ob) == sig and not kept:
        log(f'BAD {STEP[0]} quad on {ob.name}: NOOP - {msg[:80]}')
    if kept:
        log(f'FAIL {STEP[0]} quad on {ob.name}: {msg[:120]}')
    return msg[:100]


def pipeline():
    """The whole thing in one go: DynaMesh, noise, Decimate, Quad Remesh."""
    out = [pipe_dynamesh()]
    to_object()
    noise(C.active_object, rng.choice([0.02, 0.05]), rng.uniform(2, 6))
    out.append(pipe_decimate())
    out.append(pipe_quad())
    return ' | '.join(str(o)[:40] for o in out)


STEP = [0]
STEPS = {
    'dynamesh': pipe_dynamesh,
    'sculpt': lambda: (to_object(), noise(C.active_object, rng.choice([0.01, 0.03, 0.08]), rng.uniform(1, 6),
                                          region=(Vector(C.active_object.location) + Vector((rng.uniform(-1, 1),
                                                                                             rng.uniform(-1, 1),
                                                                                             rng.uniform(-1, 1))),
                                                  rng.uniform(0.3, 1.5)) if rng.random() < 0.7 else None), 'noise')[-1],
    'decimate': pipe_decimate,
    'quad': pipe_quad,
    'pipeline': pipeline,
    'cut_plain': lambda: cut_step('plain'),
    'cut_bevel': lambda: cut_step('bevel'),
    'cut_gn': lambda: cut_step('gn'),
    'cut_ramp': lambda: cut_step('ramp'),
    'cut_alt': lambda: cut_step('alt'),
    'cut_line': lambda: cut_step('line'),
    'hide': lambda: hide_step('part'),
    'hide_strip': lambda: hide_step('strip'),
    'hide_restore': lambda: hide_step('restore'),
    'hide_show_all': lambda: hide_step('show_all'),
    'hide_apply': lambda: hide_step('apply'),
    'hide_split': lambda: hide_step('split'),
    'hard_edges': lambda: (sculpt_act('HE_FIND', he_angle=math.radians(rng.choice([20, 30, 45])),
                                      he_width=rng.choice([0.0, 0.01, 0.04]), he_segments=rng.randint(1, 4),
                                      he_subdiv=rng.randint(0, 1), he_client=rng.random() < 0.7),
                           sculpt_act('HE_APPLY'))[-1],
    'fix_mesh': fix_mesh,
    'thin': add_thin,
}
WEIGHTS = {'dynamesh': 2, 'sculpt': 3, 'decimate': 2, 'quad': 2, 'pipeline': 2,
           'cut_plain': 3, 'cut_bevel': 4, 'cut_gn': 4, 'cut_ramp': 4, 'cut_alt': 2, 'cut_line': 3,
           'hide': 3, 'hide_strip': 2, 'hide_restore': 2, 'hide_show_all': 1, 'hide_apply': 1, 'hide_split': 1,
           'hard_edges': 1, 'fix_mesh': 1, 'thin': 1}
OPEN_OK.update({'hide_split'})
names = list(STEPS)
weights = [WEIGHTS.get(n, 1) for n in names]
parts = body()
to_object()
# a plain block too (no holes, flat top): where the Cut Ramp check can measure the slope
_s = part_size(bpy.data.objects['Body']) / 2
bpy.ops.mesh.primitive_cube_add(size=_s * rng.uniform(0.7, 1.1), location=(0, -_s * 1.9, 0))
C.active_object.name = 'Block'
parts.append('Block')
C.view_layer.objects.active = bpy.data.objects['Body']
log(f'SCENARIO {seed}: {parts} ({sum(len(o.data.polygons) for o in meshes()):,} faces)')
# the user's way in: the body goes through the pipeline first (most seeds), so the cuts land on a remeshed part
if rng.random() < 0.7:
    try:
        select_only(bpy.data.objects['Body'])
        log('STEP -1 pipeline on Body')
        t = time.perf_counter()
        log(f'  ok {time.perf_counter() - t:.2f}s {pipeline()}')
    except Exception as ex:
        log(f'ERROR -1 pipeline: {type(ex).__name__}: {str(ex).splitlines()[0][:150] if str(ex) else ""}')
to_object()
for o in meshes():
    q = quality(o)
    if any(q[k] for k in ('open', 'multi', 'flipped', 'twins', 'zero')):
        log(f'NOTE start {o.name}: {q}')
if os.environ.get('MECH_SAVE_STEP') == 'pre':                  # (the scene step 0 starts from)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.environ.get('MECH_SAVE_DIR', OUT), f'step_{seed}_pre.blend'),
                                copy=True)
t_all = time.perf_counter()
for i in range(nsteps):
    STEP[0] = i
    name = rng.choices(names, weights)[0]
    ms = meshes()
    if not ms:
        log(f'STEP {i} no mesh left - new body')
        body()
        continue
    if C.active_object is None or C.active_object.type != 'MESH' or C.active_object not in ms or rng.random() < 0.25:
        to_object()
        C.view_layer.objects.active = rng.choice(ms)
    ob = C.active_object
    select_only(ob)
    before = {o.name: quality(o) for o in ms}
    log(f'STEP {i} {name} on {ob.name} ({len(ob.data.polygons):,} faces, {len(ms)} parts)')
    t = time.perf_counter()
    try:
        if name in os.environ.get('MECH_SKIP_STEPS', '').split(','):
            r = 'skip (MECH_SKIP_STEPS)'
        else:
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
        dt = time.perf_counter() - t
        log(f'  ok {dt:.2f}s {str(r)[:100]}')
        if dt > 20:
            log(f'SLOW {i} {name} on {ob.name}: {dt:.1f}s')
        if os.environ.get('MECH_SAVE_STEP') == str(i):
            to_object()
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.environ.get('MECH_SAVE_DIR', OUT),
                                                              f'step_{seed}_{i}.blend'), copy=True)
    except Exception as ex:
        log(f'ERROR {i} {name}: {type(ex).__name__}: {str(ex).splitlines()[0][:150] if str(ex) else ""}')
log(f'DONE {seed} in {time.perf_counter() - t_all:.1f}s')
