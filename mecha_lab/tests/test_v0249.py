"""0.24.9 Cut on a mesh with a live Mirror: drawing over the mirrored copy cuts too (the base mesh is cut with the
shape mirrored back), also with a pivot object and after flipping the object on a world axis (negative scale)."""
import sys

_src = open(__file__.replace('test_v0249.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
from mathutils import Matrix, Vector

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
MODE[0], NATIVE[0] = 'CUT', 'mecha.cut'
S.mch_settings.mch_active_tool = 'CUT'

LEFT = [(220, 470), (280, 470), (280, 530), (220, 530)]      # world x = -2.8 .. -2.2
RIGHT = [(720, 470), (780, 470), (780, 530), (720, 530)]     # world x = +2.2 .. +2.8


def half(name, pivot=None, scale_x=1.0):
    b = cube(name, 2.0)
    b.data.transform(Matrix.Translation((2.5, 0, 0)))       # base half at local x = 1.5 .. 3.5
    m = b.modifiers.new('Mirror', 'MIRROR')
    if pivot is not None:
        m.mirror_object = pivot
    b.scale.x = scale_x
    b.data.update()
    C.view_layer.update()
    return b


def wipe():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


def hole_x(ob):
    """Local x of the new pocket walls (vertices not on the original box corners)."""
    xs = sorted({round(v.co.x, 3) for v in ob.data.vertices if abs(abs(v.co.y) - 0.3) < 0.02})
    return xs


for label, pts, scale_x, want in (('original side', RIGHT, 1.0, (2.2, 2.8)), ('mirrored side', LEFT, 1.0, (2.2, 2.8)),
                                  ('flipped: original now on the left', LEFT, -1.0, (2.2, 2.8)),
                                  ('flipped: mirrored copy now on the right', RIGHT, -1.0, (2.2, 2.8))):
    b = half('H', scale_x=scale_x)
    select_only(b)
    r, m = lasso(pts)
    xs = hole_x(b)
    check(f'live Mirror, {label}: cut', r == {'FINISHED'} and m.startswith('Cut:'), (r, m))
    check(f'live Mirror, {label}: pocket on the base half at local x 2.2 .. 2.8',
          xs and abs(min(xs) - want[0]) < 0.03 and abs(max(xs) - want[1]) < 0.03, xs)
    check(f'live Mirror, {label}: still one closed solid', non_manifold(b) == 0)
    wipe()

# pivot object (the Mecha Mirror uses an empty) moved to x = 1: the copy sits at x = -1.5 .. 0.5 (world)
pivot = bpy.data.objects.new('Pivot', None)
C.scene.collection.objects.link(pivot)
pivot.location.x = 1.0
b = cube('P', 2.0)
b.data.transform(Matrix.Translation((2.5, 0, 0)))
b.modifiers.new('Mirror', 'MIRROR').mirror_object = pivot
b.data.update()
C.view_layer.update()
select_only(b)
r, m = lasso([(395, 470), (445, 470), (445, 530), (395, 530)])   # world x = -1.05 .. -0.55 -> base 2.55 .. 3.05
xs = hole_x(b)
check('pivot Mirror, mirrored side: cut at the reflected place', r == {'FINISHED'} and xs and
      abs(min(xs) - 2.55) < 0.03 and abs(max(xs) - 3.05) < 0.03, (r, m, xs))
wipe()

# no Mirror: drawing beside the mesh still says nothing was cut
b = cube('N', 2.0)
select_only(b)
r, m = lasso(RIGHT)
check('no Mirror, off the mesh: nothing changed', r != {'FINISHED'} and len(b.data.polygons) == 6, (r, m))
check('no temporary meshes left', not [me for me in bpy.data.meshes if 'mirror' in me.name.lower()],
      [me.name for me in bpy.data.meshes])

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
