"""0.24.73 Work budgets: how big a result may get before Blender runs out of memory - checked before the work starts
(a step that runs out of memory takes Blender down with it, unsaved work included).

``faces_fit(n)``: ``n`` more faces fit - under the hard cap and within half of the memory free right now.
"""
from __future__ import annotations

import sys

BYTES_PER_FACE = 400            # a finished face in Blender: mesh + evaluated copy + undo + drawing (generous)
HARD_FACES = 20_000_000         # never more than this in one result, whatever the memory says
SHARE = 0.5                     # a result may use at most this share of the free memory


def available_memory():
    """Bytes of memory free now, or None when the system does not say."""
    try:
        if sys.platform == 'win32':
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                            ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                            ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                            ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                            ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
            m = MemoryStatus()
            m.dwLength = ctypes.sizeof(MemoryStatus)
            k = ctypes.WinDLL('kernel32')
            k.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(MemoryStatus)]
            k.GlobalMemoryStatusEx.restype = ctypes.c_int
            return int(m.ullAvailPhys) if k.GlobalMemoryStatusEx(ctypes.byref(m)) else None
        if sys.platform.startswith('linux'):
            with open('/proc/meminfo', encoding='ascii') as f:
                for line in f:
                    if line.startswith('MemAvailable:'):
                        return int(line.split()[1]) * 1024
    except (OSError, ValueError, AttributeError):
        return None
    return None


def faces_fit(faces, per_face=BYTES_PER_FACE):
    """(ok, reason): a result of ``faces`` faces fits.  The reason says why not (for the message)."""
    faces = int(faces)
    if faces > HARD_FACES:
        return False, f'{faces:,} polygons is more than the {HARD_FACES:,} limit'
    free = available_memory()
    if free is not None and faces * per_face > SHARE * free:
        return False, (f'{faces:,} polygons need about {faces * per_face / 2 ** 30:.1f} GB, only '
                       f'{free / 2 ** 30:.1f} GB is free')
    return True, ''


def max_faces(per_face=BYTES_PER_FACE):
    """The most faces one result may have now."""
    free = available_memory()
    if free is None:
        return HARD_FACES
    return max(0, min(HARD_FACES, int(SHARE * free / per_face)))
