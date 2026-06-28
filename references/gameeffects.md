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
- **`EFFECT_PLAYER_REPLACE_CONSTRUCTIBLE`** — the **only** effect that puts a constructible on an
  **already-occupied** tile (Destroy one, Create another in place — and **Create can be a WONDER**, the
  only way to place a wonder without an empty tile). Args **`Destroy`** + **`Create`** only (no tile/city/
  count arg); `COLLECTION_OWNER`, `permanent run-once`. ⚠ **It converts ALL the player's instances of the
  `Destroy` type at once** (confirmed in-game: 2 of building X → 2 wonders) — so only ever name a type the
  player has exactly one of. Base use = Golden-Age building upgrades (`BUILDING_ACADEMY`→`_EX`). See the
  victory-wonder recycle pattern below.

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

### Victory-wonder recycle: place a WONDER on an occupied tile (the "Foundations" pattern)

Problem: wonders need an **empty** tile (constructibles.md), so a packed tall city can be unable to build a
Modern **victory** wonder (`WONDER_WORLDS_FAIR`, `WONDER_MANHATTAN_PROJECT`). `EFFECT_PLAYER_REPLACE_CONSTRUCTIBLE`
is the fix, and the clean delivery is a **1-step self-converting building** (proven in-game 2026-06-28):

1. Define a normal **"Foundations" BUILDING** (constructibles.md table set) — a building can overbuild an
   **obsolete** district, which is the tile relief (normal play can't overbuild ageless buildings or place a
   wonder on an occupied tile; the REPLACE below is the bypass). Gate its appearance on the **wonder's own
   unlock node** via `ProgressionTreeNodeUnlocks`
   (`KIND_CONSTRUCTIBLE`) so it only appears once you've earned the wonder normally — never a victory shortcut.
2. Bind a convert modifier to that building via **`<ConstructibleModifiers>`** (the same hook the base game uses to
   hang on-completion effects off a constructible, e.g. `MOD_MANHATTAN_PROJECT_GRANT_NUCLEAR_DEVICE`). On completion
   it REPLACEs the building → the wonder, on that tile, with the full wonder cinematic:

```xml
<!-- GameEffects (e.g. modifiers.xml). NOT added to the attach wrapper - it's bound to the building, not the player. -->
<Modifier id="MA_RECLAIM_WORLDS_FAIR" collection="COLLECTION_OWNER" effect="EFFECT_PLAYER_REPLACE_CONSTRUCTIBLE" permanent="true" run-once="true">
  <SubjectRequirements>
    <Requirement type="REQUIREMENT_PLAYER_HAS_CONSTRUCTIBLE" inverse="true"><Argument name="ConstructibleType">WONDER_WORLDS_FAIR</Argument></Requirement>
    <!-- + your tall gate (REQUIREMENT_PLAYER_HAS_X_SETTLEMENTS inverse) -->
  </SubjectRequirements>
  <Argument name="Destroy">BUILDING_MA_WORLDS_FAIR_SITE</Argument>
  <Argument name="Create">WONDER_WORLDS_FAIR</Argument>
</Modifier>
```
```xml
<!-- Data (Database). Loads AFTER the GameEffects file in the action group so the FK resolves. -->
<ConstructibleModifiers><Row ConstructibleType="BUILDING_MA_WORLDS_FAIR_SITE" ModifierId="MA_RECLAIM_WORLDS_FAIR"/></ConstructibleModifiers>
```

Key points / gotchas:
- **Fire REPLACE from a building's `ConstructibleModifiers` (on completion) or from `ProjectCompletionModifiers`
  — NOT from the game-start attach wrapper** (firing REPLACE at game start is a native crash; the base game only
  fires REPLACE at Age transitions, when the constructibles already exist).
- The **`Destroy` building must be unique** (you build exactly one) since REPLACE hits all instances of the type.
  A capped/deliberate Foundations building you only build when needed satisfies this; the `inverse
  REQUIREMENT_PLAYER_HAS_CONSTRUCTIBLE(the wonder)` guard prevents ever creating a second.
- **Victory credit works:** the win checks owning the wonder (or completing a project whose `PrereqConstructible`
  is the wonder, e.g. `PROJECT_OPERATION_IVY` for Military) — the engine can't tell a REPLACE-placed wonder from a
  normally-built one. Confirmed in-game (Operation Ivy unlocked after a REPLACE-placed Manhattan Project).
- Give the Foundations building the **wonder's own icon** (constructibles.md → Icons) and put its how-it-works text
  in the building's **`Tooltip`** (the pop-out renders Tooltip, not Description).

### Appeal (tile desirability) — thresholds, requirements & effects

Appeal is an **accumulated** plot score (NOT a static per-tile value): each **adjacent
item of natural beauty** — forest, savannah woodland, sagebrush steppe, mangrove swamp,
taiga, mountain, coast, navigable river, natural wonder — grants **+1 Appeal** to the tile.
The thresholds and payouts are **engine-side** (not in any GlobalParameters table — don't
look for a moddable cutoff), stated verbatim in the **Civilopedia**:
`Base/modules/base-standard/text/en_us/Civilopedia_Concepts_Text.xml` (the "Appeal" concept):

| Grade | Accumulated Appeal | Vanilla payout (improved **rural** tile) |
|---|---|---|
| Average | 0–2 | nothing |
| **Charming** | **3–4** | +1 Happiness |
| **Breathtaking** | **5+** | +2 Happiness |

- The **Appeal value** lives on terrain/features in `Base/modules/base-standard/data/terrain.xml`
  (+ the natural-wonder terrain files): ordinary natural-beauty features = **`Appeal="1"`**;
  **natural wonders = `Appeal="6"`** → a single adjacent natural wonder alone clears Breathtaking
  (≥5), which is why NW-adjacent tiles read as "always Breathtaking" in-game.
- **`REQUIREMENT_PLOT_HAS_APPEAL`** — gate a plot-yield modifier on a tile's Appeal grade. Two
  threshold args map directly to the grades:
  - `UseAppealHappinessThreshold="true"` = **Charming (3+)** — the +1-Happiness tier.
  - `UseAppealDoubleHappinessThreshold="true"` = **Breathtaking (5+)** — the +2 ("double") tier.
    (That's the literal origin of the "double happiness" name.)
- **Consume appeal** (reward yields on appealing tiles): `EFFECT_PLOT_ADJUST_YIELD` on
  `COLLECTION_CITY_PLOT_YIELDS` (or `COLLECTION_PLAYER_PLOT_YIELDS`) + `REQUIREMENT_PLOT_HAS_APPEAL`.
  Add `REQUIREMENT_PLOT_DISTRICT_CLASS` (`DistrictClass=RURAL`) to restrict to the rural ring.
  Base proofs: `MOD_SHWEDAGON_ZEDI_DAW_TILE_APPEAL_SCIENCE` (RURAL + single/Charming),
  `MOD_HEIAN_HOO_DO_HALL_APPEAL_YIELDS` (no district filter + double/Breathtaking, Cul/Prod/Happy).
- **Grant appeal** (make wonders raise nearby Appeal): **`EFFECT_PLAYER_GRANT_WONDER_APPEAL`**
  (arg `Amount`) — **new in 1.4.1 / Brush & Blade**, defined only in `DLC/heian/modules/data/`
  (`WONDER_HOO_DO_HALL`). It is **player-scoped and wonder-generic** — Amount = appeal each of the
  player's wonders radiates to surrounding tiles (so it *is* an "all wonders grant appeal" lever).
  ⚠ It's the **only** appeal-*granting* effect — base 1.4.1 has none; Appeal otherwise comes only
  from terrain/features. Verify it resolves with the Heian DLC **disabled** before relying on it
  (engine effect, but the only on-disk definition ships in the DLC module).
- **Adjacency variants** also key off appeal grade by name: `AdjacentCharmingAppeal="True"` /
  `AdjacentBreathtakingAppeal="True"` on an `Adjacency_YieldChange` row (Heian Jinja/Jōbō proofs)
  — an alternative to `REQUIREMENT_PLOT_HAS_APPEAL` when the bonus is a building adjacency.

> **Custom activatable adjacency recipe (e.g. "+Happiness to buildings next to a Wonder").** Three pieces,
> and the **table name on the activation row is a crash-class gotcha**:
> 1. Define the rule in **`<Adjacency_YieldChanges>`**: `<Row ID="MyRule" YieldType="YIELD_HAPPINESS"
>    YieldChange="1" TilesRequired="1" AdjacentDistrict="DISTRICT_WONDER"/>`.
> 2. Register the activation row in **`<Constructible_WildcardAdjacencies>`** (NOT `Constructible_Adjacencies`):
>    `<Row YieldChangeId="MyRule" RequiresActivation="true" ConstructibleClass="BUILDING"/>`. Using
>    `Constructible_Adjacencies` throws **`table Constructible_Adjacencies has no column named ConstructibleClass`**,
>    rolls back the *whole* UpdateDatabase action group it's in, and **crashes on load**. Base proof:
>    `ExAttributeCultural01WonderHappiness` (Classical Revival) in `age-exploration/data/constructibles-shared.xml`.
> 3. Turn it on with `EFFECT_CITY_ACTIVATE_CONSTRUCTIBLE_ADJACENCY` (arg `ConstructibleAdjacency="MyRule"`,
>    `COLLECTION_PLAYER_CITIES`). It's binary (the rule's `YieldChange` is the magnitude). These `<Database>`-schema
>    rows need their own data file, loaded BEFORE the modifier that activates them. **Keep that data file in its OWN
>    UpdateDatabase action** (or a load-order that tolerates rollback) — if it shares the action group with your
>    modifiers and errors, it takes them ALL down.
> 4. **Wildcard vs class-restricted.** OMIT `ConstructibleClass` on the activation row → the adjacency applies to
>    **every** constructible, buildings AND wonders = the **Machu Picchu** pattern (`MachuPikchuWildcardMountainCulture`,
>    `AdjacentTerrain="TERRAIN_MOUNTAIN"` → all buildings gain Culture per adjacent mountain). With
>    `ConstructibleClass="BUILDING"` it's buildings only. `AdjacentDistrict`/`AdjacentTerrain` picks what it keys off.
>    **Water-keyed adjacency columns** (verified vs base data — AnjuvannamCoastGold, CandiBentarRiverCulture, AltarLake):
>    `AdjacentTerrain="TERRAIN_COAST"` / `="TERRAIN_NAVIGABLE_RIVER"`, `AdjacentNavigableRiver="true"`, `AdjacentLake="true"`.
>    (For per-tile *worked-yield* gates — as opposed to building adjacency — use the `EFFECT_PLOT_ADJUST_YIELD` water gates
>    in the plot-requirements note below: `REQUIREMENT_PLOT_IS_RIVER`/`_IS_LAKE`/`_BIOME_TYPE_MATCHES`/`_FEATURE_TYPE_MATCHES`.)
> 5. **Scale per Age cleanly** (yields, so per-Age scaling is fine): define numbered rules (`MyRule1/2/3`, YieldChange
>    1/2/3) and have each Age activate ONLY its own — a clean +1/+2/+3 with no cross-Age stacking, using only the
>    proven ACTIVATE effect. (Avoid `EFFECT_CITY_ADJUST_ADJACENCY_FLAT_AMOUNT` to bump an *activated wildcard* — that
>    combo is unverified; the numbered-rules approach sidesteps it.)

> **Don't gate STATIC-WORLD effects on a per-Age node.** The physical world (terrain, features, wonders,
> the Appeal they generate) persists unchanged across Age transitions. So a STRUCTURAL effect — "wonders
> grant Appeal," "a building next to a Wonder gets Happiness," appeal-/terrain-based adjacencies — must not
> be gated on a per-Age tech/civic node: it would blink **off at every Age rollover until re-research**,
> though nothing in the world changed. Gate such effects on **durable** conditions (a settlement-count /
> "tall" gate) or leave them **self-scoping** ("no wonder → no effect"), and keep them **binary** (population
> size doesn't decide whether a wonder confers a benefit — no pop tiers). **Yields are the opposite** — yield
> amounts legitimately change with tech/era, so node-gating + re-earning + scaling them per Age is correct.
> See [[civ7-age-transition-static-functions]].

> **Working impassable terrain — make mountains yield (no special civ).** Mountains are impassable/dead by default.
> To reclaim them: (1) grant the base **faux improvement** via `EFFECT_PLAYER_GRANT_CONSTRUCTIBLE_UNLOCK`
> (`ConstructibleType="IMPROVEMENT_INCA_MOUNTAIN"`) — it's `RequiresUnlock="true"` and **NOT civ-locked**, displays
> in-game as **"Expedition Base"**, and despite its `Age="AGE_EXPLORATION"` tag it works in **all Ages** (Nepal grants
> it from Antiquity: `MOD_NEPAL_IMPROVE_MOUNTAINS`, comment "reusing the same faux improvement"). Building it makes the
> mountain a worked `DISTRICT_RURAL` tile. (2) Put yields ON the peak with `EFFECT_PLOT_ADJUST_YIELD` (see below) gated
> `REQUIREMENT_PLOT_TERRAIN_TYPE_MATCHES`(`TerrainType=TERRAIN_MOUNTAIN`) + `REQUIREMENT_PLOT_DISTRICT_CLASS` inverse
> (`CITYCENTER, URBAN, WONDER`) — mirrors the Inca Apus (`TRAIT_MOD_APUS_MOUNTAIN_FOOD`). **Alternative, no improvement
> needed:** a **warehouse** yield `TerrainInCity="TERRAIN_MOUNTAIN"` pays per-mountain-in-city automatically (how
> Modern grants +1 Happiness per mountain, `MOMountainTerrainHappiness`).
>
> **Working the open OCEAN — the sea twin of the mountain reclaim** (verified in-game 2026-06-27). Ocean workability is
> Age-dependent: **Antiquity** = coast/rivers/lakes/reefs workable but NOT open ocean; **Exploration** = open ocean
> BLOCKED unless granted; **Modern** = all civs work ocean natively. To let a tall city work empty ocean in Exploration,
> grant `IMPROVEMENT_HAWAII_FISHING_BOAT` via `EFFECT_PLAYER_GRANT_CONSTRUCTIBLE_UNLOCK` (`COLLECTION_OWNER`) — the literal
> sea-twin of the `IMPROVEMENT_INCA_MOUNTAIN` grant (same effect/collection, sits a few lines away in Hawaii's
> `TRAIT_MOD_HAWAII_IMPROVE_OCEAN`). It's a `DISTRICT_RURAL` improvement valid on `TERRAIN_OCEAN` with NO resource gate,
> so it works empty ocean. Then `BIOME_MARINE` plot-yields pay the ocean half (coast was already paying in AQ).

> **`EFFECT_PLOT_ADJUST_YIELD` plot requirements** (subject = a plot; use the PLAYER-rooted `COLLECTION_PLAYER_PLOT_YIELDS`
> so it survives the attach wrapper, NOT the city-context `COLLECTION_CITY_PLOT_YIELDS`). Stack any of:
> `REQUIREMENT_PLOT_TERRAIN_TYPE_MATCHES` (`TerrainType`), `REQUIREMENT_PLOT_DISTRICT_CLASS` (`DistrictClass`, supports
> `inverse`), `REQUIREMENT_PLOT_HAS_APPEAL`, and **`REQUIREMENT_PLOT_IS_HOMELANDS`** (bare; `inverse`=distant lands —
> use it to hemisphere-scope a player-wide plot effect so it doesn't bleed across hemispheres). Comma-list `YieldType`
> + one `Amount` applies that amount to each yield (Hoo-Do/Inca proofs).
>
> **Water plot gates** (verified in-game 2026-06-27; same `EFFECT_PLOT_ADJUST_YIELD` recipe, swap the terrain match):
> `REQUIREMENT_PLOT_IS_RIVER` takes **`Navigable`** (navigable rivers) AND **`Minor`** (minor rivers) as args — one
> requirement covers both river kinds; `REQUIREMENT_PLOT_IS_LAKE` (bare); `REQUIREMENT_PLOT_BIOME_TYPE_MATCHES`
> (`BiomeType="BIOME_MARINE"`) = **coast AND ocean in one gate**; `REQUIREMENT_PLOT_FEATURE_TYPE_MATCHES` accepts a
> **`FeatureClassType`** arg (e.g. `FEATURE_CLASS_AQUATIC` = all reefs/atolls in one rule) as well as a single
> `FeatureType`; `REQUIREMENT_PLOT_IS_NATURAL_WONDER` (bare) = the plot is a natural wonder (scope to *water* NWs by also
> requiring `BIOME_MARINE`, DLC-agnostic). Reqs in `SubjectRequirements` are AND-ed — separate water types = separate
> modifiers, which lets each carry its own yield set + amount, and they STACK on a tile that matches several (e.g. a
> reef in marine biome gets both rules — a deliberate premium-tile spike; add an `inverse` gate to de-dupe if unwanted).

> **Gate gameplay on DISCOVERY, not just a tech.** `REQUIREMENT_PLAYER_DISCOVERED_NATURAL_WONDER` (no `FeatureType` =
> *any* natural wonder; proven in-game by `MOUNT_EVEREST_REVEAL`) is a real in-game `OwnerRequirements` gate — an
> effect switches on once the player discovers a natural wonder (an exploration unlock, not a tree unlock). It's a
> one-way latch, so it doesn't blink at Age transitions. **NOT** the same as a civ **`<CivilizationUnlocks>`** entry —
> that's META-progression (unlocking a civ for *future games*) and can't gate in-game modifiers.
> ⚠ **"Discovered" ≠ "revealed" (confirmed in-game 2026-06-27).** The requirement needs the actual DISCOVERY event — a
> unit reaching/adjacent the NW, firing the "discovered [X]" notification — NOT merely the tile being revealed by vision.
> A turn-1 sighting of a natural wonder at the edge of vision does **not** satisfy it (base parallel: `MOUNT_EVEREST_REVEAL`
> fires *"on discovery"*). If a discovery-gated effect "isn't firing," check the player has truly discovered (visited) a NW.

> **Flat per-city "floor" yield gated on terrain/adjacency (Tonga pattern).** For a guaranteed once-per-city bonus
> (e.g. "+yield just for being coastal"), gate a city-collection yield on **`REQUIREMENT_CITY_HAS_TERRAIN`**
> (`TerrainType` + `Amount` = the city owns ≥Amount tiles of that terrain — clean, AND-combines with a tall gate) or, like
> base Tonga, on **`REQUIREMENT_BUILDING_IS_ADJACENT_TO_X`** (`BuildingType` + `AdjacentTerrainTypes`, in a
> `REQUIREMENTSET_TEST_ANY` to OR several buildings — but OR-sets don't AND cleanly with other reqs, so prefer
> `CITY_HAS_TERRAIN`). Auto-scale the amount with `<Argument name="Amount" type="ScaleByGameAge" extra="100">1</Argument>`.
> ⚠ **`EFFECT_CITY_ADJUST_YIELD` takes a SINGLE `YieldType`** (every base use does; e.g. `MOD_FOUNDER_BELIEF_DOMESTIC_FOOD`
> / `_PRODUCTION` are split modifiers) — emit one modifier per yield. (`EFFECT_PLOT_ADJUST_YIELD` *does* take a comma list.)

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
