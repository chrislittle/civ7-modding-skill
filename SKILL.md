---
name: civ7-modding
description: >-
  Build, deploy, and debug Civilization VII gameplay/database mods (modinfo +
  GameEffects modifiers + projects + traditions). Use this skill whenever the
  user is working on a Civ VII / Civ 7 / Civilization VII mod — writing or fixing
  a .modinfo, defining Modifiers/Effects/Requirements, adding city or player
  bonuses, creating Projects, tradition unlocks, or tech/civic-node-gated bonuses, or
  troubleshooting a mod that
  "shows enabled but does nothing," crashes on map load, or never appears in-game.
  Also use when they mention Modding.log / Database.log, the Firaxis Games Mods
  folder, EFFECT_* / REQUIREMENT_* / COLLECTION_* names, the attach-modifiers
  pattern, or why a mod isn't in "Target Mods." Prefer this skill over generic XML
  help for anything Civ VII modding related, even if the user doesn't say "skill."
---

# Civilization VII Modding

Civ VII mods fail in **silent, non-obvious ways** — a mod can show "enabled" in the
Add-Ons menu, pass FK validation, and still apply nothing, with a clean log. This
skill encodes the rules that actually govern whether a mod loads and takes effect,
plus a deploy/debug workflow to prove it. The rules here were learned by isolation
testing, not from documentation — trust them over guesses.

## The six rules that cause "silent nothing"

Read these first. Each one produces a mod that looks fine but does nothing (or
crashes), with no obvious error. They are the failure modes you'll actually hit.

1. **Mod `Version` MUST be an integer.** `version="0.1"` (or `<Version>0.1</Version>`)
   makes the engine parse the version to 0/invalid and **silently drop the mod from
   "Target Mods"** — it is discovered, shows *enabled* in Add-Ons, but never applies.
   Use `version="1"`. This single rule has cost people multiple debugging sessions.

2. **Player/city bonuses must be delivered through an attach wrapper.** Binding a
   `COLLECTION_PLAYER_CITIES` (or any player/city) modifier *directly* in
   `<GameModifiers>` gives it no owner context, so it loads without error and never
   fires. Wrap it: a `COLLECTION_MAJOR_PLAYERS` + `EFFECT_ATTACH_MODIFIERS` modifier
   whose `ModifierId` argument lists the real modifiers, and bind only that wrapper.
   This is the base game's `MOD_CS_HILLFORT` pattern. See [references/gameeffects.md](references/gameeffects.md).

3. **A Project with no effect is hidden** from the city build list. Give it at least
   one `ProjectCompletionModifiers` row. Tech-unlocked **City** projects use
   `RequiresUnlock="false"` (the `ProgressionTreeNodeUnlocks` row is the gate); only
   Town warehouse projects use `"true"`. See [references/projects.md](references/projects.md).

4. **Never put player-settlement requirements in `OwnerRequirements` on a
   `COLLECTION_PLAYER_CONSTRUCTIBLES` modifier** — that's a hard crash at map load (a
   bare constructible has no settlement/owner context). Such requirements belong in
   `SubjectRequirements` on a city collection. See [references/troubleshooting.md](references/troubleshooting.md).

5. **"Enabled" ≠ "Applied."** A mod has three independent states: Discovered
   ("Loading Mod" in Modding.log) → Enabled (toggled in Add-Ons) → **Applied**. Only
   the last means your rows ran. Confirm it by finding the mod under **"Applied all
   components of enabled mods"** in Modding.log. FK "Passed Validation" is about the
   whole DB, not proof your rows loaded. See [references/deploy-and-debug.md](references/deploy-and-debug.md).

6. **`REQUIREMENT_PLAYER_HAS_COMPLETED_PROGRESSION_TREE_NODE` silently never fires
   without `<Argument name="MinDepth">1</Argument>`.** Gating a bonus on a researched
   tech/civic node and omitting `MinDepth` → the requirement never passes, with **no log
   error**; every gated bonus stays off forever. Every base-game use of this requirement
   includes `MinDepth`. It works in `OwnerRequirements`. This is the clean way to unlock
   bonuses with no Project/Tradition — see [references/projects.md](references/projects.md#gating-on-a-tech-node-without-a-project).

## What a Civ VII mod is

A mod is a folder containing a `.modinfo` file plus the data it loads:

- **`.modinfo`** (root `<Mod xmlns="ModInfo">`) — declares `<Properties>` (incl. the
  integer `<Version>`), `<Dependencies>`/`<References>`, `<ActionCriteria>` (when an
  action group applies — `<AlwaysMet/>` or `<AgeInUse>AGE_ANTIQUITY</AgeInUse>`), and
  `<ActionGroups scope="game">` whose `<Actions>` are `<UpdateDatabase>` (data XML/SQL)
  and `<UpdateText>` (localization). Full anatomy: [references/modinfo.md](references/modinfo.md).
- **Data XML** (root `<Database>`) — `Types`, `Traditions`, `TraditionModifiers`,
  `Projects`, `ProgressionTreeNodeUnlocks`, etc. These are table rows.
- **GameEffects XML** (root `<GameEffects xmlns="GameEffects">`) — the actual
  `<Modifier>` definitions (collection + effect + requirements + arguments) that
  change gameplay. Details: [references/gameeffects.md](references/gameeffects.md).

The mental model: **a gameplay change is a Modifier.** It acts on a `collection` of
objects, gated by `Requirements`. Two things to get right, separately: *delivery* (how
the modifier reaches a player — almost always the `COLLECTION_MAJOR_PLAYERS` +
`EFFECT_ATTACH_MODIFIERS` wrapper, bound via a Tradition's or always-on `GameModifiers`)
and *gating* (when it switches on — population/settlement requirements, plus an unlock
gate: a Tradition slot, a `REQUIREMENT_PLAYER_HAS_COMPLETED_PROJECT`, or — simplest, no
build/slot needed — `REQUIREMENT_PLAYER_HAS_COMPLETED_PROGRESSION_TREE_NODE` on a
researched tech/civic node).

## Authoring workflow

1. **Start from a real base-game example, never from guessed names.** Effect names,
   requirement names, and especially **argument names are not guessable**
   (`EFFECT_ADJUST_CITY_IGNORE_UNHAPPINESS_EFFECT` takes `UnhappinessEffect`, not
   `Amount`). Grep the base game for the real thing first — see
   [references/finding-base-game-patterns.md](references/finding-base-game-patterns.md).
   The templates in `assets/templates/` are copied from real base-game rows.

2. **Prove the plumbing before writing real content.** Deploy the litmus mod in
   `assets/litmus-mod/` (a one-line `UpdateDatabase` with an obvious in-game effect
   and an integer version). If *it* doesn't apply, the problem is loading/deployment,
   not your modifiers — fix that first. See [references/deploy-and-debug.md](references/deploy-and-debug.md).

3. **Write the data + effects**, validating XML well-formedness as you go:
   `powershell scripts/validate-xml.ps1 <mod-folder>` (or `[xml](Get-Content file)`).
   Order `<Item>`s so tables are registered before they're referenced (projects
   before the modifiers/traditions that name them).

4. **Deploy:** `powershell scripts/deploy-mod.ps1 <dev-folder>` copies the mod into
   `%LOCALAPPDATA%\Firaxis Games\Sid Meier's Civilization VII\Mods`. Local mods apply
   fine — no Steam Workshop needed. Re-copying over a deployed mod is harmless.

5. **Test:** enable in the in-game **Add-Ons** menu, then **start a NEW game** (most
   gameplay actions only bind at game start).

6. **Verify it applied:** `powershell scripts/check-applied.ps1 <mod-id>` reports
   Discovered / Enabled / Applied by reading Modding.log. If it didn't apply, go to
   [references/troubleshooting.md](references/troubleshooting.md).

## When something is wrong

Go straight to [references/troubleshooting.md](references/troubleshooting.md) — it maps each symptom
("mod doesn't appear in Add-Ons" / "appears but no effect" / "crash on load" / "rows
seem missing") to the documented cause and fix. Don't theorize; match the symptom.

## Reference map

| File | When to read it |
|------|-----------------|
| [references/modinfo.md](references/modinfo.md) | Writing/fixing the `.modinfo`: Properties, the integer-Version rule, Dependencies vs References, ActionCriteria, ActionGroups scope, UpdateDatabase/UpdateText. |
| [references/gameeffects.md](references/gameeffects.md) | Defining Modifiers, the attach-wrapper pattern, collections, requirements, how a Modifier reaches a player; **per-hemisphere scoping** (Homeland vs Distant Lands, the `OnlyDistantlands` spelling gotcha); resource-cap / trade-capacity effects and why GDP ≠ gold. |
| [references/projects.md](references/projects.md) | City/Town Projects, RequiresUnlock, ProgressionTreeNodeUnlocks gating, ProjectCompletionModifiers; gating bonuses on a tech node with **no** project; adding a display-only "unlocked" note to a tech panel. |
| [references/constructibles.md](references/constructibles.md) | Buildings/wonders as Constructibles + TypeTags: the **AGELESS** tag (= never obsolete; NOT overbuild-immunity — only the **WONDER class** can't be overbuilt), the **Age-transition lifecycle** (buildable only in its Age; obsolete+overbuildable after), **overbuilding**, **defining a NEW building** (the 4-table minimum), the pop-out rendering **`Tooltip` not `Description`**, **no player-state buildability gate**, and **icons** (`UpdateIcons`/`IconDefinitions`, reuse a `blp:`). |
| [references/city-states-suzerain.md](references/city-states-suzerain.md) | City-state suzerain bonuses: the draft-from-a-pool mechanic, **`Shareable`** (repeatable) vs exclusive options, the `CITY_STATE_<TYPE>_BONUS_<AGE>_7` shareable id, the suzerain effects table, `REQUIREMENT_PLAYER_ELIGIBLE_CS_BONUS` (boolean) gating, **Influence = `YIELD_DIPLOMACY` (player-level, never per-pop/per-city)** + the proven ways to grant it, why flat per-CS yields fail for tall (use per-pop), and overriding the draft-menu description text. |
| [references/town-specialization-rollin.md](references/town-specialization-rollin.md) | Internalizing base **Town specialization** focuses into a one-city/tall player (DISTINCT from the suzerain layer): the two delivery patterns, data-id vs in-game focus-name table (e.g. `PROJECT_TOWN_INN` = "Hub Town"), the roll-in pattern, and **the overlap rule** — don't re-emit a bucket whose yield/mechanic the fan-out kit already covers; roll in for a *distinct mechanic* only. |
| [references/custom-units.md](references/custom-units.md) | **Custom units**: buildable-unit minimum tables + no player-state buildability gate; porting a Modern-only ability chain (CLAIM_RESOURCE) into AQ/EX; **charges & self-consumption is hardwired** (no generic "consume after use"); **granting traps** (tech-locked units can't be granted; `run-once` fires at attach time — use a count-gated continuous grant); **icons need TWO rows** (flag + `FONTICON`) loaded in **game+shell `always`** groups (per-Age groups don't register → black icon); **`VisualRemaps` = its own `UpdateVisualRemaps` action** (not UpdateDatabase → crash), `From`=donor `To`=your unit; **the selected-unit portrait is a live 3D render** so a modelless custom unit shows BLACK there regardless; per-resource yield effects; tall-gating a charge; **no AI advisories = AI ignores the unit**. |
| [references/finding-base-game-patterns.md](references/finding-base-game-patterns.md) | How to grep the base game for real EFFECT_*/REQUIREMENT_*/COLLECTION_* names and argument names. |
| `references/effects-collections-catalog.md` *(generate locally — see note below)* | **Authoritative master list** of every EFFECT_*/COLLECTION_*/REQUIREMENT_* + YieldType **actually used** by the installed game, with per-effect/requirement argument names + usage counts and player-rooted (★) collection flags. Generate via [tools/gen-effects-catalog.py](tools/gen-effects-catalog.py). Confirm a name/argument exists here before building, instead of guessing or trusting external/stale lists. |
| `references/display-names.md` *(generate locally — see note below)* | **Data-id → in-game English display name** (6k+ pairs): `BUILDING_TEMPLE`→"Temple", `PROJECT_TOWN_INN`→"Hub Town", `YIELD_DIPLOMACY`→"Influence", techs/civics/units/civs/leaders/traditions/resources. Use when the player/wiki name and the data id differ. Generate via [tools/gen-names-trees.py](tools/gen-names-trees.py). |
| `references/progression-trees.md` *(generate locally — see note below)* | **Per-age tech + civic tree structure**: every node with computed **column** (prereq depth = how early), **Cost**, display name, and a **★ mastery flag** (node has an `UnlockDepth="2"` unlock → a `MinDepth=2` gate fires; no ★ = `MinDepth=2` silently never fires). Use when choosing a gate node and to confirm it has a mastery. Generate via [tools/gen-names-trees.py](tools/gen-names-trees.py). |
| `references/constructibles-catalog.md` *(generate locally — see note below)* | **Every constructible** (building / wonder / improvement / …) with its **Class**, the **Age you can build it in**, the **Ageless** flag, Cost, defining module, and TypeTags. The age is **not guessable from the id** (`BUILDING_TEMPLE` = Exploration, `BUILDING_MONUMENT` = Antiquity) — grep this before asserting a constructible's age or its overbuild/age-transition behavior. Generate via [tools/gen-constructibles-catalog.py](tools/gen-constructibles-catalog.py). |
| [references/deploy-and-debug.md](references/deploy-and-debug.md) | Deploy/test loop, the three mod states, reading Modding.log/Database.log, inspecting Mods.sqlite with sqlite3. |
| [references/troubleshooting.md](references/troubleshooting.md) | Symptom → cause checklist. |
| [references/tile-ownership-and-radius.md](references/tile-ownership-and-radius.md) | The **3-hex work radius is engine-hardcoded** (no GlobalParameter, no `EFFECT_*` to widen it); the native cross-city **swap/reassign** picker IS real (wiki is wrong); the diplomacy land-claim system; and how Civ6's "Neighborhood Tall Extension" faked rings 4–5 in Lua + what a Civ7 port would need (`WorldBuilder.MapPlots.setOwnership`, `engine.on`, yield-injection unknowns). Read before any "expand the city radius" request. |

> **Generate the local data references first.** Four references — `effects-collections-catalog.md`,
> `display-names.md`, `progression-trees.md`, `constructibles-catalog.md` — are **not bundled** (they're bulk
> extractions of the base game's own data/text). Generate them from your installed copy of the game (one-time,
> and after each patch):
> ```
> python tools/gen-effects-catalog.py
> python tools/gen-names-trees.py
> python tools/gen-constructibles-catalog.py
> ```
> They auto-detect the install via `$CIV7_ROOT` → Steam libraries (override by setting `CIV7_ROOT`). Output lands
> in `references/`. The rest of the references are authored and ship with the skill.

## Scripts (PowerShell, Windows)

| Script | Purpose |
|--------|---------|
| `scripts/deploy-mod.ps1 <dev-folder> [-ModsDir <path>]` | Remove the deployed copy and re-copy dev → the Firaxis Mods folder. |
| `scripts/check-applied.ps1 <mod-id>` | Report Discovered/Enabled/Applied for a mod from Modding.log + Mods.sqlite. |
| `scripts/inspect-registry.ps1 [<mod-id>]` | Copy the locked Mods.sqlite and query Mods/ModProperties (Version, Disabled). |
| `scripts/validate-xml.ps1 <mod-folder>` | Check XML well-formedness of every .xml/.modinfo in a mod. |

All scripts auto-detect the standard `%LOCALAPPDATA%\Firaxis Games\Sid Meier's
Civilization VII` location and print what they're doing. Read a script's header
comment before running if the layout is non-standard.
