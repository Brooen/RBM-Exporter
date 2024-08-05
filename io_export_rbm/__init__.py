bl_info = {
    "name": "RBM Exporter",
    "blender": (4, 1, 1),
    "category": "Import-Export",
    "description": "Exports selected objects to an RBM file",
    "author": "Brooen",
    "version": (1, 1, 1),
}

import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper
import os
import sys

# Ensure the secondary script is in the module search path
addon_dir = os.path.dirname(__file__)
if addon_dir not in sys.path:
    sys.path.append(addon_dir)

# Import the secondary script
import export_rbm_script


class ExportRBM(bpy.types.Operator, ExportHelper):
    bl_idname = "export_scene.rbm"
    bl_label = "Export RBM"
    filename_ext = ".rbm"

    filter_glob: StringProperty(
        default="*.rbm",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        supported_nodegroups = ['CARPAINTMM', 'BAVARIUMSHIELD', 'WATERHULL', 'WINDOW', 'CARLIGHT']
        selected_objects = bpy.context.selected_objects

        objects_data = []
        for obj in selected_objects:
            print(f"Processing object: {obj.name}")
            obj_data = export_rbm_script.process_object(obj, supported_nodegroups)
            if obj_data:
                objects_data.append(obj_data)

        if objects_data:
            min_max_positions = export_rbm_script.calculate_global_min_max(objects_data)
            print(f"Global min and max positions: {min_max_positions}")

            export_rbm_script.write_to_file(self.filepath, objects_data, min_max_positions)
        else:
            print("No valid objects to write.")
        
        return {'FINISHED'}


class AppendNodeGroupOperator(bpy.types.Operator):
    bl_idname = "object.append_node_group"
    bl_label = "Append Node Group"
    node_group_name: StringProperty()

    def execute(self, context):
        filepath = os.path.join(addon_dir, "assets.blend")
        with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
            if self.node_group_name in data_from.node_groups:
                data_to.node_groups = [self.node_group_name]
            if "ScaleReference" in data_from.objects:
                data_to.objects = ["ScaleReference"]

        for node_group in data_to.node_groups:
            print(f"Appended node group: {node_group.name}")

        # Add the node group to the active material
        material = context.object.active_material
        if not material:
            material = bpy.data.materials.new(name="Material")
            context.object.data.materials.append(material)
        if not material.use_nodes:
            material.use_nodes = True
        node_tree = material.node_tree
        node = node_tree.nodes.new("ShaderNodeGroup")
        node.node_tree = bpy.data.node_groups[self.node_group_name]

        return {'FINISHED'}


class AppendScaleReferenceOperator(bpy.types.Operator):
    bl_idname = "object.append_scale_reference"
    bl_label = "Add Scale Reference to scene"

    def execute(self, context):
        filepath = os.path.join(addon_dir, "assets.blend")
        with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
            data_to.objects = [name for name in data_from.objects if name == "ScaleReference"]

        for obj in data_to.objects:
            if obj is not None:
                bpy.context.collection.objects.link(obj)
                print(f"Appended scale reference object: {obj.name}")

        return {'FINISHED'}


class RBM_PT_Panel(bpy.types.Panel):
    bl_label = "RBM Exporter Panel"
    bl_idname = "RBM_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RBM Exporter'

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.operator("object.append_node_group", text="Add CARPAINTMM to material").node_group_name = "CARPAINTMM"

        row = layout.row()
        row.operator("object.append_node_group", text="Add BAVARIUMSHIELD to material").node_group_name = "BAVARIUMSHIELD"

        row = layout.row()
        row.operator("object.append_node_group", text="Add WATERHULL to material").node_group_name = "WATERHULL"

        row = layout.row()
        row.operator("object.append_node_group", text="Add WINDOW to material").node_group_name = "WINDOW"

        row = layout.row()
        row.operator("object.append_node_group", text="Add CARLIGHT to material").node_group_name = "CARLIGHT"

        row = layout.row()
        row.operator("object.append_scale_reference", text="Add Scale Reference to scene")

        row = layout.row()
        row.operator(ExportRBM.bl_idname, text="Export RBM to file")


def menu_func_export(self, context):
    self.layout.operator(ExportRBM.bl_idname, text="RBM Exporter (.rbm)")


def register():
    bpy.utils.register_class(ExportRBM)
    bpy.utils.register_class(AppendNodeGroupOperator)
    bpy.utils.register_class(AppendScaleReferenceOperator)
    bpy.utils.register_class(RBM_PT_Panel)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ExportRBM)
    bpy.utils.unregister_class(AppendNodeGroupOperator)
    bpy.utils.unregister_class(AppendScaleReferenceOperator)
    bpy.utils.unregister_class(RBM_PT_Panel)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()
