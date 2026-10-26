"""0.24.34 F + mouse = brush size in every drawing tool (like Concept Move): Line Width, PNG Stamp Radius, Mask
Brush Radius, Screw Size; Surface Draw also scales the kept Width / Height; Esc puts it back."""
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import brush_resize as br, screw_stamp, tool_state as ts, workspace_ui as wsui

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
check('the operator is there', hasattr(bpy.ops.mch, 'brush_resize'))
tools = [t for t in wsui.NATIVE_TOOLS if t.bl_keymap is not screw_stamp.TOOL_KEYMAP
         and t.bl_idname != 'mecha.primitive']
check('F = brush size in every Mecha drawing tool (Cut, Base Mesh, plates, Surface Draw, capes ...)',
      tools and all(any(k[0] == 'mch.brush_resize' and k[1]['type'] == 'F' for k in t.bl_keymap) for t in tools),
      [t.bl_idname for t in tools if not any(k[0] == 'mch.brush_resize' for k in t.bl_keymap)])
check('... and in the Screw Stamp', any(k[0] == 'mch.brush_resize' for k in screw_stamp.TOOL_KEYMAP))
check('F outside the tools is still Select / Move', any(
    k.idname == 'mch.select_move_key' and k.type == 'F' for km, k in wsui._keymaps))

real = ts.effective_tool
tool = ['CUT']
br.ts.effective_tool = lambda context: tool[0]
brush = S.mch_brush
brush.shape = 'LASSO'
brush.line_width = 0.02
items, label = br.targets(C)
check('a lasso tool: Line Width', label == 'Line Width' and items[0][1] == 'line_width')
br.scale(items, br.values(items), 2.0)
check('x2 = twice as wide', abs(brush.line_width - 0.04) < 1e-6)
br.scale(items, [0.02], 1e-9)
check('kept inside the limits (not below the minimum)', brush.line_width >= 0.0005 - 1e-12)
brush.line_width = 0.02

tool[0] = 'SDRAW'
S.mch_sdraw.width, S.mch_sdraw.height = 0.1, 0.03
items, label = br.targets(C)
br.scale(items, br.values(items), 1.5)
check('Surface Draw: Line Width and the kept Width / Height of the next stroke scale together',
      abs(brush.line_width - 0.03) < 1e-6 and abs(S.mch_sdraw.width - 0.15) < 1e-6 and abs(S.mch_sdraw.height - 0.045) < 1e-6)
S.mch_sdraw.width = S.mch_sdraw.height = 0.0
items, _l = br.targets(C)
check('... not stored yet (0 = from the Line Width): only the Line Width', len(items) == 1)

tool[0] = 'CUT'
brush.shape = 'CUSTOM'
items, label = br.targets(C)
check('PNG stamp shape: Stamp Radius (pixels)', label == 'Stamp Radius' and items[0][2] == 'PX')
brush.shape = 'STROKE'
tool[0] = 'MASK'
items, label = br.targets(C)
check('Mask Brush stroke: Mask Brush Radius', label == 'Mask Brush Radius' and items[0][1] == 'mask_brush_radius')
tool[0] = 'SCREW'
items, label = br.targets(C)
check('Screw Stamp: Size', label == 'Screw Size' and items[0][0] == S.mch_screw)
brush.shape = 'LASSO'
br.ts.effective_tool = real
summary()
