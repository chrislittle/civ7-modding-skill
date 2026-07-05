# Yield, balance & tall/wide design — Civ 7's design language

The engine will happily let you build a bonus that's *mechanically* correct and *balance*-wrong in a
way that fights the base game. This file captures the **design-language rules** a Civ 7 modder needs
so bonuses feel native and don't snowball — the meta-knowledge that top players and patch-watchers
have but that isn't visible in the data files. Each rule is grounded (data-verified or patch-sourced);
labels: **[DEV STRATEGY]** = Firaxis's own stated/observed direction, **[DATA]** = verified in the
installed 1.4.1 data, **[TECHNIQUE]** = a modding approach.

## 1. Flat yields, NOT percentage yield multipliers [DEV STRATEGY + DATA]

**Rule: for a yield-OUTPUT bonus, use a FLAT amount, never a stacking `%`-of-yield multiplier.**

Firaxis has spent patches *removing* stacking percentage yield bonuses. The **1.2.5 update
(2025-09-30)** removed *all* direct % yield bonuses from the Attribute Trees, stating stacking % were
"the biggest culprit behind ballooning Yield numbers in later Ages." Their replacements are flat and
per-Age, e.g.:
- `+10% Culture in Cities with a Wonder` → **`+5 Culture per Age`**
- `+10% Culture per Alliance` → **`+10 Culture per Age per Alliance`**
- `+3% to all yields per Alliance` → **`+3 Influence per Age, +5 Happiness per Age`**

**Data confirms the current state (1.4.1):** across *every* leader and civ (base + all DLC) only **~17**
modifiers apply a `Percent` argument to an actual yield (`EFFECT_CITY_ADJUST_YIELD` /
`EFFECT_PLAYER_ADJUST_YIELD` with `Percent`). The other ~100 leader/civ `Percent` uses are a **different
mechanic** — production-speed / purchase / efficiency **discounts** (`EFFECT_CITY_ADJUST_FAVORED_WONDER_
PRODUCTION`, `EFFECT_CITY_ADJUST_CONSTRUCTIBLE_PRODUCTION`, purchase-efficiency, growth %, combat %).

So: **`%` is for "build/buy this faster or cheaper" and combat/rates. Flat is for "how much yield you
get."** A mod that stacks `EFFECT_CITY_ADJUST_YIELD` with `Percent` on Science/Culture/etc. re-imports
the exact late-game snowball Firaxis is engineering out — it will feel non-native and break at Deity in
the later Ages. Don't. (Note: the older Civ 6 balance idiom was the opposite — generous % multipliers —
so **do not port Civ 6 % scaling into Civ 7**; the games' balance languages diverge here.)

Sources: [Civ VII Patch Notes 2025-09-30 (1.2.5)](https://support.civilization.com/hc/en-us/articles/44950826478483-Civilization-VII-Patch-Notes-September-30-2025),
[PCGamesN 1.2.5](https://www.pcgamesn.com/civilization-vii/patch-notes-1-2-5),
[Civ Wiki 1.2.5](https://civilization.fandom.com/wiki/1.2.5_Update_(Civ7)).

## 2. Age scaling = "+N per Age" via `ScaleByGameAge` [DEV STRATEGY]

The native way to make a flat bonus grow into the late game (so it keeps pace as yields inflate across
Ages) is the modifier attribute **`type="ScaleByGameAge" extra="100"`**, which multiplies the authored
`Amount` by the Age ordinal — literally Firaxis's "+N **per Age**" replacement idiom from section 1
(calibrated against `MEMENTO_AMINA_KWALKWALI`: authored `1` renders "+1 Gold per Age" → −2/−4/−6 or
+1/+2/+3 across AQ/EX/MO). Use this for late-game keep-pace scaling **instead of** % compounding. It's
one authored number that self-steepens per Age, matching the game's own curve.

## 3. There is NO cross-city yield dilution, and cities do NOT share tiles [DATA]

A common wrong assumption (correct it before reasoning about multi-city balance):
- **Each city works its OWN tiles** in its own radius/catchment. Nothing is shared between cities. Two
  cities on decent land each grow fully and independently — there is no "the tiles get split" dampening.
- **Per-pop / adjacency bonuses scale off EACH city's OWN population** (`EFFECT_CITY_ADJUST_YIELD_PER_
  POPULATION` on `COLLECTION_PLAYER_CITIES`, with a `Divisor`). A player's Nth city computes its bonus
  from its own pop, unaffected by the others.
- Therefore **N cities running the same kit ≈ N× the total bonus output** — there is no automatic brake.
  If a design needs total power to stay controlled as city count rises, you must add that brake
  *explicitly* (section 4) or via a hard settlement cap (section 5). Don't assume the engine dampens it.

## 4. Scaling by settlement count — the anti-wide gradient [TECHNIQUE]

To make **tall the best per-city return** (each additional city worth less on the bonus axis) without a
hard wall, apply an explicit **per-count gradient**: emit parallel copies of a bonus, each gated on a
settlement-count band (`REQUIREMENT_PLAYER_HAS_X_SETTLEMENTS`, section 5), and give a **larger flat
`Divisor` per higher band** (fewer settlements → smaller divisor → bigger flat per-pop bonus; more
settlements → bigger divisor → smaller each). This reproduces the Civ 6 "Wide & Tall" smooth anti-wide
gradient (which used %) in **flat, Civ-7-native** form. Combine with a hard ceiling so it can't run away.
(A pure binary "full bonus at 1 settlement, nothing at 2+" cutoff also works but is a cliff, not a
gradient — choose per your identity.)

## 5. Settlement cap & footprint control [DATA]

The levers for "how many settlements, enforced how":
- **`EFFECT_PLAYER_ADJUST_SETTLEMENT_CAP`** (`Amount`, optional `Ageless`, `Minimum`) — the one true cap
  driver. **Negative `Amount` lowers the cap and works** (verified in-game: base start cap 3 + `-2` read
  1/1 on founding, no clamp-at-0); additive `+1` grants stack back. This is how you build **earned-
  expansion** designs: lower the base cap, hand slots back on objectives. Gates *founding* (the AI
  respects it); it does **not** stop *capture*.
- **`REQUIREMENT_PLAYER_HAS_X_SETTLEMENTS`** (`RequiredCount`, `CountPerOwnSettlement`,
  **`CountPerConqueredSettlement`**, `OnlyCities`, `OnlyTowns`, `OnlyHomelands`, `OnlyDistantlands`,
  `Inverse`) — the count gate. **By default it counts captured settlements and towns**
  (`CountPerConqueredSettlement=1`, `OnlyTowns=false`), so a soft reward-gate built on it already dims
  bonuses when a player settles, upgrades a town, OR captures past the threshold. Set `OnlyCities=true`
  to count cities only.
- **`REQUIREMENT_PLAYER_OVER_SETTLEMENT_CAP`** — a dynamic "are you above your current (earned) cap"
  gate; use it to make a soft reward-gate track the cap automatically instead of a hardcoded count.
- **`EFFECT_CITY_ADJUST_YIELD_PER_UNDER_SETTLEMENT_CAP`** (Qajar family) — pays yield per *unused* cap
  slot; rewards restraint / the interim before you settle or conquer into an earned slot.
- Capture ignores the hard cap → handle the over-cap case with the count requirement / over-cap gate
  (and the base over-cap unhappiness penalty applies on top).

## 6. Hemisphere / Distant Lands is a map-fragile gate [DATA]

Every base map script marks a west/east **`LandmassRegion`** split — **including Pangaea** (the whole
dominant landmass is marked Homeland; "Distant Lands" is only the fringe islands) and **Archipelago**
(an arbitrary column cut through island soup). So gating *core* mechanics on hemisphere placement
(`REQUIREMENT_CITY_IS_DISTANT_LANDS`, `REQUIREMENT_PLAYER_HAS_X_SETTLEMENTS_FOREIGN_HEMISPHERE`) plays
well only on Continents-family maps and **breaks on Pangaea/Archipelago**. For map-agnostic design,
gate on *total footprint* (section 5) and treat a hemisphere split as an optional *bonus*, not a
requirement. `REQUIREMENT_PLAYER_HAS_X_SETTLEMENTS_FOREIGN_HEMISPHERE Count=0` cleanly detects a
"no reachable Distant Lands settled" (≈ Pangaea) situation if you want a fallback.

## Related

- Age-scaling vs static effects: don't per-Age-node-gate static-world effects (they'd blink off at Age
  rollovers) — see the mod's own design notes; yields are fine to re-scale per Age (section 2).
- Effect argument names are unguessable — confirm against `effects-collections-catalog.md` and a
  base-game example before building (per the skill's core workflow).
