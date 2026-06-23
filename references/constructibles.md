# Constructibles: AGELESS, obsolescence & overbuilding

Buildings, improvements, and wonders are all **Constructibles** (data table `Constructibles`,
root `<Database>`), tagged via `TypeTags` (e.g. `AGELESS`, `WAREHOUSE`, `PRODUCTION_WAREHOUSE`).
How a constructible behaves across Ages — and whether its tile can ever be reclaimed — is
governed by the **`AGELESS` tag** and the **`Age` column**. These rules were verified in-game.

## The `AGELESS` tag = permanent tile

- **`AGELESS`** constructible → **never goes obsolete** → **permanently occupies its tile**; it can
  **never be overbuilt**. Warehouses (Brickyard, Granary, Saw Pit, Gristmill, …) **and all Wonders**
  carry `AGELESS` (e.g. `<Row Type="WONDER_PYRAMIDS" Tag="AGELESS"/>`).
- **Non-`AGELESS`** constructible with an `Age` → goes **obsolete** once the current Age is later
  than its `Age` → becomes **overbuildable** (its tile can be reused).

## Obsolescence is engine-computed (no per-building flag)

A building is obsolete when **`Age` < the current Age**. There is **no** "obsolete now" column and
no building-level obsolete/replacement table (only *units* have replacement chains). Consequences:

- **Nothing is overbuildable during the first Age (Antiquity)** — there's no earlier age to be
  behind. You can't data-hack a building into being overbuildable within its own age.
- **To test overbuild without an age-advance cheat:** start a new game in a **later Age** via
  **Advanced Setup → Age** (a setup option, not a cheat). A later-age start hands you a capital
  pre-built with obsolete, overbuildable previous-age buildings.

## Overbuild is building → building ONLY (wonders can't overbuild)

Verified in-game: you can overbuild an obsolete building with **another building** (e.g. a Temple
over an obsolete warehouse district), but a **Wonder will NOT place on an occupied/overbuildable
tile** even if its terrain requirement is met (e.g. a river wonder won't go on a river tile that
holds an obsolete building). **Wonders require an *unoccupied* valid tile.** So:

- Overbuilding refreshes/upgrades **building slots**; it does **not** create space for wonders.
- **Design tension:** in a fixed city radius, **building density and wonders compete for the same
  finite empty tiles** — recycling buildings can't create empties. A dense city trades building
  tiles for wonder space.

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
