# Fuzz report: 40 scenarios x 14 steps (seeds 501..540)

{'OK': 40} in 180 s, largest Blender process 1030 MB

## BAD results (the mesh after a step)

- seed 517: BAD 12 hard_edges on Thin2_Split: slivers 0 -> 10
- seed 523: BAD 6 cut on Body: spikes 0 -> 1
- seed 528: BAD 8 cut on PlateB: spikes 0 -> 1
- seed 528: BAD 9 shell: new part PlateB_Shell {'spike': 1}

## Python errors inside steps (Blender lived)

- 1 x hard_edges on Thin2_Split: slivers 0 -> 10
- 1 x cut on Body: spikes 0 -> 1
- 1 x cut on PlateB: spikes 0 -> 1
- 1 x shell: 1}
