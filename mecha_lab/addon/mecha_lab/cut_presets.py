"""Mecha Lab PNG-to-vector cut presets.

Raster brightness / alpha is converted into contour loops once on import.
The JSON file holds vector loops; Blender's 2D curve fill/extrude creates a
real cutting solid, not a voxel grid.  Multi-island masks and holes supported.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import uuid
from collections import defaultdict
from pathlib import Path

import bpy
import bmesh
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty
from bpy_extras.io_utils import ImportHelper
from bpy_extras import view3d_utils
from mathutils import Vector, Matrix
from mathutils.geometry import intersect_line_plane

try:
    import bpy.utils.previews as previews
except ImportError:
    previews = None

_preview_collection = None
_items_cache = []


def preset_folder():
    return Path(bpy.utils.user_resource('CONFIG', path='mecha_lab/cut_shapes', create=True))


def _signed_area(loop):
    return 0.5 * sum(p[0]*q[1]-q[0]*p[1] for p,q in zip(loop,loop[1:]+loop[:1]))


def _perpendicular(p,a,b):
    dx,dy=b[0]-a[0], b[1]-a[1]
    d2=dx*dx+dy*dy
    if d2 < 1e-12:
        return math.dist(p,a)
    t=max(0.0,min(1.0,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/d2))
    return math.dist(p,(a[0]+t*dx,a[1]+t*dy))


def _rdp(points,epsilon):
    if len(points) < 3: return points[:]
    # Iterative implementation avoids recursion limit for dense masks.
    keep={0,len(points)-1}
    stack=[(0,len(points)-1)]
    while stack:
        a,b=stack.pop()
        if b-a<2:continue
        md, idx=-1.0,None
        for i in range(a+1,b):
            d=_perpendicular(points[i],points[a],points[b])
            if d>md:md,idx=d,i
        if md>epsilon:
            keep.add(idx);stack.extend([(a,idx),(idx,b)])
    return [points[i] for i in sorted(keep)]


def simplify_closed(loop, tolerance):
    """Preserve winding and avoid collapsing small islands/holes."""
    if len(loop)<=4 or tolerance<=0:return loop[:]
    n=len(loop)
    anchor=min(range(n),key=lambda i:(loop[i][0],loop[i][1]))
    far=max(range(n),key=lambda i:math.dist(loop[i],loop[anchor]))
    if anchor>far:anchor,far=far,anchor
    a=_rdp(loop[anchor:far+1],tolerance)
    b=_rdp(loop[far:]+loop[:anchor+1],tolerance)
    result=a[:-1]+b[:-1]
    if len(result)<3 or _signed_area(result)*_signed_area(loop)<=0:
        return loop[:]
    return result


def trace_mask(mask, width, height):
    """CCW foreground borders and CW holes (pixel-space, origin bottom-left)."""
    edges=defaultdict(list)
    for y in range(height):
        row=y*width
        for x in range(width):
            if not mask[row+x]:continue
            if y==0 or not mask[(y-1)*width+x]: edges[(x,y)].append((x+1,y))
            if x==width-1 or not mask[row+x+1]: edges[(x+1,y)].append((x+1,y+1))
            if y==height-1 or not mask[(y+1)*width+x]: edges[(x+1,y+1)].append((x,y+1))
            if x==0 or not mask[row+x-1]: edges[(x,y+1)].append((x,y))
    total=sum(map(len,edges.values()))
    if total>250000:
        raise ValueError('Mask boundary is too complex; lower resolution or remove image noise')
    loops=[]
    while edges:
        start=next(iter(edges))
        cur=start; prev=None; points=[]
        for _ in range(total+1):
            points.append(cur)
            options=edges.get(cur)
            if not options: raise ValueError('Open boundary in imported PNG')
            if prev is not None and len(options)>1:
                vx=cur[0]-prev[0];vy=cur[1]-prev[1]
                def turn(p):
                    wx=p[0]-cur[0];wy=p[1]-cur[1]
                    return math.atan2(vx*wy-vy*wx,vx*wx+vy*wy)
                nxt=max(options,key=turn)
            else: nxt=options[0]
            options.remove(nxt)
            if not options:del edges[cur]
            prev,cur=cur,nxt
            if cur==start:break
        else: raise ValueError('PNG boundary tracing exceeded expected length')
        if len(points)>=4 and abs(_signed_area(points))>=1:
            loops.append(points)
        if len(loops)>2000:
            raise ValueError('Too many independent contours; remove mask noise')
    return loops


def vectorize_mask(mask,w,h,tolerance=0.8):
    loops=trace_mask(mask,w,h)
    out=[]
    if not loops:raise ValueError('No filled area was found in the PNG')
    extent=max(w,h)
    for loop in loops:
        loop=simplify_closed(loop,tolerance)
        if len(loop)<3:continue
        # Center in a unit square while retaining original aspect ratio.
        pts=[[(x-w/2)/extent,(y-h/2)/extent] for x,y in loop]
        out.append(pts)
    if not out:raise ValueError('PNG contours are too small or invalid')
    if sum(len(x) for x in out)>12000:
        raise ValueError('Contour has too many points; increase Simplify or reduce PNG detail')
    return out


def _load_pixels(filepath, mode, threshold, invert, max_pixels=512):
    image=bpy.data.images.load(filepath, check_existing=False)
    try:
        if not image.has_data: image.reload()
        w,h=image.size
        if w<2 or h<2:raise ValueError('PNG must be at least 2x2 pixels')
        if max(w,h)>max_pixels:
            ratio=max_pixels/max(w,h)
            image.scale(max(2,round(w*ratio)),max(2,round(h*ratio)))
            w,h=image.size
        import numpy as np
        a=np.empty(w*h*4,dtype=np.float32)
        image.pixels.foreach_get(a)
        px=a.reshape(h,w,4)
        if mode=='ALPHA': values=px[:,:,3]
        else:values=(0.2126*px[:,:,0]+0.7152*px[:,:,1]+0.0722*px[:,:,2])
        if invert:binary=values<=threshold
        else:binary=values>=threshold
        # For brightness-based mode transparent background must always be blank.
        if mode=='LUMINANCE':binary &= (px[:,:,3]>0.01)
        return binary.ravel().tolist(),w,h
    finally:
        bpy.data.images.remove(image,do_unlink=True)


def import_png(filepath,name,mode='LUMINANCE',threshold=0.5,invert=False,simplify=0.8):
    mask,w,h=_load_pixels(filepath,mode,threshold,invert)
    paths=vectorize_mask(mask,w,h,simplify)
    folder=preset_folder()
    uid=uuid.uuid4().hex[:16]
    basename=re.sub(r'[^A-Za-z0-9_-]+','_',name).strip('_')[:50] or 'Shape'
    stem=basename+'_'+uid
    src=folder/(stem+'.png')
    shutil.copy2(filepath,src)
    record={'schema':1,'name':name,'source':src.name,'mode':mode,
            'size':[w,h],'loops':paths}
    out=folder/(stem+'.json')
    try:
        out.write_text(json.dumps(record,separators=(',',':')),encoding='utf-8')
    except Exception:
        src.unlink(missing_ok=True)
        raise
    _refresh_previews()
    return out


def _refresh_previews():
    global _preview_collection
    if previews is None:return
    if _preview_collection is not None:
        previews.remove(_preview_collection)
    _preview_collection=previews.new()


def preset_items(self,context):
    global _preview_collection, _items_cache
    if previews and _preview_collection is None:_preview_collection=previews.new()
    records=sorted(preset_folder().glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    items=[]
    for i,f in enumerate(records):
        try:
            d=json.loads(f.read_text(encoding='utf-8'))
            name=d.get('name',f.stem)
            thumb=preset_folder()/d.get('source','')
            icon=0
            if _preview_collection and thumb.is_file():
                key=str(thumb)
                if key not in _preview_collection:
                    _preview_collection.load(key,key,'IMAGE')
                icon=_preview_collection[key].icon_id
            items.append((f.stem,name,str(f),icon,i))
        except (OSError,ValueError,KeyError):continue
    if not items:items=[('NONE','No Cut Presets','Use Import PNG to add one',0,0)]
    _items_cache=items
    return _items_cache


def read_current(context):
    stem=context.scene.mch_png_preset
    path=preset_folder()/(stem+'.json')
    if not path.is_file():raise ValueError('Select an imported PNG preset')
    d=json.loads(path.read_text(encoding='utf-8'))
    if d.get('schema')!=1:raise ValueError('Unknown preset data version')
    return d


def build_prism(context, loops, name, width, depth, plane_matrix):
    """Use Blender's 2D curve fill (preserves holes) then weld duplicated cap vertices."""
    cu=bpy.data.curves.new(name+'_Contours','CURVE')
    cu.dimensions='2D';cu.fill_mode='BOTH'
    cu.resolution_u=16
    cu.extrude=depth/2
    for ring in loops:
        if len(ring)<3:continue
        sp=cu.splines.new('POLY')
        sp.points.add(len(ring)-1)
        for bp,(x,y) in zip(sp.points,ring):
            bp.co=(float(x)*width,float(y)*width,0,1)
        sp.use_cyclic_u=True
    obj=bpy.data.objects.new(name,cu)
    context.collection.objects.link(obj)
    obj.matrix_world=plane_matrix.copy()
    temp=None
    try:
        dg=context.evaluated_depsgraph_get()
        evaluated=obj.evaluated_get(dg)
        temp=bpy.data.meshes.new_from_object(evaluated,preserve_all_data_layers=False,depsgraph=dg)
        bm=bmesh.new()
        try:
            bm.from_mesh(temp)
            bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=max(1e-7,width*1e-6))
            if not bm.faces or not all(e.is_manifold for e in bm.edges):
                raise ValueError('Raster silhouette created non-manifold cutter; simplify the image')
            bm.normal_update()
            mesh=bpy.data.meshes.new(name+'_Mesh')
            bm.to_mesh(mesh);mesh.update()
        finally:
            bm.free()
        out=bpy.data.objects.new(name,mesh)
        context.collection.objects.link(out)
        out.matrix_world=plane_matrix.copy()
        return out
    finally:
        if temp is not None:bpy.data.meshes.remove(temp)
        bpy.data.objects.remove(obj,do_unlink=True)
        if cu.users==0:bpy.data.curves.remove(cu)


def apply_stamp(context, target, loops, position, rot, width, depth, auto_apply):
    if target.type!='MESH':raise ValueError('Choose a target mesh')
    if width<=0 or depth<=0:raise ValueError('Size and depth must be positive')
    view_normal=rot @ Vector((0,0,1))
    # Allow a small portion above the surface to avoid coplanar Boolean caps.
    center=position-view_normal*(depth*0.5-max(0.0005,depth*0.02))
    plane=Matrix.Translation(center)@rot.to_matrix().to_4x4()
    cutter=build_prism(context,loops,'MCH_PNG_Stamp',width,depth,plane)
    mod=None
    try:
        mod=target.modifiers.new('MCH_PNG_Cut','BOOLEAN')
        mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
        if hasattr(mod,'use_self'):mod.use_self=True
        if auto_apply:
            # Evaluate before applying so a failed Boolean leaves the original unchanged.
            dg=context.evaluated_depsgraph_get()
            candidate=bpy.data.meshes.new_from_object(target.evaluated_get(dg),depsgraph=dg)
            try:
                if len(candidate.polygons)==0: raise ValueError('Boolean would erase the entire target')
                bm=bmesh.new()
                try:
                    bm.from_mesh(candidate)
                    if not all(e.is_manifold for e in bm.edges):
                        original=bmesh.new()
                        try:
                            original.from_mesh(target.data)
                            if all(e.is_manifold for e in original.edges):
                                raise ValueError('Boolean result is non-manifold; lower simplify or change stamp size')
                        finally: original.free()
                finally:bm.free()
            finally:bpy.data.meshes.remove(candidate)
            for selected in context.selected_objects:selected.select_set(False)
            target.hide_set(False)
            target.select_set(True);context.view_layer.objects.active=target
            bpy.ops.object.modifier_apply(modifier=mod.name)
            bpy.data.objects.remove(cutter,do_unlink=True)
        else:
            cutter.display_type='WIRE'
            cutter.hide_render=True
            cutter.hide_set(True)
            cutter['mch_png_cutter']=True
            target['mch_png_last_cutter']=cutter.name
        return True
    except Exception:
        if mod and target.modifiers.get(mod.name):target.modifiers.remove(mod)
        if cutter.name in bpy.data.objects:bpy.data.objects.remove(cutter,do_unlink=True)
        raise


class MCH_OT_import_cut_png(bpy.types.Operator,ImportHelper):
    bl_idname='mch.import_cut_png'
    bl_label='Import PNG Cut Shape'
    bl_description='Convert a black-white PNG into reusable vector cutting contours'
    bl_options={'REGISTER'}
    filename_ext='.png'
    filter_glob:StringProperty(default='*.png',options={'HIDDEN'})
    shape_name:StringProperty(name='Preset Name',default='')
    mode:EnumProperty(name='Foreground',items=[('LUMINANCE','White / Bright','Cut out the bright pixels'),('ALPHA','Alpha Channel','Cut out the opaque pixels')],default='LUMINANCE')
    threshold:FloatProperty(name='Threshold',default=0.5,min=0.0,max=1.0)
    invert:BoolProperty(name='Invert',default=False)
    simplify:FloatProperty(name='Simplify (px)',default=0.8,min=0,max=8)
    def execute(self,context):
        try:
            name=self.shape_name.strip() or Path(self.filepath).stem
            path=import_png(self.filepath,name,self.mode,self.threshold,self.invert,self.simplify)
            context.scene.mch_png_preset=path.stem
            self.report({'INFO'},'Imported vector Cut preset: '+name)
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'},f'PNG import failed: {exc}')
            return {'CANCELLED'}


class MCH_OT_delete_cut_preset(bpy.types.Operator):
    bl_idname='mch.delete_cut_preset'
    bl_label='Delete Selected Cut Preset'
    bl_options={'REGISTER'}
    def execute(self,context):
        stem=context.scene.mch_png_preset
        f=preset_folder()/(stem+'.json')
        if not f.is_file():return {'CANCELLED'}
        try:
            d=json.loads(f.read_text(encoding='utf-8'))
            thumb=preset_folder()/Path(d['source']).name
            f.unlink();thumb.unlink(missing_ok=True)
            _refresh_previews()
            self.report({'INFO'},'Cut preset removed')
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'},str(exc));return {'CANCELLED'}


class MCH_OT_stamp_png_cut(bpy.types.Operator):
    bl_idname='mch.stamp_png_cut'
    bl_label='Stamp Cut Preset'
    bl_description='LMB stamps the selected vector mask, mouse wheel changes size, Q/ESC exits'
    bl_options={'REGISTER','UNDO','BLOCKING'}
    @classmethod
    def poll(cls,context):
        return context.area and context.area.type=='VIEW_3D' and context.mode=='OBJECT' and context.active_object and context.active_object.type=='MESH'
    def invoke(self,context,event):
        try:self._loops=read_current(context)['loops']
        except (ValueError,KeyError) as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        self._target=context.active_object
        self._region=next((r for r in context.area.regions if r.type=='WINDOW'),None)
        if self._region is None:return {'CANCELLED'}
        self._rv3d=context.space_data.region_3d
        self._area=context.area
        self._width=context.scene.mch_stamp_size
        self._depth=context.scene.mch_stamp_depth
        self._angle=context.scene.mch_stamp_angle
        self._apply=context.scene.mch_settings.auto_apply
        self._mouse=None
        self._handler=bpy.types.SpaceView3D.draw_handler_add(_draw_stamp_preview,(self,),'WINDOW','POST_PIXEL')
        self._area.header_text_set('PNG CUT | Left click stamp | Wheel size | R rotate 15deg | Q/Esc exit')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    def _end(self):
        if self._handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handler,'WINDOW');self._handler=None
        self._area.header_text_set(None);self._area.tag_redraw()
    def _hit(self):
        if self._mouse is None:return None
        origin=view3d_utils.region_2d_to_origin_3d(self._region,self._rv3d,self._mouse)
        direction=view3d_utils.region_2d_to_vector_3d(self._region,self._rv3d,self._mouse)
        inv=self._target.matrix_world.inverted_safe()
        ok,at,normal,face=self._target.ray_cast(inv@origin,inv.to_3x3()@direction)
        if not ok:return None
        return self._target.matrix_world@at
    def _rotation(self):
        from mathutils import Quaternion
        return self._rv3d.view_rotation@Quaternion((0,0,1),self._angle)
    def modal(self,context,event):
        if event.type in {'Q','ESC'} and event.value=='PRESS':
            self._end();return {'FINISHED'}
        if self._target.name not in bpy.data.objects:
            self._end();return {'CANCELLED'}
        if context.area and context.area!=self._area:
            return {'PASS_THROUGH'}
        # End on panel click, then let the UI consume the same click (no ESC needed).
        if event.mouse_x<self._region.x or event.mouse_x>=self._region.x+self._region.width or event.mouse_y<self._region.y or event.mouse_y>=self._region.y+self._region.height:
            if event.type=='LEFTMOUSE' and event.value=='PRESS':self._end()
            return {'PASS_THROUGH'}
        self._mouse=(event.mouse_x-self._region.x,event.mouse_y-self._region.y)
        if event.type in {'WHEELUPMOUSE','WHEELDOWNMOUSE'} and event.value=='PRESS':
            self._width*=1.1 if event.type=='WHEELUPMOUSE' else 1/1.1
        if event.type=='R' and event.value=='PRESS':self._angle+=math.radians(15)
        if event.type=='LEFTMOUSE' and event.value=='PRESS':
            try:
                pos=self._hit()
                if pos is None:
                    self.report({'WARNING'},'Aim the stamp at the selected mesh surface')
                    return {'RUNNING_MODAL'}
                apply_stamp(context,self._target,self._loops,pos,self._rotation(),self._width,self._depth,self._apply)
                self.report({'INFO'},'PNG cut applied')
            except Exception as exc:self.report({'ERROR'},str(exc))
        self._area.tag_redraw()
        return {'RUNNING_MODAL'}


def _draw_stamp_preview(op):
    if op._mouse is None:return
    try:
        import gpu
        from gpu_extras.batch import batch_for_shader
        pos=op._hit()
        if pos is None:return
        rot=op._rotation()
        sh=gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        sh.bind();sh.uniform_float('color',(1,0.65,0.13,0.85))
        for ring in op._loops:
            pts=[]
            for x,y in ring:
                world=pos+rot@Vector((x*op._width,y*op._width,0))
                uv=view3d_utils.location_3d_to_region_2d(op._region,op._rv3d,world)
                if uv is not None:pts.append(tuple(uv))
            if len(pts)>=3:
                batch_for_shader(sh,'LINE_STRIP',{'pos':pts+[pts[0]]}).draw(sh)
        gpu.state.blend_set('NONE')
    except Exception:pass


def draw_ui(layout,context):
    col=layout.column(align=True)
    col.separator()
    col.label(text='PNG TO VECTOR CUT',icon='IMAGE_DATA')
    col.operator('mch.import_cut_png',text='Import PNG Shape',icon='IMPORT')
    col.template_icon_view(context.scene,'mch_png_preset',show_labels=True,scale=6.0,scale_popup=6.0)
    if context.scene.mch_png_preset!='NONE':
        row=col.row(align=True)
        row.operator('mch.stamp_png_cut',text='Stamp Selected',icon='MOD_BOOLEAN')
        row.operator('mch.delete_cut_preset',text='',icon='TRASH')
    col.prop(context.scene,'mch_stamp_size')
    col.prop(context.scene,'mch_stamp_depth')
    col.prop(context.scene,'mch_stamp_angle')
    col.label(text='White=Cut; transparent=Empty')


CLASSES=(MCH_OT_import_cut_png,MCH_OT_delete_cut_preset,MCH_OT_stamp_png_cut)


def register():
    for c in CLASSES:bpy.utils.register_class(c)
    bpy.types.Scene.mch_png_preset=EnumProperty(name='PNG Cut Presets',items=preset_items)
    bpy.types.Scene.mch_stamp_size=FloatProperty(name='Width',default=1.0,min=0.001,precision=3)
    bpy.types.Scene.mch_stamp_depth=FloatProperty(name='Cut Depth',default=0.3,min=0.001,precision=3)
    bpy.types.Scene.mch_stamp_angle=FloatProperty(name='Rotation',default=0,subtype='ANGLE')


def unregister():
    for n in ('mch_stamp_angle','mch_stamp_depth','mch_stamp_size','mch_png_preset'):
        if hasattr(bpy.types.Scene,n):delattr(bpy.types.Scene,n)
    for c in reversed(CLASSES):bpy.utils.unregister_class(c)
    global _preview_collection
    if _preview_collection is not None and previews:previews.remove(_preview_collection)
    _preview_collection=None
