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
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
