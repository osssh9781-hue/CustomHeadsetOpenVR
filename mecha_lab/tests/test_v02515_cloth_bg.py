"""0.24.88 Panel Cloth: the frames run in a temporary scene (the user's scene untouched: frame, no leftover scene),
Fast Start on by default, the bake in a background Blender when the Background toggle is on (MECH_BG_FORCE here:
headless), the cloth appears at once and gets its folds when the worker is done, Refresh refused while it runs."""
import os, sys, time
os.environ['MECH_BG_FORCE'] = '1'
_src = open(__file__.replace('test_v02515_cloth_bg.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
import numpy as np
fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
from mecha_lab import cloth_sim as cs, bg_jobs, last_used
last_used.forget('wrinkle')
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
S.mch_settings.mch_active_tool = 'WRINKLE'
box = cube('Box', 4.0)
S.mch_wrinkle.sim_after = False
r, m = lasso([(330, 330), (670, 330), (670, 670), (330, 670)])
plate = C.active_object
check('a cloth plate to simulate', plate is not None and 'Wrinkle' in plate.name, m)


def height(ob):
    co = np.array([(ob.matrix_world @ v.co)[2] for v in ob.data.vertices])
    return float(np.percentile(co, 95) - 2.0)


check('Fast Start on by default', S.mch_pcloth_fast is True)
# --- inline bake in a temporary scene ---------------------------------------------------------------------------
S.frame_set(7)
n_scenes = len(bpy.data.scenes)
S.mch_zb.bg_jobs = False
t = time.perf_counter()
made = cs.run_preset(C, [plate], 'PADDING', collider='REGION')
dt = time.perf_counter() - t
pc = made[0]
check('inline bake: the cloth puffed up (PADDING)', height(pc) > 0.05, (height(pc), dt))
check('... the user\'s scene kept its frame and no scene was left behind', S.frame_current == 7 and len(bpy.data.scenes) == n_scenes,
      (S.frame_current, len(bpy.data.scenes)))
check('... sim-only vertex groups gone, faces smooth, Subsurf on', pc.vertex_groups.get(cs.SHRINK_GROUP) is None
      and all(p.use_smooth for p in pc.data.polygons) and pc.modifiers.get('MCH_Subsurf') is not None)
check('... source hidden', plate.hide_get())
bpy.data.objects.remove(pc)
plate.hide_set(False)

# --- background bake ---------------------------------------------------------------------------------------------
S.mch_zb.bg_jobs = True
check('use_background follows the Background toggle (forced worker here)', cs.use_background(C))
plate.select_set(True); C.view_layer.objects.active = plate
made = cs.run_preset(C, [plate], 'PADDING', collider='REGION', background=True)
pc = made[0]
h0 = height(pc)
check('background: the cloth object is there at once (flat start, pending flag), no cloth modifier on it, a job running',
      cs.is_pcloth(pc) and pc.get('mch_pcloth_pending') == 1 and not any(mm.type == 'CLOTH' for mm in pc.modifiers) and bg_jobs.busy(pc),
      (h0, cs.LAST_BACKGROUND))
check('... Refresh while it runs is refused (nothing made, the cloth kept)', cs.redo(C, pc, 'PADDING') == [] and pc.name in bpy.data.objects)
check('... the temporary collider object is gone from the scene', not any(o.name.endswith('_Collider') for o in bpy.data.objects))
t = time.perf_counter()
while bg_jobs.busy(pc) and time.perf_counter() - t < 240:
    time.sleep(0.5)
msgs = bg_jobs.poll()
check('... the worker finished and its result was applied', not bg_jobs.busy(pc) and msgs and 'baked' in msgs[0], msgs)
h1 = height(pc)
check('... the folds landed: puffed up like the inline bake, pending flag cleared, groups gone',
      h1 > 0.05 and 'mch_pcloth_pending' not in pc and pc.vertex_groups.get(cs.SHRINK_GROUP) is None, (h0, h1))
check('... faces smooth, Subsurf on', all(p.use_smooth for p in pc.data.polygons) and pc.modifiers.get('MCH_Subsurf') is not None)
check('the Panel Cloth box shows the Background toggle and the status row', "r.prop(zb, 'bg_jobs'" in open(cs.__file__).read()
      and 'bg_jobs.draw_status(box, ob)' in open(cs.__file__).read())
check('the lasso Sim-after path follows the toggle', 'background=cloth_sim.use_background(context)' in open(__import__('mecha_lab.cloth_wrinkle', fromlist=['x']).__file__).read())

# --- quality: self collision on by default, no crossing folds, padded family with fewer sub-steps ------------------
from mecha_lab import core_geometry as cg
import inspect
check('setup_cloth: self collision on by default, collision quality 2, self distance = the contact thickness',
      inspect.signature(cs.setup_cloth).parameters['self_collision'].default is True
      and 'c.self_distance_min = thickness' in inspect.getsource(cs.setup_cloth))
check('the padded presets run 3 - 4 solver steps per frame, the fabric presets keep 6 - 8',
      cs.preset_values('PADDING')['quality'] == 3 and cs.preset_values('PUFFER')['quality'] == 4
      and cs.preset_values('CLOTH')['quality'] == 6 and cs.preset_values('SILK')['quality'] == 8)
S.mch_zb.bg_jobs = False
bpy.data.objects.remove(pc)
plate.hide_set(False); plate.select_set(True); C.view_layer.objects.active = plate
made = cs.run_preset(C, [plate], 'CLOTH', collider='REGION')
cl = made[0]
cross = cg.self_overlaps(cl.data)
area = np.empty(len(cl.data.polygons)); cl.data.polygons.foreach_get('area', area)
check('CLOTH preset: the baked cloth has no faces passing through each other (0.24.87: 229 - 485 crossing pairs)', cross == 0, cross)
check('... and no sliver faces (smallest face at least 5 % of the mean; was 0.05 %)', area.min() / area.mean() > 0.05, area.min() / area.mean())
check('... the folds are there (not flattened by the collision)', height(cl) > 0.02, height(cl))
check('run_preset passes self_collision through (the earlier experiment silently dropped it)',
      "'self_collision'" in inspect.getsource(cs.run_preset))
summary()
