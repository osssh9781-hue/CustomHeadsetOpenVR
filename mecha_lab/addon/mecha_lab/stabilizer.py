"""Free Draw stroke stabilizer (Lazy Mouse), docs/06 F08.

The drawn point does NOT jump to the mouse.  It follows it in real time:

* Lazy Radius (px): while the cursor stays within this distance of the drawn
  point, the point does not move (hand tremor is ignored).  Further away, the
  point is pulled toward the cursor until it is back on the circle - the
  ZBrush "string" behaviour.
* Smoothing Strength (0..100 %): the pull is an exponential approach with a
  time constant, ``alpha = 1 - exp(-dt / tau)``, so the feel is the same at
  any mouse event rate (dt-aware).  0 % = instant.
* Stroke Spacing (px, the existing Free Draw "Sample Spacing"): a new outline
  point is emitted only when the drawn point moved that far from the last one.

A modal TIMER keeps calling ``tick`` so the drawn point keeps gliding when the
mouse stops.  ``finish`` lets the point catch up with the release position in
small steps (no long straight jump, no duplicate last point).

Settings are read from the brush on every update, so changing them applies
at once.  With the stabilizer OFF, or Strength 0 and Radius 0, Free Draw uses
exactly the old code path (``active`` is False).
"""
from __future__ import annotations

import math

MAX_TAU = 0.35            # seconds: time constant at 100 % strength
CATCH_UP_DT = 1.0 / 60.0
CATCH_UP_STEPS = 240


def tau_for(strength_pct):
    s = max(0.0, min(100.0, strength_pct)) / 100.0
    return MAX_TAU * s * s      # gentle at low values, strong near 100 %


class LazyStabilizer:
    def __init__(self, brush):
        self.brush = brush
        self.pos = None
        self.t = None
        self.cursor = None

    # settings are live ----------------------------------------------------
    @property
    def radius(self):
        return max(0.0, float(getattr(self.brush, 'stab_radius', 0.0)))

    @property
    def strength(self):
        return max(0.0, min(100.0, float(getattr(self.brush, 'stab_strength', 0.0))))

    @property
    def active(self):
        return bool(getattr(self.brush, 'stab_enable', False)) and (self.radius > 0.0 or self.strength > 0.0)

    # state -------------------------------------------------------------------
    def reset(self, xy, t):
        self.pos = (float(xy[0]), float(xy[1]))
        self.cursor = self.pos
        self.t = t

    def _target(self, cursor, radius):
        dx, dy = cursor[0] - self.pos[0], cursor[1] - self.pos[1]
        d = math.hypot(dx, dy)
        if d <= radius:
            return self.pos
        k = (d - radius) / d
        return (self.pos[0] + dx * k, self.pos[1] + dy * k)

    def _step(self, cursor, dt, radius=None):
        radius = self.radius if radius is None else radius
        target = self._target(cursor, radius)
        tau = tau_for(self.strength)
        alpha = 1.0 if tau <= 1e-9 else 1.0 - math.exp(-max(dt, 0.0) / tau)
        self.pos = (self.pos[0] + (target[0] - self.pos[0]) * alpha,
                    self.pos[1] + (target[1] - self.pos[1]) * alpha)
        return self.pos

    def update(self, cursor, t):
        """Mouse moved to ``cursor`` at time ``t``: returns the new drawn point."""
        if self.pos is None:
            self.reset(cursor, t)
            return self.pos
        dt = t - self.t if self.t is not None else 0.0
        self.t = t
        self.cursor = (float(cursor[0]), float(cursor[1]))
        return self._step(self.cursor, dt)

    def tick(self, t):
        """Timer event: keep gliding toward the last cursor position."""
        if self.pos is None or self.cursor is None:
            return self.pos
        return self.update(self.cursor, t)

    def finish(self, cursor, spacing=None):
        """Release: catch up with the release position in small steps.
        Returns the points to append (spaced, ending exactly at ``cursor``)."""
        if self.pos is None:
            return [tuple(cursor)]
        spacing = max(1.0, float(spacing if spacing is not None else getattr(self.brush, 'stroke_spacing', 4.0)))
        cursor = (float(cursor[0]), float(cursor[1]))
        out = []
        last = self.pos
        for i in range(CATCH_UP_STEPS):
            # the lazy radius shrinks to zero so the stroke really reaches the cursor
            r = self.radius * max(0.0, 1.0 - (i + 1) / 20.0)
            p = self._step(cursor, CATCH_UP_DT, r)
            d = math.dist(p, last)
            if d >= spacing:
                n = int(d // spacing)           # never leave a gap longer than one spacing
                for k in range(1, n + 1):
                    f = k * spacing / d
                    out.append((last[0] + (p[0] - last[0]) * f, last[1] + (p[1] - last[1]) * f))
                last = out[-1]
            if math.dist(p, cursor) < 0.5:
                break
        if not out or math.dist(out[-1], cursor) > 0.5:
            out.append(cursor)
        return out
