"""0.24.85 Linked group copies follow the original (one mesh for all: a Cut / Decimate / Re-Fix on any of them shows on
every copy), a box-lines eye per group (Layers panel / Groups card), the Mirror planes' off switch and opacity
(Symmetry card / Preferences)."""
import math

from _harness import bpy, check, cube, fresh, non_manifold, summary

import mecha_lab
from mecha_lab import core_geometry as cg, groups, symmetry, tool_state as ts, workspace_ui as wui

_src = open(__file__.replace('test_v02508_linked.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])      # noqa: S102  (the stroke driver)

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_cut.targets = 'AUTO'


def select(*obs):
    for o in C.selected_objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    C.view_layer.objects.active = obs[0]


# --- a linked group copy ---------------------------------------------------------------------------------------------
a = cube('PartA', 1.0, loc=(0, 0, 0))
b = cube('PartB', 0.6, loc=(1.5, 0, 0))
g = groups.create(C, [a, b], 'G')
h = groups.duplicate(C, g, linked=True)
copies = [o for o in groups.members(h) if o.type == 'MESH']
check('Linked Copy of a group: the copies share the parts\' meshes, both sides are marked linked',
      h is not None and len(copies) == 2 and {o.data for o in copies} == {a.data, b.data}
      and all(o.get(groups.LINKED_KEY) for o in copies + [a, b]), (h and h.name, [o.name for o in copies]))
ca = next(o for o in copies if o.data is a.data)
ca.location.y = 3.0                                   # (the copy moved away: the cut lands on the original only)
C.view_layer.update()
n0 = len(a.data.polygons)
# a Cut on the original: the shared mesh is cut, so the copy shows the cut too
select(a)
MODE[0], NATIVE[0] = 'CUT', ts.TOOL_BY_ID['CUT'][5]
S.mch_settings.mch_active_tool = 'CUT'
S.mch_cut.shared_mesh = 'SINGLE'                      # (the default: it would have made the original single-user)
r, msg = lasso([(460, 460), (540, 460), (540, 540), (460, 540)])
check('A Cut on the original (Shared Mesh = This Object Only, the default) still cuts the ONE mesh: the linked copy '
      'shows the same cut, the mesh stays shared', r == {'FINISHED'} and 'users updated' in msg and ca.data is a.data
      and len(a.data.polygons) != n0 and non_manifold(a) == 0, (r, msg[:90], ca.data is a.data))
# Decimate / Re-Fix swap the mesh object: the copies are moved onto the new mesh too
from mecha_lab import fast_decimate as fd
old = a.data
old_name = old.name
new = old.copy()
fd.swap_mesh(a, new)
check('swap_mesh (Decimate / Quad Remesh / Re-Fix): the linked copies move onto the new mesh with the original (the old '
      'mesh gone, the new one takes its name)', a.data is new and ca.data is new and new.name == old_name, (a.data.name, ca.data.name))
# a plain (unlinked) duplicate is untouched by all that
h2 = groups.duplicate(C, g, linked=False)
plain = [o for o in groups.members(h2) if o.type == 'MESH']
check('a plain Duplicate still copies the meshes (its parts are their own)', all(o.data not in {a.data, b.data} for o in plain))
check('Groups card: a Linked Copy button; Mecha Menu > Groups: Linked Copy',
      "text='Linked Copy'" in open(groups.__file__).read() and "'Linked Copy'" in open(__import__('mecha_lab.mecha_menu', fromlist=['x']).__file__).read())

# --- the group box eye ----------------------------------------------------------------------------------------------
check('a group draws its box lines (nothing hidden yet)', not g.get(groups.BOX_HIDDEN_KEY))
r = bpy.ops.mch.group_box_eye(name=g.name)
check('Layers panel / Groups card box eye: the group\'s box lines are off (a selected group still shows them)',
      r == {'FINISHED'} and g.get(groups.BOX_HIDDEN_KEY) == 1 and 'BOX_HIDDEN_KEY' in open(groups.__file__).read().split('def _draw_boxes')[1].split('def ')[0])
bpy.ops.mch.group_box_eye(name=g.name)
check('... and on again', not g.get(groups.BOX_HIDDEN_KEY))
from mecha_lab import layers_panel
check('the Layers panel group row has the box eye next to the enter button', "'mch.group_box_eye'" in open(layers_panel.__file__).read())

# --- the Mirror planes: off switch + opacity (Symmetry card, Preferences) ------------------------------------------
wsrc = open(wui.__file__).read()
check('Preferences: Show Mirror Planes (on) and Mirror Plane Opacity (10 %)',
      "sym_plane_show: BoolProperty(name='Show Mirror Planes', default=True" in wsrc
      and "sym_plane_alpha: FloatProperty(name='Mirror Plane Opacity', default=0.10, min=0.0, max=1.0" in wsrc
      and "'sym_plane_alpha'" in wsrc.split('class MCH_AddonPreferences')[-1].split('def draw(self, context)')[-1])


class _Prefs:                     # (headless: the add-on is not in Preferences > Add-ons, so prefs() is None)
    sym_plane_show = True
    sym_plane_alpha = 0.10


p = _Prefs()
real_prefs = wui.prefs
wui.prefs = lambda: p
import mecha_lab.bottom_bar as bb
real_ui = bb.ui_active
bb.ui_active = lambda c: True
select(a)
symmetry.set_mode(C, a, 'MIRROR')
bpy.ops.mch.symmetry_card()
check('the card is the part\'s', symmetry.card_target(C) == ('PART', a))
items = symmetry.build_card(C, 1000, 1000, 1.0)
labels = [i.label for i in items]
check('Symmetry card (Mirror on a part): a Plane toggle, a - / + opacity stepper and the percentage',
      'Plane' in labels and '10 %' in labels and any(i.action and i.action[0] == 'sym_plane_alpha' for i in items), labels)
it = next(i for i in items if i.action and i.action[0] == 'sym_plane')
symmetry.run_card(C, it)
check('... Plane click: the planes are off (Preferences)', not p.sym_plane_show)
symmetry.run_card(C, it)
plus = next(i for i in items if i.action and i.action[0] == 'sym_plane_alpha' and i.action[1] > 0)
symmetry.run_card(C, plus)
symmetry.run_card(C, plus)
check('... + twice: 20 %', abs(p.sym_plane_alpha - 0.20) < 1e-6, p.sym_plane_alpha)
minus = next(i for i in items if i.action and i.action[0] == 'sym_plane_alpha' and i.action[1] < 0)
for _ in range(10):
    symmetry.run_card(C, minus)
check('... - past 0 stops at 0', p.sym_plane_alpha == 0.0)
src = open(symmetry.__file__).read().split('def _draw_planes')[1].split('def _draw()')[0]
check('the plane drawing reads both: off or 0 % draws nothing, the opacity is the fill', "pref('sym_plane_show'" in src and "pref('sym_plane_alpha'" in src and 'alpha))' in src)
p.sym_plane_alpha, p.sym_plane_show = 0.10, True
C.window_manager.mch_sym_card = ''
wui.prefs = real_prefs
bb.ui_active = real_ui

# --- result shading: Decimate / Quad Remesh / Re-Fix results smooth with sharp edges by angle (export-ready) ---------
from mecha_lab import fast_decimate as fd, zb_sculpt as zs
zb = S.mch_zb
check('Shading option on the Decimate rows (Smooth default / Flat / Keep)', zb.result_shade == 'SMOOTH'
      and "'result_shade'" in open(__import__('mecha_lab.mesh_tools', fromlist=['x']).__file__).read()
      and "'result_shade'" in open(__import__('mecha_lab.zb_ui', fromlist=['x']).__file__).read())
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=1.0, depth=2.0, location=(0, -6, 0))
cyl = C.active_object
for pg in cyl.data.polygons:
    pg.use_smooth = False
import bmesh
bm = bmesh.new(); bm.from_mesh(cyl.data); bmesh.ops.triangulate(bm, faces=bm.faces[:]); bm.to_mesh(cyl.data); bm.free()
n_sharp = cg.shade_result(cyl.data, 'SMOOTH', math.radians(30.0))
sh = cyl.data.attributes['sharp_edge'].data
sharp_edges = [e for e, d in zip(cyl.data.edges, sh) if d.value]
check('shade_result SMOOTH on a flat cylinder: every face smooth, the 96 rim edges (90 degrees) sharp, the side and cap '
      'edges not', all(pg.use_smooth for pg in cyl.data.polygons) and n_sharp == 96 and len(sharp_edges) == 96
      and all(abs(abs(cyl.data.vertices[e.vertices[0]].co.z) - 1.0) < 1e-6 and abs(abs(cyl.data.vertices[e.vertices[1]].co.z) - 1.0) < 1e-6
              and abs(cyl.data.vertices[e.vertices[0]].co.z - cyl.data.vertices[e.vertices[1]].co.z) < 1e-6 for e in sharp_edges), n_sharp)
check('... FLAT: every face flat', cg.shade_result(cyl.data, 'FLAT') == 0 and not any(pg.use_smooth for pg in cyl.data.polygons))
check('... KEEP: untouched', cg.shade_result(cyl.data, 'KEEP') == -1 and not any(pg.use_smooth for pg in cyl.data.polygons))
select(cyl)
from mecha_lab import mesh_tools
msg = mesh_tools.run_one(C, cyl, zb, 'DECIMATE')
check('Decimate (Mesh Tools) with Shading = Smooth: the result is smooth with its rim sharp',
      msg.startswith('Decimate') and all(pg.use_smooth for pg in cyl.data.polygons)
      and sum(d.value for d in cyl.data.attributes['sharp_edge'].data) > 0, msg[:60])
zb.result_shade = 'FLAT'
msg = mesh_tools.run_one(C, cyl, zb, 'DECIMATE')
check('... Shading = Flat: flat', not any(pg.use_smooth for pg in cyl.data.polygons))
zb.result_shade = 'SMOOTH'

# --- the result tidy after Decimate is cheap on a clean result (numpy pre-checks) ---------------------------------
check('numpy pre-checks: a clean cylinder has no twin faces, no flipped pair, no short edge', not cg._twin_faces(cyl.data)
      and not cg._flipped_pairs(cyl.data) and cg._mesh_min_edge_area(cyl.data)[0] > 1e-3 and cg._bad_edges_mesh(cyl.data) == 0)
verts = [v.co[:] for v in cyl.data.vertices]
faces = [list(pg.vertices) for pg in cyl.data.polygons]
e0 = cyl.data.edges[0].vertices
verts.append((0.0, 0.0, 3.0))                                   # a fin: two faces back to back on one edge + a new point
faces.append([e0[0], e0[1], len(verts) - 1])
faces.append([len(verts) - 1, e0[1], e0[0]])
twin = bpy.data.meshes.new('twin')
twin.from_pydata(verts, [], faces)
twin.update()
cyl.data = twin
check('... a folded (twin) face is seen', cg._twin_faces(cyl.data) and cg._flipped_pairs(cyl.data))
out = cg.tidy_result(cyl.data, shards=False, slivers=False)
check('... and the tidy still removes it (the fin gone, the cylinder still closed)', out['folds'] == 2 and non_manifold(cyl) == 0 and len(cyl.data.vertices) == len(verts) - 1, out)
import time
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=6, radius=1.0, location=(0, 9, 0))
big = C.active_object
t = time.perf_counter(); out = cg.tidy_result(big.data, shards=False, slivers=False); dt = time.perf_counter() - t
check('tidy of a clean 82k-face sphere: nothing found, under 0.6 s (was ~1 s: every stage copied the mesh)',
      not any(out.values()) and dt < 0.6, round(dt, 2))
summary()
