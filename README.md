![step1](https://github.com/Fox178rus/MafiaDE_.compile_Blender_addon/blob/main/head2.jpg?raw=true)
# Mafia DE IRES Importer — Blender Addon

Blender addon for importing **Mafia Definitive Edition** `.ires.compiled` mesh files.

Supports cars, city buildings, props, and character parts.

![Blender screenshot placeholder](docs/screenshot.png)

---

## Features

- Import `.ires.compiled` files directly into Blender (File → Import → Mafia DE IRES)
- Multi-file selection — import multiple files at once
- LOD0-only filter (skip LOD1/2/3)
- Automatic texture loading:
  - **Near model (DDS)** — searches DDS files in the same folder as the `.ires` file
  - **Texture base (TGA/PNG)** — uses a pre-built texture database
- Build Texture Base — batch-converts all DDS from extracted SDS to TGA (requires Pillow)
- Correct vertex decoding (uint8 shader formula + merge-by-flag for split meshes)
- UV coordinates with proper V-flip

---

## Installation

### Requirements
- Blender 3.0 or newer
- Python (bundled with Blender)
- [Pillow](https://pillow.readthedocs.io/) — optional, for full DDS format support

### Steps

1. Download or clone this repository
2. In Blender: **Edit → Preferences → Add-ons → Install**
3. Navigate to the `addon/` folder and select `__init__.py`  
   *(or zip the `addon/` folder and install the zip)*
4. Enable the addon: **Mafia DE IRES Importer**
5. In addon preferences, set the **Texture Source** and paths as needed

### Install Pillow (recommended)

In Blender Preferences → Add-ons → Mafia DE IRES Importer, click **Install Pillow**.  
Or manually: open a terminal and run:
```
"<blender_path>/python/bin/python.exe" -m pip install Pillow
```

---

## Usage

### Import a single file
1. **File → Import → Mafia DE IRES (.ires.compiled)**
2. Navigate to your extracted SDS folder
3. Select one or more `.ires.compiled` files
4. Click **Import**

### Import with textures
1. Open **Edit → Preferences → Add-ons → Mafia DE IRES Importer**
2. Set **Texture Source**:
   - `Near model (DDS)` — DDS files must be in the same folder as the `.ires` file
   - `Texture base` — set **Texture Base Path** to your pre-built TGA/PNG folder
3. Import as usual

### Build Texture Base (one-time setup)
1. In addon preferences, set:
   - **Extracted SDS Root** — root folder of all extracted SDS files
   - **Texture Output Path** — where to save converted TGA files
2. Click **Build Texture Base**
3. Wait for conversion to finish (can take several minutes for full game)

---

## File Structure

```
addon/              ← Install this folder as Blender addon
  __init__.py       ← Addon entry point, preferences, operators
  ires_importer.py  ← Main import logic
  convert_dds.py    ← Standalone DDS→TGA converter (called as subprocess)
  scan_ires.py      ← Backend: buffer detection, vertex decoding, OBJ export

backend/
  scan_ires.py      ← Same file — standalone CLI usage

tools/
  export_universal.py   ← Batch exporter for cars_universal.sds (interactive CLI)
  export_universal.bat  ← Windows launcher for batch exporter

docs/
  IRES_FORMAT_RESEARCH.md   ← Full format research notes
  MERGE_FLAGS_RESEARCH.md   ← Split-mesh flag research
  MATERIAL_SLOTS.md         ← Material slot mapping research
  WORLD_LAYOUT_RESEARCH.md  ← World layout, entity positions, scale
```

---

## CLI Usage (scan_ires.py)

Export a single `.ires.compiled` to OBJ without Blender:

```bash
python backend/scan_ires.py <file.ires.compiled> [output_dir]
```

Example:
```bash
python backend/scan_ires.py "bolt_ace.sds/File_7.ires.compiled" ./output/
```

Output: one `.obj` file per sub-mesh, named by LOD and mesh index.

---

## Supported File Types

| File pattern | Content |
|---|---|
| `*.ires.compiled` | Props, characters, universal objects |
| `*.ires.[lod0].compiled` | Buildings LOD0 |
| `*.ires.[lod1].compiled` | Buildings LOD1 |
| `*.ires.[lod2].compiled` | Buildings LOD2 |
| `*.ires.[nomesh].compiled` | Metadata only (no geometry) |

---

## Vertex Format

Positions are encoded as uint8 pairs using the shader formula:
```
x = byte[0] / 256.0 + byte[1]
y = byte[2] / 256.0 + byte[3]
z = byte[4] / 256.0 + byte[5]
```

Split meshes (city environment) use a flag in `byte[5] bit7` to indicate which half a vertex belongs to. See `docs/MERGE_FLAGS_RESEARCH.md` for details.

---

## Known Limitations

- Material-to-submesh mapping for buildings requires a parsed `default.mtl` database (not included — extract from game files using `parse_mtl.py`)
- Blueprint data (exact submesh→material mapping) is encrypted in SDS and not accessible
- Character mesh assembly (scale + position from nomesh bbox) requires additional setup — see `docs/WORLD_LAYOUT_RESEARCH.md`

---

## Format Research

See the `docs/` folder for detailed reverse-engineering notes:

- **IRES_FORMAT_RESEARCH.md** — buffer detection, vertex decoding, LOD structure, sub-mesh tables
- **MERGE_FLAGS_RESEARCH.md** — split mesh reconstruction using per-vertex flags
- **MATERIAL_SLOTS.md** — material slot IDs and texture mapping
- **WORLD_LAYOUT_RESEARCH.md** — world coordinates, scale factors, entity positions, texture database

---

## Credits

Reverse engineering and implementation by the Mafia DE modding community.  
Format research based on RenderDoc captures and binary analysis of Mafia Definitive Edition game files.

Mafia Definitive Edition © 2K Games / Hangar 13. This tool is for modding/research purposes only.
