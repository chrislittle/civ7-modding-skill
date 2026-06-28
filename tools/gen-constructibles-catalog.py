import os, re, glob, collections, datetime
# Generates references/constructibles-catalog.md: EVERY constructible (building / wonder / improvement / wall / ...)
# with its CLASS, the Age you can BUILD it in, whether it's AGELESS, cost, the module it's defined in, and its tags.
# WHY: data ids don't carry an obvious age (BUILDING_TEMPLE is EXPLORATION, not Antiquity) and overbuild/age-transition
# rules hinge on age + the AGELESS tag. Grep this before asserting a constructible's age. Regenerate after each patch.
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
elem_re = re.compile(r'<(Row|Replace|Insert)\b([^>]*?)/?>')
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

# LOC -> English (for display names)
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

defs = {}                              # type -> record (first definition wins)
tags = collections.defaultdict(set)   # type -> {TAG,...}
for fp in datafiles():
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    mage = module_age(fp)
    for _t, attrs in elem_re.findall(txt):
        d = dict(attr_re.findall(attrs))
        ct = d.get("ConstructibleType")
        if ct and d.get("ConstructibleClass") and ct not in defs:   # the definition row (carries Class + Name + Cost)
            nm = d.get("Name", "")
            defs[ct] = {
                "class": d.get("ConstructibleClass", ""),
                "age":   AGE_ATTR.get(d.get("Age", ""), d.get("Age", "")) or "",
                "cost":  d.get("Cost", ""),
                "unlock": d.get("RequiresUnlock", "false"),
                "name":  loc.get(nm, nm.replace("LOC_", "").replace("_NAME", "")),
                "module": mage,
            }
        t = d.get("Type")
        if t and d.get("Tag"):   # a TypeTags row
            tags[t].add(d["Tag"])

now = datetime.date.today().isoformat()
NOISE = {"AGELESS"}   # AGELESS gets its own column; keep the rest in the Tags column
L = []; W = L.append
W("# Civ VII constructibles catalog (building / wonder / improvement / ... — class, age, ageless, cost)")
W("")
W(f"> **Provenance.** Extracted **{now}** from the local install, scanning every `Base\\modules` + `DLC` data XML for")
W(f"> constructible definition rows (rows with `ConstructibleClass`) and their `TypeTags`. **{len(defs)} constructibles.**")
W("> Regenerate after each patch via [`tools/gen-constructibles-catalog.py`](../tools/gen-constructibles-catalog.py).")
W(">")
W("> **Read the columns:**")
W("> - **Age** = the Age you can *build* it in (`AGE_*` on the row). Blank + **Ageless = yes** → buildable in any Age.")
W(">   ⚠ The age is NOT guessable from the id — e.g. `BUILDING_TEMPLE` is **EX** (Exploration), `BUILDING_MONUMENT` is AQ.")
W("> - **Ageless** = has the `AGELESS` tag → never goes obsolete, keeps its yields across Age transitions.")
W("> - **Module** = which module defines it (AQ/EX/MO age module, Base, or a DLC). An age-less building still lives in")
W(">   some module but isn't bound to that Age for *building* (e.g. `BUILDING_SAWMILL` = Ageless, EX module, no `Age`).")
W("> - **Unlk** = `RequiresUnlock` (gated by a tech/civic node or effect grant).")
W(">")
W("> See [constructibles.md](constructibles.md) for what Age + Ageless mean for **overbuilding** and **Age transitions**.")
W("")
order = ["BUILDING", "WONDER", "IMPROVEMENT", "WALL"]
byclass = collections.defaultdict(list)
for ct, r in defs.items(): byclass[r["class"]].append(ct)
def agekey(ct):
    r = defs[ct]; ai = {"AQ": 0, "EX": 1, "MO": 2, "": 3}.get(r["age"], 4)
    return (ai, r["name"])
emitted = set()
def emit(cls):
    if cls not in byclass: return
    items = sorted(byclass[cls], key=agekey)
    W(f"## {cls}  ({len(items)})")
    W("")
    W("| Age | Ageless | Type | Name | Cost | Unlk | Module | Tags |")
    W("|-----|:------:|------|------|-----:|:----:|--------|------|")
    for ct in items:
        r = defs[ct]
        ageless = "yes" if "AGELESS" in tags[ct] else ""
        othertags = ", ".join(sorted(tags[ct] - NOISE))
        unlk = "yes" if r["unlock"].lower() == "true" else ""
        W(f"| {r['age'] or '—'} | {ageless} | `{ct}` | {r['name']} | {r['cost']} | {unlk} | {r['module']} | {othertags} |")
    W("")
    emitted.add(cls)
for c in order: emit(c)
for c in sorted(set(byclass) - emitted): emit(c)
os.makedirs(REFDIR, exist_ok=True)
open(os.path.join(REFDIR, "constructibles-catalog.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("constructibles-catalog.md:", len(defs), "constructibles,", sum(1 for c in defs.values() if False), "/ classes:", {c: len(v) for c, v in byclass.items()})
