"""0.24.274 (user: "바닥에 러프니스랑 스페큘러도 조정하게 해 줘"): Fade Floor's Roughness and Specular - into its material,
shown on the Floor section; a real Cycles render: a glossy floor reflects the part, a matte one does not."""
import math
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import creature_light as cl, side_panel as sp  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
for o in list(S.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(0, 0, 0.5)); ball = C.active_object
mat = bpy.data.materials.new('Red'); mat.use_nodes = True
mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (1, 0, 0, 1)
mat.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1, 0, 0, 1)
mat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 5.0
ball.data.materials.append(mat)
st = cl.settings(S)
bpy.ops.mch.creature_floor(kind='FADE')
st.floor_color = (0.05, 0.05, 0.05)
fl = cl.floor_object(S)
pb = fl.active_material.node_tree.nodes['MCH Floor']
check('defaults as before: Roughness 0.8, Specular 0.2', abs(pb.inputs['Roughness'].default_value - 0.8) < 1e-6
      and abs(pb.inputs['Specular IOR Level'].default_value - 0.2) < 1e-6)
st.floor_roughness, st.floor_specular = 0.05, 1.0
check('set: into the floor material', abs(pb.inputs['Roughness'].default_value - 0.05) < 1e-6
      and abs(pb.inputs['Specular IOR Level'].default_value - 1.0) < 1e-6)
C.window_manager.mch_side_page = 'HDRI'
sp.FOLDED.discard('MATERIAL:floor')
items, _h = sp.content(C, 'CUT', 0, 300, 1.0)
L = [getattr(i, 'label', '') for i in items]
check('the Floor section shows Roughness and Specular', 'Roughness' in L and 'Specular' in L)
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); S.collection.objects.link(cam)
cam.location = (0, -4, 0.6); cam.rotation_euler = (math.radians(95), 0, 0); S.camera = cam
S.render.engine = 'CYCLES'; S.cycles.samples = 32; S.cycles.device = 'CPU'
S.render.resolution_x = S.render.resolution_y = 256


def red_below():
    f = os.path.join(tempfile.gettempdir(), 'mch_floor.png'); S.render.filepath = f
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(f); a = np.array(im.pixels[:]).reshape(256, 256, 4); bpy.data.images.remove(im)
    low = a[26:40, 105:150, :3]                    # (where the floor mirrors the ball: just under it)
    return float((low[..., 0] * a[26:40, 105:150, 3]).mean())


glossy = red_below()
st.floor_roughness, st.floor_specular = 1.0, 0.0
matte = red_below()
check(f'real render: the glossy floor mirrors the ball ({glossy:.3f}), the matte one does not ({matte:.3f})',
      glossy > matte * 2.0)
summary()
