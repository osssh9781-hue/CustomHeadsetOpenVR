import sys,importlib.util,bpy
root='/mnt/data/mch_092_primitive_work'
spec=importlib.util.spec_from_file_location('mecha_lab',root+'/__init__.py',submodule_search_locations=[root]);module=importlib.util.module_from_spec(spec);sys.modules['mecha_lab']=module;spec.loader.exec_module(module)
module.register()
from mecha_lab import primitive_tools as pr

class Op:
    def __setattr__(self,name,value):
        object.__setattr__(self,name,value)
class Layout:
    def box(self):return self
    def row(self,**kwargs):return self
    def column(self,**kwargs):return self
    def label(self,**kwargs):return None
    def prop(self,*args,**kwargs):return None
    def operator(self,*args,**kwargs):return Op()
    def menu(self,*args,**kwargs):return None
    scale_y=1.0
    def separator(self):return None
L=Layout()
for k in ('BOX','CYLINDER','SPHERE','CONE','CAPSULE'):
 bpy.context.scene.mch_primitive.kind=k
 module.ui_tool_settings.draw_primitive(L,bpy.context)
 print('PASS UI scene',k)
bpy.ops.mch.primitive_create(kind='BOX')
for k in ('BOX','CYLINDER','SPHERE','CONE','CAPSULE'):
 bpy.context.active_object.mch_primitive.kind=k
 module.ui_tool_settings.draw_primitive(L,bpy.context)
 print('PASS UI object',k)
from types import SimpleNamespace
pr.MCH_MT_primitive_picker.draw(SimpleNamespace(layout=L),bpy.context)
print('PASS RMB popup UI')
module.unregister()
