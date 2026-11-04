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

st = C.scene.mch_press
size = 2.0
d0, d1, d2, dmax = (pc.depth_at(st, size, t) for t in (0.0, 1.0, 2.0, 100.0))
check('Depth = (Start + Speed x seconds) x the part\'s size, up to Max',
      abs(d0 - size * st.start) < 1e-9 and abs(d1 - size * (st.start + st.speed)) < 1e-9 and d2 > d1 > d0
      and abs(dmax - size * st.max_depth) < 1e-9, [round(x, 4) for x in (d0, d1, d2, dmax)])


def held(seconds, result='CUT'):
    """A press held ``seconds`` on a 2 m box, its steps as the tool runs them (one per tick when it grew enough)."""
    fresh()
    C.scene.mch_settings.auto_apply = True
    C.scene.mch_cut.depth_mode, C.scene.mch_cut.depth = 'THROUGH', 0.1
    p = cube('P', size=2.0)
    v0 = vol(p)
    pr = pc.Press(C, p, pc.stamp_loops(C, TOP.to_screen(Vector((0, 0, 1))), st), TOP, result)
    pr.cut_to(C, pc.depth_at(st, pr.size, 0.0))
    t = 0.0
    while t < seconds:
        t += pc.TICK
        d = pc.depth_at(st, pr.size, t)
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
      and abs(runs[2][1] - pc.depth_at(st, 2.0, 1.5)) < 0.05, runs)
check('... the kept copy of the part gone afterwards', not [m for m in bpy.data.meshes
                                                            if m.name.startswith('MCH_PressBackup')])

fresh()
p = cube('P', size=2.0)
n0 = len(p.data.vertices)
pr = pc.Press(C, p, pc.stamp_loops(C, TOP.to_screen(Vector((0, 0, 1))), st), TOP, 'CUT')
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
items = [i[0] for i in pc._shape_items(st, C)]
check('... saved: normalized (centred, the long side 1, its proportions kept), in the Press Cut shape list',
      abs(min(xs) + 0.5) < 1e-6 and abs(max(xs) - 0.5) < 1e-6 and abs((max(ys) - min(ys)) - 70 / 120) < 1e-4
      and stem in items, (round(min(xs), 3), round(max(xs), 3), round(max(ys) - min(ys), 4)))
st.shape = stem
p, pr, v0 = held(0.5)
sx = sorted({round((p.matrix_world @ v.co).x, 3) for v in p.data.vertices if pocket_depth(p) and
             abs((p.matrix_world @ v.co).z - (1 - pr.depth)) < 1e-3})
check('... and pressed with it: the pocket has the saved outline (as wide as the stamp: 2 x Size px)',
      pr.depth > 0 and sx and abs((sx[-1] - sx[0]) - 2 * st.size / 100.0) < 0.02, (round(pr.depth, 4), sx[:1], sx[-1:]))
check('... Press Cut\'s own stamp is not "the last outline" (it stays the drawn one)',
      cut_presets.LAST_LOOPS[0] is kept)
summary()
