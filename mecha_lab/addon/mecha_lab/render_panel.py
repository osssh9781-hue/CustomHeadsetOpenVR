"""0.24.265 (user: "렌더 탭에다가 이거 넣어 줘" - Camera to View, Format, Color Management, the camera's Type / Focal
Length, Depth of Field) Blender's own render settings on the side panel's Render page: Camera, Depth of Field, Format,
Color Management.  Every row is the scene's / camera's own setting (nothing copied), so the Properties editor shows the
same values."""
from __future__ import annotations

import bpy


def _view3d(context):
    sp = getattr(context, 'space_data', None)
    if sp is not None and sp.type == 'VIEW_3D':
        return sp, getattr(context, 'region_data', None)
    for area in getattr(context.screen, 'areas', ()):
        if area.type == 'VIEW_3D':
            s = area.spaces.active
            return s, s.region_3d
    return None, None


def lock_on(context):
    s, _r = _view3d(context)
    return bool(s is not None and s.lock_camera)


class MCH_OT_render_lock_camera(bpy.types.Operator):
    """Camera to View: moving the view (orbit, pan, zoom) moves the camera while you look through it"""
    bl_idname = 'mch.render_lock_camera'
    bl_label = 'Camera to View'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        s, _r = _view3d(context)
        if s is None:
            return {'CANCELLED'}
        s.lock_camera = not s.lock_camera
        return {'FINISHED'}


class MCH_OT_render_add_camera(bpy.types.Operator):
    """A camera where the view is now, made the scene's camera"""
    bl_idname = 'mch.render_add_camera'
    bl_label = 'Add Camera from View'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        sc = context.scene
        cam = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
        sc.collection.objects.link(cam)
        _s, r3d = _view3d(context)
        if r3d is not None:
            cam.matrix_world = r3d.view_matrix.inverted()
        sc.camera = cam
        return {'FINISHED'}


class MCH_OT_render_look_through(bpy.types.Operator):
    """Look through the scene camera (again: back to the free view)"""
    bl_idname = 'mch.render_look_through'
    bl_label = 'Look Through Camera'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        s, r3d = _view3d(context)
        if r3d is None or context.scene.camera is None:
            return {'CANCELLED'}
        r3d.view_perspective = 'PERSP' if r3d.view_perspective == 'CAMERA' else 'CAMERA'
        return {'FINISHED'}


class MCH_OT_render_dof_focus(bpy.types.Operator):
    """Focus on Object: the camera keeps the active object sharp (again on the same object: back to Focus Distance)"""
    bl_idname = 'mch.render_dof_focus'
    bl_label = 'Focus on Active Object'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.camera is not None and context.scene.camera.type == 'CAMERA'

    def execute(self, context):
        dof = context.scene.camera.data.dof
        ob = context.active_object
        dof.focus_object = None if ob is None or dof.focus_object is ob or ob is context.scene.camera else ob
        return {'FINISHED'}


class MCH_OT_render_curves_reset(bpy.types.Operator):
    """Color Management Curves back to straight (Black Level 0, White Level 1)"""
    bl_idname = 'mch.render_curves_reset'
    bl_label = 'Reset Curves'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cm = context.scene.view_settings.curve_mapping
        cm.black_level = (0.0, 0.0, 0.0)
        cm.white_level = (1.0, 1.0, 1.0)
        for c in cm.curves:
            while len(c.points) > 2:
                c.points.remove(c.points[1])
            c.points[0].location = (0.0, 0.0)
            c.points[-1].location = (1.0, 1.0)
        cm.update()
        return {'FINISHED'}


def _t(title):
    """A section title in the UI language (a title with a summary beside it is not translated when drawn)."""
    from . import i18n
    return i18n.tr(title)


def sections(b, context, x, width):
    """Camera, Depth of Field, Format, Color Management on the Render page."""
    from . import mech_shader_ui as mu
    sc = context.scene
    cam = sc.camera if sc.camera is not None and sc.camera.type == 'CAMERA' else None

    def camera(sx, sw):
        mu.row(b, sx, sw, [mu._cell('seg', 'Camera to View', ('op', 'mch.render_lock_camera', {}),
                                    on=lock_on(context))])
        if cam is None:
            b.note(('note', 'No scene camera', True, None, None, None, True), sx, sw)
            mu.row(b, sx, sw, [mu.button('Add Camera from View', 'mch.render_add_camera')])
            return
        mu.row(b, sx, sw, [mu.button('Look Through Camera', 'mch.render_look_through')])
        d = cam.data
        mu.row(b, sx, sw, [mu.prop_cell(d, 'type', 'Type')])
        if d.type == 'ORTHO':
            mu.row(b, sx, sw, [mu.number(d, 'ortho_scale', 'Orthographic Scale')])
        elif d.type == 'PERSP':
            if d.lens_unit == 'FOV':
                mu.row(b, sx, sw, [mu.number(d, 'angle', 'Field of View')])
            else:
                mu.row(b, sx, sw, [mu.number(d, 'lens', 'Focal Length')])
            mu.row(b, sx, sw, [mu.prop_cell(d, 'lens_unit', 'Lens Unit')])
    mu.section(b, 'r_camera', _t('Camera'), x, width, camera, summary=cam.name if cam else '')
    from . import hdri_turn                     # 0.24.266 the HDRI turned / fixed to the camera
    hdri_turn.section(b, context, x, width)

    if cam is not None:
        dof = cam.data.dof

        def depth(sx, sw):
            mu.row(b, sx, sw, [mu.prop_cell(dof, 'use_dof', 'Depth of Field')])
            fo = dof.focus_object
            from . import i18n
            on_txt = f'초점: {fo.name}' if fo and i18n.lang() == 'KO' else f'Focus on Object: {fo.name}' if fo else ''
            mu.row(b, sx, sw, [mu._cell('seg', on_txt or 'Focus on Active Object',
                                        ('op', 'mch.render_dof_focus', {}), on=fo is not None)])
            if fo is None:
                mu.row(b, sx, sw, [mu.number(dof, 'focus_distance', 'Focus Distance')])
            mu.row(b, sx, sw, [mu.number(dof, 'aperture_fstop', 'F-Stop')])
            mu.row(b, sx, sw, [mu.number(dof, 'aperture_blades', 'Blades'),
                               mu.number(dof, 'aperture_rotation', 'Rotation')])
            mu.row(b, sx, sw, [mu.number(dof, 'aperture_ratio', 'Ratio')])
        mu.section(b, 'r_dof', _t('Depth of Field'), x, width, depth, start_folded=True,
                   summary=f'F {dof.aperture_fstop:g}' if dof.use_dof else '')

    r = sc.render

    def fmt(sx, sw):
        mu.row(b, sx, sw, [mu.number(r, 'resolution_x', 'Resolution X'), mu.number(r, 'resolution_y', 'Y')])
        mu.row(b, sx, sw, [mu.number(r, 'resolution_percentage', '%')])
        mu.row(b, sx, sw, [mu.number(r, 'pixel_aspect_x', 'Aspect X'), mu.number(r, 'pixel_aspect_y', 'Y')])
        mu.row(b, sx, sw, [mu.prop_cell(r, 'use_border', 'Render Region')])
    mu.section(b, 'r_format', _t('Format'), x, width, fmt,
               summary=f'{r.resolution_x} x {r.resolution_y}  {r.resolution_percentage}%')

    vs = sc.view_settings

    def colour(sx, sw):
        mu.row(b, sx, sw, [mu.prop_cell(sc.display_settings, 'display_device', 'Display')])
        mu.row(b, sx, sw, [mu.prop_cell(vs, 'view_transform', 'View')])
        mu.row(b, sx, sw, [mu.prop_cell(vs, 'look', 'Look')])
        mu.row(b, sx, sw, [mu.number(vs, 'exposure', 'Exposure'), mu.number(vs, 'gamma', 'Gamma')])
        mu.row(b, sx, sw, [mu.prop_cell(vs, 'use_curve_mapping', 'Curves')])
        if vs.use_curve_mapping:
            cm = vs.curve_mapping
            mu.row(b, sx, sw, [mu.swatch(cm, 'black_level', 'Black Level')])
            mu.row(b, sx, sw, [mu.swatch(cm, 'white_level', 'White Level')])
            mu.row(b, sx, sw, [mu.button('Reset Curves', 'mch.render_curves_reset')])
            b.note(('note', 'The curve itself: Properties > Render > Color Management', False, None, None, None,
                    True), sx, sw)
    mu.section(b, 'r_colour', _t('Color Management'), x, width, colour, start_folded=True, summary=vs.view_transform)


CLASSES = (MCH_OT_render_lock_camera, MCH_OT_render_add_camera, MCH_OT_render_look_through, MCH_OT_render_dof_focus,
           MCH_OT_render_curves_reset)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
