"""0.24.49 Recent tools and Favorites at the top of the RMB popup (and the big tool menu).

Recent: the last 5 modelling tools, newest first, no repeats (Select / Move is not a tool here).
Favorites: up to 8 pinned tools in three sets (Mecha / Creature / Cloth); the star button pins or
unpins the current tool.  Both are kept in config/mecha_lab/last_used.json, so they survive a restart.
"""
from __future__ import annotations

import bpy
from bpy.props import EnumProperty, StringProperty

from . import last_used
from . import tool_state as ts

SECTION = 'tool_recent'
RECENT_MAX = 5
FAV_MAX = 8
SETS = (('MECHA', 'Mecha', 'Favorites for hard-surface / mecha work'),
        ('CREATURE', 'Creature', 'Favorites for creature work'),
        ('CLOTH', 'Cloth', 'Favorites for cloth / costume work'))
DEFAULT_FAVS = {
    'MECHA': ['CUT', 'SPLIT', 'BASE', 'PLATE', 'DETAIL3', 'SCREW'],
    'CREATURE': ['CBASE', 'CPLATE', 'SCALES', 'SPIKE', 'HAIR', 'CMOVE'],
    'CLOTH': ['WRINKLE', 'CAPE', 'SCAPE', 'BELT', 'SDRAW', 'CMOVE'],
}


def _valid(tid):
    return tid in ts.TOOL_BY_ID and tid not in ts.HIDDEN_TOOLS


def recent():
    return [t for t in last_used.recall(SECTION).get('recent', []) if _valid(t)][:RECENT_MAX]


def note(tool_id):
    """A modelling tool was turned on: it goes to the front of Recent."""
    if not _valid(tool_id):
        return
    items = [tool_id] + [t for t in recent() if t != tool_id]
    last_used.remember(SECTION, 'recent', items[:RECENT_MAX])


def current_set():
    s = last_used.recall(SECTION).get('set', 'MECHA')
    return s if s in DEFAULT_FAVS else 'MECHA'


def favorites(fav_set=None):
    fav_set = fav_set or current_set()
    stored = last_used.recall(SECTION).get('fav', {})
    items = stored.get(fav_set, DEFAULT_FAVS[fav_set])
    return [t for t in items if _valid(t)][:FAV_MAX]


def set_favorites(items, fav_set=None):
    fav_set = fav_set or current_set()
    stored = dict(last_used.recall(SECTION).get('fav', {}))
    stored[fav_set] = [t for t in dict.fromkeys(items) if _valid(t)][:FAV_MAX]
    last_used.remember(SECTION, 'fav', stored)


def toggle_favorite(tool_id, fav_set=None):
    """Pin / unpin; returns True when it is a favorite now (False when full and not pinned)."""
    items = favorites(fav_set)
    if tool_id in items:
        set_favorites([t for t in items if t != tool_id], fav_set)
        return False
    if len(items) >= FAV_MAX or not _valid(tool_id):
        return False
    set_favorites(items + [tool_id], fav_set)
    return True


def _set_get(self):
    return [s[0] for s in SETS].index(current_set())


def _set_set(self, value):
    last_used.remember(SECTION, 'set', SETS[value][0])


def _tiles(layout, context, tools, scale):
    from .workspace_ui import icon_tile
    active = ts.effective_tool(context)
    grid = layout.grid_flow(row_major=True, columns=max(1, min(len(tools), 5)), even_columns=True, align=True)
    for tid in tools:
        t = ts.TOOL_BY_ID[tid]
        for op in icon_tile(grid, t[3], t[4], 'mch.set_tool', t[1], scale, depress=(tid == active)):
            op.tool = tid


def draw(layout, context, scale=1.4):
    """Recent + Favorites block (popups put it on top)."""
    wm = context.window_manager
    box = layout.box()
    items = recent()
    row = box.row(align=True)
    row.label(text='RECENT', icon='TIME')
    if items:
        _tiles(box, context, items, scale)
    else:
        box.label(text='Tools you use show up here')
    row = box.row(align=True)
    row.label(text='FAVORITES', icon='SOLO_ON')
    row.prop(wm, 'mch_fav_set', text='')
    active = ts.effective_tool(context)
    if _valid(active):
        pinned = active in favorites()
        op = row.operator('mch.tool_fav_toggle', text='', icon='SOLO_ON' if pinned else 'SOLO_OFF',
                          depress=pinned)
        op.tool = active
    favs = favorites()
    if favs:
        _tiles(box, context, favs, scale)
    else:
        box.label(text='Star a tool to pin it here')


class MCH_OT_tool_fav_toggle(bpy.types.Operator):
    """Pin / unpin this tool in the current Favorites set"""
    bl_idname = 'mch.tool_fav_toggle'
    bl_label = 'Pin Favorite Tool'
    bl_options = {'INTERNAL'}
    tool: StringProperty(default='', options={'SKIP_SAVE'})

    def execute(self, context):
        if not _valid(self.tool):
            return {'CANCELLED'}
        was = self.tool in favorites()
        now = toggle_favorite(self.tool)
        name = ts.TOOL_BY_ID[self.tool][1]
        if not was and not now:
            self.report({'WARNING'}, f'Favorites are full ({FAV_MAX}); unpin one first')
        else:
            self.report({'INFO'}, f'{name}: ' + ('pinned' if now else 'unpinned'))
        last_used.save()
        return {'FINISHED'}


CLASSES = (MCH_OT_tool_fav_toggle,)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.mch_fav_set = EnumProperty(name='Favorites Set', items=SETS, get=_set_get,
                                                       set=_set_set, description='Which favorites set is shown')


def unregister():
    if hasattr(bpy.types.WindowManager, 'mch_fav_set'):
        del bpy.types.WindowManager.mch_fav_set
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
