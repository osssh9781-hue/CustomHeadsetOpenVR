"""0.24.35 Ctrl+Z keeps the brush sizes (Line Width, Stamp / Mask radius, Concept / Path Move size, Screw Size,
Surface Draw size); Knife Mesh (Concept / Path Move panel): even X / Y / Z slices through the whole mesh, the shape
stays the same."""
from _harness import bpy, check, fresh, non_manifold, summary
import bmesh

import mecha_lab
from mecha_lab import concept_move as cm, tool_state as ts

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene

keys = set(ts.UNDO_KEEP)
check('Ctrl+Z keeps every brush size', {('mch_brush', 'line_width'), ('mch_brush', 'custom_size'),
                                        ('mch_brush', 'mask_brush_radius'), ('mch_concept', 'radius_px'),
                                        ('mch_concept', 'radius_world'), ('mch_screw', 'radius'),
                                        ('mch_sdraw', 'width')} <= keys)
S.mch_brush.line_width = 0.07
S.mch_concept.radius_px = 333
ts.snapshot_ui_state(S)                      # what undo_pre does
S.mch_brush.line_width = 0.02                # the undo step brings back older values ...
S.mch_concept.radius_px = 120
changed = ts.restore_ui_state(S)             # ... and undo_post puts the sizes back
check('after Ctrl+Z the sizes are what they were (not the old ones)', abs(S.mch_brush.line_width - 0.07) < 1e-6
      and S.mch_concept.radius_px == 333 and 'line_width' in changed, changed)

bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
n0 = len(cube.data.vertices)
bm = bmesh.new()
bm.from_mesh(cube.data)
planes = cm.knife_grid(bm, 4)
step = 0.5
longest = max(e.calc_length() for e in bm.edges)
bm.to_mesh(cube.data)
bm.free()
cube.data.update()
vs = [v.co for v in cube.data.vertices]
check('Knife Mesh: 3 slices per side of a cube (4 cuts)', planes == 9, planes)
check('the faces are split evenly (no edge longer than the spacing)', longest <= step + 1e-5, longest)
check('the shape stays the same (same box, closed, still on the cube faces)',
      max(max(abs(c) for c in v) for v in vs) < 1.0 + 1e-6 and non_manifold(cube) == 0
      and all(any(abs(abs(c) - 1.0) < 1e-5 for c in v) for v in vs) and len(vs) > n0)

bpy.ops.mesh.primitive_cube_add(size=1.0, location=(3, 0, 0), scale=(4, 1, 1))
bar = C.active_object
S.mch_concept.knife_cuts = 8
bpy.ops.mch.knife_grid('INVOKE_DEFAULT')
xs = sorted({round(v.co.x, 4) for v in bar.data.vertices})
ys = sorted({round(v.co.y, 4) for v in bar.data.vertices})
check('the button: the selected mesh, even spacing along each side (its own space)', len(xs) == 9 and len(ys) == 3,
      (len(xs), len(ys)))
check('Knife Mesh is in the Concept Move and Path Move panels', 'draw_knife' in cm.draw_path.__code__.co_names
      and 'draw_knife' in cm.draw.__code__.co_names)
summary()
