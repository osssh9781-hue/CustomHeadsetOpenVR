"""0.24.241 Hair Cards (user: "헤어도 헤어카드 되게" - "털 -> 카드 + 텍스처 아틀라스"): the selected hair (Fur, Hair in a
Sculpted Shape, any hair Curves object) turned into game-ready hair cards.

* the strands (as they show, Geometry Nodes and all) are grouped into ``Cards`` clumps (k-means on root, middle and
  tip), each clump one card: a strip down the clump's mean strand, ``Segments`` long, as wide as the clump spreads
  (x ``Width``), narrower to the tip (``Tip Width``), lying flat on the skin (across = the body's surface at the
  root); ``Cross`` adds a second strip turned 90 degrees (fur / tufts seen from any side);
* a strand texture is drawn for them (``Atlas`` strips side by side in one picture, each a different bunch of
  strands: dense, sparse, wavy ...), white strands with alpha, darker at the root; every card gets one strip;
* the strands' colour (the fur's colour attribute / polypaint) is kept on the cards' points (``mch_card_col``), the
  material ``MCH Hair Card`` multiplies the picture by it (alpha: dithered, both sides drawn);
* the result ``<hair>_Cards`` sits where the hair is (on its body); the hair is hidden (kept).  Pressed again on the
  hair or on its cards: the cards are made again.
"""
import math

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty

CARDS_KEY = 'mch_cards_of'       # on the cards object: its hair's name
MAT = 'MCH Hair Card'
COL = 'mch_card_col'


class MCH_PG_HairCards(bpy.types.PropertyGroup):
    cards: IntProperty(name='Cards', default=300, min=4, max=20000,
                       description='How many cards (each one a clump of strands)')
    segments: IntProperty(name='Segments', default=8, min=2, max=32, description='Points along each card')
    width: FloatProperty(name='Width', default=1.0, min=0.1, max=5.0, description='Card width x the clump\'s spread')
    tip_width: FloatProperty(name='Tip Width', default=0.4, min=0.0, max=1.5, subtype='FACTOR',
                             description='The width at the tip, a share of the root\'s')
    cross: BoolProperty(name='Cross', default=False, description='A second card turned 90 degrees (fur seen from any side)')
    tiles: IntProperty(name='Atlas', default=8, min=1, max=16, description='Different strand strips in the texture')
    res: EnumProperty(name='Texture', default='1024', items=[(s, s, '') for s in ('512', '1024', '2048', '4096')],
                      description='The strand texture size in pixels')
    hide_hair: BoolProperty(name='Hide Hair', default=True, description='Hide the hair strands once the cards are made')


def settings(context):
    return getattr(context.scene, 'mch_hair_cards', None)


def is_cards(ob):
    return ob is not None and CARDS_KEY in ob


def hair_of(ob):
    """The hair object for ``ob`` (the hair itself, or the hair of its cards)."""
    if ob is None:
        return None
    if ob.type == 'CURVES':
        return ob
    if is_cards(ob):
        h = bpy.data.objects.get(ob[CARDS_KEY])
        return h if h is not None and h.type == 'CURVES' else None
    return None


def body_of(hair):
    try:
        if hair.data.surface is not None:
            return hair.data.surface
    except AttributeError:
        pass
    return hair.parent if hair.parent is not None and hair.parent.type == 'MESH' else None


# --- the strands ---------------------------------------------------------------------------------------------------

def read_strands(context, hair, k=12):
    """(N, k, 3) world positions, each strand resampled to ``k`` points evenly along its length; (N, 3) colours or
    None.  Strands with fewer than 2 points are left out."""
    dg = context.evaluated_depsgraph_get()
    cv = hair.evaluated_get(dg).data
    n = len(cv.points)
    if n == 0 or not len(cv.curves):
        return np.zeros((0, k, 3)), None
    P = np.empty(n * 3, np.float32)
    cv.attributes['position'].data.foreach_get('vector', P)
    P = P.reshape(-1, 3)
    M = np.array(hair.matrix_world, np.float64)
    P = P @ M[:3, :3].T + M[:3, 3]
    off = np.empty(len(cv.curves) + 1, np.int64)
    try:
        cv.curve_offset_data.foreach_get('value', off)
    except AttributeError:
        sizes = np.array([c.points_length for c in cv.curves], np.int64)
        off = np.concatenate([[0], np.cumsum(sizes)])
    col = None
    for name in ('mch_fur_col', 'color', 'Color'):
        a = cv.attributes.get(name)
        if a is not None and a.domain == 'POINT' and a.data_type in {'FLOAT_COLOR', 'BYTE_COLOR'}:
            c = np.empty(n * 4, np.float32)
            a.data.foreach_get('color', c)
            col = c.reshape(-1, 4)[:, :3]
            break
    sizes = np.diff(off)
    out, cols = [], []
    t = np.linspace(0.0, 1.0, k)
    if len(sizes) and (sizes == sizes[0]).all() and sizes[0] >= 2:       # (Fur: every strand the same count - fast)
        S = P.reshape(len(sizes), sizes[0], 3)
        seg = np.linalg.norm(np.diff(S, axis=1), axis=2)
        acc = np.concatenate([np.zeros((len(S), 1)), np.cumsum(seg, axis=1)], axis=1)
        tot = np.maximum(acc[:, -1:], 1e-12)
        u = acc / tot
        R = np.empty((len(S), k, 3))
        for d in range(3):
            R[:, :, d] = np.array([np.interp(t, u[i], S[i, :, d]) for i in range(len(S))])
        if col is not None:
            cols = col.reshape(len(sizes), sizes[0], 3).mean(axis=1)
        return R, (np.asarray(cols) if col is not None else None)
    for i in range(len(sizes)):
        a, b = off[i], off[i + 1]
        if b - a < 2:
            continue
        s = P[a:b]
        acc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(s, axis=0), axis=1))])
        if acc[-1] <= 1e-12:
            continue
        u = acc / acc[-1]
        out.append(np.stack([np.interp(t, u, s[:, d]) for d in range(3)], axis=1))
        if col is not None:
            cols.append(col[a:b].mean(axis=0))
    if not out:
        return np.zeros((0, k, 3)), None
    return np.array(out), (np.array(cols) if col is not None else None)


def clumps(R, n, iters=12, seed=0):
    """k-means of the strands (root, middle, tip) into ``n`` clumps.  Returns the label of each strand."""
    N = len(R)
    n = max(1, min(n, N))
    k = R.shape[1]
    F = np.concatenate([R[:, 0], R[:, k // 2] * 0.7, R[:, -1] * 0.5], axis=1).astype(np.float32)
    rng = np.random.default_rng(seed)
    sample = F if N <= 20000 else F[rng.choice(N, 20000, replace=False)]
    C = sample[rng.choice(len(sample), n, replace=False)].copy()

    def assign(X):
        lab = np.empty(len(X), np.int64)
        cc = (C * C).sum(1)
        for a in range(0, len(X), 4096):
            x = X[a:a + 4096]
            d = cc[None, :] - 2.0 * x @ C.T
            lab[a:a + 4096] = d.argmin(1)
        return lab

    for _i in range(iters):
        lab = assign(sample)
        for j in range(n):
            m = lab == j
            if m.any():
                C[j] = sample[m].mean(0)
            else:
                C[j] = sample[rng.integers(len(sample))]
    return assign(F)


def _normals_at(body, P):
    """The body's surface normal (world) nearest each point; outward from the points' middle when no body."""
    out = np.zeros((len(P), 3))
    if body is not None and body.type == 'MESH':
        try:
            from mathutils.bvhtree import BVHTree
            from mathutils import Vector
            dg = bpy.context.evaluated_depsgraph_get()
            ev = body.evaluated_get(dg)
            bvh = BVHTree.FromObject(ev, dg)
            Mi = body.matrix_world.inverted()
            N3 = body.matrix_world.to_3x3().inverted().transposed()
            for i, p in enumerate(P):
                hit = bvh.find_nearest(Mi @ Vector(p))
                if hit[1] is not None:
                    out[i] = tuple((N3 @ hit[1]).normalized())
        except (ValueError, RuntimeError, ReferenceError):
            pass
    bad = np.linalg.norm(out, axis=1) < 0.5
    if bad.any():
        c = P.mean(0)
        d = P[bad] - c
        ln = np.linalg.norm(d, axis=1, keepdims=True)
        out[bad] = np.where(ln > 1e-9, d / np.maximum(ln, 1e-12), [0.0, 0.0, 1.0])
    return out


def card_frames(R, labels, n, width=1.0, tip=0.4, body=None):
    """Per clump: (guide (k, 3), side (k, 3) unit, half width (k,), colour index list).  Clumps with no strand left out."""
    k = R.shape[1]
    guides, members = [], []
    for j in range(n):
        m = np.nonzero(labels == j)[0]
        if len(m):
            guides.append(R[m].mean(0))
            members.append(m)
    if not guides:
        return []
    G = np.array(guides)
    roots = G[:, 0]
    nrm = _normals_at(body, roots)
    lengths = np.linalg.norm(np.diff(G, axis=1), axis=2).sum(1)
    out = []
    taper = 1.0 - (1.0 - tip) * np.linspace(0.0, 1.0, k)
    for g, m, nr, L in zip(G, members, nrm, lengths):
        tan = np.gradient(g, axis=0)
        tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-12)
        side = np.cross(tan, nr)
        bad = np.linalg.norm(side, axis=1) < 1e-6
        if bad.any():
            side[bad] = np.cross(tan[bad], [0.0, 0.0, 1.0])
        side /= np.maximum(np.linalg.norm(side, axis=1, keepdims=True), 1e-12)
        if len(m) > 1:
            proj = ((R[m] - g[None]) * side[None]).sum(2)                 # (members, k): across the card
            spread = 2.0 * proj.std(0)
            half = max(float(np.median(spread)), 0.04 * L) * np.ones(k)
        else:
            half = 0.04 * L * np.ones(k)
        half = half * width * taper
        half[0] = max(half[0], 0.02 * L * width)
        out.append((g, side, nr, half, m))
    return out


# --- the mesh ------------------------------------------------------------------------------------------------------

def build_mesh(name, frames, tiles, colours=None, cross=False):
    """One strip per card (two when ``cross``), UVs into the atlas strips, the strands' colour on the points."""
    verts, faces, uvs, cols = [], [], [], []
    rng = np.random.default_rng(7)
    for ci, (g, side, nrm, half, m) in enumerate(frames):
        k = len(g)
        c = colours[m].mean(0) if colours is not None and len(m) else np.array([1.0, 1.0, 1.0])
        tile = int(rng.integers(tiles))
        flip = bool(rng.integers(2))
        dirs = [side]
        if cross:
            d2 = np.cross(side, np.gradient(g, axis=0))
            d2 /= np.maximum(np.linalg.norm(d2, axis=1, keepdims=True), 1e-12)
            dirs.append(d2)
        for d in dirs:
            base = len(verts)
            for i in range(k):
                verts.append(g[i] - d[i] * half[i])
                verts.append(g[i] + d[i] * half[i])
                cols.append(c)
                cols.append(c)
            for i in range(k - 1):
                a = base + 2 * i
                faces.append((a, a + 1, a + 3, a + 2))
                v0, v1 = i / (k - 1), (i + 1) / (k - 1)
                u0, u1 = (tile + (1.0 if flip else 0.0)) / tiles, (tile + (0.0 if flip else 1.0)) / tiles
                uvs.extend([(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    lay = me.uv_layers.new(name='UVMap')
    lay.data.foreach_set('uv', np.array(uvs, np.float32).ravel())
    ca = me.color_attributes.new(COL, 'FLOAT_COLOR', 'POINT')
    ca.data.foreach_set('color', np.c_[np.array(cols, np.float32), np.ones(len(cols), np.float32)].ravel())
    for p in me.polygons:
        p.use_smooth = True
    me.update()
    return me


# --- the strand texture ----------------------------------------------------------------------------------------------

def strand_atlas(name, res=1024, tiles=8, seed=3):
    """A picture of ``tiles`` strips side by side, each a bunch of strands root (bottom) to tip (top): white with
    alpha, darker toward the root.  Packed in the .blend."""
    H = int(res)
    tw = max(8, H // tiles)
    W = tw * tiles
    rng = np.random.default_rng(seed)
    A = np.zeros((H, W), np.float32)
    L = np.zeros((H, W), np.float32)
    y = np.linspace(0.0, 1.0, H)[:, None]
    for t in range(tiles):
        dense = 0.5 + 0.5 * ((t * 0.37) % 1.0)
        n = int(18 + 40 * dense)
        wave = 0.0 if t % 3 == 0 else (0.03 + 0.04 * (t % 2))
        cols = np.arange(tw, dtype=np.float32)[None, :]
        trans = np.ones((H, tw), np.float32)
        lum = np.zeros((H, tw), np.float32)
        for _s in range(n):
            x0 = rng.uniform(0.15, 0.85) * tw
            drift = rng.normal(0.0, 0.08) * tw
            amp = wave * tw * rng.uniform(0.5, 1.5)
            ph = rng.uniform(0, 2 * math.pi)
            ln = rng.uniform(0.7, 1.0)                                 # (some strands shorter than the card)
            x = x0 + drift * y + amp * np.sin(ph + y * rng.uniform(4.0, 9.0))
            x = tw / 2 + (x - tw / 2) * (1.0 - 0.45 * y)                  # (the bunch narrows to the tip)
            w = max(0.6, tw / 90.0) * (1.0 - 0.6 * y) + 0.35
            a = np.exp(-((cols - x) ** 2) / (2.0 * w * w))
            a = a * np.clip((ln - y) / 0.08, 0.0, 1.0)                   # (each strand ends softly)
            a = a * rng.uniform(0.55, 0.95)
            b = rng.uniform(0.75, 1.0)
            lum += a * b * trans
            trans *= 1.0 - a
        alpha = 1.0 - trans
        A[:, t * tw:(t + 1) * tw] = alpha
        L[:, t * tw:(t + 1) * tw] = np.where(alpha > 1e-4, lum / np.maximum(alpha, 1e-4), 0.0)
    shade = (0.55 + 0.45 * y) * np.ones((1, W), np.float32)              # (darker at the root)
    L = np.clip(L * shade, 0.0, 1.0)
    img = bpy.data.images.get(name)
    if img is not None and (img.size[0] != W or img.size[1] != H):
        bpy.data.images.remove(img)
        img = None
    if img is None:
        img = bpy.data.images.new(name, W, H, alpha=True)
    px = np.stack([L, L, L, A], axis=2).astype(np.float32)
    img.pixels.foreach_set(px.ravel())
    img.alpha_mode = 'STRAIGHT'
    img.pack()
    return img


def card_material(img):
    mat = bpy.data.materials.get(MAT + ' ' + img.name) or bpy.data.materials.new(MAT + ' ' + img.name)
    try:
        mat.use_nodes = True
    except AttributeError:
        pass
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    attr = nt.nodes.new('ShaderNodeAttribute')
    attr.attribute_name = COL
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0
    nt.links.new(tex.outputs['Color'], mix.inputs[6])
    nt.links.new(attr.outputs['Color'], mix.inputs[7])
    nt.links.new(mix.outputs[2], bsdf.inputs['Base Color'])
    nt.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
    bsdf.inputs['Roughness'].default_value = 0.45
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    for n, x in ((attr, -600), (tex, -600), (mix, -350), (bsdf, -100), (out, 250)):
        n.location.x = x
    attr.location.y = 250
    try:
        mat.surface_render_method = 'DITHERED'
    except (AttributeError, TypeError):
        try:
            mat.blend_method = 'HASHED'
        except (AttributeError, TypeError):
            pass
    mat.use_backface_culling = False
    return mat


# --- the whole thing -----------------------------------------------------------------------------------------------

def make(context, hair, st):
    """Cards for ``hair``.  Returns (cards object, message).  Raises RuntimeError."""
    R, colours = read_strands(context, hair, k=max(2, int(st.segments) + 1))
    if not len(R):
        raise RuntimeError(f'{hair.name} has no strands')
    labels = clumps(R, int(st.cards))
    frames = card_frames(R, labels, int(st.cards), st.width, st.tip_width, body_of(hair))
    img = strand_atlas(hair.name + '_CardStrands', int(st.res), int(st.tiles))
    if colours is None:
        colours = np.tile(_hair_colour(hair), (len(R), 1))
    me = build_mesh(hair.name + '_Cards', frames, int(st.tiles), colours, st.cross)
    me.materials.append(card_material(img))
    old = next((o for o in bpy.data.objects if is_cards(o) and o[CARDS_KEY] == hair.name), None)
    if old is not None:
        om = old.data
        old.data = me
        if om.users == 0:
            bpy.data.meshes.remove(om)
        ob = old
        ob.hide_set(False)
    else:
        ob = bpy.data.objects.new(hair.name + '_Cards', me)
        for coll in hair.users_collection:
            coll.objects.link(ob)
        if not ob.users_collection:
            context.scene.collection.objects.link(ob)
        ob[CARDS_KEY] = hair.name
        body = body_of(hair)
        if body is not None:                          # (follows the body like the hair; points are in world space)
            ob.parent = body
            ob.matrix_parent_inverse = body.matrix_world.inverted()
    if st.hide_hair:
        hair.hide_set(True)
    for o in list(context.selected_objects):
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    msg = (f'Hair Cards: {len(R):,} strands -> {len(frames):,} cards ({len(me.polygons):,} faces), '
           f'texture {img.size[0]}x{img.size[1]} ({int(st.tiles)} strips)')
    return ob, msg


def _hair_colour(hair):
    for m in hair.data.materials:
        if m is None or not m.node_tree:
            continue
        for n in m.node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                return np.array(n.inputs['Base Color'].default_value[:3])
            if n.type == 'BSDF_HAIR_PRINCIPLED':
                try:
                    return np.array(n.inputs['Color'].default_value[:3])
                except KeyError:
                    pass
    return np.array([0.25, 0.16, 0.09])


class MCH_OT_hair_cards(bpy.types.Operator):
    """Turn the selected hair into hair cards: clumps of strands -> flat textured cards (a strand texture made for
    them, the hair's colour kept).  The hair is hidden, not removed"""
    bl_idname = 'mch.hair_cards'
    bl_label = 'Make Hair Cards'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hair_of(context.active_object) is not None and settings(context) is not None

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        hair = hair_of(context.active_object)
        try:
            _ob, msg = make(context, hair, settings(context))
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


def draw(layout, context):
    """The box in the Fur window (hair or its cards selected)."""
    st = settings(context)
    ob = context.active_object
    hair = hair_of(ob)
    if st is None or hair is None:
        return
    from . import panel_capture as pc
    box = layout.box()
    box.label(text='HAIR CARDS  (game hair)', icon='STRANDS')
    r = pc.primary(box.row(align=True))
    r.scale_y = 1.3
    r.operator('mch.hair_cards', text='Remake Hair Cards' if is_cards(ob) else 'Make Hair Cards', icon='MESH_PLANE')
    col = box.column(align=True)
    r = col.row(align=True)
    r.prop(st, 'cards')
    r.prop(st, 'segments')
    r = col.row(align=True)
    r.prop(st, 'width')
    r.prop(st, 'tip_width')
    r = col.row(align=True)
    r.prop(st, 'tiles')
    r.prop(st, 'res', text='')
    r = col.row(align=True)
    r.prop(st, 'cross', toggle=True)
    r.prop(st, 'hide_hair', toggle=True)


CLASSES = (MCH_PG_HairCards, MCH_OT_hair_cards)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_hair_cards = PointerProperty(type=MCH_PG_HairCards)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_hair_cards'):
        del bpy.types.Scene.mch_hair_cards
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
