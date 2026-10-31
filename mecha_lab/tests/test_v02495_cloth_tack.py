"""0.24.95 Cloth Drape Panel + Tack Pins (user: "다각형으로 그은 플랜을 핀으로 천 하나 사람 하나 찍고, 반대도 천 하나 사람 하나
찍으면 그게 붙어서 시뮬, 핀도 여러 개 - 마블러스 디자이너처럼"): Mode Panel draws a flat panel in front of the body; tack
pins tie cloth points to body points (as many as you like); Drape This Mesh pulls each pin onto its body point and
holds it there while the rest drapes."""
import inspect

import numpy as np
from _harness import bpy, check, fresh, select_only, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import cloth_drape as cd, mesh_io as mio

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
st = S.mch_cdrape
st.padding, st.trim, st.stop_at_pins, st.two_sides = False, False, False, False
PX = 400.0


class Front:                    # an orthographic "view" from -Y: outline points are (x, z) x PX
    view_dir = Vector((0, 1, 0))

    def ray(self, xy):
        return Vector((xy[0] / PX, -5.0, xy[1] / PX)), Vector((0, 1, 0))


bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
body = C.active_object
select_only(body)
check('Mode Panel is there', 'PANEL' in {i.identifier for i in st.bl_rna.properties['drape_mode'].enum_items})
st.drape_mode = 'PANEL'
square = [[(x * PX, z * PX) for x, z in [(-0.4, 0.2), (0.4, 0.2), (0.4, 0.9), (-0.4, 0.9)]]]
msg = cd.perform(C, square, Front())
panel = C.view_layer.objects.active
co = np.array([(panel.matrix_world @ v.co)[:] for v in panel.data.vertices])
check('Mode Panel + a drawn polygon: a flat "Cloth Panel" facing the view (one plane), as big as the polygon',
      panel is not None and panel.name.startswith('Cloth Panel') and co[:, 1].std() < 1e-6 and len(co) > 50
      and abs(co[:, 0].min() + 0.4) < 0.02 and abs(co[:, 0].max() - 0.4) < 0.02 and abs(co[:, 2].max() - 0.9) < 0.02, msg)
check('... in front of the body (nearer the viewer than the sphere under it), not touching it',
      co[:, 1].max() < -0.98 and np.linalg.norm(co, axis=1).min() > 1.0, (co[:, 1].max(), np.linalg.norm(co, axis=1).min()))
check('... no cloth session yet (the panel waits for its pins)', not cd.sim_active())

# ---- tack pins: the panel's two top corners onto two points on top of the ball (like shoulders)
tl = co[np.argmin(-co[:, 2] * 10 + co[:, 0])]       # top-left corner
tr = co[np.argmin(-co[:, 2] * 10 - co[:, 0])]       # top-right corner
p1 = Vector((-0.35, -0.25, 0.9)).normalized()
p2 = Vector((0.35, -0.25, 0.9)).normalized()
v1 = cd.add_tack(panel, Vector(tl), body, p1, p1)
v2 = cd.add_tack(panel, Vector(tr), body, p2, p2)
check('add_tack: each pair stored on the cloth (its point index, the body, the body point)',
      len(cd.tacks_of(panel)) == 2 and {t['v'] for t in cd.tacks_of(panel)} == {v1, v2} and cd.tacks_of(panel)[0]['body'] == body.name)
cd.add_tack(panel, Vector(co[0]), body, Vector((0, -1, 0)), Vector((0, -1, 0)))
check('... as many as you like; Backspace (pop_tack) removes the last', len(cd.tacks_of(panel)) == 3 and cd.pop_tack(panel) == 2)
cd.add_tack(panel, Vector(tl), body, p1 * 1.0, p1)
check('... the same cloth point tacked again replaces its old pair (no duplicates)', len(cd.tacks_of(panel)) == 2)
idx, tgt, tb = cd.tack_targets(panel, 0.01)
check('tack_targets: the cloth points and their body points (lifted off the body by the offset), the body found from them',
      tb is body and sorted(idx.tolist()) == sorted([v1, v2]) and np.allclose(np.linalg.norm(tgt, axis=1), 1.01, atol=1e-4))

# ---- Drape This Mesh with the pins: they pull in and hold, the rim is free
st.gravity = 200.0
msg = cd.perform_mesh(C, panel, body)
sess = cd.SIM['sess']
cl = sess['cloth']
check('Drape This Mesh: the tack pins drive it (no rim pins), a session ready', cl.tack is not None and int((cl.pin >= 1).sum()) == 0
      and 'tack pins' in msg and cd.sim_active(), msg)
cd.SIM['running'] = True
for _ in range(sess['frames']):
    cd.advance(sess, st)
c = cl.co
d = np.linalg.norm(c[idx] - tgt, axis=1)
check('after the drape: each pinned point sits on its body point (within 1 cm)', d.max() < 0.01, d.tolist())
check('... the panel hangs from them over the ball: finite, outside it (the top edge pulled taut across the ball\'s top '
      'between the two pins may press in a little: under 3 %), below the pins',
      np.all(np.isfinite(c)) and np.linalg.norm(c, axis=1).min() > 0.97 and np.median(c[:, 2]) < tgt[:, 2].min(),
      (np.linalg.norm(c, axis=1).min(), np.median(c[:, 2])))
ti, ta, tm = cl.tether
check('... the panel stays on its pins (tethers from them: no point farther from its pin than the cloth between them)',
      np.all(np.linalg.norm(c[ti] - c[ta], axis=1) <= tm * 1.02 + 1e-6), float((np.linalg.norm(c[ti] - c[ta], axis=1) / tm).max()))
cd.restart(C)
check('Restart keeps the pins', cd.SIM['sess']['cloth'].tack is not None and len(cd.SIM['sess']['cloth'].tack[0]) == 2)
msg = cd.cancel(C)
check('Esc puts the panel back flat, the pins kept on it', not cd.sim_active() and len(cd.tacks_of(panel)) == 2
      and np.array([(panel.matrix_world @ v.co)[:] for v in panel.data.vertices])[:, 1].std() < 1e-6, msg)
cd.clear_tacks(panel)
check('Clear Tack Pins', cd.tacks_of(panel) == [])
check('Tack Pins operator (cloth point, then body point; Backspace / Enter) and Clear are registered and in the panel',
      hasattr(bpy.types, 'MCH_OT_cdrape_tack') and hasattr(bpy.types, 'MCH_OT_cdrape_tack_clear')
      and "'mch.cdrape_tack'" in inspect.getsource(cd.draw) and 'skip=self.cloth' in inspect.getsource(cd.MCH_OT_cdrape_tack.modal))
st.drape_mode = 'AREA'
summary()
