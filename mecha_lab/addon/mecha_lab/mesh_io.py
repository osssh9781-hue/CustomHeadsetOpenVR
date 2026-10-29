"""0.24.86 Fast mesh array reads / writes.

``mesh.loops.foreach_get('vertex_index', ...)`` and friends walk the RNA collection item by item: 205 ms for the
3.9M corners of a 1.3M-face part, 90 ms for its edges, 20 - 90 ms for the points.  The same numbers sit in the
mesh's built-in attributes (``position``, ``.corner_vert``, ``.corner_edge``, ``.edge_verts``), and an attribute's
``foreach_get`` / ``foreach_set`` is one memcpy: 1 - 4 ms.  These helpers read the attribute when it is there and
fall back to the collection otherwise (an older Blender, a mesh without edges yet).
"""
from __future__ import annotations

import numpy as np


def _attr(me, name, domain, dtype):
    a = me.attributes.get(name)
    if a is None or a.domain != domain or a.data_type != dtype:
        return None
    return a


def read_co(me, dtype=np.float64):
    """Point coordinates (n, 3)."""
    n = len(me.vertices)
    a = _attr(me, 'position', 'POINT', 'FLOAT_VECTOR')
    if a is not None and len(a.data) == n:
        co = np.empty(n * 3, np.float32)
        a.data.foreach_get('vector', co)
        return co.reshape(-1, 3).astype(dtype, copy=False) if dtype != np.float32 else co.reshape(-1, 3)
    co = np.empty(n * 3, np.float64)
    me.vertices.foreach_get('co', co)
    return co.reshape(-1, 3).astype(dtype, copy=False)


def write_co(me, co):
    """Point coordinates in (n, 3) or flat."""
    co = np.ascontiguousarray(co, np.float32).ravel()
    a = _attr(me, 'position', 'POINT', 'FLOAT_VECTOR')
    if a is not None and len(a.data) * 3 == len(co):
        a.data.foreach_set('vector', co)
    else:
        me.vertices.foreach_set('co', co.astype(np.float64))


def read_corner_verts(me, dtype=np.int64):
    """The point index of every face corner."""
    n = len(me.loops)
    a = _attr(me, '.corner_vert', 'CORNER', 'INT')
    if a is not None and len(a.data) == n:
        vi = np.empty(n, np.int32)
        a.data.foreach_get('value', vi)
        return vi.astype(dtype, copy=False)
    vi = np.empty(n, np.int32)
    me.loops.foreach_get('vertex_index', vi)
    return vi.astype(dtype, copy=False)


def write_corner_verts(me, vi):
    vi = np.ascontiguousarray(vi, np.int32)
    a = _attr(me, '.corner_vert', 'CORNER', 'INT')
    if a is not None and len(a.data) == len(vi):
        a.data.foreach_set('value', vi)
    else:
        me.loops.foreach_set('vertex_index', vi)


def read_corner_edges(me, dtype=np.int64):
    """The edge index of every face corner (the edge from the corner to the next one)."""
    n = len(me.loops)
    a = _attr(me, '.corner_edge', 'CORNER', 'INT')
    if a is not None and len(a.data) == n:
        le = np.empty(n, np.int32)
        a.data.foreach_get('value', le)
        return le.astype(dtype, copy=False)
    le = np.empty(n, np.int32)
    me.loops.foreach_get('edge_index', le)
    return le.astype(dtype, copy=False)


def read_edge_verts(me, dtype=np.int64):
    """(ne, 2) point indices of the edges."""
    n = len(me.edges)
    a = _attr(me, '.edge_verts', 'EDGE', 'INT32_2D')
    if a is not None and len(a.data) == n:
        ev = np.empty(n * 2, np.int32)
        a.data.foreach_get('value', ev)
        return ev.reshape(-1, 2).astype(dtype, copy=False)
    ev = np.empty(n * 2, np.int32)
    me.edges.foreach_get('vertices', ev)
    return ev.reshape(-1, 2).astype(dtype, copy=False)


def read_face_starts(me):
    """(loop_start, loop_total) of the faces, int32 (``loop_start`` is the cheaper read; the sizes follow)."""
    n = len(me.polygons)
    start = np.empty(n, np.int32)
    me.polygons.foreach_get('loop_start', start)
    tot = np.empty(n, np.int32)
    if n:
        tot[:-1] = start[1:] - start[:-1]
        tot[-1] = len(me.loops) - start[-1]
    return start, tot


def edge_face_counts(me):
    """How many face corners use each edge (0 wire, 1 open, 2 manifold, 3+ overlapping)."""
    ne = len(me.edges)
    if not ne:
        return np.zeros(0, np.int64)
    return np.bincount(read_corner_edges(me), minlength=ne)
