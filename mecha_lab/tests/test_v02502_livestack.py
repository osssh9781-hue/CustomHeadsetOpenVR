"""0.24.82 Live Stack: the live steps (modifiers) on the active part in stack order with plain names - eye, up /
down, Apply (a tool's own Apply when it has one), remove, Apply All - in the Layers panel and N > Mecha Lab.
Blender's modifiers stay the truth (no stack engine of its own)."""
_src = open(__file__.replace('test_v02502_livestack.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import box_hide as bh, live_stack as ls, symmetry as sym, core_geometry as cg, layers_panel


def evaluated_faces(ob):
    dg = C.evaluated_depsgraph_get()
    dg.update()
    return len(ob.evaluated_get(dg).data.polygons)


for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
b = cube('Body', 2.0)
for v in b.data.vertices:
    v.co.x = v.co.x * 0.5 + 0.5
b.data.update()
select_only(b)
check('A plain mesh: nothing live', ls.entries(b) == [] and ls.warnings(b) == [])
sym.set_mode(C, b, 'MIRROR')
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
MODE[0], NATIVE[0] = 'HIDE', 'mecha.box_hide'
S.mch_settings.mch_active_tool = 'HIDE'
S.mch_cut.targets = 'AUTO'
S.mch_hide.cap = True
r, m = lasso([(560, 300), (640, 300), (640, 700), (560, 700)])
bev = b.modifiers.new('Bevel', 'BEVEL')
bev.width, bev.segments = 0.05, 2
sub = b.modifiers.new('MySubdiv', 'SUBSURF')
rows = ls.entries(b)
check('Mirror + Box Hide + Bevel + Subdivide: four steps in stack order with plain names', r == {'FINISHED'}
      and [n for _m, n, _s in rows] == ['Mirror', 'Box Hide', 'Bevel', 'MySubdiv (Subdivide)'], [n for _m, n, _s in rows])
check('... the order note: Mirror before Box Hide = both sides hidden', any('both sides' in w for w in ls.warnings(b)),
      ls.warnings(b))
select_only(b)
C.view_layer.objects.active = b
n_eval = evaluated_faces(b)
r = bpy.ops.mch.stack_toggle(name=bh.MOD)
check('The eye: Box Hide hidden in the viewport (still in the stack), more faces show', r == {'FINISHED'}
      and not b.modifiers[bh.MOD].show_viewport and len(b.modifiers) == 4 and evaluated_faces(b) > n_eval)
bpy.ops.mch.stack_toggle(name=bh.MOD)
r = bpy.ops.mch.stack_move(name='Bevel', step=-1)
check('Up: the Bevel before Box Hide', r == {'FINISHED'} and [m.name for m in b.modifiers][1] == 'Bevel')
bpy.ops.mch.stack_move(name='Bevel', step=1)
check('... and back down', [m.name for m in b.modifiers][2] == 'Bevel')
r = bpy.ops.mch.stack_apply(name=bh.MOD)
check('Apply Box Hide: the tool\'s own Apply (its record gone), the modifier baked, the others stay',
      r == {'FINISHED'} and bh.MOD not in b.modifiers and not bh.is_hidden(b)
      and [m.name for m in b.modifiers][1:] == ['Bevel', 'MySubdiv'], [m.name for m in b.modifiers])
r = bpy.ops.mch.stack_remove(name='MySubdiv')
check('Remove: the Subdivide gone', r == {'FINISHED'} and 'MySubdiv' not in b.modifiers and len(b.modifiers) == 2)
n_eval = evaluated_faces(b)
r = bpy.ops.mch.stack_apply_all()
check('Apply All: Mirror (the symmetry card\'s apply) + Bevel baked in order, the mesh as it was shown',
      r == {'FINISHED'} and len(b.modifiers) == 0 and len(b.data.polygons) == n_eval and sym.mirror_mod(b) is None,
      (len(b.modifiers), len(b.data.polygons), n_eval))
check('Names: Mecha modifiers get plain names, Blender ones their type', ls.label(b.modifiers.new('MCH_HE_Bevel', 'BEVEL'))
      == 'Edge Bevel (Hard Edges)' and ls.label(b.modifiers.new('MCH_ArmorShell', 'NODES')) == 'Armor Shell'
      and ls.label(b.modifiers.new('Shrinkwrap', 'SHRINKWRAP')) == 'Shrinkwrap'
      and ls.label(b.modifiers.new('MCH_Odd_Thing', 'DISPLACE')) == 'Odd Thing')
check('... Armor Shell not last: a note', any('Armor Shell is not last' in w for w in ls.warnings(b)), ls.warnings(b))
src_l = __import__('inspect').getsource(layers_panel.content)
check('Shown in the Layers panel (a section, open at first) and N > Mecha Lab', 'live_stack.draw' in src_l
      and 'start_folded=drawer is not live_stack.draw' in src_l
      and 'live_stack.draw' in __import__('inspect').getsource(__import__('mecha_lab.workspace_ui', fromlist=['x'])))
summary()
