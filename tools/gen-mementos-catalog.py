import os, re, glob, collections, datetime, xml.etree.ElementTree as ET
# Generates references/mementos-catalog.md: EVERY Memento (base + all DLC) with its readable name, flavour +
# functional description, the MECHANICAL effect (EFFECT_* id + key <Argument>s resolved to plain English, flagged
# flat vs %), how it's UNLOCKED, and its source module. Plus a "effects already TAKEN by a Memento" cross-index
# grouped by effect family -> the anti-duplication gate a mod designer checks before handing out a per-X bonus.
# WHY: Mementos are a pre-game loadout that already grants many "per-population / per-suzerain / per-resource / ..."
# yields. A mod that re-grants what a Memento already gives double-dips. Regenerate after each patch.

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

def module_source(path):
    """Which package a file belongs to: 'base' or 'DLC:<name>'."""
    p = path.replace("\\", "/")
    m = re.search(r'/DLC/([^/]+)/', p)
    if m: return "DLC:" + m.group(1)
    return "base"

def files(*names):
    """All base + DLC copies of the given data/config filenames."""
    out = []
    for nm in names:
        out += glob.glob(os.path.join(ROOT, "Base", "modules", "**", nm), recursive=True)
        out += glob.glob(os.path.join(ROOT, "DLC", "**", nm), recursive=True)
    return out

def parse(fp):
    """Namespace-agnostic ElementTree parse; returns root or None."""
    try:
        txt = open(fp, encoding="utf-8", errors="replace").read()
        txt = re.sub(r'\sxmlns(:\w+)?="[^"]*"', '', txt, count=1)  # drop default namespace so tags are bare
        return ET.fromstring(txt)
    except Exception:
        return None

def localname(el): return el.tag.split('}')[-1]

# ---- 1. localization (LOC -> English), formatting stripped for the short column ------------------
loc = {}
for fp in files(os.path.join("text", "en_us", "MementoText.xml")):
    r = parse(fp)
    if r is None: continue
    for row in r.iter():
        if localname(row) == "Row" and row.get("Tag"):
            txt = "".join(row.itertext()).strip()
            if txt: loc.setdefault(row.get("Tag"), re.sub(r'\s+', ' ', txt))

def clean(loc_or_text):
    """Resolve a LOC tag then strip Civ markup ([B],[icon:..],[TIP:..]..) to plain readable prose."""
    s = loc.get(loc_or_text, loc_or_text) if loc_or_text else ""
    s = re.sub(r'\[TIP:[^\]]*\]', '', s); s = re.sub(r'\[/?TIP\]', '', s)
    s = re.sub(r'\[icon:([A-Z_]+)\]', lambda m: _icon(m.group(1)), s)
    s = re.sub(r'\[/?[A-Za-z][^\]]*\]', '', s)  # [B] [/B] [LIST] etc.
    return re.sub(r'\s+', ' ', s).strip()

def _icon(tok):
    # Keep YIELD icons as a word (often no following literal). Drop other icons (ATTRIBUTE_/resource/etc.) —
    # the readable noun follows them in the string, so emitting the icon too would double the word.
    if not tok.startswith("YIELD_"): return ""
    t = tok.replace("YIELD_", "").replace("_", " ").title()
    return {"Diplomacy": "Influence"}.get(t, t)

# ---- 2. memento definitions + modifier map (base + DLC) ------------------------------------------
mementos = {}                                    # type -> record
mm = collections.defaultdict(list)               # memento type -> [ModifierId]
for fp in files("mementos.xml"):
    r = parse(fp);
    if r is None: continue
    src = module_source(fp)
    for row in r.iter():
        ln = localname(row)
        if ln == "Row" and row.get("MementoType") and row.get("Name"):
            t = row.get("MementoType")
            if t not in mementos:
                mementos[t] = {
                    "type": t, "src": src,
                    "name": clean(row.get("Name")),
                    "tag": row.get("Tag", ""),
                    "tier": row.get("Tier", ""),
                    "region": row.get("Region", ""),
                    "flavour": clean(row.get("Description")),
                    "func": clean(row.get("FunctionalDescription")),
                }
        elif ln == "Row" and row.get("MementoType") and row.get("ModifierId"):
            mm[row.get("MementoType")].append(row.get("ModifierId"))

# ---- 3. modifiers (base + DLC) ------------------------------------------------------------------
mods = {}
for fp in files("mementos-gameeffects.xml"):
    r = parse(fp)
    if r is None: continue
    for mod in r.iter():
        if localname(mod) != "Modifier": continue
        rec = {"coll": mod.get("collection", ""), "eff": mod.get("effect", ""),
               "perm": mod.get("permanent", ""), "runonce": mod.get("run-once", ""),
               "args": {}, "meta": {}, "reqs": [], "attach": []}
        for ch in mod:
            ln = localname(ch)
            if ln == "Argument":
                nm = ch.get("name"); val = (ch.text or "").strip()
                rec["args"][nm] = val
                if ch.get("type"): rec["meta"][nm] = ch.get("type")
                if nm == "ModifierId": rec["attach"].append(val)
            elif ln == "SubjectRequirements":
                for req in ch:
                    if localname(req) != "Requirement": continue
                    ra = {a.get("name"): (a.text or "").strip() for a in req if localname(a) == "Argument"}
                    rec["reqs"].append((req.get("type", ""), req.get("inverse") == "true", ra))
        mods[mod.get("id")] = rec

# ---- 4. unlock (challenge slug) from config/unlockableRewards.xml --------------------------------
unlock = {}
for fp in files(os.path.join("config", "unlockableRewards.xml")):
    r = parse(fp)
    if r is None: continue
    for row in r.iter():
        if localname(row) == "Row" and row.get("Type") == "UNLOCKABLEREWARD_TYPE_MEMENTO":
            unlock[row.get("GameItemID")] = row.get("CustomData", "")

# ---- 5. plain-English effect resolver -----------------------------------------------------------
def yv(v): return v.replace("YIELD_", "").title() if v else ""
def pretty_tag(v): return v.replace("UNIT_CLASS_", "").replace("_", " ").title() if v else v

# effect id -> (family label, lambda(args)->english-tail). '%' families flagged in fam2pct.
def _reqs_text(reqs):
    bits = []
    for typ, inv, ra in reqs:
        t = typ.replace("REQUIREMENT_", "")
        key = ra.get("Tag") or ra.get("UnitType") or ra.get("AttributeType") or ra.get("DistrictType") \
              or ra.get("TerrainType") or ra.get("BiomeType") or ra.get("ConstructibleClass") or ra.get("WarType") or ""
        label = t.lower().replace("_", " ")
        if key: label += " " + pretty_tag(key)
        bits.append(("NOT " if inv else "") + label)
    return "; ".join(b for b in bits if b)

# Map each effect to a human family. Families the task calls out are named explicitly.
EFFECT_FAMILY = {
    "TRIGGER_PLAYER_ADJUST_POPULATION_ON_CELEBRATION_STARTED": "per-celebration (population/growth)",
    "EFFECT_CITY_ADJUST_GROWTH_PER_WORKER": "per-worker (growth/yield)",
    "EFFECT_CITY_ADJUST_WORKER_YIELD": "per-worker (growth/yield)",
    "EFFECT_PLOT_ADJUST_WORKER_YIELD": "per-worker (growth/yield)",
    "EFFECT_CITY_ADJUST_YIELD_PER_SURPLUS_HAPPINESS": "per-surplus-happiness",
    "EFFECT_CITY_ADJUST_YIELD_PER_SUZERAIN": "per-suzerain",
    "EFFECT_PLAYER_ADJUST_YIELD_PER_RESOURCE": "per-resource",
    "EFFECT_CITY_ADJUST_YIELD_PER_RESOURCE": "per-resource",
    "EFFECT_PLAYER_ADJUST_YIELD_PER_UNIT_LEVEL": "per-commander-level",
    "EFFECT_CITY_ADJUST_YIELD_PER_GREAT_WORK": "per-great-work",
    "EFFECT_PLAYER_ADJUST_SETTLEMENT_CAP": "settlement-cap",
    "EFFECT_CITY_ADJUST_TRADE_ROUTE_RANGE": "trade-range / trade-capacity",
    "EFFECT_PLAYER_ADJUST_TRADE_CAPACITY": "trade-range / trade-capacity",
    "EFFECT_PLAYER_ADJUST_YIELD_PER_NUM_TRADE_ROUTES": "per-trade-route",
    "EFFECT_PLAYER_ADJUST_YIELD_FOR_GOLDEN_AGE_START": "golden-age",
    "EFFECT_PLAYER_ADJUST_GOLDEN_AGE_DURATION": "golden-age",
    "EFFECT_ADJUST_UNIT_POST_COMBAT_YIELD": "post-combat / XP yield",
    "EFFECT_ADJUST_UNIT_POST_COMBAT_HEAL": "post-combat / XP yield",
    "EFFECT_GRANT_YIELD_PER_XP_EARNED": "post-combat / XP yield",
    "EFFECT_CITY_ADJUST_YIELD_PER_NUM_CITIES": "per-num-cities",
    "EFFECT_PLAYER_ADJUST_YIELD_PER_ACTIVE_TRADITION": "per-active-tradition",
    "EFFECT_CITY_ADJUST_YIELD_PER_ACTIVE_TRADITION": "per-active-tradition",
    "EFFECT_PLAYER_ADJUST_YIELD_PER_CONQUERED_SETTLEMENT": "per-conquered-settlement",
    "EFFECT_PLAYER_ADJUST_YIELD_PER_COMPLETED_TRIUMPH": "per-triumph / per-mastery",
    "EFFECT_PLAYER_ADJUST_YIELD_PER_COMPLETED_MASTERY": "per-triumph / per-mastery",
    "TRIGGER_PLAYER_GRANT_YIELD_ON_MASTERY_COMPLETED": "per-triumph / per-mastery",
    "TRIGGER_PLAYER_ADJUST_YIELD_PER_ATTRIBUTE_TREE_UNLOCKED": "per-attribute-tree",
    "EFFECT_PLAYER_ADJUST_PROGRESSION_TREE_MASTERY_EFFICIENCY": "mastery / progression efficiency",
    "EFFECT_PLAYER_GRANT_PROGRESSION": "mastery / progression efficiency",
    "TRIGGER_CITY_GRANT_YIELD_ON_PROGRESSION_TREE_NODE_DEPTH_UNLOCKED": "per-tree-node unlocked",
    "TRIGGER_PLAYER_GRANT_YIELD_ON_PROGRESSION_TREE_NODE_DEPTH_UNLOCKED": "per-tree-node unlocked",
    "EFFECT_DIPLOMACY_ADJUST_YIELD_PER_PLAYER_RELATIONSHIP": "per-diplomatic-relationship",
    "EFFECT_DIPLOMACY_ADJUST_YIELD_PER_PLAYER_INVOLVED_ACTION": "per-diplomatic-relationship",
    "EFFECT_PLAYER_ATTRIBUTE": "flat attribute point (pre-game loadout)",
    "EFFECT_PLAYER_GRANT_TRADITION_SLOTS": "extra tradition/policy slot",
    "EFFECT_PLAYER_GRANT_YIELD": "one-shot / flat yield grant",
    "EFFECT_CITY_GRANT_YIELD": "one-shot / flat yield grant",
    "EFFECT_GRANT_RETURNED_CITIES_BONUS": "one-shot / flat yield grant",
    "EFFECT_CITY_ADJUST_YIELD": "flat city yield",
    "EFFECT_PLAYER_ADJUST_YIELD": "flat player yield (%)",
    "EFFECT_PLOT_ADJUST_YIELD": "flat plot yield",
    "EFFECT_CITY_ADJUST_CONSTRUCTIBLE_YIELD": "flat constructible yield",
    "EFFECT_PLAYER_ADJUST_CONSTRUCTIBLE_YIELD": "flat constructible yield",
    "EFFECT_CITY_ADJUST_CONSTRUCTIBLE_PRODUCTION": "production efficiency",
    "EFFECT_CITY_ADJUST_UNIT_PRODUCTION": "production efficiency",
    "EFFECT_ADJUST_PLAYER_OR_CITY_UNIT_PURCHASE_EFFICIENCY": "purchase / maintenance efficiency",
    "EFFECT_PLAYER_ADJUST_UNIT_MAINTENANCE_EFFICIENCY": "purchase / maintenance efficiency",
    "EFFECT_PLAYER_ADJUST_YIELD_CONVERSION": "yield conversion",
    "EFFECT_ADJUST_YIELD_FOR_ALLIES": "alliance yield",
    "EFFECT_PLAYER_ADJUST_YIELD_FOR_COMPLETING_NARRATIVE_EVENTS": "per-narrative-event",
    "EFFECT_PLAYER_ADJUST_YIELD_FOR_BECOMING_SUZERAIN": "on becoming suzerain",
}
def family_of(eff):
    if eff in EFFECT_FAMILY: return EFFECT_FAMILY[eff]
    e = eff.replace("EFFECT_", "").replace("TRIGGER_", "")
    if "MOVEMENT" in e or "SIGHT" in e or "HEAL" in e or "RESPAWN" in e or "ABILITY" in e: return "unit mobility / utility"
    if "COMBAT" in e or "STRENGTH" in e or "WAR_SUPPORT" in e or "FOCUSED_ATTACK" in e or "EXPERIENCE" in e: return "combat / warfare"
    if "GRANT_UNIT" in e: return "unit mobility / utility"
    return "misc"

PCT_ARGS = {"Percent", "PercentMultiplier", "PercentCost", "MaxPercent", "BoostPercentage", "Max"}
def flat_or_pct(rec):
    if PCT_ARGS & set(rec["args"]): return "%"
    if "Amount" in rec["args"] or "Divisor" in rec["args"]: return "flat"
    return "-"

def render_mod(mid, depth=0):
    """Plain-English one-liner for a single modifier id (follows ATTACH_MODIFIERS one level)."""
    rec = mods.get(mid)
    if not rec: return (f"`{mid}` (definition not found)", "-", "misc")
    eff = rec["eff"]; a = rec["args"]
    fam = family_of(eff)
    fp = flat_or_pct(rec)
    y = yv(a.get("YieldType", "")) or yv(a.get("YieldTypes", ""))
    amt = a.get("Amount", ""); pct = a.get("Percent", ""); div = a.get("Divisor", "")
    scale = " (scales by Age)" if rec["meta"].get("Amount") == "ScaleByGameAge" else ""
    mx = a.get("Max", "")
    e = eff.replace("EFFECT_", "").replace("TRIGGER_", "").replace("_", " ").title()

    if eff == "EFFECT_PLAYER_ATTRIBUTE":
        tail = f"+{amt} {a.get('AttributeType','').replace('ATTRIBUTE_','').title()} attribute point"
    elif eff == "EFFECT_PLAYER_GRANT_TRADITION_SLOTS":
        tail = f"+{amt} {a.get('SlotType','').replace('POLICY_','').replace('_SLOT','').title()} tradition/policy slot"
    elif eff == "EFFECT_PLAYER_ADJUST_SETTLEMENT_CAP":
        tail = f"+{amt} Settlement Cap"
    elif eff in ("EFFECT_CITY_ADJUST_TRADE_ROUTE_RANGE",):
        tail = f"+{amt} Trade Route range ({a.get('DomainType','').replace('DOMAIN_','').title()})"
    elif eff == "EFFECT_PLAYER_ADJUST_TRADE_CAPACITY":
        tail = f"+{amt} Trade Route capacity"
    elif eff in ("EFFECT_PLAYER_GRANT_YIELD", "EFFECT_CITY_GRANT_YIELD", "EFFECT_GRANT_RETURNED_CITIES_BONUS"):
        tail = f"grant {amt} {y}{scale}"
    elif eff in ("EFFECT_CITY_ADJUST_YIELD", "EFFECT_PLOT_ADJUST_YIELD", "EFFECT_CITY_ADJUST_WORKER_YIELD",
                 "EFFECT_PLOT_ADJUST_WORKER_YIELD", "EFFECT_CITY_ADJUST_CONSTRUCTIBLE_YIELD",
                 "EFFECT_PLAYER_ADJUST_CONSTRUCTIBLE_YIELD"):
        per = ""
        if "WORKER" in eff: per = " per Specialist"
        if "CONSTRUCTIBLE" in eff and a.get("Tag"): per = f" per {pretty_tag(a['Tag'])} building"
        tail = f"+{amt} {y}{per}{scale}"
    elif "PER_SURPLUS_HAPPINESS" in eff:
        tail = f"+{amt} {y} per surplus Happiness"
    elif "PER_SUZERAIN" in eff:
        tail = f"+{amt} {y} per Suzerain (city-state)"
    elif "PER_RESOURCE" in eff:
        tail = f"+{amt} {y} per Resource"
    elif "PER_UNIT_LEVEL" in eff:
        tail = f"+{amt} {y} per Commander level"
    elif "PER_GREAT_WORK" in eff:
        tail = f"+{amt} {y} per Great Work"
    elif "PER_NUM_CITIES" in eff:
        tail = f"+{amt} {y} per City"
    elif "PER_NUM_TRADE_ROUTES" in eff or "PER_TRADE_ROUTE" in eff:
        tail = f"+{amt} {y} per Trade Route"
    elif "PER_ACTIVE_TRADITION" in eff:
        tail = f"+{amt} {y} per active Tradition"
    elif "PER_CONQUERED_SETTLEMENT" in eff:
        tail = f"+{amt} {y} per conquered Settlement"
    elif "PER_COMPLETED_TRIUMPH" in eff:
        tail = f"+{amt} {y} per completed Triumph"
    elif "PER_COMPLETED_MASTERY" in eff or "ON_MASTERY_COMPLETED" in eff:
        tail = f"+{amt} {y} per/on completed Mastery"
    elif "PER_ATTRIBUTE_TREE_UNLOCKED" in eff:
        tail = f"+{amt} {y} per Attribute tree unlocked"
    elif "PER_PLAYER_RELATIONSHIP" in eff or "PER_PLAYER_INVOLVED_ACTION" in eff:
        tail = f"+{amt} {y} per qualifying diplomatic relationship/action"
    elif "GOLDEN_AGE_START" in eff:
        tail = f"grant {amt} {y} when a Golden Age begins"
    elif "GOLDEN_AGE_DURATION" in eff:
        tail = f"+{amt} Golden Age duration"
    elif "POST_COMBAT_YIELD" in eff:
        tail = f"grant {amt} {y} after combat"
    elif "PER_XP_EARNED" in eff:
        tail = f"grant {y} per XP earned"
    elif "FOR_BECOMING_SUZERAIN" in eff:
        tail = f"grant {amt} {y} on becoming a Suzerain{scale}"
    elif "FOR_COMPLETING_NARRATIVE_EVENTS" in eff:
        tail = f"grant {amt} {y} per Narrative Event completed"
    elif "ON_CELEBRATION_STARTED" in eff:
        tail = f"+{amt} Population when a Celebration starts"
    elif "GROWTH_PER_WORKER" in eff:
        tail = f"+{pct}% Growth per Specialist" + (f" (max {mx}%)" if mx else "")
    elif eff == "EFFECT_PLAYER_ADJUST_YIELD":
        tail = f"+{pct}% {y}"
    elif "MAINTENANCE_EFFICIENCY" in eff or "PURCHASE_EFFICIENCY" in eff:
        tail = f"{pct or a.get('PercentCost','')}% {'maintenance' if 'MAINTENANCE' in eff else 'purchase'} cost"
    elif "PRODUCTION" in eff:
        tail = f"+{pct or amt}{'%' if pct else ''} Production ({e})"
    elif "MASTERY_EFFICIENCY" in eff:
        tail = f"+{pct}% toward Masteries"
    elif "MOVEMENT" in eff:
        tail = f"+{amt} Movement"
    elif "SIGHT" in eff:
        tail = f"+{amt} Sight"
    elif "STRENGTH" in eff or "COMBAT" in eff:
        tail = f"+{amt or pct} Combat Strength ({e})"
    elif "EXPERIENCE" in eff:
        tail = f"+{pct}% Commander XP"
    elif "WAR_SUPPORT" in eff:
        tail = f"+{amt} War Support ({e})"
    elif "HEAL" in eff:
        tail = f"+{amt or a.get('Health','')} Healing"
    else:
        bits = [f"{k}={v}" for k, v in a.items() if k not in ("Tooltip",)]
        tail = f"{e}: " + ", ".join(bits) if bits else e

    req = _reqs_text(rec["reqs"])
    if req: tail += f"  [when: {req}]"
    if eff == "EFFECT_ATTACH_MODIFIERS":
        subs = [render_mod(s, depth + 1)[0] for s in rec["attach"]]
        tail = "; then ".join(subs) + (f"  [when: {req}]" if req else "")
        # family from the sub effect if resolvable
        if rec["attach"] and mods.get(rec["attach"][0]):
            fam = family_of(mods[rec["attach"][0]]["eff"])
            fp = flat_or_pct(mods[rec["attach"][0]])
    return (f"`{eff}` -> {tail}", fp, fam)

# ---- 6. build per-memento resolved effects -------------------------------------------------------
CAT_ORDER = ["Military", "Economic", "Scientific", "Cultural", "Diplomatic", "Expansionist", ""]
for t, rec in mementos.items():
    parts, fps, fams = [], set(), set()
    for mid in mm.get(t, []):
        eng, fp, fam = render_mod(mid)
        parts.append(eng); fps.add(fp); fams.add(fam)
    rec["effect_md"] = "<br>".join(parts) if parts else "(no modifier found)"
    rec["fp"] = "/".join(sorted(x for x in fps if x != "-")) or "-"
    rec["families"] = fams

def unlock_label(t):
    if t.startswith("MEMENTO_FOUNDATION_"):
        base = "Foundation pool (available to any leader)"
    else:
        who = t.split("_")[1].title()
        base = f"{who} leader progression"
    slug = unlock.get(t, "")
    return base + (f" — challenge `{slug}`" if slug else "")

# ---- 7. emit markdown ---------------------------------------------------------------------------
now = datetime.date.today().isoformat()
srcs = sorted(set(r["src"] for r in mementos.values()))
L = []; W = L.append
W("# Civ VII Mementos catalog (base + all DLC) — effect + unlock + anti-duplication gate")
W("")
W(f"> **Provenance.** Extracted **{now}** from the local install: every `mementos.xml` (definitions + modifier map),")
W(f"> `mementos-gameeffects.xml` (the modifiers/effects), `text/en_us/MementoText.xml` (readable name + description),")
W(f"> and `config/unlockableRewards.xml` (unlock challenge) across `Base\\modules` + every `DLC`. **{len(mementos)} mementos**")
W(f"> from {len(srcs)} packages. Regenerate after each patch via [`tools/gen-mementos-catalog.py`](../tools/gen-mementos-catalog.py).")
W(">")
W("> **What a Memento is.** A pre-game **loadout item** the player equips before the match (2 slots by default, more")
W("> unlocked via progression). Each grants a small permanent bonus for the whole game. Because they are chosen at")
W("> setup, their bonuses stack on top of everything a mod does — so **a mod that hands out the same per-X yield a")
W("> Memento already gives is double-dipping**. Use the [cross-index](#effects-already-taken-by-a-memento-anti-duplication-gate)")
W("> below as the anti-duplication gate: before you add a `per-population / per-suzerain / per-resource / per-great-work /")
W("> settlement-cap / golden-age / post-combat` bonus, check whether a Memento already occupies that lever.")
W(">")
W("> **Columns.** *Effect* = the `EFFECT_*` id + key `<Argument>`s resolved to plain English. **Flat vs %**: `Amount`/")
W("> `Divisor` = flat, `Percent`/`Max`/`PercentCost` = %. `(scales by Age)` = `ScaleByGameAge` — the flat value grows each Age.")
W("> *Unlock*: **Foundation pool** mementos are the shared starter set; leader-named ones unlock through that leader's")
W("> progression/challenges (slug shown). All are challenge-gated in the online metaprogression; slugs are the challenge ids.")
W("")

# main tables grouped by Tag (category)
bycat = collections.defaultdict(list)
for t, rec in mementos.items(): bycat[rec["tag"]].append(rec)
W("## Mementos by category")
W("")
for cat in CAT_ORDER + [c for c in sorted(bycat) if c not in CAT_ORDER]:
    if cat not in bycat: continue
    items = sorted(bycat[cat], key=lambda r: r["name"])
    W(f"### {cat or 'Uncategorized'}  ({len(items)})")
    W("")
    W("| Memento | Flavour | Effect (EFFECT_ + args, plain English) | Flat/% | Unlock | Source |")
    W("|---------|---------|----------------------------------------|:------:|--------|--------|")
    for r in items:
        flav = (r["func"] or r["flavour"] or "").replace("|", "\\|")
        if len(flav) > 130: flav = flav[:127] + "..."
        eff = r["effect_md"].replace("|", "\\|")
        W(f"| **{r['name']}**<br>`{r['type']}` | {flav} | {eff} | {r['fp']} | {unlock_label(r['type'])} | {r['src']} |")
    W("")

# ---- cross-index: effects already TAKEN by a memento --------------------------------------------
W("## Effects already TAKEN by a Memento (anti-duplication gate)")
W("")
W("Grouped by effect family. If a family below is **occupied**, a Memento can already be supplying that bonus at")
W("setup — think twice before a mod grants the same lever (or scope it so it does not simply stack).")
W("")
fam_members = collections.defaultdict(list)   # family -> [(memento name, effect id)]
fam_effects = collections.defaultdict(set)
for t, rec in mementos.items():
    for mid in mm.get(t, []):
        r = mods.get(mid)
        if not r: continue
        eff = r["eff"]
        if eff == "EFFECT_ATTACH_MODIFIERS" and r["attach"] and mods.get(r["attach"][0]):
            eff = mods[r["attach"][0]]["eff"]
        fam = family_of(eff)
        fam_members[fam].append(rec["name"])
        fam_effects[fam].add(eff)
# order: put the task-called-out premium families first
PREMIUM = ["per-surplus-happiness", "per-suzerain", "per-resource", "per-commander-level", "per-great-work",
           "per-num-cities", "per-trade-route", "per-active-tradition", "per-conquered-settlement",
           "per-triumph / per-mastery", "per-attribute-tree", "per-tree-node unlocked",
           "per-diplomatic-relationship", "settlement-cap", "trade-range / trade-capacity", "golden-age",
           "post-combat / XP yield", "per-worker (growth/yield)", "per-celebration (population/growth)"]
W("| Effect family | # mementos | Occupying mementos | Effect id(s) used |")
W("|---------------|:---------:|--------------------|-------------------|")
seen = set()
def emit_fam(fam):
    if fam not in fam_members or fam in seen: return
    seen.add(fam)
    names = sorted(set(fam_members[fam]))
    effs = ", ".join(f"`{e}`" for e in sorted(fam_effects[fam]))
    W(f"| **{fam}** | {len(fam_members[fam])} | {', '.join(names)} | {effs} |")
for fam in PREMIUM: emit_fam(fam)
for fam in sorted(fam_members):
    if fam not in seen: emit_fam(fam)
W("")

# ---- notably FREE premium yield-effects (exist in engine, no memento uses them) -----------------
W("### Premium per-X yield effects NOT used by any Memento (free levers)")
W("")
W("These engine effects exist (see [`effects-collections-catalog.md`](effects-collections-catalog.md)) but **no base/DLC")
W("Memento occupies them** — a mod can grant these without duplicating a Memento's setup bonus:")
W("")
used_effects = set()
for rec in mods.values():
    used_effects.add(rec["eff"])
FREE_CANDIDATES = [
    "EFFECT_CITY_ADJUST_YIELD_PER_POPULATION", "EFFECT_CITY_ADJUST_YIELD_PER_COMMANDER_LEVEL",
    "EFFECT_CITY_ADJUST_YIELD_PER_CONNECTED_CITY", "EFFECT_CITY_ADJUST_YIELD_PER_ATTRIBUTE",
    "EFFECT_CITY_ADJUST_YIELD_PER_RESOURCE_CLASS", "EFFECT_CITY_ADJUST_YIELD_PER_AVAILABLE_RESOURCE_TYPE",
    "EFFECT_CITY_ADJUST_YIELD_PER_UNLOCKED_PROGRESSION_TREE_NODE", "EFFECT_CITY_ADJUST_YIELD_PER_UNDER_SETTLEMENT_CAP",
    "EFFECT_CITY_ADJUST_YIELDS_PER_SETTLEMENT_OVER_CAP", "EFFECT_CITY_ADJUST_YIELD_PER_CITY_STATE_TRADE_ROUTE",
    "EFFECT_CITY_ADJUST_YIELD_PER_TOTAL_NUM_TRADE_ROUTES", "EFFECT_CITY_ADJUST_YIELD_PER_SUZERAINED_CITY_STATE_TYPE",
    "EFFECT_ADJUST_PLAYER_YIELD_PER_SLOTTED_RESOURCE", "EFFECT_DIPLOMACY_ADJUST_YIELD_PER_SANCTIONED_PLAYER",
    "EFFECT_CITY_GRANT_YIELD_PER_POP_DEFENSE_CONSTRUCTED",
]
for e in FREE_CANDIDATES:
    if e not in used_effects:
        W(f"- `{e}`")
W("")
os.makedirs(REFDIR, exist_ok=True)
open(os.path.join(REFDIR, "mementos-catalog.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("mementos-catalog.md:", len(mementos), "mementos,", len(mods), "modifiers,", len(srcs), "packages")
print("families:", {k: len(v) for k, v in sorted(fam_members.items())})
