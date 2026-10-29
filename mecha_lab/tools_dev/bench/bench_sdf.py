"""Local SDF feasibility: the cut region as a closed local shell, cut exactly, then resampled through Blender's
own OpenVDB voxel remesh (the fastest SDF we could use without new dependencies) at the mesh's own edge length
and at half of it.  Measures time, face count, planarity of the cut wall and the spread of its normals - what an
SDF representation does to a hard-surface cut even in the best case (resampling an exact cut).
usage: python bench_sdf.py ico9"""
import sys, time, bpy, bmesh, numpy as np
sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/tests')
from _harness import bpy, fresh
import mecha_lab
from mecha_lab import core_geometry as cg, region_cut as rc, mesh_io as mio
fresh(); mecha_lab.register()
C = bpy.context
which = sys.argv[-1]
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=9 if which != 'ico8' else 8, radius=1.0)
ob = C.active_object
m = ob.modifiers.new('d', 'DISPLACE'); t = bpy.data.textures.new('t', 'CLOUDS'); t.noise_scale = 0.3; m.texture = t; m.strength = 0.2
with C.temp_override(object=ob, active_object=ob):
    bpy.ops.object.modifier_apply(modifier='d')
me = ob.data
co = mio.read_co(me); ev = mio.read_edge_verts(me)
edge = float(np.linalg.norm(co[ev[:, 0]] - co[ev[:, 1]], axis=1).mean())
print(f'BODY {which}: {len(me.polygons):,} faces, mean edge {edge:.5f}', flush=True)
import math
from mathutils import Matrix, Vector
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.35, 0.1, 0.0)); cutter = C.active_object; cutter.scale = (0.2, 0.2, 2.6)
cutter.rotation_euler = (math.radians(15), math.radians(10), math.radians(20)); C.view_layer.update()
M = np.array(cutter.matrix_world)
R = M[:3, :3] / np.linalg.norm(M[:3, :3], axis=0)        # the cutter's axes (unit)
ctr = M[:3, 3]
WN = R[:, 0]; WD = float(WN @ ctr) - 0.1                    # the wall plane: the cutter's -x face (0.2 wide -> half 0.1)

# the local closed shell: the part inside the region box (cutter box + margin), as one closed solid
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.35, 0.1, 0.0)); box = C.active_object; box.scale = (0.32, 0.32, 1.9); C.view_layer.update()
t0 = time.perf_counter()
sub = cg.evaluate_boolean(C, ob, box, 'INTERSECT', 'MANIFOLD')
t_shell = time.perf_counter() - t0
nm = cg.non_manifold_edge_count(sub)
print(f'local shell (part inside the region box, Manifold intersect): {len(sub.polygons):,} faces, {t_shell:.2f}s, open edges {nm}', flush=True)
shell_ob = bpy.data.objects.new('Shell', sub); C.collection.objects.link(shell_ob)

t0 = time.perf_counter(); cut = cg.evaluate_boolean(C, shell_ob, cutter, 'DIFFERENCE', 'EXACT'); t_cut = time.perf_counter() - t0
print(f'exact boolean of the shell: {t_cut:.2f}s -> {len(cut.polygons):,} faces, open edges {cg.non_manifold_edge_count(cut)}', flush=True)

def wall_stats(mesh, v, label):
    """points / faces near the cutter's -x wall plane (inside the column's y range, away from the shell caps), and
    the sharp edge: faces within 2 voxels of the wall-to-surface edge whose normal is neither the wall's nor the
    surface's (rounded corner)."""
    P = mio.read_co(mesh); st, tt = mio.read_face_starts(mesh); cv = mio.read_corner_verts(mesh)
    nrm = np.empty(len(mesh.polygons) * 3); mesh.polygons.foreach_get('normal', nrm); nrm = nrm.reshape(-1, 3)
    c = np.add.reduceat(P[cv], st) / tt[:, None]
    def loc(X):
        return (X - ctr) @ R          # cutter-local coordinates
    lc, lp = loc(c), loc(P)
    inside_col = lambda L: (np.abs(L[:, 1]) < 0.08) & (np.abs(L[:, 2]) < 0.9)
    dist_c = np.abs(c @ WN - WD); dist_p = np.abs(P @ WN - WD)
    band = (dist_c < 1.5 * v) & inside_col(lc)
    pts = (dist_p < 1.5 * v) & inside_col(lp)
    area = np.empty(len(mesh.polygons)); mesh.polygons.foreach_get('area', area)
    angf = np.degrees(np.arccos(np.clip(np.abs(nrm @ WN), 0, 1)))
    wall = band & (angf < 45)                        # the wall itself (not the surface faces next to it)
    wv = np.zeros(len(P), bool); wv[cv[np.repeat(wall, tt)]] = True
    d = dist_p[wv & pts]
    aw = area[wall]; a1 = aw[angf[wall] < 1].sum() / aw.sum() if aw.sum() else 0
    near = (dist_c < 3 * v) & inside_col(lc)
    rd = near & (angf > 15) & (angf < 75)
    print(f'   {label}: {len(mesh.polygons):,} faces | wall faces {int(wall.sum()):,} (area {aw.sum():.3e}): their points {int((wv & pts).sum()):,} off the plane rms {np.sqrt((d ** 2).mean()) if len(d) else 0:.2e} max {d.max() if len(d) else 0:.2e}; '
          f'wall area with the normal within 1 deg of the plane {100 * a1:.1f}% | rounded faces along the wall edge (normal 15-75 deg off, within 3 voxels): {int(rd.sum()):,}, area {area[rd].sum():.2e} = {100 * area[rd].sum() / max(1e-12, area[near].sum()):.1f}% of the band', flush=True)

wall_stats(cut, edge, 'exact boolean (reference)')
for scale in (1.0, 0.5, 0.25):
    v = edge * scale
    o = bpy.data.objects.new('Vox', cut.copy()); C.collection.objects.link(o)
    o.data.remesh_voxel_size = v; o.data.remesh_voxel_adaptivity = 0.0
    for x in C.selected_objects: x.select_set(False)
    o.select_set(True); C.view_layer.objects.active = o
    t0 = time.perf_counter()
    with C.temp_override(object=o, active_object=o, selected_objects=[o], selected_editable_objects=[o]):
        bpy.ops.object.voxel_remesh()
    dt = time.perf_counter() - t0
    print(f'voxel remesh (OpenVDB SDF) of the cut shell at voxel {v:.2e} ({scale} x edge): {dt:.2f}s', flush=True)
    wall_stats(o.data, v, f'SDF {scale} x edge')
    bpy.data.objects.remove(o)
# what "SDF everything" costs: the whole 1.3M part at the mesh's edge length
o = bpy.data.objects.new('VoxAll', me.copy()); C.collection.objects.link(o)
o.data.remesh_voxel_size = edge; o.data.remesh_voxel_adaptivity = 0.0
for x in C.selected_objects: x.select_set(False)
o.select_set(True); C.view_layer.objects.active = o
t0 = time.perf_counter()
with C.temp_override(object=o, active_object=o, selected_objects=[o], selected_editable_objects=[o]):
    bpy.ops.object.voxel_remesh()
print(f'voxel remesh of the WHOLE part at the edge length: {time.perf_counter() - t0:.2f}s -> {len(o.data.polygons):,} faces', flush=True)
