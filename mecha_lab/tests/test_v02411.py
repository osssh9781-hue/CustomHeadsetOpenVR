"""0.24.11 Box Hide: Targets 'Selected Only' is kept by the sketch (Enter) too, and a Shift+D duplicate of a hidden
mesh gets its own hide volume (hiding more on one object no longer cuts its duplicates)."""
import sys

_src = open(__file__.replace('test_v02411.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
from mathutils import Vector

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import lasso_sketch as ls, box_hide as bh

S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
MODE[0], NATIVE[0] = 'HIDE', 'mecha.box_hide'
S.mch_settings.mch_active_tool = 'HIDE'


def two():
    a = cube('A', 2.0)
    a.location.x = -1.5
    b = cube('B', 2.0)
    b.location.x = 1.5
    C.view_layer.update()
    return a, b


WIDE = [(200, 450), (800, 450), (800, 550), (200, 550)]      # covers both (world x -3 .. 3)

# ---- sketch + Selected Only
a, b = two()
S.mch_cut.targets = 'SELECTED'
select_only(a)
ls.set_on(C, True)
r, m = lasso(WIDE)
res = bpy.ops.mch.lasso_sketch_commit(alt=False)
check('sketch Enter with Selected Only: only the selected mesh is hidden',
      res == {'FINISHED'} and bh.is_hidden(a) and not bh.is_hidden(b), (res, bh.is_hidden(a), bh.is_hidden(b)))
for o in C.selected_objects:
    o.select_set(False)
r, m = lasso(WIDE)
try:
    res = bpy.ops.mch.lasso_sketch_commit(alt=False)
except RuntimeError as ex:
    res = str(ex)
check('sketch Enter with Selected Only and nothing selected: nothing hidden', not bh.is_hidden(b), res)
ls.clear(S)
S.mch_cut.targets = 'AUTO'
r, m = lasso(WIDE)
bpy.ops.mch.lasso_sketch_commit(alt=False)
check('sketch Enter with Auto Target: every covered mesh', bh.is_hidden(a) and bh.is_hidden(b))
ls.set_on(C, False)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)

# ---- Shift+D duplicate keeps its own hiding
a = cube('A', 2.0)
C.view_layer.update()
select_only(a)
S.mch_cut.targets = 'SELECTED'
r, m = lasso([(420, 420), (480, 420), (480, 480), (420, 480)])
check('first hide on A', bh.is_hidden(a), m)
vol_a = bh.volume_of(a)
v_shape = len(vol_a.data.vertices)
dup = a.copy()                       # Shift+D: object copy, the modifier still points at A's volume
dup.data = a.data.copy()
C.scene.collection.objects.link(dup)
dup.location.x = 3.0
C.view_layer.update()
check('the duplicate starts with the same volume (as Shift+D does)', bh.volume_of(dup) is vol_a)
select_only(a)
r, m = lasso([(520, 520), (580, 520), (580, 580), (520, 580)])
check('second hide on A only', r == {'FINISHED'}, m)
check('the duplicate got its own volume', bh.volume_of(dup) is not None and bh.volume_of(dup) is not bh.volume_of(a))
check('the duplicate keeps only the first hidden part', len(bh.volume_of(dup).data.vertices) == v_shape,
      (len(bh.volume_of(dup).data.vertices), v_shape))
check('A has both parts', len(bh.volume_of(a).data.vertices) > v_shape)
check('volumes are named for their mesh', bh.volume_of(dup).get(bh.VOL_KEY) == dup.name and
      bh.volume_of(a).get(bh.VOL_KEY) == a.name)
# Show All on a mesh sharing its volume with another one leaves the other one hidden
dup2 = a.copy()
dup2.data = a.data.copy()
C.scene.collection.objects.link(dup2)
shared = bh.volume_of(a)
bh.show_all(a)
check('Show All on A keeps the volume a duplicate still uses', bh.volume_of(dup2) is shared and
      shared.name in bpy.data.objects)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
