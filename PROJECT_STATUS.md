# Vocabulary App Project Status

Last reviewed: 2026-07-27

This file is the authoritative evidence-based snapshot of the current project
state. Lifecycle intent and future milestones are defined in `ROADMAP.md`.

## Current Phase

**Feature Complete Review / Feature Freeze Preparation**

## Current Milestone

Pre-Milestone 11 scope reconciliation and Feature Freeze preparation.

## Current Release Scope

The intended current release is the existing Streamlit source application with:

- entry and template management;
- collections and dynamic cards;
- card-level review scheduling;
- quiz sessions and learning pools;
- statistics and Review Calendar;
- Today and the daily learning workflow;
- CSV/XLSX import and export;
- SQLite/XLSX backup and restore preview; and
- schema/app metadata plus additive migration foundations.

It does not promise a native desktop app, installer, destructive restore,
dictionary data, bundled pronunciation/audio, mandatory AI, cloud sync, or
accounts.

## Feature Complete Status

**Substantially implemented for the defined Streamlit scope; pending formal
review.**

Repository evidence supports completion of Milestones 1-10 and the listed
capabilities. It does not prove that every end-to-end workflow has passed a
current full-product regression.

## Feature Freeze Status

**Not passed.**

No explicit Feature Freeze approval is recorded. New feature requests must be
classified as deferred until the current release scope is reviewed and frozen.

## Completed Work

- Milestones 1-9 feature implementation.
- Milestone 10 productization and update-compatibility foundations.
- Separation of reusable core logic from Streamlit UI.
- Public documentation for content, data, architecture, migration, packaging,
  and software updates.
- Initial public Git baseline and reconstructed pre-Git history.

## Open Release Blockers

No specific release blocker has yet been confirmed by a current system-wide
audit. This is not evidence that none exist.

The blocking condition for release readiness is the absence of:

- a completed Feature Complete Review;
- explicit Feature Freeze approval;
- Milestone 11 system audit and defect classification;
- full-product manual acceptance and regression; and
- Milestone 12 release-candidate verification.

## Hardening Progress

- Milestone 11.1 System Audit and Defect Inventory: not started.
- Formal full-product manual QA artifact: not yet established.
- Hardening defect inventory: not yet established.
- Release-blocker classification: not yet performed.

## Verification Status

### Automated Checks

On 2026-07-27, Python compilation passed, the architecture audit reported no
serious boundary violations or warnings, and the packaging-readiness check
completed successfully. The packaging check reported the expected warning that
the local personal database exists and must remain excluded from Git and release
archives.

These checks do not replace workflow testing and must be rerun for the intended
release commit.

### Manual QA

Milestone 8, 9, and 10 repository checklists contain unchecked manual items.
Conversation-level or milestone-specific acceptance records do not establish a
current full-product regression. Status: **incomplete / unverified**.

### Data Migration and Existing Database Compatibility

`app_metadata`, schema/app version values, and the migration registry foundation
exist. Initialization uses additive compatibility steps. Fresh-database,
representative upgraded-database, repeated-migration, and backup-before-upgrade
coverage have not yet been demonstrated as a complete release matrix.

Status: **foundation implemented; release-level verification incomplete**.

### Privacy and Secret Scan

The initial public baseline was previously checked for excluded local data.
Every future commit and release still requires a fresh scan of tracked files,
diffs, metadata, and generated artifacts.

Status: **must pass again for the intended release commit**.

### Packaging and Clean-Environment Setup

The documented source setup is the current credible distribution path. A
reproducible clean-environment release installation has not been proven in the
current lifecycle. No native installer exists.

Status: **unverified for release candidate**.

### Remote Repository Verification

At the start of this lifecycle-alignment work:

- branch: `main`;
- last verified commit: `1b8326e3554fdb20c8e2a04b4972409a223ee54e`;
- local `main` matched `origin/main`; and
- the working tree contained authorized, uncommitted documentation/privacy
  changes.

Remote state must be updated after any approved documentation commit.

## Known Risks

- Project-local development data path is unsuitable for a packaged desktop app.
- Active quiz recovery combines durable session data with transient UI state.
- Dense tables and selection workflows depend on Streamlit behavior.
- Today/Review/Quiz focus routing requires explicit controller design in a
  future UI.
- Date and local-time behavior needs packaged-environment verification.
- Import, export, backup, and restore-preview parity is unproven outside
  Streamlit.
- Clean-environment dependency and packaging behavior is unverified.

## Unknown or Unverified

- Complete defect inventory.
- Fresh and representative upgraded-database regression.
- Full end-to-end workflow acceptance.
- Large/dense dataset behavior.
- Repeated-click, restart, interrupted-action, and malformed-input coverage
  across all workflows.
- Release-archive privacy and user-data exclusion.
- Cross-platform source setup.

## Deferred Features

Desktop migration, native packaging, installers, OS app-data migration,
dictionary/pronunciation/AI integrations, cloud/accounts, destructive restore,
and new learning modes are deferred to a later product version.

## Next Engineering Objective

Approve the current release scope and begin Milestone 11.1: System Audit and
Defect Inventory.

## Repository State

- Intended branch: `main`
- Pre-alignment verified commit:
  `1b8326e3554fdb20c8e2a04b4972409a223ee54e`
- Pre-alignment sync state: local `main` matched `origin/main`
- Release tag: none recorded
- Current lifecycle documents: `ROADMAP.md` and `PROJECT_STATUS.md`
