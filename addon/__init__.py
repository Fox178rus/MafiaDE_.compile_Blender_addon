bl_info = {
    "name":        "Mafia DE IRES Importer",
    "description": "Import Mafia Definitive Edition .ires.compiled mesh files",
    "author":      "MafiaDE Tools",
    "version":     (1, 1, 0),
    "blender":     (3, 0, 0),
    "location":    "File > Import > Mafia DE IRES (.ires.compiled)",
    "category":    "Import-Export",
}

if "bpy" in locals():
    import importlib
    if "ires_importer" in locals():
        importlib.reload(ires_importer)

import bpy
from bpy.props import StringProperty, EnumProperty, BoolProperty
from . import ires_importer


class MafiaDEPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    tex_mode: EnumProperty(
        name="Texture Source",
        items=[
            ('NONE',  "No textures",       "Don't load textures"),
            ('NEAR',  "Near model (DDS)",   "Search DDS files in same folder as .ires file"),
            ('BASE',  "Texture base",       "Use pre-built texture base (PNG/TGA)"),
        ],
        default='NONE',
    )
    tex_base_path: StringProperty(
        name="Texture Base Path",
        description="Folder with pre-built PNG/TGA texture base",
        default="",
        subtype='DIR_PATH',
    )
    sds_extracted_path: StringProperty(
        name="Extracted SDS Root",
        description="Root folder with all extracted SDS files (for building texture base)",
        default="",
        subtype='DIR_PATH',
    )
    tex_overwrite: BoolProperty(
        name="Overwrite existing",
        description="Overwrite already converted textures",
        default=True,
    )
    texconv_path: StringProperty(
        name="texconv.exe path",
        description="Path to texconv.exe (Microsoft DirectXTex) for converting all DDS formats. Download from github.com/microsoft/DirectXTex",
        default="",
        subtype='FILE_PATH',
    )
    tex_output_path: StringProperty(
        name="Texture Output Path",
        description="Where to save converted textures (subfolders: cars/weapons/characters/city)",
        default="",
        subtype='DIR_PATH',
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Texture Settings:", icon='TEXTURE')
        layout.prop(self, 'tex_mode')

        if self.tex_mode == 'BASE':
            layout.prop(self, 'tex_base_path')

        layout.separator()
        box = layout.box()
        box.label(text="Build Texture Base:", icon='FILE_FOLDER')

        # Check if Pillow is available
        try:
            import sys, site
            up = site.getusersitepackages()
            if up not in sys.path:
                sys.path.insert(0, up)
            from PIL import Image
            box.label(text="Pillow: installed ✓", icon='CHECKMARK')
        except ImportError:
            box.label(text="Pillow not installed — limited DDS support", icon='ERROR')
            box.operator("mafia_de.install_pillow", text="Install Pillow (recommended)", icon='IMPORT')

        box.prop(self, 'sds_extracted_path')
        box.prop(self, 'tex_output_path')
        row = box.row()
        row.label(text="Output format: TGA (with alpha channel)")
        row.operator("mafia_de.build_texture_base", text="Build Texture Base", icon='FILE_REFRESH')


class INSTALL_OT_pillow(bpy.types.Operator):
    bl_idname = "mafia_de.install_pillow"
    bl_label = "Install Pillow"
    bl_description = "Install Pillow (PIL) into Blender Python for full DDS support"

    def execute(self, context):
        import subprocess, sys
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', 'Pillow'],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                self.report({'INFO'}, 'Pillow installed successfully! Restart Blender.')
            else:
                self.report({'ERROR'}, 'Failed: ' + result.stderr[:200])
        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'FINISHED'}


class BUILD_OT_texture_base(bpy.types.Operator):
    bl_idname = "mafia_de.build_texture_base"
    bl_label = "Build Texture Base"
    bl_description = "Scan extracted SDS folder and convert all DDS to PNG/TGA"

    def execute(self, context):
        prefs = context.preferences.addons[__name__].preferences
        if not prefs.sds_extracted_path or not prefs.tex_output_path:
            self.report({'ERROR'}, 'Set Extracted SDS Root and Texture Output Path first')
            return {'CANCELLED'}
        count, errors = ires_importer.build_texture_base(
            prefs.sds_extracted_path,
            prefs.tex_output_path,
            'PNG',
            True,
            prefs.texconv_path,
        )
        self.report({'INFO'}, 'Converted %d files (%d errors)' % (count, errors))
        return {'FINISHED'}


def register():
    bpy.utils.register_class(MafiaDEPreferences)
    bpy.utils.register_class(INSTALL_OT_pillow)
    bpy.utils.register_class(BUILD_OT_texture_base)
    ires_importer.register()

def unregister():
    ires_importer.unregister()
    bpy.utils.unregister_class(BUILD_OT_texture_base)
    bpy.utils.unregister_class(INSTALL_OT_pillow)
    bpy.utils.unregister_class(MafiaDEPreferences)
