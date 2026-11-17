"""0.24.200 Mask in MECHA LAB (user: "마스크한 게 오브젝트 모드에서도 되는 거면 지브러시 창으로 안 넘어가고 내가 모르게 그냥
스컬프 창으로 넘어가서 작동하면 메카랩 상태에서도 마스크 쓸 수 있는 거 아닌가? 그렇게 해서 메카랩에서 마스크 쓰게 해 줘,
클로스랑 익스트랙트 할 때" / "나는 변한 게 없다고 느끼지만 사실 스컬프 모드로 변환되게 하는 거지").

**Paint Mask** puts the active mesh into Sculpt Mode with Blender's Mask brush - and the MECHA LAB screen stays as it
is (``ON``: the ZBrush screen and its keys stay away, the Mecha bars and panels keep drawing).  Drag = mask, Ctrl +
drag = erase, F = brush size.  Any other Mecha button ends it (back to Object Mode) and then does its own job, so
Drape Mask works straight from the painting; **Extract** makes the shell and comes back to Object Mode too.
"""
import bpy
import numpy as np
from bpy.props import EnumProperty

ON = [False]
MODE = ['BRUSH']                 # how the mask is put on: the brush, a lasso, a box (0.24.209)
MASK_TOOLS = {'LASSO': 'builtin.lasso_mask', 'BOX': 'builtin.box_mask'}
SHELF = {}                       # 3D views whose brush shelf this hid: put back when the painting ends
MASK = '.sculpt_mask'


def on(context=None):
    """Painting a mask in the MECHA LAB screen right now?"""
    if not ON[0]:
        return False
    context = context or bpy.context
    if getattr(context, 'mode', '') != 'SCULPT':       # (left some other way: Tab, another tab)
        ON[0] = False
    return ON[0]


TRIES = [0]


def hide_shelf():
    """Sculpt Mode's brush shelf would lie over the tool menu: hidden while painting, put back after."""
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type != 'VIEW_3D':
                    continue
                sp = area.spaces.active
                try:
                    sp.overlay.show_sculpt_mask = True
                except AttributeError:
                    pass
                if getattr(sp, 'show_region_asset_shelf', False):
                    SHELF[sp.as_pointer()] = sp
                    sp.show_region_asset_shelf = False
                    area.tag_redraw()
    except (AttributeError, ReferenceError):
        pass


def _hide_again():
    if not ON[0]:
        return None
    hide_shelf()
    TRIES[0] += 1
    return 0.25 if TRIES[0] < 8 else None


def _bump():
    try:
        from . import ui_bars
        ui_bars.bump()
    except (ImportError, AttributeError):
        pass


def begin(context):
    ob = context.view_layer.objects.active
    if ob is None or ob.type != 'MESH':
        return 'Paint Mask: select a mesh first'
    from . import zb_sculpt as zs
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    ON[0] = True                                       # (before the mode changes: the screen never flips)
    try:
        bpy.ops.object.mode_set(mode='SCULPT')
    except RuntimeError as ex:
        ON[0] = False
        return str(ex).splitlines()[0]
    msg = use_mode(context, MODE[0])
    hide_shelf()
    if not bpy.app.timers.is_registered(_hide_again):  # (Blender shows the shelf again on the first Sculpt redraw)
        TRIES[0] = 0
        bpy.app.timers.register(_hide_again, first_interval=0.15)
    _bump()
    return msg or ''


def use_mode(context, mode):
    """The mask tool while painting: the Mask brush, or Blender's lasso / box mask (drag = mask, Ctrl + drag = clear)."""
    from . import zb_sculpt as zs
    MODE[0] = mode if mode in MASK_TOOLS else 'BRUSH'
    if MODE[0] == 'BRUSH':
        return zs.activate(context, 'MaskPen') or ''
    try:
        bpy.ops.wm.tool_set_by_id(name=MASK_TOOLS[MODE[0]])
    except (RuntimeError, TypeError) as ex:
        return str(ex).splitlines()[0]
    return ''


def end(context):
    """Back to Object Mode (the mask stays on the mesh)."""
    was = ON[0]
    ON[0] = False
    for sp in list(SHELF.values()):
        try:
            sp.show_region_asset_shelf = True
        except (AttributeError, ReferenceError):
            pass
    SHELF.clear()
    if was and getattr(context, 'mode', '') == 'SCULPT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except RuntimeError:
            pass
    if was:
        _bump()
    return was


def values(ob):
    att = ob.data.attributes.get(MASK)
    if att is None:
        return np.zeros(len(ob.data.vertices), np.float32)
    v = np.empty(len(ob.data.vertices), np.float32)
    att.data.foreach_get('value', v)
    return v


def set_values(context, ob, fn):
    """The mask rewritten by ``fn(values)`` (in Object Mode: the mesh holds it there)."""
    painting = on(context)
    if painting:
        bpy.ops.object.mode_set(mode='OBJECT')
    att = ob.data.attributes.get(MASK) or ob.data.attributes.new(MASK, 'FLOAT', 'POINT')
    v = np.empty(len(ob.data.vertices), np.float32)
    att.data.foreach_get('value', v)
    att.data.foreach_set('value', np.clip(fn(v), 0.0, 1.0).astype(np.float32))
    ob.data.update()
    if painting:
        bpy.ops.object.mode_set(mode='SCULPT')


class MCH_OT_mecha_mask(bpy.types.Operator):
    """Mask in MECHA LAB: Paint (drag = mask, Ctrl + drag = erase, F = size; the screen stays MECHA LAB), Clear, Invert, Extract (the masked part as a new shell: Thick / Offset)"""
    bl_idname = 'mch.mecha_mask'
    bl_label = 'Mask'
    bl_options = {'REGISTER', 'UNDO'}
    action: EnumProperty(items=[('PAINT', 'Paint Mask', ''), ('CLEAR', 'Clear', ''), ('INVERT', 'Invert', ''),
                                ('EXTRACT', 'Extract', ''), ('BRUSH', 'Brush', ''), ('LASSO', 'Lasso', ''),
                                ('BOX', 'Box', '')], default='PAINT')

    @classmethod
    def poll(cls, context):
        ob = context.view_layer.objects.active
        return ob is not None and ob.type == 'MESH' and context.mode in {'OBJECT', 'SCULPT'}

    def execute(self, context):
        ob = context.view_layer.objects.active
        if self.action in {'BRUSH', 'LASSO', 'BOX'}:        # 0.24.209 (user: "왜 메카랩에서는 라쏘로 그리는 게 안 돼?")
            if on(context):
                msg = use_mode(context, self.action)
            else:
                MODE[0] = self.action
                msg = begin(context)
                if not ON[0]:
                    self.report({'WARNING'}, msg)
                    return {'CANCELLED'}
            _bump()
            how = {'BRUSH': 'drag = mask', 'LASSO': 'draw round an area = mask', 'BOX': 'drag a box = mask'}[self.action]
            self.report({'INFO'}, f'Mask {self.action.title()}: {how}, Ctrl = erase' + (f' ({msg})' if msg else ''))
            return {'FINISHED'}
        if self.action == 'PAINT':
            if on(context):
                end(context)
                self.report({'INFO'}, 'Paint Mask off')
                return {'FINISHED'}
            msg = begin(context)
            if not ON[0]:
                self.report({'WARNING'}, msg)
                return {'CANCELLED'}
            self.report({'INFO'}, 'Paint Mask: drag = mask, Alt = erase, X = mirror, Ctrl + click empty = invert' + (f' ({msg})' if msg else ''))
            return {'FINISHED'}
        if self.action in {'CLEAR', 'INVERT'}:
            set_values(context, ob, (lambda v: v * 0.0) if self.action == 'CLEAR' else (lambda v: 1.0 - v))
            self.report({'INFO'}, 'Mask cleared' if self.action == 'CLEAR' else 'Mask inverted')
            return {'FINISHED'}
        from . import zb_sculpt as zs
        end(context)                                   # (the painted mask onto the mesh)
        if not values(ob).any():
            self.report({'WARNING'}, 'Extract: paint a mask first (Paint Mask)')
            return {'CANCELLED'}
        ON[0] = True                                   # (through Sculpt Mode without the screen flipping)
        try:
            bpy.ops.object.mode_set(mode='SCULPT')
            msg = zs.extract(context, ob, context.scene.mch_zb.thick)
        finally:
            ON[0] = False
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            _bump()
        self.report({'INFO'}, msg)
        return {'FINISHED'}


def draw(layout, context):
    """The Mask rows (Cloth Drape's window)."""
    zb = context.scene.mch_zb
    box = layout.box()
    box.label(text='Mask (as in the ZBRUSH screen: drag = mask · Alt = erase · X = mirror)', icon='MOD_MASK')
    box.label(text='Ctrl + click empty = invert · Ctrl + lasso = mask · Ctrl + drag empty = clear')
    r = box.row(align=True)
    r.operator('mch.mecha_mask', text='Paint Mask' + (' (on)' if on(context) else ''), icon='BRUSH_DATA',
               depress=on(context)).action = 'PAINT'
    r.operator('mch.mecha_mask', text='Clear').action = 'CLEAR'
    r.operator('mch.mecha_mask', text='Invert').action = 'INVERT'
    r = box.row(align=True)                                  # 0.24.209 how: the brush, a lasso, a box
    for mode, label in (('BRUSH', 'Brush'), ('LASSO', 'Lasso'), ('BOX', 'Box')):
        r.operator('mch.mecha_mask', text=label, depress=on(context) and MODE[0] == mode).action = mode
    r = box.row(align=True)
    r.operator('mch.mecha_mask', text='Extract (mask -> shell)', icon='MOD_SOLIDIFY').action = 'EXTRACT'
    r.prop(zb, 'thick')
    r.prop(zb, 'extract_offset')


def register():
    bpy.utils.register_class(MCH_OT_mecha_mask)


def unregister():
    ON[0] = False
    bpy.utils.unregister_class(MCH_OT_mecha_mask)
