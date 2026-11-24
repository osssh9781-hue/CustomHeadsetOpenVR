"""0.24.317 Turbine (user, five photos - a composite fan, an electric motor, an afterburner nozzle, jet exhausts, a
spacecraft engine: "터빈 메뉴도 만들어 줘").

A turbine on the 3D cursor, its axis along X (the front looking down -X): a Body and a Rotor (the part that turns -
Spin turns it, live).  Styles:
* Fan - curved, twisted blades on a hub with a spinner, in a casing; a row of stator vanes behind (on / off)
* Motor - a laminated stator with copper coils round its teeth, a slotted rotor on a stepped shaft
* Nozzle - overlapping petals (Open: how wide), a glowing liner, flame-holder spokes and a centre cone
* Engine - the fan, a ribbed body and the nozzle in one
Blades: count, root / tip twist, sweep, width, thickness.  The sliders change the selected turbine."""
from __future__ import annotations

import json
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import mech_revolve as mr
from . import click_place  # 0.24.320 a click summons it there

TAG = 'mch_turbine'
PART = 'mch_turbine_part'
PARAMS = 'mch_turbine_p'
_BUSY = [False]
AX = Vector((1, 0, 0))

STYLES = (('FAN', 'Fan', 'Curved, twisted blades on a hub with a spinner, in a casing'),
          ('MOTOR', 'Motor', 'A laminated stator with copper coils round its teeth, a slotted rotor on a shaft'),
          ('NOZZLE', 'Nozzle', 'Overlapping petals, a glowing liner, flame-holder spokes and a centre cone'),
          ('ENGINE', 'Engine', 'The fan, a ribbed body and the nozzle in one'))
KEYS = ('style', 'diameter', 'length', 'blades', 'twist_root', 'twist_tip', 'sweep', 'chord', 'blade_t', 'hub',
        'spinner', 'casing', 'casing_t', 'stators', 'teeth', 'petals', 'open', 'spokes', 'ribs', 'segs')
MATS = (('MCH Turbine Metal', (0.55, 0.56, 0.58), 0.9, 0.3, None),
        ('MCH Turbine Blade', (0.05, 0.6, 0.65), 0.2, 0.35, None),
        ('MCH Turbine Copper', (0.65, 0.33, 0.18), 1.0, 0.3, None),
        ('MCH Turbine Glow', (1.0, 0.35, 0.05), 0.0, 0.5, 6.0),
        ('MCH Turbine Dark', (0.06, 0.06, 0.07), 0.3, 0.5, None))


def _st(context):
    return context.scene.mch_turbine


def numbers(st):
    return {k: getattr(st, k) for k in KEYS}


def X(origin=0.0):
    """A frame putting a revolve's Z along X, at ``origin`` along it."""
    return mr.frame(AX * origin, AX)


# --- parts --------------------------------------------------------------------------------------------------------

def solid_sheet(bm, T, Bt, mat):
    """A closed solid between two grids of points (``T`` top, ``Bt`` bottom, [v][u])."""
    nv, nu = len(T), len(T[0])
    VT = [[bm.verts.new(p) for p in row] for row in T]
    VB = [[bm.verts.new(p) for p in row] for row in Bt]
    fs = []
    for i in range(nv - 1):
        for j in range(nu - 1):
            fs.append((VT[i][j], VT[i][j + 1], VT[i + 1][j + 1], VT[i + 1][j]))
            fs.append((VB[i][j], VB[i + 1][j], VB[i + 1][j + 1], VB[i][j + 1]))
    for i in range(nv - 1):                                 # (the leading and trailing edges)
        fs.append((VT[i][0], VT[i + 1][0], VB[i + 1][0], VB[i][0]))
        fs.append((VT[i][-1], VB[i][-1], VB[i + 1][-1], VT[i + 1][-1]))
    for j in range(nu - 1):                                 # (the root and the tip)
        fs.append((VT[0][j], VB[0][j], VB[0][j + 1], VT[0][j + 1]))
        fs.append((VT[-1][j], VT[-1][j + 1], VB[-1][j + 1], VB[-1][j]))
    for f in fs:
        try:
            bm.faces.new(f).material_index = mat
        except ValueError:
            pass


def blade(bm, theta0, r0, r1, x0, chord, t, tw0, tw1, sweep, mat, flip=1.0):
    """One blade from ``r0`` to ``r1`` round X at angle ``theta0``: twisted from ``tw0`` to ``tw1`` degrees off the
    axis, its chord ``chord`` (wider toward the tip), swept round by ``sweep`` (radians at the tip)."""
    nv, nu = 12, 7
    T, Bt = [], []
    for i in range(nv):
        v = i / (nv - 1)
        r = r0 + (r1 - r0) * v
        phi = math.radians(tw0 + (tw1 - tw0) * v) * flip
        w = chord * (0.75 + 0.5 * v)
        th = theta0 + sweep * (v ** 1.6) * flip
        rowT, rowB = [], []
        for j in range(nu):
            u = j / (nu - 1) - 0.5
            th_ = t * (1.0 - 0.6 * v) * (0.3 + 0.7 * math.sqrt(max(1.0 - 4.0 * u * u, 0.0)))
            for s, row in ((1, rowT), (-1, rowB)):
                ax = x0 + u * w * math.cos(phi) - s * th_ / 2 * math.sin(phi)
                tg = u * w * math.sin(phi) + s * th_ / 2 * math.cos(phi)
                a = th + tg / max(r, 1e-6)
                row.append(Vector((ax, r * math.cos(a), r * math.sin(a))))
        T.append(rowT)
        Bt.append(rowB)
    solid_sheet(bm, T, Bt, mat)


def fan_rotor(bm, p, x0=0.0):
    """The fan: its blades, the hub, the spinner (the rotor)."""
    R = p['diameter'] / 2
    rh = R * p['hub']
    n = max(2, int(p['blades']))
    chord = R * p['chord']
    for k in range(n):
        blade(bm, 2 * math.pi * k / n, rh * 0.95, R * 0.97, x0, chord, R * p['blade_t'], p['twist_root'],
              p['twist_tip'], math.radians(p['sweep']), 1)
    L = chord * 1.4
    segs = max(32, int(p['segs']))
    P = [(0.0, x0 - L * 0.5, 0.0, 'R')] if not p['spinner'] else []
    if p['spinner']:                                          # (a spinner cone in front)
        sl = rh * 1.6
        for i in range(9):
            a = i / 8 * math.pi / 2
            P.append((rh * math.sin(a), x0 - L * 0.5 - sl * math.cos(a), 0.0, 'R'))
    P += [(rh, x0 - L * 0.5, 0.0, 'R'), (rh, x0 + L * 0.6, 0.0, 'R'), (0.0, x0 + L * 0.6, 0.0, 'R')]
    mr.revolve(bm, P, segs, matrix=X(), mat=4 if p['spinner'] else 0)
    if p['spinner']:                                          # (a spiral line on the spinner: a thin ring)
        mr.revolve(bm, [(rh * 0.55, x0 - L * 0.5 - rh * 1.25, 0.0, 'R'), (rh * 0.62, x0 - L * 0.5 - rh * 1.25, 0.0, 'R'),
                        (rh * 0.62, x0 - L * 0.5 - rh * 1.18, 0.0, 'R'), (rh * 0.55, x0 - L * 0.5 - rh * 1.18, 0.0, 'R')],
                   segs, matrix=X(), mat=0)
    return L


def casing(bm, p, xa, xb):
    R = p['diameter'] / 2
    ct = R * p['casing_t']
    ri = R * 1.0
    lip = ct * 0.6
    P = [(ri, xb, 0.0, 'R'), (ri, xa, 0.0, 'R'), (ri + ct + lip, xa, 0.0, 'R'), (ri + ct + lip, xa + ct, 0.0, 'R'),
         (ri + ct, xa + ct * 1.6, 0.0, 'R'), (ri + ct, xb, 0.0, 'R')]
    mr.revolve(bm, P, max(48, int(p['segs']) * 2), matrix=X(), mat=0)


def stators(bm, p, x0):
    R = p['diameter'] / 2
    rh = R * p['hub']
    n = max(3, int(round(p['blades'] * 1.6)))
    for k in range(n):
        blade(bm, 2 * math.pi * (k + 0.5) / n, rh * 0.95, R * 1.01, x0, R * p['chord'] * 0.45, R * p['blade_t'] * 0.8,
              -15, -10, 0.0, 4)
    mr.revolve(bm, [(0.0, x0 - R * 0.1, 0.0, 'R'), (rh, x0 - R * 0.1, 0.0, 'R'), (rh, x0 + R * 0.2, 0.0, 'R'),
                    (0.0, x0 + R * 0.2, 0.0, 'R')], max(32, int(p['segs'])), matrix=X(), mat=4)


def nozzle(bm, p, xa, R=None):
    """Petals round a converging / diverging exhaust from ``xa`` back, a glowing liner, spokes and a cone."""
    R = R or p['diameter'] / 2
    L = max(p['length'] * 0.35, R * 0.8)
    n = max(6, int(p['petals']))
    op = math.radians(p['open'])
    rs = R * 0.92                                             # (where they start)
    span = 2 * math.pi / n * 1.12                             # (each petal's width as an angle: wider than its step - they overlap)
    t = R * 0.025
    for k in range(n):
        th0 = 2 * math.pi * k / n
        T, Bt = [], []
        lift = t * 1.1 * (k % 2)                              # (every other one over its neighbours)
        for i in range(6):
            v = i / 5
            x = xa + L * v
            r = rs + L * v * math.tan(op) + lift
            w = span * (1.0 - 0.15 * v)
            rowT, rowB = [], []
            for j in range(5):
                a = th0 + (j / 4 - 0.5) * w
                rowT.append(Vector((x, (r + t) * math.cos(a), (r + t) * math.sin(a))))
                rowB.append(Vector((x, r * math.cos(a), r * math.sin(a))))
            T.append(rowT)
            Bt.append(rowB)
        solid_sheet(bm, T, Bt, 4)
    segs = max(48, int(p['segs']) * 2)
    mr.revolve(bm, [(R * 0.98, xa - R * 0.15, 0.0, 'R'), (R * 1.04, xa - R * 0.15, 0.0, 'R'), (R * 1.04, xa + R * 0.05, 0.0, 'R'),
                    (R * 0.98, xa + R * 0.05, 0.0, 'R')], segs, matrix=X(), mat=0)   # (the ring they hang on)
    ri = rs * 0.97                                            # (the liner inside, glowing)
    mr.revolve(bm, [(ri, xa + L * 0.85, 0.0, 'R'), (ri, xa - R * 0.1, 0.0, 'R'), (ri * 0.96, xa - R * 0.1, 0.0, 'R'),
                    (ri * 0.96, xa + L * 0.85, 0.0, 'R')], segs, matrix=X(), mat=3)
    xs = xa - R * 0.05                                        # (flame holder: spokes, a ring, a cone)
    ns = max(3, int(p['spokes']))
    for k in range(ns):
        a = 2 * math.pi * k / ns
        d = Vector((0, math.cos(a), math.sin(a)))
        side = AX.cross(d)
        rr = R * 0.04
        vs = []
        for rad in (R * 0.18, ri * 0.95):
            for s1 in (-1, 1):
                for s2 in (-1, 1):
                    vs.append(bm.verts.new(AX * (xs + s1 * rr) + d * rad + side * s2 * rr * 0.6))
        for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            bm.faces.new([vs[i] for i in q]).material_index = 4
    mr.revolve(bm, [(R * 0.5, xs - R * 0.05, 0.0, 'R'), (R * 0.58, xs - R * 0.05, 0.0, 'R'), (R * 0.58, xs + R * 0.05, 0.0, 'R'),
                    (R * 0.5, xs + R * 0.05, 0.0, 'R')], segs, matrix=X(), mat=4)
    cone = [(0.0, xs - R * 0.25, 0.0, 'R'), (R * 0.2, xs - R * 0.1, 0.0, 'R'), (R * 0.2, xs + R * 0.1, 0.0, 'R'),
            (0.0, xs + R * 0.55, 0.0, 'R')]
    mr.revolve(bm, cone, segs, matrix=X(), mat=4)
    return L


def motor_body(bm, p):
    """The stator: a laminated ring, teeth round its inside, a copper coil round each."""
    R = p['diameter'] / 2
    L = max(p['length'] * 0.5, R * 0.6)
    yoke = R * 0.14
    rin = R * 0.55
    segs = max(64, int(p['segs']) * 2)
    P = []
    nl = 24
    for i in range(nl + 1):                                   # (its outside in laminations: little ridges)
        x = -L / 2 + L * i / nl
        P.append((R * (0.985 if i % 2 else 1.0), x, 0.0, 'R'))
    P += [(R - yoke, L / 2, 0.0, 'R'), (R - yoke, -L / 2, 0.0, 'R')]
    mr.revolve(bm, P, segs, matrix=X(), mat=0)
    n = max(3, int(p['teeth']))
    for k in range(n):
        a = 2 * math.pi * k / n
        d = Vector((0, math.cos(a), math.sin(a)))
        side = AX.cross(d)
        tw = 2 * math.pi * rin / n * 0.32
        for (r0, r1, hw, hl, mat) in ((rin, R - yoke + 0.001 * R, tw, L / 2, 0),           # (the tooth)
                                      (rin + R * 0.06, R - yoke - R * 0.02, tw * 1.9, L / 2 + R * 0.08, 2)):  # (its coil)
            vs = [bm.verts.new(AX * (s1 * hl) + d * rr + side * s2 * hw) for rr in (r0, r1) for s1 in (-1, 1)
                  for s2 in (-1, 1)]
            for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
                bm.faces.new([vs[i] for i in q]).material_index = mat
        # (the coil's windings: thin copper rings round it, at its ends)
    mr.revolve(bm, [(R * 0.99, -L / 2 - R * 0.1, 0.0, 'R'), (R * 1.04, -L / 2 - R * 0.1, 0.0, 'R'),
                    (R * 1.04, -L / 2 + R * 0.02, 0.0, 'R'), (R * 0.99, -L / 2 + R * 0.02, 0.0, 'R')], segs, matrix=X(),
               mat=4)                                         # (an end ring - into the core, no edge shared with it)
    return L


def motor_rotor(bm, p):
    R = p['diameter'] / 2
    L = max(p['length'] * 0.5, R * 0.6)
    rr = R * 0.5
    segs = max(64, int(p['segs']) * 2)
    mr.revolve(bm, [(rr * 0.3, -L / 2, 0.0, 'R'), (rr, -L / 2, 0.0, 'C'), (rr, L / 2, 0.0, 'C'), (rr * 0.3, L / 2, 0.0, 'R')],
               segs, sq_p=max(6, int(p['teeth']) * 2), matrix=X(), mat=0)
    sh = R * 0.12                                            # (a stepped shaft out the front, a flange)
    P = [(0.0, -L / 2 - R * 1.1, 0.0, 'R'), (sh * 0.8, -L / 2 - R * 1.1, 0.0, 'R'), (sh * 0.8, -L / 2 - R * 0.7, 0.0, 'R'),
         (sh, -L / 2 - R * 0.65, 0.0, 'R'), (sh, -L / 2 - R * 0.25, 0.0, 'R'), (sh * 2.4, -L / 2 - R * 0.2, 0.0, 'R'),
         (sh * 2.4, -L / 2 + R * 0.05, 0.0, 'R'), (sh * 1.3, -L / 2 + R * 0.05, 0.0, 'R'), (sh * 1.3, L / 2 + R * 0.4, 0.0, 'R'),
         (0.0, L / 2 + R * 0.4, 0.0, 'R')]
    mr.revolve(bm, P, segs, matrix=X(), mat=0)
    mr.revolve(bm, [(sh * 0.3, -L / 2 - R * 1.12, 0.0, 'R'), (sh * 0.5, -L / 2 - R * 1.12, 0.0, 'R'),
                    (sh * 0.5, -L / 2 - R * 1.09, 0.0, 'R'), (sh * 0.3, -L / 2 - R * 1.09, 0.0, 'R')], 24,
               matrix=X(), mat=4)


def body_shell(bm, p, xa, xb, R):
    """Engine: a body with rings (ribs) round it."""
    segs = max(48, int(p['segs']) * 2)
    rb = R * 1.08
    mr.revolve(bm, [(R * 0.97, xb, 0.0, 'R'), (R * 0.97, xa, 0.0, 'R'), (rb, xa, 0.0, 'R'), (rb, xb, 0.0, 'R')], segs,
               matrix=X(), mat=0)                             # (a little into the casing: no edge shared with it)
    n = int(p['ribs'])
    for k in range(n):
        x = xa + (xb - xa) * (k + 0.5) / n
        w = (xb - xa) / max(n, 1) * 0.18
        mr.revolve(bm, [(rb * 0.99, x - w, 0.0, 'R'), (rb * 1.05, x - w, 0.0, 'R'), (rb * 1.05, x + w, 0.0, 'R'),
                        (rb * 0.99, x + w, 0.0, 'R')], segs, matrix=X(), mat=4)


def build_parts(body_me, rotor_me, p):
    bb, rb_ = bmesh.new(), bmesh.new()
    try:
        R = p['diameter'] / 2
        st = p['style']
        if st in {'FAN', 'ENGINE'}:
            L = fan_rotor(rb_, p, 0.0)
            if p['casing']:
                casing(bb, p, -L * 0.9, L * (1.6 if p['stators'] else 0.9))
            if p['stators']:
                stators(bb, p, L * 0.95)
            if st == 'ENGINE':
                xa = L * 1.7
                xb = xa + max(p['length'] * 0.6, R)
                body_shell(bb, p, xa - L * 0.15, xb, R * (1.0 + p['casing_t']))
                nozzle(bb, p, xb, R * 0.9)
        elif st == 'MOTOR':
            motor_body(bb, p)
            motor_rotor(rb_, p)
        else:
            nozzle(bb, p, 0.0)
        for bm_, me in ((bb, body_me), (rb_, rotor_me)):
            mr.finish(bm_, smooth_angle=35.0)
            bm_.to_mesh(me)
            me.update()
    finally:
        bb.free()
        rb_.free()


# --- objects ----------------------------------------------------------------------------------------------------------

def turbine_of(ob):
    return ob.get(TAG, '') if ob is not None else ''


def parts_of(scene, tid):
    return {o.get(PART, ''): o for o in scene.objects if turbine_of(o) == tid}


def _mats(me):
    if len(me.materials):
        return
    for name, col, metal, rough, glow in MATS:
        m = bpy.data.materials.get(name)
        if m is None:
            m = bpy.data.materials.new(name)
            m.use_nodes = True
            b = m.node_tree.nodes.get('Principled BSDF')
            if b is not None:
                b.inputs['Base Color'].default_value = (*col, 1.0)
                b.inputs['Metallic'].default_value = metal
                b.inputs['Roughness'].default_value = rough
                if glow:
                    for nm in ('Emission Color', 'Emission'):
                        if nm in b.inputs:
                            b.inputs[nm].default_value = (*col, 1.0)
                            break
                    if 'Emission Strength' in b.inputs:
                        b.inputs['Emission Strength'].default_value = glow
            m.diffuse_color = (*col, 1.0)
        me.materials.append(m)


def build(context, p, tid=None):
    scene = context.scene
    old = parts_of(scene, tid) if tid else {}
    if not tid:
        k = 1
        names = {turbine_of(o) for o in scene.objects}
        while f'Turbine{k}' in names:
            k += 1
        tid = f'Turbine{k}'
    body, rotor = old.get('BODY'), old.get('ROTOR')
    coll = body.users_collection[0] if body is not None and body.users_collection else context.collection
    for part in ('BODY', 'ROTOR'):
        if old.get(part) is None:
            nm = f'MCH_{tid}_{part.title()}'
            ob = bpy.data.objects.new(nm, bpy.data.meshes.new(nm))
            coll.objects.link(ob)
            ob[TAG], ob[PART] = tid, part
            old[part] = ob
    body, rotor = old['BODY'], old['ROTOR']
    if body.get(PARAMS) is None:
        body.matrix_world = Matrix.Translation(scene.cursor.location)
    for ob in (body, rotor):
        if ob.data.users > 1:
            ob.data = ob.data.copy()
    if body.mode != 'EDIT' and rotor.mode != 'EDIT':
        build_parts(body.data, rotor.data, p)
    # 0.24.318 (user: "터빈은 다 재질 없음으로 해 줘, 내가 알아서 넣을게"): no materials made or given - the parts
    # keep their slot numbers (0 metal, 1 blades, 2 copper, 3 glow, 4 dark) for slots you add
    rotor.parent = body
    rotor.matrix_parent_inverse = Matrix.Identity(4)
    body[PARAMS] = json.dumps(p)
    set_spin(scene, tid, float(body.get('mch_turbine_spin', 0.0)))
    return tid, {'BODY': body, 'ROTOR': rotor}


def set_spin(scene, tid, deg):
    parts = parts_of(scene, tid)
    body, rotor = parts.get('BODY'), parts.get('ROTOR')
    if body is None or rotor is None:
        return
    body['mch_turbine_spin'] = float(deg)
    rotor.matrix_basis = Matrix.Rotation(math.radians(deg), 4, 'X')


def selected_turbines(context):
    out = []
    for o in context.selected_objects:
        t = turbine_of(o)
        if t and t not in out:
            out.append(t)
    return out


def _update(self, context):
    if _BUSY[0]:
        return
    p = numbers(self)
    for t in selected_turbines(context):
        build(context, p, t)


def _spin_update(self, context):
    for t in selected_turbines(context):
        set_spin(context.scene, t, self.spin)


class MCH_PG_Turbine(bpy.types.PropertyGroup):
    style: bpy.props.EnumProperty(name='Style', items=STYLES, default='FAN', update=_update)
    diameter: bpy.props.FloatProperty(name='Diameter', default=1.0, min=0.01, soft_max=10.0, unit='LENGTH',
                                      update=_update)
    length: bpy.props.FloatProperty(name='Length', default=1.6, min=0.01, soft_max=20.0, unit='LENGTH', update=_update,
                                    description='Motor / Nozzle / Engine: how long')
    blades: bpy.props.IntProperty(name='Blade Count', default=18, min=2, max=80, update=_update)
    twist_root: bpy.props.FloatProperty(name='Twist Root', default=25.0, min=-89.0, max=89.0, update=_update,
                                        description='The blade\'s angle off the axis at the hub (degrees)')
    twist_tip: bpy.props.FloatProperty(name='Twist Tip', default=62.0, min=-89.0, max=89.0, update=_update,
                                       description='The blade\'s angle off the axis at the tip (degrees)')
    sweep: bpy.props.FloatProperty(name='Sweep', default=18.0, min=-60.0, max=60.0, update=_update,
                                   description='How far round the blades curve toward their tips (degrees)')
    chord: bpy.props.FloatProperty(name='Blade Width', default=0.32, min=0.02, max=1.5, update=_update,
                                   description='The blades\' width, of the radius')
    blade_t: bpy.props.FloatProperty(name='Blade Thickness', default=0.03, min=0.002, max=0.3, update=_update,
                                     description='Of the radius')
    hub: bpy.props.FloatProperty(name='Hub', default=0.26, min=0.05, max=0.9, subtype='FACTOR', update=_update,
                                 description='The hub across, of the diameter')
    spinner: bpy.props.BoolProperty(name='Spinner', default=True, update=_update, description='A cone in front')
    casing: bpy.props.BoolProperty(name='Casing', default=True, update=_update, description='A ring round the fan')
    casing_t: bpy.props.FloatProperty(name='Casing Thickness', default=0.06, min=0.005, max=0.5, update=_update)
    stators: bpy.props.BoolProperty(name='Stator Vanes', default=True, update=_update,
                                    description='A row of fixed vanes behind the fan')
    teeth: bpy.props.IntProperty(name='Coils', default=12, min=3, max=60, update=_update,
                                 description='Motor: the stator\'s teeth (a coil round each)')
    petals: bpy.props.IntProperty(name='Petals', default=16, min=6, max=60, update=_update,
                                  description='Nozzle: the overlapping petals')
    open: bpy.props.FloatProperty(name='Petal Angle', default=-8.0, min=-30.0, max=30.0, update=_update,
                                  description='Nozzle: the petals\' angle (minus: closing in, plus: opening out)')
    spokes: bpy.props.IntProperty(name='Spokes', default=10, min=3, max=40, update=_update,
                                  description='Nozzle: the flame holder\'s spokes')
    ribs: bpy.props.IntProperty(name='Body Rings', default=5, min=0, max=40, update=_update,
                                description='Engine: rings round its body')
    segs: bpy.props.IntProperty(name='Segments', default=48, min=12, max=256, update=_update)
    spin: bpy.props.FloatProperty(name='Spin', default=0.0, soft_min=-360.0, soft_max=360.0, update=_spin_update,
                                  description='The rotor turned (degrees) - live')


class MCH_OT_turbine_add(bpy.types.Operator):
    """A turbine on the 3D cursor (its axis along X) - its sliders change it while selected"""
    bl_idname = 'mch.turbine_add'
    bl_label = 'Summon Turbine'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            self.report({'WARNING'}, 'Turbine: Object Mode only')
            return {'CANCELLED'}
        tid, parts = build(context, numbers(_st(context)))
        for o in context.selected_objects:
            o.select_set(False)
        for o in parts.values():
            o.select_set(True)
        context.view_layer.objects.active = parts['BODY']
        return {'FINISHED'}


class MCH_OT_turbine_plain(bpy.types.Operator):
    """Keep the selected turbines as plain meshes (the sliders leave them alone after)"""
    bl_idname = 'mch.turbine_plain'
    bl_label = 'Make Plain'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ts_ = selected_turbines(context)
        for t in ts_:
            for o in parts_of(context.scene, t).values():
                for k in (TAG, PART, PARAMS):
                    if k in o.keys():
                        del o[k]
        return {'FINISHED'} if ts_ else {'CANCELLED'}


def draw(layout, context):
    st = _st(context)
    box = layout.box()
    box.label(text='Turbine')
    box.prop(st, 'style', text='')
    c = box.column(align=True)
    c.prop(st, 'diameter')
    if st.style != 'FAN':
        c.prop(st, 'length')
    if st.style in {'FAN', 'ENGINE'}:
        c = box.column(align=True)
        c.label(text='Fan Blades')
        for k in ('blades', 'twist_root', 'twist_tip', 'sweep', 'chord', 'blade_t', 'hub'):
            c.prop(st, k)
        r = box.row(align=True)
        r.prop(st, 'spinner')
        r.prop(st, 'stators')
        r = box.row(align=True)
        r.prop(st, 'casing')
        sub = r.row(align=True)
        sub.active = st.casing
        sub.prop(st, 'casing_t', text='Thickness')
    if st.style == 'MOTOR':
        box.prop(st, 'teeth')
    if st.style in {'NOZZLE', 'ENGINE'}:
        c = box.column(align=True)
        c.label(text='Nozzle')
        for k in ('petals', 'open', 'spokes'):
            c.prop(st, k)
        if st.style == 'ENGINE':
            c.prop(st, 'ribs')
    box.prop(st, 'spin', slider=False)
    box.prop(st, 'segs')
    box.operator('mch.turbine_add', icon='FORCE_VORTEX')
    n = len(selected_turbines(context))
    if n:
        box.label(text=f'{n} turbine(s) selected: live', icon='INFO')
        box.operator('mch.turbine_plain', icon='CHECKMARK')
    else:
        box.label(text='Select a turbine: the sliders change it', icon='INFO')


class MCH_TOOL_turbine(bpy.types.WorkSpaceTool):
    """0.24.317 Turbine"""
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.turbine_gen'
    bl_label = 'Turbine'
    bl_description = ('Click: a turbine where you click (Fan / Motor / Nozzle / Engine) - select it and the sliders '
                      'change it; Spin turns its rotor')
    bl_icon = 'ops.generic.select'
    bl_widget = None
    bl_keymap = click_place.keymap('mch.turbine_click')  # 0.24.320

    def draw_settings(context, layout, tool):
        region = getattr(context, 'region', None)
        if region is not None and region.type == 'TOOL_HEADER':
            return


class MCH_OT_turbine_click(bpy.types.Operator):
    """Click: a turbine there (on the surface hit, else on the ground); a click on a turbine selects it"""
    bl_idname = 'mch.turbine_click'
    bl_label = 'Turbine Where Clicked'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        from . import click_place
        return click_place.poll(context)

    def invoke(self, context, event):
        from . import click_place
        return click_place.click(self, context, event, lambda ob: bool(turbine_of(ob)), lambda: bpy.ops.mch.turbine_add())


CLASSES = (MCH_PG_Turbine, MCH_OT_turbine_add, MCH_OT_turbine_click, MCH_OT_turbine_plain)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_turbine = bpy.props.PointerProperty(type=MCH_PG_Turbine)
    try:
        bpy.utils.register_tool(MCH_TOOL_turbine, separator=False, group=False)
    except (ValueError, RuntimeError, KeyError):
        pass


def unregister():
    try:
        bpy.utils.unregister_tool(MCH_TOOL_turbine)
    except (ValueError, RuntimeError, KeyError):
        pass
    try:
        del bpy.types.Scene.mch_turbine
    except AttributeError:
        pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
