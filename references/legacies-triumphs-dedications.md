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
