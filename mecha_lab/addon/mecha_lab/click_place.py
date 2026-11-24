"""0.24.320 (user: "조인트랑 타이어 터빈 다 내가 클릭한곳에 생성되게 해줘"): a click summons the tool's part where you click.

Shared by the Joint Generator, Tire & Gear and Turbine tools.  A click on a mesh's surface puts it on the point hit; on
nothing, on the ground (Z 0), or - looking along the ground - at the 3D cursor's depth.  A click on one of the tool's
own parts selects it as before (the plain Select), so the sliders still change it; Shift+click is still Select toggle.
The part is summoned by the tool's own Summon operator with the 3D cursor moved there for the call and put back after,
so the result is exactly what the button makes."""
import bpy
from mathutils import Vector


def ray(context, xy):
    """(object hit or None, the point) under the region pixel ``xy``."""
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    o = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
    d = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
    hit, loc, _n, _i, hob, _m = context.scene.ray_cast(context.evaluated_depsgraph_get(), o, d)
    if hit and hob is not None:
        return bpy.data.objects.get(hob.name), Vector(loc)
    if abs(d.z) > 1e-4:
        t = -o.z / d.z
        if t > 0:
            return None, o + d * t
    return None, view3d_utils.region_2d_to_location_3d(region, rv3d, xy, context.scene.cursor.location)


def summon_at(context, where, call):
    """``call()`` (the Summon operator) with the 3D cursor on ``where``; the cursor put back after."""
    cur = context.scene.cursor
    keep = cur.location.copy()
    cur.location = where
    try:
        return call()
    finally:
        cur.location = keep


def click(op, context, event, is_part, call):
    """The click: select one of the tool's parts, else summon one there."""
    xy = (event.mouse_region_x, event.mouse_region_y)
    ob, where = ray(context, xy)
    if ob is not None and is_part(ob):
        return bpy.ops.view3d.select(location=xy)
    res = summon_at(context, where, call)
    return res if isinstance(res, set) else {'FINISHED'}


def keymap(idname):
    """The tool keymap: a click summons / selects, Shift+click is Select toggle (as before)."""
    return ((idname, {'type': 'LEFTMOUSE', 'value': 'CLICK'}, None),
            ('view3d.select', {'type': 'LEFTMOUSE', 'value': 'CLICK', 'shift': True},
             {'properties': [('toggle', True)]}))


def poll(context):
    return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'
