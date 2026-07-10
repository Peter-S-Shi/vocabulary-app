# Vocabulary App

Vocabulary App is a local-first personal vocabulary learning system for people who want to create, edit, organize, review, quiz, analyze, import, export, and back up their own English and French learning entries.

The project is currently a Python, Streamlit, and SQLite application. Streamlit is the temporary UI layer; reusable learning and data logic is kept in separate core modules to support a future desktop UI or other product form.

## Overview

Vocabulary App helps users maintain their own vocabulary database and turn it into a repeatable learning workflow:

1. Create or import entries.
2. Organize entries into collections and cards.
3. Review cards on a user-controlled schedule.
4. Practice with quizzes and learning pools.
5. Inspect statistics and daily progress.
6. Export or back up local data.

The `Today` page acts as the daily learning home. It summarizes due work, suggests review and quiz actions, and reports activity derived from existing local logs.

## Product Philosophy

- **Local-first:** learning data is stored in a local SQLite database.
- **User-owned content:** users create, edit, import, and maintain their own entries.
- **Explicit control:** review scheduling, quiz answers, pool membership, imports, deletion, and backup actions remain user-controlled.
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

### Review scheduling

- Collection Card review unit
- Due, overdue, and unscheduled cards
- Direct user-controlled scheduling
- Review state and history logs
- Review History / Schedule management

### Quiz and learning pools

- Self-graded term/meaning quizzes
- Multiple-choice and mixed multiple-choice quizzes
- Matching practice
- Template-aware quiz rules
- Active-session protection and duplicate-answer protection
- Mistake Book recovery workflow
- Proficient Pool random audits

### Statistics and review calendar

- Entry, template, collection, review, quiz, and special-pool statistics
- Review calendar and workload ranges
- Learning trends and entry-health views
- Read-only statistics architecture

### Daily learning workflow

- `Today` as the default learning home
- Due and overdue review workload
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
- bundled pronunciation audio
- bundled TTS voice models
- AI-generated vocabulary explanations, examples, or bulk learning content
- automatic correction of user-created entries
- cloud sync
- account login or authentication
- mobile app packaging
- a desktop GUI rewrite
- full destructive database restore

These exclusions reflect the current product scope.

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
    |-- review.py                # Review scheduling
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

Completed product capabilities:

- Local entry and collection management
- Collection Card review scheduling
- Quiz sessions and learning pools
- Template-based entries and French presets
- Statistics and Review Calendar
- CSV/XLSX import and export
- SQLite/XLSX backup and restore preview
- Today and Daily Learning Workflow
- Schema/app metadata and software-update compatibility foundation
- Productization QA and public-repository documentation polish

The project is now in a productization phase focused on public-repository safety, configuration, architecture boundaries, packaging feasibility, and update compatibility.

Detailed manual QA documents are available for recent milestones:

- `MILESTONE8_MANUAL_QA.md`
- `MILESTONE9_MANUAL_QA.md`
- `MILESTONE10_MANUAL_QA.md`
- `MILESTONE10_PRODUCTIZATION_QA.md`

## Roadmap

### Current productization phase

- Public GitHub readiness
- Product identity and user-owned content policy
- Local data and configuration safety
- Core/UI migration readiness
- Packaging feasibility
- Software-update and schema-version foundations
- Productization QA and Milestone 10 closure

### Future optional directions

- Language-learning enhancements that remain optional and copyright-safe
- Input-efficiency improvements compatible with the update architecture
- A future decision between packaging the local Streamlit app and migrating the UI to PySide6/PyQt

Dictionary databases, bundled pronunciation, and mandatory AI services are not current roadmap items.

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
