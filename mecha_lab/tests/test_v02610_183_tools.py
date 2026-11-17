"""0.24.183 the batch's drawn tools, through their modules (front view, outlines in screen pixels):
* Geo Sculpt Dam Standard (user: "댐스탠다드처럼 내가 그리면 안쪽으로 파지는 것도 ... 가볍게"): a V crease cut along the line,
  Alt: a ridge; nothing added to the part's mesh.
* Creature Base Mesh 2 big forms (user: "크게 형태가 들어간 요철로 바리에이션" / "너무 고밀도야 가벼워야 돼"): the drawn outline
  kept, light (a few thousand faces at most), a flat back; Stick to Surface (user: "누르면 플레이트처럼 안 누르면 베이스
  메쉬처럼"): on a part, lying on its surface.
* Mecha Holes (user: "메카 표면 디테일 홀은 다른 메쉬에 라쏘로 그릴 수 있게"): a holed panel on the part, light.
* Print Cut with a shape (user: "프린트 컷에는 왜 라쏘랑 그런 게 없어"): the part split along the shape, pins across."""
import math
import sys

import numpy as np
from _harness import bpy, bmesh, check, fresh, summary
from mathutils import Euler, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import mecha_lab
from mecha_lab import core_geometry as cg, geo_sculpt as gs, mecha_holes as mh, organic_mass as om, print3d  # noqa

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)


def px(x, z):
    return tuple(FRONT.to_screen(Vector((x, -3.0, z))))


def box(name, loc=(0, 0, 0), size=2.0, cuts=0):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    if cuts:
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    S.collection.objects.link(ob)
    ob.location = loc
    return ob


def ev(ob):
    dg = C.evaluated_depsgraph_get()
    e = ob.evaluated_get(dg)
    me = e.to_mesh()
    V = np.array([e.matrix_world @ v.co for v in me.vertices])
    nf = len(me.polygons)
    e.to_mesh_clear()
    return V, nf


def clear_sel():
    for o in C.selected_objects:
        o.select_set(False)
    C.view_layer.objects.active = None


# --- 1. Dam Standard ---------------------------------------------------------------------------------------------------
check('Dam Standard is a Geo Sculpt brush (a line brush)', 'DAM' in gs.KIND and 'DAM' in gs.LINE_KINDS and
      'DAM' in [b[0] for b in gs.BRUSHES] and 'DAM' in sum(gs.BRUSH_ROWS, ()))
A = box('Dam Part', cuts=24)
nbase = len(A.data.polygons)
up = (0, 0, 1)
line = [tuple(np.array((-0.6, -0.2, 1.0)) + np.array((1.2, 0.0, 0.0)) * j / 39) for j in range(40)]
gs.add_stroke(A, 'DAM', line, [up] * 40, 0.2, 0.6)


def height(ob, x, y):
    dg = C.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(ob, dg)
    loc = bvh.ray_cast(Vector((x, y, 5.0)), Vector((0, 0, -1)))[0]
    return None if loc is None else loc.z


ys = np.linspace(-0.45, 0.05, 101)
zs = np.array([height(A, 0.0, y) for y in ys])
deep = float(zs.min())
at = float(ys[int(np.argmin(zs))])
check(f'a crease cut in along the line: deepest {1.0 - deep:.4f} in, on the line (y {at:+.3f}), the face past the '
      f'brush untouched', 1.0 - deep > 0.02 and abs(at - (-0.2)) < 0.02 and abs(height(A, 0.0, 0.05) - 1.0) < 1e-4,
      (deep, at))
mid = np.argmin(zs)
slope_l = (zs[mid] - zs[mid - 6]) / (ys[mid] - ys[mid - 6])
slope_r = (zs[mid + 6] - zs[mid]) / (ys[mid + 6] - ys[mid])
check(f'... a V (steep walls either side of the bottom: {slope_l:.2f}, {slope_r:.2f})', slope_l < -0.3 and slope_r > 0.3)
check('... the part\'s own mesh untouched (light: the layer only)', len(A.data.polygons) == nbase)
gs.undo_last(A)
gs.add_stroke(A, 'DAM', line, [up] * 40, 0.2, -0.6)
check('Alt: a ridge instead', max(height(A, 0.0, y) for y in (-0.21, -0.2, -0.19)) > 1.02)
gs.undo_last(A)

# --- 2. Creature Base Mesh 2: the big forms -----------------------------------------------------------------------------
outline = [(0.9 * math.cos(a) * (1 + 0.1 * math.sin(3 * a)), 0.6 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 96,
                                                                                                  endpoint=False)]
forms = [k[0] for k in om.KINDS if k[3] == 'FORM']
check('the big forms are the first presets', forms and om.KINDS[0][0] in forms and len(forms) >= 6, forms)
res = {}
for kid in forms:
    S.mch_omass.kind = kid
    S.mch_omass.stick = False
    clear_sel()
    om.perform(C, [[px(20 + x, z) for x, z in outline]], FRONT)
    ob = C.active_object
    V, nf = ev(ob)
    L = np.array(ob.matrix_world.inverted()) @ np.c_[V, np.ones(len(V))].T
    L = L[:3].T
    res[kid] = (nf, float(np.ptp(L[:, 0])), float(np.ptp(L[:, 1])), float(L[:, 2].min()))
    bpy.data.objects.remove(ob)
ok_light = all(r[0] < 6000 for r in res.values())
ok_out = all(abs(r[1] - 1.8) < 0.12 and abs(r[2] - 1.2) < 0.12 for r in res.values())
check(f'every form: light ({min(r[0] for r in res.values())} .. {max(r[0] for r in res.values())} faces) and as wide '
      'and tall as the outline drawn', ok_light and ok_out, res)
# 0.24.190 quick while a slider is dragged (user: "크리쳐 베이스 메쉬는 너무 느려 ... 요철 2 번")
import time as _time  # noqa: E402
S.mch_omass.kind = forms[0]
S.mch_omass.stick = False
clear_sel()
om.perform(C, [[px(40 + x, z) for x, z in outline]], FRONT)
fm = C.active_object
n_full = len(fm.data.polygons)
om._BUSY[0] = True
fm.mch_omass.depth *= 1.2
om._BUSY[0] = False
t0 = _time.perf_counter()
om.build(fm, C, live=True)
t_live = _time.perf_counter() - t0
n_live = len(fm.data.polygons)
t0 = _time.perf_counter()
om.build(fm, C)
t_rest = _time.perf_counter() - t0
check(f'a form while its slider is dragged: quick ({t_live:.2f}s, not merged light yet: {n_live} faces), the full light '
      f'mesh when it rests ({t_rest:.2f}s, {len(fm.data.polygons)} faces)', t_live < t_rest * 0.6 and
      n_live > len(fm.data.polygons) and abs(len(fm.data.polygons) - n_full) < n_full * 0.5, (t_live, t_rest, n_live))
tag = fm.data.vertices[0].co.copy()
fm.data.vertices[0].co.z += 123.0                    # (a mark: gone if the base mesh is made again)
fm.mch_omass.color_a = (0.2, 0.3, 0.4)
fm.mch_omass.r_strength = 0.02
check('a colour / surface slider: the base mesh is not made again (only its surface)',
      abs(fm.data.vertices[0].co.z - tag.z - 123.0) < 1e-4)
fm.mch_omass.depth *= 1.1
check('... a shape slider (Height): made again', abs(fm.data.vertices[0].co.z - tag.z - 123.0) > 1.0)
import os as _os  # noqa: E402
check('the node group comes ready-made from the add-on\'s file (not built: 4 - 5 s the first time before)',
      _os.path.isfile(om.TREE_FILE) and bpy.data.node_groups[om.TREE].get('mch_v') == om.TREE_VERSION and
      len(bpy.data.node_groups[om.TREE].nodes) > 500)
bpy.data.objects.remove(fm)
# Stick to Surface: on a part
P = box('Mass Part', loc=(0.0, 0.0, -10.0), size=3.0, cuts=8)
S.mch_omass.kind = forms[0]
S.mch_omass.stick = True
clear_sel()
om.perform(C, [[px(0.6 * x, -10.0 + 0.6 * z) for x, z in outline]], FRONT)
mob = C.active_object
V, nf = ev(mob)
front_y = -1.5
check(f'Stick to Surface: on the part (its child), lying on its front face (back at y {V[:, 1].max():+.3f}, the '
      f'face at {front_y})', mob.parent == P and abs(V[:, 1].max() - front_y) < 0.03 and V[:, 1].min() < front_y - 0.005,
      (V[:, 1].min(), V[:, 1].max()))
S.mch_omass.stick = False

# --- 3. Mecha Holes ------------------------------------------------------------------------------------------------------
Q = box('Holes Part', loc=(0.0, 0.0, -20.0), size=3.0)
rect = [(-0.8, -20.6), (0.8, -20.6), (0.8, -19.4), (-0.8, -19.4)]
dense = []
for (x0, z0), (x1, z1) in zip(rect, rect[1:] + rect[:1]):
    for j in range(20):
        dense.append(px(x0 + (x1 - x0) * j / 20, z0 + (z1 - z0) * j / 20))
clear_sel()
msg = mh.perform(C, [dense], FRONT)
hp = C.active_object
V, nf = ev(hp)
check(f'Mecha Holes: a panel on the part (its child), on its front face, light ({nf} faces): {msg}',
      mh.is_holes(hp) and hp.parent == Q and nf < 20000 and abs(V[:, 1].max() + 1.5) < 0.03)
dg = C.evaluated_depsgraph_get()
bvh = BVHTree.FromObject(hp, dg)
inv = hp.matrix_world.inverted()                    # (the panel's own space: the BVH is in it)
hits = [bvh.ray_cast(inv @ Vector((x, -5.0, z)), inv.to_3x3() @ Vector((0, 1, 0)))[0]
        for x in np.linspace(-0.5, 0.5, 21) for z in np.linspace(-20.3, -19.7, 13)]
depths = np.array([(hp.matrix_world @ h).y for h in hits if h is not None])
check(f'... holes in it: from the front some rays go deeper (into the holes) than the panel face '
      f'({depths.min():+.3f} .. {depths.max():+.3f})', len(depths) > 100 and np.ptp(depths) > 0.005)

# --- 4. Print Cut with a shape ---------------------------------------------------------------------------------------------
B = box('Print Part', loc=(0.0, 0.0, -30.0), size=2.0)
half = [(0.0, -31.5), (1.5, -31.5), (1.5, -28.5), (0.0, -28.5)]
dense = []
for (x0, z0), (x1, z1) in zip(half, half[1:] + half[:1]):
    for j in range(20):
        dense.append(px(x0 + (x1 - x0) * j / 20, z0 + (z1 - z0) * j / 20))
before = set(bpy.data.objects)
msg = print3d.cut_shape(C, [B], [dense], FRONT)
made = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
pieces = [o for o in made if o.name.startswith('Print Part.')]
check(f'Print Cut, a rectangle over half the part: split in two along it, the original kept hidden ({msg})',
      len(pieces) >= 2 and B.hide_get(), [o.name for o in made])
check('... pins / keys across the cut', 'key' in msg.lower() or 'pin' in msg.lower(), msg)
check('Print Cut is in the Surface-drawing tools (draw along a part like Cloth Plate)',
      'PCUT' in __import__('mecha_lab.surface_lasso', fromlist=['MODES']).MODES)
check('S: the pin size at the cursor (an operator)', hasattr(bpy.ops.mch, 'print_pin_size'))

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
