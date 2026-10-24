"""0.23.6: skins after the references - plump round crocodile scales (big clusters + small ones,
fine grain), bearded-dragon pebbles with scattered spikes, new Croc Back (rows of keeled scutes)."""
import math
import sys

_src = open(__file__.replace('test_v0236.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
import numpy as np

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
from mecha_lab import cloth_wrinkle as cw, last_used
last_used.forget('creature')
check('six skins, Croc Back is Skin 6', cw.SKIN_IDS[-1] == 'CROC_BACK' and cw.CREATURE['CROC_BACK']['Skin'] == 6 and
      next(x for x in cw.INPUTS if x[0] == 'Skin')[4] == 6)
src = open(cw.__file__).read()
check('scales built round (dome from the scale centre + narrow groove), spikes, keel',
      'def pillow' in src and 'dome' in src and 'spike' in src and 'keel' in src)
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
S.mch_settings.mch_active_tool = 'WRINKLE'
S.mch_wrinkle.creature = True
res = {}
for k, skin in enumerate(('CROC', 'DRAGON', 'CROC_BACK')):
    b = cube('B%d' % k, 4.0, loc=(6.0 * k, 0, 0))
    VIEW[0] = cg.OrthoProjector(Quaternion(), center=Vector((6.0 * k, 0, 0)))
    S.mch_wrinkle.skin = skin
    r, m = lasso([(300, 350), (700, 350), (700, 650), (300, 650)])
    o = C.active_object
    dg = C.evaluated_depsgraph_get()
    z = np.array([v.co.z for v in o.evaluated_get(dg).data.vertices])
    res[skin] = (r == {'FINISHED'} and cw.is_creature(o) and o.get('mch_creature') == skin, z)
check('crocodile / dragon / croc back plates made', all(v[0] for v in res.values()))
check('each is displaced', all(np.ptp(v[1]) > 1e-3 for v in res.values()), {k: round(float(np.ptp(v[1])), 4) for k, v in res.items()})


def tail(z):
    """how far the highest points stick out above the typical surface (spikes -> long tail)"""
    return (z.max() - np.percentile(z, 50)) / max(np.percentile(z, 90) - np.percentile(z, 50), 1e-9)


check('dragon spikes stick out far above the pebbles (more than the croc scales)',
      tail(res['DRAGON'][1]) > tail(res['CROC'][1]) * 1.3, (round(tail(res['DRAGON'][1]), 2), round(tail(res['CROC'][1]), 2)))
S.mch_wrinkle.creature = False
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
