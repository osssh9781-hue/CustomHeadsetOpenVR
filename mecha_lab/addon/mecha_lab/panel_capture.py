"""0.24.59 Read what a tool's sidebar panel draws, without drawing it.

``capture(drawer, context)`` calls the tool's normal panel function (``ui_tool_settings.DRAWERS``) with a stand-in
layout that only writes down what was asked for - rows, columns, boxes, props, operators, labels - as a small tree.
The viewport side panel (``side_panel``) turns that tree into Mecha-style sliders / pills / switches, so every tool
gets the new look from the panel code it already has (nothing written twice, a new setting shows up by itself).
"""
from __future__ import annotations


class Node:
    """A container (root / row / column / box / split / grid) or an element (prop / op / label / menu / sep)."""
    __slots__ = ('kind', 'children', 'attrs', 'data', 'prop', 'opts', 'parent')

    def __init__(self, kind, parent=None, **opts):
        self.kind = kind
        self.children = []
        self.attrs = {}
        self.data = None
        self.prop = ''
        self.opts = opts
        self.parent = parent

    # the container's own active / enabled / alert, ANDed with its parents'
    def state(self, name, default=True):
        n = self
        val = default
        while n is not None:
            if name in n.attrs:
                v = bool(n.attrs[name])
                val = (val and v) if name != 'alert' else (val or v)
            n = n.parent
        return val

    def __repr__(self):
        return f'<{self.kind} {self.prop or self.opts.get("text", "")} {len(self.children)}>'


class OpProps:
    """What ``layout.operator()`` returns: property assignments are kept (``op.profile = 'DOME'``)."""

    def __init__(self, node):
        object.__setattr__(self, '_node', node)

    def __setattr__(self, name, value):
        self._node.opts.setdefault('props', {})[name] = value

    def __getattr__(self, name):
        return self._node.opts.get('props', {}).get(name)


CONTAINER_ATTRS = {'active', 'enabled', 'alert', 'scale_y', 'scale_x', 'use_property_split',
                   'use_property_decorate', 'operator_context', 'alignment', 'emboss', 'ui_units_x', 'ui_units_y'}


class Recorder:
    """The stand-in for ``bpy.types.UILayout``."""

    def __init__(self, node):
        object.__setattr__(self, '_node', node)

    def __setattr__(self, name, value):
        self._node.attrs[name] = value

    def __getattr__(self, name):
        if name in CONTAINER_ATTRS:
            return self._node.attrs.get(name, 1.0 if name.startswith('scale') else True)

        def anything(*_a, **_k):             # a layout call this reader does not know: an empty container
            n = Node('other', self._node)
            self._node.children.append(n)
            return Recorder(n)
        return anything

    def _child(self, kind, **opts):
        n = Node(kind, self._node, **opts)
        self._node.children.append(n)
        return n

    # containers
    def row(self, align=False, heading='', **_k):
        return Recorder(self._child('row', align=align, heading=heading))

    def column(self, align=False, heading='', **_k):
        return Recorder(self._child('column', align=align, heading=heading))

    def box(self):
        return Recorder(self._child('box'))

    def split(self, factor=0.0, align=False, **_k):
        return Recorder(self._child('split', factor=factor, align=align))

    def grid_flow(self, row_major=False, columns=0, even_columns=False, even_rows=False, align=False, **_k):
        return Recorder(self._child('grid', columns=columns, align=align))

    def column_flow(self, columns=0, align=False):
        return Recorder(self._child('grid', columns=columns, align=align))

    def panel(self, idname, default_closed=False):
        n = self._child('box')
        return Recorder(n), Recorder(n)

    # elements
    def prop(self, data, property, text=None, text_ctxt='', translate=True, icon='NONE', placeholder='',
             expand=False, slider=False, toggle=-1, icon_only=False, event=False, full_event=False, emboss=True,
             index=-1, icon_value=0, invert_checkbox=False):
        n = self._child('prop', text=text, icon=icon, expand=expand, slider=slider, toggle=toggle, index=index,
                        icon_only=icon_only)
        n.data, n.prop = data, property

    def prop_enum(self, data, property, value, text=None, icon='NONE', **_k):
        n = self._child('prop_enum', text=text, icon=icon, value=value)
        n.data, n.prop = data, property

    def operator(self, operator, text=None, text_ctxt='', translate=True, icon='NONE', emboss=True,
                 depress=False, icon_value=0, **_k):
        n = self._child('op', idname=operator, text=text, icon=icon, depress=depress)
        return OpProps(n)

    def operator_menu_enum(self, operator, property, text='', icon='NONE', **_k):
        n = self._child('op', idname=operator, text=text, icon=icon, depress=False)
        return OpProps(n)

    def menu(self, menu, text='', text_ctxt='', translate=True, icon='NONE', icon_value=0):
        self._child('menu', name=menu, text=text, icon=icon)

    def label(self, text='', text_ctxt='', translate=True, icon='NONE', icon_value=0):
        self._child('label', text=text, icon=icon)

    def separator(self, factor=1.0, type='AUTO'):
        self._child('sep', factor=factor)

    def separator_spacer(self):
        self._child('sep', factor=0.5)

    def template_icon(self, icon_value=0, scale=1.0):
        self._child('icon', icon_value=icon_value)


def capture(drawer, context):
    """The tree ``drawer(layout, context)`` draws (root Node); None when the drawer failed."""
    root = Node('root')
    try:
        drawer(Recorder(root), context)
    except Exception as ex:                     # a panel that needs a real layout: the side panel says so
        root.opts['error'] = f'{type(ex).__name__}: {ex}'
    return root


def walk(node):
    yield node
    for c in node.children:
        yield from walk(c)
