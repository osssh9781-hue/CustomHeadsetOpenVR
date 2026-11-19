"""0.24.234 Bevel Normal for every mesh (user: "토글 버튼으로 전체 메쉬에 베벨 노말 두께 내가 정한 걸로 들어가게 넣어 주라,
중앙 메뉴에, 두께는 슬라이더로" / "선택한 거 베벨 노말 지우는 것도"): the edges look rounded in the render - Cycles' Bevel
shader node on the surface normal - with no change to the meshes.

How it works (no material is copied per object):
* every material of the meshes gets one node ``MCH Bevel Normal`` (a Bevel node) put in front of its shader's Normal
  input (what was plugged in there - a bump - goes into the Bevel's own Normal input, so it is kept);
* its Radius = the slider (``Scene.mch_bevel_normal_radius``, a Value node in each material) x the object's own
  switch (an Attribute node reading the object's custom property ``mch_bevel_n``: 1 on, 0 off) - so "Remove from
  Selected" only sets that switch to 0 on the selected objects, every other object with the same material keeps it;
* a mesh with no material at all gets the plain ``MCH Bevel Base`` material (Blender's default grey) - taken off
  again when the switch goes off;
* while it is on, meshes made later get it too.

Bevel is a Cycles node: in EEVEE / Material Preview the edges show no change (Rendered view with Cycles, Quick Render
and F12 do).  Off takes every node out again and puts the links back as they were.
"""
from __future__ import annotations

import bpy
from bpy.props import BoolProperty, FloatProperty

NODE = 'MCH Bevel Normal'
VALUE = 'MCH Bevel Radius'
SWITCH = 'MCH Bevel Switch'
MULT = 'MCH Bevel Mult'
PROP = 'mch_bevel_n'                 # the object's switch (custom property)
ADDED = 'mch_bevel_added_mat'        # the object got the base material from us
FILLED = 'mch_bevel_filled'          # 0.24.262 its empty slots we filled with the base material (indices)
BASE_MAT = 'MCH Bevel Base'
SAMPLES = 8
_SEEN = {'n': -1}


def _shaders(nt):
    """The shader nodes of ``nt`` with a Normal input (Principled, Diffuse, Glossy, Subsurface ...)."""
    return [n for n in nt.nodes if not n.name.startswith('MCH Bevel') and n.inputs.get('Normal') is not None
            and (n.bl_idname.startswith('ShaderNodeBsdf') or n.bl_idname == 'ShaderNodeSubsurfaceScattering')]


def install(mat, radius):
    """Put the Bevel Normal into ``mat`` (once).  True when it is there."""
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    nt = mat.node_tree
    if nt.nodes.get(NODE) is not None:
        nt.nodes[VALUE].outputs[0].default_value = radius
        return True
    shaders = _shaders(nt)
    if not shaders:
        return False
    bev = nt.nodes.new('ShaderNodeBevel')
    bev.name = bev.label = NODE
    bev.samples = SAMPLES
    val = nt.nodes.new('ShaderNodeValue')
    val.name = val.label = VALUE
    val.outputs[0].default_value = radius
    sw = nt.nodes.new('ShaderNodeAttribute')
    sw.name = sw.label = SWITCH
    sw.attribute_type = 'OBJECT'
    sw.attribute_name = '["%s"]' % PROP
    mul = nt.nodes.new('ShaderNodeMath')
    mul.name = mul.label = MULT
    mul.operation = 'MULTIPLY'
    nt.links.new(val.outputs[0], mul.inputs[0])
    nt.links.new(sw.outputs['Fac'], mul.inputs[1])
    nt.links.new(mul.outputs[0], bev.inputs['Radius'])
    x = min(n.location.x for n in shaders) - 260
    y = max(n.location.y for n in shaders) - 420
    for i, n in enumerate((sw, val, mul, bev)):
        n.location = (x - 220 * (3 - i) + 220, y)
    feeds = set()
    src0 = next((sh.inputs['Normal'].links[0].from_socket for sh in shaders if sh.inputs['Normal'].is_linked), None)
    if src0 is not None:
        nt.links.new(src0, bev.inputs['Normal'])           # (the bump goes on, under the bevel)
        feeds.add(src0.node.name)
    for sh in shaders:
        inp = sh.inputs['Normal']
        if inp.is_linked and inp.links[0].from_socket != src0:
            continue                                      # (a shader with a normal of its own: left as it is)
        nt.links.new(bev.outputs['Normal'], inp)
    bev['mch_fed'] = ','.join(sorted(feeds))
    return True


def uninstall(mat):
    """Take the Bevel Normal out of ``mat``, the links back as they were."""
    if mat is None or mat.node_tree is None:
        return
    nt = mat.node_tree
    bev = nt.nodes.get(NODE)
    if bev is None:
        return
    src = bev.inputs['Normal'].links[0].from_socket if bev.inputs['Normal'].is_linked else None
    targets = [lk.to_socket for lk in bev.outputs['Normal'].links]
    for name in (NODE, VALUE, SWITCH, MULT):
        n = nt.nodes.get(name)
        if n is not None:
            nt.nodes.remove(n)
    if src is not None:
        for t in targets:
            nt.links.new(src, t)


def _base_material():
    m = bpy.data.materials.get(BASE_MAT)
    if m is None:
        m = bpy.data.materials.new(BASE_MAT)
        m.use_nodes = True
    return m


def _meshes(context):
    return [o for o in context.scene.objects if o.type == 'MESH']


def fill_empty(ob):
    """0.24.262 (user's MECHA.blend: "베벨 노말이 안 돼" - every part had an EMPTY first slot its faces used, the base
    material had been added after it, so no face was drawn with the Bevel) every empty slot of ``ob`` filled with
    the base material (its faces get the bevel); a mesh with no material at all gets one.  What was done is kept on
    the object (``unfill`` puts it back exactly).  Returns how many filled."""
    import json
    me = ob.data
    if ob.type != 'MESH' or me is None or me.library:
        return 0
    try:
        rec = json.loads(ob.get(FILLED, '{}'))
        rec = rec if isinstance(rec, dict) else {'idx': list(rec), 'added': 0}
    except (TypeError, ValueError):
        rec = {}
    idx, added = set(rec.get('idx', [])), int(rec.get('added', 0))
    n = 0
    if not len(me.materials):
        me.materials.append(_base_material())
        ob[ADDED] = 1                                # (as before: marked as ours)
        added += 1
        idx.add(0)
        n += 1
    for i in range(len(me.materials)):
        s_ = ob.material_slots[i] if i < len(ob.material_slots) else None
        if me.materials[i] is None and (s_ is None or s_.link == 'DATA'):
            me.materials[i] = _base_material()
            idx.add(i)
            n += 1
    if idx:
        ob[FILLED] = json.dumps({'idx': sorted(idx), 'added': added})
    return n


def unfill(ob):
    """The slots ``fill_empty`` filled emptied again, the ones it added taken off."""
    import json
    if FILLED not in ob:
        return
    me = ob.data
    try:
        rec = json.loads(ob[FILLED])
        rec = rec if isinstance(rec, dict) else {'idx': list(rec), 'added': 0}
    except (TypeError, ValueError):
        rec = {'idx': [], 'added': 0}
    if me is not None:
        for i in rec.get('idx', []):
            if i < len(me.materials) and me.materials[i] is not None and me.materials[i].name == BASE_MAT:
                me.materials[i] = None
        for _k in range(int(rec.get('added', 0))):
            if len(me.materials) and me.materials[len(me.materials) - 1] is None:
                me.materials.pop(index=len(me.materials) - 1)
    del ob[FILLED]


def give(ob, radius, on=1.0):
    """``ob`` gets the Bevel Normal (its switch ``on``); its materials get the node."""
    if ob.type != 'MESH':
        return
    fill_empty(ob)
    ob[PROP] = float(on)
    for s in ob.material_slots:
        install(s.material, radius)
    ob.update_tag()


def turn_on(context):
    sc = context.scene
    r = float(sc.mch_bevel_normal_radius)
    for ob in _meshes(context):
        if PROP not in ob:
            give(ob, r)
        else:
            fill_empty(ob)                           # 0.24.262 (a file saved with empty slots: mended)
            for s in ob.material_slots:
                install(s.material, r)
    _SEEN['n'] = len(sc.objects)


def turn_off(context):
    mats = set()
    for ob in context.scene.objects:
        if ob.type == 'MESH':
            mats |= {s.material for s in ob.material_slots if s.material is not None}
            if ob.get(ADDED):
                me = ob.data
                i = next((n for n, m in enumerate(me.materials) if m is not None and m.name == BASE_MAT), None)
                if i is not None:
                    me.materials.pop(index=i)
                del ob[ADDED]
            unfill(ob)
            if PROP in ob:
                del ob[PROP]
            ob.update_tag()
    for m in mats:
        uninstall(m)
    base = bpy.data.materials.get(BASE_MAT)
    if base is not None and base.users == 0:
        bpy.data.materials.remove(base)


def set_radius(context, r):
    for m in bpy.data.materials:
        nt = m.node_tree if m.use_nodes else None
        v = nt.nodes.get(VALUE) if nt is not None else None
        if v is not None:
            v.outputs[0].default_value = r


def _on_update(self, context):
    if self.mch_bevel_normal:
        turn_on(context)
    else:
        turn_off(context)


def _radius_update(self, context):
    r = float(self.mch_bevel_normal_radius)
    set_radius(context, r)
    for ob in context.scene.objects:                 # 0.24.236 the made-real bevels follow the slider too (until applied)
        mod = ob.modifiers.get(REAL) if ob.type == 'MESH' else None
        if mod is not None:
            mod.width = r
            weld = ob.modifiers.get(WELD)
            if weld is not None:
                weld.merge_threshold = max(1e-5, r * 0.01)


@bpy.app.handlers.persistent
def _new_meshes(scene, depsgraph):
    """While it is on: meshes made later get it too (looked at only when the object count changed)."""
    try:
        if not getattr(scene, 'mch_bevel_normal', False) or len(scene.objects) == _SEEN['n']:
            return
        _SEEN['n'] = len(scene.objects)
        r = float(scene.mch_bevel_normal_radius)
        for ob in scene.objects:
            if ob.type == 'MESH' and PROP not in ob:
                give(ob, r)
    except (ReferenceError, AttributeError, RuntimeError):
        pass


class MCH_OT_bevel_normal_remove(bpy.types.Operator):
    """Take the Bevel Normal off the selected meshes (the others keep it)"""
    bl_idname = 'mch.bevel_normal_remove'
    bl_label = 'Remove Bevel Normal from Selected'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        n = 0
        for ob in context.selected_objects:
            if ob.type == 'MESH':
                ob[PROP] = 0.0                     # (stays 0: a later "made later" pass does not give it back)
                ob.update_tag()
                n += 1
        self.report({'INFO'}, f'Bevel Normal off on {n} mesh(es)')
        return {'FINISHED'}


class MCH_OT_bevel_normal_add(bpy.types.Operator):
    """Give the Bevel Normal back to the selected meshes"""
    bl_idname = 'mch.bevel_normal_add'
    bl_label = 'Bevel Normal on Selected'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        r = float(context.scene.mch_bevel_normal_radius)
        for ob in context.selected_objects:
            give(ob, r)
        return {'FINISHED'}


REAL = 'MCH Bevel Real'


TRIES = (dict(miter_outer='MITER_ARC', weld=False),              # (0.24.238 a result that sticks out of the part:
         dict(miter_outer='MITER_SHARP', weld=False),            #  the next one; Weld first takes out doubled points
         dict(miter_outer='MITER_SHARP', weld=True),
         dict(miter_outer='MITER_SHARP', weld=True, segments=1))
WELD = 'MCH Bevel Weld'


def helper(ob, context=None):
    """0.24.238 Is ``ob`` a helper, not a part: a live cutter / gap, shown as wire or bounds, not rendered, or the
    operand of another object's Boolean?  (Make Real leaves those alone - beveling a cutter made spikes.)"""
    if ob.name.startswith(('MCH_Cutter', 'MCH_GapIn', 'MCH_GapOut')) or ob.display_type in {'WIRE', 'BOUNDS'} \
            or ob.hide_render:
        return True
    scene = context.scene if context is not None else bpy.context.scene
    for o in scene.objects:
        for m in getattr(o, 'modifiers', ()):
            if m.type == 'BOOLEAN' and (getattr(m, 'object', None) is ob
                                        or (m.operand_type == 'COLLECTION' and m.collection is not None
                                            and ob.name in m.collection.objects)):
                return True
    return False


def sticks_out(ob, width, context=None):
    """How far the made-real mesh reaches off the part's own surface (0 = all on it).  A bevel only cuts corners,
    so a point farther off than about the width is a spike."""
    import bmesh
    from mathutils.bvhtree import BVHTree
    mod = ob.modifiers.get(REAL)
    if mod is None:
        return 0.0
    ctx = context or bpy.context
    keep = mod.show_viewport
    mod.show_viewport = False                          # (the surface without it)
    ctx.view_layer.update()
    dg = ctx.evaluated_depsgraph_get()
    bm = bmesh.new()
    try:
        bm.from_object(ob, dg)
        tree = BVHTree.FromBMesh(bm)
    finally:
        bm.free()
    mod.show_viewport = keep
    ctx.view_layer.update()
    me = ob.evaluated_get(ctx.evaluated_depsgraph_get()).data
    import math
    import numpy as np
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    # 0.24.239 (user's second FBX: 3,125 points at x = 3.45e30 - Blender's Bevel had made garbage points; the nearest
    # search found nothing for them and they were let through): a point that is not finite, or far outside the part's
    # own box, is a spike at once
    lo, hi = _box(ob, ctx)
    if out_of_box(co, lo, hi, width):
        return math.inf
    far = 0.0
    for v in co:
        hit = tree.find_nearest(v)
        if hit[0] is None:
            return math.inf
        far = max(far, hit[3])
    return far


def out_of_box(co, lo, hi, width):
    """Is any point not finite, or outside the box (``lo``, ``hi``) by more than a little?"""
    import numpy as np
    if not len(co):
        return False
    pad = max(width * 4.0, float(np.max(hi - lo)) * 0.02)
    return bool(not np.isfinite(co).all() or (co < lo - pad).any() or (co > hi + pad).any())


def _box(ob, ctx):
    """(min, max) of ``ob``'s evaluated mesh without the made-real bevel (local space)."""
    import numpy as np
    mod = ob.modifiers.get(REAL)
    keep = mod.show_viewport if mod is not None else None
    if mod is not None:
        mod.show_viewport = False
        ctx.view_layer.update()
    me = ob.evaluated_get(ctx.evaluated_depsgraph_get()).data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    if mod is not None:
        mod.show_viewport = keep
        ctx.view_layer.update()
    if not len(co):
        return np.zeros(3), np.zeros(3)
    good = co[np.isfinite(co).all(1)]
    return (good.min(0), good.max(0)) if len(good) else (np.zeros(3), np.zeros(3))


def broken_points(ob, ctx=None):
    """How many points of ``ob``'s own mesh (no modifiers) are not finite or absurdly far (> 1e6) - a mesh broken
    before the bevel."""
    import numpy as np
    me = ob.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    return int(((~np.isfinite(co)).any(1) | (np.abs(co) > 1e6).any(1)).sum())


def make_real(ob, width, segments=3, context=None):
    """0.24.236 (user: "이렇게 베벨로 바뀐 메쉬를 진짜 그런 형태로 바꿀 수는 없나?") the rounded look made real geometry:
    a live Bevel modifier on ``ob`` (Angle 30°, Width as the look's Radius, Segments, Harden Normals, no overlap) at
    the end of its stack - editable, and baked by Apply Modifiers like any other; the shading bevel goes off on it (no
    double rounding).
    0.24.238 (user, a render with long spikes): the result is checked - no point may end up farther off the part's
    surface than the width; if one does, safer settings are tried (sharp miters, doubled points welded first, one
    segment); if none is clean the modifier is taken off again.  Returns the modifier, or None."""
    for t in TRIES:
        mod = ob.modifiers.get(REAL)
        if mod is None:
            mod = ob.modifiers.new(REAL, 'BEVEL')
        weld = ob.modifiers.get(WELD)
        if t['weld'] and weld is None:
            weld = ob.modifiers.new(WELD, 'WELD')
            weld.merge_threshold = max(1e-5, width * 0.01)
            ob.modifiers.move(ob.modifiers.find(WELD), ob.modifiers.find(REAL))
        elif not t['weld'] and weld is not None:
            ob.modifiers.remove(weld)
        mod.width = width
        mod.segments = t.get('segments', segments)
        mod.limit_method = 'ANGLE'
        mod.angle_limit = 0.5236
        mod.profile = 0.5
        mod.use_clamp_overlap = True
        mod.harden_normals = True
        mod.miter_outer = t['miter_outer']
        ob.update_tag()
        if sticks_out(ob, width, context) <= width * 1.5 + 1e-6:
            ob[PROP] = 0.0
            return mod
    for name in (REAL, WELD):                          # (none clean: as it was)
        m = ob.modifiers.get(name)
        if m is not None:
            ob.modifiers.remove(m)
    ob.update_tag()
    return None


class MCH_OT_bevel_normal_real(bpy.types.Operator):
    """Make the rounded edges real geometry on the SELECTED meshes only: a live Bevel modifier, Radius wide; Apply
    Modifiers bakes it"""
    bl_idname = 'mch.bevel_normal_real'
    bl_label = 'Make Bevel Real'
    bl_options = {'REGISTER', 'UNDO'}

    segments: bpy.props.IntProperty(name='Segments', default=3, min=1, max=12)

    @classmethod
    def poll(cls, context):                          # 0.24.237 (user: "베벨 메이크 리얼은 셀렉트만 되게") selected only
        return any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        obs = [o for o in context.selected_objects if o.type == 'MESH']
        if not obs:
            self.report({'WARNING'}, 'Make Real: select the meshes first')
            return {'CANCELLED'}
        r = float(context.scene.mch_bevel_normal_radius)
        done, skipped, failed = [], [], []
        for ob in obs:
            if helper(ob, context):                  # 0.24.238 cutters / wire helpers: left alone
                skipped.append(ob.name)
                continue
            nb = broken_points(ob)                   # 0.24.239 the mesh itself already has garbage points
            if nb:
                failed.append(f'{ob.name} ({nb} broken points in the mesh itself - Fix Mesh first)')
                continue
            (done if make_real(ob, r, self.segments, context) is not None else failed).append(ob.name)
        msg = f'Bevel made real on {len(done)} mesh(es)'
        if skipped:
            msg += f'; {len(skipped)} helper(s) skipped (cutters / wire)'
        if failed:
            msg += f'; no clean bevel on {", ".join(failed[:3])} - left as it was'
        self.report({'WARNING'} if failed else {'INFO'}, msg)
        return {'FINISHED'} if done else {'CANCELLED'}


CLASSES = (MCH_OT_bevel_normal_remove, MCH_OT_bevel_normal_add, MCH_OT_bevel_normal_real)


@bpy.app.handlers.persistent
def _on_load(*_a):
    """0.24.262 a file saved with the Bevel Normal on: its empty slots filled (older versions left them)."""
    try:
        for sc in bpy.data.scenes:
            if getattr(sc, 'mch_bevel_normal', False):
                for ob in sc.objects:
                    if ob.type == 'MESH' and ob.get(PROP):
                        if fill_empty(ob):
                            for s in ob.material_slots:
                                install(s.material, float(sc.mch_bevel_normal_radius))
                            ob.update_tag()
    except (ReferenceError, AttributeError, RuntimeError):
        pass


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)
    bpy.types.Scene.mch_bevel_normal = BoolProperty(
        name='Bevel Normal', default=False, update=_on_update,
        description='Every mesh\'s edges rendered rounded by the Bevel shader (Cycles), Radius wide - the meshes are '
                    'not changed')
    bpy.types.Scene.mch_bevel_normal_radius = FloatProperty(
        name='Radius', default=0.01, min=0.0, soft_max=0.1, max=1.0, unit='LENGTH', precision=3,
        update=_radius_update, description='How wide the rounded look of the edges is (Bevel Normal)')
    if _new_meshes not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_new_meshes)


def unregister():
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    if _new_meshes in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_new_meshes)
    for name in ('mch_bevel_normal', 'mch_bevel_normal_radius'):
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
