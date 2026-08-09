# Vocabulary App Project Status

Last reviewed: 2026-08-09

This file is the authoritative evidence-based snapshot of the current project
state.

Lifecycle intent and future milestones are defined in `ROADMAP.md`.

Desktop-specific migration principles and workflow mapping are defined in
`DESKTOP_MIGRATION_PLAN.md`.

## Current Phase

**Scope Reopened / Pre-Desktop Stabilization**

## Current Milestone

**Milestone 11: Pre-Desktop Stabilization**

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

### Review Completion vs Schedule Change

Current behavior requires semantic correction.

The intended product model is:

**Review Completed**

- represents actual review exposure;
- increments review count;
- updates the last-reviewed timestamp; and
- appears in review activity/history.

**Schedule Changed**

- changes only the future review date;
- must not increment review count;
- must not update the last-reviewed timestamp; and
- must not be reported as completed review activity.

The scheduling model remains user-controlled.

The product should not restore hard-coded `+1 / +7 / +30` scheduling as the
primary interaction and should not restore Again/Hard/Good/Easy SRS as the
main Review model.

### Card Identity and Historical Truthfulness

An unresolved architectural issue exists between:

- cards dynamically derived from collection order and `card_size`; and
- historical review/card records associated with collection and card number.

Collection reordering or card-size changes can cause the same apparent Card
number to refer to different entries while retaining old history.

A minimal-risk architectural decision is required before broader desktop and
analytics work depends on Card history.

The decision must consider:

- historical truthfulness;
- reorder behavior;
- card-size changes;
- backward compatibility;
- migration cost; and
- future desktop behavior.

No stable-Card-ID migration has yet been approved.

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

Entry Health requires renewed manual acceptance after the Statistics semantics
are reconciled.

## Other QA Findings Requiring Later Triage

Known QA findings also include:

- partial Chinese/French localization;
- hard-coded Entry Type filter behavior that does not naturally cover custom
  types;
- whether the Status filter should remain as a product decision;
- lack of one unified configurable display-order model across canonical and
  custom fields;
- Template Import Preview not fully exposing dynamic `field:*` information;
- Ordered Quiz Queue editing being implemented but poorly discoverable;
- stale historical acceptance expectations around Again/Hard/Good/Easy;
- obsolete or compatibility-only review-rating code that requires an explicit
  deprecation/retention decision;
- legacy entry-level review-count semantics still appearing in some UI
  contexts; and
- exceptional error rendering that may expose local file paths or database
  details.

These findings must be classified by Milestone 11 rather than treated as an
undifferentiated list of release blockers.

Streamlit-only polish should not receive the same priority as data correctness,
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

- Review = exposure/history;
- Quiz = demonstrated performance;
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

### Manual QA

Full-product manual QA now exists and has produced a baseline acceptance and
triage dataset.

Status:

**Established; requires Milestone 11 reconciliation and targeted re-testing.**

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

The lifecycle-alignment commit and pull request are recorded by Git history
after this verified baseline rather than embedded recursively as this file's
own commit identifier.

Status:

**Pre-alignment remote baseline verified; lifecycle revision applied in the
documentation branch.**

## Known Risks

- Card history currently depends on identity semantics that may become
  misleading after collection reorder or card-size changes.
- Review schedule changes may currently contaminate completed-review activity
  semantics.
- Streamlit entry-edit widget state can risk unintended data overwrite.
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

- Final Card identity/history strategy.
- Full classification and resolution plan for all current manual QA findings.
- Current repository-wide regression after the latest product-scope decision.
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

## Next Engineering Objective

Begin **Milestone 11: Pre-Desktop Stabilization**.

The first work should:

1. reconcile the existing full-product manual QA findings;
2. separate data/correctness/migration blockers from disposable
   Streamlit-specific polish;
3. resolve the confirmed entry-editing integrity issue;
4. enforce Review Completed vs Schedule Changed semantics;
5. prepare the Card identity/history options for product-owner decision;
6. re-accept Entry Health against current product semantics; and
7. establish and verify the pre-desktop baseline before repository
   restructuring begins.

Do not begin full development of the three new major capabilities before this
baseline is trustworthy.

## Repository State

- Intended branch: `main`
- Verified pre-alignment remote commit:
  `16c21d173e8ebbb486c6f87b03fc047d2cf02e7a`
- Release tag: none recorded
- Current lifecycle documents:
  - `ROADMAP.md`
  - `PROJECT_STATUS.md`
  - `DESKTOP_MIGRATION_PLAN.md`
- Current lifecycle state:
  **Scope Reopened / Pre-Desktop Stabilization**
