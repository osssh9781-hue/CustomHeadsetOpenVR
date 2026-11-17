"""0.24.195 GoZ (experimental) - user: "GoZ 로 하면 안 되는 거야?" / "그렇게 하자".

ZBrush's own link between programs, next to the OBJ bridge (``zbrush_bridge``), which stays as it is:

* **Send (GoZ)**: every selected mesh is written as ``<name>.GoZ`` into ZBrush's shared GoZ project folder
  (``<Public>/Pixologic/GoZProjects/Default``), the list of them into ``GoZBrush/GoZ_ObjectList.txt``, then ZBrush is
  started with a small ZScript (``MechaLab_GoZ_Import``) that reads the listed files with Tool > Import - the way
  the GoB add-on does it (0.24.196; ZBrush's old helper GoZBrushFromApp closed ZBrush 2026).
* **Import (GoZ)**: the files ZBrush listed in ``GoZ_ObjectList.txt`` (its GoZ button writes them) are read back;
  an object sent from here gets its mesh replaced (found by name), anything else becomes a new object.  **Auto**
  watches the list and imports when ZBrush writes it.
* **Set Up GoZ for Blender**: the two small text files ZBrush needs to show Blender among its GoZ programs
  (``GoZApps/Blender/GoZ_Info.txt`` and ``GoZ_Config.txt``).  Written only when the button is pressed.

The .GoZ layout is not published by Maxon; it is the one the open GoB add-on documents by reading and writing it
(a 32-byte heading, then blocks of: tag, byte length, count, data).  NOT RUN AGAINST A REAL ZBRUSH here (no ZBrush
on the build machine): the files are checked by writing and reading them back only.
"""
from __future__ import annotations

import json
import os
import re
import struct
import subprocess
import time
from pathlib import Path

import bpy
import numpy as np
from bpy.props import BoolProperty, StringProperty
from mathutils import Matrix

MAGIC = b'GoZb 1.0 ZBrush GoZ Binary' + b'.' * 6            # 32 bytes
T_OBJECT, T_NAME, T_SUBDIV = 0x00000001, 0x00001389, 0x0000138A
T_VERTS, T_FACES, T_UVS, T_COLOUR, T_MASK, T_GROUPS = 0x00002711, 0x00004E21, 0x000061A9, 0x000088B9, 0x00007532, 0x00009C41
NO_CORNER = 0xFFFFFFFF                                      # a triangle's fourth corner
# Blender (x, y, z) -> ZBrush (x, -z, y), and back (a turn, not a mirror: the faces keep their side)
TO_ZB = np.array(((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0)))
FROM_ZB = TO_ZB.T
MANIFEST = 'mecha_goz_manifest.json'
ID_KEY = 'mch_zb_id'
GROUP_ATTR = 'mch_polygroup'
WATCH = {'on': False, 'mtime': 0.0}
INFO_TXT = ('NAME\t\t\t=\t"Blender"\nGOZ_VERSION\t\t=\t1\nEXTENSION\t\t=\t".GoZ"\n'
            'TAMPLATE\t\t=\t"GoZ Complete Binary.GoZ"\n\n'
            'EXPORT_FLIP_Y\t\t\t=\tFALSE\nEXPORT_FLIP_Z\t\t\t=\tFALSE\nIMPORT_FLIP_Y\t\t\t=\tFALSE\n'
            'IMPORT_FLIP_Z\t\t\t=\tFALSE\n\nNORMAL_MAP_FLIP_VERT\t\t=\tFALSE\t\t\t\n'
            'TEXTURE_MAP_FLIP_VERT\t\t=\tFALSE\nDISPLACEMENT_MAP_FLIP_VERT\t=\tFALSE\n')


# ---- the file -------------------------------------------------------------------------------------------------------
def _block(tag, count, payload):
    return struct.pack('<IIQ', tag, len(payload) + 16, count) + payload


def write_goz(path, name, verts, faces, groups=None, colours=None):
    """One mesh as a .GoZ file.  ``verts`` (N, 3) in ZBrush's axes; ``faces`` (F, 4) uint32 with ``NO_CORNER`` as a
    triangle's fourth corner; ``groups`` (F,) polygroup numbers; ``colours`` (N, 3) 0..255 red, green, blue."""
    verts = np.ascontiguousarray(verts, '<f4').reshape(-1, 3)
    faces = np.ascontiguousarray(faces, '<u4').reshape(-1, 4)
    nm = name.encode('ascii', 'replace')
    with open(path, 'wb') as f:
        f.write(MAGIC)
        f.write(_block(T_OBJECT, 1, b'GoZMesh_' + nm))
        f.write(_block(T_NAME, 1, struct.pack('<I', 0)))
        f.write(_block(T_VERTS, len(verts), verts.tobytes()))
        f.write(_block(T_FACES, len(faces), faces.tobytes()))
        if colours is not None and len(colours) == len(verts):
            c = np.zeros((len(verts), 4), np.uint8)             # (stored blue, green, red, then a spare byte)
            c[:, :3] = np.asarray(colours, np.uint8).reshape(-1, 3)[:, ::-1]
            f.write(_block(T_COLOUR, len(verts), c.tobytes()))
        if groups is not None and len(groups) == len(faces):
            f.write(_block(T_GROUPS, len(faces), np.ascontiguousarray(groups, '<u2').tobytes()))
        f.write(b'\0' * 16)


def read_goz(path):
    """A .GoZ file -> dict(name, verts (N, 3), faces (F, 4), groups or None, colours (N, 3) or None).  Blocks it
    does not know are stepped over by their length; a cut-off file gives what was whole."""
    out = dict(name=Path(path).stem, verts=np.zeros((0, 3), np.float32), faces=np.zeros((0, 4), np.uint32),
               groups=None, colours=None)
    with open(path, 'rb') as f:
        data = f.read()
    if not data.startswith(b'GoZb'):
        raise ValueError(f'{Path(path).name}: not a GoZ file')
    pos = 32
    while pos + 16 <= len(data):
        tag, length, count = struct.unpack_from('<IIQ', data, pos)
        if tag == 0 or length < 16:
            break
        body = data[pos + 16:pos + length]
        pos += length
        if tag == T_OBJECT and body.startswith(b'GoZMesh_'):
            out['name'] = body[8:].split(b'\0')[0].decode('utf-8', 'replace') or out['name']
        elif tag == T_VERTS:
            n = min(int(count), len(body) // 12)
            out['verts'] = np.frombuffer(body, '<f4', n * 3).reshape(-1, 3).copy()
        elif tag == T_FACES:
            n = min(int(count), len(body) // 16)
            out['faces'] = np.frombuffer(body, '<u4', n * 4).reshape(-1, 4).copy()
        elif tag == T_COLOUR:
            n = len(body) // 4
            out['colours'] = np.frombuffer(body, np.uint8, n * 4).reshape(-1, 4)[:, 2::-1].copy()
        elif tag == T_GROUPS:
            out['groups'] = np.frombuffer(body, '<u2', len(body) // 2).copy()
    return out


# ---- where ZBrush keeps GoZ -----------------------------------------------------------------------------------------
class MCH_PG_GoZ(bpy.types.PropertyGroup):
    root: StringProperty(name='GoZ Folder', subtype='DIR_PATH', default='',
                         description='ZBrush\'s shared GoZ folder (empty = the usual place: Public\\Pixologic on '
                                     'Windows, /Users/Shared/Pixologic on a Mac)')
    apply_modifiers: BoolProperty(name='Apply Modifiers', default=True)
    tell: BoolProperty(name='Open in ZBrush', default=True,
                       description='After writing the files, start ZBrush with the import script (off: only the '
                                   'files are written - load them yourself with ZScript > Load or Tool > Import)')
    keep_backup: BoolProperty(name='Keep the Old Mesh', default=True,
                              description='The mesh an import replaces is kept as <name>_preZBrush')


def default_roots():
    pub = os.environ.get('PUBLIC') or r'C:\Users\Public'
    return [os.path.join(pub, 'Pixologic'), os.path.join(pub, 'Maxon'),
            '/Users/Shared/Pixologic', '/Users/Shared/Maxon']


def goz_root(settings=None):
    """ZBrush's shared GoZ folder ('' when this computer has none)."""
    typed = bpy.path.abspath(settings.root).strip() if settings is not None and settings.root else ''
    if typed:
        return typed if os.path.isdir(typed) else ''
    return next((r for r in default_roots() if os.path.isdir(os.path.join(r, 'GoZBrush'))), '')


def project_dir(root):
    return os.path.join(root, 'GoZProjects', 'Default')


def list_path(root):
    return os.path.join(root, 'GoZBrush', 'GoZ_ObjectList.txt')


def registered(root):
    return bool(root) and os.path.isfile(os.path.join(root, 'GoZApps', 'Blender', 'GoZ_Info.txt'))


def register_app(root):
    """Blender written into ZBrush's list of GoZ programs (two text files in GoZApps/Blender)."""
    folder = os.path.join(root, 'GoZApps', 'Blender')
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, 'GoZ_Info.txt'), 'w', newline='\n') as f:
        f.write(INFO_TXT)
    exe = bpy.app.binary_path.replace('\\', '/')
    with open(os.path.join(folder, 'GoZ_Config.txt'), 'w', newline='\n') as f:
        f.write(f'PATH = "{exe}"')
    return folder


def _manifest(root):
    try:
        with open(os.path.join(project_dir(root), MANIFEST), encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _safe(name):
    return re.sub(r'[^A-Za-z0-9_]', '_', name)[:60] or 'Mesh'


# ---- Blender -> ZBrush ----------------------------------------------------------------------------------------------
def mesh_arrays(me, matrix):
    """(verts in ZBrush's axes, faces (F, 4), groups, colours or None) of a mesh with no face above four corners."""
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get('co', co)
    m = np.array(matrix, np.float64)
    world = co.reshape(-1, 3).astype(np.float64) @ m[:3, :3].T + m[:3, 3]
    verts = world @ TO_ZB.T
    nf = len(me.polygons)
    start, tot = np.empty(nf, np.int32), np.empty(nf, np.int32)
    me.polygons.foreach_get('loop_start', start)
    me.polygons.foreach_get('loop_total', tot)
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get('vertex_index', lv)
    faces = np.full((nf, 4), NO_CORNER, np.uint32)
    for c in range(4):
        ok = tot > c
        faces[ok, c] = lv[start[ok] + c]
    mat = np.empty(nf, np.int32)
    me.polygons.foreach_get('material_index', mat)
    att = me.attributes.get(GROUP_ATTR)
    if att is not None and att.domain == 'FACE' and len(att.data) == nf:      # (the groups ZBrush gave before)
        g = np.empty(nf, np.int32)
        att.data.foreach_get('value', g)
        groups = g.astype(np.uint16)
    else:
        groups = (mat + 1).astype(np.uint16)
    colours = None
    col = me.color_attributes.active_color
    if col is not None and col.domain == 'POINT' and len(col.data) == n:
        c = np.empty(n * 4, np.float32)
        col.data.foreach_get('color_srgb', c)
        colours = np.clip(c.reshape(-1, 4)[:, :3] * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return verts.astype(np.float32), faces, groups, colours


def send(context, objects, settings):
    """The meshes written for ZBrush; returns (folder, names sent, points)."""
    from . import zbrush_bridge as zb
    root = goz_root(settings)
    if not root:
        raise RuntimeError('ZBrush\'s GoZ folder was not found (Public\\Pixologic\\GoZBrush): start ZBrush once, or '
                           'set GoZ Folder')
    folder = project_dir(root)
    os.makedirs(folder, exist_ok=True)
    man = _manifest(root)
    selected, active = list(context.selected_objects), context.view_layer.objects.active
    sent, points, lines = [], 0, []
    try:
        for ob in objects:
            tmp = zb.export_copy(context, ob, settings.apply_modifiers, split_ngons=True)
            try:
                me = tmp.data
                if not len(me.polygons):
                    continue
                zid = ob.get(ID_KEY) or __import__('uuid').uuid4().hex[:12]
                ob[ID_KEY] = zid
                name = ob.get(NAME_KEY)
                taken = {str(o[NAME_KEY]).lower() for o in bpy.data.objects if o.get(NAME_KEY) and o != ob}
                if not name or str(name).lower() in taken:
                    name, i = _safe(ob.name), 1
                    while name.lower() in taken:
                        name, i = f'{_safe(ob.name)}_{i}', i + 1
                verts, faces, groups, colours = mesh_arrays(me, ob.matrix_world)
                base = os.path.join(folder, name)
                write_goz(base + '.GoZ', name, verts, faces, groups, colours)
                with open(base + '.ztn', 'w') as f:
                    f.write(base)
                ob[NAME_KEY] = name
                man[name] = dict(id=zid, object=ob.name, matrix=[list(r) for r in ob.matrix_world], sent=time.time())
                lines.append(base)
                sent.append(ob.name)
                points += len(verts)
            finally:
                me = tmp.data
                bpy.data.objects.remove(tmp, do_unlink=True)
                if me.users == 0:
                    bpy.data.meshes.remove(me)
    finally:
        zb._restore_selection(context, selected, active)
    if lines:
        os.makedirs(os.path.dirname(list_path(root)), exist_ok=True)
        with open(list_path(root), 'w') as f:
            f.write('\n'.join(lines) + '\n')
        with open(os.path.join(folder, MANIFEST), 'w', encoding='utf-8') as f:
            json.dump(man, f, indent=1)
        try:
            WATCH['mtime'] = os.path.getmtime(list_path(root))      # (our own list is not ZBrush's answer)
        except OSError:
            pass
    return folder, sent, points


SCRIPT_NAME = 'MechaLab_GoZ_Import'
ZSCRIPT = """//Mecha Lab - GoZ import (0.24.196): every mesh named in GoZ_ObjectList.txt is read with Tool > Import.
//The first one becomes a new tool, the others its subtools.
[VarDef,listFile,"@LIST@"]
[VarDef,lineStr,""]
[VarDef,objPath,""]
[VarDef,offset,0]
[VarDef,bytes,0]
[VarDef,count,0]
[If,[FileExists,listFile],
	[MemCreateFromFile,MCH_GoZ_List,listFile]
	[Loop,999,
		[VarSet,bytes,[MemReadString,MCH_GoZ_List,lineStr,offset,1]]
		[If,[StrLength,lineStr] > 0,
			[VarSet,objPath,[StrMerge,lineStr,".GoZ"]]
			[If,[FileExists,objPath],
				[If,count == 0,
					[IKeyPress,13,[IPress,Tool:Plane3D]]
					[FileNameSetNext,objPath]
					[IPress,Tool:Import]
					[If,[IGet,Transform: Edit] == 0,
						[CanvasClick,10,10,10,20]
						[IPress,Transform: Edit]
					]
				,
					[IPress,Tool:SubTool:Insert]
					[IPress,PopUp:Cube3D]
					[FileNameSetNext,objPath]
					[IPress,Tool:Import]
				]
				[VarInc,count]
			]
		]
		[VarSet,offset,offset+bytes]
		[If,(bytes <= 0) || (offset >= [MemGetSize,MCH_GoZ_List]),
			[LoopExit]
		]
	]
	[MemDelete,MCH_GoZ_List]
	[If,count > 0,
		[IPress,Transform: Fit]
	]
,
	[Note,"Mecha Lab GoZ: GoZ_ObjectList.txt was not found",,3]
]
"""


def write_script(root):
    """The small ZScript that makes ZBrush read the listed files (its text; ZBrush makes the .zsc from it the first
    time it loads it).  Returns the path of the text file."""
    folder = project_dir(root)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, SCRIPT_NAME + '.txt')
    text = ZSCRIPT.replace('@LIST@', list_path(root).replace('\\', '/'))
    try:
        with open(path, encoding='utf-8') as f:
            same = f.read() == text
    except OSError:
        same = False
    if not same:
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        try:                                     # (the compiled one belongs to the old text)
            os.remove(os.path.join(folder, SCRIPT_NAME + '.zsc'))
        except OSError:
            pass
    return path


def call_zbrush(root):
    """ZBrush started with the import script (0.24.196: the way the GoB add-on does it - ZBrush's old helper
    GoZBrushFromApp closed ZBrush 2026 on the user's computer).  Returns a note for the report."""
    from . import zbrush_bridge as zb
    try:
        txt = write_script(root)
    except OSError as ex:
        return f'could not write the import script: {ex}'
    zsc = txt[:-4] + '.zsc'
    script = zsc if os.path.isfile(zsc) else txt
    exe = zb.zbrush_path(bpy.context.scene.mch_zbrush)
    how = f'in ZBrush: ZScript > Load > {txt}'
    if not exe:
        return 'ZBrush was not found - ' + how
    try:
        subprocess.Popen(['open', '-a', exe, script] if exe.endswith('.app') else [exe, script],
                         cwd=os.path.dirname(exe))
    except OSError as ex:
        return f'could not start ZBrush ({ex}) - ' + how
    return 'ZBrush asked to import them (if nothing comes in: ' + how + ')'


# ---- ZBrush -> Blender ----------------------------------------------------------------------------------------------
def build_mesh(name, d):
    """A Blender mesh (world space, Blender's axes) from what ``read_goz`` gave."""
    verts = d['verts'].astype(np.float64) @ FROM_ZB.T
    faces = d['faces']
    tri = faces[:, 3] == NO_CORNER
    tot = np.where(tri, 3, 4).astype(np.int32)
    start = np.concatenate(([0], np.cumsum(tot)[:-1])).astype(np.int32)
    corners = faces[~np.isin(np.arange(faces.size).reshape(faces.shape), np.nonzero(tri)[0][:, None] * 4 + 3)]
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set('co', verts.astype(np.float32).ravel())
    me.loops.add(len(corners))
    me.loops.foreach_set('vertex_index', corners.astype(np.int32))
    me.polygons.add(len(faces))
    me.polygons.foreach_set('loop_start', start)
    me.polygons.foreach_set('loop_total', tot)
    me.polygons.foreach_set('use_smooth', np.ones(len(faces), bool))
    me.update(calc_edges=True)
    me.validate()
    if d['groups'] is not None and len(d['groups']) == len(me.polygons):
        att = me.attributes.new(GROUP_ATTR, 'INT', 'FACE')
        att.data.foreach_set('value', d['groups'].astype(np.int32))
    if d['colours'] is not None and len(d['colours']) == len(me.vertices):
        col = me.color_attributes.new('Polypaint', 'BYTE_COLOR', 'POINT')
        rgba = np.ones((len(me.vertices), 4), np.float32)
        rgba[:, :3] = d['colours'].astype(np.float32) / 255.0
        col.data.foreach_set('color_srgb', rgba.ravel())
        me.color_attributes.active_color = col
    return me


def keep_materials(old, me):
    """0.24.197 (user: "갔다 오니까 재질 다 사라졌어"): the material slots of the mesh being replaced, and each face's
    material - straight across when the faces are the same ones (same count), else from the old face nearest to each
    new face (ZBrush changed the mesh: DynaMesh, ZRemesher, Divide).  Both meshes in the object's own space."""
    for mat in old.materials:
        me.materials.append(mat)
    n_old, n_new = len(old.polygons), len(me.polygons)
    if not n_old or not n_new or len(old.materials) < 2:
        return 'slots'
    idx_old = np.empty(n_old, np.int32)
    old.polygons.foreach_get('material_index', idx_old)
    if not idx_old.any():
        return 'slots'
    if n_old == n_new and len(old.vertices) == len(me.vertices):
        me.polygons.foreach_set('material_index', idx_old)
        me.update()
        return 'same faces'
    from mathutils.kdtree import KDTree
    c_old = np.empty(n_old * 3, np.float32)
    old.polygons.foreach_get('center', c_old)
    c_old = c_old.reshape(-1, 3)
    c_new = np.empty(n_new * 3, np.float32)
    me.polygons.foreach_get('center', c_new)
    c_new = c_new.reshape(-1, 3)
    kd = KDTree(n_old)
    for i, c in enumerate(c_old):
        kd.insert(c, i)
    kd.balance()
    out = np.fromiter((idx_old[kd.find(c)[1]] for c in c_new), np.int32, n_new)
    me.polygons.foreach_set('material_index', out)
    me.update()
    return 'nearest faces'


NAME_KEY = 'mch_goz_name'


def match_object(d, path, man=None, single=False):
    """The object a returned file belongs to (0.24.197, user: "보냈던 파일도 있고 가져온 것도 있어서 두 개씩 생겨, 이름이
    같으니까 같은 거끼리는 없어지는 게 낫다"): the name it was sent under is kept ON the object (ZBrush empties its
    project folder, so a list kept there was gone when the mesh came back), compared without letter case; then the
    object's own name; then a sent name the returned one begins with ("Cube1" for "Cube")."""
    names = {d['name'].lower(), Path(path).stem.lower()}
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    sent = [o for o in meshes if o.get(NAME_KEY)]
    for o in sent:
        if str(o[NAME_KEY]).lower() in names:
            return o
    for o in meshes:
        if o.name.lower() in names or _safe(o.name).lower() in names:
            return o
    for o in sorted(sent, key=lambda o: -len(str(o[NAME_KEY]))):
        if any(n.startswith(str(o[NAME_KEY]).lower()) for n in names):
            return o
    return None


def listed(root):
    """The .GoZ files the list names (ZBrush's GoZ button, or our own Send)."""
    try:
        with open(list_path(root)) as f:
            rows = [r.strip() for r in f if r.strip()]
    except OSError:
        return []
    return [r if r.lower().endswith('.goz') else r + '.GoZ' for r in rows]


def import_listed(context, settings):
    """Every listed file read in.  Returns (updated, created, errors)."""
    root = goz_root(settings)
    if not root:
        raise RuntimeError('ZBrush\'s GoZ folder was not found')
    man = _manifest(root)
    done, created, errors = [], [], []
    rows = listed(root)
    for path in rows:
        try:
            d = read_goz(path)
            if not len(d['verts']) or not len(d['faces']):
                raise ValueError(f'{Path(path).name}: no mesh in it')
            me = build_mesh(d['name'], d)
        except (OSError, ValueError) as ex:
            errors.append(str(ex))
            continue
        ob = match_object(d, path, man, len(rows) == 1)
        if ob is None:
            ob = bpy.data.objects.new(d['name'], me)
            context.scene.collection.objects.link(ob)
            created.append(ob.name)
            continue
        me.transform(Matrix(ob.matrix_world).inverted_safe())
        old = ob.data
        keep_materials(old, me)
        nm = old.name
        ob.data = me
        if old.users > 0:
            me.name = nm + '_ZBrush'
        elif settings.keep_backup:
            old.name = nm + '_preZBrush'
            old.use_fake_user = True
            me.name = nm
        else:
            bpy.data.meshes.remove(old)
            me.name = nm
        done.append(ob.name)
    return done, created, errors


def _watch():
    if not WATCH['on']:
        return None
    try:
        st = bpy.context.scene.mch_goz
        root = goz_root(st)
        mt = os.path.getmtime(list_path(root)) if root else 0.0
        if mt > WATCH['mtime'] + 1e-6:
            WATCH['mtime'] = mt
            if bpy.context.mode == 'OBJECT':
                done, created, _err = import_listed(bpy.context, st)
                print(f'Mecha Lab GoZ: updated {done}, new {created}')
    except Exception as ex:                      # (a timer must not die on a half-written file)
        print('Mecha Lab GoZ watch:', ex)
    return 1.0


# ---- buttons --------------------------------------------------------------------------------------------------------
class MCH_OT_goz_setup(bpy.types.Operator):
    """Write the two small files that make ZBrush list Blender as a GoZ program (in ZBrush's shared GoZApps folder; nothing else is changed). Restart ZBrush afterwards"""
    bl_idname = 'mch.goz_setup'
    bl_label = 'Set Up GoZ for Blender'
    bl_options = {'REGISTER'}

    def execute(self, context):
        root = goz_root(context.scene.mch_goz)
        if not root:
            self.report({'ERROR'}, 'ZBrush\'s GoZ folder was not found (Public\\Pixologic\\GoZBrush): start ZBrush '
                                   'once, or set GoZ Folder')
            return {'CANCELLED'}
        try:
            folder = register_app(root)
        except OSError as ex:
            self.report({'ERROR'}, f'Could not write there: {ex}')
            return {'CANCELLED'}
        self.report({'INFO'}, f'Blender written into {folder} - restart ZBrush, then pick Blender in Preferences > GoZ')
        return {'FINISHED'}


class MCH_OT_goz_send(bpy.types.Operator):
    """GoZ (experimental): the selected meshes straight into ZBrush - no Import / Export clicks there. ZBrush must be open"""
    bl_idname = 'mch.goz_send'
    bl_label = 'Send (GoZ)'
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        st = context.scene.mch_goz
        try:
            folder, sent, points = send(context, [o for o in context.selected_objects if o.type == 'MESH'], st)
        except (RuntimeError, OSError) as ex:
            self.report({'ERROR'}, f'GoZ send failed: {ex}')
            return {'CANCELLED'}
        if not sent:
            self.report({'WARNING'}, 'Nothing with faces was selected')
            return {'CANCELLED'}
        self.report({'INFO'}, f'GoZ: {len(sent)} object(s), {points:,} points -> {folder} | '
                    + (call_zbrush(goz_root(st)) if st.tell else 'files written only (Open in ZBrush is off)'))
        return {'FINISHED'}


class MCH_OT_goz_import(bpy.types.Operator):
    """GoZ (experimental): read what ZBrush sent with its GoZ button (a sent object gets its new mesh, anything else comes in as a new object)"""
    bl_idname = 'mch.goz_import'
    bl_label = 'Import (GoZ)'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT' and context.active_object is not None:
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            done, created, errors = import_listed(context, context.scene.mch_goz)
        except RuntimeError as ex:
            self.report({'ERROR'}, str(ex))
            return {'CANCELLED'}
        msg = f'GoZ: updated {len(done)}, new {len(created)}'
        self.report({'WARNING'} if errors else {'INFO'}, msg + (' | ' + '; '.join(errors[:3]) if errors else ''))
        return {'FINISHED'}


class MCH_OT_goz_watch(bpy.types.Operator):
    """Auto: import by itself whenever ZBrush's GoZ button sends something (until Blender is closed or this is turned off)"""
    bl_idname = 'mch.goz_watch'
    bl_label = 'Auto Import (GoZ)'
    bl_options = {'REGISTER'}

    def execute(self, context):
        WATCH['on'] = not WATCH['on']
        if WATCH['on']:
            root = goz_root(context.scene.mch_goz)
            try:
                WATCH['mtime'] = os.path.getmtime(list_path(root)) if root else 0.0
            except OSError:
                WATCH['mtime'] = 0.0
            if not bpy.app.timers.is_registered(_watch):
                bpy.app.timers.register(_watch, first_interval=1.0)
        self.report({'INFO'}, 'GoZ auto import ' + ('on' if WATCH['on'] else 'off'))
        return {'FINISHED'}


def draw(layout, context):
    st = context.scene.mch_goz
    root = goz_root(st)
    box = layout.box()
    box.label(text='GoZ (experimental - not run against a real ZBrush yet)', icon='EXPERIMENTAL')
    row = box.row(align=True)
    row.scale_y = 1.3
    row.operator('mch.goz_send', icon='EXPORT')
    row.operator('mch.goz_import', icon='IMPORT')
    row.operator('mch.goz_watch', text='Auto', icon='FILE_REFRESH', depress=WATCH['on'])
    box.operator('mch.goz_setup', icon='PREFERENCES',
                 text='Set Up GoZ for Blender' + (' (done)' if registered(root) else ''))
    box.prop(st, 'root')
    box.label(text=('GoZ folder: ' + root) if root else 'GoZ folder: not found (start ZBrush once, or set it above)',
              icon='CHECKMARK' if root else 'ERROR')
    row = box.row(align=True)
    row.prop(st, 'apply_modifiers', toggle=True)
    row.prop(st, 'tell', toggle=True)
    row.prop(st, 'keep_backup', toggle=True)


CLASSES = (MCH_PG_GoZ, MCH_OT_goz_setup, MCH_OT_goz_send, MCH_OT_goz_import, MCH_OT_goz_watch)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_goz = bpy.props.PointerProperty(type=MCH_PG_GoZ)


def unregister():
    WATCH['on'] = False
    if bpy.app.timers.is_registered(_watch):
        bpy.app.timers.unregister(_watch)
    if hasattr(bpy.types.Scene, 'mch_goz'):
        del bpy.types.Scene.mch_goz
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
