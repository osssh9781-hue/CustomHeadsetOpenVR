"""0.24.109 / 0.24.110 Press Cut lines (user):
- "한번 긋고 뷰포트 돌려서 처음 그었던 선 끝난 부분에 이어서 그릴 수 있게": a stroke that starts on the end of the last Base Mesh
  line / Line Cut goes on from it - one object, the same section, from either end
- 0.24.110 (user's picture "여기 안 돼": the line must be able to leave its plane) the new piece lies in the plane of the
  CURRENT view through the old end - a 3D centreline with a twist-free section; 0.24.111 (user: "그 메쉬 위치랑 뷰포트
  방향으로") always, no "under 20 deg keeps the first plane" exception
- "컷도 당연히 스탬프 단면으로 잘려야지! 왜 원으로 잘려" / "맥스 조절해서 얕게 만들어도 왜 다 뚫려": the Alt + drag Line Cut is
  the stamp's section swept along the line, pressed in Max x the part's size (not the Cut tool's depth / a round band)
- "스탬프를 로테이션으로 돌리면 베이스 라인으로 나오는 메쉬 앵글도 돌아가야지! 컷도 마찬가지고": the stamp's turn turns the section
"""
import json
import math
import time

from _harness import bmesh, bpy, check, cube, fresh, non_manifold, summary
from mathutils import Euler, Quaternion, Vector

import mecha_lab
from mecha_lab import base_mesh, core_geometry as cg, press_cut as pc

fresh()
mecha_lab.register()
C = bpy.context
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
TILT = cg.OrthoProjector(Euler((0.17, 0.0, 0.0)).to_quaternion(), pixels_per_unit=100.0)    # turned 10 deg
TILT34 = cg.OrthoProjector(Euler((0.6, 0.0, 0.0)).to_quaternion(), pixels_per_unit=100.0)   # turned 34 deg: the view's plane
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0.0, 0.0)).to_quaternion(), pixels_per_unit=100.0)  # from the front (y): top edge-on
SPAN = 2 * 40.0 / 100.0                                       # the stamp's longer side in world units (size 40 px)


class Region:
    width, height = 1000, 1000

    def tag_redraw(self):
        pass


class Shim:
    def report(self, kind, msg):
        self.reports.append((kind, msg))


for n in ('_finish_draw', '_cleanup'):
    setattr(Shim, n, getattr(pc.MCH_OT_press_unified, n))


def stroke(proj, world_pts, make_mesh):
    op = Shim()
    op.reports = []
    op.state, op.down_time = 'DRAW', time.perf_counter()
    op.pts = [tuple(proj.to_screen(Vector(q))) for q in world_pts]
    op.anchor = op.pts[0]
    op.press, op.region, op.projector, op.make_mesh = None, Region(), proj, make_mesh
    op.timer = op.handle = op.handle_red = None
    op.cont_end = None
    return op._finish_draw(C, op.pts[-1]), op


def vol(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    v = bm.calc_volume()
    bm.free()
    return v


def bbox(ob):
    pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    return [(min(q[i] for q in pts), max(q[i] for q in pts)) for i in range(3)]


def inside(ob, co):
    """Parity ray test: is the world point inside the (closed) mesh?"""
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromObject(ob, C.evaluated_depsgraph_get())
    d = Vector((0.31, 0.47, 0.83)).normalized()
    p, n = Vector(co), 0
    for _ in range(64):
        hit, _nrm, _idx, _dist = bvh.ray_cast(p, d)
        if hit is None:
            break
        n += 1
        p = hit + d * 1e-5
    return n % 2 == 1


def area_below(loop, v_s):
    """Area of the polygon part with y <= v_s."""
    out = []
    for a, b in zip(loop, loop[1:] + loop[:1]):
        ina, inb = a[1] <= v_s, b[1] <= v_s
        if ina:
            out.append(a)
        if ina != inb:
            t = (v_s - a[1]) / (b[1] - a[1])
            out.append((a[0] + t * (b[0] - a[0]), v_s))
    return abs(cg.signed_area(out)) if len(out) >= 3 else 0.0


def setup(result='CUT'):
    fresh()
    global C
    C = bpy.context
    st = C.scene.mch_press
    st.size, st.shape, st.rotation, st.result, st.drawn = 40.0, 'MCH_BUILTIN_M_OCTAGON', 0.0, result, False
    C.scene.mch_settings.auto_apply = True
    pc.CONTINUE['base'] = pc.CONTINUE['cut'] = None
    return st, cube('P', size=2.0)


# --- the stamp's turn on the Base Mesh line's section ---------------------------------------------------------------
st, p = setup()
pc.DRAWN[0] = [[(-0.5, -0.2), (0.5, -0.2), (0.5, 0.2), (-0.5, 0.2)]]          # a 1 x 0.4 rectangle stamp
st.drawn = True
before = set(bpy.data.objects.keys())
r, op = stroke(TOP, [(-0.6 + 1.2 * k / 12, 0.0, 1.0) for k in range(13)], True)
new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before]
bb = bbox(new[0]) if new else None
check('plain drag with a flat 1 x 0.4 stamp: the line is as wide as the stamp (0.8) and 0.32 tall', r == {'FINISHED'}
      and new and abs(bb[1][1] - bb[1][0] - SPAN) < 0.03 and abs(bb[2][1] - bb[2][0] - 0.4 * SPAN) < 0.03,
      (round(bb[1][1] - bb[1][0], 3), round(bb[2][1] - bb[2][0], 3)) if bb else r)
st.rotation = math.pi / 2
before = set(bpy.data.objects.keys())
r, op = stroke(TOP, [(-0.6 + 1.2 * k / 12, 0.6, 1.0) for k in range(13)], True)
new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before]
bb = bbox(new[0]) if new else None
check('the stamp turned 90 deg: the section turns with it (0.32 wide, 0.8 tall), standing on the surface', r == {'FINISHED'}
      and new and abs(bb[1][1] - bb[1][0] - 0.4 * SPAN) < 0.03 and abs(bb[2][1] - bb[2][0] - SPAN) < 0.03
      and -0.03 < bb[2][0] - 1.0 < 0.005, (round(bb[1][1] - bb[1][0], 3), round(bb[2][1] - bb[2][0], 3), round(bb[2][0], 3)) if bb else r)
st.rotation, st.drawn = 0.0, False

# --- going on with a Base Mesh line after the view turned --------------------------------------------------------------
st, p = setup()
r, op = stroke(TOP, [(-0.8 + 0.8 * k / 8, 0.0, 1.0) for k in range(9)], True)
ob = C.active_object
ends = base_mesh.sweep_ends(ob)
check('a line: the tool remembers it; its two ends are where the stroke began / ended', r == {'FINISHED'}
      and pc.CONTINUE['base'] == ob.name and ends is not None and (ends[0] - Vector((-0.8, 0, 1))).length < 0.05
      and (ends[1] - Vector((0, 0, 1))).length < 0.05, [tuple(round(c, 2) for c in e) for e in ends] if ends else None)
marks = pc.continue_ends(C, TILT)
check('the ends show in a turned view (the markers) where the view puts them', len(marks) == 2
      and all(math.dist(m[0], TILT.to_screen(w)) < 1.0 for m, w in zip(marks, ends)) and marks[1][3] and not marks[0][3])
radius = pc.continue_radius(st)
hit = pc.nearest_end(C, TILT, TILT.to_screen(Vector((0.05, 0.02, 1.0))), radius, 'base')
check('a stroke starting a few px from the end finds it (and knows it is the end); 60 px away finds nothing',
      hit is not None and hit[2] == ob and hit[3] is True and radius == 30.0
      and pc.nearest_end(C, TILT, TILT.to_screen(Vector((0.6, 0.0, 1.0))), radius, 'base') is None, radius)
n_obj = len(bpy.data.objects)
path0 = json.loads(ob[base_mesh.SWEEP_KEY])['path']
r, op = stroke(TILT, [(0.03 + 0.8 * k / 8, 0.02, 1.0) for k in range(9)], True)
path1 = json.loads(ob[base_mesh.SWEEP_KEY])['path']
ends1 = base_mesh.sweep_ends(ob)
bb = bbox(ob)
check('a stroke from the end with the view turned 10 deg: the SAME object goes on (no new object), the path longer',
      r == {'FINISHED'} and len(bpy.data.objects) == n_obj and len(path1) > len(path0) and non_manifold(ob) == 0,
      (r, len(bpy.data.objects) - n_obj, len(path0), len(path1), op.reports[-1:] if op.reports else None))
check('... laid in the 10 deg view\'s plane through the old end (a stroke drawn along the top stays on it), joined there',
      (ends1[0] - Vector((-0.8, 0, 1))).length < 0.05 and (ends1[1] - Vector((0.82, 0.01, 1.0))).length < 0.05
      and bb[2][0] > 0.9 and bb[2][1] < 1.0 + SPAN + 0.05 and bb[0][1] > 0.75,
      ([tuple(round(c, 2) for c in e) for e in ends1], [tuple(round(c, 2) for c in b) for b in bb]))
check('... the report says so', op.reports and 'continued' in op.reports[-1][1] and 'in the view you drew in: 10 deg' in op.reports[-1][1],
      op.reports[-1:] if op.reports else None)
r, op = stroke(TILT, [(-0.8 - 0.6 * k / 6, 0.01, 1.0) for k in range(7)], True)
ends2 = base_mesh.sweep_ends(ob)
check('from the START end: the line grows backwards (the stroke is put in front), the far end stays', r == {'FINISHED'}
      and (ends2[0] - Vector((-1.4, 0.0, 1.0))).length < 0.06 and (ends2[1] - ends1[1]).length < 1e-6
      and len(bpy.data.objects) == n_obj and non_manifold(ob) == 0, [tuple(round(c, 2) for c in e) for e in ends2])
r, op = stroke(TOP, [(0.0 + 0.8 * k / 8, -0.7, 1.0) for k in range(9)], True)
ob2 = C.active_object
check('a stroke away from both ends: a new line (its own object), now the one to go on from', r == {'FINISHED'}
      and len(bpy.data.objects) == n_obj + 1 and ob2 != ob and pc.CONTINUE['base'] == ob2.name)
# --- 0.24.110 leaving the plane: the view turned 90 deg (from the front), the stroke goes DOWN from the end ------------
n_obj = len(bpy.data.objects)
end2 = base_mesh.sweep_ends(ob2)[1]
v_before = [tuple(ob2.matrix_world @ v.co) for v in ob2.data.vertices]
r, op = stroke(FRONT, [(end2.x + 0.01, end2.y, end2.z - 0.12 * k) for k in range(7)], True)
d2 = json.loads(ob2[base_mesh.SWEEP_KEY])
ends3 = base_mesh.sweep_ends(ob2)
co = [ob2.matrix_world @ v.co for v in ob2.data.vertices]
check('the view turned 90 deg (front), a stroke down from the end: the line BENDS out of its plane (3D path), one object',
      r == {'FINISHED'} and 'path3' in d2 and len(bpy.data.objects) == n_obj and non_manifold(ob2) == 0
      and (ends3[1] - Vector((end2.x, end2.y, end2.z - 0.72))).length < 0.06 and min(v.z for v in co) < end2.z - 0.6,
      (r, 'path3' in d2, [tuple(round(c, 2) for c in e) for e in ends3], round(min(v.z for v in co), 2) if co else None,
       op.reports[-1:] if op.reports else None))
check('... the section does not twist round the bend: the down piece is as wide across (y) as the flat piece',
      co and abs((max(v.y for v in co if v.z < end2.z - 0.3) - min(v.y for v in co if v.z < end2.z - 0.3)) - SPAN) < 0.05,
      round(max(v.y for v in co if v.z < end2.z - 0.3) - min(v.y for v in co if v.z < end2.z - 0.3), 3) if co else None)
check('... the report says it was laid in the view drawn in', op.reports and 'in the view you drew in: 90 deg' in op.reports[-1][1],
      op.reports[-1:] if op.reports else None)
r, op = stroke(TILT34, [(ends3[1].x + 0.5 * k / 5, ends3[1].y + 0.01, ends3[1].z) for k in range(6)], True)
d3 = json.loads(ob2[base_mesh.SWEEP_KEY])
check('a third piece in a 34 deg view: it lies in THAT view\'s plane through the end (the drawn direction), still one closed object',
      r == {'FINISHED'} and len(d3['path3']) > len(d2['path3']) and non_manifold(ob2) == 0 and len(bpy.data.objects) == n_obj,
      (r, len(d2['path3']), len(d3['path3'])))
check('the Base Mesh tool\'s own settings are untouched', C.scene.mch_base.profile_sweep == 'OFF')

# --- the Line Cut = the stamp's section swept, Max deep ----------------------------------------------------------------
st, q = setup()
C.scene.mch_cut.depth_mode = 'THROUGH'                          # (the Cut tool's depth must not matter any more)
st.max_depth = 0.15                                             # 0.3 m of a 2 m part
v0 = vol(q)
r, op = stroke(TOP, [(-0.6 + 1.2 * k / 12, 0.0, 1.0) for k in range(13)], False)
removed = v0 - vol(q)
sec, bottom = pc.line_cut_section(C, st, 0.3, SPAN)
v_min = min(y for _x, y in sec[0])
exp = area_below(sec[0], v_min + 0.3 / SPAN) * SPAN * SPAN * 1.2
check('Alt + drag, Max 0.15 (0.3 m of a 2 m part): a groove 0.3 deep with the STAMP\'S section (the Cut tool\'s Through is not used)',
      r == {'FINISHED'} and abs(removed - exp) < exp * 0.08 and non_manifold(q) == 0 and len(bpy.data.objects) == 1,
      (round(removed, 3), round(exp, 3), op.reports[-1:] if op.reports else None))
inner = [v.co for v in q.data.vertices if abs(v.co.x) < 0.55 and abs(v.co.y) < 0.45 and 0.5 < v.co.z < 0.99]
deep = [v for v in inner if v.z < 0.72]
check('... the deepest point at 1 - 0.3; the bottom narrower than the opening (the octagon\'s lower chamfers, not a flat band)',
      inner and abs(min(v.z for v in inner) - 0.7) < 0.02 and deep and max(abs(v.y) for v in deep) < 0.3,
      (round(min(v.z for v in inner), 3) if inner else None, round(max(abs(v.y) for v in deep), 3) if deep else None))
cutd = pc.CONTINUE['cut']
fr = pc._cut_frame(cutd) if cutd else None
e0 = fr @ Vector((cutd['path'][0][0], cutd['path'][0][1], 0.0)) if cutd else None
e1 = fr @ Vector((cutd['path'][-1][0], cutd['path'][-1][1], 0.0)) if cutd else None
check('the Line Cut is remembered to go on from: its plane and its two ends', cutd is not None
      and (e0 - Vector((-0.6, 0, 1))).length < 0.05 and (e1 - Vector((0.6, 0, 1))).length < 0.05
      and len([m for m in pc.continue_ends(C, TOP) if m[2] is None]) == 2)

st, q = setup()
st.max_depth = 1.0                                              # 2 m of a 2 m part: through
v0 = vol(q)
r, op = stroke(TOP, [(-0.6 + 1.2 * k / 12, 0.0, 1.0) for k in range(13)], False)
removed = v0 - vol(q)
walls = [v.co for v in q.data.vertices if abs(v.co.z) < 0.99 and abs(v.co.x) < 0.59]
check('Max 1.0 on a 2 m part: through - a slot as wide as the stamp with FLAT ends (0.8 x 1.2 x 2; a round-ended band = 2.9)',
      r == {'FINISHED'} and abs(removed - SPAN * 1.2 * 2.0) < 0.1 and non_manifold(q) == 0,
      (round(removed, 3), round(SPAN * 1.2 * 2.0, 3), sorted({round(abs(v.y), 3) for v in walls}),
       sorted({round(v.x, 3) for v in q.data.vertices if abs(v.co.z) < 0.99 and abs(v.co.y) < 0.39})))

st, q = setup()
pc.DRAWN[0] = [[(-0.5, -0.2), (0.5, -0.2), (0.5, 0.2), (-0.5, 0.2)]]
st.drawn, st.max_depth = True, 0.15
v0 = vol(q)
r, op = stroke(TOP, [(-0.6 + 1.2 * k / 12, 0.0, 1.0) for k in range(13)], False)
rem_flat = v0 - vol(q)
st.rotation = math.pi / 2
v0 = vol(q)
r2, op = stroke(TOP, [(-0.6 + 1.2 * k / 12, -0.6, 1.0) for k in range(13)], False)
rem_turned = v0 - vol(q)
check('the stamp\'s turn turns the cut\'s section too: a 1 x 0.4 stamp flat = a 0.8 wide groove, turned 90 deg = 0.32 wide',
      r == {'FINISHED'} and r2 == {'FINISHED'} and abs(rem_flat - SPAN * 1.2 * 0.3) < 0.03
      and abs(rem_turned - 0.4 * SPAN * 1.2 * 0.3) < 0.02, (round(rem_flat, 3), round(SPAN * 1.2 * 0.3, 3), round(rem_turned, 3), round(0.4 * SPAN * 1.2 * 0.3, 3)))
st.drawn, st.rotation = False, 0.0

# --- going on with a Line Cut after the view turned --------------------------------------------------------------------
st, q = setup()
st.max_depth = 0.15
v0 = vol(q)
r, op = stroke(TOP, [(-0.8 + 0.8 * k / 8, 0.0, 1.0) for k in range(9)], False)
v1 = vol(q)
n_path = len(pc.CONTINUE['cut']['path'])
r, op = stroke(TILT, [(0.03 + 0.8 * k / 8, 0.02, 1.0) for k in range(9)], False)
v2 = vol(q)
cutd = pc.CONTINUE['cut']
fr = pc._cut_frame(cutd)
e1 = fr @ Vector((cutd['path'][-1][0], cutd['path'][-1][1], 0.0))
check('an Alt stroke from the cut\'s end with the view turned 10 deg: the groove goes on in its plane (same depth / section), no new object',
      r == {'FINISHED'} and abs((v1 - v2) - exp * 0.8 / 1.2) < exp * 0.8 / 1.2 * 0.12 and len(cutd['path']) > n_path
      and (e1 - Vector((0.82, 0.01, 1.0))).length < 0.05 and len(bpy.data.objects) == 1 and non_manifold(q) == 0,
      (round(v1 - v2, 3), round(exp * 0.8 / 1.2, 3), len(cutd['path']), op.reports[-1:] if op.reports else None))
check('... the report says so', op.reports and 'Line Cut continued' in op.reports[-1][1] and 'in the view you drew in: 10 deg' in op.reports[-1][1])
probe = (0.82 + 0.12, 0.01 + 0.12, 0.95)               # in the outer corner's wedge (past the flat end cap), 5 cm down
wedge_before = inside(q, probe)
r, op = stroke(TILT, [(0.82, 0.01 - 0.7 * k / 7, 1.0) for k in range(8)], False)
v3 = vol(q)
check('a continued cut turning a corner (-y from the end): the corner is swept too (no wedge of material left), still closed',
      r == {'FINISHED'} and wedge_before and not inside(q, probe) and v2 - v3 > exp * 0.7 / 1.2 * 0.5 and non_manifold(q) == 0,
      (round(v2 - v3, 3), round(exp * 0.7 / 1.2, 3), wedge_before, inside(q, probe)))

# 0.24.110 a groove that leaves its plane: from the front view, down from the groove's end (into the part)
st, q = setup()
st.max_depth = 0.15
r, op = stroke(TOP, [(-0.8 + 0.8 * k / 8, 0.0, 1.0) for k in range(9)], False)
v1 = vol(q)
r, op = stroke(FRONT, [(0.0, 0.0, 1.0 - 0.1 * k) for k in range(7)], False)
v2 = vol(q)
cutd = pc.CONTINUE['cut']
check('a Line Cut continued DOWN from its end in the front view: the swept stamp goes down into the part (3D path), still closed',
      r == {'FINISHED'} and v1 - v2 > 0.02 and non_manifold(q) == 0 and len(cutd['path'][-1]) == 3
      and cutd['path'][-1][2] < -0.4 and 'in the view you drew in: 90 deg' in op.reports[-1][1],
      (round(v1 - v2, 3), cutd['path'][-1] if cutd else None, op.reports[-1:] if op.reports else None))

st, q = setup('SPLIT')
st.max_depth = 0.15
n_obj = len(bpy.data.objects)
v0 = vol(q)
r, op = stroke(TOP, [(-0.6 + 1.2 * k / 12, 0.0, 1.0) for k in range(13)], False)
piece = [o for o in bpy.data.objects if o != q]
check('Split: the swept piece is kept as its own part (the groove\'s volume)', r == {'FINISHED'} and len(piece) == 1
      and abs(vol(piece[0]) - (v0 - vol(q))) < 0.01 and non_manifold(piece[0]) == 0, (len(piece), round(vol(piece[0]), 3) if piece else None))

# --- wiring ---------------------------------------------------------------------------------------------------------
src = open(pc.__file__).read()
src_b = open(base_mesh.__file__).read()
check('wired: the unified draw snaps to an end, extends the sweep / continues the cut, draws the end markers, turns the section',
      "hit = nearest_end(context, self.projector, pts[0], continue_radius(pr), 'base' if self.make_mesh else 'cut')" in src
      and 'base_mesh.extend_sweep(ob, self.projector, pts, at_end,' in src
      and 'base_mesh.sweep_cut(context, frame, local_path, section, width, height, bottom, targets, mode)' in src
      and '_draw_end_marks(context, sh, marks, 0.5 * continue_radius(st))' in src
      and 'section_rest=True, section_rotation=float(pr.rotation))' in src
      and 'def envelope_section(' in src_b and "bottom = data.get('bottom')" in src_b
      and 'base_mesh.continue_plane_path(frame, self.projector, pts, old[-1])' in src
      and 'frames = sweep_frames(stations)' in src_b and base_mesh.CONTINUE_SAME_PLANE_DEG == 0.0)
summary()
