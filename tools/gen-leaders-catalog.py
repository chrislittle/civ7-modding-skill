import os, re, glob, collections, datetime
# Generates references/leaders-catalog.md: EVERY major leader (base + all DLC, incl. "alt" personas) with its
# ability trait, the trimmed official ability blurb, and the REAL effects behind it -- each modifier resolved to
# its EFFECT_* + key <Argument>s + gating requirements. WHY: a leader's prose tooltip routinely misstates the
# mechanic (e.g. Ibn Battuta has no combat/influence-on-kill; the kill-yield leaders are Gilgamesh + Lakshmibai).
# The truth is the chain LEADER_X -> TRAIT_LEADER_X_ABILITY -> TraitModifiers -> Modifier(effect + Arguments).
# Read the effect, not the blurb. Regenerate after each patch.
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

# LOC -> English
loc = {}
for fp in textfiles():
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    for tag, en in row_text_re.findall(txt):
        loc.setdefault(tag, re.sub(r'\s+', ' ', en.strip()))
def L(t): return loc.get(t, t)

def modkey(path):
    p = path.replace("\\", "/").lower()
    m = re.search(r'/dlc/([^/]+)/', p)
    if m: return "DLC:" + m.group(1)
    if "/base-standard/" in p: return "Base"
    return "?"

# Pass 1 (all data files): leader->name/src, leader->ability trait, trait->modifier ids, trait name/desc.
leader_name = {}; leader_ability = {}; leader_src = {}
trait_mods = collections.defaultdict(list); trait_desc = {}
for fp in datafiles():
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    mk = modkey(fp)
    for m in re.finditer(r'<Row\b([^>]*\bLeaderType="[^"]*"[^>]*?)/?>', txt):
        d = dict(attr_re.findall(m.group(1))); lt = d.get("LeaderType")
        if lt and d.get("Name"):
            leader_name.setdefault(lt, d["Name"]); leader_src.setdefault(lt, mk)
        if lt and d.get("TraitType", "").startswith("TRAIT_LEADER_") and d["TraitType"].endswith("_ABILITY"):
            leader_ability[lt] = d["TraitType"]
    for m in re.finditer(r'<Row\b([^>]*\bTraitType="[^"]*"[^>]*?)/?>', txt):
        d = dict(attr_re.findall(m.group(1))); tr = d.get("TraitType")
        if tr and d.get("ModifierId"): trait_mods[tr].append(d["ModifierId"])
        if tr and (d.get("Name") or d.get("Description")) and not d.get("LeaderType"):
            trait_desc.setdefault(tr, (d.get("Name", ""), d.get("Description", "")))

# Pass 2 (gameeffect/leader files only): Modifier blocks -> effect + collection + args.
modifiers = {}
for fp in datafiles():
    low = fp.lower()
    if not ("gameeffect" in low or "leader" in low): continue
    try: txt = open(fp, encoding="utf-8", errors="replace").read()
    except OSError: continue
    for mm in re.finditer(r'<Modifier\b([^>]*?)>(.*?)</Modifier>', txt, re.S):
        d = dict(attr_re.findall(mm.group(1))); mid = d.get("id")
        if not mid: continue
        args = {}
        for am in re.finditer(r'<Argument\b([^>]*?)>(.*?)</Argument>', mm.group(2), re.S):
            ad = dict(attr_re.findall(am.group(1))); nm = ad.get("name")
            if nm and not nm.startswith(("Notify", "Tooltip", "ModName")):
                v = re.sub(r'\s+', ' ', am.group(2).strip())
                if ad.get("type"): v += " [%s%s]" % (ad["type"], ("," + ad["extra"]) if ad.get("extra") else "")
                args[nm] = v
        sr = re.search(r'<SubjectRequirements>(.*?)</SubjectRequirements>', mm.group(2), re.S)
        subj = re.findall(r'type="(REQUIREMENT_[A-Z0-9_]+)"', sr.group(1)) if sr else []
        modifiers[mid] = {"effect": d.get("effect", ""), "coll": d.get("collection", ""), "args": args, "subj": subj}

def strip_blurb(s):
    s = re.sub(r'\[/?[A-Z]+[^\]]*\]', ' ', s)          # [B] [LI] [BLIST] ...
    s = re.sub(r'\[icon:[^\]]*\]', '', s)               # icons
    s = re.sub(r'\[TIP:[^\]]*\]', '', s); s = s.replace('[/TIP]', '')
    return re.sub(r'\s+', ' ', s).strip()

def is_real_leader(lt):
    return lt in leader_ability and not any(x in lt for x in ("DEFAULT", "MINOR", "INDEPENDENT"))

def argstr(m, drop_agenda=True):
    keys = [k for k in m["args"] if k not in ("WeightType", "FirstMeetDelay", "UpdateFreq")
            and not k.startswith(("AwardTo", "AwardAmt", "Arg"))]
    return "; ".join(f"{k}={m['args'][k]}" for k in keys)

# Resolve one level of EFFECT_ATTACH_MODIFIERS: return list of (child_id, child_effect, child_argstr).
def attached(m):
    out = []
    if m["effect"] == "EFFECT_ATTACH_MODIFIERS" and m["args"].get("ModifierId"):
        for cid in re.split(r'\s*,\s*', m["args"]["ModifierId"]):
            c = modifiers.get(cid)
            if c: out.append((cid, c["effect"], argstr(c)))
    return out

# Collect, per leader, the post-combat "kill yield" rows (from the leader's own or attached modifiers).
KILL = []          # (leader_name, yield, pct, restrict, src)
def scan_kill(lt, nm):
    for mid in trait_mods.get(leader_ability[lt], []):
        m = modifiers.get(mid)
        if not m: continue
        cands = [m] + [modifiers[c[0]] for c in attached(m) if c[0] in modifiers]
        for c in cands:
            if c["effect"] == "EFFECT_ADJUST_UNIT_POST_COMBAT_YIELD":
                a = c["args"]
                KILL.append((nm, a.get("YieldType", "?"), a.get("PercentDefeatedStrength", "?"),
                             a.get("UnitDomain", "") or a.get("Tag", "") or "all", leader_src.get(lt, "?")))

now = datetime.date.today().isoformat()
leaders = sorted(l for l in leader_ability if is_real_leader(l))
base = [l for l in leaders if leader_src.get(l) == "Base"]
dlc = [l for l in leaders if leader_src.get(l) != "Base"]

L_ = []; W = L_.append
W("# Civ VII leaders catalog (ability -> real EFFECT_* + args)")
W("")
W(f"> **Provenance.** Extracted **{now}** from the local install: base + every `DLC\\*` `leaders.xml`,")
W(f"> resolved against the matching `leaders-gameeffects.xml` and `LeaderText.xml`. **{len(leaders)} major leaders**")
W(f"> ({len(base)} base + {len(dlc)} DLC, incl. 'alt' personas). Regenerate via `tools/gen-leaders-catalog.py`.")
W(">")
W("> Read the effect, not the tooltip: the mechanic is `LEADER_X -> TRAIT_LEADER_X_ABILITY -> TraitModifiers ->")
W("> Modifier(effect + Arguments)`. `[ScaleByGameAge,100]` on an Amount = x1/x2/x3 by Age (this is '+N per Age').")
W("> (E.g. **Ibn Battuta** grants wildcard attribute points + sight + a Trade-Map endeavor -- NO combat bonus and")
W("> NO influence-on-kill; the influence-on-kill leaders are **Gilgamesh** and **Lakshmibai** -- see cross-index.)")
W("> Agenda modifiers (`EFFECT_DIPLOMACY_AGENDA_*`) are AI-relationship flavor only and grant no player yields.")
W("")

def emit(lt):
    tr = leader_ability[lt]
    nm = L(leader_name.get(lt, lt))
    abil = L(trait_desc.get(tr, ("", ""))[0]) if trait_desc.get(tr, ("", ""))[0] else ""
    desc = strip_blurb(L(trait_desc.get(tr, ("", ""))[1])) if trait_desc.get(tr, ("", ""))[1] else ""
    W(f"### {nm} - \"{abil}\"  ({leader_src.get(lt,'?')})")
    if desc: W(f"Blurb: {desc}")
    for mid in trait_mods.get(tr, []):
        m = modifiers.get(mid)
        if not m:
            W(f"- `{mid}` -> (defined outside mined leader files)"); continue
        if m["effect"].startswith("EFFECT_DIPLOMACY_AGENDA"):
            W(f"- `{mid}` -> Agenda ({m['effect']})"); continue
        parts = [f"- `{mid}` -> **{m['effect']}** [{m['coll'].replace('COLLECTION_','')}]"]
        a = argstr(m)
        if a: parts.append(" | " + a)
        if m["subj"]: parts.append(" | req=" + ",".join(sorted(set(m["subj"]))))
        W("".join(parts))
        for cid, ceff, ca in attached(m):   # resolve attached modifier one level deep
            W(f"    - attaches `{cid}` -> **{ceff}**" + (f" | {ca}" if ca else ""))
    W("")

# --- Cross-index: combat / kill yields (scan first so the tables sit up top) ---
for lt in base + dlc: scan_kill(lt, L(leader_name.get(lt, lt)))
W("## Cross-index: leaders with combat / kill yields")
W("")
W("Reusable primitive **`EFFECT_ADJUST_UNIT_POST_COMBAT_YIELD`** (`PercentDefeatedStrength` = % of the")
W("defeated unit's Combat Strength granted as a yield on a kill), attached to units via `EFFECT_ATTACH_MODIFIERS`.")
W("")
W("| Leader | Yield on kill | % defeated strength | Restricted to | Source |")
W("|--------|---------------|:-------------------:|---------------|--------|")
for nm, y, pct, restrict, src in KILL:
    W(f"| {nm} | `{y}` | {pct}% | {restrict} | {src} |")
W("")

# --- Cross-index: yield-per-X scalers (auto from effect names) ---
PERX = collections.defaultdict(list)
for lt in base + dlc:
    nm = L(leader_name.get(lt, lt))
    for mid in trait_mods.get(leader_ability[lt], []):
        m = modifiers.get(mid)
        if not m: continue
        e = m["effect"]
        if ("_YIELD_PER_" in e or "_YIELD_ON_" in e or e.endswith("_YIELD_CONVERSION")
                or "PER_SURPLUS" in e or "PER_PROMOTION" in e) and not e.startswith("EFFECT_DIPLOMACY_AGENDA"):
            PERX[e].append(nm)
W("## Cross-index: yield-per-X scalers (generalizable)")
W("")
W("| Effect primitive | Leaders |")
W("|------------------|---------|")
for e in sorted(PERX):
    W(f"| `{e}` | {', '.join(sorted(set(PERX[e])))} |")
W("")

W(f"## Base game leaders ({len(base)})"); W("")
for lt in base: emit(lt)
W(f"## DLC leaders ({len(dlc)})"); W("")
for lt in dlc: emit(lt)

W("## Notes for modders")
W("")
W("- Every leader ability = a `TRAIT_LEADER_<NAME>_ABILITY` trait (in `<LeaderTraits>`) whose `<TraitModifiers>`")
W("  name the modifier ids; the modifier bodies live in `leaders-gameeffects.xml` in the SAME module (base/DLC).")
W("- **'+N per Age' = `Amount=\"N\" type=\"ScaleByGameAge\" extra=\"100\"`** on the argument, never a per-Age node gate.")
W("- **Kill yields = `EFFECT_ADJUST_UNIT_POST_COMBAT_YIELD`** (`PercentDefeatedStrength`) attached to units --")
W("  the single reusable 'gain X on defeating an enemy' primitive.")
W("- Agenda modifiers grant no player yields; drop the `EFFECT_DIPLOMACY_AGENDA_*` rows if templating an ability.")
W("- Alt (`_ALT`) personas are full separate leaders with their own trait + modifiers, sharing nothing mechanically.")

os.makedirs(REFDIR, exist_ok=True)
open(os.path.join(REFDIR, "leaders-catalog.md"), "w", encoding="utf-8").write("\n".join(L_) + "\n")
print("leaders-catalog.md:", len(leaders), "leaders (", len(base), "base +", len(dlc), "DLC )")
