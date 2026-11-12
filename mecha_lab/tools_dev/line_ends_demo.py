"""Line ends demo: wavy lines drawn (top view) over a gently curved body with Armor Plate (Round / Pointed), Creature
Plate (Pointed), Plate Detail 3 (Pointed) and Surface Draw (Square / Round / Pointed).  Shaded + wireframe."""
import math, os, sys
sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/tests')
os.chdir('/home/user/CustomHeadsetOpenVR/mecha_lab/tests')
from _harness import bpy, fresh
from mathutils import Quaternion, Vector
import mecha_lab
from mecha_lab import core_geometry as cg, lasso_line as ll, armor_plate as ap, creature_plate as cpl, plate_detail as pdm
from mecha_lab import surface_draw as sd
OUT = '/tmp/claude-0/-home-user-CustomHeadsetOpenVR/7e2bc25f-fcd2-5c43-817f-f359a797ad9a/scratchpad/taper'
fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
P = cg.OrthoProjector(Quaternion())
bpy.ops.mesh.primitive_uv_sphere_add(radius=9.0, segments=128, ring_count=64, location=(0, 0, -8.4))
body = C.active_object
bpy.ops.object.shade_smooth()
br = S.mch_brush
br.line_mode = True
br.line_width = 0.32
def wave(y, x0=-3.6, x1=-0.4, amp=12, n=40):
    return [(500 + (x0 + (x1 - x0) * i / (n - 1)) * 100, 500 + y * 100 + amp * math.sin(i / (n - 1) * math.pi * 2)) for i in range(n)]
def sel(o):
    for x in C.selected_objects:
        x.select_set(False)
    o.select_set(True); C.view_layer.objects.active = o
made = []
# left column: the plate tools
for y, tool, cap in ((3.0, 'PLATE', 'ROUND'), (1.8, 'PLATE', 'POINT'), (0.6, 'CPLATE', 'POINT'), (-0.6, 'DETAIL3', 'POINT')):
    br.line_caps = cap
    br.line_taper = 0.6
    sel(body)
    loops = ll.line_loops(C, P, wave(y), br)
    if tool == 'PLATE':
        ap.perform_plate(C, loops, P)
    elif tool == 'CPLATE':
        cpl.perform(C, loops, P)
    else:
        pdm.perform(C, loops, P, tool='DETAIL3')
    made.append((tool, cap, C.active_object.name))
    print(tool, cap, 'loop points', len(loops[0]) if loops else 0, '->', C.active_object.name)
# right column: Surface Draw, three kinds of ends
st = S.mch_sdraw
st.join = False
for y, ends in ((3.0, 'SQUARE'), (1.8, 'ROUND'), (0.6, 'POINT')):
    st.ends = ends
    st.taper = 0.6
    st.profile = 'BEVEL'
    st.width = 0.32
    st.height = 0.1
    sel(body)
    sd.perform(C, wave(y, 0.4, 3.6), P)
    ob = C.active_object
    print('SDRAW', ends, '->', ob.name, len(ob.data.polygons))
    made.append(('SDRAW', ends, ob.name))
# render
mat = bpy.data.materials.new('M'); mat.use_nodes = True
b_ = mat.node_tree.nodes['Principled BSDF']; b_.inputs['Base Color'].default_value = (0.42, 0.43, 0.46, 1); b_.inputs['Roughness'].default_value = 0.4
bm_ = bpy.data.materials.new('Body'); bm_.use_nodes = True
bm_.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.18, 0.19, 0.21, 1)
body.data.materials.clear(); body.data.materials.append(bm_)
dg = C.evaluated_depsgraph_get()
wmat = bpy.data.materials.new('W'); wmat.use_nodes = True
wmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.01, 0.01, 0.015, 1)
wires = []
for _t, _c, name in made:
    o = bpy.data.objects[name]
    o.data.materials.clear(); o.data.materials.append(mat)
    wm_ = bpy.data.meshes.new_from_object(o.evaluated_get(dg)); wo = bpy.data.objects.new(name + 'W', wm_)
    wo.matrix_world = o.matrix_world; S.collection.objects.link(wo)
    md = wo.modifiers.new('W', 'WIREFRAME'); md.thickness = 0.004; md.use_replace = True; md.use_even_offset = False
    wm_.materials.clear(); wm_.materials.append(wmat); wires.append(wo)
for (tool, cap, name), (x, y) in zip(made, [(-2.0, 3.0), (-2.0, 1.8), (-2.0, 0.6), (-2.0, -0.6), (2.0, 3.0), (2.0, 1.8), (2.0, 0.6)]):
    label = {'PLATE': 'Armor Plate', 'CPLATE': 'Creature Plate', 'DETAIL3': 'Plate Detail 3', 'SDRAW': 'Surface Draw'}[tool]
    cu = bpy.data.curves.new('T', 'FONT'); cu.body = f'{label} - {cap.title()}'; cu.size = 0.2; cu.align_x = 'CENTER'
    t = bpy.data.objects.new('T', cu); t.location = (x, y + 0.3, 0.75); S.collection.objects.link(t)
    lm = bpy.data.materials.new('L'); lm.use_nodes = True
    lm.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1, 0.75, 0.4, 1)
    lm.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.2
    cu.materials.append(lm)
cam_d = bpy.data.cameras.new('C'); cam_d.type = 'ORTHO'; cam_d.ortho_scale = 8.6
cam = bpy.data.objects.new('C', cam_d); S.collection.objects.link(cam); S.camera = cam
cam.location = (0, 1.25, 9.0); cam.rotation_euler = (0, 0, 0)
for loc, e, sz in (((-4, -4, 8), 2500, 8), ((5, 2, 6), 1200, 6)):
    ld = bpy.data.lights.new('L', 'AREA'); ld.energy = e; ld.size = sz
    lo = bpy.data.objects.new('L', ld); lo.location = loc; S.collection.objects.link(lo)
    lo.rotation_euler = (Vector((0, 1, 0)) - lo.location).to_track_quat('-Z', 'Y').to_euler()
w = bpy.data.worlds.new('W'); S.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.05, 0.055, 1)
S.render.engine = 'CYCLES'; S.cycles.samples = 48; S.cycles.device = 'CPU'
S.render.resolution_x, S.render.resolution_y = 1800, 1050
for name, wire in (('ends_shaded', False), ('ends_wire', True)):
    for wo in wires:
        wo.hide_render = not wire
    S.render.filepath = os.path.join(OUT, name + '.png'); bpy.ops.render.render(write_still=True)
print('DONE')
