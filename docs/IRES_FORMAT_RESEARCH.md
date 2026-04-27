# Mafia DE .ires.compiled — Исследование формата

## Статус: АКТИВНАЯ РАЗРАБОТКА

---

## Структура файла

### Секции
- `0..184` — заголовок (field_0=79104, header_size=28)
- `184` — GENR magic
- `256..5079` — ToC (Table of Contents) + данные объектов
- `5079..6644` — type schema (описание типов полей)
- `6644..EOF` — BUFFER_MAGIC буферы (VB/IB данные) + sub-mesh таблицы + хвост

### BUFFER_MAGIC
`63 77 E0 46` — маркер начала буфера, за ним 4 байта размера, затем данные.

### Формат поля сериализатора
```
name_len(1) + name(ASCII) + 04 00 00 00 + type_hash(4) + 04 00 00 00 + field_hash(4) + data
```

---

## Декодирование вершин

### Shader formula (позиция) — uint8
```python
x = b[0] / 256.0 + b[1]
y = b[2] / 256.0 + b[3]
z = b[4] / 256.0 + b[5]
```

## Merge-by-flag — АКТУАЛЬНАЯ логика (22.04.2026)

### stride=24 и stride=28 (окружение города)
- `fz=1` (byte[5] bit7 = 1) → вершина смещена на +128 по Z → сдвигаем **-128**
- `fz=0` → вершина на месте, не трогать
- **НЕ** применять Y merge для stride=24 (у всех вершин fy=0, это не флаг split)

### stride=52/48 (машины)
- `fz=0` → Z += 128 (старая логика, не менять)

### Известные проблемы KNOWN_IB_SIZES
- Размер 2760 был в списке машинных IB — убран, т.к. конфликтует с VB окружения
- При добавлении новых машин проверять что их IB размеры не совпадают с VB окружения

### UV offsets по stride
| stride | uv_offset | формат |
|--------|-----------|--------|
| 52 | 36 | float16 (1-v) |
| 48 | 36 | float16 (1-v) |
| 36 | 20 | float16 (1-v) |
| 32 | 20 | float16 (1-v) |
| 28 | 20 | float16 (1-v) |
| 24 | 16 | float16 (1-v) |

---

## IB → VB Matching

Приоритет: `size / (max_vi + 1)` — если результат целый и входит в KNOWN_STRIDES → это правильный stride.

**Важно:** буфер может детектироваться как stride=24 (256 вертов), хотя реально stride=32 (192 верта). Исправлено принудительным пересчётом stride по `max_vi` из IB.

```python
needed_verts = ib['max_vi'] + 1
if vb_size % needed_verts == 0:
    candidate_stride = vb_size // needed_verts
    if candidate_stride in KNOWN_STRIDES:
        use this stride
```

---

## Известные stride форматы

| stride | Описание | Примеры |
|--------|----------|---------|
| 52 | Основные меши машин (LOD0/1) | bolt_ace, bolt_truck |
| 48 | Меши машин (альтернативный) | wheel_truck03 LOD0 |
| 32 | Колёса, детали | wheel_truck03 LOD1, bolt_ace LOD2 |
| 28 | Колёса (civ), детали | wheel_truck01/02 |
| 24 | Детектируется ошибочно — реально stride=32 | — |
| 64 | Редкие меши | wheel_truck04 |
| 40 | Редкие меши | — |
| 36 | Редкие меши | — |
| 20 | Редкие меши | — |

---

## Sub-mesh таблица

Форматы в файле:
- **marker=49, stride=16**: `[4b][49][cumul][vc]`
- **marker=53, stride=16**: `[cumul][vc][idx][53]`
- **stride=12**: `[cumul][idx][1]` начиная с cumul=0

Правило: таблица валидна только если `submesh_counts[0][0] == 0` (первый fi=0).

---

## cars_universal.sds — Содержимое

### Файлы без моделей (0 VB, 0 IB) — конфиги/blueprints
`File_106, File_112, File_116, File_124, File_125, File_132` — маленькие (3-5 KB), данные light entities.

### Файлы с моделями
| Файл | Размер | Описание |
|------|--------|----------|
| File_133..152 | 121-864 KB | Крупные меши (детали машин, универсальные) |
| blueprints/env_generic/light_utilities/ | 3 KB | Конфиги фар |
| models/env_generic/street_props/bc_char_driving_low | 14 KB | Персонаж за рулём |
| models/light_entity/*.ires.compiled | 2-5 KB | Light entities (нет геометрии) |
| models/vehicles/_universal/wheels/ | 46-226 KB | **Колёса** |

### Колёса (models/vehicles/_universal/wheels/)
| Файл | LOD0 stride | LOD1 stride | LOD0 faces | LOD1 faces |
|------|-------------|-------------|------------|------------|
| wheel_civ01 | 52 | — | ~большой | — |
| wheel_civ02 | 52 | — | ~большой | — |
| wheel_civ03 | 52 | — | ~большой | — |
| wheel_civ04 | 52 | — | ~большой | — |
| wheel_civ05 | 52 | — | ~большой | — |
| wheel_truck01 | 28 | 28 | 704 | 226 |
| wheel_truck02 | 28 | 28 | — | — |
| wheel_truck03 | 48→32 | **32** | 624 | **184** |
| wheel_truck04 | 64→32 | — | 360 | — |

**wheel_truck03 LOD1**: буфер 6144 байт детектировался как stride=24 (256 вертов), реально stride=32 (192 верта). Исправлено.

---

## bolt_ace — LOD разделение (из RenderDoc)

| LOD | IB буфер | faces | Описание |
|-----|----------|-------|----------|
| LOD0 | IB_main (188994) | 17870+1606+2096+184 | кузов + варианты крыши |
| LOD1 | IB_2046k (93432) | 15572+... | кузов LOD1 |
| LOD2 | IB_main (188994) | 9369+92 | кузов LOD2 |
| LOD3 | IB_3073k+IB_3388k | 3487+357 | кузов LOD3 |

---

## Экспорт

### Параметры
- Центрирование: по bbox центру всех мешей (после merge-by-flag)
- Поворот: -90° по X → `(x, y, z)` → `(x-cx, z-cy, -(y-cz))`
- Формат: OBJ с UV

### Скрипты
- `scan_ires.py` — универсальный экспортёр одного файла
- `export_universal.py` — batch экспорт cars_universal.sds (53 файла, рекурсивно)
- `export_universal.bat` — запуск batch экспортёра

### Запуск
```
python scan_ires.py <file.ires.compiled> <out_dir>
```
или через `export_universal.bat` → выбрать номер из списка.

---

## Что сделано (обновлено 22.04.2026)
- [x] Автоматический поиск IB/VB через BUFFER_MAGIC
- [x] Merge-by-flag stride=24/28: `fz=1 → Z -= 128` (не +128!)
- [x] stride=16 добавлен в KNOWN_STRIDES
- [x] MIN_VB_VERTS снижен до 50
- [x] Пост-обработка: переклассификация IB→VB по размеру (max_vi+1)*stride
- [x] IB→VB matching: наследование stride от предыдущего IB на том же VB
- [x] 2760 убран из KNOWN_IB_SIZES (конфликт с VB окружения)
- [x] Sub-mesh таблица из файла (fi=0 обязательно)
- [x] LOD именование по MESH_LOD_MAP
- [x] IB→VB matching с принудительным пересчётом stride по max_vi
- [x] export_universal.py — рекурсивный batch экспорт
- [x] export_city.py / export_city.bat — batch экспорт города по районам

## Что делать дальше
- [ ] Проверить File_133..152 — что за меши
- [ ] Batch экспорт всех колёс (45-53 в export_universal)
- [ ] Разобрать m_LODGroup секцию → точное LOD разделение
- [ ] Batch экспорт всех 62 машин из CARS_MAFIA_DE
