# Vocabulary App

Vocabulary App is a local-first vocabulary learning system for people who want to create, edit, organize, review, quiz, analyze, import, export, and back up their own learning entries.

**v1.0.0 is the current completed public Portfolio release.** The primary product surface is a native Windows desktop application built with PySide6 and SQLite. The earlier Streamlit UI remains in the repository as a compatibility/reference surface; it is not the v1.0 release target.

## Release Status

- **Current version:** `v1.0.0`
- **Platform:** Windows 10/11 x64
- **Distribution:** GitHub Releases
- **Installer:** `VocabularyApp-Setup-1.0.0.exe`
- **Release source:** tag `v1.0.0` → merge commit `2363e73bbd85ca24f7e227f8007e0046eeabd471`
- **Installer SHA-256:** `108095e3ce7d256bc610c33f427a9ee2fee4956cb69dde3bf0e105413865b297`
- **License:** MIT

The v1.0.0 installer is Authenticode-signed with a **self-signed developer certificate** (`CN=Peter Shi`). This verifies the project signing pipeline but is **not** a publicly trusted certificate, so Windows SmartScreen may still show an unrecognized-app warning. Public-trust reputation is not claimed by this release.

See the [v1.0.0 GitHub Release](https://github.com/Peter-S-Shi/vocabulary-app/releases/tag/v1.0.0) for the published installer, checksum metadata, release notes, and known limitations.

## Overview

Vocabulary App turns a user-owned vocabulary database into a repeatable learning workflow:

1. Create or import entries.
2. Organize entries into Collections and Cards.
3. Browse or study Cards as preparation.
4. Complete Card-scoped quizzes as the authoritative Card learning event.
5. Review progress through Today, Review Calendar, and Analytics.
6. Export, back up, or migrate local data explicitly.
7. Optionally export Card audio using compatible speech voices already installed on Windows.

The `Today` workspace acts as the daily learning home. Its Card-learning activity and summaries use factual completed Card-scoped Quiz history rather than legacy Review-schedule state.

## Lifecycle Status

Milestones 1-20 are complete for the v1.0 product lifecycle.

- M11 established the Trustworthy Pre-Desktop Baseline.
- M12 reorganized repository and documentation structure.
- M13 established Import and Template Evolution Core.
- M14 established Learning Analytics and Insight Core.
- M15 established the reusable Audio Foundation.
- M16 selected PySide6 and froze the native desktop architecture/design baseline.
- M17 migrated the core daily workflow to the native desktop product.
- M18 completed management, data, Analytics, and Card Audio Export workflows.
- M19 completed system-wide Desktop Product Hardening and Human Acceptance.
- **M20 completed Windows packaging, distribution QA, release-candidate verification, Human RC Acceptance, version finalization, tagging, and public v1.0.0 publication.**

Human RC PASS was granted on 2026-08-19 against exact RC SHA `89263a4f0f477fe5455ed22bedffd1968218bb1e`. PR #33 was subsequently merged, release metadata was finalized to `1.0.0`, tag `v1.0.0` was bound to merged `main` SHA `2363e73bbd85ca24f7e227f8007e0046eeabd471`, and the canonical installer was built from that tagged source and published through GitHub Releases.

See [PROJECT_STATUS.md](PROJECT_STATUS.md) for the current evidence-based release snapshot and [ROADMAP.md](ROADMAP.md) for milestone definitions and historical lifecycle detail.

## Product Philosophy

- **Local-first:** durable learning data is stored locally in SQLite.
- **User-owned content:** users create, edit, import, and maintain their own entries.
- **Explicit control:** Card composition, quiz answers, pool membership, imports, deletion, backup, and database migration actions remain user-controlled.
- **No hidden language authority:** the app organizes learning data but does not claim to verify linguistic accuracy.
- **No account / cloud dependency:** v1.0 requires no account, telemetry, cloud sync, or mandatory external service.
- **Migration-safe release design:** application binaries and durable user data are separated, and database upgrades create safety backups before migration.

Users are responsible for ensuring that content they create, import, export, or share is accurate and that they have permission to use it.

See [Content Policy](docs/policies/CONTENT_POLICY.md) for the detailed user-owned content boundary.

## Current Features

### Entries and templates

- Entry creation, editing, search, filters, selection, and batch deletion
- Structured Quick Add text parsing
- General and custom entry templates
- Built-in French template presets
- Template field values included in search and display
- Starred and Proficient Pool batch actions

### Collections and Cards

- Configurable Collection Card sizes
- Collection-specific Entry ordering
- Dynamic Card-number calculation
- Add, remove, reorder, and delete Collection workflows
- Stable Card identity and membership revision history
- System Collections for Mistake Book, Starred, and Proficient Pool

### Study, Quiz, and learning history

- Collection Card browse/study surface
- Quick Card Quiz and Choose Quiz Type handoff routes
- Self-graded term/meaning quizzes
- Multiple-choice, mixed multiple-choice, and matching practice
- Template-aware quiz rules
- Active-session and duplicate-answer protection
- Completed Card-scoped Quiz history as the authoritative Card learning event
- Mistake Book recovery and Proficient Pool audit workflows
- Legacy Review/SRS state retained only where required for compatibility/history

### Today and Review Calendar

- `Today` Command Center as the daily learning home
- Available-Card and never-quizzed workload
- Daily quiz suggestions and recent activity
- Card-study / Quiz navigation
- Daily learning summary based on completed Card-scoped Quiz sessions
- Review Calendar / Card History workspace

### Analytics

- Learning Brief and Full Findings desktop views
- Entry, Template, Collection, Card-learning, Quiz, and special-pool statistics
- Historical ranges and learning trends
- Read-only Analytics architecture over reusable core evidence

### Import, export, and backup

- CSV and XLSX export
- General and template-based import
- Validate → Preview → Confirm → Import workflow
- Duplicate handling
- Collection/Card-aware import and export
- Template Definition CSV import/export
- SQLite backup snapshots
- Structured XLSX backup and restore preview
- Explicit existing-database import using copy-with-backup semantics; the source database is never moved

### Card Audio Export

- Single Card / Selected Cards / Whole Collection export scopes
- Repetition and overwrite/skip controls
- Background provider preflight and progress UI
- Local Windows Speech Provider / Installed Voice Binding
- Compatible voices are enumerated from the user's own Windows installation
- v1.0 does **not** bundle, download, install, or redistribute Kokoro, sherpa-onnx, Piper voices, a third-party TTS runtime, or third-party voice models
- If no compatible local voice is installed for a supported route, audio capability reports itself unavailable/configuration-required instead of silently downloading a replacement

## What This App Does Not Include

The v1.0 release does not include:

- built-in dictionary databases
- copyrighted bundled word lists
- bundled pronunciation recordings
- bundled or downloaded third-party TTS models/runtimes
- AI-generated vocabulary explanations, examples, or bulk learning content
- automatic correction of user-created entries
- cloud sync
- account login or authentication
- telemetry
- mobile packaging
- automatic software updating
- full destructive database restore

## Install v1.0.0 on Windows

### Recommended: GitHub Release installer

Download `VocabularyApp-Setup-1.0.0.exe` from the [v1.0.0 GitHub Release](https://github.com/Peter-S-Shi/vocabulary-app/releases/tag/v1.0.0).

The installer is per-user and does not require administrator installation mode. The primary installation root is under the current user's Local AppData Programs directory, while durable app data is stored separately under:

```text
%LOCALAPPDATA%\vocabulary_app\
```

The installer preserves user data by default when uninstalling. Destructive data removal requires an explicit opt-in.

Verify the published installer if desired:

```text
SHA-256  108095e3ce7d256bc610c33f427a9ee2fee4956cb69dde3bf0e105413865b297
```

Because the release uses a self-signed developer certificate rather than a publicly trusted certificate, SmartScreen may warn even though the artifact is signed. This is an acknowledged distribution limitation of the Portfolio release.

## Run from Source

Source execution is intended for development, inspection, and compatibility work rather than the normal v1.0 installation path.

### Prerequisites

- Python 3.10 or newer is recommended.
- Git is optional if the project is downloaded as an archive.

### Windows PowerShell

```powershell
git clone <repository-url>
cd vocabulary-app
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
.\.venv\Scripts\python.exe -m src.ui_desktop
```

### Streamlit compatibility/reference UI

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Streamlit normally opens at `http://localhost:8501`. It remains useful for compatibility/reference work but is not the packaged v1.0 product surface.

## Local Data and Privacy

On the packaged Windows release, the default durable data root is:

```text
%LOCALAPPDATA%\vocabulary_app\
```

Key locations include:

```text
%LOCALAPPDATA%\vocabulary_app\vocab.db
%LOCALAPPDATA%\vocabulary_app\backups\
%LOCALAPPDATA%\vocabulary_app\preferences.json
%LOCALAPPDATA%\vocabulary_app\audio-cache\
```

Application binaries are installed separately from user data. Uninstall preserves the data root by default.

Before schema migration, the app creates a safety backup. Existing databases are imported through an explicit user-selected copy workflow with backup protection; the source file is not moved or edited in place.

Advanced users may use environment overrides such as `VOCAB_APP_DB_PATH` for isolated development/testing. Repository-local databases, exports, backups, logs, caches, virtual environments, secrets, and machine-specific paths must never be committed.

See [Data Storage](docs/policies/DATA_STORAGE.md), [Data Safety](docs/policies/DATA_SAFETY.md), and [Software Update Policy](docs/policies/SOFTWARE_UPDATE_POLICY.md) for detailed handling rules.

## Architecture

The native desktop application under `src/ui_desktop/` is the primary product surface. Reusable learning/data logic remains framework-independent under `src/`; desktop views/controllers consume those APIs rather than duplicating domain logic or SQL.

The Streamlit compatibility UI remains under `app.py` and `src/ui_streamlit/`. PySide6 imports are restricted to the desktop boundary.

Major architecture/design references:

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [DESIGN.md](DESIGN.md)
- [Desktop Migration Plan](docs/migration/DESKTOP_MIGRATION_PLAN.md)
- [M16.1 Desktop Architecture Contract](docs/design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md)
- [M15.1 Speech Semantic Contract](docs/design/M15_1_SPEECH_SEMANTIC_CONTRACT.md)
- [M15.3 Batch Audio Export Contract](docs/design/M15_3_BATCH_EXPORT_CONTRACT.md)

## Tech Stack

- Python 3
- PySide6 — primary native desktop UI
- SQLite — local durable data
- Streamlit — compatibility/reference UI
- openpyxl — XLSX workflows
- PyInstaller `--onedir` — Windows application packaging
- Inno Setup — per-user Windows installer
- Windows local speech APIs / installed voices — v1.0 audio provider model

## Project Structure

```text
vocabulary-app/
|-- app.py                         # Streamlit compatibility/reference shell
|-- requirements.txt               # Core + Streamlit compatibility dependencies
|-- requirements-desktop.txt       # PySide6 desktop dependency
|-- README.md
|-- PROJECT_STATUS.md
|-- ROADMAP.md
|-- DESIGN.md
|-- winbuild/                      # PyInstaller + Inno Setup release tooling
|-- docs/                          # Design, policy, QA, packaging, and history records
|-- sample_data/
`-- src/
    |-- app_config.py              # Version, paths, app configuration
    |-- db.py                      # Database connection and initialization
    |-- entries.py                 # Entry CRUD/search
    |-- entry_templates.py         # Template management
    |-- migrations.py              # Schema/app metadata and additive migrations
    |-- collections.py             # Collections, Cards, ordering
    |-- card_history.py            # Stable Card identity and revisions
    |-- quiz.py                    # Quiz sessions and answer logs
    |-- statistics.py              # Read-only statistics queries
    |-- learning_workflow.py       # Today workflow queries
    |-- import_export.py           # Import/export validation and execution
    |-- backup.py                  # Backup / restore-preview helpers
    |-- audio_export.py            # Card Audio Export planning/execution
    |-- ui_desktop/                # Primary PySide6 product surface
    `-- ui_streamlit/              # Compatibility/reference Streamlit surface
```

## Release Verification Summary

The M20 Human RC / release process recorded the following evidence before publication:

- Full repository regression: **911 tests, 0 failures, 0 errors** at the Human-RC-accepted RC source
- Architecture audit: clean
- Fresh local standard-account install/launch/reinstall/uninstall verification
- Fresh database creation and representative existing-database import verification
- Backup-before-upgrade and real schema-migration verification
- Local Windows speech-voice enumeration verification
- Release payload/privacy inspection
- Self-signed Authenticode signing-pipeline verification
- Final `1.0.0` version/build/signature/install/launch/uninstall smoke verification
- Canonical release build manifest bound to merged/tagged source SHA `2363e73bbd85ca24f7e227f8007e0046eeabd471`

The detailed release contract and QA evidence are in:

- [M20 Release Contract](docs/packaging/M20_RELEASE_CONTRACT.md)
- [M20 Distribution QA Checklist](docs/packaging/M20_DISTRIBUTION_QA_CHECKLIST.md)
- [M20 Code Signing Setup](docs/packaging/M20_CODE_SIGNING_SETUP.md)
- [PROJECT_STATUS.md](PROJECT_STATUS.md)

## Known Distribution Limitations

- The v1.0 Portfolio release uses a self-signed Authenticode developer certificate, not a publicly trusted signing identity; SmartScreen reputation is not guaranteed.
- Full pristine clean-machine VM verification was deferred; v1.0 distribution acceptance used a fresh local standard Windows account plus the recorded install/migration/uninstall evidence.
- v1.0 is Windows 10/11 x64 only.
- Audio availability depends on compatible speech voices already installed on the user's Windows system.
- There is no automatic updater; upgrades use a new installer while preserving durable user data and creating migration safety backups.

## Roadmap and History

The completed v1.0 lifecycle was:

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
-> v1.0.0 Released
```

Future work, if any, is outside the completed v1.0 lifecycle and should begin from a new explicitly defined milestone/roadmap decision rather than reopening M20.

Historical evidence remains available throughout `docs/history/`, `docs/qa/`, and the milestone sections of [ROADMAP.md](ROADMAP.md).

## License

Vocabulary App is released under the [MIT License](LICENSE).

Copyright (c) 2026 Yunsong Shi (Peter Shi)
