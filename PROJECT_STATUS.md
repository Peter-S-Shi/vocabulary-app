# Vocabulary App Project Status

Last reviewed: 2026-08-11

This file is the authoritative evidence-based snapshot of the current project
state.

Lifecycle intent and future milestones are defined in `ROADMAP.md`.

Desktop-specific migration principles and workflow mapping are defined in
`DESKTOP_MIGRATION_PLAN.md`.

## Current Phase

**Scope Reopened / Pre-Desktop Stabilization**

## Current Milestone

**Milestone 11: Pre-Desktop Stabilization**

M11.1 Semantic Alignment and QA Scope Lock has been merged to `main`.
M11.2 Unified Learning Flow and Core Integrity is merged to `main` at
`eb8cda4e50b987b5db37b36425d3e47c94c28eaa`.
M11.3 Stable Card Identity and Entry-Level History is implemented on candidate
branch `agent/m11-3-card-identity-history` and is pending independent Draft PR
review. M11.4 has not started.

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

## Confirmed Pre-Desktop Priorities

### Entry Editing Integrity

A confirmed high-priority issue exists in the current Streamlit entry-editing
workflow:

fixed widget-state behavior can carry values between different entries and may
silently overwrite fields such as:

- Language;
- Explanation Language;
- Entry Type; and
- Status.

This must be resolved before the Streamlit application is treated as a
trustworthy migration baseline.

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

The additive `10.6.0-baseline -> 11.3.0-card-history` migration:

- establishes one active stable Card per current slot and one baseline revision;
- preserves active Card IDs across membership revisions;
- retires disappearing Cards and never reuses their IDs when a slot reappears;
- moves active Card names to stable identity while retaining the old metadata table as compatibility-only;
- binds new Card-scoped Quiz sessions to the exact `card_id` and `card_revision_id` used at start;
- leaves legacy pre-M11.3 Quiz composition null/unknown where it cannot be proved;
- records compact, field-level old/new evidence for successful non-no-op Entry edits; and
- requires an evidence-based Streamlit confirmation before user-driven cross-Card reorganization.

Collection mutation and Card-history reconciliation share one transaction.
Reads and ordinary Quiz activity create no Card revisions. The reusable core
remains Streamlit-independent and is suitable for a later native confirmation
dialog.

Known deletion boundary: ordinary membership changes and Entry hard deletion
do not remove the stored integer Entry IDs from Card revision snapshots.
Deleting an entire Collection retains the existing product behavior of
deleting that Collection's associated Card/Quiz history. A different
Collection-deletion retention policy remains a product decision for M11.4.

M11.3 branch: `agent/m11-3-card-identity-history`.
M11.3 base: `eb8cda4e50b987b5db37b36425d3e47c94c28eaa`.
The exact candidate head commit is recorded in the Draft PR and closeout
report after verification.

Candidate verification includes 30 passing M11.2/M11.3 unit and Streamlit
AppTests on isolated synthetic databases, migration failure rollback,
idempotent restart, storage-noise checks, architecture audit, and packaging
readiness. The packaging checker retains its expected warning that the local
personal database exists and must remain excluded from Git/releases.

Next engineering objective:
**M11.4 — Semantic Re-acceptance & Pre-Desktop Baseline Closure**.

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

Static inspection of `src/statistics.py:get_entry_performance_summary()` and
`get_strong_entries()` shows that current Entry Health derives attempts and
accuracy from `quiz_item_logs`, plus special-pool state; it does not use Review
count to classify Strong. M11.4 must re-accept this behavior after M11.2 and
M11.3 changes.

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

`DESKTOP_MIGRATION_PLAN.md` has been revised as part of the current lifecycle
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

For M11.1, repository evidence was inspected across Entry editing, Review,
Quiz, Today, Statistics, Collection/Card mutation, schema, backup metadata, and
user-facing exception paths. M11.1 changes documentation only; validation
results are recorded in its Draft PR.

### Manual QA

Full-product manual QA now exists and has produced a baseline acceptance and
triage dataset.

Status:

**Established; all 66 QA IDs reconciled by M11.1. Targeted implementation and
re-acceptance remain assigned to M11.2-M11.4. No additional product-owner UI
test is required for M11.1.**

### Existing Database Compatibility

Additive schema/app metadata and migration foundations exist.

Existing SQLite databases remain protected assets and must continue to open
through later desktop development.

Future schema changes for linked sources, analytics, Template speech metadata,
or audio caching must remain additive, versioned, backup-aware, and
compatibility-tested.

Status:

**Foundation exists; new-scope migration verification pending.**

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

**M11.1 merged and synchronized; M11.2 candidate pending Draft PR review.**

## Known Risks

- Card history, Quiz sessions, Review state/logs, and Card metadata currently
  depend on `collection_id + card_number`, which becomes misleading after
  reorder or `card_size` changes.
- Card membership has no revision history, so old Card composition cannot be
  reliably reconstructed.
- Entry deletion cascades to `quiz_item_logs`, which can remove Entry-level
  evidence while retaining parent Quiz-session totals; M11.3 must resolve the
  intended historical behavior without false backfill.
- Legacy scheduler state and logs remain in the schema for compatibility even
  though active M11.2 UI and completion reporting no longer use them.
- Card learning completion still depends on transitional
  `collection_id + card_number` until M11.3 introduces stable Card identity.
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

- Exact additive schema and migration design for approved stable Card identity
  and membership revisions.
- Truthful legacy-history treatment where old Card composition is unknowable.
- Product-owner acceptance of the M11.2 Streamlit behavior after Draft PR
  review.
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

## M11.2 Review Gate

Review and re-accept the **M11.2: Unified Learning Flow and Core Integrity**
Draft PR. The candidate:

1. isolates Entry edit widget state by permanent Entry ID;
2. makes completed Card-scoped Quiz the sole active Card completion evidence;
3. preserves direct Card Quiz completion and idempotent recovery;
4. provides Quick Quiz and Choose Quiz Type routes from Review;
5. removes independent scheduling/SRS controls from active Streamlit truth;
6. migrates Today, Statistics, and Learning History; and
7. replaces confirmed raw unexpected-error rendering with safe messages and
   local diagnostic logging.

Do not begin M11.3 until M11.2 is independently reviewed and merged.

## Next Engineering Objective

After that review gate and merge, the exact next engineering objective is:

**M11.3 — Stable Card Identity and Entry-Level History**

Do not begin full development of the three new major capabilities before this
baseline is trustworthy.

## Repository State

- Candidate branch: `agent/m11-2-unified-learning-flow`
- Verified synchronized M11.2 base commit:
  `daf505b4fce0760af0c4c1eb97effcc9c0b74849`
- Release tag: none recorded
- Current lifecycle documents:
  - `ROADMAP.md`
  - `PROJECT_STATUS.md`
  - `DESKTOP_MIGRATION_PLAN.md`
- Current lifecycle state:
  **Scope Reopened / Pre-Desktop Stabilization**
