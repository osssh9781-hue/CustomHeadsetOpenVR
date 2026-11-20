"""0.24.267 (user: "Viewport % 1 퍼센트인데 뷰포트로 맞춰 놨는데 렌더에서 더 풍성해져서"): Render Like Viewport - the render
keeps only the Viewport % share too.  Counted on the real render's evaluated fur (the render depsgraph)."""
import math

from _harness import bpy, check, fresh, summary
from mathutils import Euler

import mecha_lab
from mecha_lab import core_geometry as cg, creature_fur as cf  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=48)
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)
st = S.mch_fur
st.density, st.length = 20000.0, 0.08
cf.perform(C, [[(500 + 150 * math.cos(a), 500 + 120 * math.sin(a)) for a in [i * math.tau / 48 for i in range(48)]]],
           FRONT)
fur = C.active_object
pg = fur.mch_fur
check('a fur, the new switch there, off by default (all strands render as before)',
      cf.is_fur(fur) and hasattr(pg, 'display_render') and pg.display_render is False)
C.view_layer.update()
full = len(fur.evaluated_get(C.evaluated_depsgraph_get()).data.curves)
pg.display = 0.01
C.view_layer.update()
view = len(fur.evaluated_get(C.evaluated_depsgraph_get()).data.curves)
check(f'Viewport 1 %: the viewport draws about 1 % ({view} of {full})', 0 < view < full * 0.03)

COUNT = []


def grab(scene, dg=None):
    if dg is not None and dg.mode == 'RENDER':
        f = scene.objects.get(fur.name)
        COUNT.append(len(f.evaluated_get(dg).data.curves))


bpy.app.handlers.frame_change_post.append(grab)
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); S.collection.objects.link(cam)
cam.location = (0, -6, 0); cam.rotation_euler = (math.pi / 2, 0, 0); S.camera = cam
S.render.engine = 'CYCLES'; S.cycles.samples = 1; S.cycles.device = 'CPU'
S.render.resolution_x = S.render.resolution_y = 16


def rendered():
    COUNT.clear()
    bpy.ops.render.render()
    return COUNT[-1] if COUNT else None


r_off = rendered()
pg.display_render = True
r_on = rendered()
check(f'switch off: the render has every strand ({r_off} of {full}) - as before', r_off == full)
check(f'Render Like Viewport on: the render keeps the same 1 % ({r_on}, the viewport {view})', r_on == view)
pg.display_render = False
check('off again: all back', rendered() == full)
summary()
