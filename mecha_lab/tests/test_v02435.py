"""0.24.31: 5.0 build - Cape kept, the new cloth tools (Clothing / Hood / Scarf / Quad Cloth) hidden, code kept."""
from _harness import bpy, check, summary
import mecha_lab
from mecha_lab import tool_state as ts, workspace_ui as wui
mecha_lab.register()

vis = {t[0] for t in ts.VISIBLE_TOOLS}
check('EXPERIMENTAL_CLOTH is off in this build', ts.EXPERIMENTAL_CLOTH is False)
check('Clothing / Hood / Scarf not in the visible tool list', not (vis & {'GARMENT', 'HOOD', 'SCARF'}), sorted(vis))
check('Cape and Creature Hair still visible', {'CAPE', 'HAIR'} <= vis)
check('hidden tools stay in the enum (saved files keep their tool)',
      {'GARMENT', 'HOOD', 'SCARF'} <= {i[0] for i in ts.TOOL_ENUM_ITEMS})
check('Quad Cloth panel not registered', not hasattr(bpy.types, 'MCH_PT_quad_cloth')
      and not hasattr(bpy.types.Scene, 'mch_quad_cloth'))
check('hood / scarf / clothing operators kept (old live objects can still be applied)',
      all(hasattr(bpy.ops.mch, n) for n in ('hood_apply', 'scarf_apply', 'clothing_apply')))
check('Cape apply operator present', hasattr(bpy.ops.mch, 'cape_apply'))
check('Concept Move operator present', hasattr(bpy.ops.mch, 'concept_move'))
try:
    mecha_lab.unregister()
    ok = True
except Exception as e:          # noqa: BLE001
    ok = repr(e)
check('unregister works with the hidden tools never registered', ok is True, ok)
mecha_lab.register()
summary()
