# Fuzz report: 20 scenarios x 12 steps (seeds 1101..1120)

{'OK': 20} in 94 s, largest Blender process 595 MB

## BAD results (the mesh after a step)

- seed 1103: BAD 7 cut_ramp on PlateB: faces on the same points 0 -> 3
- seed 1103: BAD 7 cut_ramp on PlateB: zero-area faces 0 -> 1
- seed 1103: BAD 7 cut_ramp on PlateB: debris pieces 0 -> 1
- seed 1104: BAD 11 cut_gn on Knob: debris pieces 0 -> 4
- seed 1106: BAD 8 cut_ramp on Block: slivers 0 -> 3
- seed 1107: BAD 3 cut_bevel on Body: spikes 0 -> 2
- seed 1107: BAD 3 cut_bevel on Body: debris pieces 0 -> 2
- seed 1107: BAD 4 cut_bevel on Body: zero-area faces 0 -> 4
- seed 1107: BAD 4 cut_bevel on Body: debris pieces 2 -> 7
- seed 1107: BAD 5 cut_bevel on Body: spikes 2 -> 3
- seed 1107: BAD 5 cut_bevel on Body: zero-area faces 4 -> 7
- seed 1107: BAD 5 cut_bevel on PlateA: spikes 0 -> 1
- seed 1107: BAD 5 cut_bevel on PlateA: zero-area faces 0 -> 2
- seed 1107: BAD 5 cut_bevel on PlateA: debris pieces 0 -> 1
- seed 1107: BAD 8 cut_gn on PlateB: debris pieces 0 -> 2
- seed 1109: BAD 10 cut_gn on Body: spikes 0 -> 5
- seed 1109: BAD 10 cut_gn on Body: zero-area faces 0 -> 31
- seed 1109: BAD 10 cut_gn on Body: debris pieces 0 -> 15
- seed 1110: BAD 11 cut_bevel on Knob: spikes 0 -> 1
- seed 1112: BAD 5 cut_alt on Block: debris pieces 0 -> 1
- seed 1112: BAD 7 quad on Block: NOOP - Quad Remesh: no faces came out (try more polygons)
- seed 1112: BAD 8 quad on Block: NOOP - Quad Remesh: no faces came out (try more polygons)
- seed 1113: BAD 9 cut_gn on Knob: debris pieces 0 -> 1
- seed 1115: BAD 4 cut_gn on Body: debris pieces 0 -> 1
- seed 1117: BAD 9 cut_gn on Body: debris pieces 0 -> 1
- seed 1117: BAD 9 cut_gn on PlateA: debris pieces 0 -> 1
- seed 1117: BAD 9 cut_gn on Knob: debris pieces 0 -> 1
- seed 1118: BAD 1 cut_line on Body: debris pieces 1 -> 2
- seed 1118: BAD 10 cut_gn on Body: debris pieces 0 -> 1
- seed 1119: BAD 1 cut_gn on Body: debris pieces 0 -> 1
- seed 1119: BAD 8 cut_gn on Block: spikes 0 -> 1
- seed 1120: BAD 3 cut_bevel on Knob: spikes 0 -> 3
- seed 1120: BAD 3 cut_bevel on Knob: faces on the same points 0 -> 2
- seed 1120: BAD 3 cut_bevel on Knob: debris pieces 0 -> 2
- seed 1120: BAD 3 cut_bevel on Knob: slivers 0 -> 4
- seed 1120: BAD 6 cut_plain on Knob: spikes 1 -> 2

## Python errors inside steps (Blender lived)

- 4 x cut_gn on Body: debris pieces 0 -> 1
- 2 x quad on Block: no faces came out (try more polygons)
- 2 x cut_gn on Knob: debris pieces 0 -> 1
- 1 x cut_ramp on PlateB: faces on the same points 0 -> 3
- 1 x cut_ramp on PlateB: zero-area faces 0 -> 1
- 1 x cut_ramp on PlateB: debris pieces 0 -> 1
- 1 x cut_gn on Knob: debris pieces 0 -> 4
- 1 x cut_ramp on Block: slivers 0 -> 3
- 1 x cut_bevel on Body: spikes 0 -> 2
- 1 x cut_bevel on Body: debris pieces 0 -> 2
- 1 x cut_bevel on Body: zero-area faces 0 -> 4
- 1 x cut_bevel on Body: debris pieces 2 -> 7
- 1 x cut_bevel on Body: spikes 2 -> 3
- 1 x cut_bevel on Body: zero-area faces 4 -> 7
- 1 x cut_bevel on PlateA: spikes 0 -> 1
- 1 x cut_bevel on PlateA: zero-area faces 0 -> 2
- 1 x cut_bevel on PlateA: debris pieces 0 -> 1
- 1 x cut_gn on PlateB: debris pieces 0 -> 2
- 1 x cut_gn on Body: spikes 0 -> 5
- 1 x cut_gn on Body: zero-area faces 0 -> 31
- 1 x cut_gn on Body: debris pieces 0 -> 15
- 1 x cut_bevel on Knob: spikes 0 -> 1
- 1 x cut_alt on Block: debris pieces 0 -> 1
- 1 x cut_gn on PlateA: debris pieces 0 -> 1
- 1 x cut_line on Body: debris pieces 1 -> 2
- 1 x cut_gn on Block: spikes 0 -> 1
- 1 x cut_bevel on Knob: spikes 0 -> 3
- 1 x cut_bevel on Knob: faces on the same points 0 -> 2
- 1 x cut_bevel on Knob: debris pieces 0 -> 2
- 1 x cut_bevel on Knob: slivers 0 -> 4
- 1 x cut_plain on Knob: spikes 1 -> 2

## Refusals / slow steps (the tool said no, or took over 20 s)

- seed 1101: FAIL 1 cut_gn on PlateB: {'CANCELLED'} Auto Target: the shape does not cover any mesh; nothing was changed.
- seed 1101: FAIL 2 cut_bevel on PlateB: {'CANCELLED'} Auto Target: the shape does not cover any mesh; nothing was changed.
- seed 1101: FAIL 3 cut_bevel on PlateB: {'CANCELLED'} Aim the shape at the mesh surface (Depth mode = From Surface).
- seed 1101: FAIL 4 cut_ramp on Block: {'PASS_THROUGH'} invoke: {'PASS_THROUGH'}
- seed 1101: FAIL 7 cut_gn on Block: {'PASS_THROUGH'} invoke: {'PASS_THROUGH'}
- seed 1101: FAIL 10 cut_ramp on Block: {'PASS_THROUGH'} invoke: {'PASS_THROUGH'}
- seed 1107: FAIL 0 cut_line on PlateB: {'CANCELLED'} Aim the shape at the mesh surface (Depth mode = From Surface).
- seed 1112: FAIL 6 cut_gn on Block: {'CANCELLED'} Auto Target: the shape does not cover any mesh; nothing was changed.
- seed 1112: FAIL 9 cut_line on Block: {'CANCELLED'} No target geometry to cut.
- seed 1115: FAIL 11 cut_gn on Block: {'PASS_THROUGH'} invoke: {'PASS_THROUGH'}
- seed 1116: FAIL 10 cut_line on Block: {'PASS_THROUGH'} invoke: {'PASS_THROUGH'}
- seed 1116: FAIL 11 cut_alt on Block: {'PASS_THROUGH'} invoke: {'PASS_THROUGH'}
- seed 1117: FAIL 11 cut_bevel on PlateA: {'FINISHED'} Cut: PlateA | WARNING: Edge Finish found 0 new edges; no bevel/chamfer | FAILED, left unchanged: Body (Boolean failed sa
- seed 1119: FAIL 3 hide_part on PlateA: {'CANCELLED'} Auto Target: the shape does not cover any mesh; nothing was changed.
- seed 1120: FAIL 5 cut_ramp on PlateB: {'CANCELLED'} Auto Target: the shape does not cover any mesh; nothing was changed.
- seed 1120: FAIL 6 cut_plain on PlateB: {'CANCELLED'} Auto Target: the shape does not cover any mesh; nothing was changed.
- seed 1120: FAIL 9 hide_part on PlateB: {'CANCELLED'} Auto Target: the shape does not cover any mesh; nothing was changed.
