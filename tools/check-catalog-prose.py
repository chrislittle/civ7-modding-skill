r"""Find hand-written prose sitting in a GENERATED, GITIGNORED catalog - where it is doomed.

WHY THIS EXISTS
The reference catalogs (effects-collections, constructibles, units, religion, ...) are each
rewritten WHOLE by a tools/gen-*.py, and every one of them is gitignored from the public skill repo
because they are extractions of Firaxis content. So a finding typed into one has TWO fates, both
silent: it is destroyed the next time the generator runs, and it never reaches anyone reading the
published skill.

That happened on 2026-08-08. Two blocks of hard-won in-play results - the "founded this Age"
litmus and the day's OR-set/single-use rules - were sitting in effects-collections-catalog.md.
Both were moved to references/gameeffects.md, and the effects generator now prints a warning about
itself on every run. This script is the sweep that catches the same mistake in the other fifteen.

HOW IT DECIDES
A blockquote (a run of lines starting `>`) is GENERATED if it shares a six-word run with any
generator's source, and HAND-WRITTEN otherwise. Both sides are stripped of markdown first, because
a generator writes `> **Note**` while the file holds `> **Note**` after interpolation - comparing
raw text reports every generated header as hand-written. Six-word runs rather than whole lines
because f-string interpolation (dates, counts, paths) breaks a line in the middle: the literal tail
still matches. It errs toward reporting - a false positive costs ten seconds of reading, a false
negative costs a finding.

Run:  python tools/check-catalog-prose.py
Exit: 1 if anything hand-written is found, so it can gate a publish.
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFS = os.path.join(SKILL, 'references')
TOOLS = os.path.join(SKILL, 'tools')

# WHICH FILES ARE AT RISK: ask the generators, not a gitignore. The export's .gitignore is written
# by publish.ps1 and only exists in the export folder, so it is not visible from here - and the
# generator that WRITES a file is the authority on whether that file is generated anyway.
sources, generated = [], set()
for f in sorted(os.listdir(TOOLS)):
    if not f.endswith('.py') or f == os.path.basename(__file__):
        continue
    src = open(os.path.join(TOOLS, f), encoding='utf-8', errors='replace').read()
    sources.append(src)
    generated |= {os.path.basename(m) for m in re.findall(r'["\']([A-Za-z0-9_\-]+\.md)["\']', src)}
allsrc = '\n'.join(sources)
generated = sorted(generated)


# Files whose generator COPIES text in from elsewhere rather than emitting it as literals. Their
# blockquotes come from the copied source, so they can never be matched against the generator - and
# they are not at risk in the first place, because a re-run copies them straight back.
VERBATIM = {'dev-kit-official-docs.md'}


def norm(s):
    """Markdown and whitespace removed, so a file line and its generator literal compare equal."""
    return re.sub(r'\s+', ' ', re.sub(r'[>*`\[\]#_]', '', s)).strip().lower()


def shingles(s, n=6):
    """Overlapping n-word runs - a generated line shares a long literal run with its generator,
    a hand-written one shares none. Beats matching whole lines, which f-string interpolation
    (dates, counts, paths) breaks in the middle."""
    w = norm(s).split()
    return {' '.join(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


def blocks(text):
    """Runs of consecutive blockquote lines, with the line number each starts on."""
    out, cur, start = [], [], 0
    for i, ln in enumerate(text.split('\n'), 1):
        if ln.startswith('>'):
            if not cur:
                start = i
            cur.append(ln)
        elif cur:
            out.append((start, cur))
            cur = []
    if cur:
        out.append((start, cur))
    return out


srcshingles = set()
for _ln in allsrc.splitlines():
    srcshingles |= shingles(_ln)

findings = 0
checked = 0
skipped = []
for name in generated:
    path = os.path.join(REFS, name)
    if not os.path.exists(path):
        continue                       # not generated on this machine yet
    if name in VERBATIM:
        skipped.append(name)
        continue
    checked += 1
    text = open(path, encoding='utf-8', errors='replace').read()
    for start, blk in blocks(text):
        body = ' '.join(blk)
        sh = shingles(body)
        if not sh or (sh & srcshingles):
            continue                   # the generator emits it - safe
        findings += 1
        print('%s:%d  HAND-WRITTEN, will be lost on the next generator run' % (name, start))
        print('    %s...' % norm(body)[:70])
        print('    -> move it to a published file (gameeffects.md / troubleshooting.md / the '
              'relevant topic reference)')

print()
print('checked %d generated catalog(s)%s' % (checked,
      (' (skipped %s - verbatim copies)' % ', '.join(skipped)) if skipped else ''))
if findings:
    print('FOUND %d hand-written block(s) in generated files.' % findings)
    sys.exit(1)
print('OK - no hand-written prose is sitting in a generated, gitignored catalog.')
