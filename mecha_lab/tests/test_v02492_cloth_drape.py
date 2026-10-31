"""0.24.92 Cloth Drape: lasso a region on a mesh -> an even patch laid over it as a loose cloth (rim pinned), the
body under it a light grid collider, frames on a timer; Enter keeps the cloth object, Esc drops it."""
import inspect
import math
import types

import numpy as np
from _harness import bpy, check, fresh, select_only, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import cloth_drape as cd, core_geometry as cg, cut_engine as ce, lasso_sketch as ls, surface_lasso as sl, tool_state as ts, workspace_ui as wsui, wrinkle_lines as wl

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
kept = bpy.data.objects.get(ob.name)
kept_me = kept.data
bpy.data.objects.remove(kept)                 # (a kept cloth lies over the ball: a new lasso there would land on it)
bpy.data.meshes.remove(kept_me)
cd.perform(C, loops, Proj())
name = C.view_layer.objects.active.name
msg = cd.cancel(C)
check('Esc drops the cloth object', 'dropped' in msg and bpy.data.objects.get(name) is None and not cd.sim_active())
# ---- 0.24.95 the lasso cloth gets Offset + Cloth Detail before Space, like the mask / cape cloths (user: "라쏘로 뽑아서
# 붙일 수 있지? ... 그래 넣어줘")
st.offset = 2.0
cd.perform(C, loops, Proj())
ob_a = C.view_layer.objects.active
surf = cd.SIM['surface']
shown = lambda: np.array([v.co[:] for v in ob_a.data.vertices])
d0 = np.linalg.norm(shown() - surf, axis=1)
csize = float(np.linalg.norm(surf.max(0) - surf.min(0)))
check('Lasso cloth: before Space it is shown lifted off the ball the same everywhere (where the drape starts: the rest shape)',
      cd.SIM['source'] == 'AREA' and d0.min() > 1e-3 and np.ptp(d0) < 1e-6 and np.allclose(cd.SIM['sess']['cloth'].init, shown(), atol=1e-6),
      (d0.min(), np.ptp(d0)))
st.offset = 8.0
d1 = np.linalg.norm(shown() - surf, axis=1)
check('Offset 8 %: the waiting lasso cloth lifts at once to 8 % of its size (no new lasso)',
      abs(d1.mean() - csize * 0.08) < csize * 0.003 and np.ptp(d1) < 1e-6, (d1.mean(), csize * 0.08))
n0 = len(ob_a.data.vertices)
sp0 = st.spacing
st.spacing = sp0 / 2.0                       # (the slider: the waiting cloth is made again from the same lasso)
n1 = len(ob_a.data.vertices)
surf1 = cd.SIM['surface']
check('Cloth Detail halved before Space: the lasso cloth is made again at once from the same lasso, more points (2 x +), '
      'laid on the ball (not on the old cloth over it), shown lifted by Offset',
      n1 > 2.0 * n0 and np.allclose(np.linalg.norm(surf1, axis=1), 1.0, atol=0.02)
      and abs(np.linalg.norm(shown() - surf1, axis=1).mean() - float(np.linalg.norm(surf1.max(0) - surf1.min(0))) * 0.08) < csize * 0.003,
      (n0, n1, np.linalg.norm(surf1, axis=1).min()))
cd.restart(C)
check('Space after it: the drape runs the new cloth from the shape on screen (frame 0)',
      cd.SIM['running'] and len(cd.SIM['sess']['cloth'].co) == n1 and cd.SIM['sess']['frame'] == 0
      and abs(np.linalg.norm(cd.SIM['sess']['cloth'].init - surf1, axis=1).mean() - float(np.linalg.norm(surf1.max(0) - surf1.min(0))) * 0.08) < csize * 0.003)
st.spacing = sp0
check('... the slider while it runs leaves the running cloth alone', len(ob_a.data.vertices) == n1)
cd.cancel(C)
st.spacing = sp0 / 2.0
_t, me_fresh, _nb, _sz = cd.patch_from_loops(C, loops, Proj(), st.spacing)
check('... the same cloth a new lasso at that Cloth Detail gives (same points)', len(me_fresh.vertices) == n1, (len(me_fresh.vertices), n1))
bpy.data.meshes.remove(me_fresh)
st.spacing = sp0
st.offset = 2.0
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
# ---- 0.24.95 a COARSE CURVED body (ico sphere, 320 big facets): the cloth lies on the smooth surface the facets
# stand for (Phong samples), not on the facets (user: "is it because it is curved that it sticks like this?" -
# the facet ridges showed through the cloth)
body.location = (0.0, 0.0, -20.0)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.0)
dome = C.active_object
select_only(dome)
C.view_layer.update()
st.slack, st.gravity, st.stop_at_pins = 10.0, 100.0, False
loops_d = [[(x * PX, y * PX) for x, y in [(-0.45, 0.45), (0.45, 0.45), (0.45, -0.45), (-0.45, -0.45)]]]
target_d, me_d, nb_d, size_d = cd.patch_from_loops(C, loops_d, Proj(), st.spacing)
cd.drape(C, dome, me_d, nb_d, size_d, st, frames=40)
r_d = np.linalg.norm(np.array([v.co[:] for v in me_d.vertices]), axis=1)
check('Coarse ico dome: the cloth rides the smooth surface - no point down on a facet (radius min > 0.955; the facet '
      'centres sit at 0.935) and the radius spread under 0.03 (facets alone: 0.0355)',
      target_d is dome and r_d.min() > 0.955 and r_d.std() < 0.03, (float(r_d.min()), float(r_d.std())))
bpy.data.meshes.remove(me_d)
bpy.data.objects.remove(dome)
body.location = (0.0, 0.0, 0.0)
C.view_layer.update()
select_only(body)
st.slack, st.gravity = 25.0, 200.0

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

# ---- 0.24.95 Sketch mode (user: "클로스 드레이프에는 스케치 모드가 없어?"): Sketch on -> outlines add up, Enter = the cloth
ls.clear(S)
st.two_sides = False
TOPP = cg.OrthoProjector(Quaternion(), center=Vector((0, 0, 0)), pixels_per_unit=200.0, size=(1000, 1000))   # top view
msg = ls.add(C, 'CDRAPE', [[(420, 420), (580, 420), (580, 580), (420, 580)]], TOPP)
check('Cloth Drape is a sketch tool: with Sketch on a drawn outline joins the sketch, no cloth yet',
      'CDRAPE' in ls.MODES and ls.data(S) is not None and ls.data(S)['mode'] == 'CDRAPE' and not cd.sim_active(), msg)
ls.add(C, 'CDRAPE', [[(560, 460), (660, 460), (660, 540), (560, 540)]], TOPP)        # a second shape widens it to the right
msg = ls.commit(C)
ob = C.view_layer.objects.active
co_s = np.array([v.co[:] for v in ob.data.vertices])
check('Enter: the combined outline becomes one Cloth Drape (session ready, sketch cleared)',
      cd.sim_active() and ob.name.startswith('Cloth Drape') and ls.data(S) is None and 'Space' in msg, msg)
check('... the cloth covers both shapes (x from -0.4 to +0.8 units, one piece)',
      co_s[:, 0].min() < -0.35 and co_s[:, 0].max() > 0.75 and len(ob.data.vertices) > 200, (co_s[:, 0].min(), co_s[:, 0].max()))
cd.cancel(C)

# ---- 0.24.95 grab while it drapes (user: "중간중간 메시에 들어갈 때가 있어서 내가 잡아서 뗄 수 있게, 재생하는 중에")
st.slack, st.gravity, st.stop_at_pins = 25.0, 200.0, False
cd.perform(C, loops, Proj())
ob = C.view_layer.objects.active
sess = cd.SIM['sess']
cl = sess['cloth']
for _ in range(10):
    cd.advance(sess, st)
free = np.nonzero(cl.pin < 1.0)[0]
k = int(free[np.argmax(cl.co[free, 2])])                       # the highest free point: pull it further up
xy = np.c_[cl.co[:, 0] * PX + 500.0, cl.co[:, 2] * PX + 500.0]  # a fake screen: x -> px, z -> py (the test's view from -Y)
grab = cd.grab_pick(sess, xy, (xy[k, 0] + 5.0, xy[k, 1] - 3.0), sess['spacing'])
check('grab_pick: a press within 40 px takes the nearest free point and its neighbours (weights 1 at the centre, falling to 0)',
      grab is not None and np.hypot(*(xy[grab['centre']] - xy[k])) < 40 and len(grab['idx']) > 5
      and abs(grab['w'][list(grab['idx']).index(grab['centre'])] - 1.0) < 1e-9
      and grab['w'].min() >= 0.0 and grab['w'].max() <= 1.0, None if grab is None else (grab['centre'], k, len(grab['idx'])))
k = grab['centre']
check('... a press far from the cloth grabs nothing (the lasso tool gets the click)', cd.grab_pick(sess, xy, (-5000.0, -5000.0), sess['spacing']) is None)
check('... pinned rim points are never grabbed', all(cl.pin[i] < 1.0 for i in grab['idx']))
z0 = cl.co[k, 2]
start = cl.co[grab['idx']].copy()
target = cd.grab_move(sess, grab, np.array([0.0, 0.0, 0.4]), running=True)
for _ in range(8):
    cd.advance(sess, st)                                           # the drape runs on while the hand holds the points
check('grab_move while draping: the held point follows the hand through the frames (0.4 up, gravity notwithstanding)',
      abs(cl.co[k, 2] - (z0 + 0.4)) < 0.02 and cl.hold is not None, (cl.co[k, 2], z0 + 0.4))
moved = np.linalg.norm(cl.co[grab['idx']] - start, axis=1)
check('... the neighbours came along less the further out (weights)', moved[grab['w'] > 0.8].mean() > moved[grab['w'] < 0.2].mean() + 0.05,
      (moved[grab['w'] > 0.8].mean(), moved[grab['w'] < 0.2].mean()))
cd.grab_release(sess, grab)
check('grab_release: the hold is gone, no velocity left on the grabbed points', cl.hold is None and np.allclose(cl.prev[grab['idx']], cl.co[grab['idx']]))
cd.advance(sess, st)
cd.SIM['running'] = False
grab2 = cd.grab_pick(sess, xy, (xy[k, 0], xy[k, 1]), sess['spacing'])
c0 = cl.co[k].copy()
cd.grab_move(sess, grab2, np.array([0.2, 0.0, 0.0]), running=False)
check('paused: the grabbed points are put under the hand straight away', np.allclose(cl.co[k], c0 + (0.2, 0.0, 0.0)) and np.allclose(cl.prev[k], cl.co[k]))
cd.grab_release(sess, grab2)
check('Esc ends the session with no grab left', 'dropped' in cd.cancel(C) and cd.SIM.get('grab') is None)
check('The modal takes the left mouse for the grab and the status line says so',
      all(k_ in inspect.getsource(cd.MCH_OT_cdrape_sim.modal) for k_ in ("grab_start_event", "grab_move_event", "grab_end_event", "'LEFTMOUSE'"))
      and 'drag the cloth' in inspect.getsource(cd.status))
# ---- 0.24.95 Surface mode (user: "그냥 표면에 그리는 모드도 만들어 주라"): points clicked ON the body, orbit between
S.mch_brush.surface_mode = True
check('Cloth Drape is a Surface Lasso tool (the Surface button shows for it)', sl.enabled(C, 'CDRAPE') and 'CDRAPE' in sl.PATCH_MODES
      and "'CDRAPE'}:\n        sk.prop(brush, 'surface_mode'" in inspect.getsource(wsui))
FRONT = cg.OrthoProjector(Quaternion((1, 0, 0), math.radians(90)))                      # looking along +Y at the sphere
SIDE = cg.OrthoProjector(Quaternion((0, 0, 1), math.radians(90)) @ Quaternion((1, 0, 0), math.radians(90)))
VIEW = [FRONT]
sl.make_projector = lambda region, rv3d: VIEW[0]


class Ctx:
    def __init__(self):
        self.area = types.SimpleNamespace(type='VIEW_3D', header_text_set=lambda t: None, tag_redraw=lambda: None)
        self.region = types.SimpleNamespace(width=1000, height=1000)
        self.region_data = object()

    scene = property(lambda self: bpy.context.scene)
    view_layer = property(lambda self: bpy.context.view_layer)
    selected_objects = property(lambda self: bpy.context.selected_objects)
    collection = property(lambda self: bpy.context.scene.collection)
    preferences = property(lambda self: bpy.context.preferences)

    def evaluated_depsgraph_get(self):
        return bpy.context.evaluated_depsgraph_get()


select_only(body)
ctx, op = Ctx(), sl.SurfaceLogic()
VIEW[0] = FRONT
op.start(ctx, (450, 450), 'CDRAPE')
for xy in [(540, 450), (540, 560)]:
    op.click(ctx, xy)
VIEW[0] = SIDE                                       # orbit while drawing: the outline goes round to the side
for xy in [(450, 560), (450, 450)]:
    op.click(ctx, xy)
check('Surface: 5 points stuck on the sphere, seen from two views', len(op.points) == 5 and all(abs(p.length - 1.0) < 0.05 for p in op.world_points()),
      [round(p.length, 3) for p in op.world_points()])
parts, msg = op.finish(ctx)
ob_s = C.view_layer.objects.active
check('Enter: a Cloth Drape laid over the drawn region (session ready)', parts is not None and ob_s is not None and ob_s.name.startswith('Cloth Drape')
      and cd.sim_active() and not cd.SIM['running'], msg)
if parts is not None:
    co_s = np.array([(ob_s.matrix_world @ v.co)[:] for v in ob_s.data.vertices])
    r_s = np.linalg.norm(co_s, axis=1)
    check('... the cloth sits just off the sphere on the drawn (front-right) side', r_s.min() > 0.99 and r_s.max() < 1.1
          and co_s[:, 0].mean() > 0.05 and co_s[:, 1].mean() < -0.3, (r_s.min(), r_s.max(), co_s[:, 0].mean(), co_s[:, 1].mean()))
    cd.cancel(C)
S.mch_brush.surface_mode = False
# ---- 0.24.95 Drape Mask (user: "지브러시 탭에서 하는 것처럼 마스크 씌워서는 못해?"): the masked faces lift off as the cloth
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 30))
cube = C.active_object
fm = cd.faces_mesh(cube.data, [0, 1])
check('faces_mesh: two cube faces -> a mesh of 2 faces on their 6 (or 8) points, smooth, local coordinates kept',
      len(fm.polygons) == 2 and len(fm.vertices) in (6, 8) and all(p.use_smooth for p in fm.polygons)
      and all(abs(abs(v.co.x) - 1.0) < 1e-6 for v in fm.vertices), (len(fm.polygons), len(fm.vertices)))
bpy.data.meshes.remove(fm)
bpy.data.objects.remove(cube)
select_only(body)
check('masked_faces: no mask attribute -> nothing', len(cd.masked_faces(body.data)) == 0)
try:
    cd.perform_masked(C, body)
    check('perform_masked without a mask raises', False)
except cg.CutError as ex:
    check('perform_masked without a mask raises (paint one first)', 'mask' in str(ex), str(ex))
att = body.data.attributes.new(cd.MASK_ATTR, 'FLOAT', 'POINT')
zs = np.array([v.co.z for v in body.data.vertices])
att.data.foreach_set('value', (zs > 0.45).astype(np.float32))        # the cap of the sphere masked
n_masked = len(cd.masked_faces(body.data))
check('masked_faces: the cap faces (corner mask averaging >= 0.5: at least half the corners) and nothing else',
      len(body.data.polygons) * 0.2 < n_masked < len(body.data.polygons) * 0.45
      and all(sum(zs[i] > 0.45 for i in body.data.polygons[f].vertices) * 2 >= len(body.data.polygons[f].vertices) for f in cd.masked_faces(body.data)),
      (n_masked, len(body.data.polygons)))
st.mask_points = 100000                                          # more than the body has there: the faces as they are
msg = cd.perform_masked(C, body)
ob_m = C.view_layer.objects.active
check('perform_masked: a "Cloth Drape" object of the masked faces, parented to the body, the session ready',
      ob_m is not None and ob_m.name.startswith('Cloth Drape') and ob_m.parent is body and len(ob_m.data.polygons) == n_masked
      and cd.sim_active() and not cd.SIM['running'] and cd.SIM.get('source') == 'MASK', msg)
sess = cd.SIM['sess']
rim = int((sess['cloth'].pin >= 1).sum())
check('... its open rim is pinned (Pin Rim), the rest free', 0 < rim < len(ob_m.data.vertices) and 'pinned' in msg, (rim, len(ob_m.data.vertices)))
st.gravity = 200.0
cd.SIM['running'] = True
for _ in range(15):
    cd.step(C)
co_m = np.array([v.co[:] for v in ob_m.data.vertices])
check('... it drapes on the sphere like a lasso cloth (outside the body, moved, no NaN)',
      np.linalg.norm(co_m, axis=1).min() > 0.99 and np.all(np.isfinite(co_m)) and sess['frame'] == 15, np.linalg.norm(co_m, axis=1).min())
msg = cd.confirm(C)
check('Enter keeps the cloth object', 'kept' in msg and bpy.data.objects.get(ob_m.name) is not None and not cd.sim_active(), msg)
bpy.data.objects.remove(ob_m)
# the lighter cloth (user: "마스크로 뽑은 면을 좀 더 낮은 면으로 바꾸고 그다음 클로스를 돌리는 게 낫겠는데")
st.mask_points = 500
msg = cd.perform_masked(C, body)
ob_l = C.view_layer.objects.active
n_dense = len(cd.faces_mesh(body.data, cd.masked_faces(body.data)).vertices)
co_l = np.array([v.co[:] for v in ob_l.data.vertices])
rim_l = wl.boundary_verts(ob_l.data)
check('Cloth Points 500: the masked patch is rebuilt lighter (about 500 points instead of the body\'s), the rim kept',
      450 < len(co_l) < 560 and n_dense > 1500 and 'lighter' in msg and len(rim_l) > 30, (len(co_l), n_dense, len(rim_l), msg))
surf = cd.SIM['surface']
check('... triangles, every point of the laid patch on the sphere (relaxed and put back on the body)',
      all(len(p.vertices) == 3 for p in ob_l.data.polygons) and np.abs(np.linalg.norm(surf, axis=1) - 1.0).max() < 0.005,
      np.abs(np.linalg.norm(surf, axis=1) - 1.0).max())
el = np.linalg.norm(surf[[e.vertices[0] for e in ob_l.data.edges]] - surf[[e.vertices[1] for e in ob_l.data.edges]], axis=1)
check('... even edges (isotropic remesh: longest under 2 x the median, shortest over 0.4 x)',
      el.max() < 2.0 * np.median(el) and el.min() > 0.4 * np.median(el), (el.min(), np.median(el), el.max()))
cd.SIM['running'] = True
for _ in range(10):
    cd.step(C)
co_l2 = np.array([v.co[:] for v in ob_l.data.vertices])
check('... and it drapes (outside the sphere, finite)', np.linalg.norm(co_l2, axis=1).min() > 0.99 and np.all(np.isfinite(co_l2)))
cd.cancel(C)
st.mask_points = 0
check('Cloth Points 0 = from Cloth Detail (1.5 % -> about 3,500 points for a lasso-sized patch)', 3000 < cd.mask_target_points(st, 0.0) < 4000, cd.mask_target_points(st, 0.0))
att.data.foreach_set('value', np.ones(len(body.data.vertices), np.float32))
try:
    cd.perform_masked(C, body)
    check('the whole body masked raises (no rim to hang from)', False)
except cg.CutError as ex:
    check('the whole body masked raises (no rim to hang from)', 'whole' in str(ex), str(ex))
body.data.attributes.remove(att)
check('Drape Mask operator registered, in the panel and on the ZBrush cloth box',
      hasattr(bpy.types, 'MCH_OT_cdrape_mask') and "'mch.cdrape_mask'" in inspect.getsource(cd.draw_panel if hasattr(cd, 'draw_panel') else cd)
      and 'mch.cdrape_mask' in inspect.getsource(__import__('mecha_lab.zb_ui', fromlist=['x'])))
# ---- 0.24.95 Collide With + proxies (user: "충돌용 바디 별도의 저해상도 프록시 메쉬 ... 모든 메쉬를 프록시화, 지금 만드는 천 제외")
from mecha_lab import collider_proxy as cpx
body.location = (0.0, 0.0, 0.0)
for o in [o for o in bpy.data.objects if o is not body]:
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_ico_sphere_add(radius=0.15, subdivisions=6, location=(0.0, -1.3, 0.0))   # 81,920 triangles in front
wall = C.active_object
select_only(body)
S.mch_cut.targets = 'AUTO'
st.two_sides, st.padding, st.trim = False, False, False
st.collide_with, st.use_proxy, st.proxy_faces = 'BODY', True, 5000
check('meshes_for: Body = the body only; Targets + Auto = every visible mesh; Targets + Active = the body',
      cpx.meshes_for(C, body, (), 'BODY') == [body] and set(cpx.meshes_for(C, body, (), 'TARGETS')) == {body, wall}
      and (setattr(S.mch_cut, 'targets', 'ACTIVE') or cpx.meshes_for(C, body, (), 'TARGETS') == [body]))
S.mch_cut.targets = 'AUTO'
wall_pts = np.array([v.co[:] for v in wall.data.vertices]) + np.array(wall.location)    # (body at the origin: its space = world)
msg = cd.perform(C, loops, Proj())
ob_c = C.view_layer.objects.active
d_body = cd.SIM['sess']['grid'].distance(wall_pts)
check('Collide With Body: the other mesh is not in the collider (far)', np.median(np.abs(d_body)) > 1.0, float(np.median(np.abs(d_body))))
check('meshes_for never takes the cloth being made', ob_c not in cpx.meshes_for(C, body, [ob_c], 'TARGETS') and wall in cpx.meshes_for(C, body, [ob_c], 'TARGETS'))
cd.cancel(C)
st.collide_with = 'TARGETS'
msg = cd.perform(C, loops, Proj())
grid = cd.SIM['sess']['grid']
d_t = grid.distance(wall_pts)
check('Collide With Targets (Auto): the other mesh is in the collider (its surface at distance ~0)',
      np.median(np.abs(d_t)) < grid.cell * 2, (float(np.median(np.abs(d_t))), grid.cell))
coll = bpy.data.collections.get(cpx.COLL)
px = [o for o in coll.objects if o.get(cpx.SRC) == wall.name] if coll else []
ntri = sum(len(p.vertices) - 2 for p in px[0].data.polygons) if px else 0
check('... from a low-res proxy: "<name>_proxy" in the hidden "MCH Cloth Proxies" collection, about Proxy Faces triangles, not selectable / rendered',
      len(px) == 1 and px[0].name == wall.name + '_proxy' and coll.hide_viewport and coll.hide_render and px[0].hide_select
      and 4000 <= ntri <= 6000, (len(px), ntri))
check('... the body itself collides through a LOCAL piece (only the region round the cloth: here lighter than the budget, '
      'so no proxy object); a mesh under the budget is used as it is',
      not any(o.get(cpx.SRC) == body.name and not o.get(cpx.LOCAL) for o in coll.objects) and cpx.proxy_mesh(C, body, 20000) == (body.data, False))
data0 = px[0].data
cd.cancel(C)
cd.perform(C, loops, Proj())
check('a second drape reuses the proxy (not made again)', px[0].data == data0)
cd.cancel(C)
wall.data.vertices[0].co.x += 0.01
wall.data.update()
cd.perform(C, loops, Proj())
check('... the mesh changed: the proxy is made again', px[0].data != data0 and px[0].name == wall.name + '_proxy')
cd.cancel(C)
st.show_proxy = True
check('Show Proxies shows the collection (wire)', not coll.hide_viewport and px[0].display_type == 'WIRE')
st.show_proxy = False
st.use_proxy = False
cd.perform(C, loops, Proj())
check('Proxy off: the mesh itself is the collider (still in it)', np.median(np.abs(cd.SIM['sess']['grid'].distance(wall_pts))) < cd.SIM['sess']['grid'].cell * 2)
cd.cancel(C)
st.use_proxy, st.collide_with = True, 'BODY'
check('Snapshot covers Collide With / Proxy (a change restarts the drape)', all(k in inspect.getsource(cd._snapshot) for k in ("'collide_with'", "'use_proxy'", "'proxy_faces'")))
check('cpx.clear removes every proxy and the collection', cpx.clear(C) >= 1 and bpy.data.collections.get(cpx.COLL) is None)
bpy.data.objects.remove(wall)
check('Cloth Drape key maps carry the sketch keys (Enter / Alt+Enter / Backspace / Esc) and Space for the drape',
      any(k[0] == 'mch.lasso_sketch_key' for k in wsui.MCH_TOOL_cloth_drape.bl_keymap) and any(k[0] == 'mch.cdrape_sim' for k in wsui.MCH_TOOL_cloth_drape.bl_keymap))
summary()
