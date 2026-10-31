"""0.24.95 Drape Mask: the collider from a LOCAL low-res proxy of the region round the cloth (user: "마스크한 영역은 콜리전으로
로우 메시 뽑고 그 위에 시뮬용 천 뽑는 건가? 그게 더 이득이지 않나? 천 디테일 조정도 가능하고") and the cloth's Points following
the slider before Space."""
import numpy as np
from _harness import bpy, check, fresh, select_only, summary

import mecha_lab
from mecha_lab import cloth_drape as cd, collider_proxy as cpx, mesh_io as mio

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
st = S.mch_cdrape
st.padding, st.trim, st.stop_at_pins, st.two_sides = False, False, False, False

bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=256, ring_count=128)     # ~65k triangles: a heavy body
body = C.active_object
select_only(body)
att = body.data.attributes.new(cd.MASK_ATTR, 'FLOAT', 'POINT')
zs = np.array([v.co.z for v in body.data.vertices])
att.data.foreach_set('value', (zs > 0.7).astype(np.float32))                       # the cap masked
st.use_proxy, st.proxy_faces, st.mask_points, st.collide_with = True, 5000, 800, 'BODY'
msg = cd.perform_masked(C, body)
coll = bpy.data.collections.get(cpx.COLL)
loc = [o for o in coll.objects if o.get(cpx.SRC) == body.name and o.get(cpx.LOCAL)] if coll else []
check('Drape Mask on a heavy body: the collider is a LOCAL proxy "<name>_proxy_local" (hidden collection)',
      len(loc) == 1 and loc[0].name == body.name + '_proxy_local' and cd.sim_active(), msg)
lc = mio.read_co(loc[0].data)
ntri = sum(len(p.vertices) - 2 for p in loc[0].data.polygons)
check('... it covers only the region round the cloth (nothing near the bottom of the ball), about Proxy Faces triangles',
      lc[:, 2].min() > -0.2 and 4000 <= ntri <= 6000, (lc[:, 2].min(), ntri))
# the same budget on the whole ball: how many of its triangles fall in the region
whole, temp = cpx.proxy_mesh(C, body, 5000)
wc = mio.read_co(whole)
in_whole = int((wc[:, 2] > lc[:, 2].min()).sum())
in_local = len(lc)
check('... the same budget spent there: more points than a whole-body proxy has in that region (here the region is '
      'nearly half the ball; the smaller the mask against the body, the bigger the gain)', in_local > 1.5 * in_whole, (in_local, in_whole))
sess = cd.SIM['sess']
cd.SIM['running'] = True
for _ in range(30):
    cd.advance(sess, st)
c = sess['cloth'].co
check('... the cloth drapes on it: finite, outside the ball', np.all(np.isfinite(c)) and np.linalg.norm(c, axis=1).min() > 0.985,
      np.linalg.norm(c, axis=1).min())
cd.restart(C)
cd.SIM['running'] = False
ob = C.view_layer.objects.active
n0 = len(ob.data.vertices)
st.mask_points = 2400                                    # (the slider: the waiting cloth follows at once)
n1 = len(ob.data.vertices)
check('Points 800 -> 2400 before Space: the mask cloth is made again at once, about 3 x the points',
      2.3 < n1 / max(n0, 1) < 3.7 and np.allclose(cd.SIM['surface'], mio.read_co(ob.data)), (n0, n1))
cd.restart(C)
check('Space / Restart after it: the drape starts from the new cloth', cd.SIM['running'] and len(cd.SIM['sess']['cloth'].co) == n1
      and cd.SIM['sess']['frame'] == 0)
check('Points is in the snapshot', 'mask_points' in cd._snapshot.__code__.co_consts or "'mask_points'" in open(cd.__file__).read())
cd.cancel(C)
summary()
