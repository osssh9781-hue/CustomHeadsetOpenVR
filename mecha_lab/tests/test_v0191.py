"""0.19.1 High Poly for hand-off: right-click > Make High Poly = dense copies
(support bevel + subdivision, applied, smooth), originals kept / hidden,
Low / High view; the 0.15 floating side tool list removed."""
import math
import os
import sys
import tempfile

from _harness import bpy, check, cube, fresh, non_manifold, select_only, sphere, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import bottom_bar as bb, highpoly as hp

check('support bevel = a fraction of the mesh size', abs(hp.support_width((3, 4, 0), 0.01) - 0.05) < 1e-9)
check('face estimate grows 4x per level', hp.estimate_faces(100, 2) == 4 * hp.estimate_faces(100, 1))
check('huge mesh: level lowered under the limit', hp.safe_level(500_000, 3) < 3 and hp.safe_level(100, 3) == 3)
check('side tool list removed', not hasattr(bb, 'MCH_GGT_side_toolbar'))

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
box = cube('Box', 2.0)
ball = sphere('Ball', loc=(5, 0, 0))
nb, nball = len(box.data.polygons), len(ball.data.polygons)
box.select_set(True)
ball.select_set(True)
C.view_layer.objects.active = box
res = bpy.ops.mch.make_highpoly(level=2)
coll = bpy.data.collections.get('HighPoly')
hps = {o.get('mch_highpoly_src'): o for o in coll.objects} if coll else {}
check('Make High Poly: one dense copy per mesh in "HighPoly"', res == {'FINISHED'} and set(hps) == {'Box', 'Ball'})
hb, hs = hps.get('Box'), hps.get('Ball')
check('originals unchanged and hidden', len(box.data.polygons) == nb and len(ball.data.polygons) == nball and
      box.hide_get() and ball.hide_get())
check('copies are dense plain meshes (modifiers applied), smooth shaded', len(hb.data.polygons) > nb * 16 and
      len(hb.modifiers) == 0 and all(p.use_smooth for p in hb.data.polygons))
check('copies closed', non_manifold(hb) == 0 and non_manifold(hs) == 0)
xs = [abs((hb.matrix_world @ v.co).x) for v in hb.data.vertices]
check('box edges stay crisp: the copy keeps nearly the full size (support loops)', max(xs) > 0.97, max(xs))
flat = sum(1 for v in hb.data.vertices if abs(abs(v.co.z) - 1.0) < 2e-3)
check('box faces stay flat (many verts within 0.1 % of the top/bottom planes)', flat > 50, flat)
r = [((hs.matrix_world @ v.co) - Vector((5, 0, 0))).length for v in hs.data.vertices]
check('curved mesh becomes round: radius varies little', (max(r) - min(r)) / max(r) < 0.08, (min(r), max(r)))
bpy.ops.mch.highpoly_view(show='LOW')
check('Show Low: originals back, copies hidden', not box.hide_get() and hb.hide_get())
bpy.ops.mch.highpoly_view(show='HIGH')
check('Show High: copies back, originals hidden', box.hide_get() and not hb.hide_get())
# again from the originals -> replaces, never duplicates
bpy.ops.mch.highpoly_view(show='LOW')
select_only(box)
bpy.ops.mch.make_highpoly(level=1)
check('Make again: the old copy is replaced', len([o for o in coll.objects if o.get('mch_highpoly_src') == 'Box']) == 1)
check('a high poly copy is never used as a source', not hp._targets(C) or all(not hp.is_highpoly(o) for o in hp._targets(C)))
check('Make High Poly in the right-click menu', any(getattr(f, '__name__', '') == '_context_menu'
                                                   for f in bpy.types.VIEW3D_MT_object_context_menu._dyn_ui_initialize()))
check('no own FBX exporter (Blender File > Export > FBX is used)', not hasattr(hp, 'MCH_OT_export_highpoly_fbx'))
# join
box.hide_set(False)
ball.hide_set(False)
select_only(box)
ball.select_set(True)
bpy.ops.mch.make_highpoly(join=True)
check('Join Into One: one high poly object', C.active_object.name == 'HighPoly_Joined' and
      len(C.selected_objects) == 1)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
