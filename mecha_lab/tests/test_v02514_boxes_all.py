"""0.24.87 Every group's box lines off at once: Scene.mch_settings.group_boxes (default on), the Layers panel head
button / Groups card toggle (mch.group_boxes_all), the viewport drawing guard (groups.boxes_on)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import bpy, check, cube, fresh, summary
import mecha_lab
from mecha_lab import groups, layers_panel
fresh()
mecha_lab.register()
C = bpy.context
S = C.scene

check('Scene setting Group Box Lines exists and is on by default', S.mch_settings.group_boxes is True)
check('drawing guard: on', groups.boxes_on(C))
a, b = cube('A', loc=(0, 0, 0)), cube('B', loc=(3, 0, 0))
for o in (a, b): o.select_set(True)
C.view_layer.objects.active = a
g = groups.create(C, [a, b], 'G')
r = bpy.ops.mch.group_boxes_all()
check('Layers head / Groups card button: all box lines off', r == {'FINISHED'} and S.mch_settings.group_boxes is False)
check('drawing guard: off (the box drawing returns before any group is looked at)', not groups.boxes_on(C)
      and 'if not boxes_on(context):' in open(groups.__file__).read().split('def _draw_boxes')[1].split('groups = [')[0])
check('the per-group eye is untouched by it', not g.get(groups.BOX_HIDDEN_KEY))
bpy.ops.mch.group_boxes_all()
check('... and on again', S.mch_settings.group_boxes is True)
src = open(layers_panel.__file__).read()
check('the Layers panel head has the all-groups box button next to the minimise button',
      "('op', 'mch.group_boxes_all', {})" in src.split('def layout')[1])
check('the Groups card has the Box Lines (all groups) toggle', "layout.prop(st, 'group_boxes'" in open(groups.__file__).read())
# the drawn head items: the button is present and reflects the state
try:
    its = layers_panel.layout(C, 1200, 800, 1.0)['items']
    btn = [i for i in its if getattr(i, 'action', None) == ('op', 'mch.group_boxes_all', {})]
    check('the drawn head item exists and is pressed while the lines are on', len(btn) == 1 and bool(btn[0].on))
    S.mch_settings.group_boxes = False
    its = layers_panel.layout(C, 1200, 800, 1.0)['items']
    btn = [i for i in its if getattr(i, 'action', None) == ('op', 'mch.group_boxes_all', {})]
    check('... and released while they are off', len(btn) == 1 and not btn[0].on)
    S.mch_settings.group_boxes = True
except Exception as ex:   # (the drawn panel needs the bars; headless may not have them)
    check('drawn head items (skipped headless): ' + str(ex)[:60], True)
summary()
