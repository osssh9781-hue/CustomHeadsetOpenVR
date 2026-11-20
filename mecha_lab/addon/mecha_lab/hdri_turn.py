"""0.24.266 (user: "내가 지정해 놓은 HDRI 를 내 카메라 쪽에 고정해 놓고 렌더 탭에서 돌리면서 렌더 - 각도 슬라이더, 다시 원점으로
돌리기도 편하게") Turn the world's HDRI from the Render page, and keep it fixed to the scene camera.

Whatever made the world (the user's own HDRI add-on, Mecha Lab's HDRI, a hand-made world), every Environment Texture in
it gets one Mapping node of ours in front (``mch:hdri_turn``, the vector that fed it before goes through it).  Its Z
rotation is a driver: Rotation (+ the camera's world Z turn when Follow Camera is on) - so the light and the background
stay put relative to the camera when the camera orbits the model, and the slider turns them.  Nothing else in the world
is changed; Turn Off takes our node out and puts the old link back."""
from __future__ import annotations

import math

import bpy
from bpy.props import BoolProperty, FloatProperty, PointerProperty

NODE = 'mch:hdri_turn'


def _tree(scene):
    w = scene.world
    return w.node_tree if w is not None and w.use_nodes and w.node_tree is not None else None


def envs(scene):
    nt = _tree(scene)
    return [n for n in nt.nodes if n.bl_idname == 'ShaderNodeTexEnvironment'] if nt is not None else []


def turn_nodes(scene):
    nt = _tree(scene)
    return [n for n in nt.nodes if n.name.startswith(NODE)] if nt is not None else []


def _driver(nt, node, scene):
    _drive(node.inputs['Rotation'], 'default_value', node, scene)


def _drive(owner, path, tag, scene):
    """``owner.path[2]`` = Rotation (+ the camera's Z turn); ``tag`` remembers the camera it follows."""
    node = tag
    sock = owner
    try:
        sock.driver_remove(path, 2)
    except (TypeError, RuntimeError):
        pass
    fc = sock.driver_add(path, 2)
    d = fc.driver
    d.type = 'SCRIPTED'
    for v in list(d.variables):
        d.variables.remove(v)
    t = d.variables.new()
    t.name, t.type = 'turn', 'SINGLE_PROP'
    t.targets[0].id_type = 'SCENE'
    t.targets[0].id = scene
    t.targets[0].data_path = 'mch_hdri_turn.turn'
    st = scene.mch_hdri_turn
    cam = scene.camera
    if st.follow and cam is not None:
        c = d.variables.new()
        c.name, c.type = 'cam', 'TRANSFORMS'
        c.targets[0].id = cam
        c.targets[0].transform_type = 'ROT_Z'
        c.targets[0].transform_space = 'WORLD_SPACE'
        d.expression = 'cam + turn'
    else:
        d.expression = 'turn'
    node['mch_cam'] = cam.name if (st.follow and cam is not None) else ''


def ensure(scene):
    """Our Mapping node in front of every Environment Texture of the world (one per vector source), its driver up to
    date.  Returns the number of HDRI images it turns."""
    nt = _tree(scene)
    if nt is None:
        return 0
    groups = {}
    for env in envs(scene):
        sock = env.inputs['Vector']
        src = sock.links[0].from_socket if sock.is_linked else None
        if src is not None and src.node.name.startswith(NODE):
            groups.setdefault(src.node.name, (src.node, []))[1].append(env)
            continue
        key = (src.node.name + ':' + src.identifier) if src is not None else ''
        groups.setdefault(key, (src, []))[1].append(env)
    for key, (src, lst) in groups.items():
        if isinstance(src, bpy.types.Node):          # (already ours)
            node = src
        else:
            node = nt.nodes.new('ShaderNodeMapping')
            node.name = node.label = NODE
            node.vector_type = 'TEXTURE'             # (the environment turns the way the camera does)
            e0 = lst[0]
            node.location = (e0.location.x - 220, e0.location.y - 260)
            if src is None:
                tc = nt.nodes.new('ShaderNodeTexCoord')
                tc.name = tc.label = NODE + '_coord'
                tc.location = (node.location.x - 200, node.location.y)
                nt.links.new(tc.outputs['Generated'], node.inputs['Vector'])
                node['mch_from'] = ''
            else:
                nt.links.new(src, node.inputs['Vector'])
                node['mch_from'] = key
            for e in lst:
                nt.links.new(node.outputs['Vector'], e.inputs['Vector'])
        _driver(nt, node, scene)
    return len(envs(scene))


# --- 0.24.266 (user: "라이팅을 설정해 놨다면 그 라이팅을 내가 픽하면 그것도 같이 돌아가면") lights turning with the HDRI ---

PIVOT = 'MCH_Light_Turn'


def pivot(scene, make=False, centre=None):
    ob = bpy.data.objects.get(PIVOT)
    if ob is None and make:
        ob = bpy.data.objects.new(PIVOT, None)
        ob.empty_display_type = 'PLAIN_AXES'
        ob.empty_display_size = 0.3
        ob.hide_render = True
        scene.collection.objects.link(ob)
        if centre is not None:
            ob.location = centre
    if ob is not None and make:
        _drive(ob, 'rotation_euler', ob, scene)
    return ob


def lights(scene):
    pv = bpy.data.objects.get(PIVOT)
    return [o for o in pv.children if o.type == 'LIGHT'] if pv is not None else []


def add_lights(scene, obs):
    """The lights among ``obs`` hung on the turning pivot (they stay where they are now)."""
    lts = [o for o in obs if o.type == 'LIGHT' and o.parent is None or (o.type == 'LIGHT' and o.parent.name != PIVOT)]
    if not lts:
        return 0
    meshes = [o for o in scene.objects if o.type == 'MESH' and o.visible_get()]
    centre = None
    if meshes:
        from mathutils import Vector
        pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), 0.0))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), 0.0))
        centre = (lo + hi) / 2
    pv = pivot(scene, make=True, centre=centre)
    bpy.context.view_layer.update()
    for o in lts:
        mw = o.matrix_world.copy()
        o['mch_old_parent'] = o.parent.name if o.parent is not None else ''
        o.parent = pv
        o.matrix_world = mw
    return len(lts)


def release_lights(scene):
    """The lights back off the pivot (where they are now), the pivot gone."""
    pv = bpy.data.objects.get(PIVOT)
    if pv is None:
        return 0
    bpy.context.view_layer.update()
    n = 0
    for o in list(pv.children):
        mw = o.matrix_world.copy()
        old = bpy.data.objects.get(o.get('mch_old_parent', '') or '')
        o.parent = old
        o.matrix_world = mw
        if 'mch_old_parent' in o:
            del o['mch_old_parent']
        n += 1
    bpy.data.objects.remove(pv)
    return n


def remove(scene):
    """Our nodes out, the old links back."""
    nt = _tree(scene)
    if nt is None:
        return
    for node in turn_nodes(scene):
        if node.bl_idname != 'ShaderNodeMapping':
            continue
        src = node.inputs['Vector'].links[0].from_socket if node.inputs['Vector'].is_linked else None
        if src is not None and src.node.name.startswith(NODE):
            src = None                               # (our own Texture Coordinate: nothing was linked before)
        targets = [lk.to_socket for lk in node.outputs['Vector'].links]
        try:
            node.inputs['Rotation'].driver_remove('default_value', 2)
        except (TypeError, RuntimeError):
            pass
        nt.nodes.remove(node)
        if src is not None:
            for t in targets:
                nt.links.new(src, t)
    for node in turn_nodes(scene):
        nt.nodes.remove(node)


def active(scene):
    st = scene.mch_hdri_turn
    return st.follow or abs(st.turn) > 1e-6


def _upd(self, context):
    sc = self.id_data
    if bpy.data.objects.get(PIVOT) is not None:
        pivot(sc, make=True)                         # (the camera it follows may have changed)
    if active(sc):
        ensure(sc)
    elif turn_nodes(sc):
        remove(sc)


class MCH_PG_HdriTurn(bpy.types.PropertyGroup):
    follow: BoolProperty(name='Follow Camera', default=False, update=_upd,
                         description='The HDRI stays fixed to the scene camera: orbit the camera round the model and the '
                                     'light and background turn with it')
    turn: FloatProperty(name='HDRI Rotation', default=0.0, subtype='ANGLE', soft_min=-math.pi, soft_max=math.pi,
                        update=_upd, description='Turn the HDRI (the light and the background) round the model')


class MCH_OT_hdri_turn_reset(bpy.types.Operator):
    """HDRI Rotation back to 0 (where it started)"""
    bl_idname = 'mch.hdri_turn_reset'
    bl_label = 'Back to Start'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.mch_hdri_turn.turn = 0.0
        return {'FINISHED'}


class MCH_OT_hdri_turn_lights(bpy.types.Operator):
    """Pick the lights you set up: the selected lights turn with the HDRI (Rotation and Follow Camera).  Release: they
    stay where they are and no longer turn"""
    bl_idname = 'mch.hdri_turn_lights'
    bl_label = 'Turn Selected Lights Too'
    bl_options = {'REGISTER', 'UNDO'}
    release: BoolProperty(default=False, options={'SKIP_SAVE'})

    def execute(self, context):
        sc = context.scene
        if self.release:
            n = release_lights(sc)
            self.report({'INFO'}, f'{n} light(s) no longer turn')
            return {'FINISHED'}
        n = add_lights(sc, context.selected_objects)
        if not n:
            self.report({'WARNING'}, 'Select the lights to turn (in the viewport or the outliner)')
            return {'CANCELLED'}
        self.report({'INFO'}, f'{n} light(s) turn with the HDRI')
        return {'FINISHED'}


class MCH_OT_hdri_turn_follow(bpy.types.Operator):
    """Follow Camera on / off: the HDRI fixed to the scene camera"""
    bl_idname = 'mch.hdri_turn_follow'
    bl_label = 'Follow Camera'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        st = context.scene.mch_hdri_turn
        st.follow = not st.follow
        return {'FINISHED'}


def _check(scene, _dg=None):
    """The world was rebuilt (another HDRI picked) or the scene camera changed: our node back / the driver re-aimed."""
    try:
        sc = scene if isinstance(scene, bpy.types.Scene) else bpy.context.scene
        if sc is None or not active(sc):
            return
        ours = turn_nodes(sc)
        cam = sc.camera.name if (sc.mch_hdri_turn.follow and sc.camera is not None) else ''
        bare = [e for e in envs(sc) if not (e.inputs['Vector'].is_linked
                                            and e.inputs['Vector'].links[0].from_node.name.startswith(NODE))]
        if bare or any(n.get('mch_cam', '') != cam for n in ours if n.bl_idname == 'ShaderNodeMapping'):
            bpy.app.timers.register(lambda: (ensure(bpy.context.scene), None)[1], first_interval=0.01)
    except (ReferenceError, AttributeError, RuntimeError):
        pass


def section(b, context, x, width):
    """The Render page's HDRI Rotation section."""
    from . import mech_shader_ui as mu, i18n
    sc = context.scene
    st = sc.mch_hdri_turn

    def fill(sx, sw):
        n = len(envs(sc))
        if n == 0:
            b.note(('note', 'No HDRI in the world (pick one first)', True, None, None, None, True), sx, sw)
        mu.row(b, sx, sw, [mu._cell('seg', 'Follow Camera', ('op', 'mch.hdri_turn_follow', {}), on=st.follow)])
        if st.follow and sc.camera is None:
            b.note(('note', 'No scene camera: add one in Camera above', True, None, None, None, True), sx, sw)
        mu.row(b, sx, sw, [mu.number(st, 'turn', 'HDRI Rotation')])
        mu.row(b, sx, sw, [mu.button('Back to Start', 'mch.hdri_turn_reset')])
        lts = lights(sc)
        mu.row(b, sx, sw, [mu.button('Turn Selected Lights Too', 'mch.hdri_turn_lights')])
        if lts:
            txt = (f'조명 {len(lts)} 개가 같이 돎' if i18n.lang() == 'KO' else f'{len(lts)} light(s) turn with it')
            b.note(('note', txt, False, None, None, None, True), sx, sw)
            mu.row(b, sx, sw, [mu.button('Release Lights', 'mch.hdri_turn_lights', release=True)])
    summ = f'{math.degrees(st.turn):.0f}°' + (' + ' + i18n.tr('Camera') if st.follow else '')
    mu.section(b, 'r_hdri_turn', i18n.tr('HDRI Rotation'), x, width, fill, summary=summ,
               colour=mu.COLOURS['r_hdri_turn'])


CLASSES = (MCH_PG_HdriTurn, MCH_OT_hdri_turn_reset, MCH_OT_hdri_turn_follow, MCH_OT_hdri_turn_lights)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_hdri_turn = PointerProperty(type=MCH_PG_HdriTurn)
    if _check not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_check)


def unregister():
    if _check in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_check)
    if hasattr(bpy.types.Scene, 'mch_hdri_turn'):
        del bpy.types.Scene.mch_hdri_turn
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
