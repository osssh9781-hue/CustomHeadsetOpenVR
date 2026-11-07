"""0.24.112 Swept lines: Sharp / Round corners and the Line HUD (user: "만든 이후에 두께랑 이런 거 실시간으로 조정할 수 있게",
"꺾이는 부분이 완전 꺾이는 거랑 라운드로 꺾이는 거 옵션으로 ... 그리고 있는 메쉬 옆에 떠 있는 점으로 내가 클릭하면 변하는 걸로").

- fillet_path: a bend becomes an arc tangent to both legs, radius limited by a short leg, tiny turns untouched
- sweep_frames: at a bend the ring is mitred (stretched 1 / cos(turn / 2) across the bend) -> a swept L has its outer
  corner exactly at the mitre point; Round has no such tip and stays closed
- the line's own points stay stations (a corner is not smeared over two samples)
- a live Press line: the corner toggle and the thickness setter rebuild it (and carry into the defaults)
- the Line HUD layout (pure) and its classes; the Line Cut honours the corner setting
"""
import json
import math
import time

from _harness import bmesh, bpy, check, cube, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import base_mesh, core_geometry as cg, line_hud, press_cut as pc

fresh()
mecha_lab.register()
C = bpy.context
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
SPAN = 0.8


def d(a, b):
    return math.dist(a, b)


# --- fillet_path --------------------------------------------------------------------------------------------------
L = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)]
f = base_mesh.fillet_path(L, 0.3)
check('fillet_path: a 90 deg bend becomes an arc of radius 0.3 tangent to both legs (from (0.7, 0) to (1, 0.3), centre (0.7, 0.3))',
      len(f) >= 6 and d(f[1], (0.7, 0, 0)) < 1e-6 and d(f[-2], (1, 0.3, 0)) < 1e-6
      and all(abs(d(q, (0.7, 0.3, 0)) - 0.3) < 1e-6 for q in f[1:-1]) and f[0] == L[0] and f[-1] == L[-1],
      [tuple(round(c, 3) for c in q) for q in f])
f2 = base_mesh.fillet_path([(0.0, 0.0, 0.0), (0.2, 0.0, 0.0), (0.2, 1.0, 0.0)], 0.3)
check('... a short leg limits the arc (45 % of 0.2 = 0.09 each side)', d(f2[1], (0.11, 0, 0)) < 1e-6 and d(f2[-2], (0.2, 0.09, 0)) < 1e-6)
f3 = base_mesh.fillet_path([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.05, 0.0)], 0.3)
check('... a tiny turn (3 deg) is left alone', len(f3) == 3)
f4 = base_mesh.fillet_path([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 1.0)], 0.25)
check('... a 3D bend (x then up z) arcs in its own plane', len(f4) >= 6 and all(abs(q[1]) < 1e-9 for q in f4)
      and all(abs(d(q, (0.75, 0, 0.25)) - 0.25) < 1e-6 for q in f4[1:-1]))

# --- sweep_frames: the mitre ----------------------------------------------------------------------------------------
fr = base_mesh.sweep_frames(L)
U1, V1, M1, k1, _R1 = fr[1]
check('sweep_frames: at the bend T is the bisector, the ring is stretched sqrt(2) along M (in the turn plane, across), straight runs k = 1',
      abs(k1 - 2 ** 0.5) < 1e-6 and M1 is not None and abs(abs(M1.dot(U1)) - 1.0) < 1e-6 and fr[0][3] == 1.0 and fr[0][2] is None
      and fr[2][2] is None, (round(k1, 4), tuple(round(c, 3) for c in M1) if M1 else None))

# --- a swept L, square section 0.2: Sharp has the mitre tip, Round has not -----------------------------------------
SQ = [[(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]]


def sweep(corner, radius=1.0, path=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0))):
    bm = base_mesh._build_sweep_bmesh({'path': [list(q) for q in path], 'loops': SQ},
                                      base_mesh._SweepCutterSettings(0.2, 0.2, 0.0, corner, radius))
    co = [tuple(v.co) for v in bm.verts]
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return co, nm


co, nm = sweep('SHARP')
tip = [q for q in co if d((q[0], q[1]), (1.1, -0.1)) < 1e-4]
check('Sharp: the outer corner of a swept L is the exact mitre point (1.1, -0.1), top and bottom, closed',
      len(tip) == 2 and nm == 0 and max(q[0] - q[1] for q in co) < 1.2 + 1e-4, (len(tip), nm, round(max(q[0] - q[1] for q in co), 4)))
check('... the line\'s own points stay stations: a ring sits exactly at the corner (x = 1 +- 0.1 on the bisector)',
      any(abs(q[0] - 0.9) < 1e-4 and abs(q[1] - 0.1) < 1e-4 for q in co))
co_r, nm_r = sweep('ROUND', 1.0)
check('Round (radius 1 x width = 0.2): no mitre tip, the outer corner pulled in (outer radius 0.3: 1.02 along the diagonal), closed',
      nm_r == 0 and abs(max(q[0] - q[1] for q in co_r) - (0.6 + 0.3 * 2 ** 0.5)) < 0.01
      and not any(d((q[0], q[1]), (1.1, -0.1)) < 1e-3 for q in co_r), (nm_r, round(max(q[0] - q[1] for q in co_r), 4), len(co), len(co_r)))
f5 = base_mesh.fillet_path([(0.0, 0.0, 0.0), (0.3, 0.0, 0.0), (0.3, 0.3, 0.0)], 0.2, min_radius=0.2)
check('... legs too short for the minimum radius (half the section): that bend stays sharp instead of folding', len(f5) == 3)
co_3, nm_3 = sweep('ROUND', 1.0, path=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 1.0)))
check('... a Round bend out of the plane (x then up) is closed too', nm_3 == 0 and len(co_3) > 16)
co_s, nm_s = sweep('SHARP', path=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))
check('a zigzag with two bends: both mitred, closed', nm_s == 0 and sum(1 for q in co_s if d((q[0], q[1]), (1.1, -0.1)) < 1e-4) == 2
      and sum(1 for q in co_s if d((q[0], q[1]), (1.1, 1.1)) < 1e-4) == 2)

# --- a live Press line: the toggle and the thickness setter rebuild it --------------------------------------------
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


def extent(ob, axis):
    co = [ob.matrix_world @ v.co for v in ob.data.vertices]
    return max(q[axis] for q in co) - min(q[axis] for q in co)


fresh()
C = bpy.context
st = C.scene.mch_press
st.size, st.shape, st.rotation, st.result, st.drawn = 40.0, 'MCH_BUILTIN_M_OCTAGON', 0.0, 'CUT', False
C.scene.mch_settings.auto_apply = True
C.scene.mch_base.line_corner, C.scene.mch_base.corner_radius = 'SHARP', 1.0
pc.CONTINUE['base'] = pc.CONTINUE['cut'] = None
p = cube('P', size=2.0)
r, op = stroke(TOP, [(-1.0 + 1.4 * k / 7, -0.6, 1.0) for k in range(8)], True)
ob = C.active_object
r2, op = stroke(TOP, [(0.4, -0.6 + 1.4 * k / 7, 1.0) for k in range(8)], True)      # on from the end: an L (legs 1.4)
check('a Press line drawn as an L (two strokes): one live swept object, Sharp corners by default',
      r == {'FINISHED'} and r2 == {'FINISHED'} and ob == C.active_object and ob.mch_base.line_corner == 'SHARP'
      and len(json.loads(ob[base_mesh.SWEEP_KEY])['path']) >= 3 and non_manifold(ob) == 0)
n_sharp = len(ob.data.vertices)
mode = line_hud.toggle_corner(ob)
check('the HUD dot: toggle -> Round, the live line rebuilt at once (more rings), closed; the Base Mesh defaults carry it',
      mode == 'ROUND' and ob.mch_base.line_corner == 'ROUND' and len(ob.data.vertices) > n_sharp and non_manifold(ob) == 0
      and C.scene.mch_base.line_corner == 'ROUND', (mode, n_sharp, len(ob.data.vertices)))
r0 = ob.mch_base.corner_radius
co_big = [tuple(v.co) for v in ob.data.vertices]
ob.mch_base.corner_radius = 0.6
co_small = [tuple(v.co) for v in ob.data.vertices]
check('... the radius slider: a smaller radius (0.6 x) rebuilds closed with a tighter bend (different mesh)',
      non_manifold(ob) == 0 and len(co_small) > n_sharp and co_small != co_big)
ob.mch_base.corner_radius = 0.3
check('... under half the section (0.3 x): 0.24.114 it still rounds - the inner side creased, closed', non_manifold(ob) == 0
      and len(ob.data.vertices) > n_sharp)
ob.mch_base.corner_radius = r0
mode = line_hud.toggle_corner(ob)
check('... toggle again -> Sharp, back to the mitred mesh', mode == 'SHARP' and len(ob.data.vertices) == n_sharp)
ex0, w0, h0 = extent(ob, 0), ob.mch_base.section_width, ob.mch_base.height
line_hud.set_thickness(ob, w0 * 1.5)
check('the thickness slider: width x1.5 and the height with it (the stamp in proportion), the mesh wider at once',
      abs(ob.mch_base.section_width - w0 * 1.5) < 1e-6 and abs(ob.mch_base.height - h0 * 1.5) < 1e-6
      and extent(ob, 0) > ex0 + 0.15 and non_manifold(ob) == 0, (round(w0, 3), round(ob.mch_base.section_width, 3), round(ex0, 3), round(extent(ob, 0), 3)))
line_hud.set_thickness(ob, w0, (ob.mch_base.section_width, ob.mch_base.height))
check('... and back', abs(ob.mch_base.section_width - w0) < 1e-6 and abs(ob.mch_base.height - h0) < 1e-6 and abs(extent(ob, 0) - ex0) < 1e-3)
C.scene.mch_base.line_corner = 'SHARP'

# --- the Line Cut honours the corner setting -----------------------------------------------------------------------
def vol(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    v = bm.calc_volume()
    bm.free()
    return v


removed = {}
for corner in ('SHARP', 'ROUND'):
    fresh()
    C = bpy.context
    st = C.scene.mch_press
    st.size, st.shape, st.rotation, st.result, st.drawn, st.max_depth = 40.0, 'MCH_BUILTIN_M_OCTAGON', 0.0, 'CUT', False, 0.15
    C.scene.mch_settings.auto_apply = True
    C.scene.mch_base.line_corner, C.scene.mch_base.corner_radius = corner, 1.0
    pc.CONTINUE['base'] = pc.CONTINUE['cut'] = None
    q = cube('Q', size=2.0)
    v0 = vol(q)
    r, op = stroke(TOP, [(-0.9 + 1.2 * k / 8, -0.5, 1.0) for k in range(9)], False)
    r2, op = stroke(TOP, [(0.3, -0.5 + 1.4 * k / 8, 1.0) for k in range(8)], False)      # on from the groove's end: an L
    removed[corner] = v0 - vol(q)
    check(f'Line Cut with {corner} corners: an L groove (two strokes), closed', r == {'FINISHED'} and r2 == {'FINISHED'}
          and removed[corner] > 0.05 and non_manifold(q) == 0, (r, r2, round(removed[corner], 3)))
check('... Round takes less out at the bend than Sharp (the mitre tip is rounded off)', removed['SHARP'] - removed['ROUND'] > 0.005,
      (round(removed['SHARP'], 4), round(removed['ROUND'], 4)))
C.scene.mch_base.line_corner = 'SHARP'

# --- the HUD ---------------------------------------------------------------------------------------------------------
lay = line_hud.hud_layout((500.0, 500.0), 1000.0, 1000.0)
check('hud_layout: the dot right of the line\'s end, the thickness slider right of the dot; no radius slider when Sharp',
      lay['corner'][0] > 500 + line_hud.BTN and lay['thick'][0] > lay['corner'][0] + line_hud.BTN and 'radius' not in lay, lay)
lay_r = line_hud.hud_layout((500.0, 500.0), 1000.0, 1000.0, round_on=True)
check('... Round: the radius slider under the thickness one', 'radius' in lay_r and lay_r['radius'][1] < lay_r['thick'][1]
      and abs(lay_r['radius'][0] - lay_r['thick'][0]) < 1e-9)
lay_e = line_hud.hud_layout((990.0, 500.0), 1000.0, 1000.0)
check('... near the right edge it moves left of the end and stays inside the region', lay_e['thick'][0] + line_hud.SLIDER_W / 2 <= 1000
      and lay_e['corner'][0] < 990, lay_e)
check('the HUD is registered (the dot\'s operator; the gizmo group and slider classes carry their ids)',
      hasattr(bpy.ops.mch, 'line_corner_toggle') and line_hud.MCH_GGT_line_hud.bl_idname == 'MCH_GGT_line_hud'
      and line_hud.MCH_GT_line_slider.bl_idname == 'MCH_GT_line_slider' and 'MCH_GT_line_slider' in str(line_hud.CLASSES))
check('settings: line_corner / corner_radius exist, default Sharp / 1.0, copied to live parts and carried back',
      C.scene.mch_base.bl_rna.properties['line_corner'].default == 'SHARP'
      and abs(C.scene.mch_base.bl_rna.properties['corner_radius'].default - 1.0) < 1e-9
      and 'line_corner' in base_mesh.SETTING_KEYS and 'corner_radius' in base_mesh.CARRY_KEYS)
src_pc, src_b, src_i = open(pc.__file__).read(), open(base_mesh.__file__).read(), open(mecha_lab.__file__).read()
check('wired: the sweep fillets Round paths and mitres rings; the Press sidebar and the cutter use the corner setting; the HUD is registered',
      "path = fillet_path(path, float(getattr(p, 'corner_radius', 1.0))" in src_b and 'off += M * (off.dot(M) * (kk - 1.0))' in src_b
      and "row.prop(base, 'line_corner', expand=True)" in src_pc and "corner=getattr(bsd, 'line_corner', 'SHARP')" in src_pc
      and 'line_hud.register()' in src_i and "row.prop(p, 'line_corner', expand=True)" in open(mecha_lab.ui_tool_settings.__file__).read())
summary()
