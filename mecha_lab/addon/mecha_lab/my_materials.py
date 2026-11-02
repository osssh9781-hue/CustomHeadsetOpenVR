"""0.24.95 My Materials (user: "기존에 만들어 놓은 재질도 프리셋으로 등록 가능한가? 가능하게 해 줘"): any material - a Mech
Shader or Creature Shader one, or one of your own node materials - saved whole as a preset, with a ball picture, and
put on the selected parts with a click, in any .blend.

* where: Blender's user config folder, ``<config>/mecha_lab/my_materials/`` - one small .blend per material (the
  material and what it needs: node groups, packed pictures; outside pictures by their full path) + its 128 px ball
  picture + ``index.json`` (name -> file); made only when something is saved
* Save Material...: any material of this file (the selected part's to start with), under a name.  A Mech material's
  lasso Zones stay behind (they belong to the part they were drawn on).  The ball is rendered in a scene of its own
  (Cycles, the interior HDRI as the preset balls) - the user's scene is not touched
* a ball clicked: a copy of that material on the selected meshes (their active slot; a Mech / Creature material gets
  the part's edges measured / its size, as Apply does)
* Delete...: its files gone

(My Presets is the other kind: only a Mech / Creature material's settings, put onto the material already there.)"""
from __future__ import annotations

import json
import math
import os
import re

import bpy
from bpy.props import EnumProperty, StringProperty

DIR = [None]                       # (a test points it elsewhere: never the user's own folder)
THUMB = 128
_CACHE = {}


def folder():
    if DIR[0]:
        return DIR[0]
    d = bpy.utils.user_resource('CONFIG', path='mecha_lab', create=False)    # (made only when saving)
    return os.path.join(d, 'my_materials')


def _index_path():
    return os.path.join(folder(), 'index.json')


def index():
    """{name: {'file': .blend, 'icon': .png, 'mat': material name inside, 'kind': mech / creature / eye / other}}
    - read again only when it changed (the side panel asks many times a second)."""
    p = _index_path()
    try:
        mtime = os.path.getmtime(p)
    except OSError:
        return {}
    if _CACHE.get('key') != (p, mtime):
        try:
            with open(p, encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        _CACHE['key'], _CACHE['data'] = (p, mtime), data if isinstance(data, dict) else {}
    return dict(_CACHE['data'])


def names():
    return list(index())


def _write_index(data):
    os.makedirs(folder(), exist_ok=True)
    p = _index_path()
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, p)
    _CACHE.clear()


def kind(mat):
    from . import creature_shader as cs, mech_shader as ms
    if ms.is_mech(mat):
        return 'mech'
    if cs.is_eye(mat):
        return 'eye'
    if cs.is_creature(mat):
        return 'creature'
    return 'other'


def _safe(name):
    s = re.sub(r'[^A-Za-z0-9_.-]+', '_', name).strip('._') or 'material'
    return s[:60]


def _clean_copy(mat, name):
    """A copy of ``mat`` to save: its Zones left behind (projectors, masks), not tied to a part's material."""
    from . import zones as zn
    cp = mat.copy()
    cp.name = name
    zs = zn.zones_of(cp)
    if zs is not None and len(zs):
        while len(zs):
            zs.remove(0)
        zn.relink(cp)
    if getattr(cp, 'mch_zone_parent', None) is not None:
        cp.mch_zone_parent = None
        cp.mch_zone_follow = False
    return cp


# -----------------------------------------------------------------------------
# the ball picture
# -----------------------------------------------------------------------------

def render_ball(mat, path, size=THUMB, samples=24):
    """``mat`` on a ball, rendered to ``path`` (PNG, transparent background) in a scene of its own (removed after)."""
    import bmesh
    from . import creature_shader as cs, mech_shader as ms
    made = []
    had = {im.as_pointer() for im in bpy.data.images}
    sc = bpy.data.scenes.new('.MCH Ball')
    try:
        me = bpy.data.meshes.new('.MCH Ball')
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=5, radius=1.0)
        bm.to_mesh(me)
        bm.free()
        for p in me.polygons:
            p.use_smooth = True
        me.materials.append(mat)
        ob = bpy.data.objects.new('.MCH Ball', me)
        made += [ob, me]
        sc.collection.objects.link(ob)
        if ms.is_mech(mat) or cs.is_creature(mat):
            try:
                ms.store_curvature(me)
            except (AttributeError, RuntimeError, ValueError):
                pass
        cd = bpy.data.cameras.new('.MCH Ball Cam')
        cd.type = 'ORTHO'
        cd.ortho_scale = 2.3
        cam = bpy.data.objects.new('.MCH Ball Cam', cd)
        made += [cam, cd]
        sc.collection.objects.link(cam)
        cam.location = (0.0, -6.0, 2.2)
        cam.rotation_euler = (-cam.location).normalized().to_track_quat('-Z', 'Y').to_euler()
        sc.camera = cam
        w = bpy.data.worlds.new('.MCH Ball World')
        made.append(w)
        w.use_nodes = True
        nt = w.node_tree
        bg = nt.nodes.get('Background')
        hdr = os.path.join(ms.hdri_dir(), 'interior.exr')
        if bg is not None and os.path.isfile(hdr):
            env = nt.nodes.new('ShaderNodeTexEnvironment')
            env.image = bpy.data.images.load(hdr, check_existing=True)
            mp = nt.nodes.new('ShaderNodeMapping')
            tc = nt.nodes.new('ShaderNodeTexCoord')
            mp.inputs['Rotation'].default_value[2] = math.radians(90)
            nt.links.new(tc.outputs['Generated'], mp.inputs['Vector'])
            nt.links.new(mp.outputs['Vector'], env.inputs['Vector'])
            nt.links.new(env.outputs['Color'], bg.inputs['Color'])
        elif bg is not None:
            bg.inputs['Color'].default_value = (0.5, 0.5, 0.52, 1.0)
        sc.world = w
        r = sc.render
        sc.render.engine = 'CYCLES'
        sc.cycles.device = 'CPU'
        sc.cycles.samples = samples
        sc.cycles.use_denoising = False
        sc.cycles.max_bounces = 6
        sc.cycles.sample_clamp_indirect = 3.0
        r.film_transparent = True
        r.resolution_x = r.resolution_y = size
        r.resolution_percentage = 100
        r.image_settings.file_format = 'PNG'
        r.image_settings.color_mode = 'RGBA'
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.exposure = -0.25
        r.filepath = path
        bpy.ops.render.render(write_still=True, scene=sc.name)
    finally:
        bpy.data.scenes.remove(sc)
        for idb in made:
            try:
                if isinstance(idb, bpy.types.Object):
                    bpy.data.objects.remove(idb)
                elif isinstance(idb, bpy.types.Mesh):
                    bpy.data.meshes.remove(idb)
                elif isinstance(idb, bpy.types.Camera):
                    bpy.data.cameras.remove(idb)
                elif isinstance(idb, bpy.types.World):
                    bpy.data.worlds.remove(idb)
            except (ReferenceError, RuntimeError):
                pass
        for im in list(bpy.data.images):        # (the HDRI loaded for the ball, if this file did not have it)
            if im.as_pointer() not in had and im.users == 0:
                bpy.data.images.remove(im)
    return os.path.isfile(path)


# -----------------------------------------------------------------------------
# save / apply / delete
# -----------------------------------------------------------------------------

def save(mat, name, thumb=True):
    """``mat`` saved whole as the preset ``name`` (replacing one of that name).  Returns the index entry."""
    name = name.strip()
    if not name:
        raise RuntimeError('give it a name')
    if mat is None:
        raise RuntimeError('no material to save')
    os.makedirs(folder(), exist_ok=True)
    data = index()
    old = data.get(name)
    stem = old['file'][:-6] if old else _safe(name)
    if not old:
        k = 1
        while any(e['file'] == stem + '.blend' for e in data.values()):
            k += 1
            stem = f'{_safe(name)}_{k}'
    blend = os.path.join(folder(), stem + '.blend')
    icon = os.path.join(folder(), stem + '.png')
    cp = _clean_copy(mat, name)
    try:
        bpy.data.libraries.write(blend, {cp}, fake_user=True, path_remap='ABSOLUTE', compress=True)
        if thumb:
            try:
                render_ball(cp, icon)
            except (RuntimeError, OSError) as ex:
                print('My Materials: no ball picture -', ex)
        entry = {'file': stem + '.blend', 'icon': stem + '.png' if os.path.isfile(icon) else '', 'mat': cp.name,
                 'kind': kind(mat)}
    finally:
        bpy.data.materials.remove(cp)
    data[name] = entry
    _write_index(data)
    return entry


def load(name):
    """The preset ``name`` appended into this file (a new material).  Returns it."""
    e = index().get(name)
    if e is None:
        raise RuntimeError(f'no saved material "{name}"')
    blend = os.path.join(folder(), e['file'])
    if not os.path.isfile(blend):
        raise RuntimeError(f'its file is missing: {blend}')
    with bpy.data.libraries.load(blend, link=False) as (src, dst):
        if e['mat'] not in src.materials:
            raise RuntimeError(f'"{e["mat"]}" is not in {blend}')
        dst.materials = [e['mat']]
    mat = dst.materials[0]
    mat.use_fake_user = False
    return mat


def apply(context, name, objs=None):
    """A copy of the preset on the meshes ``objs`` (the selected ones): their active slot.  Returns (material, n)."""
    from . import creature_shader as cs, mech_shader as ms
    objs = [o for o in (objs if objs is not None else context.selected_objects) if o is not None and o.type == 'MESH']
    if not objs:
        raise RuntimeError('select the meshes to put it on')
    mat = load(name)
    for ob in objs:
        if ob.material_slots:
            ob.material_slots[ob.active_material_index].material = mat
        else:
            ob.data.materials.append(mat)
        if ms.is_mech(mat) or cs.is_creature(mat):
            try:
                ms.store_curvature(ob.data)
            except (AttributeError, RuntimeError, ValueError):
                pass
    if cs.is_creature(mat):
        getattr(mat, cs.KEY).size = cs.body_size(objs)
    return mat, len(objs)


def delete(name):
    data = index()
    e = data.pop(name, None)
    if e is None:
        return False
    for f in (e.get('file'), e.get('icon')):
        if f:
            try:
                os.remove(os.path.join(folder(), f))
            except OSError:
                pass
    _write_index(data)
    return True


def icon_path(name):
    e = index().get(name) or {}
    p = os.path.join(folder(), e['icon']) if e.get('icon') else ''
    return p if p and os.path.isfile(p) else ''


# -----------------------------------------------------------------------------
# operators
# -----------------------------------------------------------------------------

_MAT_ITEMS, _SAVED_ITEMS = [], []          # (kept: Blender reads an enum's strings after the call)


def _material_items(self, context):
    _MAT_ITEMS[:] = [(m.name, m.name, '') for m in bpy.data.materials if not m.name.startswith('.')] \
        or [('', '(no materials)', '')]
    return _MAT_ITEMS


def _saved_items(self, context):
    _SAVED_ITEMS[:] = [(n, n, '') for n in names()] or [('', '(none saved)', '')]
    return _SAVED_ITEMS


class MCH_OT_my_material_save(bpy.types.Operator):
    """Save a material whole as one of My Materials (any material of this file - also your own node materials): a
    ball for it, for every .blend"""
    bl_idname = 'mch.my_material_save'
    bl_label = 'Save Material'
    bl_options = {'REGISTER'}
    material: EnumProperty(name='Material', items=_material_items)
    name: StringProperty(name='Name', default='')

    def invoke(self, context, event):
        ob = context.active_object
        mat = getattr(ob, 'active_material', None) if ob is not None else None
        if mat is not None:
            try:
                self.material = mat.name
            except TypeError:
                pass
        self.name = self.material or ''
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        mat = bpy.data.materials.get(self.material)
        try:
            save(mat, self.name or (mat.name if mat is not None else ''))
        except RuntimeError as ex:
            self.report({'WARNING'}, f'My Materials: {ex}')
            return {'CANCELLED'}
        self.report({'INFO'}, f'My Materials: "{self.name or mat.name}" saved')
        _redraw(context)
        return {'FINISHED'}


class MCH_OT_my_material_apply(bpy.types.Operator):
    """Put a copy of this saved material on the selected meshes"""
    bl_idname = 'mch.my_material_apply'
    bl_label = 'Use My Material'
    bl_options = {'REGISTER', 'UNDO'}
    name: StringProperty(default='')

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            mat, n = apply(context, self.name)
        except RuntimeError as ex:
            self.report({'WARNING'}, f'My Materials: {ex}')
            return {'CANCELLED'}
        self.report({'INFO'}, f'"{mat.name}" on {n} mesh(es)')
        return {'FINISHED'}


class MCH_OT_my_material_delete(bpy.types.Operator):
    """Delete one of My Materials (its files)"""
    bl_idname = 'mch.my_material_delete'
    bl_label = 'Delete My Material'
    bl_options = {'REGISTER'}
    name: EnumProperty(name='Material', items=_saved_items)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if not self.name or not delete(self.name):
            return {'CANCELLED'}
        _redraw(context)
        return {'FINISHED'}


def _redraw(context):
    try:
        from . import side_panel
        side_panel.dirty()
    except (ImportError, AttributeError):
        pass


CLASSES = (MCH_OT_my_material_save, MCH_OT_my_material_apply, MCH_OT_my_material_delete)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
