"""0.24.227 (user, a screenshot of the small green cube above the top bar: "이것만 빼 주면 돼, 이게 뭔지 모르겠어"):
Blender shows the active tool's icon in the 3D view's tool settings row whenever its toolbar (T) is hidden.  In the
MECHA LAB workspace that icon says nothing (the tool is named on our own screen) - it is left blank there.  Nothing
else of that row changes; other workspaces are as before."""
import bpy

from . import tool_state as ts

_ORIG = [None]


class _NoIcon:
    """A UILayout stand-in: everything goes to the real layout, but an icon is drawn blank."""

    def __init__(self, real):
        object.__setattr__(self, '_real', real)

    def __getattr__(self, name):
        return getattr(self._real, name)

    def __setattr__(self, name, value):
        setattr(self._real, name, value)

    def template_icon(self, icon_value=0, scale=1.0):
        self._real.template_icon(icon_value=0, scale=scale)


def _wrapped(context, layout, **kw):
    try:
        if not kw.get('show_tool_icon_always') and ts.is_mecha_workspace(context.workspace):
            layout = _NoIcon(layout)
    except (AttributeError, ReferenceError, TypeError):
        pass
    return _ORIG[0](context, layout, **kw)


def register():
    if bpy.app.background or _ORIG[0] is not None:
        return
    try:
        from bl_ui.space_toolsystem_common import ToolSelectPanelHelper as H
        _ORIG[0] = H.draw_active_tool_header
        H.draw_active_tool_header = staticmethod(_wrapped)
    except (ImportError, AttributeError):
        _ORIG[0] = None


def unregister():
    if _ORIG[0] is None:
        return
    try:
        from bl_ui.space_toolsystem_common import ToolSelectPanelHelper as H
        H.draw_active_tool_header = staticmethod(_ORIG[0])
    except (ImportError, AttributeError):
        pass
    _ORIG[0] = None
