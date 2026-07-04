# UI modding (JavaScript / HTML / CSS)

Civ VII's entire interface is an embedded HTML/JS runtime (Coherent GT): every screen,
panel, lens, and tooltip is a web component defined in `Base/modules/core/ui/` and
`Base/modules/<module>/ui/`. UI mods ship JavaScript that runs inside that runtime.
This is a **separate modding domain** from gameplay/database mods: no Modifiers, no
GameEffects — instead you decorate or patch the game's own JS components.

Everything in this reference is distilled from shipping, working Steam Workshop mods
(all public, good study material — subscribe and read the source in
`steamapps/workshop/content/1295660/<item-id>/`):

| Pattern source | Mod (Workshop item) | Author |
|---|---|---|
| Decorators, shared Mod-Options tab, file replacement, ui-next | City Hall (3507102289) | beezany |
| Lens-layer prototype patch | Concise Specialists Lens (3506915277) | JNR |
| Custom lens/layer/interface-mode/view/hotkeys, per-game storage | Detailed Map Tacks (3507297712) | wltk |
| Component prototype patching | Advanced Yield Bar (3512790304) | izica |
| Modifier/requirement evaluation in JS, cross-mod API, TS stubs | Policy Yield Previews (3515801789) | leonardfactory |
| Custom screens, dock buttons, SQL text, settings manager | Drongo's suite: Cheat Panel (3734207916), Wonder Screen (3734274579), City Planner (3734169112), Top Panel (3734234006), Adjacency Lens (3737207667), etc. | Drongo / One More Turn |

## Contents

- [Modinfo wiring for UI mods](#modinfo-wiring-for-ui-mods)
- [The three patch techniques (prefer the least invasive)](#the-three-patch-techniques)
- [Custom screens and panels](#custom-screens-and-panels)
- [Lenses and lens layers](#lenses-and-lens-layers)
- [Interface modes and views](#interface-modes-and-views)
- [Hotkeys](#hotkeys)
- [Mod options and the shared settings store](#mod-options-and-the-shared-settings-store)
- [Persisting mod data](#persisting-mod-data)
- [The JS game API surface](#the-js-game-api-surface)
- [Cross-mod integration](#cross-mod-integration)
- [ui-next: the second UI stack](#ui-next-the-second-ui-stack)
- [Debugging UI mods](#debugging-ui-mods)

## Modinfo wiring for UI mods

UI mods use the same `.modinfo` anatomy as data mods (integer Version rule included)
but different Actions:

- **`<UIScripts><Item>path.js</Item></UIScripts>`** — load a JS file as an ES module
  when the context starts. This is the workhorse: decorators, patches, and component
  definitions all load this way.
- **`<ImportFiles><Item>path</Item></ImportFiles>`** — mount a file into the UI
  virtual filesystem so it's addressable at an `fs://game/...` URL. Used for `.html`
  templates, `.css`, and `.png` assets — **and for wholesale replacement of base-game
  UI files**: an imported file whose relative path matches a base module file (e.g.
  `ui/production-chooser/panel-production-chooser.js`, which exists in
  `base-standard`) **shadows the original** — the game loads your copy instead
  (Drongo's Compact Production and Policy Screen work entirely this way; City Hall
  replaces four files this way). Replacement is the most conflict-prone technique —
  see the ladder below.
- **`<UpdateIcons>`** — icon XML (`IconDefinitions`). `<Path>` can point at an
  imported PNG: import `assets/logo.png`, then `<Path>fs://game/logo.png</Path>`.
- **`<UpdateText>`** — accepts **`.sql` files as well as XML**. Several mods write
  text as `INSERT OR REPLACE INTO LocalizedText (Tag, Language, Text) VALUES (...);`
  — same table, free choice of format. Localize per-language with the `locale`
  attribute: `<Item locale="de_DE">text/de_DE/InGameText.xml</Item>` (no attribute =
  default/en_US).
- **`<UpdateDatabase>` is scope-sensitive**: in a `scope="shell"` group it writes the
  **frontend/config database** (input tables like `InputActions`,
  `InputActionDefaultGestures`, `InputContextConstraints` live there); in a
  `scope="game"` group it writes the gameplay database (`InterfaceModes` etc.).
  Registering a hotkey therefore needs a *shell*-scope UpdateDatabase.

**Scopes:** `scope="shell"` = main menu / options / create-game screens;
`scope="game"` = in-game HUD. A script that should exist in both places (options
registration, settings) must be listed in **both** a shell-scope and a game-scope
ActionGroup — every options-bearing mod surveyed does exactly that.

**LoadOrder is the compatibility contract.** Base UI defines components; mods that
decorate/patch must load after them, and mods that patch *other mods* must load after
those. Observed conventions: mods exposing an API to others use a low value
(Policy Yield Previews: 500, documented so consumers pick >500); ordinary
decorators use 1000–10000; aggressive whole-screen replacers use 100000. A
`<References>` entry on another mod (e.g. City Hall references JNR's lens mod)
declares soft ordering without a hard dependency.

**fs:// paths.** Your mod's files are addressable at
`fs://game/<mod-id>/<relative-path>` — this is the canonical form for
`Controls.define` content/styles, `Controls.loadStyle`, and cross-file imports
(`import { x } from 'fs://game/drongos-top-panel/ui/settings/settings.js'`).
ImportFiles-mounted assets are also reachable at the VFS root (`fs://game/logo.png`)
and, when shadowing, under the base module's path. In JS `import` statements, base
modules are absolute-rooted: `'/core/ui/...'`, `'/base-standard/ui/...'`.

UI-only mods set `<AffectsSavedGames>0</AffectsSavedGames>` so they can be
added/removed mid-campaign. `<EnabledByDefault>1</EnabledByDefault>` and
`<ShowInBrowser>1</ShowInBrowser>` are common. `<SpecialThanks>` and `<LastUpdated>`
are surfaced by mod-manager UI mods.

## The three patch techniques

Ranked from most to least compatible. Use the highest one that can do the job.

### 1. `Controls.decorate` — the official augmentation hook

The engine exposes a decorator registry keyed by component tag name. A decorator
class receives the live component instance and gets lifecycle callbacks:

```js
export class MyDecorator {
    constructor(component) {
        this.component = component;       // component.Root = its DOM root
    }
    beforeAttach() { }
    afterAttach() {
        // add buttons, listeners, DOM — the component is in the document now
    }
    beforeDetach() { }
    afterDetach() { }                     // remove window listeners here
}
Controls.decorate('panel-sub-system-dock', (c) => new MyDecorator(c));
```

All four methods must exist (even empty). Decorators from multiple mods coexist on
the same component — this is why it's the preferred technique. Useful decoration
targets seen in the wild:

- `'panel-sub-system-dock'` — the right-side HUD dock. The component has a real API:
  `panel.addButton({ tooltip, modifierClass, callback, class, audio, focusedAudio })`.
  This is THE way to give a custom screen an entry point.
- `'panel-mini-map'` — `component.miniMapButtonRow.appendChild(...)` to add minimap
  buttons.
- `'lens-panel'` — `component.createLayerCheckbox("LOC_MY_LAYER", "my-layer-id")` to
  add a lens-layer toggle to the minimap's lens panel.
- `'screen-options'` / options screens — see mod options below.

### 2. Prototype / instance monkey-patching

For changing *existing behavior* rather than adding alongside it. Grab the class via
the component registry, keep the original method, delegate:

```js
const def = Controls.getDefinition('yield-bar-entry');
const proto = def.createInstance.prototype;
const orig = proto.updateValueText;
proto.updateValueText = function (...args) {
    if (myCase(this)) { /* custom */ return; }
    orig.apply(this, args);
};
```

Variants observed working:
- **Singleton patch** — managers exported as instances are patched directly:
  `HotkeyManager.handleInput = function(...) {...}` (keep+call the original).
- **Registered-object patch** — a lens layer already registered can be fetched and
  its methods replaced: `LensManager.layers.get('fxs-worker-yields-layer').updateSpecialistPlot = function (info) {...}` (JNR's whole mod is this one patch).
- **Import the base module first** so the thing you patch is guaranteed registered:
  `import '/base-standard/ui/lenses/layer/worker-yields-layer.js';` before touching
  `LensManager.layers`. Bare side-effect imports pin load order within your script.
- izica's Advanced Yield Bar wraps its patches in a `setTimeout(..., 600)` to dodge
  init-order races — that works but is fragile; prefer `engine.whenReady.then(...)`
  or side-effect imports.

### 3. Whole-file replacement via ImportFiles

Ship a modified copy of a base file at the same relative path. Total control, but:
two mods replacing the same file = last-load-order wins, the other mod breaks
silently; and every game patch that touches the original silently diverges from your
copy. The big UI overhaul mods accept this cost. If you replace a file other mods
commonly patch (production chooser, diplo ribbon…), expect conflict reports.

## Custom screens and panels

A new screen is a web component: subclass `Panel`, register with `Controls.define`,
and open it through `ContextManager`.

```js
import Panel from '/core/ui/panel-support.js';
import { MustGetElement } from '/core/ui/utilities/utilities-dom.js';

class MyScreen extends Panel {
    onInitialize() { this.frame = MustGetElement(".my-frame", this.Root); }
    onAttach()     { /* wire buttons: el.addEventListener("action-activate", fn) */ }
    onDetach()     { /* unhook */ }
    onReceiveFocus() { super.onReceiveFocus(); /* NavTray setup */ }
}

Controls.define('screen-my-mod', {
    createInstance: MyScreen,
    description: 'My screen.',
    styles:  ['fs://game/<mod-id>/ui/my-screen.css'],
    content: ['fs://game/<mod-id>/ui/my-screen.html'],   // ImportFiles'd template
    attributes: [],
    classNames: ['w-full', 'h-full'],
});
```

Open/close with `ContextManager.push("screen-my-mod", { singleton: true,
createMouseGuard: true })` / `ContextManager.pop(...)`. A toggle checks
`ContextManager.getCurrentTarget()?.tagName == 'SCREEN-MY-MOD'`. Standard supporting
cast: `FocusManager` (focus), `NavTray` (controller hints), `Databind` (list
binding), `InputEngineEventName` + `inputEvent.isCancelInput()` for Esc/B-button
close handling, `fxs-activatable` elements firing `action-activate`, and Tailwind-ish
utility classes (`flex`, `absolute`, `text-xs`…) available throughout. The HTML
template can carry its own `<style>` block — sizes in `rem`.

### CSS gotchas inside the game UI

- **⚠ `font-style: italic` renders text INVISIBLE** — no error, no fallback, the
  element simply shows nothing. The shipped game fonts have no italic face and the
  engine doesn't synthesize an oblique; the entire base UI (core + base-standard)
  contains zero italic declarations, which is the tell. Verified in-game 2026-07-04
  (three styled-but-empty elements all shared `font-style: italic`; removing it made
  all three appear). De-emphasize with color/opacity/size instead.
- CSS **shorthand properties can be rejected** where the longhand works (reported by
  the Enhanced Town Focus Info changelog for a `text-decoration` shorthand). If a
  rule mysteriously doesn't apply, try the longhand form.
- **Flexbox `margin-left: auto` is silently ignored** (verified in-game 2026-07-04):
  the classic push-to-the-right idiom leaves the element hugging its neighbor. Use an
  explicit spacer element (`<span style="flex:1 1 auto">`) or `justify-content:
  space-between` instead.
- Render `[icon:…]`/`[B]`/`[N]` markup by assigning `el.innerHTML =
  Locale.stylize(locTagOrText)`; `textContent` + `Locale.compose` leaves the tokens
  as literal text.

### Custom art on a dock button

`addButton({ modifierClass })` reuses a base icon (the modifierClass keys a
`.ssb__button-icon.<class> { background-image: url("blp:…") }` rule) — so two mods
picking the same modifierClass get identical twin buttons. To ship your own art:
keep the modifierClass (it provides sizing/ring behavior), `ImportFiles` a
transparent PNG, and override with higher specificity keyed on the `class` you
passed to `addButton`:

```css
.ssb__button.tut-my-mod .ssb__button-icon {
    background-image: url("fs://game/<mod-id>/ui/icons/my-icon.png");
    background-size: contain; background-repeat: no-repeat; background-position: center;
}
```

Load it at decorate time with `Controls.loadStyle(...)` (the panel's
`Controls.define` styles only load with the panel). Leave ~15% transparent margin in
the PNG or the art pokes outside the circular button frame.

## Lenses and lens layers

`LensManager` (`'/core/ui/lenses/lens-manager.js'`) governs map lenses.

- **A lens** = named sets of layers: `{ activeLayers: Set, allowedLayers: Set }`,
  registered `LensManager.registerLens('my-lens', instance)`. Base layer names you'll
  compose: `fxs-hexgrid-layer`, `fxs-resource-layer`, `fxs-yields-layer`,
  `fxs-city-borders-layer`, `fxs-culture-borders-layer`. Base lenses:
  `fxs-default-lens`, `fxs-settler-lens`, `fxs-building-placement-lens`.
- **A layer** = an object with `initLayer()`, `applyLayer()`, `removeLayer()`,
  registered `LensManager.registerLensLayer('my-layer', instance)`.
- Add your layer to an existing lens:
  `LensManager.lenses.get("fxs-default-lens").allowedLayers.add("my-layer")`.
- Runtime control: `LensManager.setActiveLens(id)`, `toggleLayer(id)`,
  `enableLayer(id)`, `isLayerEnabled(id)`; react to lens switches via the
  `LensActivationEventName` window event (`event.detail.activeLens`), and to layer
  hotkeys via the `'layer-hotkey'` window event.
- Surface a checkbox for the layer with the `'lens-panel'` decorator (above).

Drawing on the map from a layer:

- **3D sprites/text at plots** — `this.yieldVisualizer.addSprite(location, textureName,
  offsets, {scale})`, `.addText(location, str, offsets, {fonts:["TitleFont"], fontSize,
  faceCamera:true})`, `.addYieldChange(...)` (see the worker-yields layer).
- **VFX at plots** — `const grp = WorldUI.createModelGroup("MyGroup");
  grp.addVFXAtPlot("VFX_3dUI_Tut_SelectThis_01", plotCoord, {x:0,y:0,z:0});
  grp.clear()`.
- Plot coordinates from an index: `GameplayMap.getLocationFromIndex(plotIndex)`.

## Interface modes and views

For UI states that own the whole interaction (placement cursors, choosers):

1. **Register the mode in the gameplay DB** (game-scope `UpdateDatabase`):
   `<InterfaceModes><Row InterfaceModeType="MYMOD_INTERFACEMODE_X" ViewName="MyView"/></InterfaceModes>`
2. **Add the JS handler**: `InterfaceMode.addHandler('MYMOD_INTERFACEMODE_X', handler)`
   where handler implements `transitionTo(old, new, context)`, `transitionFrom(...)`,
   and `handleInput(inputEvent)` (return `false` + `stopPropagation()` to consume;
   check `inputEvent.detail.status == InputActionStatuses.FINISH`, names like
   `'mousebutton-left'`, `'accept'`, `'sys-menu'`, `inputEvent.isCancelInput()`).
   Switch with `InterfaceMode.switchTo("MYMOD_INTERFACEMODE_X")` / `switchToDefault()`.
3. **Register the view** the mode names: `ViewManager.addHandler(instance)` with
   `getName()`, `getInputContext()` (`InputContext.World`), `getHarnessTemplate()`,
   `enterView()/exitView()`, and `getRules()` — a list of
   `{ name: "unit-flags", type: UISystem.World, visible: "false" }` toggles that
   hide/show HUD systems while the view is active. The harness template is a
   `<template>` of `fxs-slot` regions (top-left, bottom-center, …) appended to
   `document.body`, and is where your custom panels mount.

In `transitionTo`, modes typically also call `LensManager.setActiveLens(...)`,
`WorldUI.setUnitVisibility(false)`, `UI.Player.deselectAllUnits()` /
`deselectAllCities()`.

## Hotkeys

Three pieces, two scopes:

1. **Shell-scope `UpdateDatabase`** with input rows:
   ```xml
   <InputActions>
     <Row ActionId="open-my-panel" DeviceType="Keyboard" Name="LOC_MY_KEY" Description="LOC_MY_KEY"/>
   </InputActions>
   <InputContextConstraints>
     <Row ActionId="open-my-panel" ContextId="World"/>
   </InputContextConstraints>
   <InputActionDefaultGestures>
     <Row ActionId="open-my-panel" Index="0" GestureType="KBMouse" GestureData="KEY_F2"/>
   </InputActionDefaultGestures>
   ```
   This also makes the binding appear (and be remappable) in the game's key-binding
   options. Localize the `LOC_*` names in both scopes.
2. **Game-scope interception.** Two working styles:
   - Patch `HotkeyManager.handleInput` (keep the original; on
     `InputActionStatuses.FINISH` + your action name, call
     `HotkeyManager.sendHotkeyEvent(name)` — which dispatches a window CustomEvent
     `'hotkey-<name>'` — and return `false`).
   - Or register your own engine input handler:
     `ContextManager.registerEngineInputHandler({ handleInput(inputEvent) {...} })`
     and dispatch the CustomEvent yourself, guarded by
     `InterfaceMode.allowsHotKeys()`.
3. **Listen**: `window.addEventListener('hotkey-open-my-panel', fn)`. For lens-layer
   toggles use `HotkeyManager.sendLayerHotkeyEvent(name)` and listen for
   `'layer-hotkey'` checking `event.detail.name`.

## Mod options and the shared settings store

There is no official mod-settings API, so the community converged on a shared
convention — follow it exactly, because deviating breaks *other* mods:

**The Options "Mods" tab.** Register the category (idempotently — many mods do this)
and your options, in scripts loaded in **both shell and game** scopes:

```js
import '/core/ui/options/screen-options.js';   // ensure options screen loads first
import { CategoryType, Options, OptionType } from '/core/ui/options/model-options.js';
import { CategoryData } from '/core/ui/options/options-helpers.js';

CategoryType["Mods"] = "mods";
CategoryData[CategoryType.Mods] ??= {
    title: "LOC_UI_CONTENT_MGR_SUBTITLE",
    description: "LOC_UI_CONTENT_MGR_SUBTITLE_DESCRIPTION",
};

Options.addInitCallback(() => {
    Options.addOption({
        category: CategoryType.Mods,
        group: "my_mod_group",
        type: OptionType.Checkbox,        // dropdowns etc. also exist
        id: "my-option-id",
        initListener:   (info) => info.currentValue = mySettings.flag,
        updateListener: (_info, value) => mySettings.flag = value,
        label: "LOC_OPTIONS_MY_FLAG",
        description: "LOC_OPTIONS_MY_FLAG_DESCRIPTION",
    });
});
```

**⚠ Registration gotcha:** the stock `Options.addInitCallback` queues your callback
only for the options model's FIRST initialization — a late-loading mod's options
**silently never appear** (re-opening the screen replays only an internal *re-init*
list). The shipped community fix (Enhanced Town Focus Info) patches
`Options.addInitCallback` to push the callback onto BOTH `optionsInitCallbacks` and
`optionsReInitCallbacks` before registering. Verified as the cause of a
"my Options entry doesn't show but other mods' do" bug (2026-07-04).

The options screen renders a **group header from an auto-derived LOC key**:
`LOC_OPTIONS_GROUP_<YOUR_GROUP_ID_UPPERCASED>`. Define that string or players see the
raw key above your options.

**⚠ THE ONE-KEY localStorage RULE.** The engine's `localStorage` bridge is broken for
multiple keys: **if any mod writes a second localStorage key, reading breaks for
EVERY mod.** The convention (documented in Drongo's and beezany's source, enforced by
cleanup code that deletes stray keys): all mods share the single key `"modSettings"`,
holding one JSON object namespaced per mod:

```js
const all = JSON.parse(localStorage.getItem("modSettings") || "{}");
all["my-mod-id"] ??= {};
all["my-mod-id"]["myOption"] = value;
localStorage.setItem("modSettings", JSON.stringify(all));
```

Never `localStorage.setItem("my-own-key", ...)`. (Several mods carry migration code
to remove their own legacy extra keys — that's the scar tissue.)

**The more robust backend** is the engine's user-options store, usable alongside (or
instead of) localStorage:
`UI.setOption("user", "Mod", "my-mod.my-option", value)` +
`Configuration.getUser().saveCheckpoint()`; read with
`UI.getOption("user", "Mod", name)` (returns `null` if unset). City Hall writes both
and prefers `UI.getOption` on read. Game-side gameplay option groups also exist
(`UI.getOption("user", "Gameplay", ...)`).

## Persisting mod data

- **Per-user, global**: the `modSettings` localStorage object or `UI.setOption`
  (above). Survives across games; not tied to a save.
- **Per-game**: the `Catalog` serializer
  (`'/core/ui/utilities/utility-serialize.js'`) — `new Catalog("MYMOD")`, then
  `catalog.getObject("MY_ID")` gives an object with `write(key, string)`,
  `read(key)`, `getKeys()`. Detailed Map Tacks stores all tack data this way (JSON
  strings per plot key), reloading it on `Loading.runWhenLoaded(...)`. Deletion
  quirk: write `null` **and** remove the key from the object's `childrenIDs` set.
- UI state that only needs the session: module-level variables.

## The JS game API surface

Read access is broad; **write access to game state goes through operation requests**,
not direct setters. No official docs — but Policy Yield Previews ships TypeScript
ambient declarations (`types/engine.d.ts`, `types/GameInfo.d.ts` — 55KB of API
surface) that double as the best available reference; wire them into a `jsconfig.json`
for IntelliSense while developing.

Frequently used, all confirmed in shipping mods:

- **Players / player**: `Players.get(GameContext.localPlayerID)` (or
  `localObserverID`), `player.Stats.getNetYield(YieldTypes.YIELD_GOLD)`,
  `player.Stats.getYields()` (recursive breakdown tree), `player.Cities.getCities()`,
  `player.Units.getUnits()`, `player.Resources.getResources()`, `player.Culture`,
  `player.Diplomacy`.
- **City**: `city.Workers.getNumWorkers(false)`, `city.urbanPopulation`,
  `city.ruralPopulation`, `city.BuildQueue.getQueue()`,
  `city.Constructibles.getGreatWorkBuildings()`.
- **Static data**: `GameInfo.<Table>` (array-likes mirroring the gameplay DB:
  `GameInfo.Units.lookup(type)`, `GameInfo.Yields[i].YieldType`,
  `GameInfo.ProgressionTreeNodes`, row `$index` gives the hash/index used by APIs).
- **Map**: `GameplayMap.getLocationFromIndex(i)`, plus per-plot query methods.
- **Mutations** (the only way): `Game.PlayerOperations.sendRequest(playerID,
  PlayerOperationTypes.GRANT_TREE_NODE, { ProgressionTreeNodeType: node.$index,
  FullyUnlock: 1 })` — the cheat-panel mods are a catalog of available operations.
- **Text**: `Locale.compose("LOC_KEY", args...)`; text markup understood by UI
  strings: `[icon:YIELD_GOLD]`, `[B]bold[/B]`, `[n]` newline.
- **Events**: `engine.whenReady.then(fn)` (script start), `engine.on/off('EventName',
  fn, ctx)` and component-scoped `this.Root.listenForEngineEvent('EventName', fn,
  this)`. Real event names seen: `CityPopulationChanged`,
  `ConstructibleAddedToMap`, `PlayerTurnActivated`, `LocalPlayerTurnEnd`,
  `DiplomacyRelationshipChanged`, `DiplomacyDeclareWar`… Mods can also define their
  own bus events: `engine.trigger("MyCustomEvent")` + `engine.on("MyCustomEvent",...)`.
- `Loading.runWhenLoaded(fn)` — after game load (earlier and more reliable than the
  `'user-interface-loaded-and-ready'` window event, which lags ~1s).

A remarkable existence proof: Policy Yield Previews re-implements the **entire
GameEffects modifier/requirement evaluation pipeline in UI JS** (reads `GameInfo`
modifier tables, resolves collections to subjects, applies effect semantics, renders
predicted yields). If you need to *display* what a Modifier would do, that mod's
`scripts/` tree is the reference implementation.

### The attributed yield tree (`player.Stats.getYields()`)

Returns one recursive breakdown tree per yield (index-aligned with `GameInfo.Yields`)
— the engine's own attribution, exact to the decimal. Node shape: `{ value, type,
id, description?, steps?, base?, modifier? }`. **Walk `steps` plus `base`/`modifier`
only when they are objects** — they can also be plain numbers, and a naive walker
that wraps them silently drops most of the tree. Structure: player total → named
player-level sources (diplomacy actions appear by display name) → per-city subtree →
`From Buildings` (per building) / `From Improvements` (per plot) / deductions
(per-building maintenance, itemized).

**The label lever is the effect's `Tooltip` ARGUMENT** —
`<Argument name="Tooltip">LOC_MY_LABEL</Argument>` on the modifier — NOT the
`<String context="Description">` row. This is how the base game names its yield
contributions (the `Tooltip` argument appears on nearly every yield effect in the
base data: 126 uses on `EFFECT_CITY_ADJUST_YIELD`, 4-of-4 on
`…_YIELD_PER_POPULATION`, 35 on `EFFECT_PLAYER_ADJUST_CONSTRUCTIBLE_YIELD`, …).
Established by in-game experiment (2026-07-04, incl. fresh-game controls):

| Experiment | Result |
|---|---|
| `EFFECT_PLOT_ADJUST_YIELD` **with** a `Tooltip` arg | ✓ labeled leaf per plot (composed text), under "Additions" |
| `EFFECT_CITY_ADJUST_YIELD` **with** a `Tooltip` arg | ✓ labeled leaf (composed text), directly under city Income |
| Same two classes, **no** `Tooltip` | exact anonymous leaf — value right, name gone |
| `EFFECT_PLAYER_ADJUST_CONSTRUCTIBLE_YIELD` with a `Tooltip` arg | ✗ **still anonymous** (exact leaf under its building) — this class's `Tooltip` feeds a different surface; identify structurally or recompute |
| Any class with a `<String context="Description">` added | **still anonymous — `Description` rows do NOT label the tree** (they're for other UI surfaces) |
| warehouse / appeal effects | engine self-labels ("Warehouse Bonus", "Appeal Bonus") regardless |

**Binding timing:** the label text is **snapshotted when the modifier attaches** and
persists in the save — changing a `Tooltip` mid-campaign leaves the old text on
already-attached instances until they re-attach (requirements re-evaluating, or a new
game, which shows the new label from turn 1). Proven by observing a test label survive
its own revert across sessions. Only matters during development; shipped players never
see a label change mid-save.

The leaf `id` field is a runtime registry — **not** a `GameInfo.Modifiers` or
`ModifierStrings` index; don't join on it. To identify labeled leaves, match the
composed text (`Locale.compose` your Tooltip keys and string-compare; the tree stores
composed text, so this stays localization-consistent). For unlabeled contributions,
either match structurally (known position + expected value) or recompute from
`GameInfo.ModifierArguments` (`Amount`/`Percent`) × live state — the tree then serves
as a total-level validation.

## Cross-mod integration

- **Expose an API**: attach a frozen object to `globalThis`
  (`globalThis.MyModApi = Object.freeze({...})`) from a known-LoadOrder script;
  document that consumers must use a higher LoadOrder. Make every method no-throw
  (return `{ isValid:false, error }` instead).
- **Consume optionally**: `if (globalThis.LfYieldsPreview) { ... }` — no Dependencies
  entry needed; with a hard `<Dependencies>` entry the global is guaranteed present.
- **Detect other mods' components defensively**:
  `LensManager.layers?.has("bz-culture-borders-layer")` and pick base-game
  fallbacks otherwise (Drongo's Adjacency Lens integrates City Hall's layers this
  way without depending on it).

## ui-next: the second UI stack

Newer game versions are migrating screens to **`core/ui-next/`** — a SolidJS-based
component system (`core/vendor/solid-js/`), with `defineLegacyComponent` bridging to
the old registry. Consequences, all observed in current mods:

- Some screens now have **both** implementations (production chooser: old
  `ui/production-chooser/panel-production-chooser.js` *and*
  `ui-next/components/production-chooser-item.js`). Mods that restyle such screens
  must ship **both** the `ui/` and `ui-next/` replacements or the mod only half-works.
- ui-next components are compiled Solid output (`template()`, `createEffect`,
  `insert`) — patch by file replacement, not by prototype hooks; there's no
  `Controls.getDefinition` prototype to monkey-patch for them.
- Some services moved (e.g. `FocusManager` now at
  `'/core/ui-next/services/focus-manager.js'`). **Patches move import paths between
  game versions and silently break mods** — a moved options-screen module is a known
  cause of "my mod's options tab stopped appearing after the patch." Re-verify import
  paths against the installed `Base/modules/core/` after every game update.

## Debugging UI mods

- **Console output**: `console.log/warn/error` from UI scripts lands in the game's
  UI log (`Logs/` next to Modding.log). Errors thrown during a script's module load
  kill that script silently — a mod that "does nothing" often just threw on line 1
  (bad import path is the classic).
- **FireTuner** (Steam → *Sid Meier's Civilization VII SDK*) has a **Scripting
  Console** that evaluates JS against the live game — the fastest way to poke
  `Players.get(...)`, test selectors, or dump state. Input is single-line; wrap
  multi-statement probes in an IIFE one-liner.
- **Reload UI without restarting**: `UI.refreshPlayerColors?.()` aside, the known
  community lever is the cheat-panel "Reload UI" action; with Drongo's Cheat Panel
  installed (F8) you get it as a button. UI scripts re-run on reload — a much faster
  dev loop than relaunching, though `UpdateDatabase`/text changes still need a
  restart.
- **Inspect the real DOM**: there's no built-in inspector; log
  `document.querySelector(...)` results from FireTuner, or read the base module
  source in `Base/modules/core/ui/` + `Base/modules/base-standard/ui/` — grep there
  for component tag names (`Controls.define('panel-...'`) the same way you grep for
  EFFECT names in data modding.
