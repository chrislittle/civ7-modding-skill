# Troubleshooting: symptom → cause

Match the symptom, don't theorize. Civ VII rarely tells you what's wrong, so this maps
the observable behavior to the documented cause and the fix. Work top-down within each
section — the first causes are the most common.

## Symptom: mod doesn't appear / shows enabled but does NOTHING

The mod is discovered and toggled on, but no effect in-game. First, confirm whether it
actually **Applied**: `powershell scripts/check-applied.ps1 <mod-id>` (or grep
`Modding.log` for the mod under "Applied all components of enabled mods" and in the
"Target Mods" list).

**If it did NOT apply (absent from Target Mods):**

1. **Non-integer `<Version>`.** *The* most common cause. `version="0.1"` → silently
   dropped from Target Mods while still showing enabled. Fix: integer `version="1"` in
   both the `<Mod version="">` attribute and `<Version>` tag. Verify the parsed value
   in `Mods.sqlite` → `ModProperties` (`scripts/inspect-registry.ps1`).
   → [modinfo.md](modinfo.md#properties)
2. **ActionGroup criteria never met.** A group gated on the wrong `AGE_*` constant (or a
   typo'd criteria id) never runs. Confirm the criteria matches the Age you started.
3. **Wrong scope.** Gameplay rows in a `scope="shell"` group won't affect a game.
   Gameplay = `scope="game"`. → [modinfo.md](modinfo.md#actiongroups)
4. **Didn't start a NEW game** / enabled mid-session. Re-enable, start a fresh game.
5. **Not actually deployed** where the engine looks, or deployed as a broken junction.
   Re-run `scripts/deploy-mod.ps1`; confirm the folder is in `…\Mods\`.

**If it DID apply but the bonus still does nothing:**

6. **Player/city modifier bound directly in `<GameModifiers>`.** No owner context → it
   attaches to no one, silently. Deliver it via a `COLLECTION_MAJOR_PLAYERS` +
   `EFFECT_ATTACH_MODIFIERS` wrapper and bind only the wrapper.
   → [gameeffects.md](gameeffects.md#the-attach-wrapper-rule)
7. **Requirements never pass.** Your `SubjectRequirements`/`OwnerRequirements` gate the
   effect out (population threshold not reached, settlement count, project not built).
   Temporarily remove the gates (or add an ungated debug probe like +50 gold/turn) to
   confirm the effect fires at all, then reintroduce gates one at a time.
8. **Wrong argument name** — the effect ran but ignored your arg because the name is
   off (args are case-sensitive and not guessable). Re-copy the exact
   `<Argument name="...">` from a real base-game usage.
   → [finding-base-game-patterns.md](finding-base-game-patterns.md)
9. **`REQUIREMENT_PLAYER_HAS_COMPLETED_PROGRESSION_TREE_NODE` missing `MinDepth`.** If a
   bonus gated on a researched tech/civic node never fires even with the node researched,
   you almost certainly omitted `<Argument name="MinDepth">1</Argument>`. Without it the
   requirement silently never passes — no log error. Add `MinDepth=1`.
   → [projects.md](projects.md#gating-on-a-tech-node-without-a-project)
10. **Misspelled `OnlyDistantlands`.** A per-hemisphere bonus/count scoped to the distant
    hemisphere never fires because the arg was written `OnlyDistantLands` (capital L). The
    correct spelling is **`OnlyDistantlands`** (lowercase "l"); the wrong case parses with no
    error and silently never passes. (`OnlyHomelands` is camelCased normally.)
    → [gameeffects.md](gameeffects.md#scoping-by-hemisphere-homeland-vs-distant-lands)
11. **`REQUIREMENT_PLAYER_DISCOVERED_NATURAL_WONDER` not satisfied — "discovered" ≠ "revealed."** A bonus gated on
    discovering a natural wonder won't fire just because the NW tile is visible on the map. It needs the actual
    DISCOVERY event (a unit reaching/adjacent the wonder → the "discovered [X]" notification). A turn-1 sighting at the
    edge of vision is a *reveal*, not a discovery. Confirmed in-game; base parallel `MOUNT_EVEREST_REVEAL` fires *"on
    discovery."* If testing, send a unit to actually visit a NW. → [gameeffects.md](gameeffects.md#requirements)

## Symptom: project doesn't appear in the city's build list

1. **Project has no effect** → hidden. Add a `ProjectCompletionModifiers` row binding a
   real Modifier. → [projects.md](projects.md#the-two-rules-that-hide-a-project)
2. **`RequiresUnlock` wrong.** Tech-unlocked City projects need `RequiresUnlock="false"`
   (the `ProgressionTreeNodeUnlocks` row is the gate). `"true"` is for Town warehouse
   projects.
3. **Not unlocked / wrong node.** The `ProgressionTreeNodeUnlocks` row points at a
   `ProgressionTreeNodeType` you haven't researched, or a mistyped node. Verify the node
   id against `progression-trees-tech.xml`.
4. **`CityOnly` vs settlement type** — a `CityOnly="true"` project won't show in a Town.

## Symptom: my new building shows BLANK (no icon) in the build list

The constructible has no icon mapping. Icons load via an **`<UpdateIcons>`** action (NOT `<UpdateDatabase>`)
with `IconDefinitions` rows mapping the type → a `blp:` asset; you can reuse a base asset (no art needed).
→ [constructibles.md](constructibles.md#icons-map-a-constructible-to-an-icon-reuse-an-existing-asset)

## Symptom: my custom UNIT's flag/icon is blank, or the selected-unit portrait square is black

Three separate causes — work through them in order:
1. **Icon registered only in `scope="game"`.** The unit-flag manager reads icon-name definitions from the
   **shell** icon DB. Load `surveyor-icons.xml` in **both** a `scope="game"` and a `scope="shell"` group,
   `criteria="always"`. Per-Age (`criteria="age-*"`) icon groups don't register at all.
2. **Only a flag row, no FONTICON row.** The list/tooltip portrait uses a `Context="FONTICON" IconSize="64"`
   row; add it alongside the default-context flag row.
3. **The big selected-unit PANEL portrait is still black** even with icons + a correct `VisualRemap` — that
   square is a **live 3D render of the unit's own art asset** (`live:/UNIT_TYPE`), which a brand-new unit
   lacks; remaps can't alias it. Map + build-menu look fine; only that panel square is affected. Usually
   accept it. → [custom-units.md](custom-units.md#icons-a-unit-needs-two-rows-in-both-scopes-from-an-always-group)

Log note: `UI.log` records only **failed** resource loads — a *successful* icon load logs nothing, so
"my blp was never requested" is NOT proof it didn't resolve. Don't diagnose from its absence.

## Symptom: my building's pop-out info panel shows the wrong / short text

The constructible pop-out renders the **`Tooltip`** field, not `Description`. Put the player-facing
"what it does" text in `LOC_..._TOOLTIP`. → [constructibles.md](constructibles.md#the-production-pop-out-renders-tooltip-not-description)

## Symptom: I can't hide/disable a building based on player state (owns wonder X, has N cities)

You can't — the `Constructibles` schema gates buildability only on physical placement + `RequiresUnlock`, with
**no player-state requirement hook**. Conditional hiding needs a UI mod (JS production-list filter); in pure data,
gate the building's *effect* (a `<Modifier>` requirement) instead, and accept the entry stays visible.
→ [constructibles.md](constructibles.md#defining-a-new-building-the-minimum-table-set)

## Symptom: a story/effect-seeded resource renders on the map but the Prospector/Surveyor CLAIM won't target it

Expected — not a bug in your mod. The claim's native validity only sees **natively-registered**
resources (map-gen, age-transition seeding, discovery-site story rewards). A resource placed by
a runtime story or plot-collection modifier (`EFFECT_PLOT_PLACE_RESOURCE`) renders, shows yields,
and occupies the plot, but the claim highlighter never lights it — regardless of terrain or
range, and the story-row `ResourceReq` column doesn't help. No data-side fix exists (in-game
verified 2026-07-03, six-run litmus). If you need a claimable seeded resource, deliver it via a
**discovery-queue story bound to a map-gen site** (those register natively) or grant it directly
on owned land with `EFFECT_CITY_ADD_RESOURCE_TO_PLOT` (CITY-class resources only).
→ [narrative-events.md](narrative-events.md) + [custom-units.md](custom-units.md)

## Symptom: my chained narrative stories all fire at once / land their rewards on the wrong tile

Two engine rules (in-game verified 2026-07-03): **`UNLOCKED`-by-predecessor does not meter
same-trigger repeats** — every story in the chain completes off the FIRST trigger gossip
(burst); and **`DuplicateCount>1` gossip requirements anchor the story plot ERRATICALLY** (not
reliably the Kth gossip's tile). The only shape with correct anchoring: **one REQUISITE story
per distinct trigger filter, count=1 + `AfterInit`**. To meter N repeats, use N distinct trigger
filters (e.g. different UnitTypes). → [narrative-events.md](narrative-events.md)

## Symptom: wrong constructible age (e.g. treating Temple as Antiquity)

Constructible ages are **not** guessable from the id (`BUILDING_TEMPLE` = Exploration, `BUILDING_MONUMENT` =
Antiquity). Grep the generated [constructibles-catalog.md](constructibles-catalog.md) for the Age + Ageless flag
before asserting one. Generate it via `python tools/gen-constructibles-catalog.py`.

## Symptom: game CRASHES on load / at map generation

1. **`REQUIREMENT_PLAYER_HAS_X_SETTLEMENTS` (or other player-settlement requirement) in
   `OwnerRequirements` on a `COLLECTION_PLAYER_CONSTRUCTIBLES` modifier.** Hard crash at
   map load — a bare constructible has no settlement/owner context. Move the gate to
   `SubjectRequirements` on a city collection, or drop it for those modifiers.
   → [gameeffects.md](gameeffects.md#requirements)
2. **Malformed XML** — a file that isn't well-formed can take the load down. Run
   `scripts/validate-xml.ps1 <mod-folder>` before every test.
3. **Overriding an existing text tag with `<EnglishText><Row Tag="…">`.** `<Row>` does an
   INSERT; re-defining a tag the base game already defines (e.g. a `CITY_STATE_…_DESCRIPTION`)
   collides → "There were errors loading 'text/…' that require a rollback" → "Rolling back
   database to a good state" → crash. **The data loaded fine; the TEXT file killed it.** Fix:
   override with the upsert verb — `<LocalizedText><Replace Tag="…" Language="en_US"><Text>…
   </Text></Replace></LocalizedText>` (the exact pattern base l10n files use). Use `<Row>` only
   for NEW tags. (This crash shows in **Modding.log**, not Database.log.)
4. **`VisualRemaps` loaded via `<UpdateDatabase>`.** Database.log: `no such table: VisualRemaps
   … In XMLSerializer while updating table VisualRemaps from file …`. `VisualRemaps` isn't a
   gameplay-DB table — it has its **own action**, `<UpdateVisualRemaps>`. Move the remap file out
   of the `UpdateDatabase` list into an `UpdateVisualRemaps` action (an `always` group).
   → [custom-units.md](custom-units.md#3d-model--the-live-render-portrait-visualremap--its-hard-limit)
5. **Diagnosis tip:** a runtime crash leaves `Modding.log` *clean* (often ending
   "Successfully reconfigured game") with the process dying after — distinct from a
   load-exclusion failure where the mod simply never reaches "Applied."
   → [deploy-and-debug.md](deploy-and-debug.md#reading-the-logs)

## Symptom: a *generated* data file is valid XML but the bonus is off / ungated / wrong

If you emit GameEffects from a script (PowerShell template, codegen), **valid XML does not
mean correct content.** A templated value that resolves to empty still produces well-formed
XML — e.g. `<Argument name="ProgressionTreeNodeType"></Argument>` (an empty node) makes the
gate silently never pass, with no error from the generator or the XML validator.

1. **Empty/blank substituted values.** Grep the *generated output* for the tell-tale empty
   attribute (`pattern='ProgressionTreeNodeType"></Argument>'`) before deploying. More
   generally, after generating, spot-check that the values you expected actually landed.
2. **PowerShell variable-name collisions are case-INSENSITIVE.** `$N` and `$n` are the same
   variable; a `foreach ($n in …)` loop will clobber a `$N` you set earlier, so later
   `$N.Foo` lookups return nothing → empty substitutions (cause of #1). Rename to disambiguate.
3. **Don't trust `Select-String -SimpleMatch | %{ $_.Matches.Count }`** to verify counts — under
   `-SimpleMatch` the `.Matches` collection isn't populated and it falsely returns 0. Use
   `(Select-String -Pattern … -SimpleMatch).Count` (matching-line count) instead.

The habit: **regenerate → grep the output for both presence (expected ids/nodes) and absence
(empty args) → only then deploy.** A green XML-validator and a non-erroring generator are
necessary, not sufficient.

## Symptom: some of my rows are missing / FK errors

1. **`<Item>` load order.** Within an ActionGroup, a file that references a table must
   load after the file that creates it (projects before modifiers/traditions that name
   them). Reorder the `<Item>`s. → [modinfo.md](modinfo.md#actiongroups)
2. Check `Database.log` for the specific SQL/FK error and the row it rejected.
3. Remember "Passed Validation" is the **whole DB**, not proof your rows are in — if the
   mod never applied, your rows were never inserted in the first place.

## When you're stuck in a silent-failure loop

Stop guessing and **isolate the layer**: deploy `assets/litmus-mod/` (integer version,
single `AlwaysMet` SQL with an obvious effect). If the litmus effect shows → pipeline
is fine, the bug is in your content (sections above). If even the litmus does nothing →
the bug is environmental (deploy path, enable, version, new-game). This binary split is
almost always faster than re-reading your XML for the tenth time.
→ [deploy-and-debug.md](deploy-and-debug.md#the-litmus-mod)
