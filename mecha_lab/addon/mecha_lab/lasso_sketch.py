"""0.19.3 Sketch First for every lasso tool (Cut, Split, Armor Plate; Base
Mesh keeps its own sketch, switched by the same button).

With the Sketch button on (next to the shapes in the viewport header):
    draw          add the outline to a sketch (tool colour, filled)
    Alt + draw    subtract it from the sketch
    Enter         apply the tool with the combined outline
    Alt + Enter   the tool's Alt action (Cut: keep inside)
    Backspace     remove the last outline,  Esc  clear the sketch

The sketch lives on a plane facing the view of the first outline, so the view
can be orbited between outlines; the tool runs with that first view
(``armor_plate.FrozenProjector``).  The outline boolean is Base Mesh's
``sketch_regions`` (constrained Delaunay, exact overlaps / holes).
"""
from __future__ import annotations

import json

import bpy
from bpy.props import BoolProperty
from mathutils import Matrix, Vector

from . import core_geometry as cg
from . import tool_state as ts

KEY = 'mch_lasso_sketch'          # Scene ID prop (JSON) - Ctrl+Z steps back through it
MODES = {'CUT', 'SPLIT', 'PLATE', 'WRINKLE', 'DETAIL', 'DETAIL2', 'DETAIL3', 'HIDE'}   # 0.24.1 + Plate Detail 1 / 2, Box Hide


def is_on(context):
    """Sketch state shown on the button for the current tool (Base Mesh has its own)."""
    scene = context.scene
    if ts.effective_tool(context) == 'BASE' and hasattr(scene, 'mch_base'):
        return bool(scene.mch_base.sketch)
    return bool(getattr(getattr(scene, 'mch_brush', None), 'sketch_first', False))


def set_on(context, value):
    scene = context.scene
    scene.mch_brush.sketch_first = value
    if hasattr(scene, 'mch_base'):
        scene.mch_base.sketch = value


def enabled(context, mode):
    brush = getattr(context.scene, 'mch_brush', None)
    return bool(brush is not None and getattr(brush, 'sketch_first', False) and mode in MODES)


def data(scene):
    text = scene.get(KEY) if scene is not None else None
    if not text:
        return None
    try:
        d = json.loads(text)
    except (TypeError, ValueError):
        return None
    return d if d.get('items') else None


def clear(scene):
    if scene is not None and KEY in scene:
        del scene[KEY]


def _frame(d):
    m = Matrix.Identity(4)
    for r in range(4):
        for c in range(4):
            m[r][c] = d['frame'][r * 4 + c]
    return m


def add(context, mode, loops, projector, subtract=False):
    """Add (Alt: subtract) a drawn outline to the sketch of ``mode``."""
    from . import armor_plate as ap
    from . import base_mesh as bm_
    scene = context.scene
    groups = cg.prepare_loops(loops)
    d = data(scene)
    if d is not None and d.get('mode') != mode:
        d = None                                        # another tool: start over
    if d is None:
        if subtract:
            raise cg.CutError('Draw a shape first: Alt subtracts from the sketch.')
        frozen = ap.freeze_projector(projector)
        if frozen is None:
            raise cg.CutError('Sketch needs a 3D viewport.')
        origin, x, y, n = bm_.plane_frame(context, projector, groups)
        frame = Matrix.Identity(4)
        for r in range(3):
            frame[r][0], frame[r][1], frame[r][2], frame[r][3] = x[r], y[r], n[r], origin[r]
        d = {'mode': mode, 'frame': [frame[r][c] for r in range(4) for c in range(4)], 'proj': frozen, 'items': []}
    frame = _frame(d)
    origin, n = frame.translation, frame.col[2].to_3d().normalized()
    inv = frame.inverted()

    def to_local(q):
        o, dv = projector.ray(q)
        if abs(dv.dot(n)) < 1e-6:
            raise cg.CutError('The view is edge-on to the sketch: orbit a little and draw again.')
        v = inv @ cg._plane_hit(o, dv, origin, n)[0]
        return (v.x, v.y)
    local = cg.organize_loops([[to_local(q) for q in lp] for outer, holes in groups for lp in [outer] + holes])
    d['items'].append({'op': 'SUB' if subtract else 'ADD',
                       'groups': [[[list(q) for q in o], [[list(q) for q in h] for h in hs]] for o, hs in local]})
    scene[KEY] = json.dumps(d)
    pieces = bm_.sketch_regions(d['items'])
    name = ts.TOOL_BY_ID[mode][1]
    return (f'{name} sketch: {"subtracted" if subtract else "added"} ({len(pieces)} piece(s)) | '
            f'Enter: {"hide" if mode == "HIDE" else "apply"}, Alt+Enter: '
            f'{"keep inside" if mode == "CUT" else "show again" if mode == "HIDE" else "apply"}, '
            f'Backspace: last, Esc: clear')


def screen_loops(d):
    """The combined sketch as screen loops in the first view, + that view."""
    from . import armor_plate as ap
    from . import base_mesh as bm_
    proj = ap.thaw_projector(d['proj'])
    frame = _frame(d)
    loops = []
    for outer, holes in bm_.sketch_regions(d['items']):
        for lp in [outer] + list(holes):
            pts = [proj.to_screen(frame @ Vector((q[0], q[1], 0.0))) for q in lp]
            if any(p is None for p in pts):
                raise cg.CutError('The sketch is behind the view it was drawn in.')
            loops.append([tuple(p) for p in pts])
    return loops, proj


def commit(context, alt=False):
    """Run the tool once with the combined outline.  The sketch is cleared on success."""
    scene = context.scene
    d = data(scene)
    if d is None:
        raise cg.CutError('No sketch: draw with the Sketch button on first.')
    loops, proj = screen_loops(d)
    if not loops:
        raise cg.CutError('The sketch is empty (everything was subtracted). Esc clears it.')
    mode = d['mode']
    if mode == 'PLATE':
        from . import armor_plate as ap
        msg = ap.perform_plate(context, loops, proj)
    elif mode == 'WRINKLE':
        from . import cloth_wrinkle as cw
        msg = cw.perform_wrinkle(context, loops, proj)
    elif mode in {'DETAIL', 'DETAIL2', 'DETAIL3'}:
        from . import plate_detail as pd
        msg = pd.perform(context, loops, proj, mode)
    elif mode == 'HIDE':
        from . import box_hide as bh
        from . import cut_engine as ce
        # 0.24.11 the Targets setting counts here too (Selected Only / Active), like a drawn Box Hide
        how = getattr(getattr(scene, 'mch_cut', None), 'targets', 'AUTO')
        targets = ce.auto_targets(context.view_layer, proj, loops)
        if how == 'SELECTED':
            targets = [o for o in targets if o.select_get()]
        elif how == 'ACTIVE':
            targets = [o for o in targets if o == context.active_object]
        if not targets:
            raise cg.CutError('The sketch does not cover a mesh' + ('' if how == 'AUTO' else ' (selected)') +
                              ': nothing was hidden.')
        msg = bh.perform(context, targets, loops, proj, restore=alt)
    else:
        from . import cut_engine as ce
        how = getattr(getattr(scene, 'mch_cut', None), 'targets', 'AUTO')
        if how == 'AUTO':
            targets = ce.auto_targets(context.view_layer, proj, loops)
        elif how == 'ACTIVE':
            ob = context.active_object
            targets = [ob] if ob is not None and ob.type == 'MESH' else []
        else:
            targets = [o for o in context.selected_objects if o.type == 'MESH']
        if not targets:
            raise cg.CutError('The sketch does not cover a mesh (or select one): nothing was changed.')
        msg = ce.perform_closed(context, mode, targets, loops, proj, alt)
    clear(scene)
    return msg


# -----------------------------------------------------------------------------
# Drawing
# -----------------------------------------------------------------------------

_CACHE = {}
_handle = None


def _draw_data(scene):
    text = scene.get(KEY)
    hit = _CACHE.get('v')
    if hit is not None and hit[0] == text:
        return hit[1]
    from . import base_mesh as bm_
    d = data(scene)
    out = None
    if d is not None:
        frame = _frame(d)
        verts, tris = bm_.sketch_triangles(d['items'])
        world = [tuple(frame @ Vector((v[0], v[1], 0.0))) for v in verts]
        lines = []
        for lp in (bm_._boundary_loops(verts, tris) if tris else []):
            pts = [tuple(frame @ Vector((q[0], q[1], 0.0))) for q in lp]
            for i in range(len(pts)):
                lines += [pts[i], pts[(i + 1) % len(pts)]]
        out = (d['mode'], world, tris, lines)
    _CACHE['v'] = (text, out)
    return out


def _draw():
    try:
        context = bpy.context
        scene = context.scene
        if scene is None or not scene.get(KEY):
            return
        dd = _draw_data(scene)
        if not dd or ts.effective_tool(context) != dd[0]:
            return
        import gpu
        from gpu_extras.batch import batch_for_shader
        from . import cut_engine as ce
        mode, world, tris, lines = dd
        col = ce.stroke_color(mode, False)[:3]
        sh = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('NONE')
        if tris:
            sh.uniform_float('color', (*col, 0.18))
            batch_for_shader(sh, 'TRIS', {'pos': world}, indices=tris).draw(sh)
        if lines:
            gpu.state.line_width_set(2.0)
            sh.uniform_float('color', (*col, 0.95))
            batch_for_shader(sh, 'LINES', {'pos': lines}).draw(sh)
            gpu.state.line_width_set(1.0)
        gpu.state.blend_set('NONE')
    except Exception:        # never break viewport drawing
        pass


# -----------------------------------------------------------------------------
# Operators (Enter / Alt+Enter / Backspace / Esc in the lasso tools)
# -----------------------------------------------------------------------------


def _key_poll(context):
    try:
        d = data(context.scene)
        return (d is not None and context.area is not None and context.area.type == 'VIEW_3D' and
                ts.effective_tool(context) == d.get('mode'))
    except (AttributeError, KeyError, TypeError):
        return False


class MCH_OT_lasso_sketch_commit(bpy.types.Operator):
    """Apply the tool with the sketch (Enter).  Alt+Enter: the tool's Alt action (Cut: keep inside)"""
    bl_idname = 'mch.lasso_sketch_commit'
    bl_label = 'Apply Sketch'
    bl_options = {'REGISTER', 'UNDO'}
    alt: BoolProperty(name='Alt Action', default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and data(context.scene) is not None

    def execute(self, context):
        try:
            msg = commit(context, self.alt)
        except cg.CutError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class MCH_OT_lasso_sketch_key(bpy.types.Operator):
    """Enter / Alt+Enter in a lasso tool while a sketch exists"""
    bl_idname = 'mch.lasso_sketch_key'
    bl_label = 'Sketch Key'
    bl_options = {'INTERNAL'}
    alt: BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return _key_poll(context)

    def execute(self, context):
        return bpy.ops.mch.lasso_sketch_commit('EXEC_DEFAULT', alt=self.alt)


class MCH_OT_lasso_sketch_clear(bpy.types.Operator):
    """Throw the sketch away (Esc)"""
    bl_idname = 'mch.lasso_sketch_clear'
    bl_label = 'Clear Sketch'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _key_poll(context) or (context.area is None and data(context.scene) is not None)

    def execute(self, context):
        clear(context.scene)
        self.report({'INFO'}, 'Sketch cleared')
        return {'FINISHED'}


class MCH_OT_lasso_sketch_undo(bpy.types.Operator):
    """Remove the last outline from the sketch (Backspace)"""
    bl_idname = 'mch.lasso_sketch_undo'
    bl_label = 'Remove Last Sketch Outline'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return data(context.scene) is not None

    def execute(self, context):
        d = data(context.scene)
        d['items'].pop()
        if d['items']:
            context.scene[KEY] = json.dumps(d)
        else:
            clear(context.scene)
        return {'FINISHED'}


class MCH_OT_sketch_toggle(bpy.types.Operator):
    """Sketch First for the lasso tools: draw outlines, Alt+draw subtracts, Enter applies"""
    bl_idname = 'mch.sketch_toggle'
    bl_label = 'Sketch'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        set_on(context, not is_on(context))
        return {'FINISHED'}


KEYMAP = (
    ('mch.lasso_sketch_key', {'type': 'RET', 'value': 'PRESS'}, None),
    ('mch.lasso_sketch_key', {'type': 'NUMPAD_ENTER', 'value': 'PRESS'}, None),
    ('mch.lasso_sketch_key', {'type': 'RET', 'value': 'PRESS', 'alt': True}, {'properties': [('alt', True)]}),
    ('mch.lasso_sketch_key', {'type': 'NUMPAD_ENTER', 'value': 'PRESS', 'alt': True}, {'properties': [('alt', True)]}),
    ('mch.lasso_sketch_clear', {'type': 'ESC', 'value': 'PRESS'}, None),
    ('mch.lasso_sketch_undo', {'type': 'BACK_SPACE', 'value': 'PRESS'}, None),
)

CLASSES = (MCH_OT_lasso_sketch_commit, MCH_OT_lasso_sketch_key, MCH_OT_lasso_sketch_clear, MCH_OT_lasso_sketch_undo,
           MCH_OT_sketch_toggle)


def register():
    global _handle
    for c in CLASSES:
        bpy.utils.register_class(c)
    if not bpy.app.background and _handle is None:
        _handle = bpy.types.SpaceView3D.draw_handler_add(_draw, (), 'WINDOW', 'POST_VIEW')


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
