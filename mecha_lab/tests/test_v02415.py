"""0.24.15 lean mirror: moving the mouse onto another object makes it the mirror centre - the copy goes to its far
side (axis = the world axis from the selection toward it); off any object the usual lean works again.
Meshes and collection instances."""
import sys

_src = open(__file__.replace('test_v02415.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
from mathutils import Matrix, Vector

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import mirror_tools as mt

S.mch_mirror.space = 'WORLD'
S.mch_mirror.center = 'ORIGIN'
S.mch_mirror.x, S.mch_mirror.y, S.mch_mirror.z = True, False, False


class Lean(mt.MirrorLeanLogic):
    pass


class LeanI(mt.InstanceMirrorLogic):
    pass


arm = cube('Arm', 1.0)
arm.location = (-2.0, 0.0, 0.0)
body = cube('Body', 2.0)
body.location = (1.5, 0.0, 0.0)
C.view_layer.update()
select_only(arm)
op = Lean()
op.start(C, Region(), VIEW[0], (500, 500))
op.on_move(S, (650, 500))                    # on Body (world x 1.5)
mod = arm.modifiers.get(mt.MOD_NAME)
piv = mod.mirror_object
check('pointing at Body: it becomes the mirror centre', op.pivot_name == 'Body' and piv is not None and
      (piv.matrix_world.translation - Vector((1.5, 0, 0))).length < 1e-4, (op.pivot_name, piv and tuple(piv.matrix_world.translation)))
check('axis X toward Body, the Arm side kept (copy lands beyond Body)', tuple(mod.use_axis) == (True, False, False)
      and mod.use_bisect_flip_axis[0], (tuple(mod.use_axis), tuple(mod.use_bisect_flip_axis)))
check('the message names it', 'across Body' in op.describe(), op.describe())
dg = C.evaluated_depsgraph_get()
ev = arm.evaluated_get(dg)
xs = [(ev.matrix_world @ v.co).x for v in ev.data.vertices]
check('the copy is on the far side of Body (x about 5)', max(xs) > 4.9 and min(xs) < -2.4, (min(xs), max(xs)))
op.on_move(S, (500, 900))                    # empty space above
check('off any object: back to the normal lean (world origin)', op.pivot_name is None and
      piv.matrix_world.translation.length < 1e-4)
op.on_move(S, (650, 500))
op.finish_live(S)
check('finish keeps the mirror across Body', arm.modifiers.get(mt.MOD_NAME).mirror_object.matrix_world.translation.x > 1.4)
op2 = Lean()
op2.start(C, Region(), VIEW[0], (500, 500))
op2.on_move(S, (300, 500))                   # on the Arm itself: not a pivot
check('the selected object itself is never the pivot', op2.pivot_name is None)
op2.restore_all()

# ---- collection instance
coll = bpy.data.collections.new('Part')
S.collection.children.link(coll)
pc = cube('PartCube', 1.0)
for c in list(pc.users_collection):
    c.objects.unlink(pc)
coll.objects.link(pc)
inst = bpy.data.objects.new('PartInst', None)
inst.instance_type = 'COLLECTION'
inst.instance_collection = coll
S.collection.objects.link(inst)
inst.location = (-2.0, 2.5, 0.0)
body.location = (1.5, 2.5, 0.0)
arm.location = (-2.0, -3.0, 0.0)
C.view_layer.update()
select_only(inst)
opi = LeanI()
opi.start(C, Region(), VIEW[0], (500, 500))
opi.on_move(S, (300, 750))                   # on the instance itself (world -2, 2.5): ignored
check('instance: its own collection parts are not a pivot', opi.pivot_name is None, opi.pivot_name)
opi.on_move(S, (650, 750))                   # on Body
C.view_layer.update()
tw = mt.instance_twins(inst)
check('instance pointing at Body: mirrored instance beyond it (x = 5)', opi.pivot_name == 'Body' and len(tw) == 1 and
      abs(tw[0].matrix_world.translation.x - 5.0) < 1e-4, (opi.pivot_name, [tuple(t.matrix_world.translation) for t in tw]))
opi.restore_all()
check('Esc: no twin left', not mt.instance_twins(inst))
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
