import os, re, glob, collections, datetime
# Generates references/resource-effects-catalog.md: EVERY map resource and the concrete gameplay
# EFFECT(s) it grants (Wine->Happiness, Horses->Cavalry strength, Incense->city Science, ...), per Age.
# WHY: resource IDs don't tell you what they DO, and the effect (and the class) is defined PER-AGE in
# each age module's resources-gameeffects.xml -- a resource can grant totally different bonuses in
# AQ vs EX vs MO, or nothing. Complements resources-and-ages.md (classes/validity). Run with `py -3`.
# Regenerate after each patch.

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
AGES = [("AQ", "age-antiquity"), ("EX", "age-exploration"), ("MO", "age-modern")]
attr_re = re.compile(r'(\w+)="([^"]*)"')
row_text_re = re.compile(r'<Row\b[^>]*\bTag="(LOC_[A-Z0-9_]+)"[^>]*>\s*<Text>(.*?)</Text>', re.S)

def read(path):
    try: return open(path, encoding="utf-8", errors="replace").read()
    except OSError: return ""

# ---- readable names (resource text lives under each module's text/en_us) ----
loc = {}
for fp in glob.glob(os.path.join(ROOT, "Base", "modules", "**", "text", "en_us", "*.xml"), recursive=True):
    for tag, en in row_text_re.findall(read(fp)):
        loc.setdefault(tag, re.sub(r'\s+', ' ', en.strip()))
def rname(res):
    nm = loc.get("LOC_%s_NAME" % res)
    if nm: return nm
    return res.replace("RESOURCE_", "").replace("_", " ").title()

# ---- baseline defs + ValidAges (all in base-standard/data/resources.xml) ----
base_xml = read(os.path.join(ROOT, "Base", "modules", "base-standard", "data", "resources.xml"))
baseclass, tradeable, slots, valid = {}, {}, {}, collections.defaultdict(set)
for m in re.finditer(r'<Row\b([^>]*\bResourceType="RESOURCE_[A-Z_]+"[^>]*\bResourceClassType="[A-Z_]+"[^>]*)/?>', base_xml):
    d = dict(attr_re.findall(m.group(1)))
    r = d["ResourceType"]
    baseclass[r] = d["ResourceClassType"].replace("RESOURCECLASS_", "")
    tradeable[r] = d.get("Tradeable", "true").lower() != "false"
    if d.get("BonusResourceSlots"): slots[r] = d["BonusResourceSlots"]
for m in re.finditer(r'<Row ResourceType="(RESOURCE_[A-Z_]+)" AgeType="AGE_([A-Z]+)"', base_xml):
    valid[m.group(1)].add({"ANTIQUITY": "AQ", "EXPLORATION": "EX", "MODERN": "MO"}[m.group(2)])

# ---- per-age class overrides (Update Where/Set in each age module) ----
ageclass = {a: {} for a, _ in AGES}
for a, mod in AGES:
    xml = read(os.path.join(ROOT, "Base", "modules", mod, "data", "resources.xml"))
    for blk in re.findall(r'<Update>(.*?)</Update>', xml, re.S):
        w = re.search(r'ResourceType="(RESOURCE_[A-Z_]+)"', blk)
        s = re.search(r'ResourceClassType="RESOURCECLASS_([A-Z_]+)"', blk)
        if w and s: ageclass[a][w.group(1)] = s.group(1)
def cls_for(res, age):
    if age not in valid.get(res, set()) and res not in ("RESOURCE_GOLD_DISTANT_LANDS", "RESOURCE_SILVER_DISTANT_LANDS"):
        return "—"
    return ageclass[age].get(res, baseclass.get(res, "?"))

# ---- effect modifiers per age ----
UCLASS = lambda t: t.replace("UNIT_CLASS_", "").title().replace(", ", " & ")
YIELD = lambda y: {"YIELD_DIPLOMACY": "Influence"}.get(y, y.replace("YIELD_", "").title())
DOMAIN = lambda d: {"SEA": "Naval", "LAND": "Land"}.get(d.replace("DOMAIN_", ""), d.replace("DOMAIN_", "").title())
def arg(d, k, default=""): return d.get(k, default)

def block_args(blk):
    return {m.group(1): m.group(2).strip() for m in re.finditer(r'<Argument name="(\w+)">(.*?)</Argument>', blk, re.S)}
def block_reqs(blk):
    reqs = []
    sub = re.search(r'<SubjectRequirements>(.*?)</SubjectRequirements>', blk, re.S)
    if not sub: return reqs
    for rm in re.finditer(r'<Requirement type="(REQUIREMENT_[A-Z_]+)"([^>]*)>?(.*?)(?:</Requirement>|/>)', sub.group(1), re.S):
        rt, ra, rbody = rm.group(1), rm.group(2), rm.group(3)
        inv = 'inverse="true"' in ra or "inverse='true'" in ra
        ba = block_args(rbody)
        reqs.append((rt, inv, ba))
    return reqs

def cond_text(collection, reqs):
    bits = []
    coll = {"COLLECTION_ALL_CITIES": "all cities", "COLLECTION_ALL_CAPITAL_CITIES": "capital",
            "COLLECTION_ALL_PLAYERS": "player-wide", "COLLECTION_ALL_UNITS": "units"}.get(collection, collection)
    for rt, inv, ba in reqs:
        if rt == "REQUIREMENT_CITY_HAS_BUILD_QUEUE": bits.append("Cities only")
        elif rt == "REQUIREMENT_CITY_IS_TOWN": bits.append("Towns only")
        elif rt == "REQUIREMENT_CITY_IS_CAPITAL": bits.append("non-capital" if inv else "capital")
        elif rt == "REQUIREMENT_CITY_IS_DISTANT_LANDS": bits.append("Homeland" if inv else "Distant-Lands")
        elif rt == "REQUIREMENT_CITY_HAS_BUILDING":
            b = ba.get("BuildingType", "").replace("BUILDING_", "").replace("_", " ").title()
            bits.append(("no " if inv else "has ") + b)
        elif rt == "REQUIREMENT_PLAYER_IS_IN_GOLDEN_AGE": bits.append("Golden Age")
    return coll, bits

def describe(mod):
    """mod = (effid, collection, args, reqs) -> plain-English string."""
    eff, collection, a, reqs = mod
    coll, bits = cond_text(collection, reqs)
    amt = a.get("Amount", a.get("Percent", ""))
    yld = YIELD(a.get("YieldType", "")) if a.get("YieldType") else ""
    pct = a.get("PercentMultiplier", "false").lower() == "true"
    unit = "%" if (pct or "Percent" in a or eff.endswith("PURCHASE_EFFICIENCY_PER_RESOURCE")) else ""
    tail = (" [" + ", ".join(bits) + "]") if bits else ""
    if eff == "EFFECT_CITY_ADJUST_YIELD_PER_RESOURCE":
        return "+%s%s %s per copy%s" % (amt, unit, yld, tail)
    if eff == "EFFECT_CITY_ADJUST_YIELD_PER_AVAILABLE_RESOURCE_TYPE":
        return "+%s%s %s per available copy (empire)%s" % (amt, unit, yld, tail)
    if eff == "EFFECT_ADJUST_PLAYER_YIELD_PER_SLOTTED_RESOURCE":
        return "+%s%s %s per slotted copy, player-wide%s" % (amt, unit, yld, tail)
    if eff == "EFFECT_PLAYER_ADJUST_YIELD_PER_RESOURCE_TYPE":
        return "+%s%s %s per copy, player-wide%s" % (amt, unit, yld, tail)
    if eff == "EFFECT_UNIT_ADJUST_COMBAT_STRENGTH_PER_RESOURCE":
        tag = ""
        for rt, inv, ba in reqs:
            if rt == "REQUIREMENT_UNIT_TAG_MATCHES": tag = UCLASS(ba.get("Tag", ""))
        return "+%s Combat Strength per copy to %s" % (amt, tag or "units")
    if eff == "EFFECT_UNIT_ADJUST_HEAL_PER_RESOURCE":
        return "+%s HP healed/turn per copy, all units" % amt
    if eff == "EFFECT_CITY_ADJUST_BIOME_WONDER_PRODUCTION_PER_RESOURCE":
        biome = a.get("BiomeType", "").replace("BIOME_", "").title()
        emp = " (empire)" if a.get("Empire", "").lower() == "true" else ""
        return "+%s%% Wonder production per copy in %s cities%s" % (amt, biome, emp)
    if eff == "EFFECT_CITY_ADJUST_CONSTRUCTIBLE_PRODUCTION_PER_RESOURCE":
        tgt = a.get("ConstructibleType", a.get("ConstructibleClass", "")).replace("BUILDING_", "").replace("_", " ").title()
        emp = " (empire)" if a.get("Empire", "").lower() == "true" else ""
        return "+%s%% production toward %s per copy%s%s" % (amt, tgt, emp, tail)
    if eff == "EFFECT_CITY_ADJUST_CONSTRUCTIBLE_PRODUCTION_PER_SLOTTED_RESOURCE":
        tgt = a.get("ConstructibleClass", a.get("ConstructibleType", "")).title()
        return "+%s%% %s production per slotted copy" % (amt, tgt)
    if eff == "EFFECT_CITY_ADJUST_UNIT_PRODUCTION_PER_RESOURCE":
        ut = a.get("UnitTag", "")
        who = (" (%s)" % UCLASS(ut)) if ut else ""
        return "+%s%% unit production per copy%s%s" % (amt, who, tail)
    if eff == "EFFECT_CITY_ADJUST_UNIT_PRODUCTION_PER_SLOTTED_RESOURCE":
        return "+%s%% %s unit production per slotted copy" % (amt, DOMAIN(a.get("Domain", "")))
    if eff == "EFFECT_PLAYER_ADJUST_PURCHASE_EFFICIENCY_PER_RESOURCE":
        what = "Building" if a.get("AffectBuildings", "").lower() == "true" else "Unit"
        return "-%s%% %s purchase cost per copy, player-wide" % (amt, what)
    return eff + tail  # fallback: raw

# collect modifiers per resource per age
eff_by_res = collections.defaultdict(lambda: {a: [] for a, _ in AGES})
effcount = collections.Counter()
for a, mod in AGES:
    xml = read(os.path.join(ROOT, "Base", "modules", mod, "data", "resources-gameeffects.xml"))
    for mm in re.finditer(r'<Modifier\b([^>]*)>(.*?)</Modifier>', xml, re.S):
        head, body = mm.group(1), mm.group(2)
        hd = dict(attr_re.findall(head))
        eff, coll = hd.get("effect", ""), hd.get("collection", "")
        args = block_args(body)
        res = args.get("ResourceType")
        if not res: continue
        eff_by_res[res][a].append((eff, coll, args, block_reqs(body)))
        effcount[eff] += 1

# ---- emit ----
now = datetime.date.today().isoformat()
allres = sorted(set(list(baseclass) + list(eff_by_res)), key=rname)
L = []; W = L.append
W("# Civ VII resource-effects catalog (what each resource actually DOES)")
W("")
W("> **Provenance.** Extracted **%s** from the local install by parsing every" % now)
W("> `Base\\modules\\age-*\\data\\resources-gameeffects.xml` (the `MOD_<RESOURCE>_<EFFECT>` modifiers)")
W("> plus `resources.xml` (class / `Tradeable` / `Resource_ValidAges`). **%d resources.**" % len(allres))
W("> Regenerate via [`tools/gen-resource-effects-catalog.py`](../tools/gen-resource-effects-catalog.py) (`py -3`).")
W(">")
W("> Per-resource EFFECT table. For classes, per-age validity, and age-transition traps see the")
W("> companion **[resources-and-ages.md](resources-and-ages.md)**. Each resource's effect and class are")
W("> defined **per-Age** (each Age = base-standard baseline + that Age module's patches) so a resource")
W("> can grant different bonuses in AQ / EX / MO, or none.")
W("")
W("## How to read this")
W("")
W("**Every resource effect is defined per-Age and only fires in that Age.** The **Effects** column tags")
W("each line `AQ:` / `EX:` / `MO:`. Counting modes: **per copy** = per copy worked/assigned in that city;")
W("**per available copy (empire)** = per copy available to the empire, granted in every city of the")
W("collection (empire-wide scaler); **per slotted copy** = per copy placed in a resource slot. Amounts are")
W("flat yield unless written `%` (`PercentMultiplier=true`, a % modifier / purchase discount). Conditions")
W("in `[...]`: **Cities only** (Towns excluded, `CITY_HAS_BUILD_QUEUE`), **Towns only**, capital/non-capital,")
W("**Homeland**/**Distant-Lands**, building gates (Port/Rail Station/Palace/Factory), **Golden Age**.")
W("`Influence` = `YIELD_DIPLOMACY`. Class `—` = not valid that Age. For the full EFFECT_* primitive table")
W("and the class/age-journey/suzerain/Distant-Lands background see **[resources-and-ages.md](resources-and-ages.md)**.")
W("")
W("| Resource | Class by Age (AQ / EX / MO) | Trade | Effects by Age |")
W("|----------|------------------------------|:-----:|----------------|")
for res in allres:
    nm = rname(res)
    if res.endswith("_DISTANT_LANDS") and "Distant" not in nm: nm += " (Distant Lands)"
    trip = " / ".join(cls_for(res, a) for a, _ in AGES)
    tr = "no" if not tradeable.get(res, True) else "yes"
    lines = []
    for a, _ in AGES:
        biomes = collections.defaultdict(list)  # (amt) -> [biome] for wonder-prod grouping
        for mod in eff_by_res[res][a]:
            eff, coll, args, reqs = mod
            if eff == "EFFECT_CITY_ADJUST_BIOME_WONDER_PRODUCTION_PER_RESOURCE":
                biomes[args.get("Amount", "")].append(args.get("BiomeType", "").replace("BIOME_", "").title())
            else:
                lines.append("%s: %s" % (a, describe(mod)))
        for amt, bl in biomes.items():
            lines.append("%s: +%s%% Wonder production per copy in %s cities (empire)" % (a, amt, " / ".join(bl)))
    if not lines:
        if res in slots: lines = ["*no yield effect* — grants **+%s resource slots** (utility)" % slots[res]]
        else: lines = ["*no effect in the main resource set*"]
    W("| **%s** | %s | %s | %s |" % (nm, trip, tr, "<br>".join(lines)))
W("")
W("**v2-only:** `RESOURCE_RUBIES` (BONUS, reclassed TREASURE in EX) exists only in the alternate")
W("resource-distribution `-v2` dataset (`resources-v2.xml`) and has **no yield effect** in the main set.")
W("")
W("**DLC:** the only DLC resources file, `DLC\\ashoka-himiko-alt\\modules\\data\\resources.xml`, adds **no new")
W("resources and no new effects** — only `Resource_RequiredLeaders` gating (Cocoa/Sugar/Tea/Spices/Incense →")
W("Ashoka-alt; Furs/Jade → Himiko-alt). All effects above are base-game (the 3 Age modules).")
W("")
W("---")
W("")
W("## Cross-index: resources by yield / benefit granted")
W("")
W("- **Happiness** — Dyes, Dates, Wool, Gold, Wine (Capital), Pearls, Ivory (EX/MO), Sugar (EX/MO), Cocoa (Towns), Furs (EX/MO), Spices (MO), Horses (MO).")
W("- **Food** — Cotton, Dates, Fish, Kaolin, Silver, Sugar (EX/MO), Spices (MO), Wine (MO), Truffles (MO), Cloves.")
W("- **Production** — Cotton, Hides, Gypsum, Ivory (EX/MO), Whales, Wine (MO), Tea (EX Homeland), Tobacco (MO); build-%: Coffee, Gypsum, Lapis Lazuli, Coal (Rail/Port), Oil (Factory), Incense (Temple).")
W("- **Gold** — Gold, Silver, Jade (%), Lapis Lazuli (%), Cloves (%), Nickel (%), Furs (Golden Age); purchase-discount: Gold/Silver Distant-Lands.")
W("- **Science** — Incense (AQ %), Tea (EX flat + MO %), Nickel (MO %).")
W("- **Culture** — Silk (%), Spices (EX), Kaolin (MO %), Wine (Golden Age).")
W("- **Influence** — Spices (EX).")
W("- **Combat Strength** — Horses (Cavalry), Iron (Infantry), Niter (Naval/Siege->Ranged/Siege), Coal (Light naval), Oil (Cavalry/Heavy), Rubber (Infantry/Aircraft).")
W("- **Unit healing** — Quinine (+1 HP/turn). **Resource slots** — Camels (+2).")
W("- **Wonder production (biome-gated)** — Marble (most/all biomes), Ivory (AQ Desert/Plains/Tropical).")
W("- **Unit-production %** — Salt, Truffles, Cotton (land), Citrus (naval), Incense (religious).")
W("")
W("### Tall / 1-city design notes")
W("")
W("- **`_PER_AVAILABLE_RESOURCE_TYPE`** (Gold/Silver/Wine/Furs/Sugar/Spices/Tea/Cocoa) scales with how many")
W("  copies the **empire** holds and applies in every city — a real empire-wide multiplier, strong in a")
W("  single metropolis that banks the whole pool. **But** it counts *available* (assignable) copies, so a")
W("  TREASURE-classed resource in Exploration (Gold/Silver/Furs/Cocoa/Spices/Sugar/Tea/Horses, `Assignable=false`)")
W("  has the modifier defined yet yields ~0 in Homelands that Age — the copies feed treasure fleets, not the")
W("  slot pool. The `MOD_*` rows persist across Ages; the *class* is what silences them. See resources-and-ages.md.")
W("- **`_PER_RESOURCE`** flat yields scale with copies **worked in that city** — direct and tall-friendly.")
W("- **`CITY_HAS_BUILD_QUEUE` = Cities only**: %-boosts (Incense/Jade/Silk/Nickel/Salt/Truffles/Lapis/Cloves)")
W("  never fire in Towns — relevant to the town-spec fold-in.")
W("")
W("_Effect-type distribution: %s_" % ", ".join("%s x%d" % (e.replace("EFFECT_", ""), c) for e, c in effcount.most_common()))

os.makedirs(REFDIR, exist_ok=True)
open(os.path.join(REFDIR, "resource-effects-catalog.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("resource-effects-catalog.md:", len(allres), "resources;", sum(effcount.values()), "effect modifiers")
print("effect types:", dict(effcount))
