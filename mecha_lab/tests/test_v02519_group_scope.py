"""0.24.107 Group scope fixes on top of the v0.24.106 group system.

- the watcher / click-key timers survive opening a file (persistent) + load / undo / append handlers
- leaving a scope never stops half way (an object outside the view layer, a deleted handle)
- auto-add: only a new part that has stayed still for a tick with no modal running; never a helper, a ghosted part
- viewport click: the whole group; double-click on the same part enters, on another part does not; double-click on
  empty space steps out one level; nested groups one level at a time
- Layers row Exit: one level; picking a group from the list leaves only the scope levels it must
- Alt+X with a group and loose meshes: the mesh mirror
- Shift+D: symmetry centre copies next to the originals, a world centre's copy follows the new group, a nested
  group's repetition object moves with the copy
- the handle is hidden, group boxes are off by default, the green outline draws the selected group's parts
"""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import bpy, check, cube, fresh, summary
from mathutils import Vector
import mecha_lab
from mecha_lab import groups, group_outline, mirror_tools
fresh()
mecha_lab.register()
C = bpy.context
S = C.scene

# --- timers and handlers ------------------------------------------------------------------------------------------
src = open(groups.__file__).read()
check('the auto-add timer is registered and persistent (a plain timer is dropped when a file opens)',
      bpy.app.timers.is_registered(groups._auto_group_tick) and
      "register(_auto_group_tick, first_interval=0.45, persistent=True)" in src)
check('... the click-key timer too', "register(_register_group_keymaps, first_interval=0.2, persistent=True)" in src)
check('load / undo / redo / append handlers are in place',
      groups._on_load in bpy.app.handlers.load_post and groups._on_undo in bpy.app.handlers.undo_post
      and groups._on_undo in bpy.app.handlers.redo_post and groups._on_import in bpy.app.handlers.blend_import_post)

a, b = cube('A', loc=(0, 0, 0)), cube('B', loc=(3, 0, 0))
c, d = cube('Cn', loc=(0, 4, 0)), cube('Dn', loc=(3, 4, 0))
G = groups.create(C, [a, b, c, d], 'G')
H = groups.create(C, [c, d], 'H')
check('nested group H is inside G', groups.group_of(H.parent) == G and H in groups.members(G), [o.name for o in groups.members(G)])
check('the group handle is not shown (tiny cross), group boxes off by default',
      G.empty_display_type == 'PLAIN_AXES' and G.empty_display_size <= groups.HANDLE_SIZE * 1.01
      and S.mch_settings.group_boxes is False, (G.empty_display_size, S.mch_settings.group_boxes))

tmp = os.path.join(tempfile.mkdtemp(), 'scope_file.blend')
groups.enter_scope(C, G)
bpy.ops.wm.save_as_mainfile(filepath=tmp)
bpy.ops.wm.open_mainfile(filepath=tmp)
C = bpy.context
S = C.scene
check('after opening a file the auto-add timer still runs (0.24.106 lost it)', bpy.app.timers.is_registered(groups._auto_group_tick))
check('... the scope came back with the file', groups.scope(C) is not None and groups.scope(C).name == 'G')
a, b, c, d = (bpy.data.objects[n] for n in ('A', 'B', 'Cn', 'Dn'))
G, H = bpy.data.objects['G'], bpy.data.objects['H']
groups.clear_scope(C)

# --- leaving a scope never stops half way ---------------------------------------------------------------------------
side = bpy.data.collections.new('Side')
S.collection.children.link(side)
lone = cube('Lone', loc=(9, 0, 0))
S.collection.objects.unlink(lone)
side.objects.link(lone)
S.mch_group_scope_display = 'HIDDEN'
groups.enter_scope(C, G)
lc = C.view_layer.layer_collection.children['Side']
lc.exclude = True              # 'Lone' is now outside the view layer: hide_set raises on it
err = None
try:
    groups.clear_scope(C)
except Exception as ex:        # noqa
    err = ex
check('leaving a scope with an object outside the view layer: no error, nothing left ghosted',
      err is None and groups.scope(C) is None and not any(groups.SAVED_KEY in o for o in S.objects),
      repr(err))
lc.exclude = False
check('... and its pick flag is back', not lone.hide_select)
S.mch_group_scope_display = 'WIRE'

groups.enter_scope(C, G)
check('entering a scope ghosts the outside part', lone.hide_select and lone.display_type == 'WIRE')
tmpg = cube('TmpG', loc=(0, -6, 0))
T = groups.create(C, [tmpg], 'T')
groups.clear_scope(C)
groups.enter_scope(C, T)
bpy.data.objects.remove(T, do_unlink=True)          # the handle we are in is gone
r = groups.ensure_scope(C)
check('a scope whose group was deleted is undone (no part stays unpickable)',
      r is None and S.get(groups.SCOPE_KEY) is None and not lone.hide_select and lone.display_type != 'WIRE'
      and not a.hide_select)
bpy.data.objects.remove(tmpg, do_unlink=True)

# leftovers after an undo-like state: saved flags but no scope
lone['mch_scope_saved'] = '[true, "WIRE", false]'
lone.hide_select, lone.display_type = True, 'WIRE'
groups.ensure_scope(C, leftovers=True)
check('saved flags without a scope (undo / old file) are put back', groups.SAVED_KEY not in lone and lone.hide_select is True
      and lone.display_type == 'WIRE')
lone.hide_select, lone.display_type = False, 'SOLID'

# --- auto-add ------------------------------------------------------------------------------------------------------
groups.enter_scope(C, G)
groups.auto_group_step(C)                      # seeds
bpy.ops.mesh.primitive_cube_add(location=(1, 1, 5))
new = C.active_object
r1 = groups.auto_group_step(C)
check('a new part does not join on the tick it appears', r1 == [] and new.parent is None)
new.location.x += 0.5                            # it is moved before the next tick
C.view_layer.update()
r2 = groups.auto_group_step(C)
check('... nor on a tick where it has moved', r2 == [] and new.parent is None, r2)
r3 = groups.auto_group_step(C)
check('... it joins after a quiet tick, into the group we are in, staying where it is', r3 == [new] and new.parent == G
      and abs(new.matrix_world.translation.x - 1.5) < 1e-5 and new.name in groups.collection_of(G).objects)

bpy.ops.mesh.primitive_cube_add(location=(1, 1, 9))
busy_one = C.active_object
real_busy = groups._busy
groups._busy = lambda ctx: True                  # a modal operator (G after Shift+A, a tool drawing) is running
for _ in range(4):
    groups.auto_group_step(C)
check('while a modal operator runs a new part waits', busy_one.parent is None)
groups._busy = real_busy
for _ in range(3):
    groups.auto_group_step(C)
check('... and joins once it ends', busy_one.parent == G)

bpy.ops.mesh.primitive_cube_add(location=(1, 1, 12))
helper = C.active_object
helper.display_type = 'WIRE'
bpy.ops.mesh.primitive_cube_add(location=(1, 1, 14))
cutter = C.active_object
cutter['mch_cut_carrier'] = True
bpy.ops.mesh.primitive_cube_add(location=(1, 1, 16))
nopick = C.active_object
nopick.hide_select = True
for _ in range(4):
    groups.auto_group_step(C)
check('helpers never join: wire display, a cutter, an unpickable object',
      helper.parent is None and cutter.parent is None and nopick.parent is None)
for o in (helper, cutter, nopick):
    bpy.data.objects.remove(o, do_unlink=True)

bpy.ops.mesh.primitive_cube_add(location=(1, 1, 18))
undone = C.active_object
groups._on_undo()
for _ in range(4):
    groups.auto_group_step(C)
check('an object that is there after an undo step is not "new"', undone.parent is None)
bpy.data.objects.remove(undone, do_unlink=True)
check('the watcher knows objects by session_uid (stays the same over undo)', groups._uid(a) == a.session_uid)
groups.clear_scope(C)
bpy.ops.mesh.primitive_cube_add(location=(1, 1, 20))
outside = C.active_object
for _ in range(4):
    groups.auto_group_step(C)
check('outside any scope nothing joins', outside.parent is None)

# --- viewport clicks ------------------------------------------------------------------------------------------------


class Region:
    type = 'WINDOW'
    width, height = 800, 600


class Ctx:
    """bpy.context with a 3D View window region (background has none)."""
    region = Region()

    def __getattr__(self, name):
        return getattr(bpy.context, name)


class Ev:
    def __init__(self, x=100, y=100):
        self.mouse_region_x, self.mouse_region_y = x, y
        self.shift = self.ctrl = self.alt = False


class Op:
    def __init__(self, enter):
        self.enter = enter


HIT = {'ob': None}
groups._pick_visible_mesh = lambda context, event: HIT['ob']


def click(ob, enter=False, xy=(100, 100)):
    HIT['ob'] = ob
    return groups.MCH_OT_group_view_pick.invoke(Op(enter), Ctx(), Ev(*xy))


def dbl(ob, xy=(100, 100)):
    click(ob, False, xy)
    return click(ob, True, xy)


for o in list(C.selected_objects):
    o.select_set(False)
r = click(a)
check('click on a part outside any scope: its outermost group is selected',
      r == {'FINISHED'} and G.select_get() and C.view_layer.objects.active == G and not a.select_get())
click(a)
r = click(b, True)
check('a double-click whose clicks hit two different parts does not enter', r == {'PASS_THROUGH'} and groups.scope(C) is None)
r = dbl(a)
check('double-click on a part: into its group', r == {'FINISHED'} and groups.scope(C) == G)
r = click(a)
check('inside: a click picks the one part', r == {'FINISHED'} and a.select_get() and not G.select_get())
r = click(c)
check('inside: a click on a nested group\'s part picks that group (one level)', r == {'FINISHED'} and H.select_get())
r = dbl(c)
check('double-click on it: into the nested group', r == {'FINISHED'} and groups.scope(C) == H
      and groups.scope_path(C) == ['G', 'H'])
r = click(None)
check('a single click on empty space only passes through (Blender deselects)', r == {'PASS_THROUGH'} and groups.scope(C) == H)
r = dbl(None)
check('double-click on empty space: one level out (H -> G), H selected', r == {'FINISHED'} and groups.scope(C) == G
      and H.select_get())
r = dbl(None)
check('... again: out of G', r == {'FINISHED'} and groups.scope(C) is None and G.select_get())
r = dbl(None)
check('... outside any scope it does nothing', r == {'PASS_THROUGH'})
groups.enter_scope(C, G)
groups._last_click.update(t=-100.0, hit='A', xy=(5, 5))     # the first click went to another handler (unseen)
r = click(None, True, (300, 300))
check('a double-click whose first click this operator never saw: Blender\'s own same-spot test stands (exits)',
      r == {'FINISHED'} and groups.scope(C) is None)
check('the click operator makes an undo step (Ctrl+Z no longer drops you out of the scope silently)',
      'UNDO' in groups.MCH_OT_group_view_pick.bl_options)

check('helpers are not click targets', groups._is_helper(type('O', (), {'get': lambda s, k, d=None: k == 'mch_cut_carrier',
                                                                  'display_type': 'SOLID', 'name': 'x'})()))

# --- Layers row -----------------------------------------------------------------------------------------------------
groups.enter_scope(C, H)
r = bpy.ops.mch.group_pick(name='H', enter=False)
check('Layers row Exit on the group we are in: one level out (it left every level)', r == {'FINISHED'}
      and groups.scope(C) == G)
groups.enter_scope(C, H)
r = bpy.ops.mch.group_pick(name='G', enter=False)
check('picking the outer group from the list leaves the scope to pick it', groups.scope(C) is None and G.select_get())
groups.enter_scope(C, G)
r = bpy.ops.mch.group_pick(name='H', enter=False)
check('picking a group inside the current scope keeps the scope', groups.scope(C) == G and H.select_get())
groups.clear_scope(C)

# --- Alt+X ------------------------------------------------------------------------------------------------------------
loose = cube('Loose', loc=(-6, 0, 0))
for o in list(C.selected_objects):
    o.select_set(False)
G.select_set(True)
check('Alt+X: a group alone -> group mirror', mirror_tools.mirror_targets_kind(C) == 'GROUP')
a.select_set(True)
check('... the group and one of its own parts -> still the group mirror', mirror_tools.mirror_targets_kind(C) == 'GROUP')
loose.select_set(True)
check('... a group and a loose mesh -> the mesh mirror (0.24.106 ignored the mesh)', mirror_tools.mirror_targets_kind(C) == 'MESH')
for o in list(C.selected_objects):
    o.select_set(False)

# --- Shift+D ----------------------------------------------------------------------------------------------------------
piv = bpy.data.objects.new('WorldPivot', None)
S.collection.objects.link(piv)
piv['_mch_world_pivot'] = 1
m = a.modifiers.new('Mirror', 'MIRROR')
m.mirror_object = piv
groups.set_repeat(C, H, mode='MIRROR', axes=(True, False, False))
coll_g = groups.collection_of(G)
carriers_before = sorted(o.name for o in coll_g.objects if groups.CARRIER_KEY in o)
h2 = groups.duplicate(C, G)
new_coll = groups.collection_of(h2)
a2 = next(o for o in groups.members(h2) if o.type == 'MESH' and o.modifiers.get('Mirror'))
p2 = a2.modifiers['Mirror'].mirror_object
check('Shift+D: the part copy mirrors about a copy of the centre', p2 is not None and p2 != piv)
check('... that copy sits next to the original centre, not inside the new group\'s collection',
      p2.name not in new_coll.objects and p2.name in S.collection.objects)
check('... and follows the new group (a world centre stayed behind before)', p2.parent == h2)
carriers_after = sorted(o.name for o in coll_g.objects if groups.CARRIER_KEY in o)
h_copy = next(o for o in groups.members(h2) if groups.is_group(o))
car2 = groups.carrier_of(h_copy)
check('... the nested group\'s repetition object goes with the copy (it stayed in the original group)',
      carriers_after == carriers_before and car2 is not None and car2.name in new_coll.objects, (carriers_before, carriers_after))

# --- green outline --------------------------------------------------------------------------------------------------
for o in list(C.selected_objects):
    o.select_set(False)
groups.select_group(C, G)
objs = group_outline.outline_objects(C)
check('outline: a selected group outlines all its parts, nested ones too (handles and repetition objects not)',
      {o.name for o in objs} >= {'A', 'B', 'Cn', 'Dn'} and not any(groups.is_group(o) or groups.CARRIER_KEY in o for o in objs),
      [o.name for o in objs])
groups.enter_scope(C, G)
check('... inside that group it is not outlined', group_outline.outline_objects(C) == [])
groups.select_group(C, H)
check('... a nested group selected inside it is', {o.name for o in group_outline.outline_objects(C)} == {'Cn', 'Dn'})
groups.clear_scope(C)
dg = C.evaluated_depsgraph_get()
co, tri = group_outline.mesh_arrays(b, dg)
check('outline cache: the evaluated triangles', len(co) == 8 and len(tri) == 12)
segs = group_outline.silhouette_segments(co, tri, b.matrix_world, Vector((3, 0, 10)), Vector((0, 0, -1)), True)
check('silhouette lines (fallback): a cube from straight above shows its 4 top edges', len(segs) == 4, len(segs))
vd = Vector((0.3, 0.2, -1)).normalized()
segs = group_outline.silhouette_segments(co, tri, b.matrix_world, Vector((3, 0, 10)), vd, True)
check('... from a slant its 6-sided outline', len(segs) == 6, len(segs))
group_outline._cache['B'] = ('x', 12, None)
group_outline.forget('B')
check('the cache entry of a changed part is dropped', 'B' not in group_outline._cache)
check('outline handlers registered (geometry changes, load, undo)',
      group_outline._on_depsgraph in bpy.app.handlers.depsgraph_update_post and group_outline._on_reset in bpy.app.handlers.undo_post)

mecha_lab.unregister()
check('unregister removes the handlers', groups._on_undo not in bpy.app.handlers.undo_post
      and group_outline._on_depsgraph not in bpy.app.handlers.depsgraph_update_post
      and not bpy.app.timers.is_registered(groups._auto_group_tick))
summary()
