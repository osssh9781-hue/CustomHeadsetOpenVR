"""0.23.7: Through (the plate outline goes through the mesh - back too, split into panels at the
silhouette and at sharp creases) for Armor + Cloth Plate; cloth types after the references:
Puffer (quilted channels), Cotton (crumpled thin creases), Drape (big soft folds) + the Crumple layer."""
import math
import sys

_src = open(__file__.replace('test_v0237.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
import bmesh
from mathutils import Matrix
import numpy as np

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
from mecha_lab import armor_plate as ap, cloth_wrinkle as cw, last_used, through_region as tr
for sec in ('wrinkle', 'creature', 'shell'):
    last_used.forget(sec)
check('Through + Crease brush options', hasattr(S.mch_brush, 'through_mode') and S.mch_brush.through_mode is False
      and abs(S.mch_brush.through_crease - 50.0) < 1e-6)

# ---- pure: a band across a lying cylinder -> top half + bottom half
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=1.0, radius2=1.0, depth=6.0,
                      matrix=Matrix.Rotation(math.pi / 2, 4, 'Y'))
proj = cg.OrthoProjector(Quaternion())
band = [[(400, 300), (600, 300), (600, 700), (400, 700)]]
panels = tr.through_panels(bm, cg.prepare_loops(band), proj, 14.0, 50.0)
bm.free()
zs = [(min(c.z for c in p_['cos']), max(c.z for c in p_['cos'])) for p_ in panels]
check('through: a band over a cylinder takes the front AND the back (2 panels)', len(panels) == 2 and
      sorted(p_['front'] for p_ in panels) == [False, True], zs)
check('through: the front panel is the top half, the back the bottom half',
      any(lo > -0.05 and hi > 0.95 for lo, hi in zs) and any(hi < 0.05 and lo < -0.95 for lo, hi in zs), zs)
xs = [c.x for p_ in panels for c in p_['cos']]
check('through: the panels follow the outline (x within the band)', min(xs) > -1.05 and max(xs) < 1.05,
      (round(min(xs), 3), round(max(xs), 3)))
fine = sum(len(p_['tris']) for p_ in panels)
check('through: the region is refined to the Face Size (many small faces)', fine > 400, fine)

# ---- crease: a cube seen from the top, outline bigger than the cube
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=2.0)
big = cg.prepare_loops([[(250, 250), (750, 250), (750, 750), (250, 750)]])
n50 = len(tr.through_panels(bm.copy(), big, proj, 20.0, 50.0))
n180 = len(tr.through_panels(bm.copy(), big, proj, 20.0, 180.0))
bm.free()
check('through: sharp creases split the panels (cube: 6 sides at 50 deg)', n50 == 6, n50)
check('through: Crease 180 = only the silhouette splits (front + back)', n180 == 2, n180)

# ---- the tools with Through on
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=1.0, depth=6.0, rotation=(0, math.pi / 2, 0))
cyl = C.active_object
S.mch_brush.through_mode = True
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
S.mch_settings.mch_active_tool = 'WRINKLE'
r, m = lasso([(400, 300), (600, 300), (600, 700), (400, 700)])
obs = [o for o in C.selected_objects if cw.is_wrinkle(o)]
zr = sorted((min((o.matrix_world @ v.co).z for v in o.data.vertices),
             max((o.matrix_world @ v.co).z for v in o.data.vertices)) for o in obs)
check('Cloth Plate Through: a front and a back cloth layer around the cylinder', r == {'FINISHED'} and
      len(obs) == 2 and zr[0][0] < -0.9 and zr[1][1] > 0.9 and 'through' in m, (m, zr))
check('Cloth Plate Through: every layer has folds', all(o.data.attributes.get(cw.FOLD_H) is not None for o in obs))
MODE[0], NATIVE[0] = 'PLATE', 'mecha.armor_plate'
S.mch_settings.mch_active_tool = 'PLATE'
r, m = lasso([(400, 300), (600, 300), (600, 700), (400, 700)])
plates = [o for o in C.selected_objects if ap.is_plate_or_part(o)]
check('Armor Plate Through: a front and a back plate', r == {'FINISHED'} and len(plates) == 2 and 'through' in m, m)
src = ap.plate_source(plates[0])
check('Through plates keep their outline + panel for Face Size', src is not None and src.get('through') == 0 and
      'crease' in src)
nv = len(plates[0].mch_extract.region.vertices)
ok = ap.rebuild_plate(C, plates[0], spacing=24)
check('Face Size rebuild of a Through plate', ok and len(plates[0].mch_extract.region.vertices) != nv,
      (ok, nv, len(plates[0].mch_extract.region.vertices)))
S.mch_brush.through_mode = False

# ---- cloth types after the references
ids = cw.TYPE_IDS
check('Puffer / Cotton / Drape types', ids[:3] == ('PADDING', 'DENIM', 'LEATHER') and
      ids[3:] == ('PUFFER', 'COTTON', 'DRAPE') and next(x for x in cw.INPUTS if x[0] == 'Type')[4] == 5)
check('Crumple layer inputs', all(any(x[0] == k for x in cw.INPUTS) for k in
      ('Crumple', 'Crumple Size', 'Crumple Sharp', 'Crumple Stretch', 'Crumple Angle', 'Billow', 'Billow Size')))
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
S.mch_settings.mch_active_tool = 'WRINKLE'
made = {}
for k, wt in enumerate(('PADDING', 'PUFFER', 'COTTON', 'DRAPE')):
    b = cube('T%d' % k, 4.0, loc=(6.0 * k, 12, 0))
    VIEW[0] = cg.OrthoProjector(Quaternion(), center=Vector((6.0 * k, 12, 0)))
    S.mch_wrinkle.wtype = wt
    last_used.forget('wrinkle')
    r, m = lasso([(340, 330), (660, 330), (665, 670), (335, 670)])
    made[wt] = C.active_object
gi = cw.get_input
check('each type makes a cloth plate', all(cw.is_wrinkle(o) and int(gi(o, 'Type')) == cw.TYPE_IDS.index(k)
                                           for k, o in made.items()))
check('older type unchanged: no crumple / billow', gi(made['PADDING'], 'Crumple') == 0 and
      gi(made['PADDING'], 'Billow') == 0)
check('Puffer: 5 stitched channels, no border folds or fans', int(gi(made['PUFFER'], 'Sections')) == 5 and
      gi(made['PUFFER'], 'Pinch') == 0 and gi(made['PUFFER'], 'Fan Mix') == 0)
check('Cotton: crumple creases on, Drape: big billows on', gi(made['COTTON'], 'Crumple') > 0 and
      gi(made['DRAPE'], 'Billow') > gi(made['COTTON'], 'Billow') * 3)


def evz(o):
    dg = C.evaluated_depsgraph_get()
    return np.array([v.co.z for v in o.evaluated_get(dg).data.vertices])


o = made['COTTON']
z1 = evz(o)
c0 = gi(o, 'Crumple')
cw.set_input(o, 'Crumple', 0.0)
cw.set_input(o, 'Billow', 0.0)
z0 = evz(o)
check('the crumple layer shapes the cloth', z0.shape == z1.shape and np.abs(z1 - z0).max() > c0 * 0.2,
      float(np.abs(z1 - z0).max()))
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
