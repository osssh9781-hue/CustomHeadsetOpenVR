"""0.24.278 (user 9번: "클로스 시뮬 돌리고 스플릿이랑 컷 해서 재질 바꾸려는데 자르면 오류"): a single sheet (a cloth) is cut
as the sheet it is, as before - but without the "not one clean solid ... may be broken" warning its open outline gave
(it is not broken: no edge shared by 3+ faces); "Thin Sheets: Give Thickness" (off by default) gives it 1.5 mm first -
the pieces are clean thin solids.  On the user's 02.fbx cloth (scale 0.056 not applied) and a plain sheet; an open shell
(a helmet) and the monkey are not sheets."""
import math
import os

from _harness import bmesh, bpy, check, fresh, summary
from mathutils import Euler, Quaternion

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion())
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion())
FBX = '/root/.claude/uploads/7e2bc25f-fcd2-5c43-817f-f359a797ad9a/e34d5cf0-02.fbx'


def bad_edges(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n


def three(me):
    """Edges shared by 3+ faces (really broken)."""
    bm = bmesh.new()
    bm.from_mesh(me)
    n = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    bm.free()
    return n


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


def sheet():
    clear()
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=60, y_subdivisions=60, size=36.0)    # (36 x 0.056 = 2 m)
    ob = C.active_object
    ob.scale = (0.056, 0.056, 0.056)
    C.view_layer.update()
    return ob


ob = sheet()
check('a grid sheet is a sheet; a closed cube is not; a sphere with a pin hole is not',
      cg.is_sheet(ob.data) and not cg.is_sheet(bpy.data.meshes.new('x')) and True)
bpy.ops.mesh.primitive_uv_sphere_add(location=(5, 0, 0)); sp_ = C.active_object
bm = bmesh.new(); bm.from_mesh(sp_.data); bm.faces.ensure_lookup_table(); bmesh.ops.delete(bm, geom=[bm.faces[0]], context='FACES'); bm.to_mesh(sp_.data); bm.free()
bpy.ops.mesh.primitive_cube_add(location=(9, 0, 0)); cube = C.active_object
check('a sphere with a pin hole and a cube: not sheets (left alone)', not cg.is_sheet(sp_.data) and not cg.is_sheet(cube.data))
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=(12, 0, 0)); helm = C.active_object
bm = bmesh.new(); bm.from_mesh(helm.data)
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().z < -1e-4], context='FACES'); bm.to_mesh(helm.data); bm.free()
bpy.ops.mesh.primitive_monkey_add(location=(15, 0, 0)); monkey = C.active_object
check('an open shell (a helmet open at the bottom) and the monkey: not sheets - cut as before', not cg.is_sheet(helm.data)
      and not cg.is_sheet(monkey.data))

px = lambda v: 500 + v * 100
LOOP = [ce.rect_loop((px(-0.4), px(-0.3)), (px(0.4), px(0.3)))]
check('the switch is off by default (sheets cut as before)', S.mch_cut.sheet_thick is False)
ob = sheet()
r = ce.perform_closed(C, 'CUT', [ob], LOOP, TOP)
check(f'default Cut on a sheet: cut as a sheet (still flat), nothing broken, no "not one clean solid" warning ({r})',
      ob.dimensions.z < 1e-6 and three(ob.data) == 0 and 'clean solid' not in r and len(ob.data.polygons) < 3600)
ob = sheet()
r = ce.perform_closed(C, 'SPLIT', [ob], LOOP, TOP)
parts = [o for o in S.objects if o.type == 'MESH']
check(f'default Split on a sheet: two sheet pieces, nothing broken, no warning ({r})',
      len(parts) == 2 and all(three(o.data) == 0 for o in parts) and 'clean solid' not in r)
S.mch_cut.sheet_thick = True
ob = sheet()
r = ce.perform_closed(C, 'CUT', [ob], LOOP, TOP)
me = ob.data
check(f'Give Thickness on: Cut - a clean thin solid with the hole (open / broken edges {bad_edges(me)}), 1.5 mm',
      bad_edges(me) == 0 and len(me.polygons) > 0 and abs(ob.dimensions.z - 0.0015) < 3e-4, r)
ob = sheet()
r = ce.perform_closed(C, 'SPLIT', [ob], LOOP, TOP)
parts = [o for o in S.objects if o.type == 'MESH']
check(f'Give Thickness on: Split - two clean pieces ({[bad_edges(o.data) for o in parts]})',
      len(parts) == 2 and all(bad_edges(o.data) == 0 for o in parts), r)
S.mch_cut.sheet_thick = False

if os.path.isfile(FBX):
    clear()
    bpy.ops.import_scene.fbx(filepath=FBX)
    cloth = next(o for o in S.objects if o.type == 'MESH')
    C.view_layer.update()
    d = cloth.dimensions
    flat = min(range(3), key=lambda i: d[i])
    proj = TOP if flat == 2 else FRONT
    mw = cloth.matrix_world
    import numpy as np
    co = np.array([mw @ v.co for v in cloth.data.vertices])
    lo, hi = co.min(0), co.max(0)
    ax = (0, 1) if flat == 2 else (0, 2)
    c0 = (lo + hi) / 2
    hx, hy = (hi[ax[0]] - lo[ax[0]]) * 0.2, (hi[ax[1]] - lo[ax[1]]) * 0.2
    pp = lambda v: 500 + v * 100
    loop = ce.rect_loop((pp(c0[ax[0]] - hx), pp(c0[ax[1]] - hy)), (pp(c0[ax[0]] + hx), pp(c0[ax[1]] + hy)))
    print('FBX', cloth.name, tuple(round(x, 3) for x in d), 'scale', tuple(round(x, 3) for x in cloth.scale),
          'sheet', cg.is_sheet(cloth.data), len(cloth.data.polygons))
    r = ce.perform_closed(C, 'SPLIT', [cloth], [loop], proj)
    parts = [o for o in S.objects if o.type == 'MESH']
    check(f'the user 02.fbx cloth, default Split: sheet pieces, nothing broken, no warning ({len(parts)}: {r})',
          len(parts) == 2 and all(three(o.data) == 0 for o in parts) and 'clean solid' not in r)
    clear(); bpy.ops.import_scene.fbx(filepath=FBX); cloth = next(o for o in S.objects if o.type == 'MESH')
    S.mch_cut.sheet_thick = True
    r = ce.perform_closed(C, 'SPLIT', [cloth], [loop], proj)
    parts = [o for o in S.objects if o.type == 'MESH']
    check(f'... Give Thickness on: clean thin solid pieces ({[bad_edges(o.data) for o in parts]})',
          len(parts) == 2 and all(bad_edges(o.data) == 0 for o in parts), r)
    S.mch_cut.sheet_thick = False
else:
    print('02.fbx not here: skipped')
summary()
