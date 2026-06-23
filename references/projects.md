# Projects (City / Town)

A Project is a buildable item in a settlement's production list. They're one way to let a
player **opt into** an effect (build it once, get a permanent bonus) without consuming a
Tradition/Culture slot. But two non-obvious rules decide whether your project is even
visible and buildable — and if you only need "research a tech → bonuses turn on," a
project is often **more machinery than you need**: gating bonuses directly on the tech
node (no project, no build action) is simpler. See
[Gating on a tech node (without a project)](#gating-on-a-tech-node-without-a-project).

## Contents
- [The two rules that hide a project](#the-two-rules-that-hide-a-project)
- [Defining a Project](#defining-a-project)
- [Gating it behind a tech (ProgressionTreeNodeUnlocks)](#gating-it-behind-a-tech)
- [Giving it an effect (ProjectCompletionModifiers)](#giving-it-an-effect)
- [Gating on a tech node (without a project)](#gating-on-a-tech-node-without-a-project)
- [Showing an unlock note on a tech panel (display-only marker)](#showing-an-unlock-note-on-a-tech-panel-display-only-marker)
- [Worked pattern](#worked-pattern)

## The two rules that hide a project

1. **A project with no effect is hidden** from the build list. The engine won't show a
   project that does nothing. It needs at least one `ProjectCompletionModifiers` (or
   `ProjectModifiers`) row binding a real Modifier. If your project "doesn't appear,"
   this is the usual cause.

2. **`RequiresUnlock` semantics:** for a **City** project unlocked by researching a
   tech, set `RequiresUnlock="false"` — the `ProgressionTreeNodeUnlocks` row *is* the
   gate, and `false` means "don't also require a separate warehouse-style unlock."
   `RequiresUnlock="true"` is for **Town** warehouse projects. Getting this backwards
   makes a tech-gated city project never become buildable.

## Defining a Project

Projects are data-XML rows (root `<Database>`, table `Projects`). Mirror a real
base-game city project such as `PROJECT_INVENT_CALCULUS`:

```xml
<Database>
    <Projects>
        <Row ProjectType="PROJECT_MY_THING"
             Name="LOC_PROJECT_MY_THING_NAME"
             ShortName="LOC_PROJECT_MY_THING_NAME"
             Description="LOC_PROJECT_MY_THING_DESCRIPTION"
             CityOnly="true"
             Cost="200"
             MaxPlayerInstances="1"
             RequiresUnlock="false"/>
    </Projects>
</Database>
```

Key columns:

| Column | Meaning |
|--------|---------|
| `ProjectType` | Unique id (also referenced by unlock + completion rows). |
| `CityOnly` | `"true"` to restrict to Cities (vs Towns). |
| `Cost` | Production cost. Tune per Age (e.g. 200 / 500 / 1000 across Antiquity/Exploration/Modern). |
| `MaxPlayerInstances` | `1` for a once-per-player project. |
| `RequiresUnlock` | `"false"` for tech-unlocked City projects (see rule 2). |

You'll also need `Types` rows and `LOC_*` text entries for the name/description.

## Gating it behind a tech

Add a `ProgressionTreeNodeUnlocks` row so researching a tech node unlocks the project:

```xml
<ProgressionTreeNodeUnlocks>
    <Row ProgressionTreeNodeType="NODE_TECH_AQ_CURRENCY"
         TargetKind="KIND_PROJECT"
         TargetType="PROJECT_MY_THING"
         UnlockDepth="1"/>
</ProgressionTreeNodeUnlocks>
```

Find the right `ProgressionTreeNodeType` by grepping the base game's
`progression-trees-tech.xml` / `progression-trees-culture.xml` (see
[finding-base-game-patterns.md](finding-base-game-patterns.md)). `TargetKind="KIND_PROJECT"`
unlocks a project; the same table with `KIND_TRADITION` unlocks a tradition.

> **Discoverability caveat:** a `KIND_PROJECT` unlock does *not* get a descriptive line on
> the tech node — it shows only the generic project entry/icon, so players may not realize the
> project exists. (A `KIND_MODIFIER` unlock, by contrast, *does* display a readable line — see
> [Showing an unlock note on a tech panel](#showing-an-unlock-note-on-a-tech-panel-display-only-marker).)
> If discoverability of a project matters, plan a tooltip/notification (a UI concern beyond this
> database layer).

## Giving it an effect

Bind a Modifier that fires on completion:

```xml
<ProjectCompletionModifiers>
    <Row ProjectType="PROJECT_MY_THING" ModifierId="MOD_MY_THING_REWARD"/>
</ProjectCompletionModifiers>
```

…and define `MOD_MY_THING_REWARD` in a GameEffects file. For a one-time player reward
(e.g. an attribute point) you can copy the base `MOD_INVENT_CALCULUS_ATTRIBUTE`
pattern (effect `EFFECT_PLAYER_ATTRIBUTE`). For ongoing **player/city** bonuses, don't
fire the raw modifier here — fire a `COLLECTION_MAJOR_PLAYERS` + `EFFECT_ATTACH_MODIFIERS`
wrapper (see [gameeffects.md](gameeffects.md#the-attach-wrapper-rule)).

A common, robust pattern: the project completion grants a small immediate reward *and*
sets the `REQUIREMENT_PLAYER_HAS_COMPLETED_PROJECT` flag that the ongoing wrapped
bonuses gate themselves on. Building the project thus "switches on" a whole bonus set.

## Gating on a tech node (without a project)

Often you don't want a buildable project at all — you just want "research tech X → the
bonuses turn on." Do that by gating each bonus modifier on the node directly, with **no
project and no slottable tradition**:

1. Define your bonus modifiers and an attach wrapper exactly as usual
   ([gameeffects.md](gameeffects.md#the-attach-wrapper-rule)).
2. On each REWARD/cap modifier, add an `OwnerRequirements` gate on the host tech/civic
   node:

   ```xml
   <OwnerRequirements>
       <Requirement type="REQUIREMENT_PLAYER_HAS_COMPLETED_PROGRESSION_TREE_NODE">
           <Argument name="ProgressionTreeNodeType">NODE_TECH_AQ_CURRENCY</Argument>
           <Argument name="MinDepth">1</Argument>
       </Requirement>
   </OwnerRequirements>
   ```

3. Bind **only the wrapper**, always-on, via `<GameModifiers>` in a data file.

> ⚠️ **`MinDepth` is mandatory.** Omit `<Argument name="MinDepth">1</Argument>` and the
> requirement **silently never fires** — no log error, every gated bonus stays off
> forever. Every base-game use of this requirement includes `MinDepth`. (This is silent
> killer #6 in the main SKILL.) The requirement works in `OwnerRequirements`.

This is what the Tall Metropolis mod uses now. **Project vs tech-node gate, when to pick
which:**

| | Project | Tech-node gate |
|---|---------|----------------|
| Player action | must **build** it (Production cost) | automatic on **research** |
| Extra machinery | Projects row + Types + LOC + unlock + completion effect | none — just the requirement |
| Good when | you want a deliberate, costed opt-in per city | you want bonuses to flip on the moment the tech lands |

Note an Age caveat for both: a tech-node gate re-locks at each Age boundary until the new
Age's host tech is researched (each Age has its own node). Keep any always-on safety nets
**ungated** so they survive that window.

> **Heads-up — this gating is invisible in the UI.** The passive
> `REQUIREMENT_PLAYER_HAS_COMPLETED_PROGRESSION_TREE_NODE` gate turns the bonuses on correctly but
> the tech panel **advertises nothing** (the panel only lists `ProgressionTreeNodeUnlocks` rows, not
> requirements). For a breadcrumb, add a display marker — see the next section.

## Showing an unlock note on a tech panel (display-only marker)

When you gate bonuses with the passive requirement above, nothing lists on the tech node. To add a
readable "X unlocked" line **without** disturbing your delivery, use a **no-op marker modifier** that
exists purely for its description.

How the panel renders unlocks (from base `age-antiquity/data/progression-trees-tech.xml` +
`…-gameeffects.xml`):
- A `TargetKind="KIND_MODIFIER"` unlock row **both applies the modifier AND displays its
  `<String context="Description">`** as a line on the node (this is how base "+1 Specialist Limit in
  all Cities" / "+2 GDP…" appear). Add `Hidden="true"` to the row to apply silently with no line.
- `TargetKind="KIND_PROJECT"` gets **no** descriptive line (generic entry only) — so for a readable
  note, use a `KIND_MODIFIER` marker.
- These unlock modifiers are `permanent="true"` — applied **once at research**, not continuously
  re-evaluated. So **never route a population-/condition-gated bonus through a node-unlock** (the gate
  would only be checked at research time). Keep real gated bonuses on the always-on + REQUIREMENT
  path; use a separate marker just for the display line.

The marker — a genuine no-op (zero gameplay effect):

```xml
<!-- GameEffects file: the marker modifier. -->
<Modifier id="MY_UNLOCK_NOTE" collection="COLLECTION_OWNER"
          effect="EFFECT_PLAYER_ADJUST_SETTLEMENT_CAP" permanent="true">
    <Argument name="Amount">0</Argument>                  <!-- 0 = changes nothing -->
    <String context="Description">LOC_MY_UNLOCK_NOTE</String>
</Modifier>
```
```xml
<!-- Data XML file: list it on the node (omit Hidden so the line shows). -->
<ProgressionTreeNodeUnlocks>
    <Row ProgressionTreeNodeType="NODE_TECH_AQ_CURRENCY" TargetKind="KIND_MODIFIER"
         TargetType="MY_UNLOCK_NOTE" UnlockDepth="1"/>
</ProgressionTreeNodeUnlocks>
```

Define `LOC_MY_UNLOCK_NOTE` in your text file, and keep the marker **out of any attach wrapper** so
it isn't delivered twice. **Confirmed in-game:** the `Amount=0` marker renders its description on the
panel (even while the tech is still *Locked Research*) and changes nothing. `EFFECT_PLAYER_ADJUST_SETTLEMENT_CAP`
is just a convenient proven no-op — any harmless effect plus a Description String works.

> **`UnlockDepth` chooses WHICH panel the note shows on — base unlock vs. Mastery.** `UnlockDepth="1"`
> lists the note on the node's base unlock; **`UnlockDepth="2"` lists it on the node's *Mastery* panel.**
> So if a bonus is **gated at `MinDepth=2`** (it only fires once the node's mastery is complete — see the
> mastery `★` trap in [progression-trees.md](progression-trees.md)), give its discoverability marker
> `UnlockDepth="2"` too, so the description appears where the bonus actually unlocks. Putting the note at
> depth 1 while the bonus gates at depth 2 is a silent mismatch — the note shows on the base unlock but the
> effect doesn't turn on until mastery (the "mastery note didn't land on the mastery panel" bug). A depth-2
> unlock row only renders if the node actually HAS a mastery (`★` in the node table); on a node without one
> it shows nothing. Tip: drive the marker id, its LOC tag, the unlock row AND its depth from one config list
> so the three can't drift apart.

## Worked pattern

The Tall Metropolis mod's current unlock shape (tech-node gate, no project):

1. Research the host tech (Antiquity `NODE_TECH_AQ_CURRENCY`, Exploration
   `NODE_TECH_EX_EDUCATION`, Modern `NODE_TECH_MO_ELECTRICITY`).
2. A `COLLECTION_MAJOR_PLAYERS` attach wrapper (`TM_<age>_ATTACH_ALL`), bound always-on
   via `<GameModifiers>`, delivers every bonus to each player.
3. Each REWARD/cap modifier self-gates on
   `REQUIREMENT_PLAYER_HAS_COMPLETED_PROGRESSION_TREE_NODE(host node, MinDepth=1)` +
   population tier + anti-wide, so it's inert until the tech is researched and the city
   is big enough. The safety nets omit the tech gate so they cushion the Age-transition
   window.

> Historical note: earlier versions delivered the same bonuses via a slottable Tradition,
> then via a one-time `PROJECT_DEDICATE_METROPOLIS_*` City project (built once to set a
> `REQUIREMENT_PLAYER_HAS_COMPLETED_PROJECT` flag, with a +1-attribute completion reward
> copied from `PROJECT_INVENT_CALCULUS`). Both were retired in favour of the simpler
> tech-node gate above — but that project chain is still a valid pattern if you *want* a
> buildable opt-in.
