# Local Data Storage

Vocabulary App is local-first. The desktop app and current source entry point
store SQLite data by default under the platform's per-user data directory:

```text
%LOCALAPPDATA%\vocabulary_app\vocab.db  (Windows)
```

Off Windows, the database uses `$XDG_DATA_HOME/vocabulary_app/vocab.db` or
`~/.local/share/vocabulary_app/vocab.db`. The repository's `data/` folder is a
legacy placeholder, not the current desktop database destination.

The database contains user-created entries and learning records. It is user data, not source code.

From M11.3, learning records include stable Card identity, ordered Card
membership revisions, nullable Quiz-to-revision links, and compact Entry edit
events. Revision membership stores Entry IDs and positions rather than copying
full Entry content. Ordinary browsing and Quiz activity do not create new Card
revisions.

Hard-deleting an Entry removes its current Entry row and Collection membership,
but preserves its existing Quiz item logs, Card revision membership IDs, and
Entry-change events. Quiz logs already store prompt, expected answer, user
answer, correctness, and the original `entry_id`; the app does not fabricate
the deleted Entry's full content.

Deleting an entire Collection is different: it is an explicitly destructive
operation that removes the Collection's Card identity/revision history, legacy
Review state/history, Quiz sessions, and Quiz item logs. The UI requires the
Collection name plus an acknowledgement of permanent history deletion. The
Vocabulary Entries themselves remain in the local database.

From M13, a Collection may also have one `collection_source_links` metadata
row for a user-selected local CSV or XLSX append source. This row stores the
local `source_path`, file type, import mode, optional worksheet name, link time,
and last successful refresh time. It does not copy the source file into SQLite
and does not store permanent source-row identity, hashes, or Entry mappings.

The linked file is non-authoritative. A manual confirmed refresh may append
new valid rows, but source deletion, reordering, or editing does not delete,
reorder, or overwrite existing app Entries. If the file is moved, deleted, or
unavailable after a database is restored on another machine, refresh returns a
controlled unavailable-source result and preserves existing app data and link
metadata. Unlinking removes only the metadata row.

## Git and the Data Folder

`data/.gitkeep` is an empty repository placeholder that keeps the folder structure available after cloning.

Any `data/vocab.db` left by an older checkout is private local data. SQLite
files are ignored by Git and must never be committed to a public repository.

## Optional Database Path Override

Normal users do not need to configure a path. Developers and advanced users may set `VOCAB_APP_DB_PATH` before launching the app.

PowerShell:

```powershell
$env:VOCAB_APP_DB_PATH="$env:USERPROFILE\VocabularyAppData\vocab.db"
python -m streamlit run app.py
```

macOS or Linux:

```bash
VOCAB_APP_DB_PATH="$HOME/VocabularyAppData/vocab.db" python -m streamlit run app.py
```

The app creates the selected parent directory when opening the database. An override selects a different database; it does not copy, merge, or migrate the project database.

## Backups

Backups are user-data files and should be stored separately from source code.

- SQLite backup is a consistent snapshot of the active database.
- XLSX backup stores supported tables as structured sheets, including M11.3
  Card identity/revision and Entry-change tables, plus M13 linked-source
  metadata.
- XLSX restore remains preview-only and does not overwrite the active database.

Because linked-source metadata includes `source_path`, private SQLite and XLSX
backups may contain local file paths. Treat backups as private user data and do
not publish or commit them.

Stop the app before manually copying `vocab.db`.

## Packaged Desktop Data Location

The packaged desktop app stores durable per-user data outside the installation directory. On Windows, the default data directory (and bootstrap locator directory for `data-root.json` and `migration-recovery.json`) is:

- Windows: `%LOCALAPPDATA%\vocabulary_app\`

Off Windows, the same default falls back to XDG data-home semantics: `$XDG_DATA_HOME/vocabulary_app` when that variable is set, otherwise `~/.local/share/vocabulary_app`.

Starting in **v1.2.0**, users can select a unified data folder on another drive or directory via **Settings → Storage** (relocating `vocab.db`, `backups/`, `preferences.json`, and `audio-cache/` together). If a selected data root or its pointer/recovery state is missing, inaccessible, or damaged, startup fails closed with recovery guidance rather than creating a blank database or silently falling back.

`VOCAB_APP_DB_PATH` (along with `VOCAB_APP_BACKUP_DIR`, `VOCAB_APP_AUDIO_CACHE_DIR`, and `VOCAB_APP_PREFERENCES_PATH`) overrides only its respective component path (see "Optional Database Path Override" above); it selects a different path to open and does not automatically copy, merge, or migrate data between locations. Do not treat an environment variable override as a complete data-folder move; the confirmed, in-app full-data migration is provided by **Settings → Storage** (M23-B/C, shipped in **v1.2.0**).

## M23-A selected-root startup foundation (v1.2.0)

The accepted M23-A foundation in v1.2.0 accepts a versioned `data-root.json` location
pointer in the established default data directory. If absent, default v1.1.0-compatible paths
remain unchanged. A valid pointer names an existing absolute folder containing
an existing, readable and writable `vocab.db` with Vocabulary App metadata;
the app resolves that folder before opening SQLite. Without component-specific
overrides, SQLite, backups,
audio cache and preferences resolve together under the selected folder.
Missing, malformed, inaccessible or damaged pointer/database state fails
startup with a recovery message; it does not create a new database or silently
fall back.
A running process refuses a pointer switch until restart. The pointer is not a
user-facing setting, and does not require manual file edits. Do not create or edit it
manually to move live data.

The existing four explicit environment overrides each retain precedence over
their respective component. A partial override still requires a healthy
selected root for the remaining components. All four overrides together can
bypass a damaged pointer for advanced recovery only when the overridden
database already exists and passes validation; this is not an in-app
migration. Settings continues to identify environment-selected paths.

## M23-B/C unified data relocation and Settings storage workflow

The M23-B/C implementation (shipped in **v1.2.0**) provides unified, confirmed
data-folder relocation via **Settings → Storage**. Key invariants verified in
`src/app_config.py`, `src/data_relocation.py`, and `src/data_lock.py`:
- **Unified 4-component scope:** SQLite database (`vocab.db`), backups
  (`backups/`), audio cache (`audio-cache/`), and preferences (`preferences.json`)
  relocate together.
- **Sibling-directory staging & atomic no-clobber promotion:** a sibling staging
  directory is created under the target parent filesystem (`<parent>/.vocab-stage-<uuid>`)
  and pre-populated with the root provenance + four-component manifest marker
  (`.vocab_app_root_marker.json`). On Windows, final directory promotion uses
  **`MoveFileExW` with `MOVEFILE_WRITE_THROUGH` and without `MOVEFILE_REPLACE_EXISTING`**
  (`src/data_relocation.py:_atomic_promote_no_clobber`) to promote the prepared
  staging directory to an **absent** destination folder; occupied destinations
  fail closed without a check-then-replace race. (`os.replace` is used for
  atomic temp-file updates to `migration-recovery.json` and `data-root.json`,
  not as the Windows directory promotion mechanism.)
- **SQLite snapshot consistency:** uses SQLite online backup (`Connection.backup()`)
  and staging WAL truncation (`PRAGMA wal_checkpoint(TRUNCATE)`) without raw
  WAL/SHM copying.
- **Cross-process writer quiescence:** cross-process OS file locking
  (`.app_data.lock`, implemented in `src/data_lock.py` using pointer-sized Win64
  `OVERLAPPED` with `LockFileEx` on Windows and `flock` off Windows) coordinates
  all active writers and connections. Active SQLite connections
  (`LockedConnection` in `src/db.py`), preference writes, audio-cache
  materialization/composition (`AudioAssetStore.materialize` and
  `compose_card_audio`), pre-migration backups, and database imports hold
  **shared** locks for their active connection/operation lifetimes, while
  relocation (`src/data_relocation.py`) acquires an **exclusive** lock.
- **Durable recovery journal & four-component SHA-256 manifest verification:**
  `migration-recovery.json` in the default OS root (`src/app_config.py`,
  `src/data_relocation.py`) records `SWITCHING → COMMITTED` transitions alongside
  `.vocab_app_root_marker.json` provenance (`source_root`, `target_root`,
  `marker_uuid`) and four-component streaming 64KB SHA-256 manifests (`vocab.db`,
  `preferences.json`, `backups/`, `audio-cache/`). This enables safe idempotent
  rollback if interrupted before target promotion, or verified forward recovery
  to `COMMITTED` if interrupted after promotion. Any missing, damaged, or
  mismatched committed pointer (`data-root.json`), recovery journal, or target
  folder fails closed (`DataRootError`) at startup with actionable recovery
  guidance.
- **Retained rollback baseline:** source files are preserved intact and never deleted.
- **Restart boundary:** requires an immediate application restart after cutover,
  and blocks writes to the stale pre-cutover root inside the running process.
