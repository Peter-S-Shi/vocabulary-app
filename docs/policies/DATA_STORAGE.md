# Local Data Storage

Vocabulary App is local-first. In the development version, its SQLite database is stored by default at:

```text
<project root>/data/vocab.db
```

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

`data/vocab.db` is the real local database. It is ignored by Git and should never be committed to a public repository.

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

The packaged desktop app stores durable per-user data outside the installation directory. On Windows, the default data directory is:

- Windows: `%LOCALAPPDATA%\vocabulary_app\`

Off Windows, the same default falls back to XDG data-home semantics: `$XDG_DATA_HOME/vocabulary_app` when that variable is set, otherwise `~/.local/share/vocabulary_app`.

`VOCAB_APP_DB_PATH` overrides only the database file path (see "Optional Database Path Override" above); it selects a different database file to open and does not automatically copy, merge, or migrate data between locations. Moving existing data between locations remains an explicit, backup-aware operation the user performs themselves.
