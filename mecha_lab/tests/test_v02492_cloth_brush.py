"""0.24.92 Blender's cloth brushes on the ZBrush screen: 8 brushes on the bottom shelf (their own group), the
Cloth Brush box on the left shelf with the brush's own cloth settings, the Cloth Filter buttons."""
import inspect

from _harness import bpy, check, fresh, select_only, summary

import mecha_lab
from mecha_lab import zb_sculpt as zs, zb_ui

mecha_lab.register()
fresh()
C = bpy.context
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=32, ring_count=16)
ob = C.active_object
select_only(ob)
bpy.ops.object.mode_set(mode='SCULPT')
check('8 cloth brushes in the ZBrush brush table, their own shelf group, B letters all distinct',
      len(zs.CLOTH_BRUSHES) == 8 and all(z in zs.BY_Z for z in zs.CLOTH_BRUSHES) and zs.SHELF[2] == zs.CLOTH_BRUSHES
      and len({c for _z, _b, c in zs.BRUSHES}) == len(zs.BRUSHES))
ok, bad = [], []
for z in zs.CLOTH_BRUSHES:
    msg = zs.activate(C, z)
    b = zs.brush(C)
    (ok if msg == '' and zs.is_cloth(b) and zs.zb_name(b) == z else bad).append((z, msg, getattr(b, 'name', None)))
check('Every cloth brush activates (Blender Essentials) and is a CLOTH brush under its ZBrush name', not bad, bad)
b = zs.brush(C)
check('A cloth brush keeps its size / strength (no pen pressure on them: pressure would restart the simulation)',
      not b.use_pressure_size and not b.use_pressure_strength)
check('Its settings are the brush\'s own: deform type, sim area, limit, mass, damping, softbody, pin, collision',
      all(hasattr(b, k) for k in ('cloth_deform_type', 'cloth_simulation_area_type', 'cloth_sim_limit', 'cloth_mass',
                                   'cloth_damping', 'cloth_constraint_softbody_strength', 'use_cloth_pin_simulation_boundary',
                                   'use_cloth_collision')))
src = inspect.getsource(zb_ui.draw_tool_shelf)
check('The left shelf has a Cloth Brush box with those settings and the five Cloth Filter buttons',
      'Cloth Brush' in src and all(k in src for k in ("'cloth_deform_type'", "'cloth_simulation_area_type'", "'cloth_sim_limit'",
                                                       "'cloth_mass'", "'cloth_damping'", "'cloth_constraint_softbody_strength'",
                                                       "'use_cloth_pin_simulation_boundary'", "'use_cloth_collision'"))
      and 'mch.zb_cloth_filter' in src and len(zs.CLOTH_FILTERS) == 5)
check('The bottom brush shelf draws the cloth group', 'zs.SHELF[2]' in inspect.getsource(zb_ui.brush_shelf))
check('The Cloth Filter operator exists (Gravity / Inflate / Expand / Pinch / Scale)', hasattr(bpy.types, 'MCH_OT_zb_cloth_filter')
      and {i.identifier for i in bpy.ops.mch.zb_cloth_filter.get_rna_type().properties['kind'].enum_items}
      == {'GRAVITY', 'INFLATE', 'EXPAND', 'PINCH', 'SCALE'})
import os
icons = os.path.join(os.path.dirname(zs.__file__), 'icons')
missing = [bl for z, bl, _c in zs.BRUSHES if z in zs.CLOTH_BRUSHES and not os.path.isfile(os.path.join(icons, zs.icon_stem(bl) + '.png'))]
check('Every cloth brush has its icon (the Essentials preview)', not missing, missing)
zs.activate(C, 'Standard')
check('Back to a normal brush: not a cloth brush', not zs.is_cloth(zs.brush(C)))
bpy.ops.object.mode_set(mode='OBJECT')
summary()
