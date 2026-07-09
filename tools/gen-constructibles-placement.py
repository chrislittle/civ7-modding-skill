import os, re, glob, collections, datetime
# Generates references/constructibles-placement-adjacency.md: for EVERY constructible, the PLACEMENT rules
# (land vs water, TerrainType / RiverPlacement / DistrictType / Biome / Feature restrictions) and the ADJACENCY
# yields it earns (which Adjacent* predicate -> which YieldType x amount).
# WHY: the base catalog (constructibles-catalog.md) carries class/age/cost/tags but NOT where a thing can be
# placed or what it gets adjacency from. Absence of this caused real bugs: assuming a Market (land) and a
# Lighthouse (water) can share/quarter a tile, or that a science building gets Mountain adjacency (only the
# Observatory does). Grep this before asserting placement or adjacency. Regenerate after each patch.
# Run with: py -3 tools/gen-constructibles-placement.py
def find_civ7_root():
    """Locate the Civ VII install without a hardcoded user path: $CIV7_ROOT, then Steam library folders."""
    env = os.environ.get("CIV7_ROOT")
    if env and os.path.isdir(env): return env
    libs = {r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"}
    try:
        vdf = open(r"C:\Program Files (x86)\Steam\steamapps\libraryfolders.vdf", encoding="utf-8", errors="replace").read()
        for m in re.findall(r'"path"\s*"([^"]+)"', vdf): libs.add(m.replace("\\\\", "\\"))
    except OSError:
        pass
    for lib in libs:
        p = os.path.join(lib, r"steamapps\common\Sid Meier's Civilization VII")
        if os.path.isdir(p): return p
    raise SystemExit("Civ VII install not found. Set CIV7_ROOT to the game folder (...\\Sid Meier's Civilization VII).")

ROOT = find_civ7_root()
REFDIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references"))
attr_re = re.compile(r'(\w+)="([^"]*)"')
row_re  = re.compile(r'<(?:Row|Replace|Insert)\b([^>]*?)/?>')
row_text_re = re.compile(r'<Row\b[^>]*\bTag="(LOC_[A-Z0-9_]+)"[^>]*>\s*<Text>(.*?)</Text>', re.S)

def datafiles():
    out = []
    for base in (os.path.join(ROOT, "Base", "modules"), os.path.join(ROOT, "DLC")):
        out += glob.glob(os.path.join(base, "**", "data", "**", "*.xml"), recursive=True)
    return out
def textfiles():
    out = []
    for base in (os.path.join(ROOT, "Base", "modules"), os.path.join(ROOT, "DLC")):
        out += glob.glob(os.path.join(base, "**", "text", "en_us", "*.xml"), recursive=True)
    return out

# LOC -> English (constructible display names)
loc = {}
for fp in textfiles():
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    for tag, en in row_text_re.findall(txt):
        loc.setdefault(tag, re.sub(r'\s+', ' ', en.strip()))

def module_age(path):
    p = path.replace("\\", "/").lower()
    if "/age-antiquity/" in p: return "AQ"
    if "/age-exploration/" in p: return "EX"
    if "/age-modern/" in p: return "MO"
    if "/base-standard/" in p: return "Base"
    m = re.search(r'/dlc/([^/]+)/', p)
    if m: return "DLC:" + m.group(1)
    return "?"
AGE_ATTR = {"AGE_ANTIQUITY": "AQ", "AGE_EXPLORATION": "EX", "AGE_MODERN": "MO"}

def rows_in(txt, table):
    """Yield attr-dicts for every <Row>/<Replace>/<Insert> inside every <table> ... </table> block in txt.
       Handles a table appearing multiple times and self-closing empty blocks."""
    for block in re.findall(r'<%s\b[^>]*>(.*?)</%s>' % (table, table), txt, re.S):
        for attrs in row_re.findall(block):
            yield dict(attr_re.findall(attrs))

# ---- collect ----------------------------------------------------------------
defs      = {}                                 # ct -> main-row record (class/age/river/name/module/main-adjacency)
terrains  = collections.defaultdict(set)       # ct -> {TerrainType}
districts = collections.defaultdict(set)       # ct -> {DistrictType}
biomes    = collections.defaultdict(set)       # ct -> {BiomeType}
invbiomes = collections.defaultdict(set)       # ct -> {BiomeType}  (InvalidAdjacentBiomes)
featreq   = collections.defaultdict(set)       # ct -> {FeatureClassType}  (RequiredFeatureClasses)
adj_apply = collections.defaultdict(list)      # ct -> [(YieldChangeId, requiresActivation)]
adj_def   = {}                                 # YieldChangeId -> Adjacency_YieldChanges record
wildcards = []                                 # [(YieldChangeId, ConstructibleClass, ConstructibleTag, requiresActivation)]

for fp in datafiles():
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    if "Constructible" not in txt and "Adjacency_YieldChanges" not in txt: continue
    mage = module_age(fp)
    # main definition rows (carry class + age + placement flags on the Constructible itself)
    for d in rows_in(txt, "Constructibles"):
        ct = d.get("ConstructibleType")
        if not ct or not d.get("ConstructibleClass") or ct in defs: continue
        nm = d.get("Name", "")
        defs[ct] = {
            "class":  d.get("ConstructibleClass", ""),
            "age":    AGE_ATTR.get(d.get("Age", ""), d.get("Age", "")) or "",
            "river":  d.get("RiverPlacement", ""),
            "mainterrain": d.get("AdjacentTerrain", ""),   # placement requirement stated on the row itself
            "adjland": d.get("AdjacentToLand", ""),
            "existing": d.get("ExistingDistrictOnly", ""),
            "name":   loc.get(nm, nm.replace("LOC_", "").replace("_NAME", "")),
            "module": mage,
        }
    for d in rows_in(txt, "Constructible_ValidTerrains"):
        if d.get("ConstructibleType") and d.get("TerrainType"): terrains[d["ConstructibleType"]].add(d["TerrainType"])
    for d in rows_in(txt, "Constructible_ValidDistricts"):
        if d.get("ConstructibleType") and d.get("DistrictType"): districts[d["ConstructibleType"]].add(d["DistrictType"])
    for d in rows_in(txt, "Constructible_ValidBiomes"):
        if d.get("ConstructibleType") and d.get("BiomeType"): biomes[d["ConstructibleType"]].add(d["BiomeType"])
    for d in rows_in(txt, "Constructible_InvalidAdjacentBiomes"):
        if d.get("ConstructibleType") and d.get("BiomeType"): invbiomes[d["ConstructibleType"]].add(d["BiomeType"])
    for d in rows_in(txt, "Constructible_RequiredFeatureClasses"):
        if d.get("ConstructibleType") and d.get("FeatureClassType"): featreq[d["ConstructibleType"]].add(d["FeatureClassType"])
    for d in rows_in(txt, "Constructible_Adjacencies"):
        if d.get("ConstructibleType") and d.get("YieldChangeId"):
            adj_apply[d["ConstructibleType"]].append((d["YieldChangeId"], d.get("RequiresActivation", "")))
    for d in rows_in(txt, "Constructible_WildcardAdjacencies"):
        if d.get("YieldChangeId"):
            wildcards.append((d["YieldChangeId"], d.get("ConstructibleClass", ""), d.get("ConstructibleTag", ""), d.get("RequiresActivation", "")))
    for d in rows_in(txt, "Adjacency_YieldChanges"):
        if d.get("ID"): adj_def.setdefault(d["ID"], d)

# ---- predicate -> human label ----------------------------------------------
WATER_TERRAINS = {"TERRAIN_COAST", "TERRAIN_OCEAN", "TERRAIN_NAVIGABLE_RIVER"}
def short_terrain(t): return t.replace("TERRAIN_", "").replace("_", " ").title()
def short_district(t): return t.replace("DISTRICT_", "").replace("_", " ").title()
def short_biome(t): return t.replace("BIOME_", "").replace("_", " ").title()

def predicate_label(d):
    """Human label for the Adjacent* predicate on an Adjacency_YieldChanges row (the SOURCE it counts)."""
    if d.get("AdjacentResource") == "true":            return "Resource (any)"
    if d.get("AdjacentSpecificResource"):              return "Resource " + d["AdjacentSpecificResource"].replace("RESOURCE_", "").title()
    if d.get("AdjacentNaturalWonder") == "true":       return "Natural Wonder"
    t = d.get("AdjacentTerrain")
    if t == "TERRAIN_MOUNTAIN":                        return "Mountain"
    if t == "TERRAIN_COAST":                           return "Coast"
    if t == "TERRAIN_NAVIGABLE_RIVER":                 return "Navigable River"
    if t:                                              return short_terrain(t)
    if d.get("AdjacentRiver") == "true":               return "River"
    if d.get("AdjacentNavigableRiver") == "true":      return "Navigable River"
    if d.get("AdjacentLake") == "true":                return "Lake"
    if d.get("AdjacentToLand") == "true":              return "Land"
    dist = d.get("AdjacentDistrict")
    if dist == "DISTRICT_WONDER":                      return "Wonder"
    if dist:                                           return short_district(dist) + " district"
    if d.get("AdjacentQuarter") == "true":             return "Quarter (finished tile)"
    if d.get("AdjacentUniqueQuarterType"):             return "Unique Quarter " + d["AdjacentUniqueQuarterType"]
    if d.get("AdjacentBiome"):                         return "Biome " + short_biome(d["AdjacentBiome"])
    if d.get("AdjacentFeature"):                       return "Feature " + d["AdjacentFeature"].replace("FEATURE_", "").title()
    if d.get("AdjacentFeatureClass"):                  return "FeatureClass " + d["AdjacentFeatureClass"].replace("FEATURE_CLASS_", "").title()
    if d.get("AdjacentConstructible"):                 return d["AdjacentConstructible"]
    if d.get("AdjacentConstructibleTag"):              return "Tag:" + d["AdjacentConstructibleTag"]
    if d.get("AdjacentConstructibleClass"):            return "Class:" + d["AdjacentConstructibleClass"]
    if d.get("AdjacentBreathtakingAppeal") == "true":  return "Breathtaking Appeal tile"
    if d.get("AdjacentCharmingAppeal") == "true":      return "Charming Appeal tile"
    # fall back: any remaining Adjacent* attr
    for k, v in d.items():
        if k.startswith("Adjacent"): return k.replace("Adjacent", "") + ("" if v == "true" else "=" + v)
    return "?"
def yield_short(y): return y.replace("YIELD_", "").title()

# land vs water classification --------------------------------------------------
def water_class(ct):
    r = defs.get(ct, {})
    tset = terrains.get(ct, set())
    if tset and tset <= WATER_TERRAINS:                    return "Water"
    if r.get("river") in ("OFF_COAST", "ANCHORED"):        return "Water"
    if tset and (tset & WATER_TERRAINS) and not (tset - WATER_TERRAINS): return "Water"
    if r.get("river") == "RIVER":                          return "Land (river-adj.)"
    return "Land"

now = datetime.date.today().isoformat()
AGE_ORDER = {"AQ": 0, "EX": 1, "MO": 2, "": 3}
def esc(s): return s.replace("|", "\\|")

L = []; W = L.append
W("# Civ VII constructibles: PLACEMENT + ADJACENCY (land/water, terrain/district rules, adjacency yields)")
W("")
W(f"> **Provenance.** Extracted **{now}** from the local Civ VII install, scanning every `Base\\modules` + `DLC`")
W(f"> data XML for the placement companion tables (`Constructible_ValidTerrains` / `_ValidDistricts` / `_ValidBiomes`,")
W(f"> `RiverPlacement` on the `Constructibles` row) and the adjacency chain (`Constructible_Adjacencies` ->")
W(f"> `Adjacency_YieldChanges`). Companion to [constructibles-catalog.md](constructibles-catalog.md) (class/age/cost/tags).")
W("> Regenerate after each patch via [`tools/gen-constructibles-placement.py`](../tools/gen-constructibles-placement.py)")
W(f"> (`py -3`). **{len(defs)} constructibles; {sum(1 for c in defs if adj_apply.get(c))} carry adjacency rows.**")
W("")
W("## Gotchas (read first)")
W("")
W("- **Land vs Water buildings cannot share/quarter a tile.** A *water* building sits on its own **coast / navigable-river")
W("  tile** (`RiverPlacement=OFF_COAST`/`ANCHORED`, or `TerrainType` limited to `TERRAIN_COAST`/`_OCEAN`/`_NAVIGABLE_RIVER`).")
W("  A *land* building sits on a land Urban tile. So e.g. **Market (land)** and **Lighthouse (water, `OFF_COAST`+`TERRAIN_COAST`)**")
W("  can NEVER form the same quarter — they live on different tile types. A quarter = two *land* Urban buildings on one tile.")
W("- **Science buildings get NO Mountain adjacency — except the Observatory.** `BUILDING_LIBRARY` / `BUILDING_ACADEMY` earn Science")
W("  only from **adjacent Resource** (`ResourceScience`) and **adjacent Wonder district** (`WonderScience`). Only")
W("  `BUILDING_OBSERVATORY` adds `ObservatoryMountainScience` (`AdjacentTerrain=TERRAIN_MOUNTAIN`, +1 Science / mountain).")
W("- **Wonders grant adjacency to ALL neighbours** via the `Wonder*` yield-change ids, which count `AdjacentDistrict=DISTRICT_WONDER`")
W("  (wonders occupy `DISTRICT_WONDER`). Any building whose adjacency list includes its `Wonder<Yield>` id benefits from being next")
W("  to a wonder — this is data-driven per building, not universal to every building.")
W("- **`RiverPlacement=RIVER` is a LAND building** that must merely be *adjacent to* a river (e.g. Bath, Ancient Bridge); it is NOT")
W("  a water tile. Only `OFF_COAST` / `ANCHORED` (and coast-only `TerrainType`) mean the building occupies a water tile.")
W("- **`AdjacentQuarter=true` counts a completed *quarter* tile** (two finished buildings), not any single building.")
W("- Improvements (farms/mines/etc.) place on `DISTRICT_RURAL`; buildings on `DISTRICT_CITY_CENTER`/`DISTRICT_URBAN`; wonders on")
W("  `DISTRICT_WONDER`. Walls attach to existing districts (`ExistingDistrictOnly`).")
W("")

# ============================ TABLE 1: PLACEMENT ============================
W("## 1. Placement rules")
W("")
W("`Land/Water`: derived — **Water** = coast/navigable-river tile (`OFF_COAST`/`ANCHORED` or water-only `TerrainType`);")
W("**Land (river-adj.)** = `RiverPlacement=RIVER` (land tile that must touch a river); **Land** = any land Urban tile.")
W("`Terrain` / `District` / `Biome` blank = no restriction (default land Urban placement). Grouped by build Age.")
W("")
CLASS_ORDER = {"WONDER": 0, "BUILDING": 1, "IMPROVEMENT": 2, "WALL": 3}
by_age = collections.defaultdict(list)
for ct, r in defs.items(): by_age[r["age"]].append(ct)
AGE_LABEL = {"AQ": "Antiquity", "EX": "Exploration", "MO": "Modern", "": "Ageless / no build-Age"}
for age in sorted(by_age, key=lambda a: AGE_ORDER.get(a, 4)):
    items = sorted(by_age[age], key=lambda ct: (CLASS_ORDER.get(defs[ct]["class"], 9), defs[ct]["name"]))
    W(f"### {AGE_LABEL.get(age, age)}  ({len(items)})")
    W("")
    W("| Type | Name | Class | Land/Water | Terrain | RiverPlace | District | Biome / Feature |")
    W("|------|------|-------|-----------|---------|-----------|----------|-----------------|")
    for ct in items:
        r = defs[ct]
        terr = ", ".join(short_terrain(t) for t in sorted(terrains.get(ct, set())))
        if r["mainterrain"]:  # placement requirement stated on the Constructibles row itself
            terr = (terr + "; " if terr else "") + "adj." + short_terrain(r["mainterrain"])
        dist = ", ".join(short_district(t) for t in sorted(districts.get(ct, set())))
        bf = ", ".join(short_biome(b) for b in sorted(biomes.get(ct, set())))
        if featreq.get(ct): bf = (bf + "; " if bf else "") + "feat:" + ",".join(sorted(f.replace("FEATURE_CLASS_", "") for f in featreq[ct]))
        if r["adjland"] == "true": bf = (bf + "; " if bf else "") + "adj.Land"
        if r["existing"] == "true": dist = (dist + "; " if dist else "") + "existing-only"
        W(f"| `{ct}` | {esc(r['name'])} | {r['class']} | {water_class(ct)} | {terr or '—'} | {r['river'] or '—'} | {dist or '—'} | {bf or '—'} |")
    W("")

# ============================ TABLE 2: ADJACENCY ============================
W("## 2. Adjacency yields")
W("")
W("Each row = one constructible and every adjacency **source -> Yield x amount** it earns (`TilesRequired` in parens when >1;")
W("`[act]` = `RequiresActivation`, i.e. only after a civ trait / tradition / tech turns it on). Only constructibles that")
W("carry `Constructible_Adjacencies` rows are listed. Source labels come from the `Adjacent*` predicate of the linked")
W("`Adjacency_YieldChanges` def.")
W("")
W("| Type | Name | Class | Adjacency sources (source -> Yield x amount) |")
W("|------|------|-------|----------------------------------------------|")
def fmt_source(yid, act):
    d = adj_def.get(yid)
    if not d: return f"{yid}(?)"
    lbl = predicate_label(d)
    amt = d.get("YieldChange", "?")
    yt  = yield_short(d.get("YieldType", ""))
    tiles = d.get("TilesRequired", "1")
    extra = f"/{tiles} tiles" if tiles not in ("1", "", None) else ""
    tag = " [act]" if (act == "true" or d.get("RequiresActivation") == "true") else ""
    return f"{lbl} -> +{amt} {yt}{extra}{tag}"
adj_cts = [ct for ct in defs if adj_apply.get(ct)]
adj_cts.sort(key=lambda ct: (AGE_ORDER.get(defs[ct]["age"], 4), CLASS_ORDER.get(defs[ct]["class"], 9), defs[ct]["name"]))
for ct in adj_cts:
    r = defs[ct]
    seen = []
    for yid, act in adj_apply[ct]:
        s = fmt_source(yid, act)
        if s not in seen: seen.append(s)
    W(f"| `{ct}` | {esc(r['name'])} | {r['class']} | {esc('; '.join(seen))} |")
W("")

# wildcard adjacencies (class/tag-scoped, mostly civ activations)
if wildcards:
    W("### Wildcard adjacencies (apply by class / tag, not per-building)")
    W("")
    W("These `Constructible_WildcardAdjacencies` grant an adjacency to **every** constructible of a `ConstructibleClass` or")
    W("carrying a `ConstructibleTag` (nearly all `RequiresActivation` = civ/tradition-gated).")
    W("")
    W("| Applies to | Source -> Yield x amount | Activation |")
    W("|-----------|--------------------------|:----------:|")
    seenw = set()
    for yid, cls, tag, act in wildcards:
        scope = ("Class:" + cls) if cls else ("Tag:" + tag) if tag else "?"
        key = (scope, yid)
        if key in seenw: continue
        seenw.add(key)
        d = adj_def.get(yid)
        if d:
            body = f"{predicate_label(d)} -> +{d.get('YieldChange','?')} {yield_short(d.get('YieldType',''))}"
        else:
            body = yid + "(?)"
        W(f"| {scope} | {esc(body)} | {'yes' if act == 'true' else ''} |")
    W("")

os.makedirs(REFDIR, exist_ok=True)
open(os.path.join(REFDIR, "constructibles-placement-adjacency.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("constructibles-placement-adjacency.md:", len(defs), "constructibles,",
      sum(1 for c in defs if adj_apply.get(c)), "with adjacency,",
      len(adj_def), "adjacency defs,", len(wildcards), "wildcard rows")
