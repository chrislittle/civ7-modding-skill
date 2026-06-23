# Finding real EFFECT_/REQUIREMENT_/COLLECTION_ names in the base game

The single most important authoring habit: **never invent names.** Effect names,
requirement names, collection names, and especially **argument names** are not
guessable and not consistently documented. The base game is the source of truth — copy
a real, working usage and adapt the values.

## Where the base game lives

```
C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VII\Base\modules
```

Subfolders that matter:

| Folder | Holds |
|--------|-------|
| `base-standard` | Core gameplay tables, civilizations, shared GameEffects. |
| `age-antiquity`, `age-exploration`, `age-modern` | Per-Age content: projects, traditions, tech/culture trees, age-specific effects. |
| `core` | Engine/front-end config (schemas, setup). |

The content you grep is in `.xml` (data + GameEffects) and `.sql` files, plus
`.modinfo` manifests. Workshop mods (more real examples) live under
`steamapps\workshop\content\1295660`.

**DLC content lives elsewhere — grep it too.** Effects and patterns unique to a DLC
civ/leader are **not** in `Base\modules`; they're under the game's `DLC` folder:

```
C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VII\DLC\<name>\modules
```

e.g. `DLC\qajar\modules\data\civilizations-shared-gameeffects.xml`. Some of the most
useful, otherwise-undiscoverable effects live only here — the Qajar civ's
`EFFECT_CITY_ADJUST_YIELD_PER_UNDER_SETTLEMENT_CAP` (yields per settlement *under* the
cap), for instance. If a concept exists in-game but you can't find its effect anywhere in
`Base\modules`, it's probably a DLC ability — widen the grep `path` to the game root (or
the `DLC` folder) before concluding it isn't moddable. (City-state **suzerain**
per-type effects like `EFFECT_CITY_ADJUST_YIELD_PER_SUZERAINED_CITY_STATE_TYPE` *are* in
`base-standard`/age folders, but they're easy to miss — search `SUZERAIN` broadly.)

## How to grep (use the Grep tool, or ripgrep)

**1. Find an effect and see its real arguments.** Search for the `EFFECT_*` and read a
full `<Modifier>` that uses it — the `<Argument name="...">` children tell you the
exact, case-sensitive argument names:

```
Grep: pattern="EFFECT_CITY_ADJUST_CONSTRUCTIBLE_YIELD"
      path="C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VII\Base\modules"
      output_mode="content"  -C=8
```

**2. Discover what effects even exist for a concept.** Grep broadly, then narrow:

```
Grep: pattern="EFFECT_CITY_ADJUST_\w*GREAT_WORK\w*"  -o  (only matches)
Grep: pattern="EFFECT_PLAYER_\w+"  -o     # all player effects, then eyeball
```

**3. Find a requirement's arguments** — same approach:

```
Grep: pattern="REQUIREMENT_CITY_POPULATION"  -C=4
```

(That one reveals args `MinUrbanPopulation` / `MinTotalPopulation` — which you'd never
have guessed as e.g. "Amount".)

**4. Find a table's real columns** (Projects, Traditions, ProgressionTreeNodeUnlocks):
grep the table name or a known row and read the attributes on a `<Row …/>`.

```
Grep: pattern="PROJECT_INVENT_CALCULUS"   # real Project + its completion modifiers
Grep: pattern="ProgressionTreeNodeUnlocks" -C=3
```

**5. Find a delivery pattern to copy.** When you need "how does the base game give a
player an ongoing bonus," grep for `EFFECT_ATTACH_MODIFIERS` and read the
`COLLECTION_MAJOR_PLAYERS` wrapper around it (e.g. `MOD_CS_HILLFORT`).

## Workflow

1. Describe the change in plain terms ("add +2 culture to a building type in all my
   cities").
2. Grep for a base-game modifier that does something *structurally* similar and read it
   whole — collection, effect, requirements, and every argument name.
3. Copy it into your GameEffects file and change only the **values** (yield type,
   amount, requirement thresholds), keeping the **names** exactly.
4. If the bonus is player/city scope, route it through the attach wrapper
   ([gameeffects.md](gameeffects.md#the-attach-wrapper-rule)).
5. Validate well-formedness (`scripts/validate-xml.ps1`) and deploy.

When you report a chosen effect/requirement to the user, cite the base-game file you
copied it from — it makes the choice auditable and easy to revisit.
