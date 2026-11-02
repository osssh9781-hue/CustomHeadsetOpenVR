"""0.24.95 Cloth Drape Show Proxies (user: "쇼 프록시가 안 꺼져"): the collider proxies are shown exactly when the switch is
on - also after Ctrl+Z / Ctrl+Shift+Z (the undo brought back an earlier step's visibility while the switch itself
stays as it was: the switch said off, the proxies showed, a click only turned it 'on'), when the first proxy is made
with the switch already on (it was always made hidden), and when a file is opened."""
import os
import tempfile

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import cloth_drape as cd, collider_proxy as cpx

fresh()
mecha_lab.register()
C = bpy.context


def drawn():
    C.view_layer.update()
    coll = bpy.data.collections.get(cpx.COLL)
    obs = list(coll.objects) if coll is not None else []
    return [o.visible_get() for o in obs]


bpy.ops.mesh.primitive_uv_sphere_add(segments=256, ring_count=128)
body = C.active_object
st = cd.settings(C)
st.show_proxy = True                                    # (on before any proxy exists)
cpx.proxy_mesh(C, body, 2000)
check('Show Proxies on before the first proxy is made: the proxy made shown (it was always made hidden)',
      drawn() == [True], drawn())
st.show_proxy = False
check('... the switch off: hidden', drawn() == [False], drawn())
st.show_proxy = True
check('... on: shown', drawn() == [True], drawn())

bpy.ops.ed.undo_push(message='proxies shown')
st.show_proxy = False                                   # (a click in the panel: a setting, no undo step of its own)
bpy.ops.mesh.primitive_cube_add(location=(3.0, 0.0, 0.0))
bpy.ops.ed.undo_push(message='a cube')
bpy.ops.ed.undo()
check('Ctrl+Z after switching it off: the switch stays off and the proxies stay hidden (they came back before)',
      not cd.settings(C).show_proxy and drawn() == [False], (cd.settings(C).show_proxy, drawn()))
bpy.ops.ed.redo()
check('... Ctrl+Shift+Z: still off, still hidden', not cd.settings(C).show_proxy and drawn() == [False],
      (cd.settings(C).show_proxy, drawn()))
cd.settings(C).show_proxy = True
check('... one click on the switch: shown (it took two before)', drawn() == [True], drawn())

coll = bpy.data.collections.get(cpx.COLL)
lc = cpx._layer_coll(C.view_layer, coll)
cd.settings(C).show_proxy = False
lc.hide_viewport = True                                 # (hidden with the Outliner's eye as well)
cd.settings(C).show_proxy = True
check('The switch on also when the Outliner\'s eye had hidden them', drawn() == [True] and not lc.hide_viewport,
      drawn())

cd.settings(C).show_proxy = False
coll.hide_viewport = False                              # (a file saved out of step: switch off, proxies showing)
path = os.path.join(tempfile.mkdtemp(prefix='mch_proxy_'), 'proxy.blend')
bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
bpy.ops.wm.open_mainfile(filepath=path)
C = bpy.context
check('A file opened with the proxies showing but the switch off: hidden as the switch says',
      not cd.settings(C).show_proxy and drawn() == [False], (cd.settings(C).show_proxy, drawn()))
check('Unchanged files untouched: sync with nothing to do changes nothing', cpx.sync(C.scene) is False)

# the drawn panel's button (user's screenshot: Proxy off, Show Proxies on - the button could not be clicked)
from mecha_lab import side_panel as sp, ui_bars  # noqa: E402
st = cd.settings(C)
st.show_proxy = True
st.use_proxy = False
its = sp.content(C, 'CDRAPE', 0.0, 300.0, 1.0)[0]
btn = next((i for i in its if getattr(i, 'prop', '') == 'show_proxy'), None)
check('With Proxy off, the panel\'s Show Proxies button can still be clicked (it was greyed out with Proxy and did '
      'nothing)', btn is not None and btn.clickable() and drawn() == [True], btn and (btn.enabled, drawn()))
ui_bars.run(C, btn)
check('... one click: off, the proxies hidden', not st.show_proxy and drawn() == [False], (st.show_proxy, drawn()))
faces = next((i for i in its if getattr(i, 'prop', '') == 'proxy_faces'), None)
check('... Faces still greyed out with Proxy off (it only matters with Proxy on)', faces is not None
      and not faces.enabled)
summary()
