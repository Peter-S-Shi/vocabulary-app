# Data Safety

Vocabulary App stores vocabulary entries and learning activity locally.

## Local Database

The development database is:

```text
data/vocab.db
```

It may contain personal vocabulary, notes, source references, templates, collection membership, review history, quiz answers, and learning statistics.

- Do not commit this file to Git.
- Do not upload it to a public issue or discussion.
- Do not delete it unless you intentionally want to reset local data.
- Stop the app before manually copying the database.

## Backups

Create a backup before major upgrades or manual database operations.

The app can create:

- a consistent SQLite database snapshot
- a structured XLSX backup

XLSX restore is currently preview-only. It does not overwrite or merge into the active database.

## Imports and Exports

Import and export files may contain personal or third-party content.

- Make sure imported material is yours or that you have permission to use it.
- Review validation results before confirming an import.
- Inspect exported files before sharing them.
- Do not use public sample folders for private or copyrighted data.

## Public Support Requests

When reporting a problem:

- describe the schema or workflow instead of attaching a personal database
- remove personal terms, meanings, notes, and source references from screenshots
- create a small fictional reproduction file when sample data is necessary

This document provides practical product guidance, not legal advice.

