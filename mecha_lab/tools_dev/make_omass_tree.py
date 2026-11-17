"""0.24.190 Creature Base Mesh 2's node group made ready (user: "크리쳐 베이스 메쉬는 너무 느려"): building its 670 nodes
takes 4 - 5 seconds the first time the tool is used in a file - here it is built once and written to
addon/mecha_lab/node_trees/omass_tree.blend, which the tool takes it from (it builds it itself if the file is not
there, is another Blender's, or holds an older group).

    <blender python> make_omass_tree.py          (again whenever organic_mass.TREE_VERSION changes)
"""
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'addon'))
bpy.ops.wm.read_factory_settings(use_empty=True)
import mecha_lab  # noqa: E402
from mecha_lab import organic_mass as om  # noqa: E402

mecha_lab.register()
om.STORED[0] = False
ng = om.organic_tree()
ng.use_fake_user = False
os.makedirs(os.path.dirname(om.TREE_FILE), exist_ok=True)
bpy.data.libraries.write(om.TREE_FILE, {ng}, compress=True)
print('written', om.TREE_FILE, os.path.getsize(om.TREE_FILE), 'bytes;', len(ng.nodes), 'nodes, version', ng['mch_v'],
      'Blender', bpy.app.version_string)
