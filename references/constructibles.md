# Constructibles: AGELESS, obsolescence & overbuilding

Buildings, improvements, and wonders are all **Constructibles** (data table `Constructibles`,
root `<Database>`), tagged via `TypeTags` (e.g. `AGELESS`, `WAREHOUSE`, `PRODUCTION_WAREHOUSE`).
How a constructible behaves across Ages — and whether its tile can ever be reclaimed — is
governed by the **`AGELESS` tag** and the **`Age` column**. These rules were verified in-game.

## `AGELESS` = never obsolete, permanent tile (can't be overbuilt by default)

- **`AGELESS`** constructible → **never goes obsolete** (keeps its yields/effect across every Age) and its
  tile is **permanent: it cannot be overbuilt by normal play.** Warehouses (Brickyard, Granary, Sawmill, …)
  **and all Wonders** carry `AGELESS` (e.g. `<Row Type="WONDER_PYRAMIDS" Tag="AGELESS"/>`). Full list + each
  constructible's **Age** and **Ageless** flag: [constructibles-catalog.md](constructibles-catalog.md).
- **Non-`AGELESS`** constructible with an `Age` → goes **obsolete** once the current Age is later than its
  `Age`: it stays on its tile but **loses its yields** — and **this is the one overbuildable case**, a
  current-Age building can replace it at no real cost.
- ⚠ **The default game forbids overbuilding an `AGELESS` building** (and forbids overbuilding/placing a
  **WONDER** on an occupied tile). A **mod** can still reclaim such a tile with the scripted
  **`EFFECT_PLAYER_REPLACE_CONSTRUCTIBLE`** (Destroy+Create) — that is "special mod work," not a normal
  action. The Metropolis Ascendant 'Foundations' recycle uses it to place a victory WONDER on a tile normal
  play won't free (its in-game test even landed over an `AGELESS` Sawmill — which a normal overbuild can't do).
  See [gameeffects.md](gameeffects.md).

## Obsolescence is engine-computed (no per-building flag)

A building is obsolete when **`Age` < the current Age**. There is **no** "obsolete now" column and
no building-level obsolete/replacement table (only *units* have replacement chains). Consequences:

- **Nothing is overbuildable during the first Age (Antiquity)** — there's no earlier age to be
  behind. You can't data-hack a building into being overbuildable within its own age.
- **To test overbuild without an age-advance cheat:** start a new game in a **later Age** via
  **Advanced Setup → Age** (a setup option, not a cheat). A later-age start hands you a capital
  pre-built with obsolete, overbuildable previous-age buildings.

## Overbuilding: ONLY obsolete age-bound buildings (AGELESS + WONDERs are protected)

Verified in-game. By default:

- A current-Age **building** can overbuild an **obsolete previous-age building**, reclaiming that tile (you
  lose nothing — the obsolete one already lost its yields). This is how a tall player frees urban tiles.
- You **cannot** overbuild an **`AGELESS`** building (its tile is permanent), and a **WONDER** can't be
  overbuilt or placed on an occupied tile — **wonders require an *unoccupied* valid tile.**
- ⇒ Overbuilding only recycles **obsolete age-bound** tiles; it can't touch ageless tiles and doesn't free
  space for a wonder. In a fixed city radius, building density and wonders compete for finite empty tiles. To
  place a victory **WONDER** in a packed city you need the scripted **`EFFECT_PLAYER_REPLACE_CONSTRUCTIBLE`**
  ("Foundations" recycle pattern in [gameeffects.md](gameeffects.md)) — it bypasses these default restrictions.

## Recipe: make a constructible age-bound (overbuildable later)

This is the "Nerfed Warehouses" pattern — strip `AGELESS` and assign an `Age`:

```sql
UPDATE Constructibles SET Age='AGE_ANTIQUITY' WHERE ConstructibleType='BUILDING_BRICKYARD';
DELETE FROM TypeTags WHERE Tag='AGELESS' AND Type='BUILDING_BRICKYARD';
```

Use cases & caveats:
- **Good for:** letting a tile-starved (e.g. one-city/tall) player **recycle** dead obsolete
  buildings into higher-value current-age buildings, and freeing building demand off *empty* tiles.
- **It is a GLOBAL change** — the `Constructibles`/`TypeTags` edit affects **every player, incl. the
  AI**. Unlike a gated `<Modifier>`, you can't scope a table edit to one player.
- **It nerfs the building** — losing `AGELESS` means losing the cross-Age persistence/yield unless
  the player actively overbuilds it each Age.
- **Do NOT strip `AGELESS` from Wonders** — they'd go obsolete (lose their permanent effect) and be
  destroyable via overbuild. Wonders are meant to be permanent; leave them `AGELESS`.

## Age-transition lifecycle (when can you build / overbuild what)

A constructible's `Age` (and the `AGELESS` tag) decide its whole lifecycle. **Grep the
[constructibles-catalog.md](constructibles-catalog.md) for any constructible's Age — it is NOT guessable
from the id** (`BUILDING_TEMPLE` is **Exploration**, not Antiquity; `BUILDING_MONUMENT` is Antiquity).

- **Age-bound building** (has `Age="AGE_X"`, e.g. `BUILDING_TEMPLE` = `AGE_EXPLORATION`):
  - **Buildable ONLY during its own Age.** You cannot build it in a later Age — e.g. you cannot build a
    Temple in Modern. (Antiquity→Exploration→Modern: each tier's buildings are buildable only in that tier.)
  - **On transition to the next Age it goes obsolete:** it stays on its tile but **loses its yields**, and
    becomes the natural **overbuild** target (a current-Age building can replace it at no real cost).
- **`AGELESS` building** (the outlier, e.g. `BUILDING_SAWMILL` — `AGELESS`, no `Age`):
  - **Buildable in any Age**, **never obsolete** (keeps its yields across every transition), and its tile is
    **permanent — NOT overbuildable by normal play.** Only a mod's `EFFECT_PLAYER_REPLACE_CONSTRUCTIBLE` can
    reclaim it (special mod work, not a default action).
- **WONDER** (`ConstructibleClass="WONDER"`): needs an **empty** valid tile, can't be overbuilt and can't
  overbuild (most are also `AGELESS`). A packed city must use `EFFECT_PLAYER_REPLACE_CONSTRUCTIBLE` to place one.
- **First Age (Antiquity):** nothing is overbuildable (no earlier Age to be behind), so obsolescence/overbuild
  only matter from Exploration onward.

## Defining a NEW building (the minimum table set)

A buildable building needs rows in **four** tables (miss the `Buildings` row and it won't function):

```xml
<Database>
  <Types><Row Type="BUILDING_MY_THING" Kind="KIND_CONSTRUCTIBLE"/></Types>
  <Constructibles>
    <Row ConstructibleType="BUILDING_MY_THING" Name="LOC_..._NAME" Description="LOC_..._DESCRIPTION"
         Tooltip="LOC_..._TOOLTIP" ConstructibleClass="BUILDING" Cost="200" Population="0"
         Age="AGE_MODERN" RequiresUnlock="true"/>
  </Constructibles>
  <Buildings><Row ConstructibleType="BUILDING_MY_THING" Movable="false"/></Buildings>   <!-- omit Town= -> city-only -->
  <Constructible_ValidDistricts><Row ConstructibleType="BUILDING_MY_THING" DistrictType="DISTRICT_URBAN"/></Constructible_ValidDistricts>
</Database>
```

- `RequiresUnlock="true"` + a `ProgressionTreeNodeUnlocks` row (`TargetKind="KIND_CONSTRUCTIBLE"`) gates it on a
  tech/civic node — same as a base wonder (e.g. World's Fair is unlocked by `NODE_CIVIC_MO_MAIN_HEGEMONY` at
  `UnlockDepth="2"`/mastery; Manhattan Project by `NODE_TECH_MO_NUCLEAR_FISSION` at depth 1).
- `Constructible_ValidDistricts = DISTRICT_URBAN` lets it overbuild obsolete urban districts.
- **No player-state buildability gate exists.** The `Constructibles` schema gates only on physical placement
  (`Constructible_ValidDistricts/Terrains/Biomes/Features/Resources`, `Adjacent*`, hemisphere `RequiresHomeland/
  RequiresDistantLands`) + `RequiresUnlock`. **You cannot hide/disable a building because the player owns wonder
  X, has N cities, etc.** — there is no requirement-set hook on a constructible. Conditional hiding needs a UI mod
  (JS production-list filter). (You *can* still gate a `<Modifier>` the building fires — just not the building's
  own buildability.)

## The production pop-out renders `Tooltip`, NOT `Description`

For a building/constructible, the in-game **info pop-out** (the panel beside the production list) shows the
constructible's **`Tooltip`** string. Put the player-facing "what it does / how to use it" text in
`LOC_..._TOOLTIP`. (`Description` is used elsewhere/auto-composed; don't rely on it for the pop-out body.)

## Icons: map a constructible to an icon (reuse an existing asset)

A new constructible with no icon shows **blank** in the build list. Icons load via an **`<UpdateIcons>`** action
(NOT `<UpdateDatabase>`), with `IconDefinitions` rows mapping the type to a `blp:` atlas asset. You can **reuse a
base asset** — no custom art needed:

```xml
<!-- data/icons/my-icons.xml -->
<Database><IconDefinitions>
  <Row><ID>BUILDING_MY_THING</ID><Path>blp:wondericon_worldsfair</Path></Row>
</IconDefinitions></Database>
```
```xml
<!-- modinfo: icons load globally; an UpdateIcons action group, criteria="always" like the base art groups -->
<ActionGroup id="my-icons" scope="game" criteria="always">
  <Actions><UpdateIcons><Item>data/icons/my-icons.xml</Item></UpdateIcons></Actions>
</ActionGroup>
```
Find a wonder/building's `blp:` path in `Base/modules/age-*/data/icons/*-icons.xml`. Reusing the target's own icon
(e.g. a "Foundations" building that becomes the World's Fair → `blp:wondericon_worldsfair`) doubles as a UI cue.
