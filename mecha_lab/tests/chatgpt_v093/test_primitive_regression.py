import sys,importlib.util,bpy,bmesh
root='/mnt/data/mch_092_primitive_work'
spec=importlib.util.spec_from_file_location('mecha_lab',root+'/__init__.py',submodule_search_locations=[root]);mod=importlib.util.module_from_spec(spec);sys.modules['mecha_lab']=mod;spec.loader.exec_module(mod)
mod.register()
from mecha_lab import primitive_tools as pr
passed=0

def check(pred,msg):
 global passed
 assert pred,msg
 print('PASS',msg)
 passed+=1

def meshstats(obj):
 deps=bpy.context.evaluated_depsgraph_get();ev=obj.evaluated_get(deps)
 me=bpy.data.meshes.new_from_object(ev,depsgraph=deps)
 bm=bmesh.new();bm.from_mesh(me)
 stats=(len(bm.verts),len(bm.faces),sum(not e.is_manifold for e in bm.edges),
        [max(v.co[i] for v in bm.verts)-min(v.co[i] for v in bm.verts) for i in range(3)])
 bm.free();bpy.data.meshes.remove(me);return stats

check('PRIMITIVE' in mod.tool_state.TOOL_BY_ID,'tool list includes Primitive')
check('PRIMITIVE' in mod.ui_tool_settings.DRAWERS,'sidebar has primitive settings drawer')
check(hasattr(bpy.ops.mch,'primitive_create'),'create operator registered')
check(hasattr(bpy.ops.mch,'primitive_switch'),'switch operator registered')
check(hasattr(bpy.ops.mch,'primitive_apply'),'apply operator registered')
check('MCH_MT_primitive_picker' in [c.__name__ for c in pr.CLASSES],'RMB popup menu registered')
check(bool(pr._KM),'RMB keymap registered')
bpy.ops.mch.primitive_create(kind='BOX')
a=bpy.context.active_object
base=meshstats(a)
check(base[2] == 0,'default box manifold')
a.mch_primitive.top_x=2.0
taper=meshstats(a)
check(taper[3][0]>base[3][0]+0.7,'top width slider changes shape')
a.mch_primitive.hole_enabled=True
a.mch_primitive.hole_radius=0.23
hole=meshstats(a)
check(hole[2]==0 and hole[0]>taper[0],'box hole boolean is manifold and increases geometry')
a.mch_primitive.hole_enabled=False
check(meshstats(a)[0]<hole[0],'toggle hole off removes cutter')
check(bpy.ops.mch.primitive_switch(kind='CYLINDER') == {'FINISHED'},'switch to cylinder')
a.mch_primitive.radius_top=0.15
check(meshstats(a)[2]==0,'tapered cylinder manifold')
check(bpy.ops.mch.primitive_switch(kind='SPHERE')== {'FINISHED'},'switch to sphere')
check(meshstats(a)[2]==0,'sphere manifold')
check(bpy.ops.mch.primitive_switch(kind='CONE')=={'FINISHED'},'switch to cone')
a.mch_primitive.radius_top=0
check(meshstats(a)[2]==0,'sharp cone manifold')
check(bpy.ops.mch.primitive_switch(kind='CAPSULE')=={'FINISHED'},'switch to capsule')
a.mch_primitive.length=6
a.mch_primitive.radius=0.7
cs=meshstats(a)
check(cs[2]==0,'capsule manifold')
check(abs(cs[3][2]-6)<0.05,'capsule total length matches parameter')
# duplicating object shares node group; adjusting duplicate splits GN material
ob2=a.copy();ob2.data=a.data; bpy.context.collection.objects.link(ob2)
ob2.mch_primitive.active=True
ob2.mch_primitive.length=4.2
check(abs(meshstats(a)[3][2]-6)<.05,'original unchanged when shared GN edited')
check(abs(meshstats(ob2)[3][2]-4.2)<.05,'duplicate GN edits independent')
# preview edit and apply preserves duplicate
for ob in bpy.context.selected_objects:ob.select_set(False)
a.select_set(True);bpy.context.view_layer.objects.active=a
before=meshstats(a)
check(bpy.ops.mch.primitive_apply()=={'FINISHED'},'apply returns finished')
check(len(a.modifiers)==0 and not a.mch_primitive.active,'apply removes procedural mods')
check(len(a.data.vertices)==before[0],'apply preserves evaluated vertex count')
check(ob2.mch_primitive.active and len(ob2.modifiers)==2,'duplicate stays live')
mod.unregister()
print('TESTS',passed,'passed')
