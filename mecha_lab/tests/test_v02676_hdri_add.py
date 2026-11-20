"""0.24.276 (user: "HDRI 부분에 HDRI 추가하게 해 줘"): Add HDRI puts a file into the world (a new Environment Texture on
its Background when it has none, else into the one it has - nothing else of the world changed); ◀ ▶ step through the
HDRIs of that folder; Strength; Rotation / Follow Camera keep working on the new image."""
import math
import os
import tempfile

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import hdri_turn as ht, side_panel as sp  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
d = tempfile.mkdtemp(prefix='mch_hdri_')
paths = []
for i, name in enumerate(('a_sky.hdr', 'b_studio.hdr', 'c_sunset.hdr')):
    im = bpy.data.images.new(name, 16, 8, float_buffer=True)
    im.pixels.foreach_set([0.2 * (i + 1)] * (16 * 8 * 4))
    im.filepath_raw = os.path.join(d, name); im.file_format = 'HDR'; im.save()
    bpy.data.images.remove(im)
    paths.append(os.path.join(d, name))
open(os.path.join(d, 'notes.txt'), 'w').write('x')
w = bpy.data.worlds.new('Plain'); S.world = w; w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.bl_idname == 'ShaderNodeBackground')
check('a plain world: no HDRI yet', ht.current_image(S) is None)
r = bpy.ops.mch.hdri_add(filepath=paths[1])
env = ht._main_envs(S)
check('Add HDRI: an Environment Texture on the Background, the file in it',
      r == {'FINISHED'} and len(env) == 1 and env[0].image.name == 'b_studio.hdr'
      and bg.inputs['Color'].links[0].from_node == env[0] and S.world is w)
bpy.ops.mch.hdri_step(step=1)
check('▶: the next HDRI of the folder (the .txt skipped)', ht.current_image(S).name == 'c_sunset.hdr')
bpy.ops.mch.hdri_step(step=1)
check('▶ at the end: round to the first', ht.current_image(S).name == 'a_sky.hdr')
bpy.ops.mch.hdri_step(step=-1)
check('◀: back', ht.current_image(S).name == 'c_sunset.hdr')
S.mch_hdri_turn.turn = math.radians(30)
bpy.ops.mch.hdri_add(filepath=paths[0])
envs = ht._main_envs(S)
check('another file into a world that has one: the same node takes it (no second node), rotation kept',
      len(envs) == 1 and envs[0].image.name == 'a_sky.hdr' and len([n for n in ht.turn_nodes(S) if n.bl_idname == 'ShaderNodeMapping']) == 1
      and envs[0].inputs['Vector'].links[0].from_node.name == ht.NODE)
S.world = None
bpy.ops.mch.hdri_add(filepath=paths[2])
check('no world at all: a new "HDRI World" with it', S.world is not None and ht.current_image(S).name == 'c_sunset.hdr')
C.window_manager.mch_side_page = 'HDRI'
sp.FOLDED.discard('MATERIAL:r_hdri_turn')
items, _h = sp.content(C, 'CUT', 0, 300, 1.0)
L = [getattr(i, 'label', '') for i in items]
check(f'the HDRI section: Add HDRI, ◀ name ▶, Strength, the rotation', all(x in L for x in (
    'Add HDRI…', '◀', 'c_sunset.hdr', '▶', 'Strength', 'HDRI Rotation', 'Follow Camera')))
S.mch_hdri_turn.strength = 2.5
check('Strength (the panel bar) sets the world Background\'s', abs(ht.strength_socket(S).default_value - 2.5) < 1e-6)
summary()
