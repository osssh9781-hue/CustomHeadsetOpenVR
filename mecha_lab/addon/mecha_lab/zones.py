"""0.24.95 Lasso Zones on Mech Shader parts (user: "메카닉 할 때 내가 라쏘로 그은 영역 색이랑 재질 다르게 할 수 있나?" ->
picked both ways):

* **Paint Zone** (the mesh as it is): the lasso, as drawn on the screen, becomes a mask picture projected from that view
  onto the part (a hidden projector Empty parented to it - the zone moves with the part).  Inside it the Mech Shader's
  paint is the zone's own: Color, Roughness, Metallic, Paint (coverage); Opacity.  The chips, primer, scratches, dirt,
  rust go over it as over any paint.  Only faces that faced the view when it was drawn, and only as deep as the part
  (Through: the back faces too).  No UVs, no new edges.
* **Split Zone** (a material of its own): edges cut into the mesh along the lasso (projected from the view), the faces
  inside get a second Mech material (a copy to change freely - any preset) - its own material slot, the boundary
  exact, a material ID for a game engine.
* the wear (user: "엣지 까짐이랑 긁힘 때 녹은 분리된 색이랑 다르게 넣고 싶은데 - 똑같이 넣는 거랑 다르게 넣는 거 옵션으로"):
  the same as the part's by default; a Paint Zone's **Own Wear** gives it its own Edge Wear, Scratches, Dirt (crevices,
  top, low) and Rust (starting from the part's); a Split Zone's material has **Same Wear as the part** - on: its chips,
  scratches, dirt, rust follow the part's material as it changes; off: set on its own
* the boundary line (user: "컬러 다르게 한 경계에 라인으로 경계 범프 생기게, 헤이트값 조절 가능하게"): along the zone's
  edge a line in the bump - Line Height (+ raised ridge, - engraved groove, 0 none) and Line Width (% of the part's
  size).  The mask picture is a signed distance field (how far each pixel is from the lasso outline, inside +), so the
  line sits exactly on the boundary at any width; a Split Zone has it on both sides of the cut (a line-only zone in
  the part's material and in the zone's, kept in step)
* 0.24.95 Creatures too (user: "크리쳐도 이 라쏘 영역으로 재질 다르게 - 크리쳐 버전은 외곽에 에어브러시 버전, 텍스쳐 버전"):
  a Paint Zone on a Creature Shader material - markings: its colour (or one of the creature colour textures, tinted)
  and roughness over the skin's, under the crevices, scars and conditions.  Its **Edge**: Hard, **Airbrush** (a soft
  sprayed fade out past the lasso, Edge Width far) or **Texture** (the outline pushed out by an organic pattern, 0 ..
  Edge Width, Edge Scale) - what was drawn stays painted; the Mech zones have the same Edge choice

The lasso: the **Lasso Zone tool** (0.24.95, ``perform`` - the shared lasso of the drawing tools: every shape,
Corners, Line, Sketch, Slow Line, Surface, Through, Targets of the top bar), switched on by Paint Zone / Split Zone on
the Mech / Creature page; the older ``MCH_OT_zone_lasso`` (drag = freehand; clicks = a polygon) is kept.
* a part with a live Mirror: each zone also looked up at the mirrored point (``mirror_maps``) - it shows on the other
  side too; a Split Zone drawn over the mirrored half cuts the faces it mirrors
* the boundary line: up to 40 % wide, +-10 high; wider than 0.6 %: as much deeper; a coarse distance field (the mask's
  green) for wide lines; a texture per zone (Mech: the base maps, creature: its colour maps)"""
from __future__ import annotations

import math

import bpy
import numpy as np
from bpy.app.handlers import persistent
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty, PointerProperty, StringProperty)
from mathutils import Matrix, Vector

from . import mech_shader as ms

PREFIX = 'mchz:'
MASK_MAX = 1024
LINE_GAIN = 3.0                   # (Line Height 1 = 3 x the Mech bump's unit: a line reads at its narrow width)
SDF_R = 96.0                      # (the distance field's reach, mask pixels: 0 / 1 in the picture = 96 px out / in;
#                                    a zone keeps the reach its picture was made with: ``reach``)
SDF_R2 = 480.0                    # (0.24.95 a second, coarse field in the picture's green: wide boundary lines - user:
#                                    "라인 범프 두께랑 깊이 훨씬 더 두껍게"; ``reach2``, 0 = a picture without it)
LINE_REF = 0.6                    # (a line wider than this (% of the part) gets as much deeper: it keeps its steepness)
ZONE_ID = 'mch_zone_id'           # (a part's number: its zones show on it only, not on other parts sharing the material)
SYM_KEY = 'mch_zone_sym'          # (the part's Mirror the zones' mirror copies were made for - see ``mirror_maps``)
CREATURE_PALETTE = ((0.06, 0.05, 0.04), (0.75, 0.68, 0.55), (0.45, 0.08, 0.05), (0.12, 0.2, 0.08), (0.85, 0.55, 0.1),
                    (0.2, 0.25, 0.4))
PALETTE = ((0.75, 0.42, 0.02), (0.06, 0.06, 0.07), (0.05, 0.16, 0.45), (0.6, 0.04, 0.03), (0.75, 0.75, 0.72),
           (0.12, 0.25, 0.08))


# -----------------------------------------------------------------------------
# the mask picture: the lasso filled (scanlines, 2 x supersampled)
# -----------------------------------------------------------------------------

def as_loops(pts):
    """The outline as closed loops: one polygon (a list of points) or several (a list of point lists - the Sketch's
    outlines and holes, Line's band ...), filled even-odd.  Loops of under 3 points are left out."""
    pts = list(pts)
    if pts and len(pts[0]) and not isinstance(pts[0][0], (int, float, np.integer, np.floating)):
        return [list(lp) for lp in pts if len(lp) >= 3]
    return [pts] if len(pts) >= 3 else []


def _edges(loops):
    """(a, b): every outline edge's two ends, (n, 2) arrays."""
    a = np.concatenate([np.asarray(lp, np.float64)[:, :2] for lp in loops])
    b = np.concatenate([np.roll(np.asarray(lp, np.float64)[:, :2], -1, axis=0) for lp in loops])
    return a, b


def fill_polygon(pts, w, h, ss=2):
    """(h, w) float32 0..1: the closed polygon ``pts`` (pixel x, y; y up - or several loops, even-odd) filled, its
    edge anti-aliased."""
    W, H = w * ss, h * ss
    out = np.zeros((H, W), np.float32)
    loops = as_loops(pts)
    if not loops:
        return out.reshape(h, ss, w, ss).mean(axis=(1, 3))
    a, b = _edges(loops)
    x0, y0, x1, y1 = a[:, 0] * ss, a[:, 1] * ss, b[:, 0] * ss, b[:, 1] * ss
    ys = np.arange(H) + 0.5
    lo, hi = np.minimum(y0, y1), np.maximum(y0, y1)
    for r in range(H):
        y = ys[r]
        m = (lo <= y) & (hi > y)
        if not m.any():
            continue
        xs = x0[m] + (y - y0[m]) * (x1[m] - x0[m]) / (y1[m] - y0[m])
        xs.sort()
        for a, b in zip(xs[0::2], xs[1::2]):
            ia, ib = int(max(0, math.ceil(a - 0.5))), int(min(W, math.floor(b - 0.5) + 1))
            if ib > ia:
                out[r, ia:ib] = 1.0
    return out.reshape(h, ss, w, ss).mean(axis=(1, 3))


def signed_distance(pts, w, h, reach=SDF_R):
    """(h, w) float32: each pixel's distance to the polygon's outline (pixels), + inside, - outside, cut at
    +-``reach`` (only the band round the outline is measured)."""
    inside = fill_polygon(pts, w, h) >= 0.5
    d = np.full((h, w), reach, np.float32)
    loops = as_loops(pts)
    if not loops:
        return -d
    for (ax, ay), (bx, by) in zip(*_edges(loops)):
        x0, x1 = int(max(0, math.floor(min(ax, bx) - reach))), int(min(w, math.ceil(max(ax, bx) + reach) + 1))
        y0, y1 = int(max(0, math.floor(min(ay, by) - reach))), int(min(h, math.ceil(max(ay, by) + reach) + 1))
        if x1 <= x0 or y1 <= y0:
            continue
        X, Y = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
        ex, ey = bx - ax, by - ay
        ll = ex * ex + ey * ey
        t = np.clip(((X - ax) * ex + (Y - ay) * ey) / ll, 0.0, 1.0) if ll > 0 else np.zeros_like(X)
        dd = np.hypot(X - (ax + t * ex), Y - (ay + t * ey)).astype(np.float32)
        np.minimum(d[y0:y1, x0:x1], dd, out=d[y0:y1, x0:x1])
    return np.where(inside, d, -d)


def _cs():
    from . import creature_shader as cs
    return cs


def zoned(mat):
    """A material the zones work on: a Mech Shader or a Creature Shader one."""
    return ms.is_mech(mat) or _cs().is_creature(mat)


def _upsample(a, w, h, f):
    """(h, w): the (smaller) picture ``a`` (1 / ``f`` of the size) scaled up, bilinear (pixel centres kept)."""
    ys = np.clip((np.arange(h) + 0.5) / f - 0.5, 0.0, a.shape[0] - 1.0)
    xs = np.clip((np.arange(w) + 0.5) / f - 0.5, 0.0, a.shape[1] - 1.0)
    y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
    y1, x1 = np.minimum(y0 + 1, a.shape[0] - 1), np.minimum(x0 + 1, a.shape[1] - 1)
    ty, tx = (ys - y0)[:, None], (xs - x0)[None, :]
    top = a[y0][:, x0] * (1 - tx) + a[y0][:, x1] * tx
    bot = a[y1][:, x0] * (1 - tx) + a[y1][:, x1] * tx
    return (top * (1 - ty) + bot * ty).astype(np.float32)


def mask_image(name, pts, rw, rh):
    """A packed grey image of the lasso over the whole view (``rw`` x ``rh`` pixels), at most MASK_MAX on its long
    side: a signed distance field, 0.5 on the outline, + SDF_R pixels inside = 1, outside = 0.  Image row 0 is the
    bottom (Blender's)."""
    s = min(1.0, MASK_MAX / float(max(rw, rh)))
    w, h = max(8, int(round(rw * s))), max(8, int(round(rh * s)))
    sx, sy = w / float(rw), h / float(rh)
    loops = [[(p[0] * sx, p[1] * sy) for p in lp] for lp in as_loops(pts)]
    sd = signed_distance(loops, w, h)
    a = np.clip(0.5 + sd / (2.0 * SDF_R), 0.0, 1.0)
    # (the coarse field: a quarter of the size, its reach SDF_R2, scaled back up - smooth, so that is enough)
    f = 4
    cw, ch = max(4, (w + f - 1) // f), max(4, (h + f - 1) // f)
    sdc = signed_distance([[(x / f, y / f) for x, y in lp] for lp in loops], cw, ch, reach=SDF_R2 / f) * f
    c = np.clip(0.5 + _upsample(sdc, w, h, f) / (2.0 * SDF_R2), 0.0, 1.0)
    img = bpy.data.images.new(name, w, h, alpha=False, float_buffer=False)
    img.colorspace_settings.name = 'Non-Color'          # (before the pixels: changing it re-makes a new image's buffer)
    px = np.empty((h, w, 4), np.float32)
    px[..., 0] = px[..., 2] = a
    px[..., 1] = c
    px[..., 3] = 1.0
    img.pixels.foreach_set(px.ravel())
    img.update()
    img.pack()
    return img


# -----------------------------------------------------------------------------
# the zones of a material: settings, and their nodes
# -----------------------------------------------------------------------------

def _update(self, context):
    mat = self.id_data
    sync(mat)


_TEX = []


def _tex_items():
    if not _TEX:
        _TEX[:] = [('FLAT', 'Flat', 'Its colour only')] + [(k, n, '') for k, n in _cs().CMAPS['color']]
    return _TEX


_MTEX = []


def _mech_tex_items():
    if not _MTEX:                               # (0.24.95 user: "존마다 베이스 컬러 텍스처도 선택할 수 있게")
        _MTEX[:] = [('FLAT', 'Flat', 'Its colour only')] + [(k, n, '') for k, n in ms.MAPS['base'][3] if k != 'FLAT']
    return _MTEX


def _tex_enum(self, context):
    mat = getattr(self, 'id_data', None)
    return _mech_tex_items() if ms.is_mech(mat) else _tex_items()


def tex_image(mat, ident):
    """The zone texture ``ident``: a Mech base map on a Mech material, a creature colour map on a creature's."""
    if ms.is_mech(mat):
        return ms.map_image('base', ident)
    return _cs().cmap_image('color', ident)


def _tex_update(self, context):
    """A texture picked: the colour to grey (the texture as it is) the first time; its nodes made anew."""
    mat = self.id_data
    if self.tex != 'FLAT' and self.get('mch_tex_tinted') is None:
        self['mch_tex_tinted'] = 1
        self.color = (0.5, 0.5, 0.5)
    relink(mat)


def _line_update(self, context):
    """A boundary line's sliders - and its twin's (a Split Zone's line lives in the part's material and the zone's)."""
    sync(self.id_data)
    for m, z in twins(self):
        if abs(z.line_height - self.line_height) > 1e-7:
            z.line_height = self.line_height
        if abs(z.line_width - self.line_width) > 1e-7:
            z.line_width = self.line_width


def twins(zone):
    """The other zones that share ``zone``'s projector: [(material, zone)]."""
    out = []
    if zone.projector is None:
        return out
    for m in bpy.data.materials:
        for z in getattr(m, 'mch_zones', ()):
            if z.projector == zone.projector and z.as_pointer() != zone.as_pointer():
                out.append((m, z))
    return out


def _own_update(self, context):
    """Own Wear turned on: it starts from the part's own amounts."""
    mat = self.id_data
    if self.own_wear and ms.is_mech(mat):
        st = getattr(mat, ms.KEY)
        for k in ms.ZONE_WEAR:
            setattr(self, k, getattr(st, k))
    sync(mat)


# the Split Zone material's "Same Wear": what it takes from the part's material
FOLLOW = ('edge_wear', 'scratches', 'rust', 'rust_scratch', 'dirt', 'dirt_top', 'dirt_low', 'dust', 'streaks',
          'primer', 'chip_follow', 'chip_reach', 'chip_soft', 'chip_breakup', 'chip_scale', 'chip_map', 'scratch_map',
          'rust_map', 'dirt_map', 'scratch_color', 'scratch_tint', 'rust_color', 'dirt_color', 'dust_color',
          'primer_color', 'edge_mat', 'edge_color', 'edge_metal', 'edge_rough', 'edge_polish', 'edge_map', 'h_scratch',
          'h_chip', 'h_rust', 'h_dirt')


def _copy_wear(src, dst):
    for k in FOLLOW:
        a = getattr(src, k)
        b = getattr(dst, k)
        same = tuple(a) == tuple(b) if hasattr(a, '__len__') and not isinstance(a, str) else a == b
        if not same:
            setattr(dst, k, a)


def follow(mat):
    """Same Wear: ``mat``'s wear copied to its Split Zone materials that follow it, and - when ``mat`` is such a zone
    itself (a preset put on it, a slider moved) - the part's wear back on it.  Only what differs."""
    if not ms.is_mech(mat):
        return
    parent = getattr(mat, 'mch_zone_parent', None)
    if getattr(mat, 'mch_zone_follow', False) and ms.is_mech(parent) and parent is not mat:
        _copy_wear(getattr(parent, ms.KEY), getattr(mat, ms.KEY))
    src = getattr(mat, ms.KEY)
    for m in bpy.data.materials:
        if m is mat or getattr(m, 'mch_zone_parent', None) != mat or not getattr(m, 'mch_zone_follow', False) \
                or not ms.is_mech(m):
            continue
        _copy_wear(src, getattr(m, ms.KEY))


def _follow_update(self, context):
    parent = getattr(self, 'mch_zone_parent', None)
    if self.mch_zone_follow and parent is not None:
        follow(parent)


class MCH_PG_Zone(bpy.types.PropertyGroup):
    name: StringProperty(default='Zone')
    projector: PointerProperty(type=bpy.types.Object)
    mask: PointerProperty(type=bpy.types.Image)
    win: FloatVectorProperty(size=16)                         # (the view's window matrix, row by row)
    eye: FloatVectorProperty(size=3)                          # (in the part's own space: where the view was ...)
    look: FloatVectorProperty(size=3, default=(0.0, 0.0, -1.0))   # (... and which way it looked)
    persp: BoolProperty(default=True)
    near: FloatProperty(default=0.0)
    far: FloatProperty(default=1e6)
    color: FloatVectorProperty(name='Color', subtype='COLOR', size=3, min=0.0, max=1.0, default=PALETTE[0],
                               update=_update, description='The zone\'s paint colour')
    roughness: FloatProperty(name='Roughness', default=0.45, min=0.0, max=1.0, update=_update)
    metallic: FloatProperty(name='Metallic', default=0.0, min=0.0, max=1.0, update=_update,
                            description='Metallic paint (0: plain paint)')
    cover: FloatProperty(name='Paint', default=1.0, min=0.0, max=1.0, update=_update,
                         description='How much of the zone is painted (0: the bare material shows)')
    opacity: FloatProperty(name='Opacity', default=1.0, min=0.0, max=1.0, update=_update)
    through: BoolProperty(name='Through', default=False, update=_update,
                          description='Paint the faces turned away from the view too (off: only what faced it)')
    own_wear: BoolProperty(name='Own Wear', default=False, update=_own_update,
                           description='Its own chips, scratches, dirt and rust inside the zone (off: the part\'s)')
    edge_wear: FloatProperty(name='Edge Wear', default=0.0, min=0.0, max=1.0, update=_update)
    scratches: FloatProperty(name='Scratches', default=0.0, min=0.0, max=1.0, update=_update)
    dirt: FloatProperty(name='Dirt in Crevices', default=0.0, min=0.0, max=1.0, update=_update)
    dirt_top: FloatProperty(name='Dirt on Top', default=0.0, min=0.0, max=1.0, update=_update)
    dirt_low: FloatProperty(name='Dirt from Below', default=0.0, min=0.0, max=1.0, update=_update)
    rust: FloatProperty(name='Rust', default=0.0, min=0.0, max=1.0, update=_update)
    kind: EnumProperty(items=[('PAINT', 'Paint', 'A Paint Zone'), ('LINE', 'Line', 'Only a boundary line (a Split Zone)')],
                       default='PAINT')
    line_height: FloatProperty(name='Line Height', default=-0.35, min=-10.0, max=10.0, soft_min=-3.0, soft_max=3.0,
                               update=_line_update,
                               description='A line along the boundary in the bump: + a raised ridge, - an engraved '
                               'groove, 0 none (the bar: -3 .. 3; typed: up to 10)')
    line_width: FloatProperty(name='Line Width', default=0.6, min=0.05, max=40.0, soft_max=15.0, update=_line_update,
                              description='How wide the boundary line is (% of the part\'s size; the bar: up to 15, '
                              'typed: up to 40) - a wider line gets as much deeper, so it keeps its steepness')
    edge: EnumProperty(name='Edge', items=[('HARD', 'Hard', 'A clean outline'),
                                           ('AIRBRUSH', 'Airbrush', 'A soft sprayed fade across the outline'),
                                           ('TEXTURE', 'Texture', 'The outline broken up by an organic pattern')],
                       default='HARD', update=_update, description='How the zone\'s outline looks')
    edge_width: FloatProperty(name='Edge Width', default=3.0, min=0.1, max=30.0, update=_update,
                              description='How far the soft / broken-up edge reaches out past the lasso (% of the '
                              'part\'s size); what was drawn stays painted')
    edge_scale: FloatProperty(name='Edge Scale', default=1.0, min=0.1, max=10.0, update=_update,
                              description='The pattern breaking up the outline: bigger = finer')
    tex: EnumProperty(name='Texture', items=_tex_enum, update=_tex_update,
                      description='A creature colour texture for the zone (tinted by Color: grey = as it is)')
    tex_scale: FloatProperty(name='Texture Scale', default=1.0, min=0.05, max=20.0, update=_update)
    base_through: FloatProperty(name='Base Texture', default=0.0, min=0.0, max=1.0, update=_update,
                                description='How much of the material\'s own texture (its pattern, relief and '
                                            'roughness map) shows through the zone\'s paint - 0: covered')
    reach: FloatProperty(default=48.0)                        # (its distance field's reach, mask pixels)
    reach2: FloatProperty(default=0.0)                        # (its coarse field's (green), 0: none - an older picture)
    size: FloatProperty(default=1.0)                          # (the part's size when drawn, world)
    px_per_unit: FloatProperty(default=100.0)                 # (mask pixels per world unit at the part's depth)


def zones_of(mat):
    return getattr(mat, 'mch_zones', None) if mat is not None else None


def _clear_nodes(nt):
    for nd in [n for n in nt.nodes if n.name.startswith(PREFIX)]:
        nt.nodes.remove(nd)


def current(mat):
    """An older Mech / Creature tree (made before the zones' hubs - a file from an earlier version) made anew first,
    its settings kept (the shader's own sync does it; the new tree links the zones itself).  Returns True when it
    did.  (User: "근데 페인트 존이 안 먹혀" - a zone on such a material had nothing to link into.)"""
    if ms.is_mech(mat) and mat.get('mch_mech', 0) < ms.VERSION:
        ms.sync(mat)
        return True
    cs = _cs()
    if cs.is_creature(mat) and mat.get(cs.KEY, 0) < cs.VERSION:
        cs.sync(mat)
        return True
    return False


def part_id(ob):
    """The number of the part a zone is on (the custom property ZONE_ID, given the first time - unique in the file):
    the zone's nodes paint only the object with that number.  0: none (no part)."""
    if ob is None or ob.type != 'MESH':
        return 0
    try:
        pid = int(ob.get(ZONE_ID, 0))
    except (TypeError, ValueError):
        pid = 0
    taken = [o for o in bpy.data.objects if o != ob and int(o.get(ZONE_ID, 0) or 0) == pid] if pid else []
    if pid <= 0 or any(o.type == 'MESH' and o.data != ob.data for o in taken):   # (none yet, or a copy's number)
        pid = 1 + max((int(o.get(ZONE_ID, 0) or 0) for o in bpy.data.objects), default=0)
        ob[ZONE_ID] = pid
        # (0.24.95 user: "또 안 돼 - 뒤로 갔다 앞으로 다시 가면 생겨": a custom property set from here does not reach
        #  the 3D view's copy of the object - the zone's nodes saw 0, nothing painted until an undo / redo; the
        #  object told it changed: the view reads the number again)
        ob.update_tag(refresh={'OBJECT'})
    return pid


def _affine(b, vec, M, name):
    """``M`` @ ``vec`` (a 4 x 4 affine matrix) as nodes - its rows ``name``0..2 (d: the dot, a: the offset), so
    ``_set_affine`` can change it in place."""
    comb = b.node('ShaderNodeCombineXYZ')
    for r in range(3):
        d = b.node('ShaderNodeVectorMath')
        d.operation = 'DOT_PRODUCT'
        d.name = f'{name}{r}d'
        b.link(vec, d.inputs[0])
        d.inputs[1].default_value = tuple(M[r][:3])
        a = b.math('ADD', d.outputs['Value'], M[r][3])
        a.node.name = f'{name}{r}a'
        b.link(a, comb.inputs[r])
    return comb.outputs['Vector']


def _set_affine(nodes, M, name):
    for r in range(3):
        d, a = nodes.get(f'{name}{r}d'), nodes.get(f'{name}{r}a')
        if d is None or a is None:
            return False
        d.inputs[1].default_value = tuple(M[r][:3])
        a.inputs[1].default_value = M[r][3]
    return True


def _look_up(b, z, vt, q, pos, P, nrm, eye, look, lw, lsel, thr, shared):
    """One look-up of a zone at ``q`` (the point in the projector's space): (its mask - the edge, in front of the
    view, facing it or Through -, its line profile).  The drawn zone, or a mirror copy (``q`` / ``pos`` the point it
    mirrors, ``eye`` / ``look`` the view mirrored); ``P`` / ``nrm`` the shaded point and its normal (part space)."""
    W = [list(z.win[r * 4:(r + 1) * 4]) for r in range(4)]

    def row(r):
        d = b.node('ShaderNodeVectorMath')
        d.operation = 'DOT_PRODUCT'
        d.name = f'{vt}row{r}'
        b.link(q, d.inputs[0])
        d.inputs[1].default_value = W[r][:3]
        return b.math('ADD', d.outputs['Value'], W[r][3])
    den = row(3)
    u = b.math('ADD', b.math('MULTIPLY', b.math('DIVIDE', row(0), den), 0.5), 0.5)
    v = b.math('ADD', b.math('MULTIPLY', b.math('DIVIDE', row(1), den), 0.5), 0.5)
    uv = b.node('ShaderNodeCombineXYZ')
    b.link(u, uv.inputs[0])
    b.link(v, uv.inputs[1])
    tex = b.node('ShaderNodeTexImage')
    tex.name = vt + 'mask'
    tex.image = z.mask
    tex.extension = 'CLIP'
    tex.interpolation = 'Linear'
    b.link(uv.outputs['Vector'], tex.inputs['Vector'])
    # (the distance fields: mask pixels from the outline, + inside - red the fine one, green the coarse one)
    rgb = b.node('ShaderNodeSeparateColor')
    b.link(tex.outputs['Color'], rgb.inputs['Color'])
    sd = b.math('MULTIPLY', b.math('SUBTRACT', rgb.outputs[0], 0.5), 2.0 * z.reach)
    sdc = b.math('MULTIPLY', b.math('SUBTRACT', rgb.outputs[1], 0.5), 2.0 * _reach2(z))
    m = _edge(b, z, sd, pos, vt, shared)
    # (in front of the view, only as deep as the part was)
    sep = b.node('ShaderNodeSeparateXYZ')
    b.link(q, sep.inputs['Vector'])
    depth = b.math('MULTIPLY', sep.outputs['Z'], -1.0)
    gate = b.math('MULTIPLY', b.math('GREATER_THAN', depth, z.near), b.math('LESS_THAN', depth, z.far))
    # (facing the view when it was drawn - the part's own space: the zone moves with the part)
    fd = b.node('ShaderNodeVectorMath')
    fd.operation = 'DOT_PRODUCT'
    fd.name = vt + 'look'
    b.link(nrm, fd.inputs[0])
    if z.persp:
        ray = b.vmath('SUBTRACT', P, tuple(eye))
        ray.node.name = vt + 'eye'
        b.link(ray, fd.inputs[1])
    else:
        fd.inputs[1].default_value = tuple(look)
    facing = b.math('LESS_THAN', fd.outputs['Value'], 0.0)
    gate = b.math('MULTIPLY', gate, b.math('MAXIMUM', facing, thr))
    # (the boundary line's profile: across the outline, Line Width wide - the coarse field for a wide line)
    sdl = b.math('ADD', sd, b.math('MULTIPLY', b.math('SUBTRACT', sdc, sd), lsel))
    prof = b.maprange(b.math('ABSOLUTE', sdl), 0.0, lw, 1.0, 0.0)
    prof.node.interpolation_type = 'SMOOTHSTEP'
    return b.math('MULTIPLY', m, gate), b.math('MULTIPLY', prof, gate)


BAKED = 'mch_baked_sym'             # (a zone's mirror copies kept after its part's Mirror was applied - see ``bake_mirrors``)
SEEN = 'mch_sym_seen'               # (the live Mirror a zone's copies were last made for, and the part's point count)


def _reflections(ob, mod):
    """The reflections (the part's own space - every combination of the mirror's axes) of mirror modifier ``mod``."""
    if mod is None or not any(mod.use_axis):
        return []
    axes = [a for a in range(3) if mod.use_axis[a]]
    piv = Matrix.Identity(4)
    if mod.mirror_object is not None:                   # (the mirror's planes: the mirror object's, else the part's)
        piv = ob.matrix_world.inverted_safe() @ mod.mirror_object.matrix_world
    out = []
    for n in range(1, 1 << len(axes)):
        flip = [1.0, 1.0, 1.0]
        for j, a in enumerate(axes):
            if n >> j & 1:
                flip[a] = -1.0
        out.append(piv @ Matrix.Diagonal((*flip, 1.0)) @ piv.inverted_safe())
    return out


def _key(mats):
    return ';'.join(','.join(f'{v:.5f}' for r in M for v in r) for M in mats)


def _parse(key):
    out = []
    for part in (key or '').split(';'):
        try:
            v = [float(x) for x in part.split(',')]
        except ValueError:
            continue
        if len(v) == 16:
            out.append(Matrix([v[0:4], v[4:8], v[8:12], v[12:16]]))
    return out


def _mirror_axes(ob):
    """The part's live Mirror (Mecha Lab's symmetry): (its reflections in the part's own space - every combination
    of its axes -, a key for them).  None / '' without one."""
    try:
        from . import symmetry
        mod = symmetry.mirror_mod(ob)
    except (ImportError, AttributeError, ReferenceError):
        return [], ''
    if mod is None or not mod.show_viewport or not any(mod.use_axis):
        return [], ''
    out = _reflections(ob, mod)
    return out, _key(out)


def _merged(live, baked):
    """The live reflections and the kept ones, each once."""
    out, keys = [], set()
    for M in list(live) + list(baked):
        k = _key([M])
        if k not in keys:
            keys.add(k)
            out.append(M)
    return out


def mirror_maps(z):
    """[(S, Tq)] for each mirror copy of zone ``z``: S the reflection (the part's space), Tq the part's space -> the
    projector's.  The part = the projector's parent.  The live Mirror's copies and those kept from an applied one."""
    proj = z.projector
    ob = proj.parent if proj is not None else None
    if ob is None or ob.type != 'MESH':
        return []
    live, _key_ = _mirror_axes(ob)
    refl = _merged(live, _parse(z.get(BAKED, '')))
    if not refl:
        return []
    Tq = proj.matrix_world.inverted_safe() @ ob.matrix_world
    return [(S, Tq) for S in refl]


def bake_mirrors(ob, mod=None):
    """0.24.95 (user: "미러 하고 어플라이 하면 적용이 안 됐어") The part's Mirror is about to be applied: its zones keep
    their mirror copies (the mirrored half is the part's own mesh now; without this the copies went with the
    modifier).  ``mod``: the mirror modifier applied (default: the part's Mirror).  Returns the zones kept."""
    if ob is None or ob.type != 'MESH':
        return 0
    if mod is None:
        try:
            from . import symmetry
            mod = symmetry.mirror_mod(ob)
        except (ImportError, AttributeError):
            mod = None
    refl = _reflections(ob, mod) if mod is not None and mod.type == 'MIRROR' else []
    if not refl:
        return 0
    n = 0
    for sl in ob.material_slots:
        for z in zones_of(sl.material) or ():
            proj = z.projector
            if proj is None or proj.parent != ob:
                continue
            z[BAKED] = _key(_merged(_parse(z.get(BAKED, '')), refl))
            n += 1
    return n


def after_apply(ob):
    """The zones of ``ob``'s materials follow (after a modifier was applied)."""
    for sl in getattr(ob, 'material_slots', ()):
        m = sl.material
        if m is not None and zones_of(m):
            try:
                update_mirrors(m)
            except (ReferenceError, AttributeError, RuntimeError):
                pass


def _mirror_eye(z, S):
    """The view of a mirror copy, in the part's space: the eye mirrored, the direction mirrored."""
    eye = S @ Vector(z.eye)
    look = (S.to_3x3() @ Vector(z.look)).normalized()
    return tuple(eye), tuple(look)


def sym_key(mat):
    """What the zones' mirror copies of ``mat`` were made for: per zone its part's Mirror (axes, planes) and the
    copies kept from an applied one."""
    keys = []
    for z in zones_of(mat) or ():
        proj = z.projector
        ob = proj.parent if proj is not None else None
        live = _mirror_axes(ob)[1] if ob is not None and ob.type == 'MESH' else ''
        keys.append(live + '#' + z.get(BAKED, ''))
    return '|'.join(keys)


def _applied_elsewhere(z):
    """The part's Mirror gone - applied by Blender itself (not through Mecha Lab, which keeps the copies first): the
    modifier removed (not switched off) and the part's points grown by half or more since the copies were made for
    it.  Then its copies are kept as an applied Mirror's."""
    proj = z.projector
    ob = proj.parent if proj is not None else None
    seen = z.get(SEEN, '')
    if ob is None or ob.type != 'MESH' or not seen or '@' not in seen:
        return
    key, nv = seen.rsplit('@', 1)
    if not key or any(m.type == 'MIRROR' for m in ob.modifiers):
        return
    try:
        if len(ob.data.vertices) >= 1.5 * int(nv):
            z[BAKED] = _key(_merged(_parse(z.get(BAKED, '')), _parse(key)))
    except (ValueError, ReferenceError):
        pass


def _note_seen(mat):
    for z in zones_of(mat) or ():
        proj = z.projector
        ob = proj.parent if proj is not None else None
        if ob is not None and ob.type == 'MESH':
            z[SEEN] = _mirror_axes(ob)[1] + '@' + str(len(ob.data.vertices))


def update_mirrors(mat):
    """0.24.95 The part's Mirror changed (turned on / off, axes, the part moved against its mirror object): the
    zones' mirror copies follow - their matrices in place, made anew when their number changed."""
    if not zoned(mat) or not zones_of(mat):
        return False
    for z in zones_of(mat):
        _applied_elsewhere(z)
    key = sym_key(mat)
    if mat.get(SYM_KEY, '') == key:
        return False
    nodes = mat.node_tree.nodes
    live = [z for z in zones_of(mat) if z.projector is not None and z.mask is not None]
    for i, z in enumerate(live):
        tag = f'{PREFIX}{i}:'
        maps = mirror_maps(z)
        if nodes.get(f'{tag}v{len(maps)}:mask') is None and maps or nodes.get(f'{tag}v{len(maps) + 1}:mask'):
            relink(mat)                             # (more / fewer copies: made anew)
            _note_seen(mat)
            return True
        for k, (S, Tq) in enumerate(maps, start=1):
            vt = f'{tag}v{k}:'
            _set_affine(nodes, S, vt + 's')
            _set_affine(nodes, Tq, vt + 'q')
            eye, look = _mirror_eye(z, S)
            if nodes.get(vt + 'eye') is not None:
                nodes[vt + 'eye'].inputs[1].default_value = eye
            elif nodes.get(vt + 'look') is not None:
                nodes[vt + 'look'].inputs[1].default_value = look
    mat[SYM_KEY] = key
    _note_seen(mat)
    return True


def relink(mat):
    """The zone nodes made anew in ``mat`` (after its Mech Shader tree was made, or a zone added / removed) and linked
    into the Mech Shader's zone hubs."""
    if not zoned(mat):
        return
    if current(mat):                            # (made anew: the zones are linked already)
        return
    nt = mat.node_tree
    _clear_nodes(nt)
    zs = zones_of(mat)
    hub = {k: nt.nodes.get('mch:zone_' + k) for k in ('mask', 'cover', 'rough', 'metal', 'color')}
    if hub['mask'] is None or hub['color'] is None:     # (cover / metal: the Mech Shader's only)
        return
    live = [z for z in zs if z.projector is not None and z.mask is not None] if zs else []
    hub['own'] = nt.nodes.get('mch:zone_own')
    hub['height'] = nt.nodes.get('mch:zone_height')
    hub['hide'] = nt.nodes.get('mch:zone_hide')         # (0.24.95 the Mech Shader's: its texture under the paint)
    for k in ms.ZONE_WEAR:
        hub['w_' + k] = nt.nodes.get('mch:zone_w_' + k)
    for k, nd in hub.items():
        if k != 'color' and nd is not None:
            for lk in list(nd.inputs[0].links):
                nt.links.remove(lk)
    csock = {sk.identifier: sk for sk in hub['color'].inputs}['A_Color']
    for lk in list(csock.links):
        nt.links.remove(lk)
    mat[SYM_KEY] = sym_key(mat)                 # (the mirror copies made below are for the parts' Mirror as it is)
    _note_seen(mat)
    if not live:
        return
    before = {nd.as_pointer() for nd in nt.nodes}
    b = ms.Builder(nt)
    mask_t = col_t = rough_t = metal_t = cover_t = line_t = None
    geo = b.node('ShaderNodeNewGeometry')
    geo.name = PREFIX + 'geo'
    tco = b.node('ShaderNodeTexCoord')
    tco.name = PREFIX + 'tc'
    nrm = b.node('ShaderNodeVectorTransform')
    nrm.name = PREFIX + 'nrm'
    nrm.vector_type, nrm.convert_from, nrm.convert_to = 'NORMAL', 'WORLD', 'OBJECT'
    b.link(geo.outputs['Normal'], nrm.inputs['Vector'])
    shared_all = {}
    for i, z in enumerate(live):
        tag = f'{PREFIX}{i}:'
        tc = b.node('ShaderNodeTexCoord')
        tc.name = tag + 'tc'
        tc.object = z.projector
        # (the zone's sliders - shared by its mirror copies)
        lwp, lsel_v = line_px(z)
        lw = b.value(f'z{i}_lw', lwp)
        lw.node.name = tag + 'lw'
        lsel = b.value(f'z{i}_lsel', lsel_v)
        lsel.node.name = tag + 'lsel'
        lh = b.value(f'z{i}_lh', line_h(z))
        lh.node.name = tag + 'lh'
        thr = b.value(f'z{i}_through', 1.0 if z.through else 0.0)
        thr.node.name = tag + 'through'
        shared = {}
        m = prof = None
        looks = []
        # 0.24.95 (user: "왜 미러가 안 돼?") the drawn zone, then a copy for each reflection of the part's live Mirror
        for k, (S, Tq) in enumerate([(None, None)] + mirror_maps(z)):
            if S is None:
                vt, q, pos, eye, look = tag, tc.outputs['Object'], tco.outputs['Object'], tuple(z.eye), tuple(z.look)
            else:
                vt = f'{tag}v{k}:'
                pos = _affine(b, tco.outputs['Object'], S, vt + 's')     # (the point this one mirrors ...)
                q = _affine(b, pos, Tq, vt + 'q')                        # (... in the projector's space)
                eye, look = _mirror_eye(z, S)
            mv, pv = _look_up(b, z, vt, q, pos, tco.outputs['Object'], nrm.outputs['Vector'], eye, look, lw, lsel,
                              thr, shared)
            m = mv if m is None else b.math('MAXIMUM', m, mv)
            looks.append((mv, pv))
        # (0.24.95 user: "미러 하면 반대쪽 스트로크 자국이 남아": a zone over the mirror line overlaps its copy - each
        #  one's outline groove ran on inside the other; a copy's line only where no other copy covers: the line on
        #  the edge of them all)
        for k, (mv, pv) in enumerate(looks):
            if len(looks) > 1 and z.kind != 'LINE':
                cover = None
                for j, (mj, _pj) in enumerate(looks):
                    if j != k:
                        cover = mj if cover is None else b.math('MAXIMUM', cover, mj)
                pv = b.math('MULTIPLY', pv, b.math('SUBTRACT', 1.0, cover, clamp=True))
            prof = pv if prof is None else b.math('MAXIMUM', prof, pv)
        # (0.24.95 user: "셀렉트 모드로 했는데 다른 영역도 칠해져" - the material shared by other parts: the zone only on its
        #  own part - the part's number (its custom property ZONE_ID, read by an Object attribute) must match)
        pid = part_id(z.projector.parent)
        if pid:
            if 'pid' not in shared_all:
                at = b.node('ShaderNodeAttribute')
                at.name = PREFIX + 'pid'
                at.attribute_type = 'OBJECT'
                at.attribute_name = ZONE_ID
                shared_all['pid'] = at.outputs['Fac']
            same = b.node('ShaderNodeMath')
            same.operation = 'COMPARE'
            b.link(shared_all['pid'], same.inputs[0])
            same.inputs[1].default_value = float(pid)
            same.inputs[2].default_value = 0.5
            m = b.math('MULTIPLY', m, same.outputs[0])
            prof = b.math('MULTIPLY', prof, same.outputs[0])
        # (the boundary line: a smooth ridge across the outline, Line Width wide, x Line Height)
        ln = b.math('MULTIPLY', prof, b.math('MULTIPLY', lh, LINE_GAIN))
        line_t = ln if line_t is None else b.math('ADD', line_t, ln)
        if z.kind == 'LINE':
            continue
        op = b.value(f'z{i}_opacity', z.opacity)
        op.node.name = tag + 'opacity'
        m = b.math('MULTIPLY', m, op, clamp=True)
        col = b.node('ShaderNodeRGB')
        col.name = tag + 'color'
        col.outputs[0].default_value = (*z.color, 1.0)
        zcol = col.outputs[0]
        if z.tex != 'FLAT':                     # (a creature colour texture, tinted by Color: grey = as it is)
            timg = b.node('ShaderNodeTexImage')
            timg.name = tag + 'tex'
            timg.image = tex_image(mat, z.tex)
            tsc = b.value(f'z{i}_tsc', _tex_tiles(z))
            tsc.node.name = tag + 'tsc'
            b.link(b.vmath('SCALE', tco.outputs['Object'], fac=tsc), timg.inputs['Vector'])
            zcol = b.vmath('SCALE', b.mixc(1.0, timg.outputs['Color'], col.outputs[0], 'MULTIPLY'), fac=2.0)
        vals = {}
        for k, val in (('rough', z.roughness), ('metal', z.metallic), ('cover', z.cover)):
            vals[k] = b.value(f'z{i}_{k}', val)
            vals[k].node.name = tag + k
        ow = b.value(f'z{i}_own', 1.0 if z.own_wear else 0.0)
        ow.node.name = tag + 'own'
        om = b.math('MULTIPLY', m, ow)
        # (0.24.95 user: "기존에 있던 텍스처가 안 사라져" - the paint covers the material's own texture; Base Texture lets
        #  it through)
        bt = b.value(f'z{i}_bthru', z.base_through)
        bt.node.name = tag + 'bthru'
        hd = b.math('MULTIPLY', b.math('MULTIPLY', m, vals['cover']), b.math('SUBTRACT', 1.0, bt))
        hide_t = hd if mask_t is None else b.math('MAXIMUM', hide_t, hd)
        wv = {}
        for k in ms.ZONE_WEAR:
            wv[k] = b.value(f'z{i}_w_{k}', getattr(z, k))
            wv[k].node.name = tag + 'w_' + k
        if mask_t is None:
            mask_t, col_t = m, zcol
            rough_t, metal_t, cover_t = vals['rough'], vals['metal'], vals['cover']
            own_t, wear_t = om, dict(wv)
        else:                                   # (a later zone over the earlier ones)
            col_t = b.mixc(m, col_t, zcol)
            rough_t = b.mixf(m, rough_t, vals['rough'])
            metal_t = b.mixf(m, metal_t, vals['metal'])
            cover_t = b.mixf(m, cover_t, vals['cover'])
            mask_t = b.math('MAXIMUM', mask_t, m)
            wear_t = {k: b.mixf(om, wear_t[k], wv[k]) for k in ms.ZONE_WEAR}
            own_t = b.math('MAXIMUM', own_t, om)
    for nd in nt.nodes:                         # (only what was made here is the zones': named so it can go again)
        if nd.as_pointer() not in before and not nd.name.startswith(PREFIX):
            nd.name = PREFIX + nd.name
    if line_t is not None and hub['height'] is not None:
        nt.links.new(line_t, hub['height'].inputs[0])
    if mask_t is None:                          # (only lines: nothing painted)
        return
    nt.links.new(mask_t, hub['mask'].inputs[0])
    for k, sock in (('cover', cover_t), ('rough', rough_t), ('metal', metal_t)):
        if hub[k] is not None:
            nt.links.new(sock, hub[k].inputs[0])
    nt.links.new(col_t, csock)
    if hub['hide'] is not None:
        nt.links.new(hide_t, hub['hide'].inputs[0])
    if hub['own'] is not None:
        nt.links.new(own_t, hub['own'].inputs[0])
        for k in ms.ZONE_WEAR:
            if hub['w_' + k] is not None:
                nt.links.new(wear_t[k], hub['w_' + k].inputs[0])


def _edge_width_w(z):
    """The soft / broken-up outline's width, world."""
    return max(1e-5, z.edge_width / 100.0 * z.size)


def _edge_scale(z):
    """The pattern breaking up the outline: its scale on the part's own coordinates."""
    return 6.0 * z.edge_scale / max(z.size, 1e-4)


def _tex_tiles(z):
    """A zone's colour texture: tiles per unit (a creature 2 units tall: 0.5 x 2 / size, x Texture Scale)."""
    return 0.5 * 2.0 / max(z.size, 1e-4) * z.tex_scale


def _edge(b, z, sd, pos, tag, shared=None):
    """The zone's mask from its distance field ``sd`` (mask pixels, + inside).  What was drawn stays painted; the
    edge grows outwards from the lasso: Hard (1 px soft), Airbrush (a smooth fade over Edge Width, as a spray past a
    stencil), Texture (the outline pushed out by an organic pattern, 0 .. Edge Width, a little soft)."""
    if z.edge == 'HARD':
        return b.math('ADD', sd, 0.5, clamp=True)
    sdw = b.math('DIVIDE', sd, max(z.px_per_unit, 1e-6))            # (world units from the outline)
    shared = {} if shared is None else shared                       # (a zone's mirror copies: the same sliders)
    if 'ew' not in shared:
        shared['ew'] = b.value(f'{tag}ew', _edge_width_w(z))
        shared['ew'].node.name = tag + 'ew'
    ew = shared['ew']
    if z.edge == 'AIRBRUSH':
        mr = b.maprange(sdw, b.math('MULTIPLY', ew, -1.0), 0.0, 0.0, 1.0)
        mr.node.interpolation_type = 'SMOOTHSTEP'
        return mr
    if z.edge == 'TEXTURE':
        nz = b.node('ShaderNodeTexNoise')
        nz.name = tag + 'noise'
        nz.inputs['Detail'].default_value = 8.0
        nz.inputs['Roughness'].default_value = 0.65
        nz.inputs['Distortion'].default_value = 0.35
        if 'esc' not in shared:
            shared['esc'] = b.value(f'{tag}esc', _edge_scale(z))
            shared['esc'].node.name = tag + 'esc'
        esc = shared['esc']
        b.link(b.vmath('SCALE', pos, fac=esc), nz.inputs['Vector'])
        nz.inputs['Scale'].default_value = 1.0
        reach = b.maprange(nz.outputs['Fac'], 0.36, 0.64, 0.0, 1.0)   # (the noise, mostly near 0.5: stretched)
        sdw = b.math('ADD', sdw, b.math('MULTIPLY', reach, ew))          # (the outline pushed out 0 .. Edge Width)
    soft = b.math('MULTIPLY', ew, 0.06)
    mr = b.maprange(sdw, b.math('MULTIPLY', soft, -1.0), soft, 0.0, 1.0)
    mr.node.interpolation_type = 'SMOOTHSTEP'
    return mr


def _half_width_px(z):
    """Half the Line Width in mask pixels (at the part's depth when the zone was drawn)."""
    return max(0.5, z.line_width / 100.0 * z.size * z.px_per_unit / 2.0)


def _reach2(z):
    return z.reach2 if z.reach2 > 0.0 else z.reach      # (an older picture: its green is the fine field)


def line_px(z):
    """(half the line's width in mask pixels, which field it reads: 0 the fine one, 1 the coarse one) - a line wider
    than the fine field reaches reads the coarse one; never wider than the field it reads (it would flatten out)."""
    hw = _half_width_px(z)
    if hw <= 0.8 * z.reach or _reach2(z) <= z.reach:
        return min(hw, 0.95 * z.reach), 0.0
    return min(hw, 0.95 * _reach2(z)), 1.0


def line_h(z):
    """The line's height into the bump: Line Height, x as much as the line is wider than LINE_REF (a wide line as
    steep as a narrow one - user: "두께랑 깊이 훨씬 더 두껍게 보일 수 있게")."""
    return z.line_height * max(1.0, z.line_width / LINE_REF)


def sync(mat):
    """A zone's sliders into its nodes (no re-making)."""
    zs = zones_of(mat)
    if not zs or not zoned(mat):
        return
    if current(mat):                            # (an older tree: made anew, the zones linked with it)
        return
    update_mirrors(mat)                         # (the part's Mirror changed since: the mirror copies follow)
    nodes = mat.node_tree.nodes
    live = [z for z in zs if z.projector is not None and z.mask is not None]
    if nodes.get(f'{PREFIX}{len(live) - 1}:mask') is None or nodes.get(f'{PREFIX}{len(live)}:mask') is not None:
        relink(mat)
        return
    for i, z in enumerate(live):
        tag = f'{PREFIX}{i}:'
        if (nodes.get(tag + 'ew') is None) != (z.edge == 'HARD') or (nodes.get(tag + 'tex') is None) != \
                (z.tex == 'FLAT') or (nodes.get(tag + 'esc') is None) != (z.edge != 'TEXTURE'):
            relink(mat)                         # (the Edge / Texture choice changed: its nodes made anew)
            return
        lwp, lsel = line_px(z)
        for k, val in (('lw', lwp), ('lsel', lsel), ('lh', line_h(z)), ('through', 1.0 if z.through else 0.0),
                       ('ew', _edge_width_w(z)), ('esc', _edge_scale(z)), ('tsc', _tex_tiles(z))):
            nd = nodes.get(tag + k)
            if nd is not None:
                nd.outputs[0].default_value = val
        if z.kind == 'LINE':
            continue
        nodes[tag + 'color'].outputs[0].default_value = (*z.color, 1.0)
        for k, val in (('rough', z.roughness), ('metal', z.metallic), ('cover', z.cover), ('opacity', z.opacity),
                       ('own', 1.0 if z.own_wear else 0.0), ('bthru', z.base_through)) \
                + tuple(('w_' + k, getattr(z, k)) for k in ms.ZONE_WEAR):
            nodes[tag + k].outputs[0].default_value = val


# -----------------------------------------------------------------------------
# making a zone
# -----------------------------------------------------------------------------

def _view(region, rv3d):
    return rv3d.view_matrix.copy(), rv3d.window_matrix.copy(), bool(rv3d.is_perspective), region.width, region.height


def _depth_range(ob, view_matrix, persp=True):
    """How deep the part is along the view (its bounding box's corners in view space): (near, far) with a margin.  An
    orthographic view's eye can sit inside or past the part (its depth below 0): not cut at 0 there."""
    vm = view_matrix @ ob.matrix_world
    zs = [-(vm @ Vector(c)).z for c in ob.bound_box]
    pad = 0.05 * (max(zs) - min(zs) + 1e-6) + 1e-4
    return (max(0.0, min(zs) - pad) if persp else min(zs) - pad), max(zs) + pad


def _px_per_unit(ob, view_matrix, window_matrix, mask_h):
    """Mask pixels per world unit at the part's middle (seen from that view)."""
    c = ob.matrix_world @ (sum((Vector(v) for v in ob.bound_box), Vector()) / 8.0)
    vc = view_matrix @ c
    pts = []
    for dy in (0.0, 1.0):
        v = window_matrix @ Vector((vc.x, vc.y + dy, vc.z, 1.0))
        pts.append(v.y / v.w if abs(v.w) > 1e-12 else 0.0)
    return abs(pts[1] - pts[0]) * 0.5 * mask_h


def _projector(context, ob, name, view_matrix):
    proj = bpy.data.objects.new(name, None)
    proj.empty_display_type = 'PLAIN_AXES'
    proj.empty_display_size = 0.01
    cols = ob.users_collection or (context.scene.collection,)
    cols[0].objects.link(proj)
    proj.matrix_world = view_matrix.inverted()
    proj.parent = ob
    proj.matrix_parent_inverse = ob.matrix_world.inverted()
    proj.hide_select = True
    proj.hide_render = True
    proj['mch_zone'] = 1
    return proj


def _fill_zone(z, ob, proj, img, view_matrix, window_matrix, persp):
    """A zone's projector, mask and view (shared by a Paint Zone and a Split Zone's line)."""
    z.projector = proj
    z.mask = img
    z.win = [window_matrix[r][c] for r in range(4) for c in range(4)]
    z.persp = persp
    to_part = ob.matrix_world.inverted() @ view_matrix.inverted()
    z.eye = tuple(to_part.translation)
    z.look = tuple((to_part.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized())
    z.near, z.far = _depth_range(ob, view_matrix, persp)
    z.size = max(ob.dimensions) or 1.0
    z.reach = SDF_R
    z.reach2 = SDF_R2
    z.px_per_unit = _px_per_unit(ob, view_matrix, window_matrix, img.size[1])


def add_paint_zone(context, ob, pts, view_matrix, window_matrix, persp, rw, rh, color=None, through=False):
    """A Paint Zone on ``ob``'s Mech material from the lasso ``pts`` (region pixels) drawn in that view.  Returns the
    zone."""
    mat = ob.active_material
    if not zoned(mat):
        raise RuntimeError('the part has no Mech / Creature Shader material - apply one first')
    if not as_loops(pts):
        raise RuntimeError('the lasso needs at least 3 points')
    zs = zones_of(mat)
    n = len(zs) + 1
    creature = _cs().is_creature(mat)
    img = mask_image(f'.MCH Zone {mat.name} {n}', pts, rw, rh)
    proj = _projector(context, ob, f'Zone {n} ({ob.name})', view_matrix)
    z = zs.add()
    z.name = f'Zone {n}'
    _fill_zone(z, ob, proj, img, view_matrix, window_matrix, persp)
    if creature:                                # (a creature's markings: a soft airbrushed edge, its own gloss)
        z.color = color or CREATURE_PALETTE[(n - 1) % len(CREATURE_PALETTE)]
        z.edge = 'AIRBRUSH'
        z.roughness = getattr(mat, _cs().KEY).roughness
        z.line_height = 0.0
    else:
        z.color = color or PALETTE[(n - 1) % len(PALETTE)]
    z['through'] = bool(through)                # (0.24.95 the back faces too - set before its nodes are made)
    relink(mat)
    proj.hide_set(True)
    return z


def remove_zone(mat, index):
    """Remove a zone (a Split Zone's line: from both materials)."""
    zs = zones_of(mat)
    if zs is None or not (0 <= index < len(zs)):
        return False
    z = zs[index]
    proj, img = z.projector, z.mask
    others = [(m, [i for i, oz in enumerate(m.mch_zones) if oz.projector == proj])
              for m, _z in twins(z)] if proj is not None else []
    zs.remove(index)
    for m, idx in others:
        for i in sorted(set(idx), reverse=True):
            m.mch_zones.remove(i)
        relink(m)
    if proj is not None:
        bpy.data.objects.remove(proj)
    if img is not None and img.users == 0:
        bpy.data.images.remove(img)
    relink(mat)
    return True


# -----------------------------------------------------------------------------
# Split Zone: edges cut along the lasso, the faces inside a material of their own
# -----------------------------------------------------------------------------

def _inside(px, poly):
    """bool per point: inside the closed polygon (or several loops; even-odd)."""
    x, y = px[:, 0], px[:, 1]
    ins = np.zeros(len(px), bool)
    loops = as_loops(poly)
    if not loops:
        return ins
    for (ax, ay), (bx, by) in zip(*_edges(loops)):
        c = ((ay > y) != (by > y)) & (x < (bx - ax) * (y - ay) / np.where(by - ay == 0, 1e-12, by - ay) + ax)
        ins ^= c
    return ins


class _View:
    """The view the lasso was drawn in, in the part's own space: rays through region pixels, pixels of points."""

    def __init__(self, ob, view_matrix, window_matrix, persp, rw, rh):
        self.full = window_matrix @ view_matrix @ ob.matrix_world
        self.inv = self.full.inverted()
        self.rw, self.rh, self.persp = rw, rh, persp
        to_part = ob.matrix_world.inverted() @ view_matrix.inverted()
        self.eye = to_part.translation.copy()
        self.look = (to_part.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()

    def ray(self, px):
        nx, ny = 2.0 * px[0] / self.rw - 1.0, 2.0 * px[1] / self.rh - 1.0
        a = self.inv @ Vector((nx, ny, -1.0, 1.0))
        b = self.inv @ Vector((nx, ny, 1.0, 1.0))
        a, b = a.xyz / a.w, b.xyz / b.w
        return a, (b - a).normalized()

    def to_px(self, co):
        v = self.full @ Vector((co[0], co[1], co[2], 1.0))
        if abs(v.w) < 1e-12:
            return None
        return ((v.x / v.w * 0.5 + 0.5) * self.rw, (v.y / v.w * 0.5 + 0.5) * self.rh)

    def facing(self, co, normal):
        d = (Vector(co) - self.eye) if self.persp else self.look
        return normal.dot(d) < 0.0


def _walls(ob, view, pts, through=False, miss_ok=True):
    """The cutter: a band of quads along the lasso, each lasso point's ray from a little in front of the part's
    surface there to a little behind it (only the side seen is cut, not the back; ``through``: all the way through
    the part).  Part space: (verts, quads); None when the lasso misses the part and not ``miss_ok``."""
    from mathutils.bvhtree import BVHTree
    me = ob.data
    bvh = BVHTree.FromPolygons([v.co for v in me.vertices], [p.vertices for p in me.polygons])
    size = max(ob.dimensions) / max(max(ob.matrix_world.to_scale()), 1e-9) or 1.0
    margin = 0.04 * size
    rays, hits = [], []
    for px in pts:
        o, d = view.ray(px)
        rays.append((o, d))
        loc, _n, _i, dist = bvh.ray_cast(o, d)
        hits.append(dist if loc is not None else None)
    known = [h for h in hits if h is not None]
    if not known and not miss_ok:
        return None
    if through:                                     # (0.24.95 the back too: each ray across the whole part)
        corners = [Vector(v) for v in ob.bound_box]
        verts, quads = [], []
        for o, d in rays:
            ts = [(c - o).dot(d) for c in corners]
            verts.append(o + d * (min(ts) - margin))
            verts.append(o + d * (max(ts) + margin))
        n = len(pts)
        for i in range(n):
            j = (i + 1) % n
            quads.append((2 * i, 2 * j, 2 * j + 1, 2 * i + 1))
        return verts, quads
    if not known:                                   # (the lasso misses the part everywhere: through all of it)
        c = sum((Vector(v) for v in ob.bound_box), Vector()) / 8.0
        o, d = rays[0]
        mid = (c - o).dot(d)
        hits = [mid] * len(pts)
        margin = size
    else:                                           # (a point off the part: its nearest neighbour's depth)
        n = len(hits)
        for i in range(n):
            if hits[i] is None:
                for k in range(1, n):
                    for j in ((i - k) % n, (i + k) % n):
                        if hits[j] is not None and hits[i] is None:
                            hits[i] = hits[j]
    verts, quads = [], []
    for (o, d), h in zip(rays, hits):
        verts.append(o + d * max(0.0, h - margin))
        verts.append(o + d * (h + margin))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        quads.append((2 * i, 2 * j, 2 * j + 1, 2 * i + 1))
    return verts, quads


def _faces_inside(view, tris, loops, tree, size, through=False):
    """The faces of the cut mesh inside the lasso seen from ``view``: most of their area inside it (triangle by
    triangle - a face of the ring round the lasso can have its middle inside it), facing the view and seen (the first
    hit along the ray); ``through``: the back faces and hidden ones too."""
    out = []
    cands, tri_px, tri_area, owner = [], [], [], []
    for f, lts in tris.items():
        if not through and not view.facing(f.calc_center_median(), f.normal):
            continue
        cands.append(f)
        for lt in lts:
            cc = sum((l.vert.co for l in lt), Vector()) / 3.0
            pc = view.to_px(cc)
            tri_px.append(pc if pc is not None else (-1e9, -1e9))
            tri_area.append((lt[1].vert.co - lt[0].vert.co).cross(lt[2].vert.co - lt[0].vert.co).length / 2)
            owner.append(len(cands) - 1)
    if not cands:
        return out
    tin = _inside(np.array(tri_px, np.float64), loops)
    area = np.array(tri_area)
    own = np.array(owner)
    a_in = np.bincount(own, weights=area * tin, minlength=len(cands))
    a_all = np.bincount(own, weights=area, minlength=len(cands))
    best = {}
    for k, (o_, ok) in enumerate(zip(own, tin)):        # (a point of the face inside: the largest triangle in)
        if ok and (o_ not in best or area[k] > area[best[o_]]):
            best[o_] = k
    flat = [lt for f in cands for lt in tris[f]]
    for ci, f in enumerate(cands):
        if a_all[ci] <= 0 or a_in[ci] < 0.5 * a_all[ci]:
            continue
        if through:
            out.append(f)
            continue
        lt = flat[best[ci]]
        c = sum((l.vert.co for l in lt), Vector()) / 3.0
        if view.persp:
            o = view.eye
            d = (c - o)
        else:
            d = view.look.copy()
            o = c - d * (2.0 * size)
        dist = d.length if view.persp else 2.0 * size
        d.normalize()
        _loc, _n, idx, hd = tree.ray_cast(o, d)
        if idx is None or idx == f.index or hd >= dist - 1e-4 * size:
            out.append(f)
    return out


def split_zone(context, ob, pts, view_matrix, window_matrix, persp, rw, rh, preset=None, through=False):
    """Cut ``ob``'s mesh along the lasso (seen from the view; Edit-mode Intersect, Exact - the outline as new edges,
    the mesh stays one piece) and give the faces inside that are seen from the view a second Mech material (a copy
    of its own).  Returns (material, faces inside)."""
    import bmesh
    from mathutils.bvhtree import BVHTree
    mat = ob.active_material
    if not ms.is_mech(mat):
        raise RuntimeError('the part has no Mech Shader material - apply one first')
    loops = as_loops(pts)
    if not loops:
        raise RuntimeError('the lasso needs at least 3 points')
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    view = _View(ob, view_matrix, window_matrix, persp, rw, rh)
    # 0.24.95 a part with a live Mirror: drawn over its mirrored half, the faces it mirrors are cut (the Mirror shows
    # them there) - the view mirrored (its reflections in world space) finds them
    M = ob.matrix_world
    views = [view] + [_View(ob, view_matrix @ (M @ S @ M.inverted_safe()), window_matrix, persp, rw, rh)
                      for S in _mirror_axes(ob)[0]]
    wv, wq = [], []
    for vi, vw in enumerate(views):
        for lp in loops:                            # (a wall along each outline: the Sketch's islands and holes too)
            got = _walls(ob, vw, lp, through=through, miss_ok=vi == 0)
            if got is None:
                continue
            v_, q_ = got
            wq += [tuple(k + len(wv) for k in q) for q in q_]
            wv += v_
    me = ob.data
    K = me.copy()
    K.name = '.MCH Zone Knife'
    bm = bmesh.new()
    bm.from_mesh(K)
    lay = bm.faces.layers.int.new('mch_zone_cut')
    for f in bm.faces:
        f[lay] = 1
    nv = [bm.verts.new(c) for c in wv]
    for q in wq:
        try:
            f = bm.faces.new([nv[k] for k in q])
            f[lay] = 2
        except ValueError:
            pass
    bm.to_mesh(K)
    bm.free()
    ko = bpy.data.objects.new('.MCH Zone Knife', K)
    context.scene.collection.objects.link(ko)
    ko.matrix_world = ob.matrix_world.copy()
    vl = context.view_layer
    active = vl.objects.active
    selected = [o for o in vl.objects if o.select_get()]
    try:
        for o in selected:
            o.select_set(False)
        ko.select_set(True)
        vl.objects.active = ko
        bpy.ops.object.mode_set(mode='EDIT')
        try:
            ebm = bmesh.from_edit_mesh(K)
            el = ebm.faces.layers.int.get('mch_zone_cut')
            for v in ebm.verts:
                v.select_set(False)
            for f in ebm.faces:
                f.select_set(f[el] == 2)
            ebm.select_flush_mode()
            bmesh.update_edit_mesh(K)
            bpy.ops.mesh.intersect(mode='SELECT_UNSELECT', separate_mode='NONE', solver='EXACT')
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')
        bm = bmesh.new()
        bm.from_mesh(K)
    finally:
        bpy.data.objects.remove(ko)
        for o in selected:
            try:
                o.select_set(True)
            except (ReferenceError, RuntimeError):
                pass
        try:
            vl.objects.active = active
        except (ReferenceError, RuntimeError):
            pass
    try:
        lay = bm.faces.layers.int.get('mch_zone_cut')
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[lay] == 2], context='FACES')
        bm.faces.layers.int.remove(lay)
        bm.faces.ensure_lookup_table()
        bm.faces.index_update()                     # (the tree's face indices = these)
        bm.normal_update()
        # the faces inside: most of their area inside the lasso (triangle by triangle - a face of the ring round the
        # lasso can have its middle inside it), facing the view and seen (the first hit along the ray)
        tree = BVHTree.FromBMesh(bm)
        size = max(ob.dimensions) / max(max(ob.matrix_world.to_scale()), 1e-9) or 1.0
        inside = []
        tris = {}
        for lt in bm.calc_loop_triangles():
            tris.setdefault(lt[0].face, []).append(lt)
        seen = set()
        for view in views:                          # (the drawn view, then the mirrored ones: the faces of all)
            for f in _faces_inside(view, tris, loops, tree, size, through):
                if f.index not in seen:
                    seen.add(f.index)
                    inside.append(f)
        zmat = mat.copy()
        zmat.name = mat.name + ' Zone'
        zs = zones_of(zmat)
        if zs is not None:
            while len(zs):
                zs.remove(0)
        st = getattr(zmat, ms.KEY)
        if preset:
            ms.apply_preset(zmat, preset)
        else:                                       # (a painted zone of the part's own material: a colour to start)
            st.paint = max(st.paint, 1.0)
            st.paint_color = PALETTE[0]
        zmat.mch_zone_parent = mat
        zmat.mch_zone_follow = True             # (the same wear as the part's to start - a switch on its page)
        me.materials.append(zmat)
        slot = len(me.materials) - 1
        for f in inside:
            f.material_index = slot
        bm.to_mesh(me)
    finally:
        bm.free()
        bpy.data.meshes.remove(K)
    me.update()
    try:
        ms.store_curvature(me)
    except (AttributeError, RuntimeError, ValueError):
        pass
    # the boundary line on both sides of the cut: a line-only zone in the part's material and in the zone's
    n = sum(1 for m in me.materials if m is not None and getattr(m, 'mch_zone_parent', None) == mat)
    img = mask_image(f'.MCH Zone {zmat.name} line', pts, rw, rh)
    proj = _projector(context, ob, f'Split Zone {n} ({ob.name})', view_matrix)
    for m in (mat, zmat):
        z = zones_of(m).add()
        z.name = f'Split Zone {n}'
        z.kind = 'LINE'
        _fill_zone(z, ob, proj, img, view_matrix, window_matrix, persp)
    relink(mat)
    relink(zmat)
    proj.hide_set(True)
    ms.sync(zmat)
    ob.active_material_index = slot
    return zmat, len(inside)


# -----------------------------------------------------------------------------
# the Lasso Zone tool: the shared lasso (cut_engine) - every shape, Corners, Line, Sketch, Slow Line, Surface
# -----------------------------------------------------------------------------

KINDS = (('PAINT', 'Paint', 'A Paint Zone: its own paint, projected from the view (the mesh as it is)'),
         ('SPLIT', 'Split', 'A Split Zone: edges cut along the outline, the faces inside a material of their own '
                            '(Mech parts)'))


def view_of(projector):
    """(view matrix, window matrix, perspective, region width, height) of a lasso tool's projector: a live view
    (``core_geometry.Projector``: its region), a Sketch's frozen one (``armor_plate.FrozenProjector``: its
    perspective matrix) or a headless test's ``OrthoProjector`` - the window matrix then whatever turns the view made
    from its eye and direction into that projection (the zone's shader uses all of it)."""
    rv3d, region = getattr(projector, 'rv3d', None), getattr(projector, 'region', None)
    if rv3d is not None and region is not None:
        return _view(region, rv3d)
    persp = bool(projector.is_perspective)
    if hasattr(projector, 'pers'):
        P, w, h = Matrix(projector.pers), projector.w, projector.h
    else:
        w, h = projector.size
        V0 = (Matrix.Translation(projector.center) @ projector.rot.to_4x4()).inverted()
        P = Matrix.Diagonal((2.0 * projector.ppu / w, 2.0 * projector.ppu / h, -1e-3, 1.0)) @ V0
    d = Vector(projector.view_dir).normalized()
    V = (Matrix.Translation(Vector(projector.eye)) @ d.to_track_quat('-Z', 'Y').to_matrix().to_4x4()).inverted()
    return V, P @ V.inverted(), persp, int(round(w)), int(round(h))


def _part_for(context, loops, projector):
    """The part a drawn zone goes on: the active mesh when the outline covers it, else the zoned mesh it covers (the
    Target setting - Auto / Selected / Active - counts)."""
    from . import core_geometry as cg
    from . import cut_engine as ce
    from . import target_rules as tr
    allowed = tr.allowed(context)
    covered = [o for o in ce.auto_targets(context.view_layer, projector, loops)
               if o.type == 'MESH' and zoned(o.active_material) and (allowed is None or o.name in allowed)]
    ob = context.view_layer.objects.active
    if ob is not None and ob in covered:
        return ob
    if covered:
        return covered[0]
    raise cg.CutError('Lasso Zone: draw over a part with a Mech Shader or Creature Shader material (Mech / Creature '
                      'page: apply one first)')


def kind(context):
    return getattr(context.scene, 'mch_zone_kind', 'PAINT')


def perform(context, loops, projector, kind_=None):
    """The Lasso Zone tool's result: a Paint Zone or a Split Zone (``Scene.mch_zone_kind``) from the outline the
    lasso made - ``loops`` in region pixels (one outline, or several: Sketch islands and holes, Line's band),
    ``projector`` the view it was drawn in.  Returns the message."""
    from . import core_geometry as cg
    loops = as_loops(loops)
    if not loops:
        raise cg.CutError('Lasso Zone: the outline needs at least 3 points')
    kind_ = kind_ or kind(context)
    ob = _part_for(context, loops, projector)
    if kind_ == 'SPLIT' and not ms.is_mech(ob.active_material):
        raise cg.CutError('Split Zone: Mech Shader parts only (a creature: Paint)')
    vm, wm, persp, rw, rh = view_of(projector)
    through = bool(getattr(getattr(context.scene, 'mch_brush', None), 'through_mode', False))   # (top bar: Through)
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    try:
        if kind_ == 'SPLIT':
            zmat, n = split_zone(context, ob, loops, vm, wm, persp, rw, rh, through=through)
            msg = f'Split Zone: {n} faces of {ob.name} -> "{zmat.name}"'
        else:
            z = add_paint_zone(context, ob, loops, vm, wm, persp, rw, rh, through=through)
            msg = f'{z.name} on {ob.name}'
    except RuntimeError as ex:
        raise cg.CutError(f'Lasso Zone: {ex}') from ex
    vl = context.view_layer
    for o in list(context.selected_objects):
        if o != ob:
            o.select_set(False)
    ob.select_set(True)
    vl.objects.active = ob
    return msg


class MCH_OT_zone_tool(bpy.types.Operator):
    """Draw zones with the Lasso Zone tool - the shapes, Corners, Line, Sketch, Slow Line and Surface of the top bar
    (like Cut).  Esc: back to Select"""
    bl_idname = 'mch.zone_tool'
    bl_label = 'Lasso Zone'
    bl_options = {'REGISTER', 'UNDO'}
    kind: EnumProperty(items=KINDS, default='PAINT')

    def execute(self, context):
        if self.kind == 'SPLIT':
            ob = context.active_object
            mat = getattr(ob, 'active_material', None) if ob is not None else None
            if mat is not None and _cs().is_creature(mat):
                self.report({'WARNING'}, 'Split Zone: Mech Shader parts only (a creature: Paint Zone)')
                return {'CANCELLED'}
        context.scene.mch_zone_kind = self.kind
        from .workspace_ui import activate_mecha_tool
        try:
            activate_mecha_tool(context, 'ZONE')
        except (RuntimeError, KeyError, AttributeError) as ex:
            self.report({'WARNING'}, f'Lasso Zone: {ex}')
            return {'CANCELLED'}
        return {'FINISHED'}


def draw(layout, context):
    """The Lasso Zone tool's sidebar: what it makes (the zones' colours and sliders: the Mech / Creature page)."""
    if not hasattr(context.scene, 'mch_zone_kind'):
        return
    layout.row(align=True).prop(context.scene, 'mch_zone_kind', expand=True)
    brush = getattr(context.scene, 'mch_brush', None)
    if brush is not None:
        layout.prop(brush, 'through_mode', text='Through - the back faces too', toggle=True)
    col = layout.column(align=True)
    for line in ('Draw over a part with a Mech / Creature material:', 'every shape, Corners, Line, Sketch, Slow Line',
                 'and Surface of the top bar (like Cut).', 'A part with Mirror: the zone on both sides.',
                 'The zones\' colours and sliders: the Mech / Creature page.'):
        col.label(text=line)
    layout.operator('mch.side_page', text='Open the Mech Page').page = 'MATERIAL'


def tool_on(context, kind_=None):
    """The Lasso Zone tool in use (drawing ``kind_`` zones, when given)."""
    from . import tool_state as ts
    try:                                        # (its own Blender tool active: after Esc - Select - not lit)
        on = ts.native_tool_id(context) == ts.TOOL_BY_ID['ZONE'][5]
    except (AttributeError, KeyError, TypeError):
        return False
    return on and (kind_ is None or kind(context) == kind_)


# -----------------------------------------------------------------------------
# the lasso
# -----------------------------------------------------------------------------

_DRAW = {}


def _draw_lasso(op, context):
    import gpu
    from gpu_extras.batch import batch_for_shader
    pts = list(op.pts) + ([op.cursor] if op.cursor is not None and op.clicks else [])
    if len(pts) < 2:
        return
    try:
        sh = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
        sh.uniform_float('viewportSize', (context.region.width, context.region.height))
        sh.uniform_float('lineWidth', 2.0)
    except (ValueError, AttributeError):
        sh = gpu.shader.from_builtin('UNIFORM_COLOR')
    sh.uniform_float('color', (0.25, 0.6, 1.0, 0.95) if op.mode == 'PAINT' else (1.0, 0.55, 0.15, 0.95))
    batch = batch_for_shader(sh, 'LINE_LOOP', {'pos': [(x, y) for x, y in pts]})
    gpu.state.blend_set('ALPHA')
    batch.draw(sh)
    gpu.state.blend_set('NONE')


class MCH_OT_zone_lasso(bpy.types.Operator):
    """Draw a zone on the part: drag a lasso, or click its corners (Enter / Space / double-click: done; Esc: cancel).
    Paint: the zone's own paint (colour, roughness, metallic) projected from this view.  Split: edges cut along it, the
    faces inside a material of their own"""
    bl_idname = 'mch.zone_lasso'
    bl_label = 'Lasso Zone'
    bl_options = {'REGISTER', 'UNDO'}
    mode: EnumProperty(items=[('PAINT', 'Paint Zone', 'Its own paint, projected (the mesh as it is)'),
                              ('SPLIT', 'Split Zone', 'Edges cut along the lasso, a material of its own')],
                       default='PAINT')

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.type == 'MESH' and zoned(ob.active_material)

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, 'Zone: use it in the 3D view')
            return {'CANCELLED'}
        if self.mode == 'SPLIT' and not ms.is_mech(context.active_object.active_material):
            self.report({'WARNING'}, 'Split Zone: Mech Shader parts only (a creature: Paint Zone)')
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        self.pts, self.cursor, self.state, self.press = [], None, 'NONE', None
        self._region = context.region
        self._handle = bpy.types.SpaceView3D.draw_handler_add(_draw_lasso, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window.cursor_modal_set('CROSSHAIR')
        what = 'Paint Zone' if self.mode == 'PAINT' else 'Split Zone'
        context.area.header_text_set(f'{what}: drag a lasso, or click its corners (Enter / Space / double-click / the '
                                     'first point: done; Esc / right click: cancel)')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    @property
    def clicks(self):
        return self.state == 'CLICK'

    def _end(self, context):
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, AttributeError):
            pass
        context.window.cursor_modal_restore()
        if context.area is not None:
            context.area.header_text_set(None)
            context.area.tag_redraw()

    def _commit(self, context):
        self._end(context)
        region = self._region
        rv3d = region.data
        vm, wm, persp, rw, rh = _view(region, rv3d)
        ob = context.active_object
        try:
            if self.mode == 'PAINT':
                z = add_paint_zone(context, ob, self.pts, vm, wm, persp, rw, rh)
                self.report({'INFO'}, f'{z.name} on {ob.name}')
            else:
                zmat, n = split_zone(context, ob, self.pts, vm, wm, persp, rw, rh)
                self.report({'INFO'}, f'Split Zone: {n} faces -> "{zmat.name}"')
        except RuntimeError as ex:
            self.report({'WARNING'}, f'Zone: {ex}')
            return {'CANCELLED'}
        return {'FINISHED'}

    def modal(self, context, event):
        """NONE --press--> (drag past 6 px) DRAG --release--> done;  NONE / CLICK --release--> a corner (CLICK);
        CLICK: the first corner again / double-click / Enter / Space -> done."""
        if context.area is not None:
            context.area.tag_redraw()
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._end(context)
            return {'CANCELLED'}
        pos = (float(event.mouse_region_x), float(event.mouse_region_y))
        if event.type in {'RET', 'NUMPAD_ENTER', 'SPACE'} and event.value == 'PRESS' and len(self.pts) >= 3:
            return self._commit(context)
        if event.type == 'MOUSEMOVE':
            self.cursor = pos
            if self.state in {'PRESSED', 'DRAG'}:
                last = self.pts[-1] if self.pts else self.press
                far = (pos[0] - self.press[0]) ** 2 + (pos[1] - self.press[1]) ** 2 > 36.0
                if self.state == 'PRESSED' and far:
                    self.state = 'DRAG'
                    self.pts = [self.press]
                if self.state == 'DRAG' and (pos[0] - last[0]) ** 2 + (pos[1] - last[1]) ** 2 > 9.0:
                    self.pts.append(pos)
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE':
            if event.value == 'DOUBLE_CLICK' and self.clicks and len(self.pts) >= 3:
                return self._commit(context)
            if event.value == 'PRESS':
                self.press = pos
                if self.state == 'NONE':
                    self.state = 'PRESSED'
                return {'RUNNING_MODAL'}
            if event.value == 'RELEASE':
                if self.press is None:                  # (the release of the click that started it: not a corner)
                    return {'RUNNING_MODAL'}
                if self.state == 'DRAG':
                    if len(self.pts) >= 3:
                        return self._commit(context)
                    self.state, self.pts = 'NONE', []
                    return {'RUNNING_MODAL'}
                self.state = 'CLICK'
                if len(self.pts) >= 3 and (pos[0] - self.pts[0][0]) ** 2 + (pos[1] - self.pts[0][1]) ** 2 < 100.0:
                    return self._commit(context)               # (the first corner clicked again: closed)
                if not self.pts or (pos[0] - self.pts[-1][0]) ** 2 + (pos[1] - self.pts[-1][1]) ** 2 > 4.0:
                    self.pts.append(pos)
                return {'RUNNING_MODAL'}
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}                           # (orbit / zoom while drawing)
        return {'RUNNING_MODAL'}


class MCH_OT_zone_remove(bpy.types.Operator):
    """Remove this Paint Zone"""
    bl_idname = 'mch.zone_remove'
    bl_label = 'Remove Zone'
    bl_options = {'REGISTER', 'UNDO'}
    index: IntProperty(default=0)

    def execute(self, context):
        ob = context.active_object
        mat = getattr(ob, 'active_material', None) if ob is not None else None
        return {'FINISHED'} if zoned(mat) and remove_zone(mat, self.index) else {'CANCELLED'}


class MCH_OT_zone_slot(bpy.types.Operator):
    """Show this material of the part (its own settings on the Mech page)"""
    bl_idname = 'mch.zone_slot'
    bl_label = 'Material Slot'
    bl_options = {'REGISTER', 'UNDO'}
    index: IntProperty(default=0)

    def execute(self, context):
        ob = context.active_object
        if ob is None or not (0 <= self.index < len(ob.material_slots)):
            return {'CANCELLED'}
        ob.active_material_index = self.index
        return {'FINISHED'}


CLASSES = (MCH_PG_Zone, MCH_OT_zone_lasso, MCH_OT_zone_tool, MCH_OT_zone_remove, MCH_OT_zone_slot)


_WATCHING = [False]


@persistent
def _mirror_watch(scene, depsgraph=None):
    """0.24.95 A part with zones changed (its Mirror turned on / off, its axes, the part moved against its mirror
    object): the zones' mirror copies follow (``update_mirrors``: their matrices in place, made anew when needed)."""
    if _WATCHING[0] or depsgraph is None:
        return
    mats = []
    try:
        for u in depsgraph.updates:
            idb = u.id
            if not isinstance(idb, bpy.types.Object) or not (u.is_updated_transform or u.is_updated_geometry):
                continue
            ob = idb.original
            if ob.type != 'MESH':
                continue
            for sl in ob.material_slots:
                m = sl.material
                if m is not None and m not in mats and len(getattr(m, 'mch_zones', ())):
                    mats.append(m)
    except (ReferenceError, AttributeError):
        return
    if not mats:
        return
    _WATCHING[0] = True
    try:
        for m in mats:
            if m.get(SYM_KEY, '') != sym_key(m):
                update_mirrors(m)
    except (ReferenceError, AttributeError, RuntimeError) as ex:
        print('[Mecha Lab] zone mirror:', ex)
    finally:
        _WATCHING[0] = False


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    if _mirror_watch not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_mirror_watch)
    bpy.types.Material.mch_zones = CollectionProperty(type=MCH_PG_Zone)
    bpy.types.Material.mch_zone_parent = PointerProperty(type=bpy.types.Material)
    bpy.types.Material.mch_zone_follow = BoolProperty(
        name='Same Wear as the Part', default=False, update=_follow_update,
        description='This Split Zone\'s chips, scratches, dirt and rust follow the part\'s material (off: its own)')
    bpy.types.Scene.mch_zone_kind = EnumProperty(name='Zone', items=KINDS, default='PAINT',
                                                 description='What the Lasso Zone tool makes')


def unregister():
    if _mirror_watch in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_mirror_watch)
    for attr in ('mch_zones', 'mch_zone_parent', 'mch_zone_follow'):
        if hasattr(bpy.types.Material, attr):
            delattr(bpy.types.Material, attr)
    if hasattr(bpy.types.Scene, 'mch_zone_kind'):
        del bpy.types.Scene.mch_zone_kind
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
