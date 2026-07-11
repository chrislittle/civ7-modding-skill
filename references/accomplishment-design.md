# Designing accomplishments / earn-triggers (Triumphs, quests, card unlocks) that reward skill

For any mod that gates a reward on "the player did X" — Triumphs, narrative deeds, card unlocks, quest
objectives — the *quality* of X decides whether the feature is fun or filler. This is the design framework,
distilled from mining **both** games' data (Civ 6's 142 Historic Moments + Civ 7's 180 native Triumphs and
the requirement vocabulary).

## The benchmark: why Civ 7's native accomplishments feel bland
Civ 7's 180 Triumphs are **~92% "count to N" or "first to N of X"** (51% First-to, 41% threshold). One verb —
*accumulate* — with a number. No context, no combination, no spatial thought. Civ 6's ~142 Historic Moments were
the opposite: roughly half firsts/discovery, half **situational** — and the memorable ones reward *planning* and
*cleverness*, not accumulation. **Design toward Civ 6's texture; avoid the count-to-N default (it's native's turf
and it's mindless).**

## The 7 archetypes of a GOOD accomplishment (each rewards a decision, not a next-turn click)
| # | Archetype | Design intent | Civ 6 moment it echoes | Civ 7 requirement tools |
|---|---|---|---|---|
| **A** | **Spatial optimization** | Arrange your layout for a payoff — a puzzle you plan turns ahead | `DISTRICT_CONSTRUCTED_HIGH_ADJACENCY_*` (Campus/Harbor/…) | `BUILDING_IS_ADJACENT_TO_X` (BuildingCount, Adjacent{Building,Terrain,Feature,Resource,Quarter}Types) |
| **B** | **Adversity → asset** ⭐ | Turn a liability into value (flourish on harsh terrain, make dead/low tiles pay) | `CITY_BUILT_NEAR_VOLCANO`, `IMPROVEMENT_CONSTRUCTED_ON_DISASTER_YIELD_TILE`, mountain tunnels | `PLOT_HAS_APPEAL` (cultivate Breathtaking), `PLOT_BIOME_TYPE_MATCHES` (harsh biome), terrain/mountain reqs + the Arcadia yield system |
| **C** | **Placement context** | Build relative to a *rare* map feature — scouting + siting | `CITY_BUILT_NEAR_NATURAL_WONDER`, `FIND_NATURAL_WONDER` | `PLOT_ADJACENT_FEATURE_TYPE_MATCHES` (natural wonder), `PLOT_ADJACENT_TERRAIN_TYPE_MATCHES` (mountain), coast/river, `PLAYER_IMPROVED_X_NATURAL_WONDERS` |
| **D** | **Deep investment** | Max ONE asset instead of spreading (concentration = the tall thesis) | `GOVERNOR_FULLY_PROMOTED`, `SPY_MAX_LEVEL`, `BUILDING_CONSTRUCTED_FULL_*` | `COMMANDER_HAS_MAXED_DISCIPLINE`, fill Great-Work slots, fill resource slots to cap, complete a Quarter |
| **E** | **Setup chain / network** | A multi-step sequence you build toward (infrastructure, spread) | `TRADING_POST_IN_EVERY_CIV`, `RAILROAD_CONNECTS_TWO_CITIES`, `PLAYER_MET_ALL_MAJORS` | trade-route reqs, distant-lands connection, compound RequirementSets (TEST_ALL) |
| **F** | **Timing window** | Do X *during* a window (war, celebration, an age moment) — pressure/opportunity | `CITY_CHANGED_RELIGION_ENEMY_CITY_DURING_WAR`, Golden-Age focus | `PLAYER_HAS_X_WARS`, `PLAYER_IS_IN_GOLDEN_AGE`, happiness-stage (⚠ unstable) |
| **G** | **Sacrifice / tradeoff** | Give up one axis to spike another (specialization-over-balance) | Civ 6 tradeoff policy cards (Collectivism: +adjacency, −Great People) | two effects, one negative (`ADJUST_YIELD_PER_POPULATION` negative Amount) |

## Anti-patterns — do NOT use these as triggers
- ❌ **Count-to-N** ("have 12 codices") — mindless accumulation; native owns it; duplicates native Triumphs.
- ❌ **Opaque relative** ("lead in Science", "most trade routes") — the player can't see progress and **can't know at all vs unmet leaders**. Only viable with dedicated dashboard tracking, and even then the unmet-player gap remains.
- ❌ **Happens naturally** ("all buildings are current-Age") — you get it by playing normally; not an achievement.
- ❌ **The default optimal line** ⭐ ("build a max-adjacency Library in Antiquity") — subtler than *happens-naturally*: it *does* require planning (so it passes the four tests below on paper), but **it's exactly what any competent player already does to play well.** Rewarding it doesn't ask for skill or a distinctive choice — it just taxes the reward onto standard play. A good trigger must sit **above the default line**: an extra constraint the default line doesn't include (appeal-ring *and* max-adjacency), a bar **higher than the natural ceiling** (an adjacency a normal Library never reaches), an **off-meta site/axis** (max-adjacency from *mountains* on harsh land, not the obvious resource cluster), or a **sacrifice**. Litmus: *"would a strong player do this even with no reward attached?"* If yes, it isn't an accomplishment. (⚠ note: a **tall/single-settlement constraint often lifts an idea above the default line** — concentrating wonders/great-works/resources in ONE settlement is *not* what a normal wide player does — but it does **not** save something a strong player does even when tall, like the max-adjacency Library. The trigger must beat *both* default-wide and default-tall play.)
- ❌ **Happiness-STAGE gates** — civ-dependent (needs amenity-civs) + Firaxis is mid-retuning happiness; fragile. **Amendment (Chris, 2026-07-09): the TOP stage (Ecstatic) is explicitly allowed as a Major-feat condition** — unlike celebrations or mid stages, *holding* Ecstatic is a genuine sustained cost, not default play. The ban stands for lower stages and stage-laddered content; keep the retune fragility in mind at calibration.
- ❌ **Celebration / Golden-Age timing triggers** (Chris, 2026-07-09: "take anything that relies on a celebration trigger out overall, anywhere") — a well-played tall city Celebrates regularly, so "do X while Celebrating" adds no real constraint: it's a wait-a-few-turns tax, not a decision. Retires the archetype-F "Golden-Age focus" shape as a feat GATE. Happiness-STATE yield *scaling* ("While Joyous or happier: +N…") remains fine — that's a reward modifier, not a trigger.
- ❌ **Pure map-luck** ("discover a Natural Wonder", "work a disaster-fertilized tile") — fine as a *bonus* but not as a required gate (the site/event may never occur; the *opportunity* is RNG even if the action is deliberate).

## The five design tests (run every candidate through these)
1. **Planning:** does earning it make the player *arrange things turns in advance*? (good) or just wait? (bad)
2. **Visibility:** can the player *see* their progress toward it without hidden math or unmet-player data?
3. **Not-mindless:** could it be reached by mashing next-turn with no decisions? If yes, cut it.
4. **Flexible:** is there more than one path/site/order to achieve it? (rigid single-solution feats frustrate.)
5. **Above the default line** ⭐: would a strong player do this *even with no reward attached*? If yes, it's the default optimal play, not an accomplishment — add a constraint, raise the bar past the natural ceiling, move it off-meta, or attach a sacrifice until the answer is "no." (See the anti-pattern above.)

## Content-budget notes (learned the hard way)
- A yield "lane" has only **~2–4 buildings per Age** and a tile holds **2 buildings** (a full tile = a "Quarter").
  So you **cannot** generate many distinct *lane-specific* accomplishments from building COUNT — the space is
  ~1–2 ideas. **Decouple the trigger from the reward's lane:** the trigger is any good accomplishment (archetypes
  above); the *card it unlocks* carries the lane flavor. Forcing trigger=lane strangles the design.
- Cross-check every candidate against **native Triumph coverage** (they own count-of-X) and the mod's own
  **card corpus** (`cards-suzerain-governments-catalog.md`) so nothing duplicates.
- Numbers are **calibration knobs** — lock the *archetype + condition*, tune the *threshold* in playtest.
