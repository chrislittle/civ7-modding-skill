#!/usr/bin/env python3
"""Generate references/cards-suzerain-governments-catalog.md from the installed Civ VII data:
every Tradition/Policy/Crisis card + Suzerain (city-state) bonus + government (base + all DLC),
with resolved English effects. Bulk extraction — not bundled; regenerate after each patch/DLC.
Auto-detects the install via $CIV7_ROOT / Steam libraries (same as gen-effects-catalog.py)."""
import os, re, glob, html

def find_civ7_root():
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
    raise SystemExit("Civ VII install not found. Set CIV7_ROOT to the game folder.")

ROOT = find_civ7_root()
ROOTS = [os.path.join(ROOT, "Base"), os.path.join(ROOT, "DLC")]
OUTMD = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "cards-suzerain-governments-catalog.md"))

# ---- icon humanizer ----
YIELD = {'GOLD':'Gold','FOOD':'Food','PRODUCTION':'Production','SCIENCE':'Science',
         'CULTURE':'Culture','HAPPINESS':'Happiness','DIPLOMACY':'Influence','MAINTENANCE':'Maintenance'}
icon_re = re.compile(r'\[icon:([A-Za-z0-9_]+)\]')
def icon_sub(m):
    tok = m.group(1)
    return ' '+YIELD.get(tok[6:], tok[6:].title())+' ' if tok.startswith('YIELD_') else ' '
def clean(t):
    t = html.unescape(t)
    t = re.sub(r'\[TIP:[^\]]*\]', '', t)
    t = icon_re.sub(icon_sub, t)
    t = re.sub(r'\[/?(?:B|n|s|LINK|LIST|BLIST|COLOR|SIZE|TIP)[^\]]*\]', ' ', t)
    t = re.sub(r'\[[^\]]*\]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    t = re.sub(r'\b(\w+)(\s+\1\b)+', r'\1', t, flags=re.I)
    t = re.sub(r'\s+([.,;])', r'\1', t)
    return t.strip()

# ---- LOC map (English: text/ root + text/en_us/, exclude l10n/) ----
loc = {}
row_re = re.compile(r'<Row\s+Tag="([^"]+)"\s*>(.*?)</Row>', re.S)
text_re = re.compile(r'<Text>(.*?)</Text>', re.S)
for root in ROOTS:
    for f in glob.glob(os.path.join(root, "**", "text", "**", "*.xml"), recursive=True):
        if os.sep+'l10n'+os.sep in f: continue
        try: s = open(f, encoding='utf-8').read()
        except Exception: continue
        for m in row_re.finditer(s):
            tm = text_re.search(m.group(2))
            if tm: loc[m.group(1)] = clean(tm.group(1))
def L(k): return loc.get(k, '') if k else ''
def module_of(path):
    m = re.search(r'[\\/]modules[\\/]([^\\/]+)[\\/]', path) or re.search(r'[\\/]DLC[\\/]([^\\/]+)[\\/]', path)
    return m.group(1) if m else '?'
attrs = lambda s: dict(re.findall(r'(\w+)="([^"]*)"', s))
rowrx = re.compile(r'<Row\s+([^>]*?)/?>')

# ---- cards ----
cards = {}
tfiles = []
for root in ROOTS: tfiles += glob.glob(os.path.join(root,"**","data","traditions*.xml"), recursive=True)
for f in sorted(set(tfiles)):
    mod = module_of(f); s = open(f, encoding='utf-8', errors='ignore').read()
    b = re.search(r'<Traditions>(.*?)</Traditions>', s, re.S)
    if not b: continue
    for m in rowrx.finditer(b.group(1)):
        a = attrs(m.group(0))
        if 'TraditionType' not in a or 'Name' not in a: continue
        cards[a['TraditionType']] = {'type': a['TraditionType'],
            'slot': a.get('CultureSlotType','?').replace('_CULTURE_SLOT',''),
            'age': a.get('AgeType','').replace('AGE_',''), 'trait': a.get('TraitType',''),
            'module': mod, 'name': L(a['Name']), 'desc': L(a.get('Description',''))}
internal = [c for c in cards.values() if not c['name'] and not c['desc']]
cards = [c for c in cards.values() if c['name'] or c['desc']]

# ---- suzerain ----
suz = {}
for f in glob.glob(os.path.join(ROOT,"Base","modules","**","data","independents.xml"), recursive=True):
    mod = module_of(f); s = open(f, encoding='utf-8', errors='ignore').read()
    for m in rowrx.finditer(s):
        a = attrs(m.group(0))
        if 'CityStateBonusType' in a and 'Name' in a:
            suz[a['CityStateBonusType']] = {'type': a['CityStateBonusType'], 'cstype': a.get('CityStateType','?'),
                'age': mod.replace('age-','').upper(), 'name': L(a['Name']), 'desc': L(a.get('Description',''))}
suz = list(suz.values())

# ---- governments ----
govs = {}
for f in glob.glob(os.path.join(ROOT,"Base","modules","**","data","governments.xml"), recursive=True):
    mod = module_of(f); s = open(f, encoding='utf-8', errors='ignore').read()
    for m in rowrx.finditer(s):
        a = attrs(m.group(0))
        if 'GovernmentType' in a and 'Name' in a:
            base = a['GovernmentType'].replace('GOVERNMENT_','')
            ga = [L(f'LOC_GOLDEN_AGE_{base}_{i}_DESCRIPTION') for i in range(1,7)]; ga=[g for g in ga if g]
            govs[a['GovernmentType']] = {'type': a['GovernmentType'], 'age': mod.replace('age-','').upper(),
                'name': L(a['Name']), 'passive': L(f'LOC_GOVERNMENT_{base}_PASSIVE_DESCRIPTION') or L(a.get('Description','')),
                'celeb': L(a.get('CelebrationName','')), 'ga': ga}
govs = list(govs.values())

# ---- output ----
out=[]; w=out.append
w("# Civ VII CARD / SUZERAIN / GOVERNMENT CATALOG — base + all DLC (installed)")
w("\n> Generated by `tools/gen-cards-catalog.py` from the installed data (not bundled — regenerate after a patch/DLC).")
w("> **Every** slottable card + suzerain bonus + government the base game and DLC ship, with resolved English effects.")
w("> Use to (a) confirm what a base/DLC card already does before referencing it, and (b) keep a mod's new cards")
w("> **new-&-unique** — don't duplicate or closely mirror anything here. Slot types: POLICY (common/celebration pool),")
w("> TRADITION (civ-unique + attribute-tree, scarce), CRISIS. Companion: `civ6-policies-governments-catalog.md`,")
w("> `civ6-civ7-mechanic-delta.md`.\n")
policy=[c for c in cards if c['slot']=='POLICY']; trad=[c for c in cards if c['slot']=='TRADITION']; cris=[c for c in cards if c['slot']=='CRISIS']
w(f"**Totals:** {len(policy)} generic Policy · {len(trad)} Tradition (civ-unique + attribute-tree) · {len(cris)} Crisis · {len(suz)} Suzerain bonuses · {len(govs)} Governments")
if internal: w(f"\n*({len(internal)} text-less internal rows omitted: {', '.join('`'+c['type']+'`' for c in internal)}.)*\n")

def ctable(title, rows):
    w(f"\n## {title}  ({len(rows)})\n"); w("| Type | Age | Civ/Source | Name | Effect |"); w("|---|---|---|---|---|")
    for c in sorted(rows, key=lambda x:(x['age'],x['module'],x['type'])):
        civ = c['trait'].replace('TRAIT_','') or c['module']
        w(f"| `{c['type']}` | {c['age'] or '—'} | {civ} | **{c['name']}** | {c['desc']} |")
ctable("GENERIC POLICY CARDS — POLICY_CULTURE_SLOT (common / celebration-fed pool)", policy)
ctable("TRADITION-SLOT CARDS — civ-unique + attribute-tree (scarce pool)", trad)
ctable("CRISIS CARDS — CRISIS_CULTURE_SLOT", cris)
w(f"\n## SUZERAIN (CITY-STATE) BONUSES  ({len(suz)})\n"); w("| Type | Age | City-State Type | Name | Bonus |"); w("|---|---|---|---|---|")
for c in sorted(suz, key=lambda x:(x['age'],x['cstype'],x['type'])):
    w(f"| `{c['type']}` | {c['age']} | {c['cstype']} | **{c['name']}** | {c['desc']} |")
w(f"\n## GOVERNMENTS  ({len(govs)})  — passive + celebration (Golden Age) choices\n")
for g in sorted(govs, key=lambda x:(x['age'],x['type'])):
    w(f"\n### {g['name']}  (`{g['type']}`, {g['age']})")
    w(f"- **Passive:** {g['passive'] or '—'}"); w(f"- **Celebration ({g['celeb']}):**")
    for i,ga in enumerate(g['ga'],1): w(f"  {i}. {ga}")

os.makedirs(os.path.dirname(OUTMD), exist_ok=True)
open(OUTMD,"w",encoding="utf-8").write("\n".join(out))
print(f"wrote {OUTMD}\n  cards {len(cards)} (P{len(policy)} T{len(trad)} C{len(cris)}) | suzerain {len(suz)} | govs {len(govs)} | LOC {len(loc)}")
