"""Put a photo texture pack into the Mech Shader's maps (mecha_lab/mech_maps/<slot>/<ID>.*).

    python3 tools_dev/import_photo_maps.py <folder of the pack>        (numpy + Pillow)

The pack (user's "Photoreal_Textures_90_Lite": <slot>/<slot>_<id>.jpg|png, 896 px, nine slots x ten) is made to work
with the shader:

* Base maps are colour multipliers around a 0.5 grey (the shader does colour x map x 2): each is scaled to a 0.5
  mean brightness, its hue kept.  Each gets a height map (``<ID>_height.png``) from its brightness' fine detail
  (high-pass), gentler for maps whose brightness is colour, not relief (camo, heat tint).
* Roughness maps vary the roughness around the slider: each is shifted to a 0.5 mean, its contrast kept.
* Scratch maps: the lines stretched to full brightness on black (the shader cuts the lines at 1 - amount).
* Rust maps are the rust's colour (sRGB, as they are) and get a coverage mask (``<ID>_mask.png``) from how
  rust-coloured each spot is (saturation), smoothed.
* Every map must tile (box projection repeats it): a map whose edges do not meet is made to - a regular pattern
  (weave, carbon, grids) cut to a whole number of its own repeats and joined with itself shifted by whole repeats (in
  step - the weave does not double), anything else - its baked-in light flattened first - blended with itself shifted
  by half (the seam lands in the middle, under the original).
* Kept from the made maps (``make_mech_maps.py``): Chips "Edges Only" (the pack's is a frame round the tile - tiled,
  a grid of chips), the Emission pattern maps the shader never shows (Whole / Edges: those come from the mesh) and
  the Hex Grid (the pack's hexagons drift - no clean repeat to tile).

The same name with the other extension is removed, so ``map_path`` finds the new file."""
import glob
import os
import sys

import numpy as np
from PIL import Image

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'addon', 'mecha_lab', 'mech_maps')
KEEP = {('chip', 'EDGE'), ('emit', 'EDGES'), ('emit', 'FULL'), ('emit', 'HEX')}
REGULAR = {'weave', 'emit'}
REGULAR_IDS = {('base', 'CARBON')}
HEIGHT_GAIN = {'CAMO': 0.15, 'HEAT': 0.15, 'FLAT': 0.2, 'MOTTLED': 0.4, 'PATINA': 0.7, 'BRUSHED': 0.6, 'CAST': 0.8,
               'FORGED': 0.8}
SEAM_OK = 1.6


def gblur(a, sigma):
    n0, n1 = a.shape[:2]
    fy = np.fft.fftfreq(n0)[:, None]
    fx = np.fft.fftfreq(n1)[None, :]
    g = np.exp(-2.0 * (np.pi * sigma) ** 2 * (fx ** 2 + fy ** 2))
    if a.ndim == 3:
        return np.stack([np.real(np.fft.ifft2(np.fft.fft2(a[..., c]) * g)) for c in range(a.shape[2])], -1)
    return np.real(np.fft.ifft2(np.fft.fft2(a) * g))


def lum(a):
    return a if a.ndim == 2 else a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722


def seam(a):
    """How much the map jumps across its own edges, against an ordinary step inside (x, y): about 1 = tiles."""
    g = lum(a)
    sx = np.abs(g[:, 0] - g[:, -1]).mean() / max(np.abs(g[:, 1:] - g[:, :-1]).mean(), 1e-4)
    sy = np.abs(g[0] - g[-1]).mean() / max(np.abs(g[1:] - g[:-1]).mean(), 1e-4)
    return sx, sy


def roll_blend(a):
    """Seamless: the map over itself shifted by half, the shifted one at the edges (its middle - continuous across
    the wrap); the variance kept where the two mix."""
    n0, n1 = a.shape[:2]
    r = np.roll(np.roll(a, n0 // 2, 0), n1 // 2, 1)

    def ramp(n):
        t = np.linspace(0.0, 1.0, n)
        return np.clip(np.minimum(t, 1.0 - t) * 2.0 * 1.8, 0.0, 1.0)
    w = np.outer(ramp(n0), ramp(n1))
    if a.ndim == 3:
        w = w[..., None]
    m = a.mean(axis=(0, 1))
    out = (a - m) * w + (r - m) * (1.0 - w)
    out /= np.sqrt(w ** 2 + (1.0 - w) ** 2)
    return out + m


def period(g, axis):
    """The pattern's repeat along ``axis`` in pixels, to a fraction (the strongest autocorrelation peak, refined by
    the farthest peak that is a whole number of it), or None."""
    d = g - g.mean()
    f = np.fft.fft2(d)
    ac = np.real(np.fft.ifft2(f * np.conj(f)))
    line = (ac[0, :] if axis == 1 else ac[:, 0]) / max(ac[0, 0], 1e-12)
    n = len(line)
    peaks = [k for k in range(4, n // 3) if line[k] > line[k - 1] and line[k] >= line[k + 1] and line[k] > 0.15]
    if not peaks:
        return None
    p0 = max(peaks, key=lambda k: line[k])
    best = float(p0)
    for k in peaks:
        m = round(k / p0)
        if m >= 2 and abs(k - m * p0) <= 0.15 * p0 and line[k] > 0.5 * line[p0]:
            best = k / m
    return best


def flatten(a, frac=6.0):
    """The large-scale light baked into a photo taken out (a lit side would show as bands once tiled)."""
    m = a.mean(axis=(0, 1))
    return a - gblur(a, a.shape[0] / frac) + m


def regular_tile(a):
    """A regular pattern: cut to whole repeats, then blended with itself shifted by whole repeats - the two copies in
    step, so the weave does not double where they mix."""
    g = lum(a)
    n0, n1 = a.shape[:2]
    px, py = period(g, 1), period(g, 0)
    if not px or not py:
        return None
    mx, my = int(n1 // px), int(n0 // py)
    w, h = int(round(mx * px)), int(round(my * py))
    c = a[:h, :w]
    sx, sy = int(round((mx // 2) * px)), int(round((my // 2) * py))
    r = np.roll(np.roll(c, sy, 0), sx, 1)

    def ramp(n):
        t = np.linspace(0.0, 1.0, n)
        return np.clip(np.minimum(t, 1.0 - t) * 2.0 * 1.8, 0.0, 1.0)
    wgt = np.outer(ramp(h), ramp(w))
    if c.ndim == 3:
        wgt = wgt[..., None]
    out = c * wgt + r * (1.0 - wgt)
    img = Image.fromarray(np.clip(out * 255.0, 0, 255).astype(np.uint8))
    return np.asarray(img.resize((n1, n0), Image.LANCZOS)).astype(np.float64) / 255.0


def tile(slot, ident, a):
    sx, sy = seam(a)
    if max(sx, sy) <= SEAM_OK:
        return a, 'tiles'
    if slot in REGULAR or (slot, ident) in REGULAR_IDS:
        b = regular_tile(a)
        if b is not None and max(seam(b)) <= SEAM_OK:
            return b, f'cut to its repeat, joined in step ({max(sx, sy):.1f} -> {max(seam(b)):.1f})'
    b = roll_blend(flatten(a))
    return b, f'blended ({max(sx, sy):.1f} -> {max(seam(b)):.1f})'


def norm(a, lo=2.0, hi=98.0):
    p0, p1 = np.percentile(a, lo), np.percentile(a, hi)
    return np.clip((a - p0) / max(p1 - p0, 1e-9), 0.0, 1.0)


def write(slot, ident, a, ext, quality=90):
    os.makedirs(os.path.join(OUT, slot), exist_ok=True)
    for old in ('.png', '.jpg'):
        p = os.path.join(OUT, slot, ident + old)
        if old != ext and os.path.isfile(p):
            os.remove(p)
    img = Image.fromarray(np.clip(np.round(a * 255.0), 0, 255).astype(np.uint8))
    p = os.path.join(OUT, slot, ident + ext)
    if ext == '.jpg':
        img.save(p, quality=quality, optimize=True)
    else:
        img.save(p, optimize=True)
    return p


def destripe(a, width=40.0):
    """Brushed metal: the photo's slow light / dark bands across the brush lines taken out (tiled, they become
    stripes); the brush lines themselves stay."""
    col = a.mean(axis=0, keepdims=True)
    n = a.shape[1]
    f = np.fft.fftfreq(n)
    g = np.exp(-2.0 * (np.pi * width) ** 2 * f ** 2)
    slow = np.real(np.fft.ifft(np.fft.fft(col, axis=1) * (g if a.ndim == 2 else g[:, None]), axis=1))
    return a - slow + a.mean(axis=(0, 1))


def main(src):
    files = sorted(glob.glob(os.path.join(src, '*', '*.*')))
    done = 0
    for f in files:
        slot = os.path.basename(os.path.dirname(f))
        stem = os.path.splitext(os.path.basename(f))[0]
        if not stem.startswith(slot + '_'):
            continue
        ident = stem[len(slot) + 1:].upper()
        if (slot, ident) in KEEP:
            print(f'{slot}/{ident}: kept the made map')
            continue
        colour = slot in ('base', 'rust')
        a = np.asarray(Image.open(f).convert('RGB' if colour else 'L')).astype(np.float64) / 255.0
        if ident == 'BRUSHED':
            a = destripe(a)
        a, how = tile(slot, ident, a)
        if slot == 'base':
            a = a * (0.5 / max(lum(a).mean(), 1e-3))
            write(slot, ident, np.clip(a, 0, 1), '.jpg')
            g = lum(a)
            hp = gblur(g - gblur(g, 24.0), 1.2)              # (the photo's grain / JPEG noise not as bumps: glitter)
            h = 0.5 + (norm(hp) - 0.5) * HEIGHT_GAIN.get(ident, 1.0)
            write(slot, ident + '_height', h, '.jpg')
        elif slot == 'rust':
            write(slot, ident, np.clip(a, 0, 1), '.jpg')
            sat = a.max(2) - a.min(2)
            write(slot, ident + '_mask', norm(gblur(sat, 2.0), 5, 95), '.jpg')
        elif slot == 'rough':
            write(slot, ident, np.clip(a - a.mean() + 0.5, 0, 1), '.jpg', quality=85)
        elif slot == 'scratch':                               # (the lines bright on black, as the shader cuts them)
            write(slot, ident, norm(a, 70.0, 99.7), '.jpg', quality=85)
        elif slot == 'emit':
            write(slot, ident, np.clip(a, 0, 1), '.png')
        else:
            write(slot, ident, np.clip(a, 0, 1), '.jpg', quality=85)
        done += 1
        print(f'{slot}/{ident}: {how}')
    print(f'{done} maps from {src} into {OUT}')


def one(slot, ident, f):
    """A single map from one image (0.24.95: the user's burlap photo for the Weave maps):
    python3 tools_dev/import_photo_maps.py --one <slot> <ID> <image>"""
    colour = slot in ('base', 'rust')
    a = np.asarray(Image.open(f).convert('RGB' if colour else 'L')).astype(np.float64) / 255.0
    a, how = tile(slot, ident, a)
    p = write(slot, ident, np.clip(a, 0, 1), '.jpg', quality=88)
    print(f'{slot}/{ident}: {how} -> {p}')


if __name__ == '__main__':
    if sys.argv[1] == '--one':
        one(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        main(sys.argv[1])
