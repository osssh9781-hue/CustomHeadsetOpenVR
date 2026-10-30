"""0.24.95 Edge Memory + Bake High Poly: the version, the modules and the places they are wired in."""
import inspect

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bake_highpoly as bk, box_hide as bh, core_geometry as cg, edge_memory as em, fast_decimate as fd
from mecha_lab import hard_edges as he, mesh_tools as mt, zb_sculpt as zs, zb_ui as zu

mecha_lab.register()
fresh()
check('Version 0.24.95', mecha_lab.bl_info['version'] == (0, 24, 95))
check('Edge Memory: one mark name shared by every reader (internal: a voxel remesh does not smear it)', em.ATTR == '.mch_hard')
check('remove_cutter_attribute (every cut-type tool\'s last step) turns the cutter flag into Edge Memory marks',
      'edge_memory.mark_cut_borders' in inspect.getsource(cg.remove_cutter_attribute))
check('Box Hide Apply and Split Off flag the volume and take the marks',
      inspect.getsource(bh.apply).count('_flag_volume') == 1 and 'remove_cutter_attribute' in inspect.getsource(bh.apply)
      and '_flag_volume' in inspect.getsource(bh.split_off) and 'remove_cutter_attribute' in inspect.getsource(bh.split_off))
check('Hard Edges Find reads the memory (hard whatever the angle)', 'em.ATTR' in inspect.getsource(he.find))
check('Fast Decimate keeps the remembered edges like borders (feat) and marks the result again',
      'hard_feat' in inspect.getsource(fd.decimate_object) and 'transfer_segments' in inspect.getsource(fd.decimate_object))
check('swap_mesh carries the marks over every mesh swap (Quad Remesh, Re-Fix, Hard Edges, region cut)',
      'em.transfer' in inspect.getsource(fd.swap_mesh))
check('voxel remesh sites remember / restore: ZBrush DynaMesh, Mesh Tools DynaMesh, Re-Fix, Concept Move',
      all('em.remember' in inspect.getsource(m) and 'em.restore' in inspect.getsource(m)
          for m in (zs.dynamesh, mt.run_one)) and 'em.remember' in open(zs.__file__.replace('zb_sculpt', 'refix'), encoding='utf-8').read()
      and 'em.remember' in open(zs.__file__.replace('zb_sculpt', 'concept_move'), encoding='utf-8').read())
check('Bake High Poly: action BAKE_HP on the ZBrush screen (risky = safety save) and in Mesh Tools, settings on mch_zb',
      'BAKE_HP' in zs.RISKY and 'BAKE_HP' in mt.ACTIONS and all(p in bpy.context.scene.mch_zb.bl_rna.properties
                                                                 for p in ('bk_target', 'bk_rounding', 'bk_fillet')))
check('Bake High Poly box on the ZBrush shelf after Hard Edges, rows in Mesh Tools',
      "label(text='Bake High Poly')" in inspect.getsource(zu.draw_tool_shelf) and 'bk.draw_rows' in inspect.getsource(mt.draw))
import glob, os
hooked = sorted(os.path.basename(f) for f in glob.glob(os.path.join(os.path.dirname(em.__file__), '*.py'))
                if '_em.mark_generated(' in open(f, encoding='utf-8').read())
check('mark_generated hooked into every part-making tool (13 modules)',
      set(hooked) >= {'armor_plate.py', 'base_mesh.py', 'bridge_patch.py', 'creature_plate.py', 'edge_molding.py', 'face_extract.py',
                      'flower_plate.py', 'mech_ridge.py', 'plate_detail.py', 'scale_brush.py', 'screw_stamp.py', 'surface_draw.py',
                      'surface_lasso.py'}, hooked)
check('boolean_result flags any cutter', 'flag_cutter(cutter)' in inspect.getsource(cg.boolean_result))
from mecha_lab import actions_menu as am, highpoly as hp
from mecha_lab.mecha_menu import Item
check('Right-click menus: Bake High Poly in the Mecha Lab Actions popup (Resolution) and in Blender\'s object context menu',
      "action='BAKE_HP'" in inspect.getsource(am.draw_actions) and "'BAKE_HP'" in inspect.getsource(hp._context_menu))
from mecha_lab import mecha_menu as mm
res = dict((sec, rows) for sec, rows in mm.ACTIONS)['Resolution']
check('Mecha Menu (the drawn right-click panel): Resolution has Bake HP -> mch.mesh_tool BAKE_HP, with its own glyph',
      any(r[0] == 'Bake HP' and r[2] == 'mch.mesh_tool' and r[3].get('action') == 'BAKE_HP' and r[1] == 'bakehp' for r in res), res)
bpy.ops.mesh.primitive_cube_add(size=2)
items = mm.build(bpy.context, 600, 400, 1600, 900, 1.0)
check('... and build() lays it out as a button', any(getattr(it, 'label', '') == 'Bake HP' for it in items),
      [getattr(it, 'label', '') for it in items if 'Bake' in str(getattr(it, 'label', ''))])
wm = bpy.context.window_manager
wm.mch_zb_pop, wm.mch_zb_pop_xy, wm.mch_zb_pop_focus = 'MENU', (500, 400), ''
items = zu.popup(bpy.context, 1200, 900, 1.0, Item)
acts = [it.action[2].get('action') for it in items if getattr(it, 'action', None) and isinstance(it.action, tuple)
        and len(it.action) > 2 and it.action[0] == 'op' and it.action[1] == 'mch.zb_action']
check('ZBrush right-click popup: a DynaMesh / Decimate / Bake High Poly row', {'DYNAMESH', 'DECIMATE', 'BAKE_HP'} <= set(acts), acts)
wm.mch_zb_pop = ''
summary()
