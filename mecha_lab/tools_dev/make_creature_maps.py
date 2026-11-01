"""Reference maps for the Creature Shader (0.24.95 user: "썸네일 뽑아 주면 내가 지피티로 고화질 텍스처로 바꿔 올게").

Made procedurally here (512 px, every one tiles: spectral noise is periodic, Voronoi points / dots / lines wrap round
the edges) as the reference the user turns into high-resolution textures; the returned pack goes in with
``tools_dev/import_photo_maps.py`` (the same <slot>/<slot>_<ID> layout as the Mech Shader pack).

    python3 tools_dev/make_creature_maps.py [OUT]      (numpy + Pillow)

Writes OUT/<slot>/<slot>_<ID>.png, OUT/PROMPTS.md (what each map is, a prompt for an image generator) and a labelled
contact sheet OUT/../creature_map_refs_0.24.95.jpg.  Default OUT: dist/creature_map_refs_0.24.95.

All greyscale:
    skin     height - white raised, black deep (pores, wrinkles, scales, warts ...)
    mottle   colour breakup - white = where the second colour / darker tone goes
    organic  layer masks - white = the substance (blood, slime, moss, cracked mud ...)
Mud, dust, splashes, soot, frost and snow come from the Mech Shader's dirt / snow maps."""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_mech_maps import (N, XX, YY, blur, lines, norm, soft, spectral, warp, worley)  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'dist', 'creature_map_refs_0.24.95')

# slot -> (what it is, the prompt's opening, [(ID, name, Korean name, what it shows)])
MAPS = {
    'skin': ('Height maps of the skin - white raised, black deep',
             'greyscale height map, white is raised and black is deep',
             [('PORES', 'Human Pores', '사람 모공', 'human skin: fine pores and tiny creases, very subtle'),
              ('WRINKLES', 'Fine Wrinkles', '잔주름', 'fine criss-cross skin wrinkles, like the back of a hand'),
              ('HIDE', 'Deep Hide Folds', '두꺼운 가죽 주름', 'elephant / rhino hide: deep cracked folds and grooves '
               'between thick raised patches'),
              ('SCALES_S', 'Small Scales', '작은 비늘', 'lizard skin: small round bumpy scales packed tightly'),
              ('SCALES_L', 'Large Scales', '큰 비늘', 'dragon skin: large rounded scales with crisp grooves between '
               'them'),
              ('SNAKE', 'Snake Scales', '뱀 비늘', 'snake skin: overlapping diamond-shaped scales in offset rows, '
               'like roof shingles'),
              ('SCUTES', 'Croc Scutes', '악어 등판', 'crocodile back: big rectangular bony plates (scutes) in rows, '
               'each with a raised ridge'),
              ('WARTS', 'Toad Warts', '두꺼비 사마귀', 'toad skin: scattered round warts of many sizes on bumpy skin'),
              ('DENTICLES', 'Shark Skin', '상어 피부', 'shark skin: tiny dense tooth-like denticles with fine ridges '
               'all pointing one way'),
              ('CHITIN', 'Chitin Plates', '곤충 껍질', 'insect shell: hard flat polygon plates with thin grooves and '
               'tiny pits'),
              ('MEMBRANE', 'Membrane Veins', '막 핏줄', 'bat-wing membrane: a branching network of thin raised veins '
               'on thin smooth skin'),
              ('HORN', 'Horn / Bone Grain', '뿔 · 뼈 결', 'horn / bone: long fibrous striations along one direction '
               'with faint growth rings')]),
    'mottle': ('Colour breakup - white is where the second colour / darker tone goes',
               'greyscale mask, white is the marking and black the base skin',
               [('BLOTCH', 'Blotches', '얼룩', 'soft irregular blotches of different sizes, like animal skin '
                 'colouring'),
                ('FRECKLES', 'Freckles', '주근깨', 'small freckles and dots, denser in patches'),
                ('VEINS', 'Veins', '핏줄', 'thin branching veins under the skin, soft edges'),
                ('SPOTS', 'Leopard Spots', '표범 점', 'leopard rosettes: broken rings of spots'),
                ('STRIPES', 'Tiger Stripes', '호랑이 줄', 'tiger stripes: wavy tapering stripes of varying width'),
                ('MARBLE', 'Frog Marbling', '개구리 마블', 'poison-frog marbling: swirling organic bands and blobs'),
                ('BRUISE', 'Bruises', '멍', 'soft bruises and discoloured patches with blurry edges'),
                ('ROT', 'Rot Patches', '부패 반점', 'rotting skin: blotchy decayed patches with darker rims')]),
    'organic': ('Layer masks - white is the substance',
                'greyscale mask, white is the substance and black is clean skin',
                [('BLOOD', 'Blood Splatter', '피 튐', 'fresh blood splatter: drops, splashes and small satellite '
                  'droplets'),
                 ('BLOOD_DRY', 'Dried Blood', '마른 피', 'dried smeared blood patches, cracked and flaking'),
                 ('SLIME', 'Slime Sheen', '점액 광택', 'a thin glossy layer of slime in uneven streaks and pools'),
                 ('DRIPS', 'Slime Drips', '점액 흘러내림', 'slime / goo dripping down: vertical runs ending in '
                  'drops'),
                 ('MOSS', 'Moss', '이끼', 'clumpy moss growth with fuzzy edges and gaps'),
                 ('ALGAE', 'Algae Film', '녹조', 'a thin film of algae / swamp scum, patchy and speckled'),
                 ('MUD_CRACK', 'Cracked Mud', '갈라진 진흙', 'dried mud crust broken into cracked plates (cracks '
                  'black)'),
                 ('SCARS', 'Scars', '흉터', 'healed scars: long slash marks and puncture scars, slightly raised')])}

PROMPT = ('Seamless tileable texture, square, 2048 x 2048, seen straight from above (orthographic), flat even lighting '
          'with no shadows, highlights or perspective, {kind}: {what}. Fills the whole square edge to edge and tiles '
          'perfectly on all four sides. No text, no border, no vignette.')


def dots(count, sigma, seed, size_var=0.5, density=None):
    """Round soft dots: random impulses blurred (wraps round the tile).  ``density``: a 0..1 map where they gather."""
    rng = np.random.default_rng(seed)
    img = np.zeros((N, N))
    xs, ys = rng.integers(0, N, count), rng.integers(0, N, count)
    if density is not None:
        keep = rng.random(count) < density[ys, xs]
        xs, ys = xs[keep], ys[keep]
    np.add.at(img, (ys, xs), rng.uniform(1.0 - size_var, 1.0 + size_var, len(xs)))
    return blur(img, sigma)


def cell_dome(f1, f2, power=2.0):
    """A dome per Voronoi cell: 1 at its centre, 0 at its border."""
    d = f1 / np.maximum(f1 + f2, 1e-9) * 2.0
    return np.sqrt(np.clip(1.0 - d ** power, 0.0, 1.0))


def ridges(seed, beta=2.2, fmin=3.0, sharp=10.0, aniso=(1.0, 1.0), angle=0.0):
    """Thin lines where a noise crosses its middle."""
    n = spectral(seed, beta, fmin=fmin, aniso=aniso, angle=angle)
    return np.exp(-((n - 0.5) * sharp) ** 2)


# ---------------------------------------------------------------- skin (height)
def skin():
    out = {}
    fine = spectral(11, 1.4, fmin=40)
    f1, _ = worley(1200, 12)
    pits = np.exp(-(f1 / 1.4) ** 2)
    crease = ridges(13, 2.0, fmin=12, sharp=14, aniso=(1, 4), angle=35) * 0.5 + \
        ridges(14, 2.0, fmin=12, sharp=14, aniso=(1, 4), angle=-50) * 0.5
    out['PORES'] = norm(0.6 + fine * 0.25 - pits * 0.5 - crease * 0.25)
    w1 = ridges(21, 2.4, fmin=4, sharp=16, aniso=(1, 5), angle=30)
    w2 = ridges(22, 2.4, fmin=4, sharp=16, aniso=(1, 5), angle=-40)
    w3 = ridges(24, 2.2, fmin=10, sharp=20, aniso=(1, 4), angle=75) * 0.5
    out['WRINKLES'] = norm(1.0 - 0.7 * np.maximum(np.maximum(w1, w2 * 0.85), w3) + spectral(23, 1.6, fmin=30) * 0.1)
    f1, f2 = worley(60, 31, jitter=0.9, grid=True)
    big = np.exp(-((f2 - f1) / 3.0) ** 2)
    f1s, f2s = worley(380, 32, jitter=0.9, grid=True)
    small = np.exp(-((f2s - f1s) / 1.6) ** 2)
    hide = spectral(33, 2.6, fmax=10) * 0.4 + (1.0 - big) * 0.45 - small * 0.25 + spectral(34, 1.5, fmin=40) * 0.1
    out['HIDE'] = norm(warp(hide, 10, 35))
    f1, f2 = worley(700, 41, jitter=0.8, grid=True)
    out['SCALES_S'] = norm(cell_dome(f1, f2, 2.0) + spectral(42, 1.5, fmin=40) * 0.15)
    f1, f2 = worley(100, 51, jitter=0.7, grid=True)
    groove = soft(f2 - f1, 0.0, 3.0)
    out['SCALES_L'] = norm(cell_dome(f1, f2, 4.0) * 0.8 * groove + spectral(52, 1.6, fmin=30) * 0.12)
    rows, cols = 16, 16                                     # (snake: offset rows of shingled diamonds; whole cells per tile)
    h, w = N / rows, N / cols
    r = np.floor(YY / h)
    xs = XX + (r % 2) * w / 2
    u = (xs % w) / w - 0.5
    v = (YY % h) / h
    d = np.abs(u) + np.abs(v - 0.5)                         # (L1: a diamond; the offset rows interlock)
    dome = np.clip(1.0 - (d / 0.5) ** 1.5, 0.0, 1.0)
    keel = np.exp(-(u / 0.05) ** 2) * dome * 0.15
    out['SNAKE'] = norm((dome + keel) * (0.45 + 0.55 * v) + spectral(61, 1.5, fmin=40) * 0.06)
    f1, f2 = worley(36, 71, jitter=0.25, grid=True)
    plate = soft(f2 - f1, 0.0, 5.0)
    keel = np.exp(-(f1 / (N / 6 * 0.25)) ** 2)
    out['SCUTES'] = norm(plate * (0.55 + 0.35 * keel) + spectral(72, 1.8, fmin=20) * 0.12)
    f1b, _ = worley(64, 81, jitter=0.9, grid=True)
    f1s, _ = worley(400, 82, jitter=0.9, grid=True)
    rng = np.random.default_rng(84)
    big = np.sqrt(np.clip(1.0 - (f1b / 13.0) ** 2, 0.0, 1.0))
    small = np.sqrt(np.clip(1.0 - (f1s / 5.0) ** 2, 0.0, 1.0))
    out['WARTS'] = norm(spectral(83, 2.0, fmin=10) * 0.15 + np.maximum(big, small * 0.6))
    k = 48
    den = (np.sin(2 * math.pi * k * (XX + spectral(92, 2.5, fmax=8) * 6) / N) *
           np.sin(2 * math.pi * k * (YY + spectral(93, 2.5, fmax=8) * 6) / N))
    streak = spectral(94, 1.8, fmin=30, aniso=(1, 10), angle=20)
    out['DENTICLES'] = norm(soft(den, 0.2, 0.9) * 0.7 + streak * 0.3)
    f1, f2 = worley(120, 101, jitter=0.9, grid=True)
    pits = dots(900, 0.9, 102)
    out['CHITIN'] = norm(soft(f2 - f1, 0.0, 2.5) * 0.85 - np.tanh(pits * 12) * 0.2 + spectral(103, 2.4, fmax=8) * 0.1)
    f1, f2 = worley(70, 111, jitter=0.9, grid=True)
    v1 = np.exp(-((f2 - f1) / 1.3) ** 2)
    f1s, f2s = worley(350, 112, jitter=0.9, grid=True)
    v2 = np.exp(-((f2s - f1s) / 0.8) ** 2)
    out['MEMBRANE'] = norm(warp(0.3 + v1 * 0.6 + v2 * 0.3, 8, 113) + spectral(114, 1.5, fmin=40) * 0.05)
    fib = spectral(121, 1.6, fmin=4, aniso=(1, 40), angle=90)
    rings = np.sin(2 * math.pi * 7 * (YY + spectral(122, 2.6, fmax=6) * 40) / N) * 0.12
    out['HORN'] = norm(fib * 0.85 + rings + spectral(123, 1.4, fmin=50) * 0.08)
    return out


# ---------------------------------------------------------------- mottle (colour breakup)
def mottle():
    out = {}
    out['BLOTCH'] = soft(spectral(201, 3.0, fmax=12) + spectral(202, 2.0, fmin=10) * 0.15, 0.5, 0.7)
    dens = soft(spectral(211, 3.0, fmax=6), 0.15, 0.6)
    out['FRECKLES'] = np.clip(np.tanh(dots(2200, 1.6, 212, 0.7, density=dens) * 14), 0, 1)
    v = np.maximum(ridges(221, 3.0, fmin=2, sharp=22), ridges(222, 3.0, fmin=4, sharp=30) * 0.6)
    out['VEINS'] = soft(blur(warp(v, 10, 223), 0.8), 0.25, 0.8)
    f1, _ = worley(110, 231, jitter=0.8, grid=True)
    cell = N / math.sqrt(110)
    ring = np.exp(-((f1 - cell * 0.28) / (cell * 0.07)) ** 2)
    broken = ring * soft(spectral(232, 1.8, fmin=12), 0.35, 0.55)
    centre = np.exp(-(f1 / (cell * 0.14)) ** 2) * 0.25
    out['SPOTS'] = np.clip(warp(broken + centre, 4, 233) * 1.3, 0, 1)
    wobble = spectral(241, 2.8, fmax=6) * 70 + spectral(242, 2.0, fmin=6) * 12
    s = np.sin(2 * math.pi * 7 * (XX + wobble) / N)
    width = 0.55 + spectral(243, 2.5, fmax=8) * 0.35
    out['STRIPES'] = np.clip((s - width) / 0.12, 0.0, 1.0)
    turb = spectral(251, 2.2, fmax=20) * 90
    m = np.sin(2 * math.pi * (3 * XX + 2 * YY + 3 * turb) / N)          # (whole periods both ways: tiles)
    out['MARBLE'] = soft(m + (spectral(252, 3.0, fmax=8) - 0.5) * 0.8, 0.1, 0.45)
    blobs = norm(dots(12, 28.0, 261, 0.5))
    out['BRUISE'] = np.clip(soft(blobs, 0.25, 0.9) * (0.6 + 0.4 * spectral(262, 2.4, fmax=14)), 0, 1)
    p = spectral(271, 2.6, fmax=10)
    patch = soft(p, 0.55, 0.62)
    rim = soft(p, 0.52, 0.56) * (1.0 - soft(p, 0.58, 0.62))
    out['ROT'] = np.clip(patch * 0.7 + rim * 0.9 + spectral(272, 1.5, fmin=40) * 0.2 * patch, 0, 1)
    return out


# ---------------------------------------------------------------- organic (layer masks)
def organic():
    out = {}
    drops = np.tanh(dots(22, 7.0, 301, 0.7) * 900)
    sats = np.tanh(dots(260, 1.6, 302, 0.8) * 30)
    rng = np.random.default_rng(303)
    segs = []
    for _ in range(30):
        x, y = rng.random(2) * N
        a = rng.uniform(0, 2 * math.pi)
        L = rng.uniform(10, 40)
        segs.append((x, y, x + math.cos(a) * L, y + math.sin(a) * L, rng.uniform(1.5, 3.5), 1.0))
    edge = spectral(304, 1.5, fmin=30) * 0.2
    out['BLOOD'] = soft(np.maximum(np.maximum(drops, sats), lines(segs)) - edge, 0.3, 0.45)
    patch = soft(spectral(311, 2.6, fmax=12), 0.55, 0.6)
    f1, f2 = worley(160, 312, jitter=0.9, grid=True)
    cracks = np.exp(-((f2 - f1) / 1.2) ** 2)
    out['BLOOD_DRY'] = np.clip(patch * (1.0 - cracks * 0.9) * (0.75 + spectral(313, 1.5, fmin=30) * 0.25), 0, 1)
    streaks = spectral(321, 1.8, fmin=3, aniso=(1, 14), angle=0)
    pools = spectral(322, 3.0, fmax=8)
    out['SLIME'] = soft(streaks * 0.6 + pools * 0.6, 0.55, 0.75)
    rng = np.random.default_rng(331)
    segs, ends = [], np.zeros((N, N))
    for _ in range(26):
        x, y = rng.random() * N, rng.random() * N
        L = rng.uniform(40, 220)
        w = rng.uniform(2.0, 6.0)
        k = 8
        for i in range(k):
            x2 = x + rng.normal(0, 1.2)
            segs.append((x, y + L * i / k, x2, y + L * (i + 1) / k, w * (1.0 - 0.4 * i / k), 1.0))
            x = x2
        ends[int(y + L) % N, int(x) % N] += 1.0
    drop_tips = np.tanh(blur(ends, w * 0.9) * 400)
    out['DRIPS'] = np.clip(np.maximum(lines(segs), drop_tips), 0, 1)
    clumps = spectral(341, 2.4, fmax=24)
    fuzz = spectral(342, 1.2, fmin=60)
    out['MOSS'] = soft(clumps + (fuzz - 0.5) * 0.35, 0.5, 0.62)
    film = soft(spectral(351, 2.8, fmax=10), 0.45, 0.7)
    speck = np.tanh(dots(1800, 1.0, 352, 0.8) * 10)
    out['ALGAE'] = np.clip(film * 0.75 + speck * film * 0.4 + spectral(353, 1.6, fmin=30) * 0.15 * film, 0, 1)
    f1, f2 = worley(55, 361, jitter=0.9, grid=True)
    crack = np.exp(-((f2 - f1) / 2.0) ** 2)
    f1s, f2s = worley(260, 362, jitter=0.9, grid=True)
    crack2 = np.exp(-((f2s - f1s) / 1.0) ** 2) * 0.5
    curl = soft(f2 - f1, 0.0, 10.0)
    out['MUD_CRACK'] = norm(warp((1.0 - np.maximum(crack, crack2)) * (0.7 + 0.3 * curl), 5, 363))
    rng = np.random.default_rng(371)
    segs = []
    for _ in range(9):
        x, y = rng.random(2) * N
        a = rng.uniform(-0.6, 0.6) + (math.pi / 2 if rng.random() < 0.3 else 0)
        L = rng.uniform(90, 220)
        steps = 10
        for i in range(steps):
            t = i / steps
            dx = math.cos(a + 0.15 * math.sin(t * 3)) * L / steps
            dy = math.sin(a + 0.15 * math.sin(t * 3)) * L / steps
            segs.append((x, y, x + dx, y + dy, rng.uniform(5, 9) * math.sin(math.pi * (t + 0.05)), 1.0))
            x, y = x + dx, y + dy
    pucks = np.tanh(dots(16, 3.0, 372, 0.4) * 300)
    out['SCARS'] = np.clip(blur(np.maximum(lines(segs), pucks), 1.0) * 1.1, 0, 1)
    return out


# ---------------------------------------------------------------- write
def save(slot, ident, a):
    d = os.path.join(OUT, slot)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f'{slot}_{ident.lower()}.png')
    Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), 'L').save(p, optimize=True)
    return p


def seam_ok(a):
    """Across the tile's edge the map changes no more than inside (it repeats without a line)."""
    edge = max(np.abs(a[:, 0] - a[:, -1]).mean(), np.abs(a[0] - a[-1]).mean())
    inner = max(np.abs(a[:, 1:] - a[:, :-1]).mean(), np.abs(a[1:] - a[:-1]).mean())
    return edge <= inner * 1.6 + 1e-3


def font(size):
    for f in ('/usr/share/fonts/truetype/nanum/NanumGothic.ttf', '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
              '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if os.path.isfile(f):
            return ImageFont.truetype(f, size), 'CJK' in f or 'Nanum' in f
    return ImageFont.load_default(size), False


def sheet(maps):
    """All maps, labelled, in one picture (slot by slot)."""
    tile, pad, head, cols = 200, 12, 46, 6
    rows = sum(math.ceil(len(MAPS[s][2]) / cols) for s in MAPS)
    W = cols * (tile + pad) + pad
    H = rows * (tile + 44 + pad) + len(MAPS) * head + pad
    img = Image.new('RGB', (W, H), (30, 31, 35))
    d = ImageDraw.Draw(img)
    f_big, cjk = font(22)
    f_small, _ = font(15)
    y = pad
    for slot, (what, _k, items) in MAPS.items():
        d.text((pad, y + 10), f'{slot}  -  {what}', fill=(235, 236, 240), font=f_big)
        y += head
        for i, (ident, name, ko, _w) in enumerate(items):
            c = i % cols
            if c == 0 and i:
                y += tile + 44 + pad
            x = pad + c * (tile + pad)
            im = Image.fromarray((np.clip(maps[slot][ident], 0, 1) * 255).astype(np.uint8), 'L').resize((tile, tile))
            img.paste(im.convert('RGB'), (x, y))
            label = f'{ident}  {ko}' if cjk else ident
            d.text((x, y + tile + 4), label, fill=(235, 236, 240), font=f_small)
            d.text((x, y + tile + 22), name, fill=(150, 152, 160), font=f_small)
        y += tile + 44 + pad
    return img


def main():
    makers = {'skin': skin, 'mottle': mottle, 'organic': organic}
    maps = {}
    bad = []
    for slot, make in makers.items():
        maps[slot] = make()
        for ident, _n, _k, _w in MAPS[slot][2]:
            a = maps[slot][ident]
            save(slot, ident, a)
            if not seam_ok(a):
                bad.append(f'{slot}/{ident}')
            print(f'{slot}/{ident}', flush=True)
    lines_ = ['# Creature Shader - reference maps (Mecha Lab 0.24.95)', '',
              'Each map here is a 512 px placeholder made by `tools_dev/make_creature_maps.py`.  Make a high-resolution '
              'version of each (any size, 2048 px is good), keep the **same folder and file name** '
              '(`skin/skin_scales_l.png` ...; .jpg or .png), and send the folder back.', '',
              'All maps are **greyscale** and must **tile seamlessly** (they repeat over the model).', '']
    for slot, (what, kind, items) in MAPS.items():
        lines_ += [f'## {slot} - {what}', '']
        for ident, name, ko, w in items:
            lines_ += [f'### `{slot}/{slot}_{ident.lower()}` - {name} ({ko})', '',
                       PROMPT.format(kind=kind, what=w), '']
    with open(os.path.join(OUT, 'PROMPTS.md'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines_))
    sp = os.path.join(os.path.dirname(OUT), os.path.basename(OUT) + '.jpg')
    sheet(maps).save(sp, quality=90)
    print('sheet', sp)
    print('seams not ok:', bad or 'none')


if __name__ == '__main__':
    main()
