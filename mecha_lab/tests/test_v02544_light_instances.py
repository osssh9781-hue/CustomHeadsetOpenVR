"""0.24.139 (user: "다른 블렌더에서 가져왔어" - parts linked from other .blend files as collection instances) Light Copies
for linked collection instances: a light set per collection (FULL = the linked collection, off in viewports; LIGHT =
copies of its heavy objects + the rest + its child collections and nested instances mirrored, off in renders); the
instance empties on the light set while not worked on; renders use the linked objects; the library file untouched;
the file saved with the empties on their own collections; a changed library gets new copies; off removes it all."""
import os
import tempfile
import time

import numpy as np

from _harness import bpy, check, fresh, summary

import bmesh  # noqa: E402

import mecha_lab
from mecha_lab import light_copies as lc, quick_render as qr  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
TMP = tempfile.mkdtemp(prefix='mch_lci_')
LIB = os.path.join(TMP, 'parts_lib.blend')


def ball(name, coll, subdiv, loc=(0, 0, 0), radius=1.0):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    coll.objects.link(ob)
    return ob


def write_lib(hero_radius):
    """The library file: 'Leg' (a heavy Hero, a small cube, a Proxy child collection off in renders, a nested
    instance of 'Bolt'), 'Bolt' (a heavy ball)."""
    leg = bpy.data.collections.new('Leg')
    bolt = bpy.data.collections.new('Bolt')
    hero = ball('Hero', leg, 6, radius=hero_radius)
    cme = bpy.data.meshes.new('Box')
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=0.5)
    bm.to_mesh(cme)
    bm.free()
    box = bpy.data.objects.new('Box', cme)
    box.location = (0, 0, 1.6)
    leg.objects.link(box)
    proxy = bpy.data.collections.new('Proxy')
    proxy.hide_render = True
    leg.children.link(proxy)
    ball('ProxyBall', proxy, 1, loc=(0, 0, -1.6), radius=0.3)
    ball('BoltBall', bolt, 6, radius=0.4)
    nest = bpy.data.objects.new('BoltInst', None)
    nest.instance_type = 'COLLECTION'
    nest.instance_collection = bolt
    nest.location = (1.8, 0, 0)
    leg.objects.link(nest)
    bpy.data.libraries.write(LIB, {leg, bolt}, fake_user=True)
    for o in (hero, box, nest) + tuple(bolt.objects) + tuple(proxy.objects):
        me = o.data
        bpy.data.objects.remove(o)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    for c in (proxy, leg, bolt):
        bpy.data.collections.remove(c)


def faces_drawn():
    dg = C.evaluated_depsgraph_get()
    dg.update()
    return sorted((i.object.name.split(' (')[0], len(i.object.data.polygons)) for i in dg.object_instances
                  if i.is_instance and i.object.type == 'MESH')


def run(limit=120.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < limit:
        lc._verify_step(C)
        lc._work_step(C)
        lc.sync(C)
        if not lc.QUEUE and lc.WORK['thread'] is None and not lc.PENDING and not lc.VERIFY:
            break
        time.sleep(0.02)
    lc.sync(C)
    C.view_layer.update()


write_lib(1.0)
with bpy.data.libraries.load(LIB, link=True) as (src, dst):
    dst.collections = ['Leg']
leg = next(c for c in bpy.data.collections if c.name == 'Leg' and c.library is not None)
e1 = bpy.data.objects.new('LegA', None)
e1.instance_type, e1.instance_collection = 'COLLECTION', leg
e2 = bpy.data.objects.new('LegB', None)
e2.instance_type, e2.instance_collection = 'COLLECTION', leg
e2.location = (0, 6, 0)
S.collection.objects.link(e1)
S.collection.objects.link(e2)
for o in S.objects:
    o.select_set(False)
C.view_layer.objects.active = None
before = faces_drawn()
S.mch_light.min_tris = 5000
msg = lc.turn_on(C)
check('on: the linked collection found through its two instances; its two heavy objects queued (Hero, the nested '
      'BoltBall) - not the cube or the proxy ball',
      sorted(q.split('"')[1] for q in lc.QUEUE) == ['BoltBall', 'Hero'] and 'linked collection' in msg, (msg, lc.QUEUE))
run()
W = lc._set_of(lc._id_key(leg))
H = next((c for c in W.children if c.get(lc.ROLE) == 'full'), None) if W else None
L = next((c for c in W.children if c.get(lc.ROLE) == 'light'), None) if W else None
check('a light set: FULL holds the linked collection itself (off in viewports), LIGHT the copies (off in renders), '
      'kept with a fake user', W is not None and H is not None and L is not None and H.hide_viewport
      and not H.hide_render and L.hide_render and not L.hide_viewport and list(H.children) == [leg] and W.use_fake_user)
mirror = next((c for c in L.children if c.get(lc.ROLE) == 'mirror'), None)
check('LIGHT mirrors the collection: the child collection with its own switch (Proxy off in renders), the nested '
      'instance on Bolt\'s own light set', mirror is not None and mirror.hide_render
      and any(o.get(lc.INNER) and o.instance_collection.get(lc.SET) for o in L.objects))
drawn = faces_drawn()
check('both instances on the light set; the viewport draws the copies (~2,048 of 20,480 each), the cube and the '
      'proxy ball as they are - no 20,480-face mesh drawn',
      e1.instance_collection == W and e2.instance_collection == W and all(n < 3000 for _nm, n in drawn)
      and sum(1 for nm, _n in drawn if nm in ('Hero', 'BoltBall')) == 4 and ('Hero', 20480) in before,
      (before, drawn))
check('the library file was not touched (its objects still 20,480 faces; the copies are local objects in no scene)',
      len(next(o for o in leg.all_objects if o.name == 'Hero').data.polygons) == 20480
      and all(o.library is None and o.name not in S.objects for o in bpy.data.objects if o.get(lc.OF)))
n_tris = qr.scene_load(C, S.mch_qrender, depsgraph=C.evaluated_depsgraph_get(), cache=False)[0]
check('Quick Render\'s memory estimate counts the linked objects themselves (2 x 20,480 for Hero and BoltBall + the '
      'small ones)', n_tris >= 40960, n_tris)
# a render uses the linked objects: the copy swapped for a big cube - the render still shows the ball
hero_copy = lc._holder_for(lc._id_key(next(o for o in leg.all_objects if o.name == 'Hero')))
real_me = hero_copy.data
cube = bpy.data.meshes.new('BigCube')
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=2.0)
bm.to_mesh(cube)
bm.free()
hero_copy.data = cube
cam_d = bpy.data.cameras.new('Cam')
cam_d.type, cam_d.ortho_scale = 'ORTHO', 2.2
cam = bpy.data.objects.new('Cam', cam_d)
cam.location = (0, 0, 10)
S.collection.objects.link(cam)
S.camera = cam
S.render.engine = 'CYCLES'
S.cycles.samples, S.cycles.device = 4, 'CPU'
S.render.resolution_x = S.render.resolution_y = 64
S.render.film_transparent = True
S.render.filepath = os.path.join(TMP, 'r.png')
bpy.ops.render.render(write_still=True)
img = bpy.data.images.load(S.render.filepath)
px = np.empty(64 * 64 * 4, np.float32)
img.pixels.foreach_get(px)
alpha = px.reshape(64, 64, 4)[:, :, 3]
check('a Cycles render of the instance shows the linked ball, not the light copy (the copy made a big cube here: its '
      'corner stays empty)', alpha[32, 32] > 0.9 and alpha[4, 4] < 0.1, (float(alpha[32, 32]), float(alpha[4, 4])))
hero_copy.data = real_me
bpy.data.meshes.remove(cube)
bpy.data.objects.remove(cam)
# selected -> its own collection; deselected -> light again after the rest
e1.select_set(True)
lc.sync(C)
sel = (e1.instance_collection == leg, e2.instance_collection == W)
e1.select_set(False)
lc.sync(C)
lc.TOUCH.clear()
lc.sync(C)
check('a selected instance shows the linked collection itself (Make Instances Real never bakes a copy); the other '
      'stays light; deselected: light again', sel == (True, True) and e1.instance_collection == W, sel)
real = lc._browser_open
lc._browser_open = lambda: True
lc.sync(C)
br = (e1.instance_collection == leg, e2.instance_collection == leg)
lc._browser_open = real
lc.sync(C)
check('a file browser open (File > Export ...): every instance on its own collection', br == (True, True)
      and e1.instance_collection == W, br)
lc.full_all([e2])
fa = e2.instance_collection == leg
lc.TOUCH.clear()
lc.sync(C)
check('full_all (an add-on export) on an instance: its own collection, light again once it rests',
      fa and e2.instance_collection == W)
# save: the empties on their own collections in the file; reopened: light again, no copy made anew
path = os.path.join(TMP, 'assembly.blend')
bpy.ops.wm.save_as_mainfile(filepath=path)
after_save = (e1.instance_collection == W, e2.instance_collection == W)
bpy.ops.wm.open_mainfile(filepath=path)
C = bpy.context
S = C.scene
e1, e2 = S.objects['LegA'], S.objects['LegB']
on_disk = (e1.instance_collection.name, e1.instance_collection.library is not None)
made = lc.STATE['made']
run()
W = lc._set_of(json_key := lc._id_key(e1.instance_collection if e1.instance_collection.library else
                                      next(c for c in bpy.data.collections if c.name == 'Leg' and c.library)))
check('saved: the file holds the empties on the linked collection (opened without the add-on: nothing missing); '
      'reopened: compared with the library, back on the light set, no copy made anew',
      after_save == (True, True) and on_disk == ('Leg', True) and W is not None and e1.instance_collection == W
      and lc.STATE['made'] == made, (after_save, on_disk, lc.STATE['made'] - made))
# the library changed (Hero bigger): opened again -> Hero gets a new copy
bpy.ops.wm.save_mainfile()
write_lib(1.5)                                       # (the same names, written over the library file)
bpy.ops.wm.open_mainfile(filepath=path)
C = bpy.context
S = C.scene
made = lc.STATE['made']
n_verify = len(lc.VERIFY)
while lc.VERIFY:                                     # (every light set of the file compared with its library)
    lc._verify_step(C)
queued = sorted(q.split('"')[1] for q in lc.QUEUE)
run()
leg = next(c for c in bpy.data.collections if c.name == 'Leg' and c.library is not None)
hero = next(o for o in leg.all_objects if o.name == 'Hero')
hc = lc._holder_for(lc._id_key(hero))
check('a changed library: only the changed object (Hero) gets a new copy when the file is opened, the light set '
      'back on', queued == ['Hero'] and hc is not None and hc.get(lc.SIG) == lc.signature(hero)
      and S.objects['LegA'].instance_collection.get(lc.SET) and lc.STATE['made'] - made == 1 and n_verify == 2,
      (queued, lc.STATE['made'] - made, n_verify))
# off: everything of ours gone, the empties on the linked collection
msg = lc.turn_off(C)
e1, e2 = S.objects['LegA'], S.objects['LegB']
check('off: the empties on the linked collection, no mark on them, no light set / copy / nested stand-in left',
      e1.instance_collection == leg and e2.instance_collection == leg and not e1.get(lc.INST)
      and not [c for c in bpy.data.collections if c.get(lc.SET) or c.get(lc.ROLE)]
      and not [o for o in bpy.data.objects if o.get('mch_light_holder')], msg)
summary()
