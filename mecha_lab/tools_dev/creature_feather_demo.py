"""Feather demo (the user's picture: a stroke from the shoulder over the arm and out): Scale (as before - it bends
down with the arm) and Feather Vane / Ridge / Shaft (attached along the start, straight out after, Lift)."""
import math, os, sys
sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/tests')
os.chdir('/home/user/CustomHeadsetOpenVR/mecha_lab/tests')
from _harness import bpy, bmesh, fresh
from mathutils import Matrix, Quaternion, Vector
import mecha_lab
from mecha_lab import core_geometry as cg, lasso_line as ll, creature_plate as cpl
OUT = '/tmp/claude-0/-home-user-CustomHeadsetOpenVR/7e2bc25f-fcd2-5c43-817f-f359a797ad9a/scratchpad/feather'
fresh()
mecha_lab.register()
C = bpy.context
S = C.scene

def creature(x0):
    """A torso and an arm hanging down from its shoulder, one mesh."""
    me = bpy.data.meshes.new('Body'); bm = bmesh.new()
    t = bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=32, radius=1.0)
    bmesh.ops.scale(bm, vec=(0.85, 0.7, 1.5), verts=t['verts'])
    a = bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=0.32, radius2=0.26, depth=2.2)
    bmesh.ops.transform(bm, matrix=Matrix.Translation((1.15, 0, -0.15)) @ Matrix.Rotation(math.radians(-24), 4, 'Y'), verts=a['verts'])
    s = bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=0.42)
    bmesh.ops.translate(bm, vec=(0.82, 0, 0.95), verts=s['verts'])
    bm.to_mesh(me); bm.free(); me.shade_smooth()
    ob = bpy.data.objects.new('Body', me); S.collection.objects.link(ob); ob.location = (x0, 0, 0)
    return ob

FRONT = Quaternion((1, 0, 0), math.radians(90))
br = S.mch_brush
br.line_mode, br.line_width, br.line_caps, br.line_taper = True, 0.42, 'POINT', 0.7
st = S.mch_cplate
made = []
for k, (prof, style, lift) in enumerate((('SCALE', 'VANE', -1.0), ('FEATHER', 'VANE', 0.0), ('FEATHER', 'RIDGE', 0.35),
                                         ('FEATHER', 'SHAFT', 0.35))):
    x0 = k * 4.2
    body = creature(x0)
    P = cg.OrthoProjector(FRONT, center=Vector((x0, 0, 0)))
    def scr(wx, wz):
        q = P.to_screen(Vector((x0 + wx, -3.0, wz)))
        return (q[0], q[1])
    path = [scr(0.45 + 1.95 * i / 39, 1.3 - 2.1 * (i / 39) ** 1.15) for i in range(40)]
    for o in C.selected_objects:
        o.select_set(False)
    body.select_set(True); C.view_layer.objects.active = body
    st.profile, st.feather_style, st.tip_lift, st.attach = prof, style, lift, 0.35
    st.peak, st.end_peak = 0.0, -1.0
    loops = ll.line_loops(C, P, path, br)
    msg = cpl.perform(C, loops, P)
    print(prof, style, msg)
    made.append((C.active_object, body, f'{prof.title()}' + ('' if prof == 'SCALE' else f' {style.title()}') +
                 (f'  Lift {lift:g}' if prof == 'FEATHER' and lift > 0 else '')))
mat = bpy.data.materials.new('M'); mat.use_nodes = True
b_ = mat.node_tree.nodes['Principled BSDF']; b_.inputs['Base Color'].default_value = (0.75, 0.55, 0.3, 1); b_.inputs['Roughness'].default_value = 0.45
mb = bpy.data.materials.new('B'); mb.use_nodes = True
mb.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.55, 0.56, 0.58, 1)
dg = C.evaluated_depsgraph_get()
wmat = bpy.data.materials.new('W'); wmat.use_nodes = True
wmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.01, 0.01, 0.015, 1)
wires = []
for plate, body, label in made:
    plate.data.materials.clear(); plate.data.materials.append(mat)
    body.data.materials.clear(); body.data.materials.append(mb)
    wm_ = bpy.data.meshes.new_from_object(plate.evaluated_get(dg)); wo = bpy.data.objects.new(plate.name + 'W', wm_)
    wo.matrix_world = plate.matrix_world; S.collection.objects.link(wo)
    md = wo.modifiers.new('W', 'WIREFRAME'); md.thickness = 0.004; md.use_replace = True; md.use_even_offset = False
    wm_.materials.clear(); wm_.materials.append(wmat); wires.append(wo)
    cu = bpy.data.curves.new('T', 'FONT'); cu.body = label; cu.size = 0.3; cu.align_x = 'CENTER'
    t = bpy.data.objects.new('T', cu); t.location = (body.location.x + 0.7, -1.2, 2.3); t.rotation_euler = (math.radians(80), 0, 0)
    S.collection.objects.link(t)
    lm = bpy.data.materials.new('L'); lm.use_nodes = True
    lm.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1, 0.8, 0.5, 1)
    lm.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.2
    cu.materials.append(lm)
cam_d = bpy.data.cameras.new('C'); cam_d.lens = 26; cam = bpy.data.objects.new('C', cam_d); S.collection.objects.link(cam); S.camera = cam
cam.location = (11.0, -14.0, 2.2)
cam.rotation_euler = (Vector((7.4, 0, 0.0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
for loc, e, sz in (((2, -8, 8), 3000, 10), ((14, -2, 5), 1500, 6), ((6, 6, 6), 1200, 8)):
    ld = bpy.data.lights.new('L', 'AREA'); ld.energy = e; ld.size = sz
    lo = bpy.data.objects.new('L', ld); lo.location = loc; S.collection.objects.link(lo)
    lo.rotation_euler = (Vector((7, 0, 0)) - lo.location).to_track_quat('-Z', 'Y').to_euler()
w = bpy.data.worlds.new('W'); S.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.05, 0.055, 1)
S.render.engine = 'CYCLES'; S.cycles.samples = 48; S.cycles.device = 'CPU'
S.render.resolution_x, S.render.resolution_y = 2000, 800
for name, wire in (('feather_shaded', False), ('feather_wire', True)):
    for wo in wires:
        wo.hide_render = not wire
    S.render.filepath = os.path.join(OUT, name + '.png'); bpy.ops.render.render(write_still=True)
cam_d.lens = 26
cam.location = (7.6, -1.5, 16.5)
cam.rotation_euler = (Vector((7.4, 0.3, 0.0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
for wo in wires:
    wo.hide_render = True
S.render.filepath = os.path.join(OUT, 'feather_side.png')
bpy.ops.render.render(write_still=True)
# close-ups of the free part: Vane / Ridge / Shaft, looking along the feather from its tip side, low
for k, (plate, body, label) in enumerate(made[1:]):
    vs = [plate.matrix_world @ v.co for v in plate.data.vertices]
    tip = max(vs, key=lambda v: v.x)
    root = min(vs, key=lambda v: v.x)
    mid = root.lerp(tip, 0.7)
    d = (tip - root).normalized()
    cam_d.type = 'PERSP'; cam_d.lens = 60
    nrm = sum((plate.matrix_world.to_3x3() @ f.normal for f in plate.data.polygons
               if (plate.matrix_world @ f.center - mid).length < 0.4 and (plate.matrix_world.to_3x3() @ f.normal).z > -0.2), Vector())
    nrm = nrm.normalized() if nrm.length > 1e-6 else Vector((0, -0.5, 0.8)).normalized()
    cam.location = mid + nrm * 1.6 + d * 0.9 + Vector((0, 0, 0.3))      # above the free part's top side, a little
    #                                                                     toward the tip: the crest across the view
    cam.rotation_euler = (mid - cam.location).to_track_quat('-Z', 'Y').to_euler()
    for o in S.objects:
        if o.type == 'FONT':
            o.hide_render = True
    S.render.resolution_x, S.render.resolution_y = 660, 500
    S.render.filepath = os.path.join(OUT, f'close_{k}.png')
    bpy.ops.render.render(write_still=True)
print('DONE')
