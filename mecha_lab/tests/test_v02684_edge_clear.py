"""0.24.286 Edge Clear (user: "선택하는 영역의 엣지 크리즈를 클릭하면 지워지는 엣지 클리어"): a click on a creased edge
clears its crease (and sharp mark) - the whole line up to where lines meet, Shift: only that edge."""
import math
from types import SimpleNamespace

import numpy as np

from _harness import bpy, check, fresh, summary
from mathutils import Matrix

import mecha_lab
from mecha_lab import edge_clear as ec, tool_state as ts, workspace_ui

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene


def crease_all(ob, sel=None):
    me = ob.data
    n = len(me.edges)
    v = np.zeros(n, np.float32)
    s = np.zeros(n, bool)
    idx = np.arange(n) if sel is None else np.asarray(sel)
    v[idx] = 1.0
    s[idx] = True
    a = me.attributes.get('crease_edge') or me.attributes.new('crease_edge', 'FLOAT', 'EDGE')
    a.data.foreach_set('value', v)
    b = me.attributes.get('sharp_edge') or me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
    b.data.foreach_set('value', s)
    me.update()


for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=1.0, vertices=32)
cy = C.active_object
me = cy.data
E = ec.edge_verts(me)
co = np.array([v.co for v in me.vertices])
top_rim = [k for k, (a, b) in enumerate(E) if co[a, 2] > 0.4 and co[b, 2] > 0.4 and
           abs(np.hypot(*co[a, :2]) - 1) < 1e-4 and abs(np.hypot(*co[b, :2]) - 1) < 1e-4]
bot_rim = [k for k, (a, b) in enumerate(E) if co[a, 2] < -0.4 and co[b, 2] < -0.4 and
           abs(np.hypot(*co[a, :2]) - 1) < 1e-4 and abs(np.hypot(*co[b, :2]) - 1) < 1e-4]
crease_all(cy, top_rim + bot_rim)
check('the creased edges are found (both rims: 64)', int(ec.marked(me).sum()) == 64, int(ec.marked(me).sum()))
line = ec.line_of(me, top_rim[3])
check('a click\'s line: the whole top rim (32 edges), not the bottom one', sorted(line) == sorted(top_rim), len(line))

# on screen: a top view (orthographic, 1000 px for 4 units)
region = SimpleNamespace(width=1000, height=1000)
rv3d = SimpleNamespace(perspective_matrix=Matrix.Diagonal((0.5, 0.5, -0.1, 1.0)))
xy = (500 + 250 * math.cos(0.3), 500 + 250 * math.sin(0.3))         # (a point on the rim, on screen)
e = ec.screen_edge(cy, region, rv3d, xy)
check('the creased edge under the mouse (on the rim)', e in top_rim or e in bot_rim, e)
check('... none when the mouse is far from any creased edge', ec.screen_edge(cy, region, rv3d, (500, 500)) is None)
n = ec.clear_edges(me, ec.line_of(me, top_rim[0]), True)
mk = ec.marked(me)
crease = np.empty(len(me.edges), np.float32)
me.attributes['crease_edge'].data.foreach_get('value', crease)
check('click (Whole Line): the top rim\'s crease and sharp cleared (32), the bottom rim kept',
      n == 32 and not mk[top_rim].any() and mk[bot_rim].all() and crease[top_rim].max() == 0.0, n)
co1 = np.array([v.co for v in me.vertices])
check('... the mesh does not move', np.allclose(co, co1))
n = ec.clear_edges(me, [bot_rim[0]], True)
check('Shift: only that one edge', n == 1 and int(ec.marked(me)[bot_rim].sum()) == 31)
crease_all(cy, bot_rim)
S.mch_edge_clear.sharp = False
ec.clear_edges(me, bot_rim[:5], False)
sh = np.zeros(len(me.edges), bool)
me.attributes['sharp_edge'].data.foreach_get('value', sh)
check('Also Sharp off: only the crease cleared, the sharp marks stay', sh[bot_rim[:5]].all())
S.mch_edge_clear.sharp = True

# a cube: three creased lines meet at each corner - a click takes one edge between corners
bpy.ops.mesh.primitive_cube_add()
cb = C.active_object
crease_all(cb)
check('cube: the line stops at the corners (3 lines meet): one edge', len(ec.line_of(cb.data, 0)) == 1)

# 0.24.288 Alt + click: add - an edge loop creased (Alt+Shift: one edge)
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16)
sp = C.active_object
sme = sp.data
E = ec.edge_verts(sme)
co = np.array([v.co for v in sme.vertices])
ring = [k for k, (a, b) in enumerate(E) if abs(co[a, 2]) < 1e-4 and abs(co[b, 2]) < 1e-4]
loop = ec.edge_loop(sme, ring[5])
check('Alt: the edge loop through the edge clicked (the sphere\'s equator: 32 edges)', sorted(loop) == sorted(ring),
      (len(loop), len(ring)))
n = ec.mark_edges(sme, loop, True)
mk = ec.marked(sme)
crease = np.empty(len(sme.edges), np.float32)
sme.attributes['crease_edge'].data.foreach_get('value', crease)
check('... creased (1) and sharp, only those', n == 32 and int(mk.sum()) == 32 and crease[ring].min() == 1.0)
check('... and a plain click on it clears the same line again', sorted(ec.line_of(sme, ring[0])) == sorted(ring))
ec.clear_edges(sme, ec.line_of(sme, ring[0]), True)
n = ec.mark_edges(sme, [ring[2]], True)
check('Alt+Shift: one edge only', n == 1 and int(ec.marked(sme).sum()) == 1)
vert = [k for k, (a, b) in enumerate(E) if abs(co[a, 2] - co[b, 2]) > 1e-3][7]
lp = ec.edge_loop(sme, vert)
check('... a loop along the meridian stops at the poles (not quads there)', 2 < len(lp) < 32, len(lp))
region = SimpleNamespace(width=1000, height=1000)
rv3d = SimpleNamespace(perspective_matrix=Matrix.Diagonal((0.5, 0.5, -0.1, 1.0)))
from mathutils import Vector  # noqa: E402
e = ec.screen_edge(sp, region, rv3d, (500 + 250 * 0.0, 500 + 250 * 0.5), any_edge=True, near=Vector((0.0, 0.5, 0.86)))
mid = (co[E[e, 0]] + co[E[e, 1]]) / 2 if e is not None else None
check('Alt: any edge under the mouse, the one on the side you see (front, not the back)', e is not None and mid[2] > 0,
      (e, mid))
check('a tool (Cut group, Target row), its own window settings, a workspace tool: click / Shift+click / move = hover',
      'ECLEAR' in ts.TOOL_BY_ID and ts.TOOL_BY_ID['ECLEAR'][5] == 'mecha.edge_clear'
      and {k[0] for k in workspace_ui and ec.MCH_TOOL_edge_clear.bl_keymap} >= {'mch.edge_clear_click',
                                                                               'mch.edge_clear_hover'}
      and any(k[1].get('alt') for k in ec.MCH_TOOL_edge_clear.bl_keymap if k[0] == 'mch.edge_clear_click'))
summary()
