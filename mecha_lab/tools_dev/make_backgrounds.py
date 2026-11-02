"""Make the HDRI page's built-in background pictures (0.24.95 user: "hdri 배경 컬러 말고 내가 원하는 배경 이미지를
넣을 수 있게 - 너가 기본으로 몇 장 넣어 줘, 세로 가로", "배경은 스튜디오 이미지처럼 해 줘"): 8 studio backdrops (paper
sweeps white .. black, warm, cool, a painted canvas), each landscape (1920 x 1080) and portrait (1080 x 1920),
made here from scratch (numpy; no photos) into addon/mecha_lab/backgrounds/<look>_<land|port>.jpg; (0.24.95) 10 more colours, then 30 more: paper colours,
light effects (blinds, dappled light, halo, spotlight, bokeh, beam, gels, split tone, gradient) and textures.
    python -I tools_dev/make_backgrounds.py      (a python with bpy: the JPEGs are written by Blender)"""
import os
import sys

import numpy as np

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'addon', 'mecha_lab', 'backgrounds')
RNG = np.random.default_rng(7)


def _grid(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    s = max(w, h)
    return (x - w / 2) / s, (y - h / 2) / s          # (centred, the long side -0.5 .. 0.5)


def _blur(a, r):
    """A soft blur (box blur three times, per axis) of an H x W (x C) array."""
    if r < 1:
        return a
    out = a.astype(np.float32)
    for _k in range(3):
        for ax in (0, 1):
            c = np.cumsum(np.pad(out, [(r + 1, r) if i == ax else (0, 0) for i in range(out.ndim)], mode='edge'),
                          axis=ax)
            hi = np.take(c, np.arange(2 * r + 1, c.shape[ax]), axis=ax)
            lo = np.take(c, np.arange(0, c.shape[ax] - 2 * r - 1), axis=ax)
            out = (hi - lo) / (2 * r + 1)
    return out


def _noise(w, h, scale, octaves=4):
    """Smooth value noise, 0 .. 1 (``scale`` cells across the long side; no wrap - no seam)."""
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        cell = max(w, h) / max(2.0, scale * 2 ** o)
        xs, ys = np.arange(w, dtype=np.float32) / cell, np.arange(h, dtype=np.float32) / cell
        g = RNG.random((int(ys[-1]) + 3, int(xs[-1]) + 3)).astype(np.float32)
        x0, y0 = xs.astype(int), ys.astype(int)
        fx, fy = (xs - x0)[None, :], (ys - y0)[:, None]
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        a, b = g[y0][:, x0], g[y0][:, x0 + 1]
        c, d = g[y0 + 1][:, x0], g[y0 + 1][:, x0 + 1]
        out += amp * ((a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy)
        tot += amp
        amp *= 0.5
    return out / tot


def _vignette(w, h, k=1.0):
    x, y = _grid(w, h)
    return np.clip(1.0 - k * (x * x + y * y) * 2.2, 0.0, 1.0)[..., None]


def _smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def sweep(w, h, wall, floor, spot=0.25, spot_size=0.32, top_dark=0.3, vig=0.9, horizon=0.66, paper=0.006):
    """A seamless paper sweep as a studio photo shows it: the wall going darker upwards, curving softly into a
    lighter floor (no horizon line), a soft light pool behind the subject, the corners falling off."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    t = yy / (h - 1)                                    # (0 top .. 1 bottom)
    u = (xx - w / 2) / h                                # (across, in heights - the same look both ways round)
    s = _smooth((t - (horizon - 0.16)) / 0.32)[..., None]
    col = np.array(wall, np.float32) * (1 - s) + np.array(floor, np.float32) * s
    col = col * (1.0 - top_dark * (1.0 - _smooth(t / horizon)))[..., None]
    d2 = (u / (spot_size * 1.35)) ** 2 + ((t - horizon + 0.12) / spot_size) ** 2
    col = col * (1.0 + spot * np.exp(-d2))[..., None]
    r2 = (u / max(0.5, w / h * 0.5)) ** 2 + ((t - 0.5) / 0.5) ** 2
    col = col * (1.0 - vig * 0.32 * _smooth(r2 / 1.6))[..., None]
    col = col * (1.0 + paper * (_noise(w, h, 90, 2)[..., None] - 0.5) * 2)
    return col


LOOKS = (
    ('white_sweep', 'Studio White', lambda w, h: sweep(w, h, (0.84, 0.84, 0.845), (0.92, 0.92, 0.925), spot=0.1,
                                                         top_dark=0.18, vig=0.45)),
    ('light_grey', 'Light Grey Paper', lambda w, h: sweep(w, h, (0.56, 0.565, 0.57), (0.64, 0.645, 0.65), spot=0.22)),
    ('mid_grey_spot', 'Grey Spotlight', lambda w, h: sweep(w, h, (0.22, 0.225, 0.23), (0.27, 0.275, 0.28), spot=1.1,
                                                            spot_size=0.28, vig=1.0)),
    ('charcoal', 'Charcoal', lambda w, h: sweep(w, h, (0.085, 0.088, 0.092), (0.11, 0.112, 0.116), spot=0.9,
                                                spot_size=0.3, vig=1.0)),
    ('black_key', 'Black Studio', lambda w, h: sweep(w, h, (0.034, 0.034, 0.037), (0.05, 0.05, 0.054), spot=1.5,
                                                     spot_size=0.24, top_dark=0.45, vig=1.0)),
    ('warm_paper', 'Warm Paper', lambda w, h: sweep(w, h, (0.66, 0.58, 0.49), (0.73, 0.65, 0.56), spot=0.22)),
    ('cool_blue', 'Cool Blue-Grey', lambda w, h: sweep(w, h, (0.27, 0.32, 0.38), (0.32, 0.37, 0.43), spot=0.45,
                                                       vig=0.9)),
    ('canvas', 'Painted Canvas', lambda w, h: canvas(w, h)),
    # (0.24.95 user: "프리셋 한 열 장만 더 넣어 줘")
    ('olive', 'Olive Paper', lambda w, h: sweep(w, h, (0.3, 0.32, 0.21), (0.36, 0.38, 0.26), spot=0.3)),
    ('teal', 'Deep Teal', lambda w, h: sweep(w, h, (0.05, 0.17, 0.19), (0.07, 0.22, 0.24), spot=0.75, vig=1.0)),
    ('navy', 'Navy', lambda w, h: sweep(w, h, (0.045, 0.06, 0.13), (0.06, 0.08, 0.17), spot=0.9, vig=1.0)),
    ('burgundy', 'Burgundy', lambda w, h: sweep(w, h, (0.2, 0.045, 0.06), (0.25, 0.065, 0.08), spot=0.8, vig=1.0)),
    ('sand', 'Sand', lambda w, h: sweep(w, h, (0.76, 0.7, 0.58), (0.83, 0.77, 0.65), spot=0.12, top_dark=0.2,
                                        vig=0.6)),
    ('mint', 'Pastel Mint', lambda w, h: sweep(w, h, (0.6, 0.76, 0.7), (0.68, 0.82, 0.76), spot=0.14, top_dark=0.2,
                                               vig=0.6)),
    ('peach', 'Pastel Peach', lambda w, h: sweep(w, h, (0.88, 0.68, 0.6), (0.93, 0.75, 0.67), spot=0.12,
                                                 top_dark=0.2, vig=0.6)),
    ('slate', 'Slate', lambda w, h: sweep(w, h, (0.13, 0.16, 0.2), (0.16, 0.19, 0.24), spot=1.0, spot_size=0.26,
                                          vig=1.0)),
    ('gels', 'Colour Gels', lambda w, h: gels(w, h)),
    ('canvas_brown', 'Brown Canvas', lambda w, h: canvas(w, h, (0.2, 0.15, 0.1), (0.32, 0.25, 0.16))),
    # (0.24.95 user: "HDRI 픽쳐 배경 30 개만 더 만들어 줘": 15 more paper colours, 15 light effects and textures)
    ('coral', 'Coral', lambda w, h: sweep(w, h, (0.78, 0.38, 0.3), (0.84, 0.44, 0.36), spot=0.2, vig=0.7)),
    ('lavender', 'Lavender', lambda w, h: sweep(w, h, (0.56, 0.5, 0.72), (0.62, 0.56, 0.78), spot=0.2, vig=0.7)),
    ('sky_blue', 'Sky Blue', lambda w, h: sweep(w, h, (0.4, 0.6, 0.82), (0.46, 0.66, 0.86), spot=0.2, vig=0.7)),
    ('lemon', 'Lemon', lambda w, h: sweep(w, h, (0.86, 0.78, 0.3), (0.9, 0.83, 0.38), spot=0.15, top_dark=0.2,
                                          vig=0.6)),
    ('forest', 'Forest Green', lambda w, h: sweep(w, h, (0.06, 0.17, 0.09), (0.08, 0.21, 0.11), spot=0.8, vig=1.0)),
    ('plum', 'Plum', lambda w, h: sweep(w, h, (0.26, 0.08, 0.22), (0.31, 0.1, 0.27), spot=0.7, vig=1.0)),
    ('rust', 'Rust Orange', lambda w, h: sweep(w, h, (0.5, 0.19, 0.06), (0.56, 0.23, 0.08), spot=0.4, vig=0.9)),
    ('ice', 'Ice Blue', lambda w, h: sweep(w, h, (0.72, 0.8, 0.86), (0.78, 0.85, 0.9), spot=0.12, top_dark=0.2,
                                          vig=0.6)),
    ('cream', 'Cream', lambda w, h: sweep(w, h, (0.84, 0.8, 0.7), (0.9, 0.86, 0.76), spot=0.12, top_dark=0.2,
                                          vig=0.55)),
    ('blush', 'Blush Pink', lambda w, h: sweep(w, h, (0.84, 0.64, 0.64), (0.9, 0.7, 0.7), spot=0.12, top_dark=0.2,
                                               vig=0.6)),
    ('mustard', 'Mustard', lambda w, h: sweep(w, h, (0.66, 0.47, 0.1), (0.72, 0.53, 0.13), spot=0.3, vig=0.85)),
    ('sage', 'Sage', lambda w, h: sweep(w, h, (0.48, 0.55, 0.44), (0.54, 0.6, 0.5), spot=0.2, vig=0.7)),
    ('midnight', 'Midnight', lambda w, h: sweep(w, h, (0.05, 0.04, 0.12), (0.07, 0.055, 0.15), spot=1.0, vig=1.0)),
    ('warm_grey', 'Warm Grey', lambda w, h: sweep(w, h, (0.4, 0.37, 0.33), (0.46, 0.43, 0.39), spot=0.3, vig=0.85)),
    ('crimson', 'Crimson', lambda w, h: sweep(w, h, (0.42, 0.03, 0.05), (0.48, 0.05, 0.07), spot=0.7, vig=1.0)),
    ('blinds', 'Window Blinds', lambda w, h: blinds(w, h)),
    ('dappled', 'Dappled Light', lambda w, h: dappled(w, h)),
    ('split_tone', 'Warm / Cool Split', lambda w, h: split_tone(w, h)),
    ('halo', 'Halo Ring', lambda w, h: halo(w, h)),
    ('spotlight', 'Hard Spotlight', lambda w, h: spotlight(w, h)),
    ('bokeh', 'Bokeh Lights', lambda w, h: bokeh(w, h)),
    ('beam', 'Light Beam', lambda w, h: beam(w, h)),
    ('gels_red_cyan', 'Gels Red / Cyan', lambda w, h: gels(w, h, (0.6, 0.05, 0.06), (0.03, 0.38, 0.42))),
    ('gels_purple_orange', 'Gels Purple / Orange', lambda w, h: gels(w, h, (0.32, 0.08, 0.5), (0.6, 0.3, 0.05))),
    ('sunset_gradient', 'Sunset Gradient', lambda w, h: sunset_gradient(w, h)),
    ('canvas_blue', 'Blue Canvas', lambda w, h: canvas(w, h, (0.08, 0.14, 0.24), (0.18, 0.26, 0.36))),
    ('canvas_grey', 'Grey Canvas', lambda w, h: canvas(w, h, (0.22, 0.23, 0.2), (0.34, 0.34, 0.3))),
    ('concrete', 'Concrete', lambda w, h: concrete(w, h)),
    ('infinity_white', 'Infinity White', lambda w, h: infinity_white(w, h)),
    ('kraft', 'Kraft Paper', lambda w, h: kraft(w, h)),
)


def gels(w, h, left=(0.55, 0.22, 0.06), right=(0.04, 0.3, 0.36)):
    """A dark sweep lit by two coloured gels - (by default) warm orange from the left, teal from the right."""
    base = sweep(w, h, (0.035, 0.035, 0.04), (0.05, 0.05, 0.055), spot=0.4, vig=1.0)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u, t = (xx - w / 2) / h, yy / (h - 1)
    warm = np.exp(-(((u + 0.45) / 0.45) ** 2 + ((t - 0.45) / 0.45) ** 2))[..., None] * np.array(left)
    cool = np.exp(-(((u - 0.45) / 0.45) ** 2 + ((t - 0.45) / 0.45) ** 2))[..., None] * np.array(right)
    return base + warm + cool


# --- 0.24.95 (user: "HDRI 픽쳐 배경 30 개만 더 만들어 줘") the light-effect and texture backdrops ------------------

def _ut(w, h):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    return (xx - w / 2) / h, yy / (h - 1)                    # (across in heights, 0 top .. 1 bottom)


def blinds(w, h):
    """Late light through window blinds: soft slanted bright bars on a warm grey wall, fading out at the edges."""
    col = sweep(w, h, (0.36, 0.34, 0.31), (0.42, 0.4, 0.37), spot=0.1, vig=0.8)
    u, t = _ut(w, h)
    a = np.radians(-28)
    s = (u * np.cos(a) + t * np.sin(a)) / 0.085
    f = s - np.floor(s)
    bars = _smooth((0.5 - np.abs(f - 0.5) - 0.16) / 0.12)
    patch = np.exp(-(((u + 0.1) / 0.5) ** 2 + ((t - 0.42) / 0.3) ** 2))
    return col * (1.0 + 0.95 * (_blur(bars * patch, 3))[..., None] * np.array([1.0, 0.86, 0.66]))


def dappled(w, h):
    """Sun through leaves: round soft spots of warm light (the gaps between leaves act as pinholes) on a sage-grey
    wall, thick in the middle, thinning out."""
    col = sweep(w, h, (0.3, 0.33, 0.28), (0.36, 0.38, 0.33), spot=0.1, vig=0.8)
    u, t = _ut(w, h)
    rng = np.random.default_rng(5)
    light = np.zeros((h, w), np.float32)
    for _k in range(260):
        cu, ct = rng.normal(0.0, 0.32), rng.normal(0.42, 0.22)
        rad = rng.uniform(0.008, 0.03)
        light = np.maximum(light, np.exp(-(((u - cu) / (rad * 1.3)) ** 2 + ((t - ct) / rad) ** 2)) *
                           rng.uniform(0.5, 1.0))
    return col * (1.0 + 1.1 * light[..., None] * np.array([1.0, 0.9, 0.62]))


def split_tone(w, h):
    """A grey sweep washed warm from the left and cool from the right, meeting softly behind the subject."""
    col = sweep(w, h, (0.32, 0.32, 0.32), (0.38, 0.38, 0.38), spot=0.3, vig=0.9)
    u, _t = _ut(w, h)
    k = _smooth(u / (w / h) + 0.5)[..., None]
    return col * (np.array([1.35, 1.0, 0.7]) * (1 - k) + np.array([0.7, 0.95, 1.35]) * k)


def halo(w, h):
    """A ring light behind the subject on a near-black wall: a bright thin ring with a soft glow."""
    col = sweep(w, h, (0.02, 0.02, 0.025), (0.03, 0.03, 0.035), spot=0.0, vig=1.0)
    u, t = _ut(w, h)
    r = np.sqrt(u ** 2 + (t - 0.44) ** 2)
    ring = np.exp(-((r - 0.27) / 0.012) ** 2) * 0.9 + np.exp(-((r - 0.27) / 0.07) ** 2) * 0.12
    return col + ring[..., None] * np.array([0.95, 0.97, 1.0])


def spotlight(w, h):
    """A spotlight pool on a black sweep - theatre-like: bright in the middle, a soft rim, a pool on the floor."""
    col = sweep(w, h, (0.012, 0.012, 0.014), (0.02, 0.02, 0.022), spot=0.0, vig=1.0)
    u, t = _ut(w, h)
    r = np.sqrt((u / 0.3) ** 2 + ((t - 0.46) / 0.34) ** 2)
    pool = (1 - _smooth((r - 0.8) / 0.25)) * (0.75 - 0.45 * r * r)
    floor = np.exp(-((u / 0.42) ** 2 + ((t - 0.9) / 0.07) ** 2)) * 0.25
    return col + np.clip(pool + floor, 0, None)[..., None] * np.array([0.95, 0.92, 0.85])


def bokeh(w, h):
    """Out-of-focus lights behind the subject: soft coloured discs on a dark blue-grey."""
    col = sweep(w, h, (0.03, 0.035, 0.05), (0.04, 0.045, 0.06), spot=0.3, vig=1.0)
    u, t = _ut(w, h)
    rng = np.random.default_rng(21)
    hues = ((1.0, 0.65, 0.25), (1.0, 0.85, 0.5), (0.4, 0.7, 1.0), (1.0, 0.4, 0.5), (0.6, 1.0, 0.8))
    for _k in range(46):
        cu, ct = rng.uniform(-0.5 * w / h, 0.5 * w / h), rng.uniform(0.0, 1.0)
        rad = rng.uniform(0.02, 0.07)
        d = np.sqrt((u - cu) ** 2 + (t - ct) ** 2)
        disc = 1 - _smooth((d - rad * 0.85) / (rad * 0.15))
        col = col + (disc * rng.uniform(0.06, 0.2))[..., None] * np.array(hues[_k % len(hues)])
    return col


def beam(w, h):
    """A shaft of light falling from the top left through haze onto a dark blue set."""
    col = sweep(w, h, (0.03, 0.045, 0.07), (0.045, 0.06, 0.085), spot=0.3, vig=1.0)
    u, t = _ut(w, h)
    c = -0.35 + t * 0.55
    wdt = 0.06 + t * 0.16
    shaft = np.exp(-((u - c) / wdt) ** 2) * (0.35 + 0.65 * (1 - t))
    haze = 0.7 + 0.6 * _noise(w, h, 6, 3)
    return col + (shaft * haze * 0.5)[..., None] * np.array([0.75, 0.88, 1.0])


def sunset_gradient(w, h):
    """A studio gradient backdrop: violet at the top fading to warm orange at the floor."""
    col = sweep(w, h, (0.5, 0.5, 0.5), (0.5, 0.5, 0.5), spot=0.25, top_dark=0.0, vig=0.7)
    _u, t = _ut(w, h)
    k = _smooth(t / 0.9)[..., None]
    return col * (np.array([0.42, 0.2, 0.62]) * (1 - k) + np.array([1.5, 0.75, 0.32]) * k)


def concrete(w, h):
    """A bare concrete wall and floor: grey, mottled, a few darker stains."""
    col = sweep(w, h, (0.36, 0.36, 0.35), (0.3, 0.3, 0.29), spot=0.2, vig=0.8, paper=0.0)
    fine = _noise(w, h, 140, 2)
    mid = _noise(w, h, 20, 3)
    stain = _smooth((_noise(w, h, 5, 2) - 0.6) / 0.15)
    return col * (0.82 + 0.22 * fine + 0.12 * mid - 0.18 * stain)[..., None]


def infinity_white(w, h):
    """A white infinity cove: almost no horizon, a soft shadow pool on the floor."""
    col = sweep(w, h, (0.93, 0.93, 0.935), (0.97, 0.97, 0.975), spot=0.05, top_dark=0.08, vig=0.25)
    u, t = _ut(w, h)
    shade = np.exp(-((u / 0.35) ** 2 + ((t - 0.86) / 0.07) ** 2)) * 0.1
    return col * (1 - shade)[..., None]


def kraft(w, h):
    """Brown kraft paper: warm, fibrous, lit softly from the top."""
    col = sweep(w, h, (0.5, 0.37, 0.23), (0.55, 0.41, 0.26), spot=0.2, vig=0.8, paper=0.0)
    fib = _noise(w, h, 260, 2)
    blot = _noise(w, h, 9, 3)
    return col * (0.86 + 0.16 * fib + 0.1 * blot)[..., None]


def canvas(w, h, c1=(0.22, 0.25, 0.27), c2=(0.33, 0.3, 0.26)):
    """A hand-painted portrait backdrop: mottled (blue-grey and brown), lighter behind the subject."""
    lo = _noise(w, h, 3, 4)[..., None]
    mid = _noise(w, h, 9, 3)[..., None]
    c1, c2 = np.array(c1), np.array(c2)
    col = c1 * (1 - lo) + c2 * lo
    col = col * (0.82 + 0.36 * mid)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u, t = (xx - w / 2) / h, yy / (h - 1)
    col = col * (1.0 + 0.55 * np.exp(-((u / 0.42) ** 2 + ((t - 0.45) / 0.34) ** 2)))[..., None]
    r2 = (u / max(0.5, w / h * 0.5)) ** 2 + ((t - 0.5) / 0.5) ** 2
    return col * (1.0 - 0.38 * _smooth(r2 / 1.5))[..., None]


def write(path, rgb):
    import bpy
    h, w = rgb.shape[:2]
    a = np.clip(rgb, 0.0, 1.0)
    a = a + (RNG.random(a.shape).astype(np.float32) - 0.5) / 255.0                    # (no banding)
    px = np.concatenate([np.clip(a, 0, 1)[::-1], np.ones((h, w, 1), np.float32)], axis=2)  # (Blender: bottom row first)
    img = bpy.data.images.new('bg', w, h, alpha=False)
    try:
        img.pixels.foreach_set(px.astype(np.float32).ravel())
        img.filepath_raw = path
        img.file_format = 'JPEG'
        try:
            img.save(quality=88)
        except TypeError:
            img.save()
    finally:
        bpy.data.images.remove(img)


def main():
    """Every look not made yet (``--force``: all of them again; names after ``--``: only those)."""
    os.makedirs(OUT, exist_ok=True)
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    force = '--force' in sys.argv
    for key, _name, fn in LOOKS:
        if args and key not in args:
            continue
        for tag, (w, h) in (('land', (1920, 1080)), ('port', (1080, 1920))):
            p = os.path.join(OUT, f'{key}_{tag}.jpg')
            if os.path.isfile(p) and not force and not args:
                continue
            write(p, fn(w, h))
            print(p, os.path.getsize(p))


if __name__ == '__main__':
    sys.exit(main())
