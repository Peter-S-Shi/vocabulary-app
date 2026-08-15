# Milestone 16 Closure — Exit Candidate

Status: **Exit candidate / pending independent review and merge. Milestone
16 is NOT yet Complete on `main`.**

This document records the evidence for Milestone 16 exit review. It is a
closure candidate, not a closure record: nothing here is authoritative until
the M16.2 PR is independently reviewed and merged.

## Milestone Summary

| Sub-milestone | Status | Authority |
|---|---|---|
| M16.0 — Desktop UI Design Baseline | Complete on `main` | [`DESIGN.md`](../../DESIGN.md) |
| M16.1 — Desktop Architecture Foundation | Complete on `main` (PR #21, `a1dc044721e9017d39842e96e0516a88a36d129f`) | [`docs/design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md`](../design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md) |
| M16.2 — Minimal Desktop Vertical Slice & M16 Exit | **Implemented / pending independent review** | this document + PR (see below) |
| **Milestone 16 overall** | **Exit candidate, not Complete on `main`** | — |

M16.2 base: synchronized `main` at
`f2c139f758962b0684271e11df55770675cc8cbb` (PR #22 merge commit).
Branch: `agent/m16-2-desktop-vertical-slice` (see the PR for the exact
reviewed head SHA; not pinned here to avoid a stale self-reference across
any pre-merge amendment).

## Vertical-Slice Capabilities Proven

Built under `src/ui_desktop/`, against the M16.1 contract, without
reopening the framework, state-taxonomy, package, or concurrency/theme
decisions:

1. **Bootstrap and shutdown** — `src/ui_desktop/app.py` (`build_application()`
   / `main()`, module entry point `python -m src.ui_desktop`) constructs a
   real `QApplication`, calls `src.db.init_db()` once, loads and applies the
   saved theme preference, builds `MainWindow`, and runs/shuts down the
   event loop cleanly. Streamlit's `app.py` and `src/ui_streamlit/` are
   untouched and remain independently runnable.
2. **Native shell and navigation** — `MainWindow` hosts Today and Entries as
   real native workspaces behind a `QStackedWidget`, switched through
   `AppState.request_navigation()` (the typed replacement for Streamlit's
   `set_page_focus`/`session_state` pattern). `AppState` is structurally the
   single source of truth for active workspace and shell mode: `MainWindow`
   renders whatever `AppState` already holds at construction (including an
   injected non-default workspace/mode), and every transition — whether
   requested through `MainWindow.show_workspace()` or directly through
   `AppState.request_navigation()` — is proven to leave `AppState` and the
   visible UI aligned (`M162ShellStateAuthorityTests`).
3. **Management ↔ Study chrome swap** — `AppState.enter_study_mode()` /
   `enter_management_mode()` toggle the management navigation toolbar and a
   minimal Study session-bar toolbar. Proven structurally through
   controller/shell APIs and tests (`tests/test_m16_2_desktop_vertical_slice.py`
   `M162NavigationAndChromeTests`), per the M16.2 prompt § 4 — no fake
   production Study workflow was invented; full Review/Quiz content remains
   M17 scope.
4. **Today/Home slice** — `TodayController.refresh()` calls the existing
   `src.learning_workflow.get_today_overview()` unmodified (the same call
   already proven in the M16.1 spike). `TodayView` renders a compact summary
   and Today's Learning Queue as the visually dominant area, following the
   `DESIGN.md` § 4.1 Command Center hierarchy at vertical-slice depth.
5. **Entries/Table-First slice** — `EntriesController` calls
   `src.entries.search_entries()` directly; `EntriesTableModel`
   (`QAbstractTableModel`) adapts the plain dict rows; `EntriesView` renders
   a real `QTableView` as the dominant surface with basic search and a
   bottom detail label. No raw SQL in the desktop UI; no parallel Entries
   service.
6. **Theme/token pipeline** — `theming/tokens.py` transcribes `DESIGN.md`
   § 11's Neutral Base and Calm Blue Light/Dark accent/semantic tables
   (paired background/foreground values, structurally encoding the § 9
   foreground-pair rule). `ThemeManager.apply()` is the single call site
   applying `QPalette` + QSS; switching Light ↔ Dark is proven at runtime
   without restart. The remaining three accent families are additive future
   work, not required for this slice (M16.1 contract § 14/§ 18).
7. **Durable desktop preferences** — `src/app_config.py:get_app_preferences_path()`
   resolves an env override, then a `LOCALAPPDATA`-based Windows path, then
   an XDG-style **config** directory (never a cache directory) off Windows.
   `src/ui_desktop/state/preferences.py` reads/writes Appearance + Accent as
   small local JSON, degrading safely to defaults on a missing or malformed
   file. No `vocab.db` write, no schema/app-data migration.
8. **Controller/state boundary** — durable domain truth stays in SQLite via
   unmodified `src/` core calls; durable presentation preferences live only
   in the preferences file; transient navigation/selection/filter/mode state
   lives in `AppState` and the two controllers. No flat
   `st.session_state`-equivalent dictionary was introduced.
9. **Background task infrastructure** — deliberately **not** added.
   Today/Entries core calls are fast local SQLite reads with no long-running
   operation; per the M16.2 prompt § 11 and the M16.1 contract § 18, this is
   a scope decision, not an oversight. `src/ui_desktop/tasks/` and
   `src/ui_desktop/services/` remain unpopulated, to be added only when a
   real M17+ workflow demonstrates the need.
10. **Navigation contrast fix** — the M16.2 human visual-acceptance pass
    found the Management-mode Today/Entries navigation actions rendering
    with extremely low contrast, resembling disabled controls. Root cause:
    once `QApplication.setStyleSheet()` is set at all, Qt's style-sheet
    engine paints every widget application-wide, and any widget left
    without an explicit color in the sheet can silently lose its
    QPalette-resolved foreground — `QToolButton` (what toolbar actions
    render as) had no explicit rule. Fixed entirely through the centralized
    `theming/theme_manager.py` QSS layer: explicit `QToolButton` /
    `:hover` / `:pressed` / `:disabled` rules resolving paired semantic
    tokens (`text_primary` default, `accent.soft` hover, `accent.pressed`
    pressed, `text_disabled` disabled) — no one-off hardcoded widget
    colors. `M162ToolbarContrastRegressionTests` proves the stylesheet
    explicitly targets every `QToolButton` state and that the resolved
    token pairs meet `DESIGN.md` § 12's contrast minimums (WCAG
    relative-luminance formula, the same methodology `DESIGN.md`'s own
    audit uses) for both Light and Dark.
11. **Desktop launcher and application icon** — `tools/setup_desktop_launcher.py`
    creates a Windows Desktop shortcut named "Vocabulary App" that
    double-click-launches `python -m src.ui_desktop` using the current
    Python environment, preferring `pythonw.exe` so a normal launch leaves
    no console window. It resolves the real per-user Desktop folder via
    .NET's `[Environment]::GetFolderPath('Desktop')` (not a hardcoded
    `$HOME\Desktop` guess, which breaks under OneDrive Desktop
    redirection — confirmed on the development machine) and shells out to
    `powershell.exe`/`WScript.Shell`, adding no new pip dependency. The
    generated `.lnk` is machine/checkout-specific, gitignored, and never
    committed. `assets/icons/vocabulary_app.ico` (generated by
    `tools/generate_app_icon.py`, a Calm Blue "V" monogram using the
    frozen default accent token pair) is a tracked repository asset used
    by both the shortcut and the `QApplication`/`MainWindow` window icon
    (`src/ui_desktop/app.py`). This is a development launcher, not M20
    packaging: no installer, no Nuitka/PyInstaller decision, no standalone
    executable, and the shortcut is not expected to survive an
    unregenerated repository move.

## SQLite Compatibility / Data-Safety Proof

`tests/test_m16_2_desktop_vertical_slice.py::M162SqliteCompatibilityTests`
uses a **temporary synthetic database**, never the user's personal
`data/vocab.db`, and exercises the **real desktop bootstrap path** — not
just the controllers in isolation:

1. creates/initializes a synthetic current database through
   `src.db.init_db()`, entirely independent of the bootstrap exercised
   below;
2. populates two representative Entries and a Collection through
   `src.entries.add_entry()` / `src.collections.create_collection()` /
   `add_entries_to_collection()`;
3. records `schema_version` / `app_data_version` before any desktop
   bootstrap code runs;
4. sets `VOCAB_APP_DB_PATH` to that database's path and calls the real
   `src.app_config.get_database_path()` — asserting it resolves to exactly
   that file — the same resolution the real application performs, not an
   assumed equivalence to a direct `db.DB_PATH` assignment;
5. constructs the desktop application through the real bootstrap,
   `src.ui_desktop.app.build_application()`, which performs its own
   `src.db.init_db()` call against the already-existing database exactly as
   `python -m src.ui_desktop` would;
6. verifies both Entries remain present and correctly surfaced through
   `MainWindow.today_controller`/`entries_controller` after that real
   bootstrap; and
7. verifies `schema_version`/`app_data_version` are byte-for-byte unchanged
   (`CURRENT_SCHEMA_VERSION` / `APP_DATA_VERSION` from `src/migrations.py`)
   — no destructive re-migration occurred.

`db.DB_PATH` is still assigned once, to the value `get_database_path()`
itself resolved in step 4 — required because it is a module-level constant
computed once at import time (the same constraint every test in this
repository's suite already works around; see
`tests/test_m15_3_audio_export.py`) — but the resolution value is no longer
asserted-by-construction; it is independently verified against the real
`VOCAB_APP_DB_PATH`-driven resolution path first.

## Test / Verification Results

```text
Focused M16.2 desktop tests: 38/38 (33 in tests/test_m16_2_desktop_vertical_slice.py
                                     + 5 in tests/test_m16_2_desktop_launcher.py)
M16.1 architecture-spike regression: 5/5 (tests/test_m16_1_architecture_spike.py)
Full repository suite: 204/204 (161 existing + 5 M16.1 spike + 33 M16.2 slice + 5 M16.2 launcher)
Python compile/static check (all tracked .py): passed
scripts/audit_architecture.py: 59 Python files scanned; 0 serious violations; 0 warnings
scripts/check_quiz_randomization.py: passed
tools/check_packaging_readiness.py: passed, only the expected local data/vocab.db exclusion warning
```

`tests/test_m16_2_desktop_launcher.py` covers `tools/setup_desktop_launcher.py`'s
pure logic (Python-interpreter selection, PowerShell-string quoting/building)
without touching the real Desktop or shelling out to `powershell.exe`, so it
stays part of the regular headless suite. The script's actual Windows
shortcut creation was verified manually (below), not via this file.

All tests run headless (`QT_QPA_PLATFORM=offscreen`); no physical display is
required for this verification.

## Real-Window Smoke Status

A real (non-offscreen) launch was attempted on the development machine:

- the native `windows` Qt platform plugin was used (confirmed via
  `QGuiApplication.platformName()`), with one real screen detected
  (1280×720);
- the application started, navigated to the Entries workspace with a
  synthetic entry loaded, ran for several seconds, and shut down cleanly
  with exit code 0 — no crash, no unhandled exception, no raw traceback.

**This proves the app starts and runs without crashing on the real
platform. It does not prove correct visual rendering.** An attempt to
capture a screenshot for direct visual inspection was aborted after it
captured the operator's live desktop instead of the application window
(Windows' foreground-lock policy prevented a background process from
reliably raising the window above the active foreground application); that
screenshot was deleted immediately and was not used as evidence here. No
further screenshot attempt was made.

A prior human visual-acceptance pass against this document's checklist
found one real defect — the Management-mode Today/Entries navigation
actions rendering with extremely low contrast — recorded and fixed above
under Capability 10. That fix has **not** been re-confirmed by a new human
visual pass; the checklist below must be re-run in full, not assumed to
pass because the known defect was addressed in code.

The Windows desktop launcher (Capability 11) was separately verified
end to end on the development machine, without a human visual pass, by
inspecting the generated shortcut's resolved properties and by launching
the exact `TargetPath`/`Arguments`/`WorkingDirectory` the shortcut records
(simulating a double-click) and confirming the process started and stayed
running:

```text
TargetPath:       ...\.venv\Scripts\pythonw.exe   (no console window)
Arguments:         -m src.ui_desktop
WorkingDirectory:  <repository root>                (verified to exist)
IconLocation:      assets/icons/vocabulary_app.ico,0 (verified to exist)
Launched process:  started, stayed running, cleanly stopped after verification
```

The test-generated shortcut was deleted immediately after verification; no
shortcut was left on the development machine's Desktop, and none was
committed (`.lnk` is gitignored — see § Deferred / Known Limitations).

Per the M16.2 prompt § 13, `DESIGN.md` § 19 visual acceptance is **not**
claimed from this evidence. A human visual-check pass is required before
final Milestone 16 sign-off:

- [ ] `python tools/setup_desktop_launcher.py` creates a Desktop shortcut
      named "Vocabulary App" with the repository's icon (not a generic
      Python/terminal icon);
- [ ] double-clicking that shortcut opens a visible native window without
      requiring PowerShell or manual typing, and without leaving a console
      window open;
- [ ] the same icon appears on the application window/taskbar entry;
- [ ] Today and Entries are both reachable from the navigation toolbar;
- [ ] the Today/Entries navigation actions are clearly readable at rest,
      and visibly (not just structurally) change on hover/press — this is
      the specific defect Capability 10 fixes; confirm it in both Light and
      Dark;
- [ ] the Entries table is usable at normal desktop window size (readable
      rows, functioning selection, search box works);
- [ ] switching between Light and Dark (e.g. by editing the preferences
      file's `appearance` value and relaunching) is visibly coherent and
      matches the Calm Blue palette in `DESIGN.md` § 11;
- [ ] navigation/chrome does not obviously violate the frozen Management
      Mode direction (§ 3, § 4.2 of `DESIGN.md`);
- [ ] no raw traceback or local file path is visible anywhere in the UI.

## Deferred to M17 / M18 / M20

Per the M16.2 prompt § 15 scope boundary, none of the following were
implemented and none are claimed complete: Review, Quiz, Mistake Book /
Proficient Pool practice, Collections management, Templates management,
Analytics, Import/Export workflows, linked-source UI, Audio Export UI,
backup/restore UI, complete Entries editing/batch parity, full Today
workflow parity, the remaining three accent families, a full
accessibility/hardening pass, Streamlit retirement, and installer/RC
packaging. No new learning, analytics, Card, or audio semantics were
introduced; no schema or app-data migration was added.

**The desktop launcher (Capability 11) is explicitly not M20 packaging**,
and this document does not claim otherwise: `tools/setup_desktop_launcher.py`
produces a local, machine-specific Windows shortcut around the existing
Python environment, not an installer or a standalone executable. It does
not choose or freeze a Nuitka/PyInstaller packaging decision (§ 17 of the
M16.1 contract already defers that choice to M20), and the shortcut is
expected to need regeneration after the repository is moved or the Python
environment changes — a real standalone build would not have that
limitation. M20 remains fully open.

## Explicit Non-Claims

This document does not claim:

- Milestone 16 is Complete on `main`;
- full desktop migration is complete;
- Streamlit is retired;
- Feature Freeze;
- Desktop Ready;
- Release Ready.

Milestone 16 remains an **exit candidate pending independent review and
merge** of the M16.2 PR. M17 is blocked until that review closes.
