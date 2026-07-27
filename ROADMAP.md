# Vocabulary App Roadmap

This roadmap is the authoritative lifecycle and milestone outline for
Vocabulary App. For the current evidence-based snapshot, see
`PROJECT_STATUS.md`. For the reconstructed history before Git was initialized,
see `PRE_GIT_HISTORY.md`.

## Product Goal and Constraints

Vocabulary App is a local-first, user-owned vocabulary learning workflow
system. The current product form is a Python, Streamlit, and SQLite source
application.

The current release scope includes entry and template management, collections
and cards, review scheduling, quizzes and learning pools, statistics, Today,
CSV/XLSX import and export, backup generation, and restore preview.

Permanent constraints for the current release:

- user-created content and the local SQLite database are protected assets;
- core logic remains independent of Streamlit where practical;
- imports require validation, preview, confirmation, and controlled writes;
- migrations should be additive, idempotent, and backup-aware;
- restore remains preview-only and does not overwrite the active database; and
- no built-in dictionary data, bundled pronunciation/audio, mandatory AI,
  cloud sync, accounts, or native desktop installer is promised.

## Completed Product Development

Milestones 1-10 are completed historical development and productization work:

- Milestones 1-4 established the local application, entry management,
  collections/cards, review scheduling, and the Streamlit/core boundary.
- Milestone 5 added quiz sessions, objective and self-graded practice, session
  safety, Mistake Book, Starred, and Proficient Pool workflows.
- Milestone 6 added entry templates, template-aware entries, built-in template
  presets, and template-aware quizzes.
- Milestone 7 added read-only statistics, Review Calendar, trends, and entry
  health.
- Milestone 8 added CSV/XLSX import/export, SQLite/XLSX backup, and
  restore-preview safety.
- Milestone 9 added Today and the daily learning workflow.
- Milestone 10 added public-repository documentation, content/data policies,
  configuration, architecture and packaging assessments, schema/app metadata,
  migration foundations, and productization QA.

Milestone 10 completion does not mean that full-product manual acceptance,
system-wide hardening, or release-candidate delivery is complete.

## Current Phase

**Feature Complete Review / Feature Freeze Preparation**

The planned capabilities of the current Streamlit-based release are
substantially implemented. The current phase must:

- reconcile the documented scope with actual repository behavior;
- establish baseline full-product manual acceptance;
- identify and classify defects across module boundaries;
- confirm the release promise and deferred scope; and
- obtain an explicit Feature Freeze decision.

The project is not Release Ready or Current Version Complete.

## Feature Complete Review

The current Streamlit release is considered functionally feature-complete for
scope-review purposes, subject to:

- repository-wide scope reconciliation;
- baseline manual acceptance;
- system audit and defect classification;
- regression verification; and
- explicit Feature Freeze approval.

Desktop migration is not a missing feature of this release.

## Feature Freeze Gate

**Status: Not passed**

No repository evidence records an explicit Feature Freeze approval.

When this gate is approved:

- the current release scope is fixed;
- new product features move to Deferred Features / Next Version;
- release-blocking correctness, data-integrity, privacy, security,
  core-workflow, serious UX, compatibility, and migration defects remain in
  scope;
- scope may reopen only through an explicit recorded decision; and
- desktop migration or optional language-content integrations cannot enter the
  frozen release silently.

## Milestone 11: Product Hardening

Milestone 11 is project-wide hardening, not feature expansion.

### 11.1 System Audit and Defect Inventory

- Map real end-to-end user journeys.
- Reconcile implemented behavior with documentation.
- Inspect fresh, empty, populated, upgraded, malformed-input, interrupted,
  restarted, and repeated-action scenarios.
- Classify findings as release blockers, high-risk correctness/data/privacy
  issues, serious workflow/UX issues, lower-priority polish, architecture debt,
  or deferred features.
- Establish a full-product manual QA artifact.

A dedicated hardening backlog should be created only if the number or
complexity of findings justifies one.

### 11.2 Correctness and Data Integrity

Priorities include:

- existing SQLite database compatibility;
- additive and idempotent migrations;
- schema/app metadata and migration registry behavior;
- entry/template/collection relationship integrity;
- collection positions and card calculations;
- quiz duplicate-submission protection and session recovery;
- review states, dates, logs, and local-time behavior;
- import validation, preview, confirmation, duplicates, transactions, and
  partial failure;
- backup generation and restore-preview boundaries;
- delete/remove semantics across normal and system collections; and
- backup-before-upgrade expectations.

### 11.3 Workflow and UX Consistency

Audit the complete learning loop:

```text
Create or import
-> Organize
-> Today
-> Review
-> Quiz
-> Mistake Book / Proficient Pool
-> Statistics
-> Export / Backup
```

Check navigation, focus handoffs, continue/cancel/restart/recovery behavior,
naming, confirmations, empty states, warnings, irreversible-action messaging,
system-collection consistency, and parity among manual Add, Quick Add, and
imported entries.

### 11.4 Robustness, Privacy, Performance, and Repository Safety

- Verify clean and fresh startup.
- Exercise large or dense local datasets.
- Check local paths and writable-directory assumptions.
- Exclude databases, imports, exports, backups, secrets, caches, logs, and
  build artifacts from public output.
- Keep samples and issue reports synthetic and privacy-safe.
- Review dependency and packaging risks.
- Re-run the architecture boundary audit.
- Confirm core modules import no Streamlit.
- Confirm logs, screenshots, archives, and test artifacts contain no private
  learning data.

### 11.5 Full Regression and Manual Acceptance

Require:

- automated checks passing;
- affected-workflow regression after critical fixes;
- full manual acceptance of core user journeys;
- fresh and representative upgraded database coverage;
- privacy and secret-safety checks;
- documentation consistency review;
- local/remote repository verification; and
- documented deferred issues and known limitations.

### Milestone 11 Exit Criteria

- No known release-blocking defect remains.
- No known high-risk data-integrity, privacy, or security defect remains.
- All defined core workflows pass manual acceptance.
- Fresh and representative upgraded databases pass required checks.
- Import, export, and backup safety flows pass.
- Every fixed critical defect has regression coverage or a documented
  verification procedure.
- Architecture and privacy checks pass.
- New feature requests remain outside the frozen scope.
- Known limitations and deferred issues are documented.
- Roadmap, status, README, QA, and release documentation agree.
- The verified local commit matches the intended remote branch.

## Milestone 12: Release Candidate and Current-Version Delivery

Milestone 12 prepares the current Streamlit source application for a credible
release:

- decide the release-candidate version;
- prove reproducible clean-environment installation and launch;
- document supported Python and dependency assumptions;
- perform final source/archive privacy and user-data exclusion checks;
- prepare release notes and known limitations;
- reconcile final README and lifecycle documentation;
- run clean-database and existing-database smoke tests;
- run final regression;
- prepare a tag/release only after approval;
- document rollback and local-data recovery guidance; and
- verify the final local branch, remote branch, and commit.

This milestone does not automatically produce an executable or installer. If
packaging is not proven reliable, the release remains a documented source
distribution. Any RC-blocking defect returns the project to Milestone 11 and
requires relevant regression to be repeated.

## Current Version Complete

The current version may be declared complete only after:

- Milestone 11 exit criteria pass;
- Milestone 12 exit criteria pass;
- Feature Freeze and RC acceptance are explicitly recorded;
- release documentation and known limitations are accurate; and
- the intended release commit is verified remotely.

Completion transitions the project to maintenance or the next product version;
it does not mean the project is permanently finished.

## Maintenance / Next Version

After the current version is complete:

- maintain correctness, compatibility, privacy, and data safety;
- triage defects separately from new capabilities;
- use additive migrations and documented upgrade verification;
- update `PROJECT_STATUS.md` after meaningful lifecycle changes; and
- update this roadmap only when scope or lifecycle decisions change.

## Deferred Features / Next Version

- minimal PySide6/PyQt desktop shell prototype;
- phased Streamlit-to-desktop workflow migration;
- native packaging, installer, uninstaller, update, and rollback;
- OS app-data directory migration;
- full desktop parity;
- optional dictionary integrations;
- optional pronunciation/TTS integrations;
- optional AI-assisted features;
- cloud sync, accounts, or authentication;
- destructive or full database restore; and
- new learning modes not required to make current promises reliable.

The desktop strategy remains:

```text
Stabilize and verify current workflows
-> Build a deliberately small desktop shell prototype
-> Prove core reuse and database compatibility
-> Port high-frequency workflows incrementally
-> Port management and data tools
-> Package only after parity and migration safety are proven
```
