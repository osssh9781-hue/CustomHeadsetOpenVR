"""Make the add-on's own sci-fi HDRIs (0.24.95 user: "HDRI 도 만들어 줘 빨리! 배경보다도 라이팅"): lighting set-ups
for hard-surface / mech work - the light shapes (strip lights, soft boxes, neon tubes, a sun) are what matters, the
surroundings stay dark and simple.  Made from scratch (numpy; no photos) into addon/mecha_lab/hdris/<key>.exr
(2048 x 1024, half float, DWAA) and their previews into addon/mecha_lab/mech_icons/hdri_mch_<key>.png.
    python -I tools_dev/make_scifi_hdris.py        (a python with bpy: the EXRs are written by Blender)

Directions: Blender's equirectangular mapping (u = 0.5 - atan2(y, x) / 2pi, v = elevation / pi + 0.5); the model
faces -Y (front view), so a "front" light sits towards -Y and a rim light towards +Y.  Each HDRI is scaled so its
mean radiance over the sphere is about that of Blender's own studio lights (0.8), the sun one a little less."""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'addon', 'mecha_lab', 'hdris')
ICONS = os.path.join(ROOT, 'addon', 'mecha_lab', 'mech_icons')
W, H = 2048, 1024
RNG = np.random.default_rng(11)


def directions(w=W, h=H):
    v = (np.arange(h, dtype=np.float64) + 0.5) / h            # (row 0 = bottom, as Blender stores pixels)
    u = (np.arange(w, dtype=np.float64) + 0.5) / w
    el = (v - 0.5) * np.pi
    ph = (u - 0.5) * 2 * np.pi
    ce = np.cos(el)[:, None]                                  # (checked by a probe render: +X / -Y / +Z land there)
    return np.stack([ce * np.cos(ph)[None, :], -ce * np.sin(ph)[None, :], np.repeat(np.sin(el)[:, None], w, 1)], -1)


def unit(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v)


def smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def col(rgb, power=1.0):
    return np.asarray(rgb, np.float64) * power


def add(img, mask, rgb):
    img += mask[..., None] * np.asarray(rgb, np.float64)


def rect(D, center, w_deg, h_deg, up=(0, 0, 1), soft=0.15):
    """A rectangular light facing the model: ``w_deg`` x ``h_deg`` across, centred on direction ``center``."""
    c = unit(center)
    upv = np.asarray(up, np.float64)
    r = np.cross(c, upv)
    if np.linalg.norm(r) < 1e-6:
        r = np.cross(c, (0, 1, 0))
    r = unit(r)
    u = np.cross(r, c)
    dc = D @ c
    a = np.degrees(np.arctan2(D @ r, np.maximum(dc, 1e-6)))
    b = np.degrees(np.arctan2(D @ u, np.maximum(dc, 1e-6)))
    ea = 1 - smooth((np.abs(a) - w_deg / 2 * (1 - soft)) / max(w_deg / 2 * soft, 1e-3))
    eb = 1 - smooth((np.abs(b) - h_deg / 2 * (1 - soft)) / max(h_deg / 2 * soft, 1e-3))
    return ea * eb * (dc > 0)


def disc(D, center, radius_deg, soft=0.2):
    c = unit(center)
    ang = np.degrees(np.arccos(np.clip(D @ c, -1, 1)))
    return 1 - smooth((ang - radius_deg * (1 - soft)) / max(radius_deg * soft, 1e-4))


def glow(D, center, spread_deg):
    c = unit(center)
    ang = np.radians(np.degrees(np.arccos(np.clip(D @ c, -1, 1))))
    return np.exp(-(ang / np.radians(spread_deg)) ** 2)


def line(D, p0, t, width, dash=None, duty=0.6, length=None):
    """A tube light along the 3D line ``p0 + s t`` (``p0`` at right angles to ``t``; ``width`` in the same units):
    the directions that see it (it gets thinner with distance), dashed into fixtures of period ``dash``."""
    p0 = np.asarray(p0, np.float64)
    t = unit(t)
    p0 = p0 - (p0 @ t) * t
    dist0 = np.linalg.norm(p0)
    ph = p0 / dist0
    n = unit(np.cross(ph, t))
    dn = D @ n
    c0 = D @ ph
    c1 = D @ t
    ok = c0 > 1e-4
    s = np.where(ok, dist0 * c1 / np.maximum(c0, 1e-4), 0.0)
    dist = np.where(ok, dist0 * np.sqrt(c0 ** 2 + c1 ** 2) / np.maximum(c0, 1e-4), 1e9)
    half = (width / 2) / dist
    off = np.abs(np.arcsin(np.clip(dn, -1, 1)))
    m = (1 - smooth((off - half * 0.6) / np.maximum(half * 0.4, 1e-6))) * ok
    if dash:
        f = np.mod(s / dash, 1.0)
        m = m * (1 - smooth((f - duty) / 0.04)) * smooth(f / 0.04)
    if length is not None:
        m = m * (np.abs(s) < length)
    return m


def sky(D, top, horizon, ground, hz=0.08):
    z = D[..., 2]
    up = smooth(z / 0.9)
    dn = smooth(-z / 0.6)
    band = np.exp(-(z / hz) ** 2)
    img = np.asarray(horizon) * (1 - up - dn)[..., None] + np.asarray(top) * up[..., None] + \
        np.asarray(ground) * dn[..., None]
    return img + np.asarray(horizon)[None, None, :] * 0.25 * band[..., None]


def normalise(img, target=0.8):
    lum = img @ np.array([0.2126, 0.7152, 0.0722])
    h = img.shape[0]
    el = ((np.arange(h) + 0.5) / h - 0.5) * np.pi
    w = np.cos(el)[:, None]
    mean = float((lum * w).sum() / (w.sum() * img.shape[1]))
    return img * (target / max(mean, 1e-9))


# --- the looks ----------------------------------------------------------------------------------------------

def scifi_studio(D):
    """A dark product stage: a big soft key front-left-above, a cool and a warm rim strip behind, a soft top light."""
    img = sky(D, (0.012, 0.014, 0.02), (0.02, 0.022, 0.03), (0.008, 0.008, 0.01))
    add(img, rect(D, (-0.55, -1.0, 0.55), 38, 30, soft=0.3), col((1.0, 0.96, 0.9), 22))
    add(img, rect(D, (1.0, -0.6, 0.15), 24, 34, soft=0.4), col((0.85, 0.9, 1.0), 5))       # (a weak fill right)
    add(img, rect(D, (-0.8, 0.9, 0.1), 7, 60, soft=0.25), col((0.45, 0.85, 1.0), 60))      # (cool rim back-left)
    add(img, rect(D, (0.85, 0.85, 0.1), 7, 60, soft=0.25), col((1.0, 0.6, 0.25), 52))      # (warm rim back-right)
    add(img, rect(D, (0.0, 0.1, 1.0), 50, 14, up=(0, 1, 0), soft=0.35), col((0.95, 0.97, 1.0), 9))
    return img


def hangar_bay(D):
    """Rows of long ceiling strip lights, amber wall lamps, the hangar door open on a hazy day at one side."""
    img = sky(D, (0.02, 0.022, 0.025), (0.03, 0.03, 0.03), (0.035, 0.034, 0.032))
    for y in np.arange(-36, 37, 6.0):                                          # (strips along X above)
        add(img, line(D, (0, y, 9.0), (1, 0, 0), 0.5, dash=7.0, duty=0.8), col((0.92, 0.96, 1.0), 26))
    for x in (-1, 1):                                                          # (the ceiling beams: dark lines)
        for y in np.arange(-33, 34, 6.0):
            img *= (1 - 0.6 * line(D, (x * 0.0, y, 9.6), (1, 0, 0), 0.8))[..., None]
    for k in range(10):                                                        # (sodium lamps on the walls)
        a = np.radians(18 + k * 36)
        add(img, disc(D, (np.cos(a), np.sin(a), 0.18), 1.3), col((1.0, 0.55, 0.15), 60))
        add(img, glow(D, (np.cos(a), np.sin(a), 0.18), 6), col((1.0, 0.5, 0.15), 0.6))
    door = rect(D, (1.0, 0.0, 0.08), 70, 22, soft=0.06)                        # (the open door: day outside)
    add(img, door, col((0.85, 0.9, 1.0), 9))
    add(img, door * smooth((D[..., 2] + 0.02) / 0.05), col((0.4, 0.5, 0.65), 6))
    add(img, glow(D, (1.0, 0.0, -0.3), 25) * (D[..., 2] < 0), col((0.6, 0.62, 0.6), 1.2))   # (light on the floor)
    return img


def ship_corridor(D):
    """A long corridor along Y: dashed light strips where the ceiling meets the walls, cyan guide lines at the floor,
    a bright door at the far end (front-right of the model), the corridor behind dark."""
    img = sky(D, (0.012, 0.016, 0.02), (0.02, 0.025, 0.03), (0.012, 0.014, 0.016))
    for x in (-1.6, 1.6):
        add(img, line(D, (x, 0, 1.4), (0, 1, 0), 0.14, dash=1.6, duty=0.7), col((0.85, 0.95, 1.0), 34))
        add(img, line(D, (x, 0, -1.3), (0, 1, 0), 0.05), col((0.1, 0.9, 1.0), 22))
        for k in range(-12, 13):                                               # (wall ribs: faint, dark)
            img *= (1 - 0.35 * line(D, (x, k * 1.6 + 0.8, 0), (0, 0, 1), 0.18, length=1.4))[..., None]
    add(img, rect(D, (0.0, -1.0, 0.05), 9, 13, soft=0.1), col((1.0, 0.85, 0.65), 40))      # (the far door, front)
    add(img, glow(D, (0.0, -1.0, 0.0), 14), col((1.0, 0.75, 0.5), 0.8))
    ceil = np.exp(-(np.arctan2(D[..., 0], np.maximum(D[..., 2], 1e-3)) / 0.35) ** 2) * smooth(D[..., 2] / 0.5)
    add(img, ceil, col((0.6, 0.7, 0.8), 1.2))                                                  # (ceiling glow)
    return img


def neon_lab(D):
    """A dark lab: magenta and cyan neon tubes behind (rim lights), a small cool soft box above-front, LED dots."""
    img = sky(D, (0.008, 0.008, 0.012), (0.014, 0.012, 0.02), (0.01, 0.01, 0.012))
    add(img, line(D, (-2.2, 2.2, 0), (0, 0, 1), 0.08, length=2.4), col((1.0, 0.15, 0.7), 70))
    add(img, line(D, (2.2, 2.2, 0), (0, 0, 1), 0.08, length=2.4), col((0.1, 0.85, 1.0), 70))
    add(img, line(D, (0, 3.2, 2.0), (1, 0, 0), 0.06, length=2.5), col((0.6, 0.3, 1.0), 40))
    add(img, glow(D, (-1, 1, 0), 30), col((0.5, 0.05, 0.35), 0.35))
    add(img, glow(D, (1, 1, 0), 30), col((0.04, 0.35, 0.5), 0.35))
    add(img, rect(D, (0.3, -1.0, 0.9), 26, 18, soft=0.35), col((0.85, 0.92, 1.0), 9))
    for _k in range(60):                                                       # (status LEDs round the room)
        a = RNG.uniform(0, 2 * np.pi)
        z = RNG.uniform(-0.25, 0.35)
        c = ((0.2, 1.0, 0.3), (1.0, 0.3, 0.1), (0.2, 0.6, 1.0))[_k % 3]
        add(img, disc(D, (np.cos(a), np.sin(a), z), 0.25, soft=0.5), col(c, 30))
    return img


def orbital_window(D):
    """Space: a hard sun above-front-left, a planet's lit limb filling from below-front, black space with stars,
    the station's dim warm interior behind."""
    img = np.zeros(D.shape, np.float64) + 0.0015
    stars = (RNG.random(D.shape[:2]) > 0.9993) * (D[..., 2] > -0.05)
    add(img, stars * RNG.uniform(0.5, 4.0, D.shape[:2]), col((0.9, 0.95, 1.0), 1.0))
    sun = unit((-0.6, -1.0, 0.75))
    add(img, disc(D, sun, 0.55, soft=0.3), col((1.0, 0.97, 0.92), 36000))   # (the sun leads: hard shadows)
    add(img, glow(D, sun, 4), col((1.0, 0.95, 0.85), 2.5))
    pl = unit((0.2, -1.0, -1.1))                                               # (the planet: a big disc below-front)
    pd = disc(D, pl, 48, soft=0.03)
    lit = np.clip(D @ sun * 0.5 + 0.55, 0, 1) ** 1.5
    clouds = 0.88 + 0.12 * np.sin(D[..., 0] * 7 + np.sin(D[..., 1] * 5) * 1.5) * np.cos(D[..., 1] * 6 + D[..., 2] * 4)
    add(img, pd * lit * clouds, col((0.35, 0.55, 0.95), 2.6))
    limb = np.exp(-((np.degrees(np.arccos(np.clip(D @ pl, -1, 1))) - 48) / 1.6) ** 2)
    add(img, limb * lit, col((0.45, 0.7, 1.0), 3.0))
    back = smooth((D[..., 1] - 0.3) / 0.25)                                    # (the station behind the model: dim,
    img = img * (1 - back)[..., None] + back[..., None] * np.array([0.012, 0.011, 0.01])   # its window frame lit)
    add(img, np.exp(-((D[..., 1] - 0.3) / 0.02) ** 2), col((0.75, 0.85, 1.0), 6))
    for z in (0.35, -0.2):
        add(img, line(D, (0, 2.5, z * 3), (1, 0, 0), 0.05, dash=0.9, duty=0.5) * back, col((1.0, 0.8, 0.55), 10))
    return img


def red_alert(D):
    """An emergency: red beacons spinning (bright red heads with a sweep), dim white floor strips, smoke-dark room."""
    img = sky(D, (0.012, 0.006, 0.006), (0.03, 0.01, 0.01), (0.01, 0.006, 0.006))
    for k in range(5):
        a = np.radians(30 + k * 72)
        c = (np.cos(a), np.sin(a), 0.45)
        add(img, disc(D, c, 1.8, soft=0.4), col((1.0, 0.08, 0.03), 120))
        add(img, glow(D, c, 12), col((1.0, 0.1, 0.04), 1.3))
        sw = unit((np.cos(a + 0.4), np.sin(a + 0.4), 0.2))                    # (the beam's sweep on the wall)
        add(img, rect(D, sw, 26, 7, soft=0.6), col((1.0, 0.08, 0.04), 6))
    for k in range(6):                                                         # (dim white strips on the walls)
        a = np.radians(k * 60)
        add(img, line(D, (2.4 * np.cos(a), 2.4 * np.sin(a), 0), (0, 0, 1), 0.07, length=1.0), col((0.9, 0.95, 1.0), 12))
    add(img, rect(D, (0.0, -0.3, 1.0), 24, 14, up=(0, 1, 0), soft=0.5), col((0.8, 0.85, 1.0), 2.5))
    return img


def reactor_core(D):
    """Above the reactor well: a blue-white glow from below with a bright ring, orange warning lamps round the walls,
    a dark ceiling."""
    img = sky(D, (0.006, 0.008, 0.012), (0.02, 0.028, 0.04), (0.04, 0.12, 0.2))
    down = smooth((-D[..., 2] - 0.2) / 0.6)
    add(img, down, col((0.25, 0.65, 1.0), 4.5))
    el = np.degrees(np.arcsin(np.clip(D[..., 2], -1, 1)))
    add(img, np.exp(-((el + 38) / 1.6) ** 2), col((0.5, 0.85, 1.0), 28))      # (the ring round the core)
    add(img, disc(D, (0, 0, -1), 14, soft=0.4), col((0.8, 0.95, 1.0), 30))   # (the core under the model)
    for k in range(8):
        a = np.radians(k * 45 + 10)
        add(img, disc(D, (np.cos(a), np.sin(a), 0.25), 1.0), col((1.0, 0.45, 0.05), 80))
        add(img, glow(D, (np.cos(a), np.sin(a), 0.25), 7), col((1.0, 0.4, 0.05), 0.5))
    for k in range(16):                                                        # (vertical panel seams: faint)
        a = np.radians(k * 22.5)
        img *= (1 - 0.3 * line(D, (2.5 * np.cos(a), 2.5 * np.sin(a), 0), (0, 0, 1), 0.06, length=3))[..., None]
    return img


def landing_pad(D):
    """Outside under a high thin overcast: soft even light from a bright sky, the sun a soft glow, a grey pad below
    with yellow guide lights - for looking at the forms without hard shadows."""
    img = sky(D, (0.75, 0.82, 0.95), (1.0, 0.98, 0.95), (0.16, 0.16, 0.16), hz=0.12)
    sun = unit((-0.4, -0.8, 0.6))
    add(img, glow(D, sun, 10), col((1.0, 0.95, 0.85), 6))
    add(img, disc(D, sun, 2.0, soft=0.8), col((1.0, 0.96, 0.9), 40))
    for k in range(24):
        a = np.radians(k * 15)
        add(img, disc(D, (np.cos(a), np.sin(a), -0.12), 0.35), col((1.0, 0.75, 0.1), 40))
    return img


LOOKS = (
    ('scifi_studio', 'Sci-Fi Studio', scifi_studio, 0.8),
    ('hangar_bay', 'Hangar Bay', hangar_bay, 0.8),
    ('ship_corridor', 'Ship Corridor', ship_corridor, 0.7),
    ('neon_lab', 'Neon Lab', neon_lab, 0.6),
    ('orbital_window', 'Orbital Window', orbital_window, 0.7),
    ('red_alert', 'Red Alert', red_alert, 0.55),
    ('reactor_core', 'Reactor Core', reactor_core, 0.75),
    ('landing_pad', 'Landing Pad', landing_pad, 0.8),
)


def write_exr(path, rgb):
    import bpy
    h, w = rgb.shape[:2]
    px = np.concatenate([rgb, np.ones((h, w, 1))], axis=2).astype(np.float32)
    img = bpy.data.images.new('mch_hdri', w, h, alpha=False, float_buffer=True)
    sc = bpy.data.scenes.new('mch_hdri_save')
    try:
        img.pixels.foreach_set(px.ravel())
        st = sc.render.image_settings
        st.file_format = 'OPEN_EXR'
        st.color_mode = 'RGB'
        st.color_depth = '16'
        st.exr_codec = 'DWAA'
        tmp = path + '.part.exr'
        img.save_render(tmp, scene=sc)
        os.replace(tmp, path)
    finally:
        bpy.data.images.remove(img)
        bpy.data.scenes.remove(sc)


def main():
    sys.path.insert(0, os.path.join(ROOT, 'addon', 'mecha_lab'))
    import hdri_thumbs
    os.makedirs(OUT, exist_ok=True)
    D = directions()
    keys = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    for key, _name, fn, target in LOOKS:
        if keys and key not in keys:
            continue
        img = normalise(fn(D), target)
        p = os.path.join(OUT, key + '.exr')
        write_exr(p, img)
        hdri_thumbs.make_thumb(p, os.path.join(ICONS, f'hdri_mch_{key}.png'))
        print(key, os.path.getsize(p) // 1024, 'KB', 'max %.0f' % img.max())


if __name__ == '__main__':
    main()
