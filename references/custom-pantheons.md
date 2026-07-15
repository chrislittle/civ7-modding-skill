# Custom Pantheons (Civ VII) — mod-writable recipe

Verified against installed data 2026-07-13. **Feasibility: YES** — a mod can add a fully-functional custom pantheon. Pantheons are plain DB rows wired through the **standard GameEffects modifier system**, and the in-game chooser is **data-driven**, so a new belief **auto-appears** and is selectable with no acquisition wiring. (For the full 60-belief catalog + the 4 belief classes, see the generated `religion-and-beliefs-catalog.md`; this file is the hand-maintained *build recipe*.)

## Where pantheons live (CONFIRMED)

`Base/modules/age-antiquity/data/religion.xml` (+ `religion-gameeffects.xml` for the concrete effects):
- `<Types>` — `Row Type="PANTHEON_BONUS_n" Kind="KIND_BELIEF"` per pantheon.
- `<BeliefClasses>` — `BELIEF_CLASS_PANTHEON` with `MaxInReligion="1"` (picks per religion, NOT catalog size).
- `<Beliefs>` — `BeliefType`, `Name`, `Description`, `BeliefClassType="BELIEF_CLASS_PANTHEON"`, optional `Shareable="true"` (multi-civ), `AISelectionBin`.
- `<BeliefModifiers>` — binds `BeliefType` → `ModifierID` (the belief→effect link the engine attaches on adoption).

The chooser (`base-standard/ui/pantheon-chooser/screen-pantheon-chooser.js`) loops `GameInfo.Beliefs`, keeps `BeliefClassType == "BELIEF_CLASS_PANTHEON"`, and calls `Game.PlayerOperations.canStart(FOUND_PANTHEON, {BeliefType})` — so a new belief enters the selectable pool automatically once the player unlocks their pantheon normally.

## Acquisition — a mod needn't touch it

Base grants the pantheon *pick* via `EFFECT_PLAYER_UNLOCK_PANTHEON` on the **Mysticism** civic node (Maurya's Acharya grants a 2nd). To hand out an extra pick, attach `EFFECT_PLAYER_UNLOCK_PANTHEON` to any node/trait. (`EFFECT_ADD_PANTHEON` is a skill-catalog DLC pattern **not present** in this base install — treat as unverified; use `_UNLOCK_PANTHEON`.)

## Minimal worked recipe (four rows + one modifier chain + loc)

```xml
<!-- data/mod-pantheon.xml -->
<Database>
  <Types><Row Type="PANTHEON_MA_METROPOLIS" Kind="KIND_BELIEF"/></Types>
  <Beliefs>
    <Row BeliefType="PANTHEON_MA_METROPOLIS" Name="LOC_PANTHEON_MA_METROPOLIS_NAME"
         Description="LOC_PANTHEON_MA_METROPOLIS_DESCRIPTION"
         BeliefClassType="BELIEF_CLASS_PANTHEON" AISelectionBin="1"/>
  </Beliefs>
  <BeliefModifiers>
    <Row BeliefType="PANTHEON_MA_METROPOLIS" ModifierID="MOD_PANTHEON_MA_METROPOLIS"/>
  </BeliefModifiers>
</Database>
```
```xml
<!-- data/mod-pantheon-gameeffects.xml : <GameEffects xmlns="GameEffects"> -->
<Modifier id="MOD_PANTHEON_MA_METROPOLIS" collection="COLLECTION_MAJOR_PLAYERS" effect="EFFECT_ATTACH_MODIFIERS">
  <SubjectRequirements><Requirement type="REQUIREMENT_PLAYER_HAS_PANTHEON"/></SubjectRequirements>
  <Argument name="ModifierId">ATTACH_PANTHEON_MA_METROPOLIS</Argument>
</Modifier>
<Modifier id="ATTACH_PANTHEON_MA_METROPOLIS" collection="COLLECTION_PLAYER_CITIES" effect="EFFECT_CITY_ADJUST_YIELD">
  <SubjectRequirements><Requirement type="REQUIREMENT_CITY_HAS_BUILDING"><Argument name="BuildingType">BUILDING_ALTAR</Argument></Requirement></SubjectRequirements>
  <Argument name="YieldType">YIELD_SCIENCE</Argument><Argument name="Amount">3</Argument>
</Modifier>
```
Plus `LOC_PANTHEON_MA_METROPOLIS_NAME`/`_DESCRIPTION`. `BELIEF_CLASS_PANTHEON`, `BUILDING_ALTAR`, and the effects/requirements all pre-exist — the mod only references them.

## Gotchas

1. The two-step `EFFECT_ATTACH_MODIFIERS` gated on `REQUIREMENT_PLAYER_HAS_PANTHEON` is the native Antiquity shape — mirror it. (The single-step Exploration form binds the `BeliefModifier` straight to a concrete effect, gated on `REQUIREMENT_PLAYER_IS_RELIGION_FOUNDER`.)
2. `religion.xml` has a dev comment calling `BeliefModifiers` "for the AI... no effect for human players" — **misleading**; the standalone `MOD_PANTHEON_*` modifiers have no other attachment point, so `BeliefModifiers` wires them for everyone (the base pantheons are built this way).
3. **No catalog-size cap** — the pool is whatever's in `GameInfo.Beliefs` of the pantheon class.
4. **Antiquity-flavored** — native pantheons pay out *through `BUILDING_ALTAR`*, so they fade as the Altar goes obsolete (standard age-transition static-function behavior). A custom pantheon can use any effect, but key it off the Altar to behave natively.
5. Exclusivity is engine-enforced via the `FOUND_PANTHEON` operation — only the `Shareable` flag is yours.
6. A new belief needs an icon mapping (standard `UpdateIcons`) to look right in the chooser — cosmetic, not a functional blocker.

Related: `great-people.md`, and the generated `religion-and-beliefs-catalog.md`.
