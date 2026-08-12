# Migration Readiness

## Current State

- Streamlit is the active UI.
- SQLite is the local durable database.
- Most reusable learning and data logic already lives under `src/`.
- Streamlit rendering and session state are isolated under `app.py` and `src/ui_streamlit/`.
- Application path resolution is centralized in `src/app_config.py`.
- Schema/app metadata and future migration registration are centralized in `src/migrations.py`.

## Already Migration-Friendly

- Database initialization and connections: `src/db.py`
- Entries and templates: `src/entries.py`, `src/entry_templates.py`
- Collections, card grouping, ordering, and pools: `src/collections.py`
- Legacy Card review compatibility state and logs pending M11.2 migration:
  `src/review.py`
- Quiz generation, sessions, answers, and logs: `src/quiz.py`
- Template quiz rules: `src/template_quiz.py`
- Statistics and Review Calendar: `src/statistics.py`
- Today workflow queries and recommendations: `src/learning_workflow.py`
- Import/export validation and execution: `src/import_export.py`
- Backup and restore preview: `src/backup.py`
- Structured text parsing: `src/text_parser.py`
- Software update metadata and migration registry: `src/migrations.py`

These modules return plain Python data and do not import Streamlit.

## Still Streamlit-Dependent

- Page rendering and sidebar navigation
- Widget forms and transient selection state
- Today, Review, Quiz, and Statistics focus routing
- Active quiz presentation and in-memory item navigation
- File upload and download widgets
- Dataframe presentation and confirmation UI
- User-facing status, warning, and error messages

These dependencies are expected UI responsibilities.

## Audit Result

Milestone 10.4 found no Streamlit imports or `session_state` usage in core modules and no confirmed raw SQL in Streamlit page files. No large code extraction was justified.

The automated script `scripts/audit_architecture.py` checks these boundaries without becoming a runtime dependency.

## Recommended Desktop Migration Strategy

1. Milestone 11 Pre-Desktop Stabilization is complete and establishes the
   trustworthy data/business-logic baseline documented in
   `MILESTONE11_CLOSURE.md`.
2. Complete the Milestone 12 repository restructure without changing product
   behavior.
3. Implement reusable import/template, analytics, and audio foundations in
   Milestones 13-15 where this avoids duplicate UI-specific work.
4. Keep the SQLite schema and existing core modules compatible through
   additive, versioned migrations.
5. Design and prove the desktop architecture in Milestone 16.
6. Add a desktop UI package and build navigation/controllers around reusable
   core functions.
7. Replace Streamlit upload/download widgets with native file dialogs.
8. Map transient Quiz and focus state to explicit desktop controller state.
9. Migrate high-frequency and management workflows incrementally.
10. Retire Streamlit only after required desktop parity is verified.

## Risks and Watchlist

### Active quiz recovery

The database stores session status and answer logs, while the Streamlit UI also carries transient item navigation. A desktop controller will need a clear recover/resume contract.

### Import and backup file workflows

Native file dialogs must preserve validation, preview, confirmation, duplicate handling, and restore-preview safety.

### Dense tables and selection flows

Entries, collections, statistics, and import previews rely on Streamlit dataframe and widget behavior. Desktop replacements need efficient filtering and multi-selection.

### Navigation focus

Today currently routes to Review, Quiz, and Statistics through UI focus state. Desktop navigation should use typed controller/view-model state rather than global widget keys.

### Dates and local time

Card-scoped Quiz completion timestamps, factual Last Quiz views, and daily
summaries must remain consistent across local time zones and packaged
environments. Legacy due-date fields may remain for compatibility but must not
remain authoritative product truth.

### Data paths and packaging

The development database remains project-local. A packaged app needs an explicit, backup-aware move to an OS app-data directory.

### Software updates

Future schema changes should use the version metadata and additive migration registry introduced in Milestone 10.6. Major upgrades should still recommend pre-migration backups and compatibility tests.

## Readiness Assessment

The core is migration-friendly, and Milestone 10.6 established schema/app
metadata plus migration rules. This supports an incremental desktop migration,
not an unverified full rewrite.

The trustworthy pre-desktop prerequisite is now established: Entry edit
integrity, authoritative Card-scoped Quiz completion, retirement of independent
manual scheduling, stable Card identity and membership history, Entry Health
re-acceptance, database compatibility, and core/UI boundaries are resolved or
verified. Active Quiz continuation UX, dense tables, file workflows,
dates/local time, writable data paths, and software updates remain migration
risks for M12 and later desktop work.
