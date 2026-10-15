"""0.18 Mirror HUD: buttons next to a mesh that carries the live Mecha Mirror.

Right of the selected mirrored mesh(es), like the primitive HUD:
    [check] Apply   [x] Remove   X   Y   Z   Bisect   Flip
X / Y / Z switch an axis on or off, Bisect cuts on the plane first, Flip
copies toward the other side; every change updates the live modifier at once
(Mirror tool settings).  Apply bakes it, Remove drops it (mesh unchanged).

``hud_layout`` is pure and tested headless; the buttons need a real viewport.
"""
from __future__ import annotations

import bpy
from bpy.props import EnumProperty
from mathutils import Vector

from . import mirror_tools as mt
from . import tool_state as ts

BUTTONS = (('apply', 'CHECKMARK', 'mch.mesh_mirror_apply', {}, 'Apply'),
           ('remove', 'X', 'mch.mesh_mirror_remove', {}, 'Remove'),
           ('x', 'EVENT_X', 'mch.mirror_hud_option', {'option': 'X'}, 'X'),
           ('y', 'EVENT_Y', 'mch.mirror_hud_option', {'option': 'Y'}, 'Y'),
           ('z', 'EVENT_Z', 'mch.mirror_hud_option', {'option': 'Z'}, 'Z'),
           ('bisect', 'MOD_BOOLEAN', 'mch.mirror_hud_option', {'option': 'BISECT'}, 'Bisect'),
           ('flip', 'ARROW_LEFTRIGHT', 'mch.mirror_hud_option', {'option': 'FLIP'}, 'Flip side'))
ACCENT = (1.0, 0.62, 0.16)
BASE_COL = (0.17, 0.19, 0.23)
_label_handle = None


def targets(context):
    try:
        if context.mode != 'OBJECT' or not ts.is_mecha_workspace(getattr(context, 'workspace', None)):
            return []
    except (AttributeError, TypeError):
        return []
    if not shown_for_tool(context):
        return []
    return mt._mirror_targets(context)


def shown_for_tool(context):
    """0.23.18 the Apply / Remove buttons only in the Mirror (Symmetry) tool and in Select - not over Cut,
    Base Mesh and the other tools."""
    try:
        from . import bottom_bar
        if bottom_bar.in_select(context):
            return True
        return ts.effective_tool(context) == 'MIRROR'
    except (AttributeError, TypeError, KeyError, ImportError):
        return True


def is_on(p, name):
    return {'x': p.x, 'y': p.y, 'z': p.z, 'bisect': p.bisect,
            'flip': any(f for a, f in ((p.x, p.flip_x), (p.y, p.flip_y), (p.z, p.flip_z)) if a)}.get(name, False)


def hud_layout(screen_pts, region_w, region_h, btn=28.0, gap=5.0):
    pts = [p for p in screen_pts if p is not None]
    if not pts:
        return {}
    x = min(max(max(p[0] for p in pts) + btn * 1.2, btn), region_w - 110.0)
    step = btn + gap
    total = step * len(BUTTONS)
    top = min(max((max(p[1] for p in pts) + min(p[1] for p in pts)) / 2 + total / 2, total), region_h - btn)
    return {name: (x, top - i * step) for i, (name, *_r) in enumerate(BUTTONS)}


def update_targets(context):
    p = context.scene.mch_mirror
    for ob in targets(context) or mt._mirror_targets(context):
        mt.setup_mirror(ob, p, context.scene)


class MCH_OT_mirror_hud_option(bpy.types.Operator):
    """Mirror HUD: switch an axis, Bisect or the copy side; the live mirror updates at once"""
    bl_idname = 'mch.mirror_hud_option'
    bl_label = 'Mirror Option'
    bl_options = {'REGISTER', 'UNDO'}
    option: EnumProperty(items=[('X', 'X', ''), ('Y', 'Y', ''), ('Z', 'Z', ''), ('BISECT', 'Bisect', ''),
                                ('FLIP', 'Flip', '')], default='X')

    @classmethod
    def description(cls, context, properties):
        return {'X': 'Mirror across X on / off', 'Y': 'Mirror across Y on / off', 'Z': 'Mirror across Z on / off',
                'BISECT': 'Cut on the mirror plane first (copy one side over the other)',
                'FLIP': 'Copy toward the other side'}[properties.option]

    @classmethod
    def poll(cls, context):
        return bool(mt._mirror_targets(context))

    def execute(self, context):
        p = context.scene.mch_mirror
        if self.option in {'X', 'Y', 'Z'}:
            key = self.option.lower()
            new = not getattr(p, key)
            if not new and sum((p.x, p.y, p.z)) <= 1:
                self.report({'WARNING'}, 'At least one axis stays on (Remove drops the mirror)')
                return {'CANCELLED'}
            setattr(p, key, new)
        elif self.option == 'BISECT':
            p.bisect = not p.bisect
        else:
            for a in 'xyz':
                if getattr(p, a):
                    setattr(p, 'flip_' + a, not getattr(p, 'flip_' + a))
        update_targets(context)
        return {'FINISHED'}


def _current(context):
    from .primitive_hud import anchored, release_anchor
    obs = targets(context)
    if not obs:
        release_anchor('mirror')
        return [], {}
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    if region is None or rv3d is None:
        return obs, {}
    ui = context.preferences.system.ui_scale
    dg = context.evaluated_depsgraph_get()
    pts = []
    for ob in obs:
        ev = ob.evaluated_get(dg)
        for c in ev.bound_box:
            q = view3d_utils.location_3d_to_region_2d(region, rv3d, ev.matrix_world @ Vector(c))
            pts.append(None if q is None else (q[0] / ui, q[1] / ui))
    lay = hud_layout(pts, region.width / ui, region.height / ui)
    return obs, anchored('mirror', tuple(sorted(o.name for o in obs)), region, lay)


class MCH_GGT_mirror_hud(bpy.types.GizmoGroup):
    bl_idname = 'MCH_GGT_mirror_hud'
    bl_label = 'Mirror HUD'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):
        return bool(targets(context))

    def setup(self, context):
        self.items = {}
        for name, icon, op, props, _label in BUTTONS:
            gz = self.gizmos.new('GIZMO_GT_button_2d')
            gz.icon = icon
            gz.draw_options = {'BACKDROP', 'OUTLINE'}
            t = gz.target_set_operator(op)
            for k, v in props.items():
                setattr(t, k, v)
            gz.color = BASE_COL
            gz.alpha = 0.92
            gz.color_highlight = (0.32, 0.35, 0.41)
            gz.alpha_highlight = 1.0
            self.items[name] = gz

    def draw_prepare(self, context):
        _obs, lay = _current(context)
        ui = context.preferences.system.ui_scale
        p = context.scene.mch_mirror
        for name, gz in self.items.items():
            pos = lay.get(name)
            gz.hide = pos is None
            if pos is None:
                continue
            gz.scale_basis = 14.0
            gz.matrix_basis[0][3] = pos[0] * ui
            gz.matrix_basis[1][3] = pos[1] * ui
            gz.color = ACCENT if (name == 'apply' or is_on(p, name)) else BASE_COL


def _draw_labels():
    try:
        context = bpy.context
        _obs, lay = _current(context)
        if not lay:
            return
        import blf
        ui = context.preferences.system.ui_scale
        p = context.scene.mch_mirror
        blf.size(0, 11 * ui)
        for name, _i, _o, _pr, label in BUTTONS:
            x, y = lay[name]
            blf.color(0, *(ACCENT if is_on(p, name) else (0.85, 0.87, 0.9)), 1.0)
            blf.position(0, (x + 20) * ui, (y - 4) * ui, 0)
            blf.draw(0, label)
    except Exception:          # never break viewport drawing
        pass


CLASSES = (MCH_OT_mirror_hud_option, MCH_GGT_mirror_hud)


def register():
    global _label_handle
    for c in CLASSES:
        bpy.utils.register_class(c)
    if not bpy.app.background and _label_handle is None:
        _label_handle = bpy.types.SpaceView3D.draw_handler_add(_draw_labels, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    global _label_handle
    if _label_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_label_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _label_handle = None
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
