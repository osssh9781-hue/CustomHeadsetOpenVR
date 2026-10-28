"""0.24.81 Mirror + Box Hide at the same time: a part with a live Mirror (the symmetry card) hidden with Box Hide
(Follow Symmetry: the hiding comes after the Mirror in the stack) came out EMPTY - the Box Hide modifier's Manifold
flag was read off the base mesh (closed), but the mirrored mesh that reaches it has a seam of doubled edges, and
the Manifold solver gives nothing back for such input.  The flag is read off what reaches the modifier now.
Box Hide first and the Mirror after it worked before and still does (the Mirror copies the hidden result)."""
_src = open(__file__.replace('test_v02499_mirrorhide.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import box_hide as bh, core_geometry as cg, symmetry as sym

S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
MODE[0], NATIVE[0] = 'HIDE', 'mecha.box_hide'
S.mch_settings.mch_active_tool = 'HIDE'
S.mch_cut.targets = 'AUTO'


def half_cube():
    """A half part (x 0 .. 1) - the Mirror makes the other half."""
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    b = cube('Body', 2.0)
    for v in b.data.vertices:
        v.co.x = v.co.x * 0.5 + 0.5
    b.data.update()
    C.view_layer.update()
    return b


def evaluated(ob):
    dg = C.evaluated_depsgraph_get()
    dg.update()
    me = ob.evaluated_get(dg).data
    xs = [v.co.x for v in me.vertices]
    return len(me.polygons), (min(xs) if xs else 0.0, max(xs) if xs else 0.0)


S.mch_hide.cap = True
S.mch_hide.follow_symmetry = True
b = half_cube()
sym.set_mode(C, b, 'MIRROR')
n_mirror, _x = evaluated(b)
r, m = lasso([(560, 300), (640, 300), (640, 700), (560, 700)])          # world x 0.6 .. 1.4: the end of the part
n, (x0, x1) = evaluated(b)
check('A live Mirror, then Box Hide (Follow Symmetry): the part is still there, the end hidden on both sides',
      bh.is_hidden(b) and n > 0 and x1 < 0.65 and x0 > -0.65 and 'symmetric copy' in m,
      (n, round(x0, 2), round(x1, 2), m))
mod = b.modifiers[bh.MOD]
check('... the modifier knows the mirrored mesh that reaches it is not one closed solid (the seam)',
      cg.gn_get(mod, bh._ident(mod.node_group, 'Manifold')) is False
      and [mm.name for mm in b.modifiers] == ['MCH_Mirror', bh.MOD])
check('... the Mirror stays live', sym.mirror_mod(b) is not None)

b = half_cube()
r, m = lasso([(560, 300), (640, 300), (640, 700), (560, 700)])
sym.set_mode(C, b, 'MIRROR')
n, (x0, x1) = evaluated(b)
check('Box Hide first, then the Mirror: the hidden result is mirrored (as before)', bh.is_hidden(b) and n > 0
      and x1 < 0.65 and x0 > -0.65 and [mm.name for mm in b.modifiers] == [bh.MOD, 'MCH_Mirror'],
      (n, round(x0, 2), round(x1, 2)))

b = half_cube()
r, m = lasso([(560, 300), (640, 300), (640, 700), (560, 700)])
mod = b.modifiers[bh.MOD]
check('No modifier before it: a closed base mesh still takes the fast Manifold solver',
      cg.gn_get(mod, bh._ident(mod.node_group, 'Manifold')) is True)
summary()
