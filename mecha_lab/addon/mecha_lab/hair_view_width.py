"""0.24.268 (user: "뷰포트에서 디자인 맞췄으니까 렌더에서 그거에 맞게 나왔으면 - 렌더 돌리면 너무 빵빵해져", "나 사이클만 써")
Render Like Viewport for hair (Hair in Shape, Fur).

Why the render looked fuller: the viewport (Solid / Material Preview, Blender's "Strand" hair) draws every strand as a
line about one pixel wide, whatever its thickness (measured: the drawn coverage did not change from 0.25x to 4x the
radius); Cycles gives each strand its real thickness - wider than a pixel close up, so the locks fill in and puff up.

The switch puts one Geometry Nodes modifier last on the hair object: each point's radius = half a pixel at its distance
from the scene camera (the render's own pixel: lens, sensor, resolution, % - set before every render), so Cycles draws
the strands as wide as the viewport does.  The hair shader stays (measured: closest to the viewport's look).  Off: the
modifier goes, the real thickness renders."""
from __future__ import annotations

import bpy

from . import scene_scan

MOD = 'MCH Viewport Width'
TREE = 'MCH Viewport Width'
TREE_V = 2                                       # (0.24.269 Width: the Render Thickness slider)


def tree():
    ng = bpy.data.node_groups.get(TREE)
    if ng is not None and ng.get('mch_v') == TREE_V:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(TREE, 'GeometryNodeTree')
    ng.nodes.clear()
    for it in list(ng.interface.items_tree):
        ng.interface.remove(it)
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Camera', in_out='INPUT', socket_type='NodeSocketObject')
    pm = ng.interface.new_socket('Pixel Per Metre', in_out='INPUT', socket_type='NodeSocketFloat')
    pm.default_value = 0.0
    fx = ng.interface.new_socket('Pixel Fixed', in_out='INPUT', socket_type='NodeSocketFloat')
    fx.default_value = 0.0
    wd = ng.interface.new_socket('Width', in_out='INPUT', socket_type='NodeSocketFloat')
    wd.default_value = 1.0
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    oi = N.new('GeometryNodeObjectInfo')
    oi.transform_space = 'RELATIVE'                  # (the camera where the hair's points are measured)
    L.new(gi.outputs['Camera'], oi.inputs['Object'])
    pos = N.new('GeometryNodeInputPosition')
    dist = N.new('ShaderNodeVectorMath')
    dist.operation = 'DISTANCE'
    L.new(pos.outputs[0], dist.inputs[0])
    L.new(oi.outputs['Location'], dist.inputs[1])
    mul = N.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY_ADD'                   # (distance x pixel per metre + fixed pixel: orthographic)
    L.new(dist.outputs['Value'], mul.inputs[0])
    L.new(gi.outputs['Pixel Per Metre'], mul.inputs[1])
    L.new(gi.outputs['Pixel Fixed'], mul.inputs[2])
    half = N.new('ShaderNodeMath')
    half.operation = 'MULTIPLY'
    L.new(gi.outputs['Width'], half.inputs[1])       # (a radius: half the pixel x Render Thickness)
    L.new(mul.outputs[0], half.inputs[0])
    sr = N.new('GeometryNodeSetCurveRadius')
    L.new(gi.outputs['Geometry'], sr.inputs['Curve'])
    L.new(half.outputs[0], sr.inputs['Radius'])
    L.new(sr.outputs[0], go.inputs[0])
    for i, n in enumerate((gi, oi, pos, dist, mul, half, sr, go)):
        n.location = (-900 + 160 * i, -60 * (i % 2))
    ng['mch_v'] = TREE_V
    return ng


def width_of(ob):
    """The object's Render Thickness (1: as wide as the viewport's line)."""
    from . import hair_shape as hs
    pg = getattr(ob, 'mch_hshape', None) if ob.get(hs.KEY) else getattr(ob, 'mch_fur', None)
    return float(getattr(pg, 'display_width', 1.0))


def pixel(scene):
    """(pixel per metre of distance, fixed pixel) of the scene camera's render, or None (no camera)."""
    cam = scene.camera
    if cam is None or cam.type != 'CAMERA':
        return None
    r = scene.render
    pct = r.resolution_percentage / 100.0
    wx, wy = r.resolution_x * pct * r.pixel_aspect_x, r.resolution_y * pct * r.pixel_aspect_y
    d = cam.data
    fit = d.sensor_fit
    if fit == 'AUTO':
        across, sensor = max(wx, wy), d.sensor_width
    elif fit == 'HORIZONTAL':
        across, sensor = wx, d.sensor_width
    else:
        across, sensor = wy, d.sensor_height
    across = max(across, 1.0)
    if d.type == 'ORTHO':
        return 0.0, d.ortho_scale / across
    if d.type == 'PERSP':
        return sensor / max(d.lens, 1e-3) / across, 0.0
    return None                                      # (panoramic: left at the real thickness)


def _set(mod, name, value):
    from . import geo_sculpt as gs
    try:
        gs.set_input(mod, name, value)
    except (KeyError, AttributeError, TypeError):
        pass


def refresh(scene):
    """Every hair with the switch: the camera and its pixel now."""
    px = pixel(scene)
    for ob in scene.objects:
        mod = ob.modifiers.get(MOD) if ob.type == 'CURVES' else None
        if mod is None:
            continue
        if mod.node_group is None or mod.node_group.get('mch_v') != TREE_V:
            mod.node_group = tree()
        mod.show_viewport = mod.show_render = px is not None
        if px is None:
            continue
        _set(mod, 'Camera', scene.camera)
        _set(mod, 'Pixel Per Metre', float(px[0]))
        _set(mod, 'Pixel Fixed', float(px[1]))
        _set(mod, 'Width', 0.5 * width_of(ob))
        ob.update_tag()


def set_on(ob, on, scene=None):
    """The switch on ``ob`` (a hair Curves object): our modifier last, or gone."""
    mod = ob.modifiers.get(MOD)
    if not on:
        if mod is not None:
            ob.modifiers.remove(mod)
        return
    if mod is None:
        mod = ob.modifiers.new(MOD, 'NODES')
        mod.node_group = tree()
    try:
        ob.modifiers.move(list(ob.modifiers).index(mod), len(ob.modifiers) - 1)
    except (RuntimeError, TypeError, AttributeError, ValueError):
        pass
    refresh(scene or bpy.context.scene)


_LAST = {}


def _render_pre(scene, *_a):
    try:
        refresh(scene)
    except (ReferenceError, AttributeError, RuntimeError):
        pass


def _changed(scene, *_a):
    """The camera, its lens or the resolution changed: the pixel again (cheap check)."""
    try:
        if not scene_scan.candidates(                     # (0.24.349 not every object at every update)
                'hair_view_width', scene, lambda o: o.type == 'CURVES' and o.modifiers.get(MOD) is not None,
                _a[0] if _a else None):
            return
        cam = scene.camera
        key = (cam.name if cam else '', pixel(scene))
        if _LAST.get(scene.name) != key:
            _LAST[scene.name] = key
            refresh(scene)
    except (ReferenceError, AttributeError, RuntimeError):
        pass


def register():
    if _render_pre not in bpy.app.handlers.render_pre:
        bpy.app.handlers.render_pre.append(_render_pre)
    if _changed not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_changed)


def unregister():
    if _render_pre in bpy.app.handlers.render_pre:
        bpy.app.handlers.render_pre.remove(_render_pre)
    if _changed in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_changed)
