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
