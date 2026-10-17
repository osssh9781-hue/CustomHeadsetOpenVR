"""0.24.13 Alt+X on a selected collection instance: the lean gesture makes a live mirrored instance of the same
collection (it follows the original when moved / rotated); Esc restores; re-mirroring replaces the twin."""
import sys

_src = open(__file__.replace('test_v02413.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
from mathutils import Matrix, Vector

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import mirror_tools as mt, workspace_ui as wui, tool_state as ts

coll = bpy.data.collections.new('Arm')
S.collection.children.link(coll)
part = cube('ArmPart', 1.0)
for c in list(part.users_collection):
    c.objects.unlink(part)
coll.objects.link(part)
part.location = (0.5, 0.0, 0.0)
inst = bpy.data.objects.new('ArmInst', None)
inst.instance_type = 'COLLECTION'
inst.instance_collection = coll
S.collection.objects.link(inst)
inst.location = (3.0, 1.0, 0.5)
inst.rotation_euler.z = 0.3
C.view_layer.update()
check('a collection instance is recognised', mt.is_collection_instance(inst) and not mt.is_collection_instance(part))


class Lean(mt.InstanceMirrorLogic):
    pass


S.mch_mirror.space = 'WORLD'
S.mch_mirror.center = 'ORIGIN'
S.mch_mirror.x, S.mch_mirror.y, S.mch_mirror.z = True, False, False
select_only(inst)
C.view_layer.objects.active = inst
op = Lean()
ok = op.start(C, Region(), VIEW[0], (500, 500))
C.view_layer.update()
tw = mt.instance_twins(inst)
check('lean start: one live mirrored instance of the same collection', ok and len(tw) == 1 and
      tw[0].instance_collection == coll, len(tw))
R = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))


def close(a, b):
    return all(abs(a[i][j] - b[i][j]) < 1e-5 for i in range(4) for j in range(4))


check('twin = master mirrored across world X', close(tw[0].matrix_world, R @ inst.matrix_world),
      (tuple(tw[0].matrix_world.translation), tuple(inst.matrix_world.translation)))
check('the twin is a mirror image (negative determinant)', tw[0].matrix_world.determinant() < 0)
inst.location = (4.0, -2.0, 1.0)
inst.rotation_euler.z = 1.0
C.view_layer.update()
check('moving / rotating the original moves the twin', close(tw[0].matrix_world, R @ inst.matrix_world))
op.toggle_axis(S, 1)          # + Y
C.view_layer.update()
check('X + Y: three mirrored instances', len(mt.instance_twins(inst)) == 3)
msg = op.finish_live(S)
check('finish keeps them', 'Instance mirror' in msg and len(mt.instance_twins(inst)) == 3)
# re-mirror: old twins replaced, Esc restores them
op2 = Lean()
S.mch_mirror.x, S.mch_mirror.y, S.mch_mirror.z = False, False, True
op2.start(C, Region(), VIEW[0], (500, 500))
check('re-mirror replaces the twins (Z only)', len(mt.instance_twins(inst)) == 1)
op2.restore_all()
check('Esc restores the previous twins', len(mt.instance_twins(inst)) == 3)
mt.remove_instance_twins(inst)
check('remove leaves no helper empties', not [o for o in bpy.data.objects if o.get(mt.RIG_TAG)])
# 3D cursor centre
S.mch_mirror.center = 'CURSOR'
S.cursor.location = (1.0, 0.0, 0.0)
S.mch_mirror.x, S.mch_mirror.y, S.mch_mirror.z = True, False, False
op3 = Lean()
op3.start(C, Region(), VIEW[0], (500, 500))
C.view_layer.update()
t = mt.instance_twins(inst)[0]
check('3D cursor plane: twin at 2 - x', abs(t.matrix_world.translation.x - (2.0 - inst.location.x)) < 1e-5,
      t.matrix_world.translation.x)
check('the twin is not put inside its own collection', coll not in t.users_collection)
mt.remove_instance_twins(inst)
S.cursor.location = (0, 0, 0)

# ---- Alt+X routes a selected instance to the instance mirror, a mesh to the mesh mirror
calls = []
import mecha_lab.mirror_tools as _mtm
orig = _mtm.bpy
_mtm.bpy = types.SimpleNamespace(ops=types.SimpleNamespace(mch=types.SimpleNamespace(
    instance_mirror_lean=lambda *a, **k: (calls.append('inst'), {'RUNNING_MODAL'})[1],
    mirror_lean=lambda *a, **k: (calls.append('mesh'), {'RUNNING_MODAL'})[1])), types=bpy.types)
real_poll = ts.is_mecha_workspace
ts.is_mecha_workspace = lambda ws: True
try:
    fake = types.SimpleNamespace(action='MIRROR', only_empty=False, report=lambda *a: None)
    fake.execute = lambda ctx: wui.MCH_OT_hotkey.execute(fake, ctx)
    select_only(inst)
    r1 = wui.MCH_OT_hotkey.invoke(fake, C, None)
    other = cube('Body', 1.0)
    select_only(other)
    r2 = wui.MCH_OT_hotkey.invoke(fake, C, None)
finally:
    _mtm.bpy = orig
    ts.is_mecha_workspace = real_poll
check('Alt+X on a collection instance -> instance mirror; on a mesh -> mesh mirror', calls == ['inst', 'mesh'] and
      r1 == r2 == {'RUNNING_MODAL'}, calls)
# ---- 0.24.14 nothing mirrorable selected (e.g. only a curve): a plain message, not Blender's poll error
cu = bpy.data.curves.new('CurveData', 'CURVE')
cob = bpy.data.objects.new('JustACurve', cu)
S.collection.objects.link(cob)
select_only(cob)
msgs = []
r = mt.start_mirror(C, True, lambda kind, m: msgs.append(m))
check('only a curve selected: plain message (no poll error)', r == {'CANCELLED'} and msgs and
      'collection instance' in msgs[0] and 'Curve' in msgs[0] and 'poll' not in msgs[0], msgs)
select_only(cob, inst)
check('curve + collection instance -> instance mirror', mt.mirror_targets_kind(C) == 'INSTANCE')
select_only(cob, part if part.name in bpy.data.objects else inst)
from mecha_lab import bottom_bar as bb
calls2 = []
orig = _mtm.bpy
_mtm.bpy = types.SimpleNamespace(ops=types.SimpleNamespace(mch=types.SimpleNamespace(
    instance_mirror_lean=lambda *a, **k: (calls2.append('inst'), {'RUNNING_MODAL'})[1],
    mirror_lean=lambda *a, **k: (calls2.append(('mesh', k.get('keep_live'))), {'RUNNING_MODAL'})[1])),
    types=bpy.types)
try:
    for action in ('MIRROR', 'SYMMETRY'):
        body = cube('Body2', 1.0) if 'Body2' not in bpy.data.objects else bpy.data.objects['Body2']
        select_only(body)
        bb.MCH_OT_object_tidy.execute(types.SimpleNamespace(action=action, report=lambda *a: None), C)
    select_only(inst)
    bb.MCH_OT_object_tidy.execute(types.SimpleNamespace(action='MIRROR', report=lambda *a: None), C)
finally:
    _mtm.bpy = orig
check('left Mirror / Symmetry buttons use the same entry (mesh keep-live / apply, instance)',
      calls2 == [('mesh', True), ('mesh', False), 'inst'], calls2)
check('instance mirror operator registered', hasattr(bpy.ops.mch, 'instance_mirror_lean') and
      'MCH_OT_instance_mirror_lean' in dir(bpy.types))
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
