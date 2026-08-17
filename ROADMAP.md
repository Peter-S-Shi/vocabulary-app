# Vocabulary App Roadmap

This roadmap is the authoritative lifecycle and milestone outline for
Vocabulary App. For the current evidence-based snapshot, see
`PROJECT_STATUS.md`. For desktop-specific migration principles and workflow
mapping, see `docs/migration/DESKTOP_MIGRATION_PLAN.md`. For the reconstructed
history before Git was initialized, see `docs/history/PRE_GIT_HISTORY.md`.

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

**Milestone 16 — Desktop Architecture and UI Design Complete on `main`;
Milestone 17 In Progress**

The trustworthy data/business-logic baseline, repository restructure, Import
and Template Evolution foundation, and Learning Analytics and Insight Core are
complete. Milestone 15.0 closed the TTS provider-selection and feasibility
gate. Milestone 15.1 merged through PR #13 at
`ebca2c2c5c6bf11f5e0a54b9782e15f08f51d216`. Milestone 15.2 merged through
PR #15 at `c9d7e8d05c968d52af2b77c76454f849706788bc`. Milestone 15.3 merged through
PR #17 at `9448f2e44940e0d426a965823aa66c48f53ec0f1` from independently reviewed
head `765c4c5f92c29a5c30cb41b0c2aa3fbbc01df7db`, completing Milestone 15.
Milestone 16 is now **complete on `main`**. M16.0 Desktop UI Design Baseline —
information architecture, theme architecture, and accessibility rules — is
complete and frozen in [DESIGN.md](DESIGN.md). M16.1 Desktop Architecture
Foundation (framework decision and controller/view-state boundaries) merged
through PR #21 at `a1dc044721e9017d39842e96e0516a88a36d129f` from
independently reviewed head `439cc9612578b5dc78eda57e07f054bec8d60d38`; see
[M16.1 Desktop Architecture Contract](docs/design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md).
M16.2 Minimal Desktop Vertical Slice & M16 Exit merged through PR #23 at
`2e900d243950ca93aedf5cbde5b836dc6e378f25`, closing Milestone 16 after
engineering review, SQLite-compatibility review, AppState/state-boundary
review, human native-window visual acceptance, navigation-contrast
acceptance, and desktop-launcher/icon acceptance; see
[Milestone 16 Closure](docs/history/MILESTONE16_CLOSURE.md) for full
evidence (see § Milestone 16 below).

Milestone 17 — Desktop Core Workflow Migration is now **in progress** on
the single long-lived branch `agent/m17-desktop-core-workflow-migration`.
The **Motion / Transition Foundation** and Today's non-visual
controller/handoff groundwork are implemented and retained. Two earlier
Today presentations were rejected at human visual review and
controlled-reset to the M16.2 placeholder; the replacement
[DESIGN.md](DESIGN.md) (`c19b686`) was then supplied and committed as the
authoritative canonical visual-reference and spatial-composition
authority for M17+. **A third, fresh Today presentation — a Command
Center built from that authority, with a shared Management Navigation
Rail — is now complete and Human Accepted at native visual acceptance**
(PASS recorded 2026-08-16 against `fdd9cc0`, after two visual-calibration
passes and one rendering-bug fix). **Review — the Immersive Focus / Study
Mode browse-and-preparation surface — is also complete and Human Accepted
at native visual acceptance** (PASS recorded 2026-08-16 against `38d53d2`,
against `VR-STUDY-001`, `Review - Quiz.pdf` p4 Variant C, after one
corrective patch for a functional-honesty finding on the Choose Quiz Type
confirmation). **Quiz — the native session/grading/completion migration
that Review's Quick Quiz and Choose Quiz Type launch for real — is also
complete and Human Accepted at native visual acceptance** (PASS recorded
2026-08-16 against `311762c`, against `VR-STUDY-001`, after a
typography/spacing visual-calibration corrective pass and a UX-defect
corrective pass). **Quiz Presentation Choice (Feature 3B) — an optional
Flip Card + Filmstrip Quiz presentation against `VR-STUDY-002`, explicitly
scoped to Quiz only — is also complete and Human Accepted at native
visual acceptance** (PASS recorded 2026-08-16 against `c54468e`).
**Entries (Feature 4) — the real Table-First Entries Manager against
`VR-ENTRIES-001`, replacing the M16.2 architecture-proof placeholder — is
also complete and Human Accepted at native visual acceptance** (PASS
recorded 2026-08-16 against `2cc333256d2a831c3268c150a86935276117f1c8`,
after a corrective pass for typography, toolbar layout, Scope Pane
resizing, editor scroll-safety, the "Add to Collection" menu interaction,
and checkbox selection). **Minimum Collection Integration — a
Collections Navigator (DESIGN.md § 6.8, Class B) plus typed handoffs
from Collections/Today into Entries and from Collections into
Review/Study — is also complete and Human Accepted at native visual
acceptance** (PASS recorded 2026-08-17 against
`6d8ed13c206018ece80277210abb858afd8930f9`, after a corrective pass for
paged/scrollable Card navigation, efficient large-Collection Card
projection, the focused-Entry-vs-checked-Entries separation, and the
persistent direct Star toggle). **Theme Completion & Cross-Screen
Validation — closing the Appearance axis (System/Light/Dark, Calm Blue)
as a real, live-switchable, OS-aware product capability, plus a
typography color-hierarchy audit and a Navigation Rail state-rendering
reliability fix — is also complete and Human Accepted at native visual
acceptance** (PASS recorded 2026-08-17 against
`48a171f6aaa7e7ce3b60be945024c8712e69ec64`, after two corrective passes:
a typography color-role hierarchy patch, and a Navigation Rail
active/normal/disabled state-rendering reliability fix). Milestone 17
overall is not complete; the next and final objective is **M17 Parity +
Exit Verification**. See § Milestone 17 below for the operating model,
the reset history, and the current feature-sequence position.

Feature Freeze will occur only after the intended desktop feature scope has
been implemented and verified.

---

## Milestone 11: Pre-Desktop Stabilization

**Status: Complete — Trustworthy Pre-Desktop Baseline Established.**

Closure evidence is recorded in `docs/history/MILESTONE11_CLOSURE.md`. This status does not
mean Feature Freeze, Release Ready, Desktop Ready, or Product Hardening
completion. Milestone 12 subsequently reorganized the repository without
changing this historical baseline.

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

**Status: Complete — Repository Restructure Complete.**

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

M12 moved 14 supporting documents into a compact `docs/` hierarchy, added a
documentation index, repaired current references, and left the application,
core modules, schema, migrations, and learning semantics unchanged. The next
objective is Milestone 13 — Import and Template Evolution Core.

---

## Milestone 13: Import and Template Evolution Core

**Status: Complete — Import and Template Evolution Core Established.**

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
- no speech-language role in portable definition v1.

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

M13 closed with Template Definition CSV v1 and a reusable Linked Append Source
core. Template fields retain their original non-negative `display_order`;
shared values are deterministic by `(display_order ASC, field_key ASC)`. Linked
sources support one local CSV/XLSX source per Collection in `general_entry` or
`template_aware` mode, require preview and explicit confirmation, and append
New Valid rows only. They are non-authoritative and do not synchronize source
deletions, reordering, or edits back onto app content.

The accepted v1 limits include no permanent source-row identity, no background
refresh, no desktop picker UI, and no Template overwrite/merge, system
ownership portability, or `speech_language_role`. These are scope limits, not
M13 blockers. M13 closed cleanly and handed the lifecycle to Milestone 14.

---

## Milestone 14: Learning Analytics and Insight Core

**Status: Complete — Learning Analytics and Insight Core Established.**

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
- Practice / Learning Activity;
- Recovery;
- Stale Evidence;
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

M14 completed with a frozen semantic contract and three verified batches.
Batch A established read-only Evidence Profiles, Coverage, Scope Activity, and
Personal Baseline. Batch B established deterministic Primary Findings,
structured actions, clustering, hierarchy suppression, and the capped Learning
Brief. Batch C made M14 the Entry-level interpretation authority, converted
legacy Entry Health APIs into compatibility projections, and passed integrated
synthetic, M11/M13, architecture, privacy, and migration-safety acceptance.

Accepted M14 v1 limits include no persisted insight history, no global learning
score, no automatic pool/status mutation, no overdue insight backlog, no AI
judgment requirement, and no desktop-native presentation. These are deliberate
scope boundaries, not M14 closure defects.

---

## Milestone 15: Audio Foundation

**Status: Complete on `main` through PR #17 at
`9448f2e44940e0d426a965823aa66c48f53ec0f1`.**

Milestone 15 establishes a reusable local text-to-speech and card-audio
foundation before building the full desktop workflow.

**Audio-enabled Quiz behavior is deferred beyond M15. M15 provides reusable
audio-export infrastructure only and must not add spoken Quiz modes or modify
existing Quiz learning semantics.**

### 15.0 TTS Provider Selection & Feasibility

**Status: Closed.** The authoritative decision and supporting license record
are documented in:

- [M15.0 TTS Provider Selection Closure](docs/history/M15_0_TTS_PROVIDER_SELECTION_CLOSURE.md)
- [TTS License and Attribution Record](docs/policies/TTS_LICENSE_AND_ATTRIBUTION.md)

The frozen routing is:

- English: Kokoro-82M / `af_heart`;
- French: `sherpa-onnx` / `fr_FR-siwis-medium`; and
- Mandarin: Windows WinRT `SpeechSynthesizer` / Yaoyao (`zh-CN`).

Mandarin has a no-silent-fallback policy. The Yaoyao Unicode/mojibake defect
found during the feasibility work is resolved. Reusable runtime/model assets
remain machine-local and external to the repository; documentation uses
`<SHARED_TTS_DIR>` rather than a personal path.

M15.0 also established that the French morphology fields listed in the closure
record must become `required=1` through a safe versioned implementation path.
It did not resolve the schema's missing explicit field-level
`speech_language_role`. The audition heuristic is not a product contract.

### 15.1 Speech Semantics & TTS Provider Foundation

**Status: Complete on `main`.**

Establish the reusable, UI-independent speech contract and provider boundary.

- preserve the frozen English, French, and Mandarin provider routing from
  M15.0 rather than reopening provider search;
- keep provider behavior behind a replaceable abstraction instead of embedding
  it in Streamlit or desktop UI code;
- define deterministic template-level `speech_language_role` routing and
  resolve whether each spoken field uses the Entry language, Explanation
  language, or is non-spoken;
- apply the approved French `required=1` corrections through an additive,
  versioned, migration-safe path:
  - `French Verb Present`: `je`, `tu`, `il_elle_on`, `nous`, `vous`, and
    `ils_elles`;
  - `French Adjective Agreement`: `feminine_singular`, `masculine_plural`, and
    `feminine_plural`; and
  - `French Noun Gender Plural`: `gender`, `plural`, and `article`;
- preserve the initial rule that required fields participate in speech and
  optional fields do not, while making the explicit language/non-spoken role
  contract deterministic;
- sequence spoken fields deterministically in template/display order; and
- retain locally runnable behavior and the documented provider, license, and
  attribution constraints.

No full Streamlit or desktop audio UI is required in M15.1.

### 15.2 Audio Asset & Card Composition Core

**Status: Complete on `main`.**

Build the reusable audio-generation and Card-composition engine.

- base speech generation on current Entry/Field content;
- identify cached assets using relevant content, language, provider, voice, and
  configuration rather than Card number;
- invalidate assets safely when source text or relevant voice configuration
  changes;
- assemble Card audio from current Card membership and order at export time;
- provide predictable field boundaries and pauses;
- support **Repeat Each Field** and **Repeat Whole Card**; and
- keep generated audio/cache disposable and rebuildable where practical.

Audio generation must not create learning completion, Quiz evidence, analytics
evidence, or any other learning-state mutation.

### 15.3 Batch Export, Failure Safety & Milestone Closure

**Status: Complete on `main`.** PR #17 merged at
`9448f2e44940e0d426a965823aa66c48f53ec0f1` from final reviewed head
`765c4c5f92c29a5c30cb41b0c2aa3fbbc01df7db`.

Complete the reusable export workflow and close M15 before desktop UI work.

- export exactly one current Card per audio file;
- support one Card, multiple Cards, or Collection batch selection semantics;
- export a Collection as multiple Card files, never one monolithic Collection
  file;
- report batch results deterministically;
- prevent synthesis or file failures from corrupting application data;
- support safe partial-output cleanup and retry behavior;
- verify representative English, French, and Mandarin end to end;
- complete license and third-party-notice readiness;
- run regression and migration verification; and
- record final M15 closure evidence.

Full desktop export interaction remains deferred to the desktop milestones.

### Milestone 15 Exit Criteria

- Speech-provider abstraction is defined and honors the frozen routing.
- English, French, and Mandarin feasibility remains documented and verified.
- Relevant license considerations are documented.
- Field-level spoken-language semantics are deterministic.
- Approved French Template validity corrections are migration-safe.
- Entry/Field-level audio identity and invalidation rules are defined.
- Card-level composition and repetition behavior are tested.
- Batch export and failure-safety behavior are verified.
- Audio generation does not mutate learning state.
- No spoken Quiz mode or Quiz learning-semantics change is introduced.
- No full Streamlit audio UI is required.

---

## Milestone 16: Desktop Architecture and UI Design

**Status: Complete on `main`.** M16.0, M16.1, and M16.2 are all complete;
final closure is recorded in
[Milestone 16 Closure](docs/history/MILESTONE16_CLOSURE.md).

Milestone 16 begins the deliberate retirement of Streamlit as the primary UI.

The governing principle is:

> Replace the UI layer, preserve the learning engine.

Milestone 16 is organized into three coherent, independently understandable,
implementable, and verifiable engineering loops rather than by every
architectural layer or checklist item.

### M16.0 Desktop UI Design Baseline

**Status: Complete.** Absorbs the former Desktop Information Architecture and
UI System scope.

Authority: [DESIGN.md](DESIGN.md).

Completed:

- desktop information architecture;
- Management Mode / Study Mode;
- master-screen archetypes;
- Utility/Dialog grammar;
- theme architecture;
- semantic tokens;
- contrast/accessibility;
- interaction/component rules; and
- visual acceptance criteria.

No new branch was required; this work is already on `main`.

### M16.1 Desktop Architecture Foundation

**Status: Complete on `main`.** PR #21 merged at
`a1dc044721e9017d39842e96e0516a88a36d129f` from independently reviewed head
`439cc9612578b5dc78eda57e07f054bec8d60d38`. Combines the former Desktop
Framework Decision and Controller/View State scope into one architecture
decision loop.

The frozen decision — selected framework (PySide6), evidence, technical
spike, state taxonomy, package structure, concurrency model, and theme/token
implementation boundary — is recorded in
[M16.1 Desktop Architecture Contract](docs/design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md).

Scope:

- evaluate and select the desktop framework against compatibility with the
  existing Python core, SQLite integration, complex tables and forms,
  dialogs and popup workflows, background/batch tasks, packaging, licensing,
  maintainability, and future product requirements;
- use a small technical spike only if needed for evidence;
- document why the selected framework fits the existing Python/SQLite core
  and frozen `DESIGN.md` requirements;
- define controller/view-model ownership of transient UI state;
- define the boundary between transient desktop state and durable
  SQLite/core state;
- define how desktop code calls reusable core/services without duplicating
  business logic;
- identify only genuinely necessary thin orchestration/service boundaries;
- define the initial desktop module/package structure; and
- preserve existing database compatibility.

Do not build the full desktop shell in M16.1.

Exit: framework and state/architecture boundaries are frozen enough that
minimal-shell implementation no longer depends on unresolved architecture
choices.

### M16.2 Minimal Desktop Vertical Slice & M16 Exit

**Status: Complete on `main`.** PR #23 merged at
`2e900d243950ca93aedf5cbde5b836dc6e378f25`, from final reviewed head
`0e78e6f9c1892846e7b63d9696d2312dfcaa6b9a`. Combines the former Minimal
Desktop Shell scope with final Milestone 16 exit verification, built against
the frozen M16.1 architecture contract without reopening it.

Evidence, proven capabilities, test results, and the completed human
visual-check list are recorded in
[Milestone 16 Closure](docs/history/MILESTONE16_CLOSURE.md).

Scope:

- create the minimal native desktop shell using the M16.1 architecture;
- prove the app starts successfully;
- prove it opens an existing compatible SQLite database without destructive
  conversion;
- prove basic desktop shell/navigation works;
- prove at least Today/Home summary and Entries/Table-First listing through
  reusable core calls;
- establish the minimum `DESIGN.md` theme/token plumbing needed to prove the
  frozen UI contract in the chosen framework;
- prove transient controller/view state stays outside reusable
  core/business modules; and
- run final Milestone 16 exit verification and record evidence.

Do not mechanically clone Streamlit. Do not migrate every page in M16.2 — it
is a vertical-slice proof of architecture and core reuse, not the full
desktop product migration.

### Milestone 16 Exit Criteria

**Status: Complete on `main`.**

- [x] Main navigation, macro interaction model, and UI/design system are
      approved. *(M16.0 complete — `DESIGN.md`)*
- [x] Desktop framework decision is documented. *(M16.1 complete on `main` —
      PR #21, `a1dc044721e9017d39842e96e0516a88a36d129f`)*
- [x] Core desktop state-management boundaries are defined. *(M16.1 complete
      on `main` — PR #21, `a1dc044721e9017d39842e96e0516a88a36d129f`)*
- [x] Existing SQLite data opens without destructive conversion. *(M16.2
      complete on `main` — proven via synthetic-database test against the
      real desktop bootstrap; see
      [Milestone 16 Closure](docs/history/MILESTONE16_CLOSURE.md))*
- [x] A minimal vertical slice proves core reuse for at least Today and
      Entries. *(M16.2 complete on `main` — PR #23,
      `2e900d243950ca93aedf5cbde5b836dc6e378f25`)*

Every item above is verified against `main`. Milestone 16 is Complete on
`main`.

---

## Milestone 17: Desktop Core Workflow Migration

Milestone 17 ports the high-frequency learning loop incrementally, built
against the frozen M16 architecture without reopening it: PySide6; the
`src/ui_desktop/` layer boundary; `AppState`/controller ownership of
transient state; SQLite/core as durable domain truth; presentation
preferences outside SQLite; the `QPalette` + QSS theme boundary; the
controller-calls-reusable-core architecture; and `DESIGN.md` as the desktop
UI authority.

### Operating Model

Milestone 17 is **one milestone**, developed on **one long-lived branch**
through **one Draft PR** — expected
`agent/m17-desktop-core-workflow-migration` — not a set of independent
lifecycle units. The former `17.1`-`17.5` sub-milestone numbering is retired
in favor of an ordered **feature migration sequence** within this single
milestone. Do not create a new branch or PR per feature; do not treat Today,
Review, Quiz, or Entries as separate milestones, sub-milestones, branches, or
PRs.

Within the one M17 branch/PR, each feature below follows the same loop:

```text
implement -> focused verification -> commit/checkpoint -> independent review -> continue
```

The final feature checkpoint (Collection Integration) is followed by one M17
parity/exit verification pass and one final review before the single PR
merges.

### Product/UI Principle

From M17 onward, functional workflow migration and that workflow's approved
`DESIGN.md` archetype implementation are **one feature-level engineering
closure**, not two separate passes:

> Port the workflow into the native desktop architecture while implementing
> that workflow's approved `DESIGN.md` archetype in the same feature.

Do not interpret M17 as "first port the Streamlit functionality into generic
Qt widgets, polish the UI later." Do not mechanically clone Streamlit page
layouts. Streamlit remains a behavioral/reference surface where useful, not
the desktop design authority; `DESIGN.md` is the UI authority and existing
reusable core behavior is the domain/learning authority. M16 proved the
architecture — M17 begins building the actual desktop product.

### Feature Migration Sequence

Recommended order, each verified before proceeding to the next:

1. Today — **complete and Human Accepted** (third presentation, from the
   replacement `DESIGN.md`; native visual acceptance PASSED 2026-08-16
   against `fdd9cc0`) (Motion Foundation and non-visual controller/handoff
   groundwork retained; two earlier presentations were rejected pre-reset)
2. Review — **complete and Human Accepted** (Immersive Focus browse/
   preparation surface; native visual acceptance PASSED 2026-08-16 against
   `38d53d2`, after one corrective patch for a functional-honesty finding)
3. Quiz — **complete and Human Accepted** (native visual acceptance
   PASSED 2026-08-16 against `311762c`; includes Feature 3B Quiz
   Presentation Choice, also complete and Human Accepted against
   `c54468e`)
4. Entries — **complete and Human Accepted** (native visual acceptance
   PASSED 2026-08-16 against
   `2cc333256d2a831c3268c150a86935276117f1c8`, after a corrective pass)
5. minimum Collection navigation/integration required by those workflows —
   **complete and Human Accepted** (native visual acceptance PASSED
   2026-08-17 against `6d8ed13c206018ece80277210abb858afd8930f9`, after a
   corrective pass for paged Card navigation and Entries selection-model
   separation)
6. Theme Completion & Cross-Screen Validation — **complete and Human
   Accepted** (native visual acceptance PASSED 2026-08-17 against
   `48a171f6aaa7e7ce3b60be945024c8712e69ec64`, after a typography
   color-role hierarchy corrective patch and a Navigation Rail
   active/normal/disabled state-rendering reliability fix)
7. M17 parity + exit verification — not started (the final M17
   checkpoint)

#### Today

Functional workflow migration = daily workload, due-review visibility, and
workflow handoffs.
Plus DESIGN.md archetype = the real Command Center implementation.

**Status: complete and Human Accepted — a third, fresh Command Center
presentation built from the replacement `DESIGN.md`; structurally
conformant, automated-conformance PASS, and native human visual
acceptance PASSED 2026-08-16 against `fdd9cc0`.** On
`agent/m17-desktop-core-workflow-migration`, the Motion / Transition
Foundation (DESIGN.md § 25, a cross-cutting extension originally
established at the initial Today checkpoint) and Today's non-visual
controller/handoff groundwork are implemented and retained. Two earlier
Today presentations were built and **both were rejected at human visual
review**; a controlled reset returned the presentation to the M16.2
placeholder before the replacement `DESIGN.md` (final design authority,
committed at `c19b686`) was supplied as the authoritative canonical
visual-reference and spatial-composition authority for M17+. The current
presentation — a shared vertical left Management Navigation Rail plus a
three-region Today Command Center (compact summary, dominant Learning
Queue, Suggested Next Actions, right Context Rail) — was derived fresh
from that authority, not from either rejected attempt. This third
presentation itself went through two visual-realization/calibration
passes (`f917ccb`, `adb6882`) and one rendering-bug fix (`fdd9cc0`, a
`QAbstractButton.sizeHint()` gap that crushed the rail's labels
illegible) after native visual acceptance FAILs, each verified against
the real running window, not the implementation trace. **Today is
Milestone 17's first accepted feature; Milestone 17 overall is not
complete.**

#### Review

Functional workflow migration = Card browse/study/preparation, historical
learning context, and the Quick Quiz / Choose Quiz Type routes. Browsing
alone must not create completion.
Plus DESIGN.md archetype = the Immersive Focus / Study Mode implementation.

**Status: complete and Human Accepted** on
`agent/m17-desktop-core-workflow-migration` against `VR-STUDY-001`
(`Review - Quiz.pdf` p4 Variant C, parent pattern P3 -- Immersive Study):
native human visual acceptance PASSED 2026-08-16 against head `38d53d2`,
after one corrective patch (`38d53d2`) for a human-acceptance
functional-honesty finding. `ReviewController` projects the current Card
roster, Entry composition, and factual completed-Quiz history entirely
through existing `src.learning_workflow`/`src.collections` reads (no SQL,
no legacy `src/review.py` scheduler calls); `ReviewView` implements the
frozen composition -- Management Rail hidden, one minimal session bar,
one dominant learning surface, a transient right Card Contents/History
drawer reusing the shared `TransitionManager`. Quick Quiz and Choose Quiz
Type both build a real, typed `QuizLaunchIntent` (`state/handoff.py`) and,
since M17 Feature 3, both perform a real launch through the shared
`QuizController` -- neither fabricates a session or completion event
itself; Review only ever hands off the typed request. **Review is
Milestone 17's second accepted feature; Milestone 17 overall is not
complete.**

#### Quiz

Functional workflow migration = session creation, answer submission,
duplicate protection, recovery, authoritative Card-scoped completion,
Card/revision history context, Mistake Book, Proficient Pool, and other
current core behavior.
Plus DESIGN.md archetype = the Immersive Focus feedback/session
implementation.

**Status: complete and Human Accepted.** Native human visual acceptance
PASSED 2026-08-16 at head `311762c`, against `VR-STUDY-001`
(`Review - Quiz.pdf` p4 Variant C, parent pattern P3 -- Immersive Study),
after a typography/spacing visual-calibration corrective pass (`0660214`)
and a UX-defect corrective pass fixing long-content clipping, Matching
wheel-scroll/selection-rebuild instability, and Review Mistakes routing
(`311762c`). `QuizController` owns active-session presentation state
only; every session/generation/grading/completion call maps to one
existing `src.quiz`/`src.template_quiz` function (`create_quiz_session`,
`create_quiz_items`/`generate_mcq_items`/`generate_matching_items`/
`generate_template_multi_rule_quiz_items`, `record_quiz_answer`,
`mark_quiz_session_completed`). Preserves all nine current Quiz families
(term/meaning self-graded and MCQ, mixed MCQ, Matching, and the three
template-aware modes), the single-global-active-session guard
(`get_active_quiz_session`, replicated the same way every Streamlit
quiz-start entry point already does), duplicate-submission protection,
and Mistake Book/Proficient Pool side effects. Plain Matching remains
whole-Collection only (normalized even if a Card-scoped intent slips
through, per the M17 Feature 3 compatibility check); template-aware
Matching remains Card-scoped, since no core function generates a
whole-Collection template-matching set. Review's Quick Quiz / Choose Quiz
Type and Today's Learning Queue "quiz" action both perform a real launch
through this one controller. `QuizView` implements the Immersive Focus
session bar, self-graded/MCQ/Matching task surfaces (Matching using
`VR-STUDY-001`'s "wider task canvas allowed" allowance), a P6 restart/
cancel confirmation, a recovery notice for a foreign active session
(never a fake resume), a compact completion summary with Return to
Today / Next Card / Review Mistakes, and a read-only post-Quiz
mistake-review state.

#### Quiz Presentation Choice (Feature 3B)

Optional second Quiz presentation, not a redesign of Feature 3.
DESIGN.md archetype = `VR-STUDY-002` Flip Card + Filmstrip
(`Review - Quiz.pdf` p5 Variant D), explicitly scoped to Quiz only
(DESIGN.md § 6.4) -- it does not propagate to Review, Today, Entries,
Collections, Analytics, or Management Mode.

**Status: complete and Human Accepted.** Native human visual acceptance
PASSED 2026-08-16 at head `c54468e`, against `VR-STUDY-002`. One durable
preference (`quiz_presentation`,
`state/preferences.py`, never `vocab.db`; default `immersive_focus`) is
set from a new minimum Settings vertical slice (Settings → Quiz → Quiz
presentation -- the P8 Settings Form pattern, DESIGN.md § 8) and resolved
once per Quiz launch by `MainWindow` before `QuizController.start()` --
no second in-session switcher. Self-graded and MCQ Quiz families
(including template-aware types, which already progress through those
same families) render inside a bordered Flip Card + a non-interactive
orientation filmstrip when selected; both presentations consume the
identical `QuizController` session/answer/completion truth -- one Quiz
engine, two presentations. Matching always falls back to the existing
wider Immersive Matching presentation regardless of the saved preference
(a genuinely simultaneous whole-set interaction, not a linear one), and
this fallback never alters the saved preference. Completion and the
read-only mistake review remain the single shared Immersive-styled
surfaces for both presentations.

#### Entries

Functional workflow migration = entry browsing, filtering, add/edit
behavior, template-aware fields, and safe editing.
Plus DESIGN.md archetype = the real Table-First implementation.

**Status: complete and Human Accepted** on
`agent/m17-desktop-core-workflow-migration` against `VR-ENTRIES-001`
(`Entries & Collections Manager.pdf` p3 Variant B, parent pattern P2):
native human visual acceptance PASSED 2026-08-16 against head
`2cc333256d2a831c3268c150a86935276117f1c8`, after one corrective pass
(`2cc3332`) for typography, toolbar layout, Scope Pane resizing, editor
scroll-safety, the "Add to Collection" menu interaction, and checkbox
selection, following a first native visual-acceptance FAIL at the initial
implementation head (`9f63813`). Replaces the M16.2 architecture-proof
placeholder. `EntriesController` owns scope/filter/selection/editor-
orchestration state only, calling existing `src.entries.search_entries`/
`create_entry_with_template`/`update_entry_with_template`/
`delete_entries`, `src.collections.update_entry_collections`/
`add_entries_to_collection`/`add_entries_to_system_collection`, and
`src.text_parser.parse_and_validate_entry_card` for every read/write --
no SQL, no duplicated template validation, canonical-field resolution,
or Card-history reconciliation logic (one small batched query,
`get_collection_names_for_entries`, was added to `src/collections.py` to
avoid an N+1 per-row query for the table's Collections column).
`EntriesView` implements the frozen composition (Management Rail ->
bounded resizable Scope Pane, split into explicit "Scope"/"Collections"
sections -> two-row toolbar (search/filters/Quick Add/Add Entry, plus a
conditional batch-action row) -> dominant Entries Table -> subordinate
horizontal Entry Detail): real native multi-row table selection
(ExtendedSelection) plus an explicit checkbox column and header
select-all affordance sharing one selection truth, restored by id across
refresh; one P5 `_EntryEditorDialog` for both Add and Edit
(template-locked on Edit, scroll-safe form body with a pinned
Save/Cancel footer); the still-live Quick Add structured-text-card flow;
and Delete/batch-collection-removal always honoring the existing
`CrossCardMoveConfirmationRequired` gate -- never a silent delete, with
confirmation copy distinguishing permanent deletion from Collection
removal. **Entries is Milestone 17's fifth accepted feature; Milestone 17
overall is not complete. The next objective is Minimum Collection
Integration.**

#### Collection Integration

Port only the minimum Collection navigation/integration required by the four
workflows above. Full Collection/Card management remains M18 scope.

**Status: complete and Human Accepted** on
`agent/m17-desktop-core-workflow-migration` against DESIGN.md § 6.8
(Class B, "inherited from the invoking A/B surface" -- explicitly not a
full Collection Manager): native human visual acceptance PASSED
2026-08-17 against head `6d8ed13c206018ece80277210abb858afd8930f9`, after
one corrective pass (`6d8ed13`) for paged/scrollable Card navigation
(a new read-only core query, `get_card_page_for_collection`, computes
per-Card Entry counts via SQL aggregation rather than loading every
Entry row, so opening a Collection with thousands of Entries only ever
reads/renders one page), the Entries selection-model separation
(`focused_id` for bottom-detail inspection vs `checked_ids` for batch
actions, each with a distinct visual treatment), and a direct per-row
Star toggle in Entries (reusing the existing Starred system-Collection
core, including the `CrossCardMoveConfirmationRequired` safety gate on
unstar), following a first native visual-acceptance FAIL at the initial
implementation head (`009645a`). A real `Workspace.COLLECTIONS` Management Mode
workspace is now reachable through the previously-disabled `Collections`
rail destination. `CollectionsController` is a read-only projection over
`src.collections.get_collections`/`get_collection_by_id`/
`get_card_groups_for_collection` -- no SQL, no mutation, no second Card
model -- keeping normal Collections and system practice pools (Starred/
Mistake Book/Proficient Pool) as two separate lists throughout, the same
separation `EntriesController`/`_ScopePane` already established for the
Entries Scope Pane. `CollectionsView` implements Management Rail -> left
selector pane ("Collections"/"Practice Pools" sections) -> right
read-only detail (factual metadata + compact Card list for a normal
Collection, or a pool summary) with "Open Entries" / "Open in Study"
handoff actions, its visual traits inherited from Entries' Scope Pane +
detail vocabulary rather than a new visual language. Two typed handoffs
in `state/handoff.py` -- `EntriesScopeIntent` (Entries' own existing
`collection:<id>`/`system:<type>` scope key) and `StudyTargetIntent`
(`collection_id`, `card_number`) -- are each consumed exactly once by
`MainWindow`: `_open_entries_with_scope` hands the scope straight to
`EntriesController.set_scope()`; `_open_review_at_card` calls the
existing `ReviewController.open_card(...)` and fails honestly (no
navigation, no fallback to `open_default()`) if the Card is gone. Today's
"Collections Needing Attention" pool rows are now actionable, completing
the same `EntriesScopeIntent` handoff. This checkpoint also fixed a
real pre-existing latent bug: `_render_workspace(REVIEW)` was
unconditionally calling `ReviewController.open_default()` on every
render, which would have silently overwritten any specific
Collection/Card handoff the instant it navigated -- `open_default()` now
only runs from the generic entry points (`_enter_review`,
`_on_quiz_next_card`), since `ReviewView` already re-renders reactively
from `ReviewController.state_changed`. **Minimum Collection Integration
is Milestone 17's sixth accepted feature; Milestone 17 overall is not
complete. The next objective is Theme Completion & Cross-Screen
Validation.**

#### Theme Completion & Cross-Screen Validation

Close the Appearance axis (System/Light/Dark, Calm Blue) as a complete,
live-switchable, OS-aware product capability across the real M17 desktop
product, plus a typography color-hierarchy audit and Navigation Rail
state-rendering reliability fix. Three deferred Accent families
(Sage/Teal, Indigo/Violet, Warm Neutral), the Quick Theme Control
popover, and any M18 Settings expansion remain out of scope.

**Status: complete and Human Accepted** on
`agent/m17-desktop-core-workflow-migration` against the canonical Theme
Architecture Visual Validation board: native human visual acceptance
PASSED 2026-08-17 against head
`48a171f6aaa7e7ce3b60be945024c8712e69ec64`, after two corrective passes.
`System` now resolves through a live OS Light/Dark read (Qt's
`QStyleHints.colorScheme()`, `system_appearance.py`) with an explicit
logged fallback, and reacts to a live OS appearance change while
`System` remains selected (`ThemeManager.watch_system_appearance()`,
wired to Qt's own `colorSchemeChanged` signal) without ever overriding
an explicit Light/Dark choice. Settings gained a real Appearance control
that persists immediately and live-applies through the single existing
`ThemeManager.apply()` call site. A contrast re-audit against the
surfaces tokens are actually deployed on (not just their best-case
pairing) found and fixed two real defects the original M16.2 audit had
missed: Light `text-muted` failed WCAG AA against `surface-secondary`/
`app-background`, and the Entries Star column's fixed gold both
under-contrasted in Light and hue-collided with `warning` -- it is now a
theme-aware `star`/`on-star` semantic token. The first corrective pass
(typography color-role hierarchy) audited every `color:` declaration
across Today/Entries/Collections/Settings/Review/Quiz/Utility against the
four-level text-role hierarchy (primary/secondary/muted/disabled) and
fixed four confirmed, empirically-verified defects (a disabled Quiz
answer field and dialog combo boxes not visually reading as disabled, a
Settings row label colliding in visual weight with its own value, and an
unstyled Today attention-row label). That pass also discovered --
investigated, but correctly left out of its own narrow scope -- that
`QPushButton:checked/:disabled/:hover` -> child `QLabel` descendant-
pseudo-state QSS selectors are not reliably re-evaluated by Qt's style
engine (confirmed on both the offscreen and real native "windows" Qt
platforms, through the real `app.py` bootstrap path); a second corrective
pass replaced that mechanism in the Navigation Rail with one actually
driven reliably -- a Qt dynamic property (`navActive`) set directly on
the mark/label themselves for the active-vs-normal distinction (paired
with an explicit `unpolish()`/`polish()` repaint), and static Python-
decided object names for the (runtime-constant) disabled destinations --
verified end to end through the real production bootstrap path, not just
generated QSS text. **Theme Completion & Cross-Screen Validation is
Milestone 17's seventh accepted feature; Milestone 17 overall is not
complete. The next and final objective is M17 Parity + Exit
Verification.**

#### M17 Parity + Exit Verification

For each migrated workflow:

- verify existing databases;
- compare persisted state before/after equivalent actions;
- exercise restart and repeated-action behavior;
- run relevant automated tests; and
- record known parity gaps.

### Verification Model

Avoid ritual repetition. At each feature checkpoint, normally run focused
tests for that feature, relevant existing regression tests, an architecture
audit, and targeted persistence/parity checks where the feature mutates
data. Run the full repository suite when risk justifies it and at meaningful
integration checkpoints, not mechanically after every change. At final M17
exit, perform complete verification: full repository suite, architecture
audit, equivalent-action persistence/parity verification, restart/repeated-
action behavior, existing-database safety, manual native desktop acceptance,
`DESIGN.md` adherence, and lifecycle documentation reconciliation. Testing
must remain risk-based, not mechanically minimized.

### Frozen Semantic Boundaries

M17 must not reopen or silently change:

- reviewing/browsing a Card does not complete learning;
- completed Card-scoped Quiz remains the authoritative Card completion
  event;
- Again/Hard/Good/Easy legacy SRS semantics are not revived;
- Quiz history and Review exposure remain distinct evidence;
- stable Card / Card-revision semantics remain intact;
- existing SQLite user databases remain protected assets;
- desktop UI calls reusable core; no duplicated SQL/business rules;
- no raw SQL in desktop views/controllers;
- core modules do not import PySide6; and
- no new global mastery score or opaque learner grade — analytics, import,
  audio, and learning semantics are not silently changed by M17.

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
