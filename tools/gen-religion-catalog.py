import os, re, glob, collections, datetime
# Generates references/religion-and-beliefs-catalog.md: EVERY religion belief (Pantheon / Founder / Reliquary / Enhancer)
# with its display name, the resolved EFFECT_* + key args, whether the magnitude is flat or %, and the module it ships in.
# WHY: beliefs are opaque BELIEF_BONUS_# / PANTHEON_BONUS_# ids whose real effect lives one or two ATTACH_MODIFIERS hops
# away in a *-gameeffects.xml. This flattens that chain so a modder can see what each belief actually does, and documents
# the religion-system wiring (pantheon unlock incl. the Maurya 2nd-pantheon path, relic minting/slotting, holy city).
# Civ VII has NO "follower" or "reformation" belief CLASS — see the wiring section. Regenerate after each patch.

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

def datafiles():
    out = []
    for base in (os.path.join(ROOT, "Base", "modules"), os.path.join(ROOT, "DLC")):
        out += glob.glob(os.path.join(base, "**", "data", "**", "*.xml"), recursive=True)
    return out
def textfiles():
    out = []
    for base in (os.path.join(ROOT, "Base", "modules"), os.path.join(ROOT, "DLC")):
        out += glob.glob(os.path.join(base, "**", "text", "**", "*.xml"), recursive=True)
    return out

def module_of(path):
    p = path.replace("\\", "/").lower()
    if "/age-antiquity/" in p: return "AQ"
    if "/age-exploration/" in p: return "EX"
    if "/age-modern/" in p: return "MO"
    if "/base-standard/" in p: return "Base"
    m = re.search(r'/dlc/([^/]+)/', p)
    if m: return "DLC:" + m.group(1)
    return "?"

# ---- LOC -> English (names + descriptions) ---------------------------------
row_text_re = re.compile(r'<Row\b[^>]*\bTag="(LOC_[A-Z0-9_]+)"[^>]*>\s*<Text>(.*?)</Text>', re.S)
loc = {}
for fp in textfiles():
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    for tag, en in row_text_re.findall(txt):
        loc.setdefault(tag, re.sub(r'\s+', ' ', en.strip()))

def plain(locstr):
    """Strip Civ markup ([icon:X], [TIP:..]word[/TIP], [B]..[/B]) from a description for readability."""
    if not locstr: return ""
    s = loc.get(locstr, "")
    s = re.sub(r'\[icon:[^\]]*\]', '', s)
    s = re.sub(r'\[TIP:[^\]]*\]', '', s).replace('[/TIP]', '')
    s = re.sub(r'\[/?[A-Za-z][^\]]*\]', '', s)   # [B] [/B] [LINK] etc
    return re.sub(r'\s+', ' ', s).strip()

# ---- belief tables (Row-based) from every data xml ------------------------
attr_re = re.compile(r'(\w+)="([^"]*)"')
beliefs = {}          # BeliefType -> {class, name_loc, desc_loc, module}
belief_mods = collections.defaultdict(list)   # BeliefType -> [ModifierId,...]
classes = {}          # BeliefClassType -> {max, order, name}
for fp in datafiles():
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    mod = module_of(fp)
    for m in re.finditer(r'<Row\b([^>]*?)/?>', txt):
        d = dict(attr_re.findall(m.group(1)))
        if d.get("BeliefType") and d.get("BeliefClassType"):        # a Beliefs definition row
            bt = d["BeliefType"]
            beliefs.setdefault(bt, {"class": d["BeliefClassType"], "name_loc": d.get("Name", ""),
                                    "desc_loc": d.get("Description", ""), "module": mod,
                                    "share": d.get("Shareable", "").lower() == "true"})
        elif d.get("BeliefType") and (d.get("ModifierId") or d.get("ModifierID")):   # a BeliefModifiers link row
            belief_mods[d["BeliefType"]].append(d.get("ModifierId") or d.get("ModifierID"))
        if d.get("BeliefClassType") and d.get("Name") and d.get("MaxInReligion"):    # a BeliefClasses row
            classes[d["BeliefClassType"]] = {"max": d.get("MaxInReligion", ""),
                                             "order": d.get("AdoptionOrder", ""), "name": d.get("Name", "")}

# ---- GameEffects Modifier blocks from every data xml ----------------------
mod_re  = re.compile(r'<Modifier\b([^>]*?)>(.*?)</Modifier>', re.S)
modsc_re = re.compile(r'<Modifier\b([^>]*?)/>')
arg_re  = re.compile(r'<Argument\b([^>]*?)>(.*?)</Argument>', re.S)
req_re  = re.compile(r'<Requirement\b[^>]*\btype="([^"]+)"')
mods = {}   # id -> {collection, effect, args:{name:value}, reqs:[...]}
def add_mod(attrs, body):
    d = dict(attr_re.findall(attrs))
    mid = d.get("id")
    if not mid: return
    args = {}
    for a in arg_re.finditer(body or ""):
        ad = dict(attr_re.findall(a.group(1)))
        if ad.get("name"): args[ad["name"]] = re.sub(r'\s+', ' ', a.group(2).strip())
    reqs = req_re.findall(body or "")
    mods[mid] = {"collection": d.get("collection", ""), "effect": d.get("effect", ""), "args": args, "reqs": reqs}
for fp in datafiles():
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    if "<Modifier" not in txt: continue
    for m in mod_re.finditer(txt): add_mod(m.group(1), m.group(2))
    for m in modsc_re.finditer(txt): add_mod(m.group(1), "")

def resolve(mid, depth=0):
    """Follow one/two ATTACH_MODIFIERS hops to the concrete effect(s). Returns list of (effect, args)."""
    m = mods.get(mid)
    if not m: return [("(unresolved:%s)" % mid, {})]
    if m["effect"] == "EFFECT_ATTACH_MODIFIERS" and depth < 3:
        out = []
        for child in re.split(r'\s*,\s*', m["args"].get("ModifierId", "")):
            child = child.strip()
            if child: out += resolve(child, depth + 1)
        return out or [(m["effect"], m["args"])]
    return [(m["effect"], m["args"])]

ARG_KEYS = ["Amount", "Percent", "YieldType", "BeliefYieldType", "BiomeType", "TerrainType",
            "ConstructibleType", "SlotType", "Tag", "UnitType", "UnitTag", "UnitClass",
            "GreatWorkObjectType", "Population", "ConstructibleClass", "ConstructibleAdjacency",
            "ConstructibleWarehouseYield", "Enable", "AbilityType"]
def fmt_effect(pairs):
    parts, pct, flat = [], False, False
    for eff, args in pairs:
        kv = []
        for k in ARG_KEYS:
            if k in args and args[k] != "":
                kv.append(f"{k}={args[k]}")
        if "Percent" in args: pct = True
        elif "Amount" in args: flat = True
        seg = f"`{eff}`" + (" (" + ", ".join(kv) + ")" if kv else "")
        parts.append(seg)
    scale = "%" if pct else ("flat" if flat else "—")
    return " · ".join(parts), scale

CLASS_ORDER = ["BELIEF_CLASS_PANTHEON", "BELIEF_CLASS_FOUNDER", "BELIEF_CLASS_RELIQUARY", "BELIEF_CLASS_ENHANCER"]
CLASS_LABEL = {"BELIEF_CLASS_PANTHEON": "Pantheon", "BELIEF_CLASS_FOUNDER": "Founder",
               "BELIEF_CLASS_RELIQUARY": "Reliquary (Relic beliefs)", "BELIEF_CLASS_ENHANCER": "Enhancer"}
def numkey(bt):
    n = re.findall(r'(\d+)', bt)
    return (0 if bt.startswith("PANTHEON") or bt.startswith("BELIEF_BONUS") else 1, int(n[-1]) if n else 0)

byclass = collections.defaultdict(list)
for bt, r in beliefs.items(): byclass[r["class"]].append(bt)

now = datetime.date.today().isoformat()
L = []; W = L.append
W("# Civ VII religion & beliefs catalog (Pantheon / Founder / Reliquary / Enhancer — effect, flat/%, source)")
W("")
W(f"> **Provenance.** Extracted **{now}** from the local install by scanning every `Base\\modules` + `DLC` data XML for")
W(f"> `Beliefs` rows and their `BeliefModifiers`, then resolving each belief's modifier through its `EFFECT_ATTACH_MODIFIERS`")
W(f"> chain to the concrete `EFFECT_*` + arguments in the matching `*-gameeffects.xml`. **{len(beliefs)} beliefs.**")
W("> Regenerate after each patch via [`tools/gen-religion-catalog.py`](../tools/gen-religion-catalog.py).")
W(">")
W("> **Files.** Pantheons: `Base/modules/age-antiquity/data/religion.xml` + `religion-gameeffects.xml`.")
W("> Founder/Reliquary/Enhancer: `Base/modules/age-exploration/data/religion.xml` + `religion-gameeffects.xml`.")
W("> No DLC defines new beliefs (DLC only *grants* existing pantheons via narrative `EFFECT_ADD_PANTHEON`).")
W(">")
W("> **Read the columns:** **Belief** = display name (`BeliefType` id). **Effect** = the resolved concrete effect(s)")
W("> after following `EFFECT_ATTACH_MODIFIERS`, with key args. **±** = magnitude is `flat` (an `Amount`) or `%` (a `Percent`).")
W("> **Plain English** = the in-game description, markup stripped. **Module** = where the belief row is defined.")
W("")
W("> ⚠ **Civ VII has only these four belief classes** — there is **no Follower and no Reformation belief class**")
W("> (both exist in Civ VI, not here). \"Reformation\" in Civ VII is a *civic node* that grants **one extra belief pick**")
W("> via `EFFECT_ADD_BELIEF`, not a class. See the wiring section below.")
W("")

for cls in CLASS_ORDER + [c for c in byclass if c not in CLASS_ORDER]:
    if cls not in byclass: continue
    ci = classes.get(cls, {})
    hdr = f"## {CLASS_LABEL.get(cls, cls)}  ({len(byclass[cls])})"
    meta = []
    if ci.get("max"): meta.append(f"max {ci['max']}/religion")
    if ci.get("order"): meta.append(f"adoption order {ci['order']}")
    if meta: hdr += "  — " + ", ".join(meta)
    W(hdr)
    W("")
    W("| Belief | Effect (resolved `EFFECT_*` + args) | ± | Plain English | Module |")
    W("|--------|-------------------------------------|:--:|---------------|--------|")
    for bt in sorted(byclass[cls], key=numkey):
        r = beliefs[bt]
        name = loc.get(r["name_loc"], r["name_loc"].replace("LOC_", "").replace("_NAME", ""))
        share = " *(shareable)*" if r.get("share") else ""
        pairs = []
        for mid in belief_mods.get(bt, []): pairs += resolve(mid)
        eff, scale = fmt_effect(pairs) if pairs else ("—", "—")
        pe = plain(r["desc_loc"])
        if len(pe) > 240: pe = pe[:237] + "…"
        W(f"| **{name}**{share}<br>`{bt}` | {eff} | {scale} | {pe} | {r['module']} |")
    W("")

# ---- static wiring section -------------------------------------------------
W("## Religion system wiring")
W("")
W("How the pieces connect (verified against the culture/tech trees + `religion-gameeffects.xml`):")
W("")
W("**Pantheon (Antiquity).**")
W("- Unlocked by the **Mysticism** civic (`NODE_CIVIC_AQ_MAIN_MYSTICISM`, main Antiquity culture tree), which grants the")
W("  `MOD_PANTHEON_UNLOCK` modifier → `EFFECT_PLAYER_UNLOCK_PANTHEON`. The same node unlocks **`BUILDING_ALTAR`** — every")
W("  pantheon effect is gated on `REQUIREMENT_PLAYER_HAS_PANTHEON` and almost all pay out *through the Altar* (per-Altar")
W("  yields, Altar adjacencies, or `warehouse` yields active only in settlements that have an Altar).")
W("- **Second pantheon path:** the Maurya unique civic **Acharya** (`NODE_CIVIC_AQ_MAURYA_ACHARYA`) grants")
W("  `MOD_ACHARYA_PANTHEON` → a *second* `EFFECT_PLAYER_UNLOCK_PANTHEON`, letting Maurya choose an additional pantheon.")
W("- **Free/granted pantheons:** narrative events (e.g. Assyria, Ada Lovelace, Tonga DLC) use `EFFECT_ADD_PANTHEON`")
W("  (`Amount=1`) to award a pantheon pick outside the tree. `EFFECT_ADD_PANTHEON` = grant a pick; `EFFECT_PLAYER_UNLOCK_PANTHEON`")
W("  = open the chooser.")
W("- Pantheon beliefs marked *shareable* (`Shareable=true`) may be taken by multiple civs; the rest are exclusive.")
W("")
W("**Religion (Exploration).** You found a religion by earning a **Holy City** (a settlement where your religion originates).")
W("Once founded, the **Theology** civic branch (`NODE_CIVIC_EX_BRANCH_THEOLOGY`, revealed by")
W("`REQUIREMENT_FOUNDED_NO_RELIGION` *inverse* — i.e. you *have* founded one) unlocks the Evangelism tradition and:")
W("- `MOD_REFORMATION_BELIEF` → **`EFFECT_ADD_BELIEF`** (`Amount=1`): the \"Reformation\" — **one extra belief pick**")
W("  (this is the whole of \"reformation\" in Civ VII; the follow-on `NODE_CIVIC_EX_BRANCH_REFORMATION` node continues the branch).")
W("- `MOD_EX_RELIC` → **`EFFECT_GRANT_GREAT_WORK`** (`ObjectType=GREATWORKOBJECT_RELIC`, `Amount=1`): grants a Relic.")
W("  This modifier is attached at *many* Exploration culture **and** tech nodes (Colonialism, Society, Sovereignty, Theology,")
W("  Guilds, Heraldry, Education…), so relics also drip from ordinary tree progress.")
W("- **Belief slots per religion:** Reliquary max 1 (adoption order 1), Founder max 3 (order 2), Enhancer max 1 (order 3).")
W("")
W("**Relics — how they are minted and slotted (the Culture-victory chain).**")
W("- Relics are Great Works of object type **`GREATWORKOBJECT_RELIC`**. They are *minted* mainly by **Reliquary** beliefs,")
W("  each an `EFFECT_ADJUST_PLAYER_RELIC_CONVERTING_*` that awards N relics the **first time** you convert a qualifying target —")
W("  City-State (`_CITY_STATE`), enemy Capital (`_CAPITAL`), a settlement with a Temple/Altar (`_RELIGIOUS_BUILDING`), a Wonder")
W("  (`_WONDER`), Distant-Lands settlement (`_NEW_WORLD`), Treasure-Fleet town (`_TREASURE_FLEETS`), by rural/urban pop threshold")
W("  (`_RURAL_POP`/`_URBAN_POP` with `Population=10`), Holy City (`_HOLY_CITY`), your own city (`_OWNED_CITY_FIRST_TIME`),")
W("  a settlement with ≥3 specialists (`_CITY_WITH_X_SPECIALISTS`), or one with a Natural Wonder (`_NATURAL_WONDER`).")
W("- Relics are *slotted* in **`GREATWORKSLOT_RELIC`** slots. **Sanctum** (`BONUS_8_RELIC_SLOT_TEMPLE`) adds a relic slot to")
W("  every Temple (`EFFECT_CITY_ADJUST_GREAT_WORK_SLOTS`, `ConstructibleType=BUILDING_TEMPLE`); **Parampara**")
W("  (`ENHANCER_BELIEF_BONUS_9`) adds one to `Tag=SCIENCE` buildings. Slotted relics then count toward the **Exploration Culture")
W("  legacy** (`VICTORY_EXPLORATION_CULTURE_GREAT_WORK_SCORING`, `GreatWorkObjectType=GREATWORKOBJECT_RELIC`).")
W("")
W("**Holy City.** Founder beliefs **Covenant** (`BONUS_30`, temple/palace yields in the Holy City) and **Anitya** (`BONUS_29`,")
W("relics for converting a Holy City) key off the Holy City via `REQUIREMENT_CITY_IS_HOLY_CITY` / `..._RELIC_CONVERTING_HOLY_CITY`.")
W("Covenant's yields transfer to your Palace in the Modern Age if the belief is retained.")
W("")
W("**Common effect primitives seen above:** `EFFECT_ADD_RELIGIOUS_BELIEF_YIELD` (Founder per-city/per-biome/per-wonder yields,")
W("keyed by `BeliefYieldType` = `BELIEF_YIELD_PER_FOREIGN_CITY` / `_DOMESTIC_CITY` / `_NATURAL_WONDER` / `_WONDER` / `_BIOME` /")
W("`_TERRAIN_TYPE`); `EFFECT_PLAYER_ADJUST_CONSTRUCTIBLE_YIELD` & `EFFECT_CITY_ACTIVATE_CONSTRUCTIBLE_WAREHOUSE_YIELD`/`_ADJACENCY`")
W("(Altar-based pantheon yields); `EFFECT_ENABLE_RELIGION_AUTO_SPREAD_*` (auto-conversion enhancers).")

os.makedirs(REFDIR, exist_ok=True)
open(os.path.join(REFDIR, "religion-and-beliefs-catalog.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("religion-and-beliefs-catalog.md:", len(beliefs), "beliefs /",
      {CLASS_LABEL.get(c, c): len(v) for c, v in byclass.items()})
