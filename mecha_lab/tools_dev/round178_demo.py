"""0.24.178 demo, Cycles, shaded and wireframe:
  boolbevel - Boolean Bevel (user: "불린 베벨 만들자 ... 원하는 만큼 그리면 그 부분이 베벨 불린, 챔퍼랑", "기존 메쉬 엣지들에
              살짝 붙으면서 그리면 좋을 듯"): a block - a chamfer drawn along part of its top edge and on round the corner
              down its side, a whole edge rounded (a click); a cylinder - half its rim chamfered
  chamfer   - Geo Sculpt Chamfer / Round by picking edges (user: "선택할 수 있는 엣지들을 보여 주는 게"; "처음엔 돼도 같은
              메쉬 다른 곳에 한 번 더 그으면 이렇게 돼"): a panel with holes - its top edge chamfered, then an edge between
              two holes and a hole's rim rounded: the first chamfer stays as it was

    <blender python> round178_demo.py <out dir>
"""
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Euler, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'addon'))
import mecha_lab  # noqa: E402

OUT = sys.argv[-1]
ONLY = set(os.environ.get('ONLY', 'boolbevel,chamfer').split(','))
os.makedirs(OUT, exist_ok=True)
mecha_lab.register()
from mecha_lab import core_geometry as cg, creature_light as cl, creature_spike as cs  # noqa: E402
from mecha_lab import bool_bevel as bb, edge_runs as er, geo_sculpt as gs  # noqa: E402

C = bpy.context
S = C.scene
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)   # (looking +Y)


def px(x, z):
    return tuple(FRONT.to_screen(Vector((x, -6.0, z))))


def mat(name, rgb, rough=0.4, metal=0.0):
    m = bpy.data.materials.new(name)
    pb = m.node_tree.nodes['Principled BSDF']
    pb.inputs['Base Color'].default_value = (*rgb, 1)
    pb.inputs['Roughness'].default_value = rough
    pb.inputs['Metallic'].default_value = metal
    return m


def unselect():
    for o in C.selected_objects:
        o.select_set(False)
    C.view_layer.objects.active = None


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


def stage(cam_loc, look, lens=40):
    S.world = bpy.data.worlds.new('W')
    cl.apply(S, 'soft_studio')
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    S.collection.objects.link(sun)
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(40), 0.0, math.radians(-30))
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    S.collection.objects.link(cam)
    S.camera = cam
    cam.location = cam_loc
    cam.rotation_euler = (Vector(look) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


S.render.engine = 'CYCLES'
S.cycles.samples = 40
S.cycles.use_denoising = True
S.cycles.device = 'CPU'
S.render.resolution_x, S.render.resolution_y = 1200, 900
WIRE = mat('Wire', (1.0, 0.45, 0.05))
WIRE.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1.0, 0.45, 0.05, 1)
WIRE.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.5


def shoot(tag, thick=0.0012):
    for wire in (False, True):
        made = []
        if wire:
            dg = C.evaluated_depsgraph_get()
            for src in [o for o in S.objects if o.type == 'MESH' and o.visible_get() and not o.name.endswith(' wire')]:
                me = bpy.data.meshes.new_from_object(src.evaluated_get(dg), depsgraph=dg)
                wo = bpy.data.objects.new(src.name + ' wire', me)
                S.collection.objects.link(wo)
                wo.matrix_world = src.matrix_world
                md = wo.modifiers.new('W', 'WIREFRAME')
                md.use_replace = True
                md.thickness = thick
                me.materials.clear()
                me.materials.append(WIRE)
                made.append(wo)
        S.render.filepath = os.path.join(OUT, f'{tag}_{"wire" if wire else "shaded"}.png')
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print('saved', S.render.filepath, f'{time.time() - t0:.0f} s', flush=True)
        for wo in made:
            me = wo.data
            bpy.data.objects.remove(wo)
            bpy.data.meshes.remove(me)



def scene_boolbevel():
    clear()
    bpy.ops.mesh.primitive_cube_add(size=1.6, location=(0.0, 0.0, 0.0))
    blk = C.active_object
    blk.name = 'Block'
    blk.data.materials.append(mat('Block', (0.32, 0.35, 0.38), 0.4, 0.6))
    st = S.mch_bool_bevel
    st.profile, st.width = 'CHAMFER', 0.16
    path = [(x, -0.8, 0.8) for x in np.linspace(-0.3, 0.78, 14)] + [(0.8, -0.8, z) for z in np.linspace(0.75, -0.2, 10)]
    print(bb.perform(C, blk, path, reach=0.1))
    st.profile, st.segments = 'ROUND', 12
    print(bb.perform(C, blk, [(-0.8, 0.0, 0.8)], whole=True))
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.7, depth=1.0, location=(2.4, 0.4, -0.3))
    cy = C.active_object
    cy.data.materials.append(mat('Cyl', (0.3, 0.33, 0.36), 0.4, 0.6))
    st.profile, st.width = 'CHAMFER', 0.12
    half = [(2.4 + 0.7 * math.cos(a), 0.4 + 0.7 * math.sin(a), 0.2) for a in np.linspace(math.pi + 0.15, 2 * math.pi - 0.15, 30)]
    print(bb.perform(C, cy, [cy.matrix_world.inverted() @ Vector(p) for p in half], reach=0.1))
    # a plate with a square hole: its four rims clicked one by one (Chamfer) - they meet mitred at the corners
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-2.4, 0.3, 0.0))
    pl = C.active_object
    pl.scale = (1.4, 0.2, 1.4)
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-2.4, 0.3, 0.0))
    hole = C.active_object
    hole.scale = (0.6, 1.0, 0.6)
    m = pl.modifiers.new('B', 'BOOLEAN')
    m.object, m.solver = hole, 'EXACT'
    C.view_layer.objects.active = pl
    bpy.ops.object.modifier_apply(modifier='B')
    bpy.data.objects.remove(hole)
    pl.data.materials.append(mat('Plate', (0.3, 0.33, 0.36), 0.4, 0.6))
    st.profile, st.width = 'CHAMFER', 0.1
    for qx, qz in ((0.0, 0.3), (0.0, -0.3), (-0.3, 0.0), (0.3, 0.0)):     # (its mesh is in world space: applied)
        q = pl.matrix_world.inverted() @ Vector((-2.4 + qx, 0.2, qz))
        print(bb.perform(C, pl, [tuple(q)], whole=True, reach=0.05))
    stage((0.2, -6.4, 3.2), (-0.2, 0.0, 0.0), lens=36)
    shoot('bool_bevel', thick=0.0015)


def scene_chamfer():
    clear()
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    panel = C.active_object
    panel.name = 'Panel'
    panel.scale = (2.0, 0.16, 1.4)
    bpy.ops.object.transform_apply(scale=True)
    for (x, z, ww, hh) in ((0.5, 0.25, 0.2, 0.3), (0.5, -0.15, 0.2, 0.3), (0.76, 0.05, 0.08, 0.6), (-0.5, -0.1, 0.5, 0.5)):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, 0, z))
        cut = C.active_object
        cut.scale = (ww, 0.6, hh)
        m = panel.modifiers.new('B', 'BOOLEAN')
        m.object, m.operation, m.solver = cut, 'DIFFERENCE', 'EXACT'
        C.view_layer.objects.active = panel
        bpy.ops.object.modifier_apply(modifier='B')
        bpy.data.objects.remove(cut)
    panel.data.materials.append(mat('Panel', (0.32, 0.35, 0.38), 0.4, 0.6))
    for kind, p, w in (('CHAMFER', (-0.2, -0.08, 0.7), 0.1), ('ROUND', (0.71, -0.08, 0.05), 0.05),
                       ('ROUND', (-0.5, -0.08, 0.15), 0.05), ('CHAMFER', (-0.75, -0.08, -0.1), 0.04)):
        got = gs.pick_run(panel, p, 0.05)
        print(kind, 'run', got and got[0], gs.mark_edges(panel, kind, got[1], w) if got else 0)
    panel.data.materials.clear()
    panel.data.materials.append(mat('Panel', (0.12, 0.14, 0.16), 0.35, 0.8))
    stage((0.9, -2.6, 1.5), (0.0, 0.0, 0.15), lens=42)
    shoot('geo_chamfer_pick', thick=0.003)


for _nm in ('boolbevel', 'chamfer'):
    if _nm in ONLY:
        globals()['scene_' + _nm]()
print('done')
