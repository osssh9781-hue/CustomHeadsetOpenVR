"""0.24.19 lean mirror: LMB = copy to the right side of the screen and apply, RMB = copy to the left and apply
(the axis that runs left-right on screen, whatever the view).  Shift+LMB still adds an axis, Esc cancels,
pointing at another object keeps that object's side.  Meshes and collection instances."""
import math
import sys

_src = open(__file__.replace('test_v02419.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
from mathutils import Quaternion, Vector

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import mirror_tools as mt

S.mch_mirror.space = 'WORLD'
S.mch_mirror.center = 'ORIGIN'
S.mch_mirror.x, S.mch_mirror.y, S.mch_mirror.z = True, False, False
TOP = VIEW[0]
BACK = cg.OrthoProjector(Quaternion((0, 0, 1), math.pi) @ Quaternion((1, 0, 0), math.radians(90)))
FRONT = cg.OrthoProjector(Quaternion((1, 0, 0), math.radians(90)))


class Lean(mt.MirrorLeanLogic):
    keep_live = False


class LeanI(mt.InstanceMirrorLogic):
    keep_live = True


def xr(ob):
    dg = C.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    xs = [(ob.matrix_world @ v.co).x for v in me.vertices]
    ev.to_mesh_clear()
    return round(min(xs), 4), round(max(xs), 4)


def fresh_cube(name):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    t = cube(name, 1.0)
    t.location = (0.3, 0.0, 0.0)           # spans x -0.2 .. 0.8
    C.view_layer.update()
    select_only(t)
    C.view_layer.objects.active = t
    return t


def ev(type_, x=500, y=900, shift=False):
    e = E(type_, 'PRESS', x, y)
    e.shift = shift
    return e


t = fresh_cube('L')
op = Lean()
op.start(C, Region(), TOP, (500, 900))
r = op.handle(C, ev('LEFTMOUSE'))
check('LMB returns BAKE (apply at once)', r == 'BAKE', r)
check('top view LMB: copy to the screen right = +X (the -X half copied over)', xr(t) == (-0.2, 0.2), xr(t))
msg = op.finish_apply(C)
check('LMB result bakes: no modifier, mirrored mesh', mt.MOD_NAME not in t.modifiers and 'Mirror applied' in msg
      and xr(t) == (-0.2, 0.2), (msg, xr(t)))

t = fresh_cube('R')
op = Lean()
op.start(C, Region(), TOP, (500, 900))
r = op.handle(C, ev('RIGHTMOUSE'))
check('RMB no longer cancels: BAKE', r == 'BAKE', r)
check('top view RMB: copy to the screen left = -X (the +X half copied over)', xr(t) == (-0.8, 0.8), xr(t))
op.finish_apply(C)
check('RMB result bakes', mt.MOD_NAME not in t.modifiers and xr(t) == (-0.8, 0.8), xr(t))

t = fresh_cube('Back')
op = Lean()
op.start(C, Region(), BACK, (500, 900))
op.handle(C, ev('LEFTMOUSE'))
check('back view (screen right = world -X): LMB copies toward -X', xr(t) == (-0.8, 0.8), xr(t))
op.restore_all()

t = fresh_cube('Front')
op = Lean()
op.start(C, Region(), FRONT, (500, 900))
op.handle(C, ev('LEFTMOUSE'))
mod = t.modifiers[mt.MOD_NAME]
check('front view LMB: X axis (left-right on screen), not Z', tuple(mod.use_axis) == (True, False, False)
      and xr(t) == (-0.2, 0.2), (tuple(mod.use_axis), xr(t)))
op.restore_all()

t = fresh_cube('Shift')
op = Lean()
op.start(C, Region(), TOP, (500, 900))
op.handle(C, E('MOUSEMOVE', 'NOTHING', 800, 180))
r = op.handle(C, ev('LEFTMOUSE', 800, 180, shift=True))
op.handle(C, E('MOUSEMOVE', 'NOTHING', 500, 480))
mod = t.modifiers[mt.MOD_NAME]
check('Shift+LMB still adds the axis and keeps going', r == 'RUN' and tuple(mod.use_axis) == (True, True, False),
      (r, tuple(mod.use_axis)))
op.handle(C, ev('LEFTMOUSE', 500, 480, shift=True))        # lock Y too
op.locked[0] = False                                       # only Y locked
r = op.handle(C, ev('LEFTMOUSE', 500, 480))
mod = t.modifiers[mt.MOD_NAME]
check('then LMB: the locked Y stays, X copies to the right', r == 'BAKE' and tuple(mod.use_axis) == (True, True, False)
      and mod.use_bisect_flip_axis[0], (r, tuple(mod.use_axis)))
op.restore_all()

t = fresh_cube('Esc')
op = Lean()
op.start(C, Region(), TOP, (500, 900))
r = op.handle(C, E('ESC', 'PRESS'))
op.restore_all()
check('Esc still cancels: mesh untouched', r == 'CANCEL' and mt.MOD_NAME not in t.modifiers and len(t.data.vertices) == 8)

# pointing at another object: the click keeps that object's side
t = fresh_cube('Arm')
t.location = (-2.0, 0.0, 0.0)
body = cube('Body', 2.0)
body.location = (1.5, 0.0, 0.0)
C.view_layer.update()
select_only(t)
op = Lean()
op.start(C, Region(), TOP, (500, 500))
op.handle(C, E('MOUSEMOVE', 'NOTHING', 650, 500))
r = op.handle(C, ev('RIGHTMOUSE', 650, 500))
mod = t.modifiers[mt.MOD_NAME]
check('pointing at Body + RMB: still mirrored across Body (copy beyond it)', r == 'BAKE' and op.pivot_name == 'Body'
      and xr(t)[1] > 4.9, (r, op.pivot_name, xr(t)))
op.restore_all()


# modal: BAKE applies even from the Mirror button (keep_live)
class FakeOp(mt.LeanModal):
    def __init__(self, r, keep_live):
        self.r, self.keep_live, self.calls = r, keep_live, []
        self._handle, self._area = None, None

    def handle(self, context, event):
        return self.r

    def finish_apply(self, context):
        self.calls.append('apply')
        return 'a'

    def finish_live(self, scene):
        self.calls.append('live')
        return 'l'

    def restore_all(self):
        self.calls.append('restore')

    def report(self, *a):
        pass


for r, live, want in (('BAKE', True, 'apply'), ('BAKE', False, 'apply'), ('APPLY', True, 'live'),
                      ('APPLY', False, 'apply'), ('CANCEL', False, 'restore')):
    f = FakeOp(r, live)
    f.modal(C, None)
    check(f'modal {r} keep_live={live} -> {want}', f.calls == [want], f.calls)

# collection instance: LMB = the mirrored twin on the screen right
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
for o in (t, body):
    bpy.data.objects.remove(o, do_unlink=True)
inst.location = (-2.0, 0.0, 0.0)
C.view_layer.update()
select_only(inst)
opi = LeanI()
opi.start(C, Region(), TOP, (500, 900))
r = opi.handle(C, ev('LEFTMOUSE'))
tw = mt.instance_twins(inst)
check('instance LMB: BAKE, one live twin mirrored across X', r == 'BAKE' and len(tw) == 1 and opi.axes == [True, False, False],
      (r, len(tw), opi.axes))
r = opi.handle(C, ev('RIGHTMOUSE'))
check('instance RMB: BAKE too (twin stays live)', r == 'BAKE' and len(mt.instance_twins(inst)) == 1, r)
check('instance finish_apply keeps the live twin', 'follows the original' in opi.finish_apply(C))

src = open(mt.__file__).read()
check('status bar names LMB right / RMB left', 'LMB: copy to the right + apply' in src and
      'RMB: copy to the left + apply' in src and 'Esc / RMB: cancel' not in src)
sys.exit(1 if summary() else 0)
