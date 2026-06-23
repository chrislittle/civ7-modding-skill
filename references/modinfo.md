# The `.modinfo` file

The `.modinfo` is the manifest: it tells the engine what your mod is, what it
depends on, *when* each chunk of content applies, and *which files* deliver it. Get
this wrong and nothing else matters — the engine never reaches your data.

## Contents
- [Skeleton](#skeleton)
- [Properties — and the integer-Version rule](#properties)
- [Dependencies vs References](#dependencies-vs-references)
- [ActionCriteria — when does an action group apply](#actioncriteria)
- [ActionGroups — what loads, and in what order](#actiongroups)

## Skeleton

A real, working modinfo (this is the structure verified to load and apply):

```xml
<?xml version="1.0" encoding="utf-8"?>
<Mod id="my-cool-mod" version="1" xmlns="ModInfo">
    <Properties>
        <Name>My Cool Mod</Name>
        <Description>What it does.</Description>
        <Authors>Your Name</Authors>
        <Package>Mod</Package>
        <AffectsSavedGames>1</AffectsSavedGames>
        <Version>1</Version>
    </Properties>

    <Dependencies>
        <Mod id="base-standard" title="LOC_MODULE_BASE_STANDARD_NAME"/>
    </Dependencies>
    <References>
        <Mod id="core" title="LOC_MODULE_CORE_NAME"/>
    </References>

    <ActionCriteria>
        <Criteria id="always">
            <AlwaysMet/>
        </Criteria>
        <Criteria id="age-antiquity">
            <AgeInUse>AGE_ANTIQUITY</AgeInUse>
        </Criteria>
    </ActionCriteria>

    <ActionGroups>
        <ActionGroup id="text-all" scope="game" criteria="always">
            <Properties><LoadOrder>100</LoadOrder></Properties>
            <Actions>
                <UpdateText>
                    <Item>text/en_us/MyModText.xml</Item>
                </UpdateText>
            </Actions>
        </ActionGroup>
        <ActionGroup id="antiquity" scope="game" criteria="age-antiquity">
            <Properties><LoadOrder>110</LoadOrder></Properties>
            <Actions>
                <UpdateDatabase>
                    <Item>data/antiquity/projects.xml</Item>
                    <Item>data/antiquity/modifiers.xml</Item>
                    <Item>data/antiquity/traditions.xml</Item>
                </UpdateDatabase>
            </Actions>
        </ActionGroup>
    </ActionGroups>
</Mod>
```

The `id` is the mod's identity everywhere (log lines, the Mods.sqlite registry, the
deployed folder name). Keep it stable; bump it deliberately when you want the engine
to treat the mod as new.

## Properties

| Tag | Notes |
|-----|-------|
| `<Name>` / `<Description>` | Shown in the Add-Ons UI. Can be literal text or `LOC_*` keys. **For line breaks in a multi-paragraph Description, use the `[N]` token — raw newlines are collapsed to spaces** (see below). |
| `<Authors>` | Free text. |
| `<Package>` | `Mod` for player mods. |
| `<AffectsSavedGames>` | `1` if it changes gameplay (most gameplay mods). |
| `<Version>` | **MUST be an integer.** See below. |

### Line breaks in `<Description>` — use `[N]`, not raw newlines

The Add-Ons / mod-details screen **collapses literal newlines (and runs of whitespace) to a single
space**, so a long multi-paragraph `<Description>` renders as one wall of text. Use the game's newline
token **`[N]`** to force breaks — `[N]` for a line break, `[N][N]` for a paragraph gap. (`[N]` is Civ
VII's standard newline token; it's used throughout the base-game LOC text.) **Confirmed in-game
2026-06-22** rendering correctly in a mod's Add-Ons description.

Tip for readable XML source: put the `[N]` token at the **start** of each logical line (the physical
newline before it collapses to an invisible trailing space), e.g.:

```xml
<Description>My Mod — one-line tagline.
[N][N]A paragraph of intro text describing the mod.
[N][N]KEY FEATURES
[N]- First feature.
[N]- Second feature.</Description>
```

This works with inline literal text. If you instead localize the Description via a `LOC_*` key (also
valid — base/DLC modules do this), put the `[N]` tokens in the LOC string; that text path runs through
the same formatter. No other rich markup (e.g. `[B]` bold) is verified for this field — stick to `[N]`.

### The integer-Version rule (the #1 silent killer)

The engine stores a mod's version as an **integer**. A non-integer like `0.1` parses
to `0`/invalid, and the engine then **silently drops the mod from "Target Mods."** The
symptom is maximally confusing: the mod is *discovered* (you see "Loading Mod …" in
Modding.log), it shows **Enabled** in the Add-Ons menu, FK validation passes — and it
applies absolutely nothing, with no error anywhere.

- Use `<Version>1</Version>` and the matching attribute `version="1"` on `<Mod>`.
- Every base-game and working community mod uses integer versions. If a mod "shows
  enabled but does nothing," check the version **first**, before anything else.
- The version the engine actually recorded lives in the `ModProperties` table of
  `Mods.sqlite` — inspect it with `scripts/inspect-registry.ps1` if in doubt.

## Dependencies vs References

- `<Dependencies>` — modules that **must** be present and load **before** yours.
  Gameplay mods depend on `base-standard`.
- `<References>` — soft ordering: load after these *if present* (e.g. `core`). Use it
  to sequence relative to other content without making it mandatory.

Both use `<Mod id="..." title="LOC_..."/>`.

## ActionCriteria

`<Criteria>` blocks define **conditions**; an `<ActionGroup>` names one via its
`criteria` attribute. The two you'll use most:

- `<AlwaysMet/>` — always applies. Use for age-agnostic content like localized text.
- `<AgeInUse>AGE_ANTIQUITY</AgeInUse>` — applies only during that Age. Civ VII content
  is heavily Age-scoped; typically you write one criteria + one action group per Age
  (`AGE_ANTIQUITY`, `AGE_EXPLORATION`, `AGE_MODERN`) so each Age loads only its own
  rows. This also avoids duplicate-row collisions across Ages.

## ActionGroups

Each `<ActionGroup>` ties a `criteria` to a set of `<Actions>`.

- **`scope`** — `"game"` for gameplay/database content (what this skill is about).
  `"shell"` is for the front-end/setup screens (menus, config). If your gameplay rows
  aren't applying, confirm the group is `scope="game"`.
- **`<Properties><LoadOrder>N</LoadOrder>`** — lower loads first. Put text low (e.g.
  100) and data slightly higher (110) so localization exists before data references it.
- **`<Actions>`**:
  - `<UpdateDatabase><Item>path</Item>…</UpdateDatabase>` — load gameplay data XML/SQL
    and GameEffects XML. **`<Item>` order matters within a group**: a table must be
    registered before another file references it (load `projects.xml` before the
    `modifiers.xml`/`traditions.xml` that name those projects).
  - `<UpdateText><Item>text/en_us/…</Item></UpdateText>` — localization (`LOC_*` keys).
  - `<UpdateIcons><Item>data/…-icons.xml</Item>…</UpdateIcons>` — icon definitions
    (`<IconDefinitions><Row><ID>TYPE</ID><Path>blp:atlas_name</Path></Row>`). **Icons
    load into a SEPARATE icons database** — they must go through `<UpdateIcons>`, NOT
    `<UpdateDatabase>`. Putting an `<IconDefinitions>` block in a file loaded by
    `<UpdateDatabase>` errors ("no such table") and **rolls back the ENTIRE action group**,
    so the whole age's data fails to apply (mod shows "Content Configuration Validation
    Failed"). To reuse base-game art with no custom asset, point `<Path>` at an existing
    atlas entry (e.g. `blp:city_antiquity_256x256`, `blp:project_discover_calculus`); the
    UI resolves the icon by the row's `<ID>` matching the object's Type. This mirrors how
    the base game loads `data/icons/project-icons.xml`.
  - (`<UIScripts>` / `<ImportFiles>` exist for UI mods — out of scope here.)

Paths are **relative to the modinfo's folder**, forward slashes.

A quick way to reason about a confusing mod: list its action groups and ask, for each,
"what criteria gates it, and is it `scope="game"`?" An action group whose criteria is
never met (e.g. wrong AGE constant) simply never runs, silently.
