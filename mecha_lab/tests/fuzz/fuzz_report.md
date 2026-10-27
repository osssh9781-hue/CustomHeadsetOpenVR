# Fuzz report: 100 scenarios x 12 steps (seeds 1..100)

{'OK': 100} in 397 s, largest Blender process 11243 MB

## Python errors inside steps (Blender lived)

- 27 x redo: Operator bpy.ops.ed.redo.poll() failed, context is incorrect
- 21 x undo: Operator bpy.ops.ed.undo.poll() failed, context is incorrect
- 2 x highpoly: Operator bpy.ops.mch.make_highpoly.poll() failed, context is incorrect
