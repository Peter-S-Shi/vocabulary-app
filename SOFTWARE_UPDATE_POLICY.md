# Software Update Policy

Vocabulary App is a local-first application. User-created vocabulary data is stored in a local SQLite database and should be treated as the most important asset in the project.

Milestone 10.6 establishes the first explicit schema-version baseline. Earlier schema changes were handled through app initialization and additive table or column creation.

## Update Principles

- Preserve user-created entries, meanings, examples, notes, template values, collection membership, quiz logs, review logs, imports, exports, and backups.
- Prefer additive database changes: new nullable columns, new tables, new indexes, or new metadata keys.
- Do not delete or rewrite user learning content automatically during migration.
- Make migrations idempotent so they can run safely more than once.
- Recommend backups before major upgrades or any migration that touches durable user data.
- Keep optional future modules disabled by default.

## Schema and App Metadata

The `app_metadata` table stores lightweight compatibility information:

- `schema_version`
- `app_data_version`
- `last_migration_at`
- future optional feature flags

Current baseline:

```text
schema_version = 10.6.0-baseline
app_data_version = 10.6
```

Future migrations should be registered in `src/migrations.py` and run through database initialization.

## Optional Future Modules

The current core app does not include:

- built-in dictionary databases
- bundled pronunciation audio or TTS voice models
- AI-generated learning content as a core dependency
- cloud sync or account login

Future dictionary, pronunciation, AI, or advanced import assistance should be optional, disabled by default, and compatible with local-first data ownership.

## Developer Migration Checklist

Before adding a migration:

1. Is the migration additive?
2. Does it preserve user entries and logs?
3. Is it idempotent?
4. Can it run on an old database safely?
5. Is backup recommended before running?
6. Are optional features disabled by default?
7. Does the migration avoid bundled third-party language datasets?

## User Safety Guidance

Before major upgrades, users should create a backup from the app or copy the database while the app is stopped. The app should not silently move, replace, or overwrite the active database.
