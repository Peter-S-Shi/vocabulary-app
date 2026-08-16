## Objective


> **Vocabulary App · Desktop Product Design Authority & AI Coding Conformance Contract**

This is not a new UI exploration and not a product redesign.

The current `DESIGN.md` already contains many correct and approved decisions: product principles, Management / Study modes, Command Center / Table-First / Immersive Focus / Learning Brief First archetypes, Utility/Dialog grammar, theme architecture, semantic tokens, contrast/accessibility rules, component interaction rules, and visual acceptance principles.

Preserve those decisions unless the current repository or the approved visual artifacts prove that wording needs to be corrected or strengthened.

The purpose of v2 is to fix one demonstrated failure mode:

> The existing DESIGN freezes content hierarchy but does not constrain canonical spatial composition strongly enough, allowing an AI coding agent to claim compliance while substantially redesigning an approved screen.

The new document must make approved visual composition, design authority, implementation freedom, conformance evidence, and human visual acceptance explicit enough that a future coding agent can work from `DESIGN.md` alone without relying on hidden chat memory.

---

## First: inspect authoritative sources

Before editing, inspect the current repository state and relevant design/architecture/lifecycle documents, including at minimum:

- `DESIGN.md`
- `ROADMAP.md`
- `PROJECT_STATUS.md`
- `ARCHITECTURE.md`
- `docs/migration/DESKTOP_MIGRATION_PLAN.md`
- `docs/design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md`
- `docs/history/MILESTONE16_CLOSURE.md`
- relevant M14/M15 semantic contracts referenced by the current DESIGN
- current Streamlit surfaces as behavioral references where useful
- current `src/ui_desktop/` implementation only as evidence of current state, not as visual authority

Also inspect the approved visual exploration/validation artifacts and historical design prompts supplied for this design review. Treat those artifacts according to the authority rules below.

Do not infer a canonical composition from memory when a visual artifact exists.

---

# 1. Preserve the governing product principle

Keep:

> **Replace the UI layer, preserve the learning engine.**

Preserve the existing product character:

> Efficient when managing, quiet when studying, explanatory when analyzing, and precise when handling data.

Do not change learning, analytics, import, linked-source, audio, data-safety, or persistence semantics during this documentation task.

---

# 2. Add mandatory AI Coding Design-Conformance Rules

The new `DESIGN.md` must contain these rules explicitly.

## Rule A — Reading DESIGN is not design alignment

State clearly:

> **“Read DESIGN.md” is not evidence that a UI implementation is design-aligned.**

For any UI work, require a **DESIGN → Implementation Trace** mapping applicable DESIGN authority to concrete implementation decisions, including as relevant:

- screen composition;
- regions / surfaces;
- component roles;
- interaction container;
- visual hierarchy;
- navigation / chrome;
- canonical visual-reference correspondence.

A section-number citation by itself is insufficient.

## Rule B — Reverse mapping is required at delivery

Require an **Implementation → DESIGN Trace** in final delivery.

It must identify:

- which DESIGN sections controlled the feature;
- what concrete layout/component/interaction decisions resulted;
- which canonical visual references were used;
- what was implemented strictly;
- what was adapted within allowed native implementation freedom;
- what remains deferred.

If this trace cannot be established, the agent may not claim design alignment.

## Rule C — Structural tests cannot prove visual completion

State explicitly:

> **No visual requirement in `DESIGN.md` may be considered implemented solely because structural, unit, snapshot, token, contrast, widget-existence, hierarchy, or layout-property tests pass.**

Automated checks may prove structure, tokens, contrast, interaction states, layout invariants, or architecture boundaries.

They do not prove that:

- the UI looks like the approved design;
- spatial hierarchy works to a human observer;
- spacing/rhythm feels correct;
- canonical visual composition was faithfully reproduced;
- product-quality visual completion was achieved.

For visually governed UI:

> **Automated conformance + real native-window human visual acceptance are both required.**

## Rule D — Design-aligned / visually complete is a reserved claim

Define evidence levels such as:

1. Implemented
2. Structurally Conformant
3. Visually Reviewed
4. Human Accepted

Before explicit real-window human acceptance, an agent must not claim:

- “Visual parity achieved”
- “Fully aligned with DESIGN.md”
- “UI design complete”
- “Human acceptance passed”

---

# 3. Establish the Visual Authority System

Define four authority levels:

- **CANONICAL** — formally approved full visual composition; page-level design authority.
- **PATTERN** — formally approved reusable interaction/composition pattern.
- **VALIDATION** — validates theme/tokens/contrast/state behavior; cannot redefine canonical page composition.
- **EXPLORATION ONLY** — historical rejected/unselected alternatives; not valid implementation options.

Make explicit:

> Exploration artifacts are not a menu from which a coding agent may choose a different implementation.

Create a **Canonical Visual Reference Registry** with stable IDs and fields including:

- Reference ID
- file
- page / figure / variant
- authority level
- what it controls
- what it does not control
- allowed native adaptations

If a mandatory canonical reference is unavailable to the coding agent, it must stop and report missing design authority rather than inventing a replacement.

Historical design prompts are provenance / intent evidence, not current visual authority.

---

# 4. Register the approved canonical visual references

Use the approved visual artifacts and verify exact page/variant labels before writing them.

The approved selections are:

## Management Shell
Derived from the shared approved structure of Today Command Center and Entries Table-First.

Freeze the **persistent vertical left Navigation Rail** as a product-level Management Mode decision.

At normal desktop width, replacing it with top horizontal navigation, browser-like tabs, or hamburger-only navigation is a design change, not an implementation detail.

## Today / Home
Canonical:

`Today - Home.pdf`
→ Variant A — **Command Center / 学习指挥中心**

Freeze the actual approved spatial composition:

- left Navigation Rail;
- central Command Workspace as the largest region;
- compact summary near the top of the central workspace;
- **Today's Learning Queue** as the central visual anchor;
- Suggested Next Actions below/supporting the queue;
- persistent right Context Rail containing:
  - Recent Activity;
  - Collections Needing Attention;
  - Quick Actions.

Explicitly forbid composition substitutions such as:

- left rail → top navigation;
- three-region Command Center → single-column dashboard;
- Learning Queue → generic full-width management table;
- right Context Rail → stacked panels at the bottom;
- compact summary → dominant KPI dashboard.

The previously implemented pattern of top navigation + KPI tiles + full-width management table is a canonical-composition failure even if all expected content exists.

## Entries & Collections
Canonical:

`Entries & Collections Manager.pdf`
→ Variant B — **Table-First**

Freeze:

- Management left rail;
- scope / Collection region;
- toolbar;
- dominant Entries table;
- horizontal bottom detail region.

The table must remain the visual authority. Bottom detail is supporting.

Forbid substitutions such as card gallery, dominant permanent right inspector, permanent editor taking over the workspace, or top-tab navigation.

## Review / Quiz
Primary canonical:

`Review - Quiz.pdf`
→ Variant C — **Immersive Focus**

Freeze:

- Management navigation disappears during active Study Mode;
- minimal session bar;
- generous whitespace;
- one central learning task dominates;
- optional Card Contents/context appears through a transient right drawer;
- Review, Quiz, and completion states share the same Study visual language.

Do not allow a persistent Study cockpit, management shell, or permanent reference sidebar to replace this composition.

Secondary canonical Study view:

`Review - Quiz.pdf`
→ Variant D — **Flip Card + Filmstrip**

It controls only its optional Study presentation mode and does not replace Immersive Focus as the global Study Mode authority.

## Analytics
Canonical:

`Analytics - Insight.pdf`
→ Variant A — **Learning Brief First**

Freeze:

- scope/filter controls;
- **Learning Brief** as the dominant interpretation layer;
- supporting evidence beneath/after it;
- drill-down after interpretation/evidence.

Do not substitute a KPI dashboard, chart grid, Findings-table-first landing page, Evidence Landscape landing page, or global mastery score.

Also register these approved subordinate Analytics patterns:

### Finding Inbox + Evidence Inspector
Source: the corresponding approved Analytics exploration variant.

Use as a reusable subordinate pattern for Full Findings / Evidence Inspection, not as the Analytics landing page.

### Evidence Landscape
Source: the corresponding approved Analytics exploration variant.

Use as a Collection-level evidence-comparison pattern, not as the Analytics landing page.

Preserve semantic distinctions such as Touched Coverage vs Interpretable Coverage and Content Knowledge vs Scope Activity.

## Utility / Dialog Pattern Board
Register `Utility - Dialog Patterns.pdf` as **PATTERN** authority for the approved reusable utility grammar, including:

- Add/Edit focused modal/editor;
- destructive confirmation;
- Import Validate → Preview → Confirm;
- Linked Source refresh preview;
- Audio Export configuration;
- long-running progress + cancel;
- partial success + targeted retry;
- empty / neutral / warning / controlled error states.

## Theme validation artifacts
Register the Theme Architecture visual validation PDF as **VALIDATION** authority.

Register the Theme Contrast / Accessibility Hardening PDF as the latest **VALIDATION / numeric authority** where it supersedes earlier token/contrast values.

Theme validation must not be allowed to redefine canonical screen composition.

---

# 5. Add a Non-Authoritative Exploration Registry

Record unselected variants as **EXPLORATION ONLY** so future agents do not reinterpret them as valid alternatives.

Examples include unselected Today, Entries, Review/Quiz, and Analytics variants.

Do not delete their historical significance, but make it explicit that they are not implementation authority.

---

# 6. Expand Interaction Modes and freeze chrome relationships

Keep and strengthen Management Mode / Study Mode, and explicitly include:

- Management Mode
- Study Mode
- Utility / Dialog
- Transient Overlay

Management Mode:
- persistent vertical left Navigation Rail;
- medium/high information density where appropriate;
- desktop management chrome.

Study Mode:
- Management rail disappears;
- minimal session chrome;
- lower density / generous whitespace;
- one learning task at a time.

Utility/Dialog:
- no independent navigation system;
- focused transactional interaction.

Transient Overlay:
- inherits the parent screen and never creates a new shell.

---

# 7. Add a complete Screen / Window Coverage Contract

Build a comprehensive **Design Coverage Matrix** for the intended M17/M18 desktop product.

Do not inventory only primary navigation pages.

Include relevant:

- primary workspaces;
- Study Mode surfaces;
- dialogs/modals;
- drawers/side panels;
- editors;
- popovers;
- preview/confirmation flows;
- progress/result surfaces;
- settings surfaces;
- empty/error/partial-success states;
- feature-specific auxiliary windows;
- retired/integrated Streamlit-era surfaces.

Classify every surface as:

## A — Fully Specified / Canonical
Approved full composition and visual reference.

## B — Pattern-Specified
No dedicated full mockup, but a mandatory parent pattern/composition formula exists.

## C — Agent-Derived
Only where page-level design genuinely does not justify a dedicated canonical/pattern specification.

## Retired / Integrated
Legacy Streamlit surfaces that must not be recreated as standalone desktop pages merely for parity.

Keep C deliberately small.

The matrix should cover at minimum:

### M17
- Today
- Review
- Quiz variants
- Quiz completion
- Card Contents drawer
- Choose Quiz Type
- session recovery/restart/cancel
- Mistake Book / Proficient Pool launch/browse/practice
- Entries
- Entry add/edit
- search/filter/sort
- minimum Collection integration

### M18
- Collection Manager
- Card organization
- Collection/Card editors
- Template Manager
- Template Editor
- Template Field editor
- Review Calendar
- Card History
- Analytics landing
- Full Findings
- evidence drill-down
- Collection evidence comparison
- Data Tools
- Import / Export
- Template-definition import/export
- Linked Source setup/status/refresh/preview/relink/error recovery
- Backup / Restore Preview
- Audio Export config/progress/cancel/partial-success/retry/result
- Settings / Appearance / Storage
- theme popover
- relevant empty/error/warning/result states

Retired/integrated examples should include, where consistent with current migration docs:
- Streamlit Dashboard;
- old standalone Statistics presentation;
- Streamlit sidebar navigation;
- Streamlit `session_state` navigation behavior;
- legacy standalone concepts now integrated into Today/Analytics/History/Data Tools.

---

# 8. Define the approved reusable Parent Patterns

Freeze these reusable patterns:

- **P1 — Command Workspace**
- **P2 — Table-First Manager**
- **P3 — Immersive Study**
- **P4 — Learning Brief / Evidence**
- **P4A — Finding Inbox + Evidence Inspector**
- **P4B — Evidence Landscape**
- **P5 — Focused Editor**
- **P6 — Utility Workflow / Dialog**
- **P7 — Evidence Browser**
- **P8 — Settings Form**

For each pattern, define concise executable rules for:

- interaction mode;
- required regions;
- dominant/supporting relationship;
- density;
- action hierarchy;
- expected chrome;
- closest canonical reference;
- allowed variation.

Do not turn these into widget-by-widget implementation manuals.

---

# 9. Add the mandatory Agent Design-Derivation Formula

For Pattern-Specified and especially Agent-Derived surfaces, require a concise derivation record covering:

1. Interaction Mode
2. Parent Pattern
3. Primary User Task
4. Spatial Composition
5. Dominant Region
6. Density Rule
7. Surface Hierarchy
8. Action Hierarchy
9. Editing Container
10. Navigation / Chrome Inheritance
11. Motion / Transition
12. Canonical Visual Reference Relationship
13. Native Human Acceptance Target

A C-class surface may be designed by the agent only through this derivation process.

“Keep the same style” is not an acceptable design specification.

---

# 10. Add Editing Container Decision Rules

Provide clear guidance for choosing among:

- inline;
- bottom detail;
- side drawer;
- modal / pop-up;
- independent focused editor workspace/window.

Use principles such as:

- tiny/local/reversible edit → inline;
- preserve list context → bottom detail or drawer;
- focused multi-field Save/Cancel task → modal;
- complex structured editing → focused editor workspace.

Freeze the current decision:

> **Template Editor defaults to a focused editor workspace.**

Smaller field-level edits may use modal interaction where appropriate.

---

# 11. Add a restrained Motion / Transition system

Use one coherent motion language.

Principle:

> **Motion explains state change; it does not decorate the application.**

Examples:
- navigation: instant / near-instant;
- modal/popover: subtle native transition;
- drawer: short restrained slide;
- Flip Card: allowed only in the optional Flip Card Study view;
- progress: communicates process/state;
- no decorative dashboard animation.

---

# 12. Add the Implementation Freedom Boundary

Create three explicit scopes.

## Frozen Product Design Decisions

The coding agent may not independently change:

- canonical screen composition;
- navigation model;
- approved archetype / parent pattern;
- major regions;
- dominant/supporting relationships;
- Management vs Study mode/chrome;
- major interaction containers;
- canonical visual-reference authority;
- product/learning/analytics semantics;
- approved theme architecture.

## Adaptable Native Implementation Details

The agent may reasonably decide:

- exact PySide6 widget classes;
- layout mechanics;
- minor pixel-level spacing;
- exact font fallback;
- native scrollbar behavior;
- technical splitter/layout implementation;
- DPI/native metrics;
- text wrapping;
- small dimension adjustments;
- accessibility-compatible framework adjustments.

Freeze this principle:

> **Native adaptation may alter dimensions and mechanics; it may not substitute composition.**

Examples:
- adjusting column ratios is adaptation;
- changing a three-region layout into a single-column dashboard is redesign.
- narrowing a vertical rail is adaptation;
- replacing it with top navigation is redesign.

## Agent-Derived Design

Only surfaces marked C in the Coverage Matrix may receive page-level agent design decisions, and only through the derivation formula.

---

# 13. Add a Design Change Gate

If a coding agent finds that a frozen composition appears unsuitable under real PySide6/native constraints, it must not silently redesign.

Require a Design Change Proposal containing:

- Existing authority
- Problem observed
- Why normal native adaptation is insufficient
- Proposed design change
- Affected canonical references/patterns
- semantic/workflow impact
- human approval required

Then STOP.

No approved design change → no canonical composition change.

---

# 14. Preserve and reorganize the mature visual system

Retain the current approved/hardened content for:

- Appearance: System / Light / Dark
- four curated Accent families
- Theme controls
- semantic token architecture
- explicit `on-*` foreground pairs
- Accent vs Semantic State separation
- hardened token values
- Dark Mode surface hierarchy
- restrained Study Mode accent usage
- typography / spacing / density / radius principles
- components and interaction states
- keyboard / desktop behavior
- accessibility / contrast

Do not invent new token values or “improve” the palette during this rewrite.

Where the Theme Contrast / Accessibility Hardening artifact is the later numeric authority, preserve those hardened values.

---

# 15. Rewrite the Visual Acceptance Contract

For canonical A-class screens, visual completion requires:

> **DESIGN → Implementation Trace**
> + **automated structural conformance**
> + **real native-window rendering**
> + **comparison against the registered canonical reference**
> + **explicit human acceptance**

Automated tests may be regression guards, but do not substitute human visual judgment.

For each canonical master screen, define concise visual invariants and forbidden substitutions.

Examples:

## Management Shell
- persistent vertical left Navigation Rail at normal desktop width;
- top horizontal nav is not an equivalent implementation.

## Today
- central Command Workspace is largest;
- right Context Rail remains a distinct secondary region;
- Learning Queue is the central visual anchor;
- compact summary is not a dominant KPI dashboard.

## Entries
- table is visually dominant;
- detail remains subordinate and horizontal/bottom-oriented by default.

## Study
- Management chrome disappears;
- minimal session bar + central learning task;
- optional context is transient, not a permanent cockpit/sidebar.

## Analytics
- Learning Brief dominates;
- evidence supports interpretation;
- charts/tables do not become the landing-page visual authority.

Define the term:

> **Forbidden Composition Substitution**

A composition substitution is a DESIGN failure even if the same content exists, tests pass, tokens are correct, and accessibility checks pass.

---

# 16. Add reusable trace templates

Include concise templates for:

## DESIGN → Implementation Trace

Columns such as:
- DESIGN authority
- requirement
- implementation decision
- visual reference

## Implementation → DESIGN Trace

Columns such as:
- implemented surface/decision
- DESIGN authority
- strict implementation
- allowed adaptation
- deferred

Keep these small enough to use routinely.

---

# 17. Add Human Acceptance Record guidance

A visual acceptance record should identify:

- native surface/build shown;
- canonical reference compared;
- accepted/rejected;
- issues found;
- what remains pending.

Do not create a bureaucratic approval system; create clear evidence boundaries.

---

# 18. Retired / Integrated UI Concepts

Record legacy surfaces that must not be recreated merely for one-to-one Streamlit parity.

Use the current Roadmap/Migration Plan as authority.

The desktop application is not a literal Streamlit page port.

---

# 19. Fix stale lifecycle/framework wording

The current repository lifecycle has advanced beyond some wording in the existing `DESIGN.md`.

Reconcile the rewritten DESIGN with current authoritative `ROADMAP.md` and `PROJECT_STATUS.md`.

Do not reopen completed M16 architecture decisions.

PySide6 is selected and the M16 architecture/state boundaries are already frozen by the M16.1 architecture contract.

Remove or rewrite obsolete “framework undecided” / “M16 still open” wording as appropriate.

Do not modify `ROADMAP.md` or `PROJECT_STATUS.md` unless you discover a genuine current inconsistency that cannot be resolved inside `DESIGN.md`; if such an issue exists, report it before broadening scope.

---

# 20. Suggested v2 document structure

Use this as the preferred organization unless repository evidence suggests a small improvement:

## Part I — Authority & AI Coding Contract
1. Purpose, Scope & Authority
2. Governing Product Design Principle
3. AI Coding Design-Conformance Rules
4. UI Feature Design Workflow

## Part II — Visual Authority System
5. Visual Authority Levels
6. Canonical Visual Reference Registry
7. Non-Authoritative Exploration Registry

## Part III — Product Spatial Architecture
8. Interaction Modes
9. Global Management Shell
10. Canonical Screen Composition Contracts

## Part IV — Screen / Window Coverage Contract
11. Design Coverage Classification
12. Complete Design Coverage Matrix

## Part V — Reusable Design Patterns
13. Approved Parent Patterns
14. Utility / Dialog Grammar
15. Editing Container Decision Rules
16. Motion & Transition Language

## Part VI — Agent-Derived Design
17. Mandatory Design Derivation Formula

## Part VII — Implementation Freedom Boundary
18. Frozen Product Design Decisions
19. Adaptable Native Implementation Details
20. Design Change Gate

## Part VIII — Visual System
21. Theme Architecture
22. Theme Controls
23. Semantic Token Architecture
24. Explicit Foreground Pair Rule
25. Accent vs Semantic State
26. Frozen Theme Tokens
27. Dark Mode
28. Study Mode Color Restraint
29. Typography / Spacing / Density / Radius
30. Components & Interaction States
31. Keyboard & Desktop Behavior
32. Accessibility & Contrast

## Part IX — Acceptance & Evidence
33. Visual Acceptance Contract
34. Canonical Screen Acceptance Criteria
35. Forbidden Composition Substitutions
36. DESIGN → Implementation Trace Template
37. Implementation → DESIGN Trace Template
38. Human Acceptance Record

## Part X — Governance
39. Anti-Patterns
40. Retired / Integrated UI Concepts
41. Framework / Native Notes
42. Design Provenance

Keep the document coherent; do not mechanically preserve old section numbering.

---

# 21. Old → new migration principle

Treat the current DESIGN as source material.

Use this transformation:

> **Preserve → relocate → consolidate → strengthen**

Do not:

- redesign;
- simplify away frozen decisions;
- invent new product behavior;
- change semantic contracts;
- change token values;
- derive visual authority from the current imperfect M16.2 UI implementation;
- turn the document into a PySide6 construction manual.

The new document may be longer than the current one, but it should remain a design authority, not a widget-by-widget specification.

---

# 22. Visual-reference file handling

Approved visual artifacts may be supplied separately during design review. Machine-specific source locations are intentionally not recorded in this document.

Do **not** move, rename, copy, or commit those visual files into the repository during this rewrite unless separately authorized.

A future repo-owned location may be considered, such as:

`docs/design/visual-references/`

but this document does not authorize that asset migration.

---

# 23. Scope restrictions

This task is documentation-only.

Do not:

- modify production Python;
- modify tests to make the current UI appear compliant;
- implement Today/Entries/Review/Quiz/Analytics corrections;
- alter database/schema/data;
- change theme values;
- start M17 implementation;
- move visual assets;
- perform unrelated cleanup.

The current imperfect UI implementation may be cited as evidence for why stronger conformance rules are needed, but it is **not** the visual authority.

---

# 24. Verification before delivery

Before finishing:

- compare the rewritten document against the current DESIGN so mature theme/token/accessibility content was not accidentally lost;
- verify the four canonical master-screen decisions remain exactly:
  - Today → Command Center;
  - Entries → Table-First;
  - Review/Quiz → Immersive Focus primary;
  - Analytics → Learning Brief First;
- verify Flip Card + Filmstrip remains secondary;
- verify Management left Navigation Rail is frozen;
- verify the Utility Pattern Board remains authoritative;
- verify selected Analytics subordinate patterns are correctly scoped;
- verify unselected exploration variants are not presented as valid implementation alternatives;
- verify hardened token values were not changed;
- verify the document distinguishes structural proof from real human visual acceptance;
- verify current lifecycle/framework wording matches current repository authority.

No app tests are required solely because this is a documentation-only rewrite unless repository tooling has a relevant documentation check worth running.

---

# 25. Git review workflow

Do not push directly to `main`.

Use:

**new documentation branch → edit → review your diff → commit → push branch → create PR → STOP**

Do not merge the PR.

Do not delete the branch.

Do not begin UI corrective implementation.

At completion, report:

- branch;
- commit SHA;
- PR number / URL;
- files changed;
- approximate old/new DESIGN size;
- sections materially added/reorganized;
- whether any existing design decision was intentionally changed (expected answer: none, except stale lifecycle/framework wording correction);
- whether any token value changed (expected answer: no);
- any unresolved authority/reference ambiguity;
- concise self-audit against the verification checklist above.

Then stop for human review.
