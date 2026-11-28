"""0.24.355 (user: "솔로 모드 했는데도 옆에 메쉬 그림자가 같이 베이크 되는 거지?"): No High Poly AO - with Others Shade AO
off (the default) a mesh's AO comes from itself only: a mesh right beside it (another selected part too) casts no
shadow into it; on: it does, as before.  Fast engine and Cycles alike."""
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bake_maps as bm

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
RES = 256
bpy.ops.mesh.primitive_plane_add(size=2)
plate = C.active_object
plate.name = 'Plate'
plate.data.materials.append(bpy.data.materials.new('P'))
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.55))
nb = C.active_object
nb.name = 'Neighbour'
st = S.mch_bake
st.res, st.own = str(RES), True
for k in ('normal', 'ao', 'color', 'rough', 'metal', 'curv', 'height', 'emit'):
    setattr(st, k, k == 'ao')
st.save, st.use_on_low, st.new_uv, st.smooth = False, False, False, False
st.ao_samples = 64


def ao(fast, others):
    st.fast, st.ao_others = fast, others
    for o in S.objects:
        o.select_set(False)
    plate.select_set(True)
    C.view_layer.objects.active = plate
    bm.bake_pair(C, plate, [], st)
    px = np.array(bpy.data.images[f'Plate_{bm.SUFFIX["AO"]}'].pixels[:]).reshape(RES, RES, 4)[..., 0]
    c = px[RES // 2 - 8:RES // 2 + 8, RES // 2 - 8:RES // 2 + 8]       # (under the cube)
    return float(c.mean())


for fast in (True, False):
    off, on = ao(fast, False), ao(fast, True)
    nm = 'fast engine' if fast else 'Cycles'
    check(f'{nm}: Others Shade AO off - no shadow of the mesh beside it (AO under it {off:.2f})', off > 0.9)
    check(f'{nm}: Others Shade AO on - its shadow, as before (AO under it {on:.2f})', on < off - 0.2)
check('the neighbour is back in the render after the bake', not nb.hide_render and not plate.hide_render)
summary()
