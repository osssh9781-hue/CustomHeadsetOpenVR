"""Real window (0.24.165) - the user's notes on 0.24.164 by REAL clicks and drags (xdotool):

  1. Plate Detail 4: a REAL click on "Layered Cliff", a REAL outline - rock layers in long lines running down the cliff
     ("좀 더 세로로 그어져야 될 거 같아 - 저렇게 패턴이 아니라"), then a REAL drag on "Line Turn": the lines turn
  2. a REAL click on "Creature Carapace" (the plate selected): the lip thin ("외곽 라인이 너무 두꺼워")
  3. Creature Plate: a REAL drag on the window's "Edge Spikes", a REAL outline on a ball - spikes on its outline only
     ("외곽에 가시 난 버전 - 외곽에만 랜덤하게")
  4. Print Cut: a REAL click on "Key", a REAL Shift + drag across a block - one square key, closed parts (the user's
     Dovetail Key photos: "네모난 도브테일 키")
  5. Scale Line: a REAL click on "Scale Parts", a REAL line on the ball - scales laid, each with a line round its outline
     ("스케일도 외곽 부분에 살짝 라인")
"""
import math
import os
import subprocess
import sys
import time

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'addon'))
import mecha_lab  # noqa: E402
from mecha_lab import side_panel as sp  # noqa: E402
from mecha_lab.ui_gpu import ui_factor  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'w')


def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + '\n')
    LOG.flush()


mecha_lab.register()
C = bpy.context


def xdo(*args):
    subprocess.run(['xdotool', *map(str, args)], check=False)


def wins():
    r = subprocess.run(['xdotool', 'search', '--name', 'Blender'], capture_output=True, text=True)
    return r.stdout.split()


def focus(wid=None):
    for w_ in ([wid] if wid else wins()):
        subprocess.run(['xdotool', 'windowfocus', '--sync', w_], check=False)


def view3d():
    for w in C.window_manager.windows:
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                return w, a, next(r for r in a.regions if r.type == 'WINDOW')
    return None, None, None


def shot(name):
    path = os.path.join(OUT, name)
    os.system(f'import -window root "{path}"')
    log('shot', name, os.path.exists(path))
    return path


DRAWS = {'n': 0}


def _count_draw():
    DRAWS['n'] += 1


def wait_draws(n, limit=120.0):
    w, a, r = view3d()
    n0 = DRAWS['n']
    t0 = time.perf_counter()
    while DRAWS['n'] < n0 + n and time.perf_counter() - t0 < limit:
        a.tag_redraw()
        yield 0.1


def press(it):
    w, a, r = view3d()
    x, y = int(r.x + it.x + it.w / 2), int(w.height - (r.y + it.y + it.h / 2))
    xdo('mousemove', x, y)
    yield 0.6
    xdo('click', 1)
    yield 1.5


def panel_item(label):
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        its = sp.items(C, r.width, r.height, ui_factor(C, r))
    return next((i for i in its if getattr(i, 'label', '') == label and i.clickable()), None)


def scrolled_item(label):
    """The panel scrolled until the cell ``label`` is in its window; the cell (after two redraws), or None."""
    w, a, r = view3d()
    C.window_manager.mch_side_scroll = 0.0
    yield from wait_draws(2)
    for _i in range(40):
        it = panel_item(label)
        if it is not None:
            yield from wait_draws(2)
            return panel_item(label)
        with C.temp_override(window=w, area=a, region=r):
            sp.scroll_by(C, r.width, r.height, ui_factor(C, r), 120)
        yield from wait_draws(1)
    return None


def screen_xy(p):
    from bpy_extras import view3d_utils
    w, a, r = view3d()
    c = view3d_utils.location_3d_to_region_2d(r, a.spaces.active.region_3d, Vector(p))
    return int(r.x + c.x), int(w.height - (r.y + c.y))


def real_outline(pts, mods=()):
    xdo('mousemove', *pts[0])
    yield 0.4
    for m in mods:
        xdo('keydown', m)
    yield 0.2
    xdo('mousedown', 1)
    yield 0.3
    for x, y in pts[1:] + [pts[0]]:
        xdo('mousemove', x, y)
        yield 0.04
    yield 0.3
    xdo('mouseup', 1)
    yield 0.3
    for m in mods:
        xdo('keyup', m)
    yield 2.5


def ring_at(p, rx_px, ry_px, n=48, wob=0.0):
    c = screen_xy(p)
    return [(int(c[0] + rx_px * math.cos(2 * math.pi * i / n) * (1 + wob * math.sin(3 * 2 * math.pi * i / n))),
             int(c[1] - ry_px * math.sin(2 * math.pi * i / n))) for i in range(n)]


def evaluated(ob):
    import numpy as np
    dg = C.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    out = {'co': co.reshape(-1, 3), 'faces': len(me.polygons)}
    for nm in ('mch_rd', 'mch_rtop', 'mch_rough'):
        at = me.attributes.get(nm)
        a_ = np.empty(len(at.data), np.float32)
        at.data.foreach_get('value', a_)
        out[nm] = a_
    return out


def slider_drag(it, frac0, dx, steps=12):
    w, a, r = view3d()
    x, y = int(r.x + it.x + it.w * frac0), int(w.height - (r.y + it.y + it.h / 2))
    xdo('mousemove', x, y)
    yield 0.5
    xdo('mousedown', 1)
    yield 0.3
    for i in range(1, steps + 1):
        xdo('mousemove', x + i * dx, y)
        yield 0.06
    yield 0.3
    xdo('mouseup', 1)
    yield 2.5


def drag_world(a, b, mods=()):
    xa, xb = screen_xy(a), screen_xy(b)
    xdo('mousemove', *xa)
    yield 0.4
    for m in mods:
        xdo('keydown', m)
    yield 0.2
    xdo('mousedown', 1)
    yield 0.3
    for i in range(1, 16):
        xdo('mousemove', int(xa[0] + (xb[0] - xa[0]) * i / 15), int(xa[1] + (xb[1] - xa[1]) * i / 15))
        yield 0.05
    yield 0.3
    xdo('mouseup', 1)
    yield 0.4
    for m in mods:
        xdo('keyup', m)
    yield 1.5


def aniso(ob, ramp, res=0.03):
    import numpy as np
    e = evaluated(ob)
    t_ = (e['mch_rtop'] > 0.5) & (e['mch_rd'] > ramp * 0.55)
    mw = np.array(ob.matrix_world)
    q = e['co'][t_] @ mw[:3, :3].T + mw[:3, 3]
    ij = np.round(q[:, :2] / res).astype(int)
    keys, inv = np.unique(ij, axis=0, return_inverse=True)
    zm = np.bincount(inv.ravel(), q[:, 2]) / np.bincount(inv.ravel())
    cell = {tuple(k): z_ for k, z_ in zip(keys, zm)}
    dx = [abs(cell[(a_ + 1, b_)] - z_) for (a_, b_), z_ in cell.items() if (a_ + 1, b_) in cell]
    dy = [abs(cell[(a_, b_ + 1)] - z_) for (a_, b_), z_ in cell.items() if (a_, b_ + 1) in cell]
    return float(np.mean(dx)), float(np.mean(dy))


def setview(rot, loc, dist, persp='PERSP'):
    w, a, r = view3d()
    rv = a.spaces.active.region_3d
    rv.view_perspective = persp
    rv.view_rotation = Euler(rot).to_quaternion()
    rv.view_location = loc
    rv.view_distance = dist


def flow():
    import json
    import numpy as np
    import bmesh
    from mecha_lab import creature_plate as cp, greeble_line as gl, plate_detail as pd, print3d as p3
    w, a, r = view3d()
    focus()
    xdo('mousemove', 30, 540)
    yield 0.3
    xdo('key', 'Escape')
    yield 0.5
    with C.temp_override(window=w, area=a, region=r):
        ws = next((x for x in bpy.data.workspaces if x.name.startswith('MECHA LAB')), None)
        if ws is None:
            bpy.ops.mch.workspace_open()
            ws = next((x for x in bpy.data.workspaces if x.name.startswith('MECHA LAB')), None)
        w.workspace = ws
    yield 2.0
    w, a, r = view3d()
    S = C.scene
    sp3 = a.spaces.active
    res = {}
    with C.temp_override(window=w, area=a, region=r):
        for o in list(S.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, -0.1))
        slab = C.active_object
        slab.scale = (4.4, 3.0, 0.2)
        bpy.ops.object.transform_apply(scale=True)
        slab.name = 'Slab'
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None
        setview((math.radians(50), 0.0, 0.0), (0.0, 0.0, 0.0), 4.6)
        sp3.show_region_ui = False
        sp3.overlay.show_wireframes = True
        sp3.shading.type = 'SOLID'
        bpy.ops.mch.bar_tool(tool='DETAIL4')
        bpy.ops.mch.side_page(page='TOOL')
    yield 1.0
    S.mch_brush.shape = 'STROKE'
    handle = bpy.types.SpaceView3D.draw_handler_add(_count_draw, (), 'WINDOW', 'POST_PIXEL')
    yield 1.0
    # 1: Layered Cliff - lines down the cliff, Line Turn
    it = yield from scrolled_item('Layered Cliff')
    if it is not None:
        yield from press(it)
    yield from real_outline(ring_at(Vector((0.0, 0.0, 0.0)), 300, 170))
    plates = [o for o in S.objects if pd.is_detail(o)]
    A = plates[-1] if plates else None
    p = A.mch_pdetail if A else None
    ax0, ay0 = aniso(A, p.r_ramp) if A else (1.0, 0.0)
    log('1 cliff cell', it is not None, '- plate', A and A.name, 'style', p and p.r_style, '- across / along the lines',
        round(ay0 / max(ax0, 1e-9), 2))
    shot('1_cliff_lines.png')
    lt0 = p.r_lturn if p else 0.0
    it2 = yield from scrolled_item('Line Turn')
    if it2 is not None:
        yield from slider_drag(it2, 0.5, 25, steps=14)
    yield 2.0
    bx, by = aniso(A, p.r_ramp) if A else (0.0, 1.0)
    log('1b Line Turn cell', it2 is not None, 'turn', round(math.degrees(lt0)), '->', round(math.degrees(p.r_lturn)) if p else None,
        '- across / along now', round(bx / max(by, 1e-9), 2))
    res['1 a REAL click on "Layered Cliff" + a REAL outline: long lines down the cliff; a REAL drag on "Line Turn": they turn'] = (
        A is not None and it is not None and it2 is not None and p.r_style == 'CLIFF' and ay0 > 2.5 * ax0
        and math.degrees(p.r_lturn) > 45 and bx > by)
    shot('2_cliff_turned.png')
    # 2: Creature Carapace on the selected plate: the lip thin
    it = yield from scrolled_item('Creature Carapace')
    if it is not None:
        yield from press(it)
    yield 2.0
    if A is not None:
        e = evaluated(A)
        top, d, zc = e['mch_rtop'] > 0.5, e['mch_rd'], e['co'][:, 2]
        wid = p.r_ramp

        def at(lo, hi):
            m = top & (d >= lo) & (d < hi)
            return float(np.median(zc[m])) if m.any() else 0.0
        lip, groove, crest = at(0.85 * wid, 1.15 * wid), at(2.0 * wid, 2.4 * wid), at(0.92 * d[top].max(), d[top].max() + 1)
    else:
        lip = groove = crest = 0.0
        wid = 1.0
    log('2 carapace cell', it is not None, '- lip width', round(wid * 1000), 'mm =', round(wid / (p.size if p else 1) * 100, 2),
        '% of the plate - lip', round(lip * 1000), 'groove', round(groove * 1000), 'middle', round(crest * 1000), 'mm')
    res['2 a REAL click on "Creature Carapace": a thin lip along the outline (under 2 % of the plate), a groove, the middle up'] = (
        it is not None and p is not None and p.r_profile == 'CARAPACE' and wid / p.size < 0.02 and lip > groove * 1.2
        and crest > lip)
    shot('3_carapace.png')
    # 3: Creature Plate - Edge Spikes
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32, location=(0.0, 6.0, 0.0))
        ball = C.active_object
        ball.name = 'Ball'
        bpy.ops.object.shade_smooth()
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None
        setview((math.radians(40), 0.0, 0.0), (0.0, 6.0, 0.4), 4.0)
        bpy.ops.mch.bar_tool(tool='CPLATE')
        bpy.ops.mch.side_page(page='TOOL')
    yield 2.0
    st = S.mch_cplate
    st.profile = 'PUFF'
    n0 = st.spikes
    it = yield from scrolled_item('Edge Spikes')
    if it is not None:
        yield from slider_drag(it, 0.15, 12, steps=12)
    yield 1.0
    log('3 Edge Spikes cell', it is not None, '- spikes', n0, '->', st.spikes)
    yield from real_outline(ring_at(Vector((0.0, 6.0, 1.0)), 150, 110))
    pl = [o for o in S.objects if o.get(cp.SRC_KEY)]
    P = pl[-1] if pl else None
    ns, on_rim = 0, False
    if P is not None:
        me = P.data
        at_ = me.attributes.get(cp.SPIKE_TAG)
        if at_ is not None:
            tag = np.zeros(len(me.polygons), np.int32)
            at_.data.foreach_get('value', tag)
            mw = np.array(P.matrix_world)
            co = np.array([v.co for v in me.vertices]) @ mw[:3, :3].T + mw[:3, 3]
            vs = sorted({i for f, t in zip(me.polygons, tag) if t for i in f.vertices})
            per = 3 * cp.SPIKE_SEGS + 1
            ns = len(vs) // per
            sv = set(vs)
            plate_v = co[[i for i in range(len(co)) if i not in sv]]
            cen = plate_v.mean(0)
            pa = np.arctan2(plate_v[:, 1] - cen[1], plate_v[:, 0] - cen[0])
            pr_ = np.linalg.norm((plate_v - cen)[:, :2], axis=1)
            roots = [co[vs[k:k + cp.SPIKE_SEGS]].mean(0) for k in range(0, len(vs) - per + 1, per)]
            rr = []
            for x in roots:                    # (the root's distance out / the plate's reach that way: 1 = its edge)
                ang_ = math.atan2(x[1] - cen[1], x[0] - cen[0])
                near = np.abs((pa - ang_ + math.pi) % (2 * math.pi) - math.pi) < math.radians(6)
                rr.append(float(np.linalg.norm((x - cen)[:2]) / pr_[near].max()))
            on_rim = bool(rr) and min(rr) > 0.8
            log('3b plate', P.name, '- spikes', ns, '- roots at', round(min(rr), 2) if rr else None, '-',
                round(max(rr), 2) if rr else None, 'of the plate\'s reach that way (1 = its edge)')
    res['3 a REAL drag on "Edge Spikes" + a REAL outline on a ball: a plate with that many spikes, on its outline only'] = (
        it is not None and st.spikes > n0 and P is not None and ns == P.mch_cplate.spikes == st.spikes and on_rim)
    shot('4_spikes.png')
    # 4: Print Cut with a Key
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, -6.0, 0.05))
        blk = C.active_object
        blk.scale = (0.12, 0.06, 0.1)
        bpy.ops.object.transform_apply(scale=True)
        blk.name = 'Block'
        setview((math.radians(75), 0.0, math.radians(20)), (0.0, -6.0, 0.05), 0.42, 'ORTHO')
        bpy.ops.mch.bar_tool(tool='PCUT')
        bpy.ops.mch.side_page(page='TOOL')
    yield 2.0
    S.mch_print.pin_count, S.mch_print.pin_auto = 'AUTO', True
    it = yield from scrolled_item('Key')
    if it is not None:
        yield from press(it)
    yield 1.0
    yield from drag_world(Vector((-0.105, -6.0 - 0.03, 0.05)), Vector((0.105, -6.0 - 0.03, 0.052)), mods=('shift',))   # (clear of the panels)
    parts = [o for o in S.objects if o.get(p3.FROM_KEY) == 'Block']

    def closed(o):
        bm_ = bmesh.new()
        bm_.from_mesh(o.data)
        ok = not any(e_.is_boundary for e_ in bm_.edges)
        bm_.free()
        return ok
    info = json.loads(parts[0]['mch_print_pins']) if parts else {}
    log('4 Key cell', it is not None, '- style', S.mch_print.pin_style, '- parts', [o.name for o in parts], 'closed',
        [closed(o) for o in parts], '- keys', len(info.get('pins', [])), 'style', info.get('style'),
        'width', round(info.get('radius', 0) * 2000, 1), 'mm')
    res['4 a REAL click on "Key" + a REAL Shift + drag across a block: two closed parts, one square key'] = (
        it is not None and S.mch_print.pin_style == 'KEY' and len(parts) == 2 and all(closed(o) for o in parts)
        and info.get('style') == 'KEY' and len(info.get('pins', [])) == 1)
    with C.temp_override(window=w, area=a, region=r):
        if parts:
            parts[-1].location.z += 0.03
    yield 2.0
    shot('5_key.png')
    # 5: Scale Line - Scale Parts, a line on the ball
    with C.temp_override(window=w, area=a, region=r):
        P.hide_set(True) if P is not None else None
        for o in C.selected_objects:
            o.select_set(False)
        C.view_layer.objects.active = None
        setview((math.radians(40), 0.0, 0.0), (0.0, 6.0, 0.4), 4.0)
        bpy.ops.mch.bar_tool(tool='CGREEBLE')
        bpy.ops.mch.side_page(page='TOOL')
    yield 2.0
    it = yield from scrolled_item('Scale Parts')
    if it is not None:
        yield from press(it)
    yield 1.5
    rnd = next((o for o in S.objects if o.name.startswith('Scale Round')), None)
    bump = False
    if rnd is not None:
        co = np.array([v.co for v in rnd.data.vertices])
        ray = co[(np.abs(co[:, 1]) < 1e-5) & (co[:, 0] > 0)]
        ray = ray[np.argsort(-ray[:, 0])]
        z_ = ray[:, 2]
        bump = bool(((z_[1:-1] > z_[:-2]) & (z_[1:-1] > z_[2:])).any())       # (a ridge before the top: the line)
    yield from drag_world(Vector((-0.6, 5.7, 0.74)), Vector((0.6, 5.7, 0.74)))
    yield 2.0
    lines = [o for o in S.objects if gl.is_line(o)]
    log('5 Scale Parts cell', it is not None, '- Scale Round', rnd is not None, 'outline line (a ridge in its profile)', bump,
        '- lines', len(lines))
    res['5 a REAL click on "Scale Parts" + a REAL line on the ball: scales laid, each with a line round its outline'] = (
        it is not None and rnd is not None and bump and len(lines) == 1)
    shot('6_scales.png')
    bpy.types.SpaceView3D.draw_handler_remove(handle, 'WINDOW')
    for k_, v in res.items():
        log(('PASS ' if v else 'FAIL ') + k_)
    log(f'{sum(bool(v) for v in res.values())}/{len(res)} passed')
    bpy.ops.wm.quit_blender()


gen = None


def run():
    global gen
    try:
        if gen is None:
            gen = flow()
        return next(gen)
    except StopIteration:
        return None
    except Exception as ex:
        import traceback
        traceback.print_exc()
        log('ERROR', repr(ex))
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(run, first_interval=2.0)
