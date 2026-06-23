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

1. Keep a **dev source of truth** outside the game folder (e.g. `…\civ7_mods\mods\my-mod`).
2. Deploy = remove the old deployed copy, then copy dev → `Mods\`:
   `powershell scripts/deploy-mod.ps1 <dev-folder>`. Deploy a **copied folder**, not a
   junction. Local mods apply fine — no Steam Workshop needed. Re-copying over a
   deployed mod is harmless; it doesn't desync the enable toggle.
3. Launch the game → **Add-Ons** menu → toggle the mod **Enabled**.
4. **Start a NEW game.** Most gameplay actions bind at game start; enabling mid-game or
   loading an old save won't apply them.
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

## The litmus mod

When *anything* is unclear, deploy `assets/litmus-mod/` first. It's a minimal valid
mod (integer version, single `AlwaysMet` `UpdateDatabase` action) whose only job is to
produce an **obviously visible** in-game change (it sets every map's natural-wonder
count to 20). If the litmus mod's effect shows up, your loading/deploy pipeline works
and the problem is in your content. If even the litmus mod does nothing, the problem is
environmental (deploy location, enable step, version, new-game step) — fix that before
touching modifiers. Isolating "is it the pipeline or my XML?" this way is the fastest
way out of a silent-failure rabbit hole.
