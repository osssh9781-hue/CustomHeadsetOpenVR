"""0.24.170 (user: "그리블 할 때 어플라이 안 해도 내가 재질 바꿀 수 있게 해 줘, 크리쳐도 그렇고"): a live Greeble Line /
Scale Line takes a material - its first material slot (a Mech / Creature page preset on the selected line, Blender's
own slots, or the window's Body's Material) goes onto every part while it is still live; Parts' Own gives the parts
their own materials back; Apply keeps it.  Measured on the evaluated lines."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import greeble_line as gl, mech_shader as ms  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24)
ball = C.active_object
skin = bpy.data.materials.new('Skin')
ball.data.materials.append(skin)
partmat = bpy.data.materials.new('Part Paint')


def line(which, kind, yy):
    made = gl.make_starters(C, ball, which)
    for p in made:
        p.data.materials.clear()
        p.data.materials.append(partmat)              # (the parts' own material)
    C.view_layer.update()                             # (the parts' sizes - as by the time a line is drawn)
    stg = gl.settings(S, kind)
    pts, nrm = [], []
    for t in np.linspace(-0.9, 0.9, 40):
        v = Vector((math.sin(t), yy, math.cos(t))).normalized()
        pts.append(tuple(v))
        nrm.append(tuple(v))
    ln = gl.new_line(C, ball, pts, nrm, gl.picked(stg), stg, kind)
    gl.rebuild(ln, C)
    return ln


def ev_mats(ln):
    """The materials the evaluated line's faces use (realized: by face; instances: the parts' own)."""
    C.view_layer.update()
    dg = C.evaluated_depsgraph_get()
    e = ln.evaluated_get(dg)
    me = e.data
    if len(me.polygons):
        idx = np.zeros(len(me.polygons), np.int32)
        me.polygons.foreach_get('material_index', idx)
        return {(me.materials[i].name if i < len(me.materials) and me.materials[i] else None) for i in np.unique(idx)}
    out = set()
    for inst in dg.object_instances:
        if inst.is_instance and inst.parent and inst.parent.original == ln:
            ob = inst.object
            out |= {m.name if m else None for m in ob.data.materials}
    return out


scl = line('SCALES', 'CREATURE', -0.4)
check(f'a live Scale Line with no material: its parts keep their own ({ev_mats(scl)})', ev_mats(scl) == {'Part Paint'})
mat = ms.new_material(ms.PRESET_IDS[0])
ms.assign(C, [scl], mat)                                 # (what a Mech page preset does to the selected line)
check(f'a Mech page preset on the selected live Scale Line: every scale takes it at once ({ev_mats(scl)})',
      ev_mats(scl) == {mat.name} and gl.is_line(scl))
for o in C.selected_objects:
    o.select_set(False)
scl.select_set(True)
C.view_layer.objects.active = scl
bpy.ops.mch.greeble_material(action='BODY')
check(f'the window\'s "Body\'s Material": the creature\'s skin on the scales ({ev_mats(scl)})', ev_mats(scl) == {'Skin'})
bpy.ops.mch.greeble_material(action='PARTS')
check(f'"Parts\' Own": back to the parts\' own ({ev_mats(scl)})', ev_mats(scl) == {'Part Paint'})
m2 = bpy.data.materials.new('Slot Green')
scl.data.materials.append(m2)                            # (Blender's own material slot)
check(f'a material put in the line\'s slot any other way (Blender\'s slots): the scales follow ({ev_mats(scl)})',
      ev_mats(scl) == {'Slot Green'})
grb = line('MECH', 'MECH', 0.4)
ms.assign(C, [grb], mat)
check(f'a Greeble Line too ({ev_mats(grb)})', ev_mats(grb) == {mat.name})
n0 = len(scl.data.vertices)
gl.rebuild(scl, C)
check('...kept when the line is rebuilt (its sliders)', ev_mats(scl) == {'Slot Green'} and len(scl.data.vertices) == n0)
for o in C.selected_objects:
    o.select_set(False)
scl.select_set(True)
grb.select_set(True)
C.view_layer.objects.active = scl
bpy.ops.mch.greeble_apply()
mats_s = {m.name for m in scl.data.materials if m}
mats_g = {m.name for m in grb.data.materials if m}
check(f'Apply: real meshes with the material ({mats_s}, {mats_g})', not gl.is_line(scl) and not gl.is_line(grb)
      and mats_s == {'Slot Green'} and mats_g == {mat.name} and len(scl.data.polygons) > 0)
check('...the Mech material\'s line: its edges / crevices measured on the real mesh (as the page\'s Apply does), the '
      'plain material\'s not', ms.CURV in grb.data.attributes and ms.CURV not in scl.data.attributes)

mecha_lab.unregister()
summary()
