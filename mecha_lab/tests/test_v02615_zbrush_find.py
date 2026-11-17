"""0.24.194 (user: "지브러시 브릿지 만든 거 어떻게 연동해? 에드온에서 지브러시 알아서 찾아 주는 거 못 만들어?"): the bridge
finds ZBrush itself (the install folders; on Windows also the registry - not testable here), the newest one, and Send
starts it when it is not open.  Here: folders made like an install (no real ZBrush on this machine)."""
import os
import tempfile

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import zbrush_bridge as zb  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
s = C.scene.mch_zbrush
root = tempfile.mkdtemp(prefix='mch_zb_')
check('nothing installed: not found', zb.find_zbrush(roots=[root], registry=False, fresh=True) == '')
for d in ('Maxon ZBrush 2024', os.path.join('Pixologic', 'ZBrush 2022'), os.path.join('Maxon', 'ZBrush 2025.1'),
          'Blender Foundation'):
    os.makedirs(os.path.join(root, d))
for d in ('Maxon ZBrush 2024', os.path.join('Pixologic', 'ZBrush 2022'), os.path.join('Maxon', 'ZBrush 2025.1')):
    open(os.path.join(root, d, 'ZBrush.exe'), 'w').close()
got = zb.find_zbrush(roots=[root], registry=False, fresh=True)
check('three installs (Maxon ZBrush 2024, Pixologic\\ZBrush 2022, Maxon\\ZBrush 2025.1): the newest is taken',
      got == os.path.join(root, 'Maxon', 'ZBrush 2025.1', 'ZBrush.exe'), got)
s.zbrush_exe = os.path.join(root, 'Maxon ZBrush 2024', 'ZBrush.exe')
check('a path typed in wins over the search', zb.zbrush_path(s) == s.zbrush_exe)
s.zbrush_exe = os.path.join(root, 'gone', 'ZBrush.exe')
zb.FOUND[None] = got                                 # (as if the search of this computer gave it)
check('a typed path that no longer exists: the found one instead', zb.zbrush_path(s) == got)
zb.FOUND[None] = ''
s.zbrush_exe = ''
note = zb.launch_zbrush(s)
check('no ZBrush at all: Send says so instead of failing', 'not found' in note, note)
check('the button and the option exist (Find ZBrush, Open ZBrush on Send - on by default)',
      hasattr(bpy.types, 'MCH_OT_zbrush_find') and s.launch is True)
bpy.ops.mesh.primitive_cube_add()
r = bpy.ops.mch.zbrush_send()
folder = zb.exchange_folder(s)
files = [e['file'] for e in zb.read_manifest(folder).get('objects', {}).values()]
check('Send still works with no ZBrush here (the OBJ written; the clipboard needs a real window: tests/gui)',
      'FINISHED' in r and len(files) == 1 and os.path.isfile(os.path.join(str(folder), files[0])), files)
r = bpy.ops.mch.zbrush_find()
check('Find ZBrush on a computer without it: a warning, nothing set', 'CANCELLED' in r and s.zbrush_exe == '')
summary()
