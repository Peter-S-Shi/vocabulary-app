# Vocabulary App Project Status

Last reviewed: 2026-08-11

This file is the authoritative evidence-based snapshot of the current project
state.

Lifecycle intent and future milestones are defined in `ROADMAP.md`.

Desktop-specific migration principles and workflow mapping are defined in
`docs/migration/DESKTOP_MIGRATION_PLAN.md`.

## Current Phase

**Import and Template Evolution Core Complete**

## Current Milestone

**Milestone 13 Complete**

M11.1 Semantic Alignment and QA Scope Lock has been merged to `main`.
M11.2 Unified Learning Flow and Core Integrity is merged to `main` at
`eb8cda4e50b987b5db37b36425d3e47c94c28eaa`.
M11.3 Stable Card Identity and Entry-Level History is merged to `main` at
`ccda6b8385215835f3de997f268e2165c37249de`.
M11.4 Semantic Re-acceptance and Baseline Closure was merged through PR #5 to
`main` at `f0e0d2c06fa4137c07ab2f892df117af2ed3a060`. Its independent review and
merge gate is complete.

M12 Repository Restructure began from synchronized `main` at
`0bce62833632e7e73bdc4daf4430ba028415adfd` on branch
`agent/m12-repository-restructure`. It moved 14 tracked supporting documents
with `git mv`, created `docs/README.md`, and repaired current repository
references without changing application behavior.

M12 verified restructure commit:
`b4c119a2eb0f88108ea93554355ee62ec5a72634`. A later documentation-only
metadata commit may be the Draft PR head.

M13 began from merged M12 commit
`6e339ec846f22f14ee454d9ad0d68ba3fb83aee6` on branch
`agent/m13-import-template-evolution`.

```text
M13 Batch A — Template Definition Portability independently reviewed / passed
M13 Batch B — Linked Append Source independently reviewed / passed
M13 Batch C — Integration, Regression, and Closure verified / complete
```

Batch A defines Template Definition CSV version 1 with these exact columns:

```text
definition_version
template_name
template_description
language
template_type
field_key
field_label
field_type
required
display_order
```

The reusable core supports deterministic export, read-only preview and full
validation, explicit existing-name conflict handling, and atomic confirmed
import of one Template plus all fields. Imported definitions always create a
user-owned Template (`is_system = 0`). System ownership, internal IDs,
timestamps, Entry content, Entry field values, database paths, and the
not-yet-persisted `speech_language_role` are not portable fields.

Portable fields preserve their original non-negative integer `display_order`.
Ties are valid and use deterministic `(display_order ASC, field_key ASC)`
ordering for export, preview, and import insertion; values are not renumbered.

Batch A adds no schema or migration. Export/import round-trip verification
compares portable Template and ordered field semantics rather than internal IDs
or timestamps.

M13 Batch A verified correctness implementation commit:
`247652c56131b73f8bc582751c748e614dc7f890`. A later documentation-only
metadata commit may be the remote branch head during independent review.

Batch A passed independent review at branch head
`44fdde0fe79e6810b2cb1dc5a4fb3cbeea04dfab` and was merged through PR #8 to
`main` at `8574b31dde9b213fe83aade9583bf2e360fce0da`. The product owner then
authorized Batch B and Batch C on the same M13 branch. M14 remains unstarted.

Batch B implementation commit:
`633d7484874fbbf0beb7064e9abed9389414d9e4`.

Batch B adds one additive, idempotent migration:

```text
11.3.1-quiz-log-history
→ 13.0.0-linked-append-source
app_data_version = 13.0
```

The local-only `collection_source_links` table contains exactly:

```text
collection_id        INTEGER PRIMARY KEY
source_path          TEXT NOT NULL
source_type          TEXT NOT NULL        # csv | xlsx
import_mode          TEXT NOT NULL        # general_entry | template_aware
sheet_name           TEXT NULL
linked_at            TEXT NOT NULL
last_refreshed_at    TEXT NULL
```

Its Collection foreign key uses `ON DELETE CASCADE`. The linked file content,
source-row identity, row hashes, Entry mappings, and import history are not
stored. The metadata is included in database and XLSX backups.

The reusable Streamlit-independent core provides:

```text
get_collection_source_link(...)
preview_collection_source_link(...)
confirm_collection_source_link(...)
preview_linked_source_refresh(...)
confirm_linked_source_refresh(...)
unlink_collection_source(...)
```

Initial link and manual refresh rescan the current local CSV/XLSX through the
existing import engine and classify rows as New Valid, Invalid, or Duplicate.
Only New Valid rows can be appended after explicit confirmation. A readable
source with zero New Valid rows may still be linked. Preview is read-only;
confirmed writes use one transaction/savepoint for Entries, Collection
membership, Card-history reconciliation, link metadata, and refresh timestamp.

The linked file is non-authoritative. Source deletion, reordering, or editing
never deletes, reorders, or overwrites existing app Entries. App edits and
deletes never modify the source file. Because v1 deliberately stores no stable
source-row identity, an edited old row that becomes non-duplicate may later be
offered as New Valid and appended as another Entry. Missing or moved files
produce controlled errors while preserving the Collection, history, link, and
prior refresh timestamp. Unlink removes metadata only.

The existing General Entry and Template-aware import writers now reconcile
Card history on the same active connection even when the caller owns that
connection. Existing Collection Import explicitly defers per-row reconciliation
and continues to reconcile once per batch, avoiding history noise.

Before Batch C, `origin/main` and the reviewed Batch B branch were synchronized
with normal merge commit `5efaddc21a58e1610b2f8858dfd152507e1ec3c7`.
No upstream product changes existed beyond the known PR #8 Batch A merge.

Batch C verifies the combined M13 architecture end to end. A Template
Definition exported from one synthetic database imports as a user-owned
Template in another database and drives a template-aware Linked Append Source
without portable internal IDs. Shared `display_order = 0` fields remain
deterministic. Initial confirmation imports the Entry, field values, Collection
membership, Card revision, and source metadata atomically; unchanged refresh
imports zero and creates no history noise.

General Entry, Template-aware, and Collection import remain compatible.
Standalone duplicate `skip` and `import_anyway` retain their previous scope;
linked sources never expose `import_anyway`. Caller-owned transactions remain
rollbackable, while Collection Import defers row-level reconciliation and
creates one final Card-history reconciliation per batch.

Synthetic migration coverage proves the complete supported chain from
`10.6.0-baseline` through M11.3 to `13.0.0-linked-append-source`, direct M11.3
migration, failure rollback, fresh-schema convergence, and repeated-startup
idempotence without lost Entry, Collection, Quiz, Card, or link data. Database
and XLSX backups include link metadata. A copied database reopens cleanly; an
unavailable restored source path produces a controlled result without changing
Entries, Collection membership, Card history, link metadata, or refresh time.

Accepted M13 v1 limitations are:

- one linked source per Collection, manual refresh, and local CSV/XLSX only;
- `general_entry` and `template_aware` linked modes only;
- no source-row identity, hashes, overwrite, delete/reorder propagation,
  background watching, or desktop picker UI;
- an edited old row may appear as New Valid, and an app-deleted Entry may be
  offered again on a later refresh;
- a restored local source path may be unavailable on another machine; and
- Template Definition v1 is CSV-only, one Template per file, with no
  overwrite/merge/auto-rename, system ownership portability, or
  `speech_language_role`.

These are accepted scope limits, not data-integrity blockers.

```text
Milestone 12 Complete
Repository Restructure Complete
```

This is not Feature Freeze, Release Ready, Desktop Ready, Product Hardening
completion, or Current Version Complete.

The project is no longer preparing to freeze and release the existing
Streamlit application as the final current-version target.

Following full-product manual QA, real-world use, and product-owner review, the
scope has been reopened to:

- resolve correctness and data-semantic issues before migration;
- restructure the repository before another large development cycle;
- add reusable foundations for three new major capabilities;
- retire Streamlit as the long-term primary user interface; and
- complete the current product generation as a native desktop application.

## Product Direction

Vocabulary App remains a local-first, user-owned vocabulary learning system
built around a reusable Python + SQLite learning engine.

The strategic UI direction is now:

```text
Current Streamlit application
-> stabilized compatibility/reference baseline
-> native desktop application
-> desktop becomes the primary product
```

The governing migration principle remains:

> Replace the UI layer, preserve the learning engine.

Substantial new UI investment should target the desktop application rather than
the Streamlit interface unless a temporary Streamlit path is required to verify
reusable core behavior.

## Completed Historical Work

Milestones 1-10 remain completed historical development:

- Milestones 1-4: application foundation, entries, collections/cards, and
  review scheduling.
- Milestone 5: quiz sessions, learning pools, session safety, and quiz
  workflows.
- Milestone 6: entry templates, template-aware entries, template presets, and
  template-aware quizzes.
- Milestone 7: Statistics, Review Calendar, trends, and Entry Health.
- Milestone 8: CSV/XLSX import/export, backup generation, and restore preview.
- Milestone 9: Today and the daily learning workflow.
- Milestone 10: productization, repository documentation, architecture,
  packaging/migration assessments, app/schema metadata, and compatibility
  foundations.

These milestones established a substantial working Streamlit product baseline.

They do not represent the final desktop product or current-version completion.

## Full-Product Manual QA Status

A full-product manual QA artifact has now been established and used.

The latest reviewed QA set contains:

- 66 total items;
- 55 Pass;
- 6 Blocked;
- 5 Not Tested / N/A; and
- 0 Fail.

These counts do not mean the product is defect-free.

The QA process also identified:

- implementation defects;
- data/state semantic inconsistencies;
- UX and discoverability issues;
- stale historical acceptance expectations;
- documentation inconsistencies;
- product-design decisions;
- new feature requests; and
- areas requiring direct repository verification.

M11.1 reconciled all 66 stable QA IDs against the current repository and the
approved learning semantics:

- M11.2: 5 items;
- M11.3: 5 items;
- M11.4: 17 items;
- M12+/Desktop, M13, or Deferred: 12 items;
- stale expectation or verified no action: 27 items; and
- unable to verify from repository evidence: 0 items.

The counts above classify the QA inventory once per stable QA ID. Additional
repository-derived engineering findings are recorded separately in the M11.1
Draft PR and do not inflate the 66-item source total.

The original source results for M04-Q04, M05-Q05, and M07-Q02 remain Pass.
They are retained according to their own legacy-workflow meaning as
re-acceptance or superseded-expectation scope; they are not evidence for the
separate P1 finding that manual schedule updates are counted as completed
Review activity. That repository-derived finding is tracked independently as
`Derived M11-REVIEW-LOG-01` and does not change the source-item counts.

The manual QA artifact should remain a living project artifact and should be
updated only in sections affected by later milestones or regression work.

## Closed Pre-Desktop Priorities

### Entry Editing Integrity

M11.2 keyed editable state by permanent Entry ID. Automated Streamlit AppTest
coverage verifies that switching Entry A to Entry B does not leak unsaved
Language, Explanation Language, Entry Type, Status, canonical, Collection, or
Template-field widget state.

### Unified Review and Quiz Semantics

The approved authoritative model is:

```text
Browse / study a Card
-> complete a Card-scoped Quiz
-> one completed Card learning/review event
```

- Review is a Card browse/study/preparation surface and an entry point into
  Quiz. Browsing alone is not completion.
- A direct Card-scoped Quiz completion is valid without first entering Review.
- Quiz item activity remains the authoritative Entry-level performance
  evidence.
- A random or whole-pool Quiz remains valid performance activity but must not
  fabricate completion for an unrelated Card.
- Independent manual next-review scheduling, due/interval/ease state, and
  Again/Hard/Good/Easy are being retired from active product truth.
- No replacement SRS algorithm is approved for M11.

M11.2 enforces this model without adding a second event table:
`quiz_sessions.completed_at` is the Card learning-completion source for
completed Card-scoped Quiz sessions. Today, Statistics, and Learning History
derive Card completion only from that evidence. Manual scheduling and legacy
Review logs remain compatibility data but are no longer active completion
truth or active Streamlit workflow controls.

### Card Identity and Historical Truthfulness

The approved architecture resolves the product decision as follows:

- `entries.id` is the permanent authoritative Entry identity;
- Cards receive a stable durable `card_id`;
- `card_number` remains a display/order concept;
- Card membership remains user-mutable; and
- historical Card learning must retain the membership revision used at the
  time without false backfill.

M11.3 resolves the previous migration gap between:

- cards dynamically derived from collection order and `card_size`; and
- historical review/card records associated with collection and card number.

Current Card grouping remains dynamically derived from
`entry_collections.position + collections.card_size`. Stable `card_id` rows now
identify active slots, and immutable revisions record the ordered Entry IDs
that belonged to each Card at each material change.

The additive migration chain
`10.6.0-baseline -> 11.3.0-card-history -> 11.3.1-quiz-log-history`:

- establishes one active stable Card per current slot and one baseline revision;
- preserves active Card IDs across membership revisions;
- retires disappearing Cards and never reuses their IDs when a slot reappears;
- moves active Card names to stable identity while retaining the old metadata table as compatibility-only;
- binds new Card-scoped Quiz sessions to the exact `card_id` and `card_revision_id` used at start;
- leaves legacy pre-M11.3 Quiz composition null/unknown where it cannot be proved;
- records compact, field-level old/new evidence for successful non-no-op Entry edits;
- preserves existing `quiz_item_logs` after Entry hard deletion without
  inventing deleted Entry content; and
- requires an evidence-based Streamlit confirmation before user-driven cross-Card reorganization.

Collection mutation and Card-history reconciliation share one transaction.
Reads and ordinary Quiz activity create no Card revisions. The reusable core
remains Streamlit-independent and is suitable for a later native confirmation
dialog.

Known deletion boundary: Entry hard deletion preserves `quiz_item_logs`,
stored integer Entry IDs in Card revision snapshots, and
`entry_change_events`. Historical Quiz views fall back to
`Deleted Entry #<id>` plus the log's stored prompt/answer evidence.
Deleting an entire Collection retains the existing product behavior of
deleting that Collection's Card identity/revision history, legacy Review
history, Quiz sessions, and Quiz item logs. M11.4 accepts this as the current
destructive product contract because the UI requires the Collection name, an
explicit checkbox, and clear permanent-deletion wording. Vocabulary Entries
remain. No deleted-Collection preservation architecture is claimed.

M11.3 branch: `agent/m11-3-card-identity-history`.
M11.3 base: `eb8cda4e50b987b5db37b36425d3e47c94c28eaa`.
M11.3 verified implementation commit:
`f651a49271468c0442e75915f20a8b1aa17736e3`. The Draft PR head may include a
later documentation-only metadata commit; its exact head is recorded in the
Draft PR and closeout report.

M11.4 verification includes the complete M11.2/M11.3 regression suite plus
targeted stable-history, Entry Health, destructive Collection deletion,
restart/backup, stale-focus, duplicate-log, and edit-snapshot tests on isolated
synthetic databases. The complete suite passes all 38 tests, including the 6
targeted M11.4 closure tests. Python compilation, quiz-randomization,
migration-failure rollback, architecture, privacy, and packaging-readiness
checks also pass. The architecture audit scans 32 Python files with no serious
boundary violations or warnings. The packaging checker retains its expected
warning that the local personal database exists and must remain excluded from
Git/releases. No schema or migration file changes in M11.4.

M11.4 verified implementation commit:
`f0113e0592bf5198c429d3282c528c39b47f63fa`. PR #5 used documentation-only
head `b5c75ca52aa67f9fa5a7af7698358a709314d935` and merged as
`f0e0d2c06fa4137c07ab2f892df117af2ed3a060`.

Next engineering objective:
**Milestone 12 — Repository Restructure**.

### Entry Health

Entry Health remains an active and intended Statistics capability.

It is not deprecated.

Its interpretation must remain primarily performance-aware:

- Quiz attempts;
- correct/wrong outcomes;
- accuracy;
- recent performance;
- last-quizzed recency;
- Mistake Book;
- Proficient Pool; and
- related evidence.

Review count alone must not make an Entry Strong.

An Entry reviewed repeatedly but never tested can remain **Never Quizzed**.

M11.4 automated re-acceptance verifies that Entry Health derives attempts,
accuracy, recency, Weak/Neglected/Strong/At Risk results, and special-pool
signals from Quiz evidence and explicit pool membership. Artificially high
legacy `review_count`/`correct_count` values do not make a never-quizzed Entry
Strong; it remains **Never Quizzed**.

## Other QA Findings Requiring Later Triage

QA findings assigned outside active M11 implementation include:

- partial Chinese/French localization;
- hard-coded Entry Type filter behavior that does not naturally cover custom
  types;
- whether the Status filter should remain as a product decision;
- lack of one unified configurable display-order model across canonical and
  custom fields;
- Template Import Preview not fully exposing dynamic `field:*` information and
  proposed Template-definition import, assigned to M13;
- duplicate/merge and wider import-matching ideas, assigned to M13/M14 or
  Deferred according to later approved scope;
- keyboard, narrow-screen, localization, and external-evaluator work assigned
  to the desktop/hardening lifecycle; and
- Ordered Quiz Queue editing being implemented but poorly discoverable,
  assigned to the later desktop experience.

The old M05-Q03 Again/Hard/Good/Easy expectation and Streamlit Release Candidate
recommendation items are stale QA expectations. The old QA reading guide's
`Review = exposure/history` plus manual-date model is also superseded by the
approved M11 semantics; the original local QA input remains unchanged as
historical evidence.

Streamlit-only polish does not receive the same priority as data correctness,
historical truthfulness, privacy, or reusable core behavior.

## Active New Product Scope

Three major capabilities have now been approved for active product development.

### 1. Import and Template Evolution

The intended scope includes:

- Template Definition export;
- Template Definition CSV import;
- one CSV file defining one Template;
- validated preview and atomic Template creation;
- round-trip Template portability;
- linking a Collection to a local CSV/XLSX append source; and
- refresh analysis identifying new valid, invalid, and duplicate rows.

Linked local files are append sources.

Version 1 does not synchronize:

- deletion;
- reorder;
- modification of existing rows;
- application changes back to the source file; or
- bidirectional conflicts.

Reusable core behavior is planned before desktop migration.

Desktop-native file selection and refresh interaction are planned after the
desktop foundation exists.

### 2. Learning Analytics and Insight System

Statistics is being repositioned from primarily metric display toward
explainable learning analytics.

The intended analytical model distinguishes:

- raw measurements;
- comparisons and trends;
- evidence sufficiency;
- interpretable findings; and
- actionable user recommendations.

Important analytical principles include:

- completed Card-scoped Quiz = Card learning/review completion;
- Quiz item logs = demonstrated Entry-level performance;
- sparse data must not produce overconfident conclusions;
- personal baselines and relative performance are more useful than isolated
  percentages;
- Entry Health remains interpretable rather than becoming an opaque global
  score; and
- the initial insight engine should be deterministic and testable rather than
  dependent on mandatory AI generation.

Core analytical semantics and logic are planned before desktop migration.

The major dashboard and visualization redesign is planned for desktop.

### 3. Card Audio Export

The intended initial audio scope is local audio export.

Key decisions include:

- exactly one Card per exported audio file;
- multiple Cards may be generated in one batch;
- Collection selection produces multiple Card audio files rather than one
  monolithic Collection recording;
- speech assets are conceptually associated with Entry/Field content;
- Card audio is assembled from current Card membership/order at export time;
- required Template fields are included in the initial audio scope;
- optional fields are deferred;
- supported repetition modes include per-field repetition and whole-Card
  repetition;
- English, French, and Chinese are the initial target languages; and
- local TTS technology should use a distribution-compatible license strategy.

Audio-enabled Quiz playback is deferred.

The reusable speech/provider and Card-composition foundation is planned before
desktop migration.

The full batch-generation UI is planned for desktop.

## Cross-Feature Architecture Dependencies

The three major capabilities are not independent.

### Template and Audio

Audio generation requires deterministic knowledge of the language associated
with required Template field values.

Template-definition work should therefore account for speech-language
semantics where needed, such as whether a field uses:

- Entry language; or
- Explanation language.

### Analytics and Data Semantics

Learning Analytics must not be finalized on top of ambiguous Review history or
untruthful Card history.

Review-event semantics and Card-history strategy are therefore prerequisites
for trusted analytics.

### Desktop and Reusable Core

Major new business logic should be implemented independently of Streamlit where
practical so that the desktop application calls reusable services rather than
reimplementing business rules.

## Repository Structure Status

The repository remains functionally usable but structurally cluttered at the
top level compared with the owner's other mature projects.

A dedicated repository-restructure milestone is planned before the next large
feature-development cycle.

The restructure should:

- reduce root-level document clutter;
- create clear locations for lifecycle, migration, manual QA, historical, and
  supporting documentation;
- preserve Git history through moves where practical;
- repair internal references; and
- avoid opportunistic business-logic refactoring.

The restructure has not yet been executed.

## Desktop Migration Status

Desktop migration is now active product scope.

The existing migration foundation is favorable:

- reusable core modules are already separated from Streamlit in many areas;
- SQLite remains the durable source of truth;
- import/export validation and execution are largely UI-independent;
- backup logic is largely reusable;
- durable Quiz state lives in SQLite/core logic;
- Today workflow queries are reusable; and
- architecture checks have previously confirmed substantial Streamlit/core
  separation.

However, no final desktop framework has yet been approved.

No minimal desktop shell has yet established production-level compatibility.

`docs/migration/DESKTOP_MIGRATION_PLAN.md` has been revised as part of the current lifecycle
alignment to remove the superseded Streamlit-first Release Candidate
prerequisite.

## Streamlit Status

Streamlit remains temporarily supported as:

- the current runnable UI;
- a reference implementation;
- a manual verification surface where useful; and
- a temporary fallback during migration.

It is no longer the long-term primary UI target.

New Streamlit work should generally be limited to:

- correctness;
- data integrity;
- privacy/security;
- migration blockers;
- serious workflow defects; or
- minimal validation of new reusable core capabilities.

Large new Streamlit-specific UI investments should be avoided.

## Feature Freeze Status

**Not applicable yet / scope currently open.**

The earlier planned Streamlit Feature Freeze was never passed and is now
superseded by the reopened product scope.

The next formal Feature Freeze is planned after the intended desktop product
scope has been implemented and before Desktop Product Hardening.

## Hardening Status

Formal end-of-product hardening has not started.

However, pre-desktop stabilization and full-product manual QA have already
identified issues that must be corrected before major migration work.

The new lifecycle separates:

**Pre-Desktop Stabilization**

from:

**Desktop Product Hardening**

This avoids spending full release-hardening effort on a Streamlit interface
that is scheduled for retirement.

## Verification Status

### Automated Checks

Historical repository checks have included Python compilation, architecture
audits, and packaging-readiness checks.

For the 2026-08-09 lifecycle-alignment change:

- `scripts/audit_architecture.py` scanned 30 Python files and reported no
  serious boundary violations or warnings;
- affected Markdown links and directly referenced repository paths resolved;
- the documentation diff contained no Python source changes; and
- full product regression was intentionally not run because this was a
  documentation-only lifecycle change.

These checks must be rerun as appropriate against each significant engineering
milestone baseline.

For M11.4:

- the complete automated suite passed all 38 tests;
- all 6 targeted M11.4 closure tests passed;
- quiz-randomization and Python compilation checks passed;
- `scripts/audit_architecture.py` scanned 32 Python files and reported no
  serious boundary violations or warnings;
- packaging readiness passed with only the expected local-database exclusion
  warning; and
- `git diff --check` passed, with no schema or migration file changes.

For M12:

- the complete automated suite passed all 38 tests;
- Python compilation and Quiz-randomization checks passed;
- `scripts/audit_architecture.py` scanned 32 Python files and reported no
  serious boundary violations or warnings;
- packaging readiness passed with only the expected local-database exclusion
  warning;
- 32 tracked relative Markdown links were resolved with zero broken links;
- current plain-text references to all 14 moved documents were repaired;
- the final root contains only durable entry points plus intentional source,
  test, support, data-placeholder, sample, and documentation directories;
- privacy/tracked-file and `git diff --check` audits passed; and
- no `app.py`, `src/`, test, schema, migration, or runtime behavior file changed.

For M13 Batch A:

- all 22 focused Template Definition tests passed;
- the complete automated suite passed all 60 tests;
- Python compilation and Quiz-randomization checks passed;
- `scripts/audit_architecture.py` scanned 33 Python files and reported no
  serious boundary violations or warnings;
- packaging readiness passed with only the expected local-database exclusion
  warning;
- privacy/tracked-file and `git diff --check` audits passed; and
- no schema, migration, Streamlit UI, linked-source, analytics, audio, or
  desktop implementation was introduced.

For M13 Batch B:

- all 21 focused Linked Append Source test methods passed, covering the 26
  required migration, CSV/XLSX, classification, transaction, non-authoritative
  source, missing-source, unlink, Card-history, and backup behaviors;
- the complete automated suite passed all 81 tests;
- Python compilation and Quiz-randomization checks passed;
- `scripts/audit_architecture.py` scanned 34 Python files and reported no
  serious boundary violations or warnings;
- packaging readiness passed with only the expected warning that the local
  `data/vocab.db` must remain excluded; and
- no Streamlit UI or desktop UI implementation was added.

For M13 Batch C:

- all 6 focused integration/closure tests passed;
- combined Batch A + Batch B + Batch C focused tests passed all 49 tests;
- the complete automated suite passed all 87 tests;
- migration, transaction, import, Card-history, backup/reopen, restored-path,
  and privacy assertions passed using synthetic databases and files only;
- Python compilation and Quiz-randomization checks passed;
- `scripts/audit_architecture.py` scanned 34 Python files and reported no
  serious boundary violations or warnings;
- packaging readiness passed with only the expected local-database exclusion
  warning; and
- no Streamlit UI, desktop UI, analytics, audio, or M14 implementation was
  introduced.

For M11.1, repository evidence was inspected across Entry editing, Review,
Quiz, Today, Statistics, Collection/Card mutation, schema, backup metadata, and
user-facing exception paths. M11.1 changes documentation only; validation
results are recorded in its Draft PR.

### Manual QA

Full-product manual QA now exists and has produced a baseline acceptance and
triage dataset.

Status:

**Established and closed for M11. All 66 QA IDs were reconciled by M11.1; all
17 IDs assigned to M11.4 have one final disposition in
`docs/history/MILESTONE11_CLOSURE.md`. No ambiguous M11-scope QA item remains.**

### Existing Database Compatibility

Additive schema/app metadata and migration foundations exist.

Existing SQLite databases remain protected assets and must continue to open
through later desktop development.

Future schema changes for analytics, Template speech metadata, or audio caching
must remain additive, versioned, backup-aware, and
compatibility-tested.

Status:

**M11 migration baseline verified through fresh, representative legacy,
intermediate, repeated-startup, rollback, and backup-readability scenarios.**

### Privacy and Secret Safety

The public repository must continue excluding:

- personal databases;
- imported vocabulary files;
- exports;
- backups;
- generated audio;
- logs containing private learning data;
- secrets;
- local caches; and
- private path information.

Privacy checks must be repeated after repository restructuring and before every
release candidate.

### Packaging

The existing Streamlit/source distribution is no longer the final intended
Release Candidate target.

Native desktop packaging remains future work after desktop functionality and
hardening.

Status:

**Desktop packaging not started.**

### Remote Repository Verification

On 2026-08-09, immediately before the lifecycle-alignment branch was created:

- branch: `main`;
- local `HEAD`: `16c21d173e8ebbb486c6f87b03fc047d2cf02e7a`;
- fetched `origin/main`: `16c21d173e8ebbb486c6f87b03fc047d2cf02e7a`;
- default remote branch: `main`; and
- local `main` matched the fetched remote branch.

The lifecycle-alignment PR was merged to `main` as:

`f5ce774bc6645d8e6b0e80dbef71c77158c98de8`

M11.1 started from that synchronized local/remote baseline on branch
`agent/m11-1-semantic-alignment`. Its own commit and Draft PR are recorded by
Git/GitHub rather than embedded recursively as this file's own commit identifier.

M11.1 was merged to `main` as:

`daf505b4fce0760af0c4c1eb97effcc9c0b74849`

M11.2 started from that exact synchronized commit on branch
`agent/m11-2-unified-learning-flow`.

Status:

**M11.1, M11.2, M11.3, and M11.4 are merged. The trustworthy pre-desktop
baseline is established on `main` at
`f0e0d2c06fa4137c07ab2f892df117af2ed3a060`.**

## Known Risks

- Deleting an entire Collection intentionally deletes its associated
  Card/Review/Quiz history after explicit confirmation; this is an accepted
  current product contract, not a retention promise.
- Legacy scheduler state and logs remain in the schema for compatibility even
  though active M11.2 UI and completion reporting no longer use them.
- SQLite connection cleanup emits ResourceWarnings under the isolated M11.2
  test harness; this does not affect test results but remains technical debt.
- Active Quiz recovery combines durable session state with transient UI state.
- Dense table and selection workflows depend on Streamlit behavior and must be
  redesigned deliberately for desktop.
- Today/Review/Quiz focus routing requires explicit desktop controller design.
- Date/local-time behavior requires desktop and packaged-environment
  verification.
- Linked-source local file paths introduce portability and unavailable-file
  scenarios that require controlled handling.
- Learning Analytics can become misleading if built before measurement
  semantics are corrected.
- Local TTS introduces model/runtime size, packaging, performance, and license
  obligations.
- Existing user-data migration to an eventual desktop application-data
  directory must remain explicit and reversible.

## Unknown or Unverified

- Large/dense dataset behavior under the future desktop UI.
- Desktop framework selection.
- Desktop accessibility and interaction model.
- Linked-source behavior with moved, renamed, unavailable, or malformed files.
- Final Analytics thresholds and evidence-sufficiency rules.
- Final TTS provider/model selection.
- Audio-generation performance on representative hardware.
- Native packaging and clean-machine installation.
- Existing-data migration and rollback in packaged desktop form.
- Final public project license and third-party notice set.

## Deferred Features

The following remain outside the current active product scope unless explicitly
reopened:

- bidirectional local-file synchronization;
- automatic deletion/reordering of Collection data based on linked source
  files;
- advanced source conflict resolution;
- audio generation for optional Template fields;
- Audio Quiz / listening-Quiz integration;
- pronunciation assessment;
- mandatory AI-generated analytics;
- dictionary integrations;
- cloud sync;
- accounts and authentication;
- destructive/full database restore; and
- additional learning modes not required by the current product promise.

## Current Development Sequence

The approved high-level sequence is:

```text
M11  Pre-Desktop Stabilization
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

## Milestone 12 Closure Result

The repository root now retains the durable project entry points while
historical, QA, migration, policy, and packaging documents have clear homes
under `docs/`. `docs/README.md` is the supporting-document navigation index.

The existing flat `src/` core-module layout, `src/ui_streamlit/`, `tests/`,
`scripts/`, `tools/`, and `app.py` were intentionally left structurally and
behaviorally unchanged. Consolidating `scripts/` and `tools/`, decomposing
large core modules, and changing runtime package layout are deferred because
they would add churn without M12 user value.

## Milestone 13 Closure Result

Milestone 13 is complete. Template Definition Portability, Linked Append
Sources, migration convergence, existing import compatibility, Card-history
truth, backup/reopen readiness, privacy documentation, and architecture
boundaries passed the Batch C closure gate.

Batch A was merged separately through PR #8. The final M13 Draft PR contains
Batch B plus Batch C and is the remaining review/merge gate for bringing the
complete M13 closure state onto `main`.

Batch C verified closure commit:
`9b3ea9ec50682f61ac55470b0ae5b189506ded81`.

Final M13 Draft PR: #9, **M13: Complete import and template evolution core**.
It was opened from the verified closure head and contains Batch B + Batch C.
A later documentation-only PR metadata commit may be the current Draft PR head.

## Next Objective

**M14 — Learning Analytics and Insight Core**

M14 has not started. Do not begin it before explicit product-owner approval.

## Repository State

- Candidate branch: `agent/m13-import-template-evolution`
- Merged M12 base commit:
  `6e339ec846f22f14ee454d9ad0d68ba3fb83aee6`
- Verified M13 Batch A correctness implementation commit:
  `247652c56131b73f8bc582751c748e614dc7f890`
- Independently reviewed M13 Batch A head:
  `44fdde0fe79e6810b2cb1dc5a4fb3cbeea04dfab`
- M13 Batch A merge commit on `main`:
  `8574b31dde9b213fe83aade9583bf2e360fce0da`
- Verified M13 Batch B implementation commit:
  `633d7484874fbbf0beb7064e9abed9389414d9e4`
- M13 Batch C synchronization merge commit:
  `5efaddc21a58e1610b2f8858dfd152507e1ec3c7`
- Verified M13 Batch C closure commit:
  `9b3ea9ec50682f61ac55470b0ae5b189506ded81`
- Final M13 Draft PR:
  `#9 — M13: Complete import and template evolution core`
- Merged M11 trustworthy-baseline commit:
  `f0e0d2c06fa4137c07ab2f892df117af2ed3a060`
- Verified synchronized M12 base commit:
  `0bce62833632e7e73bdc4daf4430ba028415adfd`
- Verified M12 restructure commit:
  `b4c119a2eb0f88108ea93554355ee62ec5a72634`
- Verified M11.4 implementation commit:
  `f0113e0592bf5198c429d3282c528c39b47f63fa`
- M11.4 PR head:
  `b5c75ca52aa67f9fa5a7af7698358a709314d935`
- M11.4 merge commit on `main`:
  `f0e0d2c06fa4137c07ab2f892df117af2ed3a060`
- Release tag: none recorded
- Current lifecycle documents:
  - `ROADMAP.md`
  - `PROJECT_STATUS.md`
  - `docs/migration/DESKTOP_MIGRATION_PLAN.md`
- Closure evidence: `docs/history/MILESTONE11_CLOSURE.md`
- Current lifecycle state:
  **Milestone 13 Complete — Import and Template Evolution Core Complete**
- Exact next objective:
  **M14 — Learning Analytics and Insight Core (not started)**
