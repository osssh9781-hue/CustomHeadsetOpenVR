"""0.24.136 Light Copies (user: "사본 쓰면 더 빨라?" ... "그럼 일단 그렇게 해 보고" - GAMERA, 192 M triangles).

Measured (real window, 15 parts x 1.3 M triangles, software OpenGL): one Solid view change 3.71 s with the parts,
0.72 s with 10 % copies (x 5.2; tests/gui/light_copies_real_window.py).

How it works - the parts' meshes are never changed:
* every heavy part (at least ``min_tris`` triangles) gets a light copy (Fast Decimate, ``percent`` % of its
  triangles, made in the background) kept on a hidden object of its own, and a last modifier "MCH Light Copy"
  (Geometry Nodes: in the viewport the copy, in a render the part itself; the modifier is also off for renders) -
  F12, Quick Render and the render engine always get the real part;
* a part shows itself (the modifier off) while it is selected, in Edit / Sculpt Mode, for a few seconds after a tool
  read its geometry (``full``), while its copy is out of date, and while any file browser is open (File > Export /
  Import ... - Blender's own exporters read the viewport result);
* a part edited while it showed itself gets a new copy when it rests (its points / faces / modifiers are compared);
* off: the modifiers, the copies and their objects removed - nothing else was touched.

Every place in the add-on that reads a part's evaluated mesh to keep or cut it goes through ``full`` (the copy
never ends up in a mesh); "apply all modifiers" never applies this one; the Live Stack does not list it.
"""
from __future__ import annotations

import json
import threading
import time

import bpy
import numpy as np
from bpy.props import BoolProperty, IntProperty

MOD = 'MCH Light Copy'
GROUP = 'MCH Light Copy'
PROP = 'mch_light'                # on the part: {"holder": ..., "sig": ..., "full": tris, "copy": tris, "pct": %}
HOLDER = '{} (light copy)'
TAG = 'mch_light_holder'
REST = 3.0                        # seconds a part stays itself after a tool read it
TICK = 0.25
OWN_SECONDS = 1.5                 # geometry updates right after our own switch are ours, not edits
CHECK_BUDGET = 0.03               # seconds per tick for comparing parts with their copies
SCAN_SECONDS = 5.0                # new heavy parts looked for this often

TOUCH = {}                        # part name -> when a tool last needed its full geometry
OWN = {}                          # part name -> when we last switched its modifier
DIRTY = set()                     # parts whose geometry changed since their copy was made (checked when they rest)
STALE = set()                     # parts whose copy is out of date (shown as themselves until the new one is made)
QUEUE = []                        # parts waiting for a copy
FAILED = {}                       # part name -> signature its copy failed for (not tried again until it changes)
WORK = {'thread': None, 'name': None, 'src': None, 'result': None, 'error': None}
STATE = {'asked': 0, 'made': 0, 'scan': 0.0}
SAVED = {}                        # save_pre: parts that were light (put back in save_post)


# ---- settings -----------------------------------------------------------------------------------------------------

def _upd_pct(self, context):
    if self.on:
        for ob in parts(context.scene):
            if _info(ob).get('pct') != self.percent:
                queue([ob.name])


def _upd_min(self, context):
    if self.on:
        _rescan(context)


class MCH_PG_Light(bpy.types.PropertyGroup):
    on: BoolProperty(name='Light Copies', default=False,
                     description='Heavy parts you are not working on are drawn from a light copy in the viewport')
    percent: IntProperty(name='Copy %', default=10, min=2, max=50, update=_upd_pct,
                         description='How many of a part\'s triangles its light copy keeps')
    min_tris: IntProperty(name='From', default=300_000, min=10_000, soft_max=5_000_000, step=100_000,
                          update=_upd_min, description='Only parts with at least this many triangles get a copy')


def settings(context):
    sc = getattr(context, 'scene', None)
    return getattr(sc, 'mch_light', None) if sc is not None else None


# ---- the node group and the modifier ------------------------------------------------------------------------------

def node_group():
    """In the viewport the copy object's geometry (when it has faces), else - and in every render - the part."""
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None and ng.bl_idname == 'GeometryNodeTree' and _copy_socket(ng):
        return ng
    ng = bpy.data.node_groups.new(GROUP, 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Copy', in_out='INPUT', socket_type='NodeSocketObject')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    nd, lk = ng.nodes, ng.links
    gi = nd.new('NodeGroupInput')
    go = nd.new('NodeGroupOutput')
    isv = nd.new('GeometryNodeIsViewport')
    info = nd.new('GeometryNodeObjectInfo')
    info.transform_space = 'ORIGINAL'
    size = nd.new('GeometryNodeAttributeDomainSize')
    size.component = 'MESH'
    cmp = nd.new('FunctionNodeCompare')
    cmp.data_type = 'INT'
    cmp.operation = 'GREATER_THAN'
    both = nd.new('FunctionNodeBooleanMath')
    both.operation = 'AND'
    sw = nd.new('GeometryNodeSwitch')
    sw.input_type = 'GEOMETRY'
    gi.location, info.location, size.location = (-700, 0), (-480, -160), (-260, -260)
    isv.location, cmp.location, both.location, sw.location, go.location = \
        (-260, 160), (-60, -220), (120, 120), (320, 0), (520, 0)
    lk.new(gi.outputs['Copy'], info.inputs['Object'])
    lk.new(info.outputs['Geometry'], size.inputs['Geometry'])
    lk.new(size.outputs['Face Count'], cmp.inputs['A'])
    cmp.inputs['B'].default_value = 0
    lk.new(isv.outputs['Is Viewport'], both.inputs[0])
    lk.new(cmp.outputs['Result'], both.inputs[1])        # (no copy object / an empty one: the part, never nothing)
    lk.new(both.outputs['Boolean'], sw.inputs['Switch'])
    lk.new(gi.outputs['Geometry'], sw.inputs['False'])
    lk.new(info.outputs['Geometry'], sw.inputs['True'])
    lk.new(sw.outputs['Output'], go.inputs['Geometry'])
    return ng


def _copy_socket(ng):
    try:
        for it in ng.interface.items_tree:
            if getattr(it, 'item_type', '') == 'SOCKET' and it.in_out == 'INPUT' and it.name == 'Copy':
                return it.identifier
    except (AttributeError, ReferenceError):
        pass
    return ''


def _input(mod, ident):
    try:
        return getattr(mod.properties.inputs, ident).value          # (Blender 5.x)
    except AttributeError:
        pass
    try:
        return mod[ident]
    except (KeyError, TypeError):
        return None


def _set_input(mod, ident, value):
    try:
        getattr(mod.properties.inputs, ident).value = value
        return
    except AttributeError:
        pass
    mod[ident] = value


def is_light_mod(mod):
    try:
        return mod.type == 'NODES' and mod.name == MOD
    except (AttributeError, ReferenceError):
        return False


def _mod(ob):
    try:
        m = ob.modifiers.get(MOD)
    except (AttributeError, ReferenceError):
        return None
    return m if m is not None and m.type == 'NODES' else None


def _info(ob):
    try:
        return json.loads(ob.get(PROP, '') or '{}')
    except (TypeError, ValueError, AttributeError, ReferenceError):
        return {}


def _holder(ob):
    """The part's copy object (the one its modifier shows), or None."""
    mod = _mod(ob)
    if mod is None or mod.node_group is None:
        return None
    h = _input(mod, _copy_socket(mod.node_group))
    try:
        return h if h is not None and h.get(TAG) else None
    except ReferenceError:
        return None


def parts(scene):
    """The scene's parts with a light copy modifier."""
    out = []
    for ob in getattr(scene, 'objects', ()):
        try:
            if ob.type == 'MESH' and _mod(ob) is not None:
                out.append(ob)
        except ReferenceError:
            continue
    return out


# ---- the part itself for every tool -------------------------------------------------------------------------------

def _depsgraph(depsgraph):
    if depsgraph is not None:
        return depsgraph
    try:
        return bpy.context.evaluated_depsgraph_get()
    except (AttributeError, RuntimeError):
        return None


def full(ob, depsgraph=None):
    """``ob`` evaluated as the part itself (its light copy switched off for a few seconds) - every add-on read of a
    part's evaluated geometry goes through this instead of ``ob.evaluated_get(depsgraph)``."""
    orig = getattr(ob, 'original', None) or ob
    dg = _depsgraph(depsgraph)
    mod = _mod(orig)
    if mod is not None:
        now = time.monotonic()
        TOUCH[orig.name] = now
        if mod.show_viewport:
            OWN[orig.name] = now
            mod.show_viewport = False
            if dg is not None:
                try:
                    dg.update()
                except RuntimeError:
                    pass
    return orig.evaluated_get(dg) if dg is not None else orig


def full_all(objects, depsgraph=None):
    """Every one of ``objects`` as itself (one depsgraph update) - exports."""
    now = time.monotonic()
    changed = False
    for ob in objects:
        orig = getattr(ob, 'original', None) or ob
        mod = _mod(orig)
        if mod is None:
            continue
        TOUCH[orig.name] = now
        if mod.show_viewport:
            OWN[orig.name] = now
            mod.show_viewport = False
            changed = True
    if changed:
        dg = _depsgraph(depsgraph)
        if dg is not None:
            try:
                dg.update()
            except RuntimeError:
                pass
    return changed


def full_tris(ob):
    """The part's own triangle count when it has a light copy (its evaluated mesh may be the copy), else None."""
    orig = getattr(ob, 'original', None) or ob
    if _mod(orig) is None:
        return None
    n = _info(orig).get('full')
    return int(n) if isinstance(n, (int, float)) else None


# ---- is the copy still the part? ----------------------------------------------------------------------------------

_SKIP_MODPROPS = {'rna_type', 'name', 'show_expanded', 'is_active', 'is_override_data', 'persistent_uid',
                  'execution_time', 'use_pin_to_last', 'show_on_cage', 'show_in_editmode', 'show_render',
                  'ui_expand_flag', 'debug_options'}


def _modsig(ob):
    out = []
    for m in ob.modifiers:
        if is_light_mod(m):
            continue
        parts_ = [m.name, m.type, str(bool(m.show_viewport))]
        for p in m.bl_rna.properties:
            pid = p.identifier
            if pid in _SKIP_MODPROPS or p.type in {'COLLECTION'}:
                continue
            try:
                v = getattr(m, pid)
            except AttributeError:
                continue
            if p.type == 'POINTER':
                v = getattr(v, 'name', '') if v is not None else ''
            elif getattr(p, 'is_array', False):
                try:
                    v = tuple(round(x, 6) if isinstance(x, float) else x for x in v)
                except TypeError:
                    v = str(v)
            elif isinstance(v, float):
                v = round(v, 6)
            parts_.append(f'{pid}={v}')
        out.append('|'.join(str(x) for x in parts_))
    return ';'.join(out)


def signature(ob):
    """Points, faces, a checksum of the points and the modifier stack (ours left out) of the part itself."""
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get('co', co)
    w = (np.arange(n * 3, dtype=np.float64) % 7.0) + 1.0
    chk = float(np.dot(co.astype(np.float64), w)) if n else 0.0
    return f'{n}:{len(me.polygons)}:{len(me.loops)}:{chk:.6g}:{hash(_modsig(ob)) & 0xffffffff:x}'


# ---- making a copy ------------------------------------------------------------------------------------------------

def _source(ob, dg):
    """The part's geometry (its modifiers applied, ours off) as arrays for the decimation thread."""
    from . import fast_decimate as fd
    mod = _mod(ob)
    others = [m for m in ob.modifiers if not is_light_mod(m) and m.show_viewport]
    toggled = False
    if others and mod is not None and mod.show_viewport:
        OWN[ob.name] = time.monotonic()
        mod.show_viewport = False
        toggled = True
        dg.update()
    ev = None
    try:
        if others:
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
        else:
            me = ob.data
        me.calc_loop_triangles()
        nt, nv = len(me.loop_triangles), len(me.vertices)
        V = np.empty(nv * 3, np.float32)
        me.vertices.foreach_get('co', V)
        T = np.empty(nt * 3, np.int32)
        me.loop_triangles.foreach_get('vertices', T)
        tpoly = np.empty(nt, np.int32)
        me.loop_triangles.foreach_get('polygon_index', tpoly)
        tloop = np.empty(nt * 3, np.int32)
        me.loop_triangles.foreach_get('loops', tloop)
        cvert = np.empty(len(me.loops), np.int32)
        me.loops.foreach_get('vertex_index', cvert)
        attrs = fd._read_attrs(me)
        mats = [s.material for s in ob.material_slots] or list(me.materials)
        uv = me.uv_layers.active.name if me.uv_layers.active else ''
    finally:
        if ev is not None:
            try:
                ev.to_mesh_clear()
            except RuntimeError:
                pass
        if toggled:
            OWN[ob.name] = time.monotonic()
            mod.show_viewport = True
    return {'V': V.reshape(-1, 3), 'T': T.reshape(-1, 3), 'tpoly': tpoly, 'tloop': tloop, 'cvert': cvert,
            'attrs': attrs, 'mats': mats, 'uv': uv, 'ntris': nt, 'sig': signature(ob)}


def _decimate(src, target, nthreads):
    from . import fast_decimate as fd
    return fd.run(src['V'], src['T'], target, nthreads=nthreads)


def _threads():
    from . import fast_decimate as fd
    return max(1, fd.threads() - 1)                 # (one core left for Blender itself)


def _shared(holder, ob):
    """Is ``holder`` also another part's copy (a Shift+D duplicate shares it until it is changed)?"""
    for o in bpy.data.objects:
        if o is not ob and o.type == 'MESH' and _mod(o) is not None and _holder(o) == holder:
            return True
    return False


def _finish(ob, src, res, pct):
    """The finished copy onto the part: its copy object (new or refreshed) and its modifier."""
    from . import fast_decimate as fd
    oV, oF, vsrc, fsrc = res
    cvert, tloop = src['cvert'], src['tloop']
    nv = len(src['V'])
    first_loop = np.full(nv, -1, np.int64)
    first_loop[cvert[::-1]] = np.arange(len(cvert))[::-1]
    src_loop = tloop.reshape(-1, 3)[fsrc]
    keep = cvert[src_loop] == vsrc[oF]
    corner_loop = np.where(keep, src_loop, first_loop[vsrc[oF]]).ravel()
    new = bpy.data.meshes.new(HOLDER.format(ob.name))
    try:
        fd.build_mesh(new, oV, oF)
        fd._write_attrs(new, src['attrs'], vsrc, src['tpoly'][fsrc], corner_loop)
        for m in src['mats']:
            new.materials.append(m)
        if src['uv'] and src['uv'] in new.uv_layers:
            new.uv_layers.active = new.uv_layers[src['uv']]
        new.update()
    except Exception:
        bpy.data.meshes.remove(new)
        raise
    holder = _holder(ob)
    if holder is not None and _shared(holder, ob):
        holder = None
    if holder is None:
        holder = bpy.data.objects.new(HOLDER.format(ob.name), new)
        holder[TAG] = True
        holder.hide_render = True
    else:
        old = holder.data
        holder.data = new
        if old is not None and old.users == 0:
            bpy.data.meshes.remove(old)
    mod = _mod(ob)
    now = time.monotonic()
    if mod is None:
        OWN[ob.name] = now
        mod = ob.modifiers.new(MOD, 'NODES')
        mod.show_viewport = False                    # (sync shows the copy when the part rests)
        mod.node_group = node_group()
        mod.show_render = False
        mod.show_in_editmode = False
        try:
            mod.use_pin_to_last = True
        except AttributeError:
            pass
    elif mod.node_group is None or not _copy_socket(mod.node_group):
        mod.node_group = node_group()
    OWN[ob.name] = now
    _set_input(mod, _copy_socket(mod.node_group), holder)
    _keep_last(ob)
    ob[PROP] = json.dumps({'holder': holder.name, 'sig': src['sig'], 'full': int(src['ntris']),
                           'copy': int(len(oF)), 'pct': int(pct)})
    ob.update_tag()
    FAILED.pop(ob.name, None)
    if signature(ob) == src['sig']:
        STALE.discard(ob.name)
        DIRTY.discard(ob.name)
    else:                                            # (changed while the copy was made: another one)
        STALE.add(ob.name)
        queue([ob.name])


def _drop_holder(ob):
    h = _holder(ob)
    if h is not None and not _shared(h, ob):
        me = h.data
        bpy.data.objects.remove(h, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)


def _keep_last(ob):
    """Our modifier last (pinned; a modifier added after it by older code is moved below it)."""
    mods = ob.modifiers
    if not len(mods) or is_light_mod(mods[-1]):
        return
    for i, m in enumerate(mods):
        if is_light_mod(m):
            try:
                mods.move(i, len(mods) - 1)
            except (AttributeError, RuntimeError, TypeError):
                pass
            return


def make_now(ob, context=None):
    """A copy for ``ob`` right away (no thread)."""
    context = context or bpy.context
    st = settings(context)
    pct = st.percent if st is not None else 10
    src = _source(ob, context.evaluated_depsgraph_get())
    target = max(12, int(round(src['ntris'] * pct / 100.0)))
    _finish(ob, src, _decimate(src, target, _threads()), pct)


def candidates(context):
    """Visible solid mesh parts with at least ``min_tris`` triangles (evaluated, their copy not counted)."""
    st = settings(context)
    low = st.min_tris if st is not None else 300_000
    dg = context.evaluated_depsgraph_get()
    out = []
    for ob in context.view_layer.objects:
        try:
            if ob is None or ob.type != 'MESH' or not ob.visible_get() or ob.display_type not in ('SOLID', 'TEXTURED'):
                continue
            if ob.library is not None or ob.get(TAG):
                continue
            info_full = full_tris(ob)
            if info_full is not None:
                n = info_full
            else:
                me = ob.evaluated_get(dg).data
                n = len(me.loops) - 2 * len(me.polygons)      # (every n-gon is n - 2 triangles)
            if n >= low:
                out.append(ob)
        except (AttributeError, ReferenceError, RuntimeError):
            continue
    return out


def queue(names):
    for n in names:
        if n not in QUEUE and n != WORK['name']:
            QUEUE.append(n)
    STATE['asked'] = max(STATE['asked'], STATE['made'] + len(QUEUE) + (1 if WORK['name'] else 0))


def _rescan(context):
    """New heavy parts queued; parts now under ``From`` lose their copy."""
    st = settings(context)
    if st is None or not st.on:
        return
    heavy = candidates(context)
    names = {o.name for o in heavy}
    for ob in heavy:
        if _mod(ob) is None and ob.name not in QUEUE and ob.name != WORK['name'] \
                and FAILED.get(ob.name) is None:
            queue([ob.name])
    for ob in parts(context.scene):
        if ob.name not in names and ob.visible_get():
            _remove_one(ob)


def _remove_one(ob):
    mod = _mod(ob)
    _drop_holder(ob)
    if mod is not None:
        OWN[ob.name] = time.monotonic()
        ob.modifiers.remove(mod)
    if PROP in ob.keys():
        del ob[PROP]


def _work_step(context):
    """One step of the background work: a finished copy put on its part, or the next part's copy started."""
    th = WORK['thread']
    if th is not None:
        if th.is_alive():
            return
        th.join()
        name, src, res, err, pct = WORK['name'], WORK['src'], WORK['result'], WORK['error'], WORK.get('pct', 10)
        WORK.update(thread=None, name=None, src=None, result=None, error=None)
        ob = bpy.data.objects.get(name)
        if ob is not None and err is None and res is not None:
            try:
                _finish(ob, src, res, pct)
                STATE['made'] += 1
            except Exception as ex:                  # the part stays itself
                print('Mecha Light Copies:', name, ex)
                FAILED[name] = src['sig']
        elif ob is not None:
            print('Mecha Light Copies:', name, err)
            FAILED[name] = src['sig'] if src else ''
        return
    st = settings(context)
    if st is None or not st.on:
        QUEUE.clear()
        return
    while QUEUE:
        name = QUEUE.pop(0)
        ob = bpy.data.objects.get(name)
        if ob is None or ob.type != 'MESH' or ob.mode != 'OBJECT':
            if ob is not None and ob.mode != 'OBJECT':
                QUEUE.append(name)                   # (later: it is being edited)
                return
            continue
        try:
            src = _source(ob, context.evaluated_depsgraph_get())
        except (RuntimeError, ReferenceError, AttributeError, ValueError) as ex:
            print('Mecha Light Copies:', name, ex)
            continue
        if src['ntris'] < 24:
            continue
        pct = st.percent
        target = max(12, int(round(src['ntris'] * pct / 100.0)))
        WORK.update(name=name, src=src, result=None, error=None, pct=pct)
        n_threads = _threads()

        def job(src=src, target=target, n_threads=n_threads):
            try:
                WORK['result'] = _decimate(src, target, n_threads)
            except Exception as ex:                  # (reported on the main thread)
                WORK['error'] = ex
        th = threading.Thread(target=job, name='MCH light copy', daemon=True)
        WORK['thread'] = th
        th.start()
        return


# ---- which parts show their copy ----------------------------------------------------------------------------------

def _browser_open():
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == 'FILE_BROWSER':
                    return True
    except (AttributeError, ReferenceError):
        pass
    return False


def want_light(ob, now, active, browser):
    """Should this part show its copy right now?  (The active part counts only while selected: Blender keeps the last
    clicked part active after a click on empty space - nothing shows it, it is not being worked on.  In Edit / Sculpt
    mode its mode says so.)"""
    if browser:
        return False
    try:
        if ob.mode != 'OBJECT' or ob.select_get():
            return False
    except (AttributeError, ReferenceError, RuntimeError):
        return False
    name = ob.name
    if now - TOUCH.get(name, -1e9) < REST or name in STALE or name in QUEUE or WORK['name'] == name:
        return False
    holder = _holder(ob)
    return holder is not None and holder.data is not None and len(holder.data.polygons) > 0


def sync(context=None):
    """Switch every part to its copy or to itself as ``want_light`` says; a part going back to its copy is first
    compared with the copy's part (a part changed meanwhile gets a new copy).  Returns how many switched."""
    context = context or bpy.context
    st = settings(context)
    if st is None or not st.on:
        return 0
    now = time.monotonic()
    t0 = time.perf_counter()
    active = getattr(context.view_layer.objects, 'active', None)
    browser = _browser_open()
    n = 0
    for ob in parts(context.scene):
        mod = _mod(ob)
        if mod is None:
            continue
        _keep_last(ob)
        want = want_light(ob, now, active, browser)
        name = ob.name
        if want and (name in DIRTY or not mod.show_viewport):
            if time.perf_counter() - t0 > CHECK_BUDGET:
                want = False                         # (compared on a later tick)
            else:
                try:
                    same = signature(ob) == _info(ob).get('sig')
                except (AttributeError, ReferenceError, RuntimeError):
                    same = False
                DIRTY.discard(name)
                if not same:
                    STALE.add(name)
                    queue([name])
                    want = False
        if mod.show_viewport != want:
            OWN[name] = now
            mod.show_viewport = want
            n += 1
    return n


def _tick():
    try:
        ctx = bpy.context
        st = settings(ctx)
        if st is None or not st.on or getattr(ctx, 'view_layer', None) is None:
            return TICK
        now = time.monotonic()
        if now - STATE['scan'] > SCAN_SECONDS:
            STATE['scan'] = now
            _rescan(ctx)
        _work_step(ctx)
        sync(ctx)
    except Exception as ex:                          # (never let the timer die)
        print('Mecha Light Copies:', ex)
    return TICK


# ---- handlers -----------------------------------------------------------------------------------------------------

@bpy.app.handlers.persistent
def _on_update(scene, depsgraph):
    st = getattr(scene, 'mch_light', None)
    if st is None or not st.on:
        return
    now = time.monotonic()
    try:
        for u in depsgraph.updates:
            if not u.is_updated_geometry:
                continue
            idb = u.id
            if not isinstance(idb, bpy.types.Object):
                continue
            ob = idb.original
            if _mod(ob) is None or now - OWN.get(ob.name, -1e9) < OWN_SECONDS:
                continue
            DIRTY.add(ob.name)
    except (ReferenceError, AttributeError, RuntimeError):
        pass


@bpy.app.handlers.persistent
def _on_load(_dummy=None):
    QUEUE.clear()
    STALE.clear()
    TOUCH.clear()
    OWN.clear()
    FAILED.clear()
    SAVED.clear()
    WORK.update(thread=None, name=None, src=None, result=None, error=None)
    STATE.update(asked=0, made=0, scan=0.0)
    for ob in bpy.data.objects:
        if ob.type == 'MESH' and _mod(ob) is not None:
            DIRTY.add(ob.name)                       # (checked against the parts before they go light again)


@bpy.app.handlers.persistent
def _on_save_pre(_dummy=None):
    """The file holds every part showing itself (opened without the add-on: no copy in sight)."""
    SAVED.clear()
    now = time.monotonic()
    for ob in bpy.data.objects:
        mod = _mod(ob) if ob.type == 'MESH' else None
        if mod is not None and mod.show_viewport:
            SAVED[ob.name] = True
            OWN[ob.name] = now
            mod.show_viewport = False


@bpy.app.handlers.persistent
def _on_save_post(_dummy=None):
    now = time.monotonic()
    for name in list(SAVED):
        ob = bpy.data.objects.get(name)
        mod = _mod(ob) if ob is not None else None
        if mod is not None:
            OWN[name] = now
            mod.show_viewport = True
    SAVED.clear()


HANDLERS = (('depsgraph_update_post', _on_update), ('load_post', _on_load), ('save_pre', _on_save_pre),
            ('save_post', _on_save_post))


# ---- on / off -----------------------------------------------------------------------------------------------------

def _timer_on():
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=TICK, persistent=True)


def turn_on(context):
    st = settings(context)
    st.on = True
    heavy = [o for o in candidates(context) if not (_mod(o) is not None and _holder(o) is not None
                                                      and _info(o).get('pct') == st.percent)]
    STATE['asked'], STATE['made'] = 0, 0
    queue([o.name for o in heavy])
    STATE['scan'] = time.monotonic()
    _timer_on()
    return (f'Light Copies on: {len(heavy)} heavy part(s) - copies are made in the background (Blender keeps '
            'working)')


def turn_off(context):
    st = settings(context)
    if st is not None:
        st.on = False
    QUEUE.clear()
    th = WORK['thread']
    if th is not None:
        th.join()
    WORK.update(thread=None, name=None, src=None, result=None, error=None)
    n = 0
    now = time.monotonic()
    for ob in list(bpy.data.objects):
        mod = _mod(ob) if ob.type == 'MESH' else None
        if mod is not None:
            OWN[ob.name] = now
            ob.modifiers.remove(mod)
            n += 1
        if PROP in ob.keys():
            del ob[PROP]
    for h in [o for o in bpy.data.objects if o.get(TAG)]:
        me = h.data
        bpy.data.objects.remove(h, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None and ng.users == 0:
        bpy.data.node_groups.remove(ng)
    STALE.clear()
    DIRTY.clear()
    TOUCH.clear()
    FAILED.clear()
    return f'Light Copies off: {n} part(s) show themselves again, the copies removed'


def status(context):
    """Lines for the panel."""
    st = settings(context)
    if st is None or not st.on:
        return ['Off - every part is drawn in full']
    lines = []
    left = len(QUEUE) + (1 if WORK['name'] else 0)
    if left:
        done = max(0, STATE['asked'] - left)
        lines.append(f'Making copies in the background: {done} / {max(STATE["asked"], done + left)} '
                     '(Blender keeps working)')
    full_n, copy_n, light = 0, 0, 0
    for ob in parts(context.scene):
        mod = _mod(ob)
        if mod is not None and mod.show_viewport:
            info = _info(ob)
            light += 1
            full_n += int(info.get('full', 0))
            copy_n += int(info.get('copy', 0))
    lines.append(f'{light} part(s) drawn light: {full_n / 1e6:.1f} M > {copy_n / 1e6:.1f} M triangles' if light
                 else 'No part drawn light yet (selected or worked-on parts show themselves)')
    return lines


class MCH_OT_light_copies(bpy.types.Operator):
    """Light Copies: heavy parts you are not working on are drawn from a light copy (the viewport only - renders and
    exports use the parts themselves).  Again: off, the copies removed"""
    bl_idname = 'mch.light_copies'
    bl_label = 'Light Copies'
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        st = settings(context)
        if st is None:
            return {'CANCELLED'}
        msg = turn_off(context) if st.on else turn_on(context)
        self.report({'INFO'}, msg)
        try:
            from . import side_panel
            side_panel.dirty()
        except (ImportError, AttributeError):
            pass
        return {'FINISHED'}


CLASSES = (MCH_PG_Light, MCH_OT_light_copies)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_light = bpy.props.PointerProperty(type=MCH_PG_Light)
    for attr, fn in HANDLERS:
        lst = getattr(bpy.app.handlers, attr)
        for f in [f for f in lst if getattr(f, '__name__', '') == fn.__name__
                  and getattr(f, '__module__', '') == fn.__module__]:
            lst.remove(f)
        lst.append(fn)
    _timer_on()


def unregister():
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    for attr, fn in HANDLERS:
        lst = getattr(bpy.app.handlers, attr)
        for f in [f for f in lst if getattr(f, '__name__', '') == fn.__name__
                  and getattr(f, '__module__', '') == fn.__module__]:
            lst.remove(f)
    th = WORK['thread']
    if th is not None:
        th.join()
    WORK.update(thread=None, name=None, src=None, result=None, error=None)
    for ob in bpy.data.objects:                      # (without the add-on: every part shows itself)
        mod = _mod(ob) if ob.type == 'MESH' else None
        if mod is not None:
            mod.show_viewport = False
    if hasattr(bpy.types.Scene, 'mch_light'):
        del bpy.types.Scene.mch_light
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
