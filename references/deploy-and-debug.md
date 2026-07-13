# Deploy, test, and debug

The whole debugging problem in Civ VII is **observability**: a broken mod usually
produces no error. So the workflow is built around *proving* each state transition —
discovered, enabled, applied — rather than assuming it.

## Contents
- [Paths you'll use](#paths-youll-use)
- [Deploy + test loop](#deploy--test-loop)
- [The three states (and how to confirm each)](#the-three-states)
- [Reading the logs](#reading-the-logs)
- [Inspecting the Mods.sqlite registry](#inspecting-the-modssqlite-registry)
- [Dev settings (AppOptions.txt)](#dev-settings-appoptionstxt)
- [Live-poking the game: FireTuner (and the UI-mod dev loop)](#live-poking-the-game-firetuner-and-the-ui-mod-dev-loop)
- [The litmus mod](#the-litmus-mod)

## Paths you'll use

Base of the user-data folder (`%LOCALAPPDATA%` = `C:\Users\<you>\AppData\Local`):

```
%LOCALAPPDATA%\Firaxis Games\Sid Meier's Civilization VII\
├── Mods\            ← deploy your mod folder here
├── Logs\            ← Modding.log, Database.log (OVERWRITTEN each launch)
└── Mods.sqlite      ← the mod registry (locked while the game runs)
```

- Base game data to grep: `C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VII\Base\modules`
- A bundled `sqlite3.exe` is often at `%TEMP%\sqlitetools\sqlite3.exe`.

## Deploy + test loop

1. Keep a **dev source of truth** outside the game folder (e.g. `C:\dev\civ7-mods\my-mod`).
2. Deploy = remove the old deployed copy, then copy dev → `Mods\`:
   `powershell scripts/deploy-mod.ps1 <dev-folder>`. Deploy a **copied folder**, not a
   junction. Local mods apply fine — no Steam Workshop needed. Re-copying over a
   deployed mod is harmless; it doesn't desync the enable toggle.
3. Launch the game → **Add-Ons** menu → toggle the mod **Enabled**.
4. **Start a NEW game.** Most gameplay actions bind at game start; enabling mid-game or
   loading an old save won't apply them.
   ⚠ This extends to **updating** a mod: modifiers ADDED to an already-enabled mod after a
   game was created NEVER attach to that game's saves (litmus-proven 2026-07-11,
   gen2-featreq-litmus v1→v2): the `GameModifiers` → `EFFECT_ATTACH_MODIFIERS` bindings
   execute at game CREATION only; loading a save re-applies the modifier state stored in
   the save (the old modifiers keep working) but does not re-execute bindings for new
   modifier ids — even after a full app restart with "Applied all components" in
   Modding.log and a clean Database.log. Two consequences: (a) iterating on a litmus needs
   a fresh game per content addition, and (b) a shipped mod UPDATE with new modifiers does
   not affect players' in-progress games — new bonuses land on their next new game. Also
   note: the game process scans mod files at APP LAUNCH; quitting to the main menu does
   NOT re-read a redeployed modinfo — full exit + relaunch required to pick up a new
   version at all.
5. Verify it applied (next section) before concluding anything about your content.

After any edit, repeat 2–5. Editing files in the deployed copy directly also works, but
keeping a dev source + re-deploying avoids confusion about which copy is live.

## The three states

These are independent. A mod can be in an earlier state while *looking* like a later
one — that's the trap.

| State | Means | How to confirm |
|-------|-------|----------------|
| **Discovered** | Engine found the folder/modinfo. | `Modding.log` has a `Loading Mod …` line for it. |
| **Enabled** | Toggled on in Add-Ons. | Add-Ons UI shows it on; `Mods.sqlite` → `Mods.Disabled` is NULL/0. |
| **Applied** | Its action groups actually ran and inserted rows. | `Modding.log` lists it under **"Applied all components of enabled mods"** with its ` * <actiongroup>` lines, AND it's in the **"Target Mods"** list. |

**Only "Applied" means your rows ran.** The classic failure: a non-integer version
leaves a mod Discovered + Enabled but **never Applied** (dropped from Target Mods),
with no error. Always confirm Applied, e.g. `powershell scripts/check-applied.ps1 <mod-id>`.

> "Passed Validation" / FK validation in the log refers to the **whole database**, not
> proof your specific rows loaded. If the mod never applied, its rows were never
> inserted, so there was nothing of yours to validate.

## Reading the logs

`Logs\Modding.log` and `Logs\Database.log` are **overwritten every launch** — copy
them if you want to compare across runs.

- **Load/exclusion failure** (mod never applies): look for the mod in the "Target Mods"
  list and under "Applied all components of enabled mods." If it's absent there despite
  being enabled, it was excluded (check version first).
- **Runtime crash** (applied, then the game dies): `Modding.log` looks *clean* — it
  often ends with "Successfully reconfigured game" and then the process exits. A clean
  log that ends normally followed by a crash points at a runtime issue like the
  `OwnerRequirements`-on-constructibles crash, **not** a load failure.
- `Database.log` surfaces SQL/FK errors during data application — check it when rows you
  expected are missing.

## Inspecting the Mods.sqlite registry

`Mods.sqlite` records what the engine thinks about each mod (notably the stored
**Version** and the **Disabled** flag). It's **locked while the game runs**, so query a
**copy**: `powershell scripts/inspect-registry.ps1 [<mod-id>]` does the copy + query.
Manually it's:

```powershell
$src = "$env:LOCALAPPDATA\Firaxis Games\Sid Meier's Civilization VII\Mods.sqlite"
Copy-Item $src "$env:TEMP\Mods_copy.sqlite" -Force
& "$env:TEMP\sqlitetools\sqlite3.exe" "$env:TEMP\Mods_copy.sqlite" `
  "SELECT ModRowId, ModId, Disabled FROM Mods;"
& "$env:TEMP\sqlitetools\sqlite3.exe" "$env:TEMP\Mods_copy.sqlite" `
  "SELECT * FROM ModProperties WHERE Name='Version';"
```

- `Mods.Disabled`: NULL/0 = enabled, 1 = disabled.
- `ModProperties` holds the **Version the engine actually parsed** — if your modinfo
  says `1` but this shows `0`/empty, you've found a version-parse problem.

## Dev settings (AppOptions.txt)

`AppOptions.txt` sits next to the `Mods` folder (same directory as `Logs`). Options are
commented out with a leading `;` and default off — **remove the `;` and set the value to
`1`** to enable. The five worth turning on for modding (per the official dev-kit
"Getting Started" doc):

| Setting | Effect |
|---------|--------|
| `CopyDatabasesToDisk 1` | after a game starts, dumps the live DBs as `.sqlite` in the `Debug` folder (`gameplay-copy.sqlite`, frontend, localization) — the definitive way to see **every** table/column/value available, including engine-defined types not present in `Base/modules` XML. Overwritten on exit-to-menu / new game. |
| `EnableTuner 1` | lets **FireTuner** connect (see below). |
| `EnableDebugPanels 1` | in-game debug panels via the `` ` `` (backtick) key; also where `UIShortcuts` HTML panels appear. |
| `UIDebugger 1` | inspect the running UI's HTML/CSS/JS from **Google Chrome** (buggy in other browsers). |
| `UIFileWatcher 1` | hot-reloads already-loaded UI files as you edit them — no restart for UI-only changes (DB/text still need a full restart). |

`CopyDatabasesToDisk` is the answer whenever you need to confirm an effect/requirement
argument name or a table's real columns and grepping `Base/modules` isn't enough — the
runtime DB has the complete picture.

## Live-poking the game: FireTuner (and the UI-mod dev loop)

The official SDK (Steam → *Sid Meier's Civilization VII SDK*) ships **FireTuner**, whose
**Scripting Console** evaluates JavaScript against the running game — the same JS
environment UI mods run in. Fastest way to answer "what does the API actually return":

```js
(function(){const p=Players.get(GameContext.localPlayerID);return JSON.stringify(p.Stats.getNetYield(YieldTypes.YIELD_GOLD));})()
```

- Input is **single-line** — wrap multi-statement probes in an IIFE one-liner.
- A proven diff technique (from the Policy Yield Previews mod): dump
  `player.Stats.getYields()` (a recursive per-yield breakdown tree) before and after a
  change and diff the JSONs to see exactly which leaf moved. This debugs *gameplay*
  mods too — it shows whether your modifier's contribution actually landed in the
  yield tree, and under which node.
- For UI mods, a "Reload UI" action (available as a button in community cheat-panel
  mods) re-runs all UI scripts without relaunching the game — a much faster iteration
  loop. Database/text changes still need a full restart.

## The litmus mod

When *anything* is unclear, deploy `assets/litmus-mod/` first. It's a minimal valid
mod (integer version, single `AlwaysMet` `UpdateDatabase` action) whose only job is to
produce an **obviously visible** in-game change (it sets every map's natural-wonder
count to 20). If the litmus mod's effect shows up, your loading/deploy pipeline works
and the problem is in your content. If even the litmus mod does nothing, the problem is
environmental (deploy location, enable step, version, new-game step) — fix that before
touching modifiers. Isolating "is it the pipeline or my XML?" this way is the fastest
way out of a silent-failure rabbit hole.
