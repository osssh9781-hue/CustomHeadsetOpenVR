"""0.24.187 the hand / foot builder (user: "손바닥 발바닥, 그리고 사용할 손가락 프리셋 ... 각각 개수랑 길이 두께 조절하면 좋을 것
같고"): a hand / foot put together from the user's palm, sole and fingers; on a one-piece body too."""
import math
import sys

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import body_whole as bw, hand_kit as hk  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
C.scene.cursor.location = (0.0, 0.0, 0.0)


def islands(ob):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    seen, n = set(), 0
    for v in bm.verts:
        if v.index in seen:
            continue
        n += 1
        st = [v]
        seen.add(v.index)
        while st:
            a = st.pop()
            for e in a.link_edges:
                b = e.other_vert(a)
                if b.index not in seen:
                    seen.add(b.index)
                    st.append(b)
    bm.free()
    return n


def co(ob):
    return np.array([v.co[:] for v in ob.data.vertices])


r = bpy.ops.mch.handkit_add(base='Palm')
h = C.active_object
kp = h.mch_handkit
check(f'Build a Hand: the palm + 4 fingers + 1 thumb in one object ({islands(h)} pieces, {len(h.data.polygons)} faces)',
      r == {'FINISHED'} and hk.is_hand(h) and islands(h) == 6 and len(h.data.polygons) < 14000)
kp.f_count = 2
n2 = islands(h)
kp.f_count = 6
check(f'Number of fingers: 2 -> {n2} pieces, 6 -> {islands(h)}', n2 == 4 and islands(h) == 8)
kp.f_count = 4
y0, x0 = co(h)[:, 1].max(), np.ptp(co(h)[:, 0])
kp.f_length = 2.0
y1 = co(h)[:, 1].max()
kp.f_length = 1.0
check(f'Finger Length 2: the hand longer ({y0:.3f} -> {y1:.3f})', y1 > y0 + 0.03)
V0 = co(h)
kp.f_thick = 2.0
check('Finger Thickness 2: changes the fingers, the palm as it was', np.abs(co(h) - V0).max() > 0.003 and
      np.abs(co(h)[:2000] - V0[:2000]).max() < 1e-6)
kp.f_thick = 1.0
kp.f_bend = math.radians(90)
y2 = co(h)[:, 1].max()
check(f'Finger Bend 90: the fingers curled (the hand shorter: {y2:.3f})', y2 < y0 - 0.01)
kp.f_bend = 0.0
kp.t_count = 0
check('Thumbs 0: none', islands(h) == 5)
kp.t_count = 2
check('Thumbs 2: one on each side', islands(h) == 7)
kp.f_kind = 'Long'
check('Fingers: the long kind picked', co(h)[:, 1].max() > y0 + 0.02)
r = bpy.ops.mch.handkit_add(base='Sole')
f = C.active_object
check(f'Build a Foot: the sole + toes ({islands(f)} pieces)', r == {'FINISHED'} and islands(f) == 4)
# on a one-piece body
body, rig = bw.make(C, 1.8, (3, 0, 0), kind='creature2')
C.view_layer.objects.active = body
r = bpy.ops.mch.bodywhole_end(slot='Hand', variant='built')
ends = {o[bw.END_KEY]: o for o in rig.children if o.get(bw.END_KEY)}
check('One-piece body, Hands: Built - a built hand on each hand bone', r == {'FINISHED'} and
      sorted(ends) == ['Hand.L', 'Hand.R'] and all(hk.is_hand(o) for o in ends.values()))
ends['Hand.L'].mch_handkit.f_count = 3
L_, R_ = co(ends['Hand.L']), co(ends['Hand.R'])
check('... the left one\'s sliders: the right one the same (mirrored)', islands(ends['Hand.R']) == 5 and
      len(L_) == len(R_) and np.abs(L_ * (-1, 1, 1) - R_).max() < 1e-6)
r = bpy.ops.mch.bodywhole_end(slot='Hand', variant='own')
check('... Own: the built hands gone', r == {'FINISHED'} and not [o for o in rig.children if o.get(bw.END_KEY)])

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
