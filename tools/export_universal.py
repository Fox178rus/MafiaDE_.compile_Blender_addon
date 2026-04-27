"""
Экспортёр cars_universal.sds — все .ires.compiled рекурсивно.
Запуск: python export_universal.py
"""
import os, sys, glob, struct

UNIVERSAL_DIR = 'CARS_MAFIA_DE/cars_universal.sds'  # path to extracted cars_universal.sds folder
OUT_BASE = 'mafia_de_export/'                        # output folder for exported OBJ files
SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'backend', 'scan_ires.py')

BUFFER_MAGIC = bytes([0x63, 0x77, 0xe0, 0x46])

def has_geometry(path):
    """Быстрая проверка — есть ли в файле VB/IB буферы с геометрией."""
    try:
        data = open(path, 'rb').read()
        pos = 0
        while True:
            p = data.find(BUFFER_MAGIC, pos)
            if p < 0: break
            if p + 8 > len(data):
                pos = p + 1; continue
            sz = struct.unpack_from('<I', data, p + 4)[0]
            # Буфер достаточного размера для IB или VB геометрии
            if sz >= 120:  # минимум ~20 треугольников * 6 байт
                return True
            pos = p + 1
    except:
        pass
    return False

def find_all_ires(root):
    """Рекурсивно находит .ires.compiled файлы с геометрией."""
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        for f in sorted(filenames):
            if f.endswith('.ires.compiled'):
                full = os.path.join(dirpath, f)
                if not has_geometry(full):
                    continue
                rel = os.path.relpath(full, root)
                name = rel.replace('.ires.compiled', '').replace(os.sep, '__')
                result.append((name, full))
    return result

files = find_all_ires(UNIVERSAL_DIR)

if not files:
    print("No .ires.compiled files found in {}".format(UNIVERSAL_DIR))
    sys.exit(1)

while True:
    print("=" * 60)
    print("Mafia DE Universal Exporter")
    print("=" * 60)
    print()
    print("Available files ({} total):".format(len(files)))
    print()

    # Группируем по подпапкам для удобства
    last_dir = None
    for i, (name, path) in enumerate(files):
        size_kb = os.path.getsize(path) // 1024
        # Определяем подпапку
        rel = os.path.relpath(path, UNIVERSAL_DIR)
        cur_dir = os.path.dirname(rel)
        if cur_dir != last_dir:
            print("  [{}]".format(cur_dir if cur_dir else 'root'))
            last_dir = cur_dir
        basename = os.path.basename(path).replace('.ires.compiled', '')
        print("  {:3d}. {:45s} ({} KB)".format(i+1, basename, size_kb))

    print()
    print("Enter number (1-{}), range (e.g. 1-5), 0 for ALL, or Q to quit:".format(len(files)))
    choice = input("> ").strip()

    if choice.lower() == 'q':
        print("Bye!")
        break

    to_export = []
    if choice == '0':
        to_export = list(range(len(files)))
    elif '-' in choice:
        parts = choice.split('-')
        try:
            start = int(parts[0]) - 1
            end = int(parts[1]) - 1
            to_export = list(range(max(0, start), min(len(files)-1, end)+1))
        except:
            print("Invalid range"); continue
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(files):
                to_export = [idx]
            else:
                print("Invalid number"); continue
        except:
            print("Invalid input"); continue

    print()
    print("Exporting {} file(s)...".format(len(to_export)))
    print()

    ok = 0; fail = 0; skip = 0
    for idx in to_export:
        name, path = files[idx]
        out_dir = os.path.join(OUT_BASE, name)
        print("[{}/{}] {}".format(to_export.index(idx)+1, len(to_export), name))
        ret = os.system('python {} "{}" "{}"'.format(SCRIPT, path, out_dir))
        if ret == 0:
            meshes = len(glob.glob(os.path.join(out_dir, '*.obj')))
            if meshes > 0:
                ok += 1
                print("  -> {} meshes → {}".format(meshes, out_dir))
            else:
                skip += 1
                print("  -> no meshes (skipped)")
        else:
            fail += 1
            print("  -> FAILED")
        print()

    print("=" * 60)
    print("Done: {} ok, {} no meshes, {} failed".format(ok, skip, fail))
    print("Output: {}".format(OUT_BASE))
    print()
    input("Press Enter to return to menu...")
    print()
