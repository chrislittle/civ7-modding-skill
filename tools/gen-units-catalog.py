import os, re, glob, collections, datetime
# Generates references/units-catalog.md: EVERY unit (base + all DLC) with its CoreClass/domain/formation,
# combat stats, cost, the Age + node that UNLOCKS it (or "default"/civ-unique trait), and its UNIT_CLASS_* tags;
# PLUS the unit-class-tag vocabulary, the Commander line (unlock + free grants), and the promotion DISCIPLINE trees.
# WHY: unit facts (which tag = "combat", how commanders are unlocked/free-granted, what a promotion does, a unit's
# real Age) are scattered across units.xml / progression-trees / gameeffects / unit-promotions and are easy to guess
# wrong. Grep this before asserting a unit fact. Regenerate after each patch.

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
row_re = re.compile(r'<Row\b([^>]*?)/?>')
sec_re = lambda name, txt: (re.search(r'<%s>(.*?)</%s>' % (name, name), txt, re.S) or None)
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

def module_of(path):
    p = path.replace("\\", "/").lower()
    if "/age-antiquity/" in p: return "AQ"
    if "/age-exploration/" in p: return "EX"
    if "/age-modern/" in p: return "MO"
    if "/base-standard/" in p: return "Base"
    m = re.search(r'/dlc/([^/]+)/', p)
    if m: return "DLC:" + m.group(1)
    return "?"

def node_age(node):
    if "_AQ_" in node: return "AQ"
    if "_EX_" in node: return "EX"
    if "_MO_" in node: return "MO"
    return ""

# ---- LOC -> English (display names) ----
loc = {}
for fp in textfiles():
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    for tag, en in row_text_re.findall(txt):
        loc.setdefault(tag, re.sub(r'\s+', ' ', en.strip()))
def name(locid, fallback=""):
    if not locid: return fallback
    return loc.get(locid, fallback or locid.replace("LOC_", "").replace("_NAME", ""))

# ---- pass 1: units, stats, costs, tags (section-scoped so ids never collide) ----
units = {}                              # UnitType -> def record (first def wins)
stats = {}                              # UnitType -> {Combat,RangedCombat,Bombard,Range}
costs = collections.defaultdict(list)   # UnitType -> [(YieldType,Cost)]
tags  = collections.defaultdict(set)    # UnitType -> {UNIT_CLASS_*, AGELESS,...}
alltags = {}                            # tag -> category (the vocabulary)
for fp in datafiles():
    if not fp.lower().endswith("units.xml") and "units-shared" not in fp.lower(): continue
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    mod = module_of(fp)
    m = sec_re("Tags", txt)
    if m:
        for a in row_re.findall(m.group(1)):
            d = dict(attr_re.findall(a))
            if d.get("Tag"): alltags[d["Tag"]] = d.get("Category", "")
    m = sec_re("Units", txt)
    if m:
        for a in row_re.findall(m.group(1)):
            d = dict(attr_re.findall(a))
            ut = d.get("UnitType")
            if ut and d.get("CoreClass") and ut not in units:  # a genuine definition row
                units[ut] = {
                    "name":  name(d.get("Name", ""), ut.replace("UNIT_", "").title()),
                    "core":  d.get("CoreClass", "").replace("CORE_CLASS_", ""),
                    "domain": d.get("Domain", "").replace("DOMAIN_", ""),
                    "formation": d.get("FormationClass", "").replace("FORMATION_CLASS_", ""),
                    "move":  d.get("UnitMovementClass", "").replace("UNIT_MOVEMENT_CLASS_", ""),
                    "tier":  d.get("Tier", ""),
                    "maint": d.get("Maintenance", ""),
                    "moves": d.get("BaseMoves", ""),
                    "trait": d.get("TraitType", ""),
                    "promoclass": d.get("PromotionClass", "").replace("PROMOTION_CLASS_", ""),
                    "found": d.get("FoundCity", "") == "true",
                    "trade": d.get("MakeTradeRoute", "") == "true",
                    "zoc":   d.get("ZoneOfControl", ""),
                    "cantrain": d.get("CanTrain", "true").lower() != "false",
                    "module": mod,
                }
    m = sec_re("Unit_Stats", txt)
    if m:
        for a in row_re.findall(m.group(1)):
            d = dict(attr_re.findall(a))
            ut = d.get("UnitType")
            if ut and ut not in stats and any(k in d for k in ("Combat", "RangedCombat", "Bombard", "Range")):
                stats[ut] = d
    m = sec_re("Unit_Costs", txt)
    if m:
        for a in row_re.findall(m.group(1)):
            d = dict(attr_re.findall(a))
            ut = d.get("UnitType")
            if ut and d.get("Cost"): costs[ut].append((d.get("YieldType", ""), d["Cost"]))
    m = sec_re("TypeTags", txt)
    if m:
        for a in row_re.findall(m.group(1)):
            d = dict(attr_re.findall(a))
            if d.get("Type") and d.get("Tag"): tags[d["Type"]].add(d["Tag"])

# ---- pass 1b: civ -> Age and civ-unique TraitType -> Age (resolves DLC civ units with no tech-node unlock) ----
AGE_ATTR = {"AGE_ANTIQUITY": "AQ", "AGE_EXPLORATION": "EX", "AGE_MODERN": "MO"}
civ_age = {}                              # CIVILIZATION_* -> AQ/EX/MO
civ_traits = collections.defaultdict(list)  # CIVILIZATION_* -> [TRAIT_*]
for fp in datafiles():
    if "civilizations" not in fp.lower() or not fp.lower().endswith(".xml"): continue
    if "gameeffects" in fp.lower(): continue
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    for a in row_re.findall(txt):
        d = dict(attr_re.findall(a))
        c = d.get("CivilizationType")
        if not c: continue
        if d.get("Age") in AGE_ATTR: civ_age.setdefault(c, AGE_ATTR[d["Age"]])
        if d.get("TraitType") and not d.get("Name"): civ_traits[c].append(d["TraitType"])
trait_age = {}                            # TRAIT_* -> AQ/EX/MO (civ-unique trait carried on a unit)
for c, ts in civ_traits.items():
    if c in civ_age:
        for t in ts: trait_age.setdefault(t, civ_age[c])

# ---- pass 2: unit UNLOCKS (ProgressionTreeNodeUnlocks rows, KIND_UNIT) ----
unlocks = collections.defaultdict(list)   # UnitType -> [(node, requiredTrait)]
for fp in datafiles():
    low = fp.lower()
    if not (("progression-trees" in low or "unlocks" in low) and low.endswith(".xml")): continue
    if "gameeffects" in low: continue
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    m = sec_re("ProgressionTreeNodeUnlocks", txt)
    if not m: continue
    for a in row_re.findall(m.group(1)):
        d = dict(attr_re.findall(a))
        if d.get("TargetKind") == "KIND_UNIT" and d.get("TargetType"):
            unlocks[d["TargetType"]].append((d.get("ProgressionTreeNodeType", ""), d.get("RequiredTraitType", "")))

# ---- pass 3: free-grant effects (EFFECT_CITY_GRANT_UNIT) ----
grants = collections.defaultdict(list)    # UnitType -> [(modifier id, module)]
mod_block = re.compile(r'<Modifier\b[^>]*\beffect="EFFECT_CITY_GRANT_UNIT"[^>]*>(.*?)</Modifier>', re.S)
mod_id    = re.compile(r'<Modifier\b[^>]*\bid="([^"]+)"')
for fp in datafiles():
    if "gameeffects" not in fp.lower(): continue
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    mod = module_of(fp)
    for m in re.finditer(r'<Modifier\b([^>]*)\beffect="EFFECT_CITY_GRANT_UNIT"[^>]*>(.*?)</Modifier>', txt, re.S):
        head, body = m.group(1), m.group(2)
        mid = (re.search(r'\bid="([^"]+)"', head) or [None, ""])[1]
        um = re.search(r'name="UnitType"\s*>\s*([A-Z0-9_]+)', body)
        if um: grants[um.group(1)].append((mid, mod))

# ---- pass 4: promotion disciplines + promotions ----
DISC = {}       # discipline -> {"name":..., "module":...}
DISC_PROMOS = collections.defaultdict(list)   # discipline -> [(promo, prereq, grantsCommend)]
PROMO = {}      # promo -> {"name":..., "desc":..., "commend":bool}
PROMO_CLASS = {}   # promotion class -> discipline list (from ClassSets)
CLASSSET = collections.defaultdict(list)  # promotion class -> [discipline]
for fp in datafiles():
    if not fp.lower().endswith("unit-promotions.xml"): continue
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    mod = module_of(fp)
    m = sec_re("UnitPromotionDisciplines", txt)
    if m:
        for a in row_re.findall(m.group(1)):
            d = dict(attr_re.findall(a))
            t = d.get("UnitPromotionDisciplineType")
            if t: DISC.setdefault(t, {"name": name(d.get("Name", ""), t), "module": mod})
    m = sec_re("UnitPromotionDisciplineDetails", txt)
    if m:
        for a in row_re.findall(m.group(1)):
            d = dict(attr_re.findall(a))
            disc = d.get("UnitPromotionDisciplineType"); pr = d.get("UnitPromotionType")
            if disc and pr:
                DISC_PROMOS[disc].append((pr, d.get("PrereqUnitPromotion", ""), d.get("GrantsCommendation", "") == "true"))
    m = sec_re("UnitPromotions", txt)
    if m:
        for a in row_re.findall(m.group(1)):
            d = dict(attr_re.findall(a))
            t = d.get("UnitPromotionType")
            if t and t not in PROMO:
                PROMO[t] = {"name": name(d.get("Name", ""), t), "desc": name(d.get("Description", ""), ""),
                            "commend": d.get("Commendation", "") == "true"}
    m = sec_re("UnitPromotionClassSets", txt)
    if m:
        for a in row_re.findall(m.group(1)):
            d = dict(attr_re.findall(a))
            pc = d.get("PromotionClassType"); disc = d.get("UnitPromotionDisciplineType")
            if pc and disc: CLASSSET[pc].append(disc)

# ---- derive each unit's Age ----
AGEORD = {"AQ": 0, "EX": 1, "MO": 2, "Core": 3, "": 4}
def unit_age(ut, rec):
    ages = {node_age(n) for n, t in unlocks.get(ut, []) if node_age(n)}
    # also let the required-trait on an unlock row (or the unit's own trait) resolve via civ Age
    ta = trait_age.get(rec.get("trait", ""))
    if not ages:
        for n, t in unlocks.get(ut, []):
            if trait_age.get(t): ages.add(trait_age[t])
    if len(ages) == 1: return next(iter(ages))
    if ages: return "/".join(sorted(ages, key=lambda a: AGEORD.get(a, 9)))
    mod = rec["module"]
    if mod in ("AQ", "EX", "MO"): return mod
    if ta: return ta                       # DLC civ-unique w/ no tech-node unlock -> the civ's Age
    if mod == "Base": return "Core"
    return ""   # unresolved (rare)

# =================== EMIT ===================
now = datetime.date.today().isoformat()
L = []; W = L.append
W("# Civ VII units catalog (base + all DLC — stats, unlocks, classes, commanders, promotions)")
W("")
W(f"> **Provenance.** Extracted **{now}** from the local install, scanning every `Base\\modules` + `DLC` "
  f"`units.xml` (+ `units-shared.xml`), `progression-trees-*.xml` / `unlocks*.xml` (`ProgressionTreeNodeUnlocks`), "
  f"`*-gameeffects.xml` (`EFFECT_CITY_GRANT_UNIT`), and `unit-promotions.xml`. "
  f"**{len(units)} units, {len(DISC)} promotion disciplines, {len(PROMO)} promotions.**")
W("> Regenerate after each patch via [`tools/gen-units-catalog.py`](../tools/gen-units-catalog.py).")
W(">")
W("> **Read the columns:**")
W("> - **Stats** = `Combat` / `RangedCombat` (R) / `Bombard` (B) / `Range` from `Unit_Stats`. Blank = non-combat.")
W("> - **Unlock** = the `ProgressionTreeNodeType` whose `ProgressionTreeNodeUnlocks` row (`TargetKind=KIND_UNIT`) "
  "unlocks it. `default` = no unlock row → trainable from the Age's start (e.g. Warrior). "
  "`civ:TRAIT_*` = civ-unique (the row carries `RequiredTraitType`, or the unit's own `TraitType`).")
W("> - **Age** = derived from the unlock node prefix (`_AQ_`/`_EX_`/`_MO_`); falls back to the defining module. "
  "`Core` = base-standard, Age-agnostic (commanders, Settler, Scout, Merchant).")
W("> - **Class tags** = the `UNIT_CLASS_*` `TypeTags`. **`UNIT_CLASS_COMBAT` is the flag that marks a trainable "
  "military unit** (see the vocabulary section). `AGELESS` = survives Age transitions (all Commanders).")
W("")
W("---")
W("")

# ---- Section 1: Units by Age ----
W("## 1. Units (by Age)")
W("")
def stat_str(ut):
    s = stats.get(ut)
    if not s: return ""
    parts = []
    if s.get("Combat"): parts.append(s["Combat"])
    if s.get("RangedCombat"): parts.append("R" + s["RangedCombat"])
    if s.get("Bombard"): parts.append("B" + s["Bombard"])
    if s.get("Range"): parts.append("rng" + s["Range"])
    return " ".join(parts)
def cost_str(ut):
    cs = costs.get(ut)
    if not cs: return ""
    return ", ".join((c if y in ("YIELD_PRODUCTION", "") else c + y.replace("YIELD_", " ")[:4]) for y, c in cs)
def unlock_str(ut, rec):
    us = unlocks.get(ut, [])
    trait = rec.get("trait", "")
    if not us:
        if trait: return "civ:" + trait.replace("TRAIT_", "")
        return "default"
    outp = []
    for n, t in us:
        node = n.replace("NODE_TECH_", "T:").replace("NODE_CIVIC_", "C:")
        node = re.sub(r'^(T:|C:)(AQ_|EX_|MO_)', r'\1', node)
        if t: node += " [civ:" + t.replace("TRAIT_", "") + "]"
        elif trait: node += " [civ:" + trait.replace("TRAIT_", "") + "]"
        outp.append(node)
    # de-dup preserve order
    seen = set(); ded = [x for x in outp if not (x in seen or seen.add(x))]
    return "; ".join(ded)
def notes_str(ut, rec):
    n = []
    if rec["promoclass"]: n.append("Commander/" + rec["promoclass"])
    if rec["found"]: n.append("founds settlement")
    if rec["trade"]: n.append("trade route")
    if not rec["cantrain"] and not rec["promoclass"]: n.append("not trainable")
    ct = tags.get(ut, set())
    if "AGELESS" in ct: n.append("AGELESS")
    if rec["move"]: n.append(rec["move"].lower())
    return ", ".join(n)

# resolve ages, then family-propagate (UNIT_FOO tier-1 with no unlock inherits from UNIT_FOO_2 etc.)
age_of = {ut: unit_age(ut, rec) for ut, rec in units.items()}
fam_age = {}
for ut, a in age_of.items():
    if a and a not in ("Core", ""):
        fam_age.setdefault(re.sub(r'_\d+$', '', ut), a)
for ut in age_of:
    if not age_of[ut]:
        fa = fam_age.get(re.sub(r'_\d+$', '', ut))
        if fa: age_of[ut] = fa
by_age = collections.defaultdict(list)
for ut in units:
    by_age[age_of[ut]].append(ut)
def classtags_str(ut):
    ct = sorted(t.replace("UNIT_CLASS_", "") for t in tags.get(ut, set()) if t.startswith("UNIT_CLASS_"))
    return " ".join(ct)
for age in sorted(by_age, key=lambda a: (AGEORD.get(a, 9), a)):
    items = sorted(by_age[age], key=lambda u: (units[u]["tier"] or "9", units[u]["core"], units[u]["name"]))
    label = {"AQ": "Antiquity", "EX": "Exploration", "MO": "Modern", "Core": "Core / Age-agnostic",
             "": "Unresolved (dev/sandbox or Age not derivable)"}.get(age, age)
    W(f"### {label}  ({len(items)})")
    W("")
    W("| Tier | Type | Name | Core/Domain | Stats | Cost | Unlock | Class tags | Notes |")
    W("|:---:|------|------|------|------|-----:|------|------|------|")
    for ut in items:
        r = units[ut]
        cd = (r["core"] + ("/" + r["domain"] if r["domain"] else ""))
        W(f"| {r['tier'] or '—'} | `{ut}` | {r['name']} | {cd} | {stat_str(ut)} | {cost_str(ut)} | "
          f"{unlock_str(ut, r)} | {classtags_str(ut)} | {notes_str(ut, r)} |")
    W("")

# ---- Section 2: Unit-class-tag vocabulary ----
W("---")
W("")
W("## 2. Unit class tags (`UNIT_CLASS_*` vocabulary)")
W("")
W("Every trainable military unit carries **`UNIT_CLASS_COMBAT`**; civilians/support carry `UNIT_CLASS_NON_COMBAT`. "
  "Role tags (`MELEE`/`RANGED`/`CAVALRY`/`SIEGE`/`NAVAL`/...) stack on top and drive promotions, bonuses, and AI. "
  "A tag is applied via a `<Row Type=\"UNIT_*\" Tag=\"UNIT_CLASS_*\"/>` row in the `<TypeTags>` block of `units.xml`.")
W("")
counts = collections.Counter()
for ut, ts in tags.items():
    for t in ts:
        if t.startswith("UNIT_CLASS_"): counts[t] += 1
W("| Tag | # units | Example units |")
W("|-----|--------:|---------------|")
for t in sorted(alltags, key=lambda x: (-counts.get(x, 0), x)):
    if not t.startswith("UNIT_CLASS_"): continue
    ex = [u for u in units if t in tags.get(u, set())][:4]
    exn = ", ".join(units[u]["name"] for u in ex)
    W(f"| `{t}` | {counts.get(t,0)} | {exn} |")
W("")

# ---- Section 3: Commander line ----
W("---")
W("")
W("## 3. Commander line")
W("")
W("Commanders are `FORMATION_CLASS_COMMAND`, `CanEarnExperience=true`, **AGELESS** (carry across Ages), and cost-scale "
  "per copy (`COST_PROGRESSION_PREVIOUS_COPIES`). Each has its own `PromotionClass` feeding the disciplines in section 4. "
  "The **Army Commander is free-granted** at the Antiquity *Discipline* civic (`NODE_CIVIC_AQ_MAIN_DISCIPLINE`) via "
  "`MOD_DISCIPLINE_FREE_COMMANDER` (`EFFECT_CITY_GRANT_UNIT` on `COLLECTION_PLAYER_CAPITAL_CITY`, `run-once`).")
W("")
W("| Unit | Name | Domain | Promotion class | Unlocked by | Free grant |")
W("|------|------|--------|-----------------|-------------|------------|")
for ut in ("UNIT_ARMY_COMMANDER", "UNIT_FLEET_COMMANDER", "UNIT_SQUADRON_COMMANDER", "UNIT_CARRIER_COMMANDER", "UNIT_AERODROME_COMMANDER"):
    if ut not in units: continue
    r = units[ut]
    ul = unlock_str(ut, r)
    gr = "; ".join(f"`{mid}` ({mod})" for mid, mod in grants.get(ut, [])) or "—"
    W(f"| `{ut}` | {r['name']} | {r['domain']} | {r['promoclass']} | {ul} | {gr} |")
W("")
# other notable free-granted units
notable = [(ut, g) for ut, g in grants.items() if ut in units and ut not in
           ("UNIT_ARMY_COMMANDER", "UNIT_FLEET_COMMANDER", "UNIT_SQUADRON_COMMANDER", "UNIT_CARRIER_COMMANDER")]
if notable:
    W("**Other units granted by `EFFECT_CITY_GRANT_UNIT`** (free-unit effects — traditions, wonders, narrative, etc.):")
    W("")
    W("| Unit | # grant modifiers | Sample modifier |")
    W("|------|------:|-----------------|")
    for ut, g in sorted(notable, key=lambda x: -len(x[1]))[:30]:
        W(f"| `{ut}` ({units[ut]['name']}) | {len(g)} | `{g[0][0]}` ({g[0][1]}) |")
    W("")

# ---- Section 4: Promotion disciplines ----
W("---")
W("")
W("## 4. Promotion disciplines & promotions")
W("")
W("Commanders spend earned XP inside **disciplines** (skill trees). Each `UnitPromotionDisciplineDetails` row places a "
  "promotion in a discipline with an optional `PrereqUnitPromotion` (the tree edges); `GrantsCommendation=true` marks a "
  "capstone that hands out a Commendation. **Commendations** (`Commendation=true`) are the meta-rewards granted on "
  "reaching a cap. Below, each discipline lists its promotions as `Promotion (prereq)` with the effect text.")
W("")
# group disciplines by commander family via name prefix
def disc_family(d):
    for k in ("ARMY", "FLEET", "SQUADRON", "AERODROME", "CARRIER"):
        if "_" + k + "_" in d or d.endswith("_" + k): return k
    return "OTHER"
fam_order = ["ARMY", "FLEET", "SQUADRON", "CARRIER", "AERODROME", "OTHER"]
by_fam = collections.defaultdict(list)
for d in DISC: by_fam[disc_family(d)].append(d)
for fam in fam_order:
    if fam not in by_fam: continue
    W(f"### {fam.title()} disciplines")
    W("")
    for disc in sorted(by_fam[fam]):
        info = DISC[disc]
        promos = DISC_PROMOS.get(disc, [])
        if not promos and "COMMENDATION" in disc: continue  # commendation "disciplines" are single-promo shells
        W(f"**`{disc}`** — {info['name']}  ({len(promos)} promotions)")
        W("")
        if promos:
            W("| Promotion | Prereq | Effect |")
            W("|-----------|--------|--------|")
            seen = set()
            for pr, prereq, gc in promos:
                key = (pr, prereq)
                if key in seen: continue
                seen.add(key)
                p = PROMO.get(pr, {"name": pr, "desc": ""})
                pn = p["name"] + (" *(→commendation)*" if gc else "")
                pq = PROMO.get(prereq, {}).get("name", "") if prereq else "—"
                W(f"| {pn} (`{pr.replace('PROMOTION_','')}`) | {pq or '—'} | {p['desc']} |")
            W("")

# ---- Commendations list ----
comm = [p for p in PROMO if PROMO[p]["commend"]]
if comm:
    W("### Commendations (meta-rewards)")
    W("")
    W("| Commendation | Effect |")
    W("|--------------|--------|")
    seen = set()
    for p in sorted(comm):
        base = PROMO[p]["name"]
        if base in seen: continue
        seen.add(base)
        W(f"| {base} (`{p.replace('PROMOTION_','')}`) | {PROMO[p]['desc']} |")
    W("")

os.makedirs(REFDIR, exist_ok=True)
open(os.path.join(REFDIR, "units-catalog.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("units-catalog.md:", len(units), "units,", len(DISC), "disciplines,", len(PROMO), "promotions,",
      "grant-units:", len(grants))
