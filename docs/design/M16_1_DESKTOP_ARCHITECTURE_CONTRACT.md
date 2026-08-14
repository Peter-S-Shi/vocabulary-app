# M16.1 — Desktop Architecture Contract

Status: **Implemented on branch `agent/m16-1-desktop-architecture-foundation`; pending independent review.**

This document is the frozen M16.1 architecture decision: desktop framework
selection, and the controller/view-state/core boundary that M16.2 must build
against. It is a decision record, not a framework tutorial and not the
desktop product itself.

Authority relationship: [DESIGN.md](../../DESIGN.md) remains the frozen
product/UI contract. This document decides *how* the selected framework
implements that contract; it does not reopen or reinterpret any DESIGN.md
decision. Where this document and `DESIGN.md` could conflict, `DESIGN.md`
wins and this document must be corrected.

---

## 1. Selected Framework

**PySide6** (Qt for Python), the official Python binding for Qt 6, maintained
by The Qt Company.

## 2. Decision Status

**Frozen for M16.2 and the desktop migration**, subject to the same
reopening standard as any other architecture decision: only on a direct,
recorded semantic or technical conflict, not preference drift.

## 3. Alternatives Considered

| Framework | Verdict | Why |
|---|---|---|
| **PySide6** | **Selected** | Official Qt binding, LGPLv3 available, mature dense-table/dialog/theming primitives, proven by spike. |
| PyQt6 | Rejected | Functionally near-identical Qt6 binding, but Riverbank Computing dual-licenses it only under GPLv3 or a paid commercial license — no LGPL option. The project's own license is not yet finalized ([README.md](../../README.md) § License); PySide6 gives the same capability without forcing a GPL/commercial choice merely to use the GUI toolkit. |
| Tkinter | Rejected | Bundled with Python (zero extra dependency), but has no dense model/view table widget comparable to `QTableView`/`QAbstractTableModel`, weak native theming, and no realistic path to DESIGN.md's semantic-token/Dark-Mode contract without extensive custom widget work. Already rated "Limited" in the Desktop Migration Plan §3; current evaluation confirms that rating still holds. |
| Toga / Briefcase (BeeWare) | Rejected for now | BeeWare is under genuine active development (Windows shortcut/MSI packaging fixes, Linux ARM64 promoted to fully supported, shipped July 2026), and Briefcase's packaging story is improving quickly. However, current primary-source evidence shows real desktop-relevant gaps in Toga's `Table` widget for this product's primary target platform (Windows): cell-widget support is a beta API currently available only on macOS, and macOS itself cannot customize table fonts — an unevenly-supported desktop feature set. No primary-source evidence was found of `Table` performance validated at a scale comparable to this product's realistic Entries-table size specifically on Windows/WinForms, unlike PySide6's directly documented `QTableView`/`QAbstractTableModel` behavior (§ 6). Rejected on that evidence gap plus the beta/macOS-only cell-widget limitation, not on a proven scalability defect — reasonable to re-evaluate if Toga's desktop data-widget maturity or published Windows-scale evidence changes. |
| Electron / webview wrapper | Rejected | Introduces a second runtime and toolchain (Node/Chromium) orthogonal to the existing Python/SQLite core, working against "replace the UI layer, preserve the learning engine" and the product's local-first single-runtime posture. Already rated "Conditional" in the Desktop Migration Plan §3; no new evidence changes that. |

No candidate was chosen or rejected because it resembles Streamlit, has the
smallest tutorial, or avoids one dependency.

## 4. Evidence / Technical Spike Result

A committed, headless-runnable spike proves the architecture-critical claims.
It is **not** product UI.

**Location:** [`tests/test_m16_1_architecture_spike.py`](../../tests/test_m16_1_architecture_spike.py)
(5 tests, `unittest`, skipped automatically when PySide6 is not installed).

**Executed:**

```text
QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe -m unittest tests.test_m16_1_architecture_spike -v
Ran 5 tests in 3.111s — OK
```

| Claim | Spike test | Result |
|---|---|---|
| PySide6 installs/imports in this repo's environment (Python 3.11.9 venv, Windows) | install + `import PySide6` (6.11.1) | PASS |
| `QApplication`/window construction, event processing, and clean close succeed without error | `test_native_window_starts_and_closes_cleanly` (`QApplication.instance()`/construction, `QMainWindow` show, `processEvents()`, close) — this proves object lifecycle and event-queue processing, **not** a full blocking `QApplication.exec()` run/quit cycle, which the spike does not exercise | PASS |
| Existing `src/db.py` + `src/app_config.py` open a temporary synthetic database unmodified | `setUp`/`tearDown` (`db.DB_PATH` swap + `db.init_db()`, same pattern as `tests/test_m15_3_audio_export.py`) | PASS |
| Representative reusable core functions callable without Streamlit | `test_core_functions_are_reusable_without_streamlit` (`src.entries.add_entry`, `src.collections.create_collection`/`add_entries_to_collection`/`get_collections`, `src.learning_workflow.get_today_overview`) | PASS |
| A synthetic dense-table model/view surface works | `test_dense_table_model_view_surface` (`QAbstractTableModel` + `QTableView`, 500 synthetic rows) | PASS |
| Runtime semantic-token style swap without restart | `test_runtime_semantic_token_style_swap` (two token maps resolved into different QSS strings, applied to a live `QWidget` in sequence) | PASS |
| Background worker → UI-thread signal handoff | `test_background_worker_to_ui_thread_signal_handoff` (`QThreadPool` + `QRunnable` worker, composed `QObject` signals, received by a `QObject` receiver on the main thread via Qt's automatic queued cross-thread connection) | PASS |

The full existing repository suite was re-run with the spike file present and
still passes: **166/166** (161 existing + 5 new), headless
(`QT_QPA_PLATFORM=offscreen`), no display required.

The spike deliberately does **not** build: the real Today/Home page, the real
Entries manager, production navigation, the real theme system, dialogs,
Review/Quiz UI, Collection management, Analytics UI, or Audio Export UI. It
uses synthetic data only and a temporary database that is discarded per test.

## 5. License / Distribution Finding

Primary-source evidence, gathered 2026-08:

- **PySide6 6.11.1** (latest at decision time) is licensed, per the official
  Qt for Python documentation (`doc.qt.io/qtforpython-6/licenses.html` and
  the Qt for Python Community Edition licensing pages), under the
  **LGPLv3 or GPLv3** open-source Community Edition, **or a commercial Qt
  license**. This is the authoritative statement used for this decision.
  (PySide6's PyPI package metadata additionally carries a `GPL-2.0-only`
  trove classifier alongside `LGPL-3.0-only`/`GPL-3.0-only`; that classifier
  list is package metadata, not the product's licensing documentation, and is
  not relied on here as the primary source.) The LGPLv3 option does not
  require this project to adopt GPL or purchase a commercial license merely
  to link against Qt, which matters because `README.md` § License currently
  states *"A final open-source license has not yet been selected."* PySide6
  keeps that decision open; PyQt6 would have forced it (GPLv3-or-commercial
  only, no LGPL — Riverbank Computing).
- **Python support:** PySide6 6.11.1 declares support for Python 3.10–3.14
  (`Requires-Python <3.15,>=3.10`), which covers this repository's `.venv`
  (Python 3.11.9).
- **Packaging:** Qt for Python ships an official `pyside6-deploy` tool
  (Nuitka-based) in addition to community-standard PyInstaller support; both
  are documented, current options for producing Windows executables.
- LGPLv3 obligations that M16.2+/packaging milestones must still honor:
  dynamic linking (not static-linking Qt into a way that defeats LGPL
  re-linking rights) and providing the license text / attribution — the same
  kind of obligation already tracked for the TTS stack in
  [`docs/policies/TTS_LICENSE_AND_ATTRIBUTION.md`](../policies/TTS_LICENSE_AND_ATTRIBUTION.md)
  and `THIRD_PARTY_NOTICES.md`. No blocker was found; this is a packaging-time
  bookkeeping item, not an M16.1 decision blocker.

## 6. Why PySide6 Fits `DESIGN.md`

- **Management Mode / Study Mode chrome swap** (DESIGN.md § 3): a single
  `QMainWindow` shell can swap its visible navigation/chrome per mode; Qt has
  no structural bias toward one persistent chrome the way some cross-platform
  toolkits do.
- **Table-First** (§ 4.2): `QTableView` + `QAbstractTableModel` is the
  standard Qt dense-data desktop pattern. The spike proves the pattern is
  *structurally* usable — correct row/column counts and cell-data resolution
  over 500 synthetic rows (§ 4) — not a measured performance/responsiveness
  benchmark. Community documentation/discussion (pythonguis.com, qtcentre.org;
  not official Qt documentation, and not independently re-measured in this
  repository) reports `QAbstractTableModel` remaining responsive to roughly
  100,000 rows via Qt's lazy row-fetching, well past this product's realistic
  Entries-table size; that figure is third-party reported evidence, not an
  M16.1 spike result and not an official Qt performance guarantee.
- **Utility/Dialog grammar** (§ 5): native `QDialog`, `QFileDialog`,
  `QMessageBox`, and custom dialogs cover Add/Edit, destructive confirmation,
  Import preview/commit, and progress/cancellation without fighting the
  toolkit.
- **Theme architecture** (§ 6–§ 13): `QPalette` (native widget chrome) +
  application-level QSS (custom-drawn components) together can represent
  Appearance × Accent, the four token layers, and the explicit foreground-pair
  rule natively — proven minimally by the spike's runtime QSS swap. See § 14
  below for the implementation boundary.
- **Keyboard & desktop behavior** (§ 17): Qt's native focus/tab-order,
  `Escape`/`Enter` handling, and keyboard navigation for tables and dialogs
  are framework-native, not something to hand-build.
- **Anti-patterns avoided** (§ 18): building the token system directly on
  `QPalette`/QSS (rather than adopting an opinionated third-party stylesheet
  library such as Material-style skins) avoids importing another product's
  visual identity (rounded cards, decorative gradients) that would conflict
  with DESIGN.md's frozen calm, desktop-native direction.

## 7. Why PySide6 Fits the Existing Python/SQLite Core

- Pure Python package; no change to `src/` core modules, SQLite schema, or
  `src/app_config.py` path resolution is required — the spike opens a real
  (temporary, synthetic) Vocabulary App database through the existing
  `src.db.init_db()` / `db.DB_PATH` / `src.app_config.get_database_path()`
  path unmodified.
- Reusable core functions are called exactly as Streamlit calls them today:
  plain Python arguments in, plain `dict`/`list`/dataclass results out (see
  § 4 evidence table). No new domain/persistence system was introduced.
- `QThreadPool`/`QRunnable` background work opens its own `sqlite3.Connection`
  per call through `src.db.get_connection()`, matching the existing
  open-per-call pattern already used throughout `src/` — no shared
  cross-thread connection is introduced (see § 13).

## 8. Desktop Package / Layer Structure

Frozen for M16.2. Names are the decision; empty/near-empty scaffolding is an
M16.2 implementation task (see § 19), not built in M16.1.

```text
src/ui_desktop/
    __init__.py
    app.py                 # QApplication bootstrap: create app, init_db() once,
                            # build MainWindow, run event loop, clean shutdown
    main_window.py          # QMainWindow shell: Management Mode chrome,
                            # Study Mode chrome swap, workspace host

    theming/
        tokens.py            # Python transcription of DESIGN.md § 8/§ 11 semantic
                              # tokens (paired background/foreground, per § 14)
        theme_manager.py      # (Appearance, Accent) -> QPalette + QSS; single
                              # apply point; runtime switch, no restart

    state/
        app_state.py          # AppState(QObject): active workspace, navigation
                              # handoff/focus payloads, live Appearance/Accent
        preferences.py         # load/save the local app-preferences file
                              # (JSON; NOT SQLite, NOT learning data)

    controllers/
        today_controller.py
        entries_controller.py
        (one per workflow, added incrementally in M16.2 / M17)

    views/
        today_view.py
        entries_view.py
        widgets/               # reusable desktop widgets: session bar, dialog
                              # shells, table chrome, empty-state widgets

    qt_models/
        entries_table_model.py  # QAbstractTableModel adapters wrapping plain
                              # dict/list results from src/ core calls
                              # (desktop-specific adapters; not domain models)

    tasks/
        worker.py              # QRunnable + composed QObject-signals worker
                              # base class; the shared progress/result/error/
                              # cancel contract (see § 13)

    services/                  # thin orchestration only; created empty/absent
                              # until a real M16.2+/M17 workflow demonstrates
                              # a genuine multi-step/transactional need (§ 6
                              # of the M16.1 prompt; see § 10 below)
```

`controller` and `view model` are treated as the same concept in this
contract (the Desktop Migration Plan uses both terms); this document
standardizes on **controller**.

## 9. Dependency Direction

```text
views/            --calls-->        controllers/
controllers/      --calls-->        src/ (core)  [+ ui_desktop/services/ where justified]
controllers/      --owns-->         state/ (transient) and state/app_state.py (shared/cross-screen)
views/, controllers/  --read-->     theming/ (resolved tokens/QPalette/QSS)
tasks/worker.py   --wraps calls to--> src/ (core) [+ services/]; never calls views/ or controllers/ directly
                                     (results flow back only via Qt signals)
src/ (core)       --never imports--> src/ui_desktop/*   (mirrors the existing
                                     Streamlit boundary rule in ARCHITECTURE.md)
```

Enforcement: `scripts/audit_architecture.py` is extended in this branch (see
§ 13 of the M16.1 prompt / Verification below) to treat `src/ui_desktop/` the
same way it already treats `src/ui_streamlit/`:

- **serious**: a core module (anything under `src/` outside `ui_streamlit/`
  and `ui_desktop/`) importing `PySide6` or `src.ui_desktop` — mirrors the
  existing Streamlit-in-core check.
- **warning**: `src/ui_desktop/*` importing Streamlit or `src.ui_streamlit`,
  or `src/ui_streamlit/*`/`app.py` importing PySide6 or `src.ui_desktop` —
  the two UI layers are independent during migration and should not casually
  depend on each other.
- the existing "UI imports sqlite3 directly" / "possible direct SQL in UI"
  warnings now also apply to `src/ui_desktop/*`, enforcing § 6 of the M16.1
  prompt ("Avoid raw SQL inside views").

This check currently passes with **0 serious, 0 warnings** across the
repository (no `src/ui_desktop/` files exist yet; the rule activates
automatically once M16.2 adds them).

## 10. Controller / View-Model Responsibilities

A controller per workflow (Today, Entries, Review, Quiz, Collections,
Templates, Analytics, Import/Export, Audio Export, Settings — added
incrementally, not all in M16.2):

- owns that workflow's transient state (selection, filters, sort order,
  temporary preview/dialog state, current Study/Quiz presentation state);
- calls `src/` core functions (or a thin `ui_desktop/services/` function
  where real multi-step orchestration is demonstrated) directly — most
  workflows are simple enough for a direct call, matching how
  `src/ui_streamlit/*_page.py` already calls core functions today;
- submits long-running work to `tasks/worker.py` and reacts to its signals;
  never blocks the UI thread on a core call expected to be slow;
- reads resolved tokens from `theming/` and requests navigation/focus
  changes through `state/app_state.py`; never hard-codes colors or
  navigation state itself;
- never receives or holds `PySide6` GUI objects passed *into* `src/` core
  calls — only plain Python arguments cross that boundary.

A thin `ui_desktop/services/` function is justified only when a desktop
workflow genuinely coordinates multiple core calls, a cancellation token, and
progress aggregation for one dialog/workflow (UI-side orchestration) — not
merely to "look layered." Reviewing the existing core module responsibilities
in `ARCHITECTURE.md`, most of the multi-step orchestration the desktop UI
will need (import validate→preview→confirm, linked-source refresh,
audio-export planning/retry) **already lives in `src/import_export.py`,
`src/linked_sources.py`, and `src/audio_export.py`** — the desktop
controllers can call those directly, the same way
`src/ui_streamlit/import_export_page.py` does today. **No `ui_desktop/services/`
file is created in M16.1**; the directory is reserved for M16.2+/M17 if a
real gap appears.

## 11. Durable vs. Transient State Boundary

### A. Durable domain / learning state — unchanged

Entries, Templates, Collections, Card identity/history, Quiz sessions/logs,
Review compatibility state, learning pools, linked-source metadata, analytics
evidence, audio-cache metadata — all remain authoritative in SQLite via the
existing `src/` modules listed in `ARCHITECTURE.md`. Desktop controllers call
those modules; they do not create a parallel copy, cache-as-truth, or second
persistence system.

### B. Durable application preferences — new, but not learning data

Appearance (`System`/`Light`/`Dark`) and Accent family
(Calm Blue/Sage/Indigo/Warm Neutral) are **UI/application preference state**,
per `DESIGN.md` § 6.1 ("must not mutate vocabulary data"). Decision: these
persist in a small local **JSON preferences file**, not in `vocab.db` and not
via a new schema migration — consistent with the M16.1 prompt's explicit
instruction not to add a migration for presentation state.

Ownership location (decision, not yet implemented — see § 19): extend
`src/app_config.py` with `get_app_preferences_path()`. Appearance/Accent are
**durable, persistent** preferences, not disposable/rebuildable data like the
audio cache — so this function must resolve to an OS-appropriate **persistent
configuration** location, not `get_audio_cache_dir()`'s cache-directory
pattern. It reuses the same *shape* (env-var override, then a
`LOCALAPPDATA`-based Windows path), but the non-Windows fallback must be an
XDG-style **config** directory (`$XDG_CONFIG_HOME` if set, else
`~/.config/vocabulary_app/preferences.json`) — never `~/.cache`, which a user
or the OS may clear at any time and would silently discard the user's saved
theme preference. `src/ui_desktop/state/preferences.py` owns reading/writing
that file; `src/` core modules never touch it. The exact resolver
implementation is an M16.2 task (§ 19); this section freezes only the
location *class* (persistent config, not cache) and the ownership boundary.

### C. Transient desktop/controller state — owned by controllers/state, not core

Examples (from the Desktop Migration Plan § 7, confirmed against the current
Streamlit `st.session_state` usage in `src/ui_streamlit/today_page.py`,
`common.py`, and equivalents in Review/Quiz/Entries pages): active
workspace/page, selected Entry IDs, selected Collection/Card, current
Study/Quiz presentation state, temporary import/template/linked-source
preview, audio-export selection and batch-progress presentation, temporary
dialog state, focus/navigation handoff, theme-control popover state.

**Concrete translation of the existing Streamlit "focus" pattern**, because it
is the single clearest transient-state migration the desktop layer must
reproduce faithfully: today, `src/ui_streamlit/common.py`'s
`set_page_focus(page_name, **focus_values)` writes arbitrary string-keyed
entries into the single flat `st.session_state` dict
(`today_page.py`'s `_save_review_focus`/`_save_quiz_focus`/
`_save_ordered_review_quiz_queue`), and the target page reads them back out.
The desktop replacement keeps the same behavior — "save a focus, switch
workspace, the target workspace picks it up" — but replaces the flat,
stringly-typed dict with:

- `AppState.request_navigation(workspace: str, payload: object) -> None`,
  emitting a `navigation_requested = Signal(str, object)` Qt signal that the
  shell (`main_window.py`) listens to and uses to switch the visible
  workspace;
- one small typed payload per workflow (e.g. `ReviewFocus(collection_id,
  card_number, card_id, source, reason)`, `QuizFocus(...)`, `QuizQueue(...)`),
  handed to that workflow's controller through a typed method (e.g.
  `ReviewController.apply_focus(payload: ReviewFocus)`) instead of reading
  loosely-named session_state keys back out.

`st.session_state` behavior is not moved into `src/` core modules under a new
name; it is re-expressed as typed controller/`AppState` state, consistent
with the M16.1 prompt § 5's explicit prohibition.

## 12. Application-Preference Ownership

Summarized from § 11.B: `src/app_config.py` (`get_app_preferences_path()`,
using an env-var-override + platform-path shape analogous to
`get_audio_cache_dir()` but resolving to a **persistent config** location,
not a cache location) + `src/ui_desktop/state/preferences.py` (read/write of
Appearance/Accent, and any other genuinely durable *presentation* preference
such as last window geometry). Explicitly **not** SQLite, **not** a schema
migration, **not** `app_data_version`-tracked state — it carries no learning
semantics and must never be conflated with `src/migrations.py`'s registry.

## 13. Background Task / Progress / Cancellation Model

This is a local, single-user desktop application. The decision is the
smallest framework-native pattern that safely supports current needs — not a
generalized job framework.

**Pattern (proven by the spike):** `QThreadPool.globalInstance()` +
`QRunnable` worker + a composed `QObject` signals object
(`progress`, `partial`, `finished`, `failed`), connected to a `QObject`
living on the UI thread (a controller). Qt's automatic connection type
detects the cross-thread case and queues signal delivery onto the receiver's
(UI) thread event loop — the spike's
`test_background_worker_to_ui_thread_signal_handoff` proves this concretely,
using a real `QObject` receiver rather than a plain Python callable (a plain
function/lambda has no thread affinity and would execute in the worker
thread, which would *not* prove the UI-safe handoff this rule requires).

**Rules, frozen for M16.2+:**

- a worker's `run()` calls an existing `src/` core function (or a
  `ui_desktop/services/` orchestration function per § 10) — never raw SQL,
  never a GUI object passed into core code;
- each worker opens and closes its **own** `sqlite3.Connection` via
  `src.db.get_connection()` inside the worker thread; a connection is never
  shared between the UI thread and a worker thread (Python's `sqlite3`
  connections are not safe to use across threads by default, and no core
  module sets `check_same_thread=False`);
- cancellation is cooperative: a worker accepts an `is_cancelled()` callable
  (backed by e.g. `threading.Event`) and passes it down only where the
  called core function already supports incremental/interruptible or
  partial-result work (the M15.3 batch audio-export plan/retry contract is
  the natural first fit — see `src/audio_export.py`); where a core function
  has no such hook, the desktop layer must not invent new cancellation or
  partial-success semantics inside `src/` to manufacture one (per the M16.1
  prompt § 7) — it can only honestly report "this step cannot be cancelled";
- errors are never raised across the thread boundary as raw exceptions to the
  View — see § 15.

No generalized distributed job queue, retry-with-backoff framework, or
persisted task history is introduced. `tasks/worker.py` is the one shared
building block; workflow-specific behavior (import batches, linked-source
refresh, audio export batches) stays in the existing core contracts.

## 14. Theme / Token Implementation Boundary

`DESIGN.md` is not reopened or reimplemented in full here (per the M16.1
prompt § 8). This section decides only the **plumbing**.

- `theming/tokens.py` is a direct Python transcription of `DESIGN.md` § 8 and
  § 11 — the Neutral Base table, the four Accent Families (Light/Dark), and
  the Semantic State tokens. `DESIGN.md`'s hex values remain the numeric
  authority; `tokens.py` must be kept in sync with it, not the reverse.
- Accent/foreground pairs are stored as **paired** values (e.g. an
  `AccentPrimaryPair(background=..., foreground=...)`-shaped record), not as
  independent flat keys — this makes `DESIGN.md` § 9's explicit
  foreground-pair rule a structural property of the token type, not just a
  convention someone could violate by combining an unrelated background and
  foreground.
- `theming/theme_manager.py` resolves `(Appearance, Accent)` into:
  1. a `QPalette` for native widget chrome (window/base backgrounds, window
     text, highlight/highlighted-text, placeholder text, etc.) — mapped from
     the neutral/accent token tables; and
  2. an application-level QSS stylesheet for custom-drawn components that
     need finer control than `QPalette` roles offer (selected-row treatment,
     `quiz-correct`/`quiz-wrong` chips, outlined destructive buttons, etc.).
- `ThemeManager.apply(appearance, accent)` is the **single** call site that
  invokes `QApplication.setPalette(...)` and `QApplication.setStyleSheet(...)`
  — called once at startup from the loaded preference (§ 12), and again
  whenever Quick Theme Control / Settings → Appearance changes selection. The
  spike's `test_runtime_semantic_token_style_swap` proves the underlying
  mechanism applies immediately, without an application restart, matching
  `DESIGN.md` § 6.1.
- Component code (`views/*`, `controllers/*`) must resolve colors only
  through `theming/`; no inline hex/RGB values in view code, mirroring
  `DESIGN.md` § 8's "never per-widget hard-coded colors" and the real bug
  `DESIGN.md` § 11.4 documents from the web design pass.

**Not done in M16.1** (explicitly deferred to M16.2, per the M16.1 prompt's
scope boundary): the real, complete transcription of all four accent
families × Light/Dark from `DESIGN.md` § 11 into `tokens.py`; a working Quick
Theme Control popover or Settings → Appearance screen; exact
typography/spacing numeric values (`DESIGN.md` § 15/§ 20 already flags these
as framework-dependent and provisional).

## 15. Error / Result Mapping

- `src/` core functions are unchanged: they keep raising Python exceptions or
  returning plain result objects exactly as they do for Streamlit today.
- `tasks/worker.py`'s `failed` signal carries a small structured payload
  (context, a safe user-facing message, and the original exception) rather
  than letting a raw exception cross into view code — mirroring the existing
  `src/ui_streamlit/error_handling.py:show_unexpected_error(context,
  user_message)` pattern.
- A shared desktop-side error-reporting helper logs the full exception via
  `logging.getLogger("vocabulary_app.ui")` (the same logger name Streamlit
  already uses, so log tooling does not need to distinguish UI layer) and
  returns/display only the safe message — raw tracebacks or local file paths
  are never shown in the UI, consistent with `AGENTS.md`'s privacy rule and
  `DESIGN.md` § 5's "what happened / what did not change / what to do next"
  error contract.
- Partial-success results (e.g. `src/audio_export.py`'s per-Card
  succeeded/skipped/failed/unresolved outcome set) pass through from core to
  controller to view unchanged — the desktop view renders them per
  `DESIGN.md` § 5's Partial Success rule; the underlying data contract is not
  reinvented.

## 16. Testing Strategy

- The existing 161-test core/Streamlit suite is unaffected and requires no
  new dependency; it continues to run with plain `unittest` and no PySide6
  installed.
- Desktop tests live alongside existing tests under `tests/`, using the same
  `unittest` style (no new test framework introduced). Any test that touches
  real Qt objects is guarded with
  `@unittest.skipUnless(PYSIDE6_AVAILABLE, ...)`, so environments without
  `requirements-desktop.txt` installed skip rather than fail — see
  `tests/test_m16_1_architecture_spike.py`.
- Controllers should stay callable and assertable without a running GUI event
  loop wherever practical (plain method calls, signal-capture assertions),
  minimizing what must go through a real `QApplication`.
- Tests that do need a real `QApplication`/widgets run headless via
  `QT_QPA_PLATFORM=offscreen` (proven in the spike) — no physical display is
  required for CI or for this non-interactive coding-agent environment.
- Headless testing proves **structural** correctness (row counts, signal
  delivery, stylesheet text, core-call results) — it does not prove
  `DESIGN.md` § 19's **visual** acceptance criteria (contrast, real pixel
  layout, actual on-screen appearance). At least one real on-screen manual
  pass remains necessary before M16.2/M17 sign-off against the visual
  contract; this document does not claim headless tests satisfy that.

## 17. Packaging Implications

- `pyside6-deploy` (Nuitka-based, official) and PyInstaller are both
  documented, current, viable options for producing a Windows executable;
  the concrete choice is deferred to the packaging milestones (M20), per the
  M16.1 prompt's scope (`DESIGN.md` § 20 already defers packaging-specific
  behavior the same way).
- **Known cost:** the full `PySide6` distribution is large — the installed
  wheel set for this spike was `PySide6` + `PySide6_Essentials` (~78MB) +
  `PySide6_Addons` (~169MB) + `shiboken6`, i.e. far more Qt modules (Qt3D,
  WebEngine, Multimedia, etc.) than this application needs. A packaging
  milestone should trim to only the required Qt modules (`QtWidgets`,
  `QtCore`, `QtGui`, likely `QtSvg` for icons) via Nuitka/PyInstaller
  excludes rather than shipping the full Addons set. This is a deferred
  packaging concern, not an M16.1 blocker.
- LGPLv3 dynamic-linking and attribution obligations apply at packaging time
  (§ 5); no blocker exists today, but `THIRD_PARTY_NOTICES.md` will need a
  Qt/PySide6 entry before any release candidate, alongside the existing TTS
  entries.
- `requirements-desktop.txt` (new, additive) keeps desktop-only dependencies
  out of the base `requirements.txt` Streamlit path, so packaging/dependency
  strategy for the Streamlit compatibility UI is unaffected.

## 18. Known Limitations / Deferred Decisions

- The full `tokens.py` transcription (all 4 accent families × Light/Dark),
  a working theme-control UI, and exact typography/spacing numbers are not
  implemented — only the plumbing pattern is decided and spike-proven (§ 14).
- `ui_desktop/services/` has no real content yet; whether Import,
  Linked-Source refresh, or Audio Export need genuine desktop-side
  orchestration (vs. direct controller → core calls) will only be known once
  M16.2/M17 builds those workflows.
- The exact shape of per-workflow focus payloads (`ReviewFocus`, `QuizFocus`,
  `QuizQueue`, etc. in § 11.C) is illustrative of the pattern, not a frozen
  field list — M16.2/M17 should finalize each payload against the actual
  Streamlit `session_state` keys it replaces for that workflow.
- Packaging tool choice (Nuitka via `pyside6-deploy` vs. PyInstaller) and Qt
  module trimming are explicitly deferred to later milestones (§ 17).
- Automated testing proves structural, not visual, correctness (§ 16); a
  manual on-screen pass against `DESIGN.md` § 19 remains a future
  requirement.
- This decision was made without a graphical display attached to the
  automated verification session; the native-window spike test only proves
  headless start/stop, not on-screen rendering. A real windowed run before
  M16.2 sign-off is recommended as a cheap additional confidence check, not
  a blocker.

## 19. M16.2 Implementation Contract

M16.2 (Minimal Desktop Vertical Slice & M16 Exit) must build against this
decision without reopening it:

1. Scaffold `src/ui_desktop/` per § 8 (empty/minimal stubs where a workflow
   is not yet needed).
2. Implement `app.py` bootstrap: construct `QApplication`, call
   `src.db.init_db()` once, build `MainWindow`, run the event loop, shut down
   cleanly.
3. Implement a minimal `MainWindow` shell proving the Management Mode ↔
   Study Mode chrome swap exists structurally (full Study Mode polish is not
   required in M16.2).
4. Implement `theming/tokens.py` with real `DESIGN.md` § 11 values (at
   minimum Calm Blue Light/Dark, to prove the pipeline end-to-end) and a
   working `ThemeManager.apply()`; a full Quick Theme Control popover can
   wait, but the apply mechanism must be exercised (even if only
   programmatically/by a settings stub).
5. Implement `TodayController` + a minimal Today view calling
   `get_today_overview` (the same call already proven in the spike) — enough
   to satisfy the M16.2 exit requirement of proving Today/Home through
   reusable core calls, not full Command Center polish.
6. Implement `EntriesController` + a minimal Entries view + an
   `EntriesTableModel` (`QAbstractTableModel`) calling `src.entries` list/
   search functions — enough to prove the Table-First dense-table pattern
   through reusable core calls, not full Table-First polish.
7. Promote `tasks/worker.py` from spike-only test code into a real reusable
   `src/ui_desktop/tasks/worker.py` module if the M16.2 vertical slice
   includes any long-running call; optional if Today/Entries alone do not
   need it yet.
8. Implement `src/ui_desktop/state/preferences.py` and the
   `src/app_config.py` `get_app_preferences_path()` addition (§ 12), storing
   at minimum Appearance + Accent.
9. Re-run `scripts/audit_architecture.py` (already extended for
   `src/ui_desktop/` in this branch) and keep it at 0 serious violations.
10. Prove existing SQLite data opens without destructive conversion using a
    **synthetic** representative database, never the user's personal
    `data/vocab.db` (per the M16.1 prompt § 13 and `AGENTS.md`).
11. Run the Milestone 16 exit-criteria checklist items owned by M16.2 in
    `ROADMAP.md` and record final exit verification evidence.

M16.2 must not reopen the framework choice, the state taxonomy, the package
layout, or the concurrency/theme boundary decided here without a recorded
direct conflict.
