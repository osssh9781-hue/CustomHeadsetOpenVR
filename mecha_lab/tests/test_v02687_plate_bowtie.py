"""0.24.292 (user: armor plate "Plate could not be built: The selection touches itself at a single vertex") a region
whose pieces meet at one point (a lasso touching itself / triangles dropped at a surface edge): the plate is built -
the point split; a speck hanging on by one point is dropped."""
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import armor_plate as ap

mecha_lab.register()
fresh()
C = bpy.context


def grid_region(cells):
    """Region mesh: unit squares (i, j) of a 0.1 grid on z = 0."""
    vid, verts, faces = {}, [], []

    def v(i, j):
        if (i, j) not in vid:
            vid[(i, j)] = len(verts)
            verts.append((i * 0.1, j * 0.1, 0.0))
        return vid[(i, j)]
    for i, j in cells:
        faces.append((v(i, j), v(i + 1, j), v(i + 1, j + 1), v(i, j + 1)))
    me = bpy.data.meshes.new('R')
    me.from_pydata(verts, [], faces)
    me.update()
    return me


bpy.ops.mesh.primitive_grid_add(x_subdivisions=40, y_subdivisions=40, size=4.0)
target = C.active_object
surround = target.data.copy()
A = [(i, j) for i in range(0, 5) for j in range(0, 5)]
B = [(i, j) for i in range(5, 10) for j in range(5, 10)]           # meets A only at the point (5, 5)
for name, cells, faces_min in (('two blocks meeting at a corner', A + B, 40),
                               ('a block with one square hanging on by a corner', A + [(5, 5)], 20)):
    region = grid_region(cells)
    try:
        part = ap.create_plate(C, target, region, surround.copy(), 'CHAMFER', 1.0)
        ok = part is not None and len(part.data.polygons) > faces_min
        info = len(part.data.polygons)
    except Exception as ex:                       # noqa: BLE001
        ok, info = False, repr(ex)
    check(f'{name}: the plate is built', ok, info)
region = grid_region(A)
part = ap.create_plate(C, target, region, surround.copy(), 'CHAMFER', 1.0)
check('a clean region still builds as before', part is not None and len(part.data.polygons) > 20)
summary()
