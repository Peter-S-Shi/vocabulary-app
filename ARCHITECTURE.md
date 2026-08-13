# Architecture

Vocabulary App is a local-first Python application with a reusable core, a SQLite persistence layer, and a temporary Streamlit UI.

## Layers

| Layer | Allowed Responsibilities | Forbidden Responsibilities |
|---|---|---|
| Core modules | SQL, validation, business rules, reusable query helpers, import/export and backup operations | Streamlit widgets, `session_state`, page rendering |
| Streamlit UI | Widgets, layout, page flow, user input collection, transient navigation and focus state | Direct SQL when avoidable, schema creation, durable business rules |
| App shell | Page configuration, initialization, sidebar navigation, page routing | Learning algorithms, SQL, collection ordering, parsing |

## Local-First Design

SQLite is the durable source of application state. The default development database is `data/vocab.db`, with optional path resolution provided by `src/app_config.py`.

The app does not silently move or replace a database. User-created entries, templates, review history, quiz logs, and learning-pool membership remain local and user-controlled.

## User-Owned Content

The software organizes and practices content supplied by users. It does not ship dictionary databases, pronunciation libraries, copyrighted word lists, or AI-generated learning datasets. See `docs/policies/CONTENT_POLICY.md`.

## Streamlit Boundary Rule

Streamlit imports are allowed only in:

- `app.py`
- `src/ui_streamlit/*.py`

Reusable modules under `src/` must not import Streamlit. They expose plain Python functions and return plain data structures so a future desktop UI can reuse them.

Streamlit `session_state` is UI state. Durable state and duplicate-action protection belong in core modules and SQLite.

## Core Module Responsibilities

- `src/app_config.py`: application identity and local path resolution
- `src/db.py`: connections, schema initialization, and additive compatibility updates
- `src/migrations.py`: schema/app metadata, feature flags, and additive migration registry
- `src/entries.py`: entry CRUD, search, filters, and batch operations
- `src/entry_templates.py`: templates, fields, and template values
- `src/collections.py`: collection membership, cards, positions, and system pools
- `src/card_history.py`: stable Card identity, revision reconciliation, cross-Card movement detection, and historical queries
- `src/review.py`: isolated legacy Review/SRS compatibility state and logs
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
- `src/linked_sources.py`: append-only local CSV/XLSX source-link preview, confirmation, refresh, and unlink orchestration
- `src/backup.py`: database/workbook backup and restore preview
- `src/text_parser.py`: structured Quick Add parsing

## UI Module Responsibilities

`src/ui_streamlit/` owns:

- page rendering and widget layout
- transient forms and selection state
- sidebar/page focus hints
- upload and download controls
- user-facing messages

UI modules call core functions rather than duplicating durable rules.

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

Review is a browse, study, and Quiz-launch surface. Legacy Review scheduling
tables and APIs remain compatibility-only and must not drive active Today,
Statistics, or Learning History completion claims.

## Learning Analytics Authority

M14 separates factual measurements, neutral analytical classification, and
deterministic interpretation:

```text
SQLite Quiz evidence
-> src/statistics.py factual measurements
-> src/analytics.py Evidence Profiles / Coverage / Personal Baseline
-> src/insights.py Findings / priority / actions / Learning Brief
-> Entry Health compatibility projection
-> current Streamlit or future desktop UI
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

## Future Desktop Migration

A desktop migration should preserve the SQLite schema and core modules, then replace `app.py` and `src/ui_streamlit/` with a package such as `src/ui_desktop/`.

The desktop layer should call the same core functions and introduce UI adapters only where Streamlit currently handles uploads, downloads, navigation, or transient widget state.

## Contributor Guardrails

Do not:

- import Streamlit from core modules
- place SQL or learning algorithms in `app.py`
- create parallel quiz, review, import, or persistence systems
- silently switch or migrate user databases
- introduce mandatory external language-content services

Run:

```powershell
python scripts/audit_architecture.py
```

before architecture-sensitive changes.
