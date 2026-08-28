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

**Milestones 19 and 20 are complete and v1.0.0 is released. Milestone 21 /
v1.1.0 implementation, Phase Patch, and Phase F release verification are
complete on merged `main`. The next lifecycle action is publication of
v1.1.0 from that merged source, subject to separate operator authorization.**

This one-step-ahead merge state does not claim that the `v1.1.0` tag or GitHub
Release already exists. See § Milestone 21 and `PROJECT_STATUS.md` for the
current release gate and evidence summary; older milestone sections remain the
historical record of how the v1.0 baseline was reached.

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

Milestone 17 — Desktop Core Workflow Migration was developed on the
single long-lived branch `agent/m17-desktop-core-workflow-migration` and
is now **complete on `main`** (merged via PR #25). The **Motion /
Transition Foundation** and Today's non-visual
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
active/normal/disabled state-rendering reliability fix). **M17 Parity +
Exit Verification — the final M17 checkpoint: the three frozen final
corrective items (Custom Entry Type, Entries sorting, Entries result
count) plus integrated cross-feature regression proof that all seven
prior checkpoints work together as one coherent product — is also
complete and Human Accepted** (native Human Exit PASS recorded
2026-08-17 against final accepted head
`d232717b6b225e7c798c510ae8e87ce87fe5d8c8`, after one corrective fix for
a parallel Entries-sorting mechanism the Sort by combo's own review
caught: `QTableView.setSortingEnabled(True)` had left native header-click
sorting wired directly to `QSortFilterProxyModel`'s own independent sort
state, which could silently override the new SQL-level "Sort by" order;
removed, with the proxy forced to `sort(-1)` so it stays a pure
index-mapping adapter). **Milestone 17 — Desktop Core Workflow Migration
is now COMPLETE.** See § Milestone 17 below for the full operating
model, the reset history, and the per-feature acceptance record.

**Milestone 18 — Desktop Management and Major Feature Completion is now
Complete on `main`** (merged via PR #29 at
`9dae05c49caec8f2a33fdaf74d0a1f3fd1db43bc`). It was developed on the single long-lived branch
`agent/m18-desktop-management-major-feature-completion` through Draft PR
#29, per the M18 Autonomous Execution Contract. **Human Gate 1 —
Management Grammar Calibration (Collection Manager + Card Organization,
Template Manager + Template Editor) is complete and Human Accepted**:
native visual acceptance PASSED 2026-08-17 against head
`283ab6f9298a7f64d2d311ffc11c01b2a186d2cf`, after an initial FAIL and two
corrective passes (Light Mode contrast root-cause fix across every new
M18 control, a discoverable "Open Template" affordance replacing an
undocumented double-click gesture, and a Templates-table
selection-by-id integrity fix). **Phase C — Remaining Management/Data
Workflows + Linked Source is also complete**: Review Calendar / Card
History, Settings storage information, Data Tools (Import/Export,
Template Definition CSV import/export, Backup / Restore Preview), and
the Linked Source desktop workflow (the feature's first UI; M13 closed
the reusable core only). Every checkpoint's own independent review found
and fixed real findings before the next one began. See § Milestone 18
below for the operating model, per-checkpoint acceptance record, and the
Streamlit disposition table. **Phase D — Analytics is also complete**:
the Analytics Landing workspace ("Learning Brief First", DESIGN.md § 6.5
CANONICAL `VR-ANALYTICS-001`) and the Full Findings drill-down (§ 6.6
`VR-ANALYTICS-002`), built entirely on the M14 core with no invented
thresholds or scores. This flips the last disabled Navigation Rail
placeholder -- every destination in the approved product IA (DESIGN.md
§ 4.1) now has a real workspace. Independent review found and fixed four
real findings before the first Human Gate 2 attempt. **Human Gate 2 --
Analytics Product Acceptance initially FAILed**: on a real production
database, opening Analytics made the app "Not Responding" -- root cause
was `get_scope_coverage_findings` reloading and recomputing the *entire*
database's evidence profiles once per Collection and again once per
Card, synchronously on the Qt UI thread (confirmed by benchmark: 137s vs
0.7s after the fix, on a synthetic 2000-entry/30,000-event database). A
corrective pass introduced `EvidenceProfileCache` (compute the
whole-database evidence snapshot once per Analytics refresh, reused
everywhere instead of reloaded per scope) plus a background `QThread`
with staged progress/error UI and stale-result guarding as
defense-in-depth. Independent review of that corrective pass found and
fixed three more real findings (a cross-thread signal race from
lambda-wrapped callbacks that PySide6 could not correctly queue, a
narrow-filter cache regression reintroducing whole-database cost on an
unrelated `src.statistics` call path, and a QThread shutdown-safety gap);
a fourth defect (a test-harness segfault from not waiting for the
background thread to fully stop) was self-caught during re-verification.
Two further HG2-corrective passes followed real native re-acceptance
testing (`9439be7` Appearance/Quiz combo min-width bump, superseded by
`8f57295`'s root-cause fix wrapping the Settings page in a native
vertical `QScrollArea`). **Human Gate 2 -- Analytics Product Acceptance
is Human Accepted**: native visual acceptance PASSED against final
accepted head `8f572959f0239b3b866cb8af936c8c84e8f53170`; see §
Milestone 18 below for the full checkpoint record.

**Phase E -- Card Audio Export is also complete**: the desktop Card
Audio Export workflow (a fourth Data Tools hub action, DESIGN.md § 7.4
"Audio Export configuration: B, `VR-UTILITY-001`"), built entirely on
the M15 `src.audio_export`/`src.audio_composition`/`src.tts_providers`
core with voice configuration deliberately read-only (M15 froze
provider/language routing) and Card-atomic cancellation added to
`execute_audio_export_plan` as a new `should_cancel` parameter. An
independent self-review pass before checkpointing found and fixed a
real staleness defect in the desktop controller. Phase F -- Integrated
M18 Exit Verification then completed with no known blocking defect, and
the milestone was called an EXIT CANDIDATE. **Human Gate 3 subsequently
FAILed** (Card Audio Export's Plan always showed "0 of X Cards ready"
with no visible reason -- root-caused to this machine having no
`VOCAB_APP_SHARED_TTS_DIR` shared TTS runtime configured, not a defect
in the Plan-building logic, which was proven correct against all 715
real Cards in the production database). A corrective fixed the
diagnostic UX (live per-language preflight status, per-Card plan
reasons). The retained M15 shared TTS runtime was then rediscovered on
the machine, audited read-only, bound temporarily via
`VOCAB_APP_SHARED_TTS_DIR`, and used to verify a real end-to-end Card
Audio Export against the production database (2 of 2 Cards ready, 2 of
2 exported to valid canonical WAV). The operator then verified the real
native happy path independently and recorded **Human Gate 3 PASS —
Human Accepted**. All three M18 Human Gates are Human Accepted; the
operator authorized the merge, and **M18 merged to `main` via PR #29 at
`9dae05c49caec8f2a33fdaf74d0a1f3fd1db43bc`**. See § Milestone 18 below
for the full checkpoint record.

**The desktop Feature Freeze began with Milestone 19** — the
intended desktop feature scope had been implemented and verified
through M17/M18. **Milestone 19 — Desktop Product Hardening is Complete
on `main`**, Human Accepted 2026-08-18 and merged via PR #30 at
`2ad211711d96583b6fffdb65de912fa672502bc8` from the single long-lived
branch `agent/m19-desktop-product-hardening` (baseline `9dae05c`); see
§ Milestone 19 below for the full record. Milestone 20 subsequently completed
with the v1.0.0 release; Milestone 21 is the current post-v1.0 increment.

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
through **one PR** —
`agent/m17-desktop-core-workflow-migration`, PR #25 (Draft throughout
development, merged 2026-08-17) — not a set of independent lifecycle
units. The former `17.1`-`17.5` sub-milestone numbering is retired
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
7. M17 parity + exit verification — **complete and Human Accepted**
   (native Human Exit PASS recorded 2026-08-17 against
   `d232717b6b225e7c798c510ae8e87ce87fe5d8c8`, after a corrective fix for
   a parallel Entries-sorting mechanism; the final M17 checkpoint)

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

**Status: complete and Human Accepted.** The final M17 checkpoint closed
three frozen final corrective items and verified the seven prior
accepted checkpoints as one integrated product, not isolated screens.

- **Custom Entry Type** (Add/Edit Entry): a "Custom..." option on the
  Entry Type field opens a native `QInputDialog` prompt; a confirmed
  non-empty value saves through the exact same `entry_type` field every
  predefined value already uses (`src/entries.py` already stored/
  validated it as free text, not an enum/foreign key -- no core or
  schema change needed). Cancel or an empty/whitespace-only confirm
  leaves the existing value unchanged.
- **Entries sorting**: `search_entries()` gained an allowlisted
  `sort_by`/`sort_direction` capability (Term/Created/Updated) fulfilling
  the toolbar spec this section's Entries subsection had already
  documented but never implemented, rather than a second sort
  implementation; a compact "Sort by" control composes with scope/
  search/filter, preserving focused/checked state across a resort.
- **Entries result count**: a subordinate "N entries" label reusing the
  count `EntriesController.refresh()` already computes.
- **Integrated workflow parity** verified and locked into regression
  tests: Today/Collections -> Entries exact scope; Collection/Card ->
  exact Review Card with no silent fallback; Review -> Quiz context
  preservation; Study exit -> correct Management workspace and
  Navigation Rail active state; Light/Dark/System theme switching never
  mutates Entry data or resets Entries presentation state; repeated
  Card navigation never duplicates learning evidence.

One corrective fix followed initial implementation: the Entries table's
pre-existing `QTableView.setSortingEnabled(True)` (M17 Feature 4) wired
native header-click sorting directly to `QSortFilterProxyModel`'s own
independent sort state -- a parallel sorting mechanism a real header
click could use to silently override the new "Sort by" SQL-level order
(confirmed empirically the proxy defaulted to `sortColumn() == 0`, not
`-1`, the instant `setSortingEnabled(True)` ran, before any click).
Removed; the proxy is forced to `sort(-1)` and remains a pure
`QTableView`<->source-model index-mapping adapter, with "Sort by" as the
one real sort entry point. New regression tests check the *visible*
proxy/table order directly (not only `EntriesController.model.rows()`,
the source model, which is exactly what let the original defect through
a fully-green suite) -- confirmed to fail against the pre-fix code and
pass against the fix.

**Native Human Exit PASS recorded 2026-08-17 against final accepted head
`d232717b6b225e7c798c510ae8e87ce87fe5d8c8`.** 592/592 local tests
passing, architecture audit clean; no remote CI is configured in this
repository. **Milestone 17 — Desktop Core Workflow Migration is
COMPLETE.**

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

**Status: Complete on `main`.** Native Human Exit PASS recorded
2026-08-17 against final accepted head
`d232717b6b225e7c798c510ae8e87ce87fe5d8c8`.

- [x] The desktop application supports the primary daily learning loop.
      *(Today, Review, Quiz, and the Collections->Study handoff all
      complete and Human Accepted; verified as connected journeys, not
      isolated screens, at M17 Parity + Exit Verification.)*
- [x] Today, Review, Quiz, and Entries are usable without Streamlit.
      *(All four complete and Human Accepted at native visual
      acceptance; Entries additionally gained Custom Entry Type,
      sorting, and a result count at the final checkpoint.)*
- [x] No known parity defect threatens persisted user data. *(Data/
      learning invariants verified: theme/preferences stay outside
      `vocab.db`; sort/filter/result-count are presentation/query state
      only; repeated navigation does not duplicate learning evidence;
      no schema change was introduced by M17.)*
- [x] Streamlit may remain as a legacy reference/fallback but is no
      longer the primary development target. *(Unchanged and still
      true; no Streamlit code was removed during M17.)*

---

## Milestone 18: Desktop Management and Major Feature Completion

Milestone 18 completes desktop parity for management/data workflows and
finishes the desktop-facing parts of the three new major capabilities.

### Operating Model

**Status: Complete on `main`** (merged via PR #29 at
`9dae05c49caec8f2a33fdaf74d0a1f3fd1db43bc` from final accepted head
`0ff85509f0cdb7248d7970b8af66c1da6a94c301`). Milestone 18 was developed under the M18
Autonomous Execution Contract as one milestone, one long-lived branch
(`agent/m18-desktop-management-major-feature-completion`), one Draft PR
(#29, Draft throughout development), and an ordered checkpoint sequence
with three Human Gates, per that contract's operating model.

**Phase B — Representative Management Grammar:**

- Collection Manager + Card Organization (`e78764e`): create/rename/
  edit/delete Collection, rename Card, remove/reposition Entries within a
  Collection. Every write calls the same `src.collections` functions the
  Streamlit Collections page already uses.
- Template Manager + Template Editor (`0f5ae60`, corrected at `781d2a4`):
  a new Templates workspace/rail destination; create/edit/delete
  Template and Field, with the existing in-use safety gates
  (`template_has_entries`, `template_field_has_values`) enforced as
  outright-disabled actions rather than mere warnings. Every write calls
  the same `src.entry_templates` functions the Streamlit Templates page
  already uses.

**Human Gate 1 — Management Grammar Calibration: complete and Human
Accepted.** Initial native visual acceptance at `781d2a4` **FAILed**:
Light Mode rendered the new Collection/Template controls at
effectively-invisible contrast (every control this checkpoint added had
no explicit QSS coverage, the same defect class the M16.2 closure
documented for Today/Entries navigation actions), and existing Custom
Templates had no discoverable entry point besides an undocumented
double-click gesture. Two corrective passes followed:

1. `5b3757c` — explicit primary/secondary/destructive QSS for every new
   M18 control (reusing the existing `QPushButton[destructive="true"]`
   property selector for delete/remove actions rather than duplicating
   per-button rules), a missing `QDialog QSpinBox` rule, and a new
   discoverable "Open Template" toolbar action (enabled only when a row
   is selected) sharing the same code path double-click already used.
2. `283ab6f` — independent review of pass 1 found the Templates table's
   row-index-based selection could silently drift to the wrong Template
   after a reordering refresh (e.g. renaming the selected Template while
   its editor was still open); selection now follows the Template's
   stable id.

**Native human visual acceptance PASSED 2026-08-17 against final
accepted head `283ab6f9298a7f64d2d311ffc11c01b2a186d2cf`.** Automated
evidence at that head: focused Collection Manager/Template Manager/
corrective tests all green (16/16, 15/15, 11/11), full repository suite
634/634, architecture audit 77 files / 0 violations, two independent
code reviews each with one real finding, both fixed and
regression-tested.

**Phase C — Remaining Management/Data Workflows + Linked Source: complete.**
Six checkpoints, each following the same implement -> focused verify ->
commit -> independent review -> repair -> continue loop, every one of
which found and fixed at least one real defect before the next
checkpoint began:

- **C1 Review Calendar / Card History** (`c141dcc`) — read-only P7
  Evidence Browser: a chronological table of completed Card-scoped Quiz
  sessions (the authoritative learning-completion evidence) with a
  range-preset filter, and selecting one shows that Card's full history
  plus its legacy Review compatibility records, kept visibly separate.
  Corrective pass `604a443` fixed a stale-selection bug (a previously
  selected row could keep showing old detail after a range change).
- **C2 Settings storage information** (`3be1da7`) — a read-only Storage
  section (database/backup/audio-cache paths, path source) added to the
  existing Appearance/Quiz Settings Form, a thin passthrough to
  `src.app_config.get_app_storage_summary()`.
- **C3 Data Tools hub + Import/Export** (`541870d`) — General/
  Template-Based/Collection Entry import (Upload -> Validate -> Preview
  -> Confirm -> Import, DESIGN.md § 12.3) and Export (All entries /
  Collection / summary, CSV/XLSX), reusing `src.import_export` entirely;
  this repository's first `QFileDialog` usage. Corrective pass `08012b1`
  fixed four issues an independent review found, most seriously a
  confirmation checkbox that never reset, which could have re-armed
  Confirm Import against a new file/mode with no fresh per-batch
  consent.
- **C4 Template Definition CSV import/export** (`511d644`) — portable
  Template *field structure* (distinct from Entry import), reusing
  `src.template_definitions` entirely.
- **C5 Backup / Restore Preview** (`103b211`) — local backup generation
  (.sqlite3 file copy, full .xlsx workbook) and read-only backup
  inspection; Restore is intentionally preview-only throughout, since no
  core function performs an actual database restore. Corrective pass
  `e87d06c` guarded a dialog-constructor call an independent review
  found could crash on a locked/unreadable database.
- **C6 Linked Source** (`549dfb6`) — the feature's first UI (M13 closed
  the reusable core only): link a Collection to a local CSV/XLSX
  append-only source, refresh it, and recover from a missing/unreadable
  source via Unlink (metadata only) + a fresh link, reusing
  `src.linked_sources` entirely; no desktop-only "relink in place"
  shortcut was invented. Corrective pass `dc5401f` fixed three issues an
  independent review found: changing the staged import mode/sheet after
  a preview didn't invalidate it (letting a stale Confirm write Entries
  under an unreviewed mode), the mode combo didn't resync after Unlink,
  and a failed Unlink produced no visible feedback.

Full repository suite green (677/677 at the C3 checkpoint; re-verified
at 723/723 after C6's corrective pass, reflecting the tests added across
C4-C6) and architecture audit clean (83 files, 0 violations) throughout.

**Phase D — Analytics: complete.** One checkpoint, same implement ->
verify -> commit -> independent review -> repair loop as Phase C:

- **D1 Analytics Landing + Full Findings** (`c8e4f40`, corrected at
  `9b2b2c1`) — the Analytics Landing workspace (DESIGN.md § 6.5
  CANONICAL `VR-ANALYTICS-001`, "Learning Brief First"): an
  interpretation-first Learning Brief built directly on
  `src.insights.build_learning_brief`, an "all Entries" / per-Collection
  scope switch, and a Coverage panel that only appears for a selected
  Collection (there is no core-defined global coverage metric, so "all"
  scope intentionally omits it rather than inventing one). The Full
  Findings drill-down (§ 6.6 `VR-ANALYTICS-002`) is a modal table over
  every Finding `src.insights.get_all_findings` returns, with a "Show
  every current Entry (including no current Finding)" toggle. Both
  finish the M18-scoped statistics_page.py/dashboard_page.py disposition
  (DESIGN.md § 7.7: integrate into Analytics/Today, not recreate for
  parity) and flip "analytics" -- the last disabled Navigation Rail
  placeholder -- to enabled, so every destination in the approved
  product IA (DESIGN.md § 4.1) now has a real workspace. No SQL, invented
  score, or mutation was added: the controller only calls existing
  `src.insights`/`src.analytics` reads. Independent review of the first
  pass found four issues, all fixed in `9b2b2c1`: a "Suggested: None"
  label misrepresenting findings with no suggested action as if one
  existed, bare "Collection"/"Template" scope labels losing the actual
  Collection/Template identity, a documented-but-unwired "show every
  current Entry" checkbox, and a redundant double data-reload on every
  Analytics navigation.

Full repository suite green (744/744 at the pre-corrective D1 checkpoint;
751/751 re-verified at final head `9b2b2c1937b71d5b7932077f8f10f6f3f4266ea1`
after its corrective pass) and architecture audit clean throughout. See the Draft PR #29 body for the complete Streamlit
disposition table -- every M18-scoped legacy surface is now migrated,
explicitly deprecated, or documented as out of scope.

**Human Gate 2 corrective: Analytics performance/responsiveness
(`50597e7`).** Native human testing found that opening Analytics on a
real production-sized database made the app "Not Responding" --
**Human Gate 2 FAILed.** Investigated with profiling rather than
guessing: benchmarked the exact code path against a synthetic
2000-entry/30,000-event database and confirmed `get_all_findings`
("All Entries" scope) took **137.15s**. Root cause:
`get_scope_coverage_findings` looped over every Collection and, within
each, every Card, calling functions that each independently reloaded
and recomputed the *entire* database's evidence profiles from scratch
(`_load_current_entry_metadata` + `load_eligible_evidence_events` + an
O(entries) personal-baseline pass) -- all synchronously on the Qt UI
thread. Root-cause fix: a new `EvidenceProfileCache`
(`src/analytics.py`) computes that whole-database snapshot exactly
*once* per Analytics pass and is threaded through every Collection/Card/
Template read that used to reload it independently; re-benchmarked at
**0.71s** (~193x), with `get_entry_evidence_profiles`'s no-cache default
path deliberately kept at its original filter-then-compute shape so
narrow single-call lookups elsewhere in the codebase see no regression.
As defense-in-depth (per this corrective's own added requirement: "if
Analytics legitimately requires noticeable computation time even after
the performance work, do not leave the user looking at a frozen
workspace"), the M14 read also moved off the Qt UI thread onto a
background `QThread`, with a monotonic generation token guarding against
a stale superseded load overwriting a newer one, and `AnalyticsView`
gained a staged/determinate `QProgressBar` + status label loading state
plus an actionable error state (Retry), built from existing theme/accent
tokens (DESIGN.md § 12.4/§ 23) -- never a fabricated percentage.
Independent review of this corrective pass found and fixed three more
real defects: worker signals connected to lambdas rather than bound
methods, which PySide6 cannot detect as cross-thread and so ran
unsynchronized on the worker thread instead of being queued onto the Qt
UI thread (undermining the stale-result guard itself); the cache
refactor's first draft unconditionally built the whole-database cache
even for callers that never asked for one (e.g. `src.statistics`'s
per-Collection lookups), reintroducing the same class of unnecessary
global recomputation on a different call path; and no shutdown hook
meant closing the app mid-load could destroy a still-running `QThread`
(fatal in Qt). A fourth defect -- a segfault in the test suite itself
from not waiting for the background thread to fully stop before
`tearDown` deleted the database -- was self-caught during
re-verification and fixed in the test helper (now reused via the
controller's own `shutdown()`). Full repository suite re-verified green
at final head `50597e7` (762 tests; the same 5 pre-existing failures in
`test_m18_review_calendar.py` -- confirmed present on the clean
pre-corrective HEAD, a relative-date-window test-data flake unrelated to
Analytics -- remain the only non-passing tests, out of scope for this
corrective) and architecture audit clean (85 files, 0 violations).

**Human Gate 2 correctives (`9439be7`, `8f57295`).** Native
re-acceptance testing on the `50597e7` head found two further real
defects, each fixed before re-presenting the gate: `9439be7` raised the
Appearance/Quiz combo boxes' QSS `min-width` (200px -> 300px) after
confirming by width-sweep that Qt's horizontal squeeze compressed their
selected values to unreadable at a normal window size; `8f57295`
superseded that per-control workaround with the actual root-cause fix
(the Settings page had no vertical `QScrollArea`, so it could never
grow taller than the window and would re-create the same squeeze for
any future content growth) by wrapping the page in a native vertical
`QScrollArea` (horizontal scrolling explicitly disabled, min-width
reverted) and adding 3 focused regression tests (81/81 Settings/theme
tests, clean architecture audit).

**Human Gate 2 -- Analytics Product Acceptance is Human Accepted.**
Native visual acceptance PASSED against final accepted head
`8f572959f0239b3b866cb8af936c8c84e8f53170`.

**Phase E -- Card Audio Export (`AudioExportController` +
`AudioExportDialog`).** A fourth Data Tools hub action (DESIGN.md §
7.4 "Audio Export configuration: B, `VR-UTILITY-001`"; § 12.5 "For Card
Audio Export preserve M15.3"), built entirely on the existing
`src.audio_export`/`src.audio_composition`/`src.tts_providers` M15
core -- no SQL, no second export engine. Scope model: Single Card /
Selected Cards / Whole Collection, matching `src.audio_export`'s
existing `SCOPE_*` constants. Voice configuration is deliberately
READ-ONLY: M15 froze provider/language routing
(`src.tts_providers.FROZEN_PROVIDER_SPECS`) and the M18 contract § 5
forbids reopening it without an actual blocker -- the workspace
confirms the frozen per-language voice assignment rather than
presenting a picker. Repetition mode/count and overwrite/skip conflict
handling are the genuinely configurable half of `CompositionConfig` the
roadmap names.

Long-running work reuses Analytics' Human Gate 2 corrective shape
exactly: a background `QThread`, a monotonic `_generation` guard
discarding a superseded run's stale result, and worker signals
connected to real bound methods (never a lambda) for correct
cross-thread queuing. Cancellation is Card-atomic -- added to
`execute_audio_export_plan` as a new `should_cancel` parameter and
`cancelled` status: a Card already published stays published, every
remaining Card comes back `cancelled`, and `build_retry_plan` treats
`cancelled` the same as `failed`/`unresolved`, a normal retry target.

An independent self-review pass before checkpointing (per the M18
contract § 11) found and fixed a real defect: several controller
setters (repetition mode/count, conflict policy, destination folder,
Card selection) invalidated the built Plan but never emitted
`state_changed`, so the Start button's stale enabled state and the
consent checkbox's stale overwrite-warning text could survive a config
change that had already invalidated them -- fixed by emitting
`state_changed` from every one of them and resetting consent on every
reload, the same "confirmation checkbox must require fresh
acknowledgment for every state change" discipline Data Tools' Import
Dialog corrective (`08012b1`) already established.

Full-suite verification surfaced a second, unrelated pre-existing
defect: `tests/test_m18_settings_storage.py`'s Human Gate 2 scroll-area
regression test measured a QComboBox's "natural width" via `sizeHint()`
before the widget was ever shown, intermittently under-reporting once
enough other GUI tests ran earlier in the same `unittest discover`
process -- confirmed deterministic under Phase E's larger suite, not a
real Settings layout regression (the sibling scrollbar-orientation test
in the same file passed throughout). Fixed by measuring post-show/
post-layout instead of pre-show.

Verified: 26/26 new focused tests (15 core `src.audio_export` tests
including 2 new cancellation/retry-of-cancelled cases, 11 new desktop
controller/dialog/QSS-structural-coverage tests), full repository suite
green (778/778), clean architecture audit (87 files, 0 violations). This
finishes the M18-scoped audio-export Streamlit disposition: no legacy
Streamlit audio-export UI existed to migrate or retire (M15 closed only
the reusable core), so this is the feature's first UI, the same
position Linked Source was in at Phase C6.

Milestone 18 management/data workflows, Phase D Analytics, and Phase E
Card Audio Export are complete, and Human Gate 2 has passed. The
remaining scope before Feature Freeze is Phase F -- Integrated M18 Exit
Verification, closing toward Human Gate 3.

**Phase F -- Integrated M18 Exit Verification (head `aa0ad72`).**
Automated/engineering exit verification, per the M18 contract § 10
Level C:

- full repository suite green, 778/778, at head `aa0ad72`;
- architecture audit clean, 87 files, 0 violations;
- no schema/migration change in Phase E (`src/migrations.py` untouched;
  `CURRENT_SCHEMA_VERSION`/`APP_DATA_VERSION` unchanged) -- existing
  compatible SQLite databases remain a protected asset;
- persistence parity: `execute_audio_export_plan` provably does not
  mutate learning state or schema (`test_export_does_not_mutate_learning_state_or_schema`,
  part of the 15/15 core `src.audio_export` suite);
- restart/repeated-action evidence: `MainWindow` constructed and closed
  3x, `AudioExportDialog` opened/closed 5x, and every `Workspace` (Today,
  Entries, Collections, Templates, Review Calendar, Data Tools,
  Analytics, Review, Quiz, Settings) cycled once through a real
  `MainWindow` against a synthetic database with 0 errors -- an
  integration-level check beyond the unit suite, exercising the same
  navigation/controller wiring a real session uses;
- long-running/cancellation/error-path evidence: Card Audio Export's
  Card-atomic cancellation, retry-of-cancelled, and honest
  provider-unavailable (`unresolved`) paths are exercised end-to-end
  through the real `QThread` worker, not just the synchronous core
  (`tests/test_m18_audio_export.py`'s `AudioExportControllerRunTests`);
- Streamlit disposition audit: every M18-scoped legacy surface is
  migrated, integrated/retired, explicitly deprecated, or documented out
  of scope (Draft PR #29's disposition table, now including Card Audio
  Export);
- `DESIGN.md` adherence: every M18 surface built against its named
  Coverage Matrix authority (§ 7.2-7.4) and Design Derivation Record
  discipline (§ 9) where no CANONICAL pixel mockup exists;
- lifecycle-document reconciliation: `ROADMAP.md`/`PROJECT_STATUS.md`
  both current as of head `aa0ad72`; `docs/migration/DESKTOP_MIGRATION_PLAN.md`'s
  § "Card Audio Export" requirements (Card/Collection selection, batch
  selection, voice settings, repetition settings, output folder,
  progress, cancellation, error recovery, overwrite handling, one file
  per Card) are all satisfied by the implemented workflow;
- privacy/repository-safety: clean `git status`, diff reviewed for
  secrets/local paths/personal data before every commit and push (per
  `AGENTS.md`'s GitHub Privacy Rule).

No blocking defect was known at head `df78286`, and the milestone was
called an EXIT CANDIDATE with Human Gate 3 READY.

**Human Gate 3 -- Final M18 Native Acceptance FAILed.** Native
acceptance testing against head `df78286` found a blocking defect in
Card Audio Export: after configuring an export and building a Plan,
every Card consistently showed unresolved ("0 of X Cards ready"), Start
Export stayed disabled, and nothing explained why.

Investigated with real production data rather than guessing:
`VOCAB_APP_SHARED_TTS_DIR` is unset in this desktop process's
environment (confirmed at User/Machine/Process scope via .NET
`Environment.GetEnvironmentVariable`, all empty), so
`ProviderRegistry.from_environment()` falls back to an
all-languages-unavailable registry; no shared-runtime folder matching
`build_shared_runtime_registry()`'s expected layout is discoverable
anywhere on this machine (only the raw Kokoro-82M Hugging Face model
cache and a populated `audio-cache` from an earlier session exist --
evidence real synthesis worked once, but that runtime is not present
now). Swept all 715 active Cards across every real Collection in the
production database with a fake-but-realistic *available* provider:
100% become `ready` with zero issues, conclusively ruling out
required-field/speech-role validation as a contributing cause -- the
entire blocker is provider availability, an environment prerequisite,
not a defect in the Plan-building logic.

**Corrective:** rather than enabling Start Export unconditionally,
fixed the actual reported problem -- no actionable reason was visible.
`AudioExportController.voice_assignment_rows()` now reports a live
per-language preflight (not just static identity); the Voice Assignment
panel gained a Status column; `src/tts_providers.py` gained a distinct
`shared_tts_dir_not_configured` code/detail differentiating "no env var
at all" from "runtime configured but broken", and
`CommandSpeechProvider.preflight()`'s missing-asset message now names
the actual missing path(s) (detail text only -- provider/language
routing semantics are not reopened); the dialog gained a Plan Preview
table showing every Card's own concrete, deduplicated reason instead of
only the aggregate count, with partial-batch honesty preserved and
tested (a ready Card shows no reason, a not-ready Card shows its own
real issue, never silently treated as ready). 4 new focused regression
tests, full repository suite green (782/782), architecture audit clean,
independently self-reviewed before checkpointing.

**Per explicit operator direction, this diagnostic corrective is
sufficient for this defect; building a new shared TTS runtime is out of
M18 scope.** The retained M15 shared TTS runtime was subsequently
rediscovered on the machine, audited read-only against
`build_shared_runtime_registry()`'s exact path expectations, bound
temporarily via `VOCAB_APP_SHARED_TTS_DIR` (process-scoped only), and
used to verify real end-to-end Card Audio Export against the production
database: live preflight succeeded for all three frozen routes, and a
real 2-Card export produced 2 valid canonical WAV files (see
`PROJECT_STATUS.md` § "Human Gate 3 runtime recovery"). The operator
then independently verified the native happy path and recorded **Human
Gate 3 PASS — Human Accepted**. With all three Human Gates accepted,
the operator authorized the merge and **M18 merged to `main` via PR #29
at `9dae05c49caec8f2a33fdaf74d0a1f3fd1db43bc`**.

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

### Mandatory M19 / M20 Productization Handoff — Card Audio Export

M18 proved the **Card Audio Export capability** end-to-end against a real
retained M15 shared TTS runtime: frozen EN/FR/ZH provider preflights
succeeded, real Cards became export-ready, real native export succeeded, and
generated WAV files satisfied the canonical WAV contract.

This does **not** mean a fresh public user can currently clone, download, or
install Vocabulary App and receive working Audio Export out-of-the-box. The
current product still depends on an externally available shared TTS runtime
exposed through `VOCAB_APP_SHARED_TTS_DIR`. This environment contract is
sufficient for M18 functional acceptance, but runtime discovery,
configuration, provisioning, and distribution have not yet been productized
for a clean end-user machine.

**M19 — Desktop Product Hardening** must evaluate and harden at least:

- shared TTS runtime discovery;
- persistent application/runtime configuration;
- behavior when the runtime is absent, incomplete, moved, or broken;
- actionable provider-preflight and recovery UX;
- first-run / Settings experience where appropriate;
- elimination of any expectation that a normal end user manually sets a shell
  environment variable merely to use Audio Export.

M19 should determine the durable product-facing runtime configuration
contract, but must not prematurely choose a packaging mechanism that
properly belongs to M20.

**M20 — Packaging and Release Candidate** must resolve how a clean external
user's installation obtains a usable TTS runtime, models, voices, and
required dependencies, explicitly evaluating:

- bundle-with-installer vs. first-run/on-demand download vs. another
  justified provisioning strategy;
- installer/runtime location and application discovery;
- package/download size;
- Windows/runtime dependencies;
- model/provider/voice redistribution and licensing constraints;
- upgrade/uninstall behavior;
- offline expectations;
- clean-machine installation verification;
- real Audio Export verification from an installation that does not inherit
  the developer machine's pre-existing TTS environment.

Release Candidate acceptance must not infer Audio Export deployability
merely from the developer machine's retained M15 runtime; a clean-user
installation must be verified independently.

**Lifecycle distinction:** M18 closes *Audio Export capability*. M19/M20
must close *Audio Export productization and deployability*. This is a
forward productization concern, not an M18 acceptance blocker.

---

## Milestone 19: Desktop Product Hardening

**Status: Complete on `main` — Human Accepted 2026-08-18 at accepted
product head `a128c50d75154ff3f85eacfd3a96e54d27d11c4d`, merged via
PR #30 at `2ad211711d96583b6fffdb65de912fa672502bc8`.** Developed under
the M19 Autonomous Product Hardening Execution Contract on the single
long-lived branch `agent/m19-desktop-product-hardening`, from the
verified M18 merge baseline `9dae05c49caec8f2a33fdaf74d0a1f3fd1db43bc`
(`main`). The desktop Feature Freeze was active throughout: one
confirmed release-relevant defect (duplicate active Quiz sessions on a
repeated launch) was root-caused and fixed; the mandatory M19/M20 Card
Audio Export productization handoff (shared TTS runtime configuration)
was closed; every other investigated hardening area was verified
already correct. Full repository suite 872/872, architecture audit
clean (95 files), native platform launch health agent-verified.

The Final Human Acceptance Gate took three attempts. Attempt 1 FAILed
with two narrow UX correctives (audio loading feedback; Navigation Rail
order). Attempt 2 PASSed the Navigation Rail order and re-FAILed the
loading feedback, relocating it to a hollow-to-solid progress ring
beside the Data Tools > Audio Export button and identifying the real
cause: a synchronous, PowerShell-spawning provider preflight blocking
the Qt UI thread before the dialog could paint. **Attempt 3 PASSed —
Milestone 19 is Human Accepted** at
`a128c50d75154ff3f85eacfd3a96e54d27d11c4d`. See `PROJECT_STATUS.md`
§ "M19 Engineering Exit Candidate summary" and its Final Human
Acceptance Gate attempt records, plus
[Milestone 19 Hardening QA](docs/qa/MILESTONE19_HARDENING_QA.md), for
the complete evidence record.

Desktop Product Hardening is complete and merged to `main`. Milestone 20 later
completed through the accepted v1.0.0 release; its criteria remain below as the
historical packaging and release contract.

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

**Status: Complete. v1.0.0 was merged, tagged, built from the tagged source,
and published after Human RC acceptance.**

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

## Milestone 21: Vocabulary App v1.1.0

**Status: Implementation and release verification complete on merged `main`;
publication from merged `main` is next. No v1.1.0 tag or GitHub Release is
claimed by this state.**

M21 is the bounded post-v1.0 product increment:

- **Phases A-E:** stable Card review scheduling; Star actions and honest
  Collection progress; local-time presentation and stable Windows identity;
  constrained Light/Dark theme customization; and release update awareness
  without automatic download or installation.
- **Phase Patch:** Quiz/Review Calendar scheduling coherence; consistent
  Proficient Pool, manual-proficient, strength-recommendation, and random
  practice behavior; and a shared normalized duplicate definition across
  preview and write paths.
- **Phase F:** v1.1.0 version and provenance authority, Windows build and
  packaged-launch proof, real isolated v1.0.0 → v1.1.0 overlay verification,
  real-Windows human acceptance, and fail-closed production-path guards for
  upgrade tooling and synthetic scheduling fixtures.

### Milestone 21 Release Gate

- three parallel Release Closure shards (Theme & Update Surface; M18
  remainder + full M19; M20 + timezone + v1.1 Phase/Patch/Review Scheduling)
  run as the GitHub Actions release-closure evidence gate, after the original
  single timeout-bounded `unittest discover` job could not complete within
  the CI time limit; `unittest discover` remains available as a manual-only
  job, not the active gate;
- Windows installer build, provenance checks, packaged launch, and the real
  isolated overlay upgrade proof remain green on the release source;
- repository-wide release review has no hard standards violation, release
  blocker, data-safety regression, or packaging regression;
- active governance documentation describes the post-merge, pre-publication
  state without rewriting historical evidence; and
- tag and GitHub Release creation remain separate operator-authorized actions
  performed only from verified merged `main`.

---

## Current Version Complete

The v1.0.0 product generation is complete and released. The v1.1.0 increment
has completed implementation and release verification; its remaining lifecycle
transition is publication from verified merged `main`. Publication, not this
merge-ready branch, establishes the new public release.

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
-> v1.0.0 Release
-> v1.1.0 Increment and Release Verification
-> v1.1.0 Publication
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
