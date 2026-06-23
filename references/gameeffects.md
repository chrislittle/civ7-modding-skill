# GameEffects: Modifiers, the attach-wrapper, collections & requirements

**A gameplay change is a Modifier.** Everything else (Traditions, Projects, tech
nodes) is just plumbing that decides *when* a Modifier reaches a player. Get the
Modifier and its delivery right and the bonus fires; get the delivery wrong and it
loads cleanly and does nothing.

## Contents
- [Anatomy of a Modifier](#anatomy-of-a-modifier)
- [Collections — whose objects the effect acts on](#collections)
- [Requirements — gating per object](#requirements)
- [Scoping by hemisphere (Homeland vs Distant Lands)](#scoping-by-hemisphere-homeland-vs-distant-lands)
- [THE attach-wrapper rule (player/city bonuses)](#the-attach-wrapper-rule)
- [Binding a Modifier to a player](#binding-a-modifier-to-a-player)

## Anatomy of a Modifier

GameEffects files use the root `<GameEffects xmlns="GameEffects">`. A Modifier names
an **effect** (what happens), a **collection** (which objects it happens to), optional
**requirements** (which of those objects qualify), and **arguments** (the effect's
parameters):

```xml
<?xml version="1.0" encoding="utf-8"?>
<GameEffects xmlns="GameEffects">
    <Modifier id="ATTACH_CULTURE_ON_CULTURE_BUILDINGS"
              collection="COLLECTION_PLAYER_CITIES"
              effect="EFFECT_CITY_ADJUST_CONSTRUCTIBLE_YIELD">
        <SubjectRequirements>
            <Requirement type="REQUIREMENT_PLAYER_ELIGIBLE_CS_BONUS">
                <Argument name="CityStateBonus">CITY_STATE_BONUS_ANTIQUITY_7</Argument>
            </Requirement>
        </SubjectRequirements>
        <Argument name="Tag">CULTURE</Argument>
        <Argument name="YieldType">YIELD_CULTURE</Argument>
        <Argument name="Amount">2</Argument>
    </Modifier>
</GameEffects>
```

(Verbatim from base `age-antiquity/data/independents-gameeffects.xml`.)

- **`effect`** and the **`<Argument name="...">`** it expects are **not guessable** —
  e.g. `EFFECT_ADJUST_CITY_IGNORE_UNHAPPINESS_EFFECT` takes `UnhappinessEffect`, not
  `Amount`. Always copy the effect + its exact argument names from a real base-game
  usage. See [finding-base-game-patterns.md](finding-base-game-patterns.md).
- **`<SubjectRequirements>`** gate the *subject* objects (the things in the
  collection). **`<OwnerRequirements>`** gate the *owner* (usually the player).
- Argument values can be **comma-separated lists** where the engine expects multiple
  (e.g. `YieldType="YIELD_FOOD, YIELD_HAPPINESS"`, or a multi-id `ModifierId`). This
  is a valid base-game pattern, not a hack.

## Collections

The `collection` decides what the effect iterates over. Common ones:

| Collection | Acts on |
|------------|---------|
| `COLLECTION_PLAYER_CITIES` | every city the owning player has |
| `COLLECTION_PLAYER_CAPITAL_CITY` | just the capital |
| `COLLECTION_ALL_CITIES` | every city in the game |
| `COLLECTION_OWNER` | the owner itself (e.g. the player) |
| `COLLECTION_MAJOR_PLAYERS` | every major (non city-state) player — used by the wrapper |
| `COLLECTION_PLAYER_CONSTRUCTIBLES` | the player's constructibles (buildings/improvements) |
| `COLLECTION_PLAYER_DISTRICTS` | the player's districts (e.g. `EFFECT_DISTRICT_ADJUST_TOTAL_HEALTH`) |
| `COLLECTION_PLAYER_UNITS` | the player's units (e.g. `EFFECT_UNIT_ADJUST_HEAL_PER_TURN`) |
| `COLLECTION_PLAYER_COMBAT` | the player's units in combat (e.g. `EFFECT_ADJUST_UNIT_STRENGTH_MODIFIER`) |
| `COLLECTION_PLAYER_PLOT_YIELDS` | the player's worked plots (e.g. `EFFECT_PLOT_ADJUST_YIELD`) |

The catch: a collection needs an **owner context** to resolve. A modifier bound at the
*game* level has no "the player," so a `COLLECTION_PLAYER_*` modifier bound there has
nothing to iterate — see the attach-wrapper rule below.

> **Picking the right collection for attach-wrapper delivery.** We deliver every bonus by attaching it
> to the **player** (the `COLLECTION_MAJOR_PLAYERS` wrapper), so each modifier must use the **player-rooted**
> collection for what it touches — NOT the city/unit/plot-context variant the base game uses when it attaches
> from a *city/unit* (e.g. a town project or a unit ability). Using the context-bound variant silently no-ops
> (no unit/city/plot to resolve against). Confirmed working through the wrapper: districts → `COLLECTION_PLAYER_
> DISTRICTS`, units → `COLLECTION_PLAYER_UNITS`, combat strength → `COLLECTION_PLAYER_COMBAT` (NOT
> `COLLECTION_UNIT_COMBAT`), plot yields → `COLLECTION_PLAYER_PLOT_YIELDS` (NOT `COLLECTION_CITY_PLOT_YIELDS`),
> warehouse yields → `COLLECTION_PLAYER_CITIES` + `EFFECT_CITY_GRANT_WAREHOUSE_YIELD`, per-building yields →
> `COLLECTION_OWNER` + `EFFECT_PLAYER_ADJUST_CONSTRUCTIBLE_YIELD` (arg `ConstructibleClass=BUILDING/WONDER` or a
> `ConstructibleType`). When in doubt, grep the base game for the effect and prefer the `COLLECTION_PLAYER_*`/
> `COLLECTION_OWNER` usage (often a tradition/trait) over a project/ability usage.

## Requirements

Requirements filter the collection per object. Like effects, **requirement types and
their argument names are not guessable** — grep a real usage. Useful ones:

- `REQUIREMENT_CITY_POPULATION` — args `MinUrbanPopulation` / `MinTotalPopulation`.
- `REQUIREMENT_CITY_IS_CITY` / `REQUIREMENT_CITY_IS_TOWN` — settlement type.
- `REQUIREMENT_PLAYER_HAS_X_SETTLEMENTS` — settlement count (often used *inverted* with
  a `RequiredCount` as an "anti-wide" guard). **See the crash warning below.**
- `REQUIREMENT_PLAYER_HAS_COMPLETED_PROJECT` — gate a bonus on a project being built.
- `REQUIREMENT_PLAYER_HAS_COMPLETED_PROGRESSION_TREE_NODE` — gate a bonus on a researched
  tech/civic node (the no-project way to unlock bonuses). Args `ProgressionTreeNodeType`
  **+ `MinDepth` (REQUIRED, set to `1`)**. **Omit `MinDepth` and it silently never fires**
  — no log error, the bonus stays off forever. Every base-game use includes it. Works in
  `OwnerRequirements`. See [projects.md](projects.md#gating-on-a-tech-node-without-a-project).
  **`MinDepth=2` = gate on the node's MASTERY** (its depth-2 unlock) — useful to split a node's
  first-tier bonus from a deeper "mastery reward." But **`MinDepth=2` only ever fires on a node that
  actually HAS a mastery** — gate it on a node with no depth-2 and it silently never fires (same trap).
  Verify first: grep the age's `progression-trees-*.xml` for an `UnlockDepth="2"` row on that node.
  (Base uses `MinDepth=2` itself, so it's proven; just confirm the target node has the mastery.)

> **Crash warning:** Do **not** place a player-settlement requirement
> (`REQUIREMENT_PLAYER_HAS_X_SETTLEMENTS`) in **`OwnerRequirements`** on a
> **`COLLECTION_PLAYER_CONSTRUCTIBLES`** modifier — a bare constructible has no
> settlement/owner context and the game **hard-crashes at map load**. Put settlement
> gates in `SubjectRequirements` on a *city* collection instead.

## Scoping by hemisphere (Homeland vs Distant Lands)

Civ VII's gameplay geography is a **binary: Homeland vs Distant Lands** (the two
hemispheres), not an arbitrary continent count. To scope a bonus — or an anti-wide count —
to one hemisphere:

- **`REQUIREMENT_CITY_IS_DISTANT_LANDS`** — a *city* `SubjectRequirement`; `inverse="true"`
  = the homeland. Canonical template: the **Spain trait** (`age-exploration/data/
  civilizations-shared-gameeffects.xml`) gives homeland cities one amount and distant-lands
  cities another, scoped only by this requirement and its inverse.
- **`REQUIREMENT_PLAYER_HAS_X_SETTLEMENTS` takes a hemisphere filter argument** —
  **`OnlyHomelands`** or **`OnlyDistantlands`** (true/false) — so you can count settlements
  *per hemisphere* (the per-hemisphere form of the anti-wide guard). Base proof: the EX
  Expansionist legacy.
  - ⚠️ **Silent-killer spelling: it is `OnlyDistantlands` — lowercase "l" in "lands".** The
    natural-looking `OnlyDistantLands` parses without error and **silently never fires** (same
    failure class as the `MinDepth` gotcha). `OnlyHomelands` is camelCased as expected.
- **`REQUIREMENT_PLAYER_HAS_X_SETTLEMENTS_FOREIGN_HEMISPHERE`** also exists (args `Count`,
  `OnlyConquered`) but is less flexible (no `OnlyCities`/exact-count) — prefer the
  `OnlyDistantlands` arg on the normal requirement.
- **No per-CONTINENT gameplay scoping.** `ContinentType` is real but **map-gen only**
  (`base-standard/data/maps.xml`); no gameplay requirement counts settlements by continent.
  "One city per continent" (N > 2) is **not data-moddable** — it needs Lua. "Per hemisphere"
  (the binary) is fully data-moddable with the above.

**Exact-count bands — prefer threshold + inverse-threshold over `RequiresExactCount` when a
filter is involved.** To express "exactly N settlements in this hemisphere" (e.g. a geometric
100/50/25 anti-wide curve), use a *pair* of requirements: a normal `RequiredCount=N` plus an
`inverse="true"` `RequiredCount=N+1` (= "≥ N AND NOT ≥ N+1"). The base game only proves the
hemisphere filters with a plain threshold, so combining `RequiresExactCount` *with*
`OnlyHomelands`/`OnlyDistantlands` is unproven and risks silently never firing — the
threshold-pair idiom uses only proven primitives.

## A few effects & mechanics worth knowing

Still copy the exact names/args from the base game — but these come up constantly for
tall/yield mods and have non-obvious quirks:

- **`EFFECT_CITY_ADJUST_ADJACENCY_FLAT_AMOUNT`** — boost ONE named adjacency rule. Args
  `Adjacency_YieldChange` (the rule id, e.g. `QuarterScience`, `WonderCulture`,
  `MountainCulture`, `ResourceScience`, `NaturalWonderCulture`) + `Amount` + `Divisor`.
  **Fractional adjacency works**: `Amount=1` / `Divisor=2` = +0.5 per adjacent source,
  confirmed in-game (not floored to 0). There is **no** blanket "+X% all adjacency"
  effect — enumerate the rules you want.
- **`EFFECT_CITY_ADJUST_CONSTRUCTIBLE_YIELD`** — flat yield to all buildings of a domain
  or a specific type. Args `YieldType` + `Tag` (`SCIENCE`/`CULTURE`/`GOLD`/…) **or**
  `ConstructibleType`. This is the **only** way to target yields by building domain
  (base proof: `ATTACH_CULTURE_ON_CULTURE_BUILDINGS`).
- **`EFFECT_CITY_ADJUST_WORKER_CAP`** — raise the per-district specialist cap. Arg
  `Amount` only — it's **always city-wide and cannot be scoped to a building or class**
  (the cap is one shared pool). Don't try to make a domain-specific specialist cap; it
  doesn't exist.
- **`EFFECT_CITY_ADJUST_RESOURCE_CAP`** — raise a settlement's resource-slot capacity (more
  assignable resources). Arg `Amount` only. Used on `COLLECTION_PLAYER_CITIES` (with
  `REQUIREMENT_CITY_IS_CITY`), capital, or owner (base proof: Qing capital +2, Monopolies +1).
- **`EFFECT_PLAYER_ADJUST_TRADE_CAPACITY`** — add player trade-route capacity. Args `Amount`
  + `MajorsOnly` (bool); `COLLECTION_OWNER`, works any Age. Like any player-level effect it
  **delivers through the standard attach wrapper** (below) — confirmed firing that way.

> **"GDP" (the Economic Victory metric) ≠ gold income.** It accrues per turn from *tracked*
> sources — chiefly **resources assigned to cities** (+1 each) and **imported** resources
> (+1 each), plus a flat amount for *having* gold buildings — **not** your treasury gold. So
> to move economic victory, grant **resource capacity + trade routes** (so the player can
> assign/import more resources), not raw gold or gold-adjacency.
> `EFFECT_PLAYER_ACTIVATE_VICTORY_POINT_TRACKER` only **activates a named tracker** (arg
> `TrackerName`, `run-once`/`permanent`) — it does **not** grant flat points per turn, so it
> is *not* a clean "give +N GDP" lever (would need a custom tracker definition).

> **Specialist model (patch 1.4.0 — affects design, not syntax):** a Specialist has **no
> base yield**; it grants **100% of its tile's adjacency** and nothing else, while costing
> **2 / 4 / 6 Food *and* Happiness per Age** (1/1 for obsolete buildings). So a Specialist
> on a low-adjacency tile is a *net loss*. The way to make specialist slots worth filling
> is to **boost adjacency** (above) — every point is doubled by the Specialist on the tile.
> `EFFECT_CITY_ADJUST_WORKER_YIELD` (a flat per-specialist yield, e.g. Abbasid Ulema) is
> therefore **off-design** under 1.4.0 — it re-introduces the base yield the devs removed.
>
> Baseline cap, for gating math: in **Antiquity the base specialist cap is 0**, and
> researching **Currency** (`NODE_TECH_AQ_CURRENCY`, base game's `MOD_AQ_SPECIALIST_CAP_INCREASE`)
> grants the first +1 — so Currency is effectively "specialists unlocked." The global
> `CITY_WORKER_STARTING_CAP` is overridden only for Exploration (1) and Modern (3); Antiquity
> uses the 0 default. So your `EFFECT_CITY_ADJUST_WORKER_CAP` bonuses stack *on top of* those.

> **No Great People in Civ VII.** There is **no** Great People / Great Person Points (GPP)
> system. When porting ideas from Civ VI (e.g. *Wide & Tall*), drop anything GPP-based —
> there is no `EFFECT_*GREAT_PERSON*` equivalent. Verify a mechanic exists in VII before
> designing around it.

## THE attach-wrapper rule

This is the second-biggest silent killer (after the integer version).

**You cannot deliver a player/city bonus by binding a `COLLECTION_PLAYER_CITIES`
(etc.) modifier directly in `<GameModifiers>`.** Game-level binding has no owner
context, so the modifier loads with no error and **never attaches to anyone**. (Proven
by an ungated +50-gold probe that produced nothing when bound directly.)

The base game *always* delivers player bonuses through a two-step **attach wrapper**,
exemplified by `MOD_CS_HILLFORT`:

```xml
<!-- Step 1: the wrapper. Bound at game level; COLLECTION_MAJOR_PLAYERS DOES resolve
     (every major player), and EFFECT_ATTACH_MODIFIERS hands each player the real
     modifiers listed in ModifierId. -->
<Modifier id="MOD_CS_HILLFORT"
          collection="COLLECTION_MAJOR_PLAYERS"
          effect="EFFECT_ATTACH_MODIFIERS">
    <Argument name="ModifierId">ATTACH_HILLFORT</Argument>
</Modifier>

<!-- Step 2: the real bonus. Now it has a player owner, so its own collection
     (COLLECTION_OWNER / COLLECTION_PLAYER_CITIES / ...) resolves correctly and its
     SubjectRequirements gate per object. -->
<Modifier id="ATTACH_HILLFORT"
          collection="COLLECTION_OWNER"
          effect="EFFECT_PLAYER_GRANT_CONSTRUCTIBLE_UNLOCK">
    <SubjectRequirements>
        <Requirement type="REQUIREMENT_PLAYER_ELIGIBLE_CS_BONUS">
            <Argument name="CityStateBonus">CITY_STATE_BONUS_ANTIQUITY_1</Argument>
        </Requirement>
    </SubjectRequirements>
    <Argument name="ConstructibleType">IMPROVEMENT_HILLFORT</Argument>
</Modifier>
```

To deliver many bonuses, list them comma-separated in one wrapper:

```xml
<Modifier id="MY_ATTACH_ALL" collection="COLLECTION_MAJOR_PLAYERS"
          effect="EFFECT_ATTACH_MODIFIERS">
    <Argument name="ModifierId">MY_BONUS_1, MY_BONUS_2, MY_BONUS_3</Argument>
</Modifier>
```

Then **bind only the wrapper** (`MY_ATTACH_ALL`). Each attached modifier resolves its
own collection against each player and self-gates with its own requirements (project
completed, population tier, etc.). The Tall Metropolis mod uses exactly this: one
`TM_<age>_ATTACH_ALL` wrapper listing ~13 bonus modifiers per Age, bound alone.

## Binding a Modifier to a player

Keep two ideas separate: **delivery** (the wrapper, which gives the modifier a player
owner) and the **unlock gate** (when it's allowed to switch on). Player/city bonuses
should *always* be delivered through the wrapper; you then choose how they unlock:

1. **Tech/civic-node gate (simplest — no project, no slotting).** Bind the wrapper
   always-on via `<GameModifiers>` and put a
   `REQUIREMENT_PLAYER_HAS_COMPLETED_PROGRESSION_TREE_NODE` (`MinDepth=1`!) in each
   bonus's `OwnerRequirements`. The bonus turns on automatically when the node is
   researched. This is the Tall Metropolis approach. See
   [projects.md](projects.md#gating-on-a-tech-node-without-a-project).

2. **Tradition** — a data-XML `<Traditions>` row, linked to a Modifier via
   `<TraditionModifiers>`, offered by a civic node via `<ProgressionTreeNodeUnlocks>`.
   The tradition's `<GameModifiers>` should bind the **wrapper**, not the raw
   player/city modifier. (Lapses when un-slotted — useful, or a pitfall, at Age boundaries.)

3. **Project completion** — a Project's `<ProjectCompletionModifiers>` row fires a
   Modifier when the project finishes; gate ongoing bonuses on
   `REQUIREMENT_PLAYER_HAS_COMPLETED_PROJECT`. See [projects.md](projects.md). Again, for
   player/city scope, fire a wrapper.

Whichever you pick: keep always-on safety nets (happiness/upkeep cushions) **ungated** so
they survive Age-transition windows when the gate is briefly unmet.

Rule of thumb: if a modifier's `collection` starts with `COLLECTION_PLAYER_` or
`COLLECTION_OWNER` and you're about to bind it directly at game level, stop — wrap it.
