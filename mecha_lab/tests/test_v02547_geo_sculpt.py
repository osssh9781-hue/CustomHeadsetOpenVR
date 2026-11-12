"""0.24.142 Geo Sculpt (user: "다이나 메쉬 안 한 메쉬에서 지오메트리 노드로 그런 척하게 해 달라구" / "이런 지오메트리 스컬핑은 한 창으로
묶어서 만들고 ... 지브러시 창처럼 S 눌러서 브러시 크기 조정" / "플랫은 알트 누르면 튀어나와야 되고" / "내가 그은 만큼만 적용되게" /
"라인을 좀 더 충실히 따라 줘" / "패널은 패널라인 브러시로 만들어 주라"):
one tool, its brushes in one window; every brush through the module on plain parts, measured on the evaluated mesh;
the part's own mesh untouched until Apply."""
import math
import os

import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from _harness import bpy, bmesh, check, fresh, summary

import mecha_lab
from mecha_lab import geo_sculpt as gs, tool_state as ts, ui_tool_settings as uts, key_legend as kl  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene

# --- 1. one tool, in the list, its window, its keys ---------------------------------------------------------------
row = ts.TOOL_BY_ID.get('GSCULPT')
icon = os.path.join(os.path.dirname(gs.__file__), 'icons', 'geo_sculpt.png')
check('Geo Sculpt is one tool in the Mecha Lab list (Surface detail), its own icon, its window in the side panel',
      row is not None and row[5] == 'mecha.geo_sculpt' and ts.NATIVE_TO_TOOL.get('mecha.geo_sculpt') == 'GSCULPT'
      and 'GSCULPT' in dict(ts.TOOL_GROUPS)['Surface detail'] and os.path.isfile(icon) and 'GSCULPT' in uts.DRAWERS
      and 'GSCULPT' in kl.EXTRA)
keys = {(k[1]['type'], k[1].get('alt', False), k[1].get('shift', False)): (k[0], dict(k[2]['properties']) if k[2] else {})
        for k in gs.MCH_TOOL_geo_sculpt.bl_keymap}
check('the tool\'s keys: LMB / Alt+LMB / Shift+LMB = a stroke, S = Draw Size and U = Intensity at the cursor (ZBrush), '
      'F = Draw Size too, Esc leaves the tool',
      keys[('LEFTMOUSE', False, False)][0] == keys[('LEFTMOUSE', True, False)][0] == keys[('LEFTMOUSE', False, True)][0]
      == 'mch.geo_stroke' and keys[('S', False, False)] == ('mch.geo_size', {'target': 'SIZE'})
      and keys[('U', False, False)] == ('mch.geo_size', {'target': 'INTENSITY'})
      and keys[('F', False, False)][0] == 'mch.geo_size' and keys[('ESC', False, False)][0] == 'mch.exit_tool', keys)
check('the brushes: Standard, Clay, Clay Buildup, Flat, Move, Smooth, Edge Line, Panel Line, Chamfer, Round - all in the '
      'window\'s rows', [b[0] for b in gs.BRUSHES] == ['STANDARD', 'CLAY', 'BUILDUP', 'FLAT', 'MOVE', 'SMOOTH', 'EDGE',
                                                       'PANEL', 'CHAMFER', 'ROUND']
      and sorted(sum(gs.BRUSH_ROWS, ())) == sorted(b[0] for b in gs.BRUSHES))


class _Rec:
    def __init__(self, log):
        self.log = log

    def column(self, **_k):
        return self

    def row(self, **_k):
        return self

    def label(self, text='', **_k):
        self.log.append(('label', text))

    def prop(self, data, prop, text=None, **_k):
        self.log.append(('prop', prop, text))

    def prop_enum(self, data, prop, value, **_k):
        self.log.append(('enum', value))

    def operator(self, idname, text='', **_k):
        self.log.append(('op', idname))
        return type('P', (), {})()


# --- 2. a plain low-poly part: strokes live in the layer, the mesh is not touched ---------------------------------
def box(name, loc=(0, 0, 0), bevel=0.1):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    if bevel:
        bmesh.ops.bevel(bm, geom=list(bm.verts) + list(bm.edges), offset=bevel, segments=1, affect='EDGES',
                        profile=0.5, clamp_overlap=True)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    S.collection.objects.link(ob)
    ob.location = loc
    return ob


def height(ob, x, y, top=5.0):
    """z of the evaluated part under (x, y) (local), from above."""
    dg = C.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(ob, dg)
    loc = bvh.ray_cast(Vector((x, y, top)), Vector((0, 0, -1)))[0]
    return None if loc is None else loc.z


def front(ob, x, z):
    """How far the evaluated part's front face (-Y) stands out at (x, z): -y of the hit."""
    dg = C.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(ob, dg)
    loc = bvh.ray_cast(Vector((x, -5.0, z)), Vector((0, 1, 0)))[0]
    return None if loc is None else -loc.y


def seg(p0, p1, n=16):
    return [tuple(np.array(p0) + (np.array(p1) - np.array(p0)) * j / (n - 1)) for j in range(n)]


up, fr = (0, 0, 1), (0, -1, 0)
A = box('Part')
base_co = np.array([v.co[:] for v in A.data.vertices])
base_faces = len(A.data.polygons)
gs.add_stroke(A, 'STANDARD', [(0.0, -0.4, 1.0)], [up], 0.3, 1.0)
mod = gs.layer(A)
sob = gs.strokes_of(A)
dg = C.evaluated_depsgraph_get()
ev_faces = len(A.evaluated_get(dg).data.polygons)
check('a stroke: the part gets its "MCH Geo Sculpt" layer reading its own stroke mesh (not in the scene); the region near '
      'the stroke is subdivided; the part\'s own mesh is exactly as it was',
      mod is not None and mod.node_group.name == gs.GROUP and sob is not None and sob.get(gs.PART_KEY) == A.name
      and not sob.users_collection and ev_faces > base_faces * 20 and len(A.data.polygons) == base_faces
      and np.allclose(np.array([v.co[:] for v in A.data.vertices]), base_co), (ev_faces, base_faces))
h0 = 1.0
hs = height(A, 0.0, -0.4)
far = height(A, 0.0, 0.7)
check('Standard: a bump on the stroke (up along the normal), nothing far from it', hs > h0 + 0.05 and abs(far - h0) < 1e-4,
      (hs, far))
# Alt: a dent
gs.undo_last(A)
gs.add_stroke(A, 'STANDARD', [(0.0, -0.4, 1.0)], [up], 0.3, -1.0)
check('Alt (negative strength): a dent instead', height(A, 0.0, -0.4) < h0 - 0.05, height(A, 0.0, -0.4))
gs.undo_last(A)
# Clay: a flat-topped band
gs.add_stroke(A, 'CLAY', seg((-0.5, -0.4, 1.0), (0.5, -0.4, 1.0)), [up] * 16, 0.2, 1.0)
hc = [height(A, x, -0.4) for x in (-0.2, 0.0, 0.2)]
check('Clay: a raised band, its top even along the stroke', min(hc) > h0 + 0.02 and max(hc) - min(hc) < 0.01, hc)
gs.undo_last(A)
# Clay Buildup: strokes fill up to a plane (a second stroke over the first does not double it)
gs.add_stroke(A, 'BUILDUP', seg((-0.5, -0.4, 1.0), (0.5, -0.4, 1.0)), [up] * 16, 0.2, 1.0)
b1 = height(A, 0.0, -0.4)
gs.add_stroke(A, 'BUILDUP', seg((-0.5, -0.4, b1), (0.5, -0.4, b1)), [up] * 16, 0.2, 1.0)
b2 = height(A, 0.0, -0.4)
check('Clay Buildup: filled up to a plane over the stroke, the next stroke builds on it by the same step (flat layers)',
      b1 > h0 + 0.05 and abs((b2 - b1) - (b1 - h0)) < 0.02, (b1, b2))
gs.undo_last(A)
gs.undo_last(A)
# Flat: a hill pressed to the stroke's plane;  Flat + Alt: a flat pad pops out
gs.add_stroke(A, 'STANDARD', [(0.0, -0.4, 1.0)], [up], 0.35, 1.4)
hill = height(A, 0.0, -0.4)
gs.add_stroke(A, 'FLAT', seg((-0.25, -0.4, 1.08), (0.25, -0.4, 1.08), 8), [up] * 8, 0.3, 1.0)
pressed = height(A, 0.0, -0.4)
check('Flat: a hill pressed down to the stroke\'s plane', hill > 1.2 and abs(pressed - 1.08) < 0.02, (hill, pressed))
gs.undo_last(A)
gs.undo_last(A)
gs.add_stroke(A, 'FLAT', seg((-0.3, 0.3, 1.0), (0.3, 0.3, 1.0), 10), [up] * 10, 0.3, -1.0)
pad = [height(A, x, 0.3) for x in (-0.2, 0.0, 0.2)]
check('Flat + Alt: a flat pad pops out (raised, its top level)', min(pad) > h0 + 0.05 and max(pad) - min(pad) < 0.01, pad)
gs.undo_last(A)
# Move: the grab point dragged
gs.add_stroke(A, 'MOVE', [(0.5, 0.5, 1.0)], [up], 0.3, 1.0, (0.0, 0.0, 0.3))
check('Move: the surface at the grab point goes the drag\'s way (up 0.3)', abs(height(A, 0.5, 0.5) - 1.3) < 0.03,
      height(A, 0.5, 0.5))
gs.undo_last(A)
# Smooth: a bump smoothed lower
gs.add_stroke(A, 'STANDARD', [(0.0, -0.4, 1.0)], [up], 0.2, 1.0)
bump = height(A, 0.0, -0.4)
gs.add_stroke(A, 'SMOOTH', [(0.0, -0.4, bump)], [up], 0.3, 1.0)
check('Smooth: the bump comes down', height(A, 0.0, -0.4) < bump - 0.01, (bump, height(A, 0.0, -0.4)))
gs.undo_last(A)
gs.undo_last(A)
check('Undo Last / no strokes: the part evaluates exactly as its mesh again (nothing left of them)',
      gs.stroke_count(A) == 0 and abs(height(A, 0.0, -0.4) - 1.0) < 1e-4)
# --- 3. Edge Line / Panel Line on a curved part: only as far as drawn, on the line --------------------------------
me = bpy.data.meshes.new('Pod')
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=4, radius=1.0)
for v in bm.verts:
    v.co.x *= 1.3
    v.co.z *= 0.8
bm.to_mesh(me)
bm.free()
me.shade_smooth()
P = bpy.data.objects.new('Pod', me)
S.collection.objects.link(P)
bvh0 = BVHTree.FromObject(P, C.evaluated_depsgraph_get())


def on_pod(xs, y):
    pts, ns = [], []
    for x in xs:
        loc, n, _i, _d = bvh0.ray_cast(Vector((x, y, 3)), Vector((0, 0, -1)))
        pts.append(tuple(loc))
        ns.append(tuple(n))
    return pts, ns


def pod_z(x, y):
    return height(P, x, y)


z_line0, z_side0, z_end0 = (bvh0.ray_cast(Vector((x, y, 3)), Vector((0, 0, -1)))[0].z
                            for x, y in ((0.0, -0.45), (0.0, -0.33), (-0.9, -0.45)))
pts, ns = on_pod(np.linspace(-0.6, 0.6, 40), -0.45)
gs.add_stroke(P, 'EDGE', pts, ns, 0.3, 0.6)
check('Edge Line: the line becomes a ridge edge (up), the flank beside it flattened (under the curve), and nothing past '
      'the line\'s end (only as far as drawn)',
      pod_z(0.0, -0.45) > z_line0 + 0.02 and abs(pod_z(-0.9, -0.45) - z_end0) < 1e-3,
      (pod_z(0.0, -0.45) - z_line0, pod_z(0.0, -0.33) - z_side0, pod_z(-0.9, -0.45) - z_end0))
# the crease follows the line: across the line the surface slope jumps right at the line (not a grid step away)
ys = np.linspace(-0.6, -0.3, 61)
zs = np.array([pod_z(0.0, y) for y in ys])
slope = np.diff(zs) / np.diff(ys)
jump = np.abs(np.diff(slope))
at = ys[1:-1][int(np.argmax(jump))]
check('Edge Line follows the line: the sharpest bend of the cross-section is on the drawn line (within 0.01)',
      abs(at - (-0.45)) < 0.01, (round(float(at), 4), round(float(jump.max()), 2)))
gs.undo_last(P)
pts, ns = on_pod(np.linspace(-0.6, 0.6, 40), -0.45)
gs.add_stroke(P, 'PANEL', pts, ns, 0.05, 0.6)
floor = pod_z(0.0, -0.45)
check('Panel Line: a groove along the line (down by |k| x r x 0.5), a flat floor, the surface beside the band as it was',
      abs((z_line0 - floor) - 0.6 * 0.05 * 0.5) < 0.006 and abs(pod_z(0.0, -0.45 + 0.01) - floor) < 0.004
      and abs(pod_z(0.0, -0.33) - z_side0) < 2e-3, (z_line0 - floor, pod_z(0.0, -0.44) - floor))
gs.undo_last(P)
gs.add_stroke(P, 'PANEL', pts, ns, 0.05, -0.6)
check('Panel Line + Alt: a raised rib instead', pod_z(0.0, -0.45) > z_line0 + 0.01, pod_z(0.0, -0.45) - z_line0)
gs.undo_last(P)
check('a line is resampled finely and its ends fade to 0 (it stops where it was drawn)',
      len(gs.resample_line(pts, ns, 0.3 * 0.03)[0]) > 100 and gs.fade_along(pts, 0.3)[0] == 0.0
      and gs.fade_along(pts, 0.3)[len(pts) // 2] == 1.0)
# --- 4. Chamfer / Round: the part's hard edges along the stroke, as wide as the brush ------------------------------
K = box('Sharp', (5, 0, 0), bevel=0)
n1 = gs.add_stroke(K, 'CHAMFER', seg((-0.9, -1.0, 1.0), (0.9, -1.0, 1.0)), [up] * 16, 0.2, 1.0)
n2 = gs.add_stroke(K, 'ROUND', seg((1.0, -1.0, -0.9), (1.0, -1.0, 0.9)), [fr] * 16, 0.3, 1.0)
cham, rnd = K.modifiers.get(gs.CHAMFER_MOD), K.modifiers.get(gs.ROUND_MOD)
dg = C.evaluated_depsgraph_get()
check('Chamfer / Round: the one hard edge along each stroke weighted; Bevel modifiers by weight (round: segments), as '
      'wide as the brush; before the sculpt layer', n1 == 1 and n2 == 1 and cham is not None and rnd is not None
      and abs(cham.width - 0.2) < 1e-6 and abs(rnd.width - 0.3) < 1e-6 and cham.segments == 1
      and rnd.segments == gs.ROUND_SEGMENTS and len(K.evaluated_get(dg).data.polygons) > 6, (n1, n2))
gs.add_stroke(K, 'CHAMFER', seg((-0.9, -0.95, 1.0), (0.9, -0.95, 1.0)), [up] * 16, 0.2, -1.0)
check('Alt along the chamfered edge: taken off (no chamfer modifier left), the round stays',
      K.modifiers.get(gs.CHAMFER_MOD) is None and K.modifiers.get(gs.ROUND_MOD) is not None)
check('a stroke across the box face (no edge along it): nothing marked',
      gs.mark_bevel(K, 'CHAMFER', seg((-0.5, -0.5, 1.0), (0.5, 0.5, 1.0)), 0.1) == 0)
# --- 5. Apply / Clear -------------------------------------------------------------------------------------------------
gs.add_stroke(A, 'CLAY', seg((-0.5, -0.4, 1.0), (0.5, -0.4, 1.0)), [up] * 16, 0.2, 1.0)
want = height(A, 0.0, -0.4)
sob_name = gs.strokes_of(A).name
n = gs.apply(C, A)
bm = bmesh.new()
bm.from_mesh(A.data)
open_e = sum(1 for e in bm.edges if not e.is_manifold)
bm.free()
check('Apply: the layer baked into the part (same surface), its stroke mesh gone, the seam welded: the part closed',
      n == 1 and gs.layer(A) is None and bpy.data.objects.get(sob_name) is None and abs(height(A, 0.0, -0.4) - want) < 1e-3
      and open_e == 0 and len(A.data.polygons) > base_faces, (n, open_e, len(A.data.polygons)))
gs.add_stroke(K, 'STANDARD', [(0.0, 0.0, 1.0)], [up], 0.3, 1.0)
gs.clear(K)
check('Clear: every stroke and bevel off (modifiers, weights, the stroke mesh)', not gs.has_any(K)
      and not any(a.name.startswith('mch_geo') for a in K.data.attributes) and len(K.modifiers) == 0)
# --- 6. a duplicate gets its own strokes -------------------------------------------------------------------------
D1 = box('Dup1', (0, 6, 0))
gs.add_stroke(D1, 'STANDARD', [(0.0, 0.0, 1.0)], [up], 0.3, 1.0)
D2 = D1.copy()
D2.data = D1.data.copy()
S.collection.objects.link(D2)
shared = gs.strokes_of(D2) == gs.strokes_of(D1)
gs.add_stroke(D2, 'STANDARD', [(0.5, 0.5, 1.0)], [up], 0.3, 1.0)
check('Shift+D copy: it shares its original\'s strokes until its first stroke, then has its own',
      shared and gs.strokes_of(D2) != gs.strokes_of(D1) and gs.stroke_count(D1) == 1 and gs.stroke_count(D2) == 2)
# --- 7. the window, the size popup ----------------------------------------------------------------------------------
C.view_layer.objects.active = D1
rec = []
gs.draw(_Rec(rec), C)
check('the window: every brush, Draw Size (S), Intensity (U), Detail of the active part, Undo Last / Clear / Apply',
      [e[1] for e in rec if e[0] == 'enum'] == list(sum(gs.BRUSH_ROWS, ()))
      and ('prop', 'size_px', 'Draw Size  (S)') in rec and ('prop', 'intensity', 'Intensity  (U)') in rec
      and any(e[0] == 'prop' and e[2] == 'Detail' for e in rec)
      and {('op', 'mch.geo_undo_last'), ('op', 'mch.geo_clear'), ('op', 'mch.geo_apply')} <= set(rec), rec)
op = type('Op', (), {})()
op.start, op.x0 = (60, 0.5), 100
op.target = 'SIZE'
grow, shrink = gs.MCH_OT_geo_size.value_for(op, 215), gs.MCH_OT_geo_size.value_for(op, -15)
op.target = 'INTENSITY'
k1 = gs.MCH_OT_geo_size.value_for(op, 150)
check('S at the cursor: right = bigger, left = smaller (like ZBrush\'s Draw Size); U: Intensity the same way',
      grow > 60 * 1.9 and shrink < 60 / 1.9 and abs(k1 - 0.7) < 1e-6, (grow, shrink, k1))
st = gs.settings(C)
st.brush = 'FLAT'
check('the brush setting: Flat picked', st.brush == 'FLAT' and 'FINISHED' in bpy.ops.mch.geo_brush(brush='PANEL')
      and st.brush == 'PANEL')
summary()
