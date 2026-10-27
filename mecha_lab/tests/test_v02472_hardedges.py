"""0.24.72 Hard Edges (ZBrush shelf): find the hard edges, crease them, a live adjustable bevel, subdivide, apply / clear."""
import math

import numpy as np

from _harness import bmesh, bpy, check, fresh, summary

import mecha_lab
from mecha_lab import fast_decimate as fd, hard_edges as he, panel_capture as pc, quad_field as qf, zb_sculpt as zs
from mecha_lab import zb_ui as zu

mecha_lab.register()
fresh()
C = bpy.context
zb = C.scene.mch_zb


def boolean(ob, cutter):
    m = ob.modifiers.new('b', 'BOOLEAN')
    m.object = cutter
    m.operation = 'DIFFERENCE'
    m.solver = 'EXACT'
    with C.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter)


def box(loc, size, name='c'):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = C.active_object
    o.scale = size
    o.name = name
    bpy.ops.object.transform_apply(scale=True)
    return o


def part(name='Block', voxel=0.012):
    p = box((0, 0, 0), (1.0, 0.6, 0.4), name)
    boolean(p, box((0.55, 0, 0.35), (0.5, 0.7, 0.2)))
    boolean(p, box((-0.1, 0, 0.4), (0.08, 0.7, 0.15)))
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.18, depth=2, location=(-0.5, 0, 0),
                                        rotation=(math.pi / 2, 0, 0))
    boolean(p, C.active_object)
    p.data.remesh_voxel_size = voxel
    with C.temp_override(object=p, active_object=p):
        bpy.ops.object.voxel_remesh()
    C.view_layer.objects.active = p
    return p


def edge_attr(me, name, dtype=float):
    a = me.attributes.get(name)
    out = np.zeros(len(me.edges), dtype)
    if a is not None:
        a.data.foreach_get('value', out)
    return out


def evaluated(ob):
    dg = C.evaluated_depsgraph_get()
    e = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(e)
    return me


def closed(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    bad = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    bm.free()
    return bad


def creases(V, T, deg=30.0):
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-30)
    e = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
    f = np.tile(np.arange(len(T)), 3)
    e.sort(1)
    key = e[:, 0] * len(V) + e[:, 1]
    o = np.argsort(key, kind='stable')
    key, e, f = key[o], e[o], f[o]
    same = np.nonzero(key[1:] == key[:-1])[0]
    sharp = (fn[f[same]] * fn[f[same + 1]]).sum(1) < math.cos(math.radians(deg))
    s = e[same[sharp]]
    return (V[s[:, 0]] + V[s[:, 1]]) * 0.5


def arrays(me):
    V = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', V)
    me.calc_loop_triangles()
    T = np.empty(len(me.loop_triangles) * 3, np.int64)
    me.loop_triangles.foreach_get('vertices', T)
    return V.reshape(-1, 3), T.reshape(-1, 3)


def near_share(pts, me, mask, tol):
    """Share of ``pts`` within ``tol`` of an edge of ``me`` picked by ``mask``."""
    ev = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get('vertices', ev)
    ev = ev.reshape(-1, 2)[mask]
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    a, b = co[ev[:, 0]], co[ev[:, 1]]
    ab = b - a
    ll = np.maximum((ab * ab).sum(1), 1e-30)
    hit = 0
    for p in pts:
        t = np.clip(((p - a) * ab).sum(1) / ll, 0, 1)
        hit += np.linalg.norm(a + ab * t[:, None] - p, axis=1).min() < tol
    return hit / max(len(pts), 1)


def defaults():
    for k in ('he_angle', 'he_merge', 'he_crease', 'he_outer', 'he_bevel', 'he_width', 'he_segments', 'he_profile',
              'he_subdiv', 'he_normals', 'he_client'):
        zb.property_unset(k)


# --- a cube: the exact case -----------------------------------------------------------------------------------------
defaults()
cube = box((0, 0, 0), (1, 1, 1), 'Cube')
n, f0, f1 = he.find(cube, zb)
me = cube.data
sharp = he.hard_flags(me)
check('Cube: Find Edges finds its 12 edges: creased, with a bevel weight', n == 12 and sharp.sum() == 12
      and (edge_attr(me, 'crease_edge') == 1.0).sum() == 12 and (edge_attr(me, 'bevel_weight_edge') == 1.0).sum() == 12,
      (n, int(sharp.sum())))
check('... Client Look (default): nothing marked Sharp for the display (the mesh alone gives the look)',
      zb.he_client and me.attributes.get('sharp_edge') is None)
check('... every face shaded smooth (the sharp edges do the hard look), the object remembers it', all(
    p.use_smooth for p in me.polygons) and he.KEY in cube)
zb.he_width = 0.1
zb.he_segments = 1
he.set_live(cube, zb)
check('Live modifiers at the end: Bevel (no Subdivide at 0, no Weighted Normals: custom normals are off by default)',
      [m.name for m in cube.modifiers] == [he.BEVEL] and not cube.modifiers[he.BEVEL].harden_normals,
      [m.name for m in cube.modifiers])
ev = evaluated(cube)
d = tuple(round(x, 4) for x in ev.vertices[0].co)
co = np.array([v.co[:] for v in ev.vertices])
check('Width 0.1, 1 segment: a chamfer (6 + 12 + 8 faces), the size stays 2 x 2 x 2, closed', len(ev.polygons) == 26
      and np.allclose(co.max(0), 1.0) and np.allclose(co.min(0), -1.0) and closed(ev) == 0, len(ev.polygons))
check('... the chamfer starts 0.1 in from each edge', np.isclose(np.sort(np.abs(co[:, 0]))[0], 0.9, atol=1e-4))
bpy.data.meshes.remove(ev)
C.view_layer.objects.active = cube
zb.he_segments = 3                                     # (the shelf: the update follows right away)
check('Changing Segments on the shelf updates the live bevel at once', cube.modifiers[he.BEVEL].segments == 3)
zb.he_width = 0.05
check('... and Width', abs(cube.modifiers[he.BEVEL].width - 0.05) < 1e-6)
zb.he_bevel = False
zb.he_subdiv = 2
ev = evaluated(cube)
co = np.array([v.co[:] for v in ev.vertices])
check('Bevel off + Subdivide 2: the creases keep the cube a cube (corners at 1, flat sides)', he.BEVEL not in
      cube.modifiers and np.allclose(np.abs(co).max(0), 1.0) and (np.abs(np.abs(co).max(1) - 1.0) < 1e-5).all()
      and len(ev.polygons) == 96, len(ev.polygons))
bpy.data.meshes.remove(ev)
zb.he_crease = False
ev = evaluated(cube)
co = np.array([v.co[:] for v in ev.vertices])
check('Crease off: Subdivide rounds it', np.abs(co).max() < 0.95, float(np.abs(co).max()))
bpy.data.meshes.remove(ev)
zb.he_normals = True
check('Weighted Normals on: that modifier comes (last)', cube.modifiers[-1].name == he.NORMALS)
zb.he_normals = False
check('... off: it goes', he.NORMALS not in cube.modifiers)
zb.he_client = False
check('Client Look off: the hard edges are marked Sharp for Blender\'s display', edge_attr(cube.data, 'sharp_edge',
                                                                                         bool).sum() == 12)
zb.he_client = True
check('... on again: the Sharp marks go', cube.data.attributes.get('sharp_edge') is None)
defaults()
he.set_live(cube, zb)
he.clear(cube)
check('Clear: marks and live modifiers gone', len(cube.modifiers) == 0 and he.hard_flags(cube.data).sum() == 0
      and cube.data.attributes.get('bevel_weight_edge') is None and he.KEY not in cube)

# --- Outer Only on an L shape ---------------------------------------------------------------------------------------
L = box((0, 0, 0), (1, 1, 1), 'L')
boolean(L, box((1, 0, 1), (1, 2, 1)))
he.find(L, zb)
zb.he_outer = True
C.view_layer.objects.active = L
he.live_update(zb, C)
me = L.data
w = edge_attr(me, 'bevel_weight_edge')
sharp = he.hard_flags(me)
check('Outer Only: the inside corner of an L gets no bevel, the outside edges do', sharp.sum() > w.sum() > 0
      and (sharp & (w == 0)).sum() >= 1, (int(sharp.sum()), float(w.sum())))
zb.he_outer = False
check('... off again: all hard edges bevelled', edge_attr(L.data, 'bevel_weight_edge').sum() == sharp.sum())
bpy.data.objects.remove(L)
defaults()

# --- a decimated hard-surface part (the workflow: DynaMesh -> Decimate -> Find Edges) -------------------------------
ob = part()
V0, T0 = arrays(ob.data)
cr = creases(V0, T0)
fd.decimate_object(ob, 5)
tris0 = len(ob.data.polygons)
n, f0, f1 = he.find(ob, zb)
me = ob.data
sharp = he.hard_flags(me)
check('Decimated part: hard edges found, Merge Flats joins the flat triangles into big faces (fewer polygons)',
      n > 50 and f1 < 0.6 * f0, (n, f0, f1))
check('... closed', closed(me) == 0)
size = 2.0
check('... the hard edges sit on the original creases (95 %+ of the crease within 0.5 % of the size)',
      near_share(cr, me, sharp, 0.005 * size) > 0.95, near_share(cr, me, sharp, 0.005 * size))
from mathutils.kdtree import KDTree
kd = KDTree(len(cr))
for i, p in enumerate(cr.tolist()):
    kd.insert(p, i)
kd.balance()
ev2 = np.empty(len(me.edges) * 2, np.int64)
me.edges.foreach_get('vertices', ev2)
ev2 = ev2.reshape(-1, 2)[sharp]
co1 = np.empty(len(me.vertices) * 3)
me.vertices.foreach_get('co', co1)
co1 = co1.reshape(-1, 3)
far = []
for a, b in ev2:
    for t in (0.25, 0.5, 0.75):                         # points along each hard edge
        far.append(kd.find((co1[a] * (1 - t) + co1[b] * t).tolist())[2])
far = np.array(far)
check('... and every one of them runs along a real crease of the original (none on flat or round parts)',
      len(far) > 0 and far.max() < 0.03, round(float(far.max()), 4))
zb.he_width = 0.01
he.set_live(ob, zb)
ev = evaluated(ob)
check('... the live bevel makes a closed mesh with more faces', closed(ev) == 0 and len(ev.polygons) > len(
    me.polygons), (len(ev.polygons), len(me.polygons)))
bpy.data.meshes.remove(ev)
zb.he_merge = False
fd.decimate_object(ob, 50)
k = len(ob.data.polygons)
he.find(ob, zb)
check('Merge Flats off: the triangles stay', len(ob.data.polygons) == k)
bpy.data.objects.remove(ob)
defaults()

# --- a quad mesh (Quad Remesh): quads stay quads -------------------------------------------------------------------
ob = part('Quads', 0.02)
qf.remesh_object(ob, 2000)
q0 = len(ob.data.polygons)
quads0 = sum(len(p.vertices) == 4 for p in ob.data.polygons)
n, f0, f1 = he.find(ob, zb)
check('Quad Remesh output: Find Edges keeps the quads (Merge Flats only joins triangle meshes), hard edges found',
      f1 == q0 and sum(len(p.vertices) == 4 for p in ob.data.polygons) == quads0 and n > 50, (n, f0, f1))
zb.he_subdiv = 1
he.set_live(ob, zb)
ev = evaluated(ob)
check('... Subdivide on the quads: closed, 4x the faces after the bevel', closed(ev) == 0
      and len(ev.polygons) > 4 * q0, (len(ev.polygons), q0))
bpy.data.meshes.remove(ev)
C.view_layer.objects.active = ob
k = he.apply_live(C, ob, zb)
me = ob.data
check('Apply: the live modifiers baked into the mesh', k == 2 and len(ob.modifiers) == 0
      and len(me.polygons) > 4 * q0, (k, len(me.polygons)))
check('... Client Look: a plain mesh - no Sharp / Crease / Bevel Weight / custom normals, every face smooth',
      all(me.attributes.get(n) is None for n in ('sharp_edge', 'crease_edge', 'bevel_weight_edge', he.HARD))
      and not getattr(me, 'has_custom_normals', False) and all(p.use_smooth for p in me.polygons)
      and closed(me) == 0)
bpy.data.objects.remove(ob)
defaults()

# --- the ZBrush shelf -----------------------------------------------------------------------------------------------
ob = part('ZB', 0.02)
fd.decimate_object(ob, 5)
zs.on = lambda c: getattr(c, 'mode', '') == 'SCULPT'
bpy.ops.object.mode_set(mode='SCULPT')
root = pc.capture(zu.draw_tool_shelf, C)
boxes = {}
for nd in pc.walk(root):
    if nd.kind == 'box':
        lab = next((c.opts.get('text') for c in nd.children if c.kind == 'label'), None)
        acts = {x.opts.get('props', {}).get('action') for x in pc.walk(nd) if x.kind == 'op'}
        props = {x.prop for x in pc.walk(nd) if x.kind == 'prop'}
        boxes[lab] = (acts, props)
hb = boxes.get('Hard Edges')
check('Hard Edges has its own box on the ZBrush shelf: Find Edges + Angle, Merge Flats / Crease / Outer Only, '
      'Bevel + Width, Segments / Shape, Subdivide / Client Look, Weighted Normals, Apply / Clear',
      hb is not None and {'HE_FIND', 'HE_APPLY', 'HE_CLEAR'} <= hb[0] and {
          'he_angle', 'he_merge', 'he_crease', 'he_outer', 'he_bevel', 'he_width', 'he_segments', 'he_profile',
          'he_subdiv', 'he_normals', 'he_client'} <= hb[1], hb)
check('Defaults: 30 degrees, Merge Flats, Crease, Bevel 2 segments, Client Look, no Weighted Normals, no Subdivide',
      abs(math.degrees(zb.he_angle) - 30) < 1e-4 and zb.he_merge and zb.he_crease and zb.he_bevel
      and zb.he_segments == 2 and zb.he_client and not zb.he_normals and zb.he_subdiv == 0 and not zb.he_outer)
n0 = len(ob.data.polygons)
bpy.ops.ed.undo_push(message='before')
r = bpy.ops.mch.zb_action(action='HE_FIND')
ob = bpy.data.objects['ZB']
check('Find Edges on the shelf: marks + live bevel, back in Sculpt Mode', r == {'FINISHED'} and C.mode == 'SCULPT'
      and he.BEVEL in ob.modifiers and he.hard_flags(ob.data).sum() > 0,
      (C.mode, [m.name for m in ob.modifiers]))
check('... a recovery copy is made before Find Edges / Apply (risky steps)', {'HE_FIND', 'HE_APPLY'} <= zs.RISKY)
zb.he_width = 0.02
check('A shelf setting drives the SubTool\'s live bevel in Sculpt Mode', abs(ob.modifiers[he.BEVEL].width - 0.02)
      < 1e-6)
bpy.ops.ed.undo()
ob = bpy.data.objects['ZB']
check('Ctrl+Z: the polygons, marks and modifiers as before, still in Sculpt Mode', len(ob.data.polygons) == n0
      and he.BEVEL not in ob.modifiers and C.mode == 'SCULPT', (len(ob.data.polygons), n0, C.mode))
bpy.ops.mch.zb_action(action='HE_FIND')
ob = bpy.data.objects['ZB']
r = bpy.ops.mch.zb_action(action='HE_APPLY')
ob = bpy.data.objects['ZB']
check('Apply on the shelf: baked, no live modifiers, the settings no longer drive it', len(ob.modifiers) == 0
      and he.KEY not in ob and C.mode == 'SCULPT')
zb.he_width = 0.05
check('... (a setting change afterwards adds nothing)', len(ob.modifiers) == 0)
bpy.ops.mch.zb_action(action='HE_CLEAR')
ob = bpy.data.objects['ZB']
check('Clear on the shelf: the marks go', he.hard_flags(ob.data).sum() == 0)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=8)
big = C.active_object
bpy.ops.object.mode_set(mode='SCULPT')
msg = zs.run(C, 'HE_FIND')
check('A DynaMesh-size mesh (300k+ polygons): it says to Decimate / Quad Remesh first (nothing changed)',
      'Decimate or Quad Remesh first' in msg and he.KEY not in big, msg)

summary()
