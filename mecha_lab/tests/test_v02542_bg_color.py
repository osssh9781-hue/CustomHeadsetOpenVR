"""0.24.137 (user: "HDRI 는 다른 애드온 쓸 거라 배경만 내가 원하는 색으로 바꿀 수 있게 해 주라, 너가 만든 게 너무 무거워")
Background Colour on any world (another add-on's HDRI): the camera sees the colour, the world still lights the parts;
off puts the world back as it was; the HDRI tab is now Render (Quick Render, Viewport, Background) - no HDRI library."""
import os
import tempfile

import numpy as np

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bg_color as bgc, mech_shader_ui as msu, side_panel as sp  # noqa: E402

fresh()
mecha_lab.register()
bpy.context.scene.mch_bg.method = 'WORLD'      # (0.24.148: Compositor is the default now; this file is the World way)
C = bpy.context
S = C.scene
st = S.mch_bg

# "another add-on's HDRI world": a world whose shader is a strong red Background
w = bpy.data.worlds.new('OtherAddonHDRI')
w.use_nodes = True
nt = w.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
red = nt.nodes.new('ShaderNodeBackground')
red.name = 'HDRI Background'
red.inputs['Color'].default_value = (1.0, 0.0, 0.0, 1.0)
red.inputs['Strength'].default_value = 1.5
out = nt.nodes.new('ShaderNodeOutputWorld')
nt.links.new(red.outputs['Background'], out.inputs['Surface'])
S.world = w
st.color = (0.0, 0.0, 1.0)
msg = bgc.apply(S)
mix = nt.nodes.get(bgc.N_MIX)
check('on: Light Path (Is Camera Ray) mixes the world\'s own shader with a Background of the colour, into the output',
      bgc.on(S) and mix is not None and mix.inputs['Fac'].links[0].from_socket.name == 'Is Camera Ray'
      and mix.inputs[1].links[0].from_node == red and mix.inputs[2].links[0].from_node.name == bgc.N_BG
      and tuple(nt.nodes[bgc.N_BG].inputs['Color'].default_value)[:3] == (0.0, 0.0, 1.0), msg)

# a real render: the camera sees blue, the sphere is lit by the red world
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0)
bpy.ops.object.shade_smooth()
bpy.ops.object.camera_add(location=(0, -6, 0), rotation=(1.5708, 0, 0))
S.camera = C.active_object
S.render.engine = 'CYCLES'
S.cycles.samples = 8
S.cycles.device = 'CPU'
S.render.resolution_x = S.render.resolution_y = 64
S.render.filepath = os.path.join(tempfile.mkdtemp(prefix='mch_bg_'), 'bg.png')
bpy.ops.render.render(write_still=True)
img = bpy.data.images.load(S.render.filepath)
px = np.empty(64 * 64 * 4, np.float32)
img.pixels.foreach_get(px)
px = px.reshape(64, 64, 4)
corner, centre = px[2, 2, :3], px[32, 32, :3]
check('a Cycles render: the background is the colour (blue), the sphere is lit by the world (red) - not by the colour',
      corner[2] > 0.8 and corner[0] < 0.1 and centre[0] > centre[2] and centre[0] > 0.2,
      (corner.round(2).tolist(), centre.round(2).tolist()))

st.color = (0.2, 0.6, 0.1)
check('changing the colour changes the node', tuple(round(v, 3) for v in nt.nodes[bgc.N_BG].inputs['Color'].default_value)[:3]
      == (0.2, 0.6, 0.1))
# Solid view too
views = bgc._views()
sp3 = views[0][2]
old_view = (sp3.shading.background_type, tuple(sp3.shading.background_color))
st.solid_too = True
mid = (sp3.shading.background_type, tuple(round(v, 3) for v in sp3.shading.background_color))
st.solid_too = False
check('Solid View Too: the 3D view\'s own background = the colour; off: its own setting back',
      mid == ('VIEWPORT', (0.2, 0.6, 0.1)) and (sp3.shading.background_type, tuple(sp3.shading.background_color)) == old_view,
      (old_view, mid))
# off: the world as it was
msg = bgc.remove(S)
check('off: the three nodes gone, the world\'s own shader on its output again (nothing else touched)',
      not bgc.on(S) and all(nt.nodes.get(n) is None for n in (bgc.N_PATH, bgc.N_BG, bgc.N_MIX))
      and out.inputs['Surface'].links[0].from_node == red and len(nt.nodes) == 2
      and tuple(red.inputs['Color'].default_value) == (1.0, 0.0, 0.0, 1.0), msg)
# another add-on rebuilding its world drops the link: reads Off; the button applies again
bgc.apply(S)
nt.links.remove(out.inputs['Surface'].links[0])
nt.links.new(red.outputs['Background'], out.inputs['Surface'])
dropped = bgc.on(S)
r = bpy.ops.mch.bg_color()
check('a world rebuilt by its add-on (our mix bypassed): Background Colour reads Off; the button puts it back',
      not dropped and 'FINISHED' in r and bgc.on(S))
r = bpy.ops.mch.bg_color()
check('the button again: off', 'FINISHED' in r and not bgc.on(S))
# no world at all: one made
S.world = None
bgc.apply(S)
check('no world: one is made, with the colour', S.world is not None and bgc.on(S))
bgc.remove(S)
# the page
items, _h = msu.hdri_content(C, 0, 300, 1.0)
labels = [getattr(i, 'label', '') for i in items]
check('the tab is now Render: Quick Render, Viewport and Background sections; no HDRI library (list, previews, folders)',
      sp.PAGES['HDRI'][0] == 'Render' and any(lb.startswith('QUICK RENDER') for lb in labels)
      and any(lb.startswith('VIEWPORT') for lb in labels) and any(lb.startswith('BACKGROUND') for lb in labels)
      and {'Background Colour', 'Colour', 'Solid View Too'} <= set(labels)
      and not {'Set HDRI', 'My HDRIs', 'Remove All'} & set(labels), [lb for lb in labels if lb][:40])   # (0.24.138 Picture: the backdrops back)


# the N sidebar's Mech Shader panel: the same Background box, no HDRI list (a recording stand-in for the layout)
class _Rec:
    def __init__(self, log):
        self.log = log

    def box(self):
        return self

    def row(self, **_kw):
        return self

    def column(self, **_kw):
        return self

    def label(self, text='', **_kw):
        self.log.append(('label', text))

    def prop(self, data, name, text=None, **_kw):
        self.log.append(('prop', name))

    def operator(self, idname, text='', **_kw):
        self.log.append(('op', idname, text))
        return type('OpProps', (), {})()

    def template_color_ramp(self, data, prop, **_kw):
        self.log.append(('ramp', prop))

    def template_icon(self, icon_value=0, **_kw):
        self.log.append(('icon', icon_value))


from mecha_lab import mech_shader as msh  # noqa: E402
rec = []
msh.draw_background(_Rec(rec), C)
check('the N sidebar: a Background box (Background Colour button, colour, Solid View Too), no Set HDRI / HDRI list',
      ('op', 'mch.bg_color', 'Background Colour') in rec and ('prop', 'color') in rec and ('prop', 'solid_too') in rec
      and not any(e[0] == 'op' and e[1] == 'mch.mech_hdri' and e[2] == 'Set HDRI' for e in rec)
      and 'draw_background(layout, context)' in open(msh.__file__, encoding='utf-8').read()
      and 'draw_hdri(layout, context)\n' not in open(msh.__file__, encoding='utf-8').read(), rec)
summary()
