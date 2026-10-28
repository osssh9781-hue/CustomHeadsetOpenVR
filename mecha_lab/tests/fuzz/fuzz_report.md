# Fuzz reports (newest first)

## 0.24.76 run: 40 scenarios x 12 steps (seeds 281..320)

{'OK': 38, 'CRASH': 1, 'HANG': 1} in 637 s, largest Blender process 7823 MB

Both findings are older than 0.24.76 - the same seeds with the 0.24.75 add-on (same scenario.py):
- seed 282 CRASH: High Poly (347k faces) -> Hard Edges settings -> undo: segfault twice with this version, segfault with 0.24.75 too (bpy without a window; same kind as the 0.24.73 "repeated undo step" crash).
- seed 291 HANG: Hard Edges Find Edges on a decimated 104k-face part in Sculpt Mode is just slow: run alone it finishes in 703 s (0.24.75: 717 s), over the 600 s limit of the run.


### seed 282: CRASH (3 s)

last step: `STEP 8 undo on Part_HP (347,008 faces, OBJECT)`

```
Info: Hard Edges: cleared
  ok 0.02s -> 176 faces
STEP 1 hard_find on Part (176 faces, SCULPT)
Info: Hard Edges: 329 edges
  ok 0.02s -> 176 faces
STEP 2 edge_mesh on Part (176 faces, SCULPT)
Info: Edge Mesh: 674 triangles (lighter than Detail), 326 hard edges, 128 quads + 410 triangles
  ok 0.42s -> 538 faces
STEP 3 extract on Part (538 faces, SCULPT)
Info: Extract: paint a mask first (Ctrl + drag on the model)
  ok 0.00s -> 538 faces
STEP 4 mask_blur on Part (538 faces, SCULPT)
Info: Mask: blur
  ok 0.28s -> 538 faces
STEP 5 close_holes on Part (538 faces, SCULPT)
Info: Close Holes: no holes
  ok 0.26s -> 538 faces
STEP 6 highpoly on Part (538 faces, SCULPT)
Info: High poly: 1 object(s), 347,008 faces in "HighPoly"
  ok 0.58s -> 347,008 faces
STEP 7 hard_sliders on Part_HP (347,008 faces, OBJECT)
  ok 0.01s -> 347,008 faces
STEP 8 undo on Part_HP (347,008 faces, OBJECT)
00:02.602  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
00:02.659  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
```

### seed 291: HANG (600 s)

last step: `STEP 11 hard_find on Part (104,002 faces, SCULPT)`

```
STEP 2 del_higher on Part (191 faces, OBJECT)
Info: Del Higher: no higher levels
  ok 0.02s -> 191 faces
STEP 3 edit_mode on Part (191 faces, SCULPT)
  ok 0.00s -> 191 faces
STEP 4 edge_mesh on Part (191 faces, EDIT_MESH)
Info: Edge Mesh: 752 triangles (already within Tolerance), 380 hard edges, 109 quads + 532 triangles
  ok 0.99s -> 641 faces
STEP 5 undo on Part (641 faces, SCULPT)
00:02.150  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
  ok 0.01s -> 191 faces
STEP 6 undo on Part (191 faces, SCULPT)
00:02.159  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
  ok 0.01s -> 191 faces
STEP 7 mask_invert on Part (191 faces, SCULPT)
  ok 0.00s -> 191 faces
STEP 8 he_style on Part (191 faces, SCULPT)
  ok 0.00s -> 191 faces
STEP 9 dynamesh on Part (191 faces, SCULPT)
Info: DynaMesh: 60,466 points
  ok 0.16s -> 60,466 faces
STEP 10 decimate on Part (60,466 faces, SCULPT)
Info: Decimate: 60,466 > 104,002 polygons in 0.3 s (4 threads)
  ok 0.28s -> 104,002 faces
STEP 11 hard_find on Part (104,002 faces, SCULPT)
```

### Python errors inside steps (Blender lived)

- 7 x undo: Operator bpy.ops.ed.undo.poll() failed, context is incorrect
- 6 x redo: Operator bpy.ops.ed.redo.poll() failed, context is incorrect
- 1 x highpoly: Operator bpy.ops.mch.make_highpoly.poll() failed, context is incorrect

## 0.24.75 run: 40 scenarios x 12 steps (seeds 241..280)

{'OK': 40} in 160 s, largest Blender process 3427 MB (run while the full test suite was running)

### Python errors inside steps (Blender lived)

- 11 x redo: Operator bpy.ops.ed.redo.poll() failed, context is incorrect
- 5 x undo: Operator bpy.ops.ed.undo.poll() failed, context is incorrect

## 0.24.74 run: 40 scenarios x 12 steps (seeds 201..240)

{'OK': 40} in 113 s, largest Blender process 2397 MB

### Python errors inside steps (Blender lived)

- 12 x undo: Operator bpy.ops.ed.undo.poll() failed, context is incorrect
- 7 x redo: Operator bpy.ops.ed.redo.poll() failed, context is incorrect
- 1 x highpoly: Operator bpy.ops.mch.make_highpoly.poll() failed, context is incorrect

## 0.24.73 run: 100 scenarios x 12 steps (seeds 1..100)

{'OK': 100} in 397 s, largest Blender process 11243 MB

### Python errors inside steps (Blender lived)

- 27 x redo: Operator bpy.ops.ed.redo.poll() failed, context is incorrect
- 21 x undo: Operator bpy.ops.ed.undo.poll() failed, context is incorrect
- 2 x highpoly: Operator bpy.ops.mch.make_highpoly.poll() failed, context is incorrect
