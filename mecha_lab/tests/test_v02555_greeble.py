"""0.24.150 (user: "표면에 기계 파츠가 다다닥 붙어 있는 이미지 ... 내가 표면에 그으면 저렇게 메쉬들이 다다다닥 이어지게 ... 내가
그은 선 따라서, 메쉬는 내가 픽킹할 수 있게 픽킹 옵션을 오른쪽 패널에"): Greeble Line - the picked meshes laid end to end
along a line drawn on a part, each standing on the surface.  The line here is a quarter of a sphere's equator given as
points (a real mouse drag: tests/gui/greeble_real_window.py)."""
import math
import os
import tempfile
import time

import numpy as np
from _harness import bpy, check, fresh, summary
import bmesh  # noqa: E402
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import greeble_line as gl, tool_state as ts, ui_tool_settings as uts  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
st = gl.settings(S)
check('the tool: Greeble Line in the tool list (Surface detail), its icon, its window in the right panel',
      'GREEBLE' in ts.TOOL_BY_ID and 'GREEBLE' in dict(ts.TOOL_GROUPS)['Surface detail']
      and os.path.isfile(os.path.join(os.path.dirname(gl.__file__), 'icons', 'greeble.png'))
      and uts.DRAWERS.get('GREEBLE') is not None and hasattr(bpy.types, 'MCH_OT_greeble_pick'))

for o in list(S.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=48)
body = C.active_object
bpy.ops.object.shade_smooth()


def box(name, sx, sy, sz, loc):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= sx
        v.co.y *= sy
        v.co.z = (v.co.z + 0.5) * sz
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    S.collection.objects.link(ob)
    ob.location = loc
    return ob


A = box('PartA', 0.2, 0.1, 0.05, (3, 0, 0))            # long side X
B = box('PartB', 0.1, 0.2, 0.08, (3, 1, 0))            # long side Y
mat = bpy.data.materials.new('Brass')
A.data.materials.append(mat)
for o in S.objects:
    o.select_set(o in (A, B))
r = bpy.ops.mch.greeble_parts(action='ADD_SELECTED')
check('Add Selected: both meshes in the parts list', 'FINISHED' in r and [it.ob for it in st.parts] == [A, B])
r = bpy.ops.mch.greeble_parts(action='ADD_SELECTED')
check('... not twice', len(st.parts) == 2)

ang = np.linspace(0.0, math.pi / 2, 200)
pts = np.stack([np.cos(ang), np.sin(ang), np.zeros_like(ang)], 1)        # a quarter of the equator
line = gl.new_line(C, body, pts, pts, gl.picked(st), st)
n = gl.rebuild(line, C)
ln = line.mch_greeble_line
me = line.data
picks = [d.value for d in me.attributes['mch_pick'].data]
check('a line a quarter of the equator long (1.571): 8 parts of 0.2 end to end, in turn A B A B ...',
      n == 8 and picks == [0, 1] * 4, (n, picks))


def placed(line):
    me = line.data
    loc = np.array([tuple(v.co) for v in me.vertices])
    q = [Quaternion(d.value) for d in me.attributes['mch_rot'].data]
    sc = [Vector(d.vector) for d in me.attributes['mch_scale'].data]
    pk = [d.value for d in me.attributes['mch_pick'].data]
    return loc, q, sc, pk


def bottoms(line, parts):
    """Each part's bottom middle and its up / length axes, in the body's space."""
    loc, q, sc, pk = placed(line)
    out = []
    for i in range(len(loc)):
        p = parts[pk[i]]
        bb = [Vector(c) for c in p.bound_box]
        mid = Vector(((min(v.x for v in bb) + max(v.x for v in bb)) / 2, (min(v.y for v in bb) + max(v.y for v in bb)) / 2,
                      min(v.z for v in bb)))
        m = q[i].to_matrix()
        world = Vector(loc[i]) + m @ Vector((mid.x * sc[i].x, mid.y * sc[i].y, mid.z * sc[i].z))
        ax = Vector((1, 0, 0)) if p == A else Vector((0, 1, 0))
        out.append((world, m @ Vector((0, 0, 1)), m @ ax))
    return out


bt = bottoms(line, [A, B])
on = max(abs(b[0].length - 1.0) for b in bt)
up = min(b[1].dot(b[0].normalized()) for b in bt)
along = min(abs(b[2].dot(Vector((-b[0].y, b[0].x, 0)).normalized())) for b in bt)
gaps = [(bt[i + 1][0] - bt[i][0]).length for i in range(len(bt) - 1)]
check('each part standing on the surface: its bottom middle on it (within 0.005), up = the surface normal',
      on < 0.005 and up > 0.995, (round(on, 4), round(up, 4)))
check('... its long side along the line (A by its X, B by its Y: Axis Auto)', along > 0.99, round(along, 4))
check('... end to end: the middles 0.2 apart (one part\'s length)', max(abs(g - 0.2) for g in gaps) < 0.005,
      [round(g, 4) for g in gaps])
dg = C.evaluated_depsgraph_get()
inst = [i for i in dg.object_instances if i.is_instance and i.parent and i.parent.original == line]
check('the parts are instances of the picked meshes (light until Apply): 8 of them', len(inst) == 8, len(inst))

# a line's own settings: changed live, they go on to the next line
for o in S.objects:
    o.select_set(False)
line.select_set(True)
C.view_layer.objects.active = line
ln.gap = 0.5
n2 = len(line.data.vertices)
check('Gap 0.5 on the line: fewer parts (every 0.3: 5 on 1.571), redone live; the next line will have Gap 0.5 too',
      n2 == 5 and abs(st.gap - 0.5) < 1e-6, (n2, st.gap))
ln.gap = 0.0
ln.rows = 3
bt3 = bottoms(line, [A, B])
check('Rows 3: three rows side by side, all on the surface', len(bt3) == 24 and max(abs(b[0].length - 1.0)
                                                                                  for b in bt3) < 0.01, len(bt3))
ln.rows = 1
ln.sink = 0.5
bts = bottoms(line, [A, B])
want = [1.0 - 0.5 * (0.05 if i % 2 == 0 else 0.08) for i in range(len(bts))]
check('Sink 0.5: each part half its height into the surface', max(abs(b[0].length - w) for b, w in zip(bts, want)) < 0.005)
ln.sink = 0.0
ln.order = 'RANDOM'
ln.seed = 3
ln.scale_random = 0.4
ln.flip_random = True
_l, qs, scs, pks = placed(line)
yaws = [abs((q.to_matrix() @ Vector((1, 0, 0))).dot(Vector((-b[0].y, b[0].x, 0)).normalized()))
        for q, b in zip(qs, bottoms(line, [A, B]))]
check('Random / Size Random / Flip Random: both parts, sizes vary, some turned round',
      set(pks) == {0, 1} and np.ptp([s.x for s in scs]) > 0.01 and len(qs) > 3)
ln.order, ln.scale_random, ln.flip_random, ln.seed = 'SEQ', 0.0, False, 0
ln.scale = 0.5
check('Part Size 0.5: twice as many (16)', len(line.data.vertices) == 16, len(line.data.vertices))
ln.scale = 1.0

t0 = time.time()
ln.scale = 0.05
dt = time.time() - t0
check(f'a dense line (Part Size 0.05: 157 parts) redone in {dt:.2f} s', len(line.data.vertices) == 157 and dt < 1.0,
      len(line.data.vertices))
ln.scale = 1.0

# it moves with the part
body.location = (0.0, 0.0, 2.0)
C.view_layer.update()
check('the line is on the part (its child): moved with it', line.parent is body
      and (line.matrix_world.translation - Vector((0, 0, 2))).length < 1e-6)
body.location = (0.0, 0.0, 0.0)
C.view_layer.update()

# Use Picked Parts: the selected line takes the ticked parts
st.parts[0].use = False
r = bpy.ops.mch.greeble_parts(action='USE_PICKED')
pk = [d.value for d in line.data.attributes['mch_pick'].data]
check('Use Picked Parts (A unticked): the line only B now', 'FINISHED' in r and set(pk) == {0}
      and gl.line_parts(line) == [B] and line.modifiers['MCH Greeble'].node_group.get(gl.SIG_KEY) == 'PartB')
st.parts[0].use = True
bpy.ops.mch.greeble_parts(action='USE_PICKED')

# the picked meshes hidden: still in the line, in a render too
st.hide_parts = True
check('Hide Parts: the picked meshes hidden in the viewport and the render', A.hide_get() and A.hide_render
      and B.hide_get() and B.hide_render)
dg = C.evaluated_depsgraph_get()
inst = [i for i in dg.object_instances if i.is_instance and i.parent and i.parent.original == line]
check('... the line still shows them', len(inst) == 8)
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
S.collection.objects.link(cam)
S.camera = cam
cam.location = (2.6, 2.6, 0.6)
cam.rotation_euler = (Vector((0.7, 0.7, 0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
S.world = bpy.data.worlds.new('W')
S.render.engine = 'CYCLES'
S.cycles.samples = 2
S.cycles.device = 'CPU'
S.render.resolution_x, S.render.resolution_y = 64, 48
S.render.image_settings.file_format = 'OPEN_EXR'
TMP = tempfile.mkdtemp(prefix='mch_greeble_')


def render(name):
    S.render.filepath = os.path.join(TMP, name + '.exr')
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(S.render.filepath)
    a = np.array(img.pixels[:], np.float32).reshape(48, 64, 4)
    bpy.data.images.remove(img)
    return a


with_line = render('with')
line.hide_render = True
without = render('without')
line.hide_render = False
check('a Cycles render: the parts there (the picked meshes hidden from the render, the line\'s parts not)',
      float(np.abs(with_line[..., :3] - without[..., :3]).max()) > 0.01
      and int(np.sum(np.abs(with_line[..., :3] - without[..., :3]).max(2) > 0.005)) > 10,
      (round(float(np.abs(with_line[..., :3] - without[..., :3]).max()), 4),
       int(np.sum(np.abs(with_line[..., :3] - without[..., :3]).max(2) > 0.005))))
st.hide_parts = False
check('Hide Parts off: the picked meshes back', not A.hide_get() and not A.hide_render)

# Apply
r = bpy.ops.mch.greeble_apply()
check('Apply: one real mesh with the parts (8 boxes = 64 vertices, the Brass material), no longer live',
      'FINISHED' in r and not gl.is_line(line) and line.modifiers.get('MCH Greeble') is None
      and len(line.data.vertices) == 64 and 'Brass' in [m.name for m in line.data.materials if m]
      and line.parent is body, (len(line.data.vertices), [m.name for m in line.data.materials if m]))

# Starter Parts
C.view_layer.objects.active = body
r = bpy.ops.mch.greeble_parts(action='STARTER')
starters = [o for o in S.objects if o.get(gl.STARTER_TAG)]
check('Starter Parts: five simple machine parts made beside the model (sized to it), in the list',
      'FINISHED' in r and len(starters) == 5 and all(o in [it.ob for it in st.parts] for o in starters)
      and all(o.location.x > 1.0 for o in starters) and 0.05 < starters[0].scale.x < 0.2
      and gl.STARTER_COLL in bpy.data.collections, [round(o.scale.x, 3) for o in starters])
line2 = gl.new_line(C, body, pts, pts, starters, st)
n3 = gl.rebuild(line2, C)
check('... a line of starter parts', n3 > 5, n3)
summary()
