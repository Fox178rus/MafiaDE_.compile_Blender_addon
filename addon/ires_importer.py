"""
Mafia DE IRES Importer for Blender.
Uses scan_ires.py as backend for correct mesh + texture handling.
"""
import bpy, bmesh, os, sys, tempfile, shutil
from bpy.props import StringProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper

def get_scan_ires():
    """
    Import scan_ires from the same directory as this addon file.
    scan_ires.py must be placed next to __init__.py in the addon folder.
    """
    addon_dir = os.path.dirname(os.path.abspath(__file__))
    if addon_dir not in sys.path:
        sys.path.insert(0, addon_dir)
    import scan_ires
    return scan_ires


def _find_all_diffuse(sds_name, tex_mode, tex_base_path, ires_dir):
    """
    Find all diffuse textures for a given SDS name.
    Returns list of (base_name, filepath) sorted by name.
    base_name = filename without extension, e.g. 'bolt_ace_masks---d'
    """
    results = []
    prefix = sds_name.lower()

    if tex_mode == 'BASE' and tex_base_path:
        # Search in base subdirs: cars/weapons/characters/city
        for subdir in ['cars', 'weapons', 'characters', 'city', '']:
            d = os.path.join(tex_base_path, subdir) if subdir else tex_base_path
            if not os.path.isdir(d):
                continue
            for fname in sorted(os.listdir(d)):
                fl = fname.lower()
                if fl.startswith(prefix) and '---d' in fl and fl.endswith(('.tga', '.png', '.dds')):
                    base = os.path.splitext(fname)[0]
                    results.append((base, os.path.join(d, fname)))
        if results:
            return results

    if tex_mode in ('NEAR', 'BASE'):
        # Search DDS files in the SDS folder (same dir as .ires.compiled)
        if os.path.isdir(ires_dir):
            for fname in sorted(os.listdir(ires_dir)):
                fl = fname.lower()
                if fl.startswith(prefix) and '---d' in fl and fl.endswith('.dds'):
                    base = os.path.splitext(fname)[0]
                    results.append((base, os.path.join(ires_dir, fname)))

    return results


def _dds_to_tga(dds_path, tga_path):
    """Convert DDS to TGA using Pillow."""
    try:
        import site
        up = site.getusersitepackages()
        if up not in sys.path:
            sys.path.insert(0, up)
    except Exception:
        pass
    try:
        from PIL import Image
        img = Image.open(dds_path)
        img.save(tga_path, 'TGA')
        return True
    except Exception as e:
        print('DDS->TGA failed:', e)
        return False


def _ensure_tga(filepath, cache_dir):
    """
    If filepath is a DDS, convert to TGA in cache_dir and return TGA path.
    If already TGA/PNG, return as-is.
    """
    if filepath.lower().endswith('.dds'):
        fname = os.path.splitext(os.path.basename(filepath))[0] + '.tga'
        tga_path = os.path.join(cache_dir, fname)
        if not os.path.exists(tga_path):
            if not _dds_to_tga(filepath, tga_path):
                return filepath  # fallback to DDS
        return tga_path
    return filepath


def import_via_scan_ires(filepath, lod0_only=True, tex_base_path='', tex_mode='NONE'):
    """Export to temp OBJ via scan_ires, then import into Blender."""
    scan = get_scan_ires()

    out_dir = tempfile.mkdtemp(prefix='mafia_de_')
    try:
        # Run scan_ires
        scan.scan_file(filepath, out_dir)

        # Get SDS name for texture lookup
        # filepath is like: .../bolt_ace.sds/File_7.ires.compiled
        sds_name = None
        path_parts = filepath.replace('\\', '/').split('/')
        for part in reversed(path_parts):
            if part.endswith('.sds'):
                sds_name = part[:-4]
                break

        ires_dir = os.path.dirname(filepath)

        # Build texture cache: sds_name -> list of (base_name, tga_path)
        # base_name like 'bolt_ace_masks---d', 'bolt_ace_roof---d'
        tex_cache = {}  # base_name_lower -> tga_path
        if tex_mode != 'NONE' and sds_name:
            diffuse_list = _find_all_diffuse(sds_name, tex_mode, tex_base_path, ires_dir)
            print('Found {} diffuse textures for {}:'.format(len(diffuse_list), sds_name))
            for base, fpath in diffuse_list:
                tga = _ensure_tga(fpath, out_dir)
                tex_cache[base.lower()] = tga
                print('  {} -> {}'.format(base, os.path.basename(tga)))

        # Find exported OBJ files
        obj_files = sorted([f for f in os.listdir(out_dir) if f.endswith('.obj')])

        # Filter by LOD first
        if lod0_only:
            obj_files = [f for f in obj_files
                         if '_lod1_' not in f and '_lod2_' not in f and '_lod3_' not in f]

        # Read all meshes, rotate, compute global Z floor
        mesh_data = []  # list of (name, rot_verts, vert_uvs, faces, mat_name)
        global_min_z = float('inf')

        for obj_file in obj_files:
            obj_path = os.path.join(out_dir, obj_file)
            name = os.path.splitext(obj_file)[0]
            verts, vert_uvs, faces, mat_name = _read_obj(obj_path)
            if not verts or not faces:
                continue
            rot_verts = _rotate_verts(verts)
            if rot_verts:
                global_min_z = min(global_min_z, min(v[2] for v in rot_verts))
            mesh_data.append((name, rot_verts, vert_uvs, faces, mat_name))

        if global_min_z == float('inf'):
            global_min_z = 0.0

        imported = []
        for name, rot_verts, vert_uvs, faces, mat_name in mesh_data:
            # Create mesh with Z floor applied globally
            obj = _create_mesh(name, rot_verts, faces, vert_uvs, z_floor=global_min_z)

            # Apply texture
            if tex_mode != 'NONE' and tex_cache:
                tex_file = _pick_texture(mat_name, sds_name, tex_cache)
                if tex_file:
                    mat_key = mat_name if mat_name else (sds_name or name)
                    _apply_material(obj, mat_key, tex_file)
                else:
                    print('No texture found for:', name, 'base:', tex_base_path or ires_dir)

            imported.append(obj)

        return imported
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def _pick_texture(mat_name, sds_name, tex_cache):
    """
    Pick the best diffuse texture from tex_cache for a given material/mesh.

    Strategy:
    1. If mat_name matches a key in tex_cache exactly → use it
    2. If mat_name contains a suffix that matches (e.g. mat='bolt_ace_roof' → 'bolt_ace_roof---d')
    3. If sds_name matches a key (e.g. 'bolt_ace---d')
    4. Fallback: first texture in cache (usually the largest/body texture)
    """
    if not tex_cache:
        return None

    # Normalize mat_name
    if mat_name:
        mn = mat_name.lower().rstrip()
        # Strip ---d suffix if present
        import re
        mn_clean = re.sub(r'---[a-z]+$', '', mn)

        # 1. Exact match: mat_name---d
        key = mn_clean + '---d'
        if key in tex_cache:
            return tex_cache[key]

        # 2. mat_name starts with a key prefix
        for k, v in tex_cache.items():
            k_clean = re.sub(r'---[a-z]+$', '', k)
            if mn_clean == k_clean:
                return v

        # 3. Partial match: mat_name contains key base
        for k, v in tex_cache.items():
            k_clean = re.sub(r'---[a-z]+$', '', k)
            if k_clean in mn_clean or mn_clean in k_clean:
                return v

    # 4. sds_name exact match
    if sds_name:
        key = sds_name.lower() + '---d'
        if key in tex_cache:
            return tex_cache[key]

    # 5. Fallback: first texture
    return next(iter(tex_cache.values()))


def _read_obj(path):
    """Read OBJ file, return (verts, uvs, faces, mat_name)."""
    verts = []; uvs = []; faces = []; mat_name = None
    uv_list = []
    for line in open(path, encoding='utf-8', errors='ignore'):
        line = line.strip()
        if line.startswith('v '):
            p = line.split()
            verts.append((float(p[1]), float(p[2]), float(p[3])))
        elif line.startswith('vt '):
            p = line.split()
            uv_list.append((float(p[1]), float(p[2])))
        elif line.startswith('usemtl '):
            mat_name = line[7:].strip()
        elif line.startswith('f '):
            parts = line.split()[1:]
            face_vi = []; face_uvi = []
            for p in parts:
                sp = p.split('/')
                vi = int(sp[0]) - 1
                uvi = int(sp[1]) - 1 if len(sp) > 1 and sp[1] else vi
                face_vi.append(vi)
                face_uvi.append(uvi)
            if len(face_vi) >= 3:
                faces.append((face_vi, face_uvi))
    # Build per-vertex UV
    vert_uvs = [(0.0, 0.0)] * len(verts)
    for face_vi, face_uvi in faces:
        for vi, uvi in zip(face_vi, face_uvi):
            if uvi < len(uv_list):
                vert_uvs[vi] = uv_list[uvi]
    return verts, vert_uvs, [f[0] for f in faces], mat_name


def _rotate_verts(verts):
    """
    scan_ires exports OBJ with rotate X -90°: raw (x,y,z) → OBJ (x, z, -y).
    We apply another +90° on X to get Blender-correct orientation:
    OBJ (x, y, z) → Blender (x, -z, y)
    Net result from raw: (x, y, z) → (x, y, z)  i.e. identity — correct upright pose.
    """
    return [(x, -z, y) for (x, y, z) in verts]


# Mafia DE vertex units → meters.
# decode_pos gives values in centimeters (b[1] is integer cm, b[0]/256 is fractional).
# 1 cm = 0.01 m
IRES_SCALE = 0.01


def _create_mesh(name, verts, faces, uvs, z_floor=0.0):
    """
    Create Blender mesh.
    verts: already rotated vertices (in raw IRES units).
    z_floor: global minimum Z — subtracted so lowest point sits at Z=0.
    Scale applied: IRES_SCALE (cm → m).
    """
    s = IRES_SCALE
    final_verts = [(x * s, y * s, (z - z_floor) * s) for (x, y, z) in verts]

    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    bm = bmesh.new()
    bvs = [bm.verts.new(v) for v in final_verts]
    bm.verts.ensure_lookup_table()
    ul = bm.loops.layers.uv.new('UVMap')
    for face_vi in faces:
        try:
            f = bm.faces.new([bvs[i] for i in face_vi])
            for loop, vi in zip(f.loops, face_vi):
                if vi < len(uvs):
                    loop[ul].uv = uvs[vi]
        except:
            pass
    bm.to_mesh(mesh); bm.free(); mesh.update()
    return obj


def _apply_material(obj, mat_name, tex_file):
    """Create and apply material with texture. Reuse existing material if same tex."""
    # Use tex filename as material key to avoid duplicates with same texture
    tex_fname = os.path.basename(tex_file)
    mat_key = mat_name + '__' + tex_fname

    mat = bpy.data.materials.get(mat_key)
    if mat is None:
        mat = bpy.data.materials.new(name=mat_key)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()
        out = nodes.new('ShaderNodeOutputMaterial')
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        tex_node = nodes.new('ShaderNodeTexImage')
        links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
        links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
        out.location = (300, 0); bsdf.location = (0, 0); tex_node.location = (-300, 0)
        img = bpy.data.images.get(tex_fname)
        if img is None:
            try:
                img = bpy.data.images.load(tex_file)
            except Exception as e:
                print('Image load failed:', e)
        if img:
            tex_node.image = img
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


# ─── Blender Operator ─────────────────────────────────────────────────────────

class IMPORT_OT_mafia_de_ires(bpy.types.Operator, ImportHelper):
    bl_idname = "import_mesh.mafia_de_ires"
    bl_label = "Import Mafia DE IRES"
    bl_description = "Import Mafia DE .ires.compiled (uses scan_ires for correct textures)"
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = ".compiled"
    # Show all files — buildings have names like File_61.ires.compiled,
    # File_99.ires.[lod0].compiled etc. Don't restrict by glob.
    filter_glob: StringProperty(default="*", options={'HIDDEN'})
    lod0_only: BoolProperty(name="LOD0 only", default=True)

    # Support multi-file selection
    files: bpy.props.CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'},
    )
    directory: StringProperty(options={'HIDDEN'})

    def execute(self, context):
        prefs = context.preferences.addons.get('mafia_de_ires')
        tex_mode = 'NONE'; tex_base = ''
        if prefs:
            p = prefs.preferences
            tex_mode = p.tex_mode
            tex_base = p.tex_base_path.strip()

        # Build list of files to import
        import_paths = []
        if self.files and self.directory:
            for f in self.files:
                fp = os.path.join(self.directory, f.name)
                if os.path.isfile(fp):
                    import_paths.append(fp)
        # Fallback: single filepath
        if not import_paths:
            fp = self.filepath
            if os.path.isfile(fp):
                import_paths.append(fp)
            elif os.path.isdir(fp):
                # User selected a folder — import all .compiled files in it
                for fname in sorted(os.listdir(fp)):
                    if fname.endswith('.compiled'):
                        import_paths.append(os.path.join(fp, fname))

        if not import_paths:
            self.report({'ERROR'}, 'No .compiled files selected')
            return {'CANCELLED'}

        total = 0
        errors = 0
        for filepath in import_paths:
            try:
                objs = import_via_scan_ires(filepath, self.lod0_only, tex_base, tex_mode)
                total += len(objs)
            except Exception as e:
                import traceback
                traceback.print_exc()
                errors += 1

        if total == 0 and errors == 0:
            self.report({'WARNING'}, 'No meshes found in selected file(s)')
            return {'FINISHED'}
        if errors:
            self.report({'WARNING'}, 'Imported %d mesh(es), %d file(s) failed' % (total, errors))
        else:
            self.report({'INFO'}, 'Imported %d mesh(es) from %d file(s)' % (total, len(import_paths)))
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'lod0_only')
        prefs = context.preferences.addons.get('mafia_de_ires')
        if prefs:
            layout.label(text="Texture: %s" % prefs.preferences.tex_mode, icon='TEXTURE')
            layout.label(text="(Change in Preferences → Add-ons → Mafia DE IRES)")


# ─── Texture base builder ─────────────────────────────────────────────────────

def get_category_folder(sds_path):
    import re
    parts = set(re.split(r'[/\\]', sds_path.lower()))
    if 'cars' in parts or 'cars_tuning' in parts: return 'cars'
    if 'weapons' in parts: return 'weapons'
    if 'basic_anim' in parts or 'combinables' in parts: return 'characters'
    return 'city'

def build_texture_base(sds_extracted_path, output_path, output_format='PNG', overwrite=False, texconv_path=''):
    """Convert all DDS using standalone script."""
    import subprocess
    addon_dir = os.path.dirname(os.path.abspath(__file__))
    converter = os.path.join(addon_dir, 'convert_dds.py')
    blender_python = sys.executable
    result = subprocess.run(
        [blender_python, converter, sds_extracted_path, output_path],
        capture_output=True, text=True, timeout=3600
    )
    count = 0; errors = 0
    import re
    for line in result.stdout.splitlines():
        if line.startswith('OK:'): count += 1
        elif line.startswith('FAIL:'): errors += 1
        elif line.startswith('DONE:'):
            m = re.search(r'(\d+) converted, (\d+) errors', line)
            if m: count = int(m.group(1)); errors = int(m.group(2))
    if result.returncode != 0 and not result.stdout:
        return 0, 1
    return count, errors


def menu_func_import(self, context):
    self.layout.operator(IMPORT_OT_mafia_de_ires.bl_idname,
                         text="Mafia DE IRES (.ires.compiled)")

def register():
    bpy.utils.register_class(IMPORT_OT_mafia_de_ires)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(IMPORT_OT_mafia_de_ires)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
