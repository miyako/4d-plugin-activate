![version](https://img.shields.io/badge/version-18%2B-EB8E5F)
![platform](https://img.shields.io/static/v1?label=platform&message=mac-intel%20|%20mac-arm%20|%20win-64&color=blue)
[![license](https://img.shields.io/github/license/miyako/4d-plugin-activate)](LICENSE)
![downloads](https://img.shields.io/github/downloads/miyako/4d-plugin-activate/total)

# 4d-plugin-activate
Move current application to front.

Activate brings the 4D application, or a specific 4D window, to the foreground. On macOS it uses `NSRunningApplication` to activate the whole 4D process; on Windows it uses native window-management calls (`ShowWindow`, `SetForegroundWindow`, `SetFocus`, and the `AttachThreadInput` foreground-stealing workaround) to restore and focus a target window, dispatched onto 4D's main thread via the plugin SDK's `PA_RunInMainProcess`.

**Important up front:** the single parameter this command takes is not always the window that ends up activated — see [Description](#activate-4d) below before relying on it to target a specific window.

| Command | Returns | Purpose |
|---|---|---|
| [`ACTIVATE 4D`](#activate-4d) | — | Brings the 4D application, or a specific window, to the foreground |

**Platforms:** macOS, Windows

---

## Requirements & platform notes

- **No return value.** `ACTIVATE 4D` is fire-and-forget — it does not report success or failure back to your 4D method.
- **Thread-safe**, per the plugin's manifest — safe to call from any process/thread; the actual native window calls are marshaled onto 4D's main thread internally.
- **The parameter is mandatory in syntax, but frequently unused at runtime.** On macOS it's never read. On Windows it's only consulted as a fallback — see the command description for exactly when.
- **No Linux support.** 4D itself has no Linux runtime; this is complete, not a gap.

---

## ACTIVATE 4D

### Syntax

```4d
ACTIVATE 4D(windowRef)
```

| Parameter | Type | Description |
|---|---|---|
| `windowRef` | Longint | A window reference. Mandatory as a parameter, but its value is only actually used in one specific fallback case on Windows (see Description) and is ignored entirely on macOS. |
| Result | — | This command does not return a value. |

### Description

**On macOS**, `ACTIVATE 4D` always activates the whole 4D application process (`NSRunningApplication currentApplication activateWithOptions:NSApplicationActivateIgnoringOtherApps`). It never targets an individual window, and `windowRef` is not read at all on this platform.

**On Windows**, the command first tries to find 4D's own main/MDI frame window:
- On 4D version 16 and later, this is 4D's main application window handle.
- On earlier 4D versions, it's found heuristically, by matching a window whose class name corresponds to 4D's install folder and whose owning instance matches the running 4D process. This heuristic can occasionally fail to find a match (e.g. with an unusual install path) — see [Error handling](#error-handling--troubleshooting).

If that lookup succeeds — which it normally does — **that window is activated, and `windowRef` is not consulted at all.** Only if the lookup fails does the command fall back to resolving `windowRef` to a native window handle and activating that window instead. In other words: under typical conditions, `ACTIVATE 4D(windowRef)` brings 4D's main application window forward regardless of what you pass for `windowRef`; passing a specific window reference only has an effect in the fallback case.

Activating a window (either the main window or the `windowRef` fallback) restores it if minimized, brings it to the top of the Z-order, and gives it keyboard focus — using the standard `AttachThreadInput` workaround needed to reliably steal foreground focus on Windows.

### Example

```4d
// Bring 4D to the front from anywhere in your code — the common case,
// where the main application window is activated and the parameter
// is effectively a placeholder
ACTIVATE 4D(0)
```

```4d
// Passing the current window's reference — only takes effect
// on Windows, and only if 4D's main window can't be found;
// otherwise the main window is activated instead
ACTIVATE 4D(WINDOW REF)
```

```4d
// Typical use: re-focus the 4D application after a long background
// process or an external tool may have taken focus away
CALL WORKER("main"; Formula(ACTIVATE 4D(0)))
```
The exact worker/process command you use to hand this off (`CALL WORKER`, a form method, a database method) depends on your project structure — the call itself is what matters here.

---

## Error handling & troubleshooting

- **No error is ever raised.** This command has no return value and no error-reporting path — if it appears to do nothing, there's nothing to catch; check the conditions below instead.
- **Exceptions inside the handler are silently discarded.** The plugin's dispatcher wraps every command in a catch-all that swallows any internal exception without reporting it. Because `ACTIVATE 4D` has no return value, this can't cause 4D to hang — but a failure here is invisible either way.
- **On Windows, `windowRef` is usually not the window that gets activated.** If you need a *specific* window brought forward and 4D's main window keeps getting activated instead, that's expected: the fallback to `windowRef` only triggers when 4D's own main-window lookup fails.
- **On pre-4D-16 Windows builds, main-window detection is heuristic and can miss.** It relies on matching a window class name to the application's install folder name; an unusual install path can cause the match to fail, which then falls through to the `windowRef` fallback.
- **On macOS, there's no way to target a specific window.** `ACTIVATE 4D` only ever brings the whole application forward on this platform — if you need to focus a specific window on macOS, this command isn't the tool for it.

---

## Quick reference

```4d
 // Bring 4D to the front (typical usage — main window is activated)
ACTIVATE 4D(0)

 // Windows-only fallback target if 4D's main window can't be found
ACTIVATE 4D(WINDOW REF)
```
