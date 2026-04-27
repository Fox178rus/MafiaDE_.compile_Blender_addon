# Mafia DE — World Layout Research

## Структура файлов игры

```
D:\Games\Mafia Definitive Edition\sds_retail\
├── city\extracted\          — меши зданий/объектов (lh_XX_*.sds)
├── maps\                    — карта мира
│   ├── map_lost_heaven.sds  — главный файл карты (267KB)
│   └── extracted\map_lost_heaven.sds\gui\config\maps\map_lost_heaven.xml
├── roads\                   — дороги
├── city_univers\            — универсальные объекты города
└── traffic\                 — трафик
```

## map_lost_heaven.xml — параметры карты

```xml
<vect x0="-3036.74463433581" y0="4474.26239730356" kx="3.90911108644989" ky="-3.91657889193175" />
```

- `x0, y0` — мировые координаты левого верхнего угла карты-миниатюры
- `kx, ky` — масштаб: пикселей на единицу мирового пространства
- Диапазон мировых координат Lost Heaven: примерно X: -3000..3000, Y: -5000..5000

---

## Структура SDS блока (ИССЛЕДОВАНО ПОЛНОСТЬЮ)

Пример: `lh_02_little_italy_block_a_lod0.sds` / `lh_03_works_quarter_east_block_a_lod0.sds`

### Типы файлов внутри SDS блока

| Файлы | Тип | Содержимое |
|-------|-----|------------|
| File_141..248 | `.ires.compiled` | Пропсы/мелкие объекты (фонари, скамейки и т.д.) |
| File_217..226 | `.flownode` | Скрипты Lua (m_Inputs, m_Outputs, m_NodeLuaTablePath) |
| File_227 | `.vi.compiled` | FlowScript визуального индекса, LOD distances |
| File_236 | `.ires.[nomesh].compiled` | Метаданные модели без геометрии |
| File_259..260 | `.entity.compiled` | Позиции всех инстансов в мировых координатах |
| File_261 | `.lodbaked.[lod0].compiled` | Запечённый меш (не весь квартал — отдельный объект) |
| File_271..322 | `.ires.[lod0].compiled` | Здания (LOD0 геометрия) |
| File_285 | `.ires.[lod1].compiled` | LOD1 версия здания |
| File_286 | `.ires.[lod2].compiled` | LOD2 версия здания |

### Структура lh_02 block_a lod0:
```
File_175.vi.compiled          — визуальный индекс
File_176.entity.compiled      — главный entity (878KB) — все инстансы с позициями
File_177.entity.compiled      — дополнительный entity (vfx, lights)
File_191..231.ires.[lod0]     — 41 меш (здания + пропсы block_a)
```

---

## Форматы файлов

### .ires.[lod0].compiled — геометрия модели
- Содержит VB (вершины) + IB (индексы) буферы
- Буферы помечены BUFFER_MAGIC = `63 77 e0 46`
- Вершины кодируются: `x = byte[0]/256 + byte[1]` → диапазон 0..255 raw units
- **Scale не хранится** — нужен nomesh файл
- Хвост файла: `m_StdMatTree`, `m_OpcodeData` — материальные данные
- Stride=28 или 24 — здания/окружение; stride=52 — машины

### .ires.compiled (без lod тега) — пропсы
- Тот же формат что lod0
- Содержит bbox в реальных метрах (hash=0x15894197, size=24, 6 float)
- Bbox: (min_x, min_y, min_z, max_x, max_y, max_z) в метрах

### .ires.[nomesh].compiled — метаданные модели
- **НЕТ геометрии** (0 VB, 0 IB буферов)
- Содержит поля: `m_BBox`, `m_LocalMatrix`, `m_LODs`, `m_FaceGroups`, `m_ConvexDataAABB`
- **Bbox в реальных метрах** (hash=0x15894197, size=24, 6 float)
- GUID nomesh = GUID lod0 (одинаковый!) → связь nomesh↔lod0 через GUID
- Хранится в lod1 SDS (не в lod0!)

### .entity.compiled — позиции инстансов
- Формат: блоки [type=4][hash][size][data]
- Содержит имена инстансов (`lh_02_house_j_v4_00`) и матрицы трансформации
- Матрица 3x4 float: f[0]=tx, f[4]=ty, f[8]=tz (translation в первом столбце)
- 47 инстансов зданий в block_a, 46 матриц трансформации
- Blueprint GUID хранится в нераспакованной части SDS — недоступен

### .flownode — скрипты
- FlowScript ноды (Lua)
- Поля: m_Inputs, m_Outputs, m_NodeLuaTablePath, m_FunctionPorts
- Не содержит геометрии или позиций

### .vi.compiled — визуальный индекс
- FlowScript
- LOD distances (~128, ~239, ~893 units)
- Иногда содержит мировые координаты района

### .lodbaked.[lod0].compiled — запечённый меш
- Содержит геометрию (VB+IB), stride=28
- НЕ весь квартал — отдельный крупный объект (линия метро и т.д.)
- Bbox в raw units 0..256 (не мировые координаты)

---

## Масштаб моделей (РЕШЕНО)

### Проблема
Все модели в raw units 0..255. Scale не хранится в lod0 ires файле.

### Решение: nomesh bbox
Scale вычисляется через сравнение:
- **raw bbox** из экспортированного OBJ (из вывода scan_ires)
- **real bbox** из `.ires.[nomesh].compiled` (hash=0x15894197)

```
scale = real_size / raw_size  (равномерный по всем осям)
```

### Примеры scale факторов (lh_02 block_a):
| lod0 файл | nomesh файл | Реальный размер | Scale |
|-----------|-------------|-----------------|-------|
| File_226 | File_396 (lod1) | 9.9×24.7×17.4м | 0.1363 |
| File_205 | File_403 (lod1) | 15.3×20.8×13.5м | 0.1053 |
| File_194 | File_568 (lod1) | 10.2×20.5×14.1м | 0.1100 |
| File_197 | File_576 (lod1) | 11.8×12.7×9.7м | 0.077 |

### Алгоритм получения scale:
1. Открыть `lh_XX_block_N_lod1.sds/SDSContent.xml`
2. Найти `.ires.[nomesh].compiled` файлы
3. GUID nomesh = GUID lod0 → связь установлена
4. Прочитать bbox из nomesh (hash=0x15894197, size=24)
5. Экспортировать lod0 через scan_ires, взять bbox из вывода
6. scale = real_bbox_size / raw_bbox_size

### Blender применение:
После rotate -90X (scan_ires): blender_X=game_X, blender_Y=game_Z, blender_Z=-game_Y
Scale равномерный → `obj.scale = (s, s, s)`

---

## Связь ires файл → тип здания (НЕ РЕШЕНО)

### Что нашли
- entity.compiled содержит 47 инстансов с именами (`lh_02_house_j_v4_00`)
- Матрицы трансформации найдены (46 штук) в диапазоне Little Italy
- Blueprint GUID хранится в нераспакованной части SDS

### Что не нашли
- Связь `File_NNN.ires.[lod0]` → имя типа здания
- Blueprint файлы зашифрованы внутри SDS

### Кластеры позиций зданий (lh_02 block_a):
10 кластеров матриц трансформации:
```
(-1529.6, -82.1, 8.1)   [10 pts]
(-1507.0, -105.2, 4.4)  [1 pt]
(-1490.4, -118.7, 7.9)  [6 pts]
(-1463.8, -149.0, 7.3)  [11 pts]
(-1446.6, -130.4, 4.3)  [2 pts]
(-1442.2, -171.8, 7.3)  [11 pts]
(-1413.0, -106.5, 6.9)  [5 pts]
(-1411.4, -190.3, 7.8)  [3 pts]
(-1409.0, -74.1, 7.6)   [5 pts]
(-1408.5, -142.0, 6.0)  [6 pts]
```

---

## Nomesh → lod0 GUID маппинг (lh_02 block_a lod1)

| nomesh GUID | nomesh файл | lod0 файл | Реальный размер |
|-------------|-------------|-----------|-----------------|
| 629853667705807016 | File_395 | File_210 | 5.88×0×0.97м |
| 858131862843138457 | File_396 | File_226 | 9.92×24.74×17.45м |
| 1103199419832372041 | File_398 | File_230 | 8.79×1.95×14.37м |
| 3046054945742439762 | File_399 | File_220 | 12.37×18.29×15.18м |
| 3479865069012363935 | File_400 | File_217 | 10.82×1.21×8.50м |
| 3701813037189243920 | File_401 | File_228 | 6.65×0×5.77м |
| 4507377296847203069 | File_403 | File_205 | 15.34×20.83×13.46м |
| 4757781638163753741 | File_404 | File_227 | 9.95×10.50×6.22м |
| 4826850270291161285 | File_405 | File_219 | 3.61×1.25×4.65м |
| 6548497711585795466 | File_407 | File_231 | 10.50×18.45×6.78м |
| 6704993808361718315 | File_408 | File_203 | 10.07×0.62×3.76м |
| 8300943660304753842 | File_411 | File_202 | 10.07×0.65×12.95м |
| 8439948821436890668 | File_412 | File_200 | 1.40×0×1.94м |
| 10289162880289292012 | File_413 | File_229 | 8.79×3.46×14.37м |
| 13118263263922099741 | File_417 | File_211 | 14.62×0.71×6.24м |
| 13356792118662441580 | File_418 | File_213 | 17.35×25.12×7.24м |
| 14020993353409451685 | File_420 | File_199 | 1.68×2.40×2.22м |
| 14097719244955913309 | File_421 | File_221 | 4.85×15.07×25.49м |
| 8731997541021290184 | File_562 | File_192 | 15.17×15.49×8.80м |
| 16338879407232395420 | File_568 | File_194 | 10.21×20.46×14.04м |
| 11475080863233460245 | File_571 | File_195 | 10.21×20.30×12.88м |
| 7719198337007075924 | File_576 | File_197 | 11.83×12.72×9.71м |
| 1020322621003482341 | File_586 | File_201 | 9.99×19.23×3.92м |
| 12238649302284045648 | File_593 | File_204 | 10.13×19.66×2.04м |
| 5726337633435835001 | File_598 | File_206 | 15.18×19.53×8.32м |
| 9024475597701135132 | File_600 | File_207 | 15.34×19.53×4.07м |
| 16195623447708996039 | File_604 | File_208 | 15.14×19.34×3.85м |
| 433704492157985025 | File_605 | File_209 | 15.58×20.36×1.74м |
| 9648781004608098425 | File_614 | File_212 | 17.26×25.12×12.85м |
| 11181848322330770546 | File_619 | File_214 | 17.26×25.12×7.22м |
| 2377784852378011861 | File_625 | File_216 | 17.26×25.16×0.41м |
| 8449295980481004255 | File_630 | File_218 | 12.15×18.91×22.53м |
| 17142841111271893869 | File_639 | File_222 | 12.17×17.25×9.38м |
| 9225138079455178307 | File_642 | File_223 | 12.29×17.75×2.13м |
| 9981701397257774736 | File_643 | File_224 | 16.42×19.77×7.88м |

---

## Форматы файлов в SDS (ПОЛНЫЙ СПИСОК)

### Изученные форматы

| Формат | Кол-во | Содержимое |
|--------|--------|------------|
| `.ires.[lod0].compiled` | 3434 | Геометрия LOD0 (VB+IB буферы) |
| `.ires.[lod1].compiled` | 3662 | Геометрия LOD1 |
| `.ires.[lod2].compiled` | 3662 | Геометрия LOD2 |
| `.ires.[nomesh].compiled` | 3662 | Метаданные: bbox, имя типа, m_Materials |
| `.ires.compiled` | 25209 | Пропсы: геометрия + bbox + имя материала (коллизионного) |
| `.entity.compiled` | 1240 | Позиции инстансов, матрицы трансформации |
| `.vi.compiled` | 548 | FlowScript, LOD distances |
| `.flownode` | 2061 | Lua скрипты (m_Inputs, m_Outputs) |
| `.lodbaked.[lod0/1/2].compiled` | 135×3 | Запечённые меши (ландшафт, крупные объекты) |
| `.collision.compiled` | 97 | Коллизионные меши |
| `.hkx` | 1133 | Havok анимации/физика |
| `.hkt` | 277 | Havok коллизии |
| `.nav` | 138 | Навигационные меши для AI |

### Форматы ландшафта/растительности

| Формат | Кол-во | Содержимое |
|--------|--------|------------|
| `.gxml` | 7216 | Painter/vegetation параметры (трава, мусор, цветы) |
| `.gbin` | 3858 | Бинарные данные ландшафта |
| `.genr` | 89 | Streaming данные (пути к сценам) |
| `.scene.[lod0/1/2/nomesh].compiled` | 57×4 | Описания сцен |
| `.trb.compiled` | 92 | Неизвестно |

### Форматы данных

| Формат | Кол-во | Содержимое |
|--------|--------|------------|
| `.xml` | 1193 | XML данные (SDSContent и др.) |
| `.iproftime` | 25 | Профилировочные данные |

## Текстурная база (ГОТОВО)

```
F:\BLENDER_ADDONS\Mafia-5ds-main\MAFIA_DE_TEXTURES\
  LOD0\D\    - 3433 diffuse/albedo
  LOD0\N\    - 2507 normal maps
  LOD0\G\    - 2827 gloss/glossmetal
  LOD0\E\    - 589  emissive
  LOD0\DM\   - 548  detail mask
  LOD0\H\    - 21   H maps
  LOD0\OTHER\ - 127 прочие
  LOD1\D\    - 2292 diffuse
  LOD1\N\    - 1650 normal maps
  LOD1\G\    - 1854 gloss
  LOD1\E\    - 321  emissive
  LOD1\DM\   - 231  detail mask
  LOD1\H\    - 16   H maps
```
- Все DDS перемещены из extracted в базу по папкам D/N/G/E/DM/H
- В extracted DDS не осталось

## Где хранятся текстуры зданий

Текстуры зданий перечислены в **lod1 SDS XML** (SDSContent.xml).
Пример: `lh_02_little_italy_block_a_lod1.sds` содержит в XML:
- `lh_02_house_a_v1---d.dds` (GUID=12788074033627363777)
- `lh_02_house_a_v1_keyed---d.dds` (GUID=16396335568131659146)
- `lh_uni_wall_bricks_c_v1---d.dds` и т.д.

Все эти текстуры **есть в базе** `MAFIA_DE_TEXTURES\LOD0\D\`.

## Как машины находят текстуры (РЕШЕНО)

Для машин текстуры лежат **прямо в той же папке SDS** что и ires файл.
Имена текстур = имя модели + суффикс: `bolt_v8---d.dds`, `bc_streetcar_chassis---d.dds`.
Никакой таблицы материалов не нужно — всё в одном месте.

## Проблема: связь меш → текстура у зданий (ЧАСТИЧНО РЕШЕНА)

Для здания `lh_02_house_a_v3` (File_194.ires.[lod0]):
- mesh0 → `lh_02_house_a_v1---d.dds` ✓ (есть в LOD0/D)
- mesh1 → `lh_uni_wall_bricks_c_v1---d.dds` ✓ (есть в LOD0/D)
- mesh2 → `lh_02_house_a_v1_keyed---d.dds` ✓ (есть в LOD0/D)

Маппинг установлен вручную через slot индексы из nomesh m_Materials:
- slot=2 → `lh_02_house_a_v1` (mesh0, основные стены)
- slot=8 → `lh_uni_wall_bricks_c_v1` (mesh1, кирпич)
- slot=80 → `lh_02_house_a_v1_keyed` (mesh2, детали)

GUID текстур **не хранятся** в lod0 ires и nomesh файлах.
Slot → имя текстуры: связь не автоматизирована, требует ручного маппинга или
анализа Blueprint данных (зашифрованы в SDS).

## MTL файл (НОВОЕ — апрель 2026)

### Расположение
```
D:\Games\Mafia Definitive Edition\edit\materials\default.mtl
```
Распарсен в `default_parsed.json` (16642 материала, 0 ошибок).

### Формат (Material_v63, из MafiaToolkit)
```
Header: MTLB + int32 version(63) + int32 count + int32 unk
Per material:
  uint64  mat_hash
  str32   mat_name       (uint32 len + chars)
  uint32  Unk0
  byte[2] Unk1
  int32   Flags
  byte[9] Unk2
  uint64  ShaderID
  uint32  ShaderHash
  int32   paramCount
  params[]: char[4] id + int32 size + float[] values
  int32   textureCount
  textures[]: char[4] id + uint64 hash + uint16 len + chars  ← str16!
  int32   samplerCount
  samplers[]: char[4] id + int32 unk0 + byte[6] states + int16 unk1
```
**Ключевое**: имя текстуры в HashName использует uint16 (2 байта) как длину, не uint32!

### Скрипты
- `parse_mtl.py` — полный парсер, сохраняет в JSON
- `build_building_tex_map.py` — маппинг имя здания → материалы → текстуры

### Пример материала lh_02_house_a_v1
```json
{
  "hash": "0x5912612d4b5d1b96",
  "name": "lh_02_house_a_v1",
  "textures": {
    "T000": "lh_02_house_a_v1---d.dds",
    "T001": "lh_02_house_a_v1---n.dds",
    "T002": "lh_02_house_a_v1---g.dds",
    "T011": "lh_02_house_a_v1---e.dds",
    "T014": "uni_normal.dds",
    "T027": "uni_color_white.dds"
  }
}
```

## Sub-mesh → материал (ИССЛЕДОВАНО, апрель 2026)

### Что нашли в lod0 ires хвосте (File_194)

Sub-mesh таблица (stride=12, формат `[cumul][mat_id][1]`):
```
entry[0]: cumul=0     mat_id=7  → 14070 треугольников
entry[1]: cumul=14070 mat_id=8  → 2052 треугольников
```

MatGrpHash таблица (после sub-mesh):
```
MatGrpHash=0x55CCD019  count=2
MatGrpHash=0x82743058  count=4
MatGrpHash=0x4DDC4E5F  count=8
```

### Что такое MatGrpHash
- **НЕ** хеш имени материала (не FNV64, не FNV32)
- **НЕ** хеш из MTL файла (ни полный uint64, ни половины)
- **НЕ** shader_hash из MTL
- Это внутренний ID типа шейдерной группы Illusion Engine
- Одинаковые значения встречаются во ВСЕХ зданиях lh_02 block_a
- Связь MatGrpHash → имя материала хранится только в Blueprint (зашифрован в SDS)

### Что такое local mat_id
- mat_id=7, mat_id=8 — локальные индексы в m_MatTable lod0 файла
- Связь local_mat_id → MatGrpHash: count поля совпадают (mat_id=8 → MatGrpHash с count=8)
- Связь MatGrpHash → имя материала: **не установлена** без Blueprint

### Вывод
Точный маппинг sub-mesh → конкретный материал из MTL **недоступен** без Blueprint.
Blueprint зашифрован внутри SDS и не распаковывается стандартными средствами.

## Рабочий метод назначения текстур (ПРАКТИЧЕСКИЙ)

### Алгоритм (работает для ~95% зданий)
1. Из nomesh берём имя типа здания: `lh_02_house_a_v3`
2. Убираем суффикс версии: `lh_02_house_a`
3. Ищем в MTL все материалы с этим префиксом
4. Берём T000 (diffuse) первого найденного материала
5. Назначаем эту текстуру всем sub-mesh здания

### Результаты для lh_02 block_a
| Здание | MTL материалов | T000 diffuse |
|--------|---------------|--------------|
| lh_02_house_a_v3 | 7 | lh_02_house_a_v1---d.dds |
| lh_02_house_e_v7 | 1 | lh_02_house_e_v7---d.dds |
| lh_02_house_g_v2 | 1 | lh_02_house_g_v2---d.dds |
| lh_00_generic_a_v3 | 1 | lh_00_generic_a_v3---d.dds |
| lh_05_house_t_v1 | 1 | lh_05_house_t_v1---d.dds |
| lh_05_house_v_v1 | 1 | lh_05_house_v_v2---d.dds |

### Ограничение
Разные sub-mesh одного здания могут иметь разные материалы (кирпич, штукатурка, детали),
но без Blueprint мы не знаем какой sub-mesh какой материал использует.
Для визуализации достаточно одной основной текстуры на здание.

## Персонажи Mafia DE (апрель 2026)

### Расположение файлов
```
D:\Games\Mafia Definitive Edition\sds_retail\combinables\
  extracted\character_persistent.sds\models\characters\male\base\ma_basebody.ires.compiled
  auto_unique\extracted\<hash>-ma_head_101_nsantangelo.sds\models\...\ma_head_101_nsantangelo.ires.compiled
  auto_unique\extracted\<hash>-ma_suitjacket_101_tommy.sds\File_4.ires.compiled
  auto_unique\extracted\<hash>-ma_pants_101_tommy_gngstr1.sds\File_4.ires.compiled

D:\Games\Mafia Definitive Edition\sds_retail\basic_anim\extracted\skeletons.sds\File_0.hkx
```

### Скелет (HKX packfile)
- 94+ кости, стандартная Mixamo-совместимая иерархия
- Позиции в метрах (локальные, относительно родителя)
- Reference pose offset в файле: **2506416**
- Stride: 48 байт на кость (QsTransform: translation[4] + rotation[4] + scale[4])
- Hips→Head chain length: **0.915м**
- Скелет сохранён в `skeleton_tpose.json`

### Иерархия костей
```
Hips → Pelvis → LeftUpLeg/RightUpLeg → ... → Foot → ToeBase
     → Spine → Spine1 → Spine2 → Spine3
               → LeftShoulder/RightShoulder → Arm → ForeArm → Hand → Fingers
               → Neck → Neck1 → Head → Glasses/Hat/FacialRoot
```

### Масштаб и позиция мешей (РЕШЕНО)

Каждая часть хранится в своих raw units, центрирована в (0,0,0) при экспорте через scan_ires.

**Coordinate mapping (Blender = game):**
- Blender X = game X
- Blender Y = game Y  
- Blender Z = game Z (высота)

**Scale = real_Z_size / raw_Y_size** (из nomesh bbox):

| Часть | Scale | Center (X,Y,Z) | Z range |
|-------|-------|----------------|---------|
| basebody | 0.01205 | (0.000, 0.087, 0.781) | 0.01..1.55м |
| head | 0.00390 | (0.000, 0.026, 1.636) | 1.44..1.84м |
| jacket | 0.02442 | (0.000, 0.012, 1.244) | 0.86..1.63м |
| pants | 0.00862 | (0.002, -0.005, 0.583) | 0.03..1.13м |

**Алгоритм:**
1. Импортировать OBJ (центрирован в 0,0,0)
2. `obj.scale = (scale, scale, scale)` + apply
3. `obj.location = (cx, cy, cz)` из nomesh bbox center

**Источник данных:** nomesh bbox (hash=0x15894197, size=24) из `.ires.compiled` файла каждой части.

### Скрипты
- `parse_hkx_skeleton.py` — парсит HKX и извлекает кости
- `skeleton_tpose.json` — извлечённый скелет (94 кости)
- `load_tommy_v2.py` — загружает все части с правильным scale и позицией ✓
- `load_tommy_with_skeleton.py` — загружает меши + арматуру (в разработке)

- Экспорт геометрии: ✓ (scan_ires.py)
- Scale из nomesh bbox: ✓
- Текстура из MTL по имени здания: ✓ (parse_mtl.py + build_building_tex_map.py)
- Разные текстуры на sub-mesh: ✗ (требует Blueprint, недоступен)
- Мировые координаты: ✓ (из entity.compiled)
- Расстановка зданий: ✗ (связь ires→позиция не установлена)

## Анимации Mafia DE (апрель 2026)

### Файлы анимаций
```
D:\Games\Mafia Definitive Edition\sds_retail\basic_anim\extracted\
  basic_anim.sds\File_0.hkx    — 71MB, 4038 анимаций (hero_*, enemy_*, ped_*)
  script_anim.sds\File_0.hkx   — 839KB, катсценовые анимации (sc_*, lh_pigeon_*)
  skeletons.sds\File_0.hkx     — 2.5MB, скелеты персонажей
```

### Формат HKX
- Все файлы: TagFile обёртка (24 байта) + HKX packfile
- Packfile: `hk_2014.2.0-r1`, pointer_size=8, little endian
- Анимации: **hkaSplineCompressedAnimation** (сжатый формат, все анимации)
- Нет hkaInterleavedUncompressedAnimation

### Конвертация через HavokToolset
```
HavokToolset\havok_toolset.exe hk_to_gltf C:\mafia_hkx\basic_anim_x64.hkx
```
- Нужен skeleton_x64.hkx (сохранить из Havok Preview Tool как MSVC x64)
- Config: havok_toolset.config → skeleton-path=C:/mafia_hkx/skeleton_x64.hkx
- Результат: GLB со скелетом (11076 нод) но БЕЗ анимаций
- Причина: `Unhandled tag chunk 0x7A453882` — кастомный chunk Mafia DE

### Статус
- Скелет в GLB: ✓ (но анимации не декодируются)
- hkaSplineCompressedAnimation декодер: нужно написать или найти
- Файлы: C:\mafia_hkx\ (basic_anim_x64.hkx, skeleton_x64.hkx, basic_anim_x64.glb)
