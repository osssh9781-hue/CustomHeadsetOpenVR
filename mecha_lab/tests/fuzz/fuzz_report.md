# Fuzz report: 100 scenarios x 14 steps (seeds 1..100)

{'OK': 90, 'CRASH': 10} in 273 s, largest Blender process 3465 MB

## seed 2: CRASH (2 s)

last step: `STEP 10 hard_find on Part (4 faces, SCULPT)`

```
  ok 0.04s -> 4 faces
STEP 1 mask on Part (4 faces, SCULPT)
  ok 0.01s -> 4 faces
STEP 2 auto_groups on Part (4 faces, SCULPT)
Info: Auto Groups
  ok 0.00s -> 4 faces
STEP 3 undo_push on Part (4 faces, SCULPT)
  ok 0.00s -> 4 faces
STEP 4 mask_invert on Part (4 faces, SCULPT)
  ok 0.00s -> 4 faces
STEP 5 object_mode on Part (4 faces, SCULPT)
  ok 0.00s -> 4 faces
STEP 6 undo on Part (4 faces, OBJECT)
00:01.445  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
00:01.461  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
  ok 0.02s -> 4 faces
STEP 7 undo_push on Part (4 faces, SCULPT)
  ok 0.00s -> 4 faces
STEP 8 fix_mesh on Part (4 faces, SCULPT)
Info: Fix Mesh: done
  ok 0.00s -> 4 faces
STEP 9 del_higher on Part (4 faces, SCULPT)
Info: Del Higher: no higher levels
  ok 0.00s -> 4 faces
STEP 10 hard_find on Part (4 faces, SCULPT)
```

## seed 3: CRASH (2 s)

last step: `STEP 11 dynamesh on Part (10 faces, SCULPT)`

```
Info: Split: nothing to take out
  ok 0.00s -> 10 faces
STEP 4 fix_mesh on Part (10 faces, SCULPT)
Info: Fix Mesh: done
  ok 0.00s -> 10 faces
STEP 5 fix_mesh on Part (10 faces, SCULPT)
Info: Fix Mesh: done
  ok 0.00s -> 10 faces
STEP 6 hard_clear on Part (10 faces, SCULPT)
Info: Hard Edges: cleared
  ok 0.01s -> 10 faces
STEP 7 undo on Part (10 faces, SCULPT)
00:01.621  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
  ok 0.01s -> 10 faces
STEP 8 mask_invert on Part (10 faces, SCULPT)
  ok 0.00s -> 10 faces
STEP 9 undo on Part (10 faces, SCULPT)
00:01.629  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
00:01.637  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
00:01.644  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
  ok 0.02s -> 10 faces
STEP 10 hard_clear on Part (10 faces, SCULPT)
Info: Hard Edges: cleared
  ok 0.00s -> 10 faces
STEP 11 dynamesh on Part (10 faces, SCULPT)
```

## seed 5: CRASH (2 s)

last step: `STEP 10 dynamesh on Part_HP (8,806 faces, SCULPT)`

```
Info: Auto Groups
  ok 0.00s -> 500 faces
STEP 2 highpoly on Part (500 faces, SCULPT)
Info: High poly: 1 object(s), 8,806 faces in "HighPoly"
  ok 0.33s -> 8,806 faces
STEP 3 highpoly on Part_HP (8,806 faces, OBJECT)
ERROR 3 highpoly: RuntimeError: Operator bpy.ops.mch.make_highpoly.poll() failed, context is incorrect
STEP 4 mask_blur on Part_HP (8,806 faces, OBJECT)
Info: Mask: blur
  ok 0.00s -> 8,806 faces
STEP 5 undo on Part_HP (8,806 faces, SCULPT)
  ok 0.01s -> 8,806 faces
STEP 6 hard_apply on Part_HP (8,806 faces, SCULPT)
Info: Hard Edges: nothing to apply
  ok 0.01s -> 8,806 faces
STEP 7 undo on Part_HP (8,806 faces, SCULPT)
00:01.717  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
  ok 0.01s -> 8,806 faces
STEP 8 fix_mesh on Part_HP (8,806 faces, SCULPT)
Info: Fix Mesh: done
  ok 0.03s -> 8,806 faces
STEP 9 inflate on Part_HP (8,806 faces, SCULPT)
Info: Inflate 10
  ok 0.01s -> 8,806 faces
STEP 10 dynamesh on Part_HP (8,806 faces, SCULPT)
```

## seed 13: CRASH (2 s)

last step: `STEP 3 undo on Part_HP (1,254 faces, SCULPT)`

```
SCENARIO 13: part cyl (59 faces)
STEP 0 highpoly on Part (59 faces, OBJECT)
Info: High poly: 1 object(s), 1,254 faces in "HighPoly"
  ok 0.79s -> 1,254 faces
STEP 1 mask_blur on Part_HP (1,254 faces, OBJECT)
Info: Mask: blur
  ok 0.02s -> 1,254 faces
STEP 2 groups_from_mask on Part_HP (1,254 faces, SCULPT)
Info: Polygroup from mask
  ok 0.00s -> 1,254 faces
STEP 3 undo on Part_HP (1,254 faces, SCULPT)
00:02.183  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
```

## seed 38: CRASH (38 s)

last step: `STEP 7 decimate on Part (2,526 faces, SCULPT)`

```
SCENARIO 38: part boolean (175 faces)
STEP 0 hard_clear on Part (175 faces, OBJECT)
Info: Hard Edges: cleared
  ok 0.03s -> 175 faces
STEP 1 extract on Part (175 faces, SCULPT)
Info: Extract: paint a mask first (Ctrl + drag on the model)
  ok 0.00s -> 175 faces
STEP 2 undo on Part (175 faces, SCULPT)
00:01.720  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
00:01.730  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
00:01.738  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
  ok 0.03s -> 175 faces
STEP 3 mirror_weld on Part (175 faces, SCULPT)
Info: Mirror And Weld
  ok 0.00s -> 158 faces
STEP 4 quad on Part (158 faces, SCULPT)
Info: Quad Remesh: 158 > 2,526 polygons, 69 % quads, 853 hard edges marked in 35.6 s
  ok 35.66s -> 2,526 faces
STEP 5 del_hidden on Part (2,526 faces, SCULPT)
Info: Nothing hidden (Ctrl+Shift + drag to hide)
  ok 0.00s -> 2,526 faces
STEP 6 undo on Part (2,526 faces, SCULPT)
00:37.413  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
  ok 0.01s -> 2,526 faces
STEP 7 decimate on Part (2,526 faces, SCULPT)
```

## seed 60: CRASH (2 s)

last step: `STEP 6 quad on Part (22 faces, SCULPT)`

```
SCENARIO 60: part cyl (22 faces)
STEP 0 object_mode on Part (22 faces, OBJECT)
  ok 0.00s -> 22 faces
STEP 1 del_lower on Part (22 faces, OBJECT)
Info: Del Lower: no subdivision levels
  ok 0.03s -> 22 faces
STEP 2 hard_sliders on Part (22 faces, SCULPT)
  ok 0.00s -> 22 faces
STEP 3 mask_invert on Part (22 faces, SCULPT)
  ok 0.00s -> 22 faces
STEP 4 undo on Part (22 faces, SCULPT)
00:01.922  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
  ok 0.02s -> 22 faces
STEP 5 merge_visible on Part (22 faces, SCULPT)
Info: Nothing to merge
  ok 0.00s -> 22 faces
STEP 6 quad on Part (22 faces, SCULPT)
```

## seed 75: CRASH (2 s)

last step: `STEP 3 undo on Part_HP (9,216 faces, OBJECT)`

```
SCENARIO 75: part torus (576 faces)
STEP 0 extract on Part (576 faces, OBJECT)
Info: Extract: paint a mask first (Ctrl + drag on the model)
  ok 0.03s -> 576 faces
STEP 1 mirror_weld on Part (576 faces, SCULPT)
Info: Mirror And Weld
  ok 0.00s -> 576 faces
STEP 2 highpoly on Part (576 faces, SCULPT)
Info: High poly: 1 object(s), 9,216 faces in "HighPoly"
  ok 0.02s -> 9,216 faces
STEP 3 undo on Part_HP (9,216 faces, OBJECT)
00:01.502  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
00:01.510  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
```

## seed 78: CRASH (2 s)

last step: `STEP 6 quad on Part.001 (6 faces, SCULPT)`

```
SCENARIO 78: part thin (6 faces)
STEP 0 groups_from_mask on Part (6 faces, OBJECT)
Info: Polygroup from mask
  ok 0.03s -> 6 faces
STEP 1 undo on Part (6 faces, SCULPT)
00:01.649  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
ERROR 1 undo: RuntimeError: Operator bpy.ops.ed.undo.poll() failed, context is incorrect
STEP 2 divide on Part (6 faces, SCULPT)
Info: Divide: SDiv 1
  ok 0.01s -> 6 faces
STEP 3 dynamesh on Part (6 faces, SCULPT)
Info: DynaMesh: this SubTool has subdivision levels - Del Higher / Del Lower first
  ok 0.00s -> 6 faces
STEP 4 undo on Part (6 faces, SCULPT)
00:01.678  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
  ok 0.02s -> 6 faces
STEP 5 duplicate on Part (6 faces, SCULPT)
Info: Duplicate: Part.001
  ok 0.00s -> 6 faces
STEP 6 quad on Part.001 (6 faces, SCULPT)
```

## seed 81: CRASH (2 s)

last step: `STEP 8 hard_sliders on Part.001 (500 faces, SCULPT)`

```
SCENARIO 81: part monkey (500 faces)
STEP 0 hard_sliders on Part (500 faces, OBJECT)
  ok 0.00s -> 500 faces
STEP 1 mask on Part (500 faces, OBJECT)
  ok 0.07s -> 500 faces
STEP 2 hard_sliders on Part (500 faces, SCULPT)
  ok 0.00s -> 500 faces
STEP 3 del_hidden on Part (500 faces, SCULPT)
Info: Nothing hidden (Ctrl+Shift + drag to hide)
  ok 0.00s -> 500 faces
STEP 4 undo on Part (500 faces, SCULPT)
00:01.740  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
ERROR 4 undo: RuntimeError: Operator bpy.ops.ed.undo.poll() failed, context is incorrect
STEP 5 undo_push on Part (500 faces, SCULPT)
  ok 0.00s -> 500 faces
STEP 6 undo_push on Part (500 faces, SCULPT)
  ok 0.00s -> 500 faces
STEP 7 duplicate on Part (500 faces, SCULPT)
Info: Duplicate: Part.001
  ok 0.01s -> 500 faces
STEP 8 hard_sliders on Part.001 (500 faces, SCULPT)
Attempt to free nullptr pointer
```

## seed 93: CRASH (2 s)

last step: `STEP 7 decimate on Part (6 faces, SCULPT)`

```
SCENARIO 93: part thin (6 faces)
STEP 0 hard_apply on Part (6 faces, OBJECT)
Info: Hard Edges: nothing to apply
  ok 0.03s -> 6 faces
STEP 1 decimate on Part (6 faces, SCULPT)
Info: Decimate: 6 > 6 polygons in 0.0 s (4 threads)
  ok 0.01s -> 6 faces
STEP 2 mask_invert on Part (6 faces, SCULPT)
  ok 0.00s -> 6 faces
STEP 3 undo on Part (6 faces, SCULPT)
00:01.471  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
00:01.479  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
00:01.488  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
  ok 0.03s -> 6 faces
STEP 4 mask_invert on Part (6 faces, SCULPT)
  ok 0.00s -> 6 faces
STEP 5 hard_apply on Part (6 faces, SCULPT)
Info: Hard Edges: nothing to apply
  ok 0.00s -> 6 faces
STEP 6 undo on Part (6 faces, SCULPT)
00:01.500  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
00:01.512  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
  ok 0.02s -> 6 faces
STEP 7 decimate on Part (6 faces, SCULPT)
```

## Python errors inside steps (Blender lived)

- 28 x redo: Operator bpy.ops.ed.redo.poll() failed, context is incorrect
- 17 x undo: Operator bpy.ops.ed.undo.poll() failed, context is incorrect
- 4 x highpoly: Operator bpy.ops.mch.make_highpoly.poll() failed, context is incorrect
