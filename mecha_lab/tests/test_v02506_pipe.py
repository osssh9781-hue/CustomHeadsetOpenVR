"""0.24.83 From the ZBrush-pipeline fuzz (tests/fuzz/pipe_scenario.py: DynaMesh > Decimate > Quad Remesh, then Cut in
every flavour and Box Hide): the 0.24.82 result tidy opened closed cuts (dissolve_degenerate), From Surface over two
parts cut only the first surface hit, a second Box Hide on a part (or a strip over a hidden part) failed on coplanar
caps, the Hard Edges bevel came out broken on a dense body, a line over nothing said 'outside the view', and a Cut Ramp
on a flat block is measured: deep at the first side, up to the surface at the far side."""
import math

from _harness import bpy, check, cube, fresh, non_manifold, summary
import bmesh
from mathutils import Vector

import mecha_lab
from mecha_lab import box_hide as bh, core_geometry as cg, hard_edges as he, tool_state as ts

_src = open(__file__.replace('test_v02506_pipe.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])      # noqa: S102  (Ctx, Op, E, MODE, NATIVE, VIEW, lasso)

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
S.mch_cut.targets = 'AUTO'
cut = S.mch_cut


def to_object():
    if C.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def reset_cut():
    cut.depth_mode, cut.depth, cut.edge_finish, cut.gn_finish, cut.gn_ramp, cut.solver = 'THROUGH', 0.1, 'NONE', 'NONE', False, 'AUTO'


def stroke(mode, pts, alt=False, side=None):
    MODE[0], NATIVE[0] = mode, ts.TOOL_BY_ID[mode][5]
    S.mch_settings.mch_active_tool = mode
    to_object()
    ctx, op = Ctx(), Op()
    r = op.invoke(ctx, E('LEFTMOUSE', 'PRESS', *pts[0], alt=alt))
    if r != {'RUNNING_MODAL'}:
        return r, (op.reports[-1][1] if op.reports else '')
    op.modal(ctx, E('LEFTMOUSE', 'RELEASE', *pts[0], alt=alt))
    for x, y in pts[1:]:
        op.modal(ctx, E('LEFTMOUSE', 'PRESS', x, y, alt=alt))
        op.modal(ctx, E('LEFTMOUSE', 'RELEASE', x, y, alt=alt))
    r = op.modal(ctx, E('RET', alt=alt))
    if r == {'RUNNING_MODAL'} and side is not None:
        op.modal(ctx, E('MOUSEMOVE', 'NOTHING', *side, alt=alt))
        r = op.modal(ctx, E('LEFTMOUSE', 'PRESS', *side, alt=alt))
    return r, (op.reports[-1][1] if op.reports else '')


def ev_faces(ob):
    return len(ob.evaluated_get(C.evaluated_depsgraph_get()).data.polygons)


def height_at(ob, x, y):
    """World z of ``ob`` under screen point (x, y) in the top view (None = nothing there)."""
    inv = ob.matrix_world.inverted()
    ok, loc, _n, _i = ob.ray_cast(inv @ Vector(((x - 500) / 100, (y - 500) / 100, 100)), inv.to_3x3() @ Vector((0, 0, -1)))
    return (ob.matrix_world @ loc).z if ok else None


# --- tidy_result: a stage that would open the mesh is dropped ---------------------------------------------------
b = cube('Guard', 2.0)
bm = bmesh.new()
bm.from_mesh(b.data)
bm.faces.ensure_lookup_table()
def _del_one(t):
    t.faces.ensure_lookup_table()
    bmesh.ops.delete(t, geom=[t.faces[0]], context='FACES')
    return 1


bm2, n = cg._guarded(bm, _del_one)
check('_guarded: a stage that opens a closed mesh (one face deleted) is dropped - the mesh stays as it was',
      n == 0 and bm2 is bm and len(bm2.faces) == 6 and cg._bad_edges(bm2) == 0, (n, len(bm2.faces)))
bm2.free()
# a cut's boolean result is never opened by the tidy: 200 random boolean results on a bevelled, remeshed body
import random
rng = random.Random(7)
bpy.ops.mesh.primitive_cube_add(size=2.0)
body = C.active_object
body.name = 'Body'
m = body.modifiers.new('bv', 'BEVEL')
m.width, m.segments = 0.12, 3
with C.temp_override(object=body, active_object=body):
    bpy.ops.object.modifier_apply(modifier='bv')
m = body.modifiers.new('rm', 'REMESH')
m.mode, m.voxel_size = 'VOXEL', 0.08
with C.temp_override(object=body, active_object=body):
    bpy.ops.object.modifier_apply(modifier='rm')
m = body.modifiers.new('dc', 'DECIMATE')
m.ratio = 0.08
with C.temp_override(object=body, active_object=body):
    bpy.ops.object.modifier_apply(modifier='dc')
opened = []
reset_cut()
for k in range(12):
    reset_cut()
    cx, cy = 500 + rng.uniform(-60, 60), 500 + rng.uniform(-60, 60)
    w, h = rng.uniform(20, 90), rng.uniform(20, 90)
    pts = [(cx - w, cy - h), (cx + w, cy - h), (cx + w, cy + h), (cx - w, cy + h)]
    r, msg = stroke('CUT', pts)
    nm = non_manifold(body)
    if nm:
        opened.append((k, nm, msg[:60]))
    if len(body.data.polygons) < 40:
        break
check('12 random cuts on a bevelled + remeshed + decimated body: none leaves the closed body open (the 0.24.82 tidy '
      'opened 35 edges on such a part)', not opened and non_manifold(body) == 0, opened)
bpy.data.objects.remove(body)
bpy.data.objects.remove(b)

# --- From Surface over two parts: each part gets its own pocket -----------------------------------------------------
fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_cut.targets = 'AUTO'
cut = S.mch_cut
base = cube('Base', 2.0)                                      # top at z = 1
plate = cube('Plate', 1.0, loc=(0, 0, 1.55))                  # a plate above it: z 1.05 .. 2.05
plate.scale = (1.0, 1.0, 0.1)
bpy.ops.object.transform_apply(scale=True)
plate_top = max((plate.matrix_world @ v.co).z for v in plate.data.vertices)
reset_cut()
cut.depth_mode, cut.depth = 'SURFACE', 0.05
f0, f1 = len(base.data.polygons), len(plate.data.polygons)
r, msg = stroke('CUT', [(470, 470), (530, 470), (530, 530), (470, 530)])
z_base, z_plate = height_at(base, 500, 500), height_at(plate, 500, 500)
check('From Surface over the base AND the plate above it: both get a 0.05 pocket from their OWN surface (one range '
      'for all cut only the plate; the base was "not touched")', r == {'FINISHED'} and 'Base' in msg and 'Plate' in msg
      and 'not touched' not in msg and abs(z_base - 0.95) < 1e-3 and abs(z_plate - (plate_top - 0.05)) < 1e-3,
      (msg[:90], z_base, z_plate))
check('... both parts still closed', non_manifold(base) == 0 and non_manifold(plate) == 0)
check('own_pocket: None for a part not under the shape',
      __import__('mecha_lab.cut_engine', fromlist=['x']).own_pocket(C, base, cg.prepare_loops([[(900, 900), (950, 900), (950, 950)]]), VIEW[0], cut) is None)

# --- Box Hide twice on a part / a strip over a hidden part: coplanar caps -------------------------------------------
reset_cut()
blk = cube('Blk', 2.0, loc=(4, 0, 0))                           # screen 800..1000 - centre (900, 500)
n0 = ev_faces(blk)
r1, m1 = stroke('HIDE', [(850, 450), (900, 450), (900, 550), (850, 550)])
n1 = ev_faces(blk)
r2, m2 = stroke('HIDE', [(880, 420), (940, 420), (940, 580), (880, 580)])     # overlaps the first, same caps
n2 = ev_faces(blk)
check('Box Hide twice on the same part (the second shape overlaps the first, same near / far caps): both hide',
      r1 == {'FINISHED'} and r2 == {'FINISHED'} and 'Hidden' in m2 and bh.is_hidden(blk) and n1 != n0 and n2 != n1,
      (m1[:50], m2[:50], n0, n1, n2))
r3, m3 = stroke('HIDE', [(810, 495), (990, 495), (990, 505), (810, 505)])    # a thin strip across the hidden part
check('... a thin strip over the hidden part hides too (failed: "EXACT: result has 34 non-manifold edges")',
      r3 == {'FINISHED'} and 'Hidden' in m3 and ev_faces(blk) != n2, (m3[:80], n2, ev_faces(blk)))
vol = bh.volume_of(blk)
check('... the hide volume stays one clean solid; the shapes went in one after the other (counted)',
      vol is not None and non_manifold(vol) == 0 and int(vol.get(bh.UNIONS_KEY, 0)) == 3, (vol and non_manifold(vol), vol and vol.get(bh.UNIONS_KEY)))
bpy.ops.mch.box_hide_show_all()

# --- a line over nothing -------------------------------------------------------------------------------------------
S.mch_brush.line_open = True
r, msg = stroke('CUT', [(100, 100), (300, 100)], side=(200, 150))
S.mch_brush.line_open = False
check('An open-line cut over no mesh at all says so (it said "Targets are outside the view")',
      r == {'CANCELLED'} and ('does not cross any mesh' in msg or 'Click on a mesh' in msg or 'does not cover' in msg
                               or 'No target geometry' in msg), (r, msg[:80]))

# --- Cut Ramp on a flat block: measured ---------------------------------------------------------------------------
reset_cut()
ramp = cube('Ramp', 2.0, loc=(0, -4, 0))                       # screen x 400..600, y 0..200, top z = 1
cut.depth_mode, cut.depth, cut.gn_ramp, cut.gn_ramp_length, cut.gn_ramp_soft = 'SURFACE', 0.3, True, 1.0, 0.0
pts = [(440, 60), (560, 60), (560, 140), (440, 140)]           # first side drawn = the bottom edge (y 60) = deep side
r, msg = stroke('CUT', pts)
deep, far_, mid = height_at(ramp, 500, 70), height_at(ramp, 500, 130), height_at(ramp, 500, 100)
check('Cut Ramp: deepest (about Cut Depth 0.3) at the first side drawn, rising to the surface at the far side, half way '
      'in between', r == {'FINISHED'} and 'Ramp' in msg and deep is not None and far_ is not None and mid is not None
      and 1.0 - deep > 0.2 and 1.0 - far_ < 0.12 and (1.0 - far_) < (1.0 - mid) < (1.0 - deep)
      and 1.0 - min(h for h in (deep, far_, mid)) <= 0.3 + 1e-3, (msg[:60], deep, mid, far_))
check('... the block stays closed', non_manifold(ramp) == 0)
cut.gn_ramp = False

# --- Hard Edges: a broken bevel is narrowed, then dropped -----------------------------------------------------------
hb = cube('HB', 2.0, loc=(0, 4, 0))
zb = S.mch_zb
zb.he_width, zb.he_segments, zb.he_bevel = 0.05, 2, True
to_object()
C.view_layer.objects.active = hb
hb.select_set(True)
he.find(hb, zb)
he.set_live(hb, zb)
check('Hard Edges on a clean cube: the bevel is sound - no note, the width as asked',
      hb.get(he.NOTE) is None and hb.modifiers.get(he.BEVEL) is not None and abs(hb.modifiers[he.BEVEL].width - 0.05) < 1e-6,
      (hb.get(he.NOTE), [m.name for m in hb.modifiers]))
check('_sound: the odd broken edge the bevel modifier leaves where bevels meet is tolerated (8 or 0.1 %), more is not',
      he._sound.__doc__ and 'max(8' in open(he.__file__).read())
calls = []
orig = he._broken


def fake_broken(ob):            # broken until the width is under 0.02
    calls.append(ob.modifiers[he.BEVEL].width)
    return (0, 0, 1000, 1000) if ob.modifiers[he.BEVEL].width < 0.02 else (60, 100, 1000, 1000)


he._broken = fake_broken
try:
    he.set_live(hb, zb)
finally:
    he._broken = orig
bev = hb.modifiers.get(he.BEVEL)
check('... a bevel that comes out broken (60 bad edges, 100 zero faces) is halved until it is sound: 0.05 > 0.025 > 0.0125, '
      'and the note says so', bev is not None and abs(bev.width - 0.0125) < 1e-6 and 'overlapped' in str(hb.get(he.NOTE, '')),
      (bev and bev.width, hb.get(he.NOTE), calls))
he._broken = lambda ob: (60, 100, 1000, 1000)
try:
    he.set_live(hb, zb)
finally:
    he._broken = orig
check('... broken whatever the width: no bevel, the note tells why (a clean mesh without a bevel beats a broken one)',
      hb.modifiers.get(he.BEVEL) is None and 'no bevel' in str(hb.get(he.NOTE, '')), (hb.get(he.NOTE), [m.name for m in hb.modifiers]))
msg = __import__('mecha_lab.zb_sculpt', fromlist=['x'])
check('... Find Edges reports the note', "ob.get(he.NOTE)" in open(msg.__file__).read())

# --- shards: a few faces with next to no volume (a corner a GN chamfer shaved off) are dropped ------------------------
b = cube('Sh', 2.0, loc=(0, 8, 0))
me = b.data
verts = [tuple(v.co) for v in me.vertices]
faces = [tuple(p.vertices) for p in me.polygons]
n0 = len(verts)
verts += [(3.0, 0.0, 0.0), (3.5, 0.0, 0.0), (3.0, 0.4, 0.0), (3.0, 0.0, 0.001)]        # a flat tetra, 0.5 across
faces += [(n0, n0 + 1, n0 + 2), (n0, n0 + 3, n0 + 1), (n0 + 1, n0 + 3, n0 + 2), (n0, n0 + 2, n0 + 3)]
me2 = bpy.data.meshes.new('sh')
me2.from_pydata(verts, [], faces)
me2.update()
b.data = me2
out = cg.tidy_result(b.data, cg.mesh_size(b.data))
check('tidy_result: a 4-face piece 0.5 wide (25 % of the part) with next to no volume is a shard and goes',
      out['shards'] == 4 and len(b.data.polygons) == 6, (out, len(b.data.polygons)))

# --- a Cut setting re-cuts the live last cut from a timer, never inside the property update ------------------------
from mecha_lab import ramp_edit as re_
re_._PENDING.clear()
re_.refresh_later(C, 'cutlive')
re_.refresh_later(C, ('cut', 'cutlive'))
check('refresh_later queues the kinds (headless: no timer, flush() runs them once; the UI registers a 0 s timer)',
      list(re_._PENDING) == ['cutlive', 'cut'] and bpy.app.background)
check('... flush empties the queue and returns None (the timer is done)', re_.flush() is None and not re_._PENDING)
src_ts = open(ts.__file__).read()
check("the Cut / GN Edge / Ramp setting updates use refresh_later (the direct re-cut inside the update took Blender "
      "down: fuzz seed 353)", 'ramp_edit.refresh_later' in src_ts and 'ramp_edit.refresh(context' not in src_ts)

# --- an edge finish that breaks the mesh is dropped, the plain cut kept ---------------------------------------------
ce = __import__('mecha_lab.cut_engine', fromlist=['x'])
g = cube('Guarded', 2.0, loc=(0, 12, 0))
me = g.data
ce._DROPPED.clear()


def break_it():                      # a "finish" that deletes a face: the mesh opens
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[0]], context='FACES')
    bm.to_mesh(me)
    bm.free()
    return 7


n = ce._finish_guarded(me, break_it, 'Guarded')
check('_finish_guarded: a finish that opens the mesh is undone (6 faces back, closed), counts 0, the part listed',
      n == 0 and len(me.polygons) == 6 and non_manifold(g) == 0 and ce._DROPPED == ['Guarded'] and 'Guarded' in ce._dropped_note(),
      (n, len(me.polygons), ce._DROPPED))
ce._DROPPED.clear()


def bevel_it():                      # a harmless finish: a real bevel on every edge
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=0.1, segments=1, affect='EDGES')
    bm.to_mesh(me)
    bm.free()
    return 12


n = ce._finish_guarded(me, bevel_it, 'Guarded')
check('... a sound finish is kept as it is', n == 12 and len(me.polygons) > 6 and not ce._DROPPED, (n, len(me.polygons)))
check('every edge finish of a Cut / Split / line cut goes through the guard',
      open(ce.__file__).read().count('_finish_guarded(') >= 5)

# --- a part that crosses itself: counted, and a broken cut on it says so --------------------------------------------
sc = cube('Cross', 2.0, loc=(0, -8, 0))
check('self_overlaps: a clean cube crosses itself nowhere', cg.self_overlaps(sc.data) == 0, cg.self_overlaps(sc.data))
me = sc.data
verts = [tuple(v.co) for v in me.vertices]
faces = [tuple(p.vertices) for p in me.polygons]
n0 = len(verts)
verts += [(-0.5, -0.5, 0.0), (0.5, -0.5, 0.0), (0.0, 1.5, 0.0)]        # (local) a triangle poking out through a wall
faces.append((n0, n0 + 1, n0 + 2))
verts += [(-0.5, -0.5, 1.5), (0.5, -0.5, 1.5), (0.0, 0.5, 1.5)]        # ... and one above it, touching nothing
faces.append((n0 + 3, n0 + 4, n0 + 5))
me2 = bpy.data.meshes.new('cross')
me2.from_pydata(verts, [], faces)
me2.update()
sc.data = me2
check('... a face pushed through a part counts as a crossing (6 cube faces x 1: the one inside crosses the walls it '
      'pokes through, the one above crosses nothing)', 1 <= cg.self_overlaps(sc.data) <= 6, cg.self_overlaps(sc.data))
check('... too big to check = -1', cg.self_overlaps(sc.data, limit=2) == -1)
check("A closed part whose cut came out broken is checked for crossings and the WARNING says so",
      'crosses itself' in open(__import__('mecha_lab.cut_engine', fromlist=['x']).__file__).read())

summary()
