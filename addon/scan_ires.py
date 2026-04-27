"""
Mafia DE .ires.compiled — универсальный сканер и экспортёр.
Запуск: python scan_ires.py <file.ires.compiled> [out_dir]
"""
import struct, sys, os, datetime
from collections import defaultdict

MIN_IB_TRIS   = 20    # минимум треугольников в меше
MIN_VB_VERTS  = 50    # минимум вершин в VB
KNOWN_STRIDES = [52, 28, 40, 48, 64, 32, 24, 20, 36, 16]
SCALE = 0.00390625    # 1/256

BUFFER_MAGIC = bytes([0x63, 0x77, 0xe0, 0x46])

# Известные IB размеры — эти буферы всегда IB, никогда не VB
KNOWN_IB_SIZES = {
    188994, 93432, 20922, 2142,       # bolt_ace
    171402, 84648, 17322, 2418,       # bolt_ace_pickup
    143700, 71844, 18270, 1620,       # bolt_delivery
    137184, 67608, 20598, 1584,       # bolt_model_b (137184 = LOD0!)
    180642, 93306, 27606,              # bolt_truck
}

# LOD принадлежность по (ib_size, first_idx)
# Из RenderDoc данных bolt_ace
MESH_LOD_MAP = {
    # IB_main (188994) — LOD0 и LOD0 (cabin отдельный draw call)
    (188994, 0):      (0, 0),
    (188994, 53610):  (0, 1),
    (188994, 58428):  (0, 2),
    (188994, 64716):  (0, 3),
    (188994, 65268):  (0, 4),
    (188994, 93375):  (0, 5),
    (188994, 93591):  (0, 6),
    (188994, 93867):  (0, 7),
    # IB_2046k (93432) — LOD1
    (93432,  0):      (1, 0),
    (93432,  32283):  (1, 1),
    (93432,  33819):  (1, 2),
    (93432,  37290):  (1, 3),
    (93432,  37548):  (1, 4),
    (93432,  46326):  (1, 5),
    # IB_3073k (20922) — LOD2
    (20922,  0):      (2, 0),
    (20922,  5664):   (2, 1),
    (20922,  5895):   (2, 2),
    (20922,  5910):   (2, 3),
    (20922,  5997):   (2, 4),
    # IB_3388k (2142) — LOD3
    (2142,   0):      (3, 0),
    (2142,   573):    (3, 1),
    # bolt_model_b
    (137184, 0):      (0, 0),
    (137184, 19644):  (0, 1),
    (137184, 34917):  (0, 2),
    (137184, 35565):  (0, 3),
    (137184, 67716):  (0, 4),
    (137184, 67992):  (0, 5),
    (67608,  0):      (1, 0),
    (67608,  16857):  (1, 1),
    (67608,  21234):  (1, 2),
    (67608,  21477):  (1, 3),
    (67608,  33252):  (1, 4),
    (67608,  33432):  (1, 9),
    (67608,  12744):  (1, 5),
    (67608,  7411):   (1, 6),
    (67608,  12654):  (1, 7),
    (20598,  0):      (2, 0),
    (20598,  3363):   (2, 1),
    (1584,   0):      (3, 0),
    (1584,   423):    (3, 1),
    # bolt_delivery
    (143700, 0):      (0, 0),
    (143700, 30726):  (0, 1),
    (143700, 42216):  (0, 2),
    (143700, 43278):  (0, 3),
    (143700, 70896):  (0, 4),
    (143700, 70992):  (0, 5),
    (143700, 71070):  (0, 6),
    (143700, 71166):  (0, 7),
    (71844,  0):      (1, 0),
    (71844,  24276):  (1, 1),
    (71844,  27096):  (1, 2),
    (71844,  27402):  (1, 3),
    (71844,  35682):  (1, 4),
    (71844,  35700):  (1, 5),
    (18270,  0):      (2, 0),
    (18270,  4110):   (2, 1),
    (1620,   0):      (3, 0),
    (1620,   411):    (3, 1),
    # bolt_truck
    (180642, 0):      (0, 0),
    (180642, 17838):  (0, 1),
    (180642, 36603):  (0, 2),
    (180642, 63783):  (0, 3),
    (180642, 64491):  (0, 4),
    (180642, 89265):  (0, 5),
    (93306,  0):      (1, 0),
    (93306,  16317):  (1, 1),
    (93306,  21099):  (1, 2),
    (93306,  38043):  (1, 3),
    (93306,  38313):  (1, 4),
    (93306,  46362):  (1, 5),
    (27606,  0):      (2, 0),
    (27606,  3816):   (2, 1),
    (27606,  4008):   (2, 2),
    (27606,  7605):   (2, 3),
    # bolt_ace_pickup
    (171402, 0):      (0, 0),
    (171402, 52923):  (0, 1),
    (171402, 56421):  (0, 2),
    (171402, 58947):  (0, 3),
    (171402, 59505):  (0, 4),
    (171402, 83577):  (0, 5),
    (171402, 83793):  (0, 6),
    (171402, 84717):  (0, 7),
    (84648,  0):      (1, 0),
    (84648,  28080):  (1, 1),
    (84648,  29670):  (1, 2),
    (84648,  32058):  (1, 3),
    (84648,  32283):  (1, 4),
    (84648,  40914):  (1, 5),
    (84648,  41064):  (1, 6),
    (17322,  0):      (2, 0),
    (17322,  5238):   (2, 1),
    (2418,   0):      (3, 0),
    (2418,   618):    (3, 1),
}

# Sub-mesh таблицы из RenderDoc (firstIndex, numIdx) для каждого IB размера
RDOC_SUBMESH_TABLES = {
    # bolt_ace
    188994: [(0,53610),(53610,4818),(58428,6288),(64716,552),(65268,28107),(93375,216),(93591,276),(93867,594)],
    93432:  [(0,32283),(32283,1536),(33819,3471),(37290,258),(37548,8778),(46326,54)],
    20922:  [(0,5664),(5664,231),(5895,15),(5910,87),(5997,4272)],
    2142:   [(0,573),(573,498)],
    # bolt_ace_pickup
    171402: [(0,52923),(52923,3498),(56421,2526),(58947,558),(59505,24072),(83577,216),(83793,924),(84717,984)],
    84648:  [(0,28080),(28080,1590),(29670,2388),(32058,225),(32283,8631),(40914,150),(41064,738),(41802,522)],
    17322:  [(0,5238),(5238,3201)],
    2418:   [(0,618),(618,591)],
    # bolt_delivery
    143700: [(0,30726),(30726,11490),(42216,1062),(43278,27618),(70896,96),(70992,78),(71070,96),(71166,684)],
    71844:  [(0,24276),(24276,2820),(27096,306),(27402,8280),(35682,18),(35700,222)],
    18270:  [(0,4110),(4110,4839),(8949,186)],
    1620:   [(0,411),(411,399)],
    # bolt_model_b
    137184: [(0,19644),(19644,15273),(34917,648),(35565,32151),(67716,276),(67992,600)],
    67608:  [(0,16857),(16857,4377),(21234,243),(21477,11775)],
    20598:  [(0,3363),(3363,6753),(10116,183)],
    1584:   [(0,423),(423,369)],
    # bolt_truck
    180642: [(0,17838),(17838,18765),(36603,27180),(63783,708),(64491,24774),(89265,210)],
    93306:  [(0,16317),(16317,4782),(21099,16944),(38043,270),(38313,8049),(46362,60)],
    27606:  [(0,3816),(3816,192),(4008,3597),(7605,6054)],
}

# ─────────────────────────────────────────────────────────────────────────────
# Декодирование вершин
# ─────────────────────────────────────────────────────────────────────────────

def decode_pos(data, vb_off, vi, stride):
    """Shader formula: x = b[0]/256 + b[1], y = b[2]/256 + b[3], z = b[4]/256 + b[5]"""
    off = vb_off + vi * stride
    if off + 6 > len(data): return 0.0, 0.0, 0.0
    b = data[off:off+6]
    x = b[0] * SCALE + b[1]
    y = b[2] * SCALE + b[3]
    z = b[4] * SCALE + b[5]
    return x, y, z

def decode_pos_snorm(data, vb_off, vi, stride):
    off = vb_off + vi * stride
    if off + 4 > len(data): return 0.0, 0.0, 0.0
    b = data[off:off+4]
    def s(v): return (v if v < 128 else v - 256) / 127.0
    return s(b[0]), s(b[1]), s(b[2])

def decode_split_flag(data, vb_off, vi, stride):
    """
    Читает флаг split из VB данных.
    Для stride=48: бит 7 byte[5] — если 0, вершина из нижней половины (+128 по Z).
    """
    if stride != 48:
        return None
    off = vb_off + vi * stride + 5
    if off >= len(data):
        return None
    return (data[off] >> 7) & 1  # 0=нижняя (нужен +128), 1=верхняя

def decode_uv(data, vb_off, vi, stride, uv_off):
    off = vb_off + vi * stride + uv_off
    if off + 4 > len(data): return 0.0, 0.0
    try:
        u, v = struct.unpack_from('<2e', data, off)
        if not (-1000 < u < 1000 and -1000 < v < 1000): return 0.0, 0.0
        # stride=48: стандартная инверсия V
        if stride == 48:
            return u, 1.0 - v
        return u, 1.0 - v
    except: return 0.0, 0.0

UV_OFFSETS = {52: 36, 28: 20, 40: 36, 48: 16, 64: 44, 32: 20, 24: 16, 20: 16, 36: 20}
def find_uv_offset(stride): return UV_OFFSETS.get(stride, stride - 4)

# ─────────────────────────────────────────────────────────────────────────────
# Поиск буферов
# ─────────────────────────────────────────────────────────────────────────────

def is_vb_candidate(data, off, stride, vc):
    """
    Проверяет что данные выглядят как VB геометрии.
    Поддерживает два формата: uint8 (shader formula) и float32.
    """
    if BUFFER_MAGIC in data[off:off+256]: return False

    # Проверяем float32 формат (первые 3 float = x,y,z)
    if stride >= 12:
        try:
            floats = [struct.unpack_from('<f', data, off + i*stride)[0] for i in range(min(8, vc))]
            if all(-1000 < f < 1000 and f != 0.0 for f in floats):
                # Проверяем разнообразие
                if len(set(round(f, 1) for f in floats)) >= 3:
                    return True
        except: pass

    # Проверяем uint8 shader formula формат
    xs = set(); zs = set()
    for vi in range(min(32, vc)):
        base = off + vi * stride
        if base + 4 > len(data): return False
        b = data[base:base+4]
        xs.add(b[0]); zs.add(b[2])
    if len(xs) < 2 or len(zs) < 2: return False

    # Не последовательные uint16
    if stride >= 2 and vc >= 8:
        vals = struct.unpack_from('<8H', data, off)
        diffs = [vals[i+1] - vals[i] for i in range(7)]
        if all(0 <= d <= 4 for d in diffs):
            return False

    # stride < 28 с нулевыми float — не VB
    if stride < 28:
        floats = struct.unpack_from('<{}f'.format(stride // 4), data, off)
        if all(abs(f) < 0.001 for f in floats):
            return False

    return True

def find_all_buffers(data):
    """
    Находит все буферы через BUFFER_MAGIC.
    Классифицирует каждый как VB, IB или unknown.
    Возвращает список dict отсортированный по data_off.
    """
    size = len(data)
    buffers = []
    pos = 0
    while True:
        p = data.find(BUFFER_MAGIC, pos)
        if p < 0: break
        if p + 8 > size:
            pos = p + 1; continue
        buf_size = struct.unpack_from('<I', data, p + 4)[0]
        data_off = p + 8
        if buf_size > 0 and data_off + buf_size <= size:
            buffers.append({'magic': p, 'off': data_off, 'size': buf_size,
                            'type': 'unknown', 'stride': 0, 'verts': 0, 'max_vi': 0})
        pos = p + 1

    for b in buffers:
        off = b['off']; sz = b['size']
        # Если размер в KNOWN_IB_SIZES — это точно IB, не проверяем как VB
        if sz in KNOWN_IB_SIZES:
            if sz % 2 == 0 and sz >= MIN_IB_TRIS * 3 * 2:
                n = sz // 2
                vals = struct.unpack_from('<{}H'.format(n), data, off)
                mx = max(vals)
                if 50 <= mx <= 65000:
                    b['type'] = 'IB'; b['max_vi'] = mx; b['n_idx'] = sz // 2
            continue

        # Сначала пробуем IB — приоритет над VB
        # Критерий IB: max_vi < n_idx (вершин меньше чем индексов)
        if sz % 2 == 0 and sz >= MIN_IB_TRIS * 3 * 2:
            n = sz // 2
            vals = struct.unpack_from('<{}H'.format(n), data, off)
            mx = max(vals)
            if 50 <= mx <= 65000 and mx < n:
                b['type'] = 'IB'; b['max_vi'] = mx; b['n_idx'] = n
                continue

        # Пробуем VB — сохраняем все подходящие stride варианты
        vb_candidates = []
        for stride in KNOWN_STRIDES:
            if sz % stride != 0: continue
            vc = sz // stride
            if vc < MIN_VB_VERTS: continue
            if is_vb_candidate(data, off, stride, vc):
                vb_candidates.append((stride, vc))
        # Явно добавляем все кратные stride варианты которые дают разумное vc
        for stride in KNOWN_STRIDES:
            if sz % stride != 0: continue
            vc = sz // stride
            if vc < MIN_VB_VERTS: continue
            if (stride, vc) not in vb_candidates:
                ok = True
                for vi in range(min(4, vc)):
                    base = off + vi * stride
                    if base + 2 > len(data): ok = False; break
                    if all(data[base+j] == 0 for j in range(min(6, stride))):
                        ok = False; break
                if ok:
                    vb_candidates.append((stride, vc))
        # Убираем дубликаты, сохраняем порядок
        seen_strides = set()
        vb_candidates_dedup = []
        for s, v in vb_candidates:
            if s not in seen_strides:
                seen_strides.add(s)
                vb_candidates_dedup.append((s, v))
        vb_candidates = vb_candidates_dedup
        if vb_candidates:
            b['type'] = 'VB'; b['stride'] = vb_candidates[0][0]; b['verts'] = vb_candidates[0][1]
            b['vb_candidates'] = vb_candidates
        # Fallback IB если VB не нашли
        if b['type'] == 'unknown' and sz % 2 == 0 and sz >= MIN_IB_TRIS * 3 * 2:
            n = sz // 2
            vals = struct.unpack_from('<{}H'.format(n), data, off)
            mx = max(vals)
            if 50 <= mx <= 65000:
                b['type'] = 'IB'; b['max_vi'] = mx; b['n_idx'] = sz // 2

    # Пост-обработка: переклассифицируем IB как VB если размер == (max_vi+1)*stride
    ib_list_post = [b for b in buffers if b['type'] == 'IB']
    for ib in ib_list_post:
        needed = ib['max_vi'] + 1
        for other in ib_list_post:
            if other is ib: continue
            sz = other['size']
            if sz % needed == 0:
                s = sz // needed
                if s in KNOWN_STRIDES and 10 <= needed <= 100000:
                    other['type'] = 'VB'
                    other['stride'] = s
                    other['verts'] = needed
                    other['vb_candidates'] = [(s, needed)]
                    break

    return sorted(buffers, key=lambda b: b['off'])

# ─────────────────────────────────────────────────────────────────────────────
# Sub-mesh таблица
# ─────────────────────────────────────────────────────────────────────────────

def find_best_submesh_table(data, ib_size=None):
    """
    Универсальный поиск sub-mesh таблицы.
    Форматы: marker=49 stride=16, marker=53 stride=16, stride=12 [cumul][idx][1].
    Возвращает список (firstIndex, count) пар.
    """
    size = len(data)
    max_cumul = (ib_size // 2) if ib_size else 500000
    best_entries = []

    # Метод 1: marker=49, stride=16: [4b][49][cumul][vc]
    MARKER49 = struct.pack('<I', 49)
    visited = set()
    pos = 0
    while True:
        p = data.find(MARKER49, pos)
        if p < 0: break
        if p < 4: pos = p+1; continue
        ts = p - 4
        if ts in visited: pos = p+1; continue
        entries = []; off = ts; prev = 0
        while off + 16 <= size and len(entries) < 200:
            mk = struct.unpack_from('<I', data, off+4)[0]
            if mk != 49: break
            cumul = struct.unpack_from('<I', data, off+8)[0]
            vc    = struct.unpack_from('<I', data, off+12)[0]
            if cumul <= prev or cumul > max_cumul: break
            if vc > 100000: break
            entries.append((cumul, vc))
            prev = cumul; off += 16
        if len(entries) > len(best_entries): best_entries = entries
        visited.add(ts); pos = p+1

    # Метод 2: marker=53, stride=16: [cumul][vc][idx][53]
    MARKER53 = struct.pack('<I', 53)
    pos = 0
    while True:
        p = data.find(MARKER53, pos)
        if p < 0: break
        if p < 12: pos = p+1; continue
        ts = p - 12
        entries = []; off = ts; prev = 0
        while off + 16 <= size and len(entries) < 200:
            cumul = struct.unpack_from('<I', data, off)[0]
            vc    = struct.unpack_from('<I', data, off+4)[0]
            idx   = struct.unpack_from('<I', data, off+8)[0]
            mk    = struct.unpack_from('<I', data, off+12)[0]
            if mk != 53: break
            if cumul <= prev or cumul > max_cumul: break
            if idx > 50 or vc > 100000: break
            entries.append((cumul, vc))
            prev = cumul; off += 16
        if len(entries) > len(best_entries): best_entries = entries
        pos = p+1

    # Метод 3: stride=12: [cumul][idx][1] начиная с cumul=0
    # Быстрый поиск через data.find() нулевого cumul
    ZERO = b'\x00\x00\x00\x00'
    pos = 0
    while True:
        p = data.find(ZERO, pos)
        if p < 0: break
        if p + 12 <= size:
            i0 = struct.unpack_from('<I', data, p+4)[0]
            o0 = struct.unpack_from('<I', data, p+8)[0]
            if o0 in (1,2,3) and 1 <= i0 <= 20:
                entries = []; off = p; prev = -1
                while off + 12 <= size and len(entries) < 200:
                    cumul = struct.unpack_from('<I', data, off)[0]
                    idx   = struct.unpack_from('<I', data, off+4)[0]
                    one   = struct.unpack_from('<I', data, off+8)[0]
                    if one not in (1,2,3,4,5): break
                    if cumul < prev or cumul > max_cumul: break
                    if idx > 50: break
                    entries.append((cumul, idx))
                    prev = cumul; off += 12
                if len(entries) > len(best_entries):
                    best_entries = [(c, i) for c, i in entries]
        pos = p + 1

    if not best_entries: return []

    # Конвертируем cumulative → (firstIndex, count)
    result = []
    prev = 0
    for cumul, _ in best_entries:
        count = cumul - prev
        if count >= 15:
            result.append((prev, count))
        prev = cumul
    # Добавляем хвост — проверяем есть ли ещё записи после последней
    if ib_size and prev < ib_size // 2:
        # Ищем следующую запись в файле после последней найденной
        last_cumul = best_entries[-1][0]
        last_b = struct.pack('<I', last_cumul)
        search_pos = 0
        while True:
            p = data.find(last_b, search_pos)
            if p < 0: break
            # Проверяем что это наша таблица (следующая запись должна быть > last_cumul)
            next_off = p + 12
            if next_off + 12 <= len(data):
                next_cumul = struct.unpack_from('<I', data, next_off)[0]
                next_idx   = struct.unpack_from('<I', data, next_off+4)[0]
                next_one   = struct.unpack_from('<I', data, next_off+8)[0]
                if (last_cumul < next_cumul <= ib_size // 2 and
                    next_idx <= 50 and next_one in range(1, 10)):
                    # Нашли продолжение — добавляем
                    count = next_cumul - last_cumul
                    if count >= 15:
                        result.append((last_cumul, count))
                    # Проверяем ещё одну запись
                    next_off2 = next_off + 12
                    if next_off2 + 12 <= len(data):
                        nc2 = struct.unpack_from('<I', data, next_off2)[0]
                        ni2 = struct.unpack_from('<I', data, next_off2+4)[0]
                        no2 = struct.unpack_from('<I', data, next_off2+8)[0]
                        if (next_cumul < nc2 <= ib_size // 2 and
                            ni2 <= 50 and no2 in range(1, 10)):
                            count2 = nc2 - next_cumul
                            if count2 >= 15:
                                result.append((next_cumul, count2))
                    break
            search_pos = p + 1
        # Финальный хвост если ещё осталось
        if result and result[-1][0] + result[-1][1] < ib_size // 2:
            last_end = result[-1][0] + result[-1][1]
            tail = ib_size // 2 - last_end
            if tail >= 15:
                result.append((last_end, tail))
    return result

# ─────────────────────────────────────────────────────────────────────────────
# Разбивка IB на sub-mesh
# ─────────────────────────────────────────────────────────────────────────────

def tris_from_chunk(chunk, max_vi):
    """Строит список треугольников из chunk uint16, фильтруя по max_vi."""
    tris = []
    n = (len(chunk) // 3) * 3
    for t in range(0, n, 3):
        i0, i1, i2 = chunk[t], chunk[t+1], chunk[t+2]
        if i0 == i1 or i1 == i2 or i0 == i2: continue
        if i0 <= max_vi and i1 <= max_vi and i2 <= max_vi:
            tris.append((i0, i1, i2))
    return tris

def split_by_table(all_vals, max_vi, submesh_counts):
    """Разбивает IB по таблице sub-mesh. submesh_counts = список (firstIndex, count)."""
    blocks = []
    for first_idx, count in submesh_counts:
        if first_idx + count > len(all_vals): continue
        chunk = all_vals[first_idx:first_idx+count]
        # Используем реальный max из chunk (не глобальный max_vi)
        chunk_max = max(chunk) if chunk else 0
        tris = tris_from_chunk(chunk, chunk_max)
        if len(tris) >= MIN_IB_TRIS:
            mx = max(max(t) for t in tris)
            mn = min(min(t) for t in tris)
            blocks.append((tris, mn, mx, first_idx))
    return blocks

def split_by_running_max(all_vals, max_vi, min_stable=1500):
    """
    Fallback: разбивает IB по скачкам prefix_max.
    Работает для машин без sub-mesh таблицы.
    """
    n = len(all_vals)
    if n < MIN_IB_TRIS * 3: return []

    # prefix_max
    pm = [0] * n
    pm[0] = all_vals[0]
    for i in range(1, n):
        pm[i] = max(pm[i-1], all_vals[i])

    boundaries = [0]
    last_change = 0
    for i in range(1, n):
        if pm[i] > pm[i-1]:
            if i - last_change >= min_stable and pm[i-1] > MIN_VB_VERTS:
                boundaries.append(i)
            last_change = i
    boundaries.append(n)

    blocks = []
    for k in range(len(boundaries)-1):
        lo = boundaries[k]; hi = boundaries[k+1]
        count = ((hi - lo) // 3) * 3
        if count < MIN_IB_TRIS * 3: continue
        chunk = all_vals[lo:lo+count]
        tris = tris_from_chunk(chunk, max_vi)
        if len(tris) >= MIN_IB_TRIS:
            mx = max(max(t) for t in tris)
            mn = min(min(t) for t in tris)
            blocks.append((tris, mn, mx))
    return blocks

def split_ib(data, ib_off, ib_size, max_vi, submesh_counts):
    """Разбивает IB буфер на sub-mesh блоки. Возвращает (tris, vi_lo, vi_hi, first_idx)."""
    n = ib_size // 2
    all_vals = struct.unpack_from('<{}H'.format(n), data, ib_off)

    # Метод 1: sub-mesh таблица из файла (приоритет над RDOC)
    # Проверяем что таблица начинается с fi=0 (иначе ложная таблица)
    if submesh_counts and submesh_counts[0][0] == 0:
        blocks = split_by_table(all_vals, max_vi, submesh_counts)
        if blocks: return blocks

    # Метод 0: таблица из RenderDoc (fallback если файловая не нашлась)
    if ib_size in RDOC_SUBMESH_TABLES:
        blocks = []
        for first_idx, count in RDOC_SUBMESH_TABLES[ib_size]:
            if first_idx + count > n: continue
            chunk = all_vals[first_idx:first_idx+count]
            tris = tris_from_chunk(chunk, max_vi)
            if len(tris) >= MIN_IB_TRIS:
                mx = max(max(t) for t in tris)
                mn = min(min(t) for t in tris)
                blocks.append((tris, mn, mx, first_idx))
        if blocks: return blocks

    # Метод 2: весь буфер как один меш
    tris = tris_from_chunk(all_vals, max_vi)
    if len(tris) >= MIN_IB_TRIS:
        mx = max(max(t) for t in tris)
        mn = min(min(t) for t in tris)
        return [(tris, mn, mx, 0)]

    return []

# ─────────────────────────────────────────────────────────────────────────────
# Auto-merge (исправление split по оси)
# ─────────────────────────────────────────────────────────────────────────────

def find_gap(values, min_gap=20.0):
    sv = sorted(set(round(v, 1) for v in values))
    best = None; best_size = min_gap
    for i in range(1, len(sv)):
        gap = sv[i] - sv[i-1]
        if gap > best_size:
            best_size = gap
            best = (sv[i-1] + sv[i]) / 2.0, gap
    return best

def compute_shift(verts, snorm_verts, is_far, axis):
    snorm_map = defaultdict(list)
    for i, sn in enumerate(snorm_verts):
        key = (round(sn[0],3), round(sn[1],3), round(sn[2],3))
        snorm_map[key].append(i)
    deltas = []
    for indices in snorm_map.values():
        far   = [i for i in indices if is_far[i]]
        close = [i for i in indices if not is_far[i]]
        if far and close:
            deltas.append(verts[close[0]][axis] - verts[far[0]][axis])
    if not deltas: return None, 0
    deltas.sort()
    return deltas[len(deltas)//2], len(deltas)

def merge_by_flag(data, vb_off, used_vi, verts, stride):
    """
    Использует бит 7 high byte каждой координаты для точного определения split.
    flag=0 → нижняя половина (+128), flag=1 → верхняя (без изменений).
    Для stride=28: применяется по X, Y и Z независимо.
    Для других stride: только по Z.
    """
    merged = list(verts)
    n_shifted = 0
    for i, vi in enumerate(used_vi):
        off = vb_off + vi * stride
        if off + 6 > len(data): continue
        if stride == 28:
            # stride=28: X в bytes 0-1, Z в bytes 4-5
            # fz=1 — вершины смещены на +128 по Z
            fx = (data[off+1] >> 7) & 1
            fz = (data[off+5] >> 7) & 1
            v = list(merged[i])
            changed = False
            if fz == 1: v[2] -= 128.0; changed = True
            if changed:
                merged[i] = tuple(v)
                n_shifted += 1
        elif stride == 24:
            # fz=1 — вершины смещены на +128 по Z, сдвигаем обратно
            fz = (data[off+5] >> 7) & 1
            if fz == 1:
                v = list(merged[i]); v[2] -= 128.0; merged[i] = tuple(v)
                n_shifted += 1
        else:
            # Другие stride: только Z (byte[5] bit7)
            if off + 6 > len(data): continue
            flag = (data[off+5] >> 7) & 1
            if flag == 0:
                v = list(merged[i]); v[2] += 128.0; merged[i] = tuple(v)
                n_shifted += 1
    if n_shifted > 0:
        print("  Merge-by-flag stride={} ({} far verts)".format(stride, n_shifted))
    return merged

def auto_merge(verts, snorm_verts, stride=52):
    """
    stride=52 (машины): merge даже без snorm seam
    stride!=52 (объекты): только с snorm seam + проверки
    """
    merged = list(verts)
    is_car = (stride == 52)
    best_axis = None; best_gap = 8.0; best_threshold = 0; best_shift = None

    for axis in [2, 0, 1]:
        vals = [v[axis] for v in merged]
        result = find_gap(vals, min_gap=8.0)
        if result is None: continue
        threshold, gap_size = result
        if axis != 2 and best_axis == 2: continue
        if gap_size <= best_gap and axis != 2: continue

        is_far_tmp = [v[axis] < threshold for v in merged]
        shift, n_seam = compute_shift(merged, snorm_verts, is_far_tmp, axis)

        if shift is not None and n_seam >= 5:
            if abs(shift) < 5.0: continue
            # Проверяем что far+shift не выходит за 258, но если нет перекрытия с close — ок
            far_vals_check = [merged[i][axis] for i in range(len(merged)) if is_far_tmp[i]]
            close_vals_check = [merged[i][axis] for i in range(len(merged)) if not is_far_tmp[i]]
            if far_vals_check and close_vals_check:
                # Если far_max+shift < close_min — нет перекрытия, merge правильный
                if max(far_vals_check) + abs(shift) < min(close_vals_check):
                    pass  # ok
                elif max(far_vals_check) + abs(shift) > 258:
                    continue  # выходит за 258 И есть перекрытие — блокируем
            far_vals = [merged[i][axis] for i in range(len(merged)) if is_far_tmp[i]]
            close_vals = [merged[i][axis] for i in range(len(merged)) if not is_far_tmp[i]]
            if far_vals and close_vals:
                refined_threshold = (max(far_vals) + min(close_vals)) / 2.0
                is_far_tmp = [v[axis] < refined_threshold for v in merged]
                shift2, n_seam2 = compute_shift(merged, snorm_verts, is_far_tmp, axis)
                if shift2 is not None and n_seam2 >= 3 and abs(shift2) >= 5.0:
                    threshold = refined_threshold; shift = shift2; n_seam = n_seam2
            best_gap = gap_size; best_axis = axis
            best_threshold = threshold; best_shift = shift
        else:
            if is_car:
                # Машины: merge без snorm seam
                # Проверяем что это реальный split: close_min > far_max (gap между группами)
                far_check = [merged[i][axis] for i in range(len(merged)) if is_far_tmp[i]]
                close_check = [merged[i][axis] for i in range(len(merged)) if not is_far_tmp[i]]
                if far_check and close_check and min(close_check) <= max(far_check):
                    continue  # нет gap — не split
                best_gap = gap_size; best_axis = axis
                best_threshold = threshold; best_shift = 128.0
            else:
                # Объекты: пропускаем если нет snorm seam
                continue

    if best_axis is None or best_shift is None:
        # Fallback: gap не найден — пробуем через snorm напрямую по Z
        # Ищем пары вершин с одинаковым snorm но разным Z (delta ~128)
        snorm_map = defaultdict(list)
        for i, sn in enumerate(snorm_verts):
            key = (round(sn[0],2), round(sn[1],2), round(sn[2],2))
            snorm_map[key].append(i)
        deltas = []
        for indices in snorm_map.values():
            if len(indices) >= 2:
                zvals = [merged[i][2] for i in indices]
                mn, mx = min(zvals), max(zvals)
                if 100 < mx - mn < 160:
                    deltas.append(mx - mn)
        if deltas:
            deltas.sort()
            median_delta = deltas[len(deltas)//2]
            if abs(median_delta - 128.0) < 10:
                # Проверяем через compute_shift что seam реальный
                zvals_all = [v[2] for v in merged]
                threshold_fb = (min(zvals_all) + max(zvals_all)) / 2.0
                is_far_fb = [v[2] < threshold_fb for v in merged]
                shift_fb, n_seam_fb = compute_shift(merged, snorm_verts, is_far_fb, 2)
                if n_seam_fb < 5:
                    return merged  # нет реального seam — не split
                # Проверяем что far вершины после +128 не выходят за 255
                far_z_vals = [merged[i][2] for i in range(len(merged)) if is_far_fb[i]]
                if far_z_vals and max(far_z_vals) + 128.0 > 258:
                    return merged  # не split — объект просто большой
                # Split найден через snorm — ищем первый gap >= 0.2 выше threshold
                # но ищем gap который разделяет на ~128 единиц (не маленький gap внутри группы)
                zvals_all = [v[2] for v in merged]
                threshold = (min(zvals_all) + max(zvals_all)) / 2.0
                sorted_z = sorted(set(round(z, 4) for z in zvals_all))
                # Ищем gap >= 0.2 выше threshold, но пропускаем gap если после него
                # следующее значение тоже должно быть в нижней группе (delta с парой ~128)
                for k in range(len(sorted_z)-1):
                    if sorted_z[k] >= threshold:
                        gap = sorted_z[k+1] - sorted_z[k]
                        if gap >= 0.2:
                            # Проверяем: значение после gap — оно из верхней половины?
                            # Если sorted_z[k+1] + 128 > max(zvals_all) — это верхняя половина
                            if sorted_z[k+1] + 128.0 > max(zvals_all) + 1:
                                threshold = (sorted_z[k] + sorted_z[k+1]) / 2.0
                                break
                            # Иначе продолжаем искать
                is_far = [v[2] < threshold for v in merged]
                n_far = sum(is_far)
                if 0 < n_far < len(merged):
                    print("  Auto-merge (snorm fallback) axis=Z shift=128.0 ({} far verts)".format(n_far))
                    for i in range(len(merged)):
                        if is_far[i]:
                            v = list(merged[i]); v[2] += 128.0; merged[i] = tuple(v)
        return merged

    is_far = [v[best_axis] < best_threshold for v in merged]
    n_far = sum(is_far)
    if n_far == 0 or n_far == len(merged):
        return merged  # все в одной группе — не split

    print("  Auto-merge axis={} gap={:.1f} shift={:.4f} n_seam={} ({} far verts)".format(
        best_axis, best_gap, best_shift, 0, n_far))
    for i in range(len(merged)):
        if is_far[i]:
            v = list(merged[i]); v[best_axis] += best_shift; merged[i] = tuple(v)
    return merged

# ─────────────────────────────────────────────────────────────────────────────
# Экспорт OBJ
# ─────────────────────────────────────────────────────────────────────────────

def export_obj(data, tris, vb_off, stride, out_path, name, offset=(0,0,0), global_z_center=None, mat_name=None):
    if not tris: return 0, 0, (0,0),(0,0),(0,0)
    used_vi = sorted(set(v for t in tris for v in t))
    remap = {vi: i for i, vi in enumerate(used_vi)}
    uv_off = find_uv_offset(stride)

    verts       = [decode_pos(data, vb_off, vi, stride) for vi in used_vi]
    snorm_verts = [decode_pos_snorm(data, vb_off, vi, stride) for vi in used_vi]
    uvs         = [decode_uv(data, vb_off, vi, stride, uv_off) for vi in used_vi]
    verts = merge_by_flag(data, vb_off, used_vi, verts, stride)

    # stride=32 и stride=24: центрируем по собственному bbox, глобальный offset не нужен
    if stride in (32, 24):
        xs_loc = [v[0] for v in verts]
        ys_loc = [v[1] for v in verts]
        zs_loc = [v[2] for v in verts]
        xc_loc = (min(xs_loc) + max(xs_loc)) / 2.0
        yc_loc = (min(ys_loc) + max(ys_loc)) / 2.0
        zc_loc = (min(zs_loc) + max(zs_loc)) / 2.0
        verts = [(v[0]-xc_loc, v[1]-yc_loc, v[2]-zc_loc) for v in verts]
        offset = (0, 0, 0)

    # Если меш без gap но его Z_raw значительно ниже центра машины — сдвигаем +128
    if global_z_center is not None and stride not in (32, 24):
        z_vals = [v[2] for v in verts]
        z_max = max(z_vals)
        # Если весь меш ниже центра на 50+ единиц — это несмерджённый split
        if z_max < global_z_center - 50:
            verts = [(v[0], v[1], v[2] + 128) for v in verts]
            print("  Force-shift +128 Z (z_max={:.1f} < center-50={:.1f})".format(
                z_max, global_z_center - 50))

    # Rotate X -90°: (x,y,z) -> (x, z, -y), потом центрируем
    cx, cy, cz = offset
    verts = [(v[0]-cx, v[2]-cy, -v[1]-cz) for v in verts]

    # Фильтруем артефактные треугольники между несвязными компонентами
    import math
    def elen(i, j):
        a, b = verts[i], verts[j]
        return math.sqrt((a[0]-b[0])**2+(a[1]-b[1])**2+(a[2]-b[2])**2)

    from collections import defaultdict
    adj = defaultdict(set)
    for t in tris:
        ri,rj,rk = remap[t[0]],remap[t[1]],remap[t[2]]
        adj[ri].update([rj,rk]); adj[rj].update([ri,rk]); adj[rk].update([ri,rj])

    comp = {}; cid = 0
    for s in range(len(used_vi)):
        if s in comp: continue
        q = [s]
        while q:
            v = q.pop()
            if v in comp: continue
            comp[v] = cid
            q.extend(nb for nb in adj[v] if nb not in comp)
        cid += 1

    clean_faces = [(remap[t[0]]+1, remap[t[1]]+1, remap[t[2]]+1) for t in tris]

    if not clean_faces:
        return 0, 0, (0,0),(0,0),(0,0)

    with open(out_path, 'w') as f:
        f.write('# {} vb_off={} stride={} vi={}-{}\n'.format(
            name, vb_off, stride, used_vi[0], used_vi[-1]))
        if mat_name:
            f.write('mtllib {}.mtl\n'.format(mat_name))
            f.write('usemtl {}\n'.format(mat_name))
        for v in verts: f.write('v {:.6f} {:.6f} {:.6f}\n'.format(*v))
        for uv in uvs:  f.write('vt {:.6f} {:.6f}\n'.format(*uv))
        for fc in clean_faces: f.write('f {0}/{0} {1}/{1} {2}/{2}\n'.format(*fc))

    xs=[v[0] for v in verts]; ys=[v[1] for v in verts]; zs=[v[2] for v in verts]
    return len(verts), len(clean_faces), (min(xs),max(xs)), (min(ys),max(ys)), (min(zs),max(zs))

MTL_JSON = ''  # Set via set_mtl_json() or leave empty to skip material lookup
_mtl_db = None  # lazy-loaded

def set_mtl_json(path):
    """Set path to default_parsed.json (parsed Mafia DE material database)."""
    global MTL_JSON, _mtl_db
    MTL_JSON = path
    _mtl_db = None  # reset cache

def _load_mtl_db():
    """Загружает MTL базу (lazy)."""
    global _mtl_db
    if _mtl_db is not None:
        return _mtl_db
    if not os.path.exists(MTL_JSON):
        _mtl_db = {}
        return _mtl_db
    import json
    data = json.load(open(MTL_JSON, encoding='utf-8'))
    # Индекс: имя → материал
    _mtl_db = {m['name']: m for m in data}
    return _mtl_db

def get_submesh_materials(building_name, n_meshes):
    """
    Возвращает список имён материалов (diffuse текстур) для каждого sub-mesh.
    Использует MTL базу и семантику суффиксов имён материалов.

    Порядок назначения (по убыванию размера меша):
      mesh0 (самый большой) → основные стены (без суффикса или _v1.._v9)
      mesh1                 → кирпич/детали (_bricks, _plaster, _floor, _top)
      mesh2                 → keyed детали (_keyed)
      остальные             → повторяем основной материал

    Возвращает список из n_meshes строк (имя diffuse .dds файла).
    """
    import re as _re
    db = _load_mtl_db()
    if not db:
        return [None] * n_meshes

    # Базовый префикс: убираем суффикс версии
    base = _re.sub(r'_v\d.*$', '', building_name)

    # Собираем все материалы с этим префиксом
    candidates = [m for name, m in db.items() if name.startswith(base)]
    if not candidates:
        return [None] * n_meshes

    def get_diffuse(mat):
        """Get best diffuse texture. Prefer texture matching building base name."""
        t0 = None
        for t in mat['textures']:
            if t['id'] == 'T000':
                t0 = t['name']
                break
        if not t0:
            return None
        # If T000 doesn't start with building base, look for a better slot
        # e.g. lh_02_house_a_v1_keyed has T000=bc_03_... but lh_02_... is in another slot
        if not t0.startswith(base):
            # First: check other texture slots
            for t in mat['textures']:
                if t['name'].startswith(base) and t['name'].endswith('---d.dds'):
                    return t['name']
            # Second: try mat_name---d.dds directly (e.g. lh_02_house_a_v1_keyed---d.dds)
            candidate = mat['name'] + '---d.dds'
            if os.path.exists(os.path.join(TEX_DB_LOD0, candidate)):
                return candidate
        return t0

    # Классифицируем по суффиксу
    main_mats   = []  # основные стены
    bricks_mats = []  # кирпич
    keyed_mats  = []  # keyed детали
    other_mats  = []  # прочие

    for m in candidates:
        name = m['name']
        suffix = name[len(base):]  # всё после базового префикса
        if any(s in suffix for s in ['_bricks', '_plaster', '_stone', '_concrete']):
            bricks_mats.append(m)
        elif '_keyed' in suffix:
            keyed_mats.append(m)
        elif _re.match(r'^(_v\d+)?(_\d+)?$', suffix):
            # Точное совпадение или _v1, _v1_01 и т.д.
            main_mats.append(m)
        else:
            other_mats.append(m)

    # Если нет основного — берём первый попавшийся
    if not main_mats:
        main_mats = candidates[:1]

    # Точное совпадение имени здания имеет приоритет
    exact = [m for m in main_mats if m['name'] == building_name]
    if exact:
        main_mats = exact + [m for m in main_mats if m['name'] != building_name]

    # Строим список по порядку мешей
    result = []
    # Для mesh0 — основные стены
    # Для mesh1..N — кирпич/детали по порядку, потом keyed
    secondary = bricks_mats + other_mats + keyed_mats
    for i in range(n_meshes):
        if i == 0:
            result.append(get_diffuse(main_mats[0]))
        elif i - 1 < len(secondary):
            result.append(get_diffuse(secondary[i - 1]))
        else:
            result.append(get_diffuse(main_mats[0]))

    return result


def extract_material_name(data):
    """Извлекает имя материала/текстуры из ires файла."""
    import re
    # Ищем во всём файле (nomesh файлы содержат имя дальше 8KB)
    strings = re.findall(b'[\x20-\x7e]{5,}', data)
    for s in strings:
        s = s.decode('ascii', 'ignore')
        # Имя вида lh_XX_yyy или bc_XX_yyy — это имя текстуры/материала
        if re.match(r'^(lh|bc|dlc|env|prop|uni)_[a-z0-9_]{3,}$', s, re.IGNORECASE):
            # Исключаем служебные строки
            if not any(x in s for x in ['m_', 'GENR', 'KL2T', 'tXn3']):
                return s
    return None

TEX_BASE = ''      # Set via set_tex_base() — root of extracted SDS city folder
TEX_DB_LOD0 = ''  # Set via set_tex_db() — folder with pre-built LOD0/D textures

def set_tex_base(path):
    """Set root path of extracted SDS city folder."""
    global TEX_BASE, _tex_index
    TEX_BASE = path
    _tex_index = {}

def set_tex_db(path):
    """Set path to pre-built texture database (LOD0/D folder)."""
    global TEX_DB_LOD0
    TEX_DB_LOD0 = path

_tex_index = {}  # имя файла -> полный путь (приоритет: lost_heaven_tex > lod1)

def _build_tex_index(district=None):
    """Строит индекс DDS файлов для нужного района."""
    global _tex_index
    base = TEX_BASE
    if not os.path.exists(base):
        return
    # Определяем папки для поиска по префиксу района
    search_dirs = set()
    if district:
        for d in os.listdir(base):
            if (d.startswith(district) or
                d.startswith('lost_heaven_tex_' + district) or
                'lost_heaven_tex_merged' in d):
                search_dirs.add(os.path.join(base, d))
    # Всегда добавляем lod0/lod1 текущего района
    for sdir in list(search_dirs):
        search_dirs.add(sdir)
    if not search_dirs:
        # Fallback — только lod0/lod1 папки (не все)
        for d in os.listdir(base):
            if 'lod0' in d or 'lod1' in d or 'tex' in d:
                search_dirs.add(os.path.join(base, d))
    for sdir in search_dirs:
        if not os.path.isdir(sdir):
            continue
        try:
            for f in os.listdir(sdir):
                if f.endswith('.dds') and f not in _tex_index:
                    _tex_index[f] = os.path.join(sdir, f)
        except:
            pass

def _find_tex_by_prefix(mat_name):
    """Ищет DDS по имени материала. Сначала в базе LOD0, потом по extracted."""
    global _tex_index
    target = mat_name + '---d.dds'
    
    # Сначала проверяем базу LOD0 (самые большие файлы)
    if os.path.exists(TEX_DB_LOD0):
        p = os.path.join(TEX_DB_LOD0, target)
        if os.path.exists(p):
            _tex_index[target] = p
            return p
    
    # Fallback: ищем по extracted, берём самый большой файл
    base = TEX_BASE
    if not os.path.exists(base):
        return None
    import re as _re
    m = _re.match(r'^(lh_\d+|bc_\d+|uni_|lh_uni)', mat_name)
    prefix = m.group(1) if m else None
    
    best_path = None
    best_size = 0
    for d in os.listdir(base):
        sdir = os.path.join(base, d)
        if not os.path.isdir(sdir): continue
        if prefix and prefix not in d and 'lost_heaven_tex' not in d and 'install_tex' not in d:
            continue
        fpath = os.path.join(sdir, target)
        if os.path.exists(fpath):
            size = os.path.getsize(fpath)
            if size > best_size:
                best_size = size
                best_path = fpath
    
    if best_path:
        _tex_index[target] = best_path
    return best_path

def find_dds(mat_name, out_dir, ires_path=None):
    """Ищет DDS файл по имени материала и копирует в out_dir."""
    import shutil, re as _re
    target = mat_name + '---d.dds'
    
    # Сначала ищем точное совпадение в базе LOD0/D
    src = _find_tex_by_prefix(mat_name)
    
    if not src:
        # Fallback: убираем суффикс версии и ищем в базе
        base_name = _re.sub(r'_v\d+$', '', mat_name)
        for v in ['_v1', '_v2', '_v3', '_v4', '_v5']:
            candidate = base_name + v + '---d.dds'
            # Сначала в базе LOD0/D
            p = os.path.join(TEX_DB_LOD0, candidate)
            if os.path.exists(p):
                src = p
                break
        if not src:
            # Fallback в extracted
            district = None
            if ires_path:
                m = _re.search(r'(lh_\d+_[a-z_]+?)(?:_block|_general|_lod|_collision)', ires_path.replace('\\','/'))
                if m:
                    district = m.group(1)
            _build_tex_index(district)
            for v in ['_v1', '_v2', '_v3', '_v4', '_v5']:
                candidate = base_name + v + '---d.dds'
                if candidate in _tex_index:
                    src = _tex_index[candidate]
                    break
    
    if src:
        dst = os.path.join(out_dir, target)
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
    return target

def dds_to_tga(dds_path, tga_path):
    """Конвертирует DDS в TGA через Pillow."""
    try:
        from PIL import Image
        img = Image.open(dds_path)
        img.save(tga_path)
        return True
    except Exception as e:
        print("  DDS->TGA failed: {}".format(e))
        return False

def write_mtl(out_dir, mat_name, ires_path=None):
    """Генерирует .mtl файл для OBJ, конвертирует DDS->TGA."""
    diffuse_dds = find_dds(mat_name, out_dir, ires_path)
    dds_path = os.path.join(out_dir, diffuse_dds)
    tga_name = diffuse_dds.replace('.dds', '.tga')
    tga_path = os.path.join(out_dir, tga_name)
    if os.path.exists(dds_path) and not os.path.exists(tga_path):
        dds_to_tga(dds_path, tga_path)
    tex_ref = tga_name if os.path.exists(tga_path) else diffuse_dds
    mtl_path = os.path.join(out_dir, mat_name + '.mtl')
    with open(mtl_path, 'w') as f:
        f.write('newmtl {}\n'.format(mat_name))
        f.write('Ka 1.0 1.0 1.0\n')
        f.write('Kd 1.0 1.0 1.0\n')
        f.write('Ks 0.0 0.0 0.0\n')
        f.write('map_Kd {}\n'.format(tex_ref))
    return mtl_path

# ─────────────────────────────────────────────────────────────────────────────
# Главная функция
# ─────────────────────────────────────────────────────────────────────────────

def scan_file(path, out_dir, no_center=False):
    data = open(path, 'rb').read()
    size = len(data)
    base = os.path.splitext(os.path.basename(path))[0]
    print("=" * 60)
    print("File: {} ({} bytes)".format(path, size))
    os.makedirs(out_dir, exist_ok=True)

    # Извлекаем имя материала — сначала из текущего файла, потом из предыдущего
    mat_name = extract_material_name(data)
    # Для именованных файлов (не File_NNN) — берём имя файла
    if not mat_name and not base.startswith('File_'):
        # Убираем расширения типа .ires
        import re as _re2
        mat_name = _re2.sub(r'\.(ires|compiled|lod\d+).*', '', base)
    if not mat_name:
        # Ищем в соседних файлах (File_NNN-1, File_NNN-2)
        import re as _re
        m = _re.search(r'File_(\d+)', os.path.basename(path))
        if m:
            num = int(m.group(1))
            dir_path = os.path.dirname(path)
            for delta in [-1, -2, 1]:
                neighbor = os.path.join(dir_path, 'File_{}.ires.compiled'.format(num + delta))
                if os.path.exists(neighbor):
                    try:
                        nd = open(neighbor, 'rb').read()
                        mat_name = extract_material_name(nd)
                        if mat_name:
                            break
                    except:
                        pass
    if not mat_name:
        # Ищем в nomesh файле из lod1 SDS (там хранится имя материала)
        import re as _re, xml.etree.ElementTree as _ET
        m = _re.search(r'File_(\d+)', os.path.basename(path))
        sds_dir = os.path.dirname(path)
        if m:
            # Получаем GUID текущего lod0 файла из SDSContent.xml
            xml_path = os.path.join(sds_dir, 'SDSContent.xml')
            if os.path.exists(xml_path):
                try:
                    tree = _ET.parse(xml_path)
                    fname_key = os.path.basename(path)
                    target_guid = None
                    for e in tree.getroot().findall('ResourceEntry'):
                        f = e.find('File')
                        if f is not None and f.text and os.path.basename(f.text) == fname_key:
                            target_guid = int(e.get('FileGUID', 0))
                            break
                    if target_guid:
                        # Ищем nomesh с тем же GUID в lod1 SDS
                        lod1_dir = sds_dir.replace('_lod0.sds', '_lod1.sds')
                        lod1_xml = os.path.join(lod1_dir, 'SDSContent.xml')
                        if os.path.exists(lod1_xml):
                            tree1 = _ET.parse(lod1_xml)
                            for e in tree1.getroot().findall('ResourceEntry'):
                                if int(e.get('FileGUID', 0)) == target_guid:
                                    f = e.find('File')
                                    if f is not None and f.text and '[nomesh]' in f.text:
                                        nomesh_path = os.path.join(lod1_dir, f.text)
                                        if os.path.exists(nomesh_path):
                                            nd = open(nomesh_path, 'rb').read()
                                            mat_name = extract_material_name(nd)
                                        break
                except:
                    pass
    if mat_name:
        print("Material: {}".format(mat_name))
    else:
        mat_name = base  # fallback — имя файла

    # Шаг 1: все буферы
    buf_map = find_all_buffers(data)
    vb_list = [b for b in buf_map if b['type'] == 'VB']
    ib_list = [b for b in buf_map if b['type'] == 'IB']

    print("\nBuffers found: {} VB, {} IB".format(len(vb_list), len(ib_list)))
    for b in buf_map:
        if b['type'] == 'VB':
            print("  VB  @{:<8d} size={:<8d} stride={} verts={}".format(
                b['off'], b['size'], b['stride'], b['verts']))
        elif b['type'] == 'IB':
            print("  IB  @{:<8d} size={:<8d} idx={} max_vi={}".format(
                b['off'], b['size'], b['n_idx'], b['max_vi']))

    if not vb_list:
        print("No VB found!"); return []

    # Шаг 2: sub-mesh таблица — ищем для каждого IB отдельно
    # find_best_submesh_table теперь возвращает (firstIndex, count) пары
    submesh_table_global = find_best_submesh_table(data)
    if submesh_table_global:
        print("\nSub-mesh table (global): {} entries".format(len(submesh_table_global)))
    else:
        print("\nNo global sub-mesh table")

    # Шаг 3: сопоставляем IB → VB
    # Приоритет: точное совпадение verts == max_vi+1 (с учётом всех stride вариантов)
    print("\nIB → VB matching:")
    ib_to_vb = {}
    for ib in ib_list:
        ib_off = ib['off']; ib_end = ib_off + ib['size']
        best_vb = None; best_dist = float('inf'); best_stride = None

        # Ищем точное совпадение по любому из stride вариантов VB
        exact = []
        for vb in vb_list:
            for stride, vc in vb.get('vb_candidates', [(vb['stride'], vb['verts'])]):
                if vc == ib['max_vi'] + 1:
                    exact.append((vb, stride, vc))
        
        if exact:
            # Берём ближайший физически
            for vb, stride, vc in exact:
                vb_off = vb['off']; vb_end = vb_off + vb['size']
                if ib_end <= vb_off: dist = vb_off - ib_end
                elif ib_off >= vb_end: dist = ib_off - vb_end
                else: dist = 0
                if dist < best_dist:
                    best_dist = dist; best_vb = vb; best_stride = stride
        else:
            # Ближайший VB с verts > max_vi
            # Среди кандидатов берём тот stride который даёт минимальное превышение над max_vi
            candidates = [vb for vb in vb_list if vb['verts'] > ib['max_vi']]
            for vb in candidates:
                vb_off = vb['off']; vb_end = vb_off + vb['size']
                if ib_end <= vb_off: dist = vb_off - ib_end
                elif ib_off >= vb_end: dist = ib_off - vb_end
                else: continue
                # Ищем лучший stride — предпочитаем тот же stride что уже используется для этого VB
                best_s = vb['stride']; best_vc = vb['verts']
                # Если этот VB уже матчится с другим IB — берём его stride
                for prev_ib_off, prev_vb in ib_to_vb.items():
                    if prev_vb['off'] == vb['off']:
                        best_s = prev_vb['stride']
                        best_vc = prev_vb['verts']
                        break
                else:
                    # Иначе перебираем все stride — минимальное превышение над max_vi
                    for s in KNOWN_STRIDES:
                        if vb['size'] % s == 0:
                            vc = vb['size'] // s
                            if vc > ib['max_vi'] and vc < best_vc:
                                best_s = s; best_vc = vc
                # Если нашли stride с меньшим превышением — обновляем verts для сравнения
                effective_verts = best_vc
                if dist < best_dist or (dist == best_dist and effective_verts < (best_vb['verts'] if best_vb else 999999)):
                    best_dist = dist; best_vb = vb; best_stride = best_s

        if best_vb is not None:
            # Применяем правильный stride
            matched_vb = dict(best_vb)
            if best_stride and best_stride != best_vb['stride']:
                matched_vb['stride'] = best_stride
                matched_vb['verts'] = best_vb['size'] // best_stride
            # Дополнительная проверка: если verts != max_vi+1, но size/(max_vi+1) — целое
            # и это известный stride — используем его
            needed_verts = ib['max_vi'] + 1
            if matched_vb['verts'] != needed_verts:
                sz = matched_vb['size']
                if sz % needed_verts == 0:
                    candidate_stride = sz // needed_verts
                    if candidate_stride in KNOWN_STRIDES:
                        matched_vb['stride'] = candidate_stride
                        matched_vb['verts'] = needed_verts
            ib_to_vb[ib_off] = matched_vb
            tag = " [EXACT]" if matched_vb['verts'] == ib['max_vi'] + 1 else ""
            print("  IB@{} → VB@{} dist={}{} (max_vi={}, verts={}, stride={})".format(
                ib_off, best_vb['off'], best_dist, tag, ib['max_vi'], matched_vb['verts'], matched_vb['stride']))
        else:
            print("  IB@{} → NO MATCH (max_vi={})".format(ib_off, ib['max_vi']))

    # Шаг 4: разбиваем IB на sub-mesh и экспортируем
    all_meshes = []
    for ib in ib_list:
        if ib['off'] not in ib_to_vb: continue
        vb_default = ib_to_vb[ib['off']]
        # Используем реальный max_vi из IB для разбивки (не из VB)
        max_vi = ib['max_vi']
        # Ищем sub-mesh таблицу для этого конкретного IB
        # Файловая таблица имеет приоритет — она точнее чем RDOC
        ib_submesh = find_best_submesh_table(data, ib['size'])
        if ib_submesh:
            submesh_counts = ib_submesh
        elif ib['size'] in RDOC_SUBMESH_TABLES:
            submesh_counts = RDOC_SUBMESH_TABLES[ib['size']]
        else:
            submesh_counts = []
        blocks = split_ib(data, ib['off'], ib['size'], max_vi, submesh_counts)
        for tris, vi_lo, vi_hi, first_idx in blocks:
            # Per-submesh VB matching: выбираем VB с verts > vi_hi
            vb = vb_default
            if vi_hi >= vb_default['verts']:
                # Ищем VB который покрывает этот диапазон индексов
                candidates = [v for v in vb_list if v['verts'] > vi_hi]
                if candidates:
                    vb = min(candidates, key=lambda v: abs(v['verts'] - vi_hi - 1))
            all_meshes.append({
                'ib_off': ib['off'], 'tris': tris,
                'vb_off': vb['off'], 'stride': vb['stride'],
                'vi_lo': vi_lo, 'vi_hi': vi_hi,
                'n_tris': len(tris),
                'ib_size': ib['size'],
                'first_idx': first_idx,
            })

    # Убираем дубли по (ib_off, vi_lo)
    seen = set()
    unique = []
    for m in all_meshes:
        key = (m['ib_off'], m['vi_lo'])
        if key not in seen:
            seen.add(key); unique.append(m)
    all_meshes = sorted(unique, key=lambda m: m['n_tris'], reverse=True)
    print("\nExporting {} meshes:".format(len(all_meshes)))

    # Проход 1: декодируем все вершины с merge, вычисляем bbox в повёрнутом пространстве
    # rotate -90 X: (x,y,z) -> (x, z, -y)
    all_xs = []; all_ys = []; all_zs = []
    for m in all_meshes:
        used_vi = sorted(set(v for t in m['tris'] for v in t))
        verts_m = [decode_pos(data, m['vb_off'], vi, m['stride']) for vi in used_vi]
        snorm_m = [decode_pos_snorm(data, m['vb_off'], vi, m['stride']) for vi in used_vi]
        verts_m = merge_by_flag(data, m['vb_off'], used_vi, verts_m, m['stride'])
        for v in verts_m:
            all_xs.append(v[0])
            all_ys.append(v[2])   # после rotate Y = старый Z
            all_zs.append(-v[1])  # после rotate Z = -старый Y
    if all_xs:
        cx = (min(all_xs) + max(all_xs)) / 2.0
        cy = (min(all_ys) + max(all_ys)) / 2.0
        cz = (min(all_zs) + max(all_zs)) / 2.0
        # global_z_center — центр Z в исходных координатах (до rotate)
        # all_ys = Z_raw после rotate, значит Z_raw_center = cy + CY_rot
        # Но проще: берём Z_raw напрямую из вершин
        all_z_raw = []
        for m in all_meshes:
            for vi in sorted(set(v for t in m['tris'] for v in t)):
                all_z_raw.append(decode_pos(data, m['vb_off'], vi, m['stride'])[2])
        global_z_center = (min(all_z_raw) + max(all_z_raw)) / 2.0
        print("  Center (rotated): X={:.2f} Y={:.2f} Z={:.2f}  Z_raw_center={:.2f}".format(
            cx, cy, cz, global_z_center))
    else:
        cx = cy = cz = 0.0
        global_z_center = 128.0
    if no_center:
        offset = (0.0, 0.0, 0.0)
    else:
        offset = (cx, cy, cz)

    exported = 0
    used_names = set()

    # Получаем список материалов для sub-mesh через MTL базу
    submesh_mats = get_submesh_materials(mat_name, len(all_meshes))

    for idx, m in enumerate(all_meshes):
        mesh_key = (m.get('ib_size', 0), m.get('first_idx', 0))
        if mesh_key in MESH_LOD_MAP:
            lod_n, mesh_m = MESH_LOD_MAP[mesh_key]
            name = '{}_lod{}_mesh{}'.format(base, lod_n, mesh_m)
        else:
            ib_sizes_sorted = sorted(set(mm['ib_size'] for mm in all_meshes), reverse=True)
            lod_n = ib_sizes_sorted.index(m['ib_size']) if m['ib_size'] in ib_sizes_sorted else 0
            same_lod = [mm for mm in all_meshes if mm['ib_size'] == m['ib_size']]
            mesh_m = same_lod.index(m) if m in same_lod else idx
            name = '{}_lod{}_mesh{}'.format(base, lod_n, mesh_m)
        # Если имя уже занято — добавляем fi чтобы сделать уникальным
        if name in used_names:
            name = '{}_fi{}'.format(name, m.get('first_idx', idx))
        used_names.add(name)
        out_path = os.path.join(out_dir, name + '.obj')
        # Выбираем материал для этого sub-mesh
        mesh_mat = submesh_mats[idx] if idx < len(submesh_mats) and submesh_mats[idx] else mat_name
        # Убираем суффикс ---d.dds если это полное имя файла
        if mesh_mat and mesh_mat.endswith('---d.dds'):
            mesh_mat_name = mesh_mat[:-8]  # убираем ---d.dds
        else:
            mesh_mat_name = mesh_mat or mat_name
        result = export_obj(data, m['tris'], m['vb_off'], m['stride'], out_path, name, offset, global_z_center, mesh_mat_name)
        if len(result) == 5:
            nv, nf, xr, yr, zr = result
            print("  [{:02d}] IB@{:<8d} VB@{:<8d} stride={} vi={}-{} → {} verts {} faces".format(
                idx, m['ib_off'], m['vb_off'], m['stride'], m['vi_lo'], m['vi_hi'], nv, nf))
            print("        X={:.2f}..{:.2f}  Y={:.2f}..{:.2f}  Z={:.2f}..{:.2f}".format(
                xr[0],xr[1], yr[0],yr[1], zr[0],zr[1]))
            exported += 1
        else:
            print("  [{:02d}] ERROR".format(idx))

    print("\nDone. {} meshes → {}".format(exported, out_dir))
    # Генерируем MTL файлы для всех уникальных материалов
    if exported > 0:
        # Основной материал
        write_mtl(out_dir, mat_name, path)
        # Дополнительные материалы sub-mesh
        written_mats = {mat_name}
        for sm in submesh_mats:
            if sm and sm.endswith('---d.dds'):
                sm_name = sm[:-8]
            else:
                sm_name = sm or mat_name
            if sm_name and sm_name not in written_mats:
                write_mtl(out_dir, sm_name, path)
                written_mats.add(sm_name)
        print("MTL: {} materials written".format(len(written_mats)))
    return all_meshes

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    path = sys.argv[1]
    no_center = '--no-center' in sys.argv
    args = [a for a in sys.argv[2:] if not a.startswith('--')]
    if args:
        out_dir = args[0]
    else:
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        base = os.path.splitext(os.path.basename(path))[0]
        out_dir = os.path.join(os.path.dirname(path), 'ires_scan_{}_{}'.format(base, ts))
    scan_file(path, out_dir, no_center=no_center)
