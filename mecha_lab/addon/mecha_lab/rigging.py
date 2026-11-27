"""0.24.241 Rig (user: "리깅 툴" - 사람 / 크리쳐 몸, 메카 (딱딱한 부품), 꼬리 / 촉수 / 머리카락 체인).

Body (Human / Quadruped)
    Select the body mesh (standing on the ground, facing -Y; a quadruped's head toward -Y), Make Rig: the joints are
    found on the mesh (the middle of its cross-sections at the usual heights: hips, chest, neck, shoulders, elbows,
    wrists, hips, knees, ankles - measured, not guessed: an arm in T or A pose, long legs or short), an armature
    ``<body>_Rig`` is built (deform bones + IK: a hand / foot target and an elbow / knee pole for every limb, the
    pole angle chosen so the rest pose does not move), the body bound to it (automatic weights; where Blender's
    heat weights fail - an open or broken mesh - every point gets the nearest bones by distance instead).  Edit
    Bones moves the joints (Blender's own edit mode), Bind again after.

Mecha (rigid parts)
    Select the parts, Make Rig: one bone per part (from its middle along its longest side), all under a root;
    a part already parented to another keeps that order.  Each part rides its bone rigidly (bone parent, no
    weights).  With the Rig tool, click a part: its joint (the bone's start) moves to where you clicked - into the
    middle of the part along the view (the halfway point between where the ray goes in and out).  Link to Active:
    the selected parts' bones under the active part's bone.

Chain (tail, tentacle, hair lock)
    Select the long mesh (or a curve), Make Rig: ``Bones`` bones along it (the middle of its cross-sections from the
    thick end to the thin end), the mesh bound to them.  With an armature selected too the chain goes into it,
    under its bone nearest the chain's root.  Jiggle: during playback the chain lags and swings after the
    movement (Stiffness, Damping).
"""
import json
import math

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty
from mathutils import Matrix, Vector

RIG_KEY = 'mch_rig'            # on the armature: 'BODY' / 'QUAD' / 'MECHA' / 'CHAIN'
BODY_KEY = 'mch_rig_body'      # on the armature: the bound body's name
PART_KEY = 'mch_rig_bone'      # on a mecha part: its bone's name
SPRING_KEY = 'mch_spring'      # on the armature: {chain root bone: [stiffness, damping]} (as a string list)

KINDS = [('BODY', 'Human', 'A standing body (feet on the ground, facing -Y): spine, arms, legs, IK'),
         ('QUAD', 'Quadruped', 'A four-legged body (head toward -Y): spine, neck, head, four legs, tail, IK'),
         ('MECHA', 'Mecha', 'Rigid parts: one bone per selected part, the parts ride their bones'),
         ('MGUIDE', 'Mecha Guides', 'Mecha parts: drag guide lines through them - ONE bone for each part a line '
                                    'crosses, joints where the line goes from part to part; Leg / IK lines get IK'),
         ('NAMED', 'Mecha Names', 'Mecha parts named Pelvis, Torso, Head, UpperArm.L, Forearm.L, Hand.L, Thigh.R ... '
                                  '(or 골반 몸통 머리 위팔 ...): bones by the names, joints where they meet, IK on '
                                  'the arms and legs'),
         ('CHAIN', 'Chain', 'A tail / tentacle / hair lock: bones along it, Jiggle'),
         ('AUTO', 'Auto Creature', 'Any creature: its legs found where it touches the ground (any number), its tails, '
                                   'arms and tentacles as swaying chains - no template'),
         ('GUIDE', 'Guides', 'Draw the bones yourself: drag lines over the creature (through the middle of its body), '
                             'the first one the body; lines ending on the ground are legs with IK')]


class MCH_PG_Rig(bpy.types.PropertyGroup):
    kind: EnumProperty(name='Rig', items=KINDS, default='BODY')
    ik: BoolProperty(name='IK', default=True, description='Hand / foot targets and elbow / knee poles on the limbs')
    bind: BoolProperty(name='Bind', default=True, description='Bind the mesh to the rig (weights) right away')
    bones: IntProperty(name='Bones', default=8, min=2, max=64, description='Bones in a chain')
    jiggle: BoolProperty(name='Jiggle', default=False, description='The chain lags and swings after the movement '
                         'during playback')
    stiffness: FloatProperty(name='Stiffness', default=0.25, min=0.01, max=1.0, subtype='FACTOR',
                             description='How hard the chain pulls back to its pose')
    damping: FloatProperty(name='Damping', default=0.25, min=0.0, max=0.95, subtype='FACTOR',
                           description='How fast the swing dies down')
    legs: EnumProperty(name='Legs', default='NORMAL', items=[
        ('NORMAL', 'Normal Legs', 'Thigh, shin, foot (a knee bending forward)'),
        ('REVERSE', 'Reverse Legs', 'Digitigrade: thigh, shin, a long hock bending back, foot (IK on all three)')])
    fingers: BoolProperty(name='Fingers', default=True, description='Three bones a finger; turn the first bone: the '
                          'finger curls')
    auto_joints: BoolProperty(name='Auto Joints', default=True,
                              description='Mecha: the order and the joints from where the parts touch; the legs (parts '
                              'down to one on the ground) get IK')
    face: BoolProperty(name='Face Bones', default=True, description='Jaw, eyes (looking at a target), brows, lips')
    mguide_kind: EnumProperty(name='Line Kind', default='AUTO', items=[
        ('AUTO', 'Auto', 'The first line the body; a line ending on the ground a leg (IK); the others plain'),
        ('BODY', 'Body', 'The body: the bones everything hangs on'),
        ('LEG', 'Leg', 'A leg: IK on its last part (knee in front), walked by Auto Animation'),
        ('IK', 'IK', 'An arm / a claw: IK on its last part (elbow behind)'),
        ('BONES', 'Plain', 'Plain bones, no IK')])
    seamless: BoolProperty(name='Seamless', default=True,
                           description='Mecha Names: the parts bend by weights the same on both sides of every cut - '
                           'a body cut into parts keeps its cuts shut in any pose (off: each part rides its bone stiff, '
                           'like hard mecha armour)')
    axis: EnumProperty(name='Turn Axis', default='X', items=[('X', 'X', 'Turns round the world X axis'),
                                                            ('Y', 'Y', 'Turns round the world Y axis'),
                                                            ('Z', 'Z', 'Turns round the world Z axis')])
    lo: FloatProperty(name='Turn From', default=-45.0, min=-360.0, max=360.0, description='The smallest turn (degrees)')
    hi: FloatProperty(name='Turn To', default=45.0, min=-360.0, max=360.0, description='The largest turn (degrees)')
    hatch: FloatProperty(name='Open Angle', default=110.0, min=1.0, max=360.0,
                         description='How far a hatch opens (degrees) - it turns from 0 to this only')
    guide_kind: EnumProperty(name='Line Kind', default='AUTO', items=[
        ('AUTO', 'Auto', 'The first line the body; a line ending on the ground a leg; the others plain bones'),
        ('BODY', 'Body', 'The body / spine / neck / head: the bones everything hangs on'),
        ('LEG', 'Leg', 'A leg: IK on its foot, walked by Auto Animation'),
        ('IK', 'IK', 'Bones with IK at the end (an arm, a claw, a jaw): grab the end, the rest follows; not walked'),
        ('BONES', 'Plain Bones', 'Plain bones, no IK (a tail, a tentacle: they sway in Auto Animation)'),
        ('EYE', 'Eye', 'Draw a circle round an eye (on the surface): an eye bone in it, looking at one shared target'),
        ('MOUTH', 'Mouth', 'Draw along the lips (on the surface): small lip bones along the line - the lower ones move '
                           'with the jaw'),
        ('FINGER', 'Finger', 'Draw along a finger (knuckle to tip): 3 bones on the hand; Finger Curl / Spread move all '
                             'the fingers at once')])
    ik_chain: IntProperty(name='IK Bones', default=0, min=0, max=16,
                          description='How many bones the IK bends, counted up from the selected end bone (0: the whole '
                          'limb, up to where it branches off)')


def settings(context):
    return getattr(context.scene, 'mch_rig', None)


def is_rig(ob):
    return ob is not None and ob.type == 'ARMATURE' and RIG_KEY in ob


def rig_of(ob):
    """The rig ``ob`` belongs to (itself, its armature modifier's, its bone parent's), or None."""
    if ob is None:
        return None
    if is_rig(ob):
        return ob
    if ob.parent is not None and is_rig(ob.parent):
        return ob.parent
    for m in getattr(ob, 'modifiers', ()):
        if m.type == 'ARMATURE' and is_rig(m.object):
            return m.object
    return None


# --- the mesh, measured --------------------------------------------------------------------------------------------

def world_points(context, ob):
    dg = context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        co = np.empty(len(me.vertices) * 3, np.float64)
        me.vertices.foreach_get('co', co)
    finally:
        ev.to_mesh_clear()
    co = co.reshape(-1, 3)
    M = np.array(ob.matrix_world)
    return co @ M[:3, :3].T + M[:3, 3]


def _centre(V, mask, fallback):
    return V[mask].mean(0) if mask.sum() >= 3 else np.asarray(fallback, np.float64)


def _slab(V, axis, at, half):
    return np.abs(V[:, axis] - at) < half


def trace(V, mask, a, b, steps=24, radius=None):
    """0.24.242 (user: a posed creature - bent arms, striding legs) the middle line of a limb from ``a`` to ``b``:
    step by step toward ``b``, each step pulled to the middle of the mesh points around it (the limb's tube), so the
    line bends where the limb bends.  Returns the points (steps + 1)."""
    P = V[mask]
    a, b = np.asarray(a, float), np.asarray(b, float)
    L = float(np.linalg.norm(b - a))
    if len(P) < 10 or L < 1e-6:
        return np.array([a + (b - a) * t for t in np.linspace(0, 1, steps + 1)])
    r = radius or 0.16 * L
    path, p = [a], a
    for i in range(1, steps):
        guess = p + (b - p) / (steps - i + 1)
        m = np.linalg.norm(P - guess, axis=1) < r
        p = P[m].mean(0) if m.sum() >= 4 else guess
        path.append(p)
    path.append(b)
    return np.array(path)


def bends(path, k=1, gap=3, lo=0.2, hi=0.8):
    """The ``k`` sharpest bends of a line (index, degrees), sharpest first, at least ``gap`` points apart, looked for
    between ``lo`` and ``hi`` of the way along (a limb's own joints - not the shoulder / hip where it starts)."""
    n = len(path)
    ang = np.zeros(n)
    sp = max(2, n // 7)                            # (measured over a stretch: a muscle's bulge is no joint)
    for i in range(max(sp, int(lo * (n - 1))), min(n - sp, int(hi * (n - 1)) + 1)):
        u, v = path[i] - path[i - sp], path[i + sp] - path[i]
        lu, lv = np.linalg.norm(u), np.linalg.norm(v)
        if lu > 1e-9 and lv > 1e-9:
            ang[i] = math.degrees(math.acos(max(-1.0, min(1.0, float(u @ v) / (lu * lv)))))
    out = []
    for i in np.argsort(-ang):
        if ang[i] <= 0:
            break
        if all(abs(i - j) >= gap for j, _a in out):
            out.append((int(i), float(ang[i])))
        if len(out) == k:
            break
    return out


def body_joints(V, legs='NORMAL'):
    """The joints of a standing body (dict name -> point), the +X side's ('.L'); the -X side mirrored."""
    lo, hi = V.min(0), V.max(0)
    H = hi[2] - lo[2]
    x0 = 0.5 * (lo[0] + hi[0])
    z = lambda f: lo[2] + f * H
    core = np.abs(V[:, 0] - x0) < 0.11 * H
    J = {}
    for name, f in (('hips', 0.5), ('spine', 0.6), ('chest', 0.7), ('neck', 0.815), ('head', 0.875)):
        c = _centre(V, _slab(V, 2, z(f), 0.025 * H) & core, (x0, 0.5 * (lo[1] + hi[1]), z(f)))
        J[name] = np.array([x0, c[1], z(f)])
    J['head_top'] = np.array([x0, J['head'][1], hi[2]])
    side = V[:, 0] > x0
    sh = np.array([x0 + 0.1 * H, J['chest'][1], z(0.795)])
    ring = _slab(V, 2, sh[2], 0.04 * H) & side & (np.abs(V[:, 0] - sh[0]) < 0.05 * H)
    sh = _centre(V, ring, sh)
    sh[0] = max(sh[0], x0 + 0.07 * H)
    # the hand: the point farthest from the shoulder outside the torso and the legs (T pose: out to the side; A pose:
    # hanging beside the thighs) - the legs stay inside 0.12 H of the middle
    out = side & (V[:, 0] - x0 > 0.12 * H) & (V[:, 2] > z(0.3))
    if out.sum() < 3:
        out = side & (V[:, 0] - x0 > 0.08 * H) & (V[:, 2] > z(0.3))
    cand = V[out]
    tip = cand[np.argmax(np.linalg.norm(cand - sh, axis=1))] if len(cand) else np.array([x0 + 0.4 * H, sh[1], z(0.8)])
    arm = tip - sh
    L = np.linalg.norm(arm)
    d = arm / max(L, 1e-9)
    hand_len = min(0.1 * H, 0.3 * L)
    wrist = sh + d * (L - hand_len)
    elbow = sh + d * (0.5 * (L - hand_len))

    def near(p, r, msk):
        m = (np.linalg.norm(V - p, axis=1) < r) & msk
        return _centre(V, m, p)
    elbow = near(elbow, 0.04 * H, out | (side & (V[:, 0] - x0 > 0.1 * H)))
    wrist = near(wrist, 0.03 * H, out)
    amask = side & (V[:, 2] > z(0.25)) & (V[:, 0] - x0 > 0.09 * H)     # (not the torso beside a hanging arm)
    path = trace(V, amask, sh, wrist, radius=0.04 * H)         # 0.24.242 a bent arm: the elbow where it bends
    bd = bends(path, 1, lo=0.3, hi=0.85)
    if bd and bd[0][1] > 35.0:                     # (a hanging arm's slight bend / the shoulder's bulge: no)
        elbow = path[bd[0][0]]
    J.update({'shoulder.L': np.array([x0 + 0.025 * H, J['chest'][1], sh[2] + 0.01 * H]), 'upper_arm.L': sh,
              'forearm.L': elbow, 'hand.L': wrist, 'hand_tip.L': tip})
    leg = side & (V[:, 0] - x0 > 0.005 * H) & (V[:, 0] - x0 < 0.12 * H)
    th = _centre(V, _slab(V, 2, z(0.42), 0.02 * H) & leg, (x0 + 0.07 * H, J['hips'][1], z(0.42)))
    hip = np.array([x0 + 0.8 * (th[0] - x0), th[1], z(0.465)])
    mid = (np.abs(V[:, 0] - x0) < 0.015 * H) & (V[:, 2] > z(0.3)) & (V[:, 2] < z(0.65))
    if mid.any():                                  # 0.24.242 the crotch measured: the hips just above it
        crotch = float(V[mid][:, 2].min())
        hz = crotch + 0.02 * H
        ring = _slab(V, 2, hz + 0.02 * H, 0.015 * H) & leg
        c_ = _centre(V, ring, (hip[0], hip[1], hz))
        if hz > hip[2]:                            # (only when the legs part higher up than a person's)
            hip = np.array([x0 + 0.8 * (c_[0] - x0), c_[1], hz])
    knee = _centre(V, _slab(V, 2, z(0.275), 0.02 * H) & leg, (th[0], th[1], z(0.275)))
    za = z(0.04) if legs == 'REVERSE' else z(0.07)          # (a digitigrade ankle sits low, near the toes)
    ankle = _centre(V, _slab(V, 2, za, 0.015 * H) & leg, (th[0], th[1], za))
    feet = leg & (V[:, 2] < z(0.06))
    toe = V[feet][np.argmin(V[feet][:, 1])] if feet.any() else ankle + np.array([0, -0.12 * H, 0])
    toe = np.array([ankle[0], toe[1], z(0.015)])
    lmask = leg & (V[:, 2] < hip[2] + 0.03 * H)
    path = trace(V, lmask, hip, ankle, steps=30, radius=0.05 * H)                 # 0.24.242 the leg's middle line: its bends
    if legs == 'REVERSE':
        bd = sorted(bends(path, 2, gap=4, lo=0.2, hi=0.93), key=lambda x: x[0])
        if len(bd) == 2 and min(a for _i, a in bd) > 8.0:
            knee, hock = path[bd[0][0]], path[bd[1][0]]
        else:
            knee, hock = path[int(0.42 * (len(path) - 1))], path[int(0.75 * (len(path) - 1))]
        J['hock.L'] = hock
    else:
        bd = bends(path, 1)
        if bd and bd[0][1] > 25.0:
            knee = path[bd[0][0]]
        else:
            knee[1] = min(knee[1], 0.5 * (hip[1] + ankle[1]) - 0.005 * H)   # (straight: bent forward a little)
    J.update({'thigh.L': hip, 'shin.L': knee, 'foot.L': ankle, 'toe.L': toe})
    return J, H, x0


FINGERS = ('thumb', 'index', 'middle', 'ring', 'pinky')


def hand_fingers(V, side, wrist, tip, H):
    """0.24.242 (user: "손가락 움직이는 거") the fingers of one hand: {name: [base, joint, joint, tip]} and the knuckle
    point.  Measured on the mesh: the hand's length runs wrist -> tip, its width is the widest spread across it (the
    thumb side toward -Y); four fingers spread over the palm width at the knuckles, each as long as the mesh reaches
    there; the thumb from near the wrist to its farthest point; every joint centred in the finger's thickness."""
    d = tip - wrist
    L = float(np.linalg.norm(d))
    if L < 1e-6:
        return {}, wrist
    d = d / L
    rel = V - wrist
    s = rel @ d
    near = side & (np.linalg.norm(rel, axis=1) < 1.25 * L) & (s > -0.05 * L)
    P, sP = V[near], s[near]
    if len(P) < 20:
        return {}, wrist + d * 0.45 * L
    flat = (P - wrist) - sP[:, None] * d
    mid = (sP > 0.25 * L) & (sP < 0.75 * L)
    X = flat[mid] if mid.sum() > 10 else flat
    _u, _s, vt = np.linalg.svd(X - X.mean(0), full_matrices=False)
    w = vt[0] - d * (vt[0] @ d)
    w /= max(np.linalg.norm(w), 1e-9)
    if w[1] > 0:                                   # (the thumb side toward the front, -Y)
        w = -w
    n = np.cross(d, w)
    wv, nv = flat @ w, flat @ n
    palm = (sP > 0.2 * L) & (sP < 0.45 * L)
    if palm.sum() < 8:
        palm = sP > 0
    lo, hi = np.percentile(wv[palm], 5), np.percentile(wv[palm], 95)
    W = max(hi - lo, 0.02 * H)
    wc = 0.5 * (lo + hi)
    sk = 0.58 * L                                  # (the knuckles: about 3 / 5 down the hand, measured on a body)
    knuckle = wrist + d * sk + w * wc

    def centred(p, r):
        rel_p = P - p
        m = np.linalg.norm(rel_p, axis=1) < r
        if m.sum() >= 3:
            off = (P[m] - p) @ n
            return p + n * float(np.mean(off))
        return p
    out = {}
    # the four fingers: the far half of the hand split across its width into four bunches (1-D k-means)
    far = sP > sk + 0.35 * (float(sP.max()) - sk)
    fw = np.sort(wv[far & (wv < wc + 0.45 * W)]) if far.any() else np.array([])
    if len(fw) >= 8:
        cen = np.percentile(fw, [87.5, 62.5, 37.5, 12.5])
        for _i in range(12):
            lab = np.argmin(np.abs(fw[:, None] - cen[None, :]), axis=1)
            cen = np.array([fw[lab == j].mean() if (lab == j).any() else cen[j] for j in range(4)])
        cen = np.sort(cen)[::-1]
    else:
        cen = wc + W * np.array([0.33, 0.11, -0.11, -0.33])
    for name, wf in zip(FINGERS[1:], cen):
        m = (np.abs(wv - wf) < W / 8) & (sP > sk)
        end = float(sP[m].max()) if m.any() else L
        base = wrist + d * sk + w * wf
        nb = float(np.mean(nv[(np.abs(wv - wf) < W / 6) & (np.abs(sP - sk) < 0.1 * L)])) if \
            ((np.abs(wv - wf) < W / 6) & (np.abs(sP - sk) < 0.1 * L)).any() else 0.0
        pts = [wrist + d * (sk + (end - sk) * t) + w * wf + n * nb for t in (0.0, 0.45, 0.75, 1.0)]
        out[name] = [centred(q, W / 7) for q in pts[:3]] + [pts[3]]
    side_t = (wv > wc + 0.3 * W) & (sP < 0.75 * L)
    if side_t.sum() >= 3:
        cand = P[side_t]
        t_tip = cand[np.argmax(np.linalg.norm(cand - (wrist + w * wc), axis=1))]
    else:
        t_tip = wrist + d * 0.6 * L + w * (wc + 0.6 * W)
    t_base = wrist + d * 0.12 * L + w * (wc + 0.25 * W)
    out['thumb'] = [centred(t_base + (t_tip - t_base) * t, W / 7) if t < 1 else t_tip for t in (0.0, 0.4, 0.72, 1.0)]
    out['_n'] = n                                  # (the back of the hand: the fingers' roll, so they curl one way)
    return out, knuckle


def face_marks(context, body, J, H, x0):
    """0.24.242 (user: "얼굴까지") where the face's bones go, from the neck joint to the top of the head: the eyes,
    brows, mouth, chin - each on the front of the face (a ray from the front), set a little inside it."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    dg = context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg)
    bvh = BVHTree.FromObject(ev, dg)
    Mi = body.matrix_world.inverted()
    M = body.matrix_world
    zn = float(J['neck'][2])
    zt = float(J['head_top'][2])
    span = max(zt - zn, 1e-3)
    yc = float(J['head'][1])

    def front(x, z, inset):
        o = Mi @ Vector((x, yc - 2.0 * span, z))
        dv = (Mi.to_3x3() @ Vector((0, 1, 0))).normalized()
        hit = bvh.ray_cast(o, dv)
        if hit[0] is None:
            return np.array([x, yc - 0.35 * span, z])
        p = M @ hit[0]
        return np.array([x, p.y + inset * span, z])
    z = lambda f: zn + f * span
    F = {}
    F['eye.L'] = front(x0 + 0.096 * span, z(0.68), 0.06)
    F['brow.L'] = front(x0 + 0.1 * span, z(0.75), 0.015)
    F['lip.L'] = front(x0 + 0.072 * span, z(0.46), 0.015)
    F['lip.upper'] = front(x0, z(0.485), 0.01)
    F['lip.lower'] = front(x0, z(0.435), 0.01)
    F['chin'] = front(x0, z(0.33), 0.02)
    F['jaw'] = np.array([x0, yc, z(0.52)])
    return F, span


def mirror(p, x0):
    return np.array([2 * x0 - p[0], p[1], p[2]])


def quad_joints(V):
    """The joints of a four-legged body facing -Y (dict, '.L' = +X side; F / B = front / back)."""
    lo, hi = V.min(0), V.max(0)
    H = hi[2] - lo[2]
    Lg = hi[1] - lo[1]
    x0 = 0.5 * (lo[0] + hi[0])
    y = lambda f: lo[1] + f * Lg
    z = lambda f: lo[2] + f * H
    torso = V[:, 2] > z(0.45)
    J = {}
    spine = []
    for f in (0.85, 0.65, 0.45, 0.3):                  # (pelvis ... chest, toward the head)
        c = _centre(V, _slab(V, 1, y(f), 0.04 * Lg) & torso, (x0, y(f), z(0.7)))
        spine.append(np.array([x0, y(f), c[2]]))
    J['pelvis'], J['spine'], J['chest'], J['neck'] = spine
    head = V[V[:, 1] < y(0.12)]
    hc = head.mean(0) if len(head) else np.array([x0, y(0.05), z(0.85)])
    J['head'] = np.array([x0, y(0.14), max(hc[2], spine[-1][2])])
    J['head_tip'] = np.array([x0, lo[1], hc[2]])
    tail = V[V[:, 1] > y(0.95)]
    J['tail_tip'] = np.array([x0, hi[1], tail[:, 2].mean() if len(tail) else spine[0][2]])
    side = V[:, 0] > x0 + 0.02 * (hi[0] - lo[0])
    for tag, (fa, fb) in (('F', (0.0, 0.5)), ('B', (0.5, 1.0))):
        m = side & (V[:, 1] >= y(fa)) & (V[:, 1] <= y(fb)) & (V[:, 2] < z(0.3))
        c = V[m].mean(0) if m.sum() >= 3 else np.array([x0 + 0.15 * H, y(0.5 * (fa + fb)), z(0.2)])
        col = side & (np.linalg.norm(V[:, :2] - c[:2], axis=1) < 0.12 * H)
        top = np.array([c[0], c[1], z(0.6)])
        knee = _centre(V, _slab(V, 2, z(0.32), 0.03 * H) & col, (c[0], c[1], z(0.32)))
        ankle = _centre(V, _slab(V, 2, z(0.08), 0.03 * H) & col, (c[0], c[1], z(0.08)))
        # 0.24.244 a dead straight leg: IK cannot tell which way to bend it - the knee a little toward the pole
        knee[1] = min(knee[1], 0.5 * (top[1] + ankle[1]) - 0.02 * H)
        toe = np.array([ankle[0], ankle[1] - 0.08 * H, lo[2]])
        J[f'leg{tag}.L'] = top
        J[f'shin{tag}.L'] = knee
        J[f'foot{tag}.L'] = ankle
        J[f'toe{tag}.L'] = toe
    return J, H, x0


# --- armature building ------------------------------------------------------------------------------------------------

def _new_armature(context, name, at=None):
    arm = bpy.data.armatures.new(name)
    ob = bpy.data.objects.new(name, arm)
    context.scene.collection.objects.link(ob)
    ob.show_in_front = True
    arm.display_type = 'OCTAHEDRAL'
    return ob


_BUSY = [0]          # our own edit-mode visits (not the user's): the watcher leaves them alone


class _Edit:
    """Edit mode on an armature object for the ``with`` block (the selection and mode put back after)."""

    def __init__(self, context, ob):
        self.c, self.ob = context, ob

    def __enter__(self):
        _BUSY[0] += 1
        c = self.c
        self.mode = c.mode
        self.active = c.view_layer.objects.active
        self.sel = list(c.selected_objects)
        if c.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        self.hidden = self.ob.hide_get()
        self.ob.hide_set(False)
        for o in self.sel:
            o.select_set(False)
        self.ob.select_set(True)
        c.view_layer.objects.active = self.ob
        bpy.ops.object.mode_set(mode='EDIT')
        return self.ob.data.edit_bones

    def __exit__(self, *exc):
        try:
            return self._exit()
        finally:
            _BUSY[0] -= 1

    def _exit(self):
        bpy.ops.object.mode_set(mode='OBJECT')
        self.ob.select_set(False)
        self.ob.hide_set(self.hidden)
        for o in self.sel:
            try:
                o.select_set(True)
            except (ReferenceError, RuntimeError):
                pass
        try:
            self.c.view_layer.objects.active = self.active
        except (ReferenceError, RuntimeError):
            pass
        return False


def _bone(ebs, name, head, tail, parent=None, connect=False, deform=True, roll_to=None):
    b = ebs.new(name)
    b.head = Vector(head)
    b.tail = Vector(tail)
    if (b.tail - b.head).length < 1e-5:
        b.tail = b.head + Vector((0, 0, 0.01))
    if parent is not None:
        b.parent = ebs[parent] if isinstance(parent, str) else parent
        b.use_connect = connect and (b.parent.tail - b.head).length < 1e-6
    b.use_deform = deform
    if roll_to is not None:
        b.align_roll(Vector(roll_to))
    return b


def build_body(context, body, quad=False, ik=True, fingers=True, face=True, legs='NORMAL'):
    """The armature for ``body`` (not bound).  Returns the armature object."""
    V = world_points(context, body)
    J, H, x0 = quad_joints(V) if quad else body_joints(V, legs)
    FG, FC = {}, None
    if not quad and fingers:
        side = (V[:, 0] > x0) & (V[:, 0] - x0 > 0.12 * H)     # (outside the torso and the legs: the hand only)
        if side.sum() < 50:
            side = V[:, 0] > x0
        FG, knuckle = hand_fingers(V, side, J['hand.L'], J['hand_tip.L'], H)
        if FG:
            J['hand_tip.L'] = knuckle
    if not quad and face:
        FC, span = face_marks(context, body, J, H, x0)
    ob = _new_armature(context, body.name + '_Rig')
    ob[RIG_KEY] = 'QUAD' if quad else 'BODY'
    ob[BODY_KEY] = body.name
    ob['mch_x0'] = float(x0)
    with _Edit(context, ob) as ebs:
        if quad:
            root = _bone(ebs, 'root', (x0, J['pelvis'][1], V[:, 2].min()), (x0, J['pelvis'][1] - 0.2 * H, V[:, 2].min()),
                         deform=False)
            _bone(ebs, 'pelvis', J['pelvis'], J['spine'], root)
            _bone(ebs, 'spine', J['spine'], J['chest'], 'pelvis', True)
            _bone(ebs, 'chest', J['chest'], J['neck'], 'spine', True)
            _bone(ebs, 'neck', J['neck'], J['head'], 'chest', True)
            _bone(ebs, 'head', J['head'], J['head_tip'], 'neck', True)
            tail = [J['pelvis'] + (J['tail_tip'] - J['pelvis']) * f for f in np.linspace(0, 1, 5)]
            prev = 'pelvis'
            for i in range(4):
                _bone(ebs, f'tail.{i + 1:02d}', tail[i], tail[i + 1], prev, i > 0)
                prev = f'tail.{i + 1:02d}'
            for side, mir in (('L', False), ('R', True)):
                for tag, par in (('F', 'chest'), ('B', 'pelvis')):
                    p = {k: (mirror(J[f'{k}{tag}.L'], x0) if mir else J[f'{k}{tag}.L']) for k in ('leg', 'shin', 'foot', 'toe')}
                    _bone(ebs, f'leg{tag}.{side}', p['leg'], p['shin'], par, roll_to=(0, -1, 0))
                    _bone(ebs, f'shin{tag}.{side}', p['shin'], p['foot'], f'leg{tag}.{side}', True, roll_to=(0, -1, 0))
                    _bone(ebs, f'foot{tag}.{side}', p['foot'], p['toe'], f'shin{tag}.{side}', True)
                    if ik:
                        _limb_ik_bones(ebs, f'shin{tag}.{side}', f'foot{tag}.{side}', p['foot'], p['toe'], p['shin'],
                                       (0, -0.4 * H, 0), 'root')
        else:
            g = V[:, 2].min()
            root = _bone(ebs, 'root', (x0, J['hips'][1], g), (x0, J['hips'][1] - 0.15 * H, g), deform=False)
            _bone(ebs, 'hips', J['hips'], J['spine'], root)
            _bone(ebs, 'spine', J['spine'], J['chest'], 'hips', True)
            _bone(ebs, 'chest', J['chest'], J['neck'], 'spine', True)
            _bone(ebs, 'neck', J['neck'], J['head'], 'chest', True)
            _bone(ebs, 'head', J['head'], J['head_top'], 'neck', True)
            for side, mir in (('L', False), ('R', True)):
                p = {k: (mirror(v, x0) if mir else v) for k, v in J.items() if k.endswith('.L')}
                q = lambda k: p[k + '.L']
                _bone(ebs, f'shoulder.{side}', q('shoulder'), q('upper_arm'), 'chest')
                _bone(ebs, f'upper_arm.{side}', q('upper_arm'), q('forearm'), f'shoulder.{side}', True, roll_to=(0, 1, 0))
                _bone(ebs, f'forearm.{side}', q('forearm'), q('hand'), f'upper_arm.{side}', True, roll_to=(0, 1, 0))
                _bone(ebs, f'hand.{side}', q('hand'), q('hand_tip'), f'forearm.{side}', True)
                _bone(ebs, f'thigh.{side}', q('thigh'), q('shin'), 'hips', roll_to=(0, -1, 0))
                if 'hock.L' in J:                            # 0.24.242 reverse (digitigrade) legs: a third bone
                    _bone(ebs, f'shin.{side}', q('shin'), q('hock'), f'thigh.{side}', True, roll_to=(0, -1, 0))
                    _bone(ebs, f'hock.{side}', q('hock'), q('foot'), f'shin.{side}', True, roll_to=(0, -1, 0))
                    _bone(ebs, f'foot.{side}', q('foot'), q('toe'), f'hock.{side}', True)
                    lower_leg = f'hock.{side}'
                else:
                    _bone(ebs, f'shin.{side}', q('shin'), q('foot'), f'thigh.{side}', True, roll_to=(0, -1, 0))
                    _bone(ebs, f'foot.{side}', q('foot'), q('toe'), f'shin.{side}', True)
                    lower_leg = f'shin.{side}'
                if ik:
                    _limb_ik_bones(ebs, f'forearm.{side}', f'hand.{side}', q('hand'), q('hand_tip'), q('forearm'),
                                   (0, 0.35 * H, 0), 'root')
                    _limb_ik_bones(ebs, lower_leg, f'foot.{side}', q('foot'), q('toe'), q('shin'),
                                   (0, -0.35 * H, 0), 'root')
                nb = FG.get('_n', np.array([0.0, 0.0, 1.0]))
                nb = np.array([-nb[0], nb[1], nb[2]]) if mir else nb
                for fname, pts in FG.items():               # 0.24.242 three bones a finger, on the hand
                    if fname.startswith('_'):
                        continue
                    pts = [mirror(pp, x0) if mir else pp for pp in pts]
                    prev = f'hand.{side}'
                    for i in range(3):
                        prev = _bone(ebs, f'{fname}.{i + 1:02d}.{side}', pts[i], pts[i + 1], prev, i > 0,
                                     roll_to=tuple(nb)).name
            if FC is not None:                              # 0.24.242 the face
                fw = 0.02 * span
                _bone(ebs, 'jaw', FC['jaw'], FC['chin'], 'head')
                _bone(ebs, 'chin', FC['chin'], FC['chin'] + np.array([0, -fw, -fw]), 'jaw')
                _bone(ebs, 'lip.lower', FC['lip.lower'], FC['lip.lower'] + np.array([0, -fw, 0]), 'jaw')
                _bone(ebs, 'lip.upper', FC['lip.upper'], FC['lip.upper'] + np.array([0, -fw, 0]), 'head')
                for side, mir in (('L', False), ('R', True)):
                    m_ = (lambda pp: mirror(pp, x0)) if mir else (lambda pp: pp)
                    e = m_(FC['eye.L'])
                    _bone(ebs, f'eye.{side}', e, e + np.array([0, -2 * fw, 0]), 'head', deform=False)
                    b_ = m_(FC['brow.L'])
                    _bone(ebs, f'brow.{side}', b_, b_ + np.array([0, -fw, 0]), 'head')
                    l_ = m_(FC['lip.L'])
                    _bone(ebs, f'lip.{side}', l_, l_ + np.array([0, -fw, 0]), 'head')
                c = 0.5 * (FC['eye.L'] + mirror(FC['eye.L'], x0)) + np.array([0, -3.0 * span, 0])
                _bone(ebs, 'eyes_target', c, c + np.array([0, 0, 0.2 * span]), 'head', deform=False)
    pbs = ob.pose.bones
    for side in 'LR':                                   # 0.24.242 turning a finger's first bone curls it all
        for fname in [f for f in FG if not f.startswith('_')]:
            first = f'{fname}.01.{side}'
            for i in (2, 3):
                pb = pbs.get(f'{fname}.{i:02d}.{side}')
                if pb is None:
                    continue
                c = pb.constraints.new('COPY_ROTATION')
                c.name = 'Curl'
                c.target, c.subtarget = ob, first
                c.owner_space = c.target_space = 'LOCAL'
                c.mix_mode = 'ADD'
    for side in 'LR':
        pb = pbs.get(f'eye.{side}')
        if pb is not None:
            c = pb.constraints.new('DAMPED_TRACK')
            c.target, c.subtarget = ob, 'eyes_target'
    if ik:
        ob['mch_pole_off'] = {}
        leg_low = 'hock' if 'hock.L' in J else 'shin'
        pairs = ([(f'shin{t}.{s}', f'foot{t}.{s}') for t in 'FB' for s in 'LR'] if quad else
                 [(f'forearm.{s}', f'hand.{s}') for s in 'LR'] + [(f'{leg_low}.{s}', f'foot.{s}') for s in 'LR'])
        offs = {}
        for lower, end in pairs:
            b = ob.data.bones.get(lower + '_pole')
            if b is not None:
                offs[lower] = list(b.head_local - ob.data.bones[lower].head_local)
        ob['mch_pole_off'] = offs
        for lower, end in pairs:
            _limb_ik(context, ob, lower, end, 3 if lower.startswith('hock') else 2)
        controls(ob)
    return ob


WIDGETS = 'MCH Rig Widgets'


def _widget(name, circles):
    """A wire shape for the controls (kept in a hidden collection).  ``circles``: [(centre, axis u, axis v, r)]."""
    ob = bpy.data.objects.get(name)
    if ob is not None:
        return ob
    verts, edges = [], []
    for c, u, v, r in circles:
        base = len(verts)
        for i in range(32):
            a = 2 * math.pi * i / 32
            verts.append(tuple(np.array(c) + r * (math.cos(a) * np.array(u) + math.sin(a) * np.array(v))))
            edges.append((base + i, base + (i + 1) % 32))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, edges, [])
    ob = bpy.data.objects.new(name, me)
    coll = bpy.data.collections.get(WIDGETS)
    if coll is None:
        coll = bpy.data.collections.new(WIDGETS)
        coll.hide_viewport = True
        coll.hide_render = True
    coll.objects.link(ob)
    return ob


def controls(arm):
    """0.24.242 (user: "IK 가 발이랑 손 안에 들어가 있어서 잡히는 게 불편") the controls drawn big and coloured, out of
    the mesh: a ring round each wrist, a ring round each foot (lying flat), a ball for each elbow / knee pole, a
    ring for the eyes' target."""
    X, Y, Z, O = (1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, 0)
    ring_wrist = _widget('WGT_mch_ring', [(O, X, Z, 0.9)])
    ring_foot = _widget('WGT_mch_foot', [((0, 0.45, 0), X, Y, 0.85)])
    ball = _widget('WGT_mch_ball', [(O, X, Y, 1.4), (O, X, Z, 1.4), (O, Y, Z, 1.4)])
    for pb in arm.pose.bones:
        n = pb.name
        if n.endswith('_ik'):
            pb.custom_shape = ring_foot if (n.startswith('foot') or '.foot_ik' in n) else ring_wrist
            col = 'THEME01'
        elif n.endswith('_pole'):
            pb.custom_shape = ball
            col = 'THEME09'
        elif n == 'eyes_target':
            pb.custom_shape = ring_wrist
            col = 'THEME03'
        else:
            continue
        try:
            pb.custom_shape_wire_width = 3.0
        except AttributeError:
            pass
        try:
            pb.color.palette = col
            pb.bone.color.palette = col
        except (AttributeError, TypeError):
            pass


def sync_ik(context, arm):
    """0.24.242 After Edit Bones: the IK targets back on their hands / feet, the poles back off their elbows / knees
    (the bones you moved keep their places).  Returns how many were moved."""
    offs = arm.get('mch_pole_off') or {}
    n = 0
    with _Edit(context, arm) as ebs:
        for b in list(ebs):
            if b.name.endswith('_ik') and b.name[:-3] in ebs:
                src = ebs[b.name[:-3]]
                if (b.head - src.head).length > 1e-6 or (b.tail - src.tail).length > 1e-6:
                    b.head, b.tail, b.roll = src.head.copy(), src.tail.copy(), src.roll
                    n += 1
            elif b.name.endswith('_pole') and b.name[:-5] in ebs:
                lower = ebs[b.name[:-5]]
                off = Vector(offs.get(b.name[:-5], (0.0, 0.3, 0.0)))
                want = lower.head + off
                if (b.head - want).length > 1e-6:
                    t = b.tail - b.head
                    b.head = want
                    b.tail = want + t
                    n += 1
    return n


def mirror_lr(context, arm, from_side='L'):
    """0.24.242 (user: "뼈 배치하면 미러로 반대쪽 배치") every '.L' bone's place copied to its '.R' bone, mirrored
    across the body's middle (or the other way round).  Returns how many."""
    x0 = float(arm.get('mch_x0', 0.0))
    to = 'R' if from_side == 'L' else 'L'
    n = 0
    with _Edit(context, arm) as ebs:
        for b in list(ebs):
            if not b.name.endswith('.' + from_side):
                continue
            o = ebs.get(b.name[:-1] + to)
            if o is None:
                continue
            o.head = Vector((2 * x0 - b.head.x, b.head.y, b.head.z))
            o.tail = Vector((2 * x0 - b.tail.x, b.tail.y, b.tail.z))
            o.roll = -b.roll
            n += 1
    return n


def _limb_ik_bones(ebs, lower, end, at, tip, mid, pole_off, root):
    """The IK target (a copy of the end bone, free) and the pole (off the middle joint) for one limb."""
    t = ebs.new(end + '_ik')
    t.head, t.tail = Vector(at), Vector(tip)
    t.roll = ebs[end].roll
    t.parent = ebs[root]
    t.use_deform = False
    p = ebs.new(lower + '_pole')
    p.head = Vector(mid) + Vector(pole_off)
    p.tail = p.head + Vector((0, 0, 0.05 * Vector(pole_off).length + 1e-3))
    p.parent = ebs[root]
    p.use_deform = False


def _limb_ik(context, ob, lower, end, chain=2):
    """IK on ``lower`` (``chain`` bones) to ``end``_ik with the pole; the end bone turns with its target.  The pole
    angle that keeps the rest pose still is chosen."""
    pbs = ob.pose.bones
    c = pbs[lower].constraints.new('IK')
    c.target, c.subtarget = ob, end + '_ik'
    c.pole_target, c.pole_subtarget = ob, lower + '_pole'
    c.chain_count = chain
    cr = pbs[end].constraints.new('COPY_ROTATION')
    cr.target, cr.subtarget = ob, end + '_ik'
    ups = []
    b = pbs[lower].parent
    for _i in range(chain - 1):
        if b is None:
            break
        ups.append(b)
        b = b.parent
    best = None

    def err_at(deg):
        c.pole_angle = math.radians(deg)
        context.view_layer.update()
        return sum((pb.matrix.to_translation() - pb.bone.matrix_local.to_translation()).length +
                   (pb.matrix.col[1].xyz - pb.bone.matrix_local.col[1].xyz).length +
                   (pb.matrix.col[0].xyz - pb.bone.matrix_local.col[0].xyz).length
                   for pb in ups + [pbs[lower]])
    for deg in (-90.0, 90.0, 0.0, 180.0, -45.0, 45.0, -135.0, 135.0):
        e = err_at(deg)
        if best is None or e < best[0]:
            best = (e, deg)
    for step, span in ((3.0, 24.0), (0.5, 3.0), (0.1, 0.5)):    # 0.24.242 finer: the rest pose really still
        c0 = best[1]
        for k in np.arange(-span, span + 1e-9, step):
            e = err_at(c0 + float(k))
            if e < best[0]:
                best = (e, c0 + float(k))
    c.pole_angle = math.radians(best[1])
    context.view_layer.update()
    return best


# --- binding -------------------------------------------------------------------------------------------------------

def bind(context, mesh, arm):
    """Weights for ``mesh`` from ``arm``'s deform bones (Blender's automatic weights; nearest bones where they
    fail).  Returns 'auto' / 'nearest'."""
    for m in [m for m in mesh.modifiers if m.type == 'ARMATURE']:
        mesh.modifiers.remove(m)
    deform = [b.name for b in arm.data.bones if b.use_deform]
    for vg in [vg for vg in mesh.vertex_groups if vg.name in deform]:
        mesh.vertex_groups.remove(vg)
    keep_active, keep_sel = context.view_layer.objects.active, list(context.selected_objects)
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for o in keep_sel:
        o.select_set(False)
    mw = mesh.matrix_world.copy()
    mesh.select_set(True)
    arm.select_set(True)
    context.view_layer.objects.active = arm
    how = 'auto'
    try:
        with context.temp_override(active_object=arm, object=arm, selected_objects=[mesh, arm],
                                   selected_editable_objects=[mesh, arm]):
            bpy.ops.object.parent_set(type='ARMATURE_AUTO', keep_transform=True)
    except RuntimeError:
        how = 'nearest'
    mesh.matrix_world = mw
    if how == 'auto' and _unweighted(mesh, deform) > 0.02:
        how = 'nearest'
    if how == 'nearest':
        if mesh.parent is not arm:
            mesh.parent = arm
            mesh.matrix_parent_inverse = arm.matrix_world.inverted()
            mesh.matrix_world = mw
        nearest_weights(context, mesh, arm)
        if not any(m.type == 'ARMATURE' for m in mesh.modifiers):
            m = mesh.modifiers.new('Armature', 'ARMATURE')
            m.object = arm
    for o in list(context.selected_objects):
        o.select_set(False)
    for o in keep_sel:
        try:
            o.select_set(True)
        except (ReferenceError, RuntimeError):
            pass
    context.view_layer.objects.active = keep_active
    if arm.get('mch_face_w'):                        # 0.24.259 drawn eyes / lips take their skin
        from . import rig_guides
        rig_guides.apply_face_weights(mesh, arm)
    return how


def _unweighted(mesh, names):
    idx = {vg.index for vg in mesh.vertex_groups if vg.name in names}
    if not idx or not len(mesh.data.vertices):
        return 1.0
    miss = sum(1 for v in mesh.data.vertices if not any(g.group in idx and g.weight > 1e-4 for g in v.groups))
    return miss / len(mesh.data.vertices)


def nearest_weights(context, mesh, arm, falloff=4.0):
    """Every point weighted to its two nearest deform bones (by distance to the bone segment)."""
    bones = [b for b in arm.data.bones if b.use_deform]
    if not bones:
        return
    M = np.array(arm.matrix_world)
    H = np.array([tuple(b.head_local) for b in bones]) @ M[:3, :3].T + M[:3, 3]
    T = np.array([tuple(b.tail_local) for b in bones]) @ M[:3, :3].T + M[:3, 3]
    me = mesh.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    W = np.array(mesh.matrix_world)
    P = co.reshape(-1, 3) @ W[:3, :3].T + W[:3, 3]
    D = np.empty((len(P), len(bones)))
    for j in range(len(bones)):
        d = T[j] - H[j]
        t = np.clip(((P - H[j]) @ d) / max(d @ d, 1e-12), 0.0, 1.0)
        D[:, j] = np.linalg.norm(P - (H[j] + t[:, None] * d), axis=1)
    order = np.argsort(D, axis=1)[:, :2]
    groups = {}
    for b in bones:
        groups[b.name] = mesh.vertex_groups.get(b.name) or mesh.vertex_groups.new(name=b.name)
    for i in range(len(P)):
        a, b = order[i]
        da, db = D[i, a], D[i, b] if len(bones) > 1 else 1e9
        wa = 1.0 / max(da, 1e-6) ** falloff
        wb = 1.0 / max(db, 1e-6) ** falloff if len(bones) > 1 else 0.0
        s = wa + wb
        groups[bones[a].name].add([i], wa / s, 'REPLACE')
        if wb / s > 0.02:
            groups[bones[b].name].add([i], wb / s, 'REPLACE')


# --- mecha -----------------------------------------------------------------------------------------------------------

def _part_axis(context, ob):
    V = world_points(context, ob)
    if not len(V):
        p = np.array(ob.matrix_world.translation)
        return p, p + np.array([0, 0, 0.1])
    c = 0.5 * (V.min(0) + V.max(0))
    X = V - V.mean(0)
    try:
        _u, s, vt = np.linalg.svd(X[:: max(1, len(X) // 5000)], full_matrices=False)
        d = vt[0]
    except np.linalg.LinAlgError:
        d = np.array([0, 0, 1.0])
    proj = X @ d
    if d[2] < 0 or (abs(d[2]) < 1e-6 and d[0] < 0):
        d = -d
    half = 0.5 * (proj.max() - proj.min()) if len(proj) else 0.1
    return c, c + d * max(half, 1e-3)


def _contacts(context, parts, tol_share=0.012):
    """0.24.247 which parts touch (or sink into) which: {(a, b): (contact middle (world), how many points)}."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    pts, trees, boxes = {}, {}, {}
    dg = context.evaluated_depsgraph_get()
    allV = []
    for p in parts:
        ev = p.evaluated_get(dg)
        me = ev.to_mesh()
        try:
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get('co', co)
            me.calc_loop_triangles()
            tri = np.empty(len(me.loop_triangles) * 3, np.int64)
            me.loop_triangles.foreach_get('vertices', tri)
        finally:
            ev.to_mesh_clear()
        M = np.array(p.matrix_world)
        W = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
        allV.append(W)
        trees[p.name] = BVHTree.FromPolygons([tuple(v) for v in W], tri.reshape(-1, 3).tolist()) if len(tri) else None
        step = max(1, len(W) // 2500)
        pts[p.name] = W[::step]
        boxes[p.name] = (W.min(0), W.max(0))
    V = np.concatenate(allV) if allV else np.zeros((1, 3))
    tol = tol_share * float(np.ptp(V, axis=0).max())
    out = {}
    names = [p.name for p in parts]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            la, ha = boxes[a]
            lb, hb = boxes[b]
            if (la > hb + tol).any() or (lb > ha + tol).any():
                continue
            touch = []
            for x, y in ((a, b), (b, a)):
                t = trees[y]
                if t is None:
                    continue
                ly, hy = boxes[y]
                for v in pts[x]:
                    if (v < ly - tol).any() or (v > hy + tol).any():
                        continue
                    hit = t.find_nearest(Vector(v))
                    if hit[0] is not None and hit[3] < tol:
                        touch.append(v)
                    elif hit[0] is not None and (Vector(v) - hit[0]).dot(hit[1]) < 0:
                        touch.append(v)                 # (inside the other part: sunk into it)
            if len(touch) >= 3:
                out[(a, b)] = (np.mean(touch, axis=0), len(touch))
    return out, V


def mecha_tree(context, parts):
    """0.24.247 (user: 메카 리깅 - 자동으로) the parts' order and joints from how they touch: the biggest part is the
    body; from it outward each part hangs on the part it touches nearer the body, its joint the middle of where they
    touch.  Returns (parent {name: parent name or None}, joint {name: point}, body name, all points)."""
    contacts, V = _contacts(context, parts)
    vol = {}
    for p in parts:
        W = world_points(context, p)
        vol[p.name] = float(np.prod(np.maximum(np.ptp(W, axis=0), 1e-4))) if len(W) else 0.0
    body = max(vol, key=vol.get)
    adj = {p.name: [] for p in parts}
    for (a, b), (c, n) in contacts.items():
        adj[a].append((b, c, n))
        adj[b].append((a, c, n))
    parent, joint = {body: None}, {}
    q = [body]
    while q:
        u = q.pop(0)
        for v, c, n in sorted(adj[u], key=lambda t: -t[2]):
            if v not in parent:
                parent[v] = u
                joint[v] = c
                q.append(v)
    return parent, joint, body, V


def build_mecha(context, parts, auto=True):
    parts = [p for p in parts if p.type == 'MESH']
    if not parts:
        raise RuntimeError('Select the mecha parts (meshes)')
    if auto and len(parts) > 1:
        return build_mecha_auto(context, parts)
    axes = {p.name: _part_axis(context, p) for p in parts}
    allp = np.array([a for a, _b in axes.values()])
    lo = min(world_points(context, p)[:, 2].min() for p in parts)
    ob = _new_armature(context, 'Mecha_Rig')
    ob[RIG_KEY] = 'MECHA'
    names = {}
    with _Edit(context, ob) as ebs:
        c = allp.mean(0)
        _bone(ebs, 'root', (c[0], c[1], lo), (c[0], c[1] - 0.25 * max(1e-3, np.ptp(allp[:, 1]) + np.ptp(allp[:, 2])), lo),
              deform=False)
        for p in parts:
            h, t = axes[p.name]
            names[p.name] = _bone(ebs, p.name, h, t, 'root').name
        for p in parts:                                        # (an object parent among the parts: kept as the order)
            par = p.parent
            while par is not None and par.name not in names:
                par = par.parent
            if par is not None:
                ebs[names[p.name]].parent = ebs[names[par.name]]
    for p in parts:
        attach(p, ob, names[p.name])
    return ob


def build_mecha_auto(context, parts):
    """0.24.247 the mecha rig from how its parts touch: joints where they meet, the order body -> outward, the legs
    (chains of parts that end on the ground) with IK on their feet; parts touching nothing hang on the root."""
    parent, joint, body, V = mecha_tree(context, parts)
    ground = float(V[:, 2].min())
    H = float(np.ptp(V[:, 2])) or 1.0
    size = float(np.ptp(V, axis=0).max()) or 1.0
    byname = {p.name: p for p in parts}
    kids = {n: [m for m, par in parent.items() if par == n] for n in byname}
    far, low = {}, {}
    for p in parts:
        W = world_points(context, p)
        far[p.name] = W
        low[p.name] = float(W[:, 2].min()) if len(W) else 0.0
    heads, tails = {}, {}
    for p in parts:
        W = far[p.name]
        if p.name == body or p.name not in parent:
            c = 0.5 * (W.min(0) + W.max(0))
            heads[p.name] = c
            tails[p.name] = c + np.array([0, 0, 0.25 * max(1e-3, np.ptp(W[:, 2]))])
            continue
        h = joint[p.name]
        ks = kids[p.name]
        if ks:                                    # (toward its own child's joint: a limb segment)
            t = np.mean([joint[k] for k in ks], axis=0)
        else:                                     # (a tip: toward its farthest point)
            t = W[np.argmax(np.linalg.norm(W - h, axis=1))]
        if np.linalg.norm(t - h) < 1e-4 * size:
            t = h + np.array([0, 0, 0.05 * size])
        heads[p.name], tails[p.name] = h, t
    # the legs: from the body's child down to a tip part that stands on the ground
    legs = []
    for n in byname:
        if n == body or kids[n] or n not in parent or low[n] - ground > 0.04 * H:
            continue
        chain = [n]
        while parent.get(chain[-1]) not in (None, body):
            chain.append(parent[chain[-1]])
        if len(chain) >= 2:
            legs.append(chain[::-1])              # (hip ... foot)
    # a dead straight leg: IK cannot tell which way to bend - its knee joint a hair forward (the parts stay put)
    for chain in legs:
        if len(chain) >= 3:
            a, f = heads[chain[1]], heads[chain[-1]]
            ab = f - heads[chain[0]]
            for k in chain[1:-1]:
                p_ = heads[k]
                t = float((p_ - heads[chain[0]]) @ ab / max(ab @ ab, 1e-12))
                off = p_ - (heads[chain[0]] + t * ab)
                if np.linalg.norm(off) < 0.02 * np.linalg.norm(ab):
                    heads[k] = p_ + np.array([0, -0.03 * np.linalg.norm(ab), 0])
                    pk = parent[k]
                    if pk in tails and pk != body:
                        tails[pk] = heads[k]
    ob = _new_armature(context, 'Mecha_Rig')
    ob[RIG_KEY] = 'MECHA'
    ob['mch_body_bone'] = body
    ob['mch_x0'] = float(heads[body][0])
    names = {}
    with _Edit(context, ob) as ebs:
        c = heads[body]
        _bone(ebs, 'root', (c[0], c[1], ground), (c[0], c[1] - 0.15 * size, ground), deform=False)
        order = [body] + [n for n in parent if n != body] + [n for n in byname if n not in parent]
        for n in order:
            names[n] = _bone(ebs, n, heads[n], tails[n], 'root').name
        for n in order:
            par = parent.get(n)
            if par is not None:
                ebs[names[n]].parent = ebs[names[par]]
        feet = []
        for chain in legs:
            foot, lower = chain[-1], chain[-2]
            f = ebs[names[foot]]
            mid = heads[lower] if len(chain) == 2 else heads[chain[-2]]
            ab = heads[foot] - heads[chain[0]]
            tt = float((mid - heads[chain[0]]) @ ab / max(ab @ ab, 1e-12))
            off = mid - (heads[chain[0]] + tt * ab)
            if np.linalg.norm(off) < 1e-6:
                off = np.array([0.0, -1.0, 0.0])
            off = off / np.linalg.norm(off) * 0.5 * float(np.linalg.norm(ab))
            _limb_ik_bones(ebs, names[lower], names[foot], f.head.copy(), f.tail.copy(), mid, tuple(off), 'root')
            feet.append(names[foot])
    for p in parts:
        attach(p, ob, names[p.name])
    offs, lens = {}, []
    for chain in legs:
        lower, foot = names[chain[-2]], names[chain[-1]]
        b = ob.data.bones.get(lower + '_pole')
        if b is not None:
            offs[lower] = list(b.head_local - ob.data.bones[lower].head_local)
    ob['mch_pole_off'] = offs
    for chain in legs:
        lower, foot = names[chain[-2]], names[chain[-1]]
        n_ik = max(1, min(3, len(chain) - 1))
        err, _d = _limb_ik(context, ob, lower, foot, n_ik)
        if n_ik > 2 and err > 0.01:
            pb = ob.pose.bones[lower]
            for c_ in [c_ for c_ in pb.constraints if c_.type == 'IK']:
                pb.constraints.remove(c_)
            for c_ in [c_ for c_ in ob.pose.bones[foot].constraints if c_.type == 'COPY_ROTATION']:
                ob.pose.bones[foot].constraints.remove(c_)
            _limb_ik(context, ob, lower, foot, 2)
        lens.append(float(np.linalg.norm(heads[chain[-1]] - heads[chain[0]])))
    ob['mch_legs'] = json.dumps([names[c[-1]] for c in legs])
    ob['mch_leg_len'] = float(min(lens)) if lens else 0.3 * H
    controls(ob)
    return ob


def attach(part, arm, bone):
    """``part`` rides ``bone`` rigidly, staying where it is."""
    mw = part.matrix_world.copy()
    part.parent = arm
    part.parent_type = 'BONE'
    part.parent_bone = bone
    part[PART_KEY] = bone
    b = arm.data.bones[bone]
    tail = arm.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))
    part.matrix_parent_inverse = tail.inverted()
    part.matrix_world = mw


def set_pivot(context, part, point):
    """``part``'s joint (its bone's start) to ``point`` (world); its bone keeps its direction and length."""
    arm = rig_of(part)
    bone = part.get(PART_KEY)
    if arm is None or bone not in arm.data.bones:
        raise RuntimeError('This part is not in a mecha rig')
    kids = [o for o in bpy.data.objects if o.parent is arm and o.get(PART_KEY)]
    keep = {o.name: o.matrix_world.copy() for o in kids}
    Mi = arm.matrix_world.inverted()
    with _Edit(context, arm) as ebs:
        b = ebs[bone]
        d = b.tail - b.head
        b.head = Mi @ Vector(point)
        b.tail = b.head + d
    for o in kids:
        attach(o, arm, o[PART_KEY])
        o.matrix_world = keep[o.name]


def _keep_parts(arm):
    return {o.name: o.matrix_world.copy() for o in bpy.data.objects if o.parent is arm and o.get(PART_KEY)}


def _reattach(arm, keep):
    for name, mw in keep.items():
        o = bpy.data.objects.get(name)
        if o is not None and o.get(PART_KEY) in arm.data.bones:
            attach(o, arm, o[PART_KEY])
            o.matrix_world = mw


AXES = {'X': (1.0, 0.0, 0.0), 'Y': (0.0, 1.0, 0.0), 'Z': (0.0, 0.0, 1.0)}


def limit_turn(context, part, axis, lo_deg, hi_deg):
    """0.24.242 (user: "돌아가는 영역 제한") ``part`` turns only round the world ``axis`` through its joint, between
    ``lo_deg`` and ``hi_deg`` (its bone is pointed along the axis: the turn is its own Y; the others locked).
    ``axis`` 'FREE': any way again, no limits."""
    arm = rig_of(part)
    bone = part.get(PART_KEY)
    if arm is None or bone not in arm.data.bones:
        raise RuntimeError('Select a part of a mecha rig')
    pb = arm.pose.bones[bone]
    for c in [c for c in pb.constraints if c.name == 'MCH Limit']:
        pb.constraints.remove(c)
    pb.rotation_mode = 'XYZ'
    pb.rotation_euler = (0.0, 0.0, 0.0)
    if axis == 'FREE':
        pb.lock_rotation = (False, False, False)
        return
    keep = _keep_parts(arm)
    Mi = arm.matrix_world.inverted().to_3x3()
    with _Edit(context, arm) as ebs:
        b = ebs[bone]
        L = max(b.length, 1e-3)
        b.tail = b.head + (Mi @ Vector(AXES[axis])).normalized() * L
        b.roll = 0.0
    _reattach(arm, keep)
    pb = arm.pose.bones[bone]
    pb.rotation_mode = 'XYZ'
    pb.lock_rotation = (True, False, True)
    c = pb.constraints.new('LIMIT_ROTATION')
    c.name = 'MCH Limit'
    c.owner_space = 'LOCAL'
    c.use_limit_x = c.use_limit_z = True
    c.use_limit_y = True
    c.min_y, c.max_y = math.radians(min(lo_deg, hi_deg)), math.radians(max(lo_deg, hi_deg))
    c.use_transform_limit = True


def hatch_sign(context, part, axis):
    """+1 / -1: which way round ``axis`` (through the part's joint) swings the hatch out - away from the other parts
    of its rig (not into the body)."""
    arm = rig_of(part)
    b = arm.data.bones[part[PART_KEY]]
    pivot = np.array(arm.matrix_world @ b.head_local)
    V = world_points(context, part)
    c = 0.5 * (V.min(0) + V.max(0))
    others = [o for o in bpy.data.objects if o is not part and o.parent is arm and o.get(PART_KEY)]
    holder = None
    pb_parent = b.parent
    if pb_parent is not None:                      # (the part it hangs on: its parent bone's part)
        holder = next((o for o in others if o[PART_KEY] == pb_parent.name), None)
    if holder is None and others:                  # (else the nearest part)
        def cen(o):
            W = world_points(context, o)
            return 0.5 * (W.min(0) + W.max(0))
        holder = min(others, key=lambda o: float(np.linalg.norm(cen(o) - c)))
    if holder is not None:
        W = world_points(context, holder)
        out = c - 0.5 * (W.min(0) + W.max(0))
    else:
        out = np.array([0.0, 0.0, 1.0])
    move = np.cross(np.array(AXES[axis]), c - pivot)
    return 1.0 if float(move @ out) >= 0.0 else -1.0


def make_piston(context, a, b):
    """0.24.242 (user: "피스톤같은 것도") two parts of a mecha rig as a piston: the thicker one the cylinder, the
    thinner the rod.  The cylinder's bone starts at its far end, the rod's at its far end; each always points at
    the other's start (Damped Track), so whatever the ends are linked to, the rod slides in and out of the
    cylinder along one line."""
    arm = rig_of(a)
    if arm is None or rig_of(b) is not arm or not a.get(PART_KEY) or not b.get(PART_KEY):
        raise RuntimeError('Select two parts of the same mecha rig (the cylinder and the rod)')
    Va, Vb = world_points(context, a), world_points(context, b)
    ca, cb = 0.5 * (Va.min(0) + Va.max(0)), 0.5 * (Vb.min(0) + Vb.max(0))
    u = cb - ca
    if np.linalg.norm(u) < 1e-6:
        raise RuntimeError('The two parts sit in the same place')
    u /= np.linalg.norm(u)

    def radius(V, c):
        r = (V - c) - np.outer((V - c) @ u, u)
        return float(np.linalg.norm(r, axis=1).mean())
    if radius(Va, ca) >= radius(Vb, cb):
        cyl, rod, Vc, Vr, cc, cr = a, b, Va, Vb, ca, cb
    else:
        cyl, rod, Vc, Vr, cc, cr = b, a, Vb, Va, cb, ca
        u = -u
    base = cc + u * float(((Vc - cc) @ u).min())
    end = cr + u * float(((Vr - cr) @ u).max())
    len_c = float(np.ptp((Vc - cc) @ u))
    len_r = float(np.ptp((Vr - cr) @ u))
    keep = _keep_parts(arm)
    Mi = np.array(arm.matrix_world.inverted())
    loc = lambda p: Vector(Mi[:3, :3] @ p + Mi[:3, 3])
    with _Edit(context, arm) as ebs:
        bc, br = ebs[cyl[PART_KEY]], ebs[rod[PART_KEY]]
        bc.head, bc.tail = loc(base), loc(base + u * max(len_c, 1e-3))
        br.head, br.tail = loc(end), loc(end - u * max(len_r, 1e-3))
        if br.parent is bc:
            br.parent = bc.parent
        if bc.parent is br:
            bc.parent = br.parent
    _reattach(arm, keep)
    pbs = arm.pose.bones
    for own, tgt in ((cyl[PART_KEY], rod[PART_KEY]), (rod[PART_KEY], cyl[PART_KEY])):
        pb = pbs[own]
        for c in [c for c in pb.constraints if c.name == 'MCH Piston']:
            pb.constraints.remove(c)
        c = pb.constraints.new('DAMPED_TRACK')
        c.name = 'MCH Piston'
        c.target, c.subtarget = arm, tgt
        c.head_tail = 0.0
    return cyl, rod


def through_middle(context, region, rv3d, ob, xy):
    """The point halfway between where the view ray at ``xy`` goes into ``ob`` and comes out (world), or None."""
    from bpy_extras import view3d_utils
    o = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
    d = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy).normalized()
    Mi = ob.matrix_world.inverted()
    lo, ld = Mi @ o, (Mi.to_3x3() @ d).normalized()
    hit, loc, _n, _i = ob.ray_cast(lo, ld)
    if not hit:
        return None
    first = loc
    out = loc
    p = loc + ld * 1e-4
    for _k in range(64):
        h2, l2, _n2, _i2 = ob.ray_cast(p, ld)
        if not h2:
            break
        out = l2
        p = l2 + ld * 1e-4
        if (out - first).length > 0:
            break
    return ob.matrix_world @ ((first + out) * 0.5)


# --- chain -------------------------------------------------------------------------------------------------------------

def chain_points(context, ob, n):
    """``n`` + 1 points along a long mesh (thick end first) or a curve (its first spline, start first)."""
    if ob.type == 'CURVE':
        dg = context.evaluated_depsgraph_get()
        me = ob.evaluated_get(dg).to_mesh()
        try:
            P = np.array([tuple(ob.matrix_world @ v.co) for v in me.vertices])
        finally:
            ob.evaluated_get(dg).to_mesh_clear()
        if len(P) < 2:
            raise RuntimeError('The curve is too short')
        seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        u = np.concatenate([[0], np.cumsum(seg)]) / max(seg.sum(), 1e-12)
        t = np.linspace(0, 1, n + 1)
        return np.stack([np.interp(t, u, P[:, d]) for d in range(3)], axis=1)
    V = world_points(context, ob)
    if len(V) < 4:
        raise RuntimeError('The mesh is too small for a chain')
    m = V.mean(0)
    _u, _s, vt = np.linalg.svd((V - m)[:: max(1, len(V) // 8000)], full_matrices=False)
    d = vt[0]
    s = (V - m) @ d
    lo, hi = s.min(), s.max()
    edges = np.linspace(lo, hi, 2 * n + 2)
    cent, size = [], []
    for i in range(2 * n + 1):
        msk = (s >= edges[i]) & (s <= edges[i + 1])
        if msk.sum() >= 3:
            c = V[msk].mean(0)
            cent.append(c)
            size.append(np.linalg.norm(V[msk] - c, axis=1).mean())
        else:
            cent.append(m + d * 0.5 * (edges[i] + edges[i + 1]))
            size.append(0.0)
    cent = np.array(cent)
    cent[0] = cent[0] + (cent[0] - cent[1]) * 0.5            # (out to the very ends)
    cent[-1] = cent[-1] + (cent[-1] - cent[-2]) * 0.5
    if np.mean(size[: len(size) // 3]) < np.mean(size[-(len(size) // 3):]):
        cent = cent[::-1]                                    # (the thick end first: the root)
    seg = np.linalg.norm(np.diff(cent, axis=0), axis=1)
    u = np.concatenate([[0], np.cumsum(seg)]) / max(seg.sum(), 1e-12)
    t = np.linspace(0, 1, n + 1)
    return np.stack([np.interp(t, u, cent[:, k]) for k in range(3)], axis=1)


def build_chain(context, ob, n, into=None):
    P = chain_points(context, ob, n)
    arm = into
    if arm is None:
        arm = _new_armature(context, ob.name + '_Rig')
        arm[RIG_KEY] = 'CHAIN'
    Mi = np.array(arm.matrix_world.inverted())
    L = P @ Mi[:3, :3].T + Mi[:3, 3]
    base = ob.name.replace('.', '_')
    names = []
    with _Edit(context, arm) as ebs:
        parent = None
        if into is not None and len(ebs):
            def dist(b):
                h, t = np.array(b.head), np.array(b.tail)
                d = t - h
                x = np.clip(((L[0] - h) @ d) / max(d @ d, 1e-12), 0, 1)
                return np.linalg.norm(L[0] - (h + x * d))
            parent = min(ebs, key=dist)
        for i in range(n):
            b = _bone(ebs, f'{base}.{i + 1:02d}', L[i], L[i + 1], parent, connect=i > 0)
            names.append(b.name)
            parent = b
    return arm, names


def delete_rig(context, arm):
    """0.24.249 (user: "리그 지우기도 만들어줘") the rig gone and everything it touched put back: the meshes off the
    rig (its Armature modifier and the weight groups named after its bones removed, shown in their own shape),
    the mecha parts let go where they stand in the rest pose, constraints aiming at it removed, its Auto Animation
    actions and (when no rig is left) the control shapes deleted.  The meshes themselves are never deleted.
    Returns (meshes freed, parts freed)."""
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    _EDITING.pop(arm.name, None)
    bones = {b.name for b in arm.data.bones}
    arm.data.pose_position = 'REST'                      # (the parts let go where they were made)
    context.view_layer.update()
    meshes = parts = 0
    for o in list(bpy.data.objects):
        if o is arm:
            continue
        if o.parent is arm:
            mw = o.matrix_world.copy()
            o.parent = None
            o.parent_type = 'OBJECT'
            o.parent_bone = ''
            o.matrix_world = mw
            if PART_KEY in o:
                del o[PART_KEY]
                parts += 1
        mods = [m for m in getattr(o, 'modifiers', ()) if m.type == 'ARMATURE' and m.object is arm]
        for m in mods:
            o.modifiers.remove(m)
        if mods and o.type == 'MESH':
            for vg in [vg for vg in o.vertex_groups if vg.name in bones]:
                o.vertex_groups.remove(vg)
            meshes += 1
        for c in [c for c in getattr(o, 'constraints', ()) if getattr(c, 'target', None) is arm]:
            o.constraints.remove(c)
    names = {f'{arm.name}_{g}' for g in ('Idle', 'Walk', 'Run', 'Trot')}
    for a in [a for a in bpy.data.actions if a.name in names]:
        bpy.data.actions.remove(a)
    data = arm.data
    bpy.data.objects.remove(arm)
    if data.users == 0:
        bpy.data.armatures.remove(data)
    if not any(o.type == 'ARMATURE' and RIG_KEY in o for o in bpy.data.objects):
        coll = bpy.data.collections.get(WIDGETS)
        if coll is not None:
            for w in list(coll.objects):
                me = w.data
                bpy.data.objects.remove(w)
                if me is not None and me.users == 0:
                    bpy.data.meshes.remove(me)
            bpy.data.collections.remove(coll)
    return meshes, parts


# --- the user's own Edit Mode -------------------------------------------------------------------------------------------

_EDITING = {}        # rig name -> [(mesh name, armature modifier name, was shown)]


def _users(arm):
    out = []
    for o in bpy.data.objects:
        if o.type != 'MESH':
            continue
        for m in o.modifiers:
            if m.type == 'ARMATURE' and m.object is arm:
                out.append((o, m))
    return out


@bpy.app.handlers.persistent
def _edit_watch(scene, *_a):
    """0.24.242 (user: "에딧 본에서 뼈 편집해도 오브젝트 모드 들어오면 약간 이상해"): while a rig is in Edit Mode its
    meshes are shown as they are (not bent by the bones being moved); when it leaves Edit Mode the IK targets go
    back on the moved hands / feet and the meshes are weighted again to the new bones (or the mecha parts put back
    on theirs) - by itself, with Tab too."""
    if _BUSY[0]:
        return
    try:
        rigs = [o for o in scene.objects if o.type == 'ARMATURE' and RIG_KEY in o]
    except ReferenceError:
        return
    for arm in rigs:
        if arm.mode == 'EDIT' and arm.name not in _EDITING:
            _EDITING[arm.name] = [(o.name, m.name, m.show_viewport) for o, m in _users(arm)]
            bpy.app.timers.register(lambda n=arm.name: _hide_bend(n), first_interval=0.01)
        elif arm.mode != 'EDIT' and arm.name in _EDITING:
            kept = _EDITING.pop(arm.name)
            bpy.app.timers.register(lambda n=arm.name, k=kept: _after_edit(n, k), first_interval=0.05)


def _hide_bend(name):
    for mesh, mod, _was in _EDITING.get(name, ()):
        o = bpy.data.objects.get(mesh)
        m = o.modifiers.get(mod) if o is not None else None
        if m is not None:
            m.show_viewport = False
    return None


def after_edit(context, arm, kept=()):
    """Back from Edit Mode: IK synced, meshes weighted again / parts put back, their bending shown again.
    Returns a short message."""
    for mesh, mod, was in kept:
        o = bpy.data.objects.get(mesh)
        m = o.modifiers.get(mod) if o is not None else None
        if m is not None:
            m.show_viewport = was
    kind = arm.get(RIG_KEY)
    if kind == 'MECHA':
        keep = {o.name: o.matrix_world.copy() for o in bpy.data.objects if o.parent is arm and o.get(PART_KEY)}
        for name, mw in keep.items():
            o = bpy.data.objects[name]
            attach(o, arm, o[PART_KEY])
            o.matrix_world = mw
        return f'{arm.name}: {len(keep)} parts back on their bones'
    if kind in {'BODY', 'QUAD', 'AUTO'}:
        sync_ik(context, arm)
    meshes = {mesh for mesh, _m, _w in kept}
    n = 0
    for name in meshes:
        o = bpy.data.objects.get(name)
        if o is not None:
            bind(context, o, arm)
            n += 1
    return f'{arm.name}: IK targets on the moved bones, {n} mesh(es) weighted again'


def _after_edit(name, kept):
    arm = bpy.data.objects.get(name)
    if arm is None:
        return None
    if arm.mode == 'EDIT':                     # (back in already: wait for the next exit)
        _EDITING[name] = kept
        return None
    try:
        wm = bpy.context.window_manager
        win = wm.windows[0] if wm and wm.windows else None
        if win is not None:
            with bpy.context.temp_override(window=win, scene=win.scene, view_layer=win.view_layer):
                msg = after_edit(bpy.context, arm, kept)
        else:
            msg = after_edit(bpy.context, arm, kept)
        try:
            from . import toast
            toast.show(msg)
        except (ImportError, AttributeError, TypeError):
            pass
    except Exception as ex:
        print('Mecha Lab rig after Edit Mode:', ex)
    return None


# --- jiggle (playback) ------------------------------------------------------------------------------------------------

_STATE = {}


def set_jiggle(arm, root, on, stiffness=0.25, damping=0.25):
    import json
    d = json.loads(arm.get(SPRING_KEY, '{}'))
    if on:
        d[root] = [float(stiffness), float(damping)]
    else:
        d.pop(root, None)
    arm[SPRING_KEY] = json.dumps(d)
    _ensure_handler()


def _chain_from(arm, root):
    out = [root]
    b = arm.pose.bones.get(root)
    while b is not None:
        kids = [c for c in b.children if c.bone.use_connect]
        if not kids:
            break
        b = kids[0]
        out.append(b.name)
    return out


@bpy.app.handlers.persistent
def _jiggle(scene, *_a):
    import json
    for arm in [o for o in scene.objects if o.type == 'ARMATURE' and o.get(SPRING_KEY)]:
        try:
            chains = json.loads(arm[SPRING_KEY])
        except (ValueError, TypeError):
            continue
        W = arm.matrix_world
        Wi = W.inverted()
        restart = scene.frame_current <= scene.frame_start
        for root, (k, damp) in chains.items():
            names = _chain_from(arm, root)
            for name in names:
                pb = arm.pose.bones.get(name)
                if pb is None:
                    continue
                par = pb.parent
                rel = (par.bone.matrix_local.inverted() @ pb.bone.matrix_local) if par is not None else pb.bone.matrix_local
                pose = (par.matrix @ rel) if par is not None else (pb.matrix if par is None else rel)
                head = W @ pose.to_translation()
                want = W @ (pose @ Vector((0, pb.bone.length, 0)))
                key = (arm.name, name)
                st = _STATE.get(key)
                if restart or st is None:
                    _STATE[key] = [want.copy(), Vector((0, 0, 0))]
                    pb.matrix = pose
                    continue
                pos, vel = st
                vel = (vel + (want - pos) * k) * (1.0 - damp)
                pos = pos + vel
                d0 = (want - head)
                d1 = (pos - head)
                if d1.length < 1e-9 or d0.length < 1e-9:
                    pb.matrix = pose
                    continue
                pos = head + d1.normalized() * d0.length          # (the bone keeps its length)
                _STATE[key] = [pos, vel]
                R = (Wi.to_3x3() @ d0).rotation_difference(Wi.to_3x3() @ (pos - head)).to_matrix().to_4x4()
                t = pose.to_translation()
                pb.matrix = Matrix.Translation(t) @ R @ Matrix.Translation(-t) @ pose


def _ensure_handler():
    if _jiggle not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(_jiggle)


# --- operators ---------------------------------------------------------------------------------------------------------

class MCH_OT_rig_make(bpy.types.Operator):
    """Make the rig for the selection (the kind picked in the window: Human, Quadruped, Mecha, Chain)"""
    bl_idname = 'mch.rig_make'
    bl_label = 'Make Rig'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return settings(context) is not None and context.active_object is not None

    def execute(self, context):
        st = settings(context)
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        sel = list(context.selected_objects)
        act = context.active_object
        try:
            if st.kind in {'BODY', 'QUAD'}:
                if act.type != 'MESH':
                    raise RuntimeError('Select the body mesh')
                arm = build_body(context, act, st.kind == 'QUAD', st.ik, st.fingers, st.face, st.legs)
                how = bind(context, act, arm) if st.bind else ''
                msg = (f'{arm.name}: {len(arm.data.bones)} bones' + (' with IK' if st.ik else '')
                       + (f', {act.name} bound ({"automatic" if how == "auto" else "nearest-bone"} weights)' if how else ''))
                _show(context, arm)
            elif st.kind == 'AUTO':                    # 0.24.246 any creature
                if act.type != 'MESH':
                    raise RuntimeError('Select the creature mesh')
                from . import auto_creature
                arm, info = auto_creature.build(context, act)
                how = bind(context, act, arm) if st.bind else ''
                msg = (f'{arm.name}: {info["legs"]} legs, {info["chains"]} tails / arms / tentacles, {info["bones"]} bones'
                       + (f', {act.name} bound ({"automatic" if how == "auto" else "nearest-bone"} weights)' if how else ''))
                _show(context, arm)
            elif st.kind == 'GUIDE':                   # 0.24.258 the user's own guide lines
                from . import rig_guides as rgd
                body = rgd._target_mesh(context)
                if body is None:
                    raise RuntimeError('Select the creature mesh (with its guide lines)')
                arm, info = rgd.build(context, body, rgd.strokes(body), rgd.line_kinds(body))
                g = rgd.guides_of(body)
                if g is not None:
                    g.hide_set(True)
                how = bind(context, body, arm) if st.bind else ''
                msg = (f'{arm.name}: {info["legs"]} legs, {info["chains"]} swaying chains, {info["eyes"]} eyes, '
                       f'{info["lips"]} lip bones, {info["fingers"]} fingers, {info["bones"]} bones'
                       + (f', {body.name} bound ({"automatic" if how == "auto" else "nearest-bone"} weights)' if how else ''))
                _show(context, arm)
            elif st.kind == 'MGUIDE':                  # 0.24.338 the user's own guide lines over mecha parts
                from . import mecha_guides as mg
                parts = [o for o in (sel or [act]) if o.type == 'MESH']
                arm, rep = mg.build(context, parts, mg.lines(), st.seamless)
                msg = (f'{arm.name}: {len(rep["bones"])} bones (one a part)'
                       + (f', IK on {", ".join(rep["ik"])}' if rep['ik'] else '')
                       + (f'; {len(rep["rode"])} part(s) no line crosses on the nearest bone' if rep['rode'] else ''))
                _show(context, arm)
            elif st.kind == 'NAMED':                   # 0.24.336 by the parts' names
                from . import mecha_named
                arm, rep = mecha_named.build(context, [o for o in (sel or [act]) if o.type == 'MESH'], st.seamless)
                msg = (f'{arm.name}: {len(rep["bones"])} bones by name ({", ".join(rep["bones"])})'
                       + (f', IK on {", ".join(rep["ik"])}' if rep['ik'] else ', no IK (an arm / leg needs its '
                          'upper, lower and end part)')
                       + (f'; {len(rep["rode"])} unnamed part(s) on the nearest bone' if rep['rode'] else ''))
                _show(context, arm)
            elif st.kind == 'MECHA':
                arm = build_mecha(context, sel or [act], st.auto_joints)
                nl = len(json.loads(arm.get('mch_legs', '[]')))
                msg = (f'{arm.name}: {sum(1 for o in (sel or [act]) if o.type == "MESH")} parts, each on its bone'
                       + (f', joints where they touch, {nl} leg(s) with IK' if st.auto_joints else '')
                       + ' - click a part with the Rig tool to move its joint')
                _show(context, arm)
            else:
                into = next((o for o in sel if o.type == 'ARMATURE'), None)
                src = act if act.type in {'MESH', 'CURVE'} else next((o for o in sel if o.type in {'MESH', 'CURVE'}), None)
                if src is None:
                    raise RuntimeError('Select the tail / tentacle mesh (or a curve)')
                arm, names = build_chain(context, src, st.bones, into)
                how = bind(context, src, arm) if st.bind and src.type == 'MESH' else ''
                if st.jiggle:
                    set_jiggle(arm, names[0], True, st.stiffness, st.damping)
                msg = (f'{arm.name}: a chain of {len(names)} bones' + (' (Jiggle on playback)' if st.jiggle else '')
                       + (f', {src.name} bound' if how else ''))
                _show(context, arm)
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


def _show(context, arm):
    for o in list(context.selected_objects):
        o.select_set(False)
    arm.select_set(True)
    context.view_layer.objects.active = arm


class MCH_OT_rig_name_by_place(bpy.types.Operator):
    """Name the selected parts by where they are on a body standing up, facing -Y (Head, Neck, Chest, Belly, Pelvis,
    UpperArm.L, Forearm.L, Hand.L, Thigh.R, Shin.R, Foot.R ...); a part holding both feet is split in two.  Check the
    names, then Make Rig"""
    bl_idname = 'mch.rig_name_by_place'
    bl_label = 'Name by Place'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and sum(1 for o in context.selected_objects if o.type == 'MESH') >= 2

    def execute(self, context):
        from . import mecha_named
        done = mecha_named.name_by_place(context, [o for o in context.selected_objects if o.type == 'MESH'])
        for o in bpy.data.objects:
            if o.name in done.values():
                o.select_set(True)
        self.report({'INFO'}, f'{len(done)} part(s) named: ' + ', '.join(sorted(done.values()))[:300])
        return {'FINISHED'}


class MCH_OT_rig_bind(bpy.types.Operator):
    """Bind the selected mesh to the rig again (after Edit Bones): automatic weights, nearest bones where they fail"""
    bl_idname = 'mch.rig_bind'
    bl_label = 'Bind'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and (is_rig(ob) or rig_of(ob) is not None)

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        ob = context.active_object
        arm = rig_of(ob)
        if arm.get(RIG_KEY) == 'MECHA':
            n = 0
            for o in [o for o in bpy.data.objects if o.parent is arm and o.get(PART_KEY)]:
                mw = o.matrix_world.copy()
                attach(o, arm, o[PART_KEY])
                o.matrix_world = mw
                n += 1
            self.report({'INFO'}, f'{n} parts on their bones again')
            return {'FINISHED'}
        moved = sync_ik(context, arm) if arm.get(RIG_KEY) in {'BODY', 'QUAD', 'AUTO'} else 0    # 0.24.242
        mesh = ob if ob.type == 'MESH' else bpy.data.objects.get(arm.get(BODY_KEY, ''))
        if mesh is None:
            mesh = next((o for o in context.selected_objects if o.type == 'MESH'), None)
        if mesh is None:
            self.report({'WARNING'}, 'Select the mesh to bind (with the rig)')
            return {'CANCELLED'}
        how = bind(context, mesh, arm)
        self.report({'INFO'}, f'{mesh.name} bound to {arm.name} ({"automatic" if how == "auto" else "nearest-bone"} weights)')
        return {'FINISHED'}


class MCH_OT_rig_delete(bpy.types.Operator):
    """Delete the rig: the meshes and parts stay (back in their own shape, let go of the bones), its animations go"""
    bl_idname = 'mch.rig_delete'
    bl_label = 'Delete Rig'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return rig_of(context.active_object) is not None

    def execute(self, context):
        arm = rig_of(context.active_object)
        name = arm.name
        meshes, parts = delete_rig(context, arm)
        self.report({'INFO'}, f'{name} deleted ({meshes} mesh(es), {parts} part(s) kept)')
        return {'FINISHED'}


class MCH_OT_rig_edit(bpy.types.Operator):
    """Move the joints: the rig's Edit Mode (Tab back, then Bind again)"""
    bl_idname = 'mch.rig_edit'
    bl_label = 'Edit Bones'
    bl_options = {'REGISTER', 'UNDO'}
    mode: EnumProperty(items=[('EDIT', 'Edit', ''), ('POSE', 'Pose', ''), ('OBJECT', 'Done', '')], default='EDIT')

    @classmethod
    def poll(cls, context):
        return rig_of(context.active_object) is not None

    def execute(self, context):
        arm = rig_of(context.active_object)
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        if self.mode == 'OBJECT':
            return {'FINISHED'}
        for o in list(context.selected_objects):
            o.select_set(False)
        arm.hide_set(False)
        arm.select_set(True)
        context.view_layer.objects.active = arm
        if self.mode == 'EDIT':
            arm.data.use_mirror_x = True           # 0.24.242 a .L bone moved: its .R moves with it
        bpy.ops.object.mode_set(mode=self.mode)
        return {'FINISHED'}


class MCH_OT_rig_link(bpy.types.Operator):
    """Mecha: put the selected parts' bones under the active part's bone (the parts follow it)"""
    bl_idname = 'mch.rig_link'
    bl_label = 'Link to Active'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.get(PART_KEY) and rig_of(ob) is not None

    def execute(self, context):
        act = context.active_object
        arm = rig_of(act)
        kids = [o for o in context.selected_objects if o is not act and o.get(PART_KEY) and rig_of(o) is arm]
        if not kids:
            self.report({'WARNING'}, 'Select the child parts, then the parent part last (active)')
            return {'CANCELLED'}
        keep = {o.name: o.matrix_world.copy() for o in bpy.data.objects if o.parent is arm and o.get(PART_KEY)}
        with _Edit(context, arm) as ebs:
            for o in kids:
                if o[PART_KEY] != act[PART_KEY]:
                    ebs[o[PART_KEY]].parent = ebs[act[PART_KEY]]
        for name, mw in keep.items():
            o = bpy.data.objects[name]
            attach(o, arm, o[PART_KEY])
            o.matrix_world = mw
        self.report({'INFO'}, f'{len(kids)} part(s) under {act.name}')
        return {'FINISHED'}


class MCH_OT_rig_jiggle(bpy.types.Operator):
    """Jiggle on / off for the chains of the selected rig (playback)"""
    bl_idname = 'mch.rig_jiggle'
    bl_label = 'Jiggle'
    bl_options = {'REGISTER', 'UNDO'}
    on: BoolProperty(default=True)

    @classmethod
    def poll(cls, context):
        return rig_of(context.active_object) is not None

    def execute(self, context):
        arm = rig_of(context.active_object)
        st = settings(context)
        roots = [b.name for b in arm.data.bones if b.use_deform and not b.use_connect and
                 any(c.use_connect for c in b.children)]
        if arm.get(RIG_KEY) != 'CHAIN':
            roots = [r for r in roots if not any(r.startswith(p) for p in ('hips', 'pelvis', 'spine', 'thigh', 'upper_arm',
                                                                          'shoulder', 'leg', 'neck', 'chest'))]
        for r in roots:
            set_jiggle(arm, r, self.on, st.stiffness, st.damping)
        self.report({'INFO'}, f'Jiggle {"on" if self.on else "off"}: {len(roots)} chain(s)')
        return {'FINISHED'}


class MCH_OT_rig_mirror(bpy.types.Operator):
    """Copy the bones of one side to the other, mirrored (after you placed them on one side)"""
    bl_idname = 'mch.rig_mirror'
    bl_label = 'Mirror Bones'
    bl_options = {'REGISTER', 'UNDO'}
    side: EnumProperty(items=[('L', 'L -> R', ''), ('R', 'R -> L', '')], default='L')

    @classmethod
    def poll(cls, context):
        return rig_of(context.active_object) is not None

    def execute(self, context):
        arm = rig_of(context.active_object)
        mode = context.mode
        if mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        n = mirror_lr(context, arm, self.side)
        if mode == 'EDIT_ARMATURE':
            bpy.ops.object.mode_set(mode='EDIT')
        self.report({'INFO'}, f'{n} bones mirrored {"L -> R" if self.side == "L" else "R -> L"} - Bind to weight the mesh')
        return {'FINISHED'}


class MCH_OT_rig_limit(bpy.types.Operator):
    """Mecha: the active part turns only round the chosen axis between From and To (Hatch: 0 to Open); Free: no limit"""
    bl_idname = 'mch.rig_limit'
    bl_label = 'Limit Turn'
    bl_options = {'REGISTER', 'UNDO'}
    kind: EnumProperty(items=[('LIMIT', 'Limit', ''), ('HATCH', 'Hatch', ''), ('FREE', 'Free', '')], default='LIMIT')

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and bool(ob.get(PART_KEY)) and rig_of(ob) is not None

    def execute(self, context):
        st = settings(context)
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        ob = context.active_object
        try:
            if self.kind == 'FREE':
                limit_turn(context, ob, 'FREE', 0, 0)
                msg = f'{ob.name}: turns freely'
            elif self.kind == 'HATCH':
                sign = hatch_sign(context, ob, st.axis)
                lo, hi = (0.0, st.hatch) if sign > 0 else (-st.hatch, 0.0)
                limit_turn(context, ob, st.axis, lo, hi)
                msg = f'{ob.name}: a hatch - opens {st.hatch:g} degrees round {st.axis}, outward'
            else:
                limit_turn(context, ob, st.axis, st.lo, st.hi)
                msg = f'{ob.name}: turns round {st.axis} only, {min(st.lo, st.hi):g} .. {max(st.lo, st.hi):g} degrees'
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class MCH_OT_rig_piston(bpy.types.Operator):
    """Mecha: the two selected parts become a piston - the rod slides in the cylinder, both always in line"""
    bl_idname = 'mch.rig_piston'
    bl_label = 'Piston'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return sum(1 for o in context.selected_objects if o.get(PART_KEY)) == 2

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        a, b = [o for o in context.selected_objects if o.get(PART_KEY)]
        try:
            cyl, rod = make_piston(context, a, b)
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, f'Piston: {rod.name} slides in {cyl.name} - link each end to what holds it (Link to Active)')
        return {'FINISHED'}


class MCH_OT_rig_click(bpy.types.Operator):
    """Rig tool click: on a mecha part - its joint where you clicked (in the middle of the part)"""
    bl_idname = 'mch.rig_click'
    bl_label = 'Rig Click'
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        region, rv3d = context.region, context.region_data
        if region is None or rv3d is None:
            return {'PASS_THROUGH'}
        try:
            from . import ui_bars
            if ui_bars.over_ui(context, event.mouse_region_x, event.mouse_region_y):
                return {'PASS_THROUGH'}
        except (ImportError, AttributeError):
            pass
        from bpy_extras import view3d_utils
        xy = (event.mouse_region_x, event.mouse_region_y)
        o = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
        d = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
        dg = context.evaluated_depsgraph_get()
        hit, _loc, _n, _i, ob, _m = context.scene.ray_cast(dg, o, d)
        if not hit or ob is None:
            return {'PASS_THROUGH'}
        ob = ob.original
        if ob.get(PART_KEY) and rig_of(ob) is not None:
            p = through_middle(context, region, rv3d, ob, xy)
            if p is None:
                return {'CANCELLED'}
            try:
                set_pivot(context, ob, p)
            except RuntimeError as ex:
                self.report({'WARNING'}, str(ex))
                return {'CANCELLED'}
            for x in list(context.selected_objects):
                x.select_set(False)
            ob.select_set(True)
            context.view_layer.objects.active = ob
            self.report({'INFO'}, f'{ob.name}: joint set')
            return {'FINISHED'}
        for x in list(context.selected_objects):
            x.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        return {'FINISHED'}


# --- 0.24.257 IK where the user wants it -------------------------------------------------------------------------------

def selected_bones(context, arm):
    """The rig's selected bones (Pose / Edit Bones / Object mode: as last selected), the active one first."""
    if arm.mode == 'EDIT':
        ebs = arm.data.edit_bones
        names = [e.name for e in ebs if e.select]
        act = ebs.active.name if ebs.active is not None else None
    else:                                                    # (5.x: the selection is on the pose bones)
        names = [pb.name for pb in arm.pose.bones if pb.select]
        act = arm.data.bones.active.name if arm.data.bones.active is not None else None
    if act in names:
        names.remove(act)
        names.insert(0, act)
    return names


def _ik_pole_search(context, arm, owner, c):
    """The pole angle that keeps the rest pose still (as ``_limb_ik``)."""
    pbs = arm.pose.bones
    ups, b = [], pbs[owner].parent
    for _i in range(max(0, c.chain_count - 1)):
        if b is None:
            break
        ups.append(b)
        b = b.parent

    def err_at(deg):
        c.pole_angle = math.radians(deg)
        context.view_layer.update()
        return sum((pb.matrix.to_translation() - pb.bone.matrix_local.to_translation()).length +
                   (pb.matrix.col[1].xyz - pb.bone.matrix_local.col[1].xyz).length +
                   (pb.matrix.col[0].xyz - pb.bone.matrix_local.col[0].xyz).length for pb in ups + [pbs[owner]])
    best = None
    for deg in (-90.0, 90.0, 0.0, 180.0, -45.0, 45.0, -135.0, 135.0):
        e = err_at(deg)
        if best is None or e < best[0]:
            best = (e, deg)
    for step, span in ((3.0, 24.0), (0.5, 3.0), (0.1, 0.5)):
        c0 = best[1]
        for k in np.arange(-span, span + 1e-9, step):
            e = err_at(c0 + float(k))
            if e < best[0]:
                best = (e, c0 + float(k))
    c.pole_angle = math.radians(best[1])
    context.view_layer.update()
    return best


def add_ik(context, arm, ends, chain=2):
    """0.24.257 (user: "IK 생길 부분을 내가 지정할 수 있니?") IK on each of ``ends`` (its tail reaches a new target
    ``<end>_ik``, ``chain`` bones bend, a pole ``<end>_pole`` off the bend keeps the rest pose still).  Bones that
    are IK targets / poles, or already have IK, are skipped.  Returns the ends given IK."""
    bones = arm.data.bones
    root = 'root' if 'root' in bones else None
    todo = []
    for n in ends:
        b = bones.get(n)
        if b is None or n.endswith(('_ik', '_pole')) or n + '_ik' in bones or n == root:
            continue
        if any(c.type == 'IK' for c in arm.pose.bones[n].constraints):
            continue
        chain_b = [b]
        if chain <= 0:                               # 0.24.260 the whole limb: up to where it branches off the body
            while (chain_b[-1].parent is not None and chain_b[-1].parent.name not in {root, 'body'}
                   and chain_b[-1].parent.use_deform and len(chain_b[-1].parent.children) == 1
                   and chain_b[-1].use_connect):
                chain_b.append(chain_b[-1].parent)
        else:
            while len(chain_b) < chain and chain_b[-1].parent is not None and chain_b[-1].parent.name != root:
                chain_b.append(chain_b[-1].parent)
        todo.append((n, len(chain_b)))
    if not todo:
        return []
    M = arm.matrix_world
    with _Edit(context, arm) as ebs:
        for n, k in todo:
            e = ebs[n]
            top = e
            for _i in range(k - 1):
                top = top.parent
            a_, b_, mid = Vector(top.head), Vector(e.tail), Vector(e.head if k > 1 else e.head)
            ab = b_ - a_
            off = (mid - (a_ + ab * ((mid - a_).dot(ab) / max(ab.length_squared, 1e-12)))) if k > 1 else Vector()
            if off.length < 1e-4 * max(ab.length, 1e-6):
                off = Vector(e.z_axis)                   # (a straight chain: off the bone's own side)
            off = off.normalized() * 0.5 * max(ab.length, e.length)
            t = ebs.new(n + '_ik')
            t.head = e.tail
            t.tail = e.tail + (e.tail - e.head).normalized() * 0.3 * e.length
            t.roll = e.roll
            t.parent = ebs[root] if root else None
            t.use_deform = False
            p = ebs.new(n + '_pole')
            p.head = mid + off
            p.tail = p.head + off.normalized() * 0.1 * off.length
            p.parent = ebs[root] if root else None
            p.use_deform = False
    pbs = arm.pose.bones
    for n, k in todo:
        c = pbs[n].constraints.new('IK')
        c.name = 'MCH IK'
        c.target, c.subtarget = arm, n + '_ik'
        if k > 1:
            c.pole_target, c.pole_subtarget = arm, n + '_pole'
        c.chain_count = k
        if k > 1:
            _ik_pole_search(context, arm, n, c)
    controls(arm)
    return [n for n, _k in todo]


def remove_ik(context, arm, picked):
    """0.24.257 the IK through any of ``picked`` (bones in its chain, its end's child, its target or pole) taken
    off: the constraints, the target and pole bones gone, the chain back in its rest pose; a leg it was is no longer
    walked by Auto Animation.  Returns how many IKs."""
    pbs = arm.pose.bones
    picked = set(picked)
    drop_t, drop_p, owners, bent = set(), set(), set(), set()
    for pb in pbs:
        for c in pb.constraints:
            if c.type != 'IK' or c.target is not arm:
                continue
            chain_ = [pb]
            while len(chain_) < max(1, c.chain_count or 99) and chain_[-1].parent is not None:
                chain_.append(chain_[-1].parent)
            names = {x.name for x in chain_} | {ch.name for ch in pb.children}
            if names & picked or c.subtarget in picked or c.pole_subtarget in picked:
                drop_t.add(c.subtarget)
                if c.pole_subtarget:
                    drop_p.add(c.pole_subtarget)
                owners.add(pb.name)
                bent |= {x.name for x in chain_} | {ch.name for ch in pb.children}
    if not drop_t:
        return 0
    gone = drop_t | drop_p
    for pb in pbs:
        for c in list(pb.constraints):
            if getattr(c, 'target', None) is arm and (getattr(c, 'subtarget', '') in gone
                                                      or getattr(c, 'pole_subtarget', '') in gone):
                pb.constraints.remove(c)
    for pb in pbs:                                       # (back to the rest pose: nothing bends it now)
        if pb.name in bent:
            pb.location = (0, 0, 0)
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.rotation_euler = (0, 0, 0)
    with _Edit(context, arm) as ebs:
        for n in gone:
            if n in ebs:
                ebs.remove(ebs[n])
    legs = json.loads(arm.get('mch_legs', '[]') or '[]')
    keep = [l_ for l_ in legs if l_ + '.foot_ik' not in gone and l_ + '_ik' not in gone]
    if keep != legs:
        arm['mch_legs'] = json.dumps(keep)
    return len(drop_t)


class MCH_OT_rig_ik(bpy.types.Operator):
    """Add IK to the selected end bone(s) (IK Bones: how many bend), or take off the IK the selected bones are in"""
    bl_idname = 'mch.rig_ik'
    bl_label = 'IK on Selected'
    bl_options = {'REGISTER', 'UNDO'}
    mode: EnumProperty(items=[('ADD', 'Add IK', 'IK on each selected end bone'),
                              ('REMOVE', 'Remove IK', 'The IK the selected bones are in taken off')])

    @classmethod
    def poll(cls, context):
        return rig_of(context.active_object) is not None

    def execute(self, context):
        arm = rig_of(context.active_object)
        was = arm.mode
        names = selected_bones(context, arm)
        if not names:
            self.report({'WARNING'}, 'Select the bone(s) first (Pose or Edit Bones)')
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        if self.mode == 'ADD':
            done = add_ik(context, arm, names, settings(context).ik_chain)
            msg = f'IK added: {", ".join(done)}' if done else 'Nothing new: those bones have IK already or are controls'
        else:
            k = remove_ik(context, arm, names)
            msg = f'{k} IK taken off' if k else 'The selected bones are in no IK'
        for o in list(context.selected_objects):
            o.select_set(False)
        arm.select_set(True)
        context.view_layer.objects.active = arm
        if was in {'POSE', 'EDIT'}:
            bpy.ops.object.mode_set(mode='POSE')
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class MCH_TOOL_rig(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.rig'
    bl_label = 'Rig'
    bl_description = 'Rig a body (Human / Quadruped), mecha parts or a chain; click a mecha part to set its joint'
    bl_icon = 'ops.generic.select'
    bl_widget = None
    bl_keymap = (('mch.rig_click', {'type': 'LEFTMOUSE', 'value': 'CLICK'}, None),
                 ('mch.rig_guide_draw', {'type': 'LEFTMOUSE', 'value': 'CLICK_DRAG'}, None),   # 0.24.258 Guides
                 ('mch.mecha_guide_draw', {'type': 'LEFTMOUSE', 'value': 'CLICK_DRAG'}, None))  # 0.24.338

    def draw_settings(context, layout, tool):
        return


def draw(layout, context):
    st = settings(context)
    if st is None:
        return
    from . import panel_capture as pc
    ob = context.active_object
    arm = rig_of(ob)
    box = layout.box()
    box.label(text='RIG', icon='ARMATURE_DATA')
    box.row(align=True).prop(st, 'kind', expand=True)
    col = box.column(align=True)
    if st.kind in {'BODY', 'QUAD'}:
        r = col.row(align=True)
        r.prop(st, 'ik', toggle=True)
        if st.kind == 'BODY':
            r.prop(st, 'fingers', toggle=True)
            r.prop(st, 'face', toggle=True)
        r.prop(st, 'bind', toggle=True)
        if st.kind == 'BODY':
            col.row(align=True).prop(st, 'legs', expand=True)
        box.label(text='Select the body (feet on the ground, facing -Y)', icon='INFO')
    elif st.kind == 'MECHA':
        col.row(align=True).prop(st, 'auto_joints', toggle=True)
        box.label(text='Select the parts; then click a part: its joint', icon='INFO')
    elif st.kind == 'MGUIDE':                        # 0.24.338
        from . import mecha_guides
        mecha_guides.draw(box, context, st)
    elif st.kind == 'NAMED':                         # 0.24.336
        from . import mecha_named
        r = col.row(align=True)
        r.prop(st, 'seamless', toggle=True)             # 0.24.337
        r.operator('mch.rig_name_by_place', text='Name by Place', icon='SORTALPHA')
        mecha_named.draw_help(box)
        box.label(text='Select all the parts, then Make Rig', icon='INFO')
    elif st.kind == 'AUTO':
        r = col.row(align=True)
        r.prop(st, 'bind', toggle=True)
        box.label(text='Select the creature (standing on the ground): legs, tails, arms found', icon='INFO')
    elif st.kind == 'GUIDE':                         # 0.24.258
        from . import rig_guides
        rig_guides.draw(box, context, st)
    else:
        r = col.row(align=True)
        r.prop(st, 'bones')
        r.prop(st, 'bind', toggle=True)
        r = col.row(align=True)
        r.prop(st, 'jiggle', toggle=True)
        sub = r.row(align=True)
        sub.enabled = st.jiggle
        sub.prop(st, 'stiffness', slider=True)
        sub.prop(st, 'damping', slider=True)
        box.label(text='Select the tail / tentacle (+ a rig to add it to)', icon='INFO')
    r = pc.primary(box.row(align=True))
    r.scale_y = 1.3
    r.operator('mch.rig_make', text='Make Rig', icon='ARMATURE_DATA')
    if arm is not None:
        box = layout.box()
        box.label(text=f'{arm.name}  ({len(arm.data.bones)} bones)', icon='BONE_DATA')
        r = box.row(align=True)
        r.operator('mch.rig_edit', text='Edit Bones').mode = 'EDIT'
        r.operator('mch.rig_edit', text='Pose').mode = 'POSE'
        r.operator('mch.rig_bind', text='Bind')
        if arm.get(RIG_KEY) in {'BODY', 'QUAD', 'AUTO'}:
            r = box.row(align=True)
            r.operator('mch.rig_mirror', text='Mirror L -> R').side = 'L'
            r.operator('mch.rig_mirror', text='Mirror R -> L').side = 'R'
            box.label(text='Place the bones (Edit Bones: one side moves both), Mirror, then Bind', icon='INFO')
        r = box.row(align=True)
        if arm.get(RIG_KEY) == 'MECHA':
            r.operator('mch.rig_link', text='Link to Active')
            r.operator('mch.rig_piston', text='Piston (2 parts)')
        r.operator('mch.rig_jiggle', text='Jiggle On').on = True
        r.operator('mch.rig_jiggle', text='Jiggle Off').on = False
        if 'mch_curl' in arm:                        # 0.24.259 all the fingers at once
            r = box.row(align=True)
            r.prop(arm, '["mch_curl"]', text='Finger Curl', slider=True)
            r.prop(arm, '["mch_spread"]', text='Finger Spread', slider=True)
        r = box.row(align=True)                      # 0.24.257 IK where the user wants it
        r.prop(st, 'ik_chain')
        r.operator('mch.rig_ik', text='Add IK', icon='CON_KINEMATIC').mode = 'ADD'
        r.operator('mch.rig_ik', text='Remove IK', icon='X').mode = 'REMOVE'
        box.label(text='IK: select the end bone(s) in Pose / Edit Bones, then Add IK', icon='INFO')
        box.row(align=True).operator('mch.rig_delete', text='Delete Rig', icon='TRASH')
        from . import locomotion                 # 0.24.244 Auto Animation + Unreal FBX
        locomotion.draw(layout, context)
        if arm.get(RIG_KEY) == 'MECHA':
            sub = layout.box()
            sub.label(text='TURN LIMIT  (the active part)', icon='CON_ROTLIMIT')
            sub.row(align=True).prop(st, 'axis', expand=True)
            r = sub.row(align=True)
            r.prop(st, 'lo')
            r.prop(st, 'hi')
            r = sub.row(align=True)
            r.operator('mch.rig_limit', text='Limit Turn').kind = 'LIMIT'
            r.operator('mch.rig_limit', text='Turn Free').kind = 'FREE'
            r = sub.row(align=True)
            r.prop(st, 'hatch')
            r.operator('mch.rig_limit', text='Hatch').kind = 'HATCH'


CLASSES = (MCH_PG_Rig, MCH_OT_rig_make, MCH_OT_rig_name_by_place, MCH_OT_rig_bind, MCH_OT_rig_edit, MCH_OT_rig_link, MCH_OT_rig_jiggle,
           MCH_OT_rig_mirror, MCH_OT_rig_limit, MCH_OT_rig_piston, MCH_OT_rig_click, MCH_OT_rig_delete, MCH_OT_rig_ik)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    from . import rig_guides                         # 0.24.258
    rig_guides.register()
    bpy.types.Scene.mch_rig = PointerProperty(type=MCH_PG_Rig)
    _ensure_handler()
    if _edit_watch not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_edit_watch)
    try:
        bpy.utils.register_tool(MCH_TOOL_rig, separator=False, group=False)
    except (ValueError, RuntimeError, KeyError):
        pass


def unregister():
    try:
        bpy.utils.unregister_tool(MCH_TOOL_rig)
    except (ValueError, RuntimeError, KeyError):
        pass
    if _jiggle in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(_jiggle)
    if _edit_watch in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_edit_watch)
    _EDITING.clear()
    if hasattr(bpy.types.Scene, 'mch_rig'):
        del bpy.types.Scene.mch_rig
    from . import rig_guides
    rig_guides.unregister()
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
