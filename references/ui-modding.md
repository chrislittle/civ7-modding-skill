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
- [Colors: leaders, player-color CSS, plot tinting, tree icons](#colors-leaders-player-color-css-plot-tinting-tree-icons)

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
- **Flat colored plot fills / edges** — `WorldUI.createOverlayGroup` + `addPlotOverlay`
  (see [Colors](#colors-leaders-player-color-css-plot-tinting-tree-icons) for the full
  recipe — this is how ACB-style "tint tiles by yield/type" lenses are drawn).
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
  strings: `[icon:YIELD_GOLD]`, `[B]bold[/B]`, `[n]` newline. **Parameterized LOC** uses
  `{1_Name}` placeholders (the suffix after `_` is just a label; positional) — the LOC row
  `"…up to {1_Max} this Age"` filled by `Locale.compose(key, maxValue)`. Pass an already-composed
  string as the arg (not a raw LOC key) to avoid double-resolution.
- **Progression / Triumphs / suzerain reads** (for read-only dashboards):
  - **Tree-node unlocked depth**: `Game.ProgressionTrees.getNode(playerId, nodeHash).depthUnlocked`
    (0 none / 1 base / 2 mastery). Look the node up in `GameInfo.ProgressionTreeNodes`; a node in a
    *hidden* (not-yet-revealed) tree still exists in `GameInfo`, so this returns 0 cleanly pre-reveal.
  - **Legacies / feats live**: `Players.get(pid).Legacies` component + `GameInfo.Legacies` (filter to
    your `LEGACY_*` prefix, scope to `Game.age`). Each row gives `.Name`, `.Description`,
    `.TriggerDescription`; check earned-state with the same helper the base Legacies UI uses. Lets a
    panel show "how to unlock" text (the trigger) and live earned/locked state without hardcoding.
  - **Suzerain city-states**: see [city-states-suzerain.md](city-states-suzerain.md#reading-suzerainties-from-a-ui-mod-js)
    (`Influence.getSuzerain()` + `GameInfo.CityStateTypes.lookup`).
- **Adding a switcher tab to an existing panel**: register the tab id in the panel's `TABS` list,
  add an `<fxs-activatable class="…-tab-<id>">` button in the HTML, and tag each card/row with
  `dataset.system = '<id>'`; the filter that shows `card.dataset.system == activeTab` does the rest.
  A `flex-wrap` filter row absorbs the extra button. Synthetic "cards" (plain objects with
  `{lane, system, nodeName, lines, unlockedDepth, requiredDepth}`) render through the same card
  path as real ones — handy for a bespoke tab (e.g. a per-item "what / how to get / have it?" list).
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

`getYields()` only answers for what **already exists**. To predict the yield of a
constructible **not yet built** (planner/overlay mods — Map Tacks, City Planner), you
must re-derive base + adjacency + owned-modifier yields from the data tables and live
map yourself — the full algorithm is in
[yield-preview-engine.md](yield-preview-engine.md).

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

## ⭐ The Dev Kit is the primary UI reference

Firaxis ships **"Sid Meier's Civilization VII Development Tools"** (a separate Steam
install under `steamapps/common/`). It has what the shipped game lacks:
- **`Reference/`** — the **uncompiled** UI source: `.tsx` / `.ts` / `.scss` (SolidJS
  + SCSS). Vastly clearer than the minified `.js` in `Base/modules`. When you need to
  know how a screen builds an element/class/icon, read the `.tsx`/`.scss` here first.
- **`Documentation/`** — Database Modding, modinfo, The Modifier System, Narrative
  Events (Markdown). Authoritative; check before reverse-engineering.
- **`Examples/`** — e.g. `fxs-new-policies` (a working new-traditions mod).
- **FireTuner** (live scripting console) + **SteamWorkshopUploader**.

Lesson (learned the hard way): **check the dev kit before declaring something
impossible or iterating blind.** Reading `screen-policies.scss` + `policy-card.tsx`
is what solved policy-card branding after many failed guesses.

## Asset path rule for icons & CSS `url()`

Reference an imported mod asset as **`fs://game/<modId>/<path-in-mod>`** — NOT a bare
filename. E.g. mod id `my-mod`, file `ui/icons/dock-icon.png` →
`fs://game/my-mod/ui/icons/dock-icon.png`. This holds for
`IconDefinitions` `<Path>`, CSS `background-image: url(...)`, `Controls.loadStyle`,
and JS `import`. PNGs used as data icons must also be `ImportFiles`'d in the modinfo
(dev-kit "Database Modding" doc). A bare `fs://game/logo.png` silently fails to load
(you get the frame/ring but a blank image) — this cost several debug cycles.

## Branding / restyling base cards (policy-card recipe — live-DOM-verified)

Base **policy/tradition cards do NOT expose per-card art to data** — the card icon
and background are computed in the UI JS. Confirmed dead ends (don't retry):
`IconDefinitions[TraditionType]` is never consulted; the card art derives from the
UI model's `TraitType`, which the engine **forces to `TRAIT_RANDOM`** for any
tradition not owned by a civ. So a modded `Traditions.TraitType` is ignored — native
recolor is impossible for modded non-civ cards. Brand them from JS instead.

> ⚠️ **Inspect the LIVE DOM before writing selectors — don't guess from the minified
> base `.js`.** The real class names differ from what source-reading suggests, and a
> card renders with DIFFERENT DOM in different states (see below). Use the Coherent
> debugger (port 9444) to dump the real structure and to prototype the fix by injecting
> into the running screen — see deploy-and-debug.md. Every selector below was verified
> that way; a whole session was burned guessing before.

**The recipe = a `UIScripts` decorator: MutationObserver → identify → restyle inline.**

1. **Observe + identify.** `MutationObserver(document.body, {childList,subtree})`,
   debounced rescan of `.policy-base-card`. There is **no TraditionType DOM attribute** —
   match each card by its displayed NAME: read `.font-title.uppercase.text-sm.font-bold`
   `.textContent` and look it up against `GameInfo.Traditions` (`Locale.compose(t.Name)`,
   filter your `TRADITION_MOD_` prefix). Appended child nodes + `data-*` attrs SURVIVE the
   SolidJS redraws on policy cards (⚠ unlike `tree-card-v2`, where injected children are
   wiped). Added *classes* get reset — use data-attrs or inline styles.

2. **⚠ Set colours INLINE from JS, never via CSS `var()`.** Coherent silently ignores
   `color`/`background: var(--x)` (the same dead-end the yield dashboards hit), so a
   CSS-class + custom-property theming approach renders nothing. Apply hex colours with
   `el.style.background = '#...'` etc. `Controls.loadStyle` is still fine for static
   positioning that doesn't vary, but anything lane/player-coloured must be inline.

3. **Swap the icon in place** (don't overlay a floating badge — it leaves the stock art
   poking out). The icon is TWO nested elements: `.policy-card-icon-backer` (the ~50px
   hexagon frame, `blp:accent_hex_*`) CONTAINS `.policy-card-icon` (the ~38px inner glyph,
   `blp:icon_*`, pulled left by `-ml-5` into the gutter). To brand: hide the inner
   `.policy-card-icon` (`backgroundImage='none'`) and **restyle the backer element itself**
   into your badge — `borderRadius:50%`, `border`, a dark `background`, and inject an inline
   `<svg>` logo child (inline SVG renders in Gameface — no PNG/rasterizer needed). Shift it
   a few px left (`transform:translateX(-Npx)`) so it clears the description text (which
   starts ~x:43), and give it a higher `zIndex` than any rail you draw so the rail passes
   behind it.

4. **⚠ Handle the SLOTTED state, not just the chooser list.** A card in the "available"
   list has ONE icon backer. When SLOTTED it gains a second `.policy-card-icon-backer.policy-grayscale`
   (the dual-slot "policy OR tradition" indicator), and the SLOT itself renders a greyscale
   placeholder socket BEHIND the card whose `-ml-5` icons poke out past your badge. Empty
   slots are greyscale placeholders too. For a fully clean look, **hide every
   `.policy-card-icon-backer.policy-grayscale` globally** (a card's own icon backer is
   non-greyscale, so it's untouched) — one robust rule, no per-card position guessing.
   **Test your branding in BOTH the available list AND slotted.**

⚠ **Coherent `querySelector` rejects `:not()`** (`SyntaxError: Invalid CSS selector`) —
filter in JS (`[...els].filter(...)`) instead.

Fragility is **cosmetic-only**: if a patch breaks the decorator, you lose the tint/logo,
never the card's function (it still renders + slots via the base UI). This is the intended
way to brand modded cards; a *dedicated custom slot type* does the opposite (it fails to
render at all — the government screen only supports Tradition/Policy/Crisis slot columns).

### Culture/tech TREE nodes (`tree-card-v2` in `screen-culture-tree`) — glow/highlight (⭐ 2026-07-13)
Worked example: a custom per-node "boost earned" glow. Hard-won specifics that differ from policy cards:
- **Node identity = the `type` attribute, and it is the NUMERIC node HASH, not the string.** Select
  `tree-card-v2[type]`; resolve the string via `GameInfo.ProgressionTreeNodes.lookup(Number(type))
  ?.ProgressionTreeNodeType` (filter e.g. `startsWith('NODE_MA_')`). `Game.ProgressionTrees.getNode
  (pid, hash)` / `getNodeState` / `Players.get(pid).Culture.getNodeCost(hash)` accept the hash.
- **⚠ On tree-card-v2, INJECTED CHILD ELEMENTS ARE DELETED on the next redraw** (unlike the policy-card
  case above where appended children survive — the tree re-renders its card subtree aggressively). A
  fill-over-the-card via an overlay `<div>` vanishes. **Only inline STYLE on the existing element
  survives**, and only if you REAPPLY it every scan. So highlight with `el.style.setProperty(
  'box-shadow', …, 'important')` (a glow: outer bloom + 1px edge + `inset` edge-tint hugs the rounded
  card; `outline` draws a hard RECTANGLE ignoring border-radius — looks crude). Paint the visible bar
  `.tree-card-hitbox` (the host/`.tree-card-bg` are `display:contents`/covered).
- **Realm matters:** a standalone game-scope UIScript loads into the ROOT/bootstrap document and can't
  reach the in-game tree screen; host the decorator in a UIScript group that runs in-game (proven: the
  same group as a working in-game panel/dock). Drive it with a top-level `requestAnimationFrame`
  poller (+ optional `Controls.decorate('screen-culture-tree')`), not lifecycle hooks.
- **Reading modded state per node:** a modifier can write a player property (`EFFECT_PLAYER_PROPERTY`,
  Key/Value/Operation=CHANGE) and the UI reads it back via `Players.get(pid).getProperty(Database.
  makeHash(key))` — confirmed working (base UI only ever uses `GameTutorial.getProperty`, but the
  player object exposes `getProperty` too). This is the clean way to surface "did my modded thing fire"
  to the UI when node data has no field for it (e.g. Civ7 commingles boost + research progress with no
  boost flag).

## Colors: leaders, player-color CSS, plot tinting, tree icons

Four independent color levers, distilled from shipping color mods (Atlas / Matt's
Colours / SIB Configurator = leader colors; Ash's Color-Coded Buildings = plot tint;
Orion's Bonus Icons+ = tree icons).

### 1. Leader / player map colors (data — `Colors` + `PlayerColors`)

A leader's map colors are two DB tables, edited game-scope (`UpdateDatabase`):

- **`Colors`** = named color definitions. `(Type, Color, Color3D)` where the two color
  columns are `"R,G,B,A"` strings in **0–255** (note: NOT hex, NOT 0–1). `Color` is the
  UI/flat color, `Color3D` the in-world one (usually identical). Add with
  `INSERT OR REPLACE INTO Colors (Type,Color,Color3D) VALUES ('MYCIV_PRIMARY',"100,44,148,255","100,44,148,255"), …`.
- **`PlayerColors`** = per-leader assignment, keyed `WHERE Type='LEADER_X'`. Columns:
  `PrimaryColor`, `SecondaryColor`, and three backup jerseys `Alt1PrimaryColor` /
  `Alt1SecondaryColor` … `Alt3…` (used when two players would clash). Each holds a
  `Colors.Type` string. Reassign with
  `UPDATE PlayerColors SET PrimaryColor="MYCIV_PRIMARY" WHERE Type='LEADER_X';`.

Convention that keeps colors legible: make secondary a near-white/near-black so icons
and text (which the engine derives from the pair — see below) stay readable.

### 2. Player-color CSS variables (JS/CSS — tint your own panels)

The engine exposes each player's colors as a small palette you can stamp onto any
element. This is how to make a mod panel/badge match the active player's colors.

- **API:** `UI.Color.getPlayerColors(playerId)` → the raw pair;
  `UI.Color.createPlayerColorVariants(pair)` derives, for `.primaryColor` and
  `.secondaryColor` each, `{mainColor, moreColor, lessColor, textColor, accentColor,
  tintColor}` plus a top-level `.isPrimaryLighter` flag (text/accent are auto-blended
  toward white/black for contrast — you don't compute contrast yourself).
- **Stamp helper — verified exports of `/core/ui/utilities/utilities-color.js`
  (2026-07-14, read from the install):** the function is **`applyPlayerColorsToElement(element,
  playerId)`** — NOT `realizePlayerColors` (that name does not exist here; guessing it
  wasted two debug rounds). It sets, on `element`: `--player-color-primary`,
  `--player-color-primary-more/-text/-accent` (note: **no `-less`**), the matching
  `--player-color-secondary(+-more/-text/-accent)`, and toggles class
  `primary-color-is-lighter`. The file also exports `getPlayerColorVariants(playerId)`
  (returns the variants **object** above, cached — use it to read `mainColor`/
  `isPrimaryLighter` yourself), `isPrimaryColorLighter(playerId)`, and the color
  converters `HexToFloat4 / ObjectToRgbaString / RGBAToString / numberHexToStringRGB`.
  (`UI.Player.get{Primary,Secondary}ColorValueAsString` — a plausible-looking direct
  API — did **not** resolve in a custom `Panel` context; use the `UI.Color`/utilities
  route.)
- **⚠⚠ `color: var(--x)` IS IGNORED in this Coherent build (the big one — e.g. a custom dashboard,
  2026-07-14, ~10 debug rounds).** A custom property set on an element *does* inherit to
  descendants (confirmed: `getComputedStyle(child).getPropertyValue('--x')` returns the
  parent's value), but a declaration like `.foo { color: var(--x) }` **does not use it** —
  the color collapses to inherited/black, and setting the var to any value changes nothing.
  So **CSS-variable theming for dynamic colors is a dead end here.** Symptom: your panel
  renders all-gray/black (not even the `var(--x, fallback)` fallback shows, because the var
  *is* defined — just ignored). Fix: **compute the color in JS and set it DIRECTLY as an
  inline style on each element** (`el.style.color = 'rgb(...)'`, `el.style.backgroundColor`,
  `el.style.borderColor`) after every render pass and on tab-switch. Inline styles are the
  only thing that reliably paints. Keep the CSS with hardcoded sane defaults so the base
  state is never gray; JS overrides on top.
- **⚠ `fxs-*` custom elements render their text/chrome INTERNALLY**, so host CSS `color`/
  `box-shadow` never reaches the painted pixels: `fxs-header` paints its own (gold) title
  text — you cannot recolor it from outside; `fxs-subsystem-frame`'s ornate frame is a
  **background image** (`blp:hud_sidepanel_bg` + filigree PNGs), NOT a border-image, so an
  inset `box-shadow` hides behind it and `fxs-border-image-tint` on the frame **washes the
  whole panel** (wrong lever). `fxs-border-image-tint` only tints an element that itself
  carries a `border-image-source` (`blp:`) — the base game makes a dedicated element for it
  (`.city-banner__stretch-bg`, `.diplo-ribbon__front-banner`). Recolor only the **plain
  `<div>`/`<span>`** you create in JS; leave the fxs chrome alone.
- **Legibility on a dark panel — use the engine's own `accentColor`, don't roll your own.**
  A civ's raw `primaryColor` is often dark (navy/purple/brown) and unreadable on a dark
  panel. Custom normalization is a rabbit hole (HSL-lightness ≠ perceived luminance → green
  reads bright, blue dark at the same L; brown is *dark orange* so any lift turns it orange;
  near-white civs desaturate to gray). The clean answer: **`createPlayerColorVariants(pair)
  .primaryColor.accentColor`** is the engine's pre-derived contrast-safe form (e.g. raw
  purple `rgba(55,0,101)` → accent `rgba(84,98,153)`) — muted, matches Civ7's restrained
  palette, legible on dark, and it's per-leader/persona exact (dual leaders like Friedrich
  each resolve correctly, no table to maintain). Parse its `r,g,b` and build your own
  `rgb()`/`rgba()` strings (the variant strings carry alpha `255` in 0–255 form). This was
  a pragmatic choice after rejecting custom normalization as a "mixed bag."
- **Where the data lives:** per-leader colors are `base-standard/data/colors/playercolors.xml`
  — a `Colors` block (named defs → `"R,G,B,A"`) and a `PlayerColors` block mapping each
  `LEADER_*` (and generic `PLAYERCOLOR_*` slots) to a `PrimaryColor`/`SecondaryColor`. You
  rarely need it though — `getPlayerColors(pid)` resolves the exact active color at runtime.
- **The `--player-color-*` route still works for plain elements** where you *can* use CSS:
  `applyPlayerColorsToElement(element, playerId)` sets `--player-color-primary(+-more/-text/
  -accent)` etc., and `fxs-border-image-tint: var(--player-color-primary)` tints a real
  border-image element (SIB's diplo-ribbon fix). But per the `color: var()` law above, don't
  rely on it for `color`; prefer direct inline styling for anything dynamic.

### 3. Tinting plots from a lens layer (`WorldUI` plot overlays)

For "color the map by <data>" lenses (ACB tints each tile by its building's dominant
yield). Inside a lens layer (`initLayer/applyLayer/removeLayer`, registered via
`LensManager.registerLensLayer` — see [Lenses](#lenses-and-lens-layers)):

```js
this.overlayGroup = WorldUI.createOverlayGroup("MyOverlay", 1); // (name, zIndex)
this.overlay = this.overlayGroup.addPlotOverlay();
// colors are float4 RGBA in 0–1: {x:r/255, y:g/255, z:b/255, w:alpha}
this.overlay.addPlots(plotArray, { fillColor: c, edgeColor: {x:c.x,y:c.y,z:c.z,w:0} });
this.overlay.clear();                 // wipe before each redraw
this.overlayGroup.setVisible(bool);   // show/hide the whole group
```

- `plotArray` = `[{x,y}, …]`. **Batch by color**: group all same-color plots and issue
  one `addPlots` per color (ACB builds a `Map` keyed by the color string) — far cheaper
  than per-plot calls across a full `GameplayMap.getGridWidth()×getGridHeight()` sweep.
- `fillColor` fills the hex; `edgeColor` outlines it — set one's `w:0` to draw only the
  other (fill-only, edge-only, or both = three render modes).
- Redraw on the data events you care about (ACB listens to `ConstructibleAddedToMap` /
  `ConstructibleRemovedFromMap`) and only when `this.visible`.
- Reading tile constructibles for the color decision: `MapConstructibles.getConstructibles(x,y)`
  → component IDs → `Constructibles.getByComponentID(cid)` → `GameInfo.Constructibles.lookup(item.type)`.

### 4. Recoloring / reassigning tech & civic tree bonus icons

Each tree-node bonus draws an icon via an **`IconAliases`** row (`ID` = the bonus's
modifier key like `MOD_AQ_TECH_WALL_STRENGTH`, `OtherID` = an icon definition). To
swap in your own art:

1. Register the art in **`IconDefinitions`** `(ID, Path)` with an
   `fs://game/<modId>/icons/<file>` path (extension optional; the PNG must also be
   `ImportFiles`'d). See [Asset path rule](#asset-path-rule-for-icons--css-url).
2. **Remap** the bonus to it in `IconAliases`. ⚠ **Gotcha (confirmed in Orion's
   source): `UPDATE` on an existing `IconAliases` row silently does nothing** — you must
   `DELETE FROM IconAliases WHERE ID='MOD_…';` then `INSERT INTO IconAliases (ID,OtherID)
   VALUES ('MOD_…','MY_ICON');`.
3. Run both via the modinfo **`<UpdateIcons>`** action — and register it in **both a
   `scope="shell"` and a `scope="game"` ActionGroup** (icons show in shell menus and
   in-game trees; miss one scope and half your icons revert).

This is the clean way to give a custom tech/culture-tree mod's fan-out bonuses legible,
color-coded icons instead of inheriting a generic base icon.

### 5. Custom-civ art & the "Art Fixes" compat shim

A full custom **civilization** ships art through four mechanisms (worked example: *Matt's
Civs: Ireland*, workshop `3506935009`):

- **`ImportFiles`** the raw assets — the `.png` **and** its extensionless twin (the engine
  references textures by bare ID). Import in **both** `scope="shell"` and `scope="game"`
  ActionGroups (shell = setup/civ-select, game = in-game); miss a scope and that half of
  the UI shows nothing.
- **`<UpdateIcons>` → `icons.xml`** registers them: `<Icons>` declares `ID` + `Context`
  (`DEFAULT` / `BACKGROUND` / `BACKGROUND_VERT`); `<IconDefinitions>` maps `ID`(+`Context`
  +`IconSize`) → a `Path`; `<IconAliases>` points a bonus at an existing icon. Path flavors:
  mod-relative extensionless (`<modId>/icons/<file>`), **`blp:<name>` = reuse a base-game
  texture** (`blp:CG_Rome_Colosseum_VERT`), or `fs://game/…` absolute.
- **`<UpdateVisualRemaps>` → `visual-remaps.xml`** reuses **3D in-world models** (distinct
  from the 2D `blp:` icons above): `<Row><Kind>BUILDING</Kind><From>BUILDING_MY_THING</From>
  <To>BUILDING_RAILYARD</To></Row>` gives a custom building/unit a real model with zero 3D
  art. (A sibling remap that renames the base type with a trailing `_` via `sql/icons.sql`
  frees the original ID for the custom one to remap onto.)
- Loading splash = `BACKGROUND`-context icons at `IconSize` 720/1080; age-transition
  cinematics = `.webm` via `movies.xml`.

**The catch — base UI silently drops modded-civ art in ~5 spots.** The engine's texture
pipeline prefixes custom asset paths with its atlas scheme `blp:`, which only resolves
built-in textures — so `blp:fs://…` and `blp:bg-panel-<civ>` render nothing. The community
dependency **Custom Civ Art Fixes** (Slothoth, workshop `3735898897`) is a generic
`<UIScripts>` shim (loaded in both scopes) that monkeypatches the fixes at runtime:

- `WorldUI.addBackgroundLayer` override → the post-select **splash**: if the texture is a
  registered custom civ, render the art as a full-screen **DOM overlay `<div>`** instead
  (engine layer → CSS fallback). Driven by a one-row table `CivsWithoutBackgrounds
  (CivilizationType, ArtPath)` the civ mod populates with a single `INSERT` (the only
  per-civ input needed; the other four fixes are automatic).
- `CSSStyleDeclaration.prototype.setProperty` override + a `MutationObserver` → globally
  rewrites `blp:fs://…`→`fs://…` and `blp:bg-panel-X`→ the mapped URL, catching inline
  styles on the **game-select chooser cards, age-transition cards, and diplomacy golden
  icon**.
- `Icon.getCultureIconFromProgressionTreeNodeDefinition` override → fixes the **shared
  culture-tree node icon** for anachronistic civs: when a `ProgressionTreeNodes` row is
  flagged **`CivInjectedIcon`**, it substitutes the player civ's `cult_<civ>` icon.

**When this matters:** only for a full custom **civilization**. A custom **progression tree
granted to all players** (e.g. a mod-wide custom civics/tech tree) is *not* a civ — the splash,
chooser-card, and diplomacy fixes never fire, and its nodes use plain `IconString` /
`IconAliases` (section 4), which already work without the shim. Reach for Art Fixes (and
`CivInjectedIcon`) only if you build an actual civ or a per-civ-injected culture node.

### 6. Mutating authoritative gameplay from a UIScript (the sanctioned RPC)

The common belief is "a mod's `<UIScripts>` (App UI isolate) can't change gameplay — the
gameplay isolate is walled." That's **only half true**, and the distinction is sharp
(verified in-game 2026-07-10, and by the shipping *Building Demolisher* mod, workshop
`3741851079`):

- **WorldBuilder debug map-writes are INERT/transient** from a UIScript.
  `WorldBuilder.MapPlots.setOwnership(playerId, loc)` and `…setResource(...)` report a change
  but it does not render, does not yield, and **does not survive save/reload**. Do not rely
  on them for durable state.
- **The sanctioned native-operation RPC IS authoritative and DURABLE.**
  `Game.PlayerOperations.sendRequest(playerId, "CREATE_ELEMENT" | "DESTROY_ELEMENT", args)`
  writes real, persistent game state from the UI isolate:

```js
// CREATE a rural district (auto-places the terrain-appropriate improvement, e.g. Farm):
Game.PlayerOperations.sendRequest(owner, "CREATE_ELEMENT",
  { Kind: "DISTRICT", Type: "DISTRICT_RURAL", Location: {x,y}, Owner: owner });
// CREATE a specific constructible/improvement:
Game.PlayerOperations.sendRequest(owner, "CREATE_ELEMENT",
  { Kind: "CONSTRUCTIBLE", Type: "BUILDING_…", Location: {x,y}, Owner: owner });
// DESTROY a district or constructible (get the id first):
const d = Districts.getIdAtLocation(loc);            // {owner, id}
Game.PlayerOperations.sendRequest(owner, "DESTROY_ELEMENT",
  { Kind: "DISTRICT", Owner: d.owner, LocalID: d.id });
// pre-check (optional diagnostic): returns {Success:bool}
Game.PlayerOperations.canStart(owner, "CREATE_ELEMENT", args, false);
```

- Helper reads: `Districts.getAtLocation(loc)` / `getIdAtLocation(loc)`,
  `district.getConstructibleIdsOfClass(ConstructibleClasses.IMPROVEMENT)`,
  `GameplayMap.getOwner(x,y)` (all work in UI ctx).
- **Trigger it from a unit button via the "fake Great Person" pattern** — the cleanest
  UI→action hook: give a unit `UNIT_CLASS_GREATPERSON` + `AvailableInTimeline="false"` and a
  `GreatPersonIndividuals` row with `ActionCharges` + `ActionRequires*` gates; its Activate
  press fires `engine.on("UnitGreatPersonActivated", cb)` in the UIScript. See
  [custom-units.md](custom-units.md) for the full unit data. (*Building Demolisher* grants the
  unit via a narrative story's `EFFECT_CITY_GRANT_UNIT`, human-only.)

**⚠ Hard limits — what this does NOT give you:**
- **`CREATE_ELEMENT` tiles are PLAYER-owned, not city-attached.** The tile shows *your*
  ownership + the improvement + tile yields, but **no city works or banks them** — it's an
  orphan outside every city's territory. The only levers that fold a plot into a city's
  *working* territory are `city.Growth.claimPlot` (gameplay-isolate only, a no-op in a
  UIScript) and CityCommands `EXPAND` / `PURCHASE` (C++-capped at the 3-hex city radius). So
  this is **not** a path to working ring-4/5 tiles — that wall stands (see
  [tile-ownership-and-radius.md](tile-ownership-and-radius.md)).
- Runs as the local player; **MP-desync is unverified** (the RPC is the deterministic
  sanctioned channel, so safer than WorldBuilder writes, but confirm before shipping MP).

**Good for:** live, durable **razing / rebuild** (create + destroy districts and
constructibles — a cleaner route than overbuild/REPLACE gymnastics; see
[razing-and-conquest.md](razing-and-conquest.md)), resource removal, and terrain/district
edits that must persist.
