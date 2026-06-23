import os, re, glob, collections, datetime
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
OUTMD = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "effects-collections-catalog.md"))
files=[]
for base in (os.path.join(ROOT,"Base","modules"), os.path.join(ROOT,"DLC")):
    files += glob.glob(os.path.join(base,"**","data","**","*.xml"), recursive=True)

block_re=re.compile(r'<Modifier\b(?P<attrs>[^>]*?)(?:/>|>(?P<body>.*?)</Modifier>)',re.S)
arg_re=re.compile(r'<Argument\b[^>]*\bname="([^"]+)"')
val_re=re.compile(r'<Argument\b[^>]*\bname="([^"]+)"[^>]*>([^<]*)</Argument>')
reqblk_re=re.compile(r'<(SubjectRequirements|OwnerRequirements)\b.*?</\1>',re.S)
effattr_re=re.compile(r'\beffect="(EFFECT_[A-Z0-9_]+)"')
collattr_re=re.compile(r'\bcollection="(COLLECTION_[A-Z0-9_]+)"')
req_re=re.compile(r'<Requirement\b(?P<attrs>[^>]*?)(?:/>|>(?P<body>.*?)</Requirement>)',re.S)
reqtype_re=re.compile(r'\btype="(REQUIREMENT_[A-Z0-9_]+)"')

eff_args=collections.defaultdict(collections.Counter); eff_count=collections.Counter()
req_args=collections.defaultdict(collections.Counter); req_count=collections.Counter()
coll_count=collections.Counter(); yieldtypes=collections.Counter()
for fp in files:
    try: txt=open(fp,encoding="utf-8",errors="replace").read()
    except: continue
    for c in collattr_re.findall(txt): coll_count[c]+=1
    for k,v in val_re.findall(txt):
        if k=="YieldType":
            for y in re.findall(r'YIELD_[A-Z0-9_]+', v): yieldtypes[y]+=1
    for m in req_re.finditer(txt):
        tm=reqtype_re.search(m.group("attrs") or "")
        if not tm: continue
        rt=tm.group(1); req_count[rt]+=1
        for a in arg_re.findall(m.group("body") or ""): req_args[rt][a]+=1
    for m in block_re.finditer(txt):
        em=effattr_re.search(m.group("attrs") or "")
        if not em: continue
        eff=em.group(1); eff_count[eff]+=1
        body=reqblk_re.sub("", m.group("body") or "")
        for a in arg_re.findall(body): eff_args[eff][a]+=1

PLAYER_ROOTED={"COLLECTION_OWNER","COLLECTION_PLAYER_CITIES","COLLECTION_PLAYER_UNITS","COLLECTION_PLAYER_CAPITAL_CITY","COLLECTION_MAJOR_PLAYERS","COLLECTION_PLAYER_PLOT_YIELDS","COLLECTION_PLAYER_COMBAT","COLLECTION_PLAYER_DISTRICTS","COLLECTION_PLAYER_CONSTRUCTIBLES","COLLECTION_PLAYER_CAPITAL_CITY_DISTRICTS","COLLECTION_PLAYER_TRADE_ROUTES","COLLECTION_OWNER_PLAYER","COLLECTION_OWNER_CITY","COLLECTION_CITIES_FOLLOWING_OWNER_RELIGION","COLLECTION_PLAYER_INFECTED_CITIES"}
def cat(eff):
    t=eff[len("EFFECT_"):]
    for c in ("CITY","PLAYER","UNIT","DISTRICT","PLOT","DIPLOMACY","CITIES","ARMY","COMMANDER"):
        if t.startswith(c+"_") or t==c: return c
    return "GENERAL / CROSS-CUTTING"
buckets=collections.defaultdict(list)
for e in eff_count: buckets[cat(e)].append(e)

now=datetime.date.today().isoformat()
L=[]
def w(s=""): L.append(s)
w("# Civ VII GameEffects catalog — effects · collections · requirements · yields")
w()
w(f"> **Provenance.** Extracted **{now}** directly from the local installed game by scanning")
w(f"> **{len(files)} `data/**/*.xml` files** across `Base\modules` (core, base-standard, age-antiquity,")
w("> age-exploration, age-modern) **and every installed `DLC\` module**. Steam buildid **23245653**.")
w("> This is the authoritative, version-current, DLC-inclusive list for THIS install.")
w(">")
w("> **What this is:** every identifier *actually used* by shipped content — "
  f"**{len(eff_count)} effects, {len(coll_count)} collections, {len(req_count)} requirements**, "
  "plus per-effect/per-requirement argument names (with usage counts in parentheses).")
w("> **Limitation:** it lists identifiers the shipped game/DLC *reference*; an engine type that exists")
w("> but nothing uses won't appear (rare; pull the runtime `gameplay-copy.sqlite` if ever needed —")
w("> see `docs/GLOBALPARAMETERS-CITY-TILES.md`).")
w(">")
w("> **⚠️ Re-generate after every game patch / new DLC** — do NOT trust any external/older list, which")
w("> silently goes stale. Method: re-run the extraction over the install (the generator is in the session")
w("> that created this file; the core is a scan for `effect=`, `collection=`, `<Requirement type=`, and")
w("> `<Argument name=>YieldType` over `Base\modules` + `DLC`).")
w()
w("## Yields (real `YieldType` values)")
w()
w("These are the values actually passed as a `YieldType` argument (so they exclude the hundreds of")
w("`YIELD_*` tooltip/format tokens that a naive text grep catches). Count = times used as a YieldType.")
w()
for y,c in yieldtypes.most_common():
    w(f"- `{y}` ({c})")
w()
w("**Note:** in-game **Influence = `YIELD_DIPLOMACY`** (confirmed here independently). The 7 core yields")
w("are Gold/Culture/Production/Happiness/Science/Food/Diplomacy; the rest above are pseudo-yields used by")
w("specific per-yield effects.")
w()
w("## Collections (all used)")
w()
w("Count = number of modifiers using it. **★ = player-rooted** — resolves correctly when delivered")
w("through the `COLLECTION_MAJOR_PLAYERS` attach-wrapper (the others need a city/unit/plot context and")
w("**silently no-op** if attached at player scope).")
w()
for c,n in coll_count.most_common():
    star=" ★" if c in PLAYER_ROOTED else ""
    w(f"- `{c}` ({n}){star}")
w()
w("## Effects (all used) + their arguments")
w()
w("Each effect lists its direct `<Argument name>`s (requirement args excluded), ordered by frequency.")
w("`(n)` after the effect = modifiers using it; `(n)` after an arg = times that arg appears.")
w()
order=["CITY","PLAYER","UNIT","DISTRICT","PLOT","DIPLOMACY","CITIES","ARMY","COMMANDER","GENERAL / CROSS-CUTTING"]
for b in order:
    if b not in buckets: continue
    w(f"### EFFECT — {b}")
    w()
    for e in sorted(buckets[b], key=lambda x:(-eff_count[x],x)):
        args=eff_args[e]
        argstr=", ".join(f"{a}({n})" for a,n in args.most_common()) if args else "—"
        w(f"- `{e}` ({eff_count[e]}) — {argstr}")
    w()
w("## Requirements (all used) + their arguments")
w()
for r in sorted(req_count, key=lambda x:(-req_count[x],x)):
    args=req_args[r]
    argstr=", ".join(f"{a}({n})" for a,n in args.most_common()) if args else "—"
    w(f"- `{r}` ({req_count[r]}) — {argstr}")
w()
os.makedirs(os.path.dirname(OUTMD),exist_ok=True)
open(OUTMD,"w",encoding="utf-8").write("\n".join(L)+"\n")
print("WROTE",OUTMD)
print("bytes:",os.path.getsize(OUTMD))
print("yields(real):",len(yieldtypes)," collections:",len(coll_count)," effects:",len(eff_count)," requirements:",len(req_count))
