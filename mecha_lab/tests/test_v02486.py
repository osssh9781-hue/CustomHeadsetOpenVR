"""0.24.58 The group outline fits its parts: the handle is a small cross (still a click target) and the outline is a
box drawn tight round the parts (it was a cube as big as the longest side - far bigger than a long thin part);
groups made before are tidied when the file is opened."""
import inspect

from _harness import bpy, check, cube, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import groups

mecha_lab.register()
fresh()
C = bpy.context
a = cube('A', size=1.0, loc=(0, 0, 0))
a.scale = (0.2, 0.2, 3.0)                      # a long thin part
C.view_layer.update()
g = groups.create(C, [a])
box = groups.group_box(g)
check('New group: a small cross handle, not a cube', g.empty_display_type == 'PLAIN_AXES'
      and g.empty_display_size < 1.0, (g.empty_display_type, g.empty_display_size))
check('The outline box is the parts\' own size (0.2 x 0.2 x 3)', box is not None
      and (box[1] - box[0] - Vector((0.2, 0.2, 3.0))).length < 1e-4, box and tuple(box[1] - box[0]))
lines = groups.box_lines(*box)
check('... drawn as 12 edges', len(lines) == 24)
g.empty_display_type = 'CUBE'
g.empty_display_size = 1.65
groups.tidy_handles()
check('A group made before (a big cube) is tidied', g.empty_display_type == 'PLAIN_AXES'
      and g.empty_display_size < 1.0)
check('Tidied when a file is opened; the box is drawn in the viewport (selected: orange)',
      groups._on_load in bpy.app.handlers.load_post and "'POST_VIEW'" in inspect.getsource(groups.register)
      and 'select_get' in inspect.getsource(groups._draw_boxes))
summary()
