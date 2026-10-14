"""Non-destructive mesh mirrors and linked collection-instance symmetry rigs.

Independently authored for Mecha Lab. Blender 4.3+ APIs.
"""
import math
import time

import bpy
from mathutils import Matrix, Vector
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty

MOD_NAME = 'MCH_Mirror'
RIG_TAG = '_mch_collection_mirror_role'


def _mesh_filter(self, obj):
    return obj.type == 'MESH'


def _valid_collection(self, coll):
    return coll is not None


class MCH_PG_Mirror(bpy.types.PropertyGroup):
    space: EnumProperty(name='Axis Space', items=[
        ('WORLD', 'World', 'Mirror across global X/Y/Z planes'),
        ('LOCAL', 'Local', 'Mirror around the mesh object origin and local axes')], default='WORLD')
    center: EnumProperty(name='Mirror Plane Center', items=[
        ('ORIGIN', 'World Origin', 'Plane passes through (0, 0, 0)'),
        ('CURSOR', '3D Cursor', 'Use current cursor position; global axis directions remain unchanged')], default='ORIGIN')
    x: BoolProperty(name='X', default=True)
    y: BoolProperty(name='Y', default=False)
    z: BoolProperty(name='Z', default=False)
    bisect: BoolProperty(name='Bisect', default=True,
                         description='Cut the mesh on the mirror plane first, so the side you lean the mouse to is '
                                     'replaced by a copy of the other side (off: the whole mesh is copied)')
    flip_x: BoolProperty(name='Copy toward +X', default=False, description='Mirror copies toward +X (off: toward -X)')
    flip_y: BoolProperty(name='Copy toward +Y', default=False)
    flip_z: BoolProperty(name='Copy toward +Z', default=False)
    auto_start: BoolProperty(name='Start when Mirror is picked', default=True,
                             description='Picking the Mirror tool with a mesh selected starts the live mirror at once: '
                                         'lean the mouse toward the side to copy to, Enter = apply')
    clipping: BoolProperty(name='Clipping', default=True, description='Prevent vertices crossing the mirror plane while editing')
    merge: BoolProperty(name='Merge', default=True)
    merge_distance: FloatProperty(name='Merge Distance', default=0.001, min=0.0, max=1.0, precision=5)
    source_collection: PointerProperty(name='Parts Collection', type=bpy.types.Collection)
    collection_axis: EnumProperty(name='Pair Axis', items=[
        ('X', 'World X', 'Reflect assembly instances across X plane'),
        ('Y', 'World Y', 'Reflect assembly instances across Y plane'),
        ('Z', 'World Z', 'Reflect assembly instances across Z plane')], default='X')
    collection_center: EnumProperty(name='Pair Center', items=[
        ('ORIGIN', 'World Origin', 'Use world (0,0,0) plane'),
        ('CURSOR', '3D Cursor', 'Use current cursor location as fixed mirror plane')], default='ORIGIN')
    collection_initial_offset: FloatProperty(
        name='Start Offset', default=1.0, min=0.001, soft_max=5.0,
        description='When cursor is on the mirror center, place MASTER this far onto the positive axis')


def _remove_unused_pivot(pivot):
    if pivot is None or pivot.name not in bpy.data.objects or not pivot.get('_mch_world_pivot'):
        return
    if not any(m.type == 'MIRROR' and m.mirror_object == pivot
               for ob in bpy.data.objects for m in ob.modifiers):
        bpy.data.objects.remove(pivot, do_unlink=True)


def _activate(context, ob):
    for selected in context.selected_objects:
        selected.select_set(False)
    if ob.hide_get():
        ob.hide_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob


class MCH_OT_mesh_mirror(bpy.types.Operator):
    bl_idname = 'mch.mesh_mirror'
    bl_label = 'Create / Update Mesh Mirror'
    bl_description = 'Add or update a live Mirror modifier; world mode uses a fixed world-aligned pivot Empty'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(context.selected_objects) and any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        p = context.scene.mch_mirror
        if not any((p.x, p.y, p.z)):
            self.report({'WARNING'}, 'Enable at least one mirror axis')
            return {'CANCELLED'}
        count = 0
        scene = context.scene
        targets = [o for o in context.selected_objects if o.type == 'MESH' and o.library is None]
        for obj in targets:
            if setup_mirror(obj, p, scene) is None:
                self.report({'WARNING'}, f'{obj.name}: existing name belongs to another modifier')
                continue
            count += 1
        if count:
            self.report({'INFO'}, f'Live mirror updated on {count} mesh(es)')
            return {'FINISHED'}
        return {'CANCELLED'}


def setup_mirror(obj, p, scene, axes=None, flips=None):
    """Create / update the Mecha Mirror modifier of ``obj`` from the panel
    settings (``axes`` / ``flips`` override the X/Y/Z toggles).  Returns the
    modifier, or None when the name belongs to another modifier type."""
    mod = obj.modifiers.get(MOD_NAME)
    if mod and mod.type != 'MIRROR':
        return None
    old_pivot = mod.mirror_object if mod else None
    if mod is None:
        mod = obj.modifiers.new(MOD_NAME, 'MIRROR')
    if p.space == 'WORLD':
        pivot = old_pivot if old_pivot and old_pivot.get('_mch_world_pivot') else None
        if pivot is None:
            pivot = bpy.data.objects.new(f'MCH World Pivot - {obj.name}', None)
            scene.collection.objects.link(pivot)
            pivot['_mch_world_pivot'] = True
            pivot.empty_display_type = 'ARROWS'
            pivot.empty_display_size = 0.16
            pivot.hide_render = True
        pivot.matrix_world = Matrix.Translation(
            Vector(scene.cursor.location) if p.center == 'CURSOR' else Vector((0, 0, 0)))
        mod.mirror_object = pivot
    else:
        mod.mirror_object = None
        _remove_unused_pivot(old_pivot)
    axes = (p.x, p.y, p.z) if axes is None else tuple(bool(a) for a in axes)
    flips = (p.flip_x, p.flip_y, p.flip_z) if flips is None else tuple(bool(f) for f in flips)
    for index in range(3):
        mod.use_axis[index] = axes[index]
        mod.use_bisect_axis[index] = p.bisect and axes[index]
        mod.use_bisect_flip_axis[index] = flips[index]
    mod.use_clip = p.clipping
    mod.use_mirror_merge = p.merge
    mod.merge_threshold = p.merge_distance
    return mod


# -----------------------------------------------------------------------------
# HardOps-style lean mirror: lean the mouse toward the side to copy to.
# Pure logic (MirrorLeanLogic) + operator; tests drive it with fake events.
# -----------------------------------------------------------------------------

DEAD_PX = 18.0          # mouse this close to the centre: keep the current axis
_MIRROR_ATTRS = ('use_axis', 'use_bisect_axis', 'use_bisect_flip_axis')


def mirror_frame(obj, p, scene):
    """(plane origin, [x, y, z] unit axes) of the mirror for ``obj``."""
    if p.space == 'LOCAL':
        m = obj.matrix_world
        rot = m.to_3x3().normalized()
        return m.translation.copy(), [(rot @ Vector(e)).normalized() for e in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    origin = Vector(scene.cursor.location) if p.center == 'CURSOR' else Vector((0.0, 0.0, 0.0))
    return origin, [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))]


def gesture_base(projector, origin, center):
    """World point seen at the screen ``center`` at the depth of ``origin`` (axis directions are
    measured there, so the gesture works wherever the origin is - even off screen)."""
    o, d = projector.ray(center)
    o, d = Vector(o), Vector(d).normalized()
    dist = (Vector(origin) - o).dot(d)
    if dist <= 1e-6:
        dist = max(1.0, (Vector(origin) - o).length)
    return o + d * dist


def lean_pick(projector, origin, axes, mouse, length=1.0, dead=DEAD_PX, center=None):
    """(axis index, sign) whose screen direction best matches the mouse offset
    from the plane centre (or from the gesture ``center`` on screen, 0.23.2); sign
    +1 = the mouse leans toward +axis.  None when the mouse is inside the dead zone
    or the centre is not on screen."""
    if center is not None:
        origin = gesture_base(projector, origin, center)
    c = projector.to_screen(origin)
    if c is None:
        return None
    if center is not None:
        c = tuple(center)
    vx, vy = mouse[0] - c[0], mouse[1] - c[1]
    vl = math.hypot(vx, vy)
    if vl < dead:
        return None
    best = None
    for i, a in enumerate(axes):
        e = projector.to_screen(origin + a * length)
        if e is None:
            continue
        dx, dy = e[0] - c[0], e[1] - c[1]
        dl = math.hypot(dx, dy)
        if dl < 1e-3:          # axis points straight at the viewer
            continue
        cos = (vx * dx + vy * dy) / (vl * dl)
        if best is None or abs(cos) > abs(best[2]):
            best = (i, 1 if cos > 0 else -1, cos)
    return None if best is None else (best[0], best[1])


def _snapshot(obj):
    mod = obj.modifiers.get(MOD_NAME)
    if mod is None or mod.type != 'MIRROR':
        return None
    d = {a: tuple(getattr(mod, a)) for a in _MIRROR_ATTRS}
    d.update(mirror_object=mod.mirror_object, use_clip=mod.use_clip, use_mirror_merge=mod.use_mirror_merge,
             merge_threshold=mod.merge_threshold)
    return d


def _restore(obj, snap):
    mod = obj.modifiers.get(MOD_NAME)
    if snap is None:
        if mod is not None and mod.type == 'MIRROR':
            pivot = mod.mirror_object
            obj.modifiers.remove(mod)
            _remove_unused_pivot(pivot)
        return
    if mod is None:
        mod = obj.modifiers.new(MOD_NAME, 'MIRROR')
    for a in _MIRROR_ATTRS:
        for i, v in enumerate(snap[a]):
            getattr(mod, a)[i] = v
    current = mod.mirror_object
    mod.mirror_object = snap['mirror_object']
    if current is not None and current != snap['mirror_object']:
        _remove_unused_pivot(current)
    mod.use_clip, mod.use_mirror_merge = snap['use_clip'], snap['use_mirror_merge']
    mod.merge_threshold = snap['merge_threshold']


class MirrorLeanLogic:
    """Modal: the live mirror appears at once; moving the mouse picks the axis
    (and the side to copy to).  LMB = keep live, Shift+LMB = add this axis and
    keep going, Enter / Space = apply (bake), X / Y / Z = toggle an axis,
    B = bisect on/off, Esc / RMB = cancel (restore)."""

    NAV = {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'WHEELINMOUSE', 'WHEELOUTMOUSE', 'TRACKPADPAN',
           'TRACKPADZOOM', 'MOUSEROTATE', 'NDOF_MOTION', 'NUMPAD_1', 'NUMPAD_2', 'NUMPAD_3', 'NUMPAD_4',
           'NUMPAD_5', 'NUMPAD_6', 'NUMPAD_7', 'NUMPAD_8', 'NUMPAD_9', 'NUMPAD_PERIOD'}

    def start(self, context, region, projector, mouse_xy):
        scene = context.scene
        self.p = scene.mch_mirror
        self.region = region
        # 0.23.2: the lean gesture lives at the bottom centre of the view (visible wherever the origin is)
        self.center = (region.width / 2.0, region.height * 0.18)
        self.projector = projector
        self.target_names = [o.name for o in context.selected_objects if o.type == 'MESH' and o.library is None]
        if not self.target_names:
            return False
        self.snaps = {n: _snapshot(bpy.data.objects[n]) for n in self.target_names}
        self.axes = [self.p.x, self.p.y, self.p.z]
        self.flips = [self.p.flip_x, self.p.flip_y, self.p.flip_z]
        self.locked = [False, False, False]
        if not any(self.axes):
            self.axes[0] = True
        self.current = None
        self.mouse = mouse_xy
        self._apply_live(scene)               # the mirror is live immediately
        return True

    def _targets(self):
        return [bpy.data.objects[n] for n in self.target_names if n in bpy.data.objects]

    def frame(self, scene):
        obs = self._targets()
        origin, axes = mirror_frame(obs[0], self.p, scene)
        size = max(max(obs[0].dimensions), 0.2)
        return origin, axes, size

    def _apply_live(self, scene):
        for ob in self._targets():
            setup_mirror(ob, self.p, scene, self.axes, self.flips)

    def on_move(self, scene, xy):
        self.mouse = xy
        if not self._targets():
            return
        origin, axes, size = self.frame(scene)
        pick = lean_pick(self.projector, origin, axes, xy, size * 0.6, center=self.center)
        if pick is None or pick == self.current:
            return
        self.current = pick
        i, sign = pick
        self.axes = [self.locked[k] for k in range(3)]
        self.axes[i] = True
        self.flips[i] = sign > 0              # flip ON keeps the - side and copies toward +
        self._apply_live(scene)

    def toggle_axis(self, scene, i):
        self.locked[i] = not self.locked[i]
        self.axes[i] = self.locked[i] or (self.current is not None and self.current[0] == i)
        if not any(self.axes):
            self.axes[i] = True
            self.locked[i] = True
        self._apply_live(scene)

    def lock_current(self):
        if self.current is not None:
            self.locked[self.current[0]] = True

    def store_settings(self):
        p = self.p
        p.x, p.y, p.z = self.axes
        p.flip_x, p.flip_y, p.flip_z = self.flips

    def finish_live(self, scene):
        self.store_settings()
        return f'Live mirror on {", ".join(self.target_names)}: {self.describe()} (Apply in the panel or Enter next time)'

    def finish_apply(self, context):
        from . import core_geometry
        self.store_settings()
        policy = getattr(getattr(context.scene, 'mch_cut', None), 'shared_mesh', 'SINGLE')
        done, failed = [], []
        for ob in self._targets():
            mod = ob.modifiers.get(MOD_NAME)
            pivot = mod.mirror_object if mod else None
            from . import station_primitive
            station_primitive.freeze(ob)            # keep the baked mirror (no rebuild over it)
            try:
                core_geometry.apply_single_modifier(context, ob, mod, policy)
                done.append(ob.name)
            except (RuntimeError, TypeError, ValueError, core_geometry.CutError) as ex:
                failed.append(f'{ob.name} ({ex})')
            _remove_unused_pivot(pivot)
        return f'Mirror applied ({self.describe()}): {", ".join(done)}' + \
            (' | FAILED: ' + '; '.join(failed) if failed else '')

    def restore_all(self):
        for n, snap in self.snaps.items():
            ob = bpy.data.objects.get(n)
            if ob is not None:
                _restore(ob, snap)

    def describe(self):
        out = []
        for i, axis in enumerate('XYZ'):
            if self.axes[i]:
                out.append(('+' if self.flips[i] else '-') + axis if self.p.bisect else axis)
        return ' '.join(out) + ('' if self.p.bisect else ' (no bisect)')

    def handle(self, context, event):
        """Returns 'RUN', 'PASS', 'LIVE', 'APPLY' or 'CANCEL'."""
        et, ev = event.type, event.value
        scene = context.scene
        if et in self.NAV or (et in {'LEFTMOUSE', 'MIDDLEMOUSE'} and getattr(event, 'alt', False)):
            return 'PASS'
        if et in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            self.on_move(scene, (event.mouse_x - self.region.x, event.mouse_y - self.region.y))
            return 'RUN'
        if ev != 'PRESS':
            return 'RUN'
        if et in {'ESC', 'RIGHTMOUSE'}:
            return 'CANCEL'
        if et in {'RET', 'NUMPAD_ENTER', 'SPACE'}:
            return 'APPLY'
        if et == 'LEFTMOUSE':
            if getattr(event, 'shift', False):
                self.lock_current()
                return 'RUN'
            return 'LIVE'
        if et in {'X', 'Y', 'Z'}:
            self.toggle_axis(scene, 'XYZ'.index(et))
            return 'RUN'
        if et == 'B':
            self.p.bisect = not self.p.bisect
            self._apply_live(scene)
            return 'RUN'
        return 'RUN'


def draw_lean_overlay(op):
    try:
        import blf
        import gpu
        from .cut_engine import _draw_lines, _draw_squares, _shader
        scene = bpy.context.scene
        if not op._targets():
            return
        origin, axes, size = op.frame(scene)
        c = tuple(op.center)
        base = gesture_base(op.projector, origin, c)
        cb = op.projector.to_screen(base)
        if cb is None:
            return
        sh = _shader()
        gpu.state.blend_set('ALPHA')
        colors = ((1.0, 0.35, 0.35), (0.45, 1.0, 0.45), (0.45, 0.65, 1.0))
        for i, a in enumerate(axes):
            tip = op.projector.to_screen(base + a * size * 0.6)
            if tip is None:
                continue
            dx, dy = tip[0] - cb[0], tip[1] - cb[1]
            dl = math.hypot(dx, dy)
            if dl < 1e-3:
                continue
            for sign in (1, -1):
                e = (c[0] + dx / dl * 80.0 * sign, c[1] + dy / dl * 80.0 * sign)
                on = op.axes[i] and ((op.flips[i] and sign > 0) or (not op.flips[i] and sign < 0) or not op.p.bisect)
                col = (*colors[i], 1.0 if on else 0.35)
                _draw_lines(sh, [c, e], col, width=4.0 if on else 1.5)
                _draw_squares(sh, [e], col, 6.0 if on else 3.0)
        _draw_squares(sh, [c], (1, 1, 1, 0.9), 4.0)
        gpu.state.blend_set('NONE')
        if op.mouse is not None:
            blf.size(0, 14)
            blf.color(0, 1, 1, 1, 0.95)
            blf.position(0, c[0] - 60, c[1] - 110, 0)
            blf.draw(0, 'Mirror ' + op.describe())
    except Exception:          # never break viewport drawing
        pass


class MCH_OT_mirror_lean(MirrorLeanLogic, bpy.types.Operator):
    bl_idname = 'mch.mirror_lean'
    bl_label = 'Symmetry (lean to copy)'
    bl_description = ('Live mirror at once; lean the mouse toward the side to copy to. Enter = apply, '
                      'click = keep live, Shift+click = add axis, X/Y/Z = axes, B = bisect, Esc = cancel')
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    keep_live: bpy.props.BoolProperty(default=False, options={'SKIP_SAVE'},
                                      description='Mirror button: Enter / click keep the live mirror (no apply)')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(o.type == 'MESH' for o in context.selected_objects)

    def invoke(self, context, event):
        area = context.area
        region = context.region
        if area is None or area.type != 'VIEW_3D' or region is None or region.type != 'WINDOW':
            self.report({'WARNING'}, 'Run Mirror from the 3D View')
            return {'CANCELLED'}
        from . import core_geometry as cg
        projector = cg.Projector(region, context.region_data)
        xy = (event.mouse_x - region.x, event.mouse_y - region.y)
        if not self.start(context, region, projector, xy):
            return {'CANCELLED'}
        self._handle = bpy.types.SpaceView3D.draw_handler_add(draw_lean_overlay, (self,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        self._area = area
        self._status(context)
        area.tag_redraw()
        return {'RUNNING_MODAL'}

    def _status(self, context, clear=False):
        try:
            context.workspace.status_text_set(None if clear else
                                              'Mirror: lean the mouse (from the bottom centre) toward the side to copy '
                                              'to | Enter / Space: ' + ('keep live' if self.keep_live else 'APPLY') +
                                              ' | Click: keep live | Shift+Click: add axis | X Y Z: axes | '
                                              'B: bisect | Esc / RMB: cancel')
        except (AttributeError, ReferenceError):
            pass

    def _end(self, context):
        if getattr(self, '_handle', None) is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None
        self._status(context, clear=True)
        try:
            self._area.tag_redraw()
        except (AttributeError, ReferenceError):
            pass

    def modal(self, context, event):
        r = self.handle(context, event)
        if r == 'PASS':
            return {'PASS_THROUGH'}
        if r == 'RUN':
            self._area.tag_redraw()
            return {'RUNNING_MODAL'}
        self._end(context)
        if r == 'CANCEL':
            self.restore_all()
            self.report({'INFO'}, 'Mirror cancelled')
            return {'CANCELLED'}
        if r == 'APPLY' and not self.keep_live:
            self.report({'INFO'}, self.finish_apply(context))
            return {'FINISHED'}
        self.report({'INFO'}, self.finish_live(context.scene))
        return {'FINISHED'}


def start_lean_mirror(context):
    """Picking the Mirror tool: start the lean mirror in the biggest 3D View
    (the tool list may be another editor).  Returns True when started."""
    if not getattr(context.scene.mch_mirror, 'auto_start', True) or context.mode != 'OBJECT' or \
            not any(o.type == 'MESH' for o in context.selected_objects):
        return False
    win = context.window
    screen = win.screen if win is not None else None
    if screen is None:
        return False
    areas = sorted((a for a in screen.areas if a.type == 'VIEW_3D'), key=lambda a: -a.width * a.height)
    for area in areas:
        region = next((r for r in area.regions if r.type == 'WINDOW'), None)
        if region is None:
            continue
        with context.temp_override(window=win, screen=screen, area=area, region=region):
            return bpy.ops.mch.mirror_lean('INVOKE_DEFAULT') == {'RUNNING_MODAL'}
    return False


def _mirror_targets(context):
    """F01: every selected mesh carrying the Mecha mirror (else the active one)."""
    obs = [o for o in context.selected_objects if o.type == 'MESH' and o.modifiers.get(MOD_NAME)]
    ob = context.active_object
    if not obs and ob is not None and ob.type == 'MESH' and ob.modifiers.get(MOD_NAME):
        obs = [ob]
    return obs


class MCH_OT_mesh_mirror_apply(bpy.types.Operator):
    bl_idname = 'mch.mesh_mirror_apply'
    bl_label = 'Apply Mesh Mirror'
    bl_description = 'Bake the Mecha mirror into every selected mesh that has one (Alt+D twins keep their mesh)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(_mirror_targets(context))

    def execute(self, context):
        from . import core_geometry
        policy = getattr(getattr(context.scene, 'mch_cut', None), 'shared_mesh', 'SINGLE')
        done, failed, helpers = [], [], set()
        for ob in _mirror_targets(context):
            mod = ob.modifiers.get(MOD_NAME)
            if not mod or mod.type != 'MIRROR':
                continue
            if ob.library or (ob.data and ob.data.library):
                failed.append(f'{ob.name} (linked library mesh)')
                continue
            helper = mod.mirror_object
            from . import station_primitive
            station_primitive.freeze(ob)              # the next rebuild would drop the mirrored half
            try:
                core_geometry.apply_single_modifier(context, ob, mod, policy)
                done.append(ob.name)
                if helper is not None:
                    helpers.add(helper.name)
            except (RuntimeError, TypeError, ValueError, core_geometry.CutError) as exc:
                failed.append(f'{ob.name} ({exc})')
        for name in helpers:
            _remove_unused_pivot(bpy.data.objects.get(name))
        if not done:
            self.report({'ERROR'}, 'Mirror not applied: ' + ('; '.join(failed) or 'no Mecha mirror found'))
            return {'CANCELLED'}
        msg = f'Mirror applied: {", ".join(done)}'
        if failed:
            msg += ' | FAILED: ' + '; '.join(failed)
        self.report({'WARNING' if failed else 'INFO'}, msg)
        return {'FINISHED'}


class MCH_OT_mesh_mirror_remove(bpy.types.Operator):
    bl_idname = 'mch.mesh_mirror_remove'
    bl_label = 'Remove Mesh Mirror'
    bl_description = 'Remove the Mecha mirror from every selected mesh (geometry unchanged)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(_mirror_targets(context))

    def execute(self, context):
        helpers = set()
        names = []
        for obj in _mirror_targets(context):
            mod = obj.modifiers.get(MOD_NAME)
            if mod.type == 'MIRROR' and mod.mirror_object is not None:
                helpers.add(mod.mirror_object.name)
            obj.modifiers.remove(mod)
            names.append(obj.name)
        for name in helpers:
            _remove_unused_pivot(bpy.data.objects.get(name))
        self.report({'INFO'}, 'Mirror removed: ' + ', '.join(names))
        return {'FINISHED'}


def _tagged_empty(scene, name, role):
    ob = bpy.data.objects.new(name, None)
    scene.collection.objects.link(ob)
    ob[RIG_TAG] = role
    ob.empty_display_size = 0.15
    ob.empty_display_type = 'SPHERE' if role == 'PIVOT' else 'PLAIN_AXES'
    ob.hide_render = True
    return ob


def _instance(scene, coll, name, role):
    ob = _tagged_empty(scene, name, role)
    ob.instance_type = 'COLLECTION'
    ob.instance_collection = coll
    return ob


class MCH_OT_collection_mirror(bpy.types.Operator):
    bl_idname = 'mch.collection_mirror'
    bl_label = 'Create Linked Collection Mirror'
    bl_description = 'Two linked collection instances; moving or rotating MASTER updates mirrored side using world-axis reflection'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.scene is not None

    def execute(self, context):
        s = context.scene
        p = s.mch_mirror
        coll = p.source_collection
        if not coll:
            self.report({'WARNING'}, 'Choose a source Collection first')
            return {'CANCELLED'}
        # Collection instances must never point to a collection containing the instance rig.
        # All rig controls live in the scene root, not inside source collection.
        if coll == s.collection:
            self.report({'ERROR'}, 'Cannot instance the scene root collection')
            return {'CANCELLED'}
        axis = 'XYZ'.index(p.collection_axis)
        center = Vector(s.cursor.location) if p.collection_center == 'CURSOR' else Vector((0, 0, 0))
        position = Vector(s.cursor.location)
        if (position - center).length < 1e-6:
            position[axis] += p.collection_initial_offset
        name = coll.name
        pivot = _tagged_empty(s, f'MCH {name} - Symmetry Center', 'PIVOT')
        pivot.location = center
        mirror_root = _tagged_empty(s, f'MCH {name} - Mirror Axis', 'REFLECTION')
        mirror_root.parent = pivot
        mirror_root.scale[axis] = -1.0
        mirror_root.hide_set(True)
        master = _instance(s, coll, f'MCH {name} - MASTER', 'MASTER')
        master.parent = pivot
        master.location = position - center
        master.rotation_euler = s.cursor.rotation_euler.copy()
        clone = _instance(s, coll, f'MCH {name} - MIRRORED', 'MIRRORED')
        clone.parent = mirror_root
        copy = clone.constraints.new('COPY_TRANSFORMS')
        copy.name = 'MCH_Symmetry_LiveLink'
        copy.target = master
        copy.owner_space = 'LOCAL'
        copy.target_space = 'LOCAL'
        copy.mix_mode = 'REPLACE'
        # Store object references as Blender native pointer properties (not fragile names).
        master['mch_mirror_axis'] = p.collection_axis
        _activate(context, master)
        context.view_layer.update()
        self.report({'INFO'}, 'Move/rotate MASTER instance; MIRRORED follows. Edit source collection to update both.')
        return {'FINISHED'}


class MCH_OT_collection_mirror_remove(bpy.types.Operator):
    bl_idname = 'mch.collection_mirror_remove'
    bl_label = 'Remove Collection Mirror Rig'
    bl_description = 'Remove only the generated mirror rig; source Collection and its mesh contents are left intact'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(context.active_object and context.active_object.get(RIG_TAG))

    def execute(self, context):
        ob = context.active_object
        role = ob.get(RIG_TAG)
        if role == 'PIVOT':
            pivot = ob
        elif role == 'REFLECTION':
            pivot = ob.parent
        elif role == 'MASTER':
            pivot = ob.parent
        elif role == 'MIRRORED':
            pivot = ob.parent.parent if ob.parent else None
        else:
            return {'CANCELLED'}
        if not pivot or pivot.get(RIG_TAG) != 'PIVOT':
            self.report({'WARNING'}, 'Could not locate generated symmetry rig')
            return {'CANCELLED'}
        owned = [o for o in bpy.data.objects if o.get(RIG_TAG) and
                 (o == pivot or o.parent == pivot or (o.parent and o.parent.parent == pivot))]
        for item in owned:
            bpy.data.objects.remove(item, do_unlink=True)
        self.report({'INFO'}, 'Mirror rig removed; source Collection preserved')
        return {'FINISHED'}


class MCH_PT_mirror(bpy.types.Panel):
    bl_icon = 'MOD_MIRROR'
    bl_parent_id = 'MCH_PT_main'
    bl_label = 'Mirror | World / Local / Collections'
    bl_idname = 'MCH_PT_mirror'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'


    @classmethod
    def poll(cls, context):
        from . import tool_state
        return tool_state.tool_is(context, 'MIRROR')

    def draw(self, context):
        layout = self.layout
        p = context.scene.mch_mirror
        layout.label(text='Mesh Mirror (non-destructive)')
        layout.prop(p, 'space', expand=True)
        if p.space == 'WORLD':
            layout.prop(p, 'center', expand=True)
        row = layout.row(align=True)
        row.prop(p, 'x', toggle=True)
        row.prop(p, 'y', toggle=True)
        row.prop(p, 'z', toggle=True)
        if p.bisect:
            row = layout.row(align=True)
            row.label(text='Copy toward +')
            row.prop(p, 'flip_x', text='X', toggle=True)
            row.prop(p, 'flip_y', text='Y', toggle=True)
            row.prop(p, 'flip_z', text='Z', toggle=True)
        r = layout.row()
        r.scale_y = 1.5
        r.operator('mch.mirror_lean', text='MIRROR: LEAN MOUSE TO SIDE', icon='MOUSE_MOVE')
        layout.prop(p, 'auto_start')
        col = layout.column(align=True)
        col.prop(p, 'bisect')
        col.prop(p, 'clipping')
        col.prop(p, 'merge')
        if p.merge:
            col.prop(p, 'merge_distance')
        layout.operator('mch.mesh_mirror', text='CREATE / UPDATE MIRROR', icon='MOD_MIRROR')
        ob = context.active_object
        mod = ob.modifiers.get(MOD_NAME) if ob and ob.type == 'MESH' else None
        if mod and mod.type == 'MIRROR':
            box = layout.box()
            box.label(text='Active mirror: ' + ob.name)
            row = box.row(align=True)
            for i, axis in enumerate('XYZ'):
                row.prop(mod, 'use_axis', index=i, text=axis, toggle=True)
            box.prop(mod, 'use_clip')
            box.prop(mod, 'use_mirror_merge')
            row = box.row(align=True)
            row.operator('mch.mesh_mirror_apply', text='Apply', icon='CHECKMARK')
            row.operator('mch.mesh_mirror_remove', text='Remove', icon='X')
        layout.separator()
        layout.label(text='Linked Collection Mirror (live)')
        layout.prop(p, 'source_collection')
        layout.prop(p, 'collection_axis', expand=True)
        layout.prop(p, 'collection_center', expand=True)
        layout.prop(p, 'collection_initial_offset')
        layout.operator('mch.collection_mirror', text='CREATE COLLECTION PAIR', icon='OUTLINER_COLLECTION')
        layout.label(text='Move MASTER; opposite instance follows.')
        layout.label(text='Editing source Collection updates both.')
        if ob and ob.get(RIG_TAG):
            layout.operator('mch.collection_mirror_remove', text='Remove This Mirror Rig', icon='TRASH')


CLASSES = (
    MCH_PG_Mirror,
    MCH_OT_mesh_mirror, MCH_OT_mesh_mirror_apply, MCH_OT_mesh_mirror_remove, MCH_OT_mirror_lean,
    MCH_OT_collection_mirror, MCH_OT_collection_mirror_remove,
    MCH_PT_mirror,
)
