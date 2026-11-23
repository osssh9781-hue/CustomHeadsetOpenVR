"""0.24.298 (user, a hatch photo: "아머 플레이트랑 베이스 메쉬에 윗부분 엣지 부분이랑 아래 바닥면 엣지 부분 몰딩 넣는 옵션"):
Top / Bottom Edge Molding - a band at the top edge (+ a Lip standing up round the top face), a flange at the bottom."""
import math

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import armor_plate as ap, base_mesh as bm_, core_geometry as cg

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
p = S.mch_base
sq = [(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]


def build(**kw):
    for k, v in kw.items():
        setattr(p, k, v)
    b = bm_.build_bmesh([(sq, [])], p)
    me = bpy.data.meshes.new('t')
    b.to_mesh(me)
    b.free()
    ob = bpy.data.objects.new('t', me)
    S.collection.objects.link(ob)
    return ob


def xmax_at(ob, z0, z1):
    return max((v.co.x for v in ob.data.vertices if z0 - 1e-6 <= v.co.z <= z1 + 1e-6), default=None)


p.profile = 'FLAT'
p.height = 0.5
ob = build(emold_top=False, emold_bottom=True, emold_out=0.05, emold_band=0.1, emold_shape='SQUARE')
check('Base Mesh Bottom: a flange 0.05 out, 0.1 tall at the bottom; the wall above at 1.0; closed',
      abs(xmax_at(ob, 0.0, 0.1) - 1.05) < 1e-4 and abs(xmax_at(ob, 0.11, 0.5) - 1.0) < 1e-4 and non_manifold(ob) == 0,
      (xmax_at(ob, 0.0, 0.1), xmax_at(ob, 0.11, 0.5)))
ob = build(emold_top=True, emold_bottom=False, emold_lip=0.0)
check('Top (flat band): 0.05 out over the top 0.1, flush with the top (no higher than 0.5); closed',
      abs(xmax_at(ob, 0.4, 0.5) - 1.05) < 1e-4 and abs(xmax_at(ob, 0.0, 0.39) - 1.0) < 1e-4
      and abs(max(v.co.z for v in ob.data.vertices) - 0.5) < 1e-6 and non_manifold(ob) == 0)
ob = build(emold_top=True, emold_bottom=True, emold_lip=0.04)
zs = [v.co.z for v in ob.data.vertices]
inner_top = [v.co for v in ob.data.vertices if abs(v.co.z - 0.5) < 1e-6]
check('Top with a Lip 0.04 + Bottom: the rim stands 0.04 above the top face, the top face inside it; closed',
      abs(max(zs) - 0.54) < 1e-6 and max(c.x for c in inner_top) < 1.05 and non_manifold(ob) == 0
      and abs(xmax_at(ob, 0.0, 0.1) - 1.05) < 1e-4, (max(zs), max(c.x for c in inner_top)))
for shape in ('CHAMFER', 'ROUND'):
    ob = build(emold_shape=shape)
    check(f'{shape}: closed, 0.05 out', non_manifold(ob) == 0 and abs(max(v.co.x for v in ob.data.vertices) - 1.05) < 1e-3)
p.emold_shape = 'SQUARE'
p.profile = 'BEVEL'
p.bevel_sides = 'BOTH'
p.bevel_width = 0.05
ob = build(emold_top=True, emold_bottom=False, emold_lip=0.0, mold_count=2, mold_thick=0.02)
bot = [v.co for v in ob.data.vertices if abs(v.co.z) < 1e-6]
check('Bevel (both) + Top molding + 2 side bands: the top gets the molding (no bevel there), the bottom still beveled, '
      'closed', non_manifold(ob) == 0 and max(c.x for c in bot) < 0.96 and abs(xmax_at(ob, 0.4, 0.5) - 1.05) < 1e-4,
      (max(c.x for c in bot), xmax_at(ob, 0.4, 0.5)))
p.profile = 'FLAT'
p.mold_count = 0
p.emold_top = p.emold_bottom = False
check('defaults off: Base Mesh as before', not p.bl_rna.properties['emold_top'].default
      and not p.bl_rna.properties['emold_bottom'].default)

# ---- Armor Plate
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
LOOP = [(500 + 55 * math.cos(a), 500 + 55 * math.sin(a)) for a in (2 * math.pi * k / 48 for k in range(48))]
S.mch_plate.preset = 'FLAT'
ap.perform_plate(C, [LOOP], TOP)
part = C.active_object
C.view_layer.update()


def extent():
    me = part.evaluated_get(C.evaluated_depsgraph_get()).to_mesh()
    vs = [part.matrix_world @ v.co for v in me.vertices]
    out = (max(v.x for v in vs), max(v.z for v in vs), min(v.z for v in vs))
    part.evaluated_get(C.evaluated_depsgraph_get()).to_mesh_clear()
    return out


x0, z0, b0 = extent()
pe = part.mch_extract
pe.emold_bottom = True
pe.emold_out = 0.03
C.view_layer.update()
x1, z1, b1 = extent()
check('Armor Plate (live) Bottom: the plate 0.03 wider at the bottom, as tall as before', abs((x1 - x0) - 0.03) < 0.006
      and abs(z1 - z0) < 1e-4, (x0, x1, z0, z1))
pe.emold_top = True
pe.emold_lip = 0.02
C.view_layer.update()
x2, z2, b2 = extent()
check('... Top with a Lip 0.02: the rim 0.02 above the top', abs((z2 - z0) - 0.02) < 0.003, (z0, z2))
pe.emold_top = pe.emold_bottom = False
C.view_layer.update()
x3, z3, b3 = extent()
check('... both off: the plate as it was', abs(x3 - x0) < 1e-5 and abs(z3 - z0) < 1e-5)
check('Armor Plate defaults off', not S.mch_extract.emold_top and not S.mch_extract.emold_bottom)
# (user: "그룹 내부로 들어가면 다른 오브젝트들이 다 에딧 모드로 바뀌어서 렉") entering a group: the outside parts keep their look
from mecha_lab import groups
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
a = C.active_object
bpy.ops.mesh.primitive_cube_add(location=(3, 0, 0))
b = C.active_object
bpy.ops.mesh.primitive_cube_add(location=(-3, 0, 0))
lone = C.active_object
for o in C.selected_objects:
    o.select_set(False)
a.select_set(True)
b.select_set(True)
C.view_layer.objects.active = a
g = groups.create(C, [a, b])
check('Outside Scope default: Normal', bpy.types.Scene.bl_rna.properties['mch_group_scope_display'].default == 'NORMAL')
if g is not None:
    groups.enter_scope(C, g)
    check('entering a group: the outside part keeps its look (no wireframe, no Edit Mode), only not pickable',
          lone.display_type != 'WIRE' and lone.hide_select and C.mode == 'OBJECT', (lone.display_type, C.mode))
    groups.clear_scope(C)
summary()
