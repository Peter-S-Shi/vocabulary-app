# Vocabulary App Roadmap

This roadmap is the authoritative lifecycle and milestone outline for
Vocabulary App. For the current evidence-based snapshot, see
`PROJECT_STATUS.md`. For desktop-specific migration principles and workflow
mapping, see `DESKTOP_MIGRATION_PLAN.md`. For the reconstructed history before
Git was initialized, see `PRE_GIT_HISTORY.md`.

## Product Goal and Constraints

Vocabulary App is a local-first, user-owned vocabulary learning workflow
system.

The product is transitioning from its current Python + Streamlit + SQLite
application toward a native desktop application while preserving the existing
learning engine and user data.

The active product scope includes:

- entry and template management;
- collections and cards;
- Card browse/study preparation and Card-scoped Quiz completion;
- quiz sessions and learning pools;
- learning analytics and entry health;
- Today and the daily learning workflow;
- CSV/XLSX import and export;
- template-definition portability;
- linked local-file append sources for collections;
- backup generation and restore preview;
- card-oriented local audio export; and
- migration of the user interface from Streamlit to a native desktop
  application.

Permanent product constraints:

- user-created content and the local SQLite database are protected assets;
- existing user databases must remain compatible through additive,
  versioned, and backup-aware migrations;
- reusable business logic should remain independent of Streamlit and future
  desktop UI frameworks;
- imports require validation, preview, confirmation, and controlled writes;
- linked local files are append sources, not authoritative bidirectional
  mirrors;
- completed Card-scoped Quiz is the authoritative Card learning/review event,
  while Quiz item logs remain the Entry-level performance evidence;
- analytics must remain explainable and evidence-based rather than relying on
  opaque scores;
- restore remains preview-first and does not silently overwrite the active
  database;
- audio generation should use locally runnable technology with licenses
  suitable for the intended distribution model;
- no mandatory AI, cloud sync, accounts, authentication, or bundled
  proprietary learning content is required for the product; and
- major user-interface work should target the desktop application rather than
  extending the legacy Streamlit interface.

## Completed Product Development

Milestones 1-10 are completed historical development and productization work:

- Milestones 1-4 established the local application, entry management,
  collections/cards, review scheduling, and the Streamlit/core boundary.
- Milestone 5 added quiz sessions, objective and self-graded practice, session
  safety, Mistake Book, Starred, and Proficient Pool workflows.
- Milestone 6 added entry templates, template-aware entries, built-in template
  presets, and template-aware quizzes.
- Milestone 7 added read-only statistics, Review Calendar, trends, and Entry
  Health.
- Milestone 8 added CSV/XLSX import/export, SQLite/XLSX backup, and
  restore-preview safety.
- Milestone 9 added Today and the daily learning workflow.
- Milestone 10 added public-repository documentation, content/data policies,
  configuration, architecture and packaging assessments, schema/app metadata,
  migration foundations, and productization QA.

Completion of Milestones 1-10 established a substantial Streamlit-based
product baseline. It did not constitute final product completion.

## Lifecycle Revision

The previous lifecycle assumed that the Streamlit application would first pass
Feature Freeze, Product Hardening, and Release Candidate delivery before a
desktop migration began.

That assumption is superseded.

Subsequent full-product manual QA and real-world use identified:

- correctness and data-semantic issues that must be stabilized before further
  product growth;
- three substantial product capabilities that now belong in the active product
  direction;
- repository-structure debt that should be corrected before another large
  development cycle; and
- a product decision to retire Streamlit as the long-term user-interface
  target and complete the current product generation as a native desktop
  application.

The project therefore reopens scope before Feature Freeze.

The Streamlit application remains a valuable compatibility and reference
baseline during migration, but it is no longer the intended Release Candidate
target.

## Current Phase

**Scope Reopened / Pre-Desktop Stabilization**

The immediate objective is to establish a trustworthy data and business-logic
baseline, reorganize the repository, implement reusable foundations for the
new product capabilities, and then migrate the product interface to desktop.

Feature Freeze will occur only after the intended desktop feature scope has
been implemented and verified.

---

## Milestone 11: Pre-Desktop Stabilization

Milestone 11 resolves defects and semantic inconsistencies that would otherwise
be carried into the desktop application.

This milestone is not a general Streamlit-polish phase.

### 11.1 Semantic Alignment and QA Scope Lock

Lock the approved product semantics and reconcile every established
full-product QA item against current repository evidence.

The authoritative learning model is:

```text
Browse / study a Card
-> complete a Card-scoped Quiz
-> one completed Card learning/review event
```

Direct Card Quiz completion is valid without entering Review first. A
non-Card-scoped Quiz remains valid Entry-level performance evidence but must
not fabricate completion for a specific Card.

M11.1 is documentation and evidence work only. It classifies findings for
M11.2, M11.3, M11.4, or later milestones and creates an independently
verifiable manifest. It does not change Python behavior or the database.

### 11.2 Unified Learning Flow and Core Integrity

- Resolve all Entry edit-state leakage, including metadata, Collections,
  dynamic Template fields, and manual canonical fallback fields.
- Make completed Card-scoped Quiz the single authoritative Card learning
  completion event; do not maintain a second independent Review completion.
- Preserve direct Card Quiz completion as valid Card learning activity.
- Provide both Review routes: Quick Quiz and Choose Quiz Type, preserving the
  selected Collection/Card context.
- Retire independent manual next-review scheduling, legacy due/interval/ease
  state, and Again/Hard/Good/Easy from active product behavior without
  falsifying legacy data.
- Migrate Today, Statistics, Review History, and related queries away from the
  superseded completion model.
- Replace confirmed raw exception leakage with safe user-facing errors while
  preserving useful developer diagnostics.

M11.2 must use the smallest safe migration path and must not invent a new SRS
algorithm.

### 11.3 Stable Card Identity and Entry-Level History

Introduce an additive, durable `card_id`. `card_number` may remain a display
and ordering concept, but it must no longer be the only identity used by
historical learning records.

Card content remains mutable by user choice. Record compact Card membership
revisions so new Card-scoped Quiz history can identify the Card composition
used at that time through permanent `entry_id` values.

The migration must address:

- collection reorder and position normalization;
- add/remove Entry operations and cross-Card movement;
- `card_size` changes;
- Card names and metadata;
- existing Review and Quiz records;
- Entry deletion/history behavior;
- unknown legacy composition without false backfill; and
- fresh, existing, and repeatedly migrated databases.

Cross-Card changes must warn and confirm that historical composition remains
historical while future learning uses the new composition.

### 11.4 Semantic Re-acceptance and Baseline Closure

Re-accept the resulting learning engine after M11.2 and M11.3.

- Entry Health remains based primarily on Quiz item evidence and special-pool
  state. Browsing alone must not make an Entry Strong; zero attempts may remain
  Never Quizzed.
- Today, Statistics, Review History, Quiz summaries, and direct/Review-routed
  Card quizzes must agree on the new completion semantics.
- A whole-pool/random Quiz must not create an unrelated Card completion.
- Restart/recovery must not duplicate learning completion.
- Card membership history, legacy uncertainty, migration idempotence, privacy,
  architecture boundaries, and representative existing databases must pass
  regression verification.

M11.4 closes the pre-desktop baseline; it is not the later full desktop Product
Hardening milestone.

### Milestone 11 Exit Criteria

- No known unresolved defect can silently corrupt persisted Entry data.
- Completed Card-scoped Quiz is the verified authoritative Card learning event;
  browsing alone and date changes do not create completion.
- Independent manual scheduling and legacy SRS ratings are not active product
  truth.
- Stable `card_id` and historically traceable Card membership are implemented
  through additive, idempotent migration without false legacy backfill.
- Entry Health remains explainable and Quiz-evidence based.
- No known high-risk compatibility issue blocks further schema development.
- Remaining Streamlit-specific UX issues are explicitly classified rather than
  silently treated as desktop blockers.
- `PROJECT_STATUS.md` reflects the verified baseline.

---

## Milestone 12: Repository Restructure

Milestone 12 reorganizes the repository before the next major development
cycle.

The purpose is structural clarity, maintainability, and consistency with the
owner's other mature repositories.

This milestone must not become an opportunistic business-logic rewrite.

### 12.1 Root Cleanup

Keep only durable top-level project entry points and essential project files at
the repository root.

Move historical, lifecycle-specific, QA-specific, migration-specific, or
supporting documentation into clearly named directories where appropriate.

Expected long-lived top-level files may include:

- `README.md`
- `ROADMAP.md`
- `PROJECT_STATUS.md`
- `ARCHITECTURE.md`
- `AGENTS.md`
- `LICENSE`
- dependency / packaging configuration
- application entry points where still appropriate

### 12.2 Documentation Organization

Establish clear homes for material such as:

- architecture and design notes;
- migration documentation;
- lifecycle and historical records;
- manual QA artifacts;
- packaging assessments;
- sample data;
- scripts and project tools.

Use `git mv` where practical so repository history remains traceable.

### 12.3 Safety Boundaries

Repository restructuring must:

- avoid unrelated business-logic refactoring;
- update broken documentation links and file references;
- preserve application behavior;
- preserve local-data exclusions;
- keep `.prompt-drafts/` local through `.git/info/exclude`, not repository
  `.gitignore`;
- preserve privacy-safe sample policies; and
- avoid committing local databases, exports, backups, generated audio, caches,
  secrets, or user learning data.

### Milestone 12 Exit Criteria

- Repository root and major directories follow a deliberate documented
  structure.
- All moved-document references are repaired.
- Automated tests and architecture checks pass.
- Privacy and tracked-file checks pass.
- No functional product behavior changes are introduced except unavoidable
  path/reference corrections.
- `PROJECT_STATUS.md` records the completed restructure and verified commit.

---

## Milestone 13: Import and Template Evolution Core

Milestone 13 extends the reusable import/template engine without investing in a
new Streamlit-heavy interface.

### 13.1 Template Definition Export

Provide a portable template-definition format describing a single template and
its fields.

The exported definition should contain the information required to recreate the
template, including appropriate values such as:

- template name;
- description;
- language;
- template type;
- field key;
- field label;
- field type;
- required status;
- display order; and
- speech-language role where supported.

The exported format should be suitable for later re-import.

### 13.2 Template Definition Import

Support importing one template definition from one CSV file.

The workflow must provide:

- file parsing;
- preview;
- field-level validation;
- duplicate/name-conflict handling;
- controlled confirmation; and
- atomic creation of the template and all fields.

A partially created template must not remain after a failed import.

### 13.3 Template Portability Round Trip

A supported exported template definition should be importable into another
compatible Vocabulary App database without manual field-by-field recreation.

### 13.4 Linked Collection Append Sources

Allow a collection to be linked to a local CSV or XLSX file as an append-only
source.

A refresh analyzes the current file using the existing import and validation
rules and classifies relevant rows as:

- new valid;
- invalid; or
- duplicate / already represented.

Only confirmed new valid entries are appended.

Version 1 explicitly does not synchronize:

- source-file row deletion;
- source-file reordering;
- edits to existing source rows;
- application changes back into the source file; or
- general bidirectional conflict resolution.

The linked file is an append source, not an authoritative mirror of the
collection.

### 13.5 Reusable Service Boundary

Linked-source parsing, refresh analysis, preview generation, and controlled
writes must remain reusable outside Streamlit.

A minimal Streamlit path may be used for engineering verification, but
desktop-native file selection and refresh interaction are deferred to the
desktop milestones.

### Milestone 13 Exit Criteria

- Template definitions support validated export/import round trip.
- One-file/one-template import semantics are documented and tested.
- Linked collections can persist source-link metadata.
- Refresh correctly distinguishes new valid, invalid, and duplicate rows.
- Refresh does not silently delete, reorder, or overwrite existing entries.
- Core functionality is UI-independent.
- Existing import/export behavior remains compatible.

---

## Milestone 14: Learning Analytics and Insight Core

Milestone 14 upgrades Statistics from metric display toward explainable,
actionable learning analytics.

The goal is not to maximize the number of charts or metrics.

The goal is to transform trustworthy learning records into understandable
evidence and useful next actions.

### 14.1 Measurement Semantics

Define and document the grain and meaning of important data:

- Entry;
- Card;
- Quiz Item;
- Quiz Session;
- Collection;
- Template;
- Review Event;
- date / time range.

Do not combine measurements with incompatible meanings.

In particular:

- Review represents exposure and scheduling history.
- Quiz represents demonstrated knowledge performance.

### 14.2 Analytical Layers

Maintain a conceptual separation between:

**Statistics**

- factual measurements and aggregations.

**Analytics**

- comparisons;
- baselines;
- trends;
- coverage;
- relative weakness/strength;
- recovery;
- recency; and
- evidence sufficiency.

**Insights**

- concise human-readable findings;
- priority signals; and
- actionable recommendations.

The implementation may use separate modules or another clean equivalent
architecture, but analytical interpretation should not be embedded only in the
desktop presentation layer.

### 14.3 Evidence-Aware Interpretation

Analytical conclusions should account for:

- sample size;
- recent versus historical evidence;
- personal baseline;
- relative performance;
- quiz coverage;
- repeated errors;
- recovery after earlier errors;
- review exposure without quiz evidence; and
- stale or insufficient evidence.

The application should explicitly state when data is insufficient for a
reliable conclusion.

### 14.4 User-Facing Insight Categories

Potential interpretable categories include:

- Strengths;
- Needs Attention;
- Coverage Gaps;
- Review Load;
- Recovery;
- Neglected Content;
- Never Quizzed; and
- Insufficient Evidence.

Avoid false precision and opaque global learning scores.

### 14.5 Deterministic Insight Engine

Initial insight generation should be based on deterministic, testable rules
over verified metrics.

Optional future AI may improve wording or summarization, but it must not be
required to invent or validate the analytical conclusion.

### Milestone 14 Exit Criteria

- Metric semantics are documented and testable.
- Analytics distinguish Review exposure from Quiz performance.
- Evidence sufficiency prevents overconfident conclusions from sparse data.
- Core analytics can return structured findings independent of the UI.
- Entry Health remains consistent with the wider analytics model.
- Representative datasets have deterministic expected analytical outcomes.
- No major Streamlit Statistics redesign is required for milestone completion.

---

## Milestone 15: Audio Foundation

Milestone 15 establishes a reusable local text-to-speech and card-audio
foundation before building the full desktop workflow.

### 15.1 Audio Scope

Version 1 supports audio export.

Audio-enabled Quiz behavior is deferred.

Each exported audio file represents exactly one current Card.

Users may select one or multiple Cards, or select a Collection to generate
multiple Card audio files in one batch.

A Collection must not be exported as one monolithic audio file.

### 15.2 Entry/Field Asset Identity

Speech generation is based on Entry and Field content.

Card audio is assembled from the current Card membership and order at export
time.

Reordering Entries or changing their Card membership must not require audio
assets to be permanently identified by Card number.

Cached speech assets should be invalidated when relevant source text or voice
configuration changes.

### 15.3 Required Field Speech

For the initial version:

- required template fields participate in audio generation;
- optional fields do not;
- field playback order follows the relevant template/display order; and
- field speech language must be deterministically resolvable.

Template metadata may distinguish values that use the Entry language from
values that use the Explanation language.

### 15.4 Repetition Modes

Support at least:

**Repeat Each Field**

Each field value is spoken N times before proceeding to the next field.

**Repeat Whole Card**

The complete Card sequence is spoken once and the full sequence is then
repeated N times.

### 15.5 TTS Provider and License Review

Establish a replaceable speech-provider boundary.

Evaluate locally runnable TTS technology suitable for English, French, and
Chinese.

Before bundling or distribution, verify:

- runtime license;
- model/voice license;
- redistribution requirements;
- third-party notices; and
- generated-output constraints where applicable.

Prefer technology that permits the intended public distribution model without
requiring a separate private fork.

### 15.6 Engineering Feasibility

Prove that the core can:

- synthesize representative English, French, and Chinese values;
- assemble one Card into one audio file;
- generate multiple Card files in a batch;
- apply both repetition modes; and
- handle synthesis failure without corrupting application data.

Full desktop export interaction is deferred.

### Milestone 15 Exit Criteria

- Speech-provider abstraction is defined.
- At least one viable local TTS path is technically verified.
- English, French, and Chinese feasibility is documented.
- Relevant license considerations are documented.
- Entry/Field-level audio identity and invalidation rules are defined.
- Card-level composition and repetition behavior are tested.
- No full Streamlit audio UI is required.

---

## Milestone 16: Desktop Architecture and UI Design

Milestone 16 begins the deliberate retirement of Streamlit as the primary UI.

The governing principle is:

> Replace the UI layer, preserve the learning engine.

### 16.1 Desktop Framework Decision

Evaluate the most suitable desktop framework against:

- compatibility with the existing Python core;
- SQLite integration;
- complex tables and forms;
- dialogs and popup workflows;
- background/batch tasks;
- packaging;
- licensing;
- maintainability; and
- future product requirements.

A small technical prototype may be used before the final framework decision.

### 16.2 Desktop Information Architecture

Define the main application structure and navigation.

Map existing workflows into appropriate desktop surfaces such as:

- main pages;
- dialogs;
- modal confirmation;
- popup detail windows;
- side panels;
- progress windows; and
- settings windows.

Do not mechanically reproduce Streamlit page structure where desktop-native
interaction offers a better model.

### 16.3 UI System

Define a coherent desktop design system for:

- typography;
- spacing;
- navigation;
- tables;
- forms;
- buttons;
- statuses;
- dialogs;
- warnings;
- progress;
- empty states; and
- destructive actions.

### 16.4 Controller and View State

Desktop controllers or view models should own transient UI state.

Durable learning state remains in SQLite.

Do not move former `st.session_state` behavior into reusable core modules.

### 16.5 Minimal Desktop Shell

Prove that the desktop application can:

- start successfully;
- resolve and open an existing database;
- display a basic Today summary;
- list existing entries; and
- call reusable core modules without Streamlit.

### Milestone 16 Exit Criteria

- Desktop framework decision is documented.
- Main navigation and workflow mapping are approved.
- Core desktop state-management boundaries are defined.
- Existing SQLite data opens without destructive conversion.
- A minimal shell proves core reuse.

---

## Milestone 17: Desktop Core Workflow Migration

Milestone 17 ports the high-frequency learning loop incrementally.

Recommended migration order:

1. Today
2. Review
3. Quiz
4. Entries
5. minimum Collection navigation required by those workflows

Each workflow must be verified before proceeding to the next.

### 17.1 Today

Port daily workload, due-review visibility, and workflow handoffs.

### 17.2 Review

Port Card browse/study/preparation, historical learning context, and the Quick
Quiz / Choose Quiz Type routes. Browsing alone must not create completion.

### 17.3 Quiz

Port session creation, answer submission, duplicate protection, recovery,
authoritative Card-scoped completion, Card/revision history context, Mistake
Book, Proficient Pool, and other current core behavior.

### 17.4 Entries

Port entry browsing, filtering, add/edit behavior, template-aware fields, and
safe editing.

### 17.5 Parity Verification

For each migrated workflow:

- verify existing databases;
- compare persisted state before/after equivalent actions;
- exercise restart and repeated-action behavior;
- run relevant automated tests; and
- record known parity gaps.

### Milestone 17 Exit Criteria

- The desktop application supports the primary daily learning loop.
- Today, Review, Quiz, and Entries are usable without Streamlit.
- No known parity defect threatens persisted user data.
- Streamlit may remain as a legacy reference/fallback but is no longer the
  primary development target.

---

## Milestone 18: Desktop Management and Major Feature Completion

Milestone 18 completes desktop parity for management/data workflows and
finishes the desktop-facing parts of the three new major capabilities.

### 18.1 Management Workflow Migration

Port:

- Collections and Card organization;
- Templates;
- Review Calendar;
- Import / Export;
- Backup and restore preview;
- Settings and storage information; and
- other remaining supported management workflows.

### 18.2 Linked Source Desktop Experience

Provide desktop-native interaction for linked collection sources, including:

- local file picker;
- linked-source status;
- Refresh action;
- refresh preview;
- valid/invalid/duplicate detail;
- controlled confirmation; and
- missing/unreadable-source handling.

### 18.3 Learning Analytics Desktop Experience

Create an insight-first Analytics experience.

Prioritize:

1. concise current interpretation;
2. evidence supporting the interpretation;
3. drill-down into relevant data; and
4. a practical next action where appropriate.

Charts and tables should support an analytical message rather than merely
display every available metric.

### 18.4 Card Audio Export Desktop Experience

Provide:

- Card selection;
- Collection-based batch selection;
- voice configuration;
- repetition count;
- repetition-mode selection;
- output-folder selection;
- batch progress;
- cancellation;
- synthesis error reporting;
- overwrite handling; and
- one output audio file per Card.

### Milestone 18 Exit Criteria

- Intended desktop feature scope is functionally implemented.
- Major management workflows no longer require Streamlit.
- Linked-source refresh has a complete desktop workflow.
- Analytics provides understandable, evidence-backed insights.
- Card audio export works end-to-end for supported languages.
- Streamlit-exclusive functionality is either migrated, explicitly deprecated,
  or documented as out of scope.

---

## Milestone 19: Desktop Product Hardening

Milestone 19 is the formal system-wide hardening phase for the desktop product.

No substantial new product capability should enter after this milestone begins
without reopening scope explicitly.

### 19.1 Feature Freeze

Approve the intended desktop product scope.

After approval:

- correctness fixes remain in scope;
- data-integrity, privacy, security, compatibility, and serious UX defects
  remain in scope;
- new product capabilities move to deferred work;
- scope may reopen only through an explicit recorded decision.

### 19.2 System Audit

Audit complete user journeys including:

```text
Create or import
-> Organize
-> Today
-> Review
-> Quiz
-> Learning Pools
-> Analytics
-> Export / Backup
```

Also audit:

```text
Template definition import
-> Entry import
-> Linked-file refresh
```

and:

```text
Card / Collection selection
-> Audio generation
-> Batch export
```

### 19.3 Data and Migration Integrity

Verify:

- fresh databases;
- representative upgraded databases;
- additive/repeated migrations;
- backups before major upgrade;
- collection/card history;
- review history;
- quiz history;
- analytics consistency;
- import transactions;
- linked-source refresh;
- backup/restore-preview boundaries; and
- audio-cache failure isolation.

### 19.4 Robustness and Desktop Interaction

Exercise:

- repeated clicks;
- interrupted operations;
- application restart;
- malformed import files;
- unavailable linked files;
- large/dense datasets;
- large batch audio generation;
- cancellation;
- invalid paths;
- read-only/unwritable destinations;
- empty states;
- warning dialogs;
- confirmation dialogs; and
- error recovery.

### 19.5 Privacy and Repository Safety

Verify that no release artifact includes:

- user databases;
- imports or exports;
- backups;
- generated audio;
- personal vocabulary content;
- secrets;
- local paths;
- logs containing private data; or
- caches and transient development files.

### 19.6 Full Manual Acceptance

Maintain the full-product manual QA artifact as a living acceptance record.

The desktop application becomes the primary manual acceptance target.

### Milestone 19 Exit Criteria

- No known release-blocking defect remains.
- No known high-risk data-integrity, privacy, or security defect remains.
- Core desktop workflows pass manual acceptance.
- Fresh and upgraded database scenarios pass.
- Import/export/linked-source/backup safety passes.
- Analytics outcomes are verified against representative expected cases.
- Audio generation and batch failure handling pass.
- Privacy and repository audits pass.
- Known limitations and deferred work are documented.
- `README.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, desktop migration
  documentation, and QA artifacts agree.

---

## Milestone 20: Packaging and Release Candidate

Milestone 20 prepares the desktop application for credible distribution.

### 20.1 Packaging

Establish:

- reproducible application build;
- clean-machine installation;
- supported operating-system assumptions;
- application-data location;
- existing-database migration;
- backup-before-upgrade behavior;
- uninstall behavior;
- preservation of user data where intended; and
- rollback/recovery guidance.

### 20.2 License and Third-Party Review

Finalize the project license and required third-party notices.

Review all distributed dependencies and bundled assets, including TTS runtime
and voice/model licenses where applicable.

### 20.3 Release Candidate Verification

Run:

- final automated regression;
- final manual smoke testing;
- clean-database testing;
- representative existing-database testing;
- installer/uninstaller testing;
- update/migration testing;
- privacy and secret scan;
- release-archive inspection; and
- documentation reconciliation.

Any Release Candidate blocker returns the project to the relevant hardening
work and requires affected regression to be repeated.

### 20.4 Release

Prepare a tag/release only after explicit approval.

Record the exact verified remote commit associated with the release.

### Milestone 20 Exit Criteria

- Reproducible packaging succeeds.
- Clean-machine installation and launch succeed.
- Existing user data can be migrated or opened through a documented safe path.
- Required notices and license obligations are satisfied.
- Full release regression passes.
- Release documentation is accurate.
- Final local/remote repository state is verified.
- Release Candidate acceptance is explicitly recorded.

---

## Current Version Complete

The current product generation may be declared complete only after:

- Milestone 19 exit criteria pass;
- Milestone 20 exit criteria pass;
- desktop Feature Freeze and Release Candidate acceptance are explicitly
  recorded;
- release documentation and known limitations are accurate; and
- the intended release commit is verified remotely.

Completion transitions the project to maintenance or the next product version.
It does not mean the project is permanently finished.

## Maintenance / Next Version

After the current version is complete:

- maintain correctness, compatibility, privacy, and data safety;
- triage defects separately from new capabilities;
- use additive migrations and documented upgrade verification;
- update `PROJECT_STATUS.md` after meaningful lifecycle changes; and
- update this roadmap only when scope or lifecycle decisions change.

## Deferred Features / Next Version

Deferred unless scope is explicitly reopened:

- bidirectional synchronization between linked files and collections;
- automatic deletion/reordering/overwrite of existing entries from linked
  source files;
- advanced external-source row identity and conflict resolution;
- speech generation for optional template fields;
- audio-enabled Quiz questions or automatic Quiz playback;
- pronunciation assessment;
- optional AI-generated analytical narrative;
- dictionary integrations;
- cloud sync;
- accounts or authentication;
- destructive/full database restore;
- additional learning modes not required for the current product promise; and
- other new capabilities introduced after desktop Feature Freeze.

## Current Development Sequence

```text
Pre-Desktop Stabilization
-> Repository Restructure
-> Import / Template Evolution Core
-> Learning Analytics Core
-> Audio Foundation
-> Desktop Architecture and UI Design
-> Desktop Core Workflow Migration
-> Desktop Management and Major Feature Completion
-> Desktop Product Hardening
-> Packaging / Release Candidate
```

The governing migration principle remains:

```text
Preserve trustworthy data and reusable core logic
-> stop investing in disposable Streamlit UI
-> prove desktop core reuse
-> migrate high-frequency workflows incrementally
-> complete desktop-native capabilities
-> harden the actual release target
-> package only after product-level verification
```
