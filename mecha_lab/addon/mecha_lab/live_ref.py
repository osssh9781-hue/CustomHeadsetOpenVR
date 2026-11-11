"""0.24.132 (user crash logs: EXCEPTION_ACCESS_VIOLATION inside Python while the drawn UI's memo was replaced, and
crashes on Ctrl+Z) References to Blender data that stay valid.

The drawn UI (top bar cells, side panel rows, HUD sliders) kept the ``bpy`` structs they show - ``scene.mch_brush``,
``ob.mch_cplate``, an object, a material - inside cached Python objects (``mecha_menu.Item``, ``panel_capture.Node``)
for up to half a second.  Undo (and Blender freeing a data-block the add-on removed) frees the memory such a struct
points at, and Blender only invalidates the one canonical Python wrapper of an ID - a PropertyGroup wrapper or a second
wrapper keeps pointing at freed memory.  Touching it (reading a value for the draw, writing on a click, or merely
releasing it while a dictionary is updated) is undefined behaviour: sometimes nothing, sometimes a crash.

``Ref`` remembers a struct as (data-block collection, name, RNA path) and looks it up again on every use, so nothing
in a cache ever points at memory Blender may have freed.  ``wrap`` turns a struct into a Ref (other values pass
through), ``resolve`` turns a Ref back into the live struct - or None when the data-block is gone."""
import bpy

_KINDS = (
    (bpy.types.Scene, 'scenes'), (bpy.types.Object, 'objects'), (bpy.types.WindowManager, 'window_managers'),
    (bpy.types.Material, 'materials'), (bpy.types.Brush, 'brushes'), (bpy.types.Image, 'images'),
    (bpy.types.Mesh, 'meshes'), (bpy.types.Collection, 'collections'), (bpy.types.Light, 'lights'),
    (bpy.types.World, 'worlds'), (bpy.types.Screen, 'screens'), (bpy.types.WorkSpace, 'workspaces'),
    (bpy.types.Text, 'texts'), (bpy.types.Curve, 'curves'), (bpy.types.Camera, 'cameras'),
    (bpy.types.Armature, 'armatures'), (bpy.types.NodeTree, 'node_groups'), (bpy.types.Action, 'actions'),
    (bpy.types.Texture, 'textures'), (bpy.types.ParticleSettings, 'particles'), (bpy.types.Palette, 'palettes'),
    (bpy.types.Key, 'shape_keys'), (bpy.types.Lattice, 'lattices'), (bpy.types.MetaBall, 'metaballs'),
    (bpy.types.Volume, 'volumes'), (bpy.types.PointCloud, 'pointclouds'), (bpy.types.Speaker, 'speakers'),
    (bpy.types.Sound, 'sounds'), (bpy.types.MovieClip, 'movieclips'), (bpy.types.LightProbe, 'lightprobes'),
    (bpy.types.Mask, 'masks'), (bpy.types.FreestyleLineStyle, 'linestyles'), (bpy.types.PaintCurve, 'paint_curves'),
    (bpy.types.CacheFile, 'cache_files'), (bpy.types.VectorFont, 'fonts'), (bpy.types.Library, 'libraries'),
)


def _coll_of(idb):
    for cls, coll in _KINDS:
        if isinstance(idb, cls):
            return coll
    return None


class Ref:
    """A Blender struct by (collection, data-block name, RNA path from the data-block), looked up on every use."""
    __slots__ = ('coll', 'name', 'path', 'lib')

    def __init__(self, coll, name, path='', lib=None):
        self.coll, self.name, self.path, self.lib = coll, name, path, lib

    def __repr__(self):
        return f'Ref({self.coll}[{self.name!r}]{"." + self.path if self.path else ""})'

    def __eq__(self, other):
        return isinstance(other, Ref) and (self.coll, self.name, self.path, self.lib) == (other.coll, other.name, other.path, other.lib)

    def __hash__(self):
        return hash((self.coll, self.name, self.path, self.lib))

    def get(self):
        """The live struct, or None when the data-block (or the path inside it) is gone."""
        coll = getattr(bpy.data, self.coll, None)
        if coll is None:
            return None
        try:
            idb = coll.get((self.name, self.lib)) if self.lib else coll.get(self.name)
        except (TypeError, KeyError, ReferenceError, RuntimeError):
            idb = None
        if idb is None:
            return None
        if not self.path:
            return idb
        try:
            return idb.path_resolve(self.path)
        except (ValueError, ReferenceError, TypeError, AttributeError, RuntimeError):
            return None


def wrap(data):
    """A Ref for a ``bpy`` struct that can be found again (a data-block or a path inside one); anything else as is."""
    if data is None or isinstance(data, Ref) or not isinstance(data, bpy.types.bpy_struct):
        return data
    try:
        idb = data.id_data
    except (AttributeError, ReferenceError, RuntimeError):
        return data
    if idb is None:
        return data
    coll = _coll_of(idb)
    if coll is None:
        return data
    try:
        path = '' if data == idb else data.path_from_id()
        lib = idb.library.filepath if idb.library is not None else None
        name = idb.name
    except (ValueError, ReferenceError, RuntimeError, AttributeError, TypeError, UnicodeDecodeError):
        return data
    return Ref(coll, name, path, lib)


def resolve(x):
    """The live struct for a Ref (None when gone); any other value as is."""
    return x.get() if isinstance(x, Ref) else x


def is_ref(x):
    return isinstance(x, Ref)


def deep_objects(coll):
    """0.24.132 Every object in ``coll`` and its child collections (each once, ``all_objects`` order: the collection's
    own objects, then each child's in turn).  Read from the collections' own object / child lists, NOT from
    ``Collection.all_objects`` - that is Blender's runtime object cache, and right after Ctrl+Z (plates removed or read
    back) it can still list objects that are gone: reading it in a redraw crashed Blender (reproduced: Layers panel)."""
    out, seen_o, seen_c = [], set(), set()
    if coll is None:
        return out
    stack = [coll]
    while stack:
        c = stack.pop()
        try:
            key = c.as_pointer()
        except (ReferenceError, AttributeError):
            continue
        if key in seen_c:
            continue
        seen_c.add(key)
        for o in c.objects:
            k = o.as_pointer()
            if k not in seen_o:
                seen_o.add(k)
                out.append(o)
        stack.extend(reversed(list(c.children)))
    return out
