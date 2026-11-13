"""0.24.133 Quick Render - Cycles (user: "폴리곤이 높아서 렌더링이 빡센데 좀 더 빠르고 편하게 렌더 못 하나?", "난 사이클만 써").

Measured on a 2.4 M point sculpt (Blender 5.2.3, CPU, 1280 x 720): the dense mesh itself is cheap for Cycles (loading +
BVH about 1.3 s); the time goes into samples x pixels x the shading done per sample.  Blender's defaults are 4096 samples
(adaptive) and 12 bounces; the Mech / Creature Shaders add Ambient Occlusion and Bevel nodes, each casting 8 - 16 extra
rays every time the material is shaded.  So one click renders with:

* a quality - Draft (half size, 16 samples), Preview (48), Final (256) - adaptive sampling + the denoiser (fast
  prefilter for Draft / Preview), fewer light bounces, caustics off;
* Fast Shading: the shaders' AO / Bevel nodes cast fewer rays during the render (16 -> 4; the look stays, the denoiser
  cleans it) - not for Final;
* the GPU when Blender's Preferences have one set (a button sets it - the one place Blender's own settings change, and
  only when clicked);
* the camera = what you see in the viewport (a temporary camera matching the view and its shape), or the scene camera;
* options: Clay (one grey material over everything), Selected Only, Hidden Stay Hidden, Transparent background;
* the picture saved next to the .blend (renders/<file>_<time>_<quality>.png) - or Blender's temp folder when the file
  is not saved yet.

0.24.134 (user: "1억 폴리곤이면?" - their scene: 192 M triangles, 64 GB RAM, RTX 5090): memory, not shading, is
what a very heavy scene runs out of.  Measured (Blender 5.2.3, CPU): Cycles needs about 160 bytes per triangle while it
renders (5 M - 40 M triangle meshes: 153 - 164), on top of what Blender holds; the time before the first sample grows
with it (20 M triangles: 4 s on 4 cores).  So the panel shows the triangles that will render and the memory Cycles needs,
a render that would not fit in the free RAM does not start without a second click, and CPU Only renders on the processor
(the RAM) when the scene is too big for the graphics card.  (Blender's Persistent Data was measured too and left out: a
moved light, a material value, a hidden part or another scene camera all reload the whole scene, and it holds the
memory between renders.)

Nothing in the scene stays changed: every value touched is remembered (by name, see ``live_ref``) and put back when the
render ends, is cancelled or fails; the temporary camera is removed.  Blender's render window shows the progress and
Esc stops it."""
from __future__ import annotations

import os
import time

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

from . import light_copies

QUALITY = {
    'DRAFT': dict(label='Draft', pct=50, samples=16, threshold=0.1, bounces=3, prefilter='FAST', cap=2),
    'PREVIEW': dict(label='Preview', pct=100, samples=32, threshold=0.05, bounces=4, prefilter='FAST', cap=4),
    'FINAL': dict(label='Final', pct=100, samples=256, threshold=0.02, bounces=8, prefilter='ACCURATE', cap=None),
}
QUALITY_ITEMS = [(k, v['label'], f"{v['pct']} % size, {v['samples']} samples (adaptive), {v['bounces']} bounces, "
                                 f"denoised") for k, v in QUALITY.items()]
GEOMETRY = {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'CURVES', 'POINTCLOUD', 'VOLUME', 'GREASEPENCIL'}
RAY_NODES = ('ShaderNodeAmbientOcclusion', 'ShaderNodeBevel')
CAM_NAME = 'MCH Quick Render Camera'
CLAY_NAME = 'MCH Quick Render Clay'
GPU_KINDS = ('OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL')

BYTES_PER_TRI = 160               # 0.24.134 Cycles' memory per triangle while rendering (measured, see above)
CONFIRM_SECONDS = 15.0            # a second click within this renders a scene that may not fit
_JOB = {'active': False}
LAST = {'seconds': 0.0, 'path': '', 'text': '', 'cancelled': False}
LOAD = {'key': None, 't': -1e9, 'val': (0, 0, 0)}
CONFIRM = {'t': -1e9}
GPU = {'checked': False, 'kind': 'NONE', 'names': []}


# ---- settings ------------------------------------------------------------------------------------------------------

class MCH_PG_QuickRender(bpy.types.PropertyGroup):
    quality: EnumProperty(name='Quality', items=QUALITY_ITEMS, default='PREVIEW')
    camera: EnumProperty(name='Camera', default='VIEW', items=[
        ('VIEW', 'This View', 'What you see in the viewport (a temporary camera, the frame shaped like the view)'),
        ('SCENE', 'Scene Camera', 'The scene\'s camera and its render size')])
    fast_shading: BoolProperty(name='Fast Shading', default=True,
                               description='Draft / Preview: the materials\' Ambient Occlusion / Bevel nodes cast fewer '
                                           'rays (2 / 4) and random-walk skin (subsurface) is drawn the Burley way - the '
                                           'Mech / Creature Shaders\' costliest parts.  Final: as made')
    clay: BoolProperty(name='Clay', default=False,
                       description='One grey clay material over everything (a sculpt check - and faster)')
    selected_only: BoolProperty(name='Selected Only', default=False,
                                description='Only the selected parts are rendered (lights and the HDRI stay)')
    hidden_stay_hidden: BoolProperty(name='Hidden Stay Hidden', default=True,
                                     description='What is hidden in the viewport is not rendered either')
    transparent: BoolProperty(name='Transparent', default=False, description='No background: a PNG with alpha')
    save: BoolProperty(name='Save', default=True,
                       description='Save the picture next to the .blend (renders folder) when it is done')
    folder: StringProperty(name='Folder', subtype='DIR_PATH', default='',
                           description='Where pictures are saved (empty: "renders" next to the .blend)')
    cpu_only: BoolProperty(name='CPU Only', default=False,
                           description='Render on the processor even when a GPU is set - for a scene too big for the '
                                       'graphics card\'s memory (Cycles needs about 160 bytes per triangle; the RAM is '
                                       'usually bigger)')


def settings(context):
    return getattr(context.scene, 'mch_qrender', None)


# ---- the GPU (Blender's Preferences) -----------------------------------------------------------------------------

def _cycles_prefs(context=None):
    try:
        return (context or bpy.context).preferences.addons['cycles'].preferences
    except (KeyError, AttributeError):
        return None


def gpu_state(context=None, refresh=False):
    """(compute device type, [names of the GPUs in use]) from Blender's Preferences.  Looked up once (the device list is
    slow to read) and again with ``refresh``."""
    if GPU['checked'] and not refresh:
        return GPU['kind'], GPU['names']
    cp = _cycles_prefs(context)
    kind, names = 'NONE', []
    if cp is not None:
        kind = cp.compute_device_type
        if kind != 'NONE':
            try:
                cp.refresh_devices()
            except (AttributeError, RuntimeError):
                try:
                    cp.get_devices()
                except (AttributeError, RuntimeError):
                    pass
            names = [d.name for d in cp.devices if d.use and d.type == kind]
    GPU.update(checked=True, kind=kind, names=names)
    return kind, names


def gpu_ready(context=None):
    kind, names = gpu_state(context)
    return kind != 'NONE' and bool(names)


def enable_gpu(context=None):
    """Blender's Preferences: the best GPU backend found (OptiX, CUDA, HIP, oneAPI, Metal) and its devices on.  Returns
    a message.  (Only from the button - Blender's own setting.)"""
    cp = _cycles_prefs(context)
    if cp is None:
        return 'Cycles is not enabled in this Blender'
    before = cp.compute_device_type
    for kind in GPU_KINDS:
        try:
            cp.compute_device_type = kind
        except TypeError:                 # (not a choice on this computer)
            continue
        try:
            cp.refresh_devices()
        except (AttributeError, RuntimeError):
            pass
        devs = [d for d in cp.devices if d.type == kind]
        if devs:
            for d in devs:
                d.use = True
            gpu_state(context, refresh=True)
            return f'GPU on: {", ".join(d.name for d in devs)} ({kind}) - Blender Preferences > System'
    try:
        cp.compute_device_type = before
    except TypeError:
        pass
    gpu_state(context, refresh=True)
    return 'No GPU Cycles can use was found - it renders on the CPU'


# ---- memory (0.24.134) ---------------------------------------------------------------------------------------------

def ram_info():
    """(total, available) bytes of the computer's memory, or (None, None) when it cannot be read (then nothing is
    checked).  Windows: GlobalMemoryStatusEx; Linux: /proc/meminfo; macOS: the total only."""
    import sys
    try:
        if sys.platform.startswith('win'):
            import ctypes

            class _MemStat(ctypes.Structure):
                _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                            ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                            ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                            ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                            ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
            m = _MemStat()
            m.dwLength = ctypes.sizeof(_MemStat)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                return None, None
            return int(m.ullTotalPhys), int(m.ullAvailPhys)
        if os.path.isfile('/proc/meminfo'):
            vals = {}
            with open('/proc/meminfo') as f:
                for ln in f:
                    k, _sep, v = ln.partition(':')
                    if k in ('MemTotal', 'MemAvailable'):
                        vals[k] = int(v.split()[0]) * 1024
            return vals.get('MemTotal'), vals.get('MemAvailable')
        total = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
        return int(total), None
    except (OSError, ValueError, AttributeError, ImportError, TypeError):
        return None, None


def _mesh_tris(me):
    """Triangles of a mesh without triangulating it: every face of n corners is n - 2 triangles."""
    try:
        return max(0, len(me.loops) - 2 * len(me.polygons))
    except (AttributeError, ReferenceError, RuntimeError):
        return 0


def scene_load(context, st=None, depsgraph=None, cache=True):
    """(triangles that will render, meshes, bytes Cycles needs for them) - from the evaluated scene, so modifiers
    (Mirror, Subdivision at its viewport level ...) count; a linked duplicate / instance of the same mesh counts once,
    as Cycles stores it once.  Follows Selected Only and Hidden Stay Hidden.  Kept for 3 s (the panel asks often)."""
    scene = context.scene
    sel = bool(st is not None and st.selected_only)
    hid = bool(st is None or st.hidden_stay_hidden)
    key = (scene.name, sel, hid)
    now = time.monotonic()
    if cache and LOAD['key'] == key and now - LOAD['t'] < 3.0:
        return LOAD['val']
    if depsgraph is None:
        vl = getattr(context, 'view_layer', None)
        depsgraph = getattr(vl, 'depsgraph', None) if vl is not None else None
    tris, seen = 0, set()
    names = set()
    if depsgraph is not None:
        try:
            for inst in depsgraph.object_instances:
                ob = inst.object
                if ob.type != 'MESH':
                    continue
                src = (inst.parent if inst.is_instance and inst.parent is not None else ob).original
                if src is None or src.hide_render or (sel and not src.select_get()):
                    continue
                names.add(src.name)
                me = ob.data
                k = me.as_pointer() if me is not None else 0
                if k in seen:
                    continue
                seen.add(k)
                own = light_copies.full_tris(src) if not inst.is_instance else light_copies.instance_full(ob)
                tris += own if own is not None else _mesh_tris(me)   # 0.24.136 a part drawn light renders itself
        except (ReferenceError, RuntimeError, AttributeError):
            pass
    if not hid:                                  # (hidden in the viewport, rendered anyway: their own meshes)
        try:
            for ob in context.view_layer.objects:
                if ob is None or ob.type != 'MESH' or ob.hide_render or ob.name in names or ob.visible_get():
                    continue
                if sel and not ob.select_get():
                    continue
                k = ob.data.as_pointer()
                if k not in seen:
                    seen.add(k)
                    tris += _mesh_tris(ob.data)
        except (ReferenceError, RuntimeError, AttributeError):
            pass
    val = (tris, len(seen), tris * BYTES_PER_TRI)
    LOAD.update(key=key, t=now, val=val)
    return val


def _gb(b):
    """Bytes as the computer shows memory (GiB, so a 64 GB PC reads 64 GB)."""
    g = b / 2 ** 30
    if g < 1.0:
        return f'{b / 2 ** 20:.0f} MB'
    return f'{g:.1f} GB' if g < 10 else f'{g:.0f} GB'


def _count(n):
    return f'{n / 1e6:.1f} M' if n >= 1e6 else f'{n / 1e3:.0f} K' if n >= 1e3 else str(int(n))


def memory_line(context, st=None):
    """([two short lines], too big?) for the panel: the triangles; what Cycles needs and the free RAM."""
    tris, _n, need = scene_load(context, st)
    total, avail = ram_info()
    second = f'Cycles needs ~{_gb(need)}'
    if total:
        second += f' - free RAM {_gb(avail)} / {_gb(total)}' if avail is not None else f' - RAM {_gb(total)}'
    return [f'Scene: {_count(tris)} triangles', second], bool(avail is not None and need > 0.9 * avail)


def memory_check(context, st):
    """None when the render fits (or cannot be checked), else (the warning, a short one for the toast).  A second
    click within CONFIRM_SECONDS renders anyway."""
    tris, _n, need = scene_load(context, st, depsgraph=context.evaluated_depsgraph_get(), cache=False)
    _total, avail = ram_info()
    if avail is None or need <= 0.9 * avail:
        return None
    now = time.monotonic()
    if now - CONFIRM['t'] <= CONFIRM_SECONDS:
        CONFIRM['t'] = -1e9                          # (rendered anyway: the next one is checked again)
        return None
    CONFIRM['t'] = now
    long = (f'This scene needs about {_gb(need)} for Cycles ({_count(tris)} triangles) but {_gb(avail)} of memory '
            f'is free - Blender could close.  Close other programs or use Selected Only; click Quick Render again '
            f'within {CONFIRM_SECONDS:.0f} s to render anyway')
    short = (f'needs ~{_gb(need)}, {_gb(avail)} RAM free - click again within {CONFIRM_SECONDS:.0f} s to render '
             f'anyway')
    return long, short


# ---- the temporary changes -----------------------------------------------------------------------------------------

def _set(owner, attr, value):
    """Set ``owner.attr`` and remember the old value (by name: see live_ref) to put back after the render."""
    from . import live_ref
    try:
        old = getattr(owner, attr)
    except (AttributeError, ReferenceError):
        return
    try:
        same = old == value
    except (TypeError, ValueError):
        same = False
    if same:
        return
    try:
        setattr(owner, attr, value)
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return
    _JOB['undo'].append(('prop', live_ref.wrap(owner), attr, old))


def _set_node(mat, node, attr, value):
    old = getattr(node, attr)
    if old == value:
        return
    setattr(node, attr, value)
    _JOB['undo'].append(('node', mat.name, node.name, attr, old))


def restore():
    """Every remembered value back (newest first), the temporary camera removed.  Safe to call twice."""
    from . import live_ref
    undo = _JOB.get('undo', [])
    while undo:
        rec = undo.pop()
        try:
            if rec[0] == 'prop':
                owner = live_ref.resolve(rec[1])
                if owner is not None:
                    setattr(owner, rec[2], rec[3])
            elif rec[0] == 'node':
                mat = bpy.data.materials.get(rec[1])
                node = mat.node_tree.nodes.get(rec[2]) if mat is not None and mat.node_tree is not None else None
                if node is not None:
                    setattr(node, rec[3], rec[4])
        except (AttributeError, TypeError, ValueError, RuntimeError, ReferenceError):
            pass
    cam = bpy.data.objects.get(_JOB.get('camera') or '')
    if cam is not None:
        data = cam.data
        bpy.data.objects.remove(cam, do_unlink=True)
        if data is not None and data.users == 0:
            bpy.data.cameras.remove(data)
        # (removed this way, the camera stays as an empty (None) entry in view_layer.objects until the next depsgraph
        #  update - anything walking the objects before that would trip on it: sync now)
        try:
            bpy.context.view_layer.update()
        except (AttributeError, RuntimeError):
            pass
    _JOB['camera'] = None


# ---- the camera from the view -------------------------------------------------------------------------------------

def view_frame(region_w, region_h, long_side):
    """(x, y) render size with the viewport's shape and the scene's long side."""
    long_side = max(16, int(long_side))
    if region_w <= 0 or region_h <= 0:
        return long_side, long_side
    a = region_w / float(region_h)
    if a >= 1.0:
        return long_side, max(4, int(round(long_side / a)))
    return max(4, int(round(long_side * a))), long_side


def view_camera_params(view_matrix, perspective, lens, distance, clip_start, clip_end, sensor=36.0):
    """What a camera needs to see exactly what the viewport shows: (matrix_world, type, lens, ortho_scale, clip start,
    clip end).  The viewport draws with twice a camera's view plane (Blender's CAMERA_PARAM_ZOOM_INIT_PERSP), so the
    camera's lens is half the viewport's and an orthographic view is 2 x distance x sensor / lens wide; an orthographic
    camera is moved back so nothing in front of the view is clipped."""
    from mathutils import Matrix
    mw = view_matrix.inverted()
    if perspective:
        return mw, 'PERSP', lens / 2.0, None, clip_start, clip_end
    back = clip_end * 0.5
    mw = mw @ Matrix.Translation((0.0, 0.0, back))
    return mw, 'ORTHO', lens / 2.0, 2.0 * distance * sensor / lens, 1e-3, clip_end + back


def _find_view(context):
    """(window, area, region, space) of the 3D View the render should see: the one the mouse / operator is in, else the
    biggest."""
    area = getattr(context, 'area', None)
    if area is not None and area.type == 'VIEW_3D':
        region = next((r for r in area.regions if r.type == 'WINDOW'), None)
        return context.window, area, region, area.spaces.active
    best = None
    for w in context.window_manager.windows:
        for a in w.screen.areas:
            if a.type == 'VIEW_3D' and (best is None or a.width * a.height > best[1].width * best[1].height):
                best = (w, a)
    if best is None:
        return None, None, None, None
    region = next((r for r in best[1].regions if r.type == 'WINDOW'), None)
    return best[0], best[1], region, best[1].spaces.active


def _camera_from_view(context, scene):
    _w, area, region, space = _find_view(context)
    if area is None or region is None:
        return False
    rv3d = space.region_3d
    if rv3d.view_perspective == 'CAMERA' and scene.camera is not None:
        return True                                  # (looking through the scene camera already: that one)
    mw, kind, lens, ortho, cs, ce = view_camera_params(rv3d.view_matrix, rv3d.is_perspective, space.lens,
                                                       rv3d.view_distance, space.clip_start, space.clip_end)
    data = bpy.data.cameras.new(CAM_NAME)
    data.type = kind
    data.lens = lens
    data.sensor_fit = 'AUTO'
    data.sensor_width = 36.0
    if ortho is not None:
        data.ortho_scale = ortho
    data.clip_start, data.clip_end = cs, ce
    cam = bpy.data.objects.new(CAM_NAME, data)
    scene.collection.objects.link(cam)
    cam.matrix_world = mw
    _JOB['camera'] = cam.name
    _set(scene, 'camera', cam)
    r = scene.render
    x, y = view_frame(region.width, region.height, max(r.resolution_x, r.resolution_y))
    _set(r, 'resolution_x', x)
    _set(r, 'resolution_y', y)
    _set(r, 'pixel_aspect_x', 1.0)
    _set(r, 'pixel_aspect_y', 1.0)
    _set(r, 'use_border', False)
    return True


# ---- what is rendered ----------------------------------------------------------------------------------------------

def _render_objects(context, scene):
    vl = context.view_layer
    out = []
    for ob in vl.objects:
        if ob is None:                              # (an object removed a moment ago, not synced yet)
            continue
        try:
            if not ob.hide_render:
                out.append(ob)
        except ReferenceError:
            continue
    return out


def _clay_material():
    mat = bpy.data.materials.get(CLAY_NAME)
    if mat is None:
        mat = bpy.data.materials.new(CLAY_NAME)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get('Principled BSDF')
        if bsdf is not None:
            bsdf.inputs['Base Color'].default_value = (0.62, 0.6, 0.58, 1.0)
            bsdf.inputs['Roughness'].default_value = 0.55
        mat.diffuse_color = (0.62, 0.6, 0.58, 1.0)
    return mat


def _materials_of(obs):
    mats = []
    for ob in obs:
        for slot in getattr(ob, 'material_slots', ()):
            m = slot.material
            if m is not None and m not in mats:
                mats.append(m)
    return mats


def prepare(context, st):
    """The temporary render settings on the scene (every change remembered).  Returns a short summary."""
    scene = context.scene
    q = QUALITY[st.quality]
    _JOB.update(undo=[], camera=None)
    r, cy = scene.render, scene.cycles
    _set(r, 'engine', 'CYCLES')
    _set(r, 'resolution_percentage', q['pct'])
    _set(r, 'use_lock_interface', True)           # (no edits to the heavy scene while Cycles reads it)
    gpu = gpu_ready(context) and not st.cpu_only     # (0.24.134 CPU Only: the RAM, for a scene the GPU cannot hold)
    _set(cy, 'device', 'GPU' if gpu else 'CPU')
    _set(cy, 'samples', q['samples'])
    _set(cy, 'use_adaptive_sampling', True)
    _set(cy, 'adaptive_threshold', q['threshold'])
    _set(cy, 'adaptive_min_samples', 0)
    _set(cy, 'time_limit', 0.0)
    _set(cy, 'use_denoising', True)
    _set(cy, 'denoiser', 'OPENIMAGEDENOISE')
    _set(cy, 'denoising_prefilter', q['prefilter'])
    if hasattr(cy, 'denoising_use_gpu'):
        _set(cy, 'denoising_use_gpu', gpu)
    b = q['bounces']
    _set(cy, 'max_bounces', b)
    _set(cy, 'diffuse_bounces', min(b, 3))
    _set(cy, 'glossy_bounces', min(b, 3))
    _set(cy, 'transmission_bounces', b)
    _set(cy, 'volume_bounces', 0 if st.quality != 'FINAL' else min(b, 2))
    _set(cy, 'transparent_max_bounces', max(b, 8))
    _set(cy, 'caustics_reflective', False)
    _set(cy, 'caustics_refractive', False)
    _set(cy, 'blur_glossy', 1.0)
    # 0.24.148 the background in the compositor needs the film transparent (it goes behind the render there); a
    # Transparent render with it: the compositor skipped (the parts on nothing, as asked)
    from . import bg_color
    comp_bg = bg_color.comp_on(scene)
    _set(r, 'film_transparent', bool(st.transparent) or comp_bg)
    if comp_bg and st.transparent:
        _set(r, 'use_compositing', False)
    view_cam = False
    if st.camera == 'VIEW' or scene.camera is None:
        view_cam = _camera_from_view(context, scene)
    if scene.camera is None:
        restore()
        raise RuntimeError('No camera: look through the viewport (This View) or add a scene camera')
    obs = _render_objects(context, scene)
    shown = []
    for ob in obs:
        hide = False
        try:
            if st.hidden_stay_hidden and not ob.visible_get():
                hide = True
            if st.selected_only and ob.type in GEOMETRY | {'EMPTY'} and not ob.select_get() \
                    and not ob.get('mch_creature_floor'):        # (0.24.147 the Creature Light floor stays)
                hide = True
        except (ReferenceError, RuntimeError):
            continue
        if hide and ob.type != 'CAMERA' and ob.type != 'LIGHT':
            _set(ob, 'hide_render', True)
        else:
            shown.append(ob)
    capped = 0
    if st.clay:
        _set(context.view_layer, 'material_override', _clay_material())
    elif st.fast_shading and q['cap'] is not None:
        for mat in _materials_of(shown):
            if mat.node_tree is None:
                continue
            for node in mat.node_tree.nodes:
                if node.bl_idname in RAY_NODES and getattr(node, 'samples', 0) > q['cap']:
                    _set_node(mat, node, 'samples', q['cap'])
                    capped += 1
                elif node.bl_idname == 'ShaderNodeBsdfPrincipled' and \
                        getattr(node, 'subsurface_method', 'BURLEY') in {'RANDOM_WALK', 'RANDOM_WALK_SKIN'}:
                    # (the Creature Shader's skin: random-walk subsurface traces inside the dense mesh - Burley is
                    #  the light, close look)
                    _set_node(mat, node, 'subsurface_method', 'BURLEY')
                    capped += 1
    im = r.image_settings
    _set(im, 'file_format', 'PNG')
    _set(im, 'color_mode', 'RGBA' if st.transparent else 'RGB')
    _set(im, 'color_depth', '8')
    _JOB['summary'] = (f"{q['label']}: {r.resolution_x * q['pct'] // 100} x {r.resolution_y * q['pct'] // 100}, "
                       f"{q['samples']} samples, {'GPU' if gpu else 'CPU'}"
                       + (', clay' if st.clay else (f', {capped} AO / Bevel / skin nodes lighter' if capped else ''))
                       + (', this view' if view_cam else ''))
    return _JOB['summary']


# ---- where it goes -------------------------------------------------------------------------------------------------

def output_path(context, st):
    folder = bpy.path.abspath(st.folder) if st.folder else ''
    if not folder:
        if bpy.data.filepath:
            folder = os.path.join(os.path.dirname(bpy.data.filepath), 'renders')
        else:
            folder = os.path.join(bpy.app.tempdir or os.path.expanduser('~'), 'MechaLab_Renders')
    base = bpy.path.display_name_from_filepath(bpy.data.filepath) if bpy.data.filepath else 'untitled'
    stamp = time.strftime('%Y%m%d-%H%M%S')
    return os.path.join(folder, f'{bpy.path.clean_name(base)}_{stamp}_{st.quality.lower()}.png')


def _save_result(context, path):
    img = bpy.data.images.get('Render Result')
    if img is None:
        return ''
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save_render(filepath=path, scene=context.scene)
    return path if os.path.isfile(path) else ''


# ---- the job -------------------------------------------------------------------------------------------------------

def _finish(context=None):
    """The render ended (done, cancelled or failed): the picture saved, the scene's settings back."""
    context = context or bpy.context
    if not _JOB.get('active'):
        return
    st = settings(context)
    seconds = time.monotonic() - _JOB.get('t0', time.monotonic())
    path = ''
    cancelled = bool(_JOB.get('cancelled'))
    try:
        if st is not None and st.save and not cancelled:
            path = _save_result(context, _JOB.get('path') or output_path(context, st))
    except (RuntimeError, OSError) as ex:
        LAST['text'] = f'Not saved: {ex}'
    finally:
        restore()
        _JOB['active'] = False
    LAST.update(seconds=seconds, path=path, cancelled=cancelled)
    if cancelled:
        LAST['text'] = f'Stopped after {seconds:.1f} s'
    else:
        LAST['text'] = f'{seconds:.1f} s' + (f' - {os.path.basename(path)}' if path else '')
    try:
        from . import toast
        toast.show('Quick Render: ' + LAST['text'] + (f'  ({os.path.dirname(path)})' if path else ''),
                   'INFO' if not cancelled else 'WARNING', 6.0)
    except (ImportError, AttributeError, RuntimeError):
        pass
    try:
        from . import side_panel
        side_panel.dirty()
    except (ImportError, AttributeError):
        pass


def _watch():
    if not _JOB.get('active'):
        return None
    try:
        running = bpy.app.is_job_running('RENDER')
    except (AttributeError, TypeError):
        running = False
    if running:
        _JOB['seen'] = True
        return 0.3
    if not _JOB.get('seen') and time.monotonic() - _JOB.get('t0', 0.0) < 5.0:
        return 0.3                                   # (not started yet)
    _finish()
    return None


@bpy.app.handlers.persistent
def _on_cancel(*_args):
    if _JOB.get('active'):
        _JOB['cancelled'] = True


@bpy.app.handlers.persistent
def _on_load(*_args):
    """A file opened while a quick render was going: nothing of the old scene to put back (it is gone)."""
    _JOB.update(active=False, undo=[], camera=None)


class MCH_OT_quick_render(bpy.types.Operator):
    """Render with Cycles, fast: what you see (or the scene camera), fewer samples + the denoiser, lighter AO / Bevel
    shading, the GPU when set.  The picture is saved next to the .blend; the scene's own render settings stay as they are"""
    bl_idname = 'mch.quick_render'
    bl_label = 'Quick Render'
    bl_options = {'REGISTER'}
    quality: StringProperty(default='', options={'SKIP_SAVE'}, description='Draft / Preview / Final (empty: the panel\'s)')

    @classmethod
    def poll(cls, context):
        return context.scene is not None and not _JOB.get('active') and 'cycles' in context.preferences.addons

    def _start(self, context):
        st = settings(context)
        if self.quality in QUALITY:
            st.quality = self.quality
        warn = memory_check(context, st)
        if warn:
            self.report({'WARNING'}, 'Quick Render: ' + warn[0])
            try:
                from . import toast
                toast.show('Quick Render: ' + warn[1], 'WARNING', 8.0)
            except (ImportError, AttributeError, RuntimeError):
                pass
            return None
        try:
            summary = prepare(context, st)
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex))
            return None
        _JOB.update(active=True, cancelled=False, seen=False, t0=time.monotonic(),
                    path=output_path(context, st) if st.save else '')
        return summary

    def invoke(self, context, event):
        summary = self._start(context)
        if summary is None:
            return {'CANCELLED'}
        try:
            res = bpy.ops.render.render('INVOKE_DEFAULT')
        except RuntimeError as ex:
            restore()
            _JOB['active'] = False
            self.report({'ERROR'}, f'Quick Render: {ex}')
            return {'CANCELLED'}
        if 'CANCELLED' in res:
            restore()
            _JOB['active'] = False
            self.report({'WARNING'}, 'Quick Render: Blender did not start the render')
            return {'CANCELLED'}
        if not bpy.app.timers.is_registered(_watch):
            bpy.app.timers.register(_watch, first_interval=0.3)
        self.report({'INFO'}, f'Quick Render - {summary}  (Esc in the render window stops it)')
        return {'FINISHED'}

    def execute(self, context):                      # (a script / the tests: renders and waits)
        summary = self._start(context)
        if summary is None:
            return {'CANCELLED'}
        try:
            bpy.ops.render.render()
        except RuntimeError as ex:
            _JOB['cancelled'] = True
            _finish(context)
            self.report({'ERROR'}, f'Quick Render: {ex}')
            return {'CANCELLED'}
        _finish(context)
        self.report({'INFO'}, f'Quick Render - {summary} - {LAST["text"]}')
        return {'FINISHED'}


class MCH_OT_quick_render_gpu(bpy.types.Operator):
    """Let Cycles use the GPU: Blender Preferences > System > Cycles Render Devices set to the best one found (OptiX /
    CUDA / HIP / oneAPI / Metal) - Blender's own setting, changed only by this button"""
    bl_idname = 'mch.quick_render_gpu'
    bl_label = 'Use the GPU for Cycles'
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        msg = enable_gpu(context)
        self.report({'INFO'} if gpu_ready(context) else {'WARNING'}, msg)
        try:
            from . import side_panel
            side_panel.dirty()
        except (ImportError, AttributeError):
            pass
        return {'FINISHED'}


class MCH_OT_quick_render_folder(bpy.types.Operator):
    """Open the folder the quick renders are saved in"""
    bl_idname = 'mch.quick_render_folder'
    bl_label = 'Open Render Folder'
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        st = settings(context)
        folder = os.path.dirname(LAST['path']) if LAST.get('path') else os.path.dirname(output_path(context, st))
        os.makedirs(folder, exist_ok=True)
        bpy.ops.wm.path_open(filepath=folder)
        return {'FINISHED'}


def status_lines(context):
    """Short lines for the panel: the device, the last render."""
    kind, names = gpu_state(context)
    st = settings(context)
    if kind != 'NONE' and names and st is not None and st.cpu_only:
        dev = 'CPU (CPU Only on - the GPU is not used)'
    elif kind != 'NONE' and names:
        dev = f'GPU: {names[0]}' + (f' +{len(names) - 1}' if len(names) > 1 else '') + f' ({kind})'
    else:
        dev = 'CPU only - no GPU set for Cycles'
    out = [dev]
    if LAST.get('text'):
        out.append('Last: ' + LAST['text'])
    return out


CLASSES = (MCH_PG_QuickRender, MCH_OT_quick_render, MCH_OT_quick_render_gpu, MCH_OT_quick_render_folder)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_qrender = bpy.props.PointerProperty(type=MCH_PG_QuickRender)
    if _on_cancel not in bpy.app.handlers.render_cancel:
        bpy.app.handlers.render_cancel.append(_on_cancel)
    if _on_load not in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.append(_on_load)


def unregister():
    if _JOB.get('active'):
        restore()
        _JOB['active'] = False
    if bpy.app.timers.is_registered(_watch):
        try:
            bpy.app.timers.unregister(_watch)
        except ValueError:
            pass
    for lst, fn in ((bpy.app.handlers.render_cancel, _on_cancel), (bpy.app.handlers.load_pre, _on_load)):
        while fn in lst:
            lst.remove(fn)
    if hasattr(bpy.types.Scene, 'mch_qrender'):
        del bpy.types.Scene.mch_qrender
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
