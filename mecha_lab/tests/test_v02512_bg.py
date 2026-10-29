"""0.24.86 Quad Remesh / Re-Fix in a background process: the mesh goes out as a .blend, a second Blender (here: this
python with the bpy module) runs the action, the result comes back and lands on the part; cancel; a part that
changed meanwhile keeps its own mesh."""
import os
import time

import numpy as np

os.environ["MECH_BG_FORCE"] = "1"      # (headless Blender runs inline unless asked: the worker is what is tested here)

from _harness import bpy, check, cube, fresh, non_manifold, summary

import mecha_lab
from mecha_lab import bg_jobs, core_geometry as cg, mesh_tools, zb_sculpt as zs

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
zb = S.mch_zb


def body(sub, name):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=sub, radius=1.0)
    ob = C.active_object
    ob.name = name
    m = ob.modifiers.new('d', 'DISPLACE')
    t = bpy.data.textures.new('t', 'CLOUDS')
    t.noise_scale = 0.3
    m.texture = t
    m.strength = 0.2
    with C.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier='d')
    return ob


def wait(ob, limit=240):
    t = time.perf_counter()
    while bg_jobs.busy(ob) and time.perf_counter() - t < limit:
        time.sleep(0.5)
    return bg_jobs.poll()


check('the shelf has a Background toggle (on) and the worker can run here', zb.bg_jobs is True and bg_jobs.can_run())
ob = body(6, 'Big')                                   # 82k faces: over BG_MIN
n0 = len(ob.data.polygons)
zb.qr_target, zb.qr_mode = 4.0, 'MOSTLY'
msg = mesh_tools.run_one(C, ob, zb, 'QUAD_REMESH')
check('Quad Remesh on an 82k-face part with Background on: starts a worker and returns at once, the part untouched',
      'started in the background' in msg and bg_jobs.busy(ob) and len(ob.data.polygons) == n0, msg[:90])
check('... the status line says it runs, with a Cancel button', 'running in the background' in bg_jobs.status(ob)
      and "'mch.bg_cancel'" in open(bg_jobs.__file__).read())
msg2 = mesh_tools.run_one(C, ob, zb, 'QUAD_REMESH')
check('... a second start on the same part is refused while it runs', 'already running' in msg2, msg2[:80])
ended = wait(ob)
res = bg_jobs.last_message(ob)
check('... when the worker is done the result lands on the part: quads, far fewer faces, closed, message with the '
      'background time', ended and 'Quad Remesh' in res and 'background' in res and 1000 < len(ob.data.polygons) < 12000
      and non_manifold(ob) == 0 and sum(len(p.vertices) == 4 for p in ob.data.polygons) > 0.5 * len(ob.data.polygons),
      (res[:120], len(ob.data.polygons), non_manifold(ob)))
check('... nothing runs any more, the temp files are gone', not bg_jobs.busy(ob) and not bg_jobs.status(ob)
      and not __import__('os').path.exists(bg_jobs.JOBS['Big']['dir']))

# --- cancel ----------------------------------------------------------------------------------------------------------
ob2 = body(6, 'Big2')
n2 = len(ob2.data.polygons)
msg = mesh_tools.run_one(C, ob2, zb, 'QUAD_REMESH')
time.sleep(1.0)
out = bg_jobs.cancel('Big2')
check('Cancel: the worker is killed, the part keeps its mesh, the status says cancelled', 'cancelled' in out
      and not bg_jobs.busy(ob2) and len(ob2.data.polygons) == n2, (out, len(ob2.data.polygons), n2))

# --- the part changed while the worker ran: the result is dropped ---------------------------------------------------
ob3 = body(6, 'Big3')
msg = mesh_tools.run_one(C, ob3, zb, 'QUAD_REMESH')
ob3.data.vertices[0].co.x += 0.0
bpy.ops.object.select_all(action='DESELECT')
ob3.select_set(True)
C.view_layer.objects.active = ob3
import bmesh
bm = bmesh.new()
bm.from_mesh(ob3.data)
bmesh.ops.delete(bm, geom=bm.faces[:10], context='FACES')      # (the user cut something meanwhile)
bm.to_mesh(ob3.data)
bm.free()
n3 = len(ob3.data.polygons)
ended = wait(ob3)
check('a part that changed while the worker ran keeps its own mesh and the message says the result was dropped',
      ended and 'dropped' in bg_jobs.last_message(ob3) and len(ob3.data.polygons) == n3, (bg_jobs.last_message(ob3)[:100], len(ob3.data.polygons), n3))

# --- small parts and Background off run inline ------------------------------------------------------------------------
small = cube('Small', 1.0, loc=(0, 5, 0))
msg = mesh_tools.run_one(C, small, zb, 'QUAD_REMESH')
check('a small part (under 20k faces) runs inline as before', 'started in the background' not in msg and msg.startswith('Quad Remesh'), msg[:60])
zb.bg_jobs = False
ob4 = body(6, 'Big4')
msg = mesh_tools.run_one(C, ob4, zb, 'QUAD_REMESH')
check('Background off: the big part runs inline too', 'started in the background' not in msg and len(ob4.data.polygons) < 12000, msg[:60])
zb.bg_jobs = True

# --- Re-Fix in the background -----------------------------------------------------------------------------------------
ob5 = body(6, 'Big5')
zb.refix_finish, zb.refix_faces = 'DECIMATE', 3000
msg = zs.run_action(C, ob5, zb, 'REFIX') if hasattr(zs, 'run_action') else mesh_tools.run_one(C, ob5, zb, 'REFIX')
check('Re-Fix on a big part with Background on: starts a worker', 'started in the background' in msg, msg[:80])
ended = wait(ob5)
res = bg_jobs.last_message(ob5)
check('... Re-Fix result lands: a clean light mesh, closed', ended and res.startswith('Re-Fix') and 'background' in res
      and len(ob5.data.polygons) < 20000 and non_manifold(ob5) == 0, (res[:120], len(ob5.data.polygons)))
check('the Mesh Tools and ZBrush panels show the Background toggle and the status row',
      "'bg_jobs'" in open(mesh_tools.__file__).read() and "bg_jobs.draw_status" in open(__import__('mecha_lab.zb_ui', fromlist=['x']).__file__).read())
summary()
