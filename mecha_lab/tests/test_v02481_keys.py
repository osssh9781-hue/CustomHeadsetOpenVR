"""0.24.76 ZBrush screen fixes: X symmetry is the mesh's own Mirror X (Blender 5), Tab in the MECHA LAB tab switches
MECHA LAB <-> ZBRUSH (other tabs keep Blender's Tab), High Poly Mode leaves Deform Only alone (the shading stays),
Quad Remesh / Make Quad take any face count (1 and up)."""
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import quad_field as qf, quad_remesh as qr, zb_highpoly as hp, zb_sculpt as zs

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add()
cube = C.active_object
zb = S.mch_zb

# --- symmetry ------------------------------------------------------------------------------------------------------
cube.data.use_mirror_x = False
zb.sym_x = True
check('X symmetry: turns on the mesh\'s Mirror X (what the strokes use in Blender 5)', cube.data.use_mirror_x and zb.sym_x)
zb.sym_x = False
check('... and off again', not cube.data.use_mirror_x and not zb.sym_x)
cube.data.use_mirror_x = True
check('the switch shows the mesh\'s own setting', zb.sym_x)
check('texture stamps mirror with it', len(zs.stamp_mirrors(C)) == 2, zs.stamp_mirrors(C))
cube.data.use_mirror_x = False
check('... one stamp without it', len(zs.stamp_mirrors(C)) == 1)
check('X key = the symmetry action', any(k[0] == 'X' and k[5].get('action') == 'SYM_X' for k in zs.KEYS))

# --- Tab -----------------------------------------------------------------------------------------------------------
kc = C.window_manager.keyconfigs.addon
tabs = {km.name for km in kc.keymaps for kmi in km.keymap_items if kmi.idname == 'mch.zb_tab' and kmi.type == 'TAB'}
check('Tab: in Object Mode and Sculpt key maps', {'Object Mode', 'Sculpt'} <= tabs, tabs)
check('Tab: not in the MECHA LAB tab -> Blender\'s own Tab (Edit Mode)', not bpy.ops.mch.zb_tab.poll())
real = zs.mecha_tab
zs.mecha_tab = lambda context: True
try:
    check('Tab in the MECHA LAB tab (Object Mode): available', bpy.ops.mch.zb_tab.poll())
    bpy.ops.mch.zb_tab()
    check('... goes to ZBRUSH (Sculpt Mode)', cube.mode == 'SCULPT', cube.mode)
    bpy.ops.mch.zb_tab()
    check('... and Tab again back to MECHA LAB (Object Mode)', cube.mode == 'OBJECT', cube.mode)
finally:
    zs.mecha_tab = real

# --- High Poly Mode keeps the shading ------------------------------------------------------------------------------
check('High Poly Mode: Deform Only is not touched (it hid Smooth by Angle: flat parts looked smooth)',
      'use_deform_only' not in hp.SCULPT and 'use_sculpt_delay_updates' in hp.SCULPT)

# --- any face count ------------------------------------------------------------------------------------------------
check('Make Quad Faces: down to 1', S.mch_quadremesh.bl_rna.properties['faces'].hard_min == 1)
check('Quad Remesh Target: down to 0.001 (= 1 face)', zb.bl_rna.properties['qr_target'].hard_min <= 0.001 + 1e-9)
S.mch_quadremesh.faces = 37
check('... a Faces value under 100 stays as typed', S.mch_quadremesh.faces == 37, S.mch_quadremesh.faces)
for n in (12, 37):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add()
    ob = C.active_object
    msg = qf.remesh_object(ob, n)
    check(f'Quad Remesh to {n} faces on a box: about that many, closed', 0.5 * n <= len(ob.data.polygons) <= 2.5 * n,
          (len(ob.data.polygons), msg))

summary()
