# Fuzz reports (newest first)

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
