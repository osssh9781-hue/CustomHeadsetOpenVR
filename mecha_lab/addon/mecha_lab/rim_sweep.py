"""0.24.41 Cut / Split edge finish made by Geometry Nodes: the border of the drawn area is swept.

Blender's Bevel on the Boolean result clamped to almost nothing next to the slivers a Boolean leaves on a dense
mesh, so the chamfer / bevel came out uneven or not at all.  Here the finish is carved instead:

* Python reads the new rim (edges between the cut's faces and the old surface) and, for every rim point, the
  cross-section of what has to go: from ``width`` along the surface to ``width`` down the cut wall, straight
  (Chamfer) or round (Bevel, ``segments``), plus a cap outside the part.  Those points are stored as vertex
  attributes ``mch_rp0`` ... and the rim edges as ``mch_rim``.
* A Geometry Nodes group (``MCH_RimSweep_<n>``) turns the rim edges into curves (Mesh to Curve), sweeps an
  ``n``-point profile along them (Curve to Mesh), puts every profile point where its attribute says (Index
  Switch on index mod n) and subtracts that band from the part (Mesh Boolean, Exact).
* The modifier is applied to a temporary object and the result goes back into the mesh.

The band follows the rim exactly, so the chamfer / bevel is as even as the drawn outline.
"""
from __future__ import annotations

import bmesh
import bpy
from mathutils import Vector

from . import core_geometry as cg

RIM = 'mch_rim'
POINT = 'mch_rp'
DIR = 'mch_rdir'


def _link(ng, a, b):
    ng.links.new(a, b)


def ensure_group(n):
    """The node group for an ``n``-point profile (made once per n)."""
    name = f'MCH_RimSweep3_{n}'
    ng = bpy.data.node_groups.get(name)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    nodes = ng.nodes
    gin = nodes.new('NodeGroupInput')
    gout = nodes.new('NodeGroupOutput')
    rim = nodes.new('GeometryNodeInputNamedAttribute')
    rim.data_type = 'BOOLEAN'
    rim.inputs['Name'].default_value = RIM
    m2c = nodes.new('GeometryNodeMeshToCurve')
    _link(ng, gin.outputs[0], m2c.inputs['Mesh'])
    _link(ng, rim.outputs['Attribute'], m2c.inputs['Selection'])
    # every curve runs the same way round (Mesh to Curve picks a direction per curve): a curve against the
    # stored rim direction is reversed, else its swept band would come out inside out and cut nothing
    tan = nodes.new('GeometryNodeInputTangent')
    ref = nodes.new('GeometryNodeInputNamedAttribute')
    ref.data_type = 'FLOAT_VECTOR'
    ref.inputs['Name'].default_value = DIR
    dot = nodes.new('ShaderNodeVectorMath')
    dot.operation = 'DOT_PRODUCT'
    _link(ng, tan.outputs[0], dot.inputs[0])
    _link(ng, ref.outputs['Attribute'], dot.inputs[1])
    cap = nodes.new('GeometryNodeCaptureAttribute')      # per point first (a closed loop's mean tangent is 0),
    cap.domain = 'POINT'                                   # then the curve's mean of those decides
    cap.capture_items.new('FLOAT', 'Dot')
    _link(ng, m2c.outputs['Curve'], cap.inputs['Geometry'])
    _link(ng, dot.outputs['Value'], cap.inputs['Dot'])
    less = nodes.new('FunctionNodeCompare')
    less.data_type = 'FLOAT'
    less.operation = 'LESS_THAN'
    _link(ng, cap.outputs['Dot'], less.inputs[0])
    less.inputs[1].default_value = 0.0
    rev = nodes.new('GeometryNodeReverseCurve')
    _link(ng, cap.outputs['Geometry'], rev.inputs['Curve'])
    _link(ng, less.outputs['Result'], rev.inputs['Selection'])
    prof = nodes.new('GeometryNodeCurvePrimitiveCircle')
    prof.mode = 'RADIUS'
    prof.inputs['Resolution'].default_value = n
    c2m = nodes.new('GeometryNodeCurveToMesh')
    c2m.inputs['Fill Caps'].default_value = True
    _link(ng, rev.outputs['Curve'], c2m.inputs['Curve'])
    _link(ng, prof.outputs['Curve'], c2m.inputs['Profile Curve'])
    idx = nodes.new('GeometryNodeInputIndex')
    mod = nodes.new('ShaderNodeMath')
    mod.operation = 'FLOORED_MODULO'
    mod.inputs[1].default_value = n
    _link(ng, idx.outputs['Index'], mod.inputs[0])
    sw = nodes.new('GeometryNodeIndexSwitch')
    sw.data_type = 'VECTOR'
    while len(sw.index_switch_items) < n:
        sw.index_switch_items.new()
    _link(ng, mod.outputs[0], sw.inputs['Index'])
    for j in range(n):
        a = nodes.new('GeometryNodeInputNamedAttribute')
        a.data_type = 'FLOAT_VECTOR'
        a.inputs['Name'].default_value = f'{POINT}{j}'
        _link(ng, a.outputs['Attribute'], sw.inputs[j + 1])
    setp = nodes.new('GeometryNodeSetPosition')
    _link(ng, c2m.outputs['Mesh'], setp.inputs['Geometry'])
    _link(ng, sw.outputs['Output'], setp.inputs['Position'])
    boo = nodes.new('GeometryNodeMeshBoolean')
    boo.operation = 'DIFFERENCE'
    boo.solver = 'EXACT'
    boo.inputs['Self Intersection'].default_value = True
    _link(ng, gin.outputs[0], boo.inputs['Mesh 1'])
    _link(ng, setp.outputs['Geometry'], boo.inputs['Mesh 2'])
    _link(ng, boo.outputs['Mesh'], gout.inputs[0])
    return ng


def profile_points(p, d_face, d_wall, out, width, mode, segments):
    """The cross-section to remove at rim point ``p``: ``d_face`` = along the old surface away from the rim,
    ``d_wall`` = down the cut wall, ``out`` = out of the part.  Chamfer = a straight cut from ``width`` on the
    surface to ``width`` on the wall; Bevel = a round one (tangent to both); then two points outside."""
    a = p + d_face * width
    b = p + d_wall * width
    if mode == 'CHAMFER':
        arc = [a, b]
    else:
        c = p + d_face * width + d_wall * width          # the round's centre (exact for a square corner)
        k = max(1, segments)
        import math
        arc = [c + (a - c) * math.cos(0.5 * math.pi * i / k) + (b - c) * math.sin(0.5 * math.pi * i / k)
               for i in range(k + 1)]
    h = width * 1.5
    return arc + [b + out * h, a + out * h]


def mark_rim(mesh, mode, width, segments):
    """Store the rim edges and each rim point's profile on ``mesh``.  Returns (profile size, rim edge count)."""
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        layer = cg._face_flag_layer(bm)
        if layer is None:
            return 0, 0
        edges = cg._rim_edges(bm, layer)
        if not edges:
            return 0, 0
        acc = {}
        for e in edges:
            f0, f1 = e.link_faces
            fo, fc = (f1, f0) if f0[layer] else (f0, f1)       # old surface / cut wall
            t = (e.verts[1].co - e.verts[0].co)
            if t.length < 1e-12:
                continue
            t.normalize()
            dirs = []
            for f in (fo, fc):                       # into the face: left of its loop along the edge
                lp = next(l for l in e.link_loops if l.face == f)
                along = lp.link_loop_next.vert.co - lp.vert.co
                dirs.append(f.normal.cross(along).normalized())
            out = (fo.normal + fc.normal)
            for v in e.verts:
                s = acc.setdefault(v.index, [Vector(), Vector(), Vector()])
                s[0] += dirs[0]
                s[1] += dirs[1]
                s[2] += out
        n = (segments + 1 if mode != 'CHAMFER' else 2) + 2
        cols = [[0.0, 0.0, 0.0] * len(bm.verts) for _j in range(n)]
        dcol = [0.0, 0.0, 0.0] * len(bm.verts)
        bm.verts.ensure_lookup_table()
        for vi, (df, dw, out) in acc.items():
            if df.length < 1e-9 or dw.length < 1e-9 or out.length < 1e-9:
                continue
            pts = profile_points(bm.verts[vi].co, df.normalized(), dw.normalized(), out.normalized(), width, mode,
                                 segments)
            for j, q in enumerate(pts):
                cols[j][vi * 3:vi * 3 + 3] = list(q)
            dcol[vi * 3:vi * 3 + 3] = list((dw.normalized() - df.normalized()).cross(out.normalized()))
        rim_flags = [False] * len(bm.edges)
        for e in edges:
            rim_flags[e.index] = True
    finally:
        bm.free()
    for name in [a.name for a in mesh.attributes if a.name in (RIM, DIR) or a.name.startswith(POINT)]:
        mesh.attributes.remove(mesh.attributes[name])
    attr = mesh.attributes.new(RIM, 'BOOLEAN', 'EDGE')
    attr.data.foreach_set('value', rim_flags)
    for j in range(n):
        attr = mesh.attributes.new(f'{POINT}{j}', 'FLOAT_VECTOR', 'POINT')
        attr.data.foreach_set('vector', cols[j])
    attr = mesh.attributes.new(DIR, 'FLOAT_VECTOR', 'POINT')
    attr.data.foreach_set('vector', dcol)
    return n, len(edges)


def clear(mesh):
    for name in [a.name for a in mesh.attributes if a.name in (RIM, DIR) or a.name.startswith(POINT)]:
        mesh.attributes.remove(mesh.attributes[name])


def finish(mesh, mode='CHAMFER', width=0.01, segments=3):
    """Chamfer / bevel the cut's rim on ``mesh`` (object space) with the Geometry Nodes sweep.  Returns the
    number of rim edges finished (0 = nothing done, the mesh unchanged)."""
    if mode not in {'CHAMFER', 'BEVEL'} or width <= 0 or mesh.attributes.get(cg.CUTTER_ATTR) is None:
        return 0
    n, count = mark_rim(mesh, mode, width, segments)
    if not count:
        clear(mesh)
        return 0
    scene = bpy.context.scene
    ob = bpy.data.objects.new('MCH_RimSweep_tmp', mesh)
    scene.collection.objects.link(ob)
    try:
        mod = ob.modifiers.new('MCH_RimSweep', 'NODES')
        mod.node_group = ensure_group(n)
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        ev = ob.evaluated_get(dg)
        res = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    finally:
        bpy.data.objects.remove(ob)
    try:
        if len(res.polygons) == 0:
            clear(mesh)
            return 0
        smooth = {i for i, p in enumerate(mesh.polygons) if p.use_smooth}
        mesh.clear_geometry()
        bm = bmesh.new()
        try:
            bm.from_mesh(res)
            bm.to_mesh(mesh)
        finally:
            bm.free()
        clear(mesh)
        if not smooth:
            for p in mesh.polygons:
                p.use_smooth = False
    finally:
        bpy.data.meshes.remove(res)
    mesh.update()
    return count
