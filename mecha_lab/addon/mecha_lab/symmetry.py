"""0.24.52 Symmetry, the Substance 3D Modeler way: one card beside the part instead of the old mirror side
buttons - Off / Mirror / Radial / Kaleido (= Mirror and Radial together).

- Mirror: X / Y / Z planes through the mirror centre (world origin or the 3D cursor, Preferences of the Mirror
  panel), live (the ``MCH_Mirror`` modifier of mirror_tools - Alt+X lean, Apply, Enter keep working), Bisect
  (the copy replaces the other side) and Flip (which side is copied).
- Radial: copies round an axis (X / Y / Z) through a centre, Count copies (radial_sym's live Array; one radial
  centre / count / axis per scene, like its pivot).  The centre starts where the mirror centre is (world origin or
  the 3D cursor, like Modeler's one symmetry origin); the card moves it to the part, the world or the cursor.
- Kaleido (Modeler's radial mirror): the mirror planes go through the radial centre and its axes (the mirror uses
  the radial centre as its mirror object), so each slice is mirrored in itself; the mirror works first, then the
  radial copies take the mirrored part round.  A new Kaleido starts with the plane that holds the radial axis.
- Apply bakes it, Remove takes it off.  For a group (groups.py) the same card drives its Repetition instead.

The card is drawn with the Mecha Menu painter; a left click on it is taken by ``mch.quick_hud_press`` (first in
every Mecha tool keymap), so it works in any tool.  It shows (docked at the right of the viewport) when the active
part has a symmetry, or when opened from the Mecha Menu (Symmetry > Card).
"""
from __future__ import annotations

import bpy
from bpy.props import StringProperty
from mathutils import Matrix, Vector

from . import tool_state as ts

MODES = ('OFF', 'MIRROR', 'RADIAL', 'KALEIDO')
MODE_NAMES = {'OFF': 'Off', 'MIRROR': 'Mirror', 'RADIAL': 'Radial', 'KALEIDO': 'Kaleido'}
KALEIDO_AXES = {'Z': (True, False, False), 'X': (False, True, False), 'Y': (True, False, False)}   # holds the axis


# --- state of a part -----------------------------------------------------------------------------------------

def mirror_mod(ob):
    from . import mirror_tools
    if ob is None or ob.type != 'MESH':
        return None
    m = ob.modifiers.get(mirror_tools.MOD_NAME)
    if m is not None and m.type == 'MIRROR':
        return m
    m = ob.modifiers.get('MCH_Symmetry')                       # 0.24.49 - 0.24.51 menu mirror
    return m if m is not None and m.type == 'MIRROR' else None


def radial_mod(ob):
    from . import radial_sym
    if ob is None or ob.type != 'MESH':
        return None
    m = ob.modifiers.get(radial_sym.MOD_NAME)
    return m if m is not None and m.type == 'ARRAY' else None


def mode_of(ob):
    m, r = mirror_mod(ob), radial_mod(ob)
    if m is not None and r is not None:
        return 'KALEIDO'
    return 'MIRROR' if m is not None else 'RADIAL' if r is not None else 'OFF'


def axes_of(ob):
    m = mirror_mod(ob)
    return tuple(bool(a) for a in m.use_axis) if m is not None else (False, False, False)


# --- changing it ---------------------------------------------------------------------------------------------

def _mirror_on(context, ob, axes=None):
    from . import mirror_tools
    p = context.scene.mch_mirror
    old = mirror_mod(ob)
    if old is not None and old.name != mirror_tools.MOD_NAME:             # move the 0.24.49 name over
        keep = tuple(old.use_axis)
        ob.modifiers.remove(old)
        axes = axes or keep
    cur = mirror_mod(ob)
    if axes is None:
        axes = tuple(cur.use_axis) if cur is not None and any(cur.use_axis) else (True, False, False)
    flips = tuple(cur.use_bisect_flip_axis) if cur is not None else None
    bisect = any(cur.use_bisect_axis) if cur is not None else p.bisect
    mod = mirror_tools.setup_mirror(ob, p, context.scene, axes=axes, flips=flips)
    if mod is not None:
        for i in range(3):
            mod.use_bisect_axis[i] = bisect and axes[i]
        _mirror_before_radial(ob)
        _bind_mirror(context, ob)
    return mod


def _bind_mirror(context, ob):
    """Kaleido: the mirror planes through the radial centre (its axes); without the radial copies the mirror goes
    back to the mirror centre of the Mirror panel."""
    from . import mirror_tools
    m = mirror_mod(ob)
    if m is None:
        return
    piv = context.scene.mch_rsym.pivot
    if radial_mod(ob) is not None and piv is not None:
        if m.mirror_object != piv:
            old = m.mirror_object
            m.mirror_object = piv
            mirror_tools._remove_unused_pivot(old)
    elif piv is not None and m.mirror_object == piv:
        _mirror_home(context, ob, m)


def _mirror_home(context, ob, m):
    """The mirror back on the mirror centre of the Mirror panel (planes, bisect and flips kept)."""
    from . import mirror_tools
    keep = (tuple(m.use_axis), tuple(m.use_bisect_axis), tuple(m.use_bisect_flip_axis))
    m.mirror_object = None
    mirror_tools.setup_mirror(ob, context.scene.mch_mirror, context.scene, axes=keep[0], flips=keep[2])
    for i in range(3):
        m.use_bisect_axis[i] = keep[1][i]


def unbind_all(context):
    """Before the radial centre is deleted: the mirrors that used it go back to the mirror centre."""
    piv = context.scene.mch_rsym.pivot
    if piv is None:
        return
    for ob in context.scene.objects:
        m = mirror_mod(ob)
        if m is not None and m.mirror_object == piv:
            _mirror_home(context, ob, m)


def _mirror_off(ob):
    from . import mirror_tools
    m = mirror_mod(ob)
    if m is None:
        return
    pivot = m.mirror_object
    ob.modifiers.remove(m)
    mirror_tools._remove_unused_pivot(pivot)


def _mirror_before_radial(ob):
    """Kaleido: the mirror works first, then the radial copies take the mirrored part round."""
    m, r = mirror_mod(ob), radial_mod(ob)
    if m is None or r is None:
        return
    mods = list(ob.modifiers)
    mi, ri = mods.index(m), mods.index(r)
    if mi > ri:
        ob.modifiers.move(mi, ri)


def _radial_on(context, ob):
    from . import radial_sym
    st = context.scene.mch_rsym
    if not st.active or st.pivot is None:
        piv = st.pivot
        if piv is None:
            piv = bpy.data.objects.new('MCH_RadialPivot', None)
            piv.empty_display_type = 'SPHERE'
            piv.empty_display_size = 0.15
            (context.collection or context.scene.collection).objects.link(piv)
            st.pivot = piv
        where = 'CURSOR' if getattr(context.scene.mch_mirror, 'center', 'WORLD') == 'CURSOR' else 'WORLD'
        piv.matrix_world = Matrix.Translation(_center(context, ob, where))      # the one symmetry origin
        st.active = True
    ok = radial_sym.adopt(context, ob)
    _mirror_before_radial(ob)
    _bind_mirror(context, ob)
    return ok


def _radial_off(context, ob):
    """Take the radial copies off the part (helper and keys too; the centre goes with the last part)."""
    from . import radial_sym
    r = radial_mod(ob)
    if r is not None:
        ob.modifiers.remove(r)
    _bind_mirror(context, ob)                  # a Kaleido mirror goes back to the mirror centre
    h = bpy.data.objects.get(ob.get(radial_sym.HELPER_KEY, ''))
    if h is not None:
        bpy.data.objects.remove(h, do_unlink=True)
    for key in (radial_sym.HELPER_KEY, radial_sym.R0_KEY):
        if key in ob:
            del ob[key]
    st = context.scene.mch_rsym
    if not radial_sym.members(context) and st.pivot is not None:      # the last one: the centre goes too
        unbind_all(context)
        bpy.data.objects.remove(st.pivot, do_unlink=True)
        st.pivot = None
        st.active = False


def set_mode(context, ob, mode):
    """Off / Mirror / Radial / Kaleido for one part."""
    if ob is None or ob.type != 'MESH':
        return False
    if mode not in {'RADIAL', 'KALEIDO'}:
        _radial_off(context, ob)
    if mode not in {'MIRROR', 'KALEIDO'}:
        _mirror_off(ob)
    if mode in {'RADIAL', 'KALEIDO'}:
        _radial_on(context, ob)
    if mode in {'MIRROR', 'KALEIDO'}:
        new = mirror_mod(ob) is None
        _mirror_on(context, ob, KALEIDO_AXES[context.scene.mch_rsym.axis] if mode == 'KALEIDO' and new else None)
    return True


def toggle_axis(context, ob, axis):
    """Mirror plane X / Y / Z on or off; the last one off ends the mirror (Radial stays)."""
    axes = list(axes_of(ob))
    axes[axis] = not axes[axis]
    if not any(axes):
        _mirror_off(ob)
        return False
    _mirror_on(context, ob, tuple(axes))
    return axes[axis]


def toggle_bisect(ob):
    m = mirror_mod(ob)
    if m is None:
        return False
    on = not any(m.use_bisect_axis)
    for i in range(3):
        m.use_bisect_axis[i] = on and m.use_axis[i]
    return on


def toggle_flip(ob):
    m = mirror_mod(ob)
    if m is None:
        return False
    on = not any(m.use_bisect_flip_axis)
    for i in range(3):
        m.use_bisect_flip_axis[i] = on
    return on


def set_count(context, n):
    from . import radial_sym
    st = context.scene.mch_rsym
    st.count = max(2, min(128, int(n)))
    radial_sym.refresh(context)
    return st.count


def set_radial_axis(context, axis):
    from . import radial_sym
    st = context.scene.mch_rsym
    st.axis = axis
    radial_sym.refresh(context)


def _center(context, ob, where):
    if where == 'WORLD':
        return Vector((0.0, 0.0, 0.0))
    if where == 'CURSOR':
        return Vector(context.scene.cursor.location)
    if ob is not None and ob.type == 'MESH' and ob.data.vertices:
        pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        return sum(pts, Vector()) / 8.0
    return ob.matrix_world.translation.copy() if ob is not None else Vector()


def set_center(context, ob, where):
    from . import radial_sym
    st = context.scene.mch_rsym
    if st.pivot is None:
        return False
    st.pivot.matrix_world = Matrix.Translation(_center(context, ob, where)) @ \
        st.pivot.matrix_world.to_quaternion().to_matrix().to_4x4()
    radial_sym.refresh(context)
    return True


def apply(context, ob):
    """Bake the part's symmetry into its mesh."""
    from . import core_geometry as cg
    from . import mirror_tools
    done = 0
    for m in (mirror_mod(ob), radial_mod(ob)):
        if m is None:
            continue
        pivot = m.mirror_object if m.type == 'MIRROR' else None
        try:
            cg.apply_single_modifier(context, ob, m.name)
            done += 1
        except (cg.CutError, RuntimeError, AttributeError, TypeError):
            continue
        if pivot is not None:
            mirror_tools._remove_unused_pivot(pivot)
    if radial_mod(ob) is None:
        _radial_off(context, ob)          # helper / keys / centre clean-up (the modifier is already gone)
    return done


# --- the card --------------------------------------------------------------------------------------------------

def card_target(context):
    """('PART', mesh) or ('GROUP', group empty) the card is for, or (None, None)."""
    from . import bottom_bar
    try:
        if not bottom_bar.ui_active(context):
            return None, None
    except (AttributeError, TypeError):
        return None, None
    from .workspace_ui import pref
    if not pref('symmetry_card', True):
        return None, None
    ob = context.active_object
    if ob is None or not ob.select_get():
        return None, None
    try:
        from . import groups
        g = groups.group_of(ob)
    except ImportError:
        g = None
    wm = context.window_manager
    opened = getattr(wm, 'mch_sym_card', '') == ob.name
    if g is not None and ob == g:                       # the group itself selected: its Repetition
        return 'GROUP', g
    if ob.type == 'MESH' and (mode_of(ob) != 'OFF' or opened):
        return 'PART', ob
    return None, None


def build_card(context, region_w, region_h, S=1.0):
    """Items (the Mecha Menu painter's) of the card, placed right of the target on screen."""
    from .mecha_menu import Item
    kind, ob = card_target(context)
    if ob is None:
        return []
    if kind == 'GROUP':
        from . import groups
        mode = groups.repeat_mode(ob)
        axes = groups.repeat_axes(ob)
        count, raxis = groups.repeat_count(ob), groups.repeat_axis(ob)
        title = 'Repetition  ·  ' + ob.name
    else:
        mode = mode_of(ob)
        axes = axes_of(ob)
        st = context.scene.mch_rsym
        count, raxis = st.count, st.axis
        title = 'Symmetry  ·  ' + ob.name
    pad, w = 14 * S, 300 * S
    inner = w - 2 * pad
    items = []
    y = -pad
    y -= 26 * S
    items.append(Item('title', pad, y, inner - 30 * S, 26 * S, title))
    items.append(Item('pill', pad + inner - 26 * S, y + 1 * S, 26 * S, 24 * S, '×', '', False, True, ('sym_close',)))
    y -= 36 * S
    seg_w = (inner - 3 * 4 * S) / 4
    for i, m in enumerate(MODES):
        items.append(Item('seg', pad + i * (seg_w + 4 * S), y, seg_w, 28 * S, MODE_NAMES[m], '', mode == m, True,
                          ('sym_mode', kind, m)))
    if kind == 'GROUP' and mode != 'OFF':
        from . import groups
        y -= 34 * S                              # 0.24.53 about the world (default), the group or the cursor
        items.append(Item('label', pad, y, 60 * S, 28 * S, 'Centre'))
        cw = (inner - 60 * S - 8 * S) / 3
        here = groups.repeat_center(ob)
        for i, (c, name) in enumerate((('WORLD', 'World'), ('GROUP', 'Group'), ('CURSOR', 'Cursor'))):
            items.append(Item('seg', pad + 60 * S + i * (cw + 4 * S), y, cw, 28 * S, name, '', here == c, True,
                              ('sym_center', c)))
    if mode in {'MIRROR', 'KALEIDO'}:
        y -= 12 * S
        items.append(Item('section', pad, y - 18 * S, inner, 18 * S, 'Mirror'))
        y -= 22 * S + 44 * S
        bw = inner / 3
        for i, name in enumerate('XYZ'):
            items.append(Item('abtn', pad + i * bw + 4 * S, y, bw - 8 * S, 40 * S, 'Mirror ' + name, name, axes[i],
                              True, ('sym_axis', kind, i)))
        if kind == 'PART':
            m = mirror_mod(ob)
            y -= 34 * S
            items.append(Item('toggle', pad, y, inner / 2 - 8 * S, 30 * S, 'Bisect', '',
                              bool(m and any(m.use_bisect_axis)), True, ('sym_bisect',)))
            items.append(Item('toggle', pad + inner / 2 + 8 * S, y, inner / 2 - 8 * S, 30 * S, 'Flip', '',
                              bool(m and any(m.use_bisect_flip_axis)), True, ('sym_flip',)))
    if mode in {'RADIAL', 'KALEIDO'}:
        y -= 12 * S
        items.append(Item('section', pad, y - 18 * S, inner, 18 * S, 'Radial'))
        y -= 22 * S + 30 * S
        items.append(Item('label', pad, y, 60 * S, 28 * S, 'Axis'))
        aw = (inner - 60 * S - 8 * S) / 3
        for i, name in enumerate('XYZ'):
            items.append(Item('seg', pad + 60 * S + i * (aw + 4 * S), y, aw, 28 * S, name, '', raxis == name, True,
                              ('sym_raxis', kind, name)))
        y -= 34 * S
        items.append(Item('label', pad, y, 60 * S, 28 * S, 'Count'))
        items.append(Item('pill', pad + 60 * S, y, 40 * S, 28 * S, '−', '', False, True, ('sym_count', kind, -1)))
        items.append(Item('note', pad + 104 * S, y, inner - 60 * S - 148 * S, 28 * S, f'{count} copies'))
        items.append(Item('pill', pad + inner - 40 * S, y, 40 * S, 28 * S, '+', '', False, True,
                          ('sym_count', kind, 1)))
        if kind == 'PART':
            y -= 34 * S
            items.append(Item('label', pad, y, 60 * S, 28 * S, 'Centre'))
            cw = (inner - 60 * S - 8 * S) / 3
            for i, (c, name) in enumerate((('PART', 'Part'), ('WORLD', 'World'), ('CURSOR', 'Cursor'))):
                items.append(Item('seg', pad + 60 * S + i * (cw + 4 * S), y, cw, 28 * S, name, '', False, True,
                                  ('sym_center', c)))
    if mode != 'OFF':
        y -= 40 * S
        half = (inner - 8 * S) / 2
        items.append(Item('seg', pad, y, half, 30 * S, 'Apply', '', False, True, ('sym_apply', kind)))
        items.append(Item('seg', pad + half + 8 * S, y, half, 30 * S, 'Remove', '', False, True,
                          ('sym_mode', kind, 'OFF')))
    h = -y + pad
    x0, y0 = _anchor(context, ob, w, h, region_w, region_h, S)
    out = [Item('card', x0, y0, w, h)]
    for it in items:
        it.x += x0
        it.y += y0 + h
        out.append(it)
    return out


def _anchor(context, ob, w, h, region_w, region_h, S):
    """Bottom-left corner: docked at the right of the viewport (left of an overlapping sidebar), a bit below the
    middle - 0.24.53 no longer next to the part, where it covered the part (and a group's boxes)."""
    inset = 0.0
    area = getattr(context, 'area', None)
    try:
        overlap = context.preferences.system.use_region_overlap
    except AttributeError:
        overlap = False
    if area is not None and overlap:
        inset = sum(r.width for r in area.regions if r.type == 'UI' and r.width > 1)
    x = region_w - inset - w - 16 * S
    y = region_h * 0.42 - h / 2
    x = min(max(x, 8 * S), region_w - w - 8 * S)
    y = min(max(y, 8 * S), region_h - h - 8 * S)
    return x, y


def card_items(context):
    region = context.region
    if region is None:
        return []
    from .ui_gpu import ui_factor
    try:
        return build_card(context, region.width, region.height, ui_factor(context, region))
    except (AttributeError, KeyError, TypeError, ReferenceError):
        return []


def card_hit(context, x, y):
    """(inside the card?, the clickable item under the mouse or None)."""
    items = card_items(context)
    cards = [i for i in items if i.kind == 'card']
    if not cards or not cards[0].hit(x, y):
        return False, None
    it = next((i for i in reversed(items) if i.kind != 'card' and i.clickable() and i.hit(x, y)), None)
    return True, it


def run_card(context, item):
    """Do a card click.  Returns a short report."""
    a = item.action
    kind = a[0]
    target_kind, ob = card_target(context)
    if ob is None:
        return ''
    if kind == 'sym_close':
        context.window_manager.mch_sym_card = ''
        return 'Card closed'
    if target_kind == 'GROUP':
        from . import groups
        if kind == 'sym_mode':
            groups.set_repeat(context, ob, mode=a[2])
        elif kind == 'sym_axis':
            axes = list(groups.repeat_axes(ob))
            axes[a[2]] = not axes[a[2]]
            if any(axes):
                groups.set_repeat(context, ob, axes=tuple(axes))
        elif kind == 'sym_raxis':
            groups.set_repeat(context, ob, axis=a[2])
        elif kind == 'sym_count':
            groups.set_repeat(context, ob, count=groups.repeat_count(ob) + a[2])
        elif kind == 'sym_center':
            groups.set_repeat(context, ob, center=a[1])
        elif kind == 'sym_apply':
            groups.make_real(context, ob)
        return 'Repetition: ' + MODE_NAMES.get(groups.repeat_mode(ob), '')
    if kind == 'sym_mode':
        set_mode(context, ob, a[2])
        if a[2] == 'OFF':
            context.window_manager.mch_sym_card = ''
        return 'Symmetry: ' + MODE_NAMES[a[2]]
    if kind == 'sym_axis':
        toggle_axis(context, ob, a[2])
    elif kind == 'sym_bisect':
        toggle_bisect(ob)
    elif kind == 'sym_flip':
        toggle_flip(ob)
    elif kind == 'sym_raxis':
        set_radial_axis(context, a[2])
    elif kind == 'sym_count':
        set_count(context, context.scene.mch_rsym.count + a[2])
    elif kind == 'sym_center':
        set_center(context, ob, a[1])
    elif kind == 'sym_apply':
        apply(context, ob)
        context.window_manager.mch_sym_card = ''
    return 'Symmetry: ' + MODE_NAMES[mode_of(ob)]


_handle = None


def _draw():
    try:
        context = bpy.context
        if context.region is None or context.region.type != 'WINDOW':
            return
        from .mecha_menu import _OPEN, draw
        if _OPEN[0]:
            return
        items = card_items(context)
        if items:
            from .ui_gpu import ui_factor
            draw(items, None, ui_factor(context), context)
    except Exception:          # never break viewport drawing
        pass
    from . import ui_gpu
    ui_gpu.done()


class MCH_OT_symmetry_card(bpy.types.Operator):
    """Show the Symmetry card for the active part (or the Repetition card for a group)"""
    bl_idname = 'mch.symmetry_card'
    bl_label = 'Symmetry Card'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        context.window_manager.mch_sym_card = context.active_object.name
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


class MCH_OT_symmetry_mode(bpy.types.Operator):
    """Symmetry of the active part: Off / Mirror / Radial / Kaleido"""
    bl_idname = 'mch.symmetry_mode'
    bl_label = 'Symmetry Mode'
    bl_options = {'REGISTER', 'UNDO'}
    mode: StringProperty(default='MIRROR', options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return context.mode == 'OBJECT' and ob is not None and ob.type == 'MESH'

    def execute(self, context):
        if self.mode not in MODES:
            return {'CANCELLED'}
        ob = context.active_object
        set_mode(context, ob, self.mode)
        context.window_manager.mch_sym_card = ob.name if self.mode != 'OFF' else ''
        self.report({'INFO'}, f'{ob.name}: Symmetry {MODE_NAMES[self.mode]}')
        return {'FINISHED'}


CLASSES = (MCH_OT_symmetry_card, MCH_OT_symmetry_mode)


def register():
    global _handle
    bpy.types.WindowManager.mch_sym_card = StringProperty(default='', options={'SKIP_SAVE'})
    for c in CLASSES:
        bpy.utils.register_class(c)
    if not bpy.app.background and _handle is None:
        _handle = bpy.types.SpaceView3D.draw_handler_add(_draw, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    global _handle
    if _handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _handle = None
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
    if hasattr(bpy.types.WindowManager, 'mch_sym_card'):
        del bpy.types.WindowManager.mch_sym_card
