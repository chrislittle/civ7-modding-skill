# civ7-modding — a Claude Code skill

A [Claude Code](https://claude.com/claude-code) skill for building **Civilization VII** gameplay/database
mods — `.modinfo` manifests, GameEffects modifiers/requirements, projects, traditions, tech/civic-node-gated
bonuses — plus the hard-won "silent killer" rules (integer version, the attach-wrapper, MinDepth gating, etc.).
It triggers automatically when you're working on a Civ VII mod. See [SKILL.md](SKILL.md) for the full contents.

## Install

The skill is just a folder of files that lives in a Claude Code skills directory. The installer copies it
there for you:

```bash
# Global — available in Claude Code everywhere (recommended)
npx civ7-modding-skill --global

# Project — available only when working in the current folder
npx civ7-modding-skill --project
```

Install straight from GitHub without an npm publish:

```bash
npx github:chrislittle/civ7-modding-skill --global
```

Custom location:

```bash
npx civ7-modding-skill --dir /path/to/repo   # installs to /path/to/repo/.claude/skills
```

**Manual install:** copy this folder to `~/.claude/skills/civ7-modding` (global) or
`<project>/.claude/skills/civ7-modding` (project).

After installing, **restart Claude Code** (or reload) so it picks up the skill.

## Update

Re-run the same install command. The installer **wipes and re-copies** the skill folder (it `rm`s the
target first), so you always get a clean replacement — including any files dropped upstream:

```bash
# npm registry — add @latest to bypass npx's cache and fetch the newest published version
npx civ7-modding-skill@latest --global

# …or straight from GitHub (pulls the current main)
npx github:chrislittle/civ7-modding-skill --global
```

Use the same target you installed with (`--global`, `--project`, or `--dir <path>`), then **restart Claude
Code** so it reloads the skill.

## Global vs project

- **Global** (`~/.claude/skills/`) — the skill is available in every project on your machine. Best for a
  reusable tool like this.
- **Project** (`<project>/.claude/skills/`) — the skill travels with one repo and is shared with anyone who
  clones it. Use this if you want the skill versioned alongside a specific mod project.

## Generate the data references (first run)

Four references — `references/effects-collections-catalog.md`, `references/display-names.md`,
`references/progression-trees.md`, `references/constructibles-catalog.md` — are **not bundled** (they're bulk
extractions of the base game's own data/text, so they're never redistributed). Generate them from your own
installed copy of Civilization VII (one-time, and after each game patch):

```bash
python tools/gen-effects-catalog.py
python tools/gen-names-trees.py          # display-names.md + progression-trees.md
python tools/gen-constructibles-catalog.py
```

They auto-detect the install via `$CIV7_ROOT` → your Steam library folders (set `CIV7_ROOT` to override).
Output lands in `references/` (and is `.gitignore`d so you never commit Firaxis data). Everything else in
`references/` is authored and ships with the skill.

## License

MIT — see [LICENSE](LICENSE).
