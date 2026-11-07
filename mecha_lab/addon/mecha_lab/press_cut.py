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

Hold LMB: grow a separate surface-following mesh outward (Alt + hold: press the stamp in - a cut).
Shift + drag: draw your own stamp outline (it is the stamp at once; Save Shape keeps it).
[ / ] or F + mouse: stamp size.  R + mouse left / right: turn it (0.4 degree a pixel, Shift fine, Ctrl 5 degree
steps; click keeps, Esc puts it back), Shift + R: back to 0 degrees.
"""
from __future__ import annotations

import math
import time

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty
from mathutils import Matrix, Vector

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
    tilt_x: FloatProperty(name='Tilt Left / Right', default=0.0, subtype='ANGLE',
                          min=-math.radians(65.0), max=math.radians(65.0), update=_redraw,
                          description='Slope the stamp floor left/right in screen-space, distinct from Curve')
    tilt_y: FloatProperty(name='Tilt Up / Down', default=0.0, subtype='ANGLE',
                          min=-math.radians(65.0), max=math.radians(65.0), update=_redraw,
                          description='Slope the stamp floor up/down in screen-space')
    stamp_edge: EnumProperty(name='Stamp Edge', items=[
        ('INHERIT', 'Cut Settings', 'Use the regular Cut Edge Finish settings'),
        ('NONE', 'Sharp', 'No bevel on new stamp cut edges'),
        ('CHAMFER', 'Chamfer', 'One flat bevel on the new stamp cut border'),
        ('BEVEL', 'Bevel', 'Round the new stamp cut border')], default='INHERIT')
    stamp_edge_width: FloatProperty(name='Edge Width', default=0.01, min=0.0,
                                   soft_max=0.5, precision=4, unit='LENGTH',
                                   description='Width of bevel/chamfer on new stamp cut edges, in world units')
    stamp_edge_segments: bpy.props.IntProperty(name='Bevel Segments', default=3, min=1, max=16,
                                                description='Number of segments for round bevel (chamfer uses one)')
    # 0.24.108 (user: "프레스컷에도 뺄 때 챔퍼랑 베벨 그리고 원형도 넣어 줄래?") Alt + hold (Grow): the top edge
    grow_edge: EnumProperty(name='Grow Edge', default='SHARP', update=_redraw, items=[
        ('SHARP', 'Sharp', 'The part that grows out keeps a sharp top rim'),
        ('CHAMFER', 'Chamfer', 'One flat cut along the top rim'),
        ('BEVEL', 'Bevel', 'A rounded top rim'),
        ('ROUND', 'Round', 'A dome: the whole top rises round from the rim to the middle')],
        description='Hold (Grow): the top edge of the part that grows out')
    grow_edge_size: FloatProperty(name='Edge Size', default=0.35, min=0.02, max=0.9, subtype='FACTOR', precision=2,
                                  update=_redraw,
                                  description='Chamfer / Bevel size, of the grown height (it grows with it; never '
                                              'more than about half the stamp\'s width)')
    grow_edge_segments: bpy.props.IntProperty(name='Bevel Segments', default=4, min=2, max=16, update=_redraw,
                                               description='How round the Bevel is (segments across the rounded rim)')
    # 0.24.108 (user: "튀어 나올 때 바깥면 안 찌그러져?") the outer face copied every bump of the surface under it
    grow_top: EnumProperty(name='Grow Top', default='FLAT', update=_redraw, items=[
        ('FLAT', 'Flat', 'The outer face is flat (facing the view), resting on the highest point of the surface under '
                         'the stamp - bumps in the surface never show on it; the walls reach down to the surface'),
        ('FOLLOW', 'Follow', 'The outer face follows the surface under the stamp (its bumps and curve included)')],
        description='Hold (Grow): the shape of the outer face')
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


GROW_TAP = 0.25            # 0.24.108 a tap with Grow: the mesh comes out this much of the stamp's width at once


def press_depth(press, st, seconds):
    """The depth / height for this press after ``seconds``: Grow has its own (a tap is already visible)."""
    fn = getattr(press, 'depth_for', None)
    return fn(st, seconds) if fn is not None else depth_at(st, press.size, seconds)


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
                 angle=0.0, depth=0.1, level=False, tilt=(0.0, 0.0)):
        self.targets = [t for t in targets if t is not None]
        self.projector = projector
        self.vd = projector.view_dir
        self.spacing = max(2.0, float(spacing))
        self.follow = bool(follow) and not level
        self.level = bool(level)
        self.curve = (float(curve[0]), float(curve[1]))
        self.tilt = (float(tilt[0]), float(tilt[1]))
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
        self.loops_px = [[tuple(p) for p in lp] for lp in loops]
        self.folds = None
        self.under = self._under(self.loops_px)
        t_v = self._nearest_vertex(self.under, self.loops_px)
        if t_v is not None:                          # (0.24.95 user: "레벨로 해도 잔메쉬가 남아" - a corner's tip between
            self.t_min = t_v if self.t_min is None else min(self.t_min, t_v)   # the samples stayed in front of the
        #                                                                       near cap: the part's points count too)
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

    def _under(self, loops, margin=2.0):
        """The parts' triangles round the stamp (world space, evaluated): [(points, region px, triangles, normals)];
        None if the view cannot be mapped."""
        import numpy as np
        pts = [p for lp in loops for p in lp]
        x0, x1 = min(p[0] for p in pts) - margin, max(p[0] for p in pts) + margin
        y0, y1 = min(p[1] for p in pts) - margin, max(p[1] for p in pts) + margin
        try:
            dg = bpy.context.evaluated_depsgraph_get()
        except (AttributeError, RuntimeError):
            dg = None
        out = []
        for ob in self.targets:
            try:
                ev = ob.evaluated_get(dg) if dg is not None else ob
                me = ev.to_mesh()
            except (RuntimeError, ReferenceError, AttributeError):
                continue
            try:
                co = np.empty(len(me.vertices) * 3)
                me.vertices.foreach_get('co', co)
                me.calc_loop_triangles()
                tv = np.empty(len(me.loop_triangles) * 3, np.int32)
                me.loop_triangles.foreach_get('vertices', tv)
            finally:
                ev.to_mesh_clear()
            mw = np.array(ob.matrix_world)
            co = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
            tv = tv.reshape(-1, 3)
            xy = _screen_np(self.projector, co)
            if xy is None:
                return None
            if not len(tv):
                continue
            txy = xy[tv]
            keep = ((txy[:, :, 0].max(1) >= x0) & (txy[:, :, 0].min(1) <= x1) & (txy[:, :, 1].max(1) >= y0)
                    & (txy[:, :, 1].min(1) <= y1))
            tv = tv[keep]
            nrm = np.cross(co[tv[:, 1]] - co[tv[:, 0]], co[tv[:, 2]] - co[tv[:, 0]])
            ln = np.linalg.norm(nrm, axis=1)
            ok = ln > 1e-12
            out.append((co, xy, tv[ok], nrm[ok] / ln[ok, None]))
        return out

    @staticmethod
    def _inside_np(q, loops):
        """Even-odd: which region px points ``q`` (N x 2) lie inside ``loops``."""
        import numpy as np
        A = np.array([lp[i] for lp in loops for i in range(len(lp))], float)
        B = np.array([lp[(i + 1) % len(lp)] for lp in loops for i in range(len(lp))], float)
        x, y = q[:, 0:1], q[:, 1:2]
        cross = (A[:, 1] > y) != (B[:, 1] > y)
        with np.errstate(divide='ignore', invalid='ignore'):
            xi = A[:, 0] + (y - A[:, 1]) * (B[:, 0] - A[:, 0]) / (B[:, 1] - A[:, 1])
        return (np.count_nonzero(cross & (x < xi), axis=1) % 2) == 1

    def _nearest_vertex(self, under, loops):
        """How far along the view the nearest point of the parts inside the stamp lies (None: none)."""
        import numpy as np
        if not under:
            return None
        vd = np.array(self.vd)
        best = None
        for co, xy, tv, _n in under:
            used = np.unique(tv)
            if not len(used):
                continue
            ins = used[self._inside_np(xy[used], loops)]
            if len(ins):
                t = float((co[ins] @ vd).min())
                best = t if best is None else min(best, t)
        return best

    def fold(self, loops, max_tris=1500, angle=1.0):
        """0.24.95 (user: "엣지 감지하는 기능 - 크리즈 감지되니까 그거 이용해서 꺾이는 판을 계산해서 바닥 메쉬를 딱 떨어지게
        하고 면 수도 줄이는 거") Follow over a part made of flat faces: the floor folds exactly where the part does - the
        part's own fold lines (edges between faces more than ``angle`` degrees apart, its silhouette and open sides)
        under the stamp, in region px, go into the far cap as lines (``core_geometry._curved_cap``), and where they
        cross the outline a point goes into the outline (the walls bend there too).  Between the lines the floor is
        flat: no grid - a crisp floor with few faces (a grid's points cut across a crease: a saw-toothed floor, the
        corner of a box uncut in places).  Returns the outline with the crossings, or None (a dense / sculpted
        surface, a bent stamp: the grid as before)."""
        import numpy as np
        if abs(self.curve[0]) > 1e-4 or abs(self.curve[1]) > 1e-4 or not self.under:
            return None
        if sum(len(u[2]) for u in self.under) > max_tris:
            return None
        vd = np.array(self.vd)
        cos_t = math.cos(math.radians(angle))
        segs = []
        for co, xy, tv, nrm in self.under:
            front = (nrm @ vd) < 0.0
            emap = {}
            for k, (a, b, c) in enumerate(tv):
                for e0, e1 in ((a, b), (b, c), (c, a)):
                    emap.setdefault((min(e0, e1), max(e0, e1)), []).append(k)
            for (a, b), ks in emap.items():
                f = [bool(front[k]) for k in ks]
                if not any(f):
                    continue
                if len(ks) == 2 and all(f) and float(nrm[ks[0]] @ nrm[ks[1]]) > cos_t:
                    continue                             # (flat across it: no fold)
                pa, pb = tuple(map(float, xy[a])), tuple(map(float, xy[b]))
                ln = math.dist(pa, pb)
                if ln > 1e-6:
                    # (each side of the line its own copy, a hair off it: a step seen from above - its wall edge-on,
                    #  the high and the low edge on one line - gets both depths, not one smeared across)
                    nx, ny = -(pb[1] - pa[1]) / ln * 0.6, (pb[0] - pa[0]) / ln * 0.6
                    segs.append(((pa[0] + nx, pa[1] + ny), (pb[0] + nx, pb[1] + ny)))
                    segs.append(((pa[0] - nx, pa[1] - ny), (pb[0] - nx, pb[1] - ny)))
        if not segs:
            return None
        return self._insert_folds(loops, segs)

    def _insert_folds(self, loops, segs, snap=0.75):
        """The fold lines clipped to the stamp (``self.folds``), and the outline with a point where each crosses it.
        0.24.108: a fold piece ends EXACTLY on an outline point (the corner it was snapped to, or the crossing point
        that goes into the outline) - a piece ending on an outline edge between two points made a T-junction: the
        far cap had a vertex there and the wall had not, and the cutter was "not watertight" on any creased part."""
        def cross(p, q, r, s):
            d = (q[0] - p[0]) * (s[1] - r[1]) - (q[1] - p[1]) * (s[0] - r[0])
            if abs(d) < 1e-12:
                return None
            t = ((r[0] - p[0]) * (s[1] - r[1]) - (r[1] - p[1]) * (s[0] - r[0])) / d
            u = ((r[0] - p[0]) * (q[1] - p[1]) - (r[1] - p[1]) * (q[0] - p[0])) / d
            return (t, u) if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9 else None

        def nearest_edge(x):
            best = (1e18, None, None, None)
            for li, lp in enumerate(loops):
                n = len(lp)
                for i in range(n):
                    p, q = lp[i], lp[(i + 1) % n]
                    dx, dy = q[0] - p[0], q[1] - p[1]
                    l2 = dx * dx + dy * dy or 1e-12
                    t = max(0.0, min(1.0, ((x[0] - p[0]) * dx + (x[1] - p[1]) * dy) / l2))
                    d = math.dist(x, (p[0] + t * dx, p[1] + t * dy))
                    if d < best[0]:
                        best = (d, li, i, t)
            return best

        adds = {}                                        # (loop, edge) -> [(t, point)]

        def on_outline(li, i, t):
            """The outline point a fold end lands on: the edge's corner within ``snap``, else a new point on it."""
            lp = loops[li]
            p, q = lp[i], lp[(i + 1) % len(lp)]
            x = (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
            if math.dist(x, p) <= snap:
                return tuple(p)
            if math.dist(x, q) <= snap:
                return tuple(q)
            for _t, y in adds.get((li, i), []):
                if math.dist(x, y) <= snap:              # (another fold already put a point here: share it)
                    return y
            adds.setdefault((li, i), []).append((t, x))
            return x
        inner = []
        for a, b in segs:
            cuts = [(0.0, tuple(a)), (1.0, tuple(b))]
            for li, lp in enumerate(loops):
                n = len(lp)
                for i in range(n):
                    hit = cross(lp[i], lp[(i + 1) % n], a, b)
                    if hit is None:
                        continue
                    t, u = hit
                    cuts.append((u, on_outline(li, i, t)))
            cuts.sort(key=lambda c: c[0])
            for (u0, x0), (u1, x1) in zip(cuts, cuts[1:]):
                if u1 - u0 < 1e-9 or math.dist(x0, x1) < 0.25:
                    continue
                m = ((x0[0] + x1[0]) / 2, (x0[1] + x1[1]) / 2)
                if cg.point_in_loops(m, loops):
                    inner.append([x0, x1])
        # a piece's own end (the crease's end) lying on the outline without crossing it: onto an outline point too
        for piece in inner:
            for k in (0, 1):
                d, li, i, t = nearest_edge(piece[k])
                if li is None or d >= 0.3:
                    continue
                lp = loops[li]
                if math.dist(piece[k], lp[i]) < 1e-9 or math.dist(piece[k], lp[(i + 1) % len(lp)]) < 1e-9:
                    continue
                if any(math.dist(piece[k], y) < 1e-9 for _t, y in adds.get((li, i), [])):
                    continue
                piece[k] = on_outline(li, i, t)
        inner = [(tuple(p0), tuple(p1)) for p0, p1 in inner if math.dist(p0, p1) >= 0.25]
        out = []
        for li, lp in enumerate(loops):
            new = []
            for i, p in enumerate(lp):
                new.append(tuple(p))
                last = tuple(p)
                for _t, x in sorted(adds.get((li, i), [])):
                    if math.dist(x, last) > 1e-6:
                        new.append(x)
                        last = x
            out.append(new)
        self.folds = inner
        return out

    def _planar(self):
        """The surface under the shape is one flat face and the stamp is not bent: the far cap is flat too (no grid,
        no extra points - a pocket in a flat face seen at an angle keeps clean big faces)."""
        if (abs(self.curve[0]) > 1e-4 or abs(self.curve[1]) > 1e-4 or
                abs(self.tilt[0]) > 1e-5 or abs(self.tilt[1]) > 1e-5):
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

    def tilt_off(self, xy):
        """Planar sloped stamp floor, in world units. Rotation follows the visible stamp."""
        if self.px_world <= 0.0 or (abs(self.tilt[0]) < 1e-6 and abs(self.tilt[1]) < 1e-6):
            return 0.0
        c, s = math.cos(self.angle), math.sin(self.angle)
        dx, dy = xy[0] - self.center[0], xy[1] - self.center[1]
        u, v = dx * c + dy * s, -dx * s + dy * c
        return self.px_world * (math.tan(self.tilt[0]) * (u - self.uc) +
                                math.tan(self.tilt[1]) * (v - self.vc))

    def offset(self, xy, far_co):
        """How far along the view the cutter's far cap at screen ``xy`` lies from the far plane through ``far_co``."""
        t_far = far_co.dot(self.vd)
        above = max(1e-4, self.depth * 0.05)
        if self.level and self.t_ref is not None:        # (Level: flat at the depth below the point pressed)
            base = self.t_ref + self.depth - t_far
            low = ((self.t_min if self.t_min is not None else self.t_ref) - 0.5 * above) - t_far
            return max(base + self.curve_off(xy) + self.tilt_off(xy), low)
        tx = self.t(xy) if self.follow else None
        if tx is None:                                   # (flat: the far plane is the depth below the middle)
            base, low = 0.0, -(self.depth + 0.5 * above)
        else:
            base, low = tx + self.depth - t_far, tx - 0.5 * above - t_far
        return max(base + self.curve_off(xy) + self.tilt_off(xy), low)

    def near_shift(self, near_co):
        if not (self.follow or self.level) or self.t_min is None:
            return 0.0
        margin = max(1e-4, self.depth * 0.05)
        return max(0.0, near_co.dot(self.vd) - (self.t_min - margin))


class Press:
    """One press on one part: the part as it was (kept), cut again From Surface at each new depth."""

    def __init__(self, context, target, loops, projector, result='CUT', center=None, angle=0.0, curve=(0.0, 0.0),
                 spacing=6.0, follow=False, level=False, tilt=(0.0, 0.0)):
        from . import ramp_edit
        old = ramp_edit.live_target(context, ramp_edit.ALL_KINDS)
        if old is not None:                      # (an earlier live cut stays as it is: the Cut Depth set while
            ramp_edit.finish(old)                #  pressing must not cut it again)
        self.target = target
        self.curve = (float(curve[0]), float(curve[1]))
        self.tilt = tuple(float(x) for x in tilt)
        self.curved = (abs(self.curve[0]) > 1e-4 or abs(self.curve[1]) > 1e-4 or
                       abs(self.tilt[0]) > 1e-5 or abs(self.tilt[1]) > 1e-5)
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
                                       curve=self.curve, center=self.center, angle=self.angle, level=self.level, tilt=self.tilt)
            if not self.sfloor.planar:           # (a bent stamp / a curved surface: the outline follows it too)
                folded = self.sfloor.fold(lps)   # (0.24.95 a part of flat faces: folded along its own creases)
                self.loops = folded if folded is not None else [resample(lp, self.spacing) for lp in lps]
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
        # Only the new press-created rim is chamfered/bevelled by the existing guarded Cut engine.
        # Restore global Cut settings after each depth tick; other tools must never inherit this preset.
        edge_before = (cut.edge_finish, cut.finish_width, cut.finish_segments, cut.gn_finish)
        st = context.scene.mch_press
        if st.stamp_edge != 'INHERIT':
            cut.gn_finish = 'NONE'
            cut.edge_finish = st.stamp_edge
            cut.finish_width = st.stamp_edge_width
            cut.finish_segments = 1 if st.stamp_edge == 'CHAMFER' else st.stamp_edge_segments
        cg.FLOOR[0] = self.floor(depth)
        try:
            self.message = ce.perform_closed(context, self.result, [self.target], self.loops, self.projector)
        except (cg.CutError, RuntimeError) as ex:
            self.message = str(ex)
            cg.FLOOR[0] = None
            cut_presets.QUIET[0] = False
            self._restore()
            if st.stamp_edge != 'INHERIT':
                cut.edge_finish, cut.finish_width, cut.finish_segments, cut.gn_finish = edge_before
            if self.sfloor is not None and getattr(self.sfloor, 'folds', None) and 'watertight' in str(ex):
                self.sfloor.folds = None             # 0.24.108 the folded floor did not close: the grid floor instead
                return self.cut_to(context, depth)
            if prev > 0.0 and depth != prev:
                self.cut_to(context, prev)
            return False
        finally:
            cut_presets.QUIET[0] = False
            cg.FLOOR[0] = None
            if st.stamp_edge != 'INHERIT':
                cut.edge_finish, cut.finish_width, cut.finish_segments, cut.gn_finish = edge_before
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


def dome_height(t):
    """0.24.108 Round: the dome's height (0..1) at ``t`` = distance from the rim / the largest such distance - a
    quarter circle: steep at the rim, flat on top."""
    t = min(max(float(t), 0.0), 1.0)
    return math.sqrt(max(0.0, 1.0 - (1.0 - t) ** 2))


def _rim_distance(qs, rings):
    """(t per point = distance to the nearest outline segment / the largest of them, that largest distance in px)."""
    import numpy as np
    if not qs:
        return [], 0.0
    P = np.asarray(qs, np.float64)
    best = np.full(len(P), np.inf)
    for ring in rings:
        A = np.asarray(ring, np.float64)
        if len(A) < 2:
            continue
        B = np.roll(A, -1, axis=0)
        AB = B - A
        L2 = np.maximum((AB ** 2).sum(1), 1e-12)
        for s0 in range(0, len(A), 256):                 # (chunks: points x segments stays small)
            a, ab, l2 = A[s0:s0 + 256], AB[s0:s0 + 256], L2[s0:s0 + 256]
            AP = P[:, None, :] - a[None, :, :]
            tt = np.clip((AP * ab[None]).sum(2) / l2[None], 0.0, 1.0)
            d = np.sqrt(((AP - tt[..., None] * ab[None]) ** 2).sum(2)).min(1)
            best = np.minimum(best, d)
    r = float(best.max()) if len(best) else 0.0
    if not math.isfinite(r) or r <= 1e-9:
        return [0.0] * len(qs), 0.0
    return list(best / r), r


class GrowPress:
    """Alt press: a separate closed stamp, embedded in the untouched source surface.

    Sample the source once. Only vertex positions change on timer ticks, so height
    depends on elapsed time rather than repeated Boolean operations or frame rate.
    Growth is opposite the view direction; the base follows the surface, sunk just into it (0.24.107).
    """
    def __init__(self, context, target, loops, projector, result='GROW', center=None,
                 angle=0.0, curve=(0.0, 0.0), spacing=6.0, edge=None, edge_size=None, edge_segments=None, **_unused):
        self.target = target
        self.result = 'GROW'
        self.free = target is None               # 0.24.108 nothing under the stamp: a mesh on the cursor's plane
        st = getattr(context.scene, 'mch_press', None)
        self.edge = edge or getattr(st, 'grow_edge', 'SHARP')
        self.edge_size = float(edge_size if edge_size is not None else getattr(st, 'grow_edge_size', 0.35))
        self.edge_segments = int(edge_segments if edge_segments is not None else getattr(st, 'grow_edge_segments', 4))
        self.qs, self.dome_t, self.rim_rings, self.rim_curve, self.faces_final = [], [], [], [], []
        self.rim_d, self.ring_counts = [], []      # per point: world distance to the outline; per group: ring points
        self.top = getattr(st, 'grow_top', 'FLAT')
        self.rise = []               # per point: how far along the view the surface lies behind the reference plane
        self.inradius = 0.0          # world: the smallest stamp group's inner radius (the bevel never goes past it)
        self.depth = 0.0
        self.message = ''
        self.object = None
        self.projector = projector
        self.loops = [resample(lp, spacing) for lp in loops]
        if self.free:
            self.surface = None
            self.plane = Vector(context.scene.cursor.location)
            self.px_world = self._free_px_world(center or self.loops[0][0])
        else:
            self.surface = SurfaceFloor(context, [target], projector, self.loops, spacing,
                                        follow=True, curve=curve, center=center, angle=angle)
            self.px_world = self.surface.px_world
        pts = [q for lp in self.loops for q in lp]
        span_px = max(max(q[0] for q in pts) - min(q[0] for q in pts), max(q[1] for q in pts) - min(q[1] for q in pts))
        self.span = max(span_px * self.px_world, 1e-6)          # the stamp's longer side in world units
        self.size = part_size(target) if not self.free else self.span
        self.embed = max(self.size * 0.01, 1e-6)
        self.points, self.curves, self.faces = [], [], []

    def depth_for(self, st, seconds):
        """0.24.108 Grow: a tap already brings the stamp out GROW_TAP of its width; holding adds Speed x seconds x
        the part's size, up to Max (Start is the cut's gentle first depth - too little to see on a grown part)."""
        return min(self.size * st.max_depth, GROW_TAP * self.span + st.speed * max(0.0, seconds) * self.size)

    def _free_px_world(self, xy):
        """World size of one screen pixel on the cursor's plane facing the view."""
        vd = self.projector.view_dir
        try:
            o0, d0 = self.projector.ray(xy)
            o1, d1 = self.projector.ray((xy[0] + 1.0, xy[1]))
            p0, _t = cg._plane_hit(o0, d0, self.plane, vd)
            p1, _t = cg._plane_hit(o1, d1, self.plane, vd)
            return max((p1 - p0).length, 1e-9)
        except cg.CutError:
            return 0.01

    def _build(self, context):
        import bmesh
        from mathutils import Vector
        sf, vd = self.surface, self.projector.view_dir
        if sf is not None and not sf.known:
            raise cg.CutError('No surface beneath the stamp')
        for outer, holes in cg.prepare_loops(self.loops):
            rings = [outer] + list(holes)
            flat = [q for ring in rings for q in ring]
            if sf is None:                               # 0.24.108 free: the cursor's plane, a flat cap
                from mathutils.geometry import tessellate_polygon
                points, rises = [], []
                curves = [0.0] * len(flat)
                for q in flat:
                    o, d = self.projector.ray(q)
                    hit, _ = cg._plane_hit(o, d, self.plane, vd)
                    points.append(hit)
                    rises.append(0.0)
                where = [('wall', i) for i in range(len(flat))]
                tris = tessellate_polygon([[(x, y, 0.0) for x, y in ring] for ring in rings])
                if not tris:
                    raise cg.CutError('The stamp could not be triangulated')
                extra_curves, extra_qs = [], []
            else:
                plane = vd * sf.t_ref
                points, rises = [], []
                curves = [sf.curve_off(q) for q in flat]
                for q in flat:
                    o, d = self.projector.ray(q)
                    hit, _ = cg._plane_hit(o, d, plane, vd)
                    rise = sf.t(q) - sf.t_ref
                    points.append(hit + vd * rise)
                    rises.append(rise)
                extra_curves, extra_qs = [], []

                def offset(q):
                    extra_curves.append(sf.curve_off(q))
                    extra_qs.append((float(q[0]), float(q[1])))
                    r_ = sf.t(q) - sf.t_ref
                    rises.append(r_)
                    return r_

                where, tris = cg._curved_cap(rings, self.projector, plane, vd, offset, sf.spacing)
            indices = []
            extra = iter(extra_curves)
            extra_q = iter(extra_qs)
            qs = [(float(q[0]), float(q[1])) for q in flat]
            for kind, val in where:
                if kind == 'wall':
                    indices.append(val)
                else:
                    indices.append(len(points))
                    points.append(val)
                    curves.append(next(extra))
                    qs.append(next(extra_q, qs[-1]))
            n, base = len(points), len(self.points) * 2
            t, r_px = _rim_distance(qs, rings)
            self.dome_t.extend(t)
            self.rim_d.extend(ti * r_px * self.px_world for ti in t)
            self.ring_counts.append(len(flat))
            self.qs.extend(qs)
            if r_px > 0.0 and self.px_world > 0.0:
                w = r_px * self.px_world
                self.inradius = w if self.inradius <= 0.0 else min(self.inradius, w)
            k = 0
            for ring in rings:
                self.rim_rings.append([base + n + k + i for i in range(len(ring))])
                self.rim_curve.extend(curves[k:k + len(ring)])
                k += len(ring)
            # Store paired caps in the final vertex buffer: bottom, then top.
            self.faces.extend(tuple(base + indices[i] for i in reversed(t)) for t in tris)
            self.faces.extend(tuple(base + n + indices[i] for i in t) for t in tris)
            k = 0
            for ring in rings:
                for i in range(len(ring)):
                    a, b = base + k + i, base + k + (i + 1) % len(ring)
                    self.faces.append((a, b, b + n, a + n))
                k += len(ring)
            self.points.extend(points)
            self.curves.extend(curves)
            self.rise.extend(rises[:len(points)] + [0.0] * max(0, len(points) - len(rises)))
            if not hasattr(self, 'groups'):
                self.groups = []
            self.groups.append(n)
        # One flat base behind every sampled point, rather than a thin skin
        # following the source. Keep it fixed while only the exposed cap grows.
        self.base_t = max(p.dot(vd) for p in self.points) + self.embed
        me = bpy.data.meshes.new('MCH_PressGrow')
        try:
            me.from_pydata(self._coordinates(max(self.size * 0.0005, 1e-6)), [], self.faces)
            me.update()
            bm = bmesh.new()
            try:
                bm.from_mesh(me)
                if not bm.faces or any(not e.is_manifold for e in bm.edges):
                    raise cg.CutError('Grow stamp is not watertight; try a cleaner outline')
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
                bm.to_mesh(me)
            finally:
                bm.free()
            self.faces_final = [tuple(p.vertices) for p in me.polygons]
            if self.edge == 'ROUND':
                me.shade_smooth()
            if self.target is not None:
                for mat in self.target.data.materials:
                    me.materials.append(mat)
            self.object = bpy.data.objects.new('MCH_PressGrow', me)
            collection = next(iter(self.target.users_collection), context.collection) if self.target is not None \
                else context.collection
            collection.objects.link(self.object)
        except Exception:
            if self.object is not None:
                bpy.data.objects.remove(self.object, do_unlink=True)
                self.object = None
            if me.users == 0:
                bpy.data.meshes.remove(me)
            raise

    def _coordinates(self, depth):
        vd = self.projector.view_dir
        coords, start = [], 0
        for n in self.groups:
            pts = self.points[start:start + n]
            curves = self.curves[start:start + n]
            # 0.24.107 the bottom follows the surface, sunk ``embed`` into it (one flat base at the deepest sampled
            # point came out of the back of a thin or slanted part)
            coords.extend(tuple(p + vd * self.embed) for p in pts)
            if self.top == 'FLAT' and len(self.rise) >= start + n:
                # 0.24.108 Flat: the outer face on one plane facing the view, resting on the nearest (highest) point
                # of the surface under the stamp - a bumpy surface no longer shows on it
                rs = self.rise[start:start + n]
                r_min = min(rs)
                lift = [r - r_min for r in rs]
            else:
                lift = [0.0] * n
            if self.edge == 'ROUND' and len(self.dome_t) >= start + n:
                ts_ = self.dome_t[start:start + n]       # 0.24.108 Round: a dome, 0 at the rim, full at the middle
                coords.extend(tuple(p - vd * max(depth * dome_height(t) + c + lf, 1e-7))
                              for p, c, t, lf in zip(pts, curves, ts_, lift))
            else:
                coords.extend(tuple(p - vd * max(depth + c + lf, 1e-7)) for p, c, lf in zip(pts, curves, lift))
            start += n
        return coords

    def cut_to(self, context, depth):
        try:
            if self.object is None:
                self._build(context)
            coords = self._coordinates(depth)
            if self.edge in {'CHAMFER', 'BEVEL'}:
                self._write_beveled(coords, depth)
            else:
                self.object.data.vertices.foreach_set('co', [v for p in coords for v in p])
                self.object.data.update()
            self.depth = depth
            self.message = ('Separate mesh on the 3D cursor plane (nothing under the stamp)' if self.free else
                            'Separate mesh, its base sunk just into the surface') + (
                '' if self.edge == 'SHARP' else f' | top edge: {self.edge.title()}')
            return True
        except (cg.CutError, RuntimeError, ValueError) as ex:
            self.message = str(ex)
            return False

    def bevel_offset(self, depth):
        """0.24.108 Chamfer / Bevel width (world): Edge Size x the rim's height, at most ~half the stamp's width."""
        rim_h = min((depth + c for c in self.rim_curve), default=depth)
        off = self.edge_size * max(rim_h, 0.0)
        if self.inradius > 0.0:
            off = min(off, 0.45 * self.inradius)
        return off

    def _write_beveled(self, coords, depth):
        """The grown solid rebuilt with its top rim(s) chamfered / bevelled (the rim changes with the height, so the
        bevel is made again each step - a few hundred points, quick)."""
        import bmesh
        me = self.object.data
        off = self.bevel_offset(depth)
        bm = bmesh.new()
        try:
            vs = [bm.verts.new(c) for c in coords]
            for f in self.faces_final:
                try:
                    bm.faces.new([vs[i] for i in f])
                except ValueError:
                    pass
            if off > 1e-7:
                # (the top's inner points closer to the rim than the bevel would stop it short - Blender keeps a bevel
                #  from running over its neighbours: they go first, the top stays one face there)
                near, start, pstart = [], 0, 0
                for n, rc in zip(self.groups, self.ring_counts):
                    for j in range(rc, n):
                        if pstart + j < len(self.rim_d) and self.rim_d[pstart + j] < off * 1.6:
                            near.append(vs[start + n + j])
                    start += 2 * n
                    pstart += n
                if near:
                    bmesh.ops.dissolve_verts(bm, verts=near, use_face_split=False, use_boundary_tear=False)
                edges = []
                for ring in self.rim_rings:
                    for i in range(len(ring)):
                        e = bm.edges.get((vs[ring[i]], vs[ring[(i + 1) % len(ring)]]))
                        if e is not None:
                            edges.append(e)
                if edges:
                    segs = 1 if self.edge == 'CHAMFER' else max(2, self.edge_segments)
                    res = bmesh.ops.bevel(bm, geom=edges, offset=off, offset_type='OFFSET', segments=segs,
                                          profile=0.5, affect='EDGES', clamp_overlap=True)
                    if self.edge == 'BEVEL':
                        for f in res.get('faces', []):
                            f.smooth = True
            bm.normal_update()
            bm.to_mesh(me)
        finally:
            bm.free()
        me.update()

    def pocket(self):
        return [], [], 0.0

    def finish(self, context):
        """0.24.107 the selection stays as it was (selecting the grown mesh made the next Press with Target
        Active / Selected cut the grown mesh instead of the part)."""
        if self.object is not None:
            try:
                self.object.select_set(False)
            except RuntimeError:
                pass

    def cancel(self, context):
        if self.object is not None:
            me = self.object.data
            bpy.data.objects.remove(self.object, do_unlink=True)
            if me.users == 0:
                bpy.data.meshes.remove(me)
            self.object = None


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
    twice the first ones, times the Dot Size setting and Blender's UI scale.  0.24.107: back to those sizes
    (v0.24.106 had clamped them to 3 / 7 px, and Dot Size stopped doing anything above ~1.7)."""
    try:
        k = float(context.scene.mch_press.dot_size)
    except (AttributeError, TypeError, ValueError):
        k = 1.0
    try:
        ui = float(context.preferences.system.ui_scale)
    except (AttributeError, TypeError, ValueError):
        ui = 1.0
    k *= ui if ui > 0.0 else 1.0                  # (no window: Blender reads 0 - the plain size then)
    if not math.isfinite(k) or k <= 0.0:
        k = 1.0
    k = min(k, 12.0)                               # (a broken preference must not draw screen-sized discs)
    return 8.0 * k, 18.0 * k, 11.0 * k


def _dot_triangles(points, diameter):
    """Pixel-space discs; do not rely on backend-specific point sprite sizing."""
    radius = max(0.5, min(float(diameter), 200.0) * 0.5)
    segments = 20
    circle = [(math.cos(i * math.tau / segments) * radius,
               math.sin(i * math.tau / segments) * radius) for i in range(segments)]
    vertices = []
    for point in points:
        x, y = float(point[0]), float(point[1])
        for i in range(segments):
            a, b = circle[i], circle[(i + 1) % segments]
            vertices.extend(((x, y), (x + a[0], y + a[1]), (x + b[0], y + b[1])))
    return vertices


def draw_contact(context, loops_px, center_px, offset=(0.0, 0.0)):
    """Contact markers drawn as fixed pixel-size discs, including on Blender 5.3."""
    import gpu
    from gpu_extras.batch import batch_for_shader
    old_blend = gpu.state.blend_get()
    try:
        small, ring, core = dot_sizes(context)
        dots, contact = contact_points(context, loops_px, center_px, offset, step=max(8.0, small * 1.6))
        if not dots and contact is None:
            return
        sh = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        sh.bind()

        def discs(points, diameter, color):
            sh.uniform_float('color', color)
            batch_for_shader(sh, 'TRIS', {'pos': _dot_triangles(points, diameter)}).draw(sh)

        if dots:
            discs(dots, small + 2.0, (0.05, 0.12, 0.08, 0.85))
            discs(dots, small, (0.45, 1.0, 0.65, 1.0))
        if contact is not None:
            discs([contact], ring + 2.0, (0.05, 0.12, 0.08, 0.85))
            discs([contact], ring, (1.0, 1.0, 1.0, 1.0))
            discs([contact], core, (0.15, 0.85, 0.45, 1.0))
    except Exception:
        pass
    finally:
        gpu.state.blend_set(old_blend)


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
        try:                                   # 0.24.109 the ends a new stroke can go on from
            rv3d = getattr(context, 'region_data', None)
            if reg is not None and rv3d is not None:
                marks = continue_ends(context, ce.make_projector(reg, rv3d))
                if marks:
                    _draw_end_marks(context, sh, marks, 0.5 * continue_radius(st))
        except Exception:
            pass
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


def depth_gauge(loops, depth, max_depth, ui=1.0):
    """0.24.95 (user: a red line drawn down the stamp's right side - "여기 부분에도 선으로 저렇게 표시해 줄 수 있어?") The
    depth gauge beside the stamp while pressing (region px): a track as tall as the stamp (top = the surface, bottom =
    Max), filled red from the top down to the depth pressed, a tick there.  -> dict(x, top, bottom, level, frac)."""
    pts = [p for lp in loops for p in lp]
    x = max(p[0] for p in pts) + 16.0 * ui
    top, bottom = max(p[1] for p in pts), min(p[1] for p in pts)
    if top - bottom < 60.0 * ui:                       # (a small stamp: the gauge still readable)
        mid = (top + bottom) / 2.0
        top, bottom = mid + 30.0 * ui, mid - 30.0 * ui
    frac = max(0.0, min(1.0, depth / max_depth)) if max_depth > 0.0 else 0.0
    return dict(x=x, top=top, bottom=bottom, level=top - frac * (top - bottom), frac=frac)


def _rect(sh, x0, y0, x1, y1, color):
    import gpu
    from gpu_extras.batch import batch_for_shader
    sh.bind()
    sh.uniform_float('color', color)
    batch_for_shader(sh, 'TRIS', {'pos': [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]},
                     indices=[(0, 1, 2), (0, 2, 3)]).draw(sh)


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
        ui = float(bpy.context.preferences.system.ui_scale) or 1.0
        g = depth_gauge(op.press.loops, op.press.depth, op.press.size * op.press_st.max_depth, ui)
        x, half = g['x'], 2.0 * ui
        _rect(sh, x - 1.5 * ui, g['bottom'], x + 1.5 * ui, g['top'], (0.0, 0.0, 0.0, 0.45))     # (the track)
        _rect(sh, x - half - 1.0, g['level'] - 1.0, x + half + 1.0, g['top'] + 1.0, (0.0, 0.0, 0.0, 0.6))
        _rect(sh, x - half, g['level'], x + half, g['top'], (0.95, 0.12, 0.1, 0.95))               # (pressed so far)
        for yy, w in ((g['top'], 6.0), (g['bottom'], 6.0)):                                          # (surface / Max)
            _rect(sh, x - w * ui, yy - 1.0, x + w * ui, yy + 1.0, (1.0, 1.0, 1.0, 0.7))
        _rect(sh, x - 9.0 * ui, g['level'] - 1.5 * ui, x + 9.0 * ui, g['level'] + 1.5 * ui, (1.0, 0.2, 0.15, 1.0))
        gpu.state.blend_set('NONE')
        blf.size(0, 15)
        blf.color(0, 1.0, 0.92, 0.6, 1.0)
        blf.position(0, x + 14.0 * ui, g['level'] - 5.0 * ui, 0)
        unit = bpy.context.scene.unit_settings.scale_length or 1.0
        blf.draw(0, f'{op.press.result.title()} {op.press.depth * unit * 100:.1f} cm  (hold: grow/deepen, release: keep, '
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
        press_type = GrowPress if event.alt else Press
        self.press = press_type(context, target, loops, projector, st.result, center=xy, angle=st.rotation,
                           curve=(st.curve_x, st.curve_y), spacing=max(3.0, st.size / 10.0),
                           follow=st.floor_mode == 'FOLLOW', level=st.floor_mode == 'LEVEL',
                           tilt=(st.tilt_x, st.tilt_y))
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
            d = press_depth(self.press, st, time.perf_counter() - self.t0)
            if d >= self.press.size * st.max_depth - 1e-9:
                self.full = True
            if d - self.press.depth >= STEP_MIN * self.press.size or self.full:
                if not self.press.cut_to(context, d):
                    self.full = True              # (it does not go deeper cleanly: stays where it was)
                self._update_red()
                self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if et == 'LEFTMOUSE' and ev == 'RELEASE':
            # Include the interval since the last timer tick (also short taps).
            if self.press.result == 'GROW' and not self.full:
                self.press.cut_to(context, press_depth(self.press, self.press_st, time.perf_counter() - self.t0))
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


# 0.24.100 Unified Press / Line: one tool, four gestures.
# Do not merge the geometry engines: the gesture gateway uses the existing
# Press/GrowPress, Cut and Base Mesh implementations.
UNIFIED_DRAG_PX = 12.0
UNIFIED_HOLD_SEC = 0.25
# 0.24.107 a slow start of a drawn line became a Press (12 px in 0.18 s is fast): a press that has only just begun
# turns back into the line when the pointer then travels this far from where it went down.
UNIFIED_LATE_DRAG_PX = 18.0
UNIFIED_LATE_DRAG_SEC = 0.9


# --- 0.24.109 going on with a line after the view turned ---------------------------------------------------------------
# (user: "한번 긋고 내가 뷰포트 돌려서 처음 그었던 선 끝난 부분에 이어서 그릴 수 있게" / "뷰포트 방향으로 인식하면 굳이 3D 경로까지
#  안 가도") A stroke that starts on the end of the last line goes on from it IN THE FIRST STROKE'S PLANE: the new
# points are projected onto that plane, so the section stays the one the first stroke had.  'base': the live swept
# Base Mesh line the tool made last (its name); 'cut': the last Line Cut - its plane (16 floats), the path in that
# plane, its section and size (a continued cut has the same groove).
CONTINUE = {'base': None, 'cut': None}


def continue_radius(st):
    """How close (px) to a line's end a stroke must start to go on from it: most of the stamp's half-width."""
    return max(16.0, 0.75 * float(st.size))


def _cut_frame(data):
    m = Matrix.Identity(4)
    vals = data['frame']
    for r in range(4):
        for c in range(4):
            m[r][c] = float(vals[r * 4 + c])
    return m


def _flat_frame(m):
    return [float(m[r][c]) for r in range(4) for c in range(4)]


def _ends_screen(projector, ends):
    sc = _screen_np(projector, [list(e) for e in ends])
    return None if sc is None else [(float(q[0]), float(q[1])) for q in sc]


def continue_ends(context, projector):
    """The points a new stroke can go on from: [(screen xy, world, swept line object or None for a Line Cut, at_end)]
    - the two ends of the live swept line (the active one and the one made last) and of the last Line Cut."""
    from . import base_mesh
    out = []
    cands = []
    try:
        ob = base_mesh.active_live_base(context)
        if ob is not None and ob.get(base_mesh.SWEEP_KEY):
            cands.append(ob)
    except (AttributeError, ReferenceError):
        pass
    name = CONTINUE['base']
    ob2 = bpy.data.objects.get(name) if name else None
    if ob2 is None and name:
        CONTINUE['base'] = None
    if ob2 is not None and ob2 not in cands:
        cands.append(ob2)
    for ob in cands:
        ends = base_mesh.sweep_ends(ob)
        if ends is None:
            continue
        sc = _ends_screen(projector, ends)
        if sc is None:
            continue
        for k, (w, q) in enumerate(zip(ends, sc)):
            out.append((q, w, ob, k == 1))
    cut = CONTINUE['cut']
    if cut and len(cut.get('path', ())) >= 2:
        frame = _cut_frame(cut)
        path = cut['path']
        ends = [frame @ Vector(base_mesh._xyz(path[0])), frame @ Vector(base_mesh._xyz(path[-1]))]
        sc = _ends_screen(projector, ends)
        if sc is not None:
            for k, (w, q) in enumerate(zip(ends, sc)):
                out.append((q, w, None, k == 1))
    return out


def nearest_end(context, projector, xy, radius, kind):
    """The end (see ``continue_ends``) of ``kind`` ('base' / 'cut') within ``radius`` px of ``xy``, nearest first."""
    best = None
    for item in continue_ends(context, projector):
        if (item[2] is not None) != (kind == 'base'):
            continue
        d = math.dist(item[0], xy)
        if d <= radius and (best is None or d < best[0]):
            best = (d, item)
    return best[1] if best else None


def _draw_end_marks(context, sh, marks, size):
    """Rings at the ends a stroke can go on from (cyan = Base Mesh line, orange = Line Cut)."""
    from . import cut_engine as ce
    for q, _w, ob, _end in marks:
        col = (0.3, 0.85, 1.0, 0.9) if ob is not None else (1.0, 0.62, 0.25, 0.9)
        for r in (size, size * 0.3):
            ring = [(q[0] + r * math.cos(math.tau * i / 24), q[1] + r * math.sin(math.tau * i / 24)) for i in range(24)]
            ce._draw_lines(sh, ring, col, closed=True, width=1.5)


def _rotated(loops, angle):
    c, s_ = math.cos(angle), math.sin(angle)
    return [[(x * c - y * s_, x * s_ + y * c) for x, y in lp] for lp in loops]


def line_cut_section(context, st, depth, span, eps=0.0):
    """0.24.109 The Line Cut's section: the stamp (turned as set) pressed in ``depth`` (world) and dragged along -
    its lower outline with straight walls up past the surface (``base_mesh.envelope_section``).  ``span`` is the
    stamp's longer side in world units (the section's height); ``eps`` a hair more depth (a cut through a part ends
    exactly on its far face otherwise).  Returns (section loops, bottom z of the section)."""
    from . import base_mesh
    norm, _name = base_mesh._section_loops(context, 'ALPHA')
    turned = _rotated(norm, float(st.rotation))
    v_min = min(y for lp in turned for _x, y in lp)
    v_max = max(y for lp in turned for _x, y in lp)
    d = float(depth) + float(eps)
    top = max(v_max + 0.05, v_min + (d + 0.04 * span) / max(span, 1e-9))
    return [base_mesh.envelope_section(turned, top)], -d


def _draw_unified_path(op):
    """Only an OPEN stroke is shown. Never make a closed lasso preview."""
    try:
        from . import cut_engine as ce
        import gpu
        if bpy.context.region != op.region or len(op.pts) < 2:
            return
        sh = ce._shader()
        gpu.state.blend_set('ALPHA')
        color = (0.3, 0.85, 1.0, 1.0) if op.make_mesh else (1.0, 0.76, 0.24, 1.0)
        ce._draw_lines(sh, op.pts, color, closed=False, width=2.5)
        try:                                   # 0.24.108 the band as wide as the stamp: what the line will be
            from . import lasso_line
            outline = lasso_line.band(op.pts, max(2.0, 2.0 * float(bpy.context.scene.mch_press.size)), 'ROUND')
            if len(outline) >= 3:
                ce._draw_lines(sh, outline, (color[0], color[1], color[2], 0.55), closed=True, width=1.5)
        except Exception:
            pass
        end = getattr(op, 'cont_end', None)
        if end is not None:                    # 0.24.109 the stroke goes on from this end of the last line
            r = 0.5 * continue_radius(bpy.context.scene.mch_press)
            for rr in (r, r * 0.3):
                ring = [(end[0] + rr * math.cos(math.tau * i / 24), end[1] + rr * math.sin(math.tau * i / 24)) for i in range(24)]
                ce._draw_lines(sh, ring, color, closed=True, width=2.0)
        gpu.state.blend_set('NONE')
    except Exception:
        pass


class MCH_OT_press_unified(bpy.types.Operator):
    """Drag = Base Mesh Line; Alt+drag = Line Cut; hold = Grow (a mesh out of the surface); Alt+hold = Press Cut.
    (0.24.108 user: "그냥 그릴 때는 베이스 메쉬 라인, Alt 는 컷 라인, 그냥 꾹 누르면 메쉬가 나오고, Alt + 꾹은 잘려야")"""
    bl_idname = 'mch.press_unified'
    bl_label = 'Press / Line / Base Mesh'
    bl_description = ('Draw: Base Mesh Line | Alt+draw: Line Cut | Hold: Grow (a mesh out) | '
                      'Alt+hold: Press Cut | Shift+draw: custom stamp')
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        region = context.region
        if region is None or region.type != 'WINDOW':
            return {'PASS_THROUGH'}
        rv3d = getattr(context, 'region_data', None)
        if rv3d is None:
            return {'PASS_THROUGH'}
        from . import cut_engine as ce
        self.region = region
        self.projector = ce.make_projector(region, rv3d)
        self.anchor = (float(event.mouse_region_x), float(event.mouse_region_y))
        self.pts = [self.anchor]
        self.make_mesh = not bool(event.alt)   # 0.24.108 (user) plain = Base Mesh line / Grow, Alt = Line Cut / Press
        self.state = 'WAIT'
        self.cont_end = None
        self.down_time = time.perf_counter()
        self.handle = None
        self.handle_red = None
        self.timer = context.window_manager.event_timer_add(0.04, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _update_red(self):
        return MCH_OT_press_cut._update_red(self)

    def _end(self, context):
        # The original Press modal calls self._end() on release and Esc.
        return MCH_OT_press_cut._end(self, context)

    def _cleanup(self, context):
        TURNING[0] = False
        if getattr(self, 'timer', None) is not None:
            try:
                context.window_manager.event_timer_remove(self.timer)
            except (ValueError, RuntimeError, ReferenceError):
                pass
            self.timer = None
        for name in ('handle', 'handle_red'):
            h = getattr(self, name, None)
            if h is not None:
                try:
                    bpy.types.SpaceView3D.draw_handler_remove(h, 'WINDOW')
                except (ValueError, RuntimeError, ReferenceError):
                    pass
                setattr(self, name, None)
        try:
            self.region.tag_redraw()
        except ReferenceError:
            pass

    def _begin_draw(self, context, xy):
        self.state = 'DRAW'
        self.pts.append(xy)
        TURNING[0] = True
        try:                                   # 0.24.109 a stroke that starts on the end of the last line goes on from it
            hit = nearest_end(context, self.projector, self.anchor, continue_radius(context.scene.mch_press),
                              'base' if self.make_mesh else 'cut')
            self.cont_end = hit[0] if hit is not None else None
        except Exception:
            self.cont_end = None
        self.handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_unified_path, (self,), 'WINDOW', 'POST_PIXEL')
        # No timer needed when dragging. We only need MOUSEMOVE / RELEASE.
        if self.timer is not None:
            context.window_manager.event_timer_remove(self.timer)
            self.timer = None
        self.region.tag_redraw()

    def _begin_press(self, context):
        """Begin the EXISTING Press / Grow engine at the captured pointer position.

        No nested bpy.ops invocation or artificial mouse event is needed.
        """
        from . import cut_engine as ce
        st = context.scene.mch_press
        xy = self.anchor
        try:
            loops = stamp_loops(context, xy, st)
        except (cg.CutError, ValueError, OSError) as ex:
            self.report({'WARNING'}, str(ex))
            return False
        target = press_target(context, self.projector, xy, loops)
        if target is None and not self.make_mesh:
            self.report({'WARNING'}, 'Press on a part (the stamp is not over one)')
            return False
        # (0.24.108 user: "그냥 그로우 할 때 뷰포트에 클릭해도 그냥 나오게" - Grow with nothing under the stamp: the stamp
        #  comes out as a mesh on the 3D cursor's plane facing the view)
        try:
            from . import safety_save
            safety_save.checkpoint('Mecha Unified Press')
        except Exception:
            pass
        typ = GrowPress if self.make_mesh else Press
        try:
            self.press = typ(context, target, loops, self.projector, st.result,
                             center=xy, angle=st.rotation, curve=(st.curve_x, st.curve_y),
                             spacing=max(3.0, st.size / 10.0),
                             follow=st.floor_mode == 'FOLLOW', level=st.floor_mode == 'LEVEL',
                           tilt=(st.tilt_x, st.tilt_y))
            elapsed = max(0.0, time.perf_counter() - self.down_time)
            if not self.press.cut_to(context, press_depth(self.press, st, elapsed)):
                msg = self.press.message
                self.press.cancel(context)
                self.report({'WARNING'}, msg[:200] or 'Nothing was cut')
                return False
        except Exception as ex:
            if getattr(self, 'press', None) is not None:
                try:
                    self.press.cancel(context)
                except Exception:
                    pass
            self.report({'ERROR'}, f'Unified Press failed: {ex}')
            return False
        self.press_st = st
        self.t0 = self.down_time
        self.full = False
        self.red, self.red_batch, self.red_sh = ([], [], 0.0), None, None
        MCH_OT_press_cut._update_red(self)
        self.handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_holding, (self,), 'WINDOW', 'POST_PIXEL')
        self.handle_red = bpy.types.SpaceView3D.draw_handler_add(
            _draw_pocket, (self,), 'WINDOW', 'POST_VIEW')
        self.state = 'PRESS'
        self.region.tag_redraw()
        return True

    def _press_to_draw(self, context, xy):
        """0.24.107 The pointer moved on soon after a press began: it was a slowly started line.  The press is put
        back (the part as it was) and the line goes on from where the button went down."""
        press = getattr(self, 'press', None)
        if press is not None:
            try:
                press.cancel(context)
            except (ReferenceError, RuntimeError, AttributeError):
                pass
        self.press = None
        if getattr(self, 'timer', None) is not None:
            try:
                context.window_manager.event_timer_remove(self.timer)
            except (ValueError, RuntimeError, ReferenceError, TypeError):
                pass
        self.timer = None
        for name in ('handle', 'handle_red'):
            h = getattr(self, name, None)
            if h is not None:
                try:
                    bpy.types.SpaceView3D.draw_handler_remove(h, 'WINDOW')
                except (ValueError, RuntimeError, ReferenceError):
                    pass
            setattr(self, name, None)
        self.state = 'WAIT'
        self._begin_draw(context, xy)

    def _finish_draw(self, context, xy):
        from . import cut_engine as ce, lasso_line, base_mesh, safety_save
        if math.dist(xy, self.pts[-1]) >= 0.5:
            self.pts.append(xy)
        pts = [self.pts[0]]
        for p in self.pts[1:]:
            if math.dist(p, pts[-1]) >= 0.6:
                pts.append(p)
        self._cleanup(context)
        if len(pts) < 2 or math.dist(pts[0], pts[-1]) < 3.0 and len(pts) <= 2:
            self.report({'WARNING'}, 'Draw a longer line')
            return {'CANCELLED'}
        try:                                   # 0.24.107 the Line tool's own stroke smoothing / simplify
            brush = context.scene.mch_brush
            from . import tool_state as _ts
            sm = ce.smooth_open(pts, getattr(brush, 'stroke_smooth', 0))
            sm = cg.simplify_open(sm, getattr(brush, 'stroke_simplify', 0.0) / _ts.res_scale())
            if len(sm) >= 2:
                pts = sm
        except Exception:
            pass
        try:
            brush = context.scene.mch_brush
            # 0.24.108 (user: "내가 정한 브러시 스탬프랑 단면이 똑같아야지") the line is as wide as the stamp on screen
            # ([ ] / F), and the Base Mesh line's section IS the stamp: as wide and as tall as it shows
            pr = context.scene.mch_press
            stamp_px = max(2.0, 2.0 * float(pr.size))                 # (the stamp's longer side, px)
            ppu = lasso_line.pixels_per_unit(context, self.projector, pts[0])
            span = stamp_px / max(ppu, 1e-6)                          # ... in world units
            loops = lasso_line.line_loops(context, self.projector, pts, brush, width_px=stamp_px)
            if not loops:
                raise cg.CutError('Could not form a band from this line')
            # 0.24.109 a stroke that starts on the end of the last line goes on from it (in the first stroke's plane)
            hit = nearest_end(context, self.projector, pts[0], continue_radius(pr), 'base' if self.make_mesh else 'cut')
            if self.make_mesh:
                # Press Cut plain draw ALWAYS uses the active stamp as the line's cross-section (turned as the stamp
                # is).  The scene's Base Mesh options stay independent.
                if hit is not None:
                    ob, at_end = hit[2], hit[3]
                    try:
                        safety_save.checkpoint('Mecha Base Mesh Line continued')
                    except Exception:
                        pass
                    n, turned, leaves = base_mesh.extend_sweep(ob, self.projector, pts, at_end,
                                                               end_hit=ce.surface_point(context, self.projector, pts[-1]))
                    for o in context.selected_objects:
                        o.select_set(False)
                    ob.select_set(True)
                    context.view_layer.objects.active = ob
                    msg = f'Base Mesh Line continued: {ob.name} (+{n} points' + \
                          (f', in the view you drew in: {turned:.0f} deg from the first piece' if leaves and turned >= 5.0
                           else '') + ')'
                else:
                    st = base_mesh.scene_defaults(context)
                    attach = None
                    if getattr(st, 'line_attach', False):
                        path = ce.smooth_open(pts, 6) if getattr(st, 'attach_curve', '') == 'SMOOTH' and len(pts) > 2 else pts
                        attach = (path, ce.surface_point(context, self.projector, path[0]),
                                  ce.surface_point(context, self.projector, path[-1]))
                    try:
                        safety_save.checkpoint('Mecha Base Mesh Line from Press Shape')
                    except Exception:
                        pass
                    msg = base_mesh.perform_base(context, loops, self.projector,
                                                 cutter=False, attach=attach, path=pts,
                                                 sweep_style='ALPHA', section_width=span, section_height=span,
                                                 section_rest=True, section_rotation=float(pr.rotation))
                    # Keep the original Base Mesh post-create radial symmetry behaviour.
                    try:
                        from . import radial_sym
                        msg = (msg or '') + radial_sym.after_create(context, 'BASE')
                    except (AttributeError, ImportError, RuntimeError, ReferenceError):
                        pass
                ob = context.active_object
                CONTINUE['base'] = ob.name if ob is not None and ob.get(base_mesh.SWEEP_KEY) else None
            else:
                # 0.24.109 (user: "컷도 당연히 스탬프 단면으로 잘려야지" / "맥스 조절해서 얕게 만들어도 왜 다 뚫려") the Line Cut
                # is the stamp's section swept along the line, pressed in Max x the part's size (not the Cut tool's depth)
                cut = context.scene.mch_cut
                if cut.targets == 'AUTO':
                    targets = ce.auto_targets(context.view_layer, self.projector, loops)
                else:
                    targets = ce.gather_targets(context, self.projector, pts[0], 'CUT')
                prev = CONTINUE['cut'] if hit is not None else None
                if not targets and prev is not None:
                    targets = [o for o in (bpy.data.objects.get(n) for n in prev.get('targets', ())) if o is not None]
                if not targets:
                    raise cg.CutError('Line Cut: no mesh in the line / selection')
                mode = 'SPLIT' if getattr(pr, 'result', 'CUT') == 'SPLIT' else 'CUT'
                if prev is not None:
                    frame = _cut_frame(prev)
                    at_end = hit[3]
                    old = [base_mesh._xyz(q) for q in prev['path']]
                    width, height, bottom = float(prev['width']), float(prev['height']), float(prev['bottom'])
                    section = [[tuple(q) for q in lp] for lp in prev['section']]
                    if not at_end:
                        old.reverse()
                    # 0.24.110 the new piece lies in the CURRENT view's plane through the groove's end (it can leave the
                    # first plane); a view turned less than 20 deg keeps the first plane
                    new_local, turned, leaves = base_mesh.continue_plane_path(frame, self.projector, pts, old[-1])
                    corner = getattr(context.scene.mch_base, 'line_corner', 'SHARP')
                    tail, new_pts = base_mesh.join_path(old, new_local, fade=2.0 * width,
                                                        tail=width * (2.5 if corner == 'ROUND' else 1.0))
                    local_path = tail + new_pts            # (the old line's last bit again: the corner is filled)
                    full = old + new_pts
                    if not at_end:
                        full.reverse()
                else:
                    size = max(part_size(t) for t in targets)
                    depth = size * float(pr.max_depth)
                    section, bottom = line_cut_section(context, pr, depth, span, eps=0.003 * size)
                    width = height = span
                    _groups, frame, local_path = base_mesh.sweep_frame(context, loops, self.projector, pts)
                    full, turned, leaves = local_path, 0.0, False
                try:
                    safety_save.checkpoint('Mecha Line Cut')
                except Exception:
                    pass
                bsd = context.scene.mch_base
                msg = base_mesh.sweep_cut(context, frame, local_path, section, width, height, bottom, targets, mode,
                                          corner=getattr(bsd, 'line_corner', 'SHARP'),
                                          corner_radius=float(getattr(bsd, 'corner_radius', 1.0)))
                if prev is not None:
                    msg = 'Line Cut continued: ' + msg + \
                          (f' | in the view you drew in: {turned:.0f} deg from the first piece' if leaves and turned >= 5.0
                           else '')
                CONTINUE['cut'] = {'frame': _flat_frame(frame), 'path': [list(q) for q in full],
                                   'section': [[list(q) for q in lp] for lp in section], 'width': width,
                                   'height': height, 'bottom': bottom, 'targets': [t.name for t in targets]}
            self.report({'INFO'}, msg or ('Base Mesh Line' if self.make_mesh else 'Line Cut'))
            return {'FINISHED'}
        except cg.CutError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        except Exception as ex:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f'Unified draw failed: {ex}')
            return {'CANCELLED'}

    def modal(self, context, event):
        if self.state == 'PRESS':
            if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'} and \
                    time.perf_counter() - self.down_time < UNIFIED_LATE_DRAG_SEC:
                xy = (float(event.mouse_region_x), float(event.mouse_region_y))
                if math.dist(self.anchor, xy) >= UNIFIED_LATE_DRAG_PX:
                    self._press_to_draw(context, xy)
                    return {'RUNNING_MODAL'}
            # Preserve timer-based growth, release, Esc/RMB undo semantics verbatim.
            outcome = MCH_OT_press_cut.modal(self, context, event)
            if 'FINISHED' in outcome or 'CANCELLED' in outcome:
                self.state = 'DONE'
            return outcome
        et, ev = event.type, event.value
        if ev == 'PRESS' and et in {'ESC', 'RIGHTMOUSE'}:
            self._cleanup(context)
            return {'CANCELLED'}
        if et in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            xy = (float(event.mouse_region_x), float(event.mouse_region_y))
            if self.state == 'WAIT':
                if math.dist(self.anchor, xy) >= UNIFIED_DRAG_PX:
                    self._begin_draw(context, xy)
            elif self.state == 'DRAW' and math.dist(xy, self.pts[-1]) >= 2.0:
                self.pts.append(xy)
                self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if et == 'TIMER' and self.state == 'WAIT':
            if time.perf_counter() - self.down_time >= UNIFIED_HOLD_SEC:
                if not self._begin_press(context):
                    self._cleanup(context)
                    return {'CANCELLED'}
            return {'RUNNING_MODAL'}
        if et == 'LEFTMOUSE' and ev == 'RELEASE':
            xy = (float(event.mouse_region_x), float(event.mouse_region_y))
            # Some tablets coalesce all movement into the release event.
            if self.state == 'WAIT' and math.dist(xy, self.anchor) >= UNIFIED_DRAG_PX:
                self._begin_draw(context, xy)
            if self.state == 'DRAW':
                xy = (float(event.mouse_region_x), float(event.mouse_region_y))
                return self._finish_draw(context, xy)
            # Quick tap (< hold threshold): still make an ordinary shallow press.
            if not self._begin_press(context):
                self._cleanup(context)
                return {'CANCELLED'}
            outcome = MCH_OT_press_cut.modal(self, context, event)
            if 'FINISHED' in outcome or 'CANCELLED' in outcome:
                self.state = 'DONE'
            return outcome
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        if self.state == 'PRESS':
            try:
                self.press.cancel(context)
            except (ReferenceError, RuntimeError):
                pass
        self._cleanup(context)


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


def shape_name(st):
    """The display name of the stamp picked (built-in or imported)."""
    from . import cut_presets
    for item in cut_presets.preset_items(st, bpy.context):
        if item[0] == st.shape:
            return item[1]
    return st.shape


class MCH_OT_press_pick_shape(bpy.types.Operator):
    """Use this shape as the Press Cut stamp"""
    bl_idname = 'mch.press_pick_shape'
    bl_label = 'Press Cut Stamp'
    bl_options = {'INTERNAL'}

    stem: StringProperty()

    @classmethod
    def description(cls, context, properties):
        from . import cut_presets
        for item in cut_presets.preset_items(context.scene.mch_press, context):
            if item[0] == properties.stem:
                return item[1]
        return cls.__doc__

    def execute(self, context):
        try:
            context.scene.mch_press.shape = self.stem          # (the drawn stamp gives way: _shape_picked)
        except TypeError:
            self.report({'WARNING'}, 'Shape not available')
            return {'CANCELLED'}
        return {'FINISHED'}


class MCH_OT_press_shape_grid(bpy.types.Operator):
    """0.24.95 (user: "여기 썸네일 만들어 주기로 한 건 어디 갔어?") The stamps as a grid of pictures (the top bar's stamp
    button): the 13 shapes, the 50 mech form-blocking stamps and the imported ones"""
    bl_idname = 'mch.press_shape_grid'
    bl_label = 'Press Cut Stamps'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=760)

    def execute(self, context):
        return {'FINISHED'}

    def draw(self, context):
        from . import cut_presets
        st = context.scene.mch_press
        layout = self.layout
        layout.label(text='Stamp  (Shift + draw: your own)', icon='IMAGE_DATA')
        grid = layout.grid_flow(row_major=True, columns=10, even_columns=True, even_rows=True, align=False)
        for stem, name, _desc, icon, _i in cut_presets.preset_items(st, context):
            if stem == 'NONE':
                continue
            col = grid.column(align=True)
            if icon:
                col.template_icon(icon_value=icon, scale=2.6)
            op = col.operator('mch.press_pick_shape', text=name.split(' (')[0][:12],
                              depress=(stem == st.shape and not st.drawn))
            op.stem = stem


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
    # 0.24.104 Press Cut Alt+drag directly sweeps the current stamp. Base Mesh
    # tool's standalone section choices remain independent and unchanged.
    base = context.scene.mch_base
    section = layout.box()
    section.label(text='Draw: Base Mesh Line (the stamp as its section)', icon='CURVE_PATH')
    section.label(text='Uses the selected Press Cut shape automatically')
    section.prop(base, 'section_width')
    section.prop(base, 'height', text='Section Height')
    section.prop(base, 'section_rotation')
    section.prop(base, 'section_twist')
    section.prop(base, 'section_taper', slider=True)
    row = section.row(align=True)                 # 0.24.112 the bends: Sharp (mitre) / Round (+ radius)
    row.prop(base, 'line_corner', expand=True)
    if base.line_corner == 'ROUND':
        section.prop(base, 'corner_radius', slider=True)
    section.label(text='(the dot next to a made line toggles this; its sliders set thickness)', icon='BLANK1')
    col = layout.column(align=True)
    col.label(text='Curve (a round stamp)')
    col.prop(st, 'curve_x', text='Left-Right', slider=True)
    col.prop(st, 'curve_y', text='Up-Down', slider=True)
    slope = layout.column(align=True)
    slope.label(text='Stamp Floor Tilt (not Curve)')
    slope.prop(st, 'tilt_x', text='Left / Right', slider=True)
    slope.prop(st, 'tilt_y', text='Up / Down', slider=True)
    edge = layout.box()
    edge.label(text='Stamp Cut Edge (new rim only)', icon='MOD_BEVEL')
    edge.prop(st, 'stamp_edge', text='Finish')
    if st.stamp_edge in {'BEVEL', 'CHAMFER'}:
        edge.prop(st, 'stamp_edge_width', text='Width')
        if st.stamp_edge == 'BEVEL':
            edge.prop(st, 'stamp_edge_segments', text='Segments')
    grow = layout.box()                         # 0.24.108 Alt + hold (Grow): the top edge
    grow.label(text='Hold: Grow Edge', icon='MOD_BEVEL')
    grow.row(align=True).prop(st, 'grow_top', expand=True)
    grow.row(align=True).prop(st, 'grow_edge', expand=True)
    if st.grow_edge in {'CHAMFER', 'BEVEL'}:
        grow.prop(st, 'grow_edge_size', slider=True)
        if st.grow_edge == 'BEVEL':
            grow.prop(st, 'grow_edge_segments')
    layout.row(align=True).prop(st, 'floor_mode', expand=True)
    layout.prop(st, 'dot_size', slider=True)
    col = layout.column(align=True)
    col.label(text='Hold = Grow (a mesh out)  |  Alt + hold = Press Cut')
    col.prop(st, 'start')
    col.prop(st, 'speed')
    col.prop(st, 'max_depth')
    row = layout.row(align=True)
    row.enabled = cut_presets.LAST_LOOPS[0] is not None
    row.operator('mch.save_cut_shape', text='Save Shape (the outline you drew last)', icon='FILE_TICK')
    layout.label(text='Drag: Base Mesh Line  |  Alt + drag: Line Cut (the stamp as its section, Max deep)', icon='INFO')
    layout.label(text='Start on a line\'s end mark: it goes on from there (turn the view first if you like)', icon='BLANK1')
    if brush is not None:
        lc = layout.column(align=True)
        lc.prop(brush, 'line_width', text='Draw Line Width')
        lc.prop(brush, 'line_caps', text='Line Ends')
        lc.prop(brush, 'line_taper_on', text='Taper Line')
        if brush.line_taper_on:
            lc.prop(brush, 'line_taper', text='Taper Amount')
    layout.label(text='Press on a part and hold: deeper the longer you hold', icon='INFO')
    layout.label(text='Hold: grow a separate mesh from the surface  |  Alt + hold: press in', icon='INFO')
    layout.label(text='Release: keep  |  Esc / RMB: back  |  [ ] / F size')
    layout.label(text='R + mouse: turn (Shift fine, Ctrl 5\u00b0)  |  Shift+R: 0\u00b0')


TOOL_KEYMAP = (
    ('mch.quick_hud_press', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'any': True}, None),
    ('mch.press_unified', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
    ('mch.press_unified', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'alt': True}, None),
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

CLASSES = (MCH_PG_Press, MCH_OT_press_cut, MCH_OT_press_unified, MCH_OT_press_adjust, MCH_OT_stamp_turn,
           MCH_OT_press_draw, MCH_OT_save_cut_shape, MCH_OT_press_pick_shape, MCH_OT_press_shape_grid)


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
