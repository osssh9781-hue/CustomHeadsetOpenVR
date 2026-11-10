"""0.24.129 (user: "아머 플레이트 하는데 계속 꺼지냐" + a traceback ending in UnicodeDecodeError: 'utf-8' codec can't decode
byte 0xb6) Names that are not UTF-8.

A data-block whose name holds bytes that are not UTF-8 (an object imported from a file written on a Korean Windows -
CP949 - with a Korean name, for example) makes ``id.name`` raise UnicodeDecodeError in Python.  The drawn UI reads
object names on every redraw, so one such object killed every tool invoke (the Layers panel listing a collection's
objects was the first reader).  Here: ``safe_name`` for the readers, and ``fix_bad_names`` that renames such blocks -
the raw bytes are read from the ID struct (its name field sits after five pointers; the offset is checked against a
block whose name reads fine before it is trusted) and decoded as CP949 first (the Korean name comes back), else the
undecodable bytes are dropped.  Runs when a file loads, when the add-on registers, and when the drawn UI meets the error."""
import ctypes

import bpy
from bpy.app.handlers import persistent

NAME_OFFSET = 40          # struct ID: void *next, *prev; ID *newid; Library *lib; AssetMetaData *asset_data; char name[66]
NAME_LEN = 66
KINDS = ('objects', 'meshes', 'collections', 'materials', 'images', 'curves', 'node_groups', 'armatures', 'textures',
         'actions', 'lights', 'cameras')
_OFFSET_OK = [None]
LAST = []                 # [(kind, new name), ...] of the last repair (the toast / the tests)


def safe_name(idblock, fallback='?'):
    """``idblock.name``, or ``fallback`` when the name is not UTF-8 (or the block is gone)."""
    try:
        return idblock.name
    except UnicodeDecodeError:
        return fallback
    except (AttributeError, ReferenceError, RuntimeError):
        return fallback


def offset_ok():
    """Whether NAME_OFFSET really is the name field in this Blender: checked once on a block whose name reads."""
    if _OFFSET_OK[0] is None:
        ok = False
        try:
            for attr in ('scenes', 'screens', 'objects', 'meshes', 'workspaces'):
                for idb in getattr(bpy.data, attr, ()):
                    try:
                        nm = idb.name
                    except UnicodeDecodeError:
                        continue
                    if not nm:
                        continue
                    raw = ctypes.string_at(idb.as_pointer() + NAME_OFFSET, NAME_LEN).split(b'\0')[0]
                    ok = raw[2:] == nm.encode('utf-8')
                    break
                else:
                    continue
                break
        except (AttributeError, ValueError, OSError, ReferenceError):
            ok = False
        _OFFSET_OK[0] = ok
    return _OFFSET_OK[0]


def raw_name(idblock):
    """The name's raw bytes (without the two-letter type code), or None when they cannot be read safely."""
    if not offset_ok():
        return None
    try:
        return ctypes.string_at(idblock.as_pointer() + NAME_OFFSET, NAME_LEN).split(b'\0')[0][2:]
    except (AttributeError, ValueError, OSError, ReferenceError):
        return None


def recover(raw, fallback):
    """A readable name for raw bytes: CP949 (Korean Windows) when it decodes, else the UTF-8 that is there."""
    if raw:
        try:
            s = raw.decode('cp949').strip()
            if s:
                return s
        except UnicodeDecodeError:
            pass
        s = raw.decode('utf-8', 'replace').replace('�', '').strip()
        if s:
            return s
    return fallback


def bad_blocks(data=None):
    """[(kind, block)] whose names do not read."""
    data = data or bpy.data
    out = []
    for attr in KINDS:
        coll = getattr(data, attr, None)
        if coll is None:
            continue
        try:
            blocks = list(coll)
        except (RuntimeError, ReferenceError):
            continue
        for idb in blocks:
            try:
                idb.name
            except UnicodeDecodeError:
                out.append((attr, idb))
            except (AttributeError, ReferenceError, RuntimeError):
                continue
    return out


def fix_bad_names(data=None, quiet=False):
    """Rename every data-block whose name is not UTF-8.  Returns [(kind, new name)]."""
    fixed = []
    for attr, idb in bad_blocks(data):
        new = recover(raw_name(idb), attr[:-1].capitalize() + '_fixed')
        try:
            idb.name = new
        except (AttributeError, RuntimeError, ReferenceError, TypeError):
            continue
        fixed.append((attr, safe_name(idb, new)))
    if fixed:
        LAST[:] = fixed
        msg = f'{len(fixed)} name(s) were not UTF-8 (a Korean Windows file?) and were repaired: ' + \
              ', '.join(n for _k, n in fixed[:6]) + (' ...' if len(fixed) > 6 else '')
        print('[Mecha Lab] ' + msg)
        if not quiet:
            try:
                from . import toast
                toast.show(msg, 'WARNING', 6.0)
            except (ImportError, AttributeError, RuntimeError):
                pass
    return fixed


def on_error(exc=None):
    """What a reader does when it meets UnicodeDecodeError: repair, say so, report whether anything changed."""
    try:
        return bool(fix_bad_names())
    except Exception as ex:          # noqa: BLE001 (never let the repair itself take the UI down)
        print('[Mecha Lab] name repair failed:', repr(ex), 'after', repr(exc))
        return False


@persistent
def _on_load(*_args):
    try:
        fix_bad_names()
    except Exception as ex:          # noqa: BLE001
        print('[Mecha Lab] name repair on load failed:', repr(ex))


def _later():
    try:
        fix_bad_names()
    except Exception as ex:          # noqa: BLE001
        print('[Mecha Lab] name repair failed:', repr(ex))
    return None


def register():
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)
    if bpy.app.background:
        _later()
    else:
        bpy.app.timers.register(_later, first_interval=1.0)


def unregister():
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    if bpy.app.timers.is_registered(_later):
        try:
            bpy.app.timers.unregister(_later)
        except ValueError:
            pass
