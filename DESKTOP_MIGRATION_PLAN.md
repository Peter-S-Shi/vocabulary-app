# Desktop Migration Plan

## 1. Migration Principle

> Replace the UI layer, preserve the learning engine.

Preserve as much as possible:

- SQLite schema and user databases
- `src/app_config.py`
- `src/db.py`
- `src/entries.py`
- `src/entry_templates.py`
- `src/collections.py`
- `src/review.py`
- `src/quiz.py`
- `src/template_quiz.py`
- `src/statistics.py`
- `src/learning_workflow.py`
- `src/import_export.py`
- `src/backup.py`
- `src/text_parser.py`

Replace or retire after parity:

- `app.py`
- `src/ui_streamlit/`

## 2. Candidate Desktop Frameworks

| Framework | Fit | Main Trade-off |
|---|---|---|
| PySide6 | Strong | Official Qt for Python; capable desktop UI and packaging, but adds Qt complexity and a large dependency |
| PyQt | Strong | Mature Qt ecosystem; licensing choice must be reviewed before distribution |
| Tkinter | Limited | Built into Python and simple, but less suitable for dense modern tables and complex workflows |
| Toga / Briefcase | Exploratory | Cross-platform product ambitions, but smaller ecosystem and migration uncertainty |
| Electron / webview wrapper | Conditional | Reuses web concepts but introduces a second runtime and is less natural for the current Python core |

PySide6 or PyQt is the most natural future path for a Python + SQLite local application. No irreversible framework choice is required yet.

## 3. Future Desktop Screen Mapping

| Current Streamlit Page | Future Desktop Screen |
|---|---|
| Today | Home / Today Dashboard |
| Entries | Entry Manager |
| Collections | Collection Manager |
| Review | Review Session |
| Quiz | Quiz Session |
| Statistics | Statistics Dashboard |
| Import / Export | Data Tools |
| Review History / Schedule | Review Calendar and Schedule |
| Dashboard | Secondary Overview |
| Settings / Data | Settings and Storage |

## 4. Core Service Layer Needs

Current UI pages often call focused core functions directly. That is acceptable for the MVP. A desktop UI may benefit from thin orchestration services:

```text
src/services/
  entry_service.py
  collection_service.py
  review_service.py
  quiz_service.py
  workflow_service.py
  import_export_service.py
```

Services should coordinate existing modules, not duplicate SQL or algorithms. Add them only when a desktop workflow demonstrates a concrete need.

## 5. Session State Migration

`st.session_state` is transient UI state and must not move into core modules.

Future desktop controllers or view models should own:

- selected page and active tab
- selected entry IDs
- focused collection and review card
- current quiz item and revealed-answer state
- quiz UI recovery state
- import preview and confirmation state
- temporary filters and table selection

Durable quiz sessions, answer logs, review schedules, and content remain in SQLite.

## 6. Database Compatibility

- Existing SQLite databases should open in the desktop app.
- Schema changes must be additive and versioned.
- Backups should be recommended or created before major migration.
- Canonical entries, templates, collections, review logs, and quiz logs must be preserved.
- Database movement to an OS app-data directory must be explicit and reversible.
- Destructive restore and overwrite remain confirmation-protected.

## 7. Migration Phases

### Prerequisite: Complete the current Streamlit release lifecycle

- Complete Feature Complete Review.
- Explicitly pass the Feature Freeze Gate.
- Complete Milestone 11 Product Hardening.
- Complete Milestone 12 release-candidate acceptance.
- Finish full-product manual acceptance and regression.
- Keep the architecture audit clean.
- Preserve the schema/app metadata and migration rules established in
  Milestone 10.6.

Do not begin a full desktop migration before these gates pass.

### Phase 2: Minimal desktop shell prototype

- Launch a native window.
- Resolve and open an existing database.
- Show a read-only Today overview.
- List and inspect entries.
- Prove that core modules work without Streamlit.

### Phase 3: Port high-frequency workflows

- Today
- Review
- Quiz
- Entries

Define explicit controller state and verify database parity after each workflow.

### Phase 4: Port management tools

- Collections
- Statistics and Review Calendar
- Import / Export
- Backup and restore preview
- Settings and storage information

### Phase 5: Package the desktop app

- Build scripts and clean-machine testing
- OS user-data directory
- explicit existing-data migration
- backup before update
- installer/uninstaller behavior
- rollback and release documentation

## 8. Migration Readiness Checklist

- [x] Core modules import no Streamlit
- [x] Database path resolution is centralized
- [x] Import/export validation and execution are UI-independent
- [x] Backup generation and preview are UI-independent
- [x] Quiz durable session and duplicate protection live in core/SQLite
- [x] Today workflow queries are reusable
- [x] Architecture and content policies are documented
- [x] Public sample-data policy excludes personal and copyrighted data
- [x] Schema version metadata and migration rules exist
- [ ] Feature Complete Review is complete
- [ ] Feature Freeze is explicitly approved
- [ ] Full-product manual acceptance and Product Hardening are complete
- [ ] Current Streamlit release-candidate acceptance is complete
- [ ] A minimal desktop shell prototype proves core reuse
- [ ] Packaged user-data migration and rollback are designed

## Recommended Next Decision

Complete the current Streamlit Feature Freeze, Product Hardening, and
release-candidate lifecycle before starting a full rewrite. Then build a
deliberately small PySide6/PyQt prototype and evaluate it against the verified
Streamlit workflow before choosing the final desktop framework.
