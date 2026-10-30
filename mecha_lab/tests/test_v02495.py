"""0.24.95 Edge Memory + Bake High Poly: the version, the modules and the places they are wired in."""
import inspect

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bake_highpoly as bk, box_hide as bh, core_geometry as cg, edge_memory as em, fast_decimate as fd
from mecha_lab import hard_edges as he, mesh_tools as mt, zb_sculpt as zs, zb_ui as zu

mecha_lab.register()
fresh()
check('Version 0.24.95', mecha_lab.bl_info['version'] == (0, 24, 95))
check('Edge Memory: one mark name shared by every reader', em.ATTR == 'mch_hard')
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
summary()
