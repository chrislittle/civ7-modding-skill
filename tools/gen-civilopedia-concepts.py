#!/usr/bin/env python3
"""
gen-civilopedia-concepts.py
Extract the game's OWN Civilopedia *mechanic prose* (the designers' explanations of
how each system works) into one clean markdown reference: references/civilopedia-concepts.md

This is the design gold the per-unit/civ generators DON'T give you: the CONCEPTS section
(Ages, Attributes, Combat/Army, Buildings, Statehood, Settlements/Towns, Diplomacy,
Happiness, Growth, Legends...), the AGES section (age transition + carry-over rules),
and the VICTORIES prose (exact Dominion points, tourism thresholds, age-progress gates).

Sourced from the installed game's Civilopedia_*_Text.xml + civilopedia*.xml data (ordering).
Regenerate after each patch/DLC. Autodetects install via $CIV7_ROOT -> Steam libraries.
"""
import os, re, glob, datetime

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
REFDIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references"))

def read(fp):
    try: return open(fp, encoding="utf-8", errors="replace").read()
    except OSError: return ""

# ---- 1. Load ALL localized text (Tag -> English) ----
row_text_re = re.compile(r'<Row\b[^>]*\bTag="(LOC_[A-Z0-9_]+)"[^>]*>\s*<Text>(.*?)</Text>', re.S)
loc = {}
loc_order = {}   # tag -> (file_index, position) for stable fallback ordering
def textfiles():
    out = []
    for base in (os.path.join(ROOT, "Base", "modules"), os.path.join(ROOT, "DLC")):
        out += glob.glob(os.path.join(base, "**", "text", "en_us", "*.xml"), recursive=True)
    return sorted(out)
for fi, fp in enumerate(textfiles()):
    txt = read(fp)
    for m in row_text_re.finditer(txt):
        tag, en = m.group(1), m.group(2).strip()
        loc.setdefault(tag, en)
        loc_order.setdefault(tag, (fi, m.start()))

def clean(s):
    """Render inline Civ markup into readable plaintext/markdown."""
    if s is None: return ""
    s = s.replace("[BLIST]", "\n").replace("[/BLIST]", "\n")
    s = s.replace("[LIST]", "\n").replace("[/LIST]", "\n")
    s = re.sub(r'\[LI\]', "\n- ", s)
    s = re.sub(r'\[/?B\]', "**", s)
    s = re.sub(r'\[/?I\]', "*", s)
    s = s.replace("[N]", "\n").replace("[NEWLINE]", "\n")
    s = re.sub(r'\[ICON_[A-Z0-9_]+\]', "", s)      # drop yield/icon glyph tags
    s = re.sub(r'\[/?COLOR[^\]]*\]', "", s)
    s = re.sub(r'\[/?[a-zA-Z][^\]]*\]', "", s)      # any remaining [tags]
    s = re.sub(r'[ \t]+', " ", s)
    s = re.sub(r'\n[ \t]+', "\n", s)
    s = re.sub(r'\n{3,}', "\n\n", s)
    return s.strip()

# ---- 2. Parse Civilopedia data files for page ordering / grouping ----
def datafiles():
    out = []
    for base in (os.path.join(ROOT, "Base", "modules"),):
        out += glob.glob(os.path.join(base, "**", "data", "civilopedia*.xml"), recursive=True)
    return sorted(out)

attr_re = re.compile(r'(\w+)="([^"]*)"')
def rows(txt, table):
    """Yield attr-dicts of <Row .../> inside <table>...</table>, ignoring XML comments."""
    m = re.search(r'<%s>(.*?)</%s>' % (table, table), txt, re.S)
    if not m: return
    body = re.sub(r'<!--.*?-->', '', m.group(1), flags=re.S)
    for rm in re.finditer(r'<Row\b([^>]*?)/?>', body):
        yield dict(attr_re.findall(rm.group(1)))

sections = {}          # sid -> {name, sort}
groups = {}            # sid -> {gid -> {name, sort}}
pages = []             # {sid, pid, gid, layout, name, sort}
chapter_sort = {}      # (layout, chapterid) -> sort
for fp in datafiles():
    txt = read(fp)
    for r in rows(txt, "CivilopediaSections"):
        sections[r["SectionID"]] = {"name": r.get("Name", ""), "sort": int(r.get("SortIndex", 0))}
    for r in rows(txt, "CivilopediaPageGroups"):
        groups.setdefault(r["SectionID"], {})[r["PageGroupID"]] = {"name": r.get("Name", ""), "sort": int(r.get("SortIndex", 0))}
    for r in rows(txt, "CivilopediaPages"):
        pages.append({"sid": r["SectionID"], "pid": r["PageID"], "gid": r.get("PageGroupID"),
                      "layout": r.get("PageLayoutID", "Concept"), "name": r.get("Name", ""),
                      "sort": int(r.get("SortIndex", 0))})
    for r in rows(txt, "CivilopediaPageLayoutChapters"):
        chapter_sort[(r["PageLayoutID"], r["ChapterID"])] = int(r.get("SortIndex", 0))

# ---- 3. For a page, gather title + ordered chapters/paragraphs from its text-key prefix ----
def page_prefix(pg):
    n = pg["name"]
    return n[:-6] if n.endswith("_TITLE") else n   # strip _TITLE to get the shared prefix

para_tail_re = re.compile(r'^(.*)_PARA_(\d+)$')
def render_page(pg):
    prefix = page_prefix(pg)
    if not prefix: return None
    title = clean(loc.get(pg["name"])) or clean(loc.get(prefix + "_TITLE")) or pg["pid"]
    cprefix = prefix + "_CHAPTER_"
    # collect chapter fragments
    chapters = {}   # chapterid -> {"title":..., "body":[str], "paras":{n:str}}
    for tag, en in loc.items():
        if not tag.startswith(cprefix): continue
        rest = tag[len(cprefix):]
        ch = chapters
        if rest.endswith("_TITLE"):
            cid = rest[:-6]; kind = ("title", None)
        elif rest.endswith("_BODY"):
            cid = rest[:-5]; kind = ("body", None)
        else:
            mm = para_tail_re.match(rest)
            if not mm: continue
            cid = mm.group(1); kind = ("para", int(mm.group(2)))
        c = chapters.setdefault(cid, {"title": None, "body": [], "paras": {}})
        if kind[0] == "title": c["title"] = clean(en)
        elif kind[0] == "body": c["body"].append(clean(en))
        else: c["paras"][kind[1]] = clean(en)
    if not chapters: return None
    # order chapters by data SortIndex for this layout, else alphabetical-ish (CONTENT first)
    def ckey(cid):
        s = chapter_sort.get((pg["layout"], cid))
        return (0, s) if s is not None else (1, 0 if cid == "CONTENT" else 1, cid)
    out = ["### " + title, ""]
    for cid in sorted(chapters, key=ckey):
        c = chapters[cid]
        if c["title"] and c["title"].lower() not in ("basics", "content", title.lower()):
            out.append("**" + c["title"] + "**")
            out.append("")
        for b in c["body"]:
            if b: out.append(b); out.append("")
        for n in sorted(c["paras"]):
            if c["paras"][n]: out.append(c["paras"][n]); out.append("")
    return "\n".join(out).rstrip() + "\n"

# ---- 4. Emit CONCEPTS + AGES sections grouped/ordered by data ----
md = []
md.append("# Civilization VII — Civilopedia: Concepts, Ages & Victories\n")
md.append("> Extracted verbatim from the installed game's in-game Civilopedia "
          "(`Civilopedia_*_Text.xml`), ordered by the Civilopedia's own page/group structure. "
          "This is the designers' own explanation of how each system works — the authoritative "
          "reference for mechanic behavior and magic numbers. Regenerate after each patch via "
          "`tools/gen-civilopedia-concepts.py`.\n")
md.append("_Generated %s from %s_\n" % (datetime.date.today().isoformat(), os.path.basename(ROOT)))

emitted_pids = set()
for sid in sorted(sections, key=lambda s: sections[s]["sort"]):
    if sid not in ("CONCEPTS", "AGES"):
        continue
    sec_pages = [p for p in pages if p["sid"] == sid]
    if not sec_pages: continue
    md.append("\n---\n\n## " + (clean(loc.get(sections[sid]["name"])) or sid) + "\n")
    grp = groups.get(sid, {})
    def gkey(p):
        g = grp.get(p["gid"], {})
        return (g.get("sort", 999), p["sort"])
    last_g = object()
    for p in sorted(sec_pages, key=gkey):
        if p["gid"] and p["gid"] in grp and p["gid"] != last_g:
            gname = clean(loc.get(grp[p["gid"]]["name"])) or p["gid"]
            # only print a group header when it differs meaningfully from section
            if gname and gname.lower() != (clean(loc.get(sections[sid]["name"])) or sid).lower():
                md.append("\n### ~ " + gname + " ~\n")
            last_g = p["gid"]
        body = render_page(p)
        if body and p["pid"] not in emitted_pids:
            md.append(body); md.append("")
            emitted_pids.add(p["pid"])

# ---- 5. Victories: query-generated pages, so pull their text file directly, in file order ----
vic_fp = os.path.join(ROOT, "Base", "modules", "base-standard", "text", "en_us", "Civilopedia_Victories_Text.xml")
vtxt = read(vic_fp)
if vtxt:
    md.append("\n---\n\n## Victories\n")
    # group tags by page prefix (LOC_PEDIA_PAGE_VICTORY_<X>) in file order
    seen = []
    vpages = {}
    for m in row_text_re.finditer(vtxt):
        tag = m.group(1)
        pm = re.match(r'(LOC_PEDIA_PAGE_VICTORY_[A-Z_]+?)(_CHAPTER_.*|_TITLE)$', tag)
        if not pm: continue
        pre = pm.group(1)
        if pre not in vpages:
            vpages[pre] = True; seen.append(pre)
    for pre in seen:
        title = clean(loc.get(pre + "_TITLE")) or pre
        out = ["### " + title, ""]
        # paras under CONTENT chapter
        i = 1
        while True:
            t = loc.get("%s_CHAPTER_CONTENT_PARA_%d" % (pre, i))
            if t is None: break
            out.append(clean(t)); out.append(""); i += 1
        body = loc.get(pre + "_CHAPTER_CONTENT_BODY")
        if body: out.insert(2, clean(body) + "\n")
        if i > 1 or body:
            md.append("\n".join(out).rstrip() + "\n")

out_path = os.path.join(REFDIR, "civilopedia-concepts.md")
with open(out_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md).rstrip() + "\n")
print("Wrote", out_path)
print("Pages emitted:", len(emitted_pids))
