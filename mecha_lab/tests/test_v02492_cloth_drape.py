"""0.24.92 Cloth Drape: lasso a region on a mesh -> an even patch laid over it as a loose cloth (rim pinned), the
body under it a light grid collider, frames on a timer; Enter keeps the cloth object, Esc drops it."""
import inspect
import math

import numpy as np
from _harness import bpy, check, fresh, select_only, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import cloth_drape as cd, cut_engine as ce, tool_state as ts, workspace_ui as wsui

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene


PX = 400.0                      # the outline is in "pixels": 400 px = 1 unit


class Proj:                     # an orthographic "view" from -Y: outline points are (x, z) x PX
    view_dir = Vector((0, 1, 0))

    def ray(self, xy):
        return Vector((xy[0] / PX, -5.0, xy[1] / PX)), Vector((0, 1, 0))


bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=64)
body = C.active_object
select_only(body)
loops = [[(x * PX, y * PX) for x, y in [(-0.4, 0.5), (0.0, 0.6), (0.4, 0.5), (0.45, 0.0), (0.35, -0.45), (0.0, -0.55), (-0.35, -0.45), (-0.45, 0.0)]]]
st = S.mch_cdrape
vals = (st.slack, st.shrink, st.gravity, st.stick, st.keep, st.gap, st.spacing)
check('Settings: Cotton, Looseness 25, Shrink 0, Gravity 200, Stickiness 30, Keep 5, Gap 0.6 %, Pin Rim, 60 frames, Detail 1.5 %',
      st.fabric == 'COTTON' and st.pin_rim and st.frames == 60 and np.allclose(vals, (25.0, 0.0, 200.0, 30.0, 5.0, 0.6, 1.5), atol=1e-5),
      (st.fabric, vals, st.pin_rim, st.frames))
target, me, nb, size = cd.patch_from_loops(C, loops, Proj(), st.spacing)
check('The outline becomes an even patch on the mesh under it (quads, the rim points first)',
      target is body and len(me.polygons) > 500 and nb > 30 and sum(1 for p in me.polygons if len(p.vertices) == 4) > len(me.polygons) * 0.6
      and 0.9 < size < 1.6, (len(me.vertices), len(me.polygons), nb, size))
co_patch = np.array([v.co[:] for v in me.vertices])
check('... and it lies on the sphere (radius 1 within 1 %)', np.allclose(np.linalg.norm(co_patch, axis=1), 1.0, atol=0.01))
info = cd.drape(C, body, me, nb, size, st, frames=30)
co = np.array([v.co[:] for v in me.vertices])
r = np.linalg.norm(co, axis=1)
check('drape: the cloth stays outside the body (collider = the body points under the patch only), it moved, no NaN',
      info['inside'] == 0 and r.min() > 0.99 and info['collider'] < len(body.data.vertices) * 3 and info['collider'] > 500
      and np.linalg.norm(co - co_patch, axis=1).max() > size * 0.02 and np.all(np.isfinite(co)), info)
check('... the rim stayed sewn where it was drawn (within the gap)',
      np.linalg.norm(co[:nb] - co_patch[:nb], axis=1).max() < size * 0.02, np.linalg.norm(co[:nb] - co_patch[:nb], axis=1).max())
check('... in a second or two (30 frames, grid included)', info['time'] < 6.0, round(info['time'], 2))
bpy.data.meshes.remove(me)
# 0.24.95 Gravity below zero: the cloth floats UP (user: "gravity needs minus values too")
st.stop_at_pins = False
zs = {}
for g in (200.0, -200.0):
    st.gravity = g
    target, me_g, nb_g, size_g = cd.patch_from_loops(C, loops, Proj(), st.spacing)
    co_p = np.array([v.co[:] for v in me_g.vertices])
    cd.drape(C, body, me_g, nb_g, size_g, st, frames=30)
    co_g = np.array([v.co[:] for v in me_g.vertices])
    zs[g] = float((co_g[nb_g:, 2] - co_p[nb_g:, 2]).mean())      # the free points' mean rise
    bpy.data.meshes.remove(me_g)
st.gravity = 200.0
check('Gravity -200: the free cloth points go UP (their mean rise above the start is positive), with +200 they go down',
      zs[-200.0] > 0.0 > zs[200.0] and cd.MCH_PG_ClothDrape.bl_rna.properties['gravity'].hard_min <= -600.0, zs)
# 0.24.95 a coarse body: a box with 8 points and big flat faces - the cloth must rest ON the top face, not fall
# through it (the collider samples the faces now; before, only the points were in the grid and the flat between
# them was a hole: the user's recessed floor showed through the wrinkles)
body.location = (0.0, 0.0, -20.0)                     # (the sphere out of the way: the rays must hit the box)
bpy.ops.mesh.primitive_cube_add(size=2.0)
box = C.active_object
box.scale = (1.5, 0.25, 1.5)                          # (the test's view looks from -Y: the big flat face is y = -0.25)
bpy.ops.object.transform_apply(scale=True)
select_only(box)
C.view_layer.update()
st.slack, st.gravity, st.stop_at_pins = 60.0, 300.0, False
loops_box = [[(x * PX, y * PX) for x, y in [(-0.5, 0.5), (0.5, 0.5), (0.5, -0.5), (-0.5, -0.5)]]]
target_b, me_b, nb_b, size_b = cd.patch_from_loops(C, loops_box, Proj(), st.spacing)
info_b = cd.drape(C, box, me_b, nb_b, size_b, st, frames=40)
co_b = np.array([v.co[:] for v in me_b.vertices])
check('A coarse box (8 points, 6 faces): the cloth stays OUTSIDE its big flat face (every point at y <= -0.25 + 0.3 % of '
      'the outline, none through the wall), the collider holds face samples, not just 8 points',
      target_b is box and co_b[:, 1].max() <= -0.25 + 0.003 * size_b and info_b['collider'] > 100,
      (float(co_b[:, 1].max()), info_b['collider'], info_b['inside']))
bpy.data.meshes.remove(me_b)
bpy.data.objects.remove(box)
body.location = (0.0, 0.0, 0.0)
C.view_layer.update()
select_only(body)
st.slack, st.gravity = 25.0, 200.0
# Stop at Pins: a big loose cloth on the sphere's lower half hangs below the rim's lowest point - with the rule it cannot
loops_lo = [[(x * PX, y * PX) for x, y in [(-0.5, 0.1), (0.0, 0.15), (0.5, 0.1), (0.55, -0.4), (0.3, -0.75), (-0.3, -0.75), (-0.55, -0.4)]]]
st.slack = 60.0
for flag in (False, True):
    st.stop_at_pins = flag
    target, me, nb, size = cd.patch_from_loops(C, loops_lo, Proj(), st.spacing)
    co_p = np.array([v.co[:] for v in me.vertices])
    cd.drape(C, body, me, nb, size, st, frames=40)
    co = np.array([v.co[:] for v in me.vertices])
    rim_low = co_p[:nb, 2].min()
    if flag:
        check('Stop at Pins: no point lower than the lowest rim point (half a spacing = about 2 cm allowed)',
              co[:, 2].min() >= rim_low - 0.03, (co[:, 2].min(), rim_low))
    else:
        check('(without it the loose cloth sags below the rim)', co[:, 2].min() < rim_low - 1e-3, (co[:, 2].min(), rim_low))
    bpy.data.meshes.remove(me)
st.slack = 25.0
st.stop_at_pins = False
# Front + Back: the outline on the near AND the far side of the sphere, the side seams sewn
class Proj2(Proj):
    eye = Vector((0, -50, 0)); is_perspective = False
    def to_screen(self, co): return (co[0] * PX, co[2] * PX)
loops_w = [[(x * PX, y * PX) for x, y in [(-0.85, 0.5), (0.0, 0.55), (0.85, 0.5), (0.88, 0.0), (0.85, -0.5), (0.0, -0.55), (-0.85, -0.5), (-0.88, 0.0)]]]
target, me2, nb2, size2, info = cd.patch_two_sides(C, loops_w, Proj2(), st.spacing)
co2 = np.array([v.co[:] for v in me2.vertices])
nf = info['front']
check('patch_two_sides: two pieces in one mesh (front first), the front on y < 0, the back on y > 0, both on the sphere',
      len(co2) == 2 * nf and np.all(co2[:nf, 1] < 0) and np.all(co2[nf:, 1] > 0) and np.allclose(np.linalg.norm(co2, axis=1), 1.0, atol=0.02),
      (len(co2), nf, co2[:nf, 1].max(), co2[nf:, 1].min()))
side, top, bottom = cd.rim_classes([(x, y) for x, y in [(-1, 1), (0, 1.1), (1, 1), (1.1, 0), (1, -1), (0, -1.1), (-1, -1), (-1.1, 0)]], 8)
check('rim_classes: the left / right points are the side seams, the rest top or bottom',
      list(side) == [False, False, False, True, False, False, False, True] and list(top) == [True, True, True, False, False, False, False, False]
      and int(bottom.sum()) == 3)
sew = info['sew']
check('... the seam pairs join a front rim point to the same back rim point; the open top edge indexed on both pieces',
      len(sew) > 10 and np.all(sew[:, 1] - sew[:, 0] == nf) and len(info['top']) > 4 and np.all(np.isin(info['top'][len(info['top']) // 2:], np.arange(nf, 2 * nf))),
      (len(sew), len(info['top'])))
gap0 = np.linalg.norm(co2[sew[:, 1]] - co2[sew[:, 0]], axis=1).mean()
info_d = cd.drape(C, body, me2, nb2, size2, st, frames=60, sew=sew, pin_idx=info['top'])
co3 = np.array([v.co[:] for v in me2.vertices])
check('drape with the seams: the two pieces are pulled together round the sides (the seam gap from ~0.8 to a few cm; the wide bending of Wrinkles 70 holds it a little open), outside the sphere, no NaN',
      info_d['seam_gap'] < 0.1 and np.linalg.norm(co3, axis=1).min() > 0.97 and np.all(np.isfinite(co3)), (gap0, info_d['seam_gap'], np.linalg.norm(co3, axis=1).min()))
n_before = len(me2.vertices)
welded = cd.weld_seams(me2, sew)
check('weld_seams: every seam pair becomes one point', welded == len(sew) and len(me2.vertices) == n_before - len(sew), (welded, len(me2.vertices)))
bpy.data.meshes.remove(me2)
st.two_sides = True
msg = cd.perform(C, loops_w, Proj2())
ob2 = C.view_layer.objects.active
check('perform with Front + Back on: the message names the seam pairs, the session carries them', 'front + back' in msg and cd.SIM.get('sew') is not None
      and cd.SIM['sess']['cloth'].sew is not None, msg)
cd.SIM['running'] = True
for _ in range(8):
    cd.step(C)
check('... frames run, the seam strength ramps up from 0', cd.SIM['sess']['frame'] == 8 and 0 < cd.SIM['sess']['cloth'].sew_strength <= 1.0)
n_before = len(ob2.data.vertices)
msg = cd.confirm(C)
check('Enter welds the seams into one surface', 'welded' in msg and len(ob2.data.vertices) == n_before - len(cd.SIM.get('sew', [])) if cd.SIM else 'welded' in msg and len(ob2.data.vertices) < n_before, msg)
bpy.data.objects.remove(ob2)
st.two_sides = False
# the live flow
msg = cd.perform(C, loops, Proj())
ob = C.view_layer.objects.active
check('perform: a "Cloth Drape" object parented to the body, selected, the session ready (not running)',
      ob is not None and ob.name.startswith('Cloth Drape') and ob.parent is body and cd.sim_active() and not cd.SIM['running']
      and 'Space' in msg, msg)
before = np.array([v.co[:] for v in ob.data.vertices])
cd.SIM['running'] = True
for _ in range(10):
    cd.step(C)
after = np.array([v.co[:] for v in ob.data.vertices])
check('step: frames move the cloth object', cd.SIM['sess']['frame'] == 10 and np.linalg.norm(after - before, axis=1).max() > 1e-4)
st.gravity = 400.0
check('restart with new sliders: back to the laid patch, frame 0', cd.restart(C) and cd.SIM['sess']['frame'] == 0
      and cd.SIM['snapshot'][3] == 400.0)
st.gravity = 200.0
try:
    cd.perform(C, loops, Proj())
    second = False
except Exception as ex:
    second = 'first' in str(ex)
check('A second lasso while one cloth is live is refused (keep or drop it first)', second)
msg = cd.confirm(C)
check('Enter keeps the object, the session ends', 'kept' in msg and not cd.sim_active() and bpy.data.objects.get(ob.name) is not None, msg)
cd.perform(C, loops, Proj())
name = C.view_layer.objects.active.name
msg = cd.cancel(C)
check('Esc drops the cloth object', 'dropped' in msg and bpy.data.objects.get(name) is None and not cd.sim_active())
check('Tool wiring: CDRAPE in the tool table (Cloth group, lasso shape), the cut engine dispatch + colour, the workspace tool with Space',
      'CDRAPE' in ts.TOOL_BY_ID and 'CDRAPE' in ts.SHAPE_TOOLS and any('CDRAPE' in g[1] for g in ts.TOOL_GROUPS if g[0] == 'Cloth')
      and "cloth_drape.perform" in inspect.getsource(ce) and 'CDRAPE' in ce._COLORS
      and any(k[0] == 'mch.cdrape_sim' for k in wsui.MCH_TOOL_cloth_drape.bl_keymap))
src = inspect.getsource(cd.draw)
check('Panel: Drape / Restart / Keep / Drop + every slider', all(k in src for k in ("'slack'", "'shrink'", "'gravity'", "'stick'", "'keep'", "'gap'", "'stop_at_pins'", "'two_sides'",
                                                                                   "'spacing'", "'pin_rim'", "'frames'", "'fabric'", 'Keep (Enter)', 'Drop (Esc)')))
# -- the mesh itself as the cloth (a remeshed piece of your own) ----------------------------------------------------
bpy.ops.mesh.primitive_grid_add(size=1.2, x_subdivisions=40, y_subdivisions=40, location=(0, 0, 1.08))
piece = C.active_object
piece.name = 'Piece'
piece.rotation_euler = (0.0, 0.0, 0.3)
body.select_set(True)
piece.select_set(True)
C.view_layer.objects.active = piece
check('body_for: the other selected mesh is the body', cd.body_for(C, piece) is body)
before = np.array([v.co[:] for v in piece.data.vertices])
msg = cd.perform_mesh(C, piece, body)
check('Drape This Mesh: the grid itself is the cloth on the sphere, its open edges pinned, a backup kept',
      cd.sim_active() and cd.SIM['mode'] == 'MESH' and cd.SIM['ob'] == 'Piece' and 'pinned' in msg
      and bpy.data.meshes.get(cd.SIM['backup']) is not None and int(np.count_nonzero(cd.SIM['sess']['cloth'].pin >= 1)) == 4 * 40, msg)
cd.SIM['running'] = True
for _ in range(40):
    cd.step(C)
after = np.array([v.co[:] for v in piece.data.vertices])
world = after @ np.array(piece.matrix_world.to_3x3()).T + np.array(piece.matrix_world.translation)
check('... it drops onto the sphere and stays outside it (world space, the sphere is the collider)',
      np.linalg.norm(after - before, axis=1).max() > 0.05 and np.linalg.norm(world, axis=1).min() > 0.985,
      (np.linalg.norm(after - before, axis=1).max(), np.linalg.norm(world, axis=1).min()))
msg = cd.cancel(C)
restored = np.array([v.co[:] for v in piece.data.vertices])
check('Esc puts the mesh back as it was', 'put back' in msg and np.allclose(restored, before, atol=1e-6) and not cd.sim_active()
      and 'Piece_mch_cd_backup' not in bpy.data.meshes, msg)
cd.perform_mesh(C, piece, body)
msg = cd.confirm(C)
check('Enter keeps the changed mesh, the backup gone', 'kept' in msg and 'Piece_mch_cd_backup' not in bpy.data.meshes
      and not np.allclose(np.array([v.co[:] for v in piece.data.vertices]), before))
check('The operator + the panel button exist', hasattr(bpy.types, 'MCH_OT_cdrape_mesh') and 'mch.cdrape_mesh' in inspect.getsource(cd.draw))
# -- the body's wrinkle lines as tubes under the cloth ---------------------------------------------------------------
import json
from mecha_lab import wrinkle_lines as wl
pts = [Vector((math.sin(t) * 0.866, -math.cos(t) * 0.866, 0.5)) for t in np.linspace(-0.8, 0.8, 12)]   # an arc on the back (-Y) at z = 0.5
body[wl.PROP] = json.dumps([dict(pts=[list(p) for p in pts], nrm=[list(p.normalized()) for p in pts], strength=1.0)])
wl._CACHE.pop(body.name, None)
st.use_lines = True
target, me2, nb2, size2 = cd.patch_from_loops(C, loops, Proj(), st.spacing)
info_t = cd.drape(C, body, me2, nb2, size2, st, frames=30)
co_t = np.array([v.co[:] for v in me2.vertices])
band_t = co_t[(co_t[:, 2] > 0.42) & (co_t[:, 2] < 0.58) & (co_t[:, 1] < -0.7)]
st.use_lines = False
me3 = cd.patch_from_loops(C, loops, Proj(), st.spacing)[1]
info_f = cd.drape(C, body, me3, nb2, size2, st, frames=30)
co_f = np.array([v.co[:] for v in me3.vertices])
band_f = co_f[(co_f[:, 2] > 0.42) & (co_f[:, 2] < 0.58) & (co_f[:, 1] < -0.7)]
lift = np.linalg.norm(band_t, axis=1).max() - np.linalg.norm(band_f, axis=1).max()
check('Lines as Tubes: over the drawn line the cloth rests higher than without it (a tube under it, about the tube radius)',
      info_t['collider'] > 0 and len(band_t) > 5 and lift > 0.012, (lift, len(band_t)))
bpy.data.meshes.remove(me3)
st.use_lines = True
check('The Draw Lines operator + the Lines as Tubes toggle + the tube sliders are in the panel',
      hasattr(bpy.types, 'MCH_OT_cdrape_lines') and all(k in inspect.getsource(cd.draw) for k in ("'use_lines'", 'mch.cdrape_lines', "'lift'", "'fade'")))
bpy.data.meshes.remove(me2)
from mecha_lab import tool_presets
name, pg = tool_presets.group_for(S, 'CDRAPE')
check('Tool Presets save the Cloth Drape sliders (scene.mch_cdrape)', name == 'mch_cdrape' and pg is not None)
# ---- 0.24.95 Padding (quilting) + Trim (piping) ----------------------------------------------------------------
on = cd.quilt_lines(np.array([[0.0, 0.0], [0.1, 0.05], [0.2, 0.2], [0.05, 0.1], [0.4, 0.33]]), 0.2, 0.011, 'SQUARE')
check('quilt_lines SQUARE, cell 0.2: points on a seam (0,0), (0.2,0.2), (0.4, 0.33 -> near 0.4 across) count, the others not',
      list(on) == [True, False, True, False, True], list(on))
on_d = cd.quilt_lines(np.array([[0.0, 0.0], [0.1, 0.1], [0.1, -0.1]]), 0.2, 0.011, 'DIAMOND')
check('quilt_lines DIAMOND: the grid turned 45 degrees ((0.1, 0.1) sits on a turned seam)', bool(on_d[0]) and bool(on_d[1]), list(on_d))
st.padding, st.pad_pattern, st.pad_size, st.pad_puff, st.slack, st.gravity, st.stop_at_pins = True, 'DIAMOND', 20.0, 100.0, 30.0, 100.0, False
target, me_p, nb_p, size_p = cd.patch_from_loops(C, loops, Proj(), st.spacing)
uv = cd.read_uv(me_p)
check('The patch keeps its screen layout on the mesh (uv 0..1 of the outline size)', uv is not None and uv.min() >= -1e-6 and uv.max() <= 1.0 + 1e-6 and len(uv) == len(me_p.vertices))
sess = cd.build(C, body, me_p, nb_p, size_p, st)
pin = sess['cloth'].pin
check('Padding: the seam points are held (far more pins than the rim alone), the puff is on',
      sess.get('quilt', 0) > 0 and (pin >= 1).sum() > nb_p * 1.5 and sess.get('puff', 0) > 0, (sess.get('quilt'), int((pin >= 1).sum()), nb_p))
for _ in range(40):
    cd.advance(sess, st)
co_q = sess['cloth'].co
r_q = np.linalg.norm(co_q, axis=1)
seam = pin >= 1
check('... after 40 frames the cells stand off the sphere above the seams (free points higher than seam points), nothing inside the sphere',
      r_q[~seam].mean() > r_q[seam].mean() + 0.005 and r_q.min() > 0.99 and np.all(np.isfinite(co_q)),
      (float(r_q[~seam].mean()), float(r_q[seam].mean()), float(r_q.min())))
bpy.data.meshes.remove(me_p)
# Whole: no seams, the drawn area puffs as one cushion (user: "no quilting, just the shape I drew puffing up")
st.pad_pattern = 'NONE'
target, me_w, nb_w, size_w = cd.patch_from_loops(C, loops, Proj(), st.spacing)
sess_w = cd.build(C, body, me_w, nb_w, size_w, st)
pin_w = sess_w['cloth'].pin
for _ in range(40):
    cd.advance(sess_w, st)
r_w = np.linalg.norm(sess_w['cloth'].co, axis=1)
check('Padding "Whole": only the rim is held (no seam pins), the puff is on, and the middle stands higher off the sphere than the rim',
      int((pin_w >= 1).sum()) == nb_w and sess_w.get('puff', 0) > 0 and sess_w.get('quilt', 0) == 0 and r_w[nb_w:].mean() > r_w[:nb_w].mean() + 0.01,
      (int((pin_w >= 1).sum()), nb_w, float(r_w[nb_w:].mean()), float(r_w[:nb_w].mean())))
bpy.data.meshes.remove(me_w)
st.pad_pattern = 'DIAMOND'
st.padding = False
st.trim, st.trim_width = True, 2.0
msg = cd.perform(C, loops, Proj())
ob_c = cd._ob()
msg2 = cd.confirm(C)
trim_ob = bpy.data.objects.get('Cloth Trim')
rim_n = cd.SIM.get('nb') if cd.SIM else None
check('Trim: on Keep a piping tube object "Cloth Trim", child of the cloth, 8 faces per rim edge, round the outline',
      trim_ob is not None and trim_ob.parent == ob_c and len(trim_ob.data.polygons) == len(cd.rim_loops(ob_c.data)[0][0]) * 8
      and 'trim on 1 edge loops' in msg2, (len(trim_ob.data.polygons) if trim_ob else None, msg2))
co_t = np.array([v.co[:] for v in trim_ob.data.vertices])
co_r = np.array([ob_c.data.vertices[i].co[:] for i in cd.rim_loops(ob_c.data)[0][0]])
from mathutils.kdtree import KDTree
kd = KDTree(len(co_r)); [kd.insert(Vector(c), i) for i, c in enumerate(co_r)]; kd.balance()
far = max(kd.find(Vector(c))[2] for c in co_t)
check('... every trim point within the piping radius of the rim', far <= size_p * 0.02 / 2 + 1e-3, far)
st.trim = False
for o in (trim_ob, ob_c):
    if o is not None:
        bpy.data.objects.remove(o)
check('Settings snapshot covers the new options (a change restarts the drape)', all(k in inspect.getsource(cd._snapshot) for k in ("'padding'", "'pad_size'", "'trim'", "'trim_width'")))
summary()
