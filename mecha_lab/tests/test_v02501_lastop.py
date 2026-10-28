"""0.24.82 Redo Last: a drawing tool that made a part is remembered (its stroke, the view, the targets, the parts it
made); Redo Last (Actions card / Mecha Menu / N panel) removes those parts and draws the same stroke again with the
settings of now.  Tools that change a mesh (Cut ...) are not remembered (a plain Cut stays live on its own)."""
_src = open(__file__.replace('test_v02501_lastop.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import last_op, cut_engine, actions_menu, mecha_menu

S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
MODE[0], NATIVE[0] = 'PLATE', 'mecha.armor_plate'
S.mch_settings.mch_active_tool = 'PLATE'
box = cube('Box', 4.0)
check('Nothing drawn yet: nothing to redo', not last_op.available(C) and not last_op.MCH_OT_last_redo.poll(C))
S.mch_plate.spacing = 120
before = set(bpy.data.objects.keys())
r, m = lasso([(300, 350), (700, 350), (700, 650), (300, 650)])
made = [n for n in bpy.data.objects.keys() if n not in before]
rec = last_op.record()
check('Armor Plate drawn: the stroke is remembered with the parts it made', r == {'FINISHED'} and made
      and rec is not None and rec['mode'] == 'PLATE' and set(rec['made']) == set(made)
      and len(rec['loops']) == 1 and len(rec['loops'][0]) >= 4 and rec['proj'] is not None
      and last_op.available(C), (r, made, m[:60], rec and {k: (v if k in ('mode', 'made', 'targets', 'shape') else '..') for k, v in rec.items()}, rec and len(rec['loops'])))
faces0 = len(bpy.data.objects[made[0]].data.polygons)
n_obj = len(bpy.data.objects)
check('... the label names the tool and the count', 'Armor Plate' in last_op.label() and '1 part' in last_op.label(),
      last_op.label())

S.mch_plate.spacing = 60                                  # smaller faces: a denser plate
r = bpy.ops.mch.last_redo()
rec2 = last_op.record()
check('Redo Last: the first part is gone, the same outline drawn again with the new setting (more faces)',
      r == {'FINISHED'} and rec2 is not None and rec2['made'] and len(bpy.data.objects) == n_obj
      and all(n in bpy.data.objects for n in rec2['made'])
      and len(bpy.data.objects[rec2['made'][0]].data.polygons) > faces0 * 1.5
      and len(box.data.polygons) == 6, (r, rec2 and rec2['made'], faces0,
                                        rec2 and len(bpy.data.objects[rec2['made'][0]].data.polygons)))
# the part deleted by hand: Redo makes it again
for n in rec2['made']:
    bpy.data.objects.remove(bpy.data.objects[n])
check('... the part deleted by hand: nothing to redo until something is drawn', not last_op.available(C))

# a tool that changes a mesh is not remembered
MODE[0], NATIVE[0] = 'CUT', 'mecha.cut'
S.mch_settings.mch_active_tool = 'CUT'
S.mch_cut.targets = 'SELECTED'
select_only(box)
last_op.forget()
r, m = lasso([(300, 350), (500, 350), (500, 650), (300, 650)])
check('A Cut is not remembered here (it stays live on its own)', r == {'FINISHED'} and last_op.record() is None, m[:60])

# Base Mesh too (a new part from a lasso)
MODE[0], NATIVE[0] = 'BASE', 'mecha.base_mesh'
S.mch_settings.mch_active_tool = 'BASE'
from mecha_lab import base_mesh
bp = base_mesh.scene_defaults(C)
bp.sketch = False
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
S.mch_brush.line_mode = False
from mecha_lab import lasso_memory
lasso_memory.sync(C)
before = set(bpy.data.objects.keys())
r, m = lasso([(100, 100), (280, 100), (280, 280), (100, 280)])
made = [n for n in bpy.data.objects.keys() if n not in before]
check('Base Mesh drawn: remembered', r == {'FINISHED'} and made and last_op.available(C)
      and last_op.record()['mode'] == 'BASE', (r, made, m[:60]))
n_obj = len(bpy.data.objects)
first = bpy.data.objects[made[0]] if made else None
r = bpy.ops.mch.last_redo() if last_op.available(C) else None
check('... Redo Last makes it again (the old one gone, a new one there)', r == {'FINISHED'}
      and len(bpy.data.objects) == n_obj and last_op.available(C)
      and bpy.data.objects[last_op.record()['made'][0]] is not first, (r, last_op.record() and last_op.record()['made']))

check('Buttons: the Actions card (live rows), the Mecha Menu (Actions > Redo Last), the N panel',
      'mch.last_redo' in __import__('inspect').getsource(actions_menu._live_rows)
      and any(op == 'mch.last_redo' for sec, items in mecha_menu.ACTIONS for lab, ic, op, *_r in items)
      and 'last_op.draw' in __import__('inspect').getsource(__import__('mecha_lab.workspace_ui', fromlist=['x'])))
check('Only part-making tools are remembered (Cut / Split / Box Hide / Mask stay out)',
      {'PLATE', 'BASE', 'CPLATE', 'DETAIL', 'BELT', 'SDRAW'} <= last_op.MODES
      and not {'CUT', 'SPLIT', 'HIDE', 'MASK'} & last_op.MODES)
summary()
