"""Regression for v0.5.9 features kept in 0.7.0 (headless, operators via bpy.ops).

Covers the 'apply' entry points that failed on shared meshes in v0.5.9 and
smoke-tests that the remaining tools still execute in Blender 5.0.
Interactive drawing operators (mch.draw_path) are modal and NOT run here.
"""
import math
import sys

from _harness import bpy, check, cube, cylinder, fresh, non_manifold, select_only, summary, volume

import mecha_lab

C = bpy.context


def call(op, **kw):
    try:
        return op(**kw)
    except RuntimeError as ex:
        print('  (operator reported)', str(ex).splitlines()[0])
        return {'CANCELLED'}


mecha_lab.register()

# Mirror create + apply on an Alt+D shared mesh
fresh()
t = cube('M', loc=(2, 0, 0))
twin = t.copy()
twin.location = (0, 5, 0)
C.scene.collection.objects.link(twin)
select_only(t)
check('mirror create', call(bpy.ops.mch.mesh_mirror) == {'FINISHED'})
r = call(bpy.ops.mch.mesh_mirror_apply)
check('mirror apply on shared mesh works', r == {'FINISHED'} and not t.modifiers, r)
check('mirror apply doubled geometry, twin untouched',
      len(t.data.vertices) == 16 and len(twin.data.vertices) == 8, (len(t.data.vertices), len(twin.data.vertices)))
check('world pivot helper removed after apply', not any(o.get('_mch_world_pivot') for o in bpy.data.objects))

# Radial array create / bake and Radial Boolean
fresh()
C.scene.cursor.location = (0, 0, 0)
spoke = cube('Spoke', size=0.2, loc=(1.0, 0, 0))
select_only(spoke)
C.scene.mch_settings.radial_count = 8
check('radial create', call(bpy.ops.mch.radial_create) == {'FINISHED'})
carrier = C.view_layer.objects.active
r = call(bpy.ops.mch.radial_bake)
check('radial bake', r == {'FINISHED'} and len(carrier.data.vertices) == 64, (r, len(carrier.data.vertices)))
fresh()
tire = cylinder('Tire', segments=32, radius=1.2, depth=0.4)
tooth = cube('Tooth', size=0.3, loc=(1.2, 0, 0))
select_only(tooth)
call(bpy.ops.mch.radial_create)
carrier = C.view_layer.objects.active
carrier.mch_radial.boolean_target = tire
r1 = call(bpy.ops.mch.radial_boolean_link)
r2 = call(bpy.ops.mch.radial_boolean_apply)
check('radial boolean link + apply', r1 == {'FINISHED'} and r2 == {'FINISHED'} and volume(tire) < math.pi * 1.44 * 0.4,
      (r1, r2, volume(tire)))
check('radial boolean result manifold', non_manifold(tire) == 0)

# Boolean union / intersect / slice
for op in ('UNION', 'INTERSECT'):
    fresh()
    a = cube('A')
    b = cube('B', loc=(1, 1, 1))
    select_only(a, b)
    r = call(bpy.ops.mch.boolean, operation=op)
    check(f'boolean {op}', r == {'FINISHED'} and non_manifold(a) == 0 and 'B' not in bpy.data.objects, r)
fresh()
a = cube('A')
b = cube('B', loc=(1, 1, 1))
select_only(a, b)
r = call(bpy.ops.mch.slice)
check('slice keeps both pieces', r == {'FINISHED'} and 'A_SlicePiece' in bpy.data.objects and
      abs(volume(a) + volume(bpy.data.objects['A_SlicePiece']) - 8.0) < 1e-4, r)

# Remesh (voxel + smooth)
fresh()
a = cube('A')
select_only(a)
C.scene.mch_settings.voxel_size = 0.2
r = call(bpy.ops.mch.one_click_remesh)
check('one-click remesh applied', r == {'FINISHED'} and not a.modifiers and len(a.data.vertices) > 8, r)

# Mask extract
fresh()
a = cube('A')
select_only(a)
attr = a.data.attributes.new('mch_mask', 'INT', 'FACE')
attr.data[0].value = 1
r = call(bpy.ops.mch.mask_extract)
check('mask extract creates raised object', r == {'FINISHED'} and 'A_RaisedMask' in bpy.data.objects, r)

# Surface conform snap
fresh()
base = cube('Base', size=4.0)
part = cube('Part', size=0.5, loc=(0, 0, 3))
select_only(base, part)
r = call(bpy.ops.mch.surface_conform)
check('surface conform runs', r == {'FINISHED'}, r)

# Old operator ids still resolve (keymaps / scripts from v0.5.9)
for name in ('draw_delete_cut', 'cut_finalize', 'draw_mask', 'stamp_png_cut', 'select_tool', 'boolean',
             'slice', 'smart_fuse', 'surface_cut', 'draw_path', 'bake_live', 'mesh_mirror'):
    check(f'operator mch.{name} registered', hasattr(bpy.types, 'MCH_OT_' + name) or
          name in dir(bpy.ops.mch))

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
