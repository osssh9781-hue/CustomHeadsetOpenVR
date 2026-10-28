"""0.24.76 Facet carve: Base Mesh Alt carve (Height / Ramp) and Cut Ramp over a bent, faceted surface get one floor
plane per flat face (a sharp crease where two meet) instead of a dense grid with smoothed normals; Steep Edges Even /
Limit; anything it is not for falls back to the old carve."""
import math
from types import SimpleNamespace

from _harness import bmesh, bpy, check, fresh, summary
from mathutils import Quaternion, Vector
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import base_mesh as bmm, core_geometry as cg, cut_engine as ce, facet_carve as fc
from mecha_lab import panel_capture as pc, surface_draw as sd, ui_tool_settings as uts

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
S.mch_settings.auto_apply = True
PPU = 1000.0
TOP = cg.OrthoProjector(Quaternion(), center=Vector((0, 0, 0)), pixels_per_unit=PPU)
cut = S.mch_cut
cut.targets = 'ACTIVE'


def P(x, y):
    return (500 + x * PPU, 500 + y * PPU)


def rect(cx, cy, w, h):
    return ce.rect_loop(P(cx - w / 2, cy - h / 2), P(cx + w / 2, cy + h / 2))


def clear():
    if C.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


def select(ob):
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob


def roof(name='Roof', ridge=0.45):
    """A prism with a ridge along Y: two roof faces 26.6 deg (ridge 0.45) over walls 0.2 high."""
    bm = bmesh.new()
    sec = [(-0.5, 0.0), (0.5, 0.0), (0.5, 0.2), (0.0, ridge), (-0.5, 0.2)]
    a = [bm.verts.new((x, -0.4, z)) for x, z in sec]
    b = [bm.verts.new((x, 0.4, z)) for x, z in sec]
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    for i in range(len(sec)):
        j = (i + 1) % len(sec)
        bm.faces.new([a[i], a[j], b[j], b[i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    S.collection.objects.link(ob)
    select(ob)
    return ob


def chamfer_block(name='Block'):
    """A Base Mesh block with a wide 45 deg chamfer round the top (facets: top, chamfer, side)."""
    s = S.mch_base
    s.profile, s.height, s.bevel_width, s.bevel_segments, s.bevel_sides, s.offset = 'CHAMFER', 0.3, 0.12, 1, 'TOP', 0.0
    before = set(bpy.data.objects)
    bmm.perform_base(C, [rect(0, 0, 1.0, 0.8)], TOP)
    ob = [o for o in bpy.data.objects if o not in before][0]
    select(ob)
    dg = C.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    ob.modifiers.clear()
    ob.data = me
    ob.name = name
    return ob


def settings(steep='EVEN', profile='SQUARE'):
    return SimpleNamespace(profile=profile, edge=0.35, sink=0.0, edge_abs=None, fill_res=28, segments=4,
                           fine=20 / 28.0, steep=steep)


def info(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    vol = bm.calc_volume()
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    return len(ob.data.polygons), nm, vol, bvh


def depth_at(bvh0, bvh1, x, y):
    o, d = Vector((x, y, 5.0)), Vector((0, 0, -1))
    h0, h1 = bvh0.ray_cast(o, d), bvh1.ray_cast(o, d)
    if h0[0] is None or h1[0] is None:
        return None
    return h1[0].z - h0[0].z, h0[0].z


def carve(ob, loop, depth, st, ramp=None):
    groups = cg.prepare_loops([loop])
    sd.carve_area(C, ob, groups, TOP, st, depth, False, ramp=ramp)
    return dict(fc.LAST)


# --- roof: two faces, Base Mesh Height carve across the ridge ------------------------------------------------------
clear()
ob = roof()
n0, _nm, v0, bvh0 = info(ob)
D = 0.05
last = carve(ob, rect(0, 0, 0.4, 0.3), D, settings())
n1, nm1, v1, bvh1 = info(ob)
check('roof, Height: the facet carve (2 faces under the outline)', last.get('path') == 'facet' and last.get('facets') == [2],
      last)
check('roof, Height: closed, few faces (was ~350 with the grid)', nm1 == 0 and n1 < 60, (n1, nm1))
slope = math.atan2(0.25, 0.5)
errs = []
for x in (-0.15, -0.08, 0.08, 0.15):
    for y in (-0.08, 0.0, 0.08):
        r = depth_at(bvh0, bvh1, x, y)
        if r is not None:
            errs.append(abs(-r[0] * math.cos(slope) - D) / D)
check('roof, Height: the floor is the depth below each face (measured across it) within 1 %',
      len(errs) == 12 and max(errs) < 0.01, [round(e, 4) for e in errs])
r_ridge = depth_at(bvh0, bvh1, 0.0, 0.0)
check('roof, Height: a sharp crease under the ridge (depth / cos there too)',
      r_ridge is not None and abs(-r_ridge[0] * math.cos(slope) - D) / D < 0.02, r_ridge)
check('roof, Height: the volume taken = outline area x depth (about)', abs((v0 - v1) - 0.4 * 0.3 * D / math.cos(slope))
      / (0.4 * 0.3 * D) < 0.08, (v0 - v1, 0.4 * 0.3 * D / math.cos(slope)))

# --- roof: Ramp (straight) and Ramp Soft ---------------------------------------------------------------------------
clear()
ob = roof()
loop = rect(0, 0, 0.4, 0.3)
edge = (loop[0], loop[1])
last = carve(ob, loop, D, settings(), ramp=(edge[0], edge[1], 1.0, 0.0))
n1, nm1, _v, _b = info(ob)
check('roof, Ramp: the facet carve, closed, few faces', last.get('path') == 'facet' and nm1 == 0 and n1 < 80, (last, n1))
clear()
ob = roof()
last = carve(ob, loop, D, settings(), ramp=(edge[0], edge[1], 1.0, 0.5))
n1, nm1, _v, _b = info(ob)
check('roof, Ramp Soft 0.5: the facet carve, closed, under 1,000 faces (the grid made ~6,000)',
      last.get('path') == 'facet' and nm1 == 0 and n1 < 1000, (last, n1))

# --- Steep Edges: Even / Limit -------------------------------------------------------------------------------------
vols = {}
for mode in ('EVEN', 'LIMIT'):
    clear()
    ob = chamfer_block()
    _n, _nm, v0, bvh0 = info(ob)
    last = carve(ob, rect(0.42, 0.0, 0.2, 0.2), 0.04, settings(mode))
    n1, nm1, v1, bvh1 = info(ob)
    vols[mode] = (v0 - v1, last.get('path'), nm1, last.get('facets'))
check('Steep Edges: across the chamfer both ways use the facet carve and stay closed',
      all(v[1] == 'facet' and v[2] == 0 for v in vols.values()), vols)
check('Steep Edges: Limit takes less off a steep side than Even', vols['LIMIT'][0] < 0.9 * vols['EVEN'][0], vols)
vols = {}
for mode in ('EVEN', 'LIMIT'):
    clear()
    ob = roof()
    _n, _nm, v0, _b = info(ob)
    carve(ob, rect(0, 0, 0.4, 0.3), D, settings(mode))
    vols[mode] = v0 - info(ob)[2]
check('Steep Edges: two equal roof faces - Limit = Even (both seen as straight)',
      abs(vols['LIMIT'] - vols['EVEN']) < 1e-4 * max(vols.values()) + 1e-9, vols)
vols = {}
for mode in ('EVEN', 'LIMIT'):
    clear()
    ob = chamfer_block()
    _n, _nm, v0, _b = info(ob)
    carve(ob, rect(-0.1, 0.0, 0.3, 0.3), 0.04, settings(mode))
    vols[mode] = v0 - info(ob)[2]
check('Steep Edges: on one flat face only - Limit = Even', abs(vols['LIMIT'] - vols['EVEN']) < 1e-6, vols)

# --- falls back to the old carve -----------------------------------------------------------------------------------
clear()
bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=0.5)
ob = C.active_object
last = carve(ob, rect(0, 0, 0.3, 0.3), 0.03, settings())
check('a curved, dense surface: the old carve (more facets than MAX_FACETS)', last.get('path') == 'old'
      and 'facets' in (last.get('reason') or ''), last)
check('... and it still carved', info(ob)[1] == 0 and len(ob.data.polygons) > 2000, len(ob.data.polygons))
clear()
ob = roof()
s2 = settings(profile='CHAMFER')
s2.edge_abs = 0.01
last = carve(ob, rect(0, 0, 0.4, 0.3), D, s2)
check('a Chamfer edge: the old carve', last.get('path') == 'old' and last.get('reason') == 'CHAMFER', last)
fc.ENABLED = False
clear()
ob = roof()
last = carve(ob, rect(0, 0, 0.4, 0.3), D, settings())
fc.ENABLED = True
check('switched off (tests): the old carve, and it still works', last.get('path') == 'old' and info(ob)[1] == 0, last)

# --- through the tools: Base Mesh Alt carve, Cut Ramp, the Steep Edges settings ------------------------------------
check('settings: Base Mesh carve_steep and Cut gn_ramp_steep, Even by default',
      S.mch_base.carve_steep == 'EVEN' and cut.gn_ramp_steep == 'EVEN')
clear()
ob = roof()
p = bmm.scene_defaults(C)
p.sketch, p.profile, p.alt_mode, p.carve_depth = False, 'FLAT', 'HEIGHT', D
msg = bmm.carve_surface(C, [rect(0, 0, 0.4, 0.3)], TOP, p, targets=[ob], live=False)
check('Base Mesh Alt carve (Height) on the roof: the facet carve', fc.LAST.get('path') == 'facet'
      and info(ob)[1] == 0, (msg, fc.LAST))
clear()
ob = chamfer_block()
cut.gn_finish, cut.gn_ramp, cut.depth = 'NONE', True, 0.04
cut.gn_ramp_soft, cut.gn_ramp_length = 0.0, 1.0
loop = rect(0.42, 0.0, 0.2, 0.2)
v0 = info(ob)[2]
ce.cut_ramp(C, [ob], [loop], TOP, live=False)
v_even = v0 - info(ob)[2]
path_even = fc.LAST.get('path')
clear()
ob = chamfer_block()
cut.gn_ramp_steep = 'LIMIT'
v0 = info(ob)[2]
ce.cut_ramp(C, [ob], [loop], TOP, live=False)
v_lim = v0 - info(ob)[2]
cut.gn_ramp_steep = 'EVEN'
cut.gn_ramp = False
check('Cut Ramp across the chamfer: the facet carve, Limit takes less than Even',
      path_even == 'facet' and fc.LAST.get('path') == 'facet' and v_lim < v_even, (v_even, v_lim))
cut.gn_ramp = True
tree = pc.capture(lambda lay, ctx: uts.draw_gn_edge(lay, ctx, 'CUT'), C)
cut.gn_ramp = False
check('Cut panel (GN Edge > Ramp) shows Steep Edges', any(n.kind == 'prop' and n.prop == 'gn_ramp_steep'
                                                          for n in pc.walk(tree)))
sp = bmm.scene_defaults(C)                        # (the settings the panel shows now)
sp.alt_mode, sp.profile = 'HEIGHT', 'FLAT'
tree = pc.capture(lambda lay, ctx: uts._draw_base_sketch(lay, ctx, bmm), C)
check('Base Mesh panel (Alt: Height) shows Steep Edges', any(n.kind == 'prop' and n.prop == 'carve_steep'
                                                             for n in pc.walk(tree)), tree.opts.get('error'))

summary()
