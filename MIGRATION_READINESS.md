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
- Review scheduling and logs: `src/review.py`
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

1. Complete Feature Complete Review and explicitly pass the Feature Freeze Gate.
2. Complete Milestone 11 Product Hardening and Milestone 12 release-candidate
   acceptance for the current Streamlit release.
3. Freeze and manually verify the current learning workflows.
4. Keep the SQLite schema and existing core modules.
5. Add a new UI package such as `src/ui_desktop/`.
6. Build desktop navigation and view models around current core functions.
7. Replace Streamlit upload/download widgets with native file dialogs.
8. Map transient quiz and focus state to explicit desktop controller state.
9. Preserve database compatibility or provide additive migration scripts.
10. Retire Streamlit pages only after workflow parity is verified.

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

Review due dates and daily summaries must remain consistent across local time zones and packaged environments.

### Data paths and packaging

The development database remains project-local. A packaged app needs an explicit, backup-aware move to an OS app-data directory.

### Software updates

Future schema changes should use the version metadata and additive migration registry introduced in Milestone 10.6. Major upgrades should still recommend pre-migration backups and compatibility tests.

## Readiness Assessment

The core is migration-friendly, and Milestone 10.6 established schema/app
metadata plus migration rules. This supports a future deliberately small
prototype; it does not establish readiness for a full rewrite.

The current Streamlit workflows must first pass Feature Complete Review,
explicit Feature Freeze, Product Hardening, full regression/manual acceptance,
and release-candidate verification. Active quiz recovery, dense tables, file
workflows, focus state, dates/local time, writable data paths, and software
updates remain migration risks.
