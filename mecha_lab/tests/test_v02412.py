"""0.24.12 Smart Fuse: 3+ selected meshes are fused into the active one; fusing the next part onto a live preview
confirms it first; Cut / Split on a live preview bakes it first (the cut used to miss the hidden source part)."""
import sys

_src = open(__file__.replace('test_v02412.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
import mecha_lab as ml

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene


def call(op, **kw):
    try:
        return op(**kw)
    except RuntimeError as ex:
        print('  (operator reported)', str(ex).splitlines()[0])
        return {'CANCELLED'}


def wipe():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


def row(n, step=1.5):
    obs = []
    for i in range(n):
        o = cube(f'P{i}', 2.0)
        o.location.x = i * step
        o.location.z = 0.13 * i           # not coplanar: real overlaps
        o.rotation_euler.x = 0.07 * i
        obs.append(o)
    C.view_layer.update()
    return obs


# ---- five meshes at once
obs = row(5)
select_only(*obs)
C.view_layer.objects.active = obs[0]
r = call(bpy.ops.mch.smart_fuse)
names = [o.name for o in bpy.data.objects if o.type == 'MESH']
check('5 selected: all fused into the active mesh', r == {'FINISHED'} and names == ['P0'], (r, names))
p0 = bpy.data.objects['P0']
check('one closed solid, no fuse modifiers left', non_manifold(p0) == 0 and not p0.modifiers and
      not p0.mch_fuse.active, (non_manifold(p0), [m.name for m in p0.modifiers]))
check('it spans all five parts', p0.dimensions.x > 7.5, p0.dimensions.x)
wipe()

# a part that touches nothing is reported, the rest still fuses
obs = row(3)
far = cube('Far', 2.0)
far.location.x = 30
C.view_layer.update()
select_only(*obs, far)
C.view_layer.objects.active = obs[0]
r = call(bpy.ops.mch.smart_fuse)
check('a separate part stays (reported), the overlapping ones fuse', r == {'FINISHED'} and 'Far' in bpy.data.objects
      and not bpy.data.objects['Far'].hide_get() and 'P1' not in bpy.data.objects and 'P2' not in bpy.data.objects,
      (r, [(o.name, o.hide_get()) for o in bpy.data.objects]))
wipe()

# ---- chain: two -> live preview, then the next one onto it
obs = row(3)
select_only(obs[0], obs[1])
C.view_layer.objects.active = obs[0]
r = call(bpy.ops.mch.smart_fuse)
check('two: live preview as before', r == {'FINISHED'} and ml.fuse_is_live(obs[0]))
select_only(obs[0], obs[2])
C.view_layer.objects.active = obs[0]
r = call(bpy.ops.mch.smart_fuse)
check('next part onto the live preview: the first is confirmed, the new one is live',
      r == {'FINISHED'} and 'P1' not in bpy.data.objects and ml.fuse_is_live(obs[0]) and
      obs[0].mch_fuse.source == obs[2], r)
r = bpy.ops.mch.smart_fuse_confirm()
check('confirm: one closed solid of three parts', r == {'FINISHED'} and non_manifold(obs[0]) == 0 and
      obs[0].dimensions.x > 4.5)
wipe()

# ---- two at a time, four times in a row (the user's way): stays one closed solid, no old seam marks left
obs = row(5)
for i in range(1, 5):
    p0, pi = bpy.data.objects['P0'], bpy.data.objects[f'P{i}']
    select_only(p0, pi)
    C.view_layer.objects.active = p0
    r1 = call(bpy.ops.mch.smart_fuse)
    r2 = call(bpy.ops.mch.smart_fuse_confirm)
    check(f'fuse {i} (two at a time): done, still closed, seam mark cleared',
          r1 == r2 == {'FINISHED'} and non_manifold(p0) == 0 and ml._FUSE_EDGE_ATTRIBUTE not in p0.data.attributes,
          (r1, r2, non_manifold(p0)))
far = cube('Far2', 2.0)
far.location.x = 30
C.view_layer.update()
p0 = bpy.data.objects['P0']
select_only(p0, far)
C.view_layer.objects.active = p0
r = call(bpy.ops.mch.smart_fuse)
check('after fuses, a far part is still refused (the old seam mark no longer counts)', r == {'CANCELLED'} and
      'Far2' in bpy.data.objects and not p0.modifiers, r)
wipe()

# ---- Cut on a live preview bakes it first
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
MODE[0], NATIVE[0] = 'CUT', 'mecha.cut'
S.mch_settings.mch_active_tool = 'CUT'
a = cube('A', 2.0)
b = cube('B', 2.0)
b.location = (1.5, 0.0, 0.3)
b.rotation_euler.x = 0.1
C.view_layer.update()
select_only(a, b)
C.view_layer.objects.active = a
r = call(bpy.ops.mch.smart_fuse)
check('live preview before the cut', ml.fuse_is_live(a))
# cut a hole through the source part only (world x 2.0 .. 2.4)
r, m = lasso([(700, 470), (740, 470), (740, 530), (700, 530)])
check('cut on the live preview: fuse baked, source gone, cut done', r == {'FINISHED'} and not ml.fuse_is_live(a)
      and 'B' not in bpy.data.objects and m.startswith('Cut:'), (r, m))
xs = [v.co.x + a.location.x for v in a.data.vertices]
check('the hole is in the former source part (x 2.0 .. 2.4)', any(abs(x - 2.0) < 0.02 for x in xs) and
      any(abs(x - 2.4) < 0.02 for x in xs))
check('still one closed solid, no fuse modifiers', non_manifold(a) == 0 and not a.modifiers)

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
