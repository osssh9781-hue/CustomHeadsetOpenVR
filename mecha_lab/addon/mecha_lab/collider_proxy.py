"""0.24.95 Collider proxies: a low-resolution copy of every mesh a cloth collides with (user: "충돌용 바디 별도의
저해상도 프록시 메쉬 생성 ... 셀렉트 모드 전체 ... 모든 메쉬를 프록시화, 지금 만드는 천 제외").

Which meshes: ``meshes_for`` follows the shared Targets setting (T) - Auto = every visible mesh, Selected = the
selected meshes, Active = the body only - always with the body, never the cloth being made (nor its children such
as the trim) nor a proxy.

The proxies: real mesh objects "<name>_proxy" in the hidden collection "MCH Cloth Proxies" (wire display, never
rendered or selectable), Fast Decimate of the evaluated mesh down to about ``faces`` triangles.  A proxy is made
again only when its source changed (point / face count, the sum of the points, the modifiers' result), so a
second drape or a restart costs nothing.  A mesh lighter than the budget is used as it is (no proxy).
"""
from __future__ import annotations

import bpy
import numpy as np

COLL = 'MCH Cloth Proxies'
SRC = 'mch_proxy_src'
SIG = 'mch_proxy_sig'


def collection(context, create=True):
    coll = bpy.data.collections.get(COLL)
    if coll is None and create:
        coll = bpy.data.collections.new(COLL)
        context.scene.collection.children.link(coll)
        coll.hide_render = True
        coll.hide_select = True
        coll.hide_viewport = True
    return coll


def set_visible(context, on):
    coll = collection(context, create=False)
    if coll is not None:
        coll.hide_viewport = not on


def is_proxy(ob):
    return ob is not None and SRC in ob.keys()


def _exclusions(cloth_obs):
    out = set()
    stack = [o for o in cloth_obs if o is not None]
    while stack:
        o = stack.pop()
        if o.name in out:
            continue
        out.add(o.name)
        stack.extend(o.children)
    return out


def meshes_for(context, body, cloth_obs=(), mode='BODY'):
    """The collider meshes: ``mode`` 'BODY' = the body only; 'TARGETS' = the Targets setting decides (Auto: every
    visible mesh, Selected: the selected ones, Active: the body).  The body always; the cloth objects (and their
    children) and proxies never."""
    skip = _exclusions(cloth_obs)
    out = [body] if body is not None and body.name not in skip else []
    if mode != 'TARGETS':
        return out
    how = getattr(getattr(context.scene, 'mch_cut', None), 'targets', 'AUTO')
    if how == 'ACTIVE':
        return out
    pool = context.selected_objects if how == 'SELECTED' else context.view_layer.objects
    for o in pool:
        if o.type != 'MESH' or o == body or o.name in skip or is_proxy(o):
            continue
        try:
            if not o.visible_get():
                continue
        except RuntimeError:
            continue
        out.append(o)
    return out


def _evaluated(context, ob):
    """(mesh, temporary?) - the object's mesh with its modifiers (a temporary copy only when it has some)."""
    if not any(m.show_viewport for m in ob.modifiers):
        return ob.data, False
    dg = context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    return me, True


def _signature(me):
    n = len(me.vertices)
    co = np.empty(n * 3, np.float64)
    me.vertices.foreach_get('co', co)
    return f'{n}:{len(me.polygons)}:{float(co.sum()):.6g}:{float(np.abs(co).sum()):.6g}'


def proxy_mesh(context, ob, faces):
    """The mesh to collide with for ``ob`` (object space): its proxy (made / refreshed here) when its evaluated
    mesh has more than ``faces`` triangles, else its own (evaluated) mesh.  Returns (mesh, is_temporary_copy)."""
    from . import fast_decimate as fd
    from . import mesh_io as mio
    src, temp = _evaluated(context, ob)
    try:
        _start, tot = mio.read_face_starts(src)
        nt = int((np.asarray(tot) - 2).sum())
        if nt <= faces * 1.2 or not fd.available():
            handed, temp = temp, False            # (a temporary copy goes to the caller, who frees it)
            return src, handed
        sig = _signature(src)
        name = ob.name + '_proxy'
        px = next((o for o in collection(context).objects if o.get(SRC) == ob.name and not o.get(LOCAL)), None)
        if px is not None and px.get(SIG) == sig and px.type == 'MESH':
            px.matrix_world = ob.matrix_world.copy()
            return px.data, False
        src.calc_loop_triangles()
        T = np.empty((len(src.loop_triangles), 3), np.int64)
        src.loop_triangles.foreach_get('vertices', T.ravel())
        V2, F2, _vs, _fs = fd.run(mio.read_co(src), T, int(faces), keep_borders=True)
        new = bpy.data.meshes.new(name)
        fd.build_mesh(new, np.asarray(V2, np.float64), np.asarray(F2, np.int64))
        new.polygons.foreach_set('use_smooth', np.ones(len(new.polygons), bool))
        new.update()
        if px is None:
            px = bpy.data.objects.new(name, new)
            collection(context).objects.link(px)
            px.display_type = 'WIRE'
            px.hide_render = True
            px.hide_select = True
            px[SRC] = ob.name
        else:
            old = px.data
            px.data = new
            if old.users == 0:
                bpy.data.meshes.remove(old)
        px[SIG] = sig
        px.matrix_world = ob.matrix_world.copy()
        return new, False
    finally:
        if temp:
            bpy.data.meshes.remove(src)


LOCAL = 'mch_proxy_local'


def local_proxy_mesh(context, ob, lo, hi, faces):
    """0.24.95 a LOCAL proxy (user: "마스크한 영역은 콜리전으로 로우 메시 뽑고 ..."): only the part of ``ob``'s evaluated
    mesh inside the box ``lo`` .. ``hi`` (object space: where the cloth can reach), decimated to about ``faces``
    triangles - the whole budget on that region instead of on the whole body, so a dense body keeps its shape
    there.  Cached as "<name>_proxy_local" until the mesh or the region changes.  Returns (mesh, temporary?)."""
    from . import fast_decimate as fd
    from . import mesh_io as mio
    from .cloth_drape import faces_mesh
    src, temp = _evaluated(context, ob)
    try:
        lo = np.asarray(lo, np.float64)
        hi = np.asarray(hi, np.float64)
        co = mio.read_co(src)
        inside = np.all((co >= lo) & (co <= hi), axis=1)
        vi = mio.read_corner_verts(src)
        start, tot = mio.read_face_starts(src)
        if not inside.any() or not len(start):
            handed, temp = temp, False
            return src, handed
        sel = np.nonzero(np.add.reduceat(inside[vi].astype(np.int32), start) > 0)[0]
        nt = int((np.asarray(tot)[sel] - 2).sum())
        if nt <= faces * 1.2 or not fd.available():   # (light enough already: the region itself)
            return faces_mesh(src, sel, name=ob.name + '_region'), True
        sig = _signature(src) + '|' + ','.join(f'{x:.4g}' for x in np.concatenate([lo, hi])) + f'|{int(faces)}'
        name = ob.name + '_proxy_local'
        coll = collection(context)
        px = next((o for o in coll.objects if o.get(SRC) == ob.name and o.get(LOCAL)), None)
        if px is not None and px.get(SIG) == sig and px.type == 'MESH':
            px.matrix_world = ob.matrix_world.copy()
            return px.data, False
        region = faces_mesh(src, sel, name=name)
        try:
            region.calc_loop_triangles()
            T = np.empty((len(region.loop_triangles), 3), np.int64)
            region.loop_triangles.foreach_get('vertices', T.ravel())
            V2, F2, _vs, _fs = fd.run(mio.read_co(region), T, int(faces), keep_borders=True)
        finally:
            bpy.data.meshes.remove(region)
        new = bpy.data.meshes.new(name)
        fd.build_mesh(new, np.asarray(V2, np.float64), np.asarray(F2, np.int64))
        new.polygons.foreach_set('use_smooth', np.ones(len(new.polygons), bool))
        new.update()
        if px is None:
            px = bpy.data.objects.new(name, new)
            coll.objects.link(px)
            px.display_type = 'WIRE'
            px.hide_render = True
            px.hide_select = True
            px[SRC] = ob.name
            px[LOCAL] = True
        else:
            old = px.data
            px.data = new
            if old.users == 0:
                bpy.data.meshes.remove(old)
        px[SIG] = sig
        px.matrix_world = ob.matrix_world.copy()
        return new, False
    finally:
        if temp:
            bpy.data.meshes.remove(src)


def clear(context):
    """Remove every proxy (and the collection)."""
    coll = collection(context, create=False)
    if coll is None:
        return 0
    n = 0
    for o in list(coll.objects):
        me = o.data
        bpy.data.objects.remove(o)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
        n += 1
    bpy.data.collections.remove(coll)
    return n
