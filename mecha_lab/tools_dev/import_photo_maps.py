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


def _min_path(cost):
    """The cheapest path down ``cost`` (rows x columns): one column per row, moving at most one column a row."""
    n, m = cost.shape
    acc = cost.copy()
    back = np.zeros((n, m), np.int64)
    idx = np.arange(m)
    for i in range(1, n):
        prev = acc[i - 1]
        cand = np.stack([np.r_[np.inf, prev[:-1]], prev, np.r_[prev[1:], np.inf]])     # (from left, same, right)
        k = np.argmin(cand, axis=0)
        acc[i] += cand[k, idx]
        back[i] = idx + (k - 1)
    path = np.empty(n, np.int64)
    path[-1] = int(np.argmin(acc[-1]))
    for i in range(n - 1, 0, -1):
        path[i - 1] = back[i, path[i]]
    return path


def _wrap_rows(a, y, h):
    return np.take(a, np.arange(y, y + h) % a.shape[0], axis=0)


def _gmat(n, sigma):
    """A Gaussian blur along one axis of n pixels as a matrix (nothing beyond the ends: zero padding)."""
    i = np.arange(n)
    return np.exp(-0.5 * ((i[:, None] - i[None, :]) / sigma) ** 2)


def _smooth_fill(d, known, sigma):
    """``d`` known only where ``known``: smoothed and carried over the rest (normalised convolution)."""
    gy, gx = _gmat(d.shape[0], sigma), _gmat(d.shape[1], sigma)
    k = known.astype(np.float64)
    num = gy @ (d * k) @ gx.T
    den = gy @ k @ gx.T
    return num / np.maximum(den, 1e-6)


def _off_edge(cost, outer_first):
    """A cut kept off the overlap's outer side (a cut along the window's own edge is a straight line)."""
    c = cost.copy()
    m = c.shape[1]
    n = max(4, m // 5)
    pen = (c.mean() + 1e-4) * 40.0 * np.linspace(1.0, 0.0, n)
    if outer_first:
        c[:, :n] += pen[None, :]
    else:
        c[:, m - n:] += pen[::-1][None, :]
    return c


def _heal_band(a, a_hp, src, src_hp, valid, centre, half, overlap, step, used, keep_away, ease, span=None):
    """Cover the band of columns ``centre - half .. centre + half`` (a seam runs down its middle) with patches of the
    map taken from elsewhere.  Each patch: the source window (``valid``: not crossing a seam; not next to where it
    goes, not where an earlier patch came from) that best meets what is already there (``*_hp``: the map with its fine
    detail doubled) - the map either side of the band, the patch above (and below, for the last one: the band wraps) -
    found at half size, then to the pixel; its brightness eased to its surroundings (a smooth correction from the
    overlaps - None: as much as it takes; a number: from the differences smaller than that, at most that); joined along the cheapest cut through each overlap.
    ``span`` (first row, rows): only those rows, the rows just before and after them kept (they meet the patches);
    None: the whole band round (the last patch meets the first).  ``a`` / ``a_hp`` are changed in place."""
    n0, n1 = a.shape
    x0 = centre - half - overlap
    w = 2 * (half + overlap)
    cols = np.arange(x0, x0 + w) % n1
    if span is None:
        k = max(2, int(round(n0 / step)))
        ys = [int(round(i * n0 / k)) for i in range(k + 1)]          # (the last patch runs into the first)
    else:
        k = max(1, int(round((span[1] - overlap) / step)))
        ys = [span[0] + int(round(i * (span[1] - overlap) / k)) for i in range(k + 1)]
    sm = src_hp[::2, ::2]
    F1, F2 = np.fft.rfft2(sm), np.fft.rfft2(sm * sm)
    yy, xx = np.arange(0, n0, 2), np.arange(0, n1, 2)

    def wdist(v, c, n):
        d = np.abs(v - c) % n
        return np.minimum(d, n - d)
    for i, y in enumerate(ys[:-1]):
        h = ys[i + 1] - y + overlap
        rows = np.arange(y, y + h) % n0
        tgt = a[np.ix_(rows, cols)]
        tgt_hp = a_hp[np.ix_(rows, cols)]
        known = np.zeros((h, w), bool)
        known[:, :overlap] = known[:, -overlap:] = True
        top = i > 0 or span is not None
        if top:
            known[:overlap] = True
        if i == k - 1:
            known[-overlap:] = True
        # sum over the known pixels of (src - tgt)^2 for every source window (FFT, half size)
        m = known[::2, ::2].astype(np.float64)
        t = tgt_hp[::2, ::2] * m
        hm, wm = m.shape
        K1 = np.zeros(sm.shape)
        K1[:hm, :wm] = m
        K2 = np.zeros(sm.shape)
        K2[:hm, :wm] = t
        ssd = (np.fft.irfft2(F2 * np.conj(np.fft.rfft2(K1)), sm.shape)
               - 2.0 * np.fft.irfft2(F1 * np.conj(np.fft.rfft2(K2)), sm.shape))
        full_ok = valid(h, w)
        ok = valid(h + 4, w + 4)[::2, ::2]
        ok &= ~((wdist(yy, y, n0)[:, None] < keep_away) & (wdist(xx, x0, n1)[None, :] < keep_away))
        for uy, ux in used:
            ok &= ~((wdist(yy, uy, n0)[:, None] < keep_away // 2) & (wdist(xx, ux, n1)[None, :] < keep_away // 2))
        ssd = np.where(ok, ssd, np.inf)
        cand = np.argsort(ssd.ravel())[:6]
        best, pos = np.inf, None
        for c in cand:
            cy, cx = np.unravel_index(c, ssd.shape)
            for dy in (-2, -1, 0, 1, 2):
                for dx in (-2, -1, 0, 1, 2):
                    sy, sx = (cy * 2 + dy) % n0, (cx * 2 + dx) % n1
                    if not full_ok[sy, sx]:                 # (never a window across a seam)
                        continue
                    win = src_hp[np.ix_(np.arange(sy, sy + h) % n0, np.arange(sx, sx + w) % n1)]
                    e = (((win - tgt_hp) ** 2) * known).sum()
                    if e < best:
                        best, pos = e, (sy, sx)
        sy, sx = pos
        used.append((sy, sx))
        sr, sc = np.arange(sy, sy + h) % n0, np.arange(sx, sx + w) % n1
        patch, patch_hp = src[np.ix_(sr, sc)], src_hp[np.ix_(sr, sc)]
        d = tgt - patch                                                  # (its brightness eased to what is round it)
        if ease is None:
            fix = _smooth_fill(d, known, 0.18 * w)
        else:                                       # (masks: from the small differences only - black against white
            fix = np.clip(_smooth_fill(d, known & (np.abs(d) < ease), 0.18 * w), -ease, ease)   # is not a shade)
        patch = patch + fix
        # where the patch is kept: right of the left cut, left of the right cut, under the top cut (above the bottom)
        err = (patch - tgt) ** 2
        mask = np.ones((h, w))
        p = _min_path(_off_edge(err[:, :overlap], True))
        mask[np.arange(w)[None, :] <= p[:, None]] = 0.0
        p = _min_path(_off_edge(err[:, -overlap:], False))
        mask[np.arange(w)[None, :] >= (w - overlap + p)[:, None]] = 0.0
        if top:
            p = _min_path(_off_edge(err[:overlap].T, True))
            mask[np.arange(h)[:, None] <= p[None, :]] = 0.0
        if i == k - 1:
            p = _min_path(_off_edge(err[-overlap:].T, False))
            mask[np.arange(h)[:, None] >= (h - overlap + p)[None, :]] = 0.0
        mask = np.clip(_blur_small(mask, 1.5), 0.0, 1.0)
        mask[:, 0] = mask[:, -1] = 0.0                             # (the window's own edge stays as it was)
        if top:
            mask[0] = 0.0
        if i == k - 1:
            mask[-1] = 0.0
        a[np.ix_(rows, cols)] = tgt * (1.0 - mask) + patch * mask
        a_hp[np.ix_(rows, cols)] = tgt_hp * (1.0 - mask) + patch_hp * mask
    return a


def _blur_small(a, sigma):
    r = max(1, int(3 * sigma))
    x = np.arange(-r, r + 1)
    g = np.exp(-0.5 * (x / sigma) ** 2)
    g /= g.sum()
    p = np.pad(a, r, mode='edge')
    p = np.apply_along_axis(lambda v: np.convolve(v, g, 'valid'), 0, p)
    return np.apply_along_axis(lambda v: np.convolve(v, g, 'valid'), 1, p)


def periodic_part(u):
    """The map less the smooth field that makes its edges jump (Moisan's periodic + smooth decomposition): what is
    left meets itself across the edges in its slow shading; its detail is unchanged."""
    m, n = u.shape
    v = np.zeros_like(u)
    v[0, :] += u[-1, :] - u[0, :]
    v[-1, :] += u[0, :] - u[-1, :]
    v[:, 0] += u[:, -1] - u[:, 0]
    v[:, -1] += u[:, 0] - u[:, -1]
    den = (2.0 * np.cos(2.0 * np.pi * np.arange(m) / m)[:, None] + 2.0 * np.cos(2.0 * np.pi * np.arange(n) / n)[None, :]
           - 4.0)
    den[0, 0] = 1.0
    sh = np.fft.fft2(v) / den
    sh[0, 0] = 0.0
    return u - np.real(np.fft.ifft2(sh))


def heal_tile(a, crop=0, half=72, overlap=64, step=200, ease=None, periodic=False):
    """0.24.95 Seamless both ways without showing anything twice: ``crop`` px off every side (a border a generator
    has blurred / shifted to fake a seamless edge), the map shifted by half (its seams now cross in the middle, its
    own middle continuous across the wrap), then the two seam lines covered with patches of the map from elsewhere
    (``_heal_band``: down the vertical seam, then across the horizontal one).  Only a band ~2 x (half + overlap) px
    wide round each seam changes; the rest is the map as it was (moved by half).  Greyscale.  ``ease``: how much a
    patch's brightness may be shifted to meet its surroundings (None: freely - heights; a little for black / white
    masks, which a smooth shift would turn grey).  ``periodic``: first the map's own slow shading made to meet across
    its edges (``periodic_part`` - heights whose corners are lit differently)."""
    if crop:
        a = a[crop:-crop, crop:-crop]
    if periodic:
        a = periodic_part(a)
    n0, n1 = a.shape
    a = np.roll(np.roll(a, n0 // 2, 0), n1 // 2, 1)
    cy, cx = n0 // 2, n1 // 2
    src = a.copy()
    src_hp = 2.0 * src - gblur(src, 12.0)        # (matched on the map with its fine detail doubled)
    a_hp = src_hp.copy()
    used = []
    away = 2 * (half + overlap)

    def valid(h, w):
        """Source windows (top-left corners) that do not cross either seam."""
        ys = np.arange(n0)
        xs = np.arange(n1)
        cross_y = ((cy - ys) % n0 > 0) & ((cy - ys) % n0 < h)
        cross_x = ((cx - xs) % n1 > 0) & ((cx - xs) % n1 < w)
        return ~cross_y[:, None] & ~cross_x[None, :]
    a = _heal_band(a, a_hp, src, src_hp, valid, cx, half, overlap, step, used, away, ease)
    used_t = [(x, y) for y, x in used]
    aT, a_hpT = a.T.copy(), a_hp.T.copy()
    # (across the horizontal seam: not through the vertical band's middle - its patches run on across the seam
    # there - so from one side of it round to the other)
    _heal_band(aT, a_hpT, src.T.copy(), src_hp.T.copy(), lambda h, w: valid(w, h).T, cy, half, overlap, step,
               used_t, away, ease, span=(cx + half - overlap, n1 - 2 * half + 2 * overlap))
    return np.ascontiguousarray(aT.T)


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


CREATURE_OUT = os.path.join(os.path.dirname(OUT), 'creature_maps')
SOFT_MASKS = {('mottle', 'BRUISE'), ('organic', 'BLOOD_DRY')}


def creature(src, crop=160):
    """0.24.95 The Creature Shader maps (the user's "Creature_Hyperreal_28maps_2048" pack: skin / mottle / organic,
    <slot>/<slot>_<id>.jpg, greyscale).  Its tiles are not seamless - each side's outer ~150 px were shifted / blended
    and only the outermost pixel matched, so a line shows where they repeat: ``crop`` px off every side, then
    ``heal_tile`` (the seams covered with patches of the map from elsewhere; heights and soft shades first made to
    meet in their slow shading).  Skin heights stretched to the full range (1 - 99 %); masks kept as they are.
    python3 tools_dev/import_photo_maps.py --creature <pack folder> [crop px]"""
    done = 0
    for f in sorted(glob.glob(os.path.join(src, '*', '*.*'))):
        slot = os.path.basename(os.path.dirname(f))
        stem = os.path.splitext(os.path.basename(f))[0]
        if slot not in ('skin', 'mottle', 'organic') or not stem.startswith(slot + '_'):
            continue
        ident = stem[len(slot) + 1:].upper()
        a = np.asarray(Image.open(f).convert('L')).astype(np.float64) / 255.0
        before = seam(a[1:-1, 1:-1])
        soft = slot == 'skin' or (slot, ident) in SOFT_MASKS    # (heights / soft shades: eased freely)
        a = heal_tile(a, crop, ease=None if soft else 0.15, periodic=soft)
        if slot == 'skin':
            a = norm(a, 1.0, 99.0)
        d = os.path.join(CREATURE_OUT, slot)
        os.makedirs(d, exist_ok=True)
        Image.fromarray(np.clip(np.round(a * 255.0), 0, 255).astype(np.uint8)).save(
            os.path.join(d, ident + '.jpg'), quality=90, optimize=True)
        done += 1
        print(f'{slot}/{ident}: {a.shape[1]} px, seam (inside the outer pixel) {max(before):.1f} -> {max(seam(a)):.2f}')
    print(f'{done} creature maps into {CREATURE_OUT}')


if __name__ == '__main__':
    if sys.argv[1] == '--one':
        one(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == '--creature':
        creature(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 160)
    else:
        main(sys.argv[1])
