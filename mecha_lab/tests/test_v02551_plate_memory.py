"""0.24.145 (user: "아머 플레이트도 저장이 안 돼" / "방금 그리면서 ... 값을 조정했으면 다음 긋는 선은 그 값을 기억해야 될 거 아녀,
그리고 블렌더를 끄고 새 프로젝트를 열면 기본값"): a value changed on a live Armor Plate goes on to the next plate of that
profile (kept on the scene - saved with the file); a new file starts with the defaults."""
from _harness import bpy, check, fresh, summary
from mathutils import Quaternion

import mecha_lab
from mecha_lab import armor_plate as ap, core_geometry as cg  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
P = cg.OrthoProjector(Quaternion())
bpy.ops.mesh.primitive_uv_sphere_add(radius=6.0, segments=64, ring_count=32, location=(0, 0, -5.4))
body = C.active_object


def draw_plate(x0):
    for o in C.selected_objects:
        o.select_set(False)
    body.select_set(True)
    C.view_layer.objects.active = body
    loop = [(500 + x0, 450), (600 + x0, 450), (600 + x0, 550), (500 + x0, 550)]
    ap.perform_plate(C, [loop], P)
    return C.active_object


a = draw_plate(-300)
h0 = a.mch_extract.extract_height
a.mch_extract.extract_height = h0 * 2.5                    # changed on the live plate
b = draw_plate(0)
check('a height changed on a live Armor Plate: the next plate (same profile) starts with it',
      abs(b.mch_extract.extract_height - h0 * 2.5) < 1e-6, (h0, b.mch_extract.extract_height))
check('... what the preset gave the plate and you did not touch is not kept (only what you changed)',
      set(ap.plate_memory(S).get(a.get(ap.PRESET_KEY), {})) == {'extract_height'}, ap.plate_memory(S))
fresh()
mecha_lab.register()
check('a new file: nothing kept - the defaults', ap.plate_memory(bpy.context.scene) == {})
summary()
