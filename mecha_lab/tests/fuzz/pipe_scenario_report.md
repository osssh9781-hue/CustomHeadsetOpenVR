# Fuzz report: 20 scenarios x 12 steps (seeds 1201..1220)

{'OK': 20} in 837 s, largest Blender process 6966 MB

## BAD results (the mesh after a step)

- seed 1201: BAD 8 cut_bevel on Thin80: debris pieces 0 -> 1
- seed 1201: BAD 11 cut_gn on Knob: debris pieces 0 -> 1
- seed 1202: BAD 11 cut_line on Knob: spikes 0 -> 2
- seed 1202: BAD 11 cut_line on Knob: debris pieces 0 -> 2
- seed 1204: BAD 0 cut_gn on Knob: debris pieces 0 -> 1
- seed 1205: BAD 3 cut_bevel on Knob: spikes 0 -> 4
- seed 1205: BAD 3 cut_bevel on Knob: faces on the same points 0 -> 1
- seed 1205: BAD 3 cut_bevel on Knob: zero-area faces 0 -> 1
- seed 1205: BAD 3 cut_bevel on Knob: debris pieces 0 -> 7
- seed 1207: BAD 6 cut_gn on Body: debris pieces 0 -> 1
- seed 1213: BAD 1 cut_bevel on PlateA: spikes 0 -> 1
- seed 1213: BAD 3 cut_ramp on PlateA: spikes 0 -> 1
- seed 1213: BAD 3 cut_ramp on PlateA: faces on the same points 0 -> 1
- seed 1213: BAD 3 cut_ramp on PlateA: debris pieces 0 -> 2
- seed 1213: BAD 5 quad on PlateA: debris pieces 0 -> 1
- seed 1214: BAD 0 cut_line on Body: spikes 0 -> 3
- seed 1214: BAD 0 cut_line on Body: zero-area faces 0 -> 3
- seed 1214: BAD 0 cut_line on Body: debris pieces 0 -> 18
- seed 1214: BAD 11 cut_gn on Thin89: debris pieces 0 -> 1
- seed 1215: BAD 6 cut_gn on Body: spikes 0 -> 3
- seed 1215: BAD 6 cut_gn on Body: debris pieces 0 -> 5
- seed 1215: BAD 10 cut_ramp on PlateB: spikes 0 -> 3
- seed 1215: BAD 10 cut_ramp on PlateB: debris pieces 0 -> 2
- seed 1217: BAD 5 cut_bevel on Body: spikes 0 -> 1
- seed 1217: BAD 5 cut_bevel on Body: faces on the same points 0 -> 1
- seed 1217: BAD 5 cut_bevel on Body: debris pieces 0 -> 1
- seed 1220: BAD 9 cut_bevel on Knob: debris pieces 0 -> 4

## Python errors inside steps (Blender lived)

- 2 x cut_gn on Knob: debris pieces 0 -> 1
- 1 x cut_bevel on Thin80: debris pieces 0 -> 1
- 1 x cut_line on Knob: spikes 0 -> 2
- 1 x cut_line on Knob: debris pieces 0 -> 2
- 1 x cut_bevel on Knob: spikes 0 -> 4
- 1 x cut_bevel on Knob: faces on the same points 0 -> 1
- 1 x cut_bevel on Knob: zero-area faces 0 -> 1
- 1 x cut_bevel on Knob: debris pieces 0 -> 7
- 1 x cut_gn on Body: debris pieces 0 -> 1
- 1 x cut_bevel on PlateA: spikes 0 -> 1
- 1 x cut_ramp on PlateA: spikes 0 -> 1
- 1 x cut_ramp on PlateA: faces on the same points 0 -> 1
- 1 x cut_ramp on PlateA: debris pieces 0 -> 2
- 1 x quad on PlateA: debris pieces 0 -> 1
- 1 x cut_line on Body: spikes 0 -> 3
- 1 x cut_line on Body: zero-area faces 0 -> 3
- 1 x cut_line on Body: debris pieces 0 -> 18
- 1 x cut_gn on Thin89: debris pieces 0 -> 1
- 1 x cut_gn on Body: spikes 0 -> 3
- 1 x cut_gn on Body: debris pieces 0 -> 5
- 1 x cut_ramp on PlateB: spikes 0 -> 3
- 1 x cut_ramp on PlateB: debris pieces 0 -> 2
- 1 x cut_bevel on Body: spikes 0 -> 1
- 1 x cut_bevel on Body: faces on the same points 0 -> 1
- 1 x cut_bevel on Body: debris pieces 0 -> 1
- 1 x cut_bevel on Knob: debris pieces 0 -> 4

## Refusals / slow steps (the tool said no, or took over 20 s)

- seed 1204: FAIL 2 cut_alt on PlateB: {'CANCELLED'} Aim the shape at the mesh surface (Depth mode = From Surface).
- seed 1204: FAIL 4 cut_ramp on Block: {'PASS_THROUGH'} invoke: {'PASS_THROUGH'}
- seed 1205: SLOW 3 cut_bevel on Knob: 402.1s
- seed 1205: SLOW 5 cut_gn on Knob: 415.2s
- seed 1205: FAIL 6 cut_ramp on Block: {'PASS_THROUGH'} invoke: {'PASS_THROUGH'}
- seed 1205: FAIL 7 cut_gn on Block: {'PASS_THROUGH'} invoke: {'PASS_THROUGH'}
- seed 1207: FAIL 6 cut_gn on Thin60: {'CANCELLED'} The shape does not intersect any target; nothing was changed. Failed: Body (Boolean failed safely, mesh unchanged. EXACT
- seed 1207: FAIL 9 cut_line on Block: {'CANCELLED'} Aim the shape at the mesh surface (Depth mode = From Surface).
- seed 1208: FAIL 3 cut_line on PlateB: {'CANCELLED'} No target geometry to cut.
- seed 1208: FAIL 6 cut_line on Block: {'PASS_THROUGH'} invoke: {'PASS_THROUGH'}
- seed 1209: FAIL 1 cut_bevel on PlateB: {'CANCELLED'} Auto Target: the shape does not cover any mesh; nothing was changed.
- seed 1209: FAIL 2 hide_strip on PlateB: {'CANCELLED'} Auto Target: the shape does not cover any mesh; nothing was changed.
- seed 1209: FAIL 3 cut_bevel on PlateB: {'CANCELLED'} Aim the shape at the mesh surface (Depth mode = From Surface).
- seed 1210: FAIL 7 hide_part on PlateB: {'RUNNING_MODAL'} This tool needs a closed outline (3+ points)
- seed 1210: FAIL 8 cut_bevel on PlateB: {'CANCELLED'} Aim the shape at the mesh surface (Depth mode = From Surface).
- seed 1211: FAIL 6 cut_gn on Thin61: {'CANCELLED'} Aim the shape at the mesh surface (Depth mode = From Surface).
- seed 1212: FAIL 5 cut_plain on Knob: {'FINISHED'} Cut: Knob | FAILED, left unchanged: Body (Boolean failed safely, mesh unchanged. MANIFOLD: result has 1 non-mani)
- seed 1212: FAIL 7 cut_ramp on Block: {'PASS_THROUGH'} invoke: {'PASS_THROUGH'}
- seed 1212: FAIL 8 cut_bevel on Block: {'PASS_THROUGH'} invoke: {'PASS_THROUGH'}
- seed 1212: FAIL 9 hide_strip on Block: {'PASS_THROUGH'} invoke: {'PASS_THROUGH'}
- seed 1214: FAIL 0 quad on Body: Quad Remesh: the part is thinner than a quad at this count (65,824 faces kept as they are - 657 edges would have their f
- seed 1214: SLOW 0 cut_line on Body: 29.3s
- seed 1214: FAIL 6 cut_plain on Thin89: {'FINISHED'} Cut: Thin89 | FAILED, left unchanged: Body (Boolean failed safely, mesh unchanged. MANIFOLD: result has 1 non-mani)
- seed 1214: FAIL 7 cut_bevel on Thin89: {'FINISHED'} Cut: Thin89 | BEVEL: 24 newly cut edges | FAILED, left unchanged: Body (Boolean failed safely, mesh unchanged. MANIFOLD:
- seed 1214: FAIL 8 cut_ramp on Thin89: {'FINISHED'} Cut Ramp: Thin89 | 0.112 deep at one side, up to the surface (deep side: < > / Pick Edge in GN Edge) | failed: Body (Boo
- seed 1214: FAIL 11 cut_gn on Thin89: {'FINISHED'} Cut: Thin89 | GN Chamfer: 14 border edges | FAILED, left unchanged: Body (Boolean failed safely, mesh unchanged. MANIFOL
- seed 1215: FAIL 2 cut_gn on Block: {'PASS_THROUGH'} invoke: {'PASS_THROUGH'}
- seed 1215: FAIL 3 cut_line on Block: {'PASS_THROUGH'} invoke: {'PASS_THROUGH'}
- seed 1217: FAIL 10 hide_restore on PlateA: {'CANCELLED'} The shape does not intersect the mesh; nothing was changed.
