"""0.24.28 Cape Generator: hem / tatter / column helpers, Capelet / Cloak / Poncho / Ragged on a mannequin (closed
mesh, hangs behind, lengths), Outline vs Preset, Wrap, live sliders, the body is found through older capes, Apply,
tool registration (list, icon, Enter = Apply)."""
import math
import os

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import cape_gen as cp, core_geometry as cg, tool_state as ts, workspace_ui as wsui

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene

# pure helpers
check('hem: Straight is even, Round / Pointed longest in the middle', cp.hem_profile(0.0, 'STRAIGHT') == 1.0
      and cp.hem_profile(0.5, 'ROUND') > cp.hem_profile(0.0, 'ROUND')
      and cp.hem_profile(0.5, 'POINTED') > cp.hem_profile(0.1, 'POINTED'))
check('hem: Split has a notch in the middle', cp.hem_profile(0.5, 'SPLIT') < cp.hem_profile(0.25, 'SPLIT'))
t = cp.tatter_profile(40, 0.6, 3)
check('tatter: 40 columns, torn strips between 0.4 and 1', len(t) == 40 and min(t) >= 0.4 - 1e-9 and max(t) <= 1.0
      and min(t) < 0.9, (min(t), max(t)))
check('tatter 0 = untouched', cp.tatter_profile(10, 0.0, 1) == [1.0] * 10)
cols = cp.columns([(0, 0), (100, 0), (100, 50), (0, 50)], 5)
check('columns: top and bottom of the outline across it', len(cols) == 5 and all(abs(c[1] - 50) < 1e-6 and abs(c[2])
      < 1e-6 for c in cols))


def mannequin():
    parts = []

    def add(op, **kw):
        op(**kw)
        parts.append(C.active_object)
        return parts[-1]
    tor = add(bpy.ops.mesh.primitive_uv_sphere_add, radius=1, segments=40, ring_count=20, location=(0, 0, 1.25))
    tor.scale = (0.36, 0.22, 0.5)
    add(bpy.ops.mesh.primitive_uv_sphere_add, radius=0.12, segments=24, ring_count=12, location=(0, -0.02, 1.86))
    add(bpy.ops.mesh.primitive_cylinder_add, radius=0.06, depth=0.2, location=(0, 0, 1.72))
    add(bpy.ops.mesh.primitive_cylinder_add, radius=0.085, depth=0.95, location=(0, 0, 1.6), rotation=(0, math.pi / 2, 0))
    for sx in (-1, 1):
        add(bpy.ops.mesh.primitive_cylinder_add, radius=0.06, depth=0.7, location=(sx * 0.48, 0, 1.25))
        add(bpy.ops.mesh.primitive_cylinder_add, radius=0.09, depth=0.95, location=(sx * 0.14, 0, 0.48))
    for o in C.selected_objects:
        o.select_set(False)
    for o in parts:
        o.select_set(True)
    C.view_layer.objects.active = parts[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.join()
    body = C.active_object
    body.name = 'Body'
    body.scale = (3, 3, 3)
    body.location = (0, 0, -2.7)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return body


body = mannequin()
BACK = cg.OrthoProjector(Euler((math.radians(90), 0, math.pi)).to_quaternion())   # camera behind (+Y), looking -Y
SHORT = [[(405, 738), (595, 738), (595, 705), (405, 705)]]
res = {}
for style in ('CAPELET', 'CLOAK', 'PONCHO', 'RAGGED'):
    S.mch_cape.style = style
    msg = cp.perform(C, SHORT, BACK)
    ob = C.active_object
    vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
    res[style] = (ob, min(v.z for v in vs), max(v.y for v in vs), max(v.x for v in vs) - min(v.x for v in vs))
    check(f'{style}: a live cape on the body, closed mesh', cp.live_cape(C) == ob and 'on Body' in msg
          and non_manifold(ob) == 0, (msg, non_manifold(ob)))
check('the style fills in the sliders (Ragged = torn hem)', S.mch_cape.tatter > 0.3 and S.mch_cape.style == 'RAGGED')
check('Capelet is short, Cloak long (hangs to the legs)', res['CAPELET'][1] > 0.5 and res['CLOAK'][1] < -1.0,
      (res['CAPELET'][1], res['CLOAK'][1]))
check('it hangs behind the body (the side it was drawn from)', all(r[2] > 0.5 for r in res.values()))
check('Poncho spreads wider than the Cloak', res['PONCHO'][3] > res['CLOAK'][3], (res['PONCHO'][3], res['CLOAK'][3]))
# the cape stays out of the body
from mathutils.bvhtree import BVHTree
bvh = BVHTree.FromPolygons([v.co for v in body.data.vertices], [tuple(p.vertices) for p in body.data.polygons])
ob = res['CLOAK'][0]
inside = 0
for v in list(ob.data.vertices)[::7]:
    w = ob.matrix_world @ v.co
    loc, n, _i, d = bvh.find_nearest(w)
    if loc is not None and (w - loc).dot(n) < -1e-3:
        inside += 1
check('the cloak does not go into the body', inside == 0, inside)

# live sliders
ob = res['CLOAK'][0]
for o in C.selected_objects:
    o.select_set(False)
ob.select_set(True)
C.view_layer.objects.active = ob
z0 = min((ob.matrix_world @ v.co).z for v in ob.data.vertices)
ob.mch_cape.length = 0.45
z1 = min((ob.matrix_world @ v.co).z for v in ob.data.vertices)
check('Length is live (shorter = the hem moves up)', z1 > z0 + 0.5 and ob.mch_cape.last_error == '', (z0, z1))
w0 = res['CLOAK'][3]
ob.mch_cape.wrap = 150.0
vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
check('Wrap carries it further round the body (comes forward)', min(v.y for v in vs) < 0.0, min(v.y for v in vs))
ob.mch_cape.wrap = 60.0


def hem_width(o):
    vs = [o.matrix_world @ v.co for v in o.data.vertices]
    zmin = min(v.z for v in vs)
    low = [v for v in vs if v.z < zmin + 0.4]
    return max(v.x for v in low) - min(v.x for v in low)


ob.mch_cape.straight = 0.0
wide = hem_width(ob)
ob.mch_cape.straight = 1.0
plumb = hem_width(ob)
check('Straight: the sides drop plumb (narrower hem than spreading out)', plumb < wide * 0.85
      and non_manifold(ob) == 0, (wide, plumb))
ob.mch_cape.folds = 0
ob.mch_cape.fold_depth = 0.0
ob.mch_cape.tatter = 0.4
check('folds off / tatter still a closed mesh', non_manifold(ob) == 0)

# Outline: the drawn silhouette sets the length
S.mch_cape.style = 'CLOAK'
S.mch_cape.shape = 'AUTO'
S.mch_cape.wrap = 0.0
cp.perform(C, [[(420, 738), (580, 738), (580, 400), (420, 400)]], BACK)
ob = C.active_object
zmin = min((ob.matrix_world @ v.co).z for v in ob.data.vertices)
check('a tall drawing = Outline: the hem follows its bottom (z = -1)', abs(zmin - (-1.0)) < 0.45, zmin)
check('the new cape was hung on the body, not on the older capes', 'on Body' in cp.perform(C, SHORT, BACK))
r = bpy.ops.mch.cape_apply()
check('Apply: plain mesh', 'FINISHED' in r and cp.SRC_KEY not in C.active_object)
try:
    cp.perform(C, [[(10, 10), (40, 10), (40, 30), (10, 30)]], BACK)
    check('drawing next to the body: a clear message', False)
except cg.CutError as ex:
    check('drawing next to the body: a clear message', 'body' in str(ex), str(ex))

# tool wiring
check('Cape is in the tool list', 'CAPE' in ts.TOOL_BY_ID and any(t[0] == 'CAPE' for t in ts.VISIBLE_TOOLS))
icons = os.path.join(os.path.dirname(mecha_lab.__file__), 'icons')
check('Cape has its icon', os.path.isfile(os.path.join(icons, 'cape.png')))
check('Enter applies a live cape', ('cape_apply', 'Cape') in wsui.ENTER_APPLY)
from mecha_lab import cut_engine as ce, lasso_line as ll
check('the drawing tool sends Cape outlines to the generator', 'cape_gen.perform' in open(ce.__file__).read()
      and 'CAPE' in ll.MODES)
summary()
