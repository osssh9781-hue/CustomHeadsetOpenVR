"""0.24.95 Press Cut (user: "내가 정한 라쏘 모양을 저장해 놓으면 그걸로 잘리는데 약간 밀리면서 잘리는 거지 - 내가 오래 누르면
더 잘리고 조금 누르면 조금만 잘리는"; "스케치 라쏘로 그리고 프리셋 저장 누르면 저장"):

* a new tool (Cut group, after Split): its settings, the top bar group, the sidebar, the key legend, its icon
* depth = (Start + Speed x seconds held) x the part's size, up to Max
* a held press (its steps as the tool runs them): each step cut From Surface from the part as it was - deeper the
  longer it is held, the volume taken grows, a closed solid; the Cut settings come back after; Esc puts it back
* Result Split: the pressed-in plug its own part
* the part under the mouse is pressed (not the active one)
* Save Shape: the last outline drawn (Cut / Split) kept; saved: normalized, in the Press shape list, usable;
  Press Cut's own stamp is not "the last outline"
"""
import math

from _harness import bmesh, bpy, check, cube, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, cut_presets, press_cut as pc, tool_state as ts

mecha_lab.register()
C = bpy.context
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)


def vol(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    v = bm.calc_volume()
    bm.free()
    return v


def pocket_depth(ob, top=1.0):
    zs = [(ob.matrix_world @ v.co).z for v in ob.data.vertices]
    inner = [z for z in zs if -top + 1e-3 < z < top - 1e-3]
    return top - min(inner) if inner else 0.0


ids = [t[0] for t in ts.TOOLS]
groups = dict(ts.TOOL_GROUPS)
check('Press Cut: a tool (after Split in the Cut group), its own settings, an icon',
      'PRESS' in ids and ids.index('PRESS') == ids.index('SPLIT') + 1 and groups['Cut'][2] == 'PRESS'
      and hasattr(C.scene, 'mch_press') and ts._ENUM_NUMBERS['PRESS'] == 60
      and (cg.__file__ and __import__('os').path.isfile(
          __import__('os').path.join(__import__('os').path.dirname(pc.__file__), 'icons', 'press_cut.png'))))

st = C.scene.mch_press                      # (read again after every fresh(): a new file frees the old scene)
size = 2.0
d0, d1, d2, dmax = (pc.depth_at(st, size, t) for t in (0.0, 1.0, 2.0, 100.0))
check('Depth = (Start + Speed x seconds) x the part\'s size, up to Max',
      abs(d0 - size * st.start) < 1e-9 and abs(d1 - size * (st.start + st.speed)) < 1e-9 and d2 > d1 > d0
      and abs(dmax - size * st.max_depth) < 1e-9, [round(x, 4) for x in (d0, d1, d2, dmax)])


def held(seconds, result='CUT', shape=None, curve=(0.0, 0.0)):
    """A press held ``seconds`` on a 2 m box, its steps as the tool runs them (one per tick when it grew enough)."""
    fresh()
    if shape:
        C.scene.mch_press.shape = shape
    C.scene.mch_settings.auto_apply = True
    C.scene.mch_cut.depth_mode, C.scene.mch_cut.depth = 'THROUGH', 0.1
    p = cube('P', size=2.0)
    v0 = vol(p)
    ps = C.scene.mch_press
    xy = TOP.to_screen(Vector((0, 0, 1)))
    pr = pc.Press(C, p, pc.stamp_loops(C, xy, ps), TOP, result, center=xy, curve=curve, spacing=6.0)
    pr.cut_to(C, pc.depth_at(ps, pr.size, 0.0))
    t = 0.0
    while t < seconds:
        t += pc.TICK
        d = pc.depth_at(ps, pr.size, t)
        if d - pr.depth >= pc.STEP_MIN * pr.size:
            pr.cut_to(C, d)
    pr.finish(C)
    return p, pr, v0


runs = []
for secs in (0.0, 0.5, 1.5):
    p, pr, v0 = held(secs)
    runs.append((secs, round(pr.depth, 4), round(pocket_depth(p), 4), round(v0 - vol(p), 4), non_manifold(p),
                 C.scene.mch_cut.depth_mode))
check('Held 0 / 0.5 / 1.5 s: cut deeper the longer it is held (the pocket as deep as the press), more taken away, '
      'a closed solid; the Cut settings back as they were (Through All)',
      runs[0][1] < runs[1][1] < runs[2][1] and runs[0][3] < runs[1][3] < runs[2][3]
      and all(abs(r[1] - r[2]) < 2e-3 and r[4] == 0 and r[5] == 'THROUGH' for r in runs)
      and abs(runs[2][1] - pc.depth_at(C.scene.mch_press, 2.0, 1.5)) < 0.05, runs)
check('... the kept copy of the part gone afterwards', not [m for m in bpy.data.meshes
                                                            if m.name.startswith('MCH_PressBackup')])

fresh()
p = cube('P', size=2.0)
n0 = len(p.data.vertices)
pr = pc.Press(C, p, pc.stamp_loops(C, TOP.to_screen(Vector((0, 0, 1))), C.scene.mch_press), TOP, 'CUT')
pr.cut_to(C, 0.3)
cut_once = len(p.data.vertices)
pr.cancel(C)
check('Esc / right click while holding: the part back as it was', cut_once > n0 and len(p.data.vertices) == n0
      and abs(vol(p) - 8.0) < 1e-6, (n0, cut_once, len(p.data.vertices)))

p, pr, v0 = held(1.0, 'SPLIT')
piece = bpy.data.objects.get('P_Split')
check('Result Split: the pressed-in plug is its own part (as deep as the press), both closed',
      piece is not None and abs(vol(piece) + vol(p) - v0) < 1e-3 and non_manifold(piece) == 0
      and non_manifold(p) == 0 and abs((max(v.co.z for v in piece.data.vertices)
                                        - min(v.co.z for v in piece.data.vertices)) - pr.depth) < 2e-3,
      piece and (round(vol(piece), 4), round(pr.depth, 4)))

fresh()
a = cube('A', size=2.0, loc=(-3, 0, 0))
b = cube('B', size=2.0, loc=(3, 0, 0))
C.view_layer.objects.active = b
for o in C.selected_objects:
    o.select_set(False)
C.scene.mch_cut.targets = 'AUTO'
picked = pc.press_target(C, TOP, TOP.to_screen(Vector((-3, 0, 1))))
none = pc.press_target(C, TOP, TOP.to_screen(Vector((0, 0, 1))))
check('The part under the mouse is pressed (not the active one); off the parts: nothing', picked == a and none is None,
      (picked and picked.name, none))

# Save Shape: the last drawn outline
fresh()
C.scene.mch_settings.auto_apply = True
p = cube('P', size=2.0)
cx, cy = TOP.to_screen(Vector((0, 0, 0)))
drawn = [(cx - 60, cy - 30), (cx + 60, cy - 30), (cx + 60, cy + 10), (cx, cy + 40), (cx - 60, cy + 10)]
cut_presets.LAST_LOOPS[0] = None
ce.perform_closed(C, 'CUT', [p], [drawn], TOP)
kept = cut_presets.LAST_LOOPS[0]
check('Save Shape: a Cut drawn with a lasso is kept as the last outline', kept is not None and len(kept[0]) == 5)
stem = cut_presets.save_loops('House Notch', kept)
lp = cut_presets.load_loops(stem)
xs, ys = [q[0] for q in lp[0]], [q[1] for q in lp[0]]
st = C.scene.mch_press
items = [i[0] for i in pc._shape_items(st, C)]
check('... saved: normalized (centred, the long side 1, its proportions kept), in the Press Cut shape list',
      abs(min(xs) + 0.5) < 1e-6 and abs(max(xs) - 0.5) < 1e-6 and abs((max(ys) - min(ys)) - 70 / 120) < 1e-4
      and stem in items, (round(min(xs), 3), round(max(xs), 3), round(max(ys) - min(ys), 4)))
p, pr, v0 = held(0.5, shape=stem)
st = C.scene.mch_press
sx = sorted({round((p.matrix_world @ v.co).x, 3) for v in p.data.vertices if pocket_depth(p) and
             abs((p.matrix_world @ v.co).z - (1 - pr.depth)) < 1e-3})
check('... and pressed with it: the pocket has the saved outline (as wide as the stamp: 2 x Size px)',
      st.shape == stem and pr.depth > 0 and sx and abs((sx[-1] - sx[0]) - 2 * st.size / 100.0) < 0.02, (round(pr.depth, 4), sx[:1], sx[-1:]))
check('... Press Cut\'s own stamp is not "the last outline" (it stays the drawn one)',
      cut_presets.LAST_LOOPS[0] is kept)


def floor_depth(p, x, y, r=0.05):
    """The pocket's depth below the top at (x, y) (its points within ``r``), None where nothing was cut."""
    zs = [v.co.z for v in p.data.vertices if -0.999 < v.co.z < 0.999 and abs(v.co.x - x) < r and abs(v.co.y - y) < r]
    return round(1.0 - min(zs), 3) if zs else None


# 0.24.95 (user: "곡률은 이 스탬프가 결국 평면일 텐데 그걸 좌우로 동그랗게 커브를 주는 거지 - 위아래 좌우로 나누면 좋을 듯")
res = {}
for name, curve, secs in (('lr', (0.5, 0.0), 1.2), ('ud', (0.0, 0.5), 1.2), ('both', (0.5, 0.5), 1.2),
                          ('neg', (-0.5, 0.0), 1.2), ('tap', (0.5, 0.0), 0.0)):
    p, pr, v0 = held(secs, curve=curve)
    res[name] = (round(pr.depth, 3), floor_depth(p, 0, 0), floor_depth(p, 0.4, 0), floor_depth(p, 0, 0.3),
                 non_manifold(p), round(v0 - vol(p), 4))
d = res['lr'][0]
check('Curve Left-Right +0.5: a round trough - the middle as deep as the press, shallower toward the left / right '
      'sides, the same up-down; a closed solid',
      abs(res['lr'][1] - d) < 0.01 and res['lr'][2] < d - 0.05 and abs(res['lr'][3] - d) < 0.01 and res['lr'][4] == 0,
      res['lr'])
check('Curve Up-Down +0.5: shallower toward the top / bottom only', abs(res['ud'][1] - d) < 0.01
      and abs(res['ud'][2] - d) < 0.01 and res['ud'][3] < d - 0.03 and res['ud'][4] == 0, res['ud'])
check('Both: a bowl (shallower every way), less taken away than either', res['both'][2] < d - 0.05
      and res['both'][3] < d - 0.03 and res['both'][5] < min(res['lr'][5], res['ud'][5]) and res['both'][4] == 0,
      res['both'])
check('Curve -0.5: the sides go in deepest, the middle stays raised (nothing cut there at this depth)',
      (res['neg'][1] is None or res['neg'][1] < d - 0.1) and res['neg'][2] is not None and res['neg'][4] == 0,
      res['neg'])
check('A quick tap with a round stamp: only the middle dips in (the sides not yet reached)',
      res['tap'][1] is not None and res['tap'][2] is None and res['tap'][4] == 0, res['tap'])
check('Flat stamp (no curve): the cutter as before (no grid in the floor)', pc.Press.floor.__doc__ is not None
      and held(0.5)[1].floor(0.1) is None)



# 0.24.95 (user's screenshot: a From Surface cut seen at an angle left the near side standing as a lip) Follow Surface
from mathutils import Euler  # noqa: E402
TILT = cg.OrthoProjector(Euler((math.radians(50), 0, 0)).to_quaternion(), pixels_per_unit=100.0)


def standing(p, c, half=50, step=10):
    """How many sample rays inside the square round screen ``c`` still meet the untouched top face first."""
    n = 0
    for j in range(-half, half + 1, step):
        for i in range(-half, half + 1, step):
            o, d = TILT.ray((c[0] + i, c[1] + j))
            ok, loc, _n, _f = p.ray_cast(o, d)
            n += bool(ok and abs(loc.z - 1.0) < 1e-4)
    return n


lip = {}
for follow in (False, True):
    fresh()
    C.scene.mch_settings.auto_apply = True
    C.scene.mch_cut.depth_mode, C.scene.mch_cut.depth = 'SURFACE', 0.3
    C.scene.mch_cut.depth_floor = 'FOLLOW' if follow else 'FLAT'
    p = cube('P', size=2.0)
    c = TILT.to_screen(Vector((0, 0, 1)))
    sq = [(c[0] - 60, c[1] - 60), (c[0] + 60, c[1] - 60), (c[0] + 60, c[1] + 60), (c[0] - 60, c[1] + 60)]
    ce.perform_closed(C, 'CUT', [p], [sq], TILT)
    lip[follow] = (standing(p, c), non_manifold(p), round(8.0 - vol(p), 4))
check('Cut From Surface seen at an angle: the near side stands as a lip (as before); Follow Surface on: the whole '
      'shape cut as deep below the surface everywhere (no lip), a closed solid',
      lip[False][0] > 30 and lip[True][0] == 0 and lip[True][1] == 0 and lip[True][2] > lip[False][2], lip)
fresh()
C.scene.mch_settings.auto_apply = True
p = cube('P', size=2.0)
c = TILT.to_screen(Vector((0, 0, 1)))
pr = pc.Press(C, p, pc.stamp_loops(C, c, C.scene.mch_press), TILT, 'CUT', center=c, spacing=6.0, follow=True)
pr.cut_to(C, 0.3)
pr.finish(C)
inside = 0
for q in pc.stamp_loops(C, c, C.scene.mch_press)[0][::3]:   # (sample points just inside the stamp's outline)
    qx, qy = c[0] + (q[0] - c[0]) * 0.8, c[1] + (q[1] - c[1]) * 0.8
    o, d = TILT.ray((qx, qy))
    ok, loc, _n, _f = p.ray_cast(o, d)
    inside += bool(ok and abs(loc.z - 1.0) < 1e-4)
check('Press Cut, Follow Surface (on by default): seen at an angle, no lip inside the stamp, a closed solid',
      C.scene.mch_press.floor_mode == 'FOLLOW' and inside == 0 and non_manifold(p) == 0, (inside, non_manifold(p)))

# 0.24.95 (user: "이렇게는 또 안 잘려" - the stamp's middle just off a part's side)
FRONT = cg.OrthoProjector(Quaternion((0.7071068, 0.7071068, 0, 0)), pixels_per_unit=100.0)
fresh()
C.scene.mch_settings.auto_apply = True
p = cube('P', size=2.0)
xy = FRONT.to_screen(Vector((1.25, -1.0, 0.0)))
loops = pc.stamp_loops(C, xy, C.scene.mch_press)
under = pc.press_target(C, FRONT, xy)
t = pc.press_target(C, FRONT, xy, loops)
pr = pc.Press(C, p, loops, FRONT, 'CUT', center=xy, spacing=6.0, follow=True)
ok = pr.cut_to(C, 0.3)
pr.finish(C)
far = pc.press_target(C, FRONT, FRONT.to_screen(Vector((4.0, -1.0, 0.0))),
                      pc.stamp_loops(C, FRONT.to_screen(Vector((4.0, -1.0, 0.0))), C.scene.mch_press))
check('The stamp\'s middle off the part\'s side, the stamp over it: the part is pressed and cut; nowhere near a part: '
      'nothing', under is None and t == p and ok and 8.0 - vol(p) > 0.01 and non_manifold(p) == 0 and far is None,
      (under, t and t.name, ok, round(8.0 - vol(p), 4), far))


# 0.24.95 (user: "부품 밖에서 잘리는 거 될 때도 있고 안 될 때도 있어, 중앙까지는 걸쳐야 돼") a square stamp over a bar's
# end: its middle and all four corners off the bar, only its side over it - the surface was looked for under the middle
# and the corners only: none found, nothing cut


def bar():
    ob = cube('B', size=1.0)
    for v in ob.data.vertices:                     # x -1 .. 0.1, y -0.2 .. 0.2, top z 0.5
        v.co.x = -1.0 if v.co.x < 0 else 0.1
        v.co.y *= 0.4
    ob.data.update()
    C.view_layer.update()
    return ob


def square_px(proj, c, r):
    cx, cy = proj.to_screen(Vector(c))
    r *= 100
    return [(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r)]


offs = []
for mode in ('FLAT', 'FOLLOW', 'LEVEL'):
    fresh()
    C.scene.mch_settings.auto_apply = True
    b = bar()
    v0 = vol(b)
    sq = square_px(TOP, (0.4, 0.0, 0.5), 0.4)
    xy = TOP.to_screen(Vector((0.4, 0.0, 0.5)))
    hits = [ce.surface_hit(C, [b], TOP, q) is not None for q in sq + [xy]]
    t = pc.press_target(C, TOP, xy, [sq])
    pr = pc.Press(C, b, [sq], TOP, 'CUT', center=xy, spacing=6.0, follow=mode == 'FOLLOW', level=mode == 'LEVEL')
    ok = pr.cut_to(C, 0.2)
    pr.finish(C)
    offs.append((mode, any(hits), t and t.name, ok, round(v0 - vol(b), 4), non_manifold(b)))
fresh()
C.scene.mch_settings.auto_apply = True
C.scene.mch_cut.depth_mode, C.scene.mch_cut.depth = 'SURFACE', 0.2
b = bar()
v0 = vol(b)
msg = ce.perform_closed(C, 'CUT', [b], [square_px(TOP, (0.4, 0.0, 0.5), 0.4)], TOP)
offs.append(('Cut tool', round(v0 - vol(b), 4), non_manifold(b), msg[:12]))
check('A square stamp over a bar\'s end, its middle and all 4 corners off the bar: Press (Flat / Follow / Level) and '
      'the Cut tool From Surface find the bar under its side and cut it (0.1 x 0.4 x 0.2 = 0.008), a closed solid',
      all(not o[1] and o[2] == 'B' and o[3] and abs(o[4] - 0.008) < 1e-3 and o[5] == 0 for o in offs[:3])
      and abs(offs[3][1] - 0.008) < 1e-3 and offs[3][2] == 0, offs)

# 0.24.95 Level (user: "팔로우 서페이스 말고 내가 선택한 면보다 옆에 면이 높이 있으면 거기는 그냥 내가 선택한 위치까지 걍
# 지워 버리는 버튼"): a step - the left half 1 m high, the right half 0.5 m; pressed on the low face beside the step


def step_block():
    def build(bm):
        prof = [(-1, -1), (1, -1), (1, 0.5), (0, 0.5), (0, 1), (-1, 1)]       # (x, z)
        a = [bm.verts.new((x, -1, z)) for x, z in prof]
        c = [bm.verts.new((x, 1, z)) for x, z in prof]
        bm.faces.new(a)
        bm.faces.new(list(reversed(c)))
        for i in range(len(prof)):
            j = (i + 1) % len(prof)
            bm.faces.new((a[i], a[j], c[j], c[i]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    from _harness import mesh_obj
    return mesh_obj('S', build)


def top_z(ob, x):
    o, d = TOP.ray(TOP.to_screen(Vector((x, 0.0, 0.0))))
    ok, loc, _n, _f = ob.ray_cast(o, d)
    return round(loc.z, 3) if ok else None


lv = {}
for mode in ('FLAT', 'FOLLOW', 'LEVEL'):
    fresh()
    C.scene.mch_settings.auto_apply = True
    s_ = step_block()
    sq = square_px(TOP, (0.3, 0.0, 0.5), 0.5)          # (x -0.2 .. 0.8: over the step, pressed on the low side)
    xy = TOP.to_screen(Vector((0.3, 0.0, 0.5)))
    pr = pc.Press(C, s_, [sq], TOP, 'CUT', center=xy, spacing=6.0, follow=mode == 'FOLLOW', level=mode == 'LEVEL')
    ok = pr.cut_to(C, 0.2)
    pr.finish(C)
    lv[mode] = (ok, top_z(s_, -0.1), top_z(s_, 0.5), top_z(s_, -0.6), non_manifold(s_))
check('Level: pressed on the low face beside a step - the raised face under the stamp cleared down to the same floor '
      '(0.5 - 0.2 = 0.3) as the low face; Follow: 0.2 below each face (0.8 / 0.3); Flat: the raised face left '
      'standing (1.0); outside the stamp nothing changes; closed solids',
      lv['LEVEL'][:4] == (True, 0.3, 0.3, 1.0) and lv['FOLLOW'][:4] == (True, 0.8, 0.3, 1.0)
      and lv['FLAT'][:4] == (True, 1.0, 0.3, 1.0) and all(v[4] == 0 for v in lv.values()), lv)
st = C.scene.mch_press
check('... the Floor choice: Follow (default) / Level / Flat in Press Cut, the same with Flat the default in the '
      'Cut tool (From Surface)', [i.identifier for i in st.bl_rna.properties['floor_mode'].enum_items] ==
      ['FOLLOW', 'LEVEL', 'FLAT'] and st.floor_mode == 'FOLLOW' and C.scene.mch_cut.depth_floor == 'FLAT'
      and [i.identifier for i in C.scene.mch_cut.bl_rna.properties['depth_floor'].enum_items] ==
      ['FOLLOW', 'LEVEL', 'FLAT'])



# 0.24.95 (user: "메카닉에 쓸 수 있는 스탬프도 50종 - 썸네일도 보이게 그치만 가볍게", "형태 잡기용이야")
mech = [b[0] for b in cut_presets.builtin_shapes() if b[0].startswith('MCH_BUILTIN_M_')]
bad = []
for stem in mech:
    p, pr, v0 = held(0.3, shape=stem)
    if not (pr.depth > 0 and v0 - vol(p) > 1e-4 and non_manifold(p) == 0):
        bad.append((stem[14:], round(v0 - vol(p), 5), non_manifold(p), pr.message[:40]))
import os  # noqa: E402
icons = [os.path.join(os.path.dirname(pc.__file__), 'icons', 'shape_' + st[12:].lower() + '.png') for st in mech]
check('50 mech form-blocking stamps: each pressed into a box cuts it, a closed solid; each with a light picture '
      '(64 px, a few kB)', len(mech) == 50 and not bad and all(os.path.isfile(i) and os.path.getsize(i) < 6000
                                                              for i in icons), bad)



# 0.24.95 (user: "여기 왜 라쏘 툴이 없어? 그릴 수가 없는데" -> "그렇게 하자") Shift + drag draws your own stamp
fresh()
C.scene.mch_settings.auto_apply = True
p = cube('P', size=2.0)
cx, cy = TOP.to_screen(Vector((0, 0, 1)))
house = []                                         # (a freehand house outline, as the mouse moves: many points)
for a, b in (((-50, -40), (50, -40)), ((50, -40), (50, 20)), ((50, 20), (0, 60)), ((0, 60), (-50, 20)),
             ((-50, 20), (-50, -40))):
    for k in range(12):
        house.append((cx + a[0] + (b[0] - a[0]) * k / 12, cy + a[1] + (b[1] - a[1]) * k / 12))
cut_presets.LAST_LOOPS[0] = None
ok, why = pc.use_drawn(C, house)
st = C.scene.mch_press
lp = pc.stamp_loops(C, (cx, cy), st)[0]
xs, ys = [q[0] for q in lp], [q[1] for q in lp]
check('Shift + drag: the drawn outline is the stamp at once - its shape (simplified to its corners), the size it was '
      'drawn, unturned; it is the last outline (Save Shape keeps it)',
      ok and st.drawn and abs((max(xs) - min(xs)) - 100) < 1.5 and abs((max(ys) - min(ys)) - 100) < 1.5
      and 5 <= len(lp) <= 8 and st.rotation == 0.0 and cut_presets.LAST_LOOPS[0] is not None,
      (ok, why, len(lp), round(max(xs) - min(xs), 1), round(max(ys) - min(ys), 1)))
pr = pc.Press(C, p, pc.stamp_loops(C, (cx, cy), st), TOP, 'CUT', center=(cx, cy), spacing=6.0, follow=True)
pr.cut_to(C, 0.3)
pr.finish(C)
roof = [v for v in p.data.vertices if abs(v.co.z - 0.7) < 1e-3 and v.co.y > 0.3]
check('... pressed (the stamp centred on the mouse: the house 1 m tall, its roof point 0.5 up): the pocket has the '
      'house outline, a closed solid',
      non_manifold(p) == 0 and any(abs(v.co.x) < 0.02 and abs(v.co.y - 0.5) < 0.02 for v in roof),
      [(round(v.co.x, 3), round(v.co.y, 3)) for v in roof][:6])
st.shape = 'MCH_BUILTIN_M_OCTAGON'
check('... picking a shape from the list: the drawn one gives way to it', not st.drawn
      and len(pc.stamp_loops(C, (cx, cy), st)[0]) == 8)
bow = [(cx - 50, cy - 50), (cx + 50, cy + 50), (cx + 50, cy - 50), (cx - 50, cy + 50)]
ok2, why2 = pc.use_drawn(C, bow)
tiny = pc.use_drawn(C, [(cx, cy), (cx + 2, cy), (cx + 2, cy + 2)])
check('... an outline that crosses itself, or a tiny scribble: refused with a reason (the stamp stays)',
      not ok2 and 'crosses' in why2 and not tiny[0] and not st.drawn, (why2, tiny))
press_keys2 = [(k[0], k[1]['type'], k[1].get('shift', False), k[1].get('alt', False),
               dict((k[2] or {}).get('properties', [])).get('mode')) for k in pc.TOOL_KEYMAP]
names = [k[0] for k in pc.TOOL_KEYMAP]
check('... Shift + LMB in the Press Cut tool is the drawing - the shared shape stroke (Lasso, Curve Lasso, Rectangle, '
      'Circle, Ellipse, Free Draw), Shift + Alt for a Sketch\'s subtract; LMB alone still presses; the Sketch keys '
      '(Enter / Backspace / Esc) before Esc = leave the tool (0.24.100: LMB = the unified press: hold presses, '
      'a drag is a Line Cut; Alt+LMB: Grow / Base Mesh line)',
      ('mch.cut_stroke', 'LEFTMOUSE', True, False, 'PRESS') in press_keys2
      and ('mch.cut_stroke', 'LEFTMOUSE', True, True, 'PRESS') in press_keys2
      and ('mch.press_unified', 'LEFTMOUSE', False, False, None) in press_keys2
      and ('mch.press_unified', 'LEFTMOUSE', False, True, None) in press_keys2
      and 'PRESS' in [i.identifier for i in bpy.ops.mch.cut_stroke.get_rna_type().properties['mode'].enum_items]
      and 'mch.lasso_sketch_key' in names and names.index('mch.lasso_sketch_clear') < names.index('mch.exit_tool'),
      press_keys2)

# 0.24.95 (user: "깊이 들어갈 때 메쉬 쪽에 붉은색으로 얼마나 들어가고 있는지 보이게 해 줘") while holding: the pocket's
# walls and floor in red, deeper = darker
reds = {}
for result in ('CUT', 'SPLIT'):
    fresh()
    C.scene.mch_settings.auto_apply = True
    p = cube('P', size=2.0)
    xy = TOP.to_screen(Vector((0, 0, 1)))
    lps = pc.stamp_loops(C, xy, C.scene.mch_press)
    pr = pc.Press(C, p, lps, TOP, result, center=xy, spacing=6.0)
    empty = pr.pocket()
    pr.cut_to(C, 0.3)
    pos, col, deep = pr.pocket()
    r_px = max(math.dist(q, xy) for lp in lps for q in lp) / 100.0
    zs = [q[2] for q in pos]
    inside = all(math.hypot(q[0], q[1]) <= r_px + 1e-3 for q in pos)
    floor_a = [c[3] for q, c in zip(pos, col) if abs(q[2] - (1.0 - 0.3)) < 0.01]
    rim_a = [c[3] for q, c in zip(pos, col) if abs(q[2] - 1.0) < 0.01]
    reds[result] = (len(pos), round(min(zs), 3), round(max(zs), 3), inside, round(deep, 3),
                    round(min(floor_a), 2) if floor_a else None, round(max(rim_a), 2) if rim_a else None,
                    empty[0] == [])
    pr.finish(C)
check('While pressing (Cut and Split): the pocket\'s walls and floor as red triangles, only inside the stamp, from the '
      'surface (z 1) down to the press depth (0.3); the floor darkest (alpha 0.8), the rim lightest (0.35); nothing '
      'before the first cut',
      all(v[0] > 0 and abs(v[1] - 0.7) < 0.01 and v[2] <= 1.002 and v[3] and abs(v[4] - 0.3) < 0.01
          and v[5] is not None and v[5] >= 0.79 and v[6] is not None and v[6] <= 0.36 and v[7] for v in reds.values()),
      reds)

# ... and a depth gauge beside the stamp (user: a red line drawn down the stamp's right side): as tall as the stamp,
# the top = the surface, the bottom = Max, red down to the depth pressed
sq = [(400.0, 300.0), (500.0, 300.0), (500.0, 420.0), (400.0, 420.0)]
g0, g1, g2 = (pc.depth_gauge([sq], d, 0.8) for d in (0.0, 0.4, 0.8))
g9 = pc.depth_gauge([sq], 2.0, 0.8)
gs = pc.depth_gauge([[(400.0, 300.0), (420.0, 300.0), (420.0, 310.0)]], 0.2, 0.8)
check('Depth gauge: right of the stamp, from its top (the surface) to its bottom (Max); 0 / half / Max deep = the top '
      '/ the middle / the bottom (deeper than Max stays at the bottom); a small stamp still gets a 60 px gauge',
      g0['x'] > 500 and (g0['top'], g0['bottom']) == (420.0, 300.0) and g0['level'] == 420.0
      and abs(g1['level'] - 360.0) < 1e-9 and g2['level'] == 300.0 and g9['level'] == 300.0
      and abs(gs['top'] - gs['bottom'] - 60.0) < 1e-9, (g0, g1['level'], g2['level'], gs))

# ... and a flat face seen from straight above stays flat for Follow (float32 rays read it up to 2e-4 off a plane: it
# was taken for curved and got a grid floor of ~550 faces)
fresh()
C.scene.mch_settings.auto_apply = True
p = cube('P', size=2.0)
C.scene.mch_press.size = 45.0
xy = TOP.to_screen(Vector((0, 0, 1)))
pr = pc.Press(C, p, pc.stamp_loops(C, xy, C.scene.mch_press), TOP, 'CUT', center=xy, spacing=4.5, follow=True)
pr.cut_to(C, 0.226)
nf = len(p.data.polygons)
planar = pr.sfloor.planar
pr.finish(C)
check('Follow on a flat face seen from straight above: a flat floor (the cut as clean as Flat), a closed solid',
      planar and nf < 40 and non_manifold(p) == 0, (planar, nf))

# 0.24.95 (user: "원래 쓰던 라쏘랑 스케치 다 넣어 줘") the stamp drawn as several outlines - a Sketch's islands and holes
from mecha_lab import lasso_sketch, top_bar
fresh()
C.scene.mch_settings.auto_apply = True
st = C.scene.mch_press
cx, cy = TOP.to_screen(Vector((0, 0, 1)))
ring_out = [(cx - 60, cy - 60), (cx + 60, cy - 60), (cx + 60, cy + 60), (cx - 60, cy + 60)]
ring_in = [(cx - 25, cy - 25), (cx + 25, cy - 25), (cx + 25, cy + 25), (cx - 25, cy + 25)]
ok3, why3 = pc.use_loops(C, [ring_out, list(reversed(ring_in))])
loops3 = pc.stamp_loops(C, (cx, cy), st)
p = cube('P', size=2.0)
pr = pc.Press(C, p, loops3, TOP, 'CUT', center=(cx, cy), spacing=6.0)
pr.cut_to(C, 0.3)
pr.finish(C)


def top_hit(x, y):
    o, d = TOP.ray(TOP.to_screen(Vector((x, y, 0))))
    ok, loc, _n, _f = p.ray_cast(o, d)
    return round(loc.z, 3) if ok else None


check('use_loops: an outline with a hole is the stamp (2 outlines, 120 px wide = Size 60); pressed: a ring-shaped '
      'pocket - the middle stays standing, a closed solid',
      ok3 and st.drawn and len(loops3) == 2 and abs(st.size - 60.0) < 1e-6 and top_hit(0, 0) == 1.0
      and top_hit(0.42, 0) == 0.7 and top_hit(0.8, 0) == 1.0 and non_manifold(p) == 0,
      (why3, len(loops3), st.size, top_hit(0, 0), top_hit(0.42, 0), top_hit(0.8, 0)))

fresh()
C.scene.mch_brush.sketch_first = True
st = C.scene.mch_press
m1 = lasso_sketch.add(C, 'PRESS', [ring_out], TOP)
m2 = lasso_sketch.add(C, 'PRESS', [ring_in], TOP, subtract=True)
m3 = lasso_sketch.commit(C)
loops4 = pc.stamp_loops(C, (cx, cy), st)
check('Press Cut Sketch: Shift + draw adds, Shift + Alt + draw subtracts, Enter makes the combined outline (a square '
      'with a square hole) the stamp; the sketch is cleared',
      lasso_sketch.enabled(C, 'PRESS') and 'Enter: the stamp' in m1 and st.drawn and len(loops4) == 2
      and lasso_sketch.data(C.scene) is None and 'stamp' in m3, (m1[:60], m3, len(loops4)))

ws = C.window_manager
import types
ctx_tool = types.SimpleNamespace(scene=C.scene, workspace=C.workspace)
groups3 = None
try:
    orig = top_bar.ts.effective_tool
    top_bar.ts.effective_tool = lambda _c: 'PRESS'
    import mecha_lab.mecha_menu as mm
    groups3 = dict((g[0], g[1]) for g in top_bar.groups(C, 'PRESS'))
finally:
    top_bar.ts.effective_tool = orig
labels = [c['label'] for c in groups3.get('Shift+Draw', [])]
drawc = [c['label'] for c in groups3.get('Draw', [])]
check('... the top bar in Press Cut: the shapes to draw with (Lasso, Curve Lasso, Rectangle, Circle, Ellipse, Free '
      'Draw - no PNG stamp) and Sketch; Press Cut keeps its own lasso settings (like the other drawing tools)',
      labels == ['Lasso', 'Curve Lasso', 'Rectangle', 'Circle', 'Ellipse', 'Free Draw'] and 'Sketch' in drawc
      and 'PRESS' in ts.DRAW_TOOLS, (labels, drawc))



# 0.24.95 (user: "메쉬 위에 뜨는 점이 너무 작은데") bigger contact dots, a Dot Size setting
st = C.scene.mch_press
base = pc.dot_sizes(C)
st.dot_size = 2.0
big = pc.dot_sizes(C)
st.dot_size = 1.0
check('Contact dots: about twice the first ones (outline 8 px, the press point 18 px at UI scale 1), the Dot Size '
      'setting scales them (never 0 - no window reads UI scale 0)', base[0] >= 8.0 - 1e-6 and base[1] >= 16.0
      and abs(big[0] - 2 * base[0]) < 1e-6, (base, big))


# 0.24.95 (user: "스탬프 돌리는 것도 로테이션 각도가 좀 더 섬세하게") R + mouse turns the stamp finely
ta = pc.turn_angle
deg = math.degrees
check('Stamp turn (R + mouse): 0.4 degree a pixel (25 px = 10 degrees), Shift fine (25 px = 2 degrees), Ctrl in 5 degree '
      'steps, kept in -180 .. 180 (it was 15 degree steps only)',
      abs(deg(ta(0.0, 25)) - 10.0) < 1e-6 and abs(deg(ta(0.0, 25, shift=True)) - 2.0) < 1e-6
      and abs(deg(ta(0.0, 31, ctrl=True)) - 10.0) < 1e-6 and abs(deg(ta(0.0, 3)) - 1.2) < 1e-6
      and abs(deg(ta(math.radians(170), 50)) + 170.0) < 1e-6,
      [round(deg(x), 3) for x in (ta(0.0, 25), ta(0.0, 25, shift=True), ta(0.0, 31, ctrl=True), ta(0.0, 3),
                                  ta(math.radians(170), 50))])
press_keys = [(k[0], k[1]['type'], k[1].get('shift', False)) for k in pc.TOOL_KEYMAP]
from mecha_lab import workspace_ui as wu  # noqa: E402
cut_keys = [(k[0], k[1]['type'], k[1].get('shift', False)) for k in wu._tool_keymap('CUT')]
check('... R / Shift + R (turn / back to 0) in Press Cut and in the Cut tool (Custom stamp)',
      ('mch.stamp_turn', 'R', False) in press_keys and ('mch.stamp_turn', 'R', True) in press_keys
      and ('mch.stamp_turn', 'R', False) in cut_keys and ('mch.stamp_turn', 'R', True) in cut_keys)
C.scene.mch_brush.shape = 'LASSO'
tgt_lasso = pc.turn_target(C)
C.scene.mch_brush.shape = 'CUSTOM'
tgt_custom = pc.turn_target(C)
check('... R turns only a stamp (a lasso shape leaves R to Blender); the Custom stamp of Cut / Split turns its own '
      'rotation', tgt_lasso is None and tgt_custom is not None and tgt_custom[1] == 'custom_rotation')
C.scene.mch_brush.shape = 'LASSO'
summary()
