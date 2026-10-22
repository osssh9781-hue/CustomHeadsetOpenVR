"""0.24.20 Surface Curve: draw along a mesh, a curve (tube) lies on it.

The drawn line is projected onto the mesh, thinned to a handful of control points and lifted by the tube radius
(minus Sink) along the surface normals, then made into an ordinary live Mesh Curve - so everything of Mesh Curve
works on it afterwards: Edit Points, radius per point, profile (Round / Square / Flat / Creature A-C / Guts /
From Object = your own section presets), outer lines, cap, twist, Apply.

``thin_points`` is pure and tested headless.
"""
from __future__ import annotations

import math

import bpy
from bpy.props import FloatProperty, IntProperty
from mathutils import Vector

from . import core_geometry as cg


def thin_points(pts, count):
    """``count`` points evenly spaced by length along a polyline (ends kept) - pure."""
    if len(pts) <= 2 or count >= len(pts):
        return list(pts)
    acc = [0.0]
    for a, b in zip(pts, pts[1:]):
        acc.append(acc[-1] + (b - a).length)
    total = acc[-1] or 1.0
    out, j = [], 0
    for k in range(count):
        s = total * k / (count - 1)
        while j < len(acc) - 2 and acc[j + 1] < s:
            j += 1
        t = (s - acc[j]) / max(acc[j + 1] - acc[j], 1e-12)
        out.append(pts[j].lerp(pts[j + 1], t))
    return out


class MCH_PG_SurfaceCurve(bpy.types.PropertyGroup):
    points: IntProperty(name='Points', default=12, min=2, max=80,
                        description='Control points the drawn line becomes (more = closer to the surface)')
    sink: FloatProperty(name='Sink', default=0.3, min=-1.0, max=1.0, subtype='FACTOR',
                        description='How far the tube goes into the surface (x radius)')
    smooth: IntProperty(name='Smooth', default=3, min=0, max=30, description='Soften the drawn line first')


def perform(context, path, projector):
    """Drawn path (pixels) on a mesh -> a live Mesh Curve lying on it.  Returns a report; raises cg.CutError."""
    from . import armor_plate as ap
    from . import belt_maker as bmk
    from . import curve_tube as ct
    path = [tuple(q) for q in path]
    if len(path) < 2:
        raise cg.CutError('Surface Curve: draw a line (at least 2 points).')
    target = bmk.pick_target(context, projector, path)
    if target is None:
        raise cg.CutError('Surface Curve: draw along a mesh.')
    st = context.scene.mch_surface_curve
    pts, _closed = bmk._follow_path(context, target, projector, path)
    length = sum((b - a).length for a, b in zip(pts, pts[1:]))
    if length <= 1e-9:
        raise cg.CutError('Surface Curve: the line is too short.')
    pts = bmk.smooth_path(bmk.resample(pts, length / 120.0, False), st.smooth, False)
    pts = thin_points(pts, st.points)
    bvh = ap._target_bvh(context, target)[0]
    view = Vector(projector.view_dir)
    radius = context.scene.mch_tube_defaults.radius
    lifted = []
    for q in pts:
        loc, n, _i, _d = bvh.find_nearest(q)
        q = loc if loc is not None else q
        n = n if n is not None else -view
        if n.dot(view) > 0:
            n = -n
        lifted.append(q + n.normalized() * radius * (1.0 - st.sink))
    ob = ct.new_tube(context, lifted[0], mode='TUBE')
    tb = ob.mch_tube
    tb.live = False
    tb.spline = 'SMOOTH'
    ct.set_points(ob, [(v - lifted[0], 1.0) for v in lifted])
    tb.live = True
    ct.rebuild(ob)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return (f'Surface curve "{ob.name}" on {target.name} ({len(lifted)} points) - edit it like a Mesh Curve '
            '(profile, radius, points)')


def draw(layout, context):
    from . import curve_tube as ct
    st = context.scene.mch_surface_curve
    box = layout.box()
    box.label(text='SURFACE CURVE', icon='CURVE_BEZCURVE')
    col = box.column(align=True)
    col.prop(st, 'points')
    col.prop(st, 'sink', slider=True)
    col.prop(st, 'smooth')
    box.label(text='Draw along a mesh, release: a curve on it', icon='INFO')
    ob = context.active_object
    if ct.is_tube(ob) and not ct.is_line_curve(ob):
        ct.draw(layout, context)            # the made curve: all Mesh Curve settings
    else:
        dft = context.scene.mch_tube_defaults
        c = layout.column(align=True)
        c.label(text='New curves start with:')
        c.prop(dft, 'radius')
        c.prop(dft, 'profile', text='')
        c.prop(dft, 'lines')


CLASSES = (MCH_PG_SurfaceCurve,)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_surface_curve = bpy.props.PointerProperty(type=MCH_PG_SurfaceCurve)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_surface_curve'):
        del bpy.types.Scene.mch_surface_curve
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
