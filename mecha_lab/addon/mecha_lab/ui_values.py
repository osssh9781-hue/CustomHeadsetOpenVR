"""0.24.59 Values behind the drawn panels: one way to read / change / reset a setting, whether it is a normal
property (``data.prop``) or a Geometry Nodes input on a modifier (``data['Socket_2']``, written ``'["Socket_2"]'``
as the sidebar panels do)."""
from __future__ import annotations

from . import quick_hud


def is_id(prop):
    return prop.startswith('["') and prop.endswith('"]')


def _key(prop):
    return prop[2:-2]


def _ui(data, key):
    try:
        return data.id_properties_ui(key).as_dict()
    except (AttributeError, TypeError, KeyError):
        return {}


def get(data, prop):
    return data[_key(prop)] if is_id(prop) else getattr(data, prop)


def set(data, prop, value):      # noqa: A001 - the module's verb
    if is_id(prop):
        data[_key(prop)] = value
        owner = getattr(data, 'id_data', None)
        if owner is not None:
            owner.update_tag()
    else:
        setattr(data, prop, value)


def kind(data, prop):
    if is_id(prop):
        v = get(data, prop)
        return 'BOOLEAN' if isinstance(v, bool) else 'INT' if isinstance(v, int) else \
            'FLOAT' if isinstance(v, float) else 'OTHER'
    return data.bl_rna.properties[prop].type


def text(data, prop, label=None):
    """'Name  value' (name = ``label`` when given)."""
    if not is_id(prop):
        name, _s, val = quick_hud.value_text(data, prop).partition('  ')
        return f'{label if label else name}  {val}'
    v = get(data, prop)
    val = str(v) if isinstance(v, int) else f'{v:.3f}' if isinstance(v, float) else str(v)
    return f'{label if label else _key(prop)}  {val}'


def fraction(data, prop):
    if not is_id(prop):
        from .mecha_menu import _fraction
        return _fraction(data, prop)
    ui = _ui(data, _key(prop))
    lo, hi = ui.get('soft_min', ui.get('min', 0.0)), ui.get('soft_max', ui.get('max', 1.0))
    try:
        v = float(get(data, prop))
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, (v - lo) / (hi - lo))) if hi > lo else 0.0


def drag(data, prop, start, dx, fine=False, width=None):
    """The value after dragging ``dx`` px from ``start`` (the soft range over about 300 px, ints 1 per 8 px).
    0.24.59 ``width`` = the bar's width: its whole range over the bar, so the fill follows the mouse."""
    if not is_id(prop):
        return quick_hud.drag_value(data, prop, start, dx, fine, px=width)
    ui = _ui(data, _key(prop))
    lo, hi = ui.get('soft_min', ui.get('min', 0.0)), ui.get('soft_max', ui.get('max', 1.0))
    hard_lo, hard_hi = ui.get('min', -1e30), ui.get('max', 1e30)
    k = 0.1 if fine else 1.0
    px = width if width and width > 1 else 300.0
    if isinstance(start, int) and not isinstance(start, bool):
        per = max(4.0, px / (hi - lo)) if width and hi > lo else 8.0
        return int(max(hard_lo, min(hard_hi, start + round(dx * k / per))))
    span = (hi - lo) if hi > lo else 1.0
    return float(max(hard_lo, min(hard_hi, start + dx * k * span / px)))


def reset(data, prop):
    if not is_id(prop):
        quick_hud.reset(data, prop)
        return
    ui = _ui(data, _key(prop))
    if 'default' in ui:
        set(data, prop, ui['default'])


def toggle(data, prop):
    set(data, prop, not bool(get(data, prop)))
