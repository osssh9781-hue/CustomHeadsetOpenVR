"""0.24.95 Work Scene (user: "블렌더에서 모델링 하니까 화면이 지저분해져서", "그룹 안에 넣은 거 콜렉션 인스턴스로 복사하면 그룹
원본 수정하면 인스턴스도 변경되잖아", "그렇게 버튼 만들어 줘").

A clean place to model one group, live with the rest:

* **Work Scene** - the selected group (or the selection, made a group first) goes to a scene of its own ("Work -
  <group>", the main scene's settings and world, nothing else in it) shown in a new window; where it was, a
  Collection Instance of it stays (the same place) - every edit in the work scene shows there at once.
* **Main / Work** - the window shows the other one of the two (one window is enough).
* **Bring Back** - the group back in the main scene where it was (moved as the instance was moved there), the
  instance and the work scene (and its window) gone.

Plain Blender data (a scene, a collection instance) - the file opens without the add-on."""
from __future__ import annotations

import json

import bpy
from mathutils import Matrix, Vector

WORK = 'mch_work'          # on the group's collection: where it came from (JSON)
OF = 'mch_work_of'         # on the instance and on the work scene: the group's collection
_CLOSE = []                # windows to close after the operator (a window cannot close itself while it runs one)


def current(context):
    """The group collection being worked on that this context is about: the work scene's, the active instance's,
    or the active group's (when it is in a work scene)."""
    sc = getattr(context, 'scene', None)
    if sc is not None and sc.get(OF):
        c = bpy.data.collections.get(sc[OF])
        if c is not None and c.get(WORK):
            return c
    ob = getattr(context, 'active_object', None)
    if ob is not None and ob.get(OF):
        c = bpy.data.collections.get(ob[OF])
        if c is not None and c.get(WORK):
            return c
    return None


def info(coll):
    try:
        return json.loads(coll.get(WORK, '{}'))
    except (TypeError, ValueError):
        return {}


def in_work_scene(context):
    sc = getattr(context, 'scene', None)
    return sc is not None and bool(sc.get(OF))


def _copy_props(src, dst, depth=0):
    """The add-on's settings of one scene into another (numbers, switches, choices, text; nested groups)."""
    if depth > 4:
        return
    for p in src.bl_rna.properties:
        k = p.identifier
        if k in {'rna_type', 'name'}:
            continue
        try:
            if p.type == 'POINTER':
                sub, dsub = getattr(src, k), getattr(dst, k)
                if sub is not None and dsub is not None and isinstance(sub, bpy.types.PropertyGroup):
                    _copy_props(sub, dsub, depth + 1)
            elif p.type != 'COLLECTION' and not p.is_readonly:
                setattr(dst, k, getattr(src, k))
        except (AttributeError, TypeError, ValueError, RuntimeError):
            pass


def _new_scene(main, name):
    ws = bpy.data.scenes.new(name)
    ws.world = main.world
    for k in ('system', 'scale_length', 'length_unit', 'mass_unit', 'system_rotation'):
        try:
            setattr(ws.unit_settings, k, getattr(main.unit_settings, k))
        except (AttributeError, TypeError):
            pass
    try:
        ws.render.engine = main.render.engine
    except TypeError:
        pass
    for p in bpy.types.Scene.bl_rna.properties:          # (Mecha Lab's own settings: the same tools, the same sizes)
        k = p.identifier
        if k.startswith('mch') and p.type == 'POINTER':
            try:
                a, b = getattr(main, k), getattr(ws, k)
            except AttributeError:
                continue
            if isinstance(a, bpy.types.PropertyGroup):
                _copy_props(a, b)
    ws.cursor.location = main.cursor.location
    return ws


def _show(context, scene, new_window):
    """``scene`` shown: in a new window (the old one keeps its scene), else in this one."""
    win = getattr(context, 'window', None)
    if win is None:
        return False
    if new_window:
        before = set(context.window_manager.windows[:])
        try:
            bpy.ops.wm.window_new()
        except RuntimeError:
            pass
        made = [w for w in context.window_manager.windows if w not in before]
        if made:
            made[-1].scene = scene
            return True
    win.scene = scene
    return True


def send(context, g, new_window=True):
    """Group ``g`` to a work scene of its own, a live instance of it where it was.  Returns the work scene."""
    from . import groups
    while groups.group_of(g.parent) is not None:         # (a group inside a group: the outer one goes)
        g = groups.group_of(g.parent)
    coll = groups.collection_of(g)
    if coll is None or coll.get(WORK):
        return None
    main = context.scene
    pc = groups.parent_collection(context, coll)
    master = pc == main.collection
    handle_colls = ['' if c == main.collection else c.name for c in g.users_collection]
    L = g.matrix_world.translation.copy()
    ws = _new_scene(main, f'Work - {g.name}')
    ws.collection.children.link(coll)
    ws.collection.objects.link(g)
    for c in list(g.users_collection):
        if c != ws.collection:
            c.objects.unlink(g)
    pc.children.unlink(coll)
    offset = tuple(coll.instance_offset)
    coll.instance_offset = L
    inst = bpy.data.objects.new(f'{g.name} (Work)', None)
    inst.instance_type = 'COLLECTION'
    inst.instance_collection = coll
    inst.empty_display_type = 'PLAIN_AXES'
    inst.empty_display_size = max(0.05, max(g.empty_display_size, 0.1))
    pc.objects.link(inst)
    inst.matrix_world = Matrix.Translation(L)
    inst[OF] = coll.name
    ws[OF] = coll.name
    coll[WORK] = json.dumps(dict(main=main.name, ws=ws.name, pc='' if master else pc.name, inst=inst.name,
                                 handle=g.name, handle_colls=handle_colls, offset=offset,
                                 inst_m=[list(r) for r in inst.matrix_world]))
    for o in context.selected_objects:
        o.select_set(False)
    inst.select_set(True)
    context.view_layer.objects.active = inst
    lay = ws.view_layers[0]
    try:
        g.select_set(True, view_layer=lay)
        lay.objects.active = g
    except (RuntimeError, TypeError):
        pass
    _show(context, ws, new_window)
    return ws


def _close_later():
    wm = bpy.context.window_manager
    while _CLOSE:
        w = _CLOSE.pop()
        if w in wm.windows[:] and len(wm.windows) > 1:
            try:
                with bpy.context.temp_override(window=w):
                    bpy.ops.wm.window_close()
            except (RuntimeError, TypeError):
                pass
    return None


def bring_back(context, coll):
    """The group of collection ``coll`` back in its main scene (moved as its instance was), the instance and the
    work scene gone.  Returns the group handle."""
    d = info(coll)
    main = bpy.data.scenes.get(d.get('main', ''))
    ws = bpy.data.scenes.get(d.get('ws', ''))
    if main is None:
        return None
    g = bpy.data.objects.get(d.get('handle', ''))
    inst = bpy.data.objects.get(d.get('inst', ''))
    pc = bpy.data.collections.get(d.get('pc', '')) if d.get('pc') else main.collection
    pc = pc or main.collection
    if inst is not None and g is not None and d.get('inst_m'):
        try:
            D = inst.matrix_world @ Matrix(d['inst_m']).inverted()
        except ValueError:
            D = Matrix.Identity(4)
        g.matrix_world = D @ g.matrix_world               # (the instance moved there: the group goes there)
    if ws is not None and coll.name in ws.collection.children:
        ws.collection.children.unlink(coll)
    if coll.name not in pc.children:
        pc.children.link(coll)
    if g is not None:
        for name in d.get('handle_colls') or ['']:
            c = main.collection if not name else bpy.data.collections.get(name)
            if c is not None and g.name not in c.objects:
                c.objects.link(g)
        if ws is not None and g.name in ws.collection.objects:
            ws.collection.objects.unlink(g)
    try:
        coll.instance_offset = Vector(d.get('offset') or (0.0, 0.0, 0.0))
    except (TypeError, ValueError):
        pass
    if inst is not None:
        bpy.data.objects.remove(inst)
    if WORK in coll.keys():
        del coll[WORK]
    wm = context.window_manager
    cur = getattr(context, 'window', None)
    if ws is not None:
        for w in wm.windows:
            if w.scene == ws:
                w.scene = main
                if len(wm.windows) > 1 and w != cur:
                    _CLOSE.append(w)
                elif w == cur and len(wm.windows) > 1 and \
                        any(o != w and o.scene == main for o in wm.windows):
                    _CLOSE.append(w)                      # (the work window: closed after this click)
        if not any(w.scene == ws for w in wm.windows):
            bpy.data.scenes.remove(ws)
    if _CLOSE:
        bpy.app.timers.register(_close_later, first_interval=0.05)
    if g is not None:
        lay = main.view_layers[0]
        for o in main.objects:                            # (not the view layer's list: the instance just went)
            try:
                if o.select_get(view_layer=lay):
                    o.select_set(False, view_layer=lay)
            except RuntimeError:
                pass
        try:
            g.select_set(True, view_layer=lay)
            lay.objects.active = g
        except (RuntimeError, TypeError):
            pass
    return g


def switch(context):
    """This window: the work scene <-> its main scene."""
    coll = current(context)
    if coll is None or getattr(context, 'window', None) is None:
        return False
    d = info(coll)
    sc = context.scene
    other = bpy.data.scenes.get(d.get('main' if sc.get(OF) else 'ws', ''))
    if other is None:
        return False
    context.window.scene = other
    return True


class MCH_OT_work_scene(bpy.types.Operator):
    """Work Scene: the selected group (or the selection, made a group) in a clean scene of its own, in a new window -
    a live instance of it stays where it was.  Main / Work: this window shows the other one.  Bring Back: the group
    back where it was (where the instance was moved to), the work scene gone"""
    bl_idname = 'mch.work_scene'
    bl_label = 'Work Scene'
    bl_options = {'REGISTER', 'UNDO'}
    action: bpy.props.EnumProperty(items=(('SEND', 'Work Scene', 'The group in a clean scene of its own'),
                                          ('SWITCH', 'Main / Work', 'This window shows the other scene'),
                                          ('BACK', 'Bring Back', 'The group back in the main scene')),
                                   default='SEND')
    new_window: bpy.props.BoolProperty(name='New Window', default=True,
                                       description='Show the work scene in a new window (else in this one)')

    def execute(self, context):
        from . import groups
        if context.mode != 'OBJECT':
            self.report({'WARNING'}, 'Work Scene: Object Mode only')
            return {'CANCELLED'}
        if self.action == 'SWITCH':
            if not switch(context):
                self.report({'WARNING'}, 'Main / Work: select a work instance (or be in a work scene)')
                return {'CANCELLED'}
            return {'FINISHED'}
        if self.action == 'BACK':
            coll = current(context)
            if coll is None:
                self.report({'WARNING'}, 'Bring Back: select a work instance (or be in a work scene)')
                return {'CANCELLED'}
            g = bring_back(context, coll)
            self.report({'INFO'}, f'"{g.name if g else coll.name}" back in the main scene')
            return {'FINISHED'}
        coll = current(context)
        if coll is not None:                               # (already in a work scene: show it)
            d = info(coll)
            ws = bpy.data.scenes.get(d.get('ws', ''))
            if ws is not None and context.scene != ws:
                if not any(w.scene == ws for w in context.window_manager.windows):
                    _show(context, ws, self.new_window)
                return {'FINISHED'}
            self.report({'INFO'}, 'Already in the work scene (Main / Work: back to the main scene)')
            return {'CANCELLED'}
        g = groups.group_of(context.active_object)
        if g is None:
            objs = [o for o in context.selected_objects if not o.get(OF)]
            if not objs:
                self.report({'WARNING'}, 'Work Scene: select a group or the parts to work on')
                return {'CANCELLED'}
            g = groups.create(context, objs, 'Work Group')
        ws = send(context, g, self.new_window)
        if ws is None:
            self.report({'WARNING'}, 'Work Scene: this group cannot go (it is already in a work scene)')
            return {'CANCELLED'}
        self.report({'INFO'}, f'"{ws.name}": model here - the main scene shows it live (Bring Back when done)')
        return {'FINISHED'}


def toolbar_cells(context):
    """[(label, action, ok)] for the Layers panel's second row."""
    obj_mode = getattr(context, 'mode', 'OBJECT') == 'OBJECT'
    coll = current(context)
    if coll is not None:
        here = in_work_scene(context)
        return [('Main' if here else 'Work', ('op', 'mch.work_scene', {'action': 'SWITCH'}), obj_mode),
                ('Bring Back', ('op', 'mch.work_scene', {'action': 'BACK'}), obj_mode)]
    sel = bool(getattr(context, 'selected_objects', None))
    return [('Work Scene', ('op', 'mch.work_scene', {'action': 'SEND'}), obj_mode and sel)]


def draw(layout, context):
    coll = current(context)
    row = layout.row(align=True)
    if coll is None:
        row.operator('mch.work_scene', text='Work Scene', icon='WINDOW').action = 'SEND'
        return
    here = in_work_scene(context)
    row.operator('mch.work_scene', text='Main' if here else 'Work', icon='SCENE_DATA').action = 'SWITCH'
    row.operator('mch.work_scene', text='Bring Back', icon='LOOP_BACK').action = 'BACK'


CLASSES = (MCH_OT_work_scene,)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
