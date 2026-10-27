"""0.24.65 Radial Array crash hardening: NaN / huge values, dense rings (live Exact Boolean out of memory, a
Size of 1e25 segfaulted bpy 5.2.3), removed node group / nodes / GN modifier, source deleted / renamed / outside
the view layer, library data, dependency cycles, target in Edit Mode, applying twice, no ID references kept.
Real undo cannot run headless (ed.undo poll fails in background mode), so the 'no stale ID references' rule is
checked on the module and operator classes instead."""
import math
import os
import tempfile
import types

from _harness import bpy, bmesh, check, cube, cylinder, fresh, mesh_obj, select_only, summary, volume

import mecha_lab
from mecha_lab import radial_array as ra

mecha_lab.register()
fresh()
C = bpy.context
TMP = tempfile.mkdtemp(prefix='mch_radial_')
TIRE_VOLUME = 0.5 * 32 * 1.44 * math.sin(math.tau / 32) * 0.4


def run(op, **kw):
    """bpy.ops raises RuntimeError on an ERROR report or a failed poll: (result, message)."""
    try:
        return op(**kw), ''
    except RuntimeError as ex:
        return {'CANCELLED'}, str(ex)


def ring(count=8, name='Tooth', size=0.3, loc=(1.2, 0, 0)):
    C.scene.cursor.location = (0, 0, 0)
    tooth = cube(name, size=size, loc=loc)
    select_only(tooth)
    C.scene.mch_settings.radial_count = count
    bpy.ops.mch.radial_create()
    return tooth, C.view_layer.objects.active


def tire():
    return cylinder('Tire', segments=32, radius=1.2, depth=0.4)


def linked_ring(count=8):
    ti = tire()
    tooth, car = ring(count)
    car.mch_radial.boolean_target = ti
    select_only(car)
    res, msg = run(bpy.ops.mch.radial_boolean_link)
    return ti, tooth, car, res, msg


def switch_on(car):
    return car.modifiers[ra.GN_MOD].node_group.nodes['MCH_Radial_BakeSwitch'].inputs['Switch'].default_value


class Rec:
    """Records label texts of a panel draw (every layout call returns the recorder)."""

    def __init__(self):
        self.labels = []

    def __getattr__(self, name):
        def call(*_a, **kw):
            if name == 'label':
                self.labels.append(kw.get('text', ''))
            return self
        return call


def panel_labels(car):
    select_only(car)
    rec = Rec()
    ra.MCH_PT_radial.draw(types.SimpleNamespace(layout=rec), C)
    return rec.labels


# --- pure helpers and counts ---------------------------------------------------------------------------------
check('Count 1 / 0 have no step, a full ring of 4 is a quarter turn, NaN arc gives a finite step',
      ra.radial_step(1, math.tau) == 0.0 and ra.radial_step(0, math.tau) == 0.0
      and abs(ra.radial_step(4, math.tau) - math.tau / 4) < 1e-9 and math.isfinite(ra.radial_step(3, float('nan'))))
tooth, car = ring()
p = car.mch_radial
p.count = 0
low = p.count
p.count = 100000
check('Count is clamped to 1 .. 2048 by the property', low == 1 and p.count == 2048, (low, p.count))
p.count = 8
check('A normal ring is safe to realize and to cut', ra.realize_problem(car) == ''
      and ra.realize_problem(car, ra.BOOLEAN_APPLY_LOAD) == '')
p.radius = float('nan')
check('NaN Radius is refused by the realize check (the property itself accepts NaN)',
      'NaN' in ra.realize_problem(car), ra.realize_problem(car))
p.radius = 1.2
p.scale = 1.0e25
check('A Size of 1e25 is refused as too large', 'too large' in ra.realize_problem(car), ra.realize_problem(car))
p.scale = 1.0
p.radius = 0.0
r, msg = run(bpy.ops.mch.radial_bake)
check('Zero Radius still bakes (all copies at the centre)', r == {'FINISHED'} and len(car.data.vertices) == 64,
      (r, msg, len(car.data.vertices)))

fresh()
tooth, car = ring(24)
p = car.mch_radial
dense = {}
for n in (24, 192, 2048):         # the 0.3 cube teeth of the measurements: 192 took 12 s, 2048 ran out of memory
    p.count = n
    dense[n] = (ra.realize_problem(car, ra.BOOLEAN_LIVE_LOAD), ra.realize_problem(car, ra.BOOLEAN_APPLY_LOAD))
check('Dense ring: 24 teeth are fine live, 192 pause the live cut but still apply, 2048 are refused',
      dense[24] == ('', '') and dense[192][0] and not dense[192][1] and 'too heavy' in dense[2048][1], dense)
select_only(car)
r, msg = run(bpy.ops.mch.radial_bake)
check('Count 2048 of a small cube still bakes (no Boolean: instances realize cheaply)',
      r == {'FINISHED'} and len(car.data.vertices) == 2048 * 8, (r, msg))
fresh()
check('The bake limit follows this computer\'s memory (about a third of it, at least 5 million points)',
      ra.MAX_REALIZED_VERTS >= 5_000_000 and ra.BOOLEAN_APPLY_LOAD >= 400_000 and ra._ram_gb() > 0)
limit, ra.MAX_REALIZED_VERTS = ra.MAX_REALIZED_VERTS, 5_000_000      # (as on a 16 GB computer)
src = mesh_obj('Dense', lambda bm: bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=48, radius=0.1),
               (1.2, 0, 0))
select_only(src)
C.scene.mch_settings.radial_count = 2048
bpy.ops.mch.radial_create()
car = C.view_layer.objects.active
check('Too many realized points (2048 x 3010) are refused before baking',
      'Too many points' in ra.realize_problem(car), ra.realize_problem(car))
r, msg = run(bpy.ops.mch.radial_bake)
check('Confirm refuses with a clear message and keeps the live ring',
      r == {'CANCELLED'} and 'Too many points' in msg and ra.get_radial(car) is not None, msg)
ra.MAX_REALIZED_VERTS = limit
fresh()
tooth, car = ring()
bm = bmesh.new()
bm.to_mesh(car.data)
bm.free()
check('An emptied ring source is refused', 'empty' in ra.realize_problem(car), ra.realize_problem(car))
r, msg = run(bpy.ops.mch.radial_bake)
check('Confirm on an empty ring is refused, not baked to nothing', r == {'CANCELLED'} and 'empty' in msg, msg)

# --- live Exact Boolean pauses instead of exhausting memory ------------------------------------------------------
fresh()
ti, tooth, car, res, msg = linked_ring(24)
bm_mod = ra.find_boolean_link(car)[1]
check('Link at 24 teeth: live cut on (realized cutters, Boolean shown)',
      res == {'FINISHED'} and switch_on(car) and bm_mod.show_viewport, (res, msg))
live, ra.BOOLEAN_LIVE_LOAD = ra.BOOLEAN_LIVE_LOAD, 100
car.mch_radial.count = 25
paused = (not switch_on(car)) and not bm_mod.show_viewport
labels = panel_labels(car)
ra.BOOLEAN_LIVE_LOAD = live
check('Over the live budget the cut pauses (instances, Boolean hidden) and the panel says why',
      paused and any(t.startswith('Preview paused') for t in labels), labels)
car.mch_radial.count = 24
check('Back under the budget the live cut resumes by itself', switch_on(car) and bm_mod.show_viewport)
car.mch_radial.radius = float('nan')
check('NaN Radius pauses the live cut', not switch_on(car) and not bm_mod.show_viewport)
verts = len(ti.data.vertices)
select_only(car)
r, msg = run(bpy.ops.mch.radial_boolean_apply)
check('Apply with NaN values is refused; ring and target untouched',
      r == {'CANCELLED'} and 'NaN' in msg and car.name in bpy.data.objects and len(ti.data.vertices) == verts, msg)
car.mch_radial.radius = 1.2
heavy, ra.BOOLEAN_APPLY_LOAD = ra.BOOLEAN_APPLY_LOAD, 100
r, msg = run(bpy.ops.mch.radial_boolean_apply)
ra.BOOLEAN_APPLY_LOAD = heavy
check('Apply over the memory budget is refused before evaluating',
      r == {'CANCELLED'} and 'too heavy' in msg and car.name in bpy.data.objects and len(ti.data.vertices) == verts,
      msg)
fresh()
ti, tooth, car, _r, _m = linked_ring(24)
live, ra.BOOLEAN_LIVE_LOAD = ra.BOOLEAN_LIVE_LOAD, 100
select_only(car)
r, msg = run(bpy.ops.mch.radial_boolean_apply)
ra.BOOLEAN_LIVE_LOAD = live
check('Apply still realizes the cutters when only the live preview is paused',
      r == {'FINISHED'} and volume(ti) < TIRE_VOLUME - 0.15, (r, msg, volume(ti), TIRE_VOLUME))
fresh()
ti = tire()
tooth, car = ring()
car.mch_radial.boolean_target = ti
select_only(car)
live, ra.BOOLEAN_LIVE_LOAD = ra.BOOLEAN_LIVE_LOAD, 10
r, msg = run(bpy.ops.mch.radial_boolean_link)
ra.BOOLEAN_LIVE_LOAD = live
check('Link of a ring over the live budget links it with the live preview paused',
      r == {'FINISHED'} and not switch_on(car) and not ra.find_boolean_link(car)[1].show_viewport, (r, msg))

# --- node group / nodes / GN modifier removed by the user ---------------------------------------------------------
fresh()
tooth, car = ring()
bpy.data.node_groups.remove(car.modifiers[ra.GN_MOD].node_group)
select_only(car)
r, msg = run(bpy.ops.mch.radial_bake)
check('Confirm after the node group was deleted rebuilds it and bakes the full ring (was an AttributeError)',
      r == {'FINISHED'} and len(car.data.vertices) == 64 and car.get('mch_role') == 'MCH_RADIAL_BAKED', (r, msg))
check('No orphan radial node group is left', not [g for g in bpy.data.node_groups if g.users == 0])
fresh()
tooth, car = ring()
grp = car.modifiers[ra.GN_MOD].node_group
grp.nodes.remove(grp.nodes['MCH_Radial_Points'])
car.mch_radial.count = 5
nodes = car.modifiers[ra.GN_MOD].node_group.nodes
check('Editing a ring that lost a node rebuilds it (was a KeyError on every edit)',
      nodes.get('MCH_Radial_Points') is not None and nodes['MCH_Radial_Points'].inputs['Count'].default_value == 5)
fresh()
tooth, car = ring()
grp = car.modifiers[ra.GN_MOD].node_group
grp.nodes.remove(grp.nodes['MCH_Radial_Realize'])
select_only(car)
r, msg = run(bpy.ops.mch.radial_bake)
check('Confirm after the Realize node was deleted rebuilds the group instead of baking an empty mesh',
      r == {'FINISHED'} and len(car.data.vertices) == 64, (r, msg, len(car.data.vertices)))
fresh()
ti, tooth, car, _r, _m = linked_ring()
bpy.data.node_groups.remove(car.modifiers[ra.GN_MOD].node_group)
select_only(car)
r, msg = run(bpy.ops.mch.radial_boolean_apply)
check('Boolean apply after the node group was deleted cuts all 8 teeth and shows the source again '
      '(was: one cut, then an error with the ring already gone)',
      r == {'FINISHED'} and volume(ti) < TIRE_VOLUME - 0.05 and not tooth.hide_get()
      and 'Tooth_Radial' not in bpy.data.objects, (r, msg, volume(ti), TIRE_VOLUME, tooth.hide_get()))
fresh()
tooth, car = ring()
car.modifiers.remove(car.modifiers[ra.GN_MOD])
car.mch_radial.count = 4
select_only(car)
r, msg = run(bpy.ops.mch.radial_bake)
check('Without the GN modifier: no rebuild, edits are harmless, Confirm is unavailable',
      ra.ensure_radial_group(car) is None and r == {'CANCELLED'} and 'poll' in msg, msg)

# --- source deleted / renamed / outside the view layer -----------------------------------------------------------
fresh()
tooth, car = ring()
C.scene.collection.objects.unlink(tooth)        # deleted from the scene, kept alive by the Source pointer
select_only(car)
r, msg = run(bpy.ops.mch.radial_cancel)
check('Cancel with the source deleted from the scene finishes cleanly (was a RuntimeError after the ring was gone)',
      r == {'FINISHED'} and 'Tooth_Radial' not in bpy.data.objects, (r, msg))
fresh()
tooth, car = ring()
bpy.data.objects.remove(tooth)
select_only(car)
r, msg = run(bpy.ops.mch.radial_cancel)
check('Cancel with the source removed entirely', r == {'FINISHED'} and 'Tooth_Radial' not in bpy.data.objects, (r, msg))
fresh()
tooth, car = ring()
tooth.name = 'Renamed Tooth'
select_only(car)
r, msg = run(bpy.ops.mch.radial_cancel)
check('Cancel finds a renamed source, shows and selects it again',
      r == {'FINISHED'} and not tooth.hide_get() and C.view_layer.objects.active == tooth, (r, msg))
fresh()
ti, tooth, car, _r, _m = linked_ring()
C.scene.collection.objects.unlink(tooth)
select_only(car)
r, msg = run(bpy.ops.mch.radial_boolean_apply)
check('Boolean apply with the source deleted from the scene', r == {'FINISHED'}, (r, msg))

# --- dependency cycles and Edit Mode -----------------------------------------------------------------------------
fresh()
a_src, a = ring(name='A')
b_src, b = ring(name='B', loc=(0, 1.5, 0.1))
a.mch_radial.boolean_target = b
select_only(a)
r, msg = run(bpy.ops.mch.radial_boolean_link)
check('A live Radial Array cannot be the Boolean target (dependency cycle)',
      r == {'CANCELLED'} and 'live Radial Array' in msg and not len(b.modifiers) > 1, msg)
fresh()
ti = tire()
tooth, car = ring()
car.modifiers.new('User Boolean', 'BOOLEAN').object = ti
car.mch_radial.boolean_target = ti
select_only(car)
r, msg = run(bpy.ops.mch.radial_boolean_link)
check('A target already used by a modifier on the ring is refused (dependency cycle)',
      r == {'CANCELLED'} and 'cycle' in msg and not ti.modifiers, msg)
fresh()
ti, tooth, car, _r, _m = linked_ring()
verts = len(ti.data.vertices)
select_only(ti)
bpy.ops.object.mode_set(mode='EDIT')
C.view_layer.objects.active = car
r, msg = run(bpy.ops.mch.radial_boolean_apply)
check('Boolean apply while the target is in Edit Mode is refused before evaluating',
      r == {'CANCELLED'} and 'Edit Mode' in msg and car.name in bpy.data.objects, msg)
C.view_layer.objects.active = ti
bpy.ops.object.mode_set(mode='OBJECT')
check('... and the target mesh is unchanged', len(ti.data.vertices) == verts)

# --- library data ----------------------------------------------------------------------------------------------
fresh()
ti = tire()
tooth, car = ring()
car.mch_radial.boolean_target = ti
lib_path = os.path.join(TMP, 'radial_lib.blend')
bpy.ops.wm.save_as_mainfile(filepath=lib_path, copy=True)
fresh()
with bpy.data.libraries.load(lib_path, link=True) as (data_from, data_to):
    data_to.objects = list(data_from.objects)
for ob in data_to.objects:
    C.scene.collection.objects.link(ob)
car = bpy.data.objects['Tooth_Radial']
select_only(car)
results = [run(op) for op in (bpy.ops.mch.radial_boolean_link, bpy.ops.mch.radial_bake, bpy.ops.mch.radial_cancel)]
check('A ring linked from a library: Link / Confirm / Cancel refuse with a clear message',
      all(r == {'CANCELLED'} and 'linked from a library' in m for r, m in results)
      and 'Tooth_Radial' in bpy.data.objects and ra.get_radial(car) is not None, results)
fresh()
cylinder('Tire', segments=32, radius=1.2, depth=0.4)
tire_path = os.path.join(TMP, 'tire_lib.blend')
bpy.ops.wm.save_as_mainfile(filepath=tire_path, copy=True)
fresh()
with bpy.data.libraries.load(tire_path, link=True) as (data_from, data_to):
    data_to.objects = ['Tire']
ti = data_to.objects[0]
C.scene.collection.objects.link(ti)
tooth, car = ring()
car.mch_radial.boolean_target = ti
select_only(car)
r, msg = run(bpy.ops.mch.radial_boolean_link)
check('A linked target is refused (its mesh would change without saving)',
      r == {'CANCELLED'} and 'linked from a library' in msg and not ti.modifiers, msg)
fresh()
cube('LinkedTooth', size=0.3, loc=(1.2, 0, 0))
src_path = os.path.join(TMP, 'tooth_lib.blend')
bpy.ops.wm.save_as_mainfile(filepath=src_path, copy=True)
fresh()
with bpy.data.libraries.load(src_path, link=True) as (data_from, data_to):
    data_to.objects = ['LinkedTooth']
src = data_to.objects[0]
C.scene.collection.objects.link(src)
select_only(src)
r1, m1 = run(bpy.ops.mch.radial_create)
car = C.view_layer.objects.active
r2, m2 = run(bpy.ops.mch.radial_cancel)
check('A linked source still works: Create (snapshot) and Cancel, the library object is not written',
      r1 == {'FINISHED'} and r2 == {'FINISHED'} and not src.hide_get() and src.library is not None
      and not src.modifiers, (m1, m2))

# --- applying twice ---------------------------------------------------------------------------------------------
fresh()
tooth, car = ring()
select_only(car)
r1, _m = run(bpy.ops.mch.radial_bake)
verts = len(car.data.vertices)
r2, m2 = run(bpy.ops.mch.radial_bake)
check('Confirm twice: the second is unavailable, the baked mesh is unchanged',
      r1 == {'FINISHED'} and r2 == {'CANCELLED'} and len(car.data.vertices) == verts == 64, (m2, verts))
fresh()
ti, tooth, car, _r, _m = linked_ring()
select_only(car)
r1, _m = run(bpy.ops.mch.radial_boolean_apply)
verts = len(ti.data.vertices)
r2, m2 = run(bpy.ops.mch.radial_boolean_apply)
check('Boolean apply twice: the second is unavailable (ring gone), the target is unchanged',
      r1 == {'FINISHED'} and r2 == {'CANCELLED'} and len(ti.data.vertices) == verts, m2)

# --- no ID references kept across operators (undo / redo safety) ---------------------------------------------------
held = [k for k, v in vars(ra).items() if isinstance(v, bpy.types.ID)]
held += [f'{cls.__name__}.{k}' for cls in ra.CLASSES for k, v in vars(cls).items() if isinstance(v, bpy.types.ID)]
check('No bpy ID is kept in module globals or operator classes', not held, held)

# --- last: the bpy 5.2.3 segfault (Size 1e25 with the live Exact Boolean on) --------------------------------------
fresh()
ti, tooth, car, _r, _m = linked_ring()
car.mch_radial.scale = 1.0e25
bm_mod = ra.find_boolean_link(car)[1]
check('Size 1e25 with the live cut on pauses it before the depsgraph runs',
      not switch_on(car) and not bm_mod.show_viewport)
C.view_layer.update()
check('... and the depsgraph update survives (bpy 5.2.3 segfaulted here)', True)

mecha_lab.unregister()
summary()
