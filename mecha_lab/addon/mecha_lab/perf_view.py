"""0.24.277 (user: "뷰포트 성능 표시는 좋다") Viewport performance on the Render page.

* Drawing: how long the 3D view takes to draw itself once (from the start of its scene drawing to the end of its last
  overlay - the median of the last redraws), and the frames per second that allows.  It is the time Blender spends
  sending the drawing; a graphics card still busy after it is not counted, so it is a lower bound.
* Visible: the triangles the viewport draws now (evaluated: modifiers counted, a Light Copy counted as its copy, every
  instance counted) and in how many parts.
* The heaviest parts (5): their triangles and share; click the name = select it; Hide (eye off); a part with a
  Subdivision / Multires drawn at a viewport level above 0: "Subdiv 0" draws it at level 0 in the viewport only (renders
  keep their level) - "Subdiv Back" puts the level it had back.
Counted at most every 2 s, only while the Render page is shown."""
from __future__ import annotations

import statistics
import time

import bpy

SUBD_KEY = 'mch_perf_subd'          # on a part: {modifier name: its old viewport level}
_T = {'start': None, 'ms': []}
_SCAN = {'t': -1e9, 'val': None}
_H = [None, None]


def _start_draw():
    _T['start'] = time.perf_counter()


def _end_draw():
    t0 = _T['start']
    if t0 is None:
        return
    _T['start'] = None
    ms = (time.perf_counter() - t0) * 1000.0
    g = _T['ms']
    g.append(ms)
    if len(g) > 40:
        del g[:-40]


def frame_ms():
    """The 3D view's drawing time per redraw (ms, the median of the last ones), or None before 3 redraws."""
    g = _T['ms']
    if len(g) < 3:
        return None
    return statistics.median(g[-20:])


def _tris(me):
    try:
        return max(0, len(me.loops) - 2 * len(me.polygons))
    except (AttributeError, ReferenceError, RuntimeError):
        return 0


def scan(context, force=False):
    """{'total', 'parts', 'top': [(name, tris)]} of what the viewport draws now (kept 2 s)."""
    now = time.monotonic()
    if not force and _SCAN['val'] is not None and now - _SCAN['t'] < 2.0:
        return _SCAN['val']
    per = {}
    total = 0
    try:
        dg = context.evaluated_depsgraph_get()
        for inst in dg.object_instances:
            ob = inst.object
            if ob.type != 'MESH':
                continue
            src = (inst.parent if inst.is_instance and inst.parent is not None else ob).original
            n = _tris(ob.data)
            total += n
            per[src.name] = per.get(src.name, 0) + n
    except (ReferenceError, RuntimeError, AttributeError):
        pass
    top = sorted(per.items(), key=lambda kv: -kv[1])[:5]
    val = {'total': total, 'parts': len(per), 'top': top}
    _SCAN.update(t=now, val=val)
    return val


def _subd_mods(ob):
    return [m for m in getattr(ob, 'modifiers', ()) if m.type in {'SUBSURF', 'MULTIRES'}]


def subd_level(ob):
    """The highest viewport level of its Subdivision / Multires (shown), or 0."""
    lv = 0
    for m in _subd_mods(ob):
        if m.show_viewport:
            lv = max(lv, m.levels if m.type == 'SUBSURF' else m.levels)
    return lv


def _fmt(n):
    return f'{n / 1e6:.1f} M' if n >= 1e6 else (f'{n / 1e3:.0f} K' if n >= 1e3 else str(n))


class MCH_OT_perf_part(bpy.types.Operator):
    """A heavy part: select it / hide it (eye off) / its Subdivision at viewport level 0 (renders keep theirs) / back"""
    bl_idname = 'mch.perf_part'
    bl_label = 'Heavy Part'
    bl_options = {'REGISTER', 'UNDO'}
    name: bpy.props.StringProperty()
    action: bpy.props.EnumProperty(items=[('SELECT', 'Select', ''), ('HIDE', 'Hide', ''), ('SUBD0', 'Subdiv 0', ''),
                                          ('SUBDBACK', 'Subdiv Back', '')], default='SELECT')

    def execute(self, context):
        import json
        ob = bpy.data.objects.get(self.name)
        if ob is None:
            return {'CANCELLED'}
        if self.action == 'SELECT':
            for o in list(context.selected_objects):
                o.select_set(False)
            try:
                ob.select_set(True)
                context.view_layer.objects.active = ob
            except RuntimeError:
                pass
        elif self.action == 'HIDE':
            ob.hide_set(True)
        elif self.action == 'SUBD0':
            old = {}
            for m in _subd_mods(ob):
                if m.levels > 0:
                    old[m.name] = m.levels
                    m.levels = 0
            if old:
                ob[SUBD_KEY] = json.dumps(old)
        else:
            try:
                old = json.loads(ob.get(SUBD_KEY, '{}'))
            except ValueError:
                old = {}
            for name, lv in old.items():
                m = ob.modifiers.get(name)
                if m is not None and m.levels == 0:
                    m.levels = int(lv)
            if SUBD_KEY in ob:
                del ob[SUBD_KEY]
        _SCAN['val'] = None
        try:
            from . import side_panel
            side_panel.dirty()
        except (ImportError, AttributeError):
            pass
        return {'FINISHED'}


def section(b, context, x, width):
    """The Render page's Performance section."""
    from . import mech_shader_ui as mu, i18n
    ko = i18n.lang() == 'KO'
    s = scan(context)
    ms = frame_ms()

    def fill(sx, sw):
        if ms is None:
            txt = '그리기: 뷰를 움직이면 잼' if ko else 'Drawing: move the view to measure'
        else:
            fps = 1000.0 / ms if ms > 0 else 0
            txt = (f'그리기: 한 번에 {ms:.0f} ms (최대 {fps:.0f} fps)' if ko else
                   f'Drawing: {ms:.0f} ms each time (up to {fps:.0f} fps)')
        slow = ms is not None and ms > 50
        b.note(('note', txt, slow, None, None, None, True), sx, sw)
        b.note(('note', (f'보이는 것: 삼각형 {_fmt(s["total"])} · 파트 {s["parts"]} 개' if ko else
                         f'Visible: {_fmt(s["total"])} triangles in {s["parts"]} parts'), False, None, None, None,
                True), sx, sw)
        for name, n in s['top']:
            if n <= 0:
                continue
            share = n * 100.0 / max(s['total'], 1)
            ob = bpy.data.objects.get(name)
            cells = [mu._cell('tbtn', f'{name}  {_fmt(n)} ({share:.0f}%)',
                              ('op', 'mch.perf_part', {'name': name, 'action': 'SELECT'}))]
            if ob is not None and ob.get(SUBD_KEY):
                cells.append(mu.button('Subdiv Back', 'mch.perf_part', name=name, action='SUBDBACK'))
            elif ob is not None and subd_level(ob) > 0:
                cells.append(mu.button('Subdiv 0', 'mch.perf_part', name=name, action='SUBD0'))
            cells.append(mu.button('Hide', 'mch.perf_part', name=name, action='HIDE'))
            b.place_row(cells, sx, sw, columns=len(cells))
    summ = (f'{ms:.0f} ms  ' if ms is not None else '') + _fmt(s['total'])
    mu.section(b, 'perf', i18n.tr('Performance'), x, width, fill, summary=summ, colour=mu.COLOURS['perf'])


CLASSES = (MCH_OT_perf_part,)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    if _H[0] is None:
        _H[0] = bpy.types.SpaceView3D.draw_handler_add(_start_draw, (), 'WINDOW', 'PRE_VIEW')
        _H[1] = bpy.types.SpaceView3D.draw_handler_add(_end_draw, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    for i, h in enumerate(_H):
        if h is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(h, 'WINDOW')
            except (ValueError, RuntimeError):
                pass
            _H[i] = None
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
