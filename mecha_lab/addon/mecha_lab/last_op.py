"""0.24.82 Last operation: do the last drawn part again with the settings you have now.

A drawing tool that makes a new part (Armor Plate, Base Mesh, Creature Plate, Plate Detail, Flower Plate, Scale
Brush, Belt, Surface Draw, Cape / Hood / Scarf / Garment, Hair, Spikes / Scales, Bridge ...) is remembered when it
finishes: the stroke (its loops / line in screen space), the view it was drawn in (frozen), the targets it was
drawn over, and the objects it made.  Change the tool's settings (the top bar, the Quick HUD, the panel) and press
**Redo Last** (Actions card, Mecha Menu, N panel): the parts it made go, and the same stroke is drawn again from
the same view with the settings of now - as if you had set them before drawing.

Tools that change an existing mesh (Cut, Split, Box Hide, Mask ...) are not remembered here: a plain Cut already
stays live (ramp_edit 'cutlive': its sliders cut it again), the others are cheap to draw again.

The record lives in Python for the session (not in the file): a Ctrl+Z past the stroke, a reload, or a stroke of
another tool replaces / drops it.  The record is a plain dict, so ``replay`` is tested headless.
"""
from __future__ import annotations

import bpy

from . import core_geometry as cg

# modes remembered: the ones that make a new object (see cut_engine StrokeLogic._execute_closed)
MODES = {'PLATE', 'CPLATE', 'FLOWER', 'CAPE', 'HAIR', 'GARMENT', 'HOOD', 'SCARF', 'WRINKLE', 'DETAIL', 'DETAIL2',
         'DETAIL3', 'BASE', 'CBASE', 'SDRAW', 'SCAPE', 'SCURVE', 'BRIDGE', 'SBRUSH', 'SPIKE', 'SCALES', 'BELT',
         'RIDGE', 'SHELL'}
_LAST = [None]


class Replay:
    """Stands in for the drawing gate (cut_engine.StrokeLogic) when its ``_execute_closed`` runs again: the same
    attributes and helpers, answering from the record instead of the mouse."""

    def __init__(self, rec):
        from . import armor_plate as ap
        self.rec = rec
        self.mode = rec['mode']
        self.shape = rec['shape']
        self.pts = [tuple(p) for p in rec['pts']]
        self.anchor = tuple(rec['anchor']) if rec.get('anchor') else None
        self.mouse = tuple(rec['mouse']) if rec.get('mouse') else None
        self.ctrl_held = self.shift_held = False
        self.alt_latch, self.alt_held = bool(rec.get('inverted')), False
        self.auto_target = False
        self.target_names = list(rec.get('targets', []))
        self.projector = ap.thaw_projector(rec['proj'])
        self.brush = bpy.context.scene.mch_brush
        self.sharp, self.overrides = [], []

    def inverted(self):
        return self.alt_latch

    def _line_mode(self):
        return bool(self.rec.get('line_mode'))

    def _fill_area(self):
        return bool(self.rec.get('fill'))

    def _current_loops(self, event_ctrl=False, event_shift=False):
        return [[tuple(q) for q in lp] for lp in self.rec.get('loops', [])]

    def _line_loops(self, path=None):
        return self._current_loops()

    def _line_path(self, pts=None):
        return [tuple(q) for q in self.rec.get('path', [])]

    def _targets(self):
        return [bpy.data.objects[n] for n in self.target_names if n in bpy.data.objects]

    def _line_attach(self, context, base_mesh):
        at = self.rec.get('attach')
        if not at:
            return None, None
        from mathutils import Vector
        path, a, b = at
        return ([tuple(q) for q in path], (Vector(a[0]), Vector(a[1])) if a else None,
                (Vector(b[0]), Vector(b[1])) if b else None), self._current_loops() or None

    def _live_cut(self, context, targets):
        return False


def capture(gate, context):
    """Everything a stroke's run needs, taken from the gate BEFORE it runs (its state is cleared after).
    Returns None for a tool that is not remembered."""
    if gate.mode not in MODES:
        return None
    from . import armor_plate as ap
    from . import lasso_sketch
    if lasso_sketch.enabled(context, gate.mode):
        return None                                        # (a sketch: nothing is made yet)
    proj = ap.freeze_projector(gate.projector)
    if proj is None:
        return None
    try:
        line_mode = bool(gate._line_mode())
        loops = [[tuple(q) for q in lp] for lp in (gate._current_loops(gate.ctrl_held, gate.shift_held) or [])]
        path = [tuple(q) for q in gate._line_path()] if gate.pts else []
    except (AttributeError, TypeError, ValueError, cg.CutError):
        return None
    rec = dict(mode=gate.mode, shape=gate.shape, pts=[tuple(p) for p in gate.pts], anchor=gate.anchor,
               mouse=gate.mouse, inverted=bool(gate.inverted()), line_mode=line_mode, fill=bool(gate._fill_area()),
               loops=loops, path=path, proj=proj, targets=[o.name for o in gate._targets()])
    if gate.mode in {'BASE', 'CBASE'} and line_mode:
        try:
            from . import base_mesh
            at, _loops = gate._line_attach(context, base_mesh)
            if at:
                p, a, b = at
                rec['attach'] = ([tuple(q) for q in p], (tuple(a[0]), tuple(a[1])) if a else None,
                                 (tuple(b[0]), tuple(b[1])) if b else None)
        except (AttributeError, TypeError, ValueError, cg.CutError):
            pass
    return rec


def remember(rec, made, label=''):
    """After the stroke ran: ``made`` = the objects it created (names).  Nothing made = nothing to redo."""
    if rec is None or not made:
        return
    rec = dict(rec, made=list(made), label=label or rec['mode'])
    _LAST[0] = rec


def record():
    return _LAST[0]


def forget():
    _LAST[0] = None


def available(context=None):
    """There is a last stroke, and the parts it made are still around (any of them)."""
    rec = _LAST[0]
    return rec is not None and any(n in bpy.data.objects for n in rec['made'])


def label():
    rec = _LAST[0]
    if rec is None:
        return ''
    from . import tool_state as ts
    t = ts.TOOL_BY_ID.get(rec['mode']) if hasattr(ts, 'TOOL_BY_ID') else None
    name = t[1] if t is not None and len(t) > 1 else rec['mode']
    return f'{name} ({len(rec["made"])} part{"s" if len(rec["made"]) != 1 else ""})'


def replay(context):
    """The parts the last stroke made go; the stroke runs again with the settings of now.  Returns the tool's
    message."""
    from . import cut_engine
    rec = _LAST[0]
    if rec is None:
        raise cg.CutError('Nothing to redo: draw something with a part-making tool first.')
    for n in rec['made']:
        ob = bpy.data.objects.get(n)
        if ob is None:
            continue
        me = ob.data if ob.type == 'MESH' else None
        bpy.data.objects.remove(ob, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    before = set(bpy.data.objects.keys())
    g = Replay(rec)
    msg = cut_engine.StrokeLogic._execute_closed(g, context)
    made = [n for n in bpy.data.objects.keys() if n not in before]
    _LAST[0] = dict(rec, made=made) if made else None
    return msg or 'Redone'


class MCH_OT_last_redo(bpy.types.Operator):
    """Draw the last part again with the settings you have now (its parts are replaced)"""
    bl_idname = 'mch.last_redo'
    bl_label = 'Redo Last'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and available(context)

    def execute(self, context):
        try:
            msg = replay(context)
        except cg.CutError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        except Exception as ex:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f'Redo Last failed: {ex}')
            return {'CANCELLED'}
        self.report({'INFO'}, 'Redo Last: ' + msg)
        return {'FINISHED'}


def draw(layout, context):
    """A row in a panel: what the last stroke was, and the button."""
    if not available(context):
        return
    row = layout.row(align=True)
    row.label(text='Last: ' + label(), icon='LOOP_BACK')
    row.operator('mch.last_redo', text='Redo with current settings', icon='FILE_REFRESH')


def _on_load(*_args):
    forget()


def register():
    bpy.utils.register_class(MCH_OT_last_redo)
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)


def unregister():
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    forget()
    bpy.utils.unregister_class(MCH_OT_last_redo)
