"""0.24.134 (user: "1억 폴리곤이면?" - their scene GAMERA: 192,197,328 triangles, 270 objects; 64 GB RAM, RTX 5090):
Quick Render counts the triangles that will render (modifiers included, a mesh shared by linked duplicates once - as
Cycles stores it), shows what Cycles needs (about 160 bytes a triangle, measured) against the free RAM, does not start a
render that would not fit without a second click, and CPU Only renders on the processor when a GPU is set."""
import tempfile

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import mech_shader_ui as msu, quick_render as qr  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
st = S.mch_qrender


def load(**kw):
    return qr.scene_load(C, st, depsgraph=C.evaluated_depsgraph_get(), cache=False, **kw)


bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
cube = C.active_object
check('a cube: 12 triangles, 1 mesh, 12 x 160 bytes', load() == (12, 1, 12 * qr.BYTES_PER_TRI), load())
cube.modifiers.new('m', 'MIRROR').use_axis[0] = True
cube.location.x = 2.0
check('... with a Mirror modifier: 24 (the evaluated mesh, as Cycles gets it)', load()[0] == 24, load())
bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, 3, 0))
plane = C.active_object
dup = bpy.data.objects.new('PlaneDup', plane.data)               # a linked duplicate (Alt+D): the same mesh
S.collection.objects.link(dup)
dup.location = (2, 3, 0)
C.view_layer.update()
check('a plane and its linked duplicate share one mesh: counted once (Cycles stores it once): 24 + 2',
      load()[:2] == (26, 2), load())
plane.hide_render = dup.hide_render = True
check('parts hidden from the render are not counted', load()[0] == 24, load())
plane.hide_render = dup.hide_render = False
st.selected_only = True
for o in S.objects:
    o.select_set(False)
cube.select_set(True)
check('Selected Only: only the selected part', load()[0] == 24, load())
st.selected_only = False
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, location=(0, -3, 0))   # 80 triangles
ico = C.active_object
ico.hide_set(True)
C.view_layer.update()
st.hidden_stay_hidden = True
a = load()[0]
st.hidden_stay_hidden = False
b = load()[0]
st.hidden_stay_hidden = True
check('a part hidden in the viewport: not counted with Hidden Stay Hidden, counted without (+80)', a == 26 and b == 106,
      (a, b))
ico.hide_set(False)
check('the user\'s scene (192,197,328 triangles): about 29 GB; a 64 GB PC reads 64 GB; small numbers readable',
      qr._gb(192_197_328 * qr.BYTES_PER_TRI) == '29 GB' and qr._gb(64 * 2 ** 30) == '64 GB' and qr._gb(1800) == '0 MB'
      and qr._gb(3 * 2 ** 29) == '1.5 GB' and qr._count(192_197_328) == '192.2 M' and qr._count(26) == '26'
      and qr._count(42_000) == '42 K', qr._gb(192_197_328 * qr.BYTES_PER_TRI))

total, avail = qr.ram_info()
check('the computer\'s RAM is read (here /proc/meminfo): total and free, free <= total',
      total and avail is not None and 0 < avail <= total and 1e9 < total < 1e13, (total, avail))
lines, big = qr.memory_line(C, st)
check('the panel lines: "Scene: 26 triangles", "Cycles needs ~X - free RAM Y / Z", not marked when it fits',
      lines[0] == 'Scene: 26 triangles' and lines[1].startswith('Cycles needs ~')
      and 'free RAM' in lines[1] and not big and all(len(ln) <= 48 for ln in lines), lines)

# the check before a render (a camera and small settings: a real render when it goes ahead)
bpy.ops.object.camera_add(location=(0, -12, 2), rotation=(1.45, 0, 0))
S.camera = C.active_object
S.render.resolution_x, S.render.resolution_y = 160, 90
st.camera, st.quality, st.folder = 'SCENE', 'DRAFT', tempfile.mkdtemp(prefix='mch_qrm_')
real_ram = qr.ram_info
qr.ram_info = lambda: (64e9, 1000.0)                                # (as if almost no memory were free)
lines, big = qr.memory_line(C, st)
before = (S.render.engine, S.cycles.samples, S.render.resolution_percentage)
qr.CONFIRM['t'] = -1e9
r1 = bpy.ops.mch.quick_render()
after1 = (S.render.engine, S.cycles.samples, S.render.resolution_percentage)
r2 = bpy.ops.mch.quick_render()                                   # the second click: renders anyway
r3 = bpy.ops.mch.quick_render()                                   # and the next one is checked again
check('not enough free memory: the panel line is marked; the first click does not render (nothing changed), a second '
      'click within 15 s renders anyway, the next one is checked again',
      big and 'CANCELLED' in r1 and after1 == before and 'FINISHED' in r2 and 'CANCELLED' in r3, (big, r1, r2, r3))
qr.ram_info = lambda: (64 * 2 ** 30, 20 * 2 ** 30)
qr.CONFIRM['t'] = -1e9
from mecha_lab import toast  # noqa: E402
qr.LOAD['t'] = -1e9
real_load = qr.scene_load
qr.scene_load = lambda *a, **k: (192_197_328, 270, 192_197_328 * qr.BYTES_PER_TRI)
w = qr.memory_check(C, st)
qr.scene_load = real_load
qr.CONFIRM['t'] = -1e9
check('the user\'s scene with 20 GB free: the warning names the need and the free RAM; the toast line is short and keeps '
      '"click again within 15 s to render anyway"', w is not None and '29 GB' in w[0] and '20 GB' in w[0]
      and w[1] == 'needs ~29 GB, 20 GB RAM free - click again within 15 s to render anyway'
      and len('Quick Render: ' + w[1]) <= 100, w)
qr.ram_info = lambda: (64e9, 48e9)
check('it fits (48 GB free): no warning', qr.memory_check(C, st) is None)
qr.ram_info = lambda: (None, None)
check('the RAM cannot be read: nothing is checked (no warning, the line shows no RAM)',
      qr.memory_check(C, st) is None and 'RAM' not in qr.memory_line(C, st)[0][1], qr.memory_line(C, st))
qr.ram_info = real_ram

# CPU Only
real_state = qr.gpu_state
qr.gpu_state = lambda context=None, refresh=False: ('OPTIX', ['NVIDIA GeForce RTX 5090'])
st.cpu_only = False
qr.prepare(C, st)
dev_gpu = S.cycles.device
qr.restore()
st.cpu_only = True
qr.prepare(C, st)
dev_cpu = S.cycles.device
qr.restore()
lines_cpu = qr.status_lines(C)
check('with a GPU set: the render uses it; CPU Only renders on the processor; the device line says so',
      dev_gpu == 'GPU' and dev_cpu == 'CPU' and lines_cpu[0].startswith('CPU (CPU Only on'), (dev_gpu, dev_cpu, lines_cpu))
items, _h = msu.hdri_content(C, 0, 300, 1.0)
labels = [getattr(i, 'label', '') for i in items]
check('the panel (GPU set): CPU Only toggle instead of the Use the GPU button, the two memory lines',
      'CPU Only (scene too big for the GPU)' in labels and 'Use the GPU (Blender Preferences)' not in labels
      and any(lb.startswith('Scene: ') for lb in labels) and any(lb.startswith('Cycles needs ~') for lb in labels),
      labels[:30])
qr.gpu_state = real_state
st.cpu_only = False
summary()
