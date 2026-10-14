"""0.18.0 Mirror HUD: Apply / Remove / X Y Z / Bisect / Flip next to the mirrored mesh."""
import sys

from _harness import bpy, check, cube, fresh, non_manifold, select_only, summary

import mecha_lab
from mecha_lab import mirror_hud as mh, mirror_tools as mt

ICONS = set(bpy.types.UILayout.bl_rna.functions['label'].parameters['icon'].enum_items.keys())
check('HUD icons exist in Blender', all(b[1] in ICONS for b in mh.BUTTONS), [b[1] for b in mh.BUTTONS if b[1] not in ICONS])
lay = mh.hud_layout([(400, 300), (600, 500)], 1600, 900)
check('HUD right of the mesh, Apply on top, then Remove, X, Y, Z, Bisect, Flip',
      lay['apply'][0] > 600 and lay['apply'][1] > lay['remove'][1] > lay['x'][1] > lay['z'][1] > lay['flip'][1])
check('HUD stays inside the viewport', mh.hud_layout([(1590, 450)], 1600, 900)['apply'][0] < 1600)

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
ob = cube('Part', 2.0, loc=(2, 0, 0))
select_only(ob)
p = S.mch_mirror
p.space, p.x, p.y, p.z = 'LOCAL', True, False, False
mt.setup_mirror(ob, p, S)
mod = ob.modifiers.get(mt.MOD_NAME)
check('a live Mecha Mirror on the selected mesh', mod is not None and tuple(mod.use_axis) == (True, False, False))
bpy.ops.mch.mirror_hud_option(option='Y')
check('Y button: the live mirror gets Y at once', tuple(mod.use_axis) == (True, True, False))
bpy.ops.mch.mirror_hud_option(option='X')         # X off  -> (F, T, F)
bpy.ops.mch.mirror_hud_option(option='Z')         # Z on   -> (F, T, T)
bpy.ops.mch.mirror_hud_option(option='Y')         # Y off  -> (F, F, T)
check('axes switch on and off', tuple(mod.use_axis) == (False, False, True), tuple(mod.use_axis))
r = bpy.ops.mch.mirror_hud_option(option='Z')
check('the last axis cannot be switched off (Remove does that)', r == {'CANCELLED'} and tuple(mod.use_axis)[2])
b0 = mod.use_bisect_axis[2]
bpy.ops.mch.mirror_hud_option(option='BISECT')
check('Bisect button', mod.use_bisect_axis[2] != b0)
f0 = mod.use_bisect_flip_axis[2]
bpy.ops.mch.mirror_hud_option(option='FLIP')
check('Flip button: copies toward the other side', mod.use_bisect_flip_axis[2] != f0)
check('HUD shows for the mirrored selection (MECHA LAB only)', mt._mirror_targets(C) == [ob])
check('HUD gizmo registered', 'bl_rna' in mh.MCH_GGT_mirror_hud.__dict__)
r = bpy.ops.mch.mesh_mirror_apply()
check('Apply button bakes the mirror', r == {'FINISHED'} and ob.modifiers.get(mt.MOD_NAME) is None and
      len(ob.data.vertices) > 8 and non_manifold(ob) == 0)
mt.setup_mirror(ob, p, S)
r = bpy.ops.mch.mesh_mirror_remove()
check('Remove button drops it, mesh unchanged', r == {'FINISHED'} and ob.modifiers.get(mt.MOD_NAME) is None)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
