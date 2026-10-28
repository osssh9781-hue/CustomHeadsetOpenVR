"""ZBrush <-> Blender bridge through OBJ files (NOT the GoZ protocol).

Why not GoZ: GoZ uses Pixologic/Maxon's own binary format and installer
scripts that cannot be verified here; claiming support would be dishonest.
This bridge is the reliable manual route:

1. **Send**: every selected mesh is exported to its own OBJ file in an
   exchange folder (never joined; join beforehand yourself if you want one
   ZBrush tool).  Each object gets a stable id (custom property
   ``mch_zb_id``); a manifest JSON records object name, file, export time and
   the object's world matrix at export.
2. In ZBrush: Tool > Import the OBJ, work (DynaMesh, ZRemesher, Smooth... all
   manual), then Tool > Export **to the same file name**.
3. **Import Back**: changed files (newer than the export) are imported, their
   world coordinates are converted back into the original object's local space
   (export matrix), and the object's mesh data is replaced.  Object, transform,
   modifiers, material slots and collections are kept; the previous mesh is
   kept as ``<mesh>_preZBrush`` (fake user) unless disabled.  Undo works.

Failure handling: missing/empty files are skipped with a report; renamed
objects are found by id; deleted objects are re-created from the file.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from mathutils import Matrix

MANIFEST = 'mecha_zbrush_manifest.json'
ID_KEY = 'mch_zb_id'
AXES = [('X', 'X', ''), ('Y', 'Y', ''), ('Z', 'Z', ''),
        ('NEGATIVE_X', '-X', ''), ('NEGATIVE_Y', '-Y', ''), ('NEGATIVE_Z', '-Z', '')]
GOZ_PATHS = (r'C:\Users\Public\Pixologic\GoZBrush', r'C:\Users\Public\Maxon\GoZBrush',
             '/Users/Shared/Pixologic/GoZBrush', '/Users/Shared/Maxon/GoZBrush')


class MCH_PG_ZBrush(bpy.types.PropertyGroup):
    exchange_dir: StringProperty(name='Exchange Folder', subtype='DIR_PATH', default='',
                                 description='Where OBJ files are written (empty = Blender user config folder)')
    zbrush_exe: StringProperty(name='ZBrush Executable', subtype='FILE_PATH', default='',
                               description='Optional: launch ZBrush after sending (Windows: ZBrush.exe)')
    scale: FloatProperty(name='Scale', default=1.0, min=0.0001, soft_max=1000.0,
                         description='Export multiplies by this, import divides by it')
    forward_axis: EnumProperty(name='Forward', items=AXES, default='NEGATIVE_Z')
    up_axis: EnumProperty(name='Up', items=AXES, default='Y')
    apply_modifiers: BoolProperty(name='Apply Modifiers on Send', default=True)
    split_ngons: BoolProperty(name='ZBrush-safe Faces', default=True,
                              description='Faces with more than 4 corners (Boolean / cut n-gons) are split into clean '
                                          'triangles for ZBrush only - ZBrush fans them and concave ones tear into '
                                          'slivers. Quads stay quads; the Blender mesh is not changed')
    keep_backup: BoolProperty(name='Keep Previous Mesh', default=True,
                              description='Keep the replaced mesh as <name>_preZBrush (fake user)')
    export_format: EnumProperty(name='Format', default='OBJ', items=[      # 0.24.59 the Layers panel's Export
        ('OBJ', 'OBJ', 'Wavefront OBJ (ZBrush, most programs)'), ('FBX', 'FBX', 'Autodesk FBX')])
    export_scope: EnumProperty(name='Export', default='SELECTED', items=[
        ('SELECTED', 'Selected', 'The selected meshes'), ('VISIBLE', 'Visible', 'Every visible mesh')])
    import_all: BoolProperty(name='Re-import Unchanged Files', default=False,
                             description='Also import files ZBrush did not modify')


def exchange_folder(settings):
    path = bpy.path.abspath(settings.exchange_dir).strip() if settings.exchange_dir else ''
    if not path:
        path = bpy.utils.user_resource('CONFIG', path='mecha_lab/zbrush_bridge', create=True)
    os.makedirs(path, exist_ok=True)
    return Path(path)


def detect_goz():
    return next((p for p in GOZ_PATHS if os.path.isdir(p)), None)


def read_manifest(folder):
    f = folder / MANIFEST
    if not f.is_file():
        return {'version': 1, 'objects': {}}
    try:
        data = json.loads(f.read_text(encoding='utf-8'))
        data.setdefault('objects', {})
        return data
    except (OSError, ValueError):
        return {'version': 1, 'objects': {}}


def write_manifest(folder, data):
    tmp = folder / (MANIFEST + '.tmp')
    tmp.write_text(json.dumps(data, indent=1), encoding='utf-8')
    os.replace(tmp, folder / MANIFEST)


def _safe(name):
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', name).strip('._')[:48] or 'Object'


def _restore_selection(context, selected, active):
    for o in context.selected_objects:
        o.select_set(False)
    for o in selected:
        try:
            if o.name in bpy.data.objects:
                o.select_set(True)
        except ReferenceError:
            pass
    if active is not None:
        try:
            context.view_layer.objects.active = active
        except (ReferenceError, RuntimeError):
            pass


def export_copy(context, ob, apply_modifiers, split_ngons=True):
    """0.24.37 A temporary object to export: the (evaluated) mesh with every n-gon split into triangles (beauty
    fill, quads kept), so ZBrush gets no concave n-gon to fan into slivers.  The caller removes it."""
    import bmesh
    dg = context.evaluated_depsgraph_get()
    src = ob.evaluated_get(dg) if apply_modifiers else ob
    me = bpy.data.meshes.new_from_object(src, preserve_all_data_layers=True, depsgraph=dg) if apply_modifiers \
        else ob.data.copy()
    if split_ngons:
        bm = bmesh.new()
        try:
            bm.from_mesh(me)
            ngons = [f for f in bm.faces if len(f.verts) > 4]
            if ngons:
                bmesh.ops.triangulate(bm, faces=ngons, quad_method='BEAUTY', ngon_method='BEAUTY')
                bm.to_mesh(me)
        finally:
            bm.free()
    tmp = bpy.data.objects.new(ob.name + '_ZB', me)
    tmp.matrix_world = ob.matrix_world.copy()
    context.scene.collection.objects.link(tmp)
    return tmp


def quad_copy(context, tmp, quad_size, client=False, subdiv=1):
    """0.24.76 Export Quad Mesh: the temporary export copy ``tmp`` rebuilt as quads about ``quad_size`` (scene units)
    apart - Fix Mesh first, then Quad Remesh with the part's hard edges kept - and, with ``client``, those edges
    given a narrow bevel + Subdivide baked in, every face smooth (looks the same in Maya / Max / ZBrush).  Returns
    a short note ('' when done as asked).
    0.24.77 Each part keeps its shape: the quads are at most a PART_QUADS-th of the part's own size (one Quad Size for
    the whole export made small / detailed parts a few dozen faces - flat shards in ZBrush), and the result is
    measured against the part (FIT, the part after Fix Mesh): too far off, it is made again finer (x3, TRIES times);
    still off, the part goes out as it was (repaired)."""
    from types import SimpleNamespace
    from . import hard_edges as he
    from . import quad_field as qf
    me = tmp.data
    if not len(me.polygons):
        return 'empty'
    if me.shape_keys is not None:
        return 'shape keys: exported as it is'
    k = abs(tmp.matrix_world.to_3x3().determinant()) ** (1.0 / 3.0) or 1.0     # object -> world scale
    area = sum(p.area for p in me.polygons) * k * k
    diag = _diag(me) * k
    q = min(quad_size, diag / PART_QUADS) if diag > 0 else quad_size
    target = int(min(QUAD_MAX, max(QUAD_MIN, area / max(q, 1e-9) ** 2)))
    from . import mesh_fix
    orig = me.copy()
    if mesh_fix.needs_fix(orig):                      # (measured against - and kept if need be - the repaired part:
        mesh_fix.fix_mesh(orig, fill='CRACKS')        # a broken one's inside walls are not its shape)
    err, msg = None, ''
    try:
        for _try in range(TRIES):
            msg = qf.remesh_object(tmp, target)
            if not msg.startswith('Quad Remesh') or ' > ' not in msg:
                break                                  # (not remeshed: the copy goes out as it was)
            err = fit_error(orig, tmp.data)
            if err <= FIT or target >= QUAD_MAX:
                break
            _put_back(tmp, orig)                       # too far off: again, finer
            target = int(min(QUAD_MAX, target * 3))
            err = None
        if err is None or err > FIT:
            _put_back(tmp, orig)
            return (msg if msg and not msg.startswith('Quad Remesh') else
                    'kept as it was, repaired (quads could not keep its shape)')
        if mesh_fix.needs_fix(tmp.data) and not mesh_fix.needs_fix(orig):
            mesh_fix.fix_mesh(tmp.data, fill='SMALL')    # (a small hole the remesh left in a closed part: closed)
    finally:
        if orig.users == 0:
            bpy.data.meshes.remove(orig)
    if client:
        st = SimpleNamespace(he_crease=False, he_outer=False, he_bevel=True, he_width=0.2 * q / k,
                             he_segments=2, he_style='ROUND', he_profile=0.5, he_subdiv=max(0, int(subdiv)),
                             he_normals=False, he_client=True, he_fit=False, he_match=False)
        he.set_live(tmp, st)
        he.apply_live(context, tmp, st)
        if mesh_fix.needs_fix(tmp.data):              # 0.24.81 the bevel can fold a tiny corner on itself (an edge
            mesh_fix.fix_mesh(tmp.data, fill='SMALL')    # with 4 faces, a sliver): welded away, the part stays closed
    return ''


PART_QUADS = 20                 # 0.24.77 Export Quad Mesh: at least this many quads across a part (its diagonal)
FIT = 0.005                     # ... 95 % of the part's own surface within this share of its size, or again finer
TRIES = 4


def _diag(me):
    import numpy as np
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    return float(np.linalg.norm(co.max(0) - co.min(0))) if len(co) else 0.0


def fit_error(orig, new, samples=4000):
    """How far the part's own surface (``orig`` points, up to ``samples``) is from ``new`` (same space): the 95th
    percentile, as a share of the part's size (a lost corner, a thin wall gone flat, a piece gone - all show)."""
    import bmesh
    import numpy as np
    from mathutils.bvhtree import BVHTree
    co = np.empty(len(orig.vertices) * 3, np.float64)
    orig.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    if not len(co) or not len(new.polygons):
        return float('inf')
    if len(co) > samples:
        co = co[np.random.default_rng(0).choice(len(co), samples, replace=False)]
    bm = bmesh.new()
    try:
        bm.from_mesh(new)
        bvh = BVHTree.FromBMesh(bm)
    finally:
        bm.free()
    d = np.array([(bvh.find_nearest(p)[3] if bvh.find_nearest(p)[0] is not None else np.inf) for p in co])
    size = _diag(orig)
    return float(np.percentile(d, 95) / size) if size > 0 else 0.0


def _put_back(tmp, orig):
    old = tmp.data
    tmp.data = orig.copy()
    if old.users == 0:
        bpy.data.meshes.remove(old)


QUAD_MIN = 60                   # Export Quad Mesh: at least / at most this many faces per object
QUAD_MAX = 60000


def export_size(objects):
    """Diagonal of the world bounding box of ``objects`` (the Quad Size % is of this)."""
    from mathutils import Vector
    pts = [o.matrix_world @ Vector(c) for o in objects for c in o.bound_box]
    if not pts:
        return 1.0
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return max((hi - lo).length, 1e-6)


def ngon_count(me):
    return sum(1 for p in me.polygons if p.loop_total > 4)


def send_objects(context, objects, settings):
    folder = exchange_folder(settings)
    data = read_manifest(folder)
    selected = list(context.selected_objects)
    active = context.view_layer.objects.active
    sent = []
    try:
        for ob in objects:
            zid = ob.get(ID_KEY) or uuid.uuid4().hex[:12]
            ob[ID_KEY] = zid
            path = folder / f'{_safe(ob.name)}__{zid}.obj'
            for o in context.selected_objects:
                o.select_set(False)
            tmp = export_copy(context, ob, settings.apply_modifiers, getattr(settings, 'split_ngons', True))
            try:
                tmp.select_set(True)
                context.view_layer.objects.active = tmp
                bpy.ops.wm.obj_export(filepath=str(path), export_selected_objects=True,
                                      apply_modifiers=False, export_materials=False,
                                      export_uv=True, export_normals=True, export_triangulated_mesh=False,
                                      forward_axis=settings.forward_axis, up_axis=settings.up_axis,
                                      global_scale=settings.scale)
            finally:
                me = tmp.data
                bpy.data.objects.remove(tmp, do_unlink=True)
                if me.users == 0:
                    bpy.data.meshes.remove(me)
            if not path.is_file():
                raise RuntimeError(f'OBJ export produced no file for {ob.name}')
            data['objects'][zid] = {
                'object': ob.name, 'file': path.name, 'mtime': path.stat().st_mtime,
                'sent': time.time(), 'matrix': [list(r) for r in ob.matrix_world],
                'scale': settings.scale, 'forward': settings.forward_axis, 'up': settings.up_axis}
            sent.append(ob.name)
    finally:
        _restore_selection(context, selected, active)
        write_manifest(folder, data)
    return folder, sent


def _find_object(zid, name):
    for ob in bpy.data.objects:
        if ob.get(ID_KEY) == zid and ob.type == 'MESH':
            return ob
    ob = bpy.data.objects.get(name)
    return ob if ob is not None and ob.type == 'MESH' else None


def _import_obj_mesh(context, path, entry):
    """Import one OBJ, return a single new Mesh in WORLD space (temp objects removed)."""
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=str(path), forward_axis=entry.get('forward', 'NEGATIVE_Z'),
                          up_axis=entry.get('up', 'Y'), global_scale=1.0 / max(entry.get('scale', 1.0), 1e-9))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH']
    try:
        if not meshes:
            raise RuntimeError(f'{path.name}: no mesh in file')
        import bmesh
        bm = bmesh.new()
        try:
            for o in meshes:   # one sent object may come back as several OBJ groups
                tmp = o.data.copy()
                tmp.transform(o.matrix_world)
                bm.from_mesh(tmp)
                bpy.data.meshes.remove(tmp)
            if not bm.faces:
                raise RuntimeError(f'{path.name}: mesh has no faces')
            me = bpy.data.meshes.new(path.stem)
            bm.to_mesh(me)
        finally:
            bm.free()
        return me
    finally:
        for o in new:
            data = o.data if o.type == 'MESH' else None
            bpy.data.objects.remove(o, do_unlink=True)
            if data is not None and data.users == 0:
                bpy.data.meshes.remove(data)


def import_back(context, settings):
    folder = exchange_folder(settings)
    data = read_manifest(folder)
    done, skipped, created, errors = [], [], [], []
    for zid, entry in list(data['objects'].items()):
        path = folder / entry['file']
        if not path.is_file():
            errors.append(f'{entry["object"]}: file missing')
            continue
        mtime = path.stat().st_mtime
        if mtime <= entry.get('mtime', 0) + 1e-6 and not settings.import_all:
            skipped.append(entry['object'])
            continue
        try:
            me = _import_obj_mesh(context, path, entry)
        except (RuntimeError, OSError) as ex:
            errors.append(str(ex))
            continue
        export_matrix = Matrix(entry['matrix'])
        me.transform(export_matrix.inverted_safe())
        ob = _find_object(zid, entry['object'])
        if ob is None:
            ob = bpy.data.objects.new(entry['object'], me)
            context.scene.collection.objects.link(ob)
            ob.matrix_world = export_matrix
            ob[ID_KEY] = zid
            created.append(ob.name)
        else:
            old = ob.data
            for mat in old.materials:
                me.materials.append(mat)
            shared = old.users > 1          # Alt+D copies keep the old mesh
            original_name = old.name
            ob.data = me
            if shared:
                me.name = original_name + '_ZBrush'
            elif settings.keep_backup:
                old.name = original_name + '_preZBrush'
                old.use_fake_user = True
                me.name = original_name
            else:
                bpy.data.meshes.remove(old)
                me.name = original_name
            done.append(ob.name)
        entry['mtime'] = mtime
        entry['object'] = ob.name
    write_manifest(folder, data)
    return done, skipped, created, errors


class MCH_OT_zbrush_send(bpy.types.Operator):
    bl_idname = 'mch.zbrush_send'
    bl_label = 'Send Selected to ZBrush (OBJ)'
    bl_description = ('Export each selected mesh to its own OBJ in the exchange folder (no join). '
                      'In ZBrush: Tool > Import, work, Tool > Export to the same file')
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        s = context.scene.mch_zbrush
        objs = [o for o in context.selected_objects if o.type == 'MESH']
        try:
            folder, sent = send_objects(context, objs, s)
        except (RuntimeError, OSError) as ex:
            self.report({'ERROR'}, f'Send failed: {ex}')
            return {'CANCELLED'}
        exe = bpy.path.abspath(s.zbrush_exe) if s.zbrush_exe else ''
        if exe:
            try:
                subprocess.Popen([exe])
            except OSError as ex:
                self.report({'WARNING'}, f'Could not launch ZBrush: {ex}')
        self.report({'INFO'}, f'Sent {len(sent)} object(s) to {folder}')
        return {'FINISHED'}


class MCH_OT_zbrush_import(bpy.types.Operator):
    bl_idname = 'mch.zbrush_import'
    bl_label = 'Import Back from ZBrush'
    bl_description = 'Replace the mesh of each sent object whose OBJ file was re-exported from ZBrush'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT' and context.active_object is not None:
            bpy.ops.object.mode_set(mode='OBJECT')
        done, skipped, created, errors = import_back(context, context.scene.mch_zbrush)
        msg = f'Updated {len(done)}, unchanged {len(skipped)}, re-created {len(created)}'
        if errors:
            self.report({'WARNING'}, msg + ' | ' + '; '.join(errors[:3]))
        else:
            self.report({'INFO'}, msg)
        return {'FINISHED'}


class MCH_OT_zbrush_open_folder(bpy.types.Operator):
    bl_idname = 'mch.zbrush_open_folder'
    bl_label = 'Open Exchange Folder'
    bl_options = {'REGISTER'}

    def execute(self, context):
        folder = exchange_folder(context.scene.mch_zbrush)
        try:
            bpy.ops.wm.path_open(filepath=str(folder))
        except RuntimeError as ex:
            self.report({'WARNING'}, f'{folder} ({ex})')
        return {'FINISHED'}


def manifest_rows(settings):
    folder = exchange_folder(settings)
    rows = []
    for zid, e in read_manifest(folder)['objects'].items():
        path = folder / e['file']
        state = 'missing'
        if path.is_file():
            state = 'CHANGED' if path.stat().st_mtime > e.get('mtime', 0) + 1e-6 else 'sent'
        rows.append((e['object'], e['file'], state))
    return rows


def export_objects(context, scope):
    """The meshes an Export takes: the selected ones, or every mesh visible in the viewport."""
    if scope == 'VISIBLE':
        out = []
        for o in context.view_layer.objects:
            try:
                if o.type == 'MESH' and o.visible_get():
                    out.append(o)
            except (RuntimeError, ReferenceError):
                pass
        return out
    return [o for o in context.selected_objects if o.type == 'MESH']


class MCH_OT_export_mesh(bpy.types.Operator):
    """Export meshes to an OBJ or FBX file (no ZBrush link needed): the selected ones or every visible one -
    n-gons split into clean triangles (ZBrush-safe Faces), modifiers applied, the Blender meshes unchanged"""
    bl_idname = 'mch.export_mesh'
    bl_label = 'Export'
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default='*.obj;*.fbx', options={'HIDDEN'})
    scope: EnumProperty(name='Export', default='SELECTED', items=[
        ('SELECTED', 'Selected Objects', 'Only the selected meshes'),
        ('VISIBLE', 'Visible Objects', 'Every mesh you can see in the viewport (hidden ones stay out)')])
    file_format: EnumProperty(name='Format', items=[('OBJ', 'OBJ', 'Wavefront OBJ (ZBrush, most programs)'),
                                                    ('FBX', 'FBX', 'Autodesk FBX')], default='OBJ')
    apply_modifiers: BoolProperty(name='Apply Modifiers', default=True)
    split_ngons: BoolProperty(name='ZBrush-safe Faces', default=True,
                              description='Split faces with more than 4 corners into clean triangles (quads stay)')
    scale: FloatProperty(name='Scale', default=1.0, min=0.0001, soft_max=1000.0)
    quad_mesh: BoolProperty(name='Quad Mesh', default=False,
                            description='0.24.76 Every exported object rebuilt as quads first (Fix Mesh, then Quad '
                                        'Remesh keeping its hard edges) - the Blender meshes stay as they are')
    quad_size: FloatProperty(name='Quad Size', default=1.0, min=0.1, max=10.0, subtype='PERCENTAGE', precision=2,
                             description='How far apart the quads are, in % of the size of everything exported (the '
                                         'same size on every part: a small screw gets few quads)')
    client_look: BoolProperty(name='Client Look', default=False,
                              description='Also give the hard edges a narrow bevel + Subdivide, baked into the mesh: '
                                          'it looks smooth with crisp edges in any program (more faces)')
    client_subdiv: IntProperty(name='Subdivide', default=1, min=0, max=2,
                               description='Client Look: Subdivide levels baked in (each level = 4x the faces)')

    @classmethod
    def poll(cls, context):
        return bool(export_objects(context, 'VISIBLE'))

    def draw(self, context):
        lay = self.layout
        lay.prop(self, 'scope')
        lay.prop(self, 'file_format')
        lay.prop(self, 'apply_modifiers')
        lay.prop(self, 'split_ngons')
        lay.prop(self, 'scale')
        box = lay.box()
        box.prop(self, 'quad_mesh')
        if self.quad_mesh:
            box.prop(self, 'quad_size')
            box.prop(self, 'client_look')
            if self.client_look:
                box.prop(self, 'client_subdiv')
            box.label(text='About 1-30 s per object', icon='TIME')

    def invoke(self, context, event):
        if not export_objects(context, 'SELECTED'):
            self.scope = 'VISIBLE'                     # nothing selected: offer the visible meshes
        name = context.active_object.name if context.active_object is not None else 'mecha_export'
        if not self.filepath:
            self.filepath = _safe(name) + '.' + self.file_format.lower()
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        path = Path(bpy.path.abspath(self.filepath))
        ext = '.' + self.file_format.lower()
        if path.suffix.lower() != ext:
            path = path.with_suffix(ext)
        obs = export_objects(context, self.scope)
        if not obs:
            self.report({'WARNING'}, 'Export: no mesh to export (' + ('nothing selected' if self.scope == 'SELECTED'
                                                                      else 'nothing visible') + ')')
            return {'CANCELLED'}
        selected, active = list(context.selected_objects), context.view_layer.objects.active
        temps, split, renamed, notes = [], 0, [], []
        quad = export_size(obs) * self.quad_size / 100.0 if self.quad_mesh else 0.0
        t0 = time.time()
        wm = context.window_manager
        wm.progress_begin(0, len(obs))
        try:
            for i, ob in enumerate(obs):
                if self.split_ngons:
                    src = ob.evaluated_get(context.evaluated_depsgraph_get()) if self.apply_modifiers else ob
                    split += ngon_count(src.data)
                tmp = export_copy(context, ob, self.apply_modifiers, self.split_ngons and not self.quad_mesh)
                if quad > 0.0:
                    try:
                        note = quad_copy(context, tmp, quad, self.client_look, self.client_subdiv)
                    except (RuntimeError, ValueError, MemoryError) as ex:
                        note = str(ex).splitlines()[0][:80] if str(ex) else type(ex).__name__
                    if note:
                        notes.append(f'{ob.name}: {note}')
                wm.progress_update(i + 1)
                name = ob.name                             # the file gets the real names
                ob.name = name + '__mch_export'
                renamed.append((ob, name))
                tmp.name = name
                temps.append(tmp)
            for o in context.selected_objects:
                o.select_set(False)
            for t in temps:
                t.select_set(True)
            context.view_layer.objects.active = temps[0] if temps else None
            path.parent.mkdir(parents=True, exist_ok=True)
            if self.file_format == 'OBJ':
                bpy.ops.wm.obj_export(filepath=str(path), export_selected_objects=True, apply_modifiers=False,
                                      export_materials=True, export_uv=True, export_normals=True,
                                      export_triangulated_mesh=False, global_scale=self.scale)
            else:
                bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, use_mesh_modifiers=False,
                                         global_scale=self.scale, object_types={'MESH'})
        except (RuntimeError, AttributeError, TypeError) as ex:
            self.report({'ERROR'}, f'Export failed: {ex}')
            return {'CANCELLED'}
        finally:
            wm.progress_end()
            for t in temps:
                me = t.data
                bpy.data.objects.remove(t, do_unlink=True)
                if me.users == 0:
                    bpy.data.meshes.remove(me)
            for ob, name in renamed:
                ob.name = name
            _restore_selection(context, selected, active)
        if not path.is_file():
            self.report({'ERROR'}, 'Export produced no file')
            return {'CANCELLED'}
        msg = f'Exported {len(obs)} mesh(es) to {path}' + (f' ({split} n-gons split)' if split and not quad else '')
        if quad:
            msg += f' | Quad Mesh ({quad:.3g} apart{", Client Look" if self.client_look else ""}) in {time.time() - t0:.0f} s'
            if notes:
                msg += f' | {len(notes)} not as asked: ' + '; '.join(notes[:3])
        self.report({'WARNING'} if notes else {'INFO'}, msg)
        return {'FINISHED'}


CLASSES = (MCH_PG_ZBrush, MCH_OT_zbrush_send, MCH_OT_zbrush_import, MCH_OT_zbrush_open_folder, MCH_OT_export_mesh)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_zbrush = bpy.props.PointerProperty(type=MCH_PG_ZBrush)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_zbrush'):
        del bpy.types.Scene.mch_zbrush
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
