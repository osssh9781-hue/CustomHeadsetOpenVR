"""0.24.76 Fix Mesh (like ZBrush's Fix Mesh), Make Quad / Quad Remesh on broken parts, the quads shown as wireframe,
Export with Quad Mesh / Client Look.  Broken parts are built the way Booleans, joins and exports leave them: a crack
(points on each other, not welded), slivers, a join with its shared wall left inside, a missing face."""
import math
import os
import tempfile

from _harness import bmesh, bpy, check, fresh, summary
from mathutils import Matrix, Quaternion, Vector

import mecha_lab
from mecha_lab import base_mesh as bmm, core_geometry as cg, cut_engine as ce, mesh_fix as mf
from mecha_lab import quad_field as qf, quad_remesh as qr, zbrush_bridge as zbb

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
S.mch_settings.auto_apply = True
PPU = 400.0
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


def select(*obs):
    for o in C.selected_objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    C.view_layer.objects.active = obs[-1]


def link(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    S.collection.objects.link(ob)
    return ob


def faults(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    out = mf.faults(bm)
    bm.free()
    return out


def broken_box(name, crack=True, slivers=True, wall=False, hole=False, offset=(0, 0, 0)):
    """A box with the faults asked for: ``crack`` = one face's corners duplicated (lying on the others, not welded),
    ``slivers`` = zero-area triangles along an edge, ``wall`` = a second box joined on with the shared wall left in,
    ``hole`` = a face deleted."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(offset))
    if wall:
        geom = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(Vector(offset) + Vector((1, 0, 0))))
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
        # the two boxes now share the wall at x = 0.5: two faces on the same 4 points -> keep one (the inside wall)
        keys = {}
        for f in list(bm.faces):
            k = frozenset(v.index for v in f.verts)
            if k in keys:
                bm.faces.remove(f)
            keys[k] = f
        del geom
    bm.faces.ensure_lookup_table()
    if crack:
        f = bm.faces[0]
        new = {v: bm.verts.new(v.co) for v in f.verts}
        loop = [new[v] for v in f.verts]
        bm.faces.remove(f)
        bm.faces.new(loop)
    if slivers:
        bm.edges.ensure_lookup_table()
        e = max(bm.edges, key=lambda e: e.verts[0].co.z + e.verts[1].co.z)
        bmesh.ops.subdivide_edges(bm, edges=[e], cuts=3)
        bm.faces.ensure_lookup_table()
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    if hole:
        bm.faces.ensure_lookup_table()
        bm.faces.remove(bm.faces[-1])
    bm.normal_update()
    return link(name, bm)


def cut_part(name):
    s = S.mch_base
    s.profile, s.height, s.bevel_width, s.bevel_segments, s.bevel_sides, s.offset = 'CHAMFER', 0.25, 0.04, 3, 'TOP', 0.0
    before = set(bpy.data.objects)
    bmm.perform_base(C, [ce.round_corners(rect(0, 0, 1.0, 0.6), 0.1 * PPU, 'ROUND', 6)], TOP)
    ob = [o for o in bpy.data.objects if o not in before][0]
    select(ob)
    dg = C.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    ob.modifiers.clear()
    ob.data = me
    cut.gn_finish, cut.gn_ramp, cut.depth_mode, cut.depth = 'NONE', False, 'SURFACE', 0.1
    ce.perform_closed(C, 'CUT', [ob], [rect(-0.15, 0.0, 0.35, 0.25)], TOP)
    ob.name = name
    return ob


# --- Fix Mesh -----------------------------------------------------------------------------------------------------
clear()
ob = broken_box('Crack', crack=True, slivers=True)
o0, m0 = faults(ob.data)
st = mf.fix_mesh(ob.data)
o1, m1 = faults(ob.data)
check('Fix Mesh: a crack (points on each other, not welded) -> closed', o0 > 0 and o1 == 0 and m1 == 0, (o0, m0, o1, m1, st))
check('Fix Mesh: the crack\'s points welded', st['welded'] >= 4, st)
bm = bmesh.new()
bm.from_mesh(ob.data)
check('Fix Mesh: the box keeps its volume (1.0)', abs(bm.calc_volume() - 1.0) < 1e-3, bm.calc_volume())
check('Fix Mesh: normals all outward', bm.calc_volume(signed=True) > 0.99, bm.calc_volume(signed=True))
bm.free()

clear()
bm = bmesh.new()                                       # a split n-gon's sliver: a zero-area triangle on an edge
bmesh.ops.create_cube(bm, size=1.0)
bm.edges.ensure_lookup_table()
e = bm.edges[0]
fa, fb = e.link_faces
a, b = e.verts
m = bm.verts.new((a.co + b.co) * 0.5)
for k, f in enumerate((fa, fb)):
    ring = [v for v in f.verts]
    i = ring.index(a)
    ring = ring[i:] + ring[:i]                          # a first
    bm.faces.remove(f)
    if k == 0:                                          # this side: the sliver a-m-b + the face as it was
        bm.faces.new([a, m, b] if ring[1] is b else [b, m, a])
        bm.faces.new(ring)
    else:                                               # the other side: m on its edge (a 5-gon)
        j = 1 if ring[1] is b else len(ring)
        bm.faces.new(ring[:j] + [m] + ring[j:])
ob = link('Sliver', bm)
st = mf.fix_mesh(ob.data)
check('Fix Mesh: zero-area triangles (split n-gon slivers) dissolved, closed', st['slivers'] >= 1
      and faults(ob.data) == (0, 0) and len(ob.data.polygons) == 6, (st, len(ob.data.polygons)))

clear()
ob = broken_box('Wall', crack=False, slivers=False, wall=True)
o0, m0 = faults(ob.data)
st = mf.fix_mesh(ob.data)
o1, m1 = faults(ob.data)
check('Fix Mesh: a join with its shared wall inside (3-face edges) -> the wall goes, closed',
      m0 == 4 and st['walls'] == 1 and (o1, m1) == (0, 0), (o0, m0, st))
check('Fix Mesh: two boxes joined = 10 outer faces', len(ob.data.polygons) == 10, len(ob.data.polygons))

clear()
ob = broken_box('Hole', crack=False, slivers=False, hole=True)
st = mf.fix_mesh(ob.data)
check('Fix Mesh: a missing face is filled', faults(ob.data) == (0, 0) and st['filled'] == 1, st)

clear()
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=4, y_segments=4, size=1.0)
plate = link('Plate', bm)
n0 = len(plate.data.polygons)
st = mf.fix_mesh(plate.data)
check('Fix Mesh: an open plate keeps its border (a big hole is not capped)', len(plate.data.polygons) == n0
      and st['open_after'] == st['open_before'] > 0, st)
st = mf.fix_mesh(plate.data, all_holes=True)
check('Fix Mesh: Close All Holes caps it', st['open_after'] == 0, st)

clear()
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
cube = link('Clean', bm)
st = mf.fix_mesh(cube.data)
check('Fix Mesh: a clean box is left as it is', len(cube.data.polygons) == 6 and not any(
    st[k] for k in ('welded', 'slivers', 'repeated', 'walls', 'fins', 'filled')), st)
check('Fix Mesh: needs_fix tells broken from clean', not mf.needs_fix(cube.data)
      and mf.needs_fix(broken_box('B2').data))

clear()
ob = broken_box('Op', crack=True, slivers=True, wall=True)
select(ob)
r = bpy.ops.mch.fix_mesh()
check('Fix Mesh button (mch.fix_mesh) repairs the selected mesh', r == {'FINISHED'} and faults(ob.data) == (0, 0), r)
ob2 = broken_box('Op2', crack=True, offset=(3, 0, 0))
select(ob2)
r = bpy.ops.mch.mesh_tool(action='FIX_MESH')
check('Mesh Tools: Fix Mesh', r == {'FINISHED'} and faults(ob2.data) == (0, 0), r)

# --- Make Quad (old tool) on a broken part --------------------------------------------------------------------------
clear()
part = cut_part('Broken')
bm = bmesh.new()
bm.from_mesh(part.data)
bm.faces.ensure_lookup_table()
f = max(bm.faces, key=lambda f: f.calc_area())
new = {v: bm.verts.new(v.co) for v in f.verts}                 # a crack along the biggest face
loop = [new[v] for v in f.verts]
bm.faces.remove(f)
bm.faces.new(loop)
bm.to_mesh(part.data)
bm.free()
check('broken part: has open sides before', faults(part.data)[0] > 0, faults(part.data))
qs = S.mch_quadremesh
qs.method, qs.faces = 'PATCH', 1500
select(part)
r = bpy.ops.mch.quad_remesh()
res = C.active_object
check('Make Quad (Patch) on a broken part: repaired first and made (was refused: "open / non-manifold edges")',
      r == {'FINISHED'} and res.name.endswith('_Quad') and len(res.data.polygons) > 200, (r, res.name))
check('Make Quad result: closed', faults(res.data) == (0, 0), faults(res.data))
check('Make Quad result: shown as wireframe', res.show_wire and res.show_all_edges)
walled = broken_box('Walled', crack=False, slivers=False, wall=True, offset=(5, 0, 0))
qr.prepare(walled.data.copy(), math.radians(30))     # (a crack its own merge closes; an inside wall it can't)
check('Make Quad: the repair is noted ("Fix Mesh first")', bool(qr.FIXED) and qr.FIXED['multi_before'] > 0, qr.FIXED)

# Flow that QuadriFlow gives up on: Patch instead, said so
clear()
part = cut_part('FlowFail')
qs.method = 'FLOW'
orig = qr._flow


def _fail(*_a, **_k):
    raise RuntimeError('QuadriFlow could not remesh this part (try more Faces or a smaller Edge Angle).')


qr._flow = _fail
try:
    me, kept, miss, note = qr.build_mesh(C, part, qs)
finally:
    qr._flow = orig
check('Make Quad Flow: QuadriFlow failing -> the Patch method instead, with a note',
      len(me.polygons) > 200 and 'used Patch instead' in note, note)
bpy.data.meshes.remove(me)

# --- Quad Remesh (new engine) on a broken part ----------------------------------------------------------------------
clear()
ob = broken_box('NewQR', crack=True, slivers=True, wall=True)
mesh_name = ob.data.name
msg = qf.remesh_object(ob, 1500)
check('Quad Remesh on a broken part: a repaired copy is remeshed ("Fix Mesh first")', 'Fix Mesh first' in msg
      and len(ob.data.polygons) > 500, msg)
check('Quad Remesh result: closed', faults(ob.data) == (0, 0), faults(ob.data))
check('Quad Remesh result: shown as wireframe', ob.show_wire and ob.show_all_edges)
check('Quad Remesh: the repaired copy is not left in the file', not any(
    m.name.startswith(mesh_name + '.') and m.users == 0 for m in bpy.data.meshes), [m.name for m in bpy.data.meshes])
clear()
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
ob = link('CleanQR', bm)
msg = qf.remesh_object(ob, 600)
check('Quad Remesh on a clean part: no repair step', 'Fix Mesh' not in msg and len(ob.data.polygons) > 300, msg)

# --- Export: Quad Mesh / Client Look --------------------------------------------------------------------------------
clear()
a = cut_part('PartA')
b = broken_box('PartB', crack=True, slivers=True, wall=True, offset=(3, 0, 0))
bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.05, depth=0.1, location=(-2, 0, 0))
c = C.active_object
c.name = 'Screw'
work = {o.name: (len(o.data.polygons), o.data.name) for o in (a, b, c)}
d = tempfile.mkdtemp(prefix='mch_export_')
path = os.path.join(d, 'quad.fbx')
select(a, b, c)
r = bpy.ops.mch.export_mesh(filepath=path, scope='SELECTED', file_format='FBX', quad_mesh=True, quad_size=1.0)
check('Export Quad Mesh: FBX written', r == {'FINISHED'} and os.path.isfile(path), r)
check('Export Quad Mesh: the Blender meshes stay as they were', all(
    len(bpy.data.objects[n].data.polygons) == f and bpy.data.objects[n].data.name == m for n, (f, m) in work.items()))
check('Export Quad Mesh: no temporary object left', sorted(o.name for o in bpy.data.objects) == sorted(work))


def reimport(fp):
    clear()
    bpy.ops.import_scene.fbx(filepath=fp)
    out = {}
    for o in bpy.data.objects:
        if o.type != 'MESH':
            continue
        bm = bmesh.new()
        bm.from_mesh(o.data)
        q = sum(1 for f in bm.faces if len(f.verts) == 4)
        out[o.name] = (len(bm.faces), q / max(1, len(bm.faces)), mf.faults(bm),
                       sum(1 for f in bm.faces if f.smooth), bm.calc_volume())
        bm.free()
    return out


got = reimport(path)
check('Export Quad Mesh: all three parts in the file', sorted(got) == sorted(work), sorted(got))
check('Export Quad Mesh: mostly quads (>= 85 %; the 77-face screw >= 70 %)',
      got['PartA'][1] >= 0.85 and got['PartB'][1] >= 0.85 and got['Screw'][1] >= 0.7,
      {k: round(v[1], 2) for k, v in got.items()})
check('Export Quad Mesh: closed (the broken part repaired on the way)', all(v[2] == (0, 0) for v in got.values()),
      {k: v[2] for k, v in got.items()})
check('Export Quad Mesh: one quad size for all - the small screw gets few faces',
      got['Screw'][0] < got['PartA'][0] / 4, {k: v[0] for k, v in got.items()})
quad_faces = {k: v[0] for k, v in got.items()}

clear()
a = cut_part('PartA')
select(a)
path2 = os.path.join(d, 'client.fbx')
r = bpy.ops.mch.export_mesh(filepath=path2, scope='SELECTED', file_format='FBX', quad_mesh=True, quad_size=1.0,
                            client_look=True, client_subdiv=1)
got2 = reimport(path2)
v = got2.get('PartA')
check('Export Client Look: written, about 4x the faces (bevel + Subdivide 1 baked)', r == {'FINISHED'} and v is not None
      and v[0] > 3 * quad_faces['PartA'], (r, v, quad_faces['PartA']))
check('Export Client Look: every face smooth, closed', v is not None and v[3] == v[0] and v[2] == (0, 0), v)

summary()
