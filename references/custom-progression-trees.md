# Custom Progression Trees (whole new civics trees)

**A mod can add an entirely new civics (culture progression) tree — pure data, no UI work.**
In-game verified 2026-07-09 (litmus `custom-civics-tree-litmus`: a 3-node Antiquity tree
rendered as its own Civics-screen tab, laid out automatically, and was researchable). This is
the same machinery behind the base game's civ-unique trees, the Exploration **Theology** branch,
and the three Modern **Ideology** trees (Democracy/Fascism/Communism).

Scope note: this file is about adding a NEW tree. Injecting a node into an EXISTING tree also
works (verified separately) — same tables, just point `ProgressionTree` at the base tree and
hang a `ProgressionTreePrereqs` row off an existing node.

## The five tables

| Table | Role |
|---|---|
| `Types` | `KIND_TREE` for the tree; `KIND_TREE_NODE` per node |
| `ProgressionTrees` | the tree row: `AgeType`, `SystemType="SYSTEM_CULTURE"`, `Name`, optional `RevealRequirementSetId`, `IconString`, `PrereqFormat="OR"`, `CostProgressionModel`/`Param1`, `MultipleUnlockName`, `CivInjectedName` |
| `ProgressionTreeNodes` | per node: `ProgressionTree`, `Cost`, `Name`, `IconString` (reuse a base `cult_*` glyph), optional `Repeatable="true"` + `RepeatableCostProgressionModel` (the Future-Civic pattern — a repeatable sink node), `CanSteal` |
| `ProgressionTreePrereqs` | the arrows (`Node` ← `PrereqNode`). **Layout is automatic** — no column/row fields needed |
| `ProgressionTreeNodeUnlocks` | what completing a node grants: `TargetKind` = `KIND_TRADITION` / `KIND_MODIFIER` / `KIND_CONSTRUCTIBLE` / `KIND_DIPLOMATIC_ACTION`; `UnlockDepth` 1/2 (2 = mastery); extras: `RequiredGovernmentType`, `RequiredTraitType`/`NotTraitType`, `Hidden="true"`, `AIIgnoreUnlockValue` |

Optional polish: `TypeQuotes` (node quote + VO), `ProgressionTree_Advisories` (advisor class
per node — include them; likely feeds AI valuation).

The **main** tech/civics trees are not special data — the `Ages` table points at them
(`MainCultureProgressionTreeType` / `MainTechProgressionTreeType`,
base-standard/data/ages.xml). Every other tree is a hideable "branch" tree.

## Why the UI just works

The Civics screen asks the engine for `player.Culture.getAvailableTrees()` and builds one tab
per tree (Dev Kit `Reference/base-standard/ui/culture-tree/screen-culture-tree.ts` +
`model-culture-tree.ts`); the culture chooser (pick-next-civic) iterates the same list. No
hardcoded tree list anywhere.

⚠ **Don't put "MAIN" in a custom tree's type string** — the tab sort and the chooser both
special-case `ProgressionTreeType.includes("MAIN")` to float the main tree first.

## The three reveal routes (all shipped in base)

A non-main tree is **hidden by default**. Reveal it one of three ways:

1. **`RevealRequirementSetId` on the ProgressionTrees row** — evaluated live.
   Base: Theology = founded-a-religion + age check; Ideologies =
   `REQUIREMENT_PLAYER_HAS_COMPLETED_PROGRESSION_TREE_NODE` on Political Theory
   (age-modern/data/progression-trees-culture-common.xml). For an always-visible tree, use a
   single always-true requirement (e.g. base `REQ_AGE_IS_EXPLORATION` from
   base-standard/data/unlocks.xml). ⚠ In THIS reveal-reqset context base omits `MinDepth`
   and it works (unlike the modifier-requirement context, where omitting MinDepth is the
   silent killer). A `RequirementStrings` row with `Context="RevealProgress"` gives the
   hidden tree its "how to reveal" teaser line.
2. **`EFFECT_PLAYER_REVEAL_CULTURE_TREE`** (arg `ProgressionTreeType`) — how civ-unique trees
   appear: a trait-attached `COLLECTION_OWNER` modifier gated on
   `REQUIREMENT_PLAYER_HAS_CIVILIZATION_OR_LEADER_TRAIT`
   (age-exploration/data/civilizations-gameeffects.xml, `MOD_REVEAL_CIV_CULTURE_TREE_*`).
   Works with a **leader** trait too → leader-specific trees are possible. For a universal
   tree, deliver through the standard attach wrapper (`COLLECTION_MAJOR_PLAYERS` +
   `EFFECT_ATTACH_MODIFIERS` → the reveal modifier) bound in `GameModifiers`. ✅ This is the
   route the litmus verified in-game.
   The `Civilizations.UniqueCultureProgressionTree` column is bookkeeping/UI, not the reveal.
3. **A hidden node-unlock granting the reveal modifier** — "research X → a new tree appears".
   The Test-of-Time tree is revealed by `<Row ProgressionTreeNodeType="NODE_CIVIC_AQ_MAIN_CHIEFDOM"
   TargetKind="KIND_MODIFIER" TargetType="MOD_REVEAL_CIV_CULTURE_TREE_TEST_OF_TIME_ANTIQUITY"
   UnlockDepth="1" Hidden="true"/>` (age-antiquity/data/progression-trees-culture-tot-common.xml).

## Node rewards

Node-granted `KIND_MODIFIER` targets attach with the player as owner. Base shape:
`collection="COLLECTION_OWNER"` + `permanent="true"` + `<String context="Description">` (the
tree UI prints that string on the node card). City-wide yields: unlock a `KIND_TRADITION`
whose `TraditionModifiers` use `COLLECTION_PLAYER_CITIES` (normal tradition plumbing).

## Limits / cautions

- **Culture trees only.** `EFFECT_PLAYER_REVEAL_CULTURE_TREE` has no TECH twin (0 hits in the
  effects catalog). A custom `SYSTEM_TECH` tree could only try the reqset route — **unproven**,
  and the tech screen may assume one tree.
- **Trees are per-Age** (`AgeType` is required). Researched-node modifiers do not survive the
  Age transition — so per the static-functions design rule, never deliver static-world effects
  (appeal, wonder/terrain adjacency) through a per-Age tree node; yields/caps/slots are fine.
- **AI**: unverified whether AI researches a modded tree (advisories included as a hint).
  Watch an AI game before shipping anything competitive.
- Nodes cost **Culture** and compete with the main civics tree for it — a custom tree has
  built-in opportunity cost, same as Theology/civ-unique trees.

## Working example

`civ7_mods/mods/custom-civics-tree-litmus` — one 3-node tree (root + 2 tracks) per Age, each
Age a different reveal route (AQ = effect via wrapper ✅ verified; EX = always-true reqset;
MO = conditional after Political Theory), plus a depth-2 mastery on a custom node and
tradition/slot/settlement-cap rewards. Research writeup:
`civ7_mods/docs/CUSTOM-CIVICS-TREE-RESEARCH.md`.
