"""0.23.13: padding puff from a membrane (no X ridge to the corners), padding pinches as thin V creases."""
import math
import sys

_src = open(__file__.replace('test_v02313.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
import bmesh
import numpy as np

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import cloth_wrinkle as cw, last_used

# 1. membrane on a square grid: no kink across the diagonal (the border distance has one)
bm = bmesh.new()
N = 30
bmesh.ops.create_grid(bm, x_segments=N, y_segments=N, size=1.0)
bm.verts.ensure_lookup_table()
dist = {v: 1.0 - max(abs(v.co.x), abs(v.co.y)) for v in bm.verts}
u = np.array(cw._membrane(bm, dist))
co = np.array([v.co[:2] for v in bm.verts])
d = np.array([dist[v] for v in bm.verts])
check('membrane: 0 on the border, max = deepest border distance',
      abs(u[np.array([v.is_boundary for v in bm.verts])]).max() < 1e-9 and abs(u.max() - d.max()) < 1e-6)


def sd(f, s):
    # walk across the diagonal x = y at (0.6, 0.6) along (1, -1); second difference at the crossing
    vals = []
    for t in (-s, 0.0, s):
        p = np.array([0.6 + t, 0.6 - t])     # grid points (step 2/30)
        vals.append(f[np.argmin(((co - p) ** 2).sum(1))])
    return abs(vals[0] - 2 * vals[1] + vals[2])


def kink(f):
    # a smooth surface: the second difference shrinks 4x when the step halves; a ridge (kink) only 2x
    h = 2.0 / N
    return sd(f, 4 * h) / max(sd(f, 2 * h), 1e-12)


check('border distance has the ridge (control)', kink(d) < 2.6, round(float(kink(d)), 2))
check('membrane: no ridge along the diagonal (X gone)', kink(u) > 3.2, round(float(kink(u)), 2))
bm.free()

# 2. the cloth plate stores the membrane; padding uses V pinches (Fold In)
check('padding preset folds in (pinch)', cw.PRESETS['PADDING'].get('Pinch', 0) > 0)
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
last_used.forget('wrinkle')
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
S.mch_settings.mch_active_tool = 'WRINKLE'
S.mch_wrinkle.wtype = 'PADDING'
b = cube('B', 4.0)
r, m = lasso([(330, 330), (670, 330), (680, 660), (320, 670)])
o = C.active_object
check('cloth plate has the membrane attribute', cw.EDGE_SMOOTH in o.data.attributes)
check('padding: Fold In on', cw.get_input(o, 'Fold In') >= 0.5 if hasattr(cw, 'get_input') else True)
dg = C.evaluated_depsgraph_get()
me = o.evaluated_get(dg).data
check('padding plate evaluates', len(me.vertices) > 100 and all(math.isfinite(c) for v in me.vertices[:200] for c in v.co))

# 3. Space: no big tool menu any more; Space held while drawing moves the outline
kc = C.window_manager.keyconfigs.addon
check('Space no longer opens the tool menu', kc is None or not any(
    ki.idname == 'mch.space_tools' for km in kc.keymaps for ki in km.keymap_items))
ctx, op = Ctx(), Op()
pts = [(330, 330), (670, 330), (680, 660)]
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', *pts[0]))
op.modal(ctx, E('LEFTMOUSE', 'RELEASE', *pts[0]))
for x, y in pts[1:]:
    op.modal(ctx, E('LEFTMOUSE', 'PRESS', x, y))
    op.modal(ctx, E('LEFTMOUSE', 'RELEASE', x, y))
before = [tuple(p) for p in op.pts]
op.modal(ctx, E('MOUSEMOVE', 'NOTHING', 680, 660))
op.modal(ctx, E('SPACE', 'PRESS', 680, 660))
op.modal(ctx, E('MOUSEMOVE', 'NOTHING', 700, 640))
op.modal(ctx, E('MOUSEMOVE', 'NOTHING', 720, 610))
r_sp = op.modal(ctx, E('SPACE', 'RELEASE', 720, 610))
after = [tuple(p) for p in op.pts]
check('Space + mouse move shifts every point by the mouse motion (stroke still running)',
      len(after) == len(before) and all(abs(a[0] - b[0] - 40) < 1e-6 and abs(a[1] - b[1] + 50) < 1e-6
                                        for a, b in zip(after, before)) and 'RUNNING_MODAL' in r_sp, (before, after))
op.modal(ctx, E('MOUSEMOVE', 'NOTHING', 760, 600))
check('after Space is released the mouse no longer moves the outline', [tuple(p) for p in op.pts] == after)
op.modal(ctx, E('ESC'))
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
