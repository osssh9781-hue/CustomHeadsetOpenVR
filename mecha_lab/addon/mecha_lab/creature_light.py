"""Creature Light (0.24.147, user: "크리쳐용 hdri ... 크리쳐의 기본 텍스쳐가 잘보이고 라이팅이 어느정도 부드럽고 스펙큘러도
과하지 않게 ... 익스포져랑 빛부분 에미션도 조절 ... 휴랑 세추리이션도 ... 30종 ... 가볍게").

30 lighting set-ups for creatures, made in the world's nodes - no picture files at all (light: nothing to load, nothing
in the zip): a sky gradient (top / horizon / ground) and up to four big soft lights (round, smooth-edged patches of
the sky).  Big soft lights = soft shadows and broad, quiet highlights, and the sky fills the shadows so the base
texture still reads.  Each set-up is levelled to the same brightness (the brightest side of a white part), so
switching keeps the exposure.

Like an HDRI maker: Exposure (stops), Light Emission (the lights only), Sky Fill (the sky only), Hue, Saturation,
Softness (the lights bigger and softer, the same light put out), Rotation (the lights round the model).
Lights Seen by Camera off (default): the camera sees only the soft sky gradient behind the model, the lights still
light it and show in its reflections.

The floor (user: "바닥은 쉐도우 케쳐도 좋은데 그거랑 같이 그냥 플랜인디 그라데이션 맵으로 가운데부분만 불투명하고 외곽은
투명하게 원처럼"):
  Shadow Catcher  a disc under the model that shows only the shadows on the background (Cycles).
  Fade Floor      a disc whose centre is a soft floor and whose edge fades out to transparent in a smooth circle -
                  no hard edge, nothing for a denoiser to chew on.
The disc sits under the lowest visible part, centred under the parts, sized to them (Fit to Model again after a move).

The world: 'MCH Creature Light' (the scene's own world kept: Off puts it back).  The Background Colour / Picture of
the Render tab works on it like on any world (it is put back on the new world when it was on).
"""
import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty

GROUP = 'MCH Creature Light'
GROUP_VERSION = 1
WORLD = 'MCH Creature Light'
TAG = 'mch_clight'                  # world / group / floor tag
PREV_KEY = 'mch_clight_prev'        # scene: the world before (name)
FLOOR = 'MCH Creature Floor'
FLOOR_TAG = 'mch_creature_floor'
FLOOR_MAT = 'MCH Fade Floor'
SLOTS = 4
PAGE = 9
TARGET = 2.6                        # the brightest side of a white part (irradiance) for every set-up
INNER = 0.45                        # a light is full inside INNER x its size, fades out to its size (smooth)

W = (1.0, 1.0, 1.0)
WARM = (1.0, 0.9, 0.78)
COOL = (0.8, 0.88, 1.0)


def _g(v):
    return (v, v, v)


# (ident, label, sky top, horizon, ground, level, [(azimuth, elevation, size, colour, power)], hint)
#   azimuth: 0 = in front of the model (-Y, where the front view looks from), + = to its left as seen (+X)
#   size: the light's half-angle (degrees);  power: what it adds to a white part facing it (before levelling)
PRESETS = (
    ('soft_studio', 'Soft Studio', _g(0.22), _g(0.16), _g(0.06), 1.0,
     [(-40, 35, 35, (1.0, 0.97, 0.93), 1.6), (55, 15, 45, (0.9, 0.95, 1.0), 0.45), (160, 30, 25, W, 0.9)],
     'A big key, a soft fill, a rim - the everyday look'),
    ('turntable', 'Neutral Turntable', _g(0.3), _g(0.25), _g(0.1), 1.0,
     [(0, 50, 55, W, 0.9), (180, 35, 40, W, 0.6)], 'Even, almost shadowless - the textures as they are'),
    ('overcast', 'Overcast', (0.42, 0.44, 0.47), (0.3, 0.31, 0.33), (0.08, 0.08, 0.075), 1.0,
     [(0, 80, 50, (0.95, 0.97, 1.0), 0.6)], 'A grey sky, light from above'),
    ('window', 'Window Light', _g(0.12), _g(0.1), (0.045, 0.04, 0.035), 1.0,
     [(-75, 20, 30, (0.95, 0.97, 1.0), 2.2), (90, -5, 50, (1.0, 0.92, 0.82), 0.35)],
     'One big window at the side, a warm bounce'),
    ('top_softbox', 'Top Softbox', _g(0.12), _g(0.1), _g(0.035), 1.0,
     [(0, 75, 40, W, 2.0), (0, 10, 50, W, 0.35)], 'A softbox overhead, a little from the front'),
    ('three_point', 'Three Point Soft', _g(0.14), _g(0.11), _g(0.04), 1.0,
     [(-45, 30, 28, (1.0, 0.95, 0.88), 1.7), (50, 10, 40, (0.85, 0.92, 1.0), 0.55), (150, 35, 22, W, 1.2),
      (-150, 35, 22, W, 0.8)], 'Key, fill and two rims'),
    ('warm_cool', 'Warm Key Cool Fill', (0.12, 0.14, 0.18), (0.12, 0.11, 0.1), (0.05, 0.04, 0.035), 1.0,
     [(-40, 30, 30, (1.0, 0.8, 0.6), 1.7), (60, 10, 45, (0.55, 0.7, 1.0), 0.7), (170, 30, 25, (0.7, 0.85, 1.0), 1.0)],
     'Warm light, cool shadows'),
    ('museum', 'Museum', (0.18, 0.17, 0.16), (0.12, 0.11, 0.1), _g(0.04), 1.0,
     [(-25, 60, 25, (1.0, 0.9, 0.78), 1.8), (30, 55, 25, (1.0, 0.9, 0.78), 1.1)], 'Two warm spots from above'),
    ('forest', 'Forest Shade', (0.12, 0.2, 0.12), (0.1, 0.14, 0.08), (0.04, 0.05, 0.025), 1.0,
     [(-30, 55, 22, (1.0, 0.95, 0.8), 1.4), (90, 40, 40, (0.6, 0.85, 0.55), 0.4)], 'Under trees, green bounce'),
    ('desert', 'Desert Sun', (0.25, 0.32, 0.45), (0.38, 0.3, 0.22), (0.25, 0.17, 0.1), 1.0,
     [(-50, 45, 15, (1.0, 0.9, 0.75), 2.2), (0, -30, 60, (1.0, 0.75, 0.5), 0.4)], 'Hot sun, sand bouncing up'),
    ('arctic', 'Arctic', (0.3, 0.38, 0.5), (0.35, 0.4, 0.48), (0.3, 0.33, 0.38), 1.0,
     [(-60, 25, 25, (0.95, 0.97, 1.0), 1.3)], 'Cold, bright, blue shadows'),
    ('twilight', 'Twilight', (0.06, 0.06, 0.16), (0.35, 0.17, 0.12), (0.04, 0.03, 0.04), 0.9,
     [(150, 8, 45, (1.0, 0.55, 0.3), 1.4), (-60, 40, 40, (0.5, 0.5, 1.0), 0.5)], 'Sunset behind, blue sky in front'),
    ('moonlight', 'Moonlight', (0.03, 0.05, 0.1), (0.04, 0.05, 0.08), _g(0.01), 0.6,
     [(-40, 40, 20, (0.65, 0.78, 1.0), 1.4), (60, 10, 50, (0.3, 0.4, 0.6), 0.25)], 'Night, a blue moon'),
    ('torch', 'Cave Torch', (0.02, 0.018, 0.016), (0.03, 0.025, 0.02), (0.02, 0.014, 0.01), 0.75,
     [(-70, 5, 22, (1.0, 0.6, 0.3), 2.0), (100, 20, 50, (0.4, 0.5, 0.7), 0.25)], 'A torch at the side, a dark cave'),
    ('deep_sea', 'Deep Sea', (0.03, 0.18, 0.25), (0.02, 0.08, 0.12), (0.005, 0.02, 0.03), 0.8,
     [(0, 80, 30, (0.5, 0.9, 1.0), 1.6), (170, 20, 30, (0.3, 0.8, 0.9), 0.6)], 'Light from the surface far above'),
    ('volcanic', 'Volcanic', (0.05, 0.025, 0.025), (0.12, 0.04, 0.015), (0.4, 0.1, 0.02), 0.9,
     [(0, -50, 45, (1.0, 0.35, 0.08), 1.4), (-40, 35, 30, (1.0, 0.85, 0.7), 0.8)], 'Lava glowing from below'),
    ('golden_hour', 'Golden Hour', (0.2, 0.25, 0.38), (0.45, 0.3, 0.18), (0.1, 0.07, 0.05), 1.0,
     [(-70, 12, 18, (1.0, 0.72, 0.42), 2.2), (40, 60, 50, (0.6, 0.7, 1.0), 0.3)], 'Low warm sun'),
    ('morning_mist', 'Morning Mist', (0.38, 0.4, 0.42), _g(0.42), _g(0.15), 1.0,
     [(-50, 30, 50, (1.0, 0.97, 0.92), 0.8)], 'Hazy and soft all round'),
    ('jungle', 'Jungle Canopy', (0.1, 0.22, 0.1), (0.08, 0.15, 0.06), (0.03, 0.04, 0.02), 1.0,
     [(-20, 65, 18, (1.0, 0.95, 0.75), 1.5), (120, 10, 50, (0.4, 0.8, 0.3), 0.4)], 'Sun through leaves'),
    ('swamp', 'Swamp', (0.14, 0.16, 0.12), (0.16, 0.17, 0.12), (0.05, 0.06, 0.03), 0.9,
     [(-50, 35, 40, (0.85, 0.9, 0.7), 1.1), (160, 20, 30, (0.7, 0.9, 0.6), 0.6)], 'Murky green-yellow'),
    ('clean_white', 'Clean White', _g(0.6), _g(0.55), _g(0.35), 1.15,
     [(-30, 40, 50, W, 1.0)], 'High key, bright all round'),
    ('low_key', 'Low Key Drama', _g(0.02), _g(0.02), _g(0.01), 0.9,
     [(-60, 35, 22, (1.0, 0.96, 0.9), 2.4), (150, 25, 18, W, 1.6), (60, 0, 50, W, 0.15)],
     'Dark, one key and a strong rim'),
    ('clamshell', 'Clam Shell', _g(0.1), _g(0.08), _g(0.06), 1.0,
     [(0, 55, 35, W, 1.6), (0, -25, 40, W, 0.7), (180, 30, 30, W, 0.6)], 'Light above and below the front'),
    ('butterfly', 'Butterfly', _g(0.1), _g(0.08), _g(0.04), 1.0,
     [(0, 45, 30, (1.0, 0.97, 0.93), 1.9), (140, 20, 25, W, 0.7), (-140, 20, 25, W, 0.7)],
     'Key straight above the front, two rims'),
    ('split', 'Split Side', _g(0.06), _g(0.05), _g(0.02), 0.9,
     [(-90, 15, 30, (1.0, 0.96, 0.9), 2.0), (90, 10, 50, (0.8, 0.85, 1.0), 0.25)], 'Half lit, half in shade'),
    ('toxic_lab', 'Toxic Lab', (0.05, 0.07, 0.05), (0.05, 0.08, 0.05), (0.02, 0.03, 0.02), 0.9,
     [(-40, 40, 30, (0.9, 1.0, 0.9), 1.3), (150, 20, 22, (0.4, 1.0, 0.3), 1.4), (-150, 20, 22, (0.4, 1.0, 0.3), 1.0)],
     'Green rims'),
    ('alien_dusk', 'Alien Dusk', (0.12, 0.04, 0.16), (0.05, 0.12, 0.15), (0.03, 0.02, 0.04), 0.9,
     [(-50, 30, 30, (1.0, 0.4, 0.9), 1.3), (140, 25, 25, (0.3, 0.9, 1.0), 1.4)], 'Magenta key, cyan rim'),
    ('biolum', 'Bioluminescent', (0.01, 0.02, 0.04), (0.01, 0.03, 0.05), _g(0.005), 0.7,
     [(160, 10, 25, (0.2, 0.9, 1.0), 1.5), (-160, 10, 25, (0.3, 0.6, 1.0), 1.2), (0, 20, 50, (0.3, 0.5, 0.8), 0.35)],
     'Dark water, glowing edges'),
    ('snow', 'Snow Field', (0.3, 0.35, 0.45), (0.4, 0.42, 0.45), (0.55, 0.57, 0.6), 1.05,
     [(-45, 30, 25, (1.0, 0.98, 0.95), 1.2)], 'White ground lighting from below'),
    ('stage', 'Stage Spot', _g(0.025), _g(0.025), _g(0.04), 0.85,
     [(-10, 60, 15, (1.0, 0.95, 0.85), 2.4), (180, 40, 20, (0.8, 0.85, 1.0), 0.9), (0, 5, 50, W, 0.2)],
     'A spot from above in the dark'),
)
BY_ID = {p[0]: p for p in PRESETS}
ORDER = [p[0] for p in PRESETS]


def _dir(az, el):
    a, e = math.radians(az), math.radians(el)
    return (math.cos(e) * math.sin(a), -math.cos(e) * math.cos(a), math.sin(e))


def _cones(size, soft):
    """(cos of the outer edge, cos of the full inside, solid angle) of a light of half-angle ``size`` x ``soft``."""
    out = min(math.radians(size) * soft, math.radians(85.0))
    inn = out * INNER
    co, ci = math.cos(out), math.cos(inn)
    return co, ci, 2.0 * math.pi * (1.0 - 0.5 * (co + ci))        # (the smooth edge averages one half)


_GAIN = {}


def _sky_of(z, top, hor, gnd):
    """The sky colour along direction height ``z`` (numpy), like the nodes."""
    import numpy as np
    def ss(e0, e1, x):
        t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
        return t * t * (3 - 2 * t)
    up = ss(0.0, 0.7, z)[:, None]
    dn = ss(0.0, -0.35, z)[:, None]
    c = np.array(hor)[None] * (1 - up) + np.array(top)[None] * up
    return c * (1 - dn) + np.array(gnd)[None] * dn


def gain(ident):
    """The factor that brings set-up ``ident`` to TARGET on the brightest side of a white part (cached)."""
    if ident in _GAIN:
        return _GAIN[ident]
    import numpy as np
    p = BY_ID[ident]
    n = 3000
    i = np.arange(n) + 0.5
    z = 1 - 2 * i / n
    r = np.sqrt(np.maximum(0, 1 - z * z))
    phi = i * math.pi * (3 - math.sqrt(5))
    d = np.stack([r * np.cos(phi), r * np.sin(phi), z], 1)          # directions over the sphere
    rad = _sky_of(z, p[2], p[3], p[4]).mean(1)
    for az, el, size, col, power in p[6]:
        co, ci, om = _cones(size, 1.0)
        L = np.array(_dir(az, el))
        t = np.clip((d @ L - co) / (ci - co), 0, 1)
        rad = rad + t * t * t * (t * (t * 6 - 15) + 10) * (power / om) * float(np.mean(col))
    normals = d[::10]
    E = (np.maximum(0, normals @ d.T) * rad[None]).sum(1) * (4 * math.pi / n)
    g = TARGET * p[5] / max(float(E.max()), 1e-6)
    _GAIN[ident] = g
    return g


# ---- the node group ----------------------------------------------------------------------------------------------

def _sock(ng, name, kind, io='INPUT', default=None, lo=None, hi=None):
    s = ng.interface.new_socket(name=name, in_out=io, socket_type=kind)
    if default is not None:
        try:
            s.default_value = default
        except (AttributeError, TypeError, ValueError):
            pass
    if lo is not None:
        s.min_value, s.max_value = lo, hi
    return s


def _build_group():
    ng = bpy.data.node_groups.new(GROUP, 'ShaderNodeTree')
    ng[TAG] = GROUP_VERSION
    _sock(ng, 'Color', 'NodeSocketColor', 'OUTPUT')
    _sock(ng, 'Sky Top', 'NodeSocketColor', default=(0.2, 0.2, 0.2, 1))
    _sock(ng, 'Horizon', 'NodeSocketColor', default=(0.15, 0.15, 0.15, 1))
    _sock(ng, 'Ground', 'NodeSocketColor', default=(0.05, 0.05, 0.05, 1))
    _sock(ng, 'Sky Fill', 'NodeSocketFloat', default=1.0, lo=0.0, hi=100.0)
    _sock(ng, 'Light Emission', 'NodeSocketFloat', default=1.0, lo=0.0, hi=100.0)
    _sock(ng, 'Hide Lights From Camera', 'NodeSocketFloat', default=1.0, lo=0.0, hi=1.0)
    _sock(ng, 'Hue', 'NodeSocketFloat', default=0.5, lo=0.0, hi=1.0)
    _sock(ng, 'Saturation', 'NodeSocketFloat', default=1.0, lo=0.0, hi=2.0)
    for i in range(1, SLOTS + 1):
        _sock(ng, f'Light {i} Direction', 'NodeSocketVector', default=(0, -1, 0))
        _sock(ng, f'Light {i} Color', 'NodeSocketColor', default=(1, 1, 1, 1))
        _sock(ng, f'Light {i} Radiance', 'NodeSocketFloat', default=0.0, lo=0.0, hi=10000.0)
        _sock(ng, f'Light {i} Edge', 'NodeSocketFloat', default=0.9, lo=-1.0, hi=1.0)
        _sock(ng, f'Light {i} Inside', 'NodeSocketFloat', default=0.98, lo=-1.0, hi=1.0)
    N, L = ng.nodes, ng.links
    gi = N.new('NodeGroupInput')
    gi.location = (-1400, 0)
    go = N.new('NodeGroupOutput')
    go.location = (900, 0)
    tc = N.new('ShaderNodeTexCoord')                 # (in a world: Generated = the direction looked along)
    tc.location = (-1200, 400)
    sep = N.new('ShaderNodeSeparateXYZ')
    sep.location = (-1000, 500)
    L.new(tc.outputs['Generated'], sep.inputs[0])

    def mrange(x, a, b, loc, interp='SMOOTHSTEP'):
        m = N.new('ShaderNodeMapRange')
        m.interpolation_type = interp
        m.location = loc
        L.new(x, m.inputs['Value'])
        for idx, v in ((1, a), (2, b)):
            if isinstance(v, (int, float)):
                m.inputs[idx].default_value = v
            else:
                L.new(v, m.inputs[idx])
        return m

    def mix(a, b, fac, loc):
        m = N.new('ShaderNodeMix')
        m.data_type = 'RGBA'
        m.location = loc
        col = [x for x in m.inputs if x.type == 'RGBA']
        fac_in = next(x for x in m.inputs if x.name == 'Factor' and x.type == 'VALUE')
        L.new(fac, fac_in)
        L.new(a, col[0])
        L.new(b, col[1])
        return m

    def mix_out(m):
        return next(x for x in m.outputs if x.type == 'RGBA')

    up = mrange(sep.outputs['Z'], 0.0, 0.7, (-800, 600))
    dn = mrange(sep.outputs['Z'], 0.0, -0.35, (-800, 350))
    m1 = mix(gi.outputs['Horizon'], gi.outputs['Sky Top'], up.outputs['Result'], (-550, 600))
    m2 = mix(mix_out(m1), gi.outputs['Ground'], dn.outputs['Result'], (-350, 500))
    sky = N.new('ShaderNodeVectorMath')
    sky.operation = 'SCALE'
    sky.location = (-150, 500)
    L.new(mix_out(m2), sky.inputs[0])
    L.new(gi.outputs['Sky Fill'], sky.inputs['Scale'])
    total = None
    for i in range(1, SLOTS + 1):
        y = 100 - (i - 1) * 260
        dot = N.new('ShaderNodeVectorMath')
        dot.operation = 'DOT_PRODUCT'
        dot.location = (-1000, y)
        L.new(tc.outputs['Generated'], dot.inputs[0])
        L.new(gi.outputs[f'Light {i} Direction'], dot.inputs[1])
        m = mrange(dot.outputs['Value'], gi.outputs[f'Light {i} Edge'], gi.outputs[f'Light {i} Inside'],
                   (-800, y), 'SMOOTHERSTEP')
        k = N.new('ShaderNodeMath')
        k.operation = 'MULTIPLY'
        k.location = (-600, y)
        L.new(m.outputs['Result'], k.inputs[0])
        L.new(gi.outputs[f'Light {i} Radiance'], k.inputs[1])
        c = N.new('ShaderNodeVectorMath')
        c.operation = 'SCALE'
        c.location = (-420, y)
        L.new(gi.outputs[f'Light {i} Color'], c.inputs[0])
        L.new(k.outputs[0], c.inputs['Scale'])
        if total is None:
            total = c
        else:
            add = N.new('ShaderNodeVectorMath')
            add.operation = 'ADD'
            add.location = (-240, y)
            L.new(total.outputs[0], add.inputs[0])
            L.new(c.outputs[0], add.inputs[1])
            total = add
    lp = N.new('ShaderNodeLightPath')                # (the camera: the lights hidden from it, when asked)
    lp.location = (-240, -900)
    hide = N.new('ShaderNodeMath')
    hide.operation = 'MULTIPLY'
    hide.location = (-60, -800)
    L.new(lp.outputs['Is Camera Ray'], hide.inputs[0])
    L.new(gi.outputs['Hide Lights From Camera'], hide.inputs[1])
    keep = N.new('ShaderNodeMath')
    keep.operation = 'SUBTRACT'
    keep.location = (100, -800)
    keep.inputs[0].default_value = 1.0
    L.new(hide.outputs[0], keep.inputs[1])
    em = N.new('ShaderNodeMath')
    em.operation = 'MULTIPLY'
    em.location = (260, -700)
    L.new(keep.outputs[0], em.inputs[0])
    L.new(gi.outputs['Light Emission'], em.inputs[1])
    lights = N.new('ShaderNodeVectorMath')
    lights.operation = 'SCALE'
    lights.location = (260, -300)
    L.new(total.outputs[0], lights.inputs[0])
    L.new(em.outputs[0], lights.inputs['Scale'])
    both = N.new('ShaderNodeVectorMath')
    both.operation = 'ADD'
    both.location = (440, 200)
    L.new(sky.outputs[0], both.inputs[0])
    L.new(lights.outputs[0], both.inputs[1])
    hs = N.new('ShaderNodeHueSaturation')
    hs.location = (640, 100)
    L.new(both.outputs[0], hs.inputs['Color'])
    L.new(gi.outputs['Hue'], hs.inputs['Hue'])
    L.new(gi.outputs['Saturation'], hs.inputs['Saturation'])
    L.new(hs.outputs['Color'], go.inputs['Color'])
    return ng


def group():
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None and ng.get(TAG) != GROUP_VERSION:
        ng.name = GROUP + ' (old)'
        ng = None
    return ng if ng is not None else _build_group()


# ---- the world ---------------------------------------------------------------------------------------------------

def our_world(scene):
    w = getattr(scene, 'world', None)
    return w if w is not None and w.get(TAG) else None


def on(scene):
    return our_world(scene) is not None


def _group_node(w):
    nt = getattr(w, 'node_tree', None)
    return nt.nodes.get(GROUP) if nt is not None else None


def _new_world():
    w = bpy.data.worlds.new(WORLD)
    w[TAG] = 1
    try:
        w.use_nodes = True
    except AttributeError:
        pass
    nt = w.node_tree
    nt.nodes.clear()
    gn = nt.nodes.new('ShaderNodeGroup')
    gn.node_tree = group()
    gn.name = gn.label = GROUP
    gn.location = (-300, 0)
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.name = 'MCH Creature Light Strength'
    bg.location = (0, 0)
    out = nt.nodes.new('ShaderNodeOutputWorld')
    out.location = (250, 0)
    nt.links.new(gn.outputs['Color'], bg.inputs['Color'])
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    return w


def _world_for(scene):
    """Our world for the scene (a new one when the scene's world is not ours; its group brought up to date)."""
    w = our_world(scene)
    if w is None:
        w = next((x for x in bpy.data.worlds if x.get(TAG) and x.users == 0), None) or _new_world()
        prev = scene.world
        scene[PREV_KEY] = prev.name if prev is not None else ''
        scene.world = w
    gn = _group_node(w)
    if gn is None:                                   # (its nodes taken apart: a fresh one)
        w = _new_world()
        scene.world = w
        gn = _group_node(w)
    if gn.node_tree is None or gn.node_tree.get(TAG) != GROUP_VERSION:
        gn.node_tree = group()
    return w


def sync(scene):
    """The settings into our world's nodes (nothing when the scene's world is not ours)."""
    st = settings(scene)
    w = our_world(scene)
    if st is None or w is None:
        return
    gn = _group_node(w)
    if gn is None or gn.node_tree is None:
        return
    p = BY_ID.get(st.preset) or PRESETS[0]
    g = gain(p[0])
    ins = gn.inputs
    ins['Sky Top'].default_value = (*[c * g for c in p[2]], 1.0)
    ins['Horizon'].default_value = (*[c * g for c in p[3]], 1.0)
    ins['Ground'].default_value = (*[c * g for c in p[4]], 1.0)
    ins['Sky Fill'].default_value = st.fill
    ins['Light Emission'].default_value = st.emission
    ins['Hide Lights From Camera'].default_value = 0.0 if st.show_lights else 1.0
    ins['Hue'].default_value = 0.5 + st.hue
    ins['Saturation'].default_value = st.saturation
    rot = st.rotation
    for i in range(SLOTS):
        n = i + 1
        if i < len(p[6]):
            az, el, size, col, power = p[6][i]
            co, ci, om = _cones(size, st.softness)
            d = _dir(az, el)
            cr, sr = math.cos(rot), math.sin(rot)
            d = (d[0] * cr - d[1] * sr, d[0] * sr + d[1] * cr, d[2])
            ins[f'Light {n} Direction'].default_value = d
            ins[f'Light {n} Color'].default_value = (*col, 1.0)
            ins[f'Light {n} Radiance'].default_value = power * g / om
            ins[f'Light {n} Edge'].default_value = co
            ins[f'Light {n} Inside'].default_value = ci
        else:
            ins[f'Light {n} Radiance'].default_value = 0.0
    bg = w.node_tree.nodes.get('MCH Creature Light Strength')
    if bg is not None:
        bg.inputs['Strength'].default_value = 2.0 ** st.exposure
    w.color = tuple(c * g * 2.0 ** st.exposure for c in p[3])     # (Solid view's world colour: the horizon)


def _bg_was_on(scene):
    try:
        from . import bg_color
        return bg_color.on(scene)
    except Exception:
        return False


def _bg_back(scene, was):
    if not was:
        return
    try:
        from . import bg_color
        bg_color.apply(scene)
    except Exception as ex:
        print('[MECHA LAB] Creature Light: background colour', ex)


def apply(scene, ident=None):
    """Creature Light on (set-up ``ident``, or the one chosen)."""
    st = settings(scene)
    if ident and ident in BY_ID and st.preset != ident:
        st['preset'] = ORDER.index(ident)            # (no update: synced once below)
    was = _bg_was_on(scene)
    already = on(scene)
    _world_for(scene)
    sync(scene)
    if not already:
        _bg_back(scene, was)
    return f'Creature Light: {BY_ID[st.preset][1]}'


def off(scene):
    """Back to the scene's own world (the one before Creature Light)."""
    if not on(scene):
        return 'Creature Light is off'
    was = _bg_was_on(scene)
    name = scene.get(PREV_KEY, '')
    prev = bpy.data.worlds.get(name) if name else None
    ours = scene.world
    scene.world = prev
    if ours is not None and ours.users == 0:
        bpy.data.worlds.remove(ours)
    if PREV_KEY in scene:
        del scene[PREV_KEY]
    if prev is not None:
        _bg_back(scene, was)
    return 'Creature Light off: your world back' if prev is not None else 'Creature Light off (no world before)'


# ---- the floor ---------------------------------------------------------------------------------------------------

def floor_object(scene):
    for ob in scene.objects:
        if ob.get(FLOOR_TAG):
            return ob
    return None


def _parts_box(context):
    """(min x, min y, min z, max x, max y) of the visible parts (the floor left out), or None."""
    dg = context.evaluated_depsgraph_get()
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    from mathutils import Vector
    for ob in context.scene.objects:
        if ob.get(FLOOR_TAG) or ob.type not in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'CURVES', 'POINTCLOUD',
                                                'VOLUME'}:
            continue
        try:
            if not ob.visible_get() or ob.hide_render:
                continue
            ev = ob.evaluated_get(dg)
            mw = ev.matrix_world
            for c in ev.bound_box:
                p = mw @ Vector(c)
                for k in range(3):
                    lo[k] = min(lo[k], p[k])
                    hi[k] = max(hi[k], p[k])
        except (ReferenceError, RuntimeError):
            continue
    if lo[0] == math.inf:
        return None
    return lo, hi


def _disc_mesh(name, n=64):
    me = bpy.data.meshes.new(name)
    vs = [(math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n), 0.0) for i in range(n)]
    me.from_pydata(vs, [], [list(range(n))])
    me.update()
    return me


def _fade_material():
    mat = bpy.data.materials.get(FLOOR_MAT)
    if mat is not None and mat.get(TAG) == GROUP_VERSION:
        return mat
    if mat is not None:
        mat.name = FLOOR_MAT + ' (old)'
    mat = bpy.data.materials.new(FLOOR_MAT)
    mat[TAG] = GROUP_VERSION
    try:
        mat.use_nodes = True
    except AttributeError:
        pass
    try:
        mat.surface_render_method = 'BLENDED'        # (EEVEE: a smooth fade, not dithered)
    except (AttributeError, TypeError):
        pass
    nt = mat.node_tree
    nt.nodes.clear()
    N, L = nt.nodes, nt.links
    tc = N.new('ShaderNodeTexCoord')
    tc.location = (-900, 200)
    ln = N.new('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    ln.location = (-700, 200)
    L.new(tc.outputs['Object'], ln.inputs[0])
    mr = N.new('ShaderNodeMapRange')
    mr.name = 'MCH Fade'
    mr.interpolation_type = 'SMOOTHERSTEP'
    mr.location = (-500, 200)
    L.new(ln.outputs['Value'], mr.inputs['Value'])
    mr.inputs['From Max'].default_value = 1.0
    mr.inputs['To Min'].default_value = 1.0
    mr.inputs['To Max'].default_value = 0.0
    op = N.new('ShaderNodeMath')
    op.name = 'MCH Opacity'
    op.operation = 'MULTIPLY'
    op.location = (-300, 200)
    L.new(mr.outputs['Result'], op.inputs[0])
    pb = N.new('ShaderNodeBsdfPrincipled')
    pb.name = 'MCH Floor'
    pb.location = (-400, -150)
    pb.inputs['Roughness'].default_value = 0.8
    for key in ('Specular IOR Level', 'Specular'):
        if key in pb.inputs:
            pb.inputs[key].default_value = 0.2
            break
    tr = N.new('ShaderNodeBsdfTransparent')
    tr.location = (-150, 50)
    mx = N.new('ShaderNodeMixShader')
    mx.location = (100, 100)
    L.new(op.outputs[0], mx.inputs['Fac'])
    L.new(tr.outputs[0], mx.inputs[1])
    L.new(pb.outputs[0], mx.inputs[2])
    out = N.new('ShaderNodeOutputMaterial')
    out.location = (300, 100)
    L.new(mx.outputs[0], out.inputs['Surface'])
    return mat


def _floor_sync(scene):
    st = settings(scene)
    ob = floor_object(scene)
    if st is None or ob is None:
        return
    mat = ob.active_material
    if st.floor == 'FADE' and mat is not None and mat.node_tree is not None:
        nt = mat.node_tree
        pb, mr, op = nt.nodes.get('MCH Floor'), nt.nodes.get('MCH Fade'), nt.nodes.get('MCH Opacity')
        if pb is not None:
            pb.inputs['Base Color'].default_value = (*st.floor_color, 1.0)
        if mr is not None:
            mr.inputs['From Min'].default_value = max(0.0, 1.0 - st.floor_edge)
        if op is not None:
            op.inputs[1].default_value = st.floor_opacity
        mat.diffuse_color = (*st.floor_color, 1.0)


def fit_floor(context):
    """The floor under the lowest visible part, centred under the parts, ``floor_size`` x their width."""
    sc = context.scene
    st = settings(sc)
    ob = floor_object(sc)
    if ob is None or st is None:
        return False
    box = _parts_box(context)
    if box is None:
        lo, hi = (-1.0, -1.0, 0.0), (1.0, 1.0, 2.0)
    else:
        lo, hi = box
    cx, cy = (lo[0] + hi[0]) * 0.5, (lo[1] + hi[1]) * 0.5
    half = max(hi[0] - lo[0], hi[1] - lo[1], (hi[2] - lo[2]) * 0.5, 1e-3) * 0.5
    r = half * st.floor_size
    ob.location = (cx, cy, lo[2])
    ob.rotation_euler = (0.0, 0.0, 0.0)
    ob.scale = (r, r, 1.0)
    return True


def set_floor(context, kind):
    """The floor: OFF (removed), CATCHER (a Shadow Catcher disc), FADE (the fading disc)."""
    sc = context.scene
    ob = floor_object(sc)
    if kind == 'OFF':
        if ob is not None:
            me = ob.data
            bpy.data.objects.remove(ob)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
        return 'Floor off'
    new = ob is None
    if new:
        ob = bpy.data.objects.new(FLOOR, _disc_mesh(FLOOR))
        ob[FLOOR_TAG] = 1
        sc.collection.objects.link(ob)
    try:
        ob.visible_shadow = False            # (it never shades the parts: lights from below still reach them)
    except AttributeError:
        pass
    ob.hide_select = True                    # (not picked by the tools / clicks)
    if kind == 'CATCHER':
        ob.is_shadow_catcher = True
        ob.data.materials.clear()
    else:
        ob.is_shadow_catcher = False
        mat = _fade_material()
        ob.data.materials.clear()
        ob.data.materials.append(mat)
    if new:
        fit_floor(context)
    _floor_sync(sc)
    if kind == 'CATCHER':
        if sc.render.engine != 'CYCLES':
            return 'Shadow Catcher floor (a Cycles feature: Rendered view / render in Cycles)'
        return 'Shadow Catcher floor: only the shadows show on the background'
    return 'Fade Floor: a soft floor fading out to the edge'


# ---- the settings ------------------------------------------------------------------------------------------------

def _upd(self, context):
    sync(context.scene)


def _upd_preset(self, context):
    if on(context.scene):
        sync(context.scene)
    self.page = ORDER.index(self.preset) // PAGE


def _upd_floor(self, context):
    set_floor(context, self.floor)


def _upd_floor_look(self, context):
    _floor_sync(context.scene)


def _upd_floor_size(self, context):
    fit_floor(context)


class MCH_PG_CreatureLight(bpy.types.PropertyGroup):
    preset: EnumProperty(name='Set-up', default=0, update=_upd_preset,
                         items=[(p[0], p[1], p[7], i) for i, p in enumerate(PRESETS)],
                         description='The creature lighting (soft lights and a sky made in the world - no files)')
    exposure: FloatProperty(name='Exposure', default=0.0, min=-6.0, max=6.0, soft_min=-3.0, soft_max=3.0, step=10,
                            update=_upd, description='Brighter / darker, in stops (the whole lighting)')
    emission: FloatProperty(name='Light Emission', default=1.0, min=0.0, max=10.0, soft_max=3.0, update=_upd,
                            description='The lights only (the bright patches) - the sky stays')
    fill: FloatProperty(name='Sky Fill', default=1.0, min=0.0, max=10.0, soft_max=3.0, update=_upd,
                        description='The sky only (what fills the shadows) - more = flatter, the texture clearer')
    hue: FloatProperty(name='Hue', default=0.0, min=-0.5, max=0.5, step=1, update=_upd,
                       description='Turn the colours of the lighting round the colour wheel')
    saturation: FloatProperty(name='Saturation', default=1.0, min=0.0, max=2.0, update=_upd,
                              description='0 = grey light, 1 = as made, 2 = stronger colours')
    softness: FloatProperty(name='Softness', default=1.0, min=0.4, max=2.5, update=_upd,
                            description='Bigger lights: softer shadows and broader, quieter highlights (the same '
                                        'light put out)')
    rotation: FloatProperty(name='Rotation', default=0.0, subtype='ANGLE', min=-math.pi, max=math.pi, update=_upd,
                            description='The lights turned round the model')
    show_lights: BoolProperty(name='Lights Seen by Camera', default=False, update=_upd,
                              description='Off: the camera sees only the soft sky gradient behind the model (the '
                                          'lights still light it and show in reflections)')
    page: IntProperty(name='Page', default=0, min=0)
    floor: EnumProperty(name='Floor', default='OFF', update=_upd_floor, items=[
        ('OFF', 'No Floor', 'No floor'),
        ('CATCHER', 'Shadow Catcher', 'A disc that shows only the shadows on the background (Cycles)'),
        ('FADE', 'Fade Floor', 'A soft floor whose edge fades to transparent in a circle (no hard edge)')])
    floor_color: FloatVectorProperty(name='Floor Colour', subtype='COLOR', size=3, min=0.0, max=1.0,
                                     default=(0.32, 0.32, 0.32), update=_upd_floor_look)
    floor_size: FloatProperty(name='Floor Size', default=2.2, min=1.0, max=10.0, update=_upd_floor_size,
                              description='The floor\'s size, times the width of the parts')
    floor_edge: FloatProperty(name='Edge Fade', default=0.7, min=0.05, max=1.0, update=_upd_floor_look,
                              description='How much of the disc fades out (1 = from the centre to the edge)')
    floor_opacity: FloatProperty(name='Floor Opacity', default=1.0, min=0.0, max=1.0, update=_upd_floor_look,
                                 description='How solid the centre of the floor is')


def settings(scene_or_context):
    sc = getattr(scene_or_context, 'scene', scene_or_context)
    return getattr(sc, 'mch_clight', None)


# ---- the operators -----------------------------------------------------------------------------------------------

class MCH_OT_creature_light(bpy.types.Operator):
    """Creature Light: soft lighting for creatures made in the world (no files) - the base texture reads, the
    highlights stay quiet.  Off: your world back"""
    bl_idname = 'mch.creature_light'
    bl_label = 'Creature Light'
    bl_options = {'REGISTER', 'UNDO'}
    action: EnumProperty(items=[('SET', 'Set', ''), ('TOGGLE', 'On / Off', ''), ('OFF', 'Off', ''),
                                ('STEP', 'Next', ''), ('PAGE', 'Page', ''), ('RESET', 'Reset', '')],
                         default='SET', options={'SKIP_SAVE'})
    ident: bpy.props.StringProperty(default='', options={'SKIP_SAVE'})
    step: IntProperty(default=1, options={'SKIP_SAVE'})

    def execute(self, context):
        sc = context.scene
        st = settings(sc)
        if st is None:
            return {'CANCELLED'}
        if self.action == 'OFF' or (self.action == 'TOGGLE' and on(sc)):
            msg = off(sc)
        elif self.action == 'PAGE':
            pages = (len(PRESETS) + PAGE - 1) // PAGE
            st.page = (st.page + self.step) % pages
            return {'FINISHED'}
        elif self.action == 'RESET':
            for key in ('exposure', 'emission', 'fill', 'hue', 'saturation', 'softness', 'rotation'):
                st.property_unset(key)
            sync(sc)
            msg = 'Creature Light: the controls back to as made'
        elif self.action == 'STEP':
            i = (ORDER.index(st.preset) + self.step) % len(ORDER)
            msg = apply(sc, ORDER[i])
            st.page = i // PAGE
        else:
            msg = apply(sc, self.ident or st.preset)
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class MCH_OT_creature_floor(bpy.types.Operator):
    """The floor under the creature: Shadow Catcher (only the shadows, Cycles) or Fade Floor (a soft disc fading out
    at the edge); Fit: under the parts again"""
    bl_idname = 'mch.creature_floor'
    bl_label = 'Creature Floor'
    bl_options = {'REGISTER', 'UNDO'}
    kind: EnumProperty(items=[('OFF', 'No Floor', ''), ('CATCHER', 'Shadow Catcher', ''), ('FADE', 'Fade Floor', ''),
                              ('FIT', 'Fit to Model', '')], default='FIT', options={'SKIP_SAVE'})

    def execute(self, context):
        st = settings(context)
        if st is None:
            return {'CANCELLED'}
        if self.kind == 'FIT':
            if floor_object(context.scene) is None:
                self.report({'WARNING'}, 'No floor yet')
                return {'CANCELLED'}
            fit_floor(context)
            self.report({'INFO'}, 'Floor fitted under the parts')
            return {'FINISHED'}
        st['floor'] = ['OFF', 'CATCHER', 'FADE'].index(self.kind)
        self.report({'INFO'}, set_floor(context, self.kind))
        return {'FINISHED'}


def thumb_path(ident):
    import os
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons', 'creature_light', ident + '.png')


CLASSES = (MCH_PG_CreatureLight, MCH_OT_creature_light, MCH_OT_creature_floor)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_clight = bpy.props.PointerProperty(type=MCH_PG_CreatureLight)


def unregister():
    try:
        del bpy.types.Scene.mch_clight
    except AttributeError:
        pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
