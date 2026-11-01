"""Make the Mech Shader texture maps (mecha_lab/mech_maps/<slot>/<id>.png): ten seamless 512 px maps per slot -
roughness, base colour, chips, scratches, rust (colour + mask), dirt, snow, emission, cloth weave.

    python3 tools_dev/make_mech_maps.py            (numpy + Pillow)

Every map tiles (spectral noise is periodic, Voronoi points and scratch lines wrap round the edges), so the shader can
repeat it over a part with box projection - no UVs needed.  The same seed makes the same maps."""
import math
import os

import numpy as np
from PIL import Image

N = 512
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'addon', 'mecha_lab', 'mech_maps')
FX = np.fft.fftfreq(N)[None, :]
FY = np.fft.fftfreq(N)[:, None]
YY, XX = np.mgrid[0:N, 0:N].astype(np.float64)


# ---------------------------------------------------------------- building blocks (all periodic)
def norm(a, lo=1.0, hi=99.0):
    p0, p1 = np.percentile(a, lo), np.percentile(a, hi)
    return np.clip((a - p0) / max(p1 - p0, 1e-9), 0.0, 1.0)


def spectral(seed, beta=2.0, fmin=1.0, fmax=None, aniso=(1.0, 1.0), angle=0.0):
    """Noise with a 1/f^beta spectrum between fmin and fmax cycles per tile, stretched by ``aniso`` along ``angle``
    (degrees): (1, 30) = streaks along the turned x axis."""
    rng = np.random.default_rng(seed)
    w = np.fft.fft2(rng.standard_normal((N, N)))
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    u = (FX * ca + FY * sa) * N * aniso[0]
    v = (-FX * sa + FY * ca) * N * aniso[1]
    f = np.sqrt(u * u + v * v)
    fr = np.sqrt((FX * N) ** 2 + (FY * N) ** 2)
    filt = np.where(f > 0, 1.0 / np.maximum(f, 1e-9) ** (beta / 2.0), 0.0)
    filt *= fr >= fmin
    if fmax is not None:
        filt *= np.exp(-(fr / fmax) ** 2)
    return norm(np.real(np.fft.ifft2(w * filt)))


def blur(a, sigma):
    g = np.exp(-2.0 * (math.pi * sigma) ** 2 * (FX ** 2 + FY ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * g))


def sample(a, x, y):
    """Bilinear sample of ``a`` at pixel coordinates (wrapping)."""
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    x0 %= N
    y0 %= N
    x1, y1 = (x0 + 1) % N, (y0 + 1) % N
    return (a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x1] * fx * (1 - fy) + a[y1, x0] * (1 - fx) * fy
            + a[y1, x1] * fx * fy)


def warp(a, amount, seed, beta=2.5, fmax=12):
    dx = (spectral(seed, beta, fmax=fmax) - 0.5) * amount
    dy = (spectral(seed + 1, beta, fmax=fmax) - 0.5) * amount
    return sample(a, XX + dx, YY + dy)


def worley(count, seed, jitter=1.0, grid=False):
    """(F1, F2) distance maps in pixels to ``count`` points (a jittered grid when ``grid``), wrapping."""
    rng = np.random.default_rng(seed)
    if grid:
        k = int(round(math.sqrt(count)))
        gx, gy = np.meshgrid(np.arange(k), np.arange(k))
        pts = (np.stack([gx.ravel(), gy.ravel()], 1) + 0.5 + (rng.random((k * k, 2)) - 0.5) * jitter) * (N / k)
    else:
        pts = rng.random((count, 2)) * N
    f1 = np.full((N, N), 1e9)
    f2 = np.full((N, N), 1e9)
    for px, py in pts:
        dx = np.abs(XX - px)
        dy = np.abs(YY - py)
        dx = np.minimum(dx, N - dx)
        dy = np.minimum(dy, N - dy)
        d = np.sqrt(dx * dx + dy * dy)
        f2 = np.where(d < f1, f1, np.minimum(f2, d))
        f1 = np.minimum(f1, d)
    return f1, f2


def lines(segs, img=None):
    """Anti-aliased line segments (x0, y0, x1, y1, width px, value) drawn with max(), wrapping round the tile."""
    img = np.zeros((N, N)) if img is None else img
    for x0, y0, x1, y1, w, val in segs:
        pad = w + 2
        lx, hx = int(math.floor(min(x0, x1) - pad)), int(math.ceil(max(x0, x1) + pad))
        ly, hy = int(math.floor(min(y0, y1) - pad)), int(math.ceil(max(y0, y1) + pad))
        gy, gx = np.mgrid[ly:hy + 1, lx:hx + 1].astype(np.float64)
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy or 1e-9
        t = np.clip(((gx - x0) * dx + (gy - y0) * dy) / L2, 0.0, 1.0)
        # tapered ends: thinner towards both ends
        taper = np.sqrt(np.clip(1.0 - (2.0 * t - 1.0) ** 2, 0.05, 1.0))
        d = np.hypot(gx - (x0 + t * dx), gy - (y0 + t * dy))
        cov = np.clip(w * 0.5 * taper + 0.5 - d, 0.0, 1.0) * val
        iy, ix = gy.astype(int) % N, gx.astype(int) % N
        np.maximum.at(img, (iy, ix), cov)
    return img


def scratch_set(seed, count, length, width, angle, spread, value=(0.6, 1.0), curve=0.0):
    rng = np.random.default_rng(seed)
    segs = []
    for _ in range(count):
        x, y = rng.random(2) * N
        a = math.radians(angle + rng.normal(0, spread))
        L = length * rng.uniform(0.4, 1.3)
        w = width * rng.uniform(0.6, 1.4)
        val = rng.uniform(*value)
        steps = 6 if curve else 1
        for k in range(steps):
            a2 = a + curve * (k - steps / 2) / steps
            dx, dy = math.cos(a2) * L / steps, math.sin(a2) * L / steps
            segs.append((x, y, x + dx, y + dy, w, val))
            x, y = x + dx, y + dy
    return lines(segs)


JPG_SLOTS = {'rough', 'chip', 'dirt', 'snow', 'rust'}      # (noisy grey maps: JPG is half the size of PNG)


def save_gray(slot, ident, a):
    os.makedirs(os.path.join(OUT, slot), exist_ok=True)
    im = Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), 'L')
    for ext in ('.png', '.jpg'):                              # (one file per map)
        old = os.path.join(OUT, slot, ident + ext)
        if os.path.exists(old):
            os.remove(old)
    if slot in JPG_SLOTS:
        im.save(os.path.join(OUT, slot, ident + '.jpg'), quality=90)
    else:
        im.save(os.path.join(OUT, slot, ident + '.png'), optimize=True)


def save_rgb(slot, ident, rgb):
    os.makedirs(os.path.join(OUT, slot), exist_ok=True)
    Image.fromarray((np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGB').save(
        os.path.join(OUT, slot, ident + '.jpg'), quality=92)


def tint(gray, lo, hi):
    lo, hi = np.array(lo), np.array(hi)
    return lo[None, None, :] * (1 - gray[..., None]) + hi[None, None, :] * gray[..., None]


def soft(a, lo, hi):
    return np.clip((a - lo) / max(hi - lo, 1e-9), 0, 1)


# ---------------------------------------------------------------- the maps
def roughness():
    s = 'rough'
    save_gray(s, 'CLEAN', 0.5 + (spectral(1, 2.5, fmax=4) - 0.5) * 0.08)
    save_gray(s, 'FINE', 0.5 + (spectral(2, 0.5, fmin=40) - 0.5) * 0.5)
    sm = warp(spectral(3, 2.8, fmax=10), 40, 30)
    save_gray(s, 'SMUDGE', 0.5 + (norm(sm) - 0.5) * 0.7)
    # fingerprints: ring whorls in soft blobs over a smudge
    rng = np.random.default_rng(4)
    fp = np.zeros((N, N))
    for _ in range(9):
        cx, cy = rng.random(2) * N
        r0 = rng.uniform(25, 45)
        dx = (XX - cx + N / 2) % N - N / 2
        dy = (YY - cy + N / 2) % N - N / 2
        ang = rng.uniform(0, math.pi)
        u = dx * math.cos(ang) + dy * math.sin(ang)
        v = (-dx * math.sin(ang) + dy * math.cos(ang)) * 1.35
        r = np.sqrt(u * u + v * v)
        fp = np.maximum(fp, (0.5 + 0.5 * np.sin(r * 1.1)) * np.exp(-(r / r0) ** 4))
    save_gray(s, 'FINGER', 0.45 + (norm(sm) - 0.5) * 0.3 + fp * 0.35)
    save_gray(s, 'BRUSHED', 0.5 + (spectral(5, 1.2, fmin=3, aniso=(1.0, 40.0)) - 0.5) * 0.8)
    save_gray(s, 'PATCHY', 0.3 + soft(warp(spectral(6, 3.0, fmax=6), 30, 60), 0.35, 0.65) * 0.4)
    g = norm(spectral(7, 1.6) * 0.6 + warp(spectral(8, 2.2), 25, 80) * 0.4)
    save_gray(s, 'GRUNGE', 0.25 + soft(g, 0.2, 0.85) * 0.55)
    f1, _f2 = worley(70, 9)
    rad = np.random.default_rng(9).uniform(6, 16)
    spots = np.clip(1 - f1 / rad, 0, 1)
    ring = np.exp(-((f1 - rad * 0.8) / 1.6) ** 2)
    save_gray(s, 'WATER', 0.45 + (spectral(10, 2.0) - 0.5) * 0.15 - spots * 0.12 + ring * 0.3)
    st = spectral(11, 1.0, fmin=2, aniso=(1.0, 30.0)) * (0.6 + 0.4 * spectral(12, 2.5, fmax=4))
    save_gray(s, 'STREAKS', 0.35 + soft(st, 0.3, 0.9) * 0.4)
    save_gray(s, 'WORN', 0.5 + (spectral(13, 1.2, fmin=3, aniso=(1.0, 25.0), angle=20) - 0.5) * 0.4
              + (norm(warp(spectral(14, 3.0, fmax=6), 30, 140)) - 0.5) * 0.4)


def base():
    s = 'base'
    save_rgb(s, 'FLAT', tint(spectral(20, 2.5, fmax=5), (0.48, 0.48, 0.48), (0.52, 0.52, 0.52)))
    save_gray(s, 'FLAT_height', 0.5 + (spectral(200, 1.0, fmin=20) - 0.5) * 0.15)   # (a fine surface grain)
    m = warp(spectral(21, 2.6, fmax=10), 40, 22)
    save_rgb(s, 'MOTTLED', tint(m, (0.42, 0.42, 0.43), (0.58, 0.58, 0.57)))
    save_gray(s, 'MOTTLED_height', 0.5 + (m - 0.5) * 0.25 + (spectral(201, 1.0, fmin=20) - 0.5) * 0.2)
    b = spectral(22, 1.1, fmin=3, aniso=(1.0, 45.0))
    save_rgb(s, 'BRUSHED', tint(b, (0.4, 0.4, 0.41), (0.6, 0.6, 0.6)))
    save_gray(s, 'BRUSHED_height', spectral(202, 0.8, fmin=6, aniso=(1.0, 45.0)))   # (the brush grooves)
    f1, _ = worley(900, 23)
    pits = np.exp(-(f1 / np.random.default_rng(23).uniform(1.0, 2.5)) ** 2)
    grain = spectral(24, 0.8, fmin=30)
    save_rgb(s, 'CAST', tint(np.clip(0.55 + (grain - 0.5) * 0.35 - pits * 0.45, 0, 1), (0.3, 0.3, 0.3),
                             (0.62, 0.62, 0.62)))
    save_gray(s, 'CAST_height', np.clip(0.6 + (grain - 0.5) * 0.5 - pits * 0.6, 0, 1))   # (sand-cast grain, pits)
    f1, f2 = worley(60, 25)
    dents = norm(f1 / (f1 + f2 + 1e-9))
    save_rgb(s, 'FORGED', tint(dents * 0.7 + spectral(26, 2.0) * 0.3, (0.4, 0.4, 0.41), (0.6, 0.6, 0.6)))
    save_gray(s, 'FORGED_height', 1.0 - norm(f1 / (f1 + f2 + 1e-9)) ** 0.7)   # (hammer dents: deep in the middle)
    h = warp(spectral(27, 2.8, fmax=8), 60, 28)
    heat = np.stack([0.5 + 0.07 * np.sin(h * 5.0), 0.49 + 0.04 * np.sin(h * 5.0 + 2.0),
                     0.5 + 0.09 * np.sin(h * 5.0 + 4.0)], -1)
    save_rgb(s, 'HEAT', heat)
    save_gray(s, 'HEAT_height', 0.5 + (spectral(203, 1.0, fmin=20) - 0.5) * 0.2)
    p = soft(warp(spectral(29, 2.5, fmax=10), 40, 30), 0.45, 0.75)
    pat = tint(spectral(31, 1.5), (0.46, 0.47, 0.47), (0.54, 0.54, 0.53)) * (1 - p[..., None]) + \
        tint(spectral(32, 2.0), (0.32, 0.52, 0.46), (0.42, 0.62, 0.55)) * p[..., None]
    save_rgb(s, 'PATINA', pat)
    save_gray(s, 'PATINA_height', 0.4 + p * 0.35 + (spectral(204, 1.2, fmin=10) - 0.5) * 0.3)   # (crusty patina)
    op = blur(spectral(33, 0.5, fmin=40), 1.2)
    save_rgb(s, 'PEEL', tint(norm(op), (0.46, 0.46, 0.46), (0.54, 0.54, 0.54)))
    save_gray(s, 'PEEL_height', norm(blur(spectral(205, 0.6, fmin=25), 2.0)))   # (orange peel: soft dimples)
    # carbon fibre: 2x2 twill of tows, 16 per tile
    t = 16
    u = (XX / N * t) % 1.0
    v = (YY / N * t) % 1.0
    cx, cy = np.floor(XX / N * t), np.floor(YY / N * t)
    over = ((cx + cy) // 2) % 2
    tow = np.where(over == 0, np.sin(math.pi * v) ** 0.5, np.sin(math.pi * u) ** 0.5)
    save_rgb(s, 'CARBON', tint(tow * 0.85 + spectral(34, 0.6, fmin=60) * 0.15, (0.12, 0.12, 0.13),
                              (0.5, 0.5, 0.52)))
    save_gray(s, 'CARBON_height', tow)                                     # (the tows' rounded backs)
    c1 = soft(warp(spectral(35, 3.0, fmax=6), 50, 36), 0.45, 0.5)
    c2 = soft(warp(spectral(37, 3.0, fmax=8), 50, 38), 0.55, 0.6)
    camo = 0.62 - c1 * 0.18 - c2 * 0.16
    save_rgb(s, 'CAMO', tint(camo, (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)))
    save_gray(s, 'CAMO_height', 0.5 + (c1 + c2) * 0.08 + (spectral(206, 0.8, fmin=25) - 0.5) * 0.2)   # (paint edges)


def chips():
    s = 'chip'
    save_gray(s, 'SOFT', spectral(40, 2.4, fmax=16))
    save_gray(s, 'FLAKES', soft(warp(spectral(41, 1.8), 18, 42, fmax=40), 0.3, 0.75))
    save_gray(s, 'BIG', soft(warp(spectral(43, 2.6, fmax=10), 45, 44, fmax=30), 0.25, 0.8))
    f1, _ = worley(500, 45)
    save_gray(s, 'DOTS', np.clip(1 - f1 / 4.0, 0, 1) * 0.8 + spectral(46, 1.5) * 0.25)
    f1, f2 = worley(40, 47)
    cr = np.exp(-(warp(f2 - f1, 6, 48) / 2.0) ** 2)
    save_gray(s, 'CRACKED', np.clip(cr * 0.9 + spectral(49, 2.0) * 0.3, 0, 1))
    save_gray(s, 'PEEL', soft(warp(spectral(50, 3.0, fmax=6), 70, 51, fmax=40), 0.3, 0.75))
    save_gray(s, 'SCUFF', np.clip(scratch_set(52, 260, 22, 5.0, 15, 25, (0.5, 1.0)) * 0.8
                                  + spectral(53, 2.0) * 0.3, 0, 1))
    save_gray(s, 'GRAIN', spectral(54, 0.7, fmin=40))
    f1, _ = worley(70, 55)
    save_gray(s, 'BLOTCH', np.clip(1 - warp(f1, 10, 56) / 40.0, 0, 1))
    save_gray(s, 'EDGE', np.full((N, N), 0.5))


def scratches():
    s = 'scratch'
    save_gray(s, 'FINE', scratch_set(60, 200, 70, 2.6, 10, 20))
    save_gray(s, 'LONG', scratch_set(61, 60, 260, 2.8, 5, 8))
    save_gray(s, 'CROSS', np.maximum(scratch_set(62, 90, 120, 2.6, 35, 6), scratch_set(63, 90, 120, 2.6, -35, 6)))
    save_gray(s, 'RANDOM', scratch_set(64, 170, 110, 2.8, 0, 180))
    save_gray(s, 'DEEP', scratch_set(65, 20, 200, 8.0, 20, 30, (0.8, 1.0)))
    save_gray(s, 'SWIRL', scratch_set(66, 110, 90, 2.4, 0, 180, curve=2.2))
    save_gray(s, 'SCUFFED', scratch_set(67, 600, 18, 3.0, 0, 180, (0.3, 0.9)))
    save_gray(s, 'VERTICAL', scratch_set(68, 120, 180, 2.6, 90, 6))
    rng = np.random.default_rng(69)
    segs = []
    for _ in range(14):                                       # claws: 3-4 parallel strokes
        x, y = rng.random(2) * N
        a = rng.uniform(0, math.pi)
        L = rng.uniform(80, 160)
        n = rng.integers(3, 5)
        for k in range(n):
            ox, oy = -math.sin(a) * k * 9, math.cos(a) * k * 9
            segs.append((x + ox, y + oy, x + ox + math.cos(a) * L, y + oy + math.sin(a) * L, 5.0, 1.0))
    save_gray(s, 'CLAW', lines(segs))
    save_gray(s, 'MICRO', scratch_set(70, 1200, 30, 1.6, 0, 180, (0.3, 0.8)))


RUST_TONES = {   # (dark, mid, bright) rust colours per preset
    'fresh': ((0.25, 0.08, 0.02), (0.55, 0.22, 0.05), (0.78, 0.45, 0.12)),
    'brown': ((0.14, 0.06, 0.03), (0.32, 0.14, 0.06), (0.5, 0.26, 0.1)),
    'dark': ((0.08, 0.04, 0.03), (0.2, 0.09, 0.05), (0.38, 0.17, 0.08)),
}


def rust():
    s = 'rust'

    def colour(seed, tone, flaky=0.5):
        dark, mid, bright = (np.array(c) for c in RUST_TONES[tone])
        a = spectral(seed, 1.6)
        b = warp(spectral(seed + 1, 2.4, fmax=20), 25, seed + 2)
        f1, f2 = worley(220, seed + 3)
        flakes = soft(f2 - f1, 0.0, 6.0)
        t = np.clip(a * 0.5 + b * 0.5, 0, 1)
        rgb = np.where((t < 0.5)[..., None], dark + (mid - dark) * (t / 0.5)[..., None],
                       mid + (bright - mid) * ((t - 0.5) / 0.5)[..., None])
        return rgb * (1 - flaky * 0.35 * (1 - flakes))[..., None]
    specs = [
        ('SPOTS', 'fresh', lambda: soft(warp(spectral(80, 2.0, fmax=30), 20, 81), 0.55, 0.8)),
        ('PATCHES', 'brown', lambda: soft(warp(spectral(82, 2.8, fmax=10), 40, 83), 0.4, 0.7)),
        ('STREAKS', 'brown', lambda: soft(spectral(84, 1.2, fmin=2, aniso=(1.0, 30.0))
                                          * (0.5 + 0.5 * spectral(85, 2.5, fmax=4)), 0.35, 0.75)),
        ('PITTED', 'dark', lambda: np.clip(1 - worley(600, 86)[0] / 5.0, 0, 1) * 0.7 + spectral(87, 2.0) * 0.3),
        ('FLAKY', 'fresh', lambda: soft(warp(spectral(88, 1.6), 20, 89, fmax=40), 0.35, 0.65)),
        ('HEAVY', 'dark', lambda: soft(warp(spectral(90, 2.5, fmax=12), 50, 91), 0.2, 0.55)),
        ('EDGES', 'brown', lambda: spectral(92, 1.8) * 0.6 + 0.2),
        ('BLOOM', 'fresh', lambda: np.clip(1 - warp(worley(55, 93)[0], 12, 94) / 30.0, 0, 1)),
        ('FINE', 'brown', lambda: soft(spectral(95, 0.6, fmin=40), 0.4, 0.8)),
        ('WATERLINE', 'dark', lambda: soft(spectral(96, 1.5, fmin=2, aniso=(1.0, 25.0)) * 0.6
                                           + (1 - YY / N) * 0.0 + spectral(97, 2.5, fmax=4) * 0.4, 0.4, 0.75)),
    ]
    for i, (ident, tone, mask) in enumerate(specs):
        save_rgb(s, ident, colour(100 + 7 * i, tone))
        save_gray(s, ident + '_mask', mask())


def dirt():
    s = 'dirt'
    save_gray(s, 'DUST', soft(spectral(120, 0.9, fmin=10) * 0.6 + spectral(121, 2.5, fmax=6) * 0.4, 0.3, 0.8))
    save_gray(s, 'MUD', soft(warp(spectral(122, 2.6, fmax=12), 50, 123, fmax=30), 0.35, 0.65))
    f1, _ = worley(140, 124)
    spl = np.clip(1 - warp(f1, 14, 125, fmax=50) / 14.0, 0, 1)
    save_gray(s, 'SPLASH', np.clip(spl + soft(spectral(126, 1.0, fmin=30), 0.7, 0.9) * 0.6, 0, 1))
    save_gray(s, 'GRIME', soft(spectral(127, 1.5) * 0.5 + warp(spectral(128, 2.2), 30, 129) * 0.5, 0.25, 0.8))
    drips = spectral(130, 1.0, fmin=3, aniso=(1.0, 40.0)) * soft(spectral(131, 2.5, fmax=5), 0.3, 0.8)
    save_gray(s, 'STREAKS', soft(drips, 0.2, 0.7))
    save_gray(s, 'SOOT', soft(warp(spectral(132, 3.0, fmax=5), 60, 133), 0.2, 0.85))
    f1, _ = worley(25, 134)
    oil = np.clip(1 - warp(f1, 30, 135) / 55.0, 0, 1)
    save_gray(s, 'OIL', oil * (0.8 + 0.2 * np.sin(f1 * 0.3)))
    save_gray(s, 'SAND', soft(spectral(136, 0.3, fmin=80), 0.45, 0.85))
    save_gray(s, 'CAKED', soft(warp(spectral(137, 2.0, fmax=30), 30, 138, fmax=40), 0.42, 0.55))
    save_gray(s, 'SMEAR', soft(warp(spectral(139, 1.5, fmin=2, aniso=(1.0, 12.0), angle=-25), 20, 140), 0.35, 0.7))


def snow():
    s = 'snow'
    save_gray(s, 'POWDER', soft(spectral(150, 1.2) * 0.6 + spectral(151, 2.5, fmax=6) * 0.4, 0.25, 0.7))
    save_gray(s, 'PATCHY', soft(warp(spectral(152, 2.8, fmax=8), 40, 153), 0.4, 0.55))
    f1, f2 = worley(300, 154)
    save_gray(s, 'FROST', np.clip(soft(f2 - f1, 0.0, 3.0) * 0.5 + spectral(155, 0.8, fmin=30) * 0.5, 0, 1))
    save_gray(s, 'DRIFT', soft(warp(spectral(156, 2.4, fmin=1, aniso=(1.0, 4.0)), 30, 157), 0.35, 0.6))
    save_gray(s, 'CRUST', soft(warp(spectral(158, 1.8), 15, 159, fmax=40), 0.4, 0.6))
    save_gray(s, 'SLUSH', soft(spectral(160, 2.0) * 0.7 + np.clip(1 - worley(90, 161)[0] / 20.0, 0, 1) * 0.3,
                               0.35, 0.7))
    f1, _ = worley(400, 162)
    save_gray(s, 'FLAKES', np.clip(1 - f1 / 3.5, 0, 1) * 0.6 + spectral(163, 2.0) * 0.4)
    save_gray(s, 'HEAVY', soft(spectral(164, 2.6, fmax=6), 0.15, 0.45))
    f1, f2 = worley(30, 165)
    save_gray(s, 'ICE', np.clip(0.7 - np.exp(-((f2 - f1) / 2.5) ** 2) * 0.5 + spectral(166, 2.0) * 0.3, 0, 1))
    save_gray(s, 'WIND', soft(spectral(167, 1.6, fmin=2, aniso=(1.0, 14.0), angle=10), 0.4, 0.65))


def emission():
    s = 'emit'
    for flag in ('FULL', 'EDGES', 'CREVICES', 'SCRATCH'):      # (the mask comes from the shader: a white map)
        save_gray(s, flag, np.ones((N, N)))
    save_gray(s, 'STRIPES', soft(np.sin(XX / N * 2 * math.pi * 8) * 0.5 + 0.5, 0.75, 0.9))
    gx = np.minimum(XX % 64, 64 - XX % 64)
    gy = np.minimum(YY % 64, 64 - YY % 64)
    save_gray(s, 'GRID', np.clip(1.5 - np.minimum(gx, gy), 0, 1))
    rng = np.random.default_rng(170)                          # circuit: right-angle traces with pads
    segs = []
    for _ in range(60):
        x, y = (rng.integers(0, 32, 2) * 16).astype(float)
        for _k in range(rng.integers(2, 5)):
            L = rng.integers(2, 8) * 16
            if rng.random() < 0.5:
                segs.append((x, y, x + L * rng.choice((-1, 1)), y, 2.5, 1.0))
                x = segs[-1][2]
            else:
                segs.append((x, y, x, y + L * rng.choice((-1, 1)), 2.5, 1.0))
                y = segs[-1][3]
    circ = lines(segs)
    pads = np.zeros((N, N))
    for x0, y0, x1, y1, _w, _v in segs[::3]:
        dx = np.minimum(np.abs(XX - x1), N - np.abs(XX - x1))
        dy = np.minimum(np.abs(YY - y1), N - np.abs(YY - y1))
        pads = np.maximum(pads, np.clip(5.5 - np.hypot(dx, dy), 0, 1))
    save_gray(s, 'CIRCUIT', np.maximum(circ, pads))
    dx = (XX % 32) - 16
    dy = (YY % 32) - 16
    save_gray(s, 'DOTS', np.clip(6.5 - np.hypot(dx, dy), 0, 1))
    # hex grid lines: 8 hexes across the tile, edge distance from the nearest centre (tiles: rows of even count)
    a = N / 8.0
    hh = a * math.sqrt(3) / 2
    rows_n = int(round(N / hh))
    best = np.full((N, N), 1e9)
    second = np.full((N, N), 1e9)
    for j in range(-1, rows_n + 1):
        for i in range(-1, 9):
            cx = (i + 0.5 * (j % 2)) * a
            cy = j * (N / rows_n)
            dx = np.minimum(np.abs(XX - cx), N - np.abs(XX - cx))
            dy = np.minimum(np.abs(YY - cy), N - np.abs(YY - cy))
            d = np.hypot(dx, dy)
            second = np.where(d < best, best, np.minimum(second, d))
            best = np.minimum(best, d)
    save_gray(s, 'HEX', np.clip(2.0 - (second - best), 0, 1))
    f1, f2 = worley(30, 171)
    save_gray(s, 'CRACKS', np.exp(-(warp(f2 - f1, 8, 172) / 1.6) ** 2))


def weave():
    s = 'weave'

    def plain(threads, seed, fuzz=0.1, rib=(1, 1)):
        u = (XX / N * threads) % 1.0
        v = (YY / N * threads) % 1.0
        cx, cy = np.floor(XX / N * threads), np.floor(YY / N * threads)
        over = (cx // rib[0] + cy // rib[1]) % 2
        warp_t = np.sin(math.pi * u) ** 0.6
        weft_t = np.sin(math.pi * v) ** 0.6
        h = np.where(over == 0, 0.55 + 0.45 * warp_t * np.sin(math.pi * v) ** 0.3,
                     0.55 + 0.45 * weft_t * np.sin(math.pi * u) ** 0.3)
        h = h * np.minimum(warp_t + 0.3, 1) * np.minimum(weft_t + 0.3, 1)
        return np.clip(h + (spectral(seed, 0.6, fmin=40) - 0.5) * fuzz, 0, 1)
    save_gray(s, 'CANVAS', plain(24, 180, 0.15))
    t = 40                                                       # twill: the over-thread steps one per row
    cx, cy = np.floor(XX / N * t), np.floor(YY / N * t)
    u = (XX / N * t) % 1.0
    v = (YY / N * t) % 1.0
    over = ((cx - cy) % 3) == 0
    tw = np.where(over, np.sin(math.pi * v) ** 0.5, np.sin(math.pi * u) ** 0.5)
    save_gray(s, 'DENIM', np.clip(tw * 0.85 + spectral(181, 0.6, fmin=50) * 0.15, 0, 1))
    save_gray(s, 'NYLON', plain(64, 182, 0.05))
    rip = plain(48, 183, 0.05)
    g = np.minimum(XX % 64, YY % 64) < 3
    save_gray(s, 'RIPSTOP', np.clip(rip * 0.8 + g * 0.35, 0, 1))
    save_gray(s, 'WOOL', np.clip(plain(16, 184, 0.2) * 0.6 + warp(spectral(185, 1.2), 6, 186) * 0.4, 0, 1))
    save_gray(s, 'FELT', blur(spectral(187, 0.4, fmin=20), 0.8) * 0.5 + spectral(188, 1.5) * 0.5)
    d1 = np.abs(((XX + YY) / N * 6) % 1.0 - 0.5)
    d2 = np.abs(((XX - YY) / N * 6) % 1.0 - 0.5)
    quilt = np.sqrt(np.clip(np.minimum(d1, d2) * 2, 0, 1))
    save_gray(s, 'QUILT', np.clip(quilt * 0.9 + spectral(189, 0.6, fmin=40) * 0.1, 0, 1))
    f1, f2 = worley(700, 190)
    save_gray(s, 'LEATHER', np.clip(soft(f2 - f1, 0.0, 4.0) * 0.7 + spectral(191, 1.0) * 0.3, 0, 1))
    u = (XX / N * 32) % 1.0
    v = (YY / N * 24) % 1.0
    knit = np.sin(math.pi * np.clip(np.abs(u - 0.5) * 2 + (v - 0.5) * 0.9, 0, 1)) ** 0.8
    save_gray(s, 'KNIT', np.clip(knit * 0.85 + spectral(192, 0.6, fmin=40) * 0.15, 0, 1))
    hx = np.minimum(XX % 32, 32 - XX % 32)
    hy = np.minimum(YY % 32, 32 - YY % 32)
    save_gray(s, 'MESH', np.clip(np.minimum(hx, hy) / 4.0, 0, 1))


if __name__ == '__main__':
    for f in (roughness, base, chips, scratches, rust, dirt, snow, emission, weave):
        f()
        print('made', f.__name__, flush=True)
    total = sum(os.path.getsize(os.path.join(b, x)) for b, _d, fs in os.walk(OUT) for x in fs)
    print('maps in', OUT, f'{total / 1e6:.1f} MB')
