"""0.24.142 (user: "n 패널 상단에 배경 이미지랑 배경 컬러 설정하는 거 넣어 줘") The background settings - colour and
picture - in a panel of their own at the top of the sidebar's Mecha Lab tab: on / off + colour, Colour | Picture, the
current picture's preview with ◀ [the list] ▶, Choose Folder…, Fill / Fit, Brightness, Contrast, Colour Ramp,
Material Preview Too, Solid View Too.  The Mech Shader panel no longer draws it at its bottom."""
import inspect

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import backdrops as bd, bg_color as bgc, mech_shader as msh  # noqa: E402

fresh()
mecha_lab.register()
bpy.context.scene.mch_bg.method = 'WORLD'      # (0.24.148: Compositor is the default now; this file is the World way)
C = bpy.context
S = C.scene
st = S.mch_bg


class _Rec:
    def __init__(self, log):
        self.log = log

    def box(self):
        return self

    def row(self, **_kw):
        return self

    def column(self, **_kw):
        return self

    def label(self, text='', **_kw):
        self.log.append(('label', text))

    def prop(self, data, name, text=None, **_kw):
        self.log.append(('prop', name))

    def operator(self, idname, text='', **_kw):
        self.log.append(('op', idname, text))
        return type('OpProps', (), {})()

    def template_icon(self, icon_value=0, **_kw):
        self.log.append(('icon', icon_value))

    def template_color_ramp(self, data, prop, **_kw):
        self.log.append(('ramp', prop))


panels = [c for c in bpy.types.Panel.__subclasses__() if getattr(c, 'bl_category', '') == 'Mecha Lab'
          and getattr(c, 'bl_region_type', '') == 'UI']
pt = bpy.types.MCH_PT_background
others = [getattr(c, 'bl_order', 0) for c in panels if c is not pt]
check(f'a Background panel in the sidebar\'s Mecha Lab tab, ordered before the other {len(others)} Mecha Lab panels',
      pt.bl_category == 'Mecha Lab' and pt.bl_region_type == 'UI' and all(pt.bl_order < o for o in others),
      (pt.bl_order, sorted(others)[:5]))
check('the Mech Shader panel no longer draws the background at its bottom (no second copy)',
      'draw_background(' not in inspect.getsource(msh.draw))
# Colour
st.mode = 'COLOR'
rec = []
bgc.draw_panel(_Rec(rec), C)
check('Colour: the on / off button and the colour, Colour | Picture, Material Preview Too, Solid View Too - no picture '
      'rows', ('op', 'mch.bg_color', 'Background Colour') in rec and all(('prop', p) in rec for p in
      ('color', 'mode', 'material_too', 'solid_too')) and ('prop', 'image_pick') not in rec, rec)
# Picture: the list, the preview, the arrows
items = st.bl_rna.properties['image_pick'].enum_items if False else bgc._pick_items(st, C)
check(f'the picture list: every studio backdrop and folder picture ({len(bd.entries())})',
      [i[0] for i in items] == [e[0] for e in bd.entries()] and len(items) == len(bd.entries()))
st.image_pick = 'B:smoke_blue_land.jpg'
pic = S.world.node_tree.nodes.get(bgc.N_PIC) if S.world else None
check('picking from the list: that picture behind the model, the background on', bgc.on(S) and st.mode == 'IMAGE'
      and st.image == 'B:smoke_blue_land.jpg' and pic is not None and pic.image.filepath.endswith('smoke_blue_land.jpg'))
rec = []
bgc.draw_panel(_Rec(rec), C)
icons = [e[1] for e in rec if e[0] == 'icon']
icon_now = bgc.preview_icon(bgc.picture_path(S))
check('Picture: ◀ [list] ▶, Choose Folder…, Fill / Fit, Brightness, Contrast, Colour Ramp; the preview drawn when '
      'Blender gives its icon (with a window - none in background mode)',
      ('prop', 'image_pick') in rec and rec.count(('op', 'mch.bg_picture_step', '')) == 2
      and ('op', 'mch.mech_bg_folder', 'Choose Folder…') in rec
      and all(('prop', p) in rec for p in ('fit', 'bright', 'contrast', 'ramp'))
      and (icons == [icon_now] if icon_now else icons == []), (icon_now, icons, rec))
check('the preview: only the picture shown is loaded', len(bgc._PREV['coll']) == 1, len(bgc._PREV['coll']))
ids = [e[0] for e in bd.entries()]
i0 = ids.index(st.image)
r1 = bpy.ops.mch.bg_picture_step(step=1)
nxt = st.image
bpy.ops.mch.bg_picture_step(step=-1)
back = st.image
st.image = ids[0]
bpy.ops.mch.bg_picture_step(step=-1)
check('▶ the next picture, ◀ back, ◀ on the first wraps to the last', 'FINISHED' in r1 and nxt == ids[i0 + 1]
      and back == ids[i0] and st.image == ids[-1], (nxt, back, st.image))
st.ramp = True
rec = []
bgc.draw_panel(_Rec(rec), C)
check('Colour Ramp on: its colour ramp right in the panel', ('ramp', 'color_ramp') in rec)
st.ramp = False
bgc.remove(S)
summary()
