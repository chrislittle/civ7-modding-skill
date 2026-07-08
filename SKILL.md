---
name: civ7-modding
description: >-
  Build, deploy, and debug Civilization VII gameplay/database mods (modinfo +
  GameEffects modifiers + projects + traditions) and UI mods (JS/HTML screens,
  panels, lenses, decorators, hotkeys, mod options). Use this skill whenever the
  user is working on a Civ VII / Civ 7 / Civilization VII mod — writing or fixing
  a .modinfo, defining Modifiers/Effects/Requirements, adding city or player
  bonuses, creating Projects, tradition unlocks, or tech/civic-node-gated bonuses,
  modding the game's UI (Controls.decorate, custom screens/panels, map lenses,
  UIScripts / ImportFiles), or troubleshooting a mod that
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

There is a second, separate modding domain: **UI mods** — JavaScript/HTML/CSS that
runs inside the game's embedded web UI (decorating or patching the game's own screen
components, adding lenses, panels, hotkeys, and mod options). No Modifiers involved;
different actions in the modinfo (`UIScripts`/`ImportFiles`), different failure modes.
See [references/ui-modding.md](references/ui-modding.md).

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
| [references/ui-modding.md](references/ui-modding.md) | **UI mods (JS/HTML/CSS)**: modinfo wiring (`UIScripts` vs `ImportFiles` file-shadowing, shell vs game scope, `UpdateText` accepts **.sql**, LoadOrder conventions, `fs://game/<mod-id>/` paths); the patch ladder (**`Controls.decorate`** → prototype monkey-patch → whole-file replacement); custom screens (`Panel` + `Controls.define` + `ContextManager`), sub-system-dock buttons; **lenses & lens layers** (LensManager, map sprites/VFX); interface modes + views; **hotkeys** (InputActions rows + HotkeyManager); **mod options + the ⚠ single-`modSettings`-localStorage-key rule**; per-game `Catalog` storage; the JS game API surface (+ community TypeScript stubs); cross-mod `globalThis` APIs; the **ui-next dual-stack** warning; FireTuner scripting-console debugging. Distilled from 18 shipping Workshop mods. |
| [references/finding-base-game-patterns.md](references/finding-base-game-patterns.md) | How to grep the base game for real EFFECT_*/REQUIREMENT_*/COLLECTION_* names and argument names. |
| [references/accomplishment-design.md](references/accomplishment-design.md) | **Designing earn-triggers (Triumphs / quest deeds / card unlocks) that reward SKILL, not next-turn mashing.** The 7 archetypes of a good accomplishment (spatial optimization · **adversity→asset** · placement context · deep investment · setup chain · timing window · sacrifice/tradeoff) with the Civ 6 Historic-Moment each echoes + the Civ 7 requirement tools; the anti-patterns (count-to-N, opaque-relative, happens-naturally, happiness-stage, map-luck); the **4 design tests** (planning / visibility / not-mindless / flexible); and the content-budget reality (a yield-lane has ~2–4 buildings, a tile holds 2 → **decouple trigger from the reward's lane**). Read before authoring any accomplishment/Triumph/quest content. |
| [references/civ6-civ7-mechanic-delta.md](references/civ6-civ7-mechanic-delta.md) | **Civ VI ↔ Civ VII mechanic delta = the feasibility gate.** Before porting a Civ-VI-inspired idea, check whether the mechanic even exists in Civ VII: Part A marks every major Civ VI subsystem ✅ present / 🔷 different-shape / ❌ absent (Great People/GPP, Great General, Governors, Amenities, Housing, Chop/Harvest, Tourism, World Congress, Loyalty, Envoys, Era Score…) with the grounded reason; Part B lists Civ VII-native systems with no Civ VI analog (the fresh design space); plus a worked Great-General-vs-Commander example. **Two caveats baked in: name-match ≠ mechanic-match (`EFFECT_DAE_*` = Influence diplomacy actions), and absent-keyword ≠ impossible (great people are a DATA TABLE, not an EFFECT_ — always check tables too).** Read before designing any card/bonus inspired by Civ VI. |
| `references/effects-collections-catalog.md` *(generate locally — see note below)* | **Authoritative master list** of every EFFECT_*/COLLECTION_*/REQUIREMENT_* + YieldType **actually used** by the installed game, with per-effect/requirement argument names + usage counts and player-rooted (★) collection flags. Generate via [tools/gen-effects-catalog.py](tools/gen-effects-catalog.py). Confirm a name/argument exists here before building, instead of guessing or trusting external/stale lists. |
| `references/cards-suzerain-governments-catalog.md` *(generate locally — see note below)* | **Every Tradition/Policy/Crisis card + Suzerain (city-state) bonus + government** shipped by base + all DLC, with resolved English effects, tagged by slot type / age / civ source (533 cards + 126 suzerain + 13 governments). Confirm what a base/DLC card already does, and keep a mod's new cards **new-&-unique** — don't duplicate/closely-mirror anything here. Generate via [tools/gen-cards-catalog.py](tools/gen-cards-catalog.py). |
| `references/civ6-policies-governments-catalog.md` *(generate locally — see note below)* | **INSPIRATION**: all Civ VI policy cards (by slot) + governments, base + Rise&Fall + Gathering Storm (136 policies + 13 governments). Mine for ideas, but run each through `civ6-civ7-mechanic-delta.md` first (many Civ VI systems don't exist in Civ VII). Generate via [tools/gen-civ6-cards-catalog.py](tools/gen-civ6-cards-catalog.py) (needs a Civ VI install; optional). |
| `references/display-names.md` *(generate locally — see note below)* | **Data-id → in-game English display name** (6k+ pairs): `BUILDING_TEMPLE`→"Temple", `PROJECT_TOWN_INN`→"Hub Town", `YIELD_DIPLOMACY`→"Influence", techs/civics/units/civs/leaders/traditions/resources. Use when the player/wiki name and the data id differ. Generate via [tools/gen-names-trees.py](tools/gen-names-trees.py). |
| `references/progression-trees.md` *(generate locally — see note below)* | **Per-age tech + civic tree structure**: every node with computed **column** (prereq depth = how early), **Cost**, display name, and a **★ mastery flag** (node has an `UnlockDepth="2"` unlock → a `MinDepth=2` gate fires; no ★ = `MinDepth=2` silently never fires). Use when choosing a gate node and to confirm it has a mastery. Generate via [tools/gen-names-trees.py](tools/gen-names-trees.py). |
| `references/constructibles-catalog.md` *(generate locally — see note below)* | **Every constructible** (building / wonder / improvement / …) with its **Class**, the **Age you can build it in**, the **Ageless** flag, Cost, defining module, and TypeTags. The age is **not guessable from the id** (`BUILDING_TEMPLE` = Exploration, `BUILDING_MONUMENT` = Antiquity) — grep this before asserting a constructible's age or its overbuild/age-transition behavior. Generate via [tools/gen-constructibles-catalog.py](tools/gen-constructibles-catalog.py). |
| [references/deploy-and-debug.md](references/deploy-and-debug.md) | Deploy/test loop, the three mod states, reading Modding.log/Database.log, inspecting Mods.sqlite with sqlite3. |
| [references/troubleshooting.md](references/troubleshooting.md) | Symptom → cause checklist. |
| [references/tile-ownership-and-radius.md](references/tile-ownership-and-radius.md) | The **3-hex work radius is engine-hardcoded** (no GlobalParameter, no `EFFECT_*` to widen it); the native cross-city **swap/reassign** picker IS real (wiki is wrong); the diplomacy land-claim system; and how Civ6's "Neighborhood Tall Extension" faked rings 4–5 in Lua + what a Civ7 port would need (`WorldBuilder.MapPlots.setOwnership`, `engine.on`, yield-injection unknowns). Read before any "expand the city radius" request. |
| [references/resources-and-ages.md](references/resources-and-ages.md) | **Resource classes & per-age validity**: the 5 resource tables; ⚠ **class is PER-AGE** (age modules patch it via `<Update>` — EX turns Horses/Gold/Silver/Furs/Cocoa/Spices/Sugar/Tea into unassignable TREASURE; MO adds FACTORY class); the "age journey" concept; suzerain-gift resources have no map-gen rows; `RESOURCE_*_DISTANT_LANDS` twins; expired-resource transition behavior UNVERIFIED. Read before granting/placing resources or reasoning about carryover. |
| [references/narrative-events.md](references/narrative-events.md) | **Narrative Events / Discovery stories** (data-only, official-doc-backed): full table anatomy (`NarrativeStories`, Links, Rewards, Overrides, Queues), Activation modes (`REQUISITE`/`AUTO`/`LINKED`/`UNLOCKED`), `ActivationRequirementSetId` = one-shot eligibility gate vs `RequirementSetId` = completion; **story plot = where the trigger happened** and `COLLECTION_NARRATIVE_STORY` + `EFFECT_PLOT_PLACE_RESOURCE` **works on UNOWNED plots** (13 base uses); the custom-discovery recipe (override `DISCOVERY_BASE`, queue = landmark×tier, sites spawn ≥3 tiles from starts); repeatability levers (`FirstOnly`, `AllowDuplicates`); the gossip appendix (`REQUIREMENT_PLAYER_HAS_AT_LEAST_NUM_GOSSIPS`, per-gossip locations, `AfterInit`). Read for goody-hut/pop-up events or seeding resources/units at map plots. |
| [references/yield-and-balance-design.md](references/yield-and-balance-design.md) | **Design LANGUAGE, not just mechanics** — read before authoring yield bonuses or any tall/wide/settlement balance: **use FLAT yields, never stacking `%` yield multipliers** (Firaxis's 1.2.5 purge — % ballooned late-Age yields; only ~17 % *yield* mods remain across all leaders/civs; `%` is for production/purchase **discounts**, NOT output; **don't port Civ 6 % scaling**); **age-scale via `ScaleByGameAge` "+N per Age"** (the dev idiom); **no cross-city dilution + cities don't share tiles** (N cities ≈ N× output, no automatic brake); the **flat anti-wide gradient** technique (per-band `Divisor`); the **settlement-cap system** (`EFFECT_PLAYER_ADJUST_SETTLEMENT_CAP` +/− works, `HAS_X_SETTLEMENTS` counts captured/towns, `OVER_SETTLEMENT_CAP`, under-cap dividend, capture ignores cap); and why **hemisphere/Distant-Lands gates break on Pangaea/Archipelago**. |
| [references/legacies-triumphs-dedications.md](references/legacies-triumphs-dedications.md) | **The "Your Empire's Legacy" screen = 3 data systems**: **Legacy Paths** (`<LegacyPaths>` — 4/Age victory + age-pacing engine; milestones advance the age timer → leave alone to stay pacing-neutral) · **Triumphs** (`<Legacies>`; `FirstPlayerOnly`="First to…", `MajorLegacy`=Major/Minor; reward=`EFFECT_PLAYER_GRANT_UNLOCK`; **absent from victories.xml = pacing-neutral**) · **Dedications** (`<AdvancedStartCards>`, Unlock-gated, **fixed cost-currency columns**: 4 domains+Wildcard+DarkAge, no Diplo/Expansion, can't add a column). Includes the add-a-Triumph **FK chain** (Types→**Unlocks**→UnlockRewards/UnlockRequirements, always-scoped; **`Legacy_LegacySets`→LEGACY_SET_DEFAULT REQUIRED to render**) and that a custom `KIND_CULTURE_SLOT` type is data-moddable but **won't render** (use `POLICY_CULTURE_SLOT`). Read before touching victory/legacy/triumph/dedication data or reasoning about age pacing. |
| [references/yield-preview-engine.md](references/yield-preview-engine.md) | **Predicting a constructible's yield at a plot BEFORE it's built** (planner/overlay mods — the hard core behind Map Tacks / City Planner). `total = base(`Constructible_YieldChanges`) + selfBonus(owned modifiers) + adjacency`. The **adjacency evaluator** (`Constructible_Adjacencies` + `Constructible_WildcardAdjacencies`, BUILDING-only wildcards; walk the 6 neighbors matching each `Adjacency_YieldChanges` `Adjacent*` predicate × `YieldChange`; `RequiresActivation` + flat-amount add-ons). The **plot-details model** (`GameplayMap.get*Type` + revealed-state + **merge in the player's planned tacks** as if built). And the clever bit — the **modifier engine**: reconstruct *"is modifier M active for the local player"* purely from data by resolving M→source (**trait**/`GameInfo.TraitModifiers`, **tradition**/`player.Culture.isTraditionActive`, **tree**/`Game.ProgressionTrees.getNodeState==FULLY_UNLOCKED`, **belief**/`player.Religion.getBeliefs`, **constructible**/`GameInfo.ConstructibleModifiers`) then hand-evaluating its Owner/Subject `RequirementSet`s in JS. ⚠ It's a re-implementation of engine logic → **strong estimate, not exact** (unhandled effects/requirements silently under-count; re-audit per patch); for *built* things use `player.Stats.getYields()` instead. Read for any "show predicted yields / adjacency planner" feature. |
| [references/game-systems-reference.md](references/game-systems-reference.md) | **How the game actually plays (runtime mechanics + magic numbers)** — the yardstick for balancing a mod against real systems. Settlement math (**base cap 3/8/16**; over-cap = −5 Happiness everywhere → −5%/point yields capped −80%; **growth cost `Food = x + yG + zG²`**, (5,20,4)/(30,50,5)/(60,60,6) by Age, only Rural+Specialists count toward G); **building adjacency yield-type map** (Culture/Happiness←Mountains+NW, Sci/Prod←Resources, Gold/Food←NavRiver/Lake/Coast; Wonders→all; Specialists +1 to every adjacency); **cost scaling** +10%/City empire-wide +5%/building (Prod & Warehouse exempt), Gold=3×Prod; combat (Tier=+5, resource +1 max 6, mastery +3, flanking, War Support/Weariness, siege/walls, nukes); diplomacy (relationship thresholds, befriend-IP points 30/60, **trade ranges 10/30·15/45·20/60** + network-connect rule); ages/**crises 70/80/90% Age Progress**; religion/ideology unlock chain (+ ideology policy-slot race). ⚠ Most values are **engine-side (not in moddable data → not grep-able)**, distilled from community Civilopedia mods — spot-check balance-critical numbers. |
| `references/civilopedia-concepts.md` *(generate locally — see note below)* | **The game's OWN Civilopedia mechanic prose** — the designers' verbatim explanation of how each system works, ordered by the Civilopedia's page structure: the **CONCEPTS** section (Ages, Attributes/skill trees, Army & Combat, Buildings/Quarters, Statehood, Settlements/Towns/Settlement-Limit, Diplomacy/Influence, **Happiness/Unhappiness** with the −5%/point capped −80% rule, Growth, Legends), the **AGES** section (age-transition + carry-over rules), and **VICTORIES** (exact Dominion/Tourism point tables + age-progress victory-threshold multipliers). Complements `game-systems-reference.md` (community-sourced) with the **authoritative first-party** wording, and complements the id/flavor generators (which give names, not mechanics). Read when you need to know how a system *actually behaves* or cite an exact number. Generate via [tools/gen-civilopedia-concepts.py](tools/gen-civilopedia-concepts.py). |
| `references/dev-kit-official-docs.md` *(generate locally — see note below)* | **Firaxis's OWN modding docs**, verbatim — the `Documentation/` folder that ships with the *Civilization VII Development Tools* SDK (Getting Started, Database Modding, The Modifier System, modinfo Files, Narrative Events). The authoritative first-party primer; this skill's authored references go **deeper** and **correct/extend** it with isolation-tested findings (integer-Version rule, attach-wrapper delivery, MinDepth silent-killer) — when they disagree, trust the tested references. Read for the official baseline or to cite Firaxis wording. Generate via [tools/gen-devkit-docs.py](tools/gen-devkit-docs.py). |
| [references/razing-and-conquest.md](references/razing-and-conquest.md) | **Razing / capture rewards / conquest hooks**: the base razing penalty model (−2/−4/−6 Influence post-burn + resets by Age, +War Support, Relationship hit — **Civ7 has NO surfaced Grievances**, that's Civ6); **`EFFECT_CITY_ADJUST_RAZE_RATE`** works on `COLLECTION_PLAYER_CITIES` (not just the Qajar unit-ability) but razing is **population-driven with steep diminishing returns** (no 1-turn floor); the **per-capture reward** pattern (`EFFECT_CITY_GRANT_YIELD` + `REQUIREMENT_PLAYER_FIRST_TIME_SETTLEMENT_OCCUPATION` + `BY_COMBAT`, `permanent`, Xerxes clone — fires per capture); **`isBeingRazed` is UI-only** (no requirement); the **don't-cancel-penalties-invisibly** UX lesson; and general requirement-logic gotchas (**flat blocks, no nested AND/OR**; Subject+Owner blocks AND together; `CountPerOwnSettlement`/`CountPerConqueredSettlement`; requirement-gated settlement-cap doesn't recompute). |

> **Generate the local data references first.** Eight references — `effects-collections-catalog.md`,
> `display-names.md`, `progression-trees.md`, `constructibles-catalog.md`, `cards-suzerain-governments-catalog.md`,
> `civ6-policies-governments-catalog.md`, `civilopedia-concepts.md`, and `dev-kit-official-docs.md` — are **not bundled**
> (they're bulk extractions of the games'/SDK's own data/text). Generate them from your installed copy (one-time, and after each patch/DLC):
> ```
> python tools/gen-effects-catalog.py
> python tools/gen-names-trees.py
> python tools/gen-constructibles-catalog.py
> python tools/gen-cards-catalog.py            # base+DLC cards / suzerain / governments
> python tools/gen-civilopedia-concepts.py     # the game's own Civilopedia mechanic prose
> python tools/gen-devkit-docs.py              # Firaxis's own SDK modding docs (needs the Dev Tools installed)
> python tools/gen-civ6-cards-catalog.py       # Civ VI inspiration (needs a Civ VI install; optional)
> ```
> The Civ VII generators auto-detect the install via `$CIV7_ROOT` → Steam libraries (override by setting `CIV7_ROOT`);
> the Civ VI one uses `$CIV6_ROOT`. Output lands in `references/`. The rest of the references — including the authored
> `civ6-civ7-mechanic-delta.md` (the feasibility gate) — ship with the skill.

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
