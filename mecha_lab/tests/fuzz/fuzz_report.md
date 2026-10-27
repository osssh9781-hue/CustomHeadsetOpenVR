# Fuzz report: 100 scenarios x 12 steps (seeds 1..100)

{'OK': 98, 'CRASH': 2} in 298 s, largest Blender process 10623 MB

## seed 5: CRASH (1 s)

last step: `STEP 7 undo on Part (500 faces, SCULPT)`

```
SCENARIO 5: part monkey (500 faces)
STEP 0 hard_apply on Part (500 faces, OBJECT)
Info: Hard Edges: nothing to apply
  ok 0.03s -> 500 faces
STEP 1 split_masked on Part (500 faces, SCULPT)
Info: Split: paint a mask first (Ctrl + drag on the model)
  ok 0.00s -> 500 faces
STEP 2 highpoly on Part (500 faces, SCULPT)
Info: High poly: 1 object(s), 8,806 faces in "HighPoly"
  ok 0.34s -> 8,806 faces
STEP 3 highpoly on Part_HP (8,806 faces, OBJECT)
ERROR 3 highpoly: RuntimeError: Operator bpy.ops.mch.make_highpoly.poll() failed, context is incorrect
STEP 4 groups_from_mask on Part_HP (8,806 faces, OBJECT)
Info: Polygroup from mask
  ok 0.00s -> 8,806 faces
STEP 5 undo on Part_HP (8,806 faces, SCULPT)
00:01.030  bpy.rna          | WARNING current value '3' matches no enum in 'BrushTextureSlot', '', 'map_mode'
  ok 0.01s -> 0 faces
STEP 6 hard_apply on Part (500 faces, OBJECT)
Info: Hard Edges: nothing to apply
  ok 0.00s -> 500 faces
STEP 7 undo on Part (500 faces, SCULPT)
```

## seed 58: CRASH (62 s)

last step: `STEP 5 divide on Part (57,926 faces, SCULPT)`

```
SCENARIO 58: part monkey (500 faces)
STEP 0 del_hidden on Part (500 faces, OBJECT)
Info: Nothing hidden (Ctrl+Shift + drag to hide)
  ok 0.02s -> 500 faces
STEP 1 he_style on Part (500 faces, SCULPT)
  ok 0.00s -> 500 faces
STEP 2 dynamesh on Part (500 faces, SCULPT)
Info: DynaMesh: 57,928 points
  ok 0.16s -> 57,926 faces
STEP 3 divide on Part (57,926 faces, SCULPT)
Info: Divide: SDiv 1
  ok 32.50s -> 57,926 faces
STEP 4 edge_mesh on Part (57,926 faces, SCULPT)
Info: Edge Mesh: Del Higher / Del Lower first
  ok 0.00s -> 57,926 faces
STEP 5 divide on Part (57,926 faces, SCULPT)
```

## Python errors inside steps (Blender lived)

- 27 x redo: Operator bpy.ops.ed.redo.poll() failed, context is incorrect
- 19 x undo: Operator bpy.ops.ed.undo.poll() failed, context is incorrect
- 1 x highpoly: Operator bpy.ops.mch.make_highpoly.poll() failed, context is incorrect
