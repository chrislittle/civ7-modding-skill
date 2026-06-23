# Town specialization → roll-in for tall / one-city mods

**This is a DISTINCT pattern from the city-state Suzerain layer** (see
[city-states-suzerain.md](city-states-suzerain.md)). Keep them separate in code and in your head: the
Suzerain layer scales with city-states you lead; the town-specialization roll-in internalizes the benefits a
*wide* empire gets from its specialized **Towns** into a player who has none.

## What town specialization is

A **Town** (not a City) with pop ≥7 builds ONE specialization project (`ExclusiveSpecialization="true"
TownOnly="true" PrereqPopulation="7"`), which attaches a modifier bundle. Two delivery patterns:

- **Pattern A "Warehouse"** — `EFFECT_CITY_GRANT_WAREHOUSE_YIELD` with named handles (`AQ/EX/MOTown*`): boosts
  the town's own worked tiles.
- **Pattern B "...IN_CITY"** — the effects that route to connected cities (the transferable ones).

A one-city player has no towns → gets none of this. The roll-in grants the same effects to the metropolis.

## ⚠️ Data id vs player-facing focus name (they differ!)

| Data id | In-game focus name | Core effect |
|---|---|---|
| `PROJECT_TOWN_GRANARY` / `_FISHING` | Farming / Fishing Town | +Food on tiles (warehouse) |
| `PROJECT_TOWN_PRODUCTION` | Mining Town | +Production on tiles (warehouse) |
| `PROJECT_TOWN_TRADE` | Trading Outpost | +5/+5 trade-route range + resource-happiness |
| `PROJECT_TOWN_TEMPLE` | **Religious Site** | +2 Relic/GW slots on Temples, +2 happiness/bldg, −25% temple cost |
| `PROJECT_TOWN_INN` | **Hub Town** | +1 Influence per connected settlement (1/continent) |
| `PROJECT_TOWN_FACTORY` (MO) | Factory Town | +1 resource cap, +5/+5 range, build discounts |
| `PROJECT_TOWN_FORT` | Fort Town | +25 district HP, +5 unit healing, +1 gold on fortifications |
| `PROJECT_TOWN_URBAN_CENTER` | Urban Center | +1 Science & +1 Culture per Quarter |
| `PROJECT_TOWN_RESORT` | Resort Town | +1 happiness/gold on appeal tiles, +50% Natural-Wonder tile yields |

Don't label a bucket by its raw id (e.g. "Inn") in player-facing text — use the focus name ("Hub Town").

## The roll-in pattern

Match the base **effect + magnitude**, swap the delivery: re-author the effect on `COLLECTION_PLAYER_CITIES`
(or `COLLECTION_OWNER` for player-level) via your attach-wrapper, gated by a progression node + pop tier +
anti-wide. Drop the bundle's `EFFECT_ADJUST_TOWN_CAN_PURCHASE_TAGGED_CONSTRUCTIBLES` sub-modifiers — a City
already builds everything.

## ⚠️ THE OVERLAP RULE (most important)

A full tall mod usually already grants Science/Culture/Gold/Production/Food via a fan-out kit (adjacency,
per-pop, under-cap, etc.). **Do NOT re-emit a town bucket whose yield/mechanic the kit already covers** — that
is pure yield inflation + a tuning nightmare + UI clutter. Classify each bucket:

- **Identical to an existing lever → don't add; the lever IS the bucket** (just relabel/tune its magnitude).
  E.g. Trading Outpost & Factory range = `EFFECT_CITY_ADJUST_TRADE_ROUTE_RANGE`; Factory resource cap =
  `EFFECT_CITY_ADJUST_RESOURCE_CAP`.
- **Same yield via a different mechanism → prefer tuning the existing lever over adding a parallel source**
  (e.g. Granary/Fishing food vs an under-cap Food lever; Urban Center per-quarter Sci/Cul vs adjacency/per-pop).
- **Genuinely new mechanic → safe to roll in.** E.g. Fort Town district HP/healing (survivability, no yield
  overlap); Religious Site temple slots (relic capacity, if your generic GW-slot grant is undertuned);
  Hub Town influence (influence engine); Resort +50% Natural-Wonder tile yields.

Rule of thumb: roll in a bucket for its **distinct mechanic**, not to stack another copy of a yield you
already grant.

## Influence note (ties to the suzerain ref)

Hub Town's base effect is `EFFECT_CITY_ADJUST_YIELD_PER_CONNECTED_CITY` = **0 for a one-city player**. And
influence can't be a per-pop/per-city yield (see [city-states-suzerain.md](city-states-suzerain.md)). Roll it
in as flat `EFFECT_PLAYER_ADJUST_CONSTRUCTIBLE_YIELD` influence on the age's Diplomacy building, gated behind
that building's unlock node (AQ `BUILDING_MONUMENT`@`NODE_TECH_AQ_MASONRY`, EX
`BUILDING_GUILDHALL`@`NODE_TECH_EX_GUILDS`).

Base data: `base-standard/data/projects*.xml` (Fort/Urban Center/Resort) +
`age-{antiquity,exploration,modern}/data/projects*.xml` (the rest).
