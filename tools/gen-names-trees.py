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
REFDIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references"))
def datafiles():
    out=[]
    for base in (os.path.join(ROOT,"Base","modules"), os.path.join(ROOT,"DLC")):
        out+=glob.glob(os.path.join(base,"**","data","**","*.xml"),recursive=True)
    return out
def textfiles():
    out=[]
    for base in (os.path.join(ROOT,"Base","modules"), os.path.join(ROOT,"DLC")):
        out+=glob.glob(os.path.join(base,"**","text","en_us","*.xml"),recursive=True)
    return out

# ---- 1. LOC -> English ----
loc={}
row_text_re=re.compile(r'<Row\b[^>]*\bTag="(LOC_[A-Z0-9_]+)"[^>]*>\s*<Text>(.*?)</Text>',re.S)
for fp in textfiles():
    try: txt=open(fp,encoding="utf-8",errors="replace").read()
    except: continue
    for tag,en in row_text_re.findall(txt):
        en=en.strip()
        if '|' in en: en=en.split('|')[0].strip()
        en=re.sub(r'\s+',' ',en)
        loc.setdefault(tag,en)

# ---- 2. id -> display name (rows with a *Type attr + Name="LOC_") ----
attr_re=re.compile(r'(\w+)="([^"]*)"')
elem_re=re.compile(r'<(Row|Replace|Insert)\b([^>]*?)/?>')
id2name={}
for fp in datafiles():
    try: txt=open(fp,encoding="utf-8",errors="replace").read()
    except: continue
    for _,attrs in elem_re.findall(txt):
        d=dict(attr_re.findall(attrs))
        name=d.get("Name","")
        if not name.startswith("LOC_"): continue
        idv=None
        for k,v in d.items():
            if k.endswith("Type") and k!="Kind" and re.match(r'^[A-Z][A-Z0-9_]+$',v):
                idv=v; break
        if not idv: continue
        en=loc.get(name)
        if en: id2name.setdefault(idv,en)

def prefix(idv):
    p=idv.split("_")[0]
    if idv.startswith("NODE_TECH"): return "NODE_TECH (techs)"
    if idv.startswith("NODE_CIVIC") or idv.startswith("NODE_CULTURE"): return "NODE_CIVIC (civics)"
    if idv.startswith("PROJECT_TOWN"): return "PROJECT_TOWN (town focuses)"
    return p
groups=collections.defaultdict(list)
for idv,en in id2name.items(): groups[prefix(idv)].append((idv,en))

now=datetime.date.today().isoformat()
CARE=["PROJECT_TOWN (town focuses)","YIELD","BUILDING","IMPROVEMENT","WONDER","QUARTER",
      "DISTRICT","UNIT","CIVILIZATION","LEADER","TRADITION","RESOURCE",
      "NODE_TECH (techs)","NODE_CIVIC (civics)","PROJECT"]
L=[]; W=L.append
W("# Civ VII data-id → in-game display name (English)")
W("")
W(f"> **Provenance.** Extracted **{now}** from the local install (Steam buildid 23245653): joined every")
W(f"> `…Type=\"ID\" Name=\"LOC_*\"` data row to its English string in `text/en_us/*.xml`, across `Base\modules`")
W(f"> + all `DLC`. **{len(id2name)} id→name pairs**, {len(loc)} en_us strings scanned. Regenerate via")
W("> [`tools/gen-names-trees.py`](../tools/gen-names-trees.py) after each patch.")
W(">")
W("> **Why this exists:** mods reference DATA ids (`BUILDING_TEMPLE`, `PROJECT_TOWN_INN`), but players and")
W("> the wiki see DISPLAY names (\"Temple\", \"Hub Town\"). This is the lookup both ways. Categories the mod")
W("> work cares about most are first; the rest follow.")
W("")
done=set()
def emit(cat):
    if cat not in groups: return
    items=sorted(groups[cat])
    W(f"### {cat}  ({len(items)})")
    W("")
    for idv,en in items: W(f"- `{idv}` → {en}")
    W("")
    done.add(cat)
for c in CARE: emit(c)
others=sorted(set(groups)-done, key=lambda c:-len(groups[c]))
W("### Other categories")
W("")
for c in others:
    W(f"**{c}** ({len(groups[c])}): " + ", ".join(f"`{i}`={n}" for i,n in sorted(groups[c])[:40]) + (" …" if len(groups[c])>40 else ""))
W("")
os.makedirs(REFDIR,exist_ok=True)
open(os.path.join(REFDIR,"display-names.md"),"w",encoding="utf-8").write("\n".join(L)+"\n")
print("display-names.md:", len(id2name),"ids,",len(loc),"strings")

# ---- 3. progression trees ----
tnode_re=re.compile(r'<Row\b[^>]*\bProgressionTreeNodeType="(NODE_[A-Z0-9_]+)"[^>]*\bProgressionTree="([A-Z0-9_]+)"[^>]*?(?:\bCost="(\d+)")?[^>]*?(?:\bName="(LOC_[A-Z0-9_]+)")?[^>]*/?>')
prereq_re=re.compile(r'<Row\b[^>]*\bNode="(NODE_[A-Z0-9_]+)"[^>]*\bPrereqNode="(NODE_[A-Z0-9_]+)"')
unlock_re=re.compile(r'<Row\b[^>]*\bProgressionTreeNodeType="(NODE_[A-Z0-9_]+)"[^>]*\bUnlockDepth="(\d)"')
nodes={}      # node -> {tree,cost,name}
prereqs=collections.defaultdict(set)  # node -> set(prereq)
mastery=set() # nodes with an UnlockDepth=2 unlock
treefiles=[]
for base in (os.path.join(ROOT,"Base","modules"),):
    treefiles+=glob.glob(os.path.join(base,"**","data","**","progression-trees*.xml"),recursive=True)
for fp in treefiles:
    try: txt=open(fp,encoding="utf-8",errors="replace").read()
    except: continue
    for _tag,attrs in elem_re.findall(txt):
        d=dict(attr_re.findall(attrs))
        node=d.get("ProgressionTreeNodeType"); tree=d.get("ProgressionTree")
        if node and tree and node.startswith("NODE_"):
            nm=d.get("Name","")
            nodes.setdefault(node,{"tree":tree,"cost":d.get("Cost",""),"name":loc.get(nm,nm)})
    for n,p in prereq_re.findall(txt): prereqs[n].add(p)
    for n,d in unlock_re.findall(txt):
        if d=="2": mastery.add(n)
def depth(n,seen=None):
    seen=seen or set()
    if n in seen or n not in prereqs or not prereqs[n]: return 1
    seen=seen|{n}
    return 1+max((depth(p,seen) for p in prereqs[n] if p in nodes), default=0)
bytree=collections.defaultdict(list)
for n,info in nodes.items(): bytree[info["tree"]].append(n)
def age_of(tree):
    for a in ("AQ","EX","MO"):
        if a in tree: return a
    return "?"
L2=[]; W2=L2.append
W2("# Civ VII progression-tree structure (techs + civics, per age)")
W2("")
W2(f"> **Provenance.** Extracted **{now}** from the local install (buildid 23245653), parsing every")
W2("> `Base\modules\**\data\**\progression-trees*.xml`. **{} nodes across {} trees.** Regenerate via".format(len(nodes),len(bytree)))
W2("> [`tools/gen-names-trees.py`](../tools/gen-names-trees.py).")
W2(">")
W2("> **Column** = computed longest prereq chain (root nodes = col 1) — the practical \"how early\" gauge;")
W2("> **Cost** is the raw research/civic cost (also a timing signal). **★ mastery** = the node has an")
W2("> unlock at `UnlockDepth=\"2\"`, so a `MinDepth=2` gate fires on it; nodes WITHOUT ★ have no mastery and")
W2("> a `MinDepth=2` gate on them **silently never fires** (the recurring trap). Gating uses")
W2("> `REQUIREMENT_PLAYER_HAS_COMPLETED_PROGRESSION_TREE_NODE` (+ optional `MinDepth`).")
W2("")
MAINFIRST=["TREE_TECHS_","TREE_CIVICS_","TREE_CULTURE_"]
def sortkey(t):
    a=age_of(t); ai={"AQ":0,"EX":1,"MO":2,"?":3}[a]
    main=0 if any(t.startswith(p) for p in MAINFIRST) else 1
    return (ai,main,t)
for tree in sorted(bytree,key=sortkey):
    ns=bytree[tree]
    W2(f"### {tree}  (age {age_of(tree)}, {len(ns)} nodes)")
    W2("")
    W2("| Col | Cost | Node | Name | Mastery |")
    W2("|----:|-----:|------|------|:-------:|")
    for n in sorted(ns,key=lambda x:(depth(x), int(nodes[x]['cost'] or 0), x)):
        info=nodes[n]
        W2(f"| {depth(n)} | {info['cost'] or ''} | `{n}` | {info['name']} | {'★' if n in mastery else ''} |")
    W2("")
open(os.path.join(REFDIR,"progression-trees.md"),"w",encoding="utf-8").write("\n".join(L2)+"\n")
print("progression-trees.md:", len(nodes),"nodes,",len(bytree),"trees,",len(mastery),"with mastery")
