"""0.24.108 Line mode: a stroke that crosses or closes on itself, and Area (user: "선끼리 닿으면 내부가 채워지는데 그게
아니라 그냥 그리는 대로 유지되고 전체 영역을 도형으로 뽑는 게 좋을 것 같아").

- the band of a stroke that meets itself is resolved exactly (the Sketch's constrained Delaunay union of simple
  pieces): a closed stroke is a RING (it came out as a filled disc, or "crosses itself"), a crossing stroke keeps
  the loop it encloses as a hole
- Area on: the whole region the line encloses is the shape (holes filled); an open stroke is unchanged either way
- the Sketch with Area: the region all the strokes enclose (4 lines -> a square), subtracted strokes still subtract
- wired: cut_engine line loops, the Press Line Cut, the top bar Area button, remembered per tool
"""
import math

from _harness import bmesh, bpy, check, cube, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import base_mesh as bm_, core_geometry as cg, cut_engine as ce, lasso_line as ll, lasso_memory
from mecha_lab import lasso_sketch as ls, press_cut as pc, top_bar

fresh()
mecha_lab.register()
C = bpy.context
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)


def area(lp):
    return abs(cg.signed_area(lp))


def circle_path(cx, cy, r, n=72, close=True):
    pts = [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    return pts + [pts[0]] if close else pts


def rho_path():
    """A stroke that crosses itself once: a tail, then a loop back over the tail."""
    pts = [(100 + i * 4.0, 300 + i * 2.0) for i in range(40)]      # the tail
    cx, cy = pts[-1][0] + 60, pts[-1][1] + 60
    pts += [(cx + 85 * math.cos(a), cy + 85 * math.sin(a)) for a in [math.radians(-135 + 300 * k / 60) for k in range(61)]]
    pts += [(pts[-1][0] - i * 3.0, pts[-1][1] - i * 4.5) for i in range(1, 30)]
    return pts


# --- the pure helpers ------------------------------------------------------------------------------------------------
small = [(0, 0), (10, 0), (12, 3), (8, 3), (10, 0.5), (20, 0.5), (20, 10), (0, 10)]
kept = ll.remove_loops(small, max_area=1.0)
gone = ll.remove_loops(small)
check('remove_loops: a big loop is kept when a max area is given, spliced away without one',
      len(kept) == len(small) and len(gone) < len(small), (len(kept), len(gone)))

W = 20.0
ring = circle_path(400, 400, 120)
b = ll.band(ring, W)
check('a closed stroke: the band outline keeps its crossing (it used to lose a whole side -> a filled disc)',
      ll.crosses(b) or area(b) < math.pi * 130 ** 2 * 0.5, (ll.crosses(b), round(area(b))))
loops = ll.band_union(ring, W)
outers = [lp for lp in loops if cg.signed_area(lp) > 0]
holes = [lp for lp in loops if cg.signed_area(lp) < 0]
check('band_union of a closed stroke: a ring - one outer, one hole, no crossings', len(outers) == 1 and len(holes) == 1
      and not cg.find_intersections(loops), (len(outers), len(holes)))
check('... the right size (outer ~ pi (R + w/2)^2, hole ~ pi (R - w/2)^2)',
      abs(area(outers[0]) - math.pi * 130 ** 2) < math.pi * 130 ** 2 * 0.03
      and abs(area(holes[0]) - math.pi * 110 ** 2) < math.pi * 110 ** 2 * 0.03,
      (round(area(outers[0])), round(math.pi * 130 ** 2), round(area(holes[0])), round(math.pi * 110 ** 2)))
filled = ll.band_union(ring, W, fill=True)
check('... Area: one disc, the whole region (pi (R + w/2)^2)', len(filled) == 1 and cg.signed_area(filled[0]) > 0
      and abs(area(filled[0]) - math.pi * 130 ** 2) < math.pi * 130 ** 2 * 0.03, round(area(filled[0])))

rho = rho_path()
b = ll.band(rho, W)
loops = ll.band_union(rho, W)
outers = [lp for lp in loops if cg.signed_area(lp) > 0]
holes = [lp for lp in loops if cg.signed_area(lp) < 0]
check('a stroke crossing itself (rho): band = one outer + the loop it encloses as a hole', len(outers) == 1 and len(holes) == 1
      and area(holes[0]) > 3000, (len(outers), len(holes), round(area(holes[0])) if holes else None))
filled = ll.band_union(rho, W, fill=True)
check('... Area: the hole filled, one loop as big as outer', len(filled) == 1 and abs(area(filled[0]) - area(outers[0])) < 1.0)
pcs = ll.band_pieces(rho, W)
check('... pieces: a quad per segment + a disc at each end (Round), none with Flat caps',
      len([q for q in pcs if len(q) != 4]) == 2 and len([q for q in ll.band_pieces(rho, W, 'FLAT') if len(q) != 4]) == 0)

open_path = [(100 + i * 6.0, 200 + 40 * math.sin(i / 5.0)) for i in range(60)]
b_open = ll.band(open_path, W)
check('an open stroke: no crossing, the band as it was', not ll.crosses(b_open) and len(b_open) > 20)
tap = ll.band_union(open_path, W, taper=0.6, fill=True)
check('taper / pressure through the union: a closed simple loop', len(tap) == 1 and not cg.find_intersections(tap)
      and non_manifold is not None)

# --- line_loops with the brush --------------------------------------------------------------------------------------
p = cube('P', size=2.0)
brush = C.scene.mch_brush
brush.line_mode, brush.line_width, brush.line_caps = True, 0.2, 'ROUND'
brush.line_area = False
sc_ring = [TOP.to_screen(Vector((0.6 * math.cos(a), 0.6 * math.sin(a), 1.0))) for a in
           [2 * math.pi * i / 72 for i in range(73)]]
sc_ring = [(q[0], q[1]) for q in sc_ring]
lp_band = ll.line_loops(C, TOP, sc_ring, brush)
brush.line_area = True
lp_area = ll.line_loops(C, TOP, sc_ring, brush)
brush.line_area = False
lp_open = ll.line_loops(C, TOP, [(q[0], q[1]) for q in [TOP.to_screen(Vector((x, 0.0, 1.0))) for x in (-0.8, -0.4, 0.0, 0.4, 0.8)]], brush)
check('line_loops: Area off -> a ring (2 loops), on -> one filled loop, an open line -> one band',
      len(lp_band) == 2 and len(lp_area) == 1 and len(lp_open) == 1, (len(lp_band), len(lp_area), len(lp_open)))
check('... the brush setting exists, off by default, remembered per tool',
      'line_area' in brush.bl_rna.properties and brush.bl_rna.properties['line_area'].default is False
      and 'line_area' in lasso_memory.PROPS)

# a real cut with each: the ring takes a ring's volume, Area the whole disc
C.scene.mch_settings.auto_apply = True
C.scene.mch_cut.depth_mode, C.scene.mch_cut.depth = 'SURFACE', 0.3
C.scene.mch_cut.depth_floor = 'FLAT'


def vol(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    v = bm.calc_volume()
    bm.free()
    return v


v0 = vol(p)
ce.perform_closed(C, 'CUT', [p], lp_band, TOP, False)
v_ring = v0 - vol(p)
fresh()
C = bpy.context
p = cube('P', size=2.0)
C.scene.mch_settings.auto_apply = True
C.scene.mch_cut.depth_mode, C.scene.mch_cut.depth = 'SURFACE', 0.3
C.scene.mch_cut.depth_floor = 'FLAT'
ce.perform_closed(C, 'CUT', [p], lp_area, TOP, False)
v_disc = v0 - vol(p)
exp_ring = math.pi * (0.7 ** 2 - 0.5 ** 2) * 0.3
exp_disc = math.pi * 0.7 ** 2 * 0.3
check('Cut, Line mode, a closed stroke: a ring groove (not the whole disc)', abs(v_ring - exp_ring) < exp_ring * 0.15
      and non_manifold(p) == 0, (round(v_ring, 3), round(exp_ring, 3)))
check('... Area: the whole disc pocket', abs(v_disc - exp_disc) < exp_disc * 0.1, (round(v_disc, 3), round(exp_disc, 3)))

# --- the Sketch: four lines enclose a square --------------------------------------------------------------------------
def bar(x0, y0, x1, y1, w=12.0):
    return [[(x0 - w, y0 - w), (x1 + w, y0 - w), (x1 + w, y1 + w), (x0 - w, y1 + w)], []]


items = [{'op': 'ADD', 'groups': [bar(0, 0, 200, 0)]}, {'op': 'ADD', 'groups': [bar(200, 0, 200, 200)]},
         {'op': 'ADD', 'groups': [bar(0, 200, 200, 200)]}, {'op': 'ADD', 'groups': [bar(0, 0, 0, 200)]}]
reg = bm_.sketch_regions(items)
reg_f = bm_.sketch_regions(items, fill=True)
check('Sketch: four line strokes -> a square frame (one piece with a hole); Area -> the whole square',
      len(reg) == 1 and len(reg[0][1]) == 1 and len(reg_f) == 1 and len(reg_f[0][1]) == 0
      and abs(area(reg_f[0][0]) - 224 ** 2) < 224 ** 2 * 0.01, (len(reg), len(reg[0][1]) if reg else None, len(reg_f)))
sub = {'op': 'SUB', 'groups': [[circle_path(100, 100, 30, 24, close=False), []]]}
reg_fs = bm_.sketch_regions(items + [sub], fill=True)
check('... a subtracted stroke still takes its hole out of the filled area', len(reg_fs) == 1 and len(reg_fs[0][1]) == 1
      and abs(area(reg_fs[0][1][0]) - math.pi * 30 ** 2) < math.pi * 30 ** 2 * 0.1)
brush = C.scene.mch_brush
brush.line_mode, brush.line_area = False, False
check('fill_on: only with Line mode + Area, for a line tool', not ls.fill_on(C, 'CUT'))
brush.line_mode, brush.line_area = True, True
check('... on', ls.fill_on(C, 'CUT') and not ls.fill_on(C, 'SDRAW'))
brush.line_mode, brush.line_area = False, False

src_ce = open(ce.__file__).read()
check('wired: the stroke engine and the Press Line Cut use line_loops; the top bar has the Area button',
      'lasso_line.line_loops(bpy.context, self.projector, self._line_path(pts), self.brush, prof)' in src_ce
      and 'lasso_line.line_loops(context, self.projector, pts, brush, width_px=stamp_px)' in open(pc.__file__).read()
      and "_seg('Area', brush, 'line_area')" in open(top_bar.__file__).read()
      and 'fill=fill_on(context, d.get(\'mode\'))' in open(ls.__file__).read())
summary()
