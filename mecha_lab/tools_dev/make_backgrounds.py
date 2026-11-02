"""Make the HDRI page's built-in background pictures (0.24.95 user: "hdri 배경 컬러 말고 내가 원하는 배경 이미지를
넣을 수 있게 - 너가 기본으로 몇 장 넣어 줘, 세로 가로", "배경은 스튜디오 이미지처럼 해 줘"): 8 studio backdrops (paper
sweeps white .. black, warm, cool, a painted canvas), each landscape (1920 x 1080) and portrait (1080 x 1920),
made here from scratch (numpy; no photos) into addon/mecha_lab/backgrounds/<look>_<land|port>.jpg.
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
)


def canvas(w, h):
    """A hand-painted portrait backdrop: mottled blue-grey and brown, lighter behind the subject."""
    lo = _noise(w, h, 3, 4)[..., None]
    mid = _noise(w, h, 9, 3)[..., None]
    c1, c2 = np.array([0.22, 0.25, 0.27]), np.array([0.33, 0.3, 0.26])
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
    os.makedirs(OUT, exist_ok=True)
    for key, _name, fn in LOOKS:
        for tag, (w, h) in (('land', (1920, 1080)), ('port', (1080, 1920))):
            p = os.path.join(OUT, f'{key}_{tag}.jpg')
            write(p, fn(w, h))
            print(p, os.path.getsize(p))


if __name__ == '__main__':
    sys.exit(main())
