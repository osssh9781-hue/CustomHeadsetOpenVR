"""0.24.95 Armor Plate: the edge lines creased on the FINAL plate (user: "아머 플레이트 할 때 나오는 메시들도 엣지 부분에
크리즈 남겨 줄래?").  The plate's own mesh was marked already; its Bevel / Solidify modifiers make new edges after that
(the bevel's border lines, the shell's corners: no crease) and copied the crease of a beveled edge onto the rows
inside the round strip.  Now a node group last on the stack creases the result again, and Apply marks the applied
mesh the same way."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Quaternion

import mecha_lab
from mecha_lab import armor_plate as ap, core_geometry as cg, edge_memory as em, face_extract as fx

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion())
BOX = [[(300, 300), (700, 300), (700, 700), (300, 700)]]
ANGLE = math.radians(30.0)


def edge_lines(me):
    """bool per edge: open, or faces meeting at more than 30 degrees, or the plate's surface lines."""
    e_s, f_s, st, en = em._edge_faces(me)
    cnt = en - st
    out = np.zeros(len(me.edges), bool)
    out[e_s[st[cnt != 2]]] = True
    s2 = st[cnt == 2]
    n = np.empty(len(me.polygons) * 3, np.float32)
    me.polygons.foreach_get('normal', n)
    n = n.reshape(-1, 3)
    d = np.einsum('ij,ij->i', n[f_s[s2]], n[f_s[s2 + 1]])
    out[e_s[s2[d < math.cos(ANGLE) - 1e-3]]] = True
    near = e_s[s2[np.abs(d - math.cos(ANGLE)) <= 1e-3]]      # (right at the angle: either way is fine)
    lines = me.attributes.get('mch_crease')
    if lines is not None and lines.domain == 'EDGE':
        v = np.zeros(len(me.edges), np.float32)
        lines.data.foreach_get('value', v)
        out |= v > 0.5
    return out, near


def creased(me):
    a = me.attributes.get('crease_edge')
    c = np.zeros(len(me.edges), np.float32)
    if a is not None:
        a.data.foreach_get('value', c)
    return c > 0.5


def judge(me):
    want, near = edge_lines(me)
    got = creased(me)
    bad = (want != got)
    bad[near] = False
    return int(want.sum()), int(bad.sum()), int(em.count(me))


for preset in ('FLAT', 'CHAMFER', 'SOFT', 'ROUND', 'HEAVY', 'SHELL'):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=3, segments=64, ring_count=32, location=(0, 0, -2.6))
    body = C.active_object
    S.mch_plate.preset = preset
    ap.perform_plate(C, BOX, TOP)
    part = next(o for o in bpy.data.objects if o is not body and o.type == 'MESH')
    mods = [m.name for m in part.modifiers]
    makes = any(m.type in {'BEVEL', 'SOLIDIFY'} for m in part.modifiers)
    check(f'{preset}: the crease node modifier is last on the stack when the plate has a Bevel / Solidify, absent when not',
          (mods[-1] == em.CREASE_MOD) if makes else (em.CREASE_MOD not in mods), mods)
    dg = C.evaluated_depsgraph_get()
    ev = bpy.data.meshes.new_from_object(part.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    n, bad, marks = judge(ev)
    bpy.data.meshes.remove(ev)
    check(f'{preset}: the live plate (with its modifiers) - every edge line creased (rim, chamfer lines, bevel borders, '
          'shell corners), nothing else (no crease inside a round bevel); the Edge Memory marks on the same edges',
          n > 0 and bad == 0 and marks == n, (n, bad, marks))
    ap.apply_plate(part)
    n, bad, marks = judge(part.data)
    check(f'{preset}: Apply - the plain mesh keeps exactly those creases and marks, no modifiers left',
          n > 0 and bad == 0 and marks == n and len(part.modifiers) == 0, (n, bad, marks))

# ---- a slider change rebuilds: the modifier follows (bevel off -> gone)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add(radius=3, segments=64, ring_count=32, location=(0, 0, -2.6))
S.mch_plate.preset = 'SOFT'
ap.perform_plate(C, BOX, TOP)
part = next(o for o in bpy.data.objects if o.name.endswith('_Plate') or 'Plate' in o.name)
part.mch_extract.bevel_width = 0.0
fx.rebuild(part)
check('Bevel set to 0 and rebuilt: the crease modifier goes with the bevel', em.CREASE_MOD not in part.modifiers,
      [m.name for m in part.modifiers])
check('One shared node group "MCH Edge Crease" (not one per plate)',
      len([g for g in bpy.data.node_groups if g.name.startswith(em.CREASE_GROUP)]) == 1)
# ---- Face Extract's own Apply (the part's modifiers applied one by one): the crease step goes in too
part.mch_extract.bevel_width = 0.02
fx.rebuild(part)
for o in C.selected_objects:
    o.select_set(False)
part.select_set(True)
C.view_layer.objects.active = part
r = bpy.ops.mch.extract_apply()
n, bad, marks = judge(part.data)
check('Face Extract Apply on a beveled plate: every modifier applied (the crease one too), the edge lines creased',
      r == {'FINISHED'} and len(part.modifiers) == 0 and n > 0 and bad == 0, ([m.name for m in part.modifiers], n, bad))
summary()
