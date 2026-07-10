# Local Data Storage

Vocabulary App is local-first. In the development version, its SQLite database is stored by default at:

```text
<project root>/data/vocab.db
```

The database contains user-created entries and learning records. It is user data, not source code.

## Git and the Data Folder

`data/.gitkeep` is an empty repository placeholder that keeps the folder structure available after cloning.

`data/vocab.db` is the real local database. It is ignored by Git and should never be committed to a public repository.

## Optional Database Path Override

Normal users do not need to configure a path. Developers and advanced users may set `VOCAB_APP_DB_PATH` before launching the app.

PowerShell:

```powershell
$env:VOCAB_APP_DB_PATH="E:\VocabularyAppData\vocab.db"
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
- XLSX backup stores supported tables as structured sheets.
- XLSX restore remains preview-only and does not overwrite the active database.

Stop the app before manually copying `vocab.db`.

## Future Packaged App Direction

No automatic path migration is implemented. A future packaged desktop version may use an operating-system app-data directory:

- Windows: `%LOCALAPPDATA%/VocabularyApp/`
- macOS: `~/Library/Application Support/VocabularyApp/`
- Linux: `~/.local/share/vocabulary-app/`

Moving existing data would require an explicit, backup-aware migration workflow.

