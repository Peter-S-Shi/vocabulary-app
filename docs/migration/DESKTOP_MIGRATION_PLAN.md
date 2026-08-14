# Desktop Migration Plan

## 1. Migration Principle

> Replace the UI layer, preserve the learning engine.

Vocabulary App is transitioning from its current Streamlit interface toward a
native desktop application.

The migration is not intended to rewrite the product from scratch.

Preserve as much as possible:

- SQLite schema and existing user databases
- `src/app_config.py`
- `src/db.py`
- `src/entries.py`
- `src/entry_templates.py`
- `src/collections.py`
- `src/review.py`
- `src/quiz.py`
- `src/template_quiz.py`
- `src/statistics.py`
- `src/learning_workflow.py`
- `src/import_export.py`
- `src/backup.py`
- `src/text_parser.py`
- new reusable analytics, linked-source, and audio services created before or
  during migration

Replace or retire after desktop parity:

- `app.py`
- `src/ui_streamlit/`
- Streamlit-specific navigation
- `st.session_state`-driven presentation/controller behavior

The desktop application should call the existing core rather than reproduce
database queries, scheduling rules, quiz logic, import rules, or analytics
semantics inside the UI layer.

## 2. Lifecycle Position

The previous migration plan assumed:

```text
Complete Streamlit Feature Freeze
-> Complete Streamlit Product Hardening
-> Complete Streamlit Release Candidate
-> Begin desktop migration
```

That sequence is superseded.

The active product direction is now:

```text
Stabilize correctness and data semantics
-> reorganize the repository
-> implement reusable foundations for approved new capabilities
-> design and prove the desktop architecture
-> migrate the primary workflows
-> complete desktop-native features
-> harden the desktop product
-> package and release the desktop product
```

The current Streamlit application remains useful as:

- the presently runnable interface;
- a behavioral reference;
- a temporary compatibility surface;
- a manual regression aid where appropriate; and
- a thin verification surface for reusable core work where useful.

It is no longer the intended final Release Candidate target.

Do not spend substantial engineering effort polishing Streamlit-only UX that
will be discarded during migration unless the issue affects:

- persisted data;
- correctness;
- privacy or security;
- database compatibility;
- historical truthfulness;
- reusable core behavior; or
- a serious workflow blocker needed to establish the migration baseline.

## 3. Candidate Desktop Frameworks

**Status: Decided in M16.1.** The evidence-backed decision, license finding,
technical spike, and rejected-alternative rationale are recorded in
[M16.1 Desktop Architecture Contract](../design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md).
This section keeps the original candidate table for historical context; the
contract document is now authoritative for the decision itself.

| Framework | Fit | Main Trade-off | M16.1 outcome |
|---|---|---|---|
| PySide6 | Strong | Official Qt for Python; strong tables, dialogs, desktop workflows, and packaging potential, but adds Qt complexity and a large dependency | **Selected** |
| PyQt | Strong | Mature Qt ecosystem and similar capability, but distribution/licensing choices require deliberate review | Rejected — GPLv3-or-commercial only, no LGPL option |
| Tkinter | Limited | Built into Python and simple, but less suitable for dense tables, modern workflow design, and larger product growth | Rejected — confirmed still limited for Table-First |
| Toga / Briefcase | Exploratory | Native-oriented and cross-platform, but smaller ecosystem and higher migration uncertainty | Rejected for now — beta/macOS-only cell-widget support and no primary-source Windows-scale Table evidence |
| Electron / webview wrapper | Conditional | Powerful UI ecosystem but introduces an additional runtime and moves farther from the existing Python desktop architecture | Rejected — second runtime/toolchain |

No framework was selected solely because it resembles the current Streamlit
interface.

The small technical prototype required before the framework decision is
committed at
[`tests/test_m16_1_architecture_spike.py`](../../tests/test_m16_1_architecture_spike.py)
and its result is recorded in the M16.1 contract § 4.

## 4. Desktop Product Design Principle

The desktop application must not be designed as a literal page-by-page clone
of Streamlit.

Streamlit's navigation and interaction constraints should not determine the
desktop information architecture.

Desktop design should use the most appropriate interaction surface for each
task:

- full main page;
- secondary page;
- modal dialog;
- non-modal detail window;
- side panel;
- context menu;
- progress dialog;
- confirmation dialog;
- file picker; or
- dedicated workflow window.

The desktop redesign should preserve product semantics, not historical UI
limitations.

## 5. Future Desktop Screen Mapping

The mapping below is conceptual rather than a strict one-to-one port.

| Current / Planned Capability | Future Desktop Surface |
|---|---|
| Today | Home / Today Dashboard |
| Entries | Entry Manager |
| Entry Add/Edit | Entry Editor dialog or dedicated editor pane |
| Collections | Collection Manager |
| Card organization | Collection/Card detail workspace |
| Review | Review Session |
| Quiz | Quiz Session |
| Review History / Schedule | Review Calendar / Card History |
| Statistics | Learning Analytics |
| Entry Health | Analytics drill-down / Entry analysis |
| Templates | Template Manager |
| Template Definition Import/Export | Template Manager / Data Tools |
| Import / Export | Data Tools |
| Linked Collection Source | Collection settings / source dialog |
| Backup / Restore Preview | Data Safety / Backup Tools |
| Card Audio Export | Audio Export workflow |
| Settings / Storage | Settings |
| Legacy Dashboard | Secondary overview or retired if redundant |

Some existing Streamlit tabs may disappear entirely if their information is
better integrated into desktop workflows.

## 6. Core Service Layer Needs

Current Streamlit pages often call focused core functions directly.

That remains acceptable where the workflow is simple.

Desktop workflows may benefit from thin orchestration services such as:

```text
src/services/
  entry_service.py
  collection_service.py
  review_service.py
  quiz_service.py
  workflow_service.py
  import_export_service.py
  linked_source_service.py
  analytics_service.py
  audio_export_service.py
```

These are conceptual boundaries, not mandatory filenames.

Services should:

- orchestrate existing reusable modules;
- coordinate multi-step workflows;
- expose UI-independent inputs/results;
- centralize transactions where appropriate; and
- make desktop controllers easier to test.

Services must not:

- duplicate SQL already owned by core modules;
- duplicate quiz/review algorithms;
- hide business rules only inside desktop code;
- become an oversized universal application layer; or
- be created merely for architectural symmetry.

Add a service only when a real desktop or reusable workflow demonstrates the
need.

## 7. Controller and UI State Migration

**Status: Made concrete in M16.1.** This section's principle is unchanged and
still applies; the concrete package structure, controller responsibilities,
durable-preference ownership, and the exact translation of the
`set_page_focus`/`session_state` pattern into typed controller/`AppState`
state are frozen in
[M16.1 Desktop Architecture Contract §§ 9-13](../design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md).

`st.session_state` is transient UI state and must not move into core modules.

Future desktop controllers or view models should own state such as:

- active page or workspace;
- selected entry IDs;
- selected collection;
- selected Card;
- current review Card;
- current Quiz item;
- revealed-answer state;
- Quiz window/controller recovery state;
- temporary filters;
- sort order;
- table selection;
- import preview;
- Template import preview;
- linked-source refresh preview;
- audio-export selection;
- audio batch progress;
- temporary dialog state; and
- current focus/navigation handoff.

Durable learning state remains in SQLite.

Examples of durable state include:

- entries;
- templates;
- collections;
- collection membership and order;
- Quiz sessions;
- Quiz item logs;
- review history;
- review schedules;
- learning pools;
- linked-source metadata;
- durable application configuration where appropriate; and
- migration metadata.

Do not serialize arbitrary desktop UI state into the database merely to replace
Streamlit session state.

## 8. Database Compatibility

Existing user SQLite databases are protected assets.

The desktop application must open existing compatible databases through a
documented migration path.

Rules:

- schema changes remain additive where practical;
- migrations remain versioned and idempotent;
- migrations should be safe to run repeatedly;
- backup should be recommended or created before significant migration;
- existing Entries, Templates, Collections, Quiz history, Review history, and
  learning pools must be preserved;
- Card history changes require explicit migration reasoning because current Card
  identity semantics are under review;
- linked-source metadata must not make source files authoritative over existing
  Entry data;
- analytics schema additions must not rewrite historical performance facts;
- audio cache metadata must remain disposable/rebuildable where practical;
- application-data relocation must be explicit and reversible; and
- destructive restore or database replacement remains confirmation-protected.

Database migration and UI migration are related but separate concerns.

A UI rewrite must not be used as justification for unnecessary schema redesign.

## 9. Pre-Migration Preconditions

Full Streamlit Release Candidate delivery is not a prerequisite.

Before serious desktop migration begins, the project instead requires a
**trustworthy pre-desktop baseline**.

This baseline must include:

- correction of confirmed Entry editing integrity risks;
- Card-scoped Quiz completion established as the single authoritative Card
  learning/review event;
- independent manual next-review scheduling and legacy SRS behavior retired
  from active product truth;
- stable `card_id` and historically traceable Card membership sufficient to
  preserve truthful history;
- re-acceptance of Entry Health semantics;
- resolution of high-risk database/data integrity issues found through manual
  QA;
- architecture checks confirming reusable core code remains independent of
  Streamlit;
- preservation of representative existing databases;
- current backup capability; and
- a recorded verified repository baseline.

Streamlit-specific visual polish is not part of this prerequisite unless it
blocks correctness verification.

## 10. Pre-Migration Feature Foundations

Before the full desktop migration, reusable portions of the approved new product
scope should be developed where doing so avoids duplicate implementation.

### Template Definition Portability

Establish reusable:

- Template Definition export;
- Template Definition CSV import;
- validation;
- preview data;
- atomic creation; and
- round-trip compatibility.

Where required by audio generation, Template fields may also carry deterministic
speech-language semantics.

### Linked Collection Append Sources

Establish reusable:

- source-link persistence;
- CSV/XLSX source parsing;
- refresh analysis;
- duplicate detection;
- new/invalid/duplicate classification; and
- confirmed append-only execution.

Desktop file pickers and source-management UI are not required at this stage.

### Learning Analytics Core

Establish reusable:

- metric semantics;
- analytical comparisons;
- personal baseline logic;
- coverage analysis;
- evidence sufficiency;
- trend/recovery interpretation; and
- structured insights.

Do not invest in a full Streamlit analytics redesign.

### Audio Foundation

Establish reusable:

- a replaceable speech-provider abstraction using the closed M15.0 routing:
  Kokoro-82M / `af_heart` for English, `sherpa-onnx` /
  `fr_FR-siwis-medium` for French, and Windows WinRT Yaoyao (`zh-CN`) for
  Mandarin with no silent fallback;
- deterministic template-level Entry-language, Explanation-language, and
  non-spoken field semantics;
- required-field speech sequencing in template/display order, including the
  approved versioned French morphology `required=1` corrections;
- Entry/Field-level cache identity;
- Card-level audio assembly;
- repetition modes; and
- representative local TTS feasibility, now verified by the M15.0 selection
  gate.

Reusable Card batch-export and failure-safety behavior will be completed before
desktop migration. The full interactive Audio Export UX remains deferred to
desktop. Audio-enabled Quiz behavior is deferred beyond M15: the Audio
Foundation provides reusable audio-export infrastructure only and must not add
spoken Quiz modes or modify existing Quiz learning semantics.

## 11. Migration Phases

### Phase 1: Desktop Architecture and Design

Define:

- framework;
- application shell;
- navigation;
- controller/view-model approach;
- design system;
- dialog strategy;
- error/warning presentation;
- file interaction;
- progress/cancellation patterns; and
- packaging constraints that may affect architecture.

Do not begin by mechanically porting all existing pages.

### Phase 2: Minimal Desktop Shell

Prove:

- native application launch;
- existing database resolution;
- database open/migration;
- basic Today data display;
- Entry listing;
- reusable core imports;
- basic navigation; and
- clean shutdown/restart behavior.

The purpose is architecture proof, not product parity.

### Phase 3: High-Frequency Workflow Migration

Recommended order:

1. Today
2. Review
3. Quiz
4. Entries
5. minimum Collection navigation required by these workflows

This order prioritizes the daily learning loop.

Each workflow should be migrated and verified independently.

### Phase 4: Management Workflow Migration

Port:

- Collections;
- Card organization;
- Templates;
- Review Calendar;
- Data Tools;
- Import / Export;
- Backup / Restore Preview;
- Settings; and
- remaining supported management workflows.

### Phase 5: Desktop-Native Major Features

Complete the desktop-facing parts of:

#### Linked Sources

- file picker;
- source status;
- Refresh action;
- refresh preview;
- detail inspection;
- confirmation; and
- unavailable-file handling.

#### Learning Analytics

- insight-first summary;
- supporting metrics;
- relevant charts;
- drill-down;
- Entry Health integration; and
- actionable recommendation presentation.

#### Card Audio Export

- Card/Collection selection;
- batch selection;
- voice settings;
- repetition settings;
- output folder;
- progress;
- cancellation;
- error recovery;
- overwrite handling; and
- one audio file per Card.

### Phase 6: Streamlit Retirement

Once required desktop parity is proven:

- stop adding Streamlit features;
- mark Streamlit as legacy;
- remove it from primary documentation and launch guidance;
- retain only what is needed for historical traceability or temporary
  compatibility;
- decide whether `app.py` and `src/ui_streamlit/` remain archived, removable,
  or available through a legacy path; and
- verify that no desktop workflow still accidentally depends on Streamlit.

Do not delete the legacy UI prematurely if it remains useful for regression
comparison during migration.

### Phase 7: Desktop Hardening

After intended desktop feature scope is implemented:

- pass formal Feature Freeze;
- perform full system audit;
- run full manual acceptance;
- verify fresh and upgraded databases;
- exercise large datasets;
- exercise malformed/interrupted workflows;
- audit analytics correctness;
- audit linked-source safety;
- audit audio-generation failures;
- verify privacy and local-path handling; and
- resolve release-blocking defects.

The desktop application is the hardening target.

### Phase 8: Packaging and Release

Only after desktop hardening:

- finalize application-data location;
- build distributable artifacts;
- test clean-machine installation;
- test update/migration behavior;
- test uninstallation;
- confirm user-data preservation;
- document rollback/recovery;
- finalize license and third-party notices;
- perform release privacy scans;
- prepare Release Candidate; and
- tag/release only after explicit approval.

## 12. Workflow-Specific Migration Notes

### Today

Today should become the primary landing surface.

It should use factual Quiz and Card history to answer:

- what has never been quizzed;
- what was last quizzed and how it performed;
- what needs attention;
- what the user was recently doing; and
- where the user should continue.

Navigation from Today into Review and Quiz should be explicit desktop
controller behavior rather than Streamlit focus-routing tricks.

### Review

Review must preserve:

- Card browse/study/preparation;
- current and historical Card composition context where available;
- factual prior Card Quiz history;
- a Quick Quiz route; and
- a Choose Quiz Type route.

Browsing alone must not create a completed learning event. The desktop redesign
must not reintroduce independent manual scheduling or legacy SRS rating behavior
as the active learning model.

### Quiz

Quiz must preserve:

- objective and self-graded modes;
- durable session state;
- duplicate-submission protection;
- restart/recovery behavior;
- Mistake Book;
- Proficient Pool;
- Card/Collection context; and
- Card-scoped completion linked to stable Card identity and the membership
  revision used at that time.

Desktop Quiz may use a dedicated workflow window if that provides a cleaner
learning experience than embedding everything into the main management shell.

### Entries

Desktop Entry management should improve:

- dense-table readability;
- search/filter behavior;
- add/edit safety;
- Template-aware field editing;
- custom-field ordering; and
- multi-selection where useful.

Entry edit state must remain isolated between different Entries.

### Collections and Cards

Desktop Collection management should explicitly represent:

- Collection order;
- Entry order;
- Card grouping;
- Card size;
- current Card composition; and
- history-sensitive operations.

Reorder behavior should reflect the approved Card history strategy.

### Templates

Template management should make field structure easier to understand and edit
than the current manual Streamlit workflow.

Template Definition import/export should reduce the need to recreate field
structures manually.

### Learning Analytics

The desktop Analytics experience should not simply port current Statistics
tables.

Preferred information order:

```text
What matters now
-> why it was flagged
-> supporting evidence
-> deeper details
-> useful next action
```

Charts should support a specific interpretation rather than function as a
generic metric gallery.

### Linked Local Files

Linked local files should appear as a property of a Collection rather than as a
global synchronization system.

The UI should make clear that:

> Refresh finds appendable new content.

It does not mean:

> Make the Collection identical to the source file.

### Audio Export

Audio generation should appear as an export workflow rather than as an Entry
editor feature.

Users should be able to choose:

- one Card;
- several Cards; or
- a Collection.

The result remains:

```text
one Card
-> one audio file
```

Batch Collection export therefore creates multiple independent audio files.

## 13. Background and Long-Running Work

Desktop migration introduces operations that may take long enough to block the
UI, including:

- large imports;
- large linked-file refresh analysis;
- backup generation;
- audio synthesis;
- audio batch composition; and
- potentially larger analytics queries.

The desktop architecture should support:

- progress reporting;
- cancellation where safe;
- disabled duplicate actions;
- controlled failure recovery; and
- clear distinction between completed, canceled, and failed work.

Business operations must remain transactionally safe even if presentation work
runs asynchronously inside the desktop application.

Do not allow background UI execution to weaken database transaction boundaries.

## 14. File-System and Local Data Design

The current source application may use project-local paths that are unsuitable
for packaged desktop software.

The desktop version must define appropriate locations for:

- application data;
- SQLite database;
- backups;
- import staging where needed;
- TTS models;
- disposable audio cache;
- user-exported audio;
- logs, if any; and
- application configuration.

Important distinctions:

### Durable user data

Examples:

- SQLite database;
- user-selected backups;
- user-selected exported files.

### Rebuildable local assets

Examples:

- audio cache;
- downloaded TTS model cache where licensing permits;
- temporary preview files.

### Developer-only files

Examples:

- test artifacts;
- local prompt drafts;
- development databases;
- temporary exports.

Packaged builds must never rely on repository-relative development paths for
durable user data.

## 15. Audio Packaging Considerations

Audio support introduces additional desktop considerations:

- TTS runtime size;
- voice/model size;
- first-run model availability;
- offline availability;
- supported languages;
- CPU/memory requirements;
- cache location;
- cache cleanup;
- model/runtime licensing;
- third-party notices; and
- packaged-resource versus downloadable-model strategy.

The audio architecture should remain provider-based so the product can replace
a TTS implementation without rewriting Card/audio workflow logic.

Generated audio files are user output and must not be committed to the
repository.

## 16. Analytics Migration Considerations

Learning Analytics depends on trustworthy historical data.

Do not treat analytics UI completion as proof that analytical conclusions are
valid.

Verification must independently test:

- metric definitions;
- grouping grain;
- date ranges;
- sparse-data handling;
- personal baselines;
- relative comparisons;
- Entry Health categories;
- Review versus Quiz interpretation; and
- representative expected insights.

The desktop UI should consume structured analytical results rather than invent
thresholds or classifications in presentation code.

## 17. Linked Source Migration Considerations

Linked local sources introduce path-specific desktop behavior.

The design must account for:

- moved files;
- renamed files;
- deleted files;
- unreadable files;
- malformed files;
- unsupported extensions;
- source changes between preview and confirmation; and
- duplicate refresh actions.

An unavailable linked file must not damage the Collection or existing Entries.

The user should be able to replace/relink the source path without rebuilding the
Collection.

## 18. Migration Readiness Checklist

### Core and Data

- [x] Core modules substantially separated from Streamlit
- [x] SQLite remains the durable source of truth
- [x] Database path resolution is centralized
- [x] Import/export validation and execution are largely UI-independent
- [x] Backup generation and preview are largely UI-independent
- [x] Quiz durable session and duplicate protection live in core/SQLite
- [x] Today workflow queries are reusable
- [x] Schema/app metadata and migration foundations exist
- [x] Entry-editing integrity issue resolved
- [x] Card-scoped Quiz is the authoritative Card learning completion
- [x] independent manual scheduling and legacy SRS retired from active behavior
- [x] stable Card identity and membership revisions implemented
- [x] Entry Health re-accepted
- [x] pre-desktop baseline verified

### New Core Foundations

- [x] Template Definition import/export core complete
- [x] linked Collection append-source core complete
- [x] Learning Analytics core complete
- [x] local TTS feasibility and provider selection verified
- [ ] Card audio composition core verified

### Desktop Architecture

- [ ] desktop framework approved
- [ ] information architecture approved
- [ ] UI design system established
- [ ] controller/view-model boundaries established
- [ ] minimal desktop shell opens existing database
- [ ] basic Today/Entries prototype works

### Workflow Migration

- [ ] Today migrated
- [ ] Review migrated
- [ ] Quiz migrated
- [ ] Entries migrated
- [ ] Collections migrated
- [ ] Templates migrated
- [ ] Review Calendar migrated
- [ ] Import / Export migrated
- [ ] Backup / Restore Preview migrated
- [ ] Settings migrated

### Major Desktop Features

- [ ] linked-source desktop workflow complete
- [ ] Learning Analytics desktop experience complete
- [ ] Card Audio Export desktop workflow complete

### Release Readiness

- [ ] Streamlit retirement decision executed
- [ ] desktop Feature Freeze approved
- [ ] full desktop Product Hardening complete
- [ ] full manual acceptance complete
- [ ] clean-machine packaging proven
- [ ] existing-data migration proven
- [ ] rollback/recovery documented
- [ ] license and third-party notices complete
- [ ] final privacy/release audit passes
- [ ] Release Candidate accepted

## 19. Recommended Development Sequence

```text
Milestone 11
Pre-Desktop Stabilization
        ↓
Milestone 12
Repository Restructure
        ↓
Milestone 13
Import and Template Evolution Core
        ↓
Milestone 14
Learning Analytics and Insight Core
        ↓
Milestone 15
Audio Foundation
        ↓
Milestone 16
Desktop Architecture and UI Design
        ↓
Milestone 17
Desktop Core Workflow Migration
        ↓
Milestone 18
Desktop Management and Major Feature Completion
        ↓
Milestone 19
Desktop Product Hardening
        ↓
Milestone 20
Packaging and Release Candidate
```

## 20. Recommended Next Decision

Do not start by building the desktop UI immediately.

The Milestone 11 trustworthy baseline, repository restructure, Import and
Template Evolution foundation, Learning Analytics core, and the complete
Milestone 15 Audio Foundation (through M15.3) are established on `main`.
Milestone 16 has started: M16.0 Desktop UI Design Baseline is complete and
frozen in `DESIGN.md`. M16.1 Desktop Architecture Foundation — the framework
decision (§ 3) and controller/view-state boundaries (§ 7) — is implemented on
its review branch and recorded in
[M16.1 Desktop Architecture Contract](../design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md),
pending independent review and merge to `main`.

Once M16.1 is independently reviewed and merged, M16.2 proves a deliberately
small native shell that opens the existing SQLite database and proves reuse
of the current learning engine (§ Phase 2 below), built against the M16.1
contract without reopening the framework or state-boundary decisions.

The migration should remain incremental:

```text
protect data
-> stabilize semantics
-> preserve the core
-> stop expanding disposable Streamlit UI
-> prove the desktop shell
-> migrate the daily learning loop
-> migrate management workflows
-> complete desktop-native features
-> harden the actual release target
-> package only after verification
```
