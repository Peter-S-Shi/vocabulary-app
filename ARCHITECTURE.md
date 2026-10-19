# Architecture

Vocabulary App is a local-first Python application with a framework-independent core, a SQLite persistence layer, a native PySide6 desktop UI (`src/ui_desktop/`) as the primary product surface, and a retained Streamlit compatibility/reference UI (`app.py`, `src/ui_streamlit/`).

## Layers

| Layer | Allowed Responsibilities | Forbidden Responsibilities |
|---|---|---|
| Core modules (`src/*.py`) | SQL, validation, business rules, reusable query helpers, import/export, backup, and unified data-root/relocation/locking operations | PySide6 or `src.ui_desktop` imports, Streamlit widgets or `session_state`, UI page rendering |
| Native Desktop UI — Primary (`src/ui_desktop/`) | Qt main window, workspace views/widgets, Qt table/list models, controllers owning transient view/workflow state, background `QThread` workers, and theme/token styling | Direct SQL, schema creation, durable business rules, Streamlit or `src.ui_streamlit` imports |
| Streamlit Compatibility UI (`app.py`, `src/ui_streamlit/`) | Compatibility widgets, layout, page flow, user input collection, transient `session_state` navigation and focus state | Direct SQL when avoidable, schema creation, durable business rules, PySide6 or `src.ui_desktop` imports |

## Local-First Design

SQLite is the durable source of application state. `src/app_config.py` resolves its default per-user database location, explicit environment overrides, and any selected data root (`data-root.json` and `migration-recovery.json`) before database initialization.

The app does not silently move or replace a database. User-created entries, templates, review history, quiz logs, and learning-pool membership remain local and user-controlled. Confirmed unified data-folder relocation is user-initiated from **Settings → Storage**, preserves the original source files intact as a rollback baseline, requires an application restart after cutover, and fails closed if a selected data root or recovery state is missing or damaged.

## User-Owned Content

The software organizes and practices content supplied by users. It does not ship dictionary databases, pronunciation libraries, copyrighted word lists, or AI-generated learning datasets. See `docs/policies/CONTENT_POLICY.md`.

## Streamlit Boundary Rule

Streamlit imports are allowed only in:

- `app.py`
- `src/ui_streamlit/*.py`

Reusable modules under `src/` must not import Streamlit. They expose plain Python functions and return plain data structures so both the native PySide6 desktop UI and the Streamlit compatibility UI reuse them without duplication.

Streamlit `session_state` is UI state. Durable state and duplicate-action protection belong in core modules and SQLite.

## Desktop UI Boundary Rule

In production application code, PySide6 imports are allowed only in
`src/ui_desktop/*.py` (selected in M16.1; see
[M16.1 Desktop Architecture Contract](docs/design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md)).
This rule covers `app.py` and `src/`, the files `scripts/audit_architecture.py`
scans; it does not restrict test code under `tests/`, which the audit script
does not scan and which may import PySide6 directly for architecture
verification (see `tests/test_m16_1_architecture_spike.py`).

Reusable modules under `src/` must not import PySide6 or `src.ui_desktop`, the
same way they must not import Streamlit or `src.ui_streamlit`. The Streamlit
compatibility UI and the native desktop UI are two independent presentation
layers; `src/ui_streamlit/*.py` must not import PySide6 or
`src.ui_desktop`, and `src/ui_desktop/*.py` must not import Streamlit or
`src.ui_streamlit`. `scripts/audit_architecture.py` enforces both directions.

## Core Module Responsibilities

- `src/app_config.py`: application identity, default/override path resolution, versioned `data-root.json` selected-root resolution, four-component streaming SHA-256 manifest verification, and `migration-recovery.json` (`SWITCHING → COMMITTED`) startup reconciliation (failing closed via `DataRootError` without creating a blank database when a selected root or recovery state is missing or damaged)
- `src/data_lock.py`: cross-process OS file locking (`.app_data.lock`, using pointer-sized Win64 `OVERLAPPED` with `LockFileEx` on Windows and `flock` off Windows), providing shared locks for active SQLite connections (`LockedConnection`), preference writes, audio-cache materialization/composition, backups, and imports, and an exclusive quiescence lock during data-folder relocation
- `src/data_relocation.py`: confirmed, transactional four-component data-folder relocation (`vocab.db` via online `Connection.backup()`, `backups/`, `audio-cache/`, and `preferences.json`) using sibling staging (`<parent>/.vocab-stage-<uuid>`), `.vocab_app_root_marker.json` provenance + SHA-256 manifest checks, atomic no-clobber promotion (`MoveFileExW` with `MOVEFILE_WRITE_THROUGH` and without `MOVEFILE_REPLACE_EXISTING` on Windows), atomic `os.replace` temp-file updates for `migration-recovery.json` and `data-root.json`, retained source rollback baseline, and mandatory restart boundary
- `src/db.py`: connections (including shared-lock-guarded `LockedConnection` on guarded roots), schema initialization, and additive compatibility updates
- `src/migrations.py`: schema/app metadata, feature flags, and additive migration registry
- `src/entries.py`: entry CRUD, search, filters, and batch operations
- `src/entry_templates.py`: templates, fields, and template values
- `src/collections.py`: collection membership, cards, positions, and system pools
- `src/card_history.py`: stable Card identity, revision reconciliation, cross-Card movement detection, and historical queries
- `src/review.py`: isolated legacy Review/SRS compatibility state and logs
- `src/review_schedule.py`: active user-managed scheduling keyed by stable `card_id`
- `src/quiz.py`: quiz sessions, item generation, answers, logs, and idempotent completion
- `src/template_quiz.py`: template-aware quiz rules
- `src/statistics.py`: factual read-only statistics/calendar queries and legacy Entry Health compatibility projections over M14
- `src/analytics.py`: M14 Evidence Profiles, neutral classifications, Coverage, Scope Activity, and Personal Baseline
- `src/insights.py`: M14 Primary Findings, priority, structured actions, clustering, hierarchy suppression, and deterministic Learning Brief selection
- `src/learning_workflow.py`: read-only Today workflow queries and recommendations
- `src/import_export.py`: transfer formats, validation, preview, and confirmed import
- `src/template_definitions.py`: deterministic, preview-first, atomic portable Template Definition CSV operations
- `src/speech_semantics.py`: M15 required-field speech planning, persisted
  language-role resolution, and controlled readiness results
- `src/tts_providers.py`: canonical language routing, fixed provider/voice
  selection, preflight, and one-unit synthesis boundary
- `src/audio_assets.py`: M15.2 content-addressed disposable unit cache,
  canonical PCM WAV normalization, validation, and atomic publication
- `src/audio_composition.py`: M15.2 current-Card speech planning, render
  identity, deterministic boundaries/repetition, and one-Card composition
- `src/audio_export.py`: M15.3 snapshot-based single/selected/Collection audio
  export planning, atomic publication, partial results, progress, and retry
- `src/linked_sources.py`: append-only local CSV/XLSX source-link preview, confirmation, refresh, and unlink orchestration
- `src/backup.py`: database/workbook backup and restore preview
- `src/text_parser.py`: structured Quick Add parsing

## UI Module Responsibilities

`src/ui_desktop/` (primary native desktop UI) owns:

- native Qt application bootstrap (`__main__.py`), `MainWindow` shell, and workspace routing
- workspace views (`views/`), custom widgets (`widgets/`), and Qt table/list models (`qt_models/`)
- controllers (`controllers/`) owning transient workspace/session state and background `QThread` worker orchestration (such as `SettingsController` and `RelocationWorker` for **Settings → Storage** data-folder relocation)
- theme tokens, QSS generation, and OS appearance tracking (`theming/`)

`src/ui_streamlit/` (retained compatibility/reference UI) owns:

- Streamlit page rendering and widget layout
- transient forms and `session_state` selection/focus hints
- upload and download controls
- user-facing messages

Both UI layers call core functions rather than duplicating durable rules.

## Database Ownership

- Schema initialization and compatibility changes belong in `src/db.py`.
- Schema/app metadata and migration registry logic belong in `src/migrations.py`.
- Feature modules may execute SQL for their owned data responsibilities.
- UI modules should not contain raw SQL.
- Migrations should be additive, backup-aware, and preserve user data.
- `data/vocab.db` must not be committed to Git.

`collection_source_links` stores at most one local append-source link per
Collection. It stores metadata, including the user-selected local path, but not
source file bytes or row-to-Entry mappings. Linked-source preview and confirmed
writes reuse `src/import_export.py`; they do not implement a parallel parser or
validation language. The source is non-authoritative and cannot delete,
reorder, or overwrite current app content.

## Learning Completion Semantics

A completed Quiz scoped to one Collection Card is the active authoritative
Card learning event. `quiz_sessions.completed_at` is the source timestamp; the
system does not create a parallel Review-completion event. Non-Card Quiz
sessions remain Entry-performance evidence only.

Current-facing Card status and history resolve the active Card by stable
`card_id`, not merely by `collection_id + card_number`. A retired Card's Quiz
history therefore cannot be reassigned to a later Card that reuses the same
display number. Transient Today/Review/Quiz focus and queue state also carries
and validates `card_id`; unavailable or mismatched state is explained and
cleared rather than redirected to another Card.

`quiz_item_logs.entry_id` is a durable historical integer reference rather
than a cascading foreign key to the current `entries` table. Hard-deleting an
Entry therefore preserves its Quiz item evidence, including the stored prompt,
expected answer, user answer, correctness, and original Entry ID. Historical
views use a generic `Deleted Entry #<id>` label when no current term exists;
they do not reconstruct or invent deleted Entry content.

`entry_collections.position` plus `collections.card_size` remains the sole
source for current Card grouping. `cards`, `card_revisions`, and
`card_revision_entries` add durable identity and immutable historical
membership snapshots without becoming a second current-membership source.
Only a material ordered-membership change creates a revision. New Card-scoped
Quiz sessions bind to the current `card_id` and `card_revision_id`; legacy
sessions remain unknown when their historical composition cannot be proved.

Review is a browse, study, and Quiz-launch surface. Active next-review
scheduling is separate from completion truth and uses stable `card_id`.
Legacy Review scheduling tables and APIs remain compatibility-only and must
not drive active Today, Statistics, or Learning History completion claims.

## Learning Analytics Authority

M14 separates factual measurements, neutral analytical classification, and
deterministic interpretation:

```text
SQLite Quiz evidence
-> src/statistics.py factual measurements
-> src/analytics.py Evidence Profiles / Coverage / Personal Baseline
-> src/insights.py Findings / priority / actions / Learning Brief
-> Entry Health compatibility projection
-> native desktop UI (primary) or Streamlit compatibility UI
```

Entry-level interpretation is authoritative in M14. Legacy public Entry Health
function names remain callable where needed, but their rows are projections of
M14 Primary Findings rather than a second threshold engine. Compatibility
arguments from the former Weak/Neglected model may remain in signatures to
avoid caller breakage; they do not override the frozen M14 contract.

All M14 paths are read-only. They add no persisted Finding, Brief, score, due
date, pool mutation, or parallel analytics database. Deleted Entries remain
outside current actionable analytics while their preserved Quiz and Card
revision history remains available to historical views.

## Implemented Desktop Architecture / Historical Migration Decision

The desktop migration (completed through M16–M20) preserved the SQLite schema
and reusable core modules while establishing `src/ui_desktop/` as the primary
native Windows product surface alongside the retained `app.py` and
`src/ui_streamlit/` compatibility UI.

M16.1 selected **PySide6** as the desktop framework and froze the
controller/view-state/core boundary. The full decision, evidence, package
structure, state taxonomy, concurrency model, and theme/token implementation
boundary are recorded in
[M16.1 Desktop Architecture Contract](docs/design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md);
this section summarizes the durable rule.

The native desktop layer (`src/ui_desktop/`) calls the same core functions the
Streamlit compatibility layer calls — plain Python arguments in, plain data
structures out — and uses desktop-specific adapters (`Qt` table/list models,
controllers owning transient state, and dedicated `QThread` workers where
needed) where Streamlit handles uploads, downloads, navigation, or transient
widget state. A thin `src/ui_desktop/services/` orchestration layer is added
only when a real desktop workflow demonstrates a genuine multi-step or
transactional need beyond a direct controller-to-core call; it is not created
for architectural symmetry.

## Contributor Guardrails

Do not:

- import Streamlit from core modules
- import PySide6 or `src.ui_desktop` from core modules
- place SQL or learning algorithms in `app.py`
- create parallel quiz, review, import, or persistence systems
- silently switch or migrate user databases
- introduce mandatory external language-content services

Run:

```powershell
python scripts/audit_architecture.py
```

before architecture-sensitive changes.
