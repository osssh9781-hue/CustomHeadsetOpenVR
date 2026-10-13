import os,sys,importlib.util,bpy,bmesh,traceback
root='/mnt/data/mch_092_primitive_work'
spec=importlib.util.spec_from_file_location('mecha_lab',root+'/__init__.py',submodule_search_locations=[root]); module=importlib.util.module_from_spec(spec);sys.modules['mecha_lab']=module;spec.loader.exec_module(module)
module.register()
print('registered')
from mecha_lab import primitive_tools as pr

def meshdata(obj):
 deps=bpy.context.evaluated_depsgraph_get(); ob_eval=obj.evaluated_get(deps)
 mesh=bpy.data.meshes.new_from_object(ob_eval,depsgraph=deps)
 bm=bmesh.new();bm.from_mesh(mesh)
 bad=sum(1 for e in bm.edges if not e.is_manifold)
 xs=[v.co.x for v in bm.verts];ys=[v.co.y for v in bm.verts];zs=[v.co.z for v in bm.verts]
 res=(len(bm.verts),len(bm.faces),bad,tuple(round(max(v)-min(v),3) for v in (xs,ys,zs)))
 bm.free();bpy.data.meshes.remove(mesh)
 return res
for kind in ('BOX','CYLINDER','SPHERE','CONE','CAPSULE'):
 try:
  result=bpy.ops.mch.primitive_create(kind=kind)
  obj=bpy.context.active_object
  print(kind,'CREATE',result,'MODS',[(m.name,m.type) for m in obj.modifiers],'STATS',meshdata(obj))
  assert meshdata(obj)[0]>0
  if kind=='BOX':
   p=obj.mch_primitive
   p.top_x=1.9;p.top_y=1.5;p.height=2.0
   print('BOX TAPER',meshdata(obj))
   p.hole_enabled=True;p.hole_radius=0.22
   print('BOX HOLE',meshdata(obj))
  if kind=='CYLINDER':
   p=obj.mch_primitive;p.radius_top=0.2;p.hole_enabled=True;p.hole_radius=0.1
   print('CYLINDER HOLE',meshdata(obj))
  if kind=='CAPSULE':
   p=obj.mch_primitive;p.length=4.5
   print('CAPSULE LENGTH',meshdata(obj))
  assert bpy.ops.mch.primitive_apply()=={'FINISHED'}
  print(kind,'APPLIED',len(obj.data.vertices),len(obj.modifiers))
 except Exception:
  traceback.print_exc()
  raise
module.unregister();print('unregistered')
