# Vocabulary App

Vocabulary App is a local-first personal vocabulary learning system for people who want to create, edit, organize, review, quiz, analyze, import, export, and back up their own English and French learning entries.

The project is currently a Python, Streamlit, and SQLite application. Streamlit is the temporary compatibility UI; reusable learning and data logic is kept in separate core modules for the planned native desktop product.

## Overview

Vocabulary App helps users maintain their own vocabulary database and turn it into a repeatable learning workflow:

1. Create or import entries.
2. Organize entries into collections and cards.
3. Browse or study cards as preparation.
4. Complete Card-scoped quizzes as the authoritative Card learning event.
5. Inspect statistics and daily progress.
6. Export or back up local data.

The `Today` page acts as the daily learning home. During Milestone 11 its
recommendations and summaries are being migrated from legacy Review-schedule
state to factual Card-scoped Quiz history.

## Lifecycle Status

Milestones 1-10 feature development and productization are complete historical
work. The project is now in **Scope Reopened / Pre-Desktop Stabilization** at
**Milestone 11**.

Streamlit remains the currently runnable compatibility/reference UI, but it is
no longer the intended Release Candidate target. The active lifecycle now
stabilizes data semantics, builds reusable foundations, migrates the product to
a native desktop UI, and hardens/packages the desktop product.

- [ROADMAP.md](ROADMAP.md) is the authoritative lifecycle and milestone plan.
- [PROJECT_STATUS.md](PROJECT_STATUS.md) is the authoritative current-state
  snapshot.
- [PRE_GIT_HISTORY.md](PRE_GIT_HISTORY.md) documents development before the
  initial public Git baseline.

### Approved Milestone 11 learning semantics

- Review is a Card browse/study/preparation surface and an entry point into
  Quiz. Browsing alone is not a completed learning event.
- Completing a Quiz scoped to a specific Card is the authoritative completed
  learning/review event for that Card. Entering that Quiz directly is equally
  valid; the user does not need to visit Review first.
- A random or whole-pool Quiz remains valid Entry-level performance activity,
  but it must not fabricate completion for an unrelated Card.
- Independent manual next-review scheduling and Again/Hard/Good/Easy interval
  scheduling are being retired from the active model during Milestone 11. No
  replacement SRS algorithm is being introduced in this milestone.
- `entries.id` is the permanent Entry identity. The approved Card direction is
  a stable `card_id` with mutable, historically traceable Entry membership.
  Current legacy records that only identify `collection_id + card_number` must
  not be presented as more precise than the stored evidence supports.

## Product Philosophy

- **Local-first:** learning data is stored in a local SQLite database.
- **User-owned content:** users create, edit, import, and maintain their own entries.
- **Explicit control:** Card composition, quiz answers, pool membership, imports, deletion, and backup actions remain user-controlled.
- **No hidden language authority:** the app organizes learning data but does not claim to verify linguistic accuracy.
- **Migration-friendly architecture:** reusable logic stays outside the Streamlit UI.

Users are responsible for ensuring that content they create, import, export, or share is accurate and that they have permission to use it.

This product boundary is intentional: manual editing can support deeper learning, local storage protects personal study data, and avoiding bundled language databases reduces licensing risk. It also keeps the system flexible for English, French, and future user-defined languages or templates.

See [CONTENT_POLICY.md](CONTENT_POLICY.md) for the detailed user-owned content policy.

## Current Features

### Entries and templates

- Entry creation, editing, search, filters, selection, and batch deletion
- Structured Quick Add text parsing
- General and custom entry templates
- Built-in French template presets
- Template field values included in search and display
- Starred and Proficient Pool batch actions

### Collections and cards

- Configurable collection card sizes
- Collection-specific entry ordering
- Dynamic card-number calculation
- Add, remove, reorder, and delete collection workflows
- System collections for Mistake Book, Starred, and Proficient Pool

### Review and legacy scheduling compatibility

- Collection Card browse/study surface
- Card-to-Quiz focus handoff
- Legacy due/overdue, manual scheduling, Review state, and Review History
  surfaces retained in the current Streamlit baseline pending M11.2 migration

These legacy scheduling surfaces describe current compatibility behavior, not
the approved authoritative learning-completion model.

### Quiz and learning pools

- Self-graded term/meaning quizzes
- Multiple-choice and mixed multiple-choice quizzes
- Matching practice
- Template-aware quiz rules
- Active-session protection and duplicate-answer protection
- Entry-level results linked to permanent `entry_id`
- Mistake Book recovery workflow
- Proficient Pool random audits

### Statistics and review calendar

- Entry, template, collection, review, quiz, and special-pool statistics
- Review calendar and workload ranges
- Learning trends and entry-health views
- Read-only statistics architecture

### Daily learning workflow

- `Today` as the default learning home
- Legacy due/overdue workload pending M11.2 semantic migration
- Daily quiz suggestions
- Special-pool status
- Review and quiz focus navigation
- Daily learning summary based on local logs

### Import / export

- CSV and XLSX export
- General and template-based import
- Validation, preview, confirmation, and transaction-safe writes
- Duplicate handling
- Collection/card-aware import and export
- Downloadable sample formats and template field maps

### Backup and restore-lite preview

- Consistent SQLite backup snapshots
- Structured XLSX backup
- Restore preview without overwriting the active database

## What This App Does Not Include

This project does not include:

- built-in dictionary databases
- copyrighted word lists
- bundled pronunciation recordings
- bundled or downloaded TTS voice models in the current implementation
- AI-generated vocabulary explanations, examples, or bulk learning content
- automatic correction of user-created entries
- cloud sync
- account login or authentication
- mobile app packaging
- an implemented desktop GUI in the current repository state
- full destructive database restore

These statements describe the current implementation. The active roadmap now
includes local Card Audio Export and native desktop migration, subject to
feasibility, licensing, compatibility, and later milestone verification.

## Tech Stack

- Python 3
- Streamlit
- SQLite
- openpyxl for XLSX workflows

## Project Structure

```text
vocab-app/
|-- app.py                       # Streamlit app shell and sidebar routing
|-- requirements.txt
|-- README.md
|-- DATA_SAFETY.md
|-- CONTRIBUTING.md
|-- data/
|   |-- .gitkeep
|   `-- vocab.db                 # Local user data; ignored by Git
|-- sample_data/
|   `-- README.md
`-- src/
    |-- db.py                    # Database connection and initialization
    |-- entries.py               # Entry CRUD and search
    |-- entry_templates.py       # Template management
    |-- migrations.py            # Schema/app metadata and additive migrations
    |-- collections.py           # Collections, cards, and ordering
    |-- review.py                # Card review compatibility state pending M11.2
    |-- quiz.py                  # Quiz sessions and answer logs
    |-- template_quiz.py         # Template-aware quiz rules
    |-- statistics.py            # Read-only statistics queries
    |-- learning_workflow.py     # Read-only Today workflow queries
    |-- import_export.py         # Import/export validation and execution
    |-- backup.py                # Backup and restore-preview helpers
    |-- text_parser.py           # Structured Quick Add parsing
    `-- ui_streamlit/            # Streamlit-specific pages and UI state
```

Core modules return plain Python data structures and do not depend on Streamlit. Streamlit-specific rendering and session state belong in `app.py` and `src/ui_streamlit/`.

## Architecture and Migration Readiness

Streamlit is the current UI layer, while reusable learning and data logic lives under `src/`. Streamlit-specific code stays in `app.py` and `src/ui_streamlit/`.

See [ARCHITECTURE.md](ARCHITECTURE.md) for boundary rules and [MIGRATION_READINESS.md](MIGRATION_READINESS.md) for the practical desktop migration assessment.

Packaging and desktop options are documented in [PACKAGING_FEASIBILITY.md](PACKAGING_FEASIBILITY.md) and [DESKTOP_MIGRATION_PLAN.md](DESKTOP_MIGRATION_PLAN.md).

Software update safety is documented in [SOFTWARE_UPDATE_POLICY.md](SOFTWARE_UPDATE_POLICY.md). Milestone 10.6 establishes the first explicit schema-version baseline through `app_metadata` and `src/migrations.py`.

## Installation

### Prerequisites

- Python 3.10 or newer is recommended.
- Git is optional if the project is downloaded as an archive.

### Windows PowerShell

```powershell
git clone <repository-url>
cd vocab-app
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### macOS or Linux

```bash
git clone <repository-url>
cd vocab-app
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
```

## Run Locally

Windows:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

macOS or Linux:

```bash
./.venv/bin/python -m streamlit run app.py
```

Streamlit normally opens:

```text
http://localhost:8501
```

Run the command from the directory containing `app.py`.

## Local Data and Privacy

The development database is stored at:

```text
data/vocab.db
```

This file may contain personal vocabulary, notes, source references, review history, and quiz activity. It is ignored by Git and must not be committed to a public repository.

The application initializes the database automatically when it starts. Do not delete `data/vocab.db` unless you intentionally want to reset all local learning data.

Before major upgrades or manual database operations, create a backup from the app or copy the database while the app is stopped.

Milestone 10.6 adds read-only schema/app metadata for software update compatibility. Future schema changes should use additive migrations, preserve user data, and keep optional modules disabled by default.

Advanced users may set `VOCAB_APP_DB_PATH` before launch to select another database path. Normal users do not need this setting, and the app does not automatically move or merge databases.

Future packaged versions may use an operating-system app-data directory rather than the source folder. See [DATA_STORAGE.md](DATA_STORAGE.md) for path behavior and [DATA_SAFETY.md](DATA_SAFETY.md) for practical handling guidance.

## Import / Export and Backup Safety

- Imports follow **Upload -> Validate -> Preview -> Confirm -> Import**.
- Invalid or unsupported rows are reported before writes.
- Imports do not create unknown templates silently.
- Exports are read-only and do not change the database.
- SQLite backup creates a consistent local snapshot.
- XLSX restore is preview-only and does not overwrite the active database.
- Import and export files may contain personal or third-party material; handle and share them carefully.

## Development Milestones

Milestones 1-10 completed the current feature set and productization
foundations:

- Local entry and collection management
- Historical Collection Card review scheduling baseline
- Quiz sessions and learning pools
- Template-based entries and French presets
- Statistics and Review Calendar
- CSV/XLSX import and export
- SQLite/XLSX backup and restore preview
- Today and Daily Learning Workflow
- Schema/app metadata and software-update compatibility foundation
- Productization QA and public-repository documentation polish

Milestone 10 productization closure is not equivalent to current-version
completion. The active lifecycle begins with Milestone 11 Pre-Desktop
Stabilization and ends with desktop Product Hardening, packaging, and Release
Candidate acceptance in Milestones 19-20.

Detailed manual QA documents are available for recent milestones:

- `MILESTONE8_MANUAL_QA.md`
- `MILESTONE9_MANUAL_QA.md`
- `MILESTONE10_MANUAL_QA.md`
- `MILESTONE10_PRODUCTIZATION_QA.md`

## Roadmap

The active product lifecycle is:

```text
M11 Pre-Desktop Stabilization
-> M12 Repository Restructure
-> M13 Import and Template Evolution Core
-> M14 Learning Analytics and Insight Core
-> M15 Audio Foundation
-> M16 Desktop Architecture and UI Design
-> M17 Desktop Core Workflow Migration
-> M18 Desktop Management and Major Feature Completion
-> M19 Desktop Product Hardening
-> M20 Packaging and Release Candidate
```

Streamlit is not the final release target. See [ROADMAP.md](ROADMAP.md) for
scope and exit criteria and [DESKTOP_MIGRATION_PLAN.md](DESKTOP_MIGRATION_PLAN.md)
for the migration strategy.

## Common Errors

### `python` is not recognized

Install Python and enable the option to add it to `PATH`, then reopen the terminal.

### PowerShell blocks `Activate.ps1`

Activation is optional. The commands in this README call the virtual-environment Python directly.

If activation is preferred:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### `streamlit` is not recognized

Use Python module execution:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

### `ModuleNotFoundError: No module named 'src'`

Start the application from the project directory containing `app.py`.

### Port 8501 is already in use

Choose another port:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8502
```

## License

A final open-source license has not yet been selected. See [LICENSE](LICENSE).
