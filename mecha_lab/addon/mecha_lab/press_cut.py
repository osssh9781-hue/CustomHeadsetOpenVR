"""0.24.95 Press Cut (user: "내가 정한 라쏘 모양을 저장해 놓으면 그걸로 잘리는데 약간 밀리면서 잘리는 거지 - 내가 오래
누르면 더 잘리고 조금 누르면 조금만 잘리는"): a saved shape (a lasso you drew and saved, a built-in one or an imported
PNG) follows the mouse like a stamp; press on a part and hold - it is cut From Surface, deeper the longer you hold
(Start + Speed x seconds, of the part's size, up to Max); let go and it stays; Esc / right click while holding puts the
part back.  Result Cut (a pocket) or Split (the pressed-in plug becomes its own part).  The Cut tool's settings still
apply (Edge Finish / GN Edge, Split sides, the live Mirror ...): each step is a plain ``perform_closed`` on the part
as it was at the press (kept), so the pressed cut is exactly the cut a From Surface lasso of that depth makes.

Save Shape: the last closed outline drawn with Cut / Split (lasso, sketch, rectangle ...) or any lasso tool is kept
for the session (``cut_presets.remember``); Save Shape writes it as a cut shape (``cut_presets.save_loops``) - it is
then in the shape list of Press Cut and of the Cut / Split Custom stamp, in every file.

Shift + drag: draw your own stamp outline (it is the stamp at once; Save Shape keeps it).
[ / ] or F + mouse: stamp size.  R + mouse left / right: turn it (0.4 degree a pixel, Shift fine, Ctrl 5 degree
steps; click keeps, Esc puts it back), Shift + R: back to 0 degrees.
"""
from __future__ import annotations

import math
import time

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty

from . import core_geometry as cg
from . import lasso_sketch

TICK = 0.05                    # (seconds between depth steps while held)
STEP_MIN = 0.002               # (a new cut only when the depth grew by this x the part's size)


def _shape_items(self, context):
    from . import cut_presets
    return cut_presets.preset_items(self, context)


def _redraw(self, context):
    for w in getattr(context.window_manager, 'windows', ()):
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                a.tag_redraw()


def _shape_picked(self, context):
    if getattr(self, 'drawn', False):
        self.drawn = False                       # (a shape picked from the list: the drawn one gives way)
    _redraw(self, context)


LAST_RED = [None]              # 0.24.95 (triangles, press depth, deepest) of the red pocket shown last
DRAWN = [None]                 # 0.24.95 the outline drawn with Shift + drag (normalized loops) - this session only


class MCH_PG_Press(bpy.types.PropertyGroup):
    result: EnumProperty(name='Result', items=[
        ('CUT', 'Cut', 'The shape pressed into the part: a pocket'),
        ('SPLIT', 'Split', 'The pressed-in plug becomes its own part')], default='CUT')
    shape: EnumProperty(name='Shape', items=_shape_items, update=_shape_picked,
                        description='The stamp: a saved lasso, a built-in shape or an imported PNG')
    drawn: BoolProperty(name='Drawn Shape', default=False, update=_redraw,
                        description='The stamp is the outline you drew with Shift + drag (Save Shape keeps it)')
    size: FloatProperty(name='Size', default=60.0, min=4.0, max=2000.0, subtype='PIXEL', update=_redraw,
                        description='Stamp radius on screen ([ / ] change it)')
    rotation: FloatProperty(name='Rotation', default=0.0, subtype='ANGLE', update=_redraw, step=10,
                            description='Stamp turn (R + mouse: turn it, Shift + R: 0)')
    dot_size: FloatProperty(name='Dot Size', default=1.0, min=0.3, max=4.0, precision=2, update=_redraw,
                            description='How big the dots are that show where the stamp touches a part')
    floor_mode: EnumProperty(name='Floor', default='FOLLOW', items=[
        ('FOLLOW', 'Follow', 'As deep below the surface everywhere under the shape, however the part is turned to the view'),
        ('LEVEL', 'Level', 'A flat floor at the depth below the point you press: everything higher under the shape - '
                           'a raised face beside it - is cleared down to it'),
        ('FLAT', 'Flat', 'A flat floor across the view from the point you press; higher faces under the shape are left '
                         'standing (seen at an angle: a lip of the near side)')],
                             description='How deep the pressed floor is under the stamp')
    curve_x: FloatProperty(name='Curve Left-Right', default=0.0, min=-1.0, max=1.0, precision=2, update=_redraw,
                           description='The stamp bent left-right like a round stamp: + the middle goes in first and '
                                       'deepest (a round trough), - the sides first (the middle stays raised); 1 = a '
                                       'half circle across the stamp')
    curve_y: FloatProperty(name='Curve Up-Down', default=0.0, min=-1.0, max=1.0, precision=2, update=_redraw,
                           description='The stamp bent up-down (both: a bowl, or a saddle with opposite signs)')
    start: FloatProperty(name='Start', default=0.01, min=0.0005, max=1.0, subtype='FACTOR', precision=3,
                         description='Depth at the press, of the part\'s size (a quick tap)')
    speed: FloatProperty(name='Speed', default=0.12, min=0.005, soft_max=1.0, max=5.0, precision=3,
                         description='Depth added per second held, of the part\'s size')
    max_depth: FloatProperty(name='Max', default=1.0, min=0.01, max=2.0, subtype='FACTOR', precision=2,
                             description='The deepest it goes, of the part\'s size (1 = through a part as thick '
                                         'as it is long)')
    shape_name: StringProperty(name='Name', default='My Shape')


# --- the pressed cut ------------------------------------------------------------------------------------------------

def part_size(ob):
    pts = cg.object_world_bounds([ob])
    if not pts:
        return 1.0
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return max(max(hi[i] - lo[i] for i in range(3)), 1e-6)


def depth_at(st, size, seconds):
    """The depth after holding ``seconds``: (Start + Speed x seconds) x the part's size, up to Max."""
    return size * min(st.max_depth, st.start + st.speed * max(0.0, seconds))


def stamp_loops(context, center, st=None):
    """The stamp's outline(s) in region px at ``center`` (the shape at its size and turn)."""
    from . import cut_engine as ce, cut_presets
    st = st or context.scene.mch_press
    norm = DRAWN[0] if (getattr(st, 'drawn', False) and DRAWN[0]) else cut_presets.load_loops(st.shape)
    return ce.custom_loops(norm, center, st.size, st.rotation)


def use_drawn(context, pts):
    """0.24.95 (user: "여기 왜 라쏘 툴이 없어? 그릴 수가 없는데") An outline drawn with Shift + drag (region px) becomes the
    stamp, at the size it was drawn and unturned; Save Shape can keep it (it is the last drawn outline).  Returns
    (True, '') or (False, why)."""
    return use_loops(context, [pts])


def use_loops(context, loops):
    """0.24.95 (user: "원래 쓰던 라쏘랑 스케치 다 넣어 줘") The outline(s) drawn in Press Cut - with any of the shared
    shapes (Lasso, Curve Lasso, Rectangle, Circle, Ellipse, Free Draw) or a Sketch's combined outline (islands and
    holes, Enter) - become the stamp, at the size drawn and unturned.  Returns (True, '') or (False, why)."""
    from . import cut_presets
    clean = []
    for pts in loops:
        lp = [(float(x), float(y)) for x, y in pts]
        if len(lp) >= 2 and math.dist(lp[0], lp[-1]) < 1e-6:
            lp = lp[:-1]
        lp = cg.simplify_open(lp + [lp[0]], 1.5)[:-1] if len(lp) >= 3 else lp
        if len(lp) >= 3:
            clean.append(lp)
    if not clean:
        return False, 'Draw a bigger outline (Shift + drag round it)'
    if cg.find_intersections([lp for lp in clean if len(lp) >= 4]):
        return False, 'The outline crosses itself - draw it again without crossing'

    def area(lp):
        return 0.5 * abs(sum(lp[i][0] * lp[(i + 1) % len(lp)][1] - lp[(i + 1) % len(lp)][0] * lp[i][1]
                             for i in range(len(lp))))
    if max(area(lp) for lp in clean) < 40.0:
        return False, 'Draw a bigger outline (Shift + drag round it)'
    try:
        DRAWN[0] = cut_presets.normalize_loops(clean)
    except cg.CutError as ex:
        return False, str(ex)
    xs, ys = [p[0] for lp in clean for p in lp], [p[1] for lp in clean for p in lp]
    st = context.scene.mch_press
    st.size = max(4.0, max(max(xs) - min(xs), max(ys) - min(ys)) / 2.0)
    st.rotation = 0.0
    st.drawn = True
    cut_presets.remember(clean)
    return True, ''


def resample(loop, step):
    """A closed loop with no side longer than ``step`` px (a curved stamp bends along every side)."""
    out = []
    n = len(loop)
    for i in range(n):
        a, b = loop[i], loop[(i + 1) % n]
        k = max(1, int(math.ceil(math.dist(a, b) / max(step, 1e-6))))
        out += [(a[0] + (b[0] - a[0]) * j / k, a[1] + (b[1] - a[1]) * j / k) for j in range(k)]
    return out


def arc_drop(s, w, h):
    """How far a circular arc across a stamp ``2 w`` wide with ``h`` sag (all world) lies below its middle at ``s``
    (-1 .. 1 across): 0 in the middle, ``h`` at the sides."""
    h = abs(h)
    if h < 1e-12 or w < 1e-12:
        return 0.0
    x = min(abs(s), 1.0) * w
    r = (w * w + h * h) / (2.0 * h)
    return h - (math.sqrt(max(r * r - x * x, 0.0)) - (r - h))


class SurfaceFloor:
    """0.24.95 The far cap of a From Surface cutter, point by point (``core_geometry.FLOOR``):

    * Follow Surface: as deep below the surface under each point as the depth (the pocket follows a slanted or
      curved surface - a flat cut seen at an angle left a lip of the near side standing and missed the far side);
      the near cap moves in front of all the surface under the shape.
    * Level (user: "내가 선택한 면보다 옆에 면이 높이 있으면 거기는 그냥 내가 선택한 위치까지 지워 버리는 버튼"): a flat floor
      at the depth below the point pressed, the near cap in front of all the surface - a raised face beside it under
      the shape is cleared down to that floor.
    * Curve Left-Right / Up-Down: the stamp's face bent into a circular arc (+ the middle deepest, - the sides).
    Never above the surface (a press not yet that deep cuts nothing there).  Points off the parts take the depth of
    the nearest point that is on them."""

    def __init__(self, context, targets, projector, loops, spacing, follow=True, curve=(0.0, 0.0), center=None,
                 angle=0.0, depth=0.1, level=False):
        self.targets = [t for t in targets if t is not None]
        self.projector = projector
        self.vd = projector.view_dir
        self.spacing = max(2.0, float(spacing))
        self.follow = bool(follow) and not level
        self.level = bool(level)
        self.curve = (float(curve[0]), float(curve[1]))
        self.depth = float(depth)
        self.cache = {}
        pts = [p for lp in loops for p in lp]
        self.center = center or (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        self.angle = float(angle)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        samples = list(pts)
        step = self.spacing * 2.0
        edges = [(lp[i], lp[(i + 1) % len(lp)]) for lp in loops for i in range(len(lp))]

        def inside(q):                           # (even-odd: holes stay out)
            n = 0
            for (x0, y0), (x1, y1) in edges:
                if (y0 > q[1]) != (y1 > q[1]) and q[0] < x0 + (q[1] - y0) * (x1 - x0) / (y1 - y0):
                    n += 1
            return n % 2 == 1
        x = min(xs) + step / 2
        while x < max(xs):                       # (a coarse grid inside the shape: the nearest surface, the
            y = min(ys) + step / 2               #  depth for points off the parts, flat or not)
            while y < max(ys):
                if inside((x, y)):
                    samples.append((x, y))
                y += step
            x += step
        if inside(self.center):
            samples.append(self.center)
        self.known = []
        for q in samples:
            t = self._ray_t(q)
            if t is not None:
                self.known.append((q[0], q[1], t))
        self.t_min = min((k[2] for k in self.known), default=None)
        self.t_ref = self._ray_t(self.center)      # (Level: the surface at the point pressed - else the nearest)
        if self.t_ref is None and self.known:
            self.t_ref = min(self.known, key=lambda q: (q[0] - self.center[0]) ** 2 + (q[1] - self.center[1]) ** 2)[2]
        self.px_world = self._px_world()
        c, s = math.cos(self.angle), math.sin(self.angle)
        cx, cy = self.center
        uv = [((x - cx) * c + (y - cy) * s, -(x - cx) * s + (y - cy) * c) for x, y in pts]
        u0, u1 = min(p[0] for p in uv), max(p[0] for p in uv)
        v0, v1 = min(p[1] for p in uv), max(p[1] for p in uv)
        self.uc, self.vc = (u0 + u1) / 2, (v0 + v1) / 2
        self.wu, self.wv = max((u1 - u0) / 2, 1e-6), max((v1 - v0) / 2, 1e-6)
        self.planar = self._planar()

    def _planar(self):
        """The surface under the shape is one flat face and the stamp is not bent: the far cap is flat too (no grid,
        no extra points - a pocket in a flat face seen at an angle keeps clean big faces)."""
        if abs(self.curve[0]) > 1e-4 or abs(self.curve[1]) > 1e-4:
            return False
        if not self.follow:
            return True
        k = self.known
        if len(k) < 3:
            return True
        import numpy as np
        A = np.array([(x, y, 1.0) for x, y, _t in k])
        b = np.array([t for _x, _y, t in k])
        coef, *_ = np.linalg.lstsq(A, b, rcond=None)
        span = max(abs(b.max() - b.min()), 1e-9)
        # (the screen rays are float32 from far behind the view: a flat face reads up to ~2e-4 off a plane - 0.24.95
        #  a flat top seen from straight above came out "curved" and got a grid floor; half a millimetre is flat)
        return float(np.abs(A @ coef - b).max()) <= max(5e-4, 2e-3 * span)

    def _ray_t(self, xy):
        """How far along the view the first surface of the parts under screen ``xy`` lies (None: none there)."""
        try:
            o, d = self.projector.ray(xy)
        except Exception:
            return None
        best = None
        for ob in self.targets:
            try:
                mw = ob.matrix_world
                inv = mw.inverted_safe()
                ok, loc, _n, _i = ob.ray_cast(inv @ o, (inv.to_3x3() @ d).normalized())
            except (RuntimeError, ReferenceError):
                continue
            if ok:
                t = (mw @ loc).dot(self.vd)
                best = t if best is None else min(best, t)
        return best

    def t(self, xy):
        key = (round(float(xy[0]), 3), round(float(xy[1]), 3))
        got = self.cache.get(key)
        if got is None:
            got = self._ray_t(xy)
            if got is None:                      # (off the parts: the nearest point that is on them)
                if not self.known:
                    return None
                got = min(self.known, key=lambda k: (k[0] - xy[0]) ** 2 + (k[1] - xy[1]) ** 2)[2]
            self.cache[key] = got
        return got

    def _px_world(self):
        """World size of one screen pixel at the surface under the stamp (its middle, else the nearest hit)."""
        if not self.known:
            return 0.0
        k = min(self.known, key=lambda q: (q[0] - self.center[0]) ** 2 + (q[1] - self.center[1]) ** 2)
        try:
            o0, d0 = self.projector.ray(self.center)
            o1, d1 = self.projector.ray((self.center[0] + 1.0, self.center[1]))
            plane = o0 + d0 * 0.0
            plane = plane + self.vd * (k[2] - plane.dot(self.vd))
            p0, _t = cg._plane_hit(o0, d0, plane, self.vd)
            p1, _t = cg._plane_hit(o1, d1, plane, self.vd)
            return max((p1 - p0).length, 1e-9)
        except cg.CutError:
            return 0.0

    def curve_off(self, xy):
        """The curve's drop below the deepest point at ``xy`` (<= 0)."""
        if (abs(self.curve[0]) < 1e-4 and abs(self.curve[1]) < 1e-4) or self.px_world <= 0.0:
            return 0.0
        c, s = math.cos(self.angle), math.sin(self.angle)
        cx, cy = self.center
        u = (xy[0] - cx) * c + (xy[1] - cy) * s
        v = -(xy[0] - cx) * s + (xy[1] - cy) * c
        k = self.px_world
        off = 0.0
        for val, mid, half, amt in ((u, self.uc, self.wu, self.curve[0]), (v, self.vc, self.wv, self.curve[1])):
            h = amt * half * k
            if abs(h) < 1e-12:
                continue
            d = arc_drop((val - mid) / half, half * k, h)
            off += -d if h > 0 else -(abs(h) - d)
        return off

    def offset(self, xy, far_co):
        """How far along the view the cutter's far cap at screen ``xy`` lies from the far plane through ``far_co``."""
        t_far = far_co.dot(self.vd)
        above = max(1e-4, self.depth * 0.05)
        if self.level and self.t_ref is not None:        # (Level: flat at the depth below the point pressed)
            base = self.t_ref + self.depth - t_far
            low = ((self.t_min if self.t_min is not None else self.t_ref) - 0.5 * above) - t_far
            return max(base + self.curve_off(xy), low)
        tx = self.t(xy) if self.follow else None
        if tx is None:                                   # (flat: the far plane is the depth below the middle)
            base, low = 0.0, -(self.depth + 0.5 * above)
        else:
            base, low = tx + self.depth - t_far, tx - 0.5 * above - t_far
        return max(base + self.curve_off(xy), low)

    def near_shift(self, near_co):
        if not (self.follow or self.level) or self.t_min is None:
            return 0.0
        margin = max(1e-4, self.depth * 0.05)
        return max(0.0, near_co.dot(self.vd) - (self.t_min - margin))


class Press:
    """One press on one part: the part as it was (kept), cut again From Surface at each new depth."""

    def __init__(self, context, target, loops, projector, result='CUT', center=None, angle=0.0, curve=(0.0, 0.0),
                 spacing=6.0, follow=False, level=False):
        from . import ramp_edit
        old = ramp_edit.live_target(context, ramp_edit.ALL_KINDS)
        if old is not None:                      # (an earlier live cut stays as it is: the Cut Depth set while
            ramp_edit.finish(old)                #  pressing must not cut it again)
        self.target = target
        self.curve = (float(curve[0]), float(curve[1]))
        self.curved = abs(self.curve[0]) > 1e-4 or abs(self.curve[1]) > 1e-4
        self.follow = bool(follow) and not level
        self.level = bool(level)
        self.spacing = max(2.0, float(spacing))
        lps = [[tuple(p) for p in lp] for lp in loops]
        shaped = self.curved or self.follow or self.level
        self.projector = projector
        pts = [p for lp in lps for p in lp]
        self.center = center or (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        self.angle = float(angle)
        self.loops = lps
        self.sfloor = None
        if shaped:
            self.sfloor = SurfaceFloor(context, [target], projector, lps, self.spacing, follow=self.follow,
                                       curve=self.curve, center=self.center, angle=self.angle, level=self.level)
            if not self.sfloor.planar:           # (a bent stamp / a curved surface: the outline follows it too)
                self.loops = [resample(lp, self.spacing) for lp in lps]
        self.px_world = self.sfloor.px_world if self.sfloor is not None else 0.0
        self.result = result
        self.size = part_size(target)
        self.backup = target.data.copy()
        self.backup.name = 'MCH_PressBackup_' + target.name
        cut = context.scene.mch_cut
        self.saved = (cut.depth_mode, cut.depth)
        self.depth = 0.0
        self.pieces = []
        self.message = ''
        self._bvh = None

    def _old_surface(self):
        """The part's surface as it was (world space): how deep a point of the cut lies under it."""
        if self._bvh is None:
            import numpy as np
            from mathutils.bvhtree import BVHTree
            me = self.backup
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get('co', co)
            mw = np.array(self.target.matrix_world)
            co = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
            self._bvh = BVHTree.FromPolygons([tuple(v) for v in co], [tuple(p.vertices) for p in me.polygons])
        return self._bvh

    def pocket(self):
        """0.24.95 (user: "깊이 들어갈 때 메쉬 쪽에 붉은색으로 얼마나 들어가고 있는지 보이게 해 줘") The faces the press
        made on the part - its pocket's walls and floor - as triangles (world space, a hair towards the view) with a
        colour per corner: light red at the surface to deep red at the bottom (how far below the part as it was, over
        the press depth).  Returns (positions, colours, deepest)."""
        import numpy as np
        from mathutils import Vector
        me = self.target.data
        if self.depth <= 0.0 or self.backup is None or not len(me.polygons):
            return [], [], 0.0
        bvh = self._old_surface()
        mw = np.array(self.target.matrix_world)
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
        me.calc_loop_triangles()
        tv = np.empty(len(me.loop_triangles) * 3, np.int32)
        me.loop_triangles.foreach_get('vertices', tv)
        tv = tv.reshape(-1, 3)
        cen = co[tv].mean(axis=1)
        idx = np.arange(len(tv))
        xy = _screen_np(self.projector, cen)         # (only round the stamp: its screen box and a margin)
        if xy is not None:
            pts = [p for lp in self.loops for p in lp]
            x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
            y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
            m = 0.15 * max(x1 - x0, y1 - y0) + 4.0
            idx = np.nonzero((xy[:, 0] >= x0 - m) & (xy[:, 0] <= x1 + m) & (xy[:, 1] >= y0 - m)
                             & (xy[:, 1] <= y1 + m))[0]
        tol = max(1e-7, min(1e-4 * self.size, 0.05 * self.depth))
        shift = -np.array(self.projector.view_dir) * (1e-3 * self.size)
        under = {}

        def below(i):
            d = under.get(i)
            if d is None:
                hit = bvh.find_nearest(Vector(co[i]))
                d = hit[3] if hit[0] is not None else 0.0
                under[i] = d
            return d
        pos, col = [], []
        for t in idx:
            hit = bvh.find_nearest(Vector(cen[t]))
            if hit[0] is None or hit[3] <= tol:
                continue                               # (a face of the part as it was)
            for i in tv[t]:
                k = min(1.0, below(int(i)) / self.depth)
                pos.append(tuple(float(v) for v in co[i] + shift))
                col.append((1.0 - 0.1 * k, 0.5 * (1.0 - k), 0.4 * (1.0 - k), 0.35 + 0.45 * k))
        return pos, col, float(max(under.values(), default=0.0))

    def floor(self, depth):
        """The cutter's far cap at ``depth`` (``core_geometry.FLOOR``): None for a flat stamp on a flat cut."""
        if self.sfloor is None:
            return None
        self.sfloor.depth = float(depth)
        return self.sfloor

    def _restore(self):
        from . import ramp_edit
        for name in self.pieces:
            ob = bpy.data.objects.get(name)
            if ob is not None:
                me = ob.data
                bpy.data.objects.remove(ob)
                if me is not None and me.users == 0:
                    bpy.data.meshes.remove(me)
        self.pieces = []
        ramp_edit._copy_into(self.backup, self.target.data)
        try:
            bpy.context.view_layer.update()      # (the surface the Follow Surface ray casts see: the part as it was)
        except (AttributeError, RuntimeError):
            pass

    def cut_to(self, context, depth):
        """The part as it was, cut From Surface ``depth`` deep.  A depth that does not cut cleanly keeps the last
        one that did; returns False then."""
        from . import cut_engine as ce, cut_presets
        cut = context.scene.mch_cut
        prev = self.depth
        self._restore()
        before = set(bpy.data.objects.keys())
        cut.depth_mode, cut.depth = 'SURFACE', max(depth, 1e-5)
        cut_presets.QUIET[0] = True              # (the stamp is not "the last drawn outline")
        cg.FLOOR[0] = self.floor(depth)          # (a curved stamp: its face bent)
        try:
            self.message = ce.perform_closed(context, self.result, [self.target], self.loops, self.projector)
        except (cg.CutError, RuntimeError) as ex:
            self.message = str(ex)
            cg.FLOOR[0] = None
            cut_presets.QUIET[0] = False
            self._restore()
            if prev > 0.0 and depth != prev:
                self.cut_to(context, prev)
            return False
        finally:
            cut_presets.QUIET[0] = False
            cg.FLOOR[0] = None
        self.pieces = [o.name for o in bpy.data.objects if o.name not in before]
        self.depth = depth
        return True

    def _settings_back(self, context):
        cut = context.scene.mch_cut
        if (cut.depth_mode, cut.depth) != self.saved:
            cut.depth_mode, cut.depth = self.saved

    def finish(self, context):
        self._settings_back(context)
        if self.backup is not None and self.backup.users == 0:
            bpy.data.meshes.remove(self.backup)
        self.backup = None

    def cancel(self, context):
        if self.backup is not None:
            self._restore()
        self.finish(context)


def press_target(context, projector, xy, loops=None):
    """The part under ``xy`` - the nearest mesh the mouse is on (Target Auto), only a selected one (Selected) or only
    the active one (Active) - or, 0.24.95 (user: "이렇게는 또 안 잘려" - the stamp's middle just off a part's side),
    the part the stamp ``loops`` cover most; None when it covers none."""
    from . import cut_engine as ce
    mode = getattr(context.scene.mch_cut, 'targets', 'AUTO')
    if mode == 'ACTIVE':
        act = context.view_layer.objects.active
        if act is None or act.type != 'MESH':
            return None
        probe = [xy] + (ce._loop_samples(loops, step=10.0, grid=11) if loops else [])
        return act if any(ce.surface_hit(context, [act], projector, q) is not None for q in probe) else None
    picked = ce.pick_mesh_under(context, projector, xy)
    if picked is not None and ce._auto_candidate(picked) and (mode != 'SELECTED' or picked.select_get()):
        return picked
    if not loops:
        return None
    cands = [o for o in ce.auto_targets(context.view_layer, projector, loops)
             if mode != 'SELECTED' or o.select_get()]
    if not cands:
        return None
    probe = ce._loop_samples(loops, step=10.0, grid=11) or [xy]   # (along the outline and inside it: every 2nd
    #                                    corner alone missed a square whose corners were all off the part - nothing cut)

    def covered(ob):
        return sum(1 for q in probe if ce.surface_hit(context, [ob], projector, q) is not None)
    best = max(cands, key=covered)
    return best if covered(best) else None


# --- drawing --------------------------------------------------------------------------------------------------------

def contact_points(context, loops_px, center_px, offset=(0.0, 0.0), step=8.0):
    """0.24.95 (user: "지금 내가 메쉬에 닿아 있는 부분을 조그만한 점으로 표시해 주면 작업할 때 편하겠는데") Where a stamp at
    ``loops_px`` touches a mesh: (points along the outline that are over a mesh, the contact point - the middle when
    it is over one, else the first covered outline point - or None).  Points in the loops' own pixel space;
    ``offset`` turns them into the region's pixels for the rays (a tool cursor draws in window pixels)."""
    region = getattr(context, 'region', None)
    rv3d = getattr(context, 'region_data', None)
    if region is None or rv3d is None or region.type != 'WINDOW':
        return [], None
    from bpy_extras import view3d_utils
    from . import target_rules
    try:
        dg = context.evaluated_depsgraph_get()
    except (AttributeError, RuntimeError):
        return [], None

    def over(q):
        rq = (q[0] - offset[0], q[1] - offset[1])
        if not (0 <= rq[0] < region.width and 0 <= rq[1] < region.height):
            return False
        o = view3d_utils.region_2d_to_origin_3d(region, rv3d, rq)
        d = view3d_utils.region_2d_to_vector_3d(region, rv3d, rq)
        hit, _loc, _n, _i, ob, _m = target_rules.scene_ray(context, dg, o, d)
        return bool(hit and ob is not None and ob.type == 'MESH')
    dots = []
    for lp in loops_px:
        for q in resample(lp, step):
            if over(q):
                dots.append(q)
    contact = center_px if over(center_px) else (dots[0] if dots else None)
    return dots, contact


def dot_sizes(context):
    """(outline dot, contact dot ring, contact dot core) in px: 0.24.95 (user: "메쉬 위에 뜨는 점이 너무 작은데") about
    twice the first ones, times the Dot Size setting and Blender's UI scale."""
    try:
        k = float(context.scene.mch_press.dot_size)
    except AttributeError:
        k = 1.0
    try:
        ui = float(context.preferences.system.ui_scale)
    except AttributeError:
        ui = 1.0
    k *= ui if ui > 0.0 else 1.0                  # (no window: Blender reads 0 - the plain size then)
    return 8.0 * k, 18.0 * k, 11.0 * k


def _dot_shader():
    import gpu
    for name in ('POINT_UNIFORM_COLOR', 'UNIFORM_COLOR'):    # (round points where Blender has the shader)
        try:
            return gpu.shader.from_builtin(name)
        except (ValueError, TypeError):
            continue
    return None


def draw_contact(context, loops_px, center_px, offset=(0.0, 0.0)):
    """The contact dots of a stamp preview (small ones on the outline over a mesh, a bigger one where it presses)."""
    try:
        import gpu
        from gpu_extras.batch import batch_for_shader
        small, ring, core = dot_sizes(context)
        dots, contact = contact_points(context, loops_px, center_px, offset, step=max(8.0, small * 1.6))
        if not dots and contact is None:
            return
        sh = _dot_shader()
        if sh is None:
            return
        gpu.state.blend_set('ALPHA')
        sh.bind()
        if dots:
            gpu.state.point_size_set(small + 2.0)                 # (a dark rim: seen on light and dark parts)
            sh.uniform_float('color', (0.05, 0.12, 0.08, 0.85))
            batch_for_shader(sh, 'POINTS', {'pos': dots}).draw(sh)
            gpu.state.point_size_set(small)
            sh.uniform_float('color', (0.45, 1.0, 0.65, 1.0))
            batch_for_shader(sh, 'POINTS', {'pos': dots}).draw(sh)
        if contact is not None:
            gpu.state.point_size_set(ring + 2.0)
            sh.uniform_float('color', (0.05, 0.12, 0.08, 0.85))
            batch_for_shader(sh, 'POINTS', {'pos': [contact]}).draw(sh)
            gpu.state.point_size_set(ring)
            sh.uniform_float('color', (1.0, 1.0, 1.0, 1.0))
            batch_for_shader(sh, 'POINTS', {'pos': [contact]}).draw(sh)
            gpu.state.point_size_set(core)
            sh.uniform_float('color', (0.15, 0.85, 0.45, 1.0))
            batch_for_shader(sh, 'POINTS', {'pos': [contact]}).draw(sh)
        gpu.state.point_size_set(1.0)
        gpu.state.blend_set('NONE')
    except Exception:          # never break viewport drawing
        pass


def draw_cursor(context, xy):
    """Idle stamp preview at the cursor (WorkSpaceTool.draw_cursor, window px)."""
    if TURNING[0]:
        return
    try:
        import gpu
        from . import cut_engine as ce
        st = context.scene.mch_press
        loops = stamp_loops(context, (float(xy[0]), float(xy[1])), st)
        sh = ce._shader()
        gpu.state.blend_set('ALPHA')
        col = (1.0, 0.62, 0.25, 1.0) if st.result == 'CUT' else (0.45, 1.0, 0.35, 1.0)
        for lp in loops:
            ce._draw_lines(sh, lp, col, closed=True, width=1.5)
        cx, cy = float(xy[0]), float(xy[1])
        reg = getattr(context, 'region', None)
        draw_contact(context, loops, (cx, cy), (reg.x, reg.y) if reg is not None else (0.0, 0.0))
        c, s = math.cos(st.rotation), math.sin(st.rotation)
        for amt, (ax, ay) in ((st.curve_x, (c, s)), (st.curve_y, (-s, c))):
            if abs(amt) > 1e-4:                  # (a bent stamp: the line it bends across, dashed by its sign)
                r = st.size * (0.9 if amt > 0 else 0.6)
                ce._draw_lines(sh, [(cx - ax * r, cy - ay * r), (cx + ax * r, cy + ay * r)],
                               (0.45, 0.85, 1.0, 0.9), width=1.0 + 2.0 * abs(amt))
        gpu.state.blend_set('NONE')
    except Exception:          # never break viewport drawing
        pass


def _screen_np(projector, pts):
    """Region px of world points ``pts`` (N x 3) for a view projector or a test projector; None if unknown."""
    import numpy as np
    try:
        if hasattr(projector, 'ppu') and hasattr(projector, '_axes'):
            right, up = projector._axes()
            d = pts - np.array(projector.center)
            return np.stack([projector.size[0] / 2 + d @ np.array(right) * projector.ppu,
                             projector.size[1] / 2 + d @ np.array(up) * projector.ppu], 1)
        rv3d, region = getattr(projector, 'rv3d', None), getattr(projector, 'region', None)
        if rv3d is None or region is None:
            return None
        h = np.c_[pts, np.ones(len(pts))] @ np.array(rv3d.perspective_matrix).T
        w = h[:, 3:4].copy()
        w[np.abs(w) < 1e-9] = 1e-9
        ndc = h[:, :2] / w
        return np.stack([(ndc[:, 0] + 1.0) * 0.5 * region.width, (ndc[:, 1] + 1.0) * 0.5 * region.height], 1)
    except Exception:
        return None


def _draw_pocket(op):
    """0.24.95 While pressing: the pocket on the part in red, deeper = darker (``Press.pocket``)."""
    try:
        if bpy.context.region != op.region or not op.red[0]:
            return
        import gpu
        from gpu_extras.batch import batch_for_shader
        if op.red_batch is None:
            op.red_sh = gpu.shader.from_builtin('SMOOTH_COLOR')
            op.red_batch = batch_for_shader(op.red_sh, 'TRIS', {'pos': op.red[0], 'color': op.red[1]})
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('LESS_EQUAL')
        gpu.state.depth_mask_set(False)
        op.red_batch.draw(op.red_sh)
        gpu.state.depth_mask_set(True)
        gpu.state.depth_test_set('NONE')
        gpu.state.blend_set('NONE')
    except Exception:
        pass


def _draw_holding(op):
    try:
        import blf
        import gpu
        from . import cut_engine as ce
        if bpy.context.region != op.region:
            return
        sh = ce._shader()
        gpu.state.blend_set('ALPHA')
        for lp in op.press.loops:
            ce._draw_lines(sh, lp, (1.0, 0.85, 0.3, 1.0), closed=True, width=2.5)
        gpu.state.blend_set('NONE')
        x, y = op.anchor
        blf.size(0, 15)
        blf.color(0, 1.0, 0.92, 0.6, 1.0)
        blf.position(0, x + op.press_st.size * 0.8 + 10, y, 0)
        unit = bpy.context.scene.unit_settings.scale_length or 1.0
        blf.draw(0, f'{op.press.result.title()} {op.press.depth * unit * 100:.1f} cm  (hold: deeper, release: keep, '
                    'Esc: back)')
    except Exception:
        pass


# --- operators ------------------------------------------------------------------------------------------------------

class MCH_OT_press_cut(bpy.types.Operator):
    """Press and hold on a part: the shape is cut in, deeper the longer you hold; let go to keep it"""
    bl_idname = 'mch.press_cut'
    bl_label = 'Press Cut'
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        region, rv3d = context.region, getattr(context, 'region_data', None)
        if region is None or rv3d is None or region.type != 'WINDOW':
            return {'PASS_THROUGH'}
        from . import cut_engine as ce
        st = context.scene.mch_press
        xy = (float(event.mouse_region_x), float(event.mouse_region_y))
        projector = ce.make_projector(region, rv3d)
        try:
            loops = stamp_loops(context, xy, st)
        except (cg.CutError, ValueError, OSError) as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        target = press_target(context, projector, xy, loops)
        if target is None:
            self.report({'WARNING'}, 'Press on a part (the stamp is not over one)')
            return {'CANCELLED'}
        try:
            from . import safety_save
            safety_save.checkpoint('Mecha Press Cut')
        except Exception:
            pass
        self.press = Press(context, target, loops, projector, st.result, center=xy, angle=st.rotation,
                           curve=(st.curve_x, st.curve_y), spacing=max(3.0, st.size / 10.0),
                           follow=st.floor_mode == 'FOLLOW', level=st.floor_mode == 'LEVEL')
        self.press_st = st
        self.region = region
        self.anchor = xy
        self.t0 = time.perf_counter()
        if not self.press.cut_to(context, depth_at(st, self.press.size, 0.0)):
            msg = self.press.message
            self.press.cancel(context)
            self.report({'WARNING'}, msg[:200] or 'Nothing was cut')
            return {'CANCELLED'}
        self.full = False
        self.red, self.red_batch, self.red_sh = ([], [], 0.0), None, None
        self._update_red()
        self.handle = bpy.types.SpaceView3D.draw_handler_add(_draw_holding, (self,), 'WINDOW', 'POST_PIXEL')
        self.handle_red = bpy.types.SpaceView3D.draw_handler_add(_draw_pocket, (self,), 'WINDOW', 'POST_VIEW')
        self.timer = context.window_manager.event_timer_add(TICK, window=context.window)
        context.window_manager.modal_handler_add(self)
        region.tag_redraw()
        return {'RUNNING_MODAL'}

    def _update_red(self):
        """The red pocket of the press as it is now (never stops the press)."""
        try:
            self.red = self.press.pocket()
        except Exception as ex:
            print('[Mecha Lab] press pocket:', ex)
            self.red = ([], [], 0.0)
        self.red_batch = None
        LAST_RED[0] = (len(self.red[0]) // 3, self.press.depth, self.red[2])

    def _end(self, context):
        try:
            context.window_manager.event_timer_remove(self.timer)
        except (ValueError, RuntimeError, ReferenceError):
            pass
        for h in (self.handle, getattr(self, 'handle_red', None)):
            try:
                if h is not None:
                    bpy.types.SpaceView3D.draw_handler_remove(h, 'WINDOW')
            except (ValueError, RuntimeError):
                pass
        self.region.tag_redraw()

    def modal(self, context, event):
        et, ev = event.type, event.value
        if et == 'TIMER' and not self.full:
            st = self.press_st
            d = depth_at(st, self.press.size, time.perf_counter() - self.t0)
            if d >= self.press.size * st.max_depth - 1e-9:
                self.full = True
            if d - self.press.depth >= STEP_MIN * self.press.size or self.full:
                if not self.press.cut_to(context, d):
                    self.full = True              # (it does not go deeper cleanly: stays where it was)
                self._update_red()
                self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if et == 'LEFTMOUSE' and ev == 'RELEASE':
            self._end(context)
            msg = self.press.message
            depth = self.press.depth
            self.press.finish(context)
            self.report({'INFO'}, f'Press {self.press.result.title()}: {depth:.4f} deep | {msg[:160]}')
            return {'FINISHED'}
        if (et == 'ESC' and ev == 'PRESS') or (et == 'RIGHTMOUSE' and ev == 'PRESS'):
            self._end(context)
            self.press.cancel(context)
            self.report({'INFO'}, 'Press Cut: put back')
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


class MCH_OT_press_adjust(bpy.types.Operator):
    """Press Cut stamp: size ([ / ]) or turn (R / Shift + R)"""
    bl_idname = 'mch.press_adjust'
    bl_label = 'Press Stamp Size / Turn'
    bl_options = {'INTERNAL'}

    size: FloatProperty(default=1.0)
    turn: FloatProperty(default=0.0)

    def execute(self, context):
        st = context.scene.mch_press
        st.size = max(4.0, min(2000.0, st.size * self.size))
        a = st.rotation + math.radians(self.turn)
        st.rotation = math.atan2(math.sin(a), math.cos(a))
        return {'FINISHED'}


TURN_PX = 0.4                  # (degrees per pixel the mouse moves while turning the stamp)
TURN_FINE = 0.08               # (with Shift)
TURN_SNAP = 5.0                # (with Ctrl: 5 degree steps)
TURNING = [False]              # (the idle stamp previews stay hidden while it is turned at its own place)


def turn_target(context):
    """(owner, property, size px, shape stem) of the stamp R turns: Press Cut's, or the Cut / Split Custom stamp;
    None for anything else (Blender's own R then)."""
    from . import tool_state as ts
    scene = context.scene
    if ts.effective_tool(context) == 'PRESS' and hasattr(scene, 'mch_press'):
        st = scene.mch_press
        return st, 'rotation', st.size, st.shape
    b = getattr(scene, 'mch_brush', None)
    if b is not None and b.shape == 'CUSTOM':
        return b, 'custom_rotation', b.custom_size, scene.mch_png_preset
    return None


def turn_angle(start, dx, ctrl=False, shift=False):
    """The stamp's turn after the mouse moved ``dx`` px from where R was pressed (radians, -180 .. 180 degrees):
    0.4 degree a pixel, Shift 0.08 (fine), Ctrl in 5 degree steps."""
    a = math.degrees(start) + dx * (TURN_FINE if shift else TURN_PX)
    if ctrl:
        a = round(a / TURN_SNAP) * TURN_SNAP
    a = (a + 180.0) % 360.0 - 180.0
    return math.radians(a)


def _draw_turn(op):
    try:
        import blf
        import gpu
        from . import cut_engine as ce
        if bpy.context.region != op.region:
            return
        ang = getattr(op.owner, op.prop)
        sh = ce._shader()
        gpu.state.blend_set('ALPHA')
        cx, cy = op.center
        if op.norm:
            for lp in ce.custom_loops(op.norm, op.center, op.size, ang):
                ce._draw_lines(sh, lp, (1.0, 0.85, 0.3, 1.0), closed=True, width=2.0)
        r = op.size * 1.15
        ce._draw_lines(sh, [(cx, cy), (cx + r * math.cos(ang), cy + r * math.sin(ang))], (0.45, 0.8, 1.0, 1.0),
                       width=1.5)
        gpu.state.blend_set('NONE')
        blf.size(0, 15)
        blf.color(0, 1.0, 0.92, 0.6, 1.0)
        blf.position(0, cx + op.size + 14, cy + 6, 0)
        blf.draw(0, f'{math.degrees(ang):.1f}\u00b0')
        blf.size(0, 12)
        blf.color(0, 0.85, 0.87, 0.9, 1.0)
        blf.position(0, cx + op.size + 14, cy - 14, 0)
        blf.draw(0, 'move: turn   Ctrl: 5\u00b0 steps   Shift: fine   click / R: keep   Esc: back')
    except Exception:
        pass


class MCH_OT_stamp_turn(bpy.types.Operator):
    """R: turn the stamp with the mouse - left / right, 0.4 degree a pixel (Shift: fine, Ctrl: 5 degree steps);
    click / Enter / R keeps, Esc / right click puts it back.  Shift + R: back to 0 degrees"""
    bl_idname = 'mch.stamp_turn'
    bl_label = 'Turn Stamp'
    bl_options = {'INTERNAL'}

    reset: BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        return turn_target(context) is not None

    def invoke(self, context, event):
        owner, prop, size, stem = turn_target(context)
        if self.reset:
            setattr(owner, prop, 0.0)
            if context.area:
                context.area.tag_redraw()
            self.report({'INFO'}, 'Stamp turn 0\u00b0')
            return {'FINISHED'}
        if context.region is None or context.region.type != 'WINDOW':
            return {'CANCELLED'}
        from . import cut_presets
        self.owner, self.prop, self.size = owner, prop, size
        self.start = getattr(owner, prop)
        self.x0 = event.mouse_x
        self.center = (float(event.mouse_region_x), float(event.mouse_region_y))
        self.region = context.region
        try:
            self.norm = cut_presets.load_loops(stem)
        except (cg.CutError, ValueError, OSError):
            self.norm = None
        TURNING[0] = True
        self.handle = bpy.types.SpaceView3D.draw_handler_add(_draw_turn, (self,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        self.region.tag_redraw()
        return {'RUNNING_MODAL'}

    def _end(self):
        TURNING[0] = False
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self.handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        self.region.tag_redraw()

    def modal(self, context, event):
        et, ev = event.type, event.value
        if et == 'MOUSEMOVE':
            setattr(self.owner, self.prop, turn_angle(self.start, event.mouse_x - self.x0, event.ctrl, event.shift))
            self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if getattr(event, 'is_repeat', False):
            return {'RUNNING_MODAL'}
        if ev == 'PRESS' and et in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER', 'SPACE', 'R'}:
            self._end()
            self.report({'INFO'}, f'Stamp turn {math.degrees(getattr(self.owner, self.prop)):.1f}\u00b0')
            return {'FINISHED'}
        if ev == 'PRESS' and et in {'RIGHTMOUSE', 'ESC'}:
            setattr(self.owner, self.prop, self.start)
            self._end()
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


def _draw_outline(op):
    try:
        import gpu
        from . import cut_engine as ce
        if bpy.context.region != op.region or len(op.pts) < 2:
            return
        sh = ce._shader()
        gpu.state.blend_set('ALPHA')
        ce._draw_lines(sh, op.pts, (1.0, 0.85, 0.3, 1.0), closed=False, width=2.0)
        ce._draw_lines(sh, [op.pts[-1], op.pts[0]], (1.0, 0.85, 0.3, 0.35), closed=False, width=1.0)
        gpu.state.blend_set('NONE')
    except Exception:
        pass


class MCH_OT_press_draw(bpy.types.Operator):
    """Shift + drag: draw your own stamp outline - let go and it is the stamp (Save Shape keeps it)"""
    bl_idname = 'mch.press_draw'
    bl_label = 'Draw Stamp'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        if context.region is None or context.region.type != 'WINDOW':
            return {'PASS_THROUGH'}
        self.region = context.region
        self.pts = [(float(event.mouse_region_x), float(event.mouse_region_y))]
        TURNING[0] = True                        # (the idle stamp preview hidden while drawing)
        self.handle = bpy.types.SpaceView3D.draw_handler_add(_draw_outline, (self,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _end(self):
        TURNING[0] = False
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self.handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        self.region.tag_redraw()

    def modal(self, context, event):
        et, ev = event.type, event.value
        if et in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            q = (float(event.mouse_region_x), float(event.mouse_region_y))
            if math.dist(q, self.pts[-1]) >= 3.0:
                self.pts.append(q)
                self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if et == 'LEFTMOUSE' and ev == 'RELEASE':
            self._end()
            ok, why = use_drawn(context, self.pts)
            if not ok:
                self.report({'WARNING'}, why)
                return {'CANCELLED'}
            self.report({'INFO'}, 'Drawn stamp ready - press on a part (Save Shape keeps it)')
            return {'FINISHED'}
        if ev == 'PRESS' and et in {'ESC', 'RIGHTMOUSE'}:
            self._end()
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


class MCH_OT_save_cut_shape(bpy.types.Operator):
    """Save the last outline you drew (Cut / Split / any lasso: lasso, sketch, rectangle ...) as a cut shape - for
    Press Cut and the Cut / Split Custom stamp, in every file"""
    bl_idname = 'mch.save_cut_shape'
    bl_label = 'Save Shape'
    bl_options = {'REGISTER'}

    name: StringProperty(name='Name', default='')
    use: BoolProperty(name='Use It', default=True, description='Make it the Press Cut shape at once')

    @classmethod
    def poll(cls, context):
        from . import cut_presets
        return cut_presets.LAST_LOOPS[0] is not None

    def invoke(self, context, event):
        from . import cut_presets
        if not self.name:
            self.name = f'My Shape {len(cut_presets.list_presets()) + 1}'
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        from . import cut_presets
        loops = cut_presets.LAST_LOOPS[0]
        if not loops:
            self.report({'WARNING'}, 'Draw an outline first (Cut / Split / a lasso)')
            return {'CANCELLED'}
        try:
            name = self.name or f'My Shape {len(cut_presets.list_presets()) + 1}'
            stem = cut_presets.save_loops(name, loops)
        except (cg.CutError, OSError, ValueError) as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        if self.use:
            try:
                context.scene.mch_press.shape = stem
            except TypeError:
                pass
        self.report({'INFO'}, f'Saved shape "{name}"')
        return {'FINISHED'}


def draw(layout, context):
    """The tool's settings (Sidebar > Mecha Lab)."""
    from . import cut_presets
    st = context.scene.mch_press
    col = layout.column(align=True)
    col.row(align=True).prop(st, 'result', expand=True)
    col.template_icon_view(st, 'shape', show_labels=True, scale=4.0, scale_popup=3.0)   # (light: 64 px pictures)
    if st.drawn and DRAWN[0]:
        row = col.row(align=True)
        row.label(text='Using the shape you drew', icon='GREASEPENCIL')
        row.prop(st, 'drawn', text='', icon='X', emboss=False)
    else:
        col.label(text='Shift + draw: draw your own stamp', icon='GREASEPENCIL')
    brush = getattr(context.scene, 'mch_brush', None)
    if brush is not None:                    # (0.24.95 the shared shapes and the Sketch draw the stamp)
        row = col.row(align=True)
        row.prop(brush, 'shape', text='Draw With')
        row.prop(brush, 'sketch_first', text='Sketch', toggle=True)
    col.prop(st, 'size')
    col.prop(st, 'rotation')
    col = layout.column(align=True)
    col.label(text='Curve (a round stamp)')
    col.prop(st, 'curve_x', text='Left-Right', slider=True)
    col.prop(st, 'curve_y', text='Up-Down', slider=True)
    layout.row(align=True).prop(st, 'floor_mode', expand=True)
    layout.prop(st, 'dot_size', slider=True)
    col = layout.column(align=True)
    col.label(text='Hold = deeper')
    col.prop(st, 'start')
    col.prop(st, 'speed')
    col.prop(st, 'max_depth')
    row = layout.row(align=True)
    row.enabled = cut_presets.LAST_LOOPS[0] is not None
    row.operator('mch.save_cut_shape', text='Save Shape (the outline you drew last)', icon='FILE_TICK')
    layout.label(text='Press on a part and hold: deeper the longer you hold', icon='INFO')
    layout.label(text='Release: keep  |  Esc / RMB: back  |  [ ] / F size')
    layout.label(text='R + mouse: turn (Shift fine, Ctrl 5\u00b0)  |  Shift+R: 0\u00b0')


TOOL_KEYMAP = (
    ('mch.quick_hud_press', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'any': True}, None),
    ('mch.press_cut', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
    # (0.24.95 Shift + draw: the stamp drawn with the shared shapes - Lasso, Curve Lasso, Rectangle, Circle, Ellipse,
    #  Free Draw - or into a Sketch; Shift + Alt: subtract from the Sketch)
    ('mch.cut_stroke', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'shift': True}, {'properties': [('mode', 'PRESS')]}),
    ('mch.cut_stroke', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'shift': True, 'alt': True},
     {'properties': [('mode', 'PRESS')]}),
    ('mch.press_adjust', {'type': 'LEFT_BRACKET', 'value': 'PRESS'}, {'properties': [('size', 1 / 1.15)]}),
    ('mch.press_adjust', {'type': 'RIGHT_BRACKET', 'value': 'PRESS'}, {'properties': [('size', 1.15)]}),
    ('mch.stamp_turn', {'type': 'R', 'value': 'PRESS'}, None),           # (R + mouse: turn, fine)
    ('mch.stamp_turn', {'type': 'R', 'value': 'PRESS', 'shift': True}, {'properties': [('reset', True)]}),
) + lasso_sketch.KEYMAP + (          # (Sketch: Enter = the stamp, Backspace = the last outline, Esc = clear)
    ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None),
    ('mch.brush_resize', {'type': 'F', 'value': 'PRESS'}, None),        # (F + mouse = stamp size)
)

CLASSES = (MCH_PG_Press, MCH_OT_press_cut, MCH_OT_press_adjust, MCH_OT_stamp_turn, MCH_OT_press_draw,
           MCH_OT_save_cut_shape)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_press = bpy.props.PointerProperty(type=MCH_PG_Press)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_press'):
        del bpy.types.Scene.mch_press
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
