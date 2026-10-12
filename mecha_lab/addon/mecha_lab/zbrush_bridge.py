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
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty
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
    keep_backup: BoolProperty(name='Keep Previous Mesh', default=True,
                              description='Keep the replaced mesh as <name>_preZBrush (fake user)')
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
            ob.select_set(True)
            context.view_layer.objects.active = ob
            bpy.ops.wm.obj_export(filepath=str(path), export_selected_objects=True,
                                  apply_modifiers=settings.apply_modifiers, export_materials=False,
                                  export_uv=True, export_normals=True, export_triangulated_mesh=False,
                                  forward_axis=settings.forward_axis, up_axis=settings.up_axis,
                                  global_scale=settings.scale)
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


CLASSES = (MCH_PG_ZBrush, MCH_OT_zbrush_send, MCH_OT_zbrush_import, MCH_OT_zbrush_open_folder)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_zbrush = bpy.props.PointerProperty(type=MCH_PG_ZBrush)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_zbrush'):
        del bpy.types.Scene.mch_zbrush
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
