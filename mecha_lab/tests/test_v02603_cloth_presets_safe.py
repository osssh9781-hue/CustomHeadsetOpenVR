"""0.24.183 (user: "내가 만든 클로스 프리셋 다 지웠어?"): the Cloth Plate presets you save (config/mecha_lab/
last_used.json - here a test folder, never the user's) are not lost:
* a second Blender open at the same time (its own copy read when it started) no longer writes them away when it
  saves its tool settings; a preset saved / deleted there is that one entry, the others as the file has them;
* the file is written whole to a new file first and swapped in; the version before kept as .bak; an unreadable
  file (Blender closed while writing) is not taken for an empty one: the backup is read, the bad file kept aside;
* presets saved in another Blender version (its own config folder) can be brought here from the menu;
* Delete asks first."""
import json
import os
import tempfile

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import cloth_wrinkle as cw, last_used as lu  # noqa: E402

fresh()
mecha_lab.register()
P = lu._path()
check('the test file is in the test config folder', P and 'mecha_lab_test_' in P, P)


def disk():
    with open(P, encoding='utf-8') as f:
        return json.load(f)


def reset_memory():
    lu._DATA = None
    lu._TOUCHED.clear()
    lu._ITEMS.clear()


VEST = {'Puff': 0.7, 'Type': 1}
COAT = {'Puff': 0.3, 'Type': 2}
lu.set_item(cw.PRESETS_KEY, 'Vest', VEST)
check('a preset is written right away', disk().get('cloth_presets', {}).get('Vest') == VEST)

# 1. another Blender wrote a preset after this one read the file; this one saves its tool settings -------------
d = disk()
d['cloth_presets']['Coat'] = COAT                    # (as the other Blender writes it)
with open(P, 'w', encoding='utf-8') as f:
    json.dump(d, f)
S = bpy.context.scene
S.mch_wrinkle.sections = 4
lu.store_scene(S)
lu.remember('wrinkle', 'Puff', 0.55)
lu.save()
d = disk()
check('saving the tool settings keeps a preset another Blender saved meanwhile',
      d['cloth_presets'].get('Coat') == COAT and d['cloth_presets'].get('Vest') == VEST, d.get('cloth_presets'))
check('... and writes this one\'s settings', d['_scene']['mch_wrinkle']['sections'] == 4 and
      d['wrinkle']['Puff'] == 0.55)
check('... and this Blender sees the other\'s preset now', 'Coat' in cw.user_presets())

# 2. a stale copy (read before both presets were saved) saving: the presets stay -------------------------------
lu._DATA = {'_scene': {}, 'cloth_presets': {}}       # (what a Blender started long ago has in memory)
lu.remember('plate', 'Width', 0.2)
lu.save()
check('a Blender with an old copy in memory does not write the presets away',
      set(disk()['cloth_presets']) == {'Vest', 'Coat'}, disk()['cloth_presets'])

# 3. deleting one: only that one ----------------------------------------------------------------------------------
d = disk()
d['cloth_presets']['Skirt'] = {'Puff': 0.1}          # (another Blender saved one more)
with open(P, 'w', encoding='utf-8') as f:
    json.dump(d, f)
bpy.ops.mch.wrinkle_preset_delete(name='Vest')
check('Delete takes only that preset away (one saved by another Blender meanwhile stays)',
      set(disk()['cloth_presets']) == {'Coat', 'Skirt'}, disk()['cloth_presets'])
check('Delete asks first (its own invoke: a confirm)', 'invoke' in cw.MCH_OT_wrinkle_preset_delete.__dict__)
check('no half-written file left', not os.path.exists(P + '.tmp'))
check('the version before is kept as .bak', os.path.exists(P + '.bak') and
      'cloth_presets' in json.load(open(P + '.bak', encoding='utf-8')))

# 4. the file unreadable (Blender closed while writing it): the backup is read, the bad file kept -------------------
lu.set_item(cw.PRESETS_KEY, 'Cape', {'Puff': 0.9})   # (the backup now has Coat / Skirt, the file Cape too)
with open(P, 'w', encoding='utf-8') as f:
    f.write('{"cloth_presets": {"Coat": {"Pu')       # (cut off half-way)
reset_memory()
got = cw.user_presets()
check('an unreadable file: the presets come from its backup, not an empty start',
      {'Coat', 'Skirt'} <= set(got), sorted(got))
check('... the unreadable file is kept aside', os.path.exists(P + '.unreadable') and
      open(P + '.unreadable', encoding='utf-8').read().startswith('{"cloth_presets": {"Coat"'))
lu.remember('wrinkle', 'Puff', 0.4)
lu.save()
check('... the next save writes a good file again with the presets', {'Coat', 'Skirt'} <= set(disk()['cloth_presets']))

# 5. no file, no backup: an empty start (nothing to keep) ------------------------------------------------------
# 6. presets of another Blender version ---------------------------------------------------------------------------
root = tempfile.mkdtemp(prefix='blender_versions_')
for ver, presets in (('5.0', {'Old Vest': {'Puff': 0.2}, 'Coat': COAT}), ('5.1', {'Coat': {'Puff': 0.8}}),
                     ('scripts', {'Nope': {}})):
    d_ = os.path.join(root, ver, 'config', 'mecha_lab')
    os.makedirs(d_)
    with open(os.path.join(d_, 'last_used.json'), 'w', encoding='utf-8') as f:
        json.dump({'cloth_presets': presets}, f)
lu.OTHER_ROOT[0] = root
other = lu.other_versions(cw.PRESETS_KEY)
check('the other Blender versions\' presets are found (not other folders)', set(other) == {'5.0', '5.1'}, other)
where = cw.presets_elsewhere()
check('the menu offers what is not here yet, newest version first', where == [('5.1', 1), ('5.0', 1)], where)
bpy.ops.mch.wrinkle_presets_import(version='5.0')
check('Bring from 5.0: its preset comes here (one already here unchanged is skipped)',
      cw.user_presets().get('Old Vest') == {'Puff': 0.2} and 'Coat (5.0)' not in cw.user_presets())
bpy.ops.mch.wrinkle_presets_import(version='5.1')
check('a preset of the same name but other values comes as "name (version)"',
      cw.user_presets().get('Coat (5.1)') == {'Puff': 0.8} and cw.user_presets().get('Coat') == COAT)
check('... both written to the file', {'Old Vest', 'Coat (5.1)'} <= set(disk()['cloth_presets']))
check('nothing left to bring', cw.presets_elsewhere() == [], cw.presets_elsewhere())
check('the other version\'s file is not changed', json.load(open(os.path.join(root, '5.0', 'config', 'mecha_lab',
                                                                  'last_used.json'), encoding='utf-8')) ==
      {'cloth_presets': {'Old Vest': {'Puff': 0.2}, 'Coat': COAT}})


# 7. the menu draws: presets, Save, Bring, Delete -------------------------------------------------------------------
class Rec:
    def __init__(self):
        self.ops = []

    def operator(self, idname, text='', icon='NONE', **_k):
        self.ops.append((idname, text))

        class P_:
            pass
        return P_()

    def label(self, **_k):
        pass

    def separator(self):
        pass

    def column(self):
        return self


root2 = tempfile.mkdtemp(prefix='blender_versions_')
d_ = os.path.join(root2, '4.5', 'config', 'mecha_lab')
os.makedirs(d_)
with open(os.path.join(d_, 'last_used.json'), 'w', encoding='utf-8') as f:
    json.dump({'cloth_presets': {'Hood': {'Puff': 0.5}}}, f)
lu.OTHER_ROOT[0] = root2
rec = Rec()
menu = type('M', (), {'layout': rec})()
cw.MCH_MT_wrinkle_presets.draw(menu, bpy.context)
texts = [t for _i, t in rec.ops]
check('the menu: the presets, Save, "Bring 1 from Blender 4.5", Delete',
      'Coat' in texts and 'Save Preset...' in texts and 'Bring 1 from Blender 4.5' in texts and 'Delete Coat' in texts,
      texts)
lu.OTHER_ROOT[0] = None

mecha_lab.unregister()
import sys  # noqa: E402
sys.exit(1 if summary() else 0)
