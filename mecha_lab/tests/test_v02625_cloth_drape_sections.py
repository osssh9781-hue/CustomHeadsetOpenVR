"""0.24.213 (user: "오른쪽 창 설정이 정리가 안 되어 있잖아, 큰 구다리로 묶고 ... 구다리 제목은 좀 더 큰 폰트나 색으로" /
"기존에 있는 기능은 절대 변경 안 되어야 하고 이상은 없어야 해"): the Cloth Drape window in big titled sections - and
every control it had in 0.24.212 (data/cloth_drape_controls_0.24.212.json: each setting, button and note, with what
it does, its text and whether it can be pressed, in 14 states of the tool) is still there, the same."""
import collections
import json
import os

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import cloth_drape as cd, mesh_io as mio, panel_capture as pc, side_panel as sp  # noqa: E402

fresh(); mecha_lab.register()
C = bpy.context
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32)
body = C.active_object
co = mio.read_co(body.data)
att = body.data.attributes.new('.sculpt_mask', 'FLOAT', 'POINT')
att.data.foreach_set('value', (co[:, 1] < -0.5).astype(np.float32))
st = cd.settings(C)


def grab():
    root = pc.capture(cd.draw, C)
    assert 'error' not in root.opts, root.opts
    out = []
    for n in pc.walk(root):
        if n.kind in {'prop', 'prop_enum'}:
            d = n.data
            owner = type(d).__name__ if d is not None else '?'
            out.append(['prop', f'{owner}.{n.prop}', n.opts.get('text'), bool(n.state('enabled')), bool(n.state('active')),
                        {k: n.opts.get(k) for k in ('expand', 'slider', 'toggle', 'value') if n.opts.get(k) not in (None, False, -1)}])
        elif n.kind == 'op':
            out.append(['op', n.opts.get('idname'), n.opts.get('text'), bool(n.state('enabled')), bool(n.state('active')),
                        dict(sorted((n.opts.get('props') or {}).items())), bool(n.opts.get('depress'))])
        elif n.kind == 'label':
            out.append(['label', '', n.opts.get('text')])
    return out


states = {}
def snap(name): states[name] = grab()
snap('idle AREA')
for m in ('CAPE', 'CSIM', 'NECK', 'PANEL'):
    st.drape_mode = m; snap('idle ' + m)
st.drape_mode = 'CSIM'; st.cape_folds = 'ALONG'; snap('idle CSIM along')
st.drape_mode = 'NECK'; st.neck_style = [i.identifier for i in st.bl_rna.properties['neck_style'].enum_items][-1]; snap('idle NECK other style')
st.drape_mode = 'AREA'
st.use_lines = True; st.line_mode = 'STITCH'; snap('idle lines stitch')
st.line_mode = 'TUBES'; st.padding = True; st.trim = True; st.use_proxy = True; snap('idle padding trim proxy')
st.padding = False; st.trim = False; st.use_proxy = False
C.scene.mch_vacuum.gather = 'PICKED'; snap('idle vacuum gather'); C.scene.mch_vacuum.gather = 'NONE'
body.select_set(True); C.view_layer.objects.active = body
cd.perform_masked(C, body); snap('live mask waiting')
cd.SIM['running'] = True; snap('live running'); cd.SIM['running'] = False
cd.SIM['done'] = True; snap('live done'); cd.SIM['done'] = False
cd.cancel(C)
body.select_set(True); C.view_layer.objects.active = body
bpy.ops.mch.vacuum_mask(); snap('live vacuum'); cd.cancel(C)

HERE = os.path.dirname(os.path.abspath(__file__))
before = json.load(open(os.path.join(HERE, 'data', 'cloth_drape_controls_0.24.212.json')))
TITLES = ['Make', 'Fabric', 'Pins & Stitches', 'Detail & Thickness', 'Finish', 'Collision']
gone, new = [], collections.Counter()
for name, was in before.items():
    cb = collections.Counter(json.dumps(x, sort_keys=True) for x in was)
    ca = collections.Counter(json.dumps(json.loads(json.dumps(x)), sort_keys=True) for x in states[name])
    gone += [(name, k) for k in (cb - ca)]
    new.update(ca - cb)
n_before = sum(len(v) for v in before.values())
check(f'every control of 0.24.212 is still in the window, the same (its action, text, enabled) - {n_before:,} checked '
      f'over {len(before)} states of the tool, {len(gone)} gone', not gone and set(states) == set(before), gone[:5])
# 0.24.359 / 0.24.361 added on purpose: Check GPU Cloth, the GPU toggle, Reset Settings
ADDED = {('op', 'mch.gpu_cloth_check'), ('prop', 'MCH_PG_ClothDrape.gpu'), ('op', 'mch.cdrape_reset')}
added = {tuple(json.loads(k)[:2]) for k in new if json.loads(k)[0] != 'label'}
extra = sorted({json.loads(k)[2] for k in new if json.loads(k)[0] == 'label'})
check(f'the only new things are the six section titles ({extra}) and the GPU Cloth Check / GPU / Reset Settings '
      f'controls ({sorted(added)})', extra == sorted(TITLES) and added == ADDED)
st.drape_mode = 'AREA'
root = pc.capture(cd.draw, C)
boxes = [n for n in root.children if n.kind == 'box']
heads = [(b.children[0].opts.get('text'), b.children[0].opts.get('icon')) for b in boxes]
check(f'the window is {len(boxes)} big sections in this order, each title with its colour: {[h[0][:18] for h in heads]}',
      [h[0] for h in heads[:7]] == ['Cloth Drape'] + TITLES and heads[7][0].startswith('Vacuum Pack')
      and all(str(h[1]).startswith('STRIP_COLOR_0') for h in heads) and len({h[1] for h in heads}) == 8)


def where(prop):
    for b in boxes:
        if any(n.kind == 'prop' and n.prop == prop for n in pc.walk(b)):
            return b.children[0].opts.get('text')


got = {p: where(p) for p in ('drape_mode', 'mask_points', 'fabric', 'wrinkles', 'pin_rim', 'stitch_tight', 'spacing',
                             'thickness', 'frames', 'padding', 'trim', 'collide_with', 'use_proxy')}
check(f'... what belongs together is together: {got}',
      got == dict(drape_mode='Cloth Drape', mask_points='Make', fabric='Fabric', wrinkles='Fabric',
                  pin_rim='Pins & Stitches', stitch_tight='Pins & Stitches', spacing='Detail & Thickness',
                  thickness='Detail & Thickness', frames='Detail & Thickness', padding='Finish', trim='Finish',
                  collide_with='Collision', use_proxy='Collision'))
# the drawn window: big titles, a fold shows what the section is set to
sp.FOLDED.clear()
b = sp.Builder('CDRAPE', 10.0, 300.0, 1.0)
try:
    b.node(root, 10.0, 300.0)
    items = b.out
except Exception as ex:                                 # (the Builder's own signature: see below)
    items = None
    print('builder:', repr(ex))
if items is not None:
    big = [i for i in items if i.kind == 'shead' and str(i.icon).startswith('big:')]
    check(f'the Mecha window draws them as big coloured titles ({len(big)}: {[i.label for i in big][:4]} ..., '
          f'{big[0].h:.0f} px high, the small ones {sp.SECTION:.0f})',
          len(big) == 8 and all(abs(i.h - sp.BIG_SECTION) < 1e-6 for i in big) and sp.BIG_SECTION > sp.SECTION
          and all(i.action and i.action[0] == 'fold' for i in big))
    n_open = len(items)
    sp.toggle_fold(big[2].action[1], big[2].action[2])              # Fabric folded
    b2 = sp.Builder('CDRAPE', 10.0, 300.0, 1.0)
    b2.node(root, 10.0, 300.0)
    fab = next(i for i in b2.out if i.kind == 'shead' and i.label == 'FABRIC')
    note = str(fab.icon).partition('|')[2]
    check(f'a click folds a section; folded, its title shows what it is set to ("{note}") and its cells are away '
          f'({n_open} -> {len(b2.out)} cells)', len(b2.out) < n_open and 'Cotton' in note and not fab.on)
    sp.toggle_fold(big[2].action[1], big[2].action[2])
summary()
