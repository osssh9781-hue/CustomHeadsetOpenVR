"""0.24.82 Toasts: a short message drawn in the viewport for a few seconds - what went wrong (a cut that could not
run, a part kept as it was, Redo Last / Apply failures) and the few things worth a glance (what Redo Last did).

Blender puts an operator's WARNING in the status bar for a moment and the INFO log; in a full-screen viewport that
is easy to miss.  ``show`` queues a line (at most ``MAX`` are kept, the newest at the bottom), the drawn UI draws
them above the bottom toolbar for ``SECONDS`` with a short fade, a timer keeps the viewport redrawing while one is
up.  ``show`` / ``active`` / ``clear`` are pure (tested headless); drawing is in ``draw``.
"""
from __future__ import annotations

import time

import bpy

SECONDS = 4.0
FADE = 0.6
MAX = 3
_QUEUE = []             # [(expires at, kind, text)]
_TIMER = [False]
COLORS = {'ERROR': (0.95, 0.30, 0.25), 'WARNING': (1.0, 0.72, 0.25), 'INFO': (0.55, 0.80, 1.0)}


def show(text, kind='WARNING', seconds=None, now=None):
    """Queue a toast.  ``kind`` ERROR / WARNING / INFO colours it."""
    text = (text or '').strip()
    if not text:
        return
    now = time.monotonic() if now is None else now
    text = text.splitlines()[0][:160]
    _QUEUE[:] = [q for q in _QUEUE if q[2] != text]               # (the same line again: moved to the bottom)
    _QUEUE.append((now + (SECONDS if seconds is None else seconds), kind if kind in COLORS else 'INFO', text))
    del _QUEUE[:-MAX]
    _arm()


def active(now=None):
    """[(seconds left, kind, text)] of the toasts still up, oldest first."""
    now = time.monotonic() if now is None else now
    _QUEUE[:] = [q for q in _QUEUE if q[0] > now]
    return [(q[0] - now, q[1], q[2]) for q in _QUEUE]


def clear():
    _QUEUE.clear()


def _arm():
    if _TIMER[0] or bpy.app.background:
        return
    try:
        bpy.app.timers.register(_tick, first_interval=0.1)
        _TIMER[0] = True
    except (ValueError, RuntimeError):
        pass


def _tick():
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except (AttributeError, RuntimeError, ReferenceError):
        pass
    if active():
        return 0.1
    _TIMER[0] = False
    return None


def draw(context, region_w, region_h, k=1.0, bottom=0.0):
    """Draw the toasts above ``bottom`` (the bottom toolbar's top), centred."""
    rows = active()
    if not rows:
        return
    from . import ui_gpu as G
    size = int(13 * k)
    h = 26 * k
    y = bottom + 12 * k
    for left, kind, text in rows:
        a = min(1.0, left / FADE)
        w = min(region_w - 40 * k, max(200 * k, len(text) * size * 0.58 + 40 * k))
        x = (region_w - w) / 2
        G.rounded_rect(x, y, w, h, 6 * k, (0.08, 0.09, 0.11, 0.88 * a))
        r, g, b = COLORS[kind]
        G.rounded_rect(x, y, 4 * k, h, 2 * k, (r, g, b, a))
        G.text(x + 14 * k, y + h / 2, G.fit(text, size, w - 28 * k), size, (0.95, 0.95, 0.95, a))
        y += h + 6 * k


def report(op, kind, text):
    """``op.report`` plus a toast for WARNING / ERROR (the usual call in a tool)."""
    try:
        op.report({kind}, text)
    except (TypeError, RuntimeError):
        pass
    if kind in ('WARNING', 'ERROR'):
        show(text, kind)
