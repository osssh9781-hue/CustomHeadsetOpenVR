"""0.24.233 (user: "사용법들을 정리 … 툴 설명 펼치게 해서" / "검색도 할 수 있게"): the usage of each tool in the key
legend card (Korean / English), the card for click tools too, and the usage search - and every key / setting the
usage names is checked against the add-on (a sentence about a setting that is not there is caught here)."""
import re

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import usage_docs as ud, key_legend as kl, tool_state as ts, i18n  # noqa: E402
from mecha_lab import panel_capture as pc, ui_tool_settings as uts, top_bar as tb  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context
check(f'usage for {len(ud.DOCS)} tools, every one a real tool with what / how / keys / settings in Korean and English',
      len(ud.DOCS) >= 10 and all(t in ts.TOOL_BY_ID for t in ud.DOCS)
      and all(all(p in d for p in ('what', 'how', 'keys', 'opts')) for d in ud.DOCS.values())
      and all(len(d['what']) == 2 and all(len(x) == 2 for x in d['how']) and all(len(x) == 3 for x in d['keys'])
              and all(len(x) == 3 for x in d['opts']) for d in ud.DOCS.values()))
hangul = re.compile('[가-힣]')
check('the Korean lines are Korean, the English ones are not',
      all(hangul.search(d['what'][0]) and not hangul.search(d['what'][1]) and
          all(hangul.search(a) and not hangul.search(b) for a, b in d['how']) for d in ud.DOCS.values()))


def window_words(tid):
    """Every name the tool's window shows (settings, buttons, labels), the top bar's cells and section names."""
    dr = uts.DRAWERS.get(tid)
    out = set()
    if dr is not None:
        tree = pc.capture(lambda lay, ctx: dr(lay, ctx), C)
        for n in pc.walk(tree):
            if n.kind in ('prop', 'prop_enum'):
                try:
                    rna = n.data.bl_rna.properties[n.prop]
                    out.add(n.opts.get('text') or rna.name)
                    if rna.type == 'ENUM':
                        out |= {e.name for e in rna.enum_items}
                except (KeyError, AttributeError):
                    pass
            elif n.kind in ('op', 'label', 'menu') and n.opts.get('text'):
                out.add(n.opts['text'])
    for title, cells in tb.groups(C, tid) or []:
        out.add(title)
        out |= {c['label'] for c in cells}
    return ' | '.join(out).lower()           # (a section title may be in capitals)


missing = {}
for tid, d in ud.DOCS.items():
    words = window_words(tid)
    for name, _ko, _en in d['opts']:
        for part in re.split(r'\s*/\s*', name):
            if part and part.lower() not in words:
                missing.setdefault(tid, []).append(part)
check(f'every setting the usage names is in that tool\'s window or top bar (missing: {missing})', not missing)
for lang in ('KO', 'EN'):
    i18n.force(lang)
    rows = kl.card_rows('CUT', 1.0, False)
    heads = [r[2] for r in rows if r[0] == 'head']
    check(f'{lang}: the Cut card - title, then {heads}, every line no wider than the card allows',
          rows[0][0] == 'title' and len(heads) >= 5 and all(kl._width(r[2], 12) <= kl.TEXT_MAX + 1 for r in rows[1:]))
i18n.force('KO')
check('folded: the title only', len(kl.card_rows('SUBD', 1.0, True)) == 1)
check('a tool with no entry yet: its keys as before', kl.card_rows('WING', 1.0, False)[0][0] == 'title'
      and any(r[0] == 'kv' for r in kl.card_rows('WING', 1.0, False)))
ents = ud.search_entries(ts.TOOLS)
ids = [e[0] for e in ents]
check(f'search: {len(ents)} entries - every tool by name, every usage line in both languages, unique',
      len(set(ids)) == len(ids) and all(any(i == f'{t[0]}|0' for i in ids) for t in ts.TOOLS)
      and any('모서리' in e[1] for e in ents) and any('Crease' in e[1] for e in ents))
check('Ctrl+Shift+F and the card\'s Search open the search', hasattr(bpy.types, 'MCH_OT_usage_search')
      and any(k.idname == 'mch.usage_search' and k.ctrl and k.shift for _km, k in kl._keymaps))
i18n.force('EN')
summary()
