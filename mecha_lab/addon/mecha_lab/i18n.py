"""0.24.212 (user: "한글 번역 버전도 싹 다 만들고 그걸 한글 / 영어 에드온 설정에서 바꿀 수 있게 해 줘"): the Mecha Lab screen in
Korean.

The code keeps its English names (settings, buttons, titles - tests, saved presets and fold states go by them);
only what is DRAWN is looked up here: ``tr(s)`` gives the Korean text when Preferences > Korean is on and the table
(``i18n_ko.KO``) has the sentence, else ``s`` itself - so a sentence nobody translated yet simply stays English.

A sentence with numbers in it ("Stitches on the cloth (3)") is looked up with ``#`` in their place
("Stitches on the cloth (#)") and the numbers are put back in order.
"""
from __future__ import annotations

import os
import re

_NUM = re.compile(r'\d+(?:[.,]\d+)*')
_CACHE = {}
_TABLE = [None]          # (exact, lower-case) once loaded
_FORCE = [None]
_LANG = [None]           # 'KO' / 'EN' cached; ``reset()`` after the setting changed
MISSES = set()           # English sentences asked for and not in the table (tools_dev collects them)
LOG = bool(os.environ.get('MCH_I18N_LOG'))


class Raw(str):
    """A text that is never translated (an object's name, what the user typed)."""
    __slots__ = ()


def raw(s):
    return Raw(s) if s is not None else s


def reset():
    _LANG[0] = None
    _CACHE.clear()


def force(code=None):
    """'KO' / 'EN' whatever the setting says (None: the setting again) - for tests and tools."""
    _FORCE[0] = code
    reset()


def lang():
    """'KO' or 'EN': the MCH_LANG environment variable (tests), else Preferences > Korean."""
    if _FORCE[0] is not None:
        return _FORCE[0]
    if _LANG[0] is None:
        env = os.environ.get('MCH_LANG', '').upper()
        if env in {'KO', 'EN'}:
            _LANG[0] = env
        else:
            try:
                from . import workspace_ui
                _LANG[0] = 'KO' if workspace_ui.pref('korean', True) else 'EN'
            except Exception:                     # (no preferences yet: asked again next time)
                return 'EN'
    return _LANG[0]


def _table():
    if _TABLE[0] is None:
        try:
            from .i18n_ko import KO
        except Exception:
            KO = {}
        _TABLE[0] = (KO, {k.lower(): v for k, v in KO.items()})
    return _TABLE[0]


def _lookup(s):
    exact, lower = _table()
    hit = exact.get(s)
    if hit is None:
        hit = lower.get(s.lower())
    return hit


def _translate(s):
    core = s.strip()
    if not core:
        return s
    lead, tail = s[:len(s) - len(s.lstrip())], s[len(s.rstrip()):]
    hit = _lookup(core)
    if hit is None and _NUM.search(core):
        nums = _NUM.findall(core)
        tmpl = _lookup(_NUM.sub('#', core))
        if tmpl is not None and tmpl.count('#') == len(nums):
            it = iter(nums)
            hit = re.sub('#', lambda _m: next(it), tmpl)
    if hit is None:                               # "Name:" / "Name..." / "Name (on)" by its stem
        for end in (':', '...', '…', ' (on)', ' (Space)', ' (Enter)', ' (Esc)'):
            if core.endswith(end) and len(core) > len(end):
                stem = _lookup(core[:-len(end)].rstrip())
                if stem is not None:
                    hit = stem + (' (켜짐)' if end == ' (on)' else end)
                    break
    if hit is None:
        if LOG and any('a' <= c.lower() <= 'z' for c in core):
            MISSES.add(core)
        return s
    return lead + hit + tail


def tr(s):
    """``s`` as it is shown: Korean when the setting is on and the sentence is in the table."""
    if not isinstance(s, str) or isinstance(s, Raw) or not s or lang() != 'KO':
        return s
    hit = _CACHE.get(s)
    if hit is None:
        if len(_CACHE) > 20000:
            _CACHE.clear()
        hit = _CACHE[s] = _translate(s)
    return hit


def vlen(s):
    """How long ``s`` is on screen once translated, in Latin letters (a Hangul / CJK letter is about 1.75 wide) -
    for the places that estimate a width from the letter count."""
    t = tr(s) if isinstance(s, str) else ''
    wide = sum(1 for c in t if ord(c) >= 0x1100)
    return len(t) + 0.75 * wide
