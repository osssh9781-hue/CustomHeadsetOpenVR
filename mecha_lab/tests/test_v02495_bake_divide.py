"""0.24.95 Bake High Poly Divide (user: "지브러시 디바이드는 렉이 안 걸리는데 하드 엣지는 킵이든 라운드든 렉이 너무 걸려 -
디바이드식으로 추가해 줘"): ZBrush's Divide with CreasePG - one Catmull-Clark pass with the hard edges creased.  Flats
stay exactly flat, hard edges stay sharp, the rest is smoothed; fast (no rounding passes, no fold checks)."""
import inspect
import math
import time

import numpy as np
from _harness import bmesh, bpy, check, fresh, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import actions_menu as am, bake_highpoly as bk, core_geometry as cg, cut_engine as ce
from mecha_lab import edge_memory as em, highpoly as hpm, mecha_menu as mm, mesh_tools as mt, zb_sculpt as zs
from mecha_lab import zb_ui as zu

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
S.mch_settings.auto_apply = True
S.mch_cut.targets = 'ACTIVE'
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)


def P(x, y):
    return (500 + x * 100, 500 + y * 100)


def part(name='Part'):
    """A 2 x 2 x 1 block with a round hole and a square pocket-through, its own edges remembered."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * 2, v.co.y * 2, v.co.z))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    S.collection.objects.link(ob)
    for o in C.selected_objects:
        o.select_set(False)
    C.view_layer.objects.active = ob
    ob.select_set(True)
    em.mark_generated(me)
    lg = ce.StrokeLogic.__new__(ce.StrokeLogic)
    lg.brush, lg.shape, lg.anchor = S.mch_brush, 'CIRCLE', P(-0.4, 0.0)
    ce.perform_closed(C, 'CUT', [ob], [lg._drag_loops(P(-0.1, 0.0), False, False)[0]], TOP)
    ce.perform_closed(C, 'CUT', [ob], [ce.rect_loop(P(0.3, -0.3), P(0.7, 0.3))], TOP)
    return ob


ob = part()
f0 = len(ob.data.polygons)
t = time.time()
hp, info = bk.build(C, ob, target_faces=200_000, bevels='DIVIDE')
t_div = time.time() - t
me = hp.data
co = np.empty(len(me.vertices) * 3)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
check(f'Divide: {f0} -> {len(me.polygons):,} faces in {t_div:.2f} s, a "_BakeHP" copy, the part hidden',
      len(me.polygons) > 20 * f0 and hp.name.endswith('_BakeHP') and ob.hide_get() and info['bevels'] == 'DIVIDE',
      (len(me.polygons), hp.name, info.get('bevels')))
top = np.abs(co[:, 2] - 0.5) < 0.02
check('... the flat top stays exactly flat (every point near it ON it: its rims are creased)',
      top.any() and np.abs(co[top, 2] - 0.5).max() < 1e-5, float(np.abs(co[top, 2] - 0.5).max()))
outer = np.abs(np.abs(co[:, :2]) - 1.0).min(1) < 1e-6
check('... the block\'s outline is kept: no point outside the block, the corners still at (+-1, +-1, +-0.5)',
      np.abs(co[:, :2]).max() < 1.0 + 1e-5 and np.abs(co[:, 2]).max() < 0.5 + 1e-5
      and all(((np.abs(co - np.array(c)) < 1e-5).all(1)).any() for c in ((1, 1, 0.5), (-1, -1, -0.5), (1, -1, 0.5))),
      (float(np.abs(co[:, :2]).max()), int(outer.sum())))
r = np.hypot(co[:, 0] + 0.4, co[:, 1])
wall = (r < 0.35) & (np.abs(co[:, 2]) < 0.45)
check('... the round hole stays round (its wall points 0.3 from its axis, within 0.5 %)',
      wall.any() and np.abs(r[wall] - 0.3).max() < 0.0015, float(np.abs(r[wall] - 0.3).max()) if wall.any() else None)
sharp = me.attributes.get('sharp_edge')
check('... the creased edges come out Sharp (shading split at the hard lines)',
      sharp is not None and any(sharp.data[i].value for i in range(len(me.edges))))

ob2 = part('Part2')
t = time.time()
hp2, info2 = bk.build(C, ob2, target_faces=200_000, bevels='KEEP')
t_keep = time.time() - t
check(f'Divide is faster than Keep on the same part ({t_div:.2f} s vs {t_keep:.2f} s)', t_div < t_keep,
      (t_div, t_keep))

# ---- the setting and the buttons
zbs = S.mch_zb
check('Setting: Bevels has Keep / Round / Divide (the panel row shows all three)',
      {i.identifier for i in zbs.bl_rna.properties['bk_bevels'].enum_items} == {'KEEP', 'ROUND', 'DIVIDE'}
      and "'bk_bevels', expand=True" in inspect.getsource(bk.draw_rows))
ob3 = part('Part3')
r = bpy.ops.mch.mesh_tool(action='BAKE_HP_DIVIDE')
check('mch.mesh_tool BAKE_HP_DIVIDE: Bake High Poly with Bevels Divide (the setting set to it), a heavy action on both '
      'screens', r == {'FINISHED'} and bk.INFO.get('bevels') == 'DIVIDE' and zbs.bk_bevels == 'DIVIDE'
      and 'BAKE_HP_DIVIDE' in mt.HEAVY and 'BAKE_HP_DIVIDE' in zs.RISKY, (r, bk.INFO.get('bevels')))
res = dict((sec, rows) for sec, rows in mm.ACTIONS)['Resolution']
check('Right-click menus: HP Divide in the Mecha Menu (Resolution), the Actions popup and the object context menu',
      any(r_[0] == 'HP Divide' and r_[3].get('action') == 'BAKE_HP_DIVIDE' for r_ in res)
      and "action='BAKE_HP_DIVIDE'" in inspect.getsource(am.draw_actions)
      and "'BAKE_HP_DIVIDE'" in inspect.getsource(hpm._context_menu))
from mecha_lab.mecha_menu import Item
wm = C.window_manager
wm.mch_zb_pop, wm.mch_zb_pop_xy, wm.mch_zb_pop_focus = 'MENU', (500, 400), ''
items = zu.popup(C, 1200, 900, 1.0, Item)
acts = [it.action[2].get('action') for it in items if getattr(it, 'action', None) and isinstance(it.action, tuple)
        and len(it.action) > 2 and it.action[0] == 'op' and it.action[1] == 'mch.zb_action']
check('ZBrush right-click popup: HP Divide next to HP Keep / HP Round', 'BAKE_HP_DIVIDE' in acts, acts)
wm.mch_zb_pop = ''
check('The message says Divide', 'Divide' in bk.describe(info))
summary()
