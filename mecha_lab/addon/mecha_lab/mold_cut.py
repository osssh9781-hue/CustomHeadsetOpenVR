"""0.24.304 Mold Cut (user: "그냥 그 컷을 분리해 주라, 몰드 컷으로 해서 탑이랑 바텀 둘 다 같이 옮겨 줘, 립이랑").

The Alt carve's own molding, apart from the Edge Molding that shapes a made solid / plate: with Mold Cut on, an Alt
carve (Base Mesh Alt: Carve Height, Armor Plate Alt) is cut with these - the shape turned the other way:
Bottom -> a step at the opening (the surface side), Top -> an undercut by the floor, Lip Rim -> a ring groove round the
floor, Dome -> a bowl floor.  Off: the Alt carve as it was (plain), whatever the Edge Molding says.
One setting for both tools.
"""
from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty

KEYS = ('emold_top', 'emold_bottom', 'emold_out', 'emold_band', 'emold_lip', 'emold_dome', 'emold_shape')


def _upd(self, context):
    try:
        from . import ramp_edit
        ramp_edit.refresh_later(context, 'platecarve')     # (a live Armor Plate carve is cut again)
    except Exception:          # a setting must never fail
        pass


class MCH_PG_MoldCut(bpy.types.PropertyGroup):
    on: BoolProperty(name='Mold Cut', default=False, update=_upd,
                     description='Alt + draw carves with these moldings (Top / Bottom / Lip Rim / Dome), turned the other '
                                 'way: Bottom = a step at the opening. Off: a plain carve')
    emold_top: BoolProperty(name='Top', default=False, update=_upd,
                            description='Mold Cut: the top band - an undercut by the floor of the carve')
    emold_bottom: BoolProperty(name='Bottom', default=True, update=_upd,
                               description='Mold Cut: the bottom flange - a step at the opening (the surface side)')
    emold_out: FloatProperty(name='Out', default=0.03, soft_min=-0.5, soft_max=0.5, precision=4, unit='LENGTH',
                             update=_upd, description='How wide the step / undercut is (less than 0: narrower, in)')
    emold_band: FloatProperty(name='Height', default=0.0, min=0.0, soft_max=1.0, precision=4, unit='LENGTH',
                              update=_upd, description='How deep the step / undercut is (0 = Auto)')
    emold_lip: FloatProperty(name='Lip Rim', default=0.0, min=0.0, soft_max=0.5, precision=4, unit='LENGTH',
                             update=_upd, description='Mold Cut (with Top): a ring groove this deep round the floor')
    emold_dome: FloatProperty(name='Dome', default=0.0, min=0.0, soft_max=0.5, precision=4, unit='LENGTH',
                              update=_upd, description='Mold Cut: the floor sinks this much more toward the middle (a bowl)')
    emold_shape: EnumProperty(name='Shape', default='SQUARE', update=_upd, items=[
        ('SQUARE', 'Square', 'A square step'), ('CHAMFER', 'Chamfer', 'A slanted step'), ('ROUND', 'Round', 'A round step'),
        ('SLOPE', 'Slope', 'A straight slant, no step')])


def settings(context):
    """The scene's Mold Cut when it is on and does something, else None."""
    from . import tool_state as ts
    if not ts.mold_on(context):                  # 0.24.305 only in Mold Base Mesh / Mold Armor Plate
        return None
    mc = getattr(getattr(context, 'scene', None), 'mch_moldcut', None)
    if mc is None or not mc.on:
        return None
    if not (mc.emold_top or mc.emold_bottom or mc.emold_dome > 0.0):
        return None
    return mc


class Over:
    """Settings view: ``base`` with the Mold Cut's molding (and no Side Molding)."""

    def __init__(self, base, mc):
        self._base = base
        self._mc = mc

    def __getattr__(self, name):
        if name in KEYS:
            return getattr(self._mc, name)
        if name == 'mold_count':
            return 0
        return getattr(self._base, name)


MOLD_KEYS = KEYS + ('mold_count',)
OFF = {'emold_top': False, 'emold_bottom': False, 'emold_dome': 0.0, 'mold_count': 0}


class NoMold:
    """0.24.305 Settings view with every molding off (the original Base Mesh / Armor Plate tools)."""

    def __init__(self, base):
        object.__setattr__(self, '_base', base)

    def __getattr__(self, name):
        if name in OFF:
            return OFF[name]
        return getattr(self._base, name)

    def __setattr__(self, name, value):
        setattr(self._base, name, value)


def strip(pg):
    """0.24.305 A made part's own settings: every molding off (a part made with an original tool)."""
    changed = False
    for k, v in OFF.items():
        if hasattr(pg, k) and getattr(pg, k) != v:
            setattr(pg, k, v)
            changed = True
    return changed


def draw(layout, mc):
    """The Mold Cut box (Base Mesh / Armor Plate panels)."""
    col = layout.column(align=True)
    col.prop(mc, 'on', toggle=True, icon='MOD_BOOLEAN')
    if not mc.on:
        return
    row = col.row(align=True)
    row.prop(mc, 'emold_bottom', toggle=True)
    row.prop(mc, 'emold_top', toggle=True)
    col.prop(mc, 'emold_out')
    col.prop(mc, 'emold_band', text='Height (0: Auto)')
    if mc.emold_top:
        col.prop(mc, 'emold_lip')
    col.prop(mc, 'emold_dome')
    col.row(align=True).prop(mc, 'emold_shape', expand=True)


def register():
    bpy.utils.register_class(MCH_PG_MoldCut)
    bpy.types.Scene.mch_moldcut = bpy.props.PointerProperty(type=MCH_PG_MoldCut)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_moldcut'):
        del bpy.types.Scene.mch_moldcut
    try:
        bpy.utils.unregister_class(MCH_PG_MoldCut)
    except RuntimeError:
        pass
