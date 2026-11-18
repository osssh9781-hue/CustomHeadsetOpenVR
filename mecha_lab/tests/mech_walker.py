"""A two-legged walker mech made of separate parts that touch (test asset, 0.24.247): Body, Turret, per side a Thigh,
a Shin and a Foot, an Upper Arm and a Gun.  ``JOINTS`` are where the parts meet (the truth)."""
import math

import bpy
from mathutils import Vector

JOINTS = {}


def rod(context, name, p, q, r):
    p, q = Vector(p), Vector(q)
    d = q - p
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=r, depth=d.length + 2 * r, location=(p + q) / 2)
    ob = context.active_object
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    ob.name = name
    return ob


def box(context, name, c, s):
    bpy.ops.mesh.primitive_cube_add(location=c, scale=s)
    context.active_object.name = name
    return context.active_object


def make(context):
    parts = [box(context, 'Body', (0, 0, 2.0), (0.6, 0.5, 0.4)), box(context, 'Turret', (0, -0.1, 2.6), (0.25, 0.25, 0.2))]
    JOINTS['Turret'] = (0, -0.1, 2.4)
    for s, x in (('L', 1), ('R', -1)):
        hip, knee, ankle = (0.45 * x, 0, 1.6), (0.45 * x, -0.25, 0.95), (0.45 * x, 0.1, 0.25)
        parts.append(rod(context, f'Thigh.{s}', hip, knee, 0.1))
        parts.append(rod(context, f'Shin.{s}', knee, ankle, 0.09))
        parts.append(box(context, f'Foot.{s}', (0.45 * x, -0.1, 0.1), (0.15, 0.3, 0.1)))
        sh, el, tip = (0.62 * x, 0, 2.15), (0.95 * x, -0.1, 1.6), (0.95 * x, -0.6, 1.35)
        parts.append(rod(context, f'UpperArm.{s}', sh, el, 0.09))
        parts.append(rod(context, f'Gun.{s}', el, tip, 0.08))
        JOINTS.update({f'Thigh.{s}': hip, f'Shin.{s}': knee, f'Foot.{s}': ankle, f'UpperArm.{s}': sh, f'Gun.{s}': el})
    for o in list(context.selected_objects):
        o.select_set(False)
    for o in parts:
        o.select_set(True)
    context.view_layer.objects.active = parts[0]
    return parts
