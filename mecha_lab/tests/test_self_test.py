"""The in-Blender self test (mch.self_test) runs and leaves the file unchanged."""
import sys
from _harness import bpy, check, cube, fresh, summary
import mecha_lab
from mecha_lab import self_test

fresh()
mecha_lab.register()
user = cube('UserObject')
user.select_set(True)
pools = lambda: (len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.scenes), len(bpy.data.curves),
                 len(bpy.data.lattices), len(bpy.data.node_groups))
before = pools()
report, ok = self_test.run(bpy.context)
print(report)
check('self test passes headless', ok, report.splitlines()[-1])
check('self test leaves no data behind', pools() == before, (before, pools()))
check('user object untouched', 'UserObject' in bpy.data.objects and len(user.data.vertices) == 8)
r = bpy.ops.mch.self_test()
check('operator runs and copies the report', r == {'FINISHED'})

# real-view step logic with a perspective / ortho RegionView3D stand-in (the GUI path)
from mathutils import Matrix, Quaternion, Vector


class Region:
    width, height = 1600, 900


class RV3D:
    def __init__(self, rot, dist, persp=True, loc=Vector((1.0, -2.0, 0.5))):
        self.view_rotation, self.view_distance, self.view_location = rot, dist, loc
        self.is_perspective = persp
        self.view_perspective = 'PERSP' if persp else 'ORTHO'
        cam = Matrix.Translation(loc) @ rot.to_matrix().to_4x4() @ Matrix.Translation((0, 0, dist))
        self.view_matrix = cam.inverted()
        n, f, fx = 0.01, 1000.0, 100.0 / 72.0
        fy = fx * Region.width / Region.height
        if persp:
            w = Matrix(((fx, 0, 0, 0), (0, fy, 0, 0), (0, 0, -(f + n) / (f - n), -2 * f * n / (f - n)), (0, 0, -1, 0)))
        else:
            sc = dist * 72.0 / 100.0
            w = Matrix(((1 / sc, 0, 0, 0), (0, fy / fx / sc, 0, 0), (0, 0, -1 / f, 0), (0, 0, 0, 1)))
        self.perspective_matrix = w @ self.view_matrix


rot = Quaternion((0.7157, 0.4365, 0.2863, 0.4632)).normalized()
for persp in (True, False):
    sc = bpy.data.scenes.new('ST_View_Test')
    with bpy.context.temp_override(scene=sc, view_layer=sc.view_layers[0]):
        try:
            res = self_test.view_cut_check(bpy.context, sc.collection, Region(), RV3D(rot, 15.0, persp))
        except Exception as ex:
            res = f'ERROR {ex}'
    check(f'0.11.2 self test real-view step: Cut / Alt Cut / Split ({"persp" if persp else "ortho"})',
          res.startswith('CUT ok, CUT Alt ok, SPLIT ok'), res)
    for ob in list(sc.objects):
        me = ob.data
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
    bpy.data.scenes.remove(sc)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
