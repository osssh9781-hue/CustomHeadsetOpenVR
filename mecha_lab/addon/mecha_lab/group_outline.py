"""0.24.107 Green outline round a selected group (Substance 3D Modeler style).

Clicking any part of a group selects the group (its handle Empty, which is not shown).  This draws a green outline
round every visible part of each selected group, so the whole group reads as picked.  It is drawing only: the
selection, the materials and the object colours stay as they are.  The outline follows move / turn / scale (it is
drawn from the evaluated objects every redraw); the parts' triangles are cached and rebuilt only when their geometry
changes.  Inside a group's scope that group is not outlined (its parts are picked one by one); a nested group
selected there is.

How: the parts are drawn into an offscreen ID mask (each part its own colour, depth tested between themselves), then
one full-region pass draws green where the mask has an edge - outside the parts' silhouette and, thinner, between two
parts.  If the GPU shader cannot be made, the parts' silhouette edges are drawn as lines instead.
"""
from __future__ import annotations

import bpy

GREEN = (0.22, 1.0, 0.36, 1.0)
BLUE = (0.3, 0.62, 1.0, 1.0)      # 0.24.114 (user: "그룹을 그룹으로 만든 거는 파란색으로") a group that holds groups


def outline_colour(context):
    """Green for a group of parts; blue when a selected group holds other groups (a group of groups)."""
    from . import groups
    try:
        for g in outline_groups(context):
            if any(groups.is_group(o) for o in groups.members(g)):
                return BLUE
    except (AttributeError, ReferenceError, RuntimeError):
        pass
    return GREEN
WIDTH = 3                   # outline thickness in pixels at UI scale 1
MAX_PARTS = 4000            # a guard for huge groups (the outline is a hint, not worth stalling the viewport)

_handle = None
_cache = {}                 # object name -> (batch, tris count, silhouette data or None)
_state = {'shader': None, 'shader_failed': False, 'off': None, 'size': (0, 0), 'quad': None, 'error': ''}


# --- what to outline --------------------------------------------------------------------------------------------

def outline_groups(context):
    """Selected group handles, except the scope we are working inside."""
    from . import groups
    try:
        current = groups.scope(context)
        sel = list(context.selected_objects)
    except (AttributeError, ReferenceError, RuntimeError):
        return []
    return [o for o in sel if groups.is_group(o) and o != current]


def outline_objects(context):
    """The visible parts of the selected groups (nested groups' parts too, repetition objects not)."""
    from . import groups
    seen, out = set(), []
    for g in outline_groups(context):
        for o in groups.members(g):
            if o in seen or o.type not in {'MESH', 'CURVE', 'SURFACE', 'FONT'} or groups.CARRIER_KEY in o:
                continue
            seen.add(o)
            try:
                if not o.visible_get() or o.display_type in {'WIRE', 'BOUNDS'}:
                    continue
            except (RuntimeError, ReferenceError):
                continue
            out.append(o)
            if len(out) >= MAX_PARTS:
                return out
    return out


# --- geometry cache ---------------------------------------------------------------------------------------------

def mesh_arrays(ob, depsgraph):
    """(positions (n, 3) float32, triangles (m, 3) int32) of the evaluated object in its own space, or None."""
    import numpy as np
    try:
        ev = ob.evaluated_get(depsgraph)
        me = ev.to_mesh()
    except (RuntimeError, ReferenceError, AttributeError):
        return None
    try:
        if me is None or not len(me.vertices) or not len(me.polygons):
            return None
        me.calc_loop_triangles()
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get('co', co)
        tri = np.empty(len(me.loop_triangles) * 3, np.int32)
        me.loop_triangles.foreach_get('vertices', tri)
        return co.reshape(-1, 3), tri.reshape(-1, 3)
    finally:
        try:
            ev.to_mesh_clear()
        except (RuntimeError, ReferenceError):
            pass


def forget(name=None):
    """Drop the cached triangles of one object (its geometry changed) or of all."""
    if name is None:
        _cache.clear()
    else:
        _cache.pop(name, None)


def _entry(ob, depsgraph, shader):
    e = _cache.get(ob.name)
    if e is not None:
        return e
    arrs = mesh_arrays(ob, depsgraph)
    if arrs is None:
        _cache[ob.name] = (None, 0, None)
        return _cache[ob.name]
    co, tri = arrs
    batch = None
    if shader is not None:
        try:
            from gpu_extras.batch import batch_for_shader
            batch = batch_for_shader(shader, 'TRIS', {'pos': co}, indices=tri)
        except Exception:        # no GPU here (background) or a driver refusal: the line fallback still works
            batch = None
    _cache[ob.name] = (batch, len(tri), (co, tri))
    return _cache[ob.name]


@bpy.app.handlers.persistent
def _on_depsgraph(scene, depsgraph):
    try:
        for u in depsgraph.updates:
            if u.is_updated_geometry and isinstance(u.id, bpy.types.Object):
                _cache.pop(u.id.original.name if u.id.original else u.id.name, None)
    except (AttributeError, ReferenceError, RuntimeError):
        pass


@bpy.app.handlers.persistent
def _on_reset(_dummy=None):
    _cache.clear()


# --- silhouette lines (fallback, and what tests can check without a GPU) ----------------------------------------

def silhouette_segments(co, tri, matrix_world, view_origin, view_dir, ortho):
    """World-space segments (k, 2, 3) of the triangle edges where the front-facing part meets the back-facing part
    (and open borders), seen from ``view_origin`` / along ``view_dir``."""
    import numpy as np
    m = np.array(matrix_world, np.float64)
    pts = co.astype(np.float64) @ m[:3, :3].T + m[:3, 3]
    a, b, c = pts[tri[:, 0]], pts[tri[:, 1]], pts[tri[:, 2]]
    n = np.cross(b - a, c - a)
    if ortho:
        facing = n @ np.asarray(view_dir, np.float64) < 0
    else:
        centre = (a + b + c) / 3.0
        facing = np.einsum('ij,ij->i', n, centre - np.asarray(view_origin, np.float64)) < 0
    if np.linalg.det(m[:3, :3]) < 0:
        facing = ~facing
    e = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    f = np.tile(np.arange(len(tri)), 3)
    key = np.sort(e, axis=1)
    order = np.lexsort((key[:, 1], key[:, 0]))
    key, f = key[order], f[order]
    same = np.all(key[1:] == key[:-1], axis=1)
    out = []
    n_e = len(key)
    first = np.ones(n_e, bool)
    first[1:] = ~same
    starts = np.flatnonzero(first)
    counts = np.diff(np.append(starts, n_e))
    single = starts[counts == 1]
    double = starts[counts == 2]
    if len(single):
        out.append(key[single])
    if len(double):
        diff = facing[f[double]] != facing[f[double + 1]]
        out.append(key[double[diff]])
    if not out:
        return np.zeros((0, 2, 3))
    k = np.concatenate(out)
    return np.stack([pts[k[:, 0]], pts[k[:, 1]]], axis=1)


# --- GPU --------------------------------------------------------------------------------------------------------

VERT = '''
void main()
{
    uvInterp = pos * 0.5 + 0.5;
    gl_Position = vec4(pos, 0.0, 1.0);
}
'''

FRAG = '''
void main()
{
    vec4 c = texture(mask, uvInterp);
    bool inside = c.a > 0.5;
    bool outer = false;
    bool between = false;
    for (int dy = -radius; dy <= radius; dy++) {
        for (int dx = -radius; dx <= radius; dx++) {
            if (dx * dx + dy * dy > radius * radius) {
                continue;
            }
            vec4 n = texture(mask, uvInterp + vec2(float(dx), float(dy)) * texel);
            if (!inside) {
                if (n.a > 0.5) {
                    outer = true;
                }
            }
            else if (abs(dx) <= 1 && abs(dy) <= 1 && n.a > 0.5 &&
                     (abs(n.r - c.r) > 0.002 || abs(n.g - c.g) > 0.002)) {
                between = true;
            }
        }
    }
    if (outer) {
        FragColor = color;
    }
    else if (between) {
        FragColor = vec4(color.rgb, color.a * 0.8);
    }
    else {
        discard;
    }
}
'''


def _edge_shader():
    if _state['shader'] is not None or _state['shader_failed']:
        return _state['shader']
    try:
        import gpu
        iface = gpu.types.GPUStageInterfaceInfo('mch_group_outline_iface')
        iface.smooth('VEC2', 'uvInterp')
        info = gpu.types.GPUShaderCreateInfo()
        info.push_constant('VEC4', 'color')
        info.push_constant('VEC2', 'texel')
        info.push_constant('INT', 'radius')
        info.sampler(0, 'FLOAT_2D', 'mask')
        info.vertex_in(0, 'VEC2', 'pos')
        info.vertex_out(iface)
        info.fragment_out(0, 'VEC4', 'FragColor')
        info.vertex_source(VERT)
        info.fragment_source(FRAG)
        _state['shader'] = gpu.shader.create_from_info(info)
        del iface, info
    except Exception as ex:          # any backend refusal: fall back to silhouette lines
        _state['shader_failed'] = True
        _state['error'] = str(ex).splitlines()[0] if str(ex) else type(ex).__name__
        _state['shader'] = None
    return _state['shader']


def _offscreen(w, h):
    import gpu
    if _state['off'] is None or _state['size'] != (w, h):
        if _state['off'] is not None:
            try:
                _state['off'].free()
            except Exception:
                pass
        _state['off'] = gpu.types.GPUOffScreen(w, h)
        _state['size'] = (w, h)
    return _state['off']


def id_colour(i):
    i += 1
    return ((i % 255) / 255.0, ((i // 255) % 255) / 255.0, 0.0, 1.0)


def _ui_scale():
    try:
        return max(0.5, float(bpy.context.preferences.system.ui_scale or 1.0))
    except (AttributeError, TypeError, ValueError):
        return 1.0


def _draw_mask(context, objs, region, rv3d, dg):
    import gpu
    flat = gpu.shader.from_builtin('UNIFORM_COLOR')
    off = _offscreen(region.width, region.height)
    with off.bind():
        fb = gpu.state.active_framebuffer_get()
        fb.clear(color=(0.0, 0.0, 0.0, 0.0), depth=1.0)
        gpu.state.depth_test_set('LESS_EQUAL')
        gpu.state.depth_mask_set(True)
        gpu.state.blend_set('NONE')
        with gpu.matrix.push_pop(), gpu.matrix.push_pop_projection():
            gpu.matrix.load_projection_matrix(rv3d.window_matrix)
            gpu.matrix.load_matrix(rv3d.view_matrix)
            for i, ob in enumerate(objs):
                batch = _entry(ob, dg, flat)[0]
                if batch is None:
                    continue
                with gpu.matrix.push_pop():
                    gpu.matrix.multiply_matrix(ob.evaluated_get(dg).matrix_world)
                    flat.bind()
                    flat.uniform_float('color', id_colour(i))
                    batch.draw(flat)
        gpu.state.depth_mask_set(False)
        gpu.state.depth_test_set('NONE')
    return off


def _draw_edges(off, region, colour=GREEN):
    import gpu
    from gpu_extras.batch import batch_for_shader
    sh = _state['shader']
    if _state['quad'] is None:
        _state['quad'] = batch_for_shader(sh, 'TRIS', {'pos': ((-1, -1), (1, -1), (1, 1), (-1, -1), (1, 1), (-1, 1))})
    gpu.state.blend_set('ALPHA')
    sh.bind()
    sh.uniform_sampler('mask', off.texture_color)
    sh.uniform_float('texel', (1.0 / region.width, 1.0 / region.height))
    sh.uniform_float('color', colour)
    sh.uniform_int('radius', max(1, int(round(WIDTH * _ui_scale()))))
    _state['quad'].draw(sh)
    gpu.state.blend_set('NONE')


def _draw_lines(context, objs, region, rv3d, dg, colour=GREEN):
    """Fallback: the silhouette edges as 2D lines."""
    import gpu
    import numpy as np
    from gpu_extras.batch import batch_for_shader
    vi = rv3d.view_matrix.inverted()
    origin = vi.translation
    view_dir = -(vi.to_3x3().col[2])
    pm = np.array(rv3d.perspective_matrix, np.float64)
    segs = []
    for ob in objs:
        e = _entry(ob, dg, None)
        if e[2] is None:
            continue
        s = silhouette_segments(e[2][0], e[2][1], ob.evaluated_get(dg).matrix_world, origin, view_dir,
                                not rv3d.is_perspective)
        if len(s):
            segs.append(s.reshape(-1, 3))
    if not segs:
        return
    p = np.concatenate(segs)
    h = np.c_[p, np.ones(len(p))] @ pm.T
    w = h[:, 3:4]
    w[np.abs(w) < 1e-9] = 1e-9
    ndc = h[:, :2] / w
    xy = np.c_[(ndc[:, 0] + 1) * 0.5 * region.width, (ndc[:, 1] + 1) * 0.5 * region.height].astype(np.float32)
    sh = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')
    sh.bind()
    sh.uniform_float('viewportSize', (region.width, region.height))
    sh.uniform_float('lineWidth', max(1.0, WIDTH * _ui_scale() * 0.8))
    sh.uniform_float('color', colour)
    batch_for_shader(sh, 'LINES', {'pos': [tuple(v) + (0.0,) for v in xy]}).draw(sh)
    gpu.state.blend_set('NONE')


def _draw():
    try:
        context = bpy.context
        if getattr(context, 'mode', 'OBJECT') != 'OBJECT':
            return
        region, rv3d = context.region, context.region_data
        if region is None or rv3d is None or region.width < 2 or region.height < 2:
            return
        objs = outline_objects(context)
        if not objs:
            return
        dg = context.evaluated_depsgraph_get()
        if _edge_shader() is not None:
            off = _draw_mask(context, objs, region, rv3d, dg)
            _draw_edges(off, region, outline_colour(context))
        else:
            _draw_lines(context, objs, region, rv3d, dg, outline_colour(context))
    except Exception as ex:      # never break viewport drawing
        _state['error'] = str(ex).splitlines()[0] if str(ex) else type(ex).__name__


def register():
    global _handle
    for hl, fn in ((bpy.app.handlers.depsgraph_update_post, _on_depsgraph), (bpy.app.handlers.load_post, _on_reset),
                   (bpy.app.handlers.undo_post, _on_reset), (bpy.app.handlers.redo_post, _on_reset)):
        if fn not in hl:
            hl.append(fn)
    if not bpy.app.background and _handle is None:
        _handle = bpy.types.SpaceView3D.draw_handler_add(_draw, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    global _handle
    for hl, fn in ((bpy.app.handlers.depsgraph_update_post, _on_depsgraph), (bpy.app.handlers.load_post, _on_reset),
                   (bpy.app.handlers.undo_post, _on_reset), (bpy.app.handlers.redo_post, _on_reset)):
        if fn in hl:
            hl.remove(fn)
    if _handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _handle = None
    if _state['off'] is not None:
        try:
            _state['off'].free()
        except Exception:
            pass
    _state.update(shader=None, shader_failed=False, off=None, size=(0, 0), quad=None)
    _cache.clear()
