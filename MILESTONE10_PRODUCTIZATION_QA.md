# Milestone 10 Productization QA

## GitHub Safety

- [ ] `.venv/`, `venv/`, and `env/` are ignored.
- [ ] `__pycache__/`, `*.pyc`, and other Python bytecode files are ignored.
- [ ] `.env` and Streamlit secrets are ignored.
- [ ] Local SQLite databases are ignored: `data/*.db`, `data/*.sqlite`, `data/*.sqlite3`.
- [ ] `data/.gitkeep` remains allowed.
- [ ] User-generated `backups/`, `exports/`, and `user_data/` are ignored.
- [ ] No real user vocabulary database is committed.
- [ ] No real user import/export workbook is committed.
- [ ] No copyrighted dictionary data, word list, pronunciation audio, or AI-generated dataset is included.

## Documentation

- [ ] README describes the app as local-first and user-owned.
- [ ] README links to content, data-safety, architecture, migration, packaging, and software-update documentation.
- [ ] Product identity is consistent across documentation.
- [ ] Documentation states that dictionary, pronunciation, bundled audio, and AI-generated learning content are not core app features.
- [ ] Streamlit is described as the temporary UI layer.
- [ ] Future directions are optional and update-compatible.

## Architecture

- [ ] Core modules do not import Streamlit.
- [ ] Streamlit UI code remains in `app.py` and `src/ui_streamlit/`.
- [ ] SQL and durable business rules do not move into `app.py`.
- [ ] App configuration remains UI-independent.
- [ ] Migration logic lives in `src/migrations.py`.
- [ ] Backup, import/export, review, quiz, statistics, and learning workflow modules remain reusable.

## App Behavior

- [ ] Today page loads.
- [ ] Entries page loads.
- [ ] Collections page loads.
- [ ] Review page loads.
- [ ] Quiz page loads.
- [ ] Statistics page loads.
- [ ] Import / Export page loads.
- [ ] Review History / Schedule page loads.
- [ ] Settings / Data page loads.
- [ ] Existing entries, collections, review states, quiz logs, and statistics remain accessible.

## Update Safety

- [ ] `app_metadata` exists after app initialization.
- [ ] `schema_version` is visible as read-only Settings / Data information.
- [ ] `app_data_version` is visible as read-only Settings / Data information.
- [ ] `last_migration_at` is visible as read-only Settings / Data information.
- [ ] Optional future feature flags are disabled by default.
- [ ] Migration policy is documented in `SOFTWARE_UPDATE_POLICY.md`.
- [ ] Backup-before-upgrade principle is documented.
- [ ] Future migrations are expected to be additive and idempotent.

## Import / Export / Backup Safety

- [ ] Import still follows Upload -> Validate -> Preview -> Confirm -> Import.
- [ ] Duplicate detection remains available.
- [ ] Template field map export still works.
- [ ] SQLite backup remains user-controlled.
- [ ] XLSX backup remains user-controlled.
- [ ] Restore-lite remains preview-only and does not overwrite the active database.

## Current Result

Milestone 10.7 is a QA and documentation closure milestone. It does not add dictionary lookup, pronunciation playback, bundled audio, AI-generated learning content, cloud sync, login, desktop GUI rewrite, or destructive restore behavior.

## Checks Run During Implementation

- [x] Python compile check passed for changed app/config/database/migration/settings files.
- [x] `scripts/audit_architecture.py` reported no serious boundary violations and no warnings.
- [x] `tools/check_packaging_readiness.py` completed successfully.
- [x] Packaging readiness warning noted: local `data/vocab.db` exists and must remain excluded from Git/release archives.
- [x] `init_db()` created/read `app_metadata` successfully on the existing local database.
- [x] Default optional feature flags were initialized as disabled.
