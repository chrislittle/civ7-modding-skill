import os, re, glob, collections, datetime
# Generates references/triumphs-legacies-catalog.md: EVERY base-game Triumph (the `Legacies` table rows) with its
# Age, class (CULTURAL/DIPLOMATIC/ECONOMIC/EXPANSIONIST/MILITARISTIC/SCIENTIFIC), Major/Minor tier, First-to? flag,
# trigger text ("Build 7 Wonders"), reward effect, archetype, and which Legacy SET it belongs to (DEFAULT / RACE /
# CONQUEROR / EXPLORER / CRISIS).
# WHY: native Triumphs already own "count / first-to N of X" earn-triggers (wonders, population, settlements,
# resources, codices, relics, artifacts, trade routes, suzerains, techs, gold, commander levels...). A mod that adds
# its own earn-triggers must NOT duplicate a native metric. Grep this before authoring a Triumph/Legacy earn-trigger.
# The 3 layers are distinct: Legacy PATHS (victories.xml, the 4/age pacing engine) vs TRIUMPHS (this = `Legacies`)
# vs DEDICATIONS (`AdvancedStartCards`). DLC adds ZERO Triumphs (all DLC *legacy* files are civ->Age bindings).
# Regenerate after each patch:  py -3 tools/gen-triumphs-catalog.py

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
row_re  = re.compile(r'<Row\b([^>]*?)/?>')
row_text_re = re.compile(r'<Row\b[^>]*\bTag="(LOC_[A-Z0-9_]+)"[^>]*>\s*<Text>(.*?)</Text>', re.S)
mod_re  = re.compile(r'<Modifier\s+id="(MOD_LEGACY_[^"]+)"(.*?)</Modifier>', re.S)

def all_xml(*needles):
    out = []
    for base in (os.path.join(ROOT, "Base", "modules"), os.path.join(ROOT, "DLC")):
        for fp in glob.glob(os.path.join(base, "**", "*.xml"), recursive=True):
            low = fp.lower()
            if any(n in low for n in needles): out.append(fp)
    return out

# ---- LOC -> English (names + trigger descriptions live in Legacies*Text.xml; scan broadly to be safe) ------------
loc = {}
for fp in all_xml("text"):
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    if "LOC_LEGACY_" not in txt and "LOC_UNLOCK_" not in txt and "LOC_CARD_" not in txt: continue
    for tag, en in row_text_re.findall(txt):
        loc.setdefault(tag, en)

def clean(loc_key):
    """Resolve a LOC key to English and strip Civ text markup ([B],[icon:..],[TIP:..]inner[/TIP],[LIST]..)."""
    s = loc.get(loc_key)
    if s is None: return ""
    s = re.sub(r'\[/?[^\]]*\]', '', s)            # drop every [..] token, keeping inner text
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"), ("&apos;", "'")):
        s = s.replace(a, b)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# ---- rewards: MOD_LEGACY_<suffix> in *legacies-gameeffects.xml  ->  effect + first argument ----------------------
reward = {}   # LEGACY_<suffix> -> "EFFECT_SHORT: arg"
for fp in all_xml("legacies-gameeffects", "legacy-gameeffects"):
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    for mid, body in mod_re.findall(txt):
        d = dict(attr_re.findall(re.match(r'[^>]*', "<Modifier id=\"%s\"%s" % (mid, body)).group(0)))
        eff = d.get("effect", "")
        am = re.search(r'<Argument\s+name="([^"]+)">\s*([^<]*?)\s*</Argument>', body)
        short = eff.replace("EFFECT_PLAYER_", "").replace("EFFECT_CITY_", "CITY_").replace("EFFECT_", "")
        arg = ""
        if am: arg = "%s=%s" % (am.group(1), am.group(2).strip())
        legkey = "LEGACY_" + mid[len("MOD_LEGACY_"):]
        reward[legkey] = (short + (": " + arg if arg else "")).strip()

# ---- Triumphs: <Legacies><Row .. Age=..></Legacies> in the 3 age modules --------------------------------------
AGE = {"AGE_ANTIQUITY": "Antiquity", "AGE_EXPLORATION": "Exploration", "AGE_MODERN": "Modern"}
AGE_ORDER = {"Antiquity": 0, "Exploration": 1, "Modern": 2}
rows = []
seen = set()
for fp in all_xml("legacies.xml"):
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    for attrs in row_re.findall(txt):
        d = dict(attr_re.findall(attrs))
        lt = d.get("LegacyType")
        if not lt or "Age" not in d or "LegacySubtype" not in d: continue   # only real Triumph defs
        if lt in seen: continue
        seen.add(lt)
        rows.append(d)

def legacy_set(lt):
    if lt.endswith("_RACE"):          return "RACE"
    if "_CONQUEROR_" in lt:           return "CONQUEROR"
    if "_EXPLORER_" in lt:            return "EXPLORER"
    if "_CRISIS_" in lt:              return "CRISIS"
    return "DEFAULT"

def cls_of(d):
    sub = d.get("LegacySubtype", "").replace("LEGACY_", "")
    return sub if sub in ("CULTURAL","DIPLOMATIC","ECONOMIC","EXPANSIONIST","MILITARISTIC","SCIENTIFIC") else sub

def archetype(d, trig):
    first = d.get("FirstPlayerOnly", "false").lower() == "true"
    hasnum = bool(re.search(r'\d', trig))
    tl = trig.lower()
    if first and re.search(r'first to (study|discover|research|complete the|reach the|be the|found)', tl) and not hasnum:
        return "discovery-first"
    if first and hasnum:      return "first-to-race"
    if first:                 return "discovery-first"
    if hasnum:                return "count-threshold"
    return "situational-combo"

recs = []
for d in rows:
    lt = d["LegacyType"]
    recs.append({
        "type": lt,
        "age": AGE.get(d["Age"], d["Age"]),
        "set": legacy_set(lt),
        "cls": cls_of(d),
        "major": d.get("MajorLegacy", "true").lower() != "false",
        "first": d.get("FirstPlayerOnly", "false").lower() == "true",
        "inactive": d.get("Inactive", "false").lower() == "true",
        "name": clean(d.get("Name", "")) or d.get("Name", ""),
        "trig": clean(d.get("TriggerDescription", "")),
        "reward": reward.get(lt, ""),
    })
    recs[-1]["arch"] = archetype(d, recs[-1]["trig"])

# ================================================================================================================
now = datetime.date.today().isoformat()
CLASS_ORDER = ["CULTURAL", "DIPLOMATIC", "ECONOMIC", "EXPANSIONIST", "MILITARISTIC", "SCIENTIFIC"]
L = []; W = L.append

default = [r for r in recs if r["set"] == "DEFAULT"]
alt     = [r for r in recs if r["set"] != "DEFAULT"]

W("# Civ VII Triumphs / Legacies catalog (native earn-triggers — don't duplicate these)")
W("")
W(f"> **Provenance.** Extracted **{now}** from the local install: the three age modules'")
W("> `Base\\modules\\age-{antiquity,exploration,modern}\\data\\legacies.xml` (`<Legacies>` rows), joined to reward")
W("> effects in the matching `legacies-gameeffects.xml` (`MOD_LEGACY_*` -> `EFFECT_*`) and trigger/name text in")
W("> `base-standard\\text\\en_us\\LegaciesText.xml` + `LegaciesScreenText.xml`.")
W(f"> **{len(recs)} Triumph rows** total ({len(default)} in the DEFAULT set, {len(alt)} in alternate sets).")
W("> Regenerate after each patch: `py -3 tools/gen-triumphs-catalog.py`.")
W(">")
W("> **DLC adds ZERO Triumphs.** Every DLC `*legacy*` file is `civilizations-legacy.xml` (a civ->Age *binding*), not a")
W("> `Legacies` row. The Triumph roster is fixed by the base game's three age modules.")
W("")
W("## The three layers (do not conflate)")
W("")
W("Civ VII stacks three separate systems people loosely call \"legacies\":")
W("")
W("| Layer | Data home | What it is |")
W("|-------|-----------|------------|")
W("| **Legacy Paths** | `victories.xml` (`LegacyPath*`) | The 4-per-age **pacing engine** (Cultural/Economic/Military/Science progress bars + Age-progress). NOT in this catalog. |")
W("| **Triumphs** | `legacies.xml` (`Legacies`) | **This catalog.** Discrete earn-once achievements. **Major** -> unlock a Dedication for next Age; **Minor** -> instant bonus this Age. |")
W("| **Dedications** | `AdvancedStartCards` | The next-Age boost cards a **Major** Triumph unlocks; chosen at Age start. NOT in this catalog. |")
W("")
W("## How to read a Triumph row")
W("")
W("- **Major / Minor** = `MajorLegacy` (default true). Major unlocks a Dedication (reward is usually")
W("  `GRANT_UNLOCK: UNLOCK_*`); Minor grants an instant effect (yield / unit / slot / population).")
W("- **First-to?** = `FirstPlayerOnly=\"true\"` -> a competitive race, only the first player to hit it scores it")
W("  (\"First to have 6 Altars\"). Otherwise every player who meets the threshold earns it.")
W("- **Archetype** = shape of the trigger: `count-threshold` (own/build N of X) - `first-to-race` (first to N of X) -")
W("  `discovery-first` (first to study/complete a specific thing) - `situational-combo` (a bespoke condition).")
W("- **Modern is all-Minor:** every Modern-age Triumph is `MajorLegacy=false` (no Age follows, so no Dedication to")
W("  unlock) - they grant instant bonuses only.")
W("")

def emit_table(items):
    W("| Triumph (name) | Trigger | Tier | First-to? | Archetype | Reward effect |")
    W("|----------------|---------|:----:|:---------:|-----------|---------------|")
    for r in sorted(items, key=lambda r: (r["type"])):
        tier  = "Major" if r["major"] else "Minor"
        first = "yes" if r["first"] else ""
        trig  = r["trig"] or "—"
        rew   = ("`%s`" % r["reward"]) if r["reward"] else "—"
        nm    = r["name"] or r["type"]
        flag  = " *(inactive)*" if r["inactive"] else ""
        W(f"| {nm}{flag} | {trig} | {tier} | {first} | {r['arch']} | {rew} |")
    W("")

for age in ("Antiquity", "Exploration", "Modern"):
    ar = [r for r in default if r["age"] == age]
    W(f"## {age} — DEFAULT set  ({len(ar)} Triumphs)")
    W("")
    for cls in CLASS_ORDER:
        cr = [r for r in ar if r["cls"] == cls]
        if not cr: continue
        W(f"### {cls}  ({len(cr)})")
        W("")
        emit_table(cr)

# ---- alternate sets -------------------------------------------------------------------------------------------
W("## Alternate Legacy sets (non-DEFAULT game modes)")
W("")
W("These rows only appear under non-default rulesets (`LegacySets` in `base-standard\\data\\legacies.xml`):")
W("**RACE** = the competitive \"first-to\" mirror of the default Triumphs; **CONQUEROR** / **EXPLORER** = alternate")
W("age-specific sets; **CRISIS** = crisis-response policy unlocks (all `Inactive`, wired through the crisis system).")
W("They reuse the same class tags and reward effects; listed here so a mod knows they exist and doesn't collide.")
W("")
for setname in ("RACE", "CONQUEROR", "EXPLORER", "CRISIS"):
    sr = [r for r in alt if r["set"] == setname]
    if not sr: continue
    W(f"### {setname} set  ({len(sr)})")
    W("")
    emit_table(sr)

# ---- archetype distribution ------------------------------------------------------------------------------------
def dist(items):
    c = collections.Counter(r["arch"] for r in items)
    return c
dc = dist(default)
tot = len(default)
countish = dc.get("count-threshold", 0) + dc.get("first-to-race", 0)
W("## Archetype distribution (DEFAULT set)")
W("")
W("| Archetype | Count | Share |")
W("|-----------|------:|------:|")
for a in ("count-threshold", "first-to-race", "discovery-first", "situational-combo"):
    n = dc.get(a, 0)
    W(f"| {a} | {n} | {100.0*n/tot:.0f}% |")
W(f"| **total** | **{tot}** | 100% |")
W("")
W(f"**~{100.0*(countish+dc.get('discovery-first',0))/tot:.0f}% of native Triumphs are count / first-to / discovery-first**")
W("(a numeric threshold on a game metric, or first-to-a-milestone). Only")
W(f"{dc.get('situational-combo',0)} are bespoke `situational-combo` conditions. **Implication for modders:** the native")
W("system already blankets \"reach N of <metric>\" and \"be first to <milestone>\". A mod's own earn-triggers should")
W("target *new* conditions, not re-skin a metric native already scores.")
W("")

# ---- metrics native already owns -------------------------------------------------------------------------------
W("## Metrics native Triumphs already own — DON'T duplicate")
W("")
W("Reconstructed from the DEFAULT trigger texts. Before adding a Triumph/Legacy earn-trigger, check this list — if")
W("your metric is here, native already scores \"count N\" and/or \"first to N\" of it; pick a genuinely new axis instead.")
W("")
for line in [
    "**Wonders** built (e.g. \"Build 7 Wonders\")",
    "**Population** / population in a single Settlement (\"have a Settlement of population N\")",
    "**Settlements / Towns / Cities** founded or owned; largest-empire race",
    "**Buildings of a class** — Altars, and other tagged constructibles counted to a threshold",
    "**Resources** assigned / **unique resources** acquired",
    "**Codices** (Science) collected",
    "**Relics** (Culture) collected",
    "**Artifacts** excavated / **Great Works** amassed",
    "**Trade Routes** established / active",
    "**City-States / Suzerains** — number befriended or made Suzerain of",
    "**Techs / Masteries / Civics** — *first to study* a specific one (Philosophy, etc.); first to complete a tree",
    "**Gold** — total treasury / gold spent / gold-per-turn thresholds",
    "**Commanders** — number trained or **Commander level** reached; units promoted",
    "**Military** — enemy units defeated, cities captured/conquered, war outcomes (CONQUEROR set)",
    "**Great People** recruited",
    "**Religion** — cities/population following your religion, first to found (where present)",
    "**Exploration** — tiles/continents/Distant-Lands revealed, Treasure Fleets (EXPLORER set)",
    "**Improvements / tiles worked**, luxury/happiness thresholds",
]:
    W(f"- {line}")
W("")
W("> These are the axes the base Triumph roster measures. Owning \"count/first-to N of X\" for these metrics is native's")
W("> job. A mod adds value with *orthogonal* triggers (new mechanics, combos, tall-play conditions) — not by re-scoring X.")
W("")

os.makedirs(REFDIR, exist_ok=True)
open(os.path.join(REFDIR, "triumphs-legacies-catalog.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
byset = collections.Counter(r["set"] for r in recs)
print("triumphs-legacies-catalog.md:", len(recs), "rows; sets:", dict(byset))
print("DEFAULT archetypes:", dict(dc))
print("DEFAULT by class:", dict(collections.Counter(r["cls"] for r in default)))
print("DEFAULT by age:", dict(collections.Counter(r["age"] for r in default)))
