# Legacies, Triumphs, Dedications & Legacy Paths

The in-game **"Your Empire's Legacy"** screen is **three distinct data systems**, not
one. Untangling them is essential before modding any of it. All are plain, additive
data tables (verified in-game 2026-07-06 on 1.4.x). Files live in each age module's
`data/`: `legacies.xml`, `legacies-gameeffects.xml`, `legacy-path-gameeffects.xml`,
`victories.xml`, `gameplay.xml`, `unlocks.xml`, `age-transition.xml`, plus schema in
`base-standard/data/legacies.xml` and `Base/Assets/schema/gameplay/01_GameplaySchema.sql`.

## The three layers

| Layer | Table(s) | What it is |
|---|---|---|
| **Legacy Paths** | `gameplay.xml` `<LegacyPaths>` + `victories.xml` `<AgeProgressionMilestones>` | The **victory / age-pacing engine**. |
| **Triumphs** | `<Legacies>` (+ `<LegacyModifiers>`) | The **reward-granting accomplishments**. |
| **Dedications** | `<AdvancedStartCards>` (+ `<AdvancedStartCardEffects>`) | The **pick-at-next-Age-start bonus cards**. |

### Legacy Paths = the pacing engine (be careful here)
- `<LegacyPaths>` = **4 per Age only**: `LEGACY_PATH_<AGE>_{CULTURE,MILITARY,SCIENCE,ECONOMIC}`.
  **No Diplomatic/Expansionist path.** (These are the 4 classic victory domains.)
- Progressed by `<AgeProgressionMilestones>` (3 per path, `RequiredPathPoints` thresholds,
  `FinalMilestone`). Each milestone fires an `AgeProgressionEventType`
  (`AGE_PROGRESSION_PLAYER_MILESTONE_1/2/3` = 5/5/10 points) into
  `AGE_PROGRESSION_<AGE>_AGE_TIMER` (`EndsAge="true"`, MaxPoints ≈140) — **milestones
  literally advance the age clock toward ending the Age** — and grant
  `AGE_REWARD_LEGACY_POINT_<DOMAIN>` (the Dedication spending currency).
- "Path points" are **engine-scored** from domain activity (e.g.
  `MODIFIER_PLAYER_ADJUST_SETTLEMENT_SCORING`), not a simple data effect.
- ⚠ **Do not add milestones / AgeProgression event points if you want to stay
  pacing-neutral** — that's the only thing that moves the age timer.

### Triumphs = `<Legacies>` rows (the reward layer)
A Triumph row: `LegacyType, LegacySubtype (6 domains + CRISIS/RACE/CONQUEROR/EXPLORER),
Age, Name, Description, TriggerDescription`, flags:
- **`FirstPlayerOnly="true"`** = a "First to…" competition Triumph.
- **`MajorLegacy="true"/"false"`** = Major vs Minor Triumph.
- `Inactive`, `ProgressString`, `TraitType`.

`<LegacyModifiers>` links each Triumph to a reward `ModifierID` (its completion reward,
usually **`EFFECT_PLAYER_GRANT_UNLOCK`**) + a `RequirementSetID` (the earn condition, a
GameEffects `<RequirementSet id=…>`).

**Pacing-neutral by construction:** `grep -c LEGACY_AQ victories.xml` = **0** — Triumphs
are NOT referenced by the age-timer/milestone/victory file. Completing Triumphs does not
move the age clock as long as their reward is unlock/grant-only. Three tangle vectors to
avoid: (1) don't register accomplishments as `AgeProgressionMilestones`; (2) don't call
`EFFECT_PLAYER_ADD_LEGACY` / grant `AGE_REWARD_LEGACY_POINT_*` (mints Dedication currency,
can trip milestones); (3) don't add `LegacyPaths`.

### Dedications = `<AdvancedStartCards>` (Age-start picks)
Each card: `CardEffectType1..N` → `<AdvancedStartCardEffects>` (`EffectType` = a normal
`<Modifier>` id, fully authorable) · `IndividualLimit`/`GroupLimit` · an **`Unlock=`** gate
· and a **cost** in a card-point currency. Cost columns are **fixed schema**:
`CultureCost, ScienceCost, MilitaristicCost, EconomicCost, WildcardCost, DarkAgeCost` —
i.e. the **4 legacy domains + Wildcard + DarkAge. No Diplomatic/Expansionist currency, and
you CANNOT add a currency column** (mods add rows, not columns). Points are the Legacy
Points carried over (`<AgeTransitionLegacyPoints>` base Wildcard=3 + earned per path).
Diplomatic/Expansionist-flavored cards are priced in an existing currency (base pairs
Expansion→Militaristic, Diplomacy→Culture; Wildcard is the neutral choice).

## The full native loop (all data-additive)
Deed → **Triumph** `RequirementSet` passes → `EFFECT_PLAYER_GRANT_UNLOCK` → the gated
**Dedication** `AdvancedStartCard` enters the next-Age pick pool → player spends carried
Legacy Points to slot it.

## Adding a Triumph — the FK chain (learned in-game)
To add one Triumph + its Unlock, you need all of:
- `<Types>` rows: the Legacy (`Kind="KIND_LEGACY"`) and the Unlock (`Kind="KIND_UNLOCK"`).
- `<Legacies>` + `<LegacyModifiers>` + `<TypeTags>` (domain tag).
- **`<Legacy_LegacySets>`** row adding the Legacy to `LEGACY_SET_DEFAULT` — **REQUIRED or
  it won't render** under the Triumphs screen's Default filter (applies to DB, filtered out
  of view otherwise).
- The reward `<Modifier>` (GRANT_UNLOCK) + the earn `<RequirementSet>` (GameEffects).
- The Unlock: `<Unlocks>` registry row + `<UnlockRewards>` (name/icon) + `<UnlockRequirements>`
  (RequirementSetId, typically `REQUIREMENT_TRIUMPHS_COMPLETED` with `TriumphTypes=<LegacyType>`).
  **Load the Unlock + its Types/registry in ALWAYS scope** (as base-standard does) so a
  next-Age Dedication card can resolve the Unlock FK across the age boundary.
- ⚠ `UnlockRequirements.UnlockType` FKs to the **`Unlocks`** table (which FKs to `Types`).
  Registering only `UnlockRewards` → "does not exist in Unlocks" FK failure → **hard crash**.

**Render confirmed in-game** (unlike custom slot types): an inserted Legacy shows in the
Triumphs screen; an inserted AdvancedStartCard is gated by its Unlock. Both are viable.

## Related: culture-slot types & card branding
- The government/Policies UI renders only **Tradition / Policy / Crisis** slot columns. A
  **custom `KIND_CULTURE_SLOT` type is data-moddable but does NOT render** — its slot/cards
  are invisible without custom JS UI. Prefer `POLICY_CULTURE_SLOT` for modded cards; grant
  extra Policy slots via `EFFECT_PLAYER_GRANT_TRADITION_SLOTS SlotType=POLICY_CULTURE_SLOT`.
- Culture-slot pools: **TRADITION** (scarce, holds civ-unique traditions + policies) ·
  **POLICY** (common, celebration/golden-age granted, holds policy cards) · **CRISIS**
  (dedicated). Slots are **player-scoped** (base `StartingTraditionSlots` 1/2/3 + grants).
- Branding modded cards with a logo/color needs a **UI decorator + CSS override** (native
  `TraitType`-driven art doesn't work for modded non-civ cards — engine forces
  `TRAIT_RANDOM`). See `ui-modding.md` → "Branding / restyling base cards".

## Designing a GOOD Triumph / earn-trigger (not filler)

When you gate a reward on "the player did X" — a Triumph, a narrative deed, a card unlock, a quest —
the *quality* of X decides whether it's fun or filler. Framework distilled from mining both games' data
(Civ 6's ~142 Historic Moments + Civ 7's 180 native Triumphs and the requirement vocabulary).

**Benchmark:** Civ 7's 180 native Triumphs are **~92% "count to N" / "first to N of X"** — one verb
(*accumulate*) with a number, no context or combination. Civ 6's Historic Moments were roughly half
situational and rewarded *planning*. **Design toward Civ 6's texture; avoid the count-to-N default —
it's native's turf and it's mindless (and duplicating it wastes your feat budget).**

**7 archetypes of a good accomplishment** (each rewards a decision, not a next-turn click):

| # | Archetype | Design intent | Civ 6 echo | Civ 7 requirement tools |
|---|---|---|---|---|
| **A** | Spatial optimization | Arrange your layout for a payoff you plan turns ahead | `DISTRICT_CONSTRUCTED_HIGH_ADJACENCY_*` | `BUILDING_IS_ADJACENT_TO_X` (BuildingCount, Adjacent{Building,Terrain,Feature,Resource,Quarter}Types) |
| **B** | Adversity → asset | Turn a liability into value (flourish on harsh terrain) | `CITY_BUILT_NEAR_VOLCANO`, `IMPROVEMENT_CONSTRUCTED_ON_DISASTER_YIELD_TILE` | `PLOT_HAS_APPEAL`, `PLOT_BIOME_TYPE_MATCHES`, terrain/mountain reqs |
| **C** | Placement context | Build relative to a *rare* map feature — scouting + siting | `CITY_BUILT_NEAR_NATURAL_WONDER`, `FIND_NATURAL_WONDER` | `PLOT_ADJACENT_FEATURE_TYPE_MATCHES` (natural wonder), coast/river, `PLAYER_IMPROVED_X_NATURAL_WONDERS` |
| **D** | Deep investment | Max ONE asset instead of spreading | `GOVERNOR_FULLY_PROMOTED`, `BUILDING_CONSTRUCTED_FULL_*` | `COMMANDER_HAS_MAXED_DISCIPLINE`, fill Great-Work / resource slots to cap, complete a Quarter |
| **E** | Setup chain / network | A multi-step sequence you build toward | `RAILROAD_CONNECTS_TWO_CITIES`, `PLAYER_MET_ALL_MAJORS` | trade-route reqs, distant-lands connection, compound RequirementSets (TEST_ALL) |
| **F** | Timing window | Do X *during* a window (war, an age moment) | `CITY_CHANGED_RELIGION_ENEMY_CITY_DURING_WAR` | `PLAYER_HAS_X_WARS`, `PLAYER_IS_IN_GOLDEN_AGE` (⚠ see anti-patterns) |
| **G** | Sacrifice / tradeoff | Give up one axis to spike another | Civ 6 tradeoff policy cards | two effects, one negative (`ADJUST_YIELD_PER_POPULATION` negative Amount) |

**Anti-patterns — do NOT gate on these:**
- ❌ **Count-to-N** ("have 12 codices") — mindless; native owns it.
- ❌ **Opaque relative** ("lead in Science") — the player can't see progress, and can't know it at all
  vs unmet leaders. Only viable with dedicated dashboard tracking.
- ❌ **Happens naturally** ("all buildings current-Age") — you get it by playing normally.
- ❌ **The default optimal line** — subtler: it *does* require planning (passes the tests on paper) but
  it's exactly what a competent player already does. A good trigger sits **above the default line**: an
  extra constraint the default doesn't include, a bar past the natural ceiling, an off-meta site/axis, or
  a sacrifice. Litmus: *"would a strong player do this even with no reward attached?"* If yes, it isn't an
  accomplishment.
- ❌ **Happiness-STAGE gates** — civ-dependent (needs amenity civs) and Firaxis is mid-retuning happiness;
  fragile. A *sustained* top-stage condition can work, but stage *ladders* are brittle — calibrate carefully.
- ❌ **Celebration / Golden-Age *timing* triggers** — a well-played empire Celebrates regularly, so "do X
  while Celebrating" is a wait-a-few-turns tax, not a decision. (Happiness-STATE yield *scaling* — "while
  Joyous: +N" — is fine; that's a reward modifier, not a trigger.)
- ❌ **Pure map-luck** ("discover a Natural Wonder") — fine as a *bonus*, not as a required gate.

**Five design tests** (run every candidate through them): **(1) Planning** — does earning it make the
player arrange things turns ahead, or just wait? **(2) Visibility** — can they see progress without hidden
math or unmet-player data? **(3) Not-mindless** — could it be reached by mashing next-turn? **(4) Flexible**
— is there more than one path/site/order? **(5) Above the default line** — would a strong player do it with
no reward attached? If yes, add a constraint / raise the bar / move it off-meta / attach a sacrifice.

**Budget note:** a yield lane has only ~2–4 buildings per Age and a tile holds 2 buildings, so you *can't*
mint many distinct lane-specific accomplishments from building COUNT. **Decouple the trigger from the
reward's lane** — the trigger is any good accomplishment (above); the card it unlocks carries the lane
flavor. Lock the *archetype + condition*; tune the *threshold* in playtest.
