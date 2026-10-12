"""Mecha Lab Cut & Remove: screen-drawn cut without supplying a cutter mesh.

Implements two geometric strategies:
- Straight strokes: Blender BMesh plane bisection with optional planar cap.
- Closed or multi-point strokes: closed view-extruded polygon cutters + exact Boolean.

Drawing is 2D in the current viewport. The stroke is projected through the object,
not snapped onto an arbitrary curved surface geodesic. Users should distinguish it
from surface-contour/print-split algorithms.
"""
import math

import bpy
import bmesh
import gpu
from gpu_extras.batch import batch_for_shader
from bpy_extras import view3d_utils
from mathutils import Vector, Matrix, geometry
from mathutils.geometry import intersect_line_plane
from bpy.props import BoolProperty, EnumProperty

_EPS = 1e-7


def signed_area(poly):
    return 0.5 * sum(poly[i][0]*poly[(i+1)%len(poly)][1] -
                     poly[(i+1)%len(poly)][0]*poly[i][1] for i in range(len(poly)))


def point_inside(p, poly):
    inside = False
    x, y = p
    for (ax, ay), (bx, by) in zip(poly, poly[1:]+poly[:1]):
        if (ay > y) != (by > y):
            xi = ax + (bx-ax) * (y-ay) / (by-ay)
            if x < xi:
                inside = not inside
    return inside


def ray_box_exit(point, direction, box):
    """Point is inside box; project ray outward to the first rectangle boundary."""
    x, y = point
    dx, dy = direction
    xmin, ymin, xmax, ymax = box
    choices = []
    for border, orig, d in ((xmin,x,dx), (xmax,x,dx), (ymin,y,dy), (ymax,y,dy)):
        if abs(d) > _EPS:
            t = (border - orig)/d
            if t > 1e-9:
                px, py = x + t*dx, y + t*dy
                if xmin - 0.01 <= px <= xmax + 0.01 and ymin - 0.01 <= py <= ymax + 0.01:
                    choices.append((t,(max(xmin,min(xmax,px)), max(ymin,min(ymax,py)))))
    if not choices:
        raise ValueError('Cut endpoints coincide: place two distinct points')
    return min(choices, key=lambda c:c[0])[1]


def perimeter_parameter(p, box):
    xmin,ymin,xmax,ymax = box
    x,y=p; w=xmax-xmin; h=ymax-ymin
    e=0.03
    if abs(y-ymin)<e: return x-xmin
    if abs(x-xmax)<e: return w+y-ymin
    if abs(y-ymax)<e: return w+h+xmax-x
    if abs(x-xmin)<e: return 2*w+h+ymax-y
    raise ValueError('Cut endpoint must lie on view rectangle')


def border_ccw(a, b, box):
    """Rectangle boundary from a to b, proceeding counterclockwise (bottom->right->top->left)."""
    xmin,ymin,xmax,ymax=box
    w=xmax-xmin; h=ymax-ymin; perimeter=2*(w+h)
    lo=perimeter_parameter(a,box); hi=perimeter_parameter(b,box)
    if hi <= lo+1e-6: hi += perimeter
    corners=[(w,(xmax,ymin)),(w+h,(xmax,ymax)),(2*w+h,(xmin,ymax)),(perimeter,(xmin,ymin))]
    route=[c for t,c in ((t+k*perimeter,p) for k in (0,1) for t,p in corners) if lo+1e-5<t<hi-1e-5]
    return route+[b]


def make_side_polygon(points, box):
    if len(points)<2:
        raise ValueError('Draw at least two points')
    p0,p1=points[:2]; pn_1,pn=points[-2:]
    a=ray_box_exit(p0,(p0[0]-p1[0],p0[1]-p1[1]),box)
    b=ray_box_exit(pn,(pn[0]-pn_1[0],pn[1]-pn_1[1]),box)
    if math.dist(a,b)<2:
        raise ValueError('Cut endpoints extend to the same edge position')
    poly=[a]+points+[b]+border_ccw(b,a,box)[:-1]
    return dedupe(poly)


def dedupe(points):
    clean=[]
    for p in points:
        p=(float(p[0]),float(p[1]))
        if not clean or math.dist(p,clean[-1])>0.05:
            clean.append(p)
    if len(clean)>1 and math.dist(clean[0],clean[-1]) < 0.05: clean.pop()
    return clean


def segments_cross(a,b,c,d):
    def cross(p,q,r): return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    p,q,r,s=cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b)
    return ((p>1e-5 and q<-1e-5 or p<-1e-5 and q>1e-5) and
            (r>1e-5 and s<-1e-5 or r<-1e-5 and s>1e-5))


def self_intersects(poly):
    n=len(poly)
    for i in range(n):
        for j in range(i+2,n):
            if i==0 and j==n-1: continue
            if segments_cross(poly[i],poly[(i+1)%n],poly[j],poly[(j+1)%n]):
                return True
    return False


def simplify_path(points, tolerance=2.8):
    """Ramer-Douglas-Peucker to reduce a mouse stroke's polygon count."""
    if len(points)<3: return points[:]
    a,b=points[0],points[-1]; vx=b[0]-a[0]; vy=b[1]-a[1]
    ll=vx*vx+vy*vy
    def distance(pt):
        if ll < _EPS: return math.dist(pt,a)
        t=max(0,min(1,((pt[0]-a[0])*vx+(pt[1]-a[1])*vy)/ll))
        return math.dist(pt,(a[0]+vx*t,a[1]+vy*t))
    i=max(range(1,len(points)-1),key=lambda i:distance(points[i]))
    if distance(points[i])<=tolerance:
        return [a,b]
    return simplify_path(points[:i+1],tolerance)[:-1]+simplify_path(points[i:],tolerance)


def object_world_center_and_size(ob):
    corners=[ob.matrix_world @ Vector(v) for v in ob.bound_box]
    center=sum(corners,Vector())/8
    radius=max((v-center).length for v in corners)
    return center,max(radius,0.001),corners


def polygon_mesh(name, poly, frame, depth, region, rv3d, center, viewnormal):
    """Make closed, consistently wound watertight prism using n-gon caps."""
    inv=frame.inverted_safe()
    pts=[]
    for x,y in poly:
        ro=view3d_utils.region_2d_to_origin_3d(region,rv3d,(x,y))
        rd=view3d_utils.region_2d_to_vector_3d(region,rv3d,(x,y))
        projected=intersect_line_plane(ro,ro+rd*100000,center,viewnormal,False)
        if projected is None: raise ValueError('Unable to project cut contour onto view plane')
        local=inv @ projected
        pts.append((local.x,local.y))
    if abs(signed_area(pts)) < 1e-8 or len(pts)<3:
        raise ValueError('The drawn cut contour has zero area')
    if signed_area(pts)<0: pts.reverse()
    n=len(pts)
    verts=[(x,y,0.0) for x,y in pts]+[(x,y,depth) for x,y in pts]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh=bpy.data.meshes.new(name+'_Mesh')
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh


def make_path(name, poly, frame, collection, depth):
    """Editable 2D Bezier contour, points can be moved or changed to Auto handles."""
    data=bpy.data.curves.new(name+'_Curve','CURVE')
    data.dimensions='2D'; data.resolution_u=20
    spline=data.splines.new('BEZIER')
    spline.bezier_points.add(len(poly)-1)
    for bp,(x,y) in zip(spline.bezier_points,poly):
        bp.co=(x,y,0)
        bp.handle_left_type='VECTOR'; bp.handle_right_type='VECTOR'
    spline.use_cyclic_u=True
    ob=bpy.data.objects.new(name,data)
    collection.objects.link(ob)
    ob.matrix_world=frame.copy()
    ob['mch_cut_path']=True
    ob['mch_cut_depth']=depth
    ob.show_in_front=True
    return ob


def create_live_cutter(path, context, depth):
    """GN Fill Curve -> extrude -> add flipped bottom cap -> weld vertices."""
    mesh=bpy.data.meshes.new('MCH_Cut_ProceduralMesh')
    cutter=bpy.data.objects.new('MCH_Cut_LiveCutter',mesh)
    context.collection.objects.link(cutter)
    cutter.matrix_world=path.matrix_world.copy()
    group=bpy.data.node_groups.new('MCH Editable Cut Prism','GeometryNodeTree')
    group.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
    group.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    nodes=group.nodes; links=group.links
    obj=nodes.new('GeometryNodeObjectInfo')
    obj.inputs['Object'].default_value=path
    obj.inputs['As Instance'].default_value=False
    obj.transform_space='RELATIVE'
    fill=nodes.new('GeometryNodeFillCurve')
    links.new(obj.outputs['Geometry'],fill.inputs['Curve'])
    extrude=nodes.new('GeometryNodeExtrudeMesh')
    extrude.mode='FACES'
    extrude.inputs['Offset'].default_value=(0,0,depth)
    if 'Individual' in extrude.inputs:
        extrude.inputs['Individual'].default_value=False
    links.new(fill.outputs['Mesh'],extrude.inputs['Mesh'])
    # Extrude Mesh omits the underside: re-add a flipped fill and weld seams.
    flip=nodes.new('GeometryNodeFlipFaces')
    links.new(fill.outputs['Mesh'],flip.inputs['Mesh'])
    joined=nodes.new('GeometryNodeJoinGeometry')
    links.new(extrude.outputs['Mesh'],joined.inputs['Geometry'])
    links.new(flip.outputs['Mesh'],joined.inputs['Geometry'])
    weld=nodes.new('GeometryNodeMergeByDistance')
    weld.inputs['Distance'].default_value=0.00001
    links.new(joined.outputs['Geometry'],weld.inputs['Geometry'])
    out=nodes.new('NodeGroupOutput')
    links.new(weld.outputs['Geometry'],out.inputs['Geometry'])
    mod=cutter.modifiers.new('MCH_EditablePrism','NODES')
    mod.node_group=group
    cutter['mch_cut_carrier']=True
    cutter['mch_cut_path_name']=path.name
    path['mch_cut_cutter_name']=cutter.name
    cutter.display_type='WIRE'
    cutter.hide_set(True)
    cutter.hide_render=True
    return cutter


def create_static_cutter(context, mesh, frame):
    cutter=bpy.data.objects.new('MCH_Cut_Temporary',mesh)
    context.collection.objects.link(cutter)
    cutter.matrix_world=frame.copy()
    cutter.display_type='WIRE'
    cutter.hide_render=True
    return cutter


def new_bool(ob, cutter, operation):
    mod=ob.modifiers.new('MCH_DrawCut_'+operation,'BOOLEAN')
    mod.operation=operation
    mod.solver='EXACT'
    mod.object=cutter
    return mod


def only_active(context, ob):
    for a in context.selected_objects:a.select_set(False)
    ob.hide_set(False)
    ob.select_set(True)
    context.view_layer.objects.active=ob


def duplicate_mesh(context, ob, name):
    copy=ob.copy(); copy.data=ob.data.copy(); copy.name=name
    context.collection.objects.link(copy)
    copy.matrix_world=ob.matrix_world.copy()
    return copy


def dispose(ob):
    if ob and ob.name in bpy.data.objects:
        bpy.data.objects.remove(ob,do_unlink=True)


def apply_modifier(context, obj, mod):
    only_active(context,obj)
    if mod and obj.modifiers.get(mod.name):
        if obj.data and obj.data.users > 1:
            obj.data = obj.data.copy()  # Blender rejects modifier_apply on shared mesh data.
        bpy.ops.object.modifier_apply(modifier=mod.name)


def clear_or_keep_bisect(context, ob, plane_world, point_world, positive, cap):
    """BMesh plane cutting without requiring a cutter solid or an operand object."""
    bm=bmesh.new()
    try:
        bm.from_mesh(ob.data)
        inverse=ob.matrix_world.inverted_safe()
        plane_local=inverse @ point_world
        # Inverse-transpose converts a world-space normal into local-space.
        n_local=(ob.matrix_world.transposed().to_3x3() @ plane_world).normalized()
        if n_local.length < 1e-8: raise ValueError('Object scale is invalid for plane cut')
        signed_normal_positive=(n_local @ (inverse.to_3x3() @ plane_world))>0
        result=bmesh.ops.bisect_plane(
            bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
            dist=0.00001,plane_co=plane_local,plane_no=n_local,
            clear_outer=bool(positive if signed_normal_positive else not positive),
            clear_inner=bool((not positive) if signed_normal_positive else positive))
        if cap:
            # Only open boundary edges on the bisected plane are eligible.
            edges=[e for e in result['geom_cut'] if isinstance(e,bmesh.types.BMEdge)
                   and e.is_valid and e.is_boundary and
                   abs((e.verts[0].co-plane_local).dot(n_local))<0.0005 and
                   abs((e.verts[1].co-plane_local).dot(n_local))<0.0005]
            if edges:
                try:
                    bmesh.ops.holes_fill(bm,edges=edges,sides=0)
                except (ValueError,RuntimeError):
                    pass
        if not bm.faces:
            raise ValueError('Bisect removed the entire object; move the cut line onto the model')
        bm.normal_update()
        bm.to_mesh(ob.data)
        ob.data.update()
    finally:
        bm.free()


def _bitmap_draw(operator):
    if not operator._area or bpy.context.area != operator._area: return
    points=operator._pts[:]
    if operator._stage=='DRAW' and operator._mouse and operator._style in {'BOX','CIRCLE','NGON'} and points:
        points=operator._make_shape(points[0],operator._mouse)
    elif operator._stage=='DRAW' and operator._mouse and points and operator._style in {'POLYLINE','POLYGON'}:
        points=points+[operator._mouse]
    shader=gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')
    try:
        if operator._stage=='SIDE' and operator._poly:
            fill=operator._poly
            if (operator._mouse and not point_inside(operator._mouse,fill)
                    and not operator._closed and len(operator._pts)>1):
                try:
                    fill=make_side_polygon(list(reversed(operator._pts)),operator._bounding_rectangle())
                except (ValueError,ZeroDivisionError):
                    pass
            if len(fill)>=3:
                triangles=geometry.tessellate_polygon([[Vector((p[0],p[1],0)) for p in fill]])
                coords=[(v.x,v.y) for tri in triangles for v in tri]
                if coords:
                    shader.bind(); shader.uniform_float('color',(1.0,0.32,0.1,0.20))
                    batch_for_shader(shader,'TRIS',{'pos':coords}).draw(shader)
        if len(points)>=2:
            shader.bind();shader.uniform_float('color',((0.25,0.90,1.0,1.0) if operator._alt_invert else (1.0,0.7,0.12,1.0)))
            batch_for_shader(shader,'LINE_STRIP',{'pos':points}).draw(shader)
            if operator._closed:
                batch_for_shader(shader,'LINES',{'pos':[points[-1],points[0]]}).draw(shader)
        if points:
            shader.bind();shader.uniform_float('color',(0.1,0.85,1.0,1.0))
            gpu.state.point_size_set(7.0)
            batch_for_shader(shader,'POINTS',{'pos':points}).draw(shader)
    finally:
        gpu.state.point_size_set(1.0)
        gpu.state.blend_set('NONE')


class MCH_OT_draw_delete_cut(bpy.types.Operator):
    bl_idname='mch.draw_delete_cut'
    bl_label='Draw Cut and Remove [C]'
    bl_description='Draw to remove the inside, or Alt+draw to preserve the inside. Instant/continuous by default.'
    bl_options={'REGISTER','UNDO','BLOCKING'}
    keep_both:BoolProperty(name='Keep Both Halves',default=False)

    @classmethod
    def poll(cls,context):
        return (context.area is not None and context.area.type=='VIEW_3D'
                and context.active_object is not None
                and context.active_object.type=='MESH'
                and context.mode in {'OBJECT','EDIT_MESH'})

    def invoke(self,context,event):
        self._edit_mode=context.mode=='EDIT_MESH'
        if self._edit_mode:
            bpy.ops.object.mode_set(mode='OBJECT')
        self._target=context.active_object
        self._area=context.area
        self._region=next((r for r in context.area.regions if r.type=='WINDOW'),None)
        self._rv3d=context.space_data.region_3d
        if not self._region or not self._rv3d:
            self.report({'ERROR'},'Cannot find 3D viewport window')
            return {'CANCELLED'}
        self._viewrot=self._rv3d.view_rotation.copy()
        self._viewnormal=self._viewrot @ Vector((0,0,1))
        self._center,self._radius,self._bbox=object_world_center_and_size(self._target)
        self._stage='DRAW';self._pts=[];self._poly=None
        self._closed=context.scene.mch_settings.cut_closed
        self._style=context.scene.mch_settings.cut_draw_style
        if self._style in {'POLYGON','NGON'}: self._closed=True
        self._mouse=None;self._drag=False
        self._alt_invert=False
        self._ngon_sides=context.scene.mch_settings.cut_ngon_sides
        self._handle=bpy.types.SpaceView3D.draw_handler_add(_bitmap_draw,(self,),'WINDOW','POST_PIXEL')
        context.window.cursor_modal_set('CROSSHAIR')
        self._header('CUT | draw=remove inside / Alt+draw=keep inside | 1-6 shapes | Q exit')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _header(self,msg):
        try: self._area.header_text_set('MECHA CUT | '+msg)
        except ReferenceError:pass

    def _end(self,context):
        if self._handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle,'WINDOW')
            self._handle=None
        context.window.cursor_modal_restore()
        self._area.header_text_set(None)
        self._area.tag_redraw()

    def _abort(self,context):
        self._end(context)
        if self._edit_mode and context.active_object==self._target:
            try:bpy.ops.object.mode_set(mode='EDIT')
            except RuntimeError:pass
        return {'CANCELLED'}

    def _position(self,event):
        if not (self._region.x<=event.mouse_x<self._region.x+self._region.width and
                self._region.y<=event.mouse_y<self._region.y+self._region.height):
            return None
        return (float(event.mouse_x-self._region.x),float(event.mouse_y-self._region.y))

    def _reset_stroke(self, context):
        self._stage='DRAW'; self._pts=[]; self._poly=None; self._mouse=None; self._drag=False
        self._alt_invert=False
        self._viewrot=self._rv3d.view_rotation.copy()
        self._viewnormal=self._viewrot @ Vector((0,0,1))
        self._center,self._radius,self._bbox=object_world_center_and_size(self._target)
        self._header('CUT ACTIVE | draw=remove inside / Alt+draw=keep inside | Q exit')
        if self._area: self._area.tag_redraw()

    def _end_or_repeat(self,context,result):
        self.report({'INFO'},result)
        if context.scene.mch_settings.cut_repeat:
            # This modal operator owns the entire drawing session; a single
            # Blender Undo step may cover several cuts. Q ends that session.
            self._reset_stroke(context)
            return {'RUNNING_MODAL'}
        self._end(context)
        return {'FINISHED'}

    def _snap(self, p):
        if not self._pts: return p
        a=self._pts[-1]
        dx,dy=p[0]-a[0],p[1]-a[1]
        r=math.hypot(dx,dy)
        if r<1e-7:return p
        ang=round(math.atan2(dy,dx)/(math.pi/4))*(math.pi/4)
        return (a[0]+math.cos(ang)*r,a[1]+math.sin(ang)*r)

    def _make_shape(self,a,b):
        if self._style=='BOX':
            return [a,(b[0],a[1]),b,(a[0],b[1])]
        if self._style=='CIRCLE':
            radius=math.dist(a,b)
            return [(a[0]+radius*math.cos(2*math.pi*i/48),a[1]+radius*math.sin(2*math.pi*i/48)) for i in range(48)]
        if self._style=='NGON':
            n=self._ngon_sides
            radius=math.dist(a,b)
            angle=math.atan2(b[1]-a[1],b[0]-a[0])
            return [(a[0]+radius*math.cos(angle+2*math.pi*i/n),
                     a[1]+radius*math.sin(angle+2*math.pi*i/n)) for i in range(n)]
        return self._pts[:]

    def _bounding_rectangle(self):
        pts=[]
        for v in self._bbox:
            projected=view3d_utils.location_3d_to_region_2d(self._region,self._rv3d,v)
            if projected is not None: pts.append((projected.x,projected.y))
        if not pts:raise ValueError('Object is outside view')
        pts+=self._pts
        xx=[p[0] for p in pts];yy=[p[1] for p in pts]
        pad=max(80,0.2*max(max(xx)-min(xx),max(yy)-min(yy)))
        return (min(xx)-pad,min(yy)-pad,max(xx)+pad,max(yy)+pad)

    def _finish_drawing(self):
        pts=dedupe(simplify_path(self._pts,2.0) if self._style=='FREEHAND' else self._pts)
        if self._style in {'BOX','CIRCLE','NGON','POLYGON'}: self._closed=True
        if self._closed:
            if len(pts)<3: raise ValueError('Closed cut needs at least 3 distinct points')
            if len(pts)>3 and math.dist(pts[0],pts[-1])<12: pts.pop()
            poly=pts
        elif len(pts)>=2:
            poly=make_side_polygon(pts,self._bounding_rectangle())
        else:
            raise ValueError('Draw at least 2 points (closed cut requires 3)')
        if len(poly)<3 or abs(signed_area(poly))<40:
            raise ValueError('The selected cutting region is too small')
        if self_intersects(poly):
            raise ValueError('Cut line intersects itself; redraw a simpler contour')
        self._pts=pts;self._poly=poly
        self._stage='SIDE'
        self._header('SIDE: click side to remove | Enter applies default | Esc clear')

    def _create_boolean_cut(self,context, erase_inside, both):
        """Polygon side is defined in camera/screen projection; cutter penetrates full model depth."""
        source=self._target
        s=context.scene.mch_settings
        depth=max(self._radius*8,0.2)
        frame=Matrix.Translation(self._center-self._viewnormal*(depth*0.5)) @ self._viewrot.to_matrix().to_4x4()
        path=None;cutter=None;piece=None
        # For a loop, inside==cutter and outside==its complement.
        # For an open line, our polygon is one of the two selectable halves.
        primary_operation=('DIFFERENCE' if erase_inside else 'INTERSECT')
        try:
            if not s.auto_apply:
                poly_world=[]
                inv=frame.inverted_safe()
                for p in self._poly:
                    ro=view3d_utils.region_2d_to_origin_3d(self._region,self._rv3d,p)
                    rd=view3d_utils.region_2d_to_vector_3d(self._region,self._rv3d,p)
                    pp=intersect_line_plane(ro,ro+rd*100000,self._center,self._viewnormal,False)
                    if pp is None:raise ValueError('View projection failed')
                    v=inv @ pp
                    poly_world.append((v.x,v.y))
                # Flip to counter-clockwise so Fill Curve has a positive Z normal.
                if signed_area(poly_world)<0:poly_world.reverse()
                path=make_path('MCH_EditableCutBoundary',poly_world,frame,context.collection,depth)
                cutter=create_live_cutter(path,context,depth)
            else:
                mesh=polygon_mesh('MCH_DrawCut',self._poly,frame,depth,self._region,self._rv3d,self._center,self._viewnormal)
                cutter=create_static_cutter(context,mesh,frame)
            if both:
                piece=duplicate_mesh(context,source,source.name+'_CutPiece')
                piece_operation='INTERSECT' if primary_operation=='DIFFERENCE' else 'DIFFERENCE'
                piece_mod=new_bool(piece,cutter,piece_operation)
            target_mod=new_bool(source,cutter,primary_operation)
            if s.auto_apply:
                # Apply from duplicate first; its initial stack contains pre-cut modifiers.
                if piece:apply_modifier(context,piece,piece_mod)
                apply_modifier(context,source,target_mod)
                dispose(cutter)
                only_active(context,source)
                if piece:piece.select_set(True)
            else:
                # RNA object pointers survive object renames and are saved in .blend.
                cutter.mch_live.target=source
                cutter.mch_live.path=path
                cutter.mch_live.source=piece
                if path: path.mch_live.source=cutter
                cutter['mch_cut_target_name']=source.name
                cutter['mch_cut_target_mod']=target_mod.name
                cutter['mch_cut_piece_name']=piece.name if piece else ''
                cutter['mch_cut_piece_mod']=piece_mod.name if piece else ''
                if path:path['mch_cut_target_name']=source.name
                if path:path['mch_cut_piece_name']=piece.name if piece else ''
                source['mch_recent_cut']=cutter.name
                only_active(context,path)
            return ('Two closed parts created' if both else ('Outside removed' if not erase_inside else 'Inside removed'))+(' (live)' if not s.auto_apply else '')
        except Exception:
            # Undo operator will also restore the source; remove our orphan temp objects now.
            if piece:dispose(piece)
            if cutter:dispose(cutter)
            if path:dispose(path)
            raise

    def _apply(self,context,mouse,keep_both,invert=False):
        # The normal gesture removes the region enclosed by the contour.
        # Holding Alt while drawing keeps that region and removes its complement.
        # For open strokes the same flag swaps the two half-spaces.
        clicked_inside=point_inside(mouse,self._poly) != bool(invert)
        try:
            # BMesh bisect for a genuinely straight line: faster, caps planar sections.
            s=context.scene.mch_settings
            if (len(self._pts)==2 and not self._closed and s.auto_apply
                    and s.cut_fast_bisect):
                a,b=self._pts
                x,y=b[0]-a[0],b[1]-a[1]
                normal=self._viewrot @ Vector((y,-x,0))
                if normal.length<1e-8:raise ValueError('Cut line too short')
                normal.normalize()
                ro=view3d_utils.region_2d_to_origin_3d(self._region,self._rv3d,a)
                rd=view3d_utils.region_2d_to_vector_3d(self._region,self._rv3d,a)
                plane_point=intersect_line_plane(ro,ro+rd*100000,self._center,self._viewnormal,False)
                cross=x*(mouse[1]-a[1])-y*(mouse[0]-a[0])
                # (dy,-dx) dot (mouse-a) = -cross
                erase_positive = (cross < 0) != bool(invert)
                if keep_both:
                    copy=duplicate_mesh(context,self._target,self._target.name+'_CutPiece')
                    try:
                        clear_or_keep_bisect(context,copy,normal,plane_point,not erase_positive,s.cut_fill_caps)
                        clear_or_keep_bisect(context,self._target,normal,plane_point,erase_positive,s.cut_fill_caps)
                    except Exception:
                        dispose(copy)
                        raise
                    only_active(context,self._target)
                    copy.select_set(True)
                    result='Straight plane cut; two halves preserved'
                else:
                    clear_or_keep_bisect(context,self._target,normal,plane_point,erase_positive,s.cut_fill_caps)
                    only_active(context,self._target)
                    result='Straight plane cut; clicked half deleted'
            else:
                result=self._create_boolean_cut(context,clicked_inside,keep_both)
            return self._end_or_repeat(context,result)
        except Exception as ex:
            self.report({'ERROR'},'Cut failed: '+str(ex))
            return self._abort(context)

    def _commit_default_side(self,context):
        # For closed polygons, inside always means remove the interior.
        # For an open cut, the default is the polygon's positive side.
        if not self._poly:return {'RUNNING_MODAL'}
        tris=geometry.tessellate_polygon([[Vector((x,y,0)) for x,y in self._poly]])
        if tris:
            tri=tris[0]
            if isinstance(tri[0], int):
                p=(sum(self._poly[i][0] for i in tri)/len(tri),sum(self._poly[i][1] for i in tri)/len(tri))
            else:
                p=(sum(v.x for v in tri)/len(tri),sum(v.y for v in tri)/len(tri))
        else:
            p=(sum(v[0] for v in self._poly)/len(self._poly),
               sum(v[1] for v in self._poly)/len(self._poly))
        return self._apply(context,p,self.keep_both,invert=self._alt_invert)

    def _complete(self,context,alt=False):
        self._alt_invert = self._alt_invert or bool(alt)
        try:
            self._finish_drawing()
        except ValueError as ex:
            self.report({'WARNING'},str(ex))
            return {'RUNNING_MODAL'}
        if context.scene.mch_settings.cut_immediate:
            return self._commit_default_side(context)
        return {'RUNNING_MODAL'}

    def modal(self,context,event):
        if self._target.name not in bpy.data.objects:
            return self._abort(context)
        if event.type in {'MIDDLEMOUSE','WHEELUPMOUSE','WHEELDOWNMOUSE','NDOF_MOTION'}:
            return {'PASS_THROUGH'}
        self._mouse=self._position(event)
        # Let sidebar / other editors receive clicks without forcing Esc.
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS' and self._mouse is None:
            self._end(context)
            return {'FINISHED', 'PASS_THROUGH'}
        # Space is reserved for the Mecha Lab tool menu, not a Cut confirmation.
        if event.type == 'SPACE' and event.value == 'PRESS':
            self._end(context)
            bpy.ops.wm.call_menu(name='MCH_MT_tool_menu')
            return {'FINISHED'}
        if event.type in {'ESC','RIGHTMOUSE'} and event.value=='PRESS':
            if self._stage=='SIDE' or self._pts:
                self._reset_stroke(context)
                return {'RUNNING_MODAL'}
            return self._abort(context)
        if event.type=='LEFTMOUSE' and event.value=='DOUBLE_CLICK' and self._stage=='DRAW' and self._pts:
            return self._complete(context,alt=event.alt)
        if event.type=='Q' and event.value=='PRESS':
            self._end(context)
            return {'FINISHED'}

        if event.type=='MOUSEMOVE' and self._drag and self._mouse:
            if self._style=='FREEHAND' and (not self._pts or math.dist(self._pts[-1],self._mouse)>=5):
                self._pts.append(self._mouse)
            self._area.tag_redraw()
        if self._stage=='DRAW':
            if event.value=='PRESS' and event.type in {'ONE','TWO','THREE','FOUR','FIVE','SIX'}:
                modes={'ONE':'POLYLINE','TWO':'FREEHAND','THREE':'BOX','FOUR':'CIRCLE',
                       'FIVE':'POLYGON','SIX':'NGON'}
                self._style=modes[event.type]
                context.scene.mch_settings.cut_draw_style=self._style
                self._closed=self._style in {'POLYGON','NGON'} or context.scene.mch_settings.cut_closed
                self._reset_stroke(context)
                return {'RUNNING_MODAL'}
            if event.type=='BACK_SPACE' and event.value=='PRESS' and self._pts:
                self._pts.pop()
            if event.type=='F' and event.value=='PRESS':
                self._closed=not self._closed
                self._header('DRAW '+('CLOSED LOOP' if self._closed else 'OPEN CUT')+': LMB points | Enter select side | Esc cancel')
            if event.type=='LEFTMOUSE' and self._mouse:
                if event.value=='PRESS':
                    if self._style=='POLYGON' and len(self._pts)>=3 and math.dist(self._pts[0],self._mouse)<12:
                        return self._complete(context,alt=event.alt)
                    # Latch Alt for this stroke: no side-picking click needed.
                    if event.alt: self._alt_invert=True
                    self._drag=True
                    p=self._snap(self._mouse) if event.shift and self._style in {'POLYLINE','POLYGON'} else self._mouse
                    if self._style in {'POLYLINE','FREEHAND','POLYGON'}:
                        self._pts.append(p)
                    elif not self._pts:self._pts.append(self._mouse)
                elif event.value=='RELEASE':
                    self._drag=False
                    if self._style in {'BOX','CIRCLE','NGON'} and self._pts:
                        self._pts=self._make_shape(self._pts[0],self._mouse)
                        return self._complete(context,alt=event.alt)
            if event.type in {'RET','NUMPAD_ENTER'} and event.value=='PRESS':
                return self._complete(context,alt=event.alt)
            self._area.tag_redraw()
            return {'RUNNING_MODAL'}
        if self._stage=='SIDE':
            if event.type=='BACK_SPACE' and event.value=='PRESS':
                self._stage='DRAW';self._poly=None
                self._header('DRAW: continue editing contour, Enter side pick')
                return {'RUNNING_MODAL'}
            if event.type=='LEFTMOUSE' and event.value=='PRESS' and self._mouse:
                return self._apply(context,self._mouse,self.keep_both or event.shift,invert=self._alt_invert or event.alt)
            if event.type in {'RET','NUMPAD_ENTER'} and event.value=='PRESS':
                return self._commit_default_side(context)
            return {'RUNNING_MODAL'}
        return {'RUNNING_MODAL'}


class MCH_OT_cut_finalize(bpy.types.Operator):
    bl_idname='mch.cut_finalize'
    bl_label='Apply Live Draw Cut'
    bl_description='Apply live boolean results and remove the editable cutting path and prism'
    bl_options={'REGISTER','UNDO'}
    @classmethod
    def poll(cls,context):
        return context.mode=='OBJECT' and context.active_object is not None
    def execute(self,context):
        ob=context.active_object
        if ob.get('mch_cut_path'):
            cutter=ob.mch_live.source or bpy.data.objects.get(ob.get('mch_cut_cutter_name',''))
        elif ob.get('mch_cut_carrier'):cutter=ob
        else:cutter=bpy.data.objects.get(ob.get('mch_recent_cut',''))
        if not cutter or not cutter.get('mch_cut_carrier'):
            self.report({'WARNING'},'Select an editable cut path, cutter, or target with a recent live cut')
            return {'CANCELLED'}
        target=cutter.mch_live.target or bpy.data.objects.get(cutter.get('mch_cut_target_name',''))
        piece=cutter.mch_live.source or bpy.data.objects.get(cutter.get('mch_cut_piece_name',''))
        path=cutter.mch_live.path or bpy.data.objects.get(cutter.get('mch_cut_path_name',''))
        if not target:
            self.report({'ERROR'},'Live cut target has been removed')
            return {'CANCELLED'}
        try:
            if piece:
                mod=piece.modifiers.get(cutter.get('mch_cut_piece_mod',''))
                if mod:apply_modifier(context,piece,mod)
            mod=target.modifiers.get(cutter.get('mch_cut_target_mod',''))
            if not mod:raise ValueError('Cut Boolean modifier missing on target')
            apply_modifier(context,target,mod)
        except (RuntimeError,ValueError) as ex:
            self.report({'ERROR'},'Apply failed: '+str(ex))
            return {'CANCELLED'}
        # Modifier references must be resolved before removing their operands.
        if target.get('mch_recent_cut')==cutter.name:del target['mch_recent_cut']
        dispose(cutter);dispose(path)
        only_active(context,target)
        if piece:piece.select_set(True)
        self.report({'INFO'},'Cut applied; editable boundary removed')
        return {'FINISHED'}


CLASSES=(MCH_OT_draw_delete_cut,MCH_OT_cut_finalize)
