#!/usr/bin/env python3
"""
gen-devkit-docs.py
Bank the Civ VII Development Kit's OFFICIAL modding documentation (the `Documentation/`
folder that ships with the "Sid Meier's Civilization VII Development Tools" Steam app)
into one local reference: references/dev-kit-official-docs.md

These are Firaxis's own primer docs (Getting Started, Database Modding, The Modifier
System, modinfo Files, Narrative Events). The skill's authored references go deeper and
correct/extend these with isolation-tested findings, but this is the authoritative
first-party source — handy to consult verbatim. Verbatim Firaxis text => generate-locally,
never shipped in the public skill export.

Autodetects the dev-kit install via $CIV7_DEVKIT_ROOT -> Steam library folders.
Regenerate after each dev-kit update (check the VERSION file).
"""
import os, re, glob, datetime

def find_devkit_root():
    env = os.environ.get("CIV7_DEVKIT_ROOT")
    if env and os.path.isdir(env): return env
    libs = {r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"}
    try:
        vdf = open(r"C:\Program Files (x86)\Steam\steamapps\libraryfolders.vdf", encoding="utf-8", errors="replace").read()
        for m in re.findall(r'"path"\s*"([^"]+)"', vdf): libs.add(m.replace("\\\\", "\\"))
    except OSError:
        pass
    for lib in libs:
        p = os.path.join(lib, r"steamapps\common\Sid Meier's Civilization VII Development Tools")
        if os.path.isdir(p): return p
    raise SystemExit("Civ VII Development Tools not found. Set CIV7_DEVKIT_ROOT to that folder.")

ROOT = find_devkit_root()
DOCS = os.path.join(ROOT, "Documentation")
REFDIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references"))

# Read order (skip Index.md; images aren't shipped so image lines are stripped).
ORDER = ["Getting Started.md", "modinfo Files.md", "Database Modding.md",
         "The Modifier System.md", "Narrative Events.md"]

def transform(md):
    # drop image embeds (assets not present) and demote every heading one level so the
    # concatenated doc has a single H1 at the top and each source doc becomes an H2 section.
    out = []
    for line in md.splitlines():
        if re.match(r'\s*>?\s*!\[.*?\]\(.*?\)\s*$', line):   # ![](Images/foo.png), incl. blockquoted
            continue
        m = re.match(r'^(#{1,6})(\s+.*)$', line)
        if m:
            level = min(len(m.group(1)) + 2, 6)          # nest under the doc's own '## <name>' wrapper
            line = "#" * level + m.group(2)
        out.append(line)
    return "\n".join(out).strip()

ver = ""
try: ver = open(os.path.join(ROOT, "VERSION"), encoding="utf-8", errors="replace").read().strip()
except OSError: pass

parts = []
parts.append("# Civilization VII — Official Dev-Kit Modding Documentation\n")
parts.append("> Verbatim copy of the `Documentation/` folder shipped with the **Civilization VII "
             "Development Tools** (the modding SDK). These are Firaxis's own first-party primers. "
             "The skill's other references go deeper and correct/extend these with isolation-tested "
             "findings (e.g. the integer-Version rule, the attach-wrapper delivery pattern, the "
             "MinDepth silent-killer) — when they disagree, trust the tested references. Image embeds "
             "are stripped (assets not copied). Regenerate via `tools/gen-devkit-docs.py`.\n")
parts.append("_Generated %s from Development Tools build %s_\n" % (datetime.date.today().isoformat(), ver or "?"))
# table of contents
parts.append("\n**Contents:** " + " · ".join("[%s](#%s)" % (
    os.path.splitext(n)[0], os.path.splitext(n)[0].lower().replace(" ", "-")) for n in ORDER) + "\n")

present = {os.path.basename(p): p for p in glob.glob(os.path.join(DOCS, "*.md"))}
for name in ORDER:
    fp = present.get(name)
    if not fp:
        continue
    md = open(fp, encoding="utf-8", errors="replace").read()
    parts.append("\n\n---\n\n## " + os.path.splitext(name)[0] + "\n")
    parts.append(transform(md))

# include any extra .md docs not in ORDER (future-proofing), except Index
for name, fp in sorted(present.items()):
    if name in ORDER or name.lower() == "index.md":
        continue
    md = open(fp, encoding="utf-8", errors="replace").read()
    parts.append("\n\n---\n\n## " + os.path.splitext(name)[0] + "\n")
    parts.append(transform(md))

out_path = os.path.join(REFDIR, "dev-kit-official-docs.md")
with open(out_path, "w", encoding="utf-8") as f:
    f.write("\n".join(parts).rstrip() + "\n")
print("Wrote", out_path)
print("Docs banked:", sum(1 for n in ORDER if n in present))
