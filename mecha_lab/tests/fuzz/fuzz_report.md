# Fuzz report: 100 scenarios x 12 steps (seeds 101..200)

{'OK': 100} in 401 s, largest Blender process 7544 MB

## Python errors inside steps (Blender lived)

- 26 x redo: Operator bpy.ops.ed.redo.poll() failed, context is incorrect
- 23 x undo: Operator bpy.ops.ed.undo.poll() failed, context is incorrect
- 1 x highpoly: Operator bpy.ops.mch.make_highpoly.poll() failed, context is incorrect
