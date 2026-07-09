import os, re, glob, collections, datetime
# Generates references/civilizations-catalog.md: EVERY playable civilization (base game + ALL DLC) with its
# Age, unique civ ability (mechanical, pulled from the ability trait's game text), unique units, unique
# buildings / unique quarter (and WHETHER it has one), unique improvement, unique civic tree, and source module.
# WHY: a civ's kit is scattered across civilizations*.xml (civ+trait link), civilizations-*gameeffects.xml
# (trait->modifier->EFFECT), units.xml / constructibles*.xml (uniques carry TraitType="TRAIT_<CIV>"), and
# UniqueQuarters rows. This joins them so a modder never has to guess or re-mine a civ's uniques. Regen after patches.

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
elem_re = re.compile(r'<(?:Row|Replace|Insert|InsertOrIgnore)\b([^>]*?)/?>')
row_text_re = re.compile(r'<Row\b[^>]*\bTag="(LOC_[A-Z0-9_]+)"[^>]*>\s*<Text>(.*?)</Text>', re.S)

def datafiles():
    out = []
    for base in (os.path.join(ROOT, "Base", "modules"), os.path.join(ROOT, "DLC")):
        out += glob.glob(os.path.join(base, "**", "data", "**", "*.xml"), recursive=True)
    return out
def textfiles():
    # Base age modules keep English under text/en_us/; DLC packs put English directly in modules/text/*.xml
    # (localized copies live under modules/l10n/, which this glob deliberately skips).
    out = []
    for base in (os.path.join(ROOT, "Base", "modules"), os.path.join(ROOT, "DLC")):
        out += glob.glob(os.path.join(base, "**", "text", "**", "*.xml"), recursive=True)
        out += glob.glob(os.path.join(base, "**", "text", "*.xml"), recursive=True)
    return sorted(set(out))

AGE = {"AGE_ANTIQUITY": "Antiquity", "AGE_EXPLORATION": "Exploration", "AGE_MODERN": "Modern"}

def source_of(path):
    p = path.replace("\\", "/")
    m = re.search(r'/DLC/([^/]+)/', p)
    if m:
        return "DLC:" + m.group(1)
    return "base"

# ---- LOC text (display names + ability descriptions), with light markup cleanup ----
loc = {}
for fp in textfiles():
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    for tag, en in row_text_re.findall(txt):
        loc.setdefault(tag, en)

def clean(s):
    if not s: return s
    s = s.replace("[BLIST]", " ").replace("[/BLIST]", " ").replace("[/LIST]", " ")
    s = re.sub(r'\[LI\]', ' • ', s)
    s = re.sub(r'\[LIST[^\]]*\]', ' ', s)
    s = re.sub(r'\[icon:[^\]]*\]', '', s)
    s = re.sub(r'\[TIP:[^\]]*\]', '', s).replace("[/TIP]", "")
    s = s.replace("[B]", "").replace("[/B]", "").replace("[I]", "").replace("[/I]", "")
    s = re.sub(r'\[N\]|\[n\]', ' ', s)
    s = re.sub(r'\[[^\]]*\]', '', s)          # any stray markup tags
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'^\s*•\s*', '', s)       # drop leading bullet
    return s

def name_of(tag, fallback=""):
    if tag and tag in loc: return clean(loc[tag])
    if fallback: return fallback.replace("LOC_", "").replace("_NAME", "").replace("_", " ").title()
    return (tag or "").replace("LOC_", "").replace("_NAME", "")

# ---- pass 1: gather rows by signature ----
civ_def   = {}                                  # civ -> {name_tag, age, tree, source}   (FULL_CIV master rows)
civ_age2  = {}                                  # civ -> age from LegacyCivilizations Age attr (backfill)
civ_traits = collections.defaultdict(set)       # civ -> {trait,...}
trait_civs = collections.defaultdict(set)       # trait -> {civ,...}
trait_text = {}                                 # trait -> (name_tag, desc_tag)
trait_mods = collections.defaultdict(list)      # trait -> [ModifierId,...]
unit_trait = {}                                 # unit -> trait
unit_name  = {}                                 # unit -> name_tag
con_class  = {}                                 # constructible -> class
con_trait  = {}                                 # constructible -> trait
con_name   = {}                                 # constructible -> name_tag (best effort)
quarters   = {}                                 # quarter -> {trait, b1, b2, name_tag}
gp_units   = set()                              # UnitType of civ-unique great people (class + individuals)
gp_class_units = set()                          # UnitType of the great-person CLASS rows only

for fp in datafiles():
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    src = source_of(fp)
    for attrs in elem_re.findall(txt):
        d = dict(attr_re.findall(attrs))
        ct = d.get("CivilizationType")
        # civ master definition (FULL_CIV)
        if ct and d.get("StartingCivilizationLevelType") == "CIVILIZATION_LEVEL_FULL_CIV":
            if ct not in civ_def:
                age = AGE.get(d.get("ApexAge", ""), "")
                civ_def[ct] = {"name": d.get("Name", ""), "age": age,
                               "tree": d.get("UniqueCultureProgressionTree", ""), "source": src}
        # LegacyCivilizations row -> Age backfill
        if ct and d.get("Age") and d.get("Name") and "StartingCivilizationLevelType" not in d:
            civ_age2.setdefault(ct, AGE.get(d.get("Age", ""), ""))
        # civ<->trait link (CivilizationTraits / LegacyCivilizationTraits)
        if ct and d.get("TraitType") and len(d) <= 3:
            tr = d["TraitType"]
            civ_traits[ct].add(tr); trait_civs[tr].add(ct)
        # trait ability definition (Name+Description, no civ/unit/constructible/modifier)
        tt = d.get("TraitType")
        if tt and d.get("Description") and not any(k in d for k in
                ("CivilizationType", "UnitType", "ConstructibleType", "ModifierId", "ResourceType")):
            trait_text.setdefault(tt, (d.get("Name", ""), d.get("Description", "")))
        # trait -> modifier
        if tt and d.get("ModifierId") and len(d) <= 3:
            trait_mods[tt].append(d["ModifierId"])
        # unique unit
        ut = d.get("UnitType")
        if ut and d.get("TraitType"):
            unit_trait.setdefault(ut, d["TraitType"])
        if ut and d.get("Name"):
            unit_name.setdefault(ut, d["Name"])
        # constructible class + trait
        con = d.get("ConstructibleType")
        if con and d.get("ConstructibleClass"):
            con_class.setdefault(con, d["ConstructibleClass"])
        if con and d.get("TraitType"):
            con_trait.setdefault(con, d["TraitType"])
        if con and d.get("Name"):
            con_name.setdefault(con, d["Name"])
        # great-person units (so they don't masquerade as trainable unique units)
        if d.get("UnitType") and (d.get("GreatPersonClassType") or d.get("GreatPersonIndividualType")):
            gp_units.add(d["UnitType"])
            if d.get("GreatPersonClassType") and not d.get("GreatPersonIndividualType"):
                gp_class_units.add(d["UnitType"])
        # unique quarter
        q = d.get("UniqueQuarterType")
        if q and d.get("TraitType"):
            quarters.setdefault(q, {"trait": d["TraitType"], "b1": d.get("BuildingType1", ""),
                                    "b2": d.get("BuildingType2", ""), "name": d.get("Name", "")})

# civ-specific trait = a trait owned by exactly ONE civ (excludes shared TRAIT_ANTIQUITY_CIV / TRAIT_ATTRIBUTE_*)
def civ_of_trait(tr):
    civs = trait_civs.get(tr, set())
    return next(iter(civs)) if len(civs) == 1 else None

# a civ is "playable/major" if it has an _ABILITY trait linked in CivilizationTraits
majors = {}
for civ, trs in civ_traits.items():
    ab = [t for t in trs if t.endswith("_ABILITY")]
    if not ab: continue
    if civ in ("CIVILIZATION_INDEPENDENT", "CIVILIZATION_NONE"): continue
    majors[civ] = ab[0]

# ---- assemble per-civ kit ----
records = {}
for civ, ability_trait in majors.items():
    dref = civ_def.get(civ, {})
    age = dref.get("age") or civ_age2.get(civ, "") or ""
    nm = name_of(dref.get("name", ""), civ.replace("CIVILIZATION_", "").title())
    tree = dref.get("tree", "")
    source = dref.get("source", "base")
    # ability text
    an_tag, ad_tag = trait_text.get(ability_trait, ("", ""))
    ability_name = name_of(an_tag) if an_tag else ability_trait.replace("TRAIT_", "").replace("_ABILITY", "").replace("_", " ").title()
    ability_desc = clean(loc.get(ad_tag, "")) if ad_tag else ""
    if not ability_desc:
        # newer DLC ship the ability with a Description tag that has no <Text> entry — fall back to the
        # ability trait's modifier ids (the mechanical hooks), so the row still says what the civ DOES.
        mods = sorted(set(trait_mods.get(ability_trait, [])))
        if mods:
            shown = ", ".join(f"`{m}`" for m in mods[:8]) + (" …" if len(mods) > 8 else "")
            ability_desc = f"*(no shipped description text — from effects: {shown})*"
    # uniques via civ-specific traits owned by this civ
    my_traits = {t for t in civ_traits[civ] if civ_of_trait(t) == civ}
    units, greatpeople, buildings, improvements = [], [], [], []
    seen_unit_names, seen_gp = set(), set()
    for ut, tr in unit_trait.items():
        if tr not in my_traits: continue
        nml = unit_name.get(ut, "")
        disp = name_of(nml, ut.replace("UNIT_", "").title())
        if ut in gp_units:                            # civ-unique great person, not a trainable UU
            if ut in gp_class_units and disp not in seen_gp:
                seen_gp.add(disp); greatpeople.append(disp)
            continue
        if disp in seen_unit_names: continue          # collapse tier variants (share the LOC name)
        seen_unit_names.add(disp); units.append(disp)
    for con, tr in con_trait.items():
        if tr not in my_traits: continue
        cls = con_class.get(con, "")
        disp = name_of(con_name.get(con, ""), con.split("_", 1)[-1].title())
        if cls == "BUILDING": buildings.append((disp, con))
        elif cls == "IMPROVEMENT": improvements.append(disp)
        elif cls == "WONDER": pass
        else: buildings.append((disp, con))
    # quarter
    myq = None
    for q, qd in quarters.items():
        if civ_of_trait(qd["trait"]) == civ:
            myq = name_of(qd["name"], q.replace("QUARTER_", "").title()); break
    records[civ] = {
        "name": nm, "age": age, "source": source, "tree": tree,
        "ability_name": ability_name, "ability_desc": ability_desc,
        "units": sorted(units), "greatpeople": sorted(greatpeople),
        "buildings": sorted(b[0] for b in buildings),
        "improvements": sorted(improvements), "quarter": myq,
    }

# ---- theme classification (heuristic from ability text) ----
THEMES = [
    ("Science",  r'science|\bresearch|tech\b|technolog'),
    ("Culture",  r'culture|civic|tourism|tradition|great work'),
    ("Military", r'combat strength|\barmy|commander|\bwar\b|\battack|defen|infantry|cavalry|\bsiege|fortif|pillag|militar|conquer|capturing a settlement'),
    ("Economy",  r'gold|trade|resource|treasure|commerce|merchant'),
    ("Growth",   r'\bfood\b|growth|population|\bpop\b|settlement|happiness|celebrat'),
]
def themes_of(desc):
    d = (desc or "").lower(); out = []
    for name, pat in THEMES:
        if re.search(pat, d): out.append(name)
    return out or ["Other"]

# ---- emit markdown ----
now = datetime.date.today().isoformat()
L = []; W = L.append
W("# Civ VII civilizations catalog (ability + unique units / buildings / quarter / improvement / civic tree)")
W("")
W(f"> **Provenance.** Extracted **{now}** from the local install, scanning every `Base\\modules` + `DLC` data XML.")
W(f"> **{len(records)} playable civilizations** (base game + all DLC). A civ is detected as *playable* when it has an")
W("> `_ABILITY` trait linked in `CivilizationTraits`; its uniques are joined from `units.xml` / `constructibles*.xml` /")
W("> `UniqueQuarters` rows carrying `TraitType=\"TRAIT_<CIV>\"`. Ability text is the ability trait's in-game description")
W("> (markup stripped) — the mechanical effect wording Firaxis ships; the raw `EFFECT_*` chain lives in each Age's")
W("> `civilizations-*gameeffects.xml` under that trait's modifiers. Regenerate after each patch via")
W("> [`tools/gen-civilizations-catalog.py`](../tools/gen-civilizations-catalog.py).")
W(">")
W("> **How a civ's kit is wired (for modders):** civ row (`Civilizations`, with `ApexAge` + `UniqueCultureProgressionTree`)")
W("> → `CivilizationTraits` links it to `TRAIT_<CIV>` (uniques hang off this one) **and** `TRAIT_<CIV>_ABILITY` (the")
W("> ability; its `TraitModifiers` → `EFFECT_*`). Unique units/buildings/improvements set `TraitType=\"TRAIT_<CIV>\"`; a")
W("> **Unique Quarter** is a `UniqueQuarters` row pairing that civ's two unique buildings. **Not every civ has a unique quarter.**")
W("")

by_age = collections.defaultdict(list)
for civ, r in records.items():
    by_age[r["age"] or "(unknown age)"].append(civ)

def build_pair(r):
    b = ", ".join(r["buildings"]) if r["buildings"] else "—"
    if r["quarter"]:
        b += f"  ▸ **Quarter: {r['quarter']}**"
    return b

for age in ("Antiquity", "Exploration", "Modern", "(unknown age)"):
    if age not in by_age: continue
    civs = sorted(by_age[age], key=lambda c: records[c]["name"])
    W(f"## {age}  ({len(civs)} civs)")
    W("")
    W("| Civ | Ability | Unique unit(s) | Unique building(s) / quarter | Unique improvement | Civic tree | Source |")
    W("|-----|---------|----------------|------------------------------|--------------------|-----------|--------|")
    for civ in civs:
        r = records[civ]
        ab = f"**{r['ability_name']}** — {r['ability_desc']}" if r["ability_desc"] else f"**{r['ability_name']}**"
        units = ", ".join(r["units"]) if r["units"] else "—"
        imp = ", ".join(r["improvements"]) if r["improvements"] else "—"
        tree = f"`{r['tree']}`" if r["tree"] else "—"
        src = r["source"].replace("DLC:", "")
        src = "base" if src == "base" else src
        W(f"| **{r['name']}**<br>`{civ}` | {ab} | {units} | {build_pair(r)} | {imp} | {tree} | {src} |")
    W("")

# ---- cross-index: civs with a unique quarter ----
q_civs = sorted((c for c in records if records[c]["quarter"]), key=lambda c: (records[c]["age"], records[c]["name"]))
W("## Cross-index — civilizations WITH a unique quarter")
W("")
W(f"{len(q_civs)} of {len(records)} civs have a Unique Quarter (a paired-building district). The rest have standalone uniques only.")
W("")
W("| Civ | Age | Unique quarter | Paired buildings |")
W("|-----|-----|----------------|------------------|")
for c in q_civs:
    r = records[c]
    W(f"| {r['name']} | {r['age']} | **{r['quarter']}** | {', '.join(r['buildings']) or '—'} |")
W("")
noq = sorted((c for c in records if not records[c]["quarter"]), key=lambda c: (records[c]["age"], records[c]["name"]))
W(f"**Civs WITHOUT a unique quarter ({len(noq)}):** " + ", ".join(records[c]["name"] for c in noq))
W("")

# ---- cross-index: civ-unique great-person classes ----
gp_civs = sorted((c for c in records if records[c]["greatpeople"]),
                 key=lambda c: (records[c]["age"], records[c]["name"]))
W("## Cross-index — civilizations WITH a unique Great-Person class")
W("")
W("Civ VII has **no universal Great-Person recruitment**; instead some civs field a civ-unique Great-Person *class*")
W("(each spawns named individuals, e.g. Egypt's Tjaty → Imhotep). These carry `TraitType=\"TRAIT_<CIV>\"` like other")
W("uniques but are defined in `greatpeople.xml`, so they are listed here rather than in the Unique-unit column.")
W("")
W("| Civ | Age | Unique Great-Person class(es) |")
W("|-----|-----|-------------------------------|")
for c in gp_civs:
    r = records[c]
    W(f"| {r['name']} | {r['age']} | {', '.join(r['greatpeople'])} |")
W("")

# ---- cross-index: by ability theme ----
W("## Cross-index — civilizations by ability theme")
W("")
W("Heuristic tags from the ability text (a civ can carry several). Use as a starting filter, not gospel.")
W("")
theme_map = collections.defaultdict(list)
for c, r in records.items():
    for t in themes_of(r["ability_desc"]):
        theme_map[t].append(r["name"])
for t in ("Science", "Culture", "Military", "Economy", "Growth", "Other"):
    if t in theme_map:
        names = sorted(set(theme_map[t]))
        W(f"- **{t}** ({len(names)}): " + ", ".join(names))
W("")

os.makedirs(REFDIR, exist_ok=True)
open(os.path.join(REFDIR, "civilizations-catalog.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("civilizations-catalog.md:", len(records), "civs / by age:",
      {a: len(v) for a, v in by_age.items()}, "/ with quarter:", len(q_civs))
