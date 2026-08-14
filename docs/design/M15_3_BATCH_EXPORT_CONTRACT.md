# M15.3 Batch Audio Export Contract

Status: Complete on `main` through PR #17 at
`9448f2e44940e0d426a965823aa66c48f53ec0f1`.

## Service and snapshot boundary

`src/audio_export.py` is a UI-independent consumer of the frozen M15.1 speech
plan and M15.2 audio asset/Card composition engine. It supports one current
Card, a caller-ordered selection, and every active Card in Collection display
order. Every scope produces one WAV per Card; a Collection is never one file.

Planning is read-only and does not create the destination. Each item records
order, Collection/Card/revision provenance, display metadata, render key,
composition configuration, readiness, and destination. Its embedded M15.2
`CardAudioPlan` is the frozen snapshot; execution never silently replans it.

## Destination and failure contract

The caller chooses the root. Names are sanitized against control characters,
separators, traversal, Windows reserved names, trailing dots/spaces, and excess
length; resolved paths must remain below the root. The default conflict policy
is `skip`; `overwrite` must be explicit.

Each Card is copied from a validated cache render into a same-directory
temporary artifact, validated, and atomically published. Temporary artifacts
are cleaned, and cache files are never moved. Outcomes are `succeeded`,
`skipped`, `failed`, or `unresolved`; independent Cards continue and batch
counts make partial success explicit.

Progress reports planning, Card start, render readiness, publish, controlled
non-success, and completion. Results retain provenance, render key, path,
cache reuse, and controlled error information.

A retry targets only failed/unresolved items. Failed items retain the exact
frozen plan. An unresolved item may be explicitly refreshed after repair.
Successful outputs are omitted, and the original conflict policy is retained.

## Authority and scope

The cache is disposable and content-addressed. Exported files are deliberate
user artifacts, but not authoritative app data and not auto-synchronized after
edits. Export mutates no Entry, Collection, Card history, Quiz/review evidence,
analytics, or learning state. There is no schema/app-data migration.

Audio-enabled Quiz behavior is deferred beyond M15. M15 provides reusable
audio-export infrastructure only and does not add spoken Quiz modes or modify
existing Quiz learning semantics.
