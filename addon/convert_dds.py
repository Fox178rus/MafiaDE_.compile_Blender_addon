"""
Standalone DDS to PNG converter.
Run via: python convert_dds.py <src_root> <dst_root>
Uses Pillow for full DDS support with alpha channel.
"""
import sys, os, re

def get_category(path):
    parts = set(re.split(r'[/\\]', path.lower()))
    if 'cars' in parts or 'cars_tuning' in parts: return 'cars'
    if 'weapons' in parts: return 'weapons'
    if 'basic_anim' in parts or 'combinables' in parts: return 'characters'
    return 'city'

def convert(src_root, dst_root):
    # Add user site-packages for Pillow
    try:
        import site
        up = site.getusersitepackages()
        if up not in sys.path:
            sys.path.insert(0, up)
    except Exception:
        pass

    from PIL import Image

    count = 0; errors = 0
    for root, dirs, files in os.walk(src_root):
        for fname in files:
            if not fname.lower().endswith('.dds'): continue
            src = os.path.join(root, fname)
            cat = get_category(root)
            cat_dir = os.path.join(dst_root, cat)
            os.makedirs(cat_dir, exist_ok=True)
            dst = os.path.join(cat_dir, os.path.splitext(fname)[0] + '.tga')
            try:
                img = Image.open(src)
                img.save(dst, 'TGA')
                count += 1
                print('OK: %s -> %s/%s' % (fname, cat, os.path.basename(dst)), flush=True)
            except Exception as e:
                errors += 1
                print('FAIL: %s: %s' % (fname, e), flush=True)
    print('DONE: %d converted, %d errors' % (count, errors), flush=True)
    return count, errors

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python convert_dds.py <src_root> <dst_root>')
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])
