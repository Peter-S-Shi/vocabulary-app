# Vocabulary App · Desktop Product & UI Design Authority (`DESIGN.md`)

Status: **Frozen Product/UI Design Authority — governs native desktop implementation from Milestone 17 onward**

`ROADMAP.md` and `PROJECT_STATUS.md` remain authoritative for lifecycle status. Milestone 16 is complete on `main`; this document preserves and strengthens the approved desktop design baseline for Milestone 17+ implementation.

This document is the canonical product/UI design authority for Vocabulary App's native desktop application. It consolidates approved product design, canonical visual composition, reusable screen patterns, theme/token rules, accessibility requirements, design-derivation rules, and AI-coding conformance requirements.

It exists to make one thing unambiguous:

> **Approved visual composition is a design decision, not an implementation suggestion.**

A future human contributor, Codex, Claude Code, or other coding agent must be able to read this document and determine:

- which product and visual decisions are frozen;
- which surfaces have canonical visual references;
- which surfaces inherit approved patterns;
- which surfaces may be agent-derived;
- how agent-derived design must be derived;
- which native implementation details remain flexible;
- how implementation must trace back to design authority;
- what automated tests can and cannot prove; and
- when a real native window must be shown to a human before UI work may be called complete.

This document is **not**:

- a component-by-component construction manual;
- a PySide6 tutorial;
- a pixel-perfect browser-to-Qt reproduction specification;
- a duplicate of `ROADMAP.md` or `PROJECT_STATUS.md`;
- a license to reopen already approved UI directions;
- a restatement of every historical design conversation.

Read it alongside:

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — application/module boundaries and learning semantics;
- [`docs/migration/DESKTOP_MIGRATION_PLAN.md`](docs/migration/DESKTOP_MIGRATION_PLAN.md) — desktop migration strategy and workflow mapping;
- [`docs/design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md`](docs/design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md) — PySide6 architecture, state, concurrency, and theme implementation boundaries;
- [`docs/design/M14_SEMANTIC_CONTRACT.md`](docs/design/M14_SEMANTIC_CONTRACT.md) — Analytics semantics;
- [`docs/design/M15_1_SPEECH_SEMANTIC_CONTRACT.md`](docs/design/M15_1_SPEECH_SEMANTIC_CONTRACT.md) — speech semantics;
- [`docs/design/M15_3_BATCH_EXPORT_CONTRACT.md`](docs/design/M15_3_BATCH_EXPORT_CONTRACT.md) — audio batch-export semantics.

Where a UI rule conflicts with an authoritative product/semantic contract, the semantic contract wins and the UI must be adjusted. The UI must not silently rewrite domain truth.

---

## 1. Governing Product Principle

> **Replace the UI layer, preserve the learning engine.**

Vocabulary App is a local-first personal vocabulary learning workspace. The desktop application may reorganize Streamlit-era pages into more coherent desktop workflows, but it must not mechanically reproduce Streamlit's layout constraints or silently alter learning, evidence, data-safety, import, analytics, linked-source, or audio semantics.

The product should feel:

> **Efficient when managing, quiet when studying, explanatory when analyzing, and precise when handling data.**

The design language is one coherent desktop product with multiple interaction modes, not a collection of independent mini-apps.

---

## 2. AI Coding Design-Conformance Rules

These rules are mandatory for every UI-affecting implementation. They do not depend on chat memory, a milestone prompt, or a particular coding agent.

### Rule A — Reading `DESIGN.md` is not design alignment

> **“Read `DESIGN.md`” is not evidence that a UI implementation is design-aligned.**

Before or during implementation, the coding agent must produce a **DESIGN → Implementation Trace** for the affected surface. The trace must map applicable design authority to concrete implementation decisions, including at minimum:

- screen composition;
- regions and surfaces;
- component roles;
- interaction container;
- visual hierarchy and dominance;
- navigation/chrome relationship; and
- canonical visual-reference correspondence.

A trace such as “follows §5.1 and §22” is insufficient. It must state what those requirements become in the actual UI.

### Rule B — Reverse mapping is required at delivery

At delivery, the coding agent must provide **Implemented UI → DESIGN Authority**.

The final report must identify:

- which DESIGN sections controlled the feature;
- which concrete layout/component/interaction decisions each section produced;
- which canonical or pattern visual references were used;
- which decisions were implemented strictly;
- which details used allowed implementation freedom;
- which items remain deferred; and
- whether native human visual acceptance is complete or still pending.

If this reverse trace cannot be established, the implementation must not claim design alignment.

### Rule C — Structural tests cannot prove visual completion

> **No visual requirement in `DESIGN.md` may be considered implemented solely because structural, unit, snapshot, token, contrast, widget-existence, hierarchy, or layout-property tests pass.**

Automated tests can prove things such as:

- required components or regions exist;
- semantic tokens resolve correctly;
- contrast meets the defined threshold;
- hover/selected/focus/disabled states exist;
- layout invariants are not structurally violated;
- architecture and state boundaries are correct.

They cannot prove that:

- the UI looks like the approved design;
- spatial hierarchy works to a human observer;
- spacing/rhythm is visually comfortable;
- canonical composition has been faithfully reproduced;
- the result has product-quality visual coherence.

For any surface with visual requirements, completion requires both:

> **Automated conformance + real native-window human visual acceptance.**

### Rule D — `design-aligned` is a reserved claim

Before human acceptance, report evidence precisely, for example:

```text
Implementation: COMPLETE
Structural conformance: PASS
Automated design guards: PASS
Native visual acceptance: PENDING
```

Do not claim any of the following before a human has reviewed the real native surface against the applicable design authority:

- “Visual parity achieved”;
- “Fully aligned with DESIGN.md”;
- “UI design complete”;
- “Human acceptance passed”.

### Design evidence levels

UI evidence is classified as:

1. **Implemented** — code exists and the surface runs.
2. **Structurally Conformant** — automated and architectural design guards pass.
3. **Visually Reviewed** — the real native surface has been viewed and compared with its authority.
4. **Human Accepted** — the human reviewer explicitly accepts the visual result.

Only Level 4 closes a visual implementation requirement.

---

## 3. Visual Reference Authority System

Visual artifacts have explicit authority levels. A coding agent must not treat every page in an exploration PDF as an interchangeable source of inspiration.

### 3.1 Authority levels

**CANONICAL** — formally approved composition. Spatial composition, major regions, hierarchy, chrome relationship, and interaction form are frozen. Only native implementation adaptation is allowed.

**PATTERN** — formally approved reusable interaction/composition pattern. It may be inherited by surfaces without their own full mockup.

**VALIDATION** — validates theme, tokens, contrast, semantic state, or cross-screen consistency. It does not override canonical screen composition.

**EXPLORATION ONLY** — historical alternatives that were considered but not selected. They are non-authoritative. A coding agent must not choose one of these variants because it appears easier, more modern, or more compatible with a framework.

### 3.2 Canonical Visual Reference Registry

The reference filename and page/variant are part of design authority. If these artifacts are later stored in the repository, preserve these logical IDs and update only their paths.

| ID | Visual reference | Authority | Controls |
|---|---|---|---|
| `VR-SHELL-001` | Shared structure derived from `Today - Home.pdf` p2 Variant A + `Entries & Collections Manager.pdf` p3 Variant B | CANONICAL | Management Mode vertical left Navigation Rail and workspace relationship |
| `VR-TODAY-001` | `Today - Home.pdf` p2, Variant A — **Command Center** | CANONICAL | Today/Home spatial composition, dominant queue, right Context Rail |
| `VR-ENTRIES-001` | `Entries & Collections Manager.pdf` p3, Variant B — **Table-First** | CANONICAL | scope + toolbar + dominant table + horizontal bottom detail |
| `VR-STUDY-001` | `Review - Quiz.pdf` p4, Variant C — **Immersive Focus** | CANONICAL | primary Study Mode composition, minimal session chrome, transient context drawer |
| `VR-STUDY-002` | `Review - Quiz.pdf` p5, Variant D — **Flip Card + Filmstrip** | CANONICAL-secondary | optional alternate Study presentation only |
| `VR-ANALYTICS-001` | `Analytics - Insight.pdf` p2, Variant A — **Learning Brief First** | CANONICAL | Analytics landing composition |
| `VR-ANALYTICS-002` | `Analytics - Insight.pdf` p3, Variant B — **Finding Inbox + Evidence Inspector** | PATTERN | Full Findings / Evidence Inspection workspace |
| `VR-ANALYTICS-003` | `Analytics - Insight.pdf` p4, Variant C — **Evidence Landscape** | PATTERN | Collection-level evidence comparison |
| `VR-UTILITY-001` | `Utility - Dialog Patterns.pdf`, full board | PATTERN | dialogs, preview/commit, progress, partial success, state language |
| `VR-THEME-001` | `Theme Architecture Visual Validation.pdf`, full document | VALIDATION | Appearance × Accent architecture, surface hierarchy, cross-screen theme behavior |
| `VR-CONTRAST-001` | `Theme Contrast Accessibility Hardening.pdf`, full document | VALIDATION — latest numeric authority | hardened tokens, explicit foreground pairs, contrast/state requirements |

### 3.3 Non-authoritative exploration variants

Unless a later explicit design decision promotes them, the following remain **EXPLORATION ONLY**:

- `Today - Home.pdf`: Study-First, Workspace Dashboard, Triage Inbox, Status Board, Schedule Planner;
- `Entries & Collections Manager.pdf`: Three-Pane Workbench, Modal Editor as a whole-screen direction, Card Gallery, Collection Wall + inline expansion, Tabbed Workspace;
- `Review - Quiz.pdf`: Guided Review → Quiz, Study Cockpit, Split Reference Pane, Worksheet;
- `Analytics - Insight.pdf`: Learning Diagnostic Report, Collection Atlas + Brief Rail, Evidence Timeline.

Historical prompts used to generate or validate these materials are **Design Provenance / Intent Evidence**, not current visual authority. They may explain why a decision was explored, but they cannot override the current DESIGN + registered reference.

### 3.4 Reference availability rule

If an A-class surface requires a canonical visual reference and the coding environment cannot access that reference, the agent must stop before claiming or attempting canonical visual completion and request the missing artifact.

The agent must not reconstruct the missing reference from memory, from an old implementation, from an exploration alternative, or from a textual summary alone.

### 3.5 Reference precedence

For spatial composition:

```text
Current DESIGN.md + registered CANONICAL/PATTERN reference
> non-authoritative exploration material
> historical prompts / chat provenance
```

For numeric theme/contrast values:

```text
VR-CONTRAST-001
> VR-THEME-001
> earlier palette values
```

For product semantics:

```text
Authoritative semantic/product contracts
> UI visual reference
```

---

## 4. Macro Interaction Model

The product has four interaction contexts.

### 4.1 Management Mode

Used for Today/Home, Entries, Collections, Templates, Analytics, Data Tools, Settings, Review Calendar/Card History, and other organization/inspection workflows.

Characteristics:

- normal desktop shell remains visible;
- a persistent vertical left Navigation Rail is the first-level navigation model;
- medium-to-high information density is acceptable;
- tables, filters, toolbars, status indicators, dialogs, batch operations, and secondary context regions are first-class patterns;
- the product should feel calm, efficient, and desktop-native.

### 4.2 Study Mode

Used for Review, Quiz, Mistake Book practice, Proficient Pool practice, and other focused learning sessions.

Characteristics:

- Management navigation disappears during active study;
- chrome is replaced by a minimal session bar;
- one learning task is prioritized at a time;
- generous whitespace is deliberate;
- optional context appears through temporary drawers or lightweight controls;
- accent use is restrained;
- Study Mode is quieter than Management Mode.

### 4.3 Utility / Dialog context

Used for focused configuration, preview/confirmation, destructive actions, import/export, linked-source setup/refresh, backup/restore preview, audio export, and other bounded workflows.

A utility surface does not invent a third application navigation model. It belongs to and returns to its parent workflow.

### 4.4 Transient overlay context

Includes popovers, context menus, tooltips, drawers, lightweight selectors, and validation hints. These inherit visual authority from their parent screen/pattern and do not become independent workspaces.

---

## 5. Global Management Shell Contract

`VR-SHELL-001` is CANONICAL.

At normal supported desktop width, Management Mode uses:

```text
┌──────────────┬─────────────────────────────────────────────────────┐
│              │                                                     │
│ LEFT         │                     WORKSPACE                       │
│ NAVIGATION   │                                                     │
│ RAIL         │                                                     │
│              │                                                     │
│              │                                                     │
│ Settings     │                                                     │
└──────────────┴─────────────────────────────────────────────────────┘
```

The exact item inventory/order may evolve with the approved product IA, but the **vertical rail model is frozen**.

### Required invariants

- first-level Management navigation is vertical and left-aligned;
- current workspace is visually distinct using the shared selection language;
- the rail is visually subordinate to the active workspace;
- Settings and low-frequency configuration may remain lower in the rail;
- theme control may be reachable from the shell but must not become a large permanent navigation destination;
- Study Mode replaces this shell rather than layering dense study UI on top of it.

### Forbidden substitutions

The following are design failures at normal desktop width:

- left rail → top horizontal navigation;
- left rail → browser-style top tabs;
- left rail → hamburger-only navigation;
- page-local navigation that creates a second competing first-level shell.

### Allowed native adaptation

- exact rail width;
- icon/text spacing;
- font fallback and native metrics;
- compact icon-only rail at narrower supported widths;
- scroll/overflow behavior if the number of navigation items requires it.

A compact rail remains a vertical rail. A framework convenience such as `QToolBar` does not authorize changing the navigation orientation.

---

## 6. Canonical Screen Composition Contracts

### 6.1 Today / Home — Command Center

**Authority:** `VR-TODAY-001` — `Today - Home.pdf` p2 Variant A.

**Purpose:** answer, quickly and calmly:

> What matters today, what can I resume, and what should I do next?

#### Frozen composition

At normal desktop width Today is a three-region Command Center:

```text
┌──────────┬──────────────────────────────┬──────────────────┐
│          │ TODAY                        │ RECENT ACTIVITY  │
│ LEFT NAV │                              │                  │
│          │ compact status summary       │                  │
│          ├──────────────────────────────┤──────────────────│
│          │                              │ COLLECTIONS      │
│          │ TODAY'S LEARNING QUEUE       │ NEEDING          │
│          │                              │ ATTENTION        │
│          │          DOMINANT            │                  │
│          │                              ├──────────────────│
│          ├──────────────────────────────┤ QUICK ACTIONS    │
│          │ Suggested Next Actions       │                  │
└──────────┴──────────────────────────────┴──────────────────┘
```

**Region 1 — Navigation Rail**: global Management Shell.

**Region 2 — Central Command Workspace**: the largest region. It contains a compact summary, Today's Learning Queue as the visual anchor, and Suggested Next Actions.

**Region 3 — Right Context Rail**: persistent but secondary context containing Recent Activity, Collections Needing Attention, and Quick Actions.

#### Dominance rule

> **Today's Learning Queue > compact summary metrics > right-context information.**

The summary may use small status cards/values, but it must not become a KPI dashboard.

#### Product semantics

Today activity must reflect factual current learning evidence and completed Card-scoped Quiz history according to `src/learning_workflow.py` and the Learning Completion Semantics in `ARCHITECTURE.md`. Legacy Review scheduling must not be reintroduced as product truth.

#### Forbidden composition substitutions

- top horizontal nav + KPI tiles + full-width management table;
- right Context Rail moved to stacked panels at the bottom at normal desktop width;
- Learning Queue replaced by a generic Entries-style management table;
- summary/KPI region becoming the dominant first-screen object;
- the rejected Workspace Dashboard exploration variant substituted for the approved Command Center;
- single-column dashboard treatment at normal supported width.

#### Allowed adaptation

- exact column widths and gaps;
- queue row/card height;
- text wrapping;
- minor summary-card sizing;
- at genuinely narrow supported widths, Right Context Rail may collapse into an explicit context drawer/panel before the central Command Workspace is structurally redesigned.

### 6.2 Entries Manager — Table-First

**Authority:** `VR-ENTRIES-001` — `Entries & Collections Manager.pdf` p3 Variant B.

**Purpose:** efficiently browse, filter, compare, organize, and edit large numbers of Entries.

#### Frozen composition

```text
┌──────────┬──────────────┬──────────────────────────────────┐
│          │              │ Entries + TOOLBAR                │
│ LEFT NAV │ SCOPE        ├──────────────────────────────────┤
│          │              │                                  │
│          │ All entries  │                                  │
│          │ Starred      │             TABLE                │
│          │ Mistake Book │                                  │
│          │ Collections  │            DOMINANT              │
│          │              │                                  │
│          │              ├──────────────────────────────────┤
│          │              │ HORIZONTAL ENTRY DETAIL          │
└──────────┴──────────────┴──────────────────────────────────┘
```

Management Rail → Scope Pane → Main Workspace.

Within the Main Workspace:

1. compact toolbar with search/filter/sort/batch/add actions;
2. dense Entries table as the dominant surface;
3. selected Entry detail in a horizontal bottom region.

#### Dominance rule

> **Table ≫ detail.**

The bottom detail supports current selection. It is not the main editor and must not visually compete with the table.

#### Required behavior

- multi-selection and batch operations remain first-class;
- selected/hover/focus states are distinct;
- management density supports long scanning sessions;
- Dark Mode preserves separation among app background, scope pane, table, selected row, detail region, and overlay/dialog surfaces.

M17 Final Parity + Exit Verification closed the last gap between this
section's frozen "search/filter/sort/batch/add actions" toolbar spec and
the implementation: a compact Sort by control (Term/Created/Updated,
composing with existing scope/search/filter) and a subordinate result-
count indicator, in an always-visible meta row beneath the toolbar --
plus a Custom option on the Entry Type field (a native text prompt; the
value is ordinary Entry data through the existing create/update path,
not a new taxonomy surface).

#### Forbidden composition substitutions

- bottom detail replaced by a permanent large right inspector as the default design;
- table replaced by a card gallery/tile wall;
- detail area consuming roughly half the default workspace;
- permanent editing form occupying the main workspace by default;
- Collection organization converted into browser-style top tabs;
- left Management Rail replaced by top navigation.

#### Allowed adaptation

- scope width;
- table column widths and row height;
- splitter mechanics;
- exact default detail height;
- native scrollbar/header behavior.

The default state must still read immediately as “table-first”.

### 6.3 Review / Quiz — Immersive Focus

**Authority:** `VR-STUDY-001` — `Review - Quiz.pdf` p4 Variant C.

This is the primary and global authority for Study Mode.

#### Frozen composition

```text
┌──────────────────────────────────────────────────────────┐
│ Back · Collection · Card                    Progress     │
│                                      [Card Contents]     │
├──────────────────────────────────────────────────────────┤
│                                                          │
│                                                          │
│                 CURRENT LEARNING TASK                    │
│                                                          │
│                       DOMINANT                           │
│                                                          │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

When contextual content is requested:

```text
MAIN LEARNING SURFACE              │ TRANSIENT RIGHT DRAWER
slightly dimmed/reflowed if needed │ Card contents / history
```

#### Frozen rules

- Management Navigation Rail disappears during active Study Mode;
- a minimal session bar remains for exit/back, Collection/Card context, progress, and necessary session actions;
- the current learning task occupies the visual center;
- generous whitespace is intentional;
- optional Card contents/history are transient, not persistent chrome;
- Review, Quiz, and Completion states share the same Study spatial language.

#### Review semantics

Review is preparation. Browsing alone does not create authoritative completion.

The user must retain explicit routes to Quick Quiz and Choose Quiz Type for the selected Collection/Card context.

#### Quiz semantics

A completed Card-scoped Quiz remains the authoritative Card learning/review completion event. Objective and self-graded modes, restart/recovery, duplicate-submission protection, Mistake Book, Proficient Pool, and Card/revision context remain governed by existing product semantics.

Do not revive `Again / Hard / Good / Easy` scheduling semantics without a separately approved product change.

#### Completion state

Completion remains inside the Immersive Focus language. A compact result summary may show correct/wrong/pending and appropriate next actions, but the surface must not transform into a dashboard or Analytics page.

#### Card Contents drawer

The Card Contents/History surface is a transient right drawer. It may resize or lightly dim/reflow the main content while open, but it must not become a permanent inspector that changes the default Study composition.

#### Forbidden composition substitutions

- Management Rail remaining visible during active study;
- persistent multi-panel Study Cockpit;
- permanent reference sidebar;
- management toolbar in the active session;
- KPI/dashboard framing;
- dense management tables as the default learning surface;
- accent theme redefining Correct/Wrong semantics.

### 6.4 Flip Card + Filmstrip — secondary Study view

**Authority:** `VR-STUDY-002` — `Review - Quiz.pdf` p5 Variant D.

This is a valid optional user-selectable Study presentation, not the global Study authority.

**M17 Feature 3B scope decision (binding):** `VR-STUDY-002` is implemented as a **Quiz-only presentation choice**, not a second global Study design language. It SHALL NOT propagate to Review, Today, Entries, Collections, Card Contents, Analytics, general Study Mode, Management Mode, or other future features. Review remains exclusively the accepted `VR-STUDY-001` Immersive Focus experience; it carries no Flip Card control of its own. A future checkpoint that wants Flip Card + Filmstrip for Review specifically requires a separate, explicitly approved product decision — do not infer it from this section.

Frozen visual relationship:

```text
minimal session context

               ┌────────────────┐
               │                │
               │   FLIP CARD    │
               │                │
               └────────────────┘

────────────────────────────────────────────
          FILMSTRIP / CARD POSITION
────────────────────────────────────────────
```

Review may use term on the front and meaning/example on the back. Quiz may reuse the card container for answer/expected-answer/feedback states. Filmstrip progress supplies position awareness.

This view controls only itself. It must not redefine Management Mode, default Immersive Focus, or the application-wide component system.

**Quiz implementation shape (M17 Feature 3B):**

- One durable preference, `quiz_presentation` (`immersive_focus` default / `flip_card_filmstrip`), stored in the existing desktop `preferences.json` (never `vocab.db`), changed only from Settings → Quiz → Quiz presentation — no second in-session switcher anywhere (Review, Choose Quiz Type, Quiz session bar, completion).
- The preference is resolved once per Quiz launch, when `QuizController.start()` is invoked, not re-read on every render.
- Self-graded and MCQ Quiz families (including template-aware types that already progress linearly through those families) render inside the Flip Card + Filmstrip when selected. Both presentations consume the exact same `QuizController` session/answer/completion truth; there is one Quiz engine, not two.
- **Matching compatibility fallback (binding):** plain and template-aware Matching are a genuinely simultaneous whole-set interaction, not a linear one-item flow. Regardless of the saved `quiz_presentation` preference, Matching always uses the existing wider Immersive Matching presentation. This fallback never alters the saved preference, never resets it to Immersive Focus, and never splits Matching into sequential fake questions.
- Completion and the read-only post-Quiz mistake review remain the single shared Immersive-styled surfaces for both presentations — `VR-STUDY-002` governs only the active self-graded/MCQ task surface, not completion/mistake-review chrome.
- The filmstrip is orientation/progress only (total count, current item, already-answered correct/wrong, remaining) and is deliberately non-interactive in this checkpoint: no click-to-jump, since the existing Quiz engine is a controlled linear progression and arbitrary navigation would require session/scoring changes out of scope here.

### 6.5 Analytics Landing — Learning Brief First

**Authority:** `VR-ANALYTICS-001` — `Analytics - Insight.pdf` p2 Variant A.

**Purpose:** answer:

> What deserves my attention now, why, and what evidence supports that interpretation?

#### Frozen composition

```text
┌──────────┬───────────────────────────────────────────────────────┐
│ LEFT NAV │ Learning Analytics             scope/filter controls │
│          ├───────────────────────────────────────────────────────┤
│          │ LEARNING BRIEF                                      │
│          │                                                       │
│          │ prioritized finding                                  │
│          │ prioritized finding             DOMINANT             │
│          │ prioritized finding                                  │
│          │                                                       │
│          ├───────────────────────────────────────────────────────┤
│          │ supporting evidence panels / drill-down entry points │
└──────────┴───────────────────────────────────────────────────────┘
```

The Learning Brief is the strongest area. Each item should clearly communicate Finding/priority, reason/evidence state, and a user-triggered recommended action where appropriate.

Supporting evidence such as Coverage, Findings Distribution, Recent Learning Evidence, and Scope Activity remains secondary.

#### Dominance rule

> **Interpretation first → evidence second → drill-down third.**

#### Frozen Analytics semantics

Preserve the M14 contract:

- no global mastery score, learner grade, or opaque health index;
- Learning Brief contains at most five prioritized items and may be empty;
- Findings are evidence-backed and deterministic;
- arbitration remains `Never Quizzed → Insufficient Evidence → Stale Evidence → Recovery → Needs Attention → Strength → None`;
- charts support interpretation rather than dominate;
- actions are recommendations and do not silently mutate learning state;
- UI consumes structured results from `src/statistics.py`, `src/analytics.py`, and `src/insights.py` rather than inventing thresholds in presentation code;
- Touched Coverage and Interpretable Coverage remain distinct;
- Collection Content Knowledge and Scope Activity remain distinct.

#### Forbidden composition substitutions

- BI/chart grid first;
- KPI tiles first;
- global mastery/health score;
- Findings table first on the landing page;
- Evidence Landscape replacing the landing composition;
- rainbow severity dashboard;
- “weakness center” framing that misrepresents neutral evidence semantics.

### 6.6 Analytics Pattern — Finding Inbox + Evidence Inspector

**Authority:** `VR-ANALYTICS-002` — `Analytics - Insight.pdf` p3 Variant B.

This is a subordinate PATTERN for Full Findings, Inspect Evidence, and Entry/Scope evidence investigation. It does not replace Analytics Landing.

Composition formula:

```text
Management Rail
      │
      ├── scope/filter controls
      ├── compact brief/status context
      └─────────────┬────────────────────────────
                    │
             FINDINGS TABLE      EVIDENCE INSPECTOR
                dominant              secondary
```

The Findings list/table owns navigation among analytical items. The Evidence Inspector explains the selected Finding using explicit evidence dimensions rather than collapsing them into one score.

### 6.7 Analytics Pattern — Evidence Landscape

**Authority:** `VR-ANALYTICS-003` — `Analytics - Insight.pdf` p4 Variant C.

This is a subordinate PATTERN for Collection-level evidence comparison.

It must maintain the semantic separations:

- Touched Coverage vs Interpretable Coverage;
- Content Knowledge vs Scope Activity;
- evidence state vs current activity;
- interpretation vs raw evidence.

It must not manufacture a Collection score or global mastery metric merely to simplify the visualization.

### 6.8 Minimum M17 Collection Integration — Collections Navigator / Collection Context

**Authority:** Class B, "inherited from the invoking A/B surface" (§ 7.2) — explicitly **not** a full Collection Manager. Design Derivation Record per § 9, since the exact local composition is not fully obvious from P2 alone:

1. **Interaction Mode** — Management.
2. **Parent Pattern** — P2 Table-First Manager, a deliberately lighter instance: a scoped list/selector + read-only detail, not a dense editable table.
3. **Primary User Task** — choose a Collection (or system practice pool) and dispatch into the correct already-accepted workflow (Entries scope, or Review/Study at an exact Card) — not manage or edit the Collection itself.
4. **Spatial Composition** — Management Rail (shared) → left Collections/Pools selector pane, split into explicit "Collections" and "Practice Pools" sections → right read-only detail pane (selected Collection's factual metadata + a compact Card list for normal Collections, or a pool summary for system pools) with handoff actions.
5. **Dominance Rule** — the selector pane and its current selection drive the surface; the detail pane is subordinate factual context, never an editing surface.
6. **Density Rule** — inherits the existing Management Mode density/spacing/typography scale already established by Entries/Today.
7. **Surface Hierarchy** — selector pane uses `surface_secondary` (matching Entries' Scope Pane / Today's Context Rail); detail content uses `surface_primary` on `app_background`, matching existing Management-mode surface roles.
8. **Action Hierarchy** — primary = "Open Entries" / "Open in Study" (accent-primary buttons, matching Entries' Add Entry / Detail Edit treatment); secondary = list selection; no destructive actions exist here (read-only).
9. **Editing Container** — none. This surface has no editor; it is read-only navigation/context only.
10. **Navigation / Chrome Inheritance** — full Management shell retained (Navigation Rail visible); no Study-mode chrome swap on this surface itself — "Open in Study" is what triggers Review's existing chrome swap.
11. **Motion / Transition** — reuses the existing shared `TransitionManager.fade_in` on workspace switch, exactly like Today/Entries; no new motion behavior.
12. **Canonical Visual Relationship** — closest visual authority is `VR-ENTRIES-001`'s Scope Pane + detail vocabulary (scoped list on the left, factual read-only detail on the right); inherits those visual traits rather than inventing new visual language.
13. **Native Human Acceptance Target** — the real native Collections workspace showing a normal-Collection selection (card list, Open Entries, Open in Study), a system-pool selection (Open Entries only), and the resulting Entries/Review handoffs actually landing on the correct scope/Card, in both Light and Dark Mode.

Explicitly out of scope for this surface (belongs to later product work, principally M18): Create/Rename/Delete Collection, editing Card size/description, Entry reordering, drag-and-drop, Card reorganization, Card name editing, Collection bulk management, a direct Collection → Quiz launcher, and the full P2 Collection Manager / P2-P5 Card Organization Workspace.

---

## 7. Screen / Window Coverage Contract

Every user-visible surface in the intended desktop product must be assigned one coverage class.

### 7.1 Coverage classes

**A — Fully Specified / Canonical**

The surface has an approved visual reference. DESIGN controls spatial composition, hierarchy, interaction model, chrome relationship, and canonical reference. The coding agent has implementation-level freedom only.

**B — Pattern-Specified**

The surface has no unique full-screen canonical mockup, but DESIGN explicitly assigns an approved parent pattern and composition formula. The agent may resolve local implementation details but may not redesign the parent pattern.

**C — Agent-Derived**

The surface is intentionally not individually designed because its value/risk does not justify a dedicated mockup. It may be derived only through the formula in §9 and still requires appropriate native acceptance.

**Retired / Integrated**

A legacy Streamlit page/surface is intentionally absorbed into a new desktop workflow or retired. Do not recreate it for page-count parity.

### 7.2 Coverage Matrix — canonical and core workflow surfaces

| Surface | Class | Parent / authority |
|---|---:|---|
| Management Shell / left Navigation Rail | A | `VR-SHELL-001` |
| Today / Home | A | P1 Command Workspace / `VR-TODAY-001` |
| Entries Manager | A | P2 Table-First / `VR-ENTRIES-001` |
| Review Session | A | P3 Immersive Study / `VR-STUDY-001` |
| Quiz Session — primary/self-graded state | A | P3 / `VR-STUDY-001` |
| Quiz Completion / Summary | A | P3 / `VR-STUDY-001` |
| Card Contents / History drawer in Study | A | P3 / `VR-STUDY-001` |
| Flip Card + Filmstrip view | A-secondary | `VR-STUDY-002` |
| Analytics Landing | A | P4 Learning Brief / `VR-ANALYTICS-001` |
| Choose Quiz Type | B | P6 Utility/Study launcher |
| Quick Quiz launch | B | P6 transient launch → P3 |
| MCQ Quiz body | B | P3; central task variant only |
| Matching Quiz body | B | P3; wider task canvas allowed |
| Template-aware self-graded Quiz | B | P3 |
| Quiz recovery/resume | B | P6 recovery → P3 |
| Restart/cancel session confirmation | B | P6 |
| Mistake Book management/browse | B | P2; practice enters P3 |
| Proficient Pool management/browse | B | P2; practice enters P3 |
| Study Collection/Card selector | B | P6 transient utility |
| Minimum M17 Collection integration | B | inherited from invoking A/B surface; not full Collection Manager |

### 7.3 Coverage Matrix — management/editing surfaces

| Surface | Class | Parent / authority |
|---|---:|---|
| Add Entry | B | P5 Focused Editor + P6 |
| Edit Entry | B | P5; container chosen by §10 |
| Template-aware Entry editor | B | P5 |
| Batch Entry edit/action | B | P2 launch + P6/P5 |
| Delete Entry / batch delete | B | P6 destructive confirmation |
| Collection membership edit | B | P2 + focused utility |
| Cross-Card move/change | B | P2 + P6 preview/confirmation |
| Cross-Card history warning | B | P6 warning/confirmation |
| Collection Manager | B | P2 Table-First Manager |
| Card Organization Workspace | B | P2 + P5 |
| Collection Editor | B | P5 |
| Card metadata editor | B | P5 |
| Template Manager | B | P2 |
| Template Editor | B | **P5 independent Focused Workspace by default** |
| Template Field small edit | B | P5 modal when bounded |
| Review Calendar | B | P7 Evidence Browser |
| Card History | B | P7 Evidence Browser |
| Settings | B | P8 Settings Form |
| Appearance Settings | B | P8 |
| Storage / data-location information | B | P8 |
| UI language setting, if retained | B | P8 |

### 7.4 Coverage Matrix — Data Tools / linked source / audio

| Surface | Class | Parent / authority |
|---|---:|---|
| Data Tools hub | B | P6 Utility Workflow |
| Import file selection | B/C | P6 + native file picker |
| Import validation | B | P6 |
| Import Preview | B | `VR-UTILITY-001`: Validate → Preview → Confirm |
| Import confirmation/result | B | P6 |
| Export configuration/result | B | P6 |
| Template definition import/export | B | P6 |
| Backup creation/result | B | P6 |
| Restore selection | B/C | P6 + native file picker |
| Restore Preview | B | P6 preview-first |
| Restore confirmation | B | P6 high-consequence confirmation |
| Linked Source setup/status | B | P6 within Collection context |
| Linked Source refresh progress | B | P6 long-running progress |
| Linked Source Refresh Preview | B | `VR-UTILITY-001` |
| valid/invalid/duplicate inspection | B | compact P2 table inside P6 |
| Confirm append | B | P6 |
| Missing/unreadable source | B | P6 warning/error/recovery |
| Relink source | B | P6 focused recovery |
| Audio Export configuration | B | `VR-UTILITY-001` |
| Card/Collection batch selection | B | P2/P6 |
| voice/repetition configuration | B | P6 focused form |
| destination folder | B/C | P6 + native picker |
| overwrite/conflict choice | B | P6 warning/confirmation |
| audio progress/cancel | B | `VR-UTILITY-001` long-running progress |
| partial success/result/retry | B | `VR-UTILITY-001` partial success |

### 7.5 Coverage Matrix — Analytics supporting surfaces

| Surface | Class | Parent / authority |
|---|---:|---|
| Full Findings | B | P4A / `VR-ANALYTICS-002` |
| Entry evidence drill-down | B | P4A |
| Finding detail | B | P4A |
| Collection evidence comparison | B | P4B / `VR-ANALYTICS-003` |
| Coverage detail | B | P4/P4B |
| Entry Health drill-down | B | P4 → P4A |
| Action/recommendation detail | B | P4 + P6 transient detail |

### 7.6 C — Agent-Derived surfaces

C is intentionally small. Typical C surfaces include:

- native OS file picker;
- context menu;
- simple sort popover;
- simple filter popover;
- tooltip;
- tiny inline validation hint;
- framework-native scrollbar adaptation;
- narrow-window overflow/collapse mechanism that remains bounded by the parent composition.

A C label does not mean “anything goes”. §9 remains mandatory.

### 7.7 Retired / Integrated legacy surfaces

The desktop app is not a one-to-one Streamlit page port.

| Legacy surface | Desktop disposition |
|---|---|
| Streamlit Dashboard | Retire/integrate into Today + Analytics; do not recreate for parity |
| standalone Statistics page | Integrate into Analytics supporting evidence |
| standalone Entry Health presentation | Integrate into Analytics drill-down |
| Review History page | Evolve into Review Calendar / Card History |
| Import / Export page | Evolve into Data Tools / utility workflows |
| Settings / Data page | Normalize into Settings + Data Safety workflows |
| Streamlit sidebar navigation | Retire; replaced by canonical Management Rail |
| `st.session_state` navigation behavior | Retire; transient state belongs to desktop AppState/controllers per M16.1 architecture |

---

## 8. Approved Parent Patterns

The product intentionally uses a small number of reusable composition families.

### P1 — Command Workspace

Authority: Today Command Center.

Use when the primary task is prioritization, resumption, and action triage rather than dense object management.

Formula: Management Rail + dominant command workspace + optional secondary context rail. The current action queue/decision area dominates; metrics remain supportive.

### P2 — Table-First Manager

Authority: Entries Table-First.

Use for Entries, Collections, Templates, pools, and other high-density object management.

Formula: Management Rail + optional scope pane + compact toolbar + dominant structured table/list + subordinate selection detail.

### P3 — Immersive Study

Authority: Immersive Focus.

Use for active Review/Quiz/practice.

Formula: replace Management shell with minimal session bar + one dominant learning task + temporary contextual drawer/overlay only when requested.

### P4 — Learning Brief / Evidence

Authority: Analytics Landing.

Use when interpretation is the first product responsibility.

Formula: scope controls + dominant interpretation/Brief + supporting evidence + explicit drill-down.

#### P4A — Finding Inbox + Evidence Inspector

Use for high-density analytical investigation after the user chooses to inspect evidence. Findings navigation dominates; selected evidence explanation is secondary.

#### P4B — Evidence Landscape

Use for Collection-level evidence comparison while preserving Content Knowledge/Scope Activity and Touched/Interpretable distinctions.

### P5 — Focused Editor

Use for deliberate object editing that should not permanently distort the parent manager.

Forms should be grouped by conceptual task, with clear Save/Cancel semantics and preserved context. Template Editor defaults to an independent focused workspace because template + field definition is complex enough to be a meaningful task. Small bounded field edits may use a modal.

### P6 — Utility Workflow / Dialog

Authority: `VR-UTILITY-001`.

Use for import/export, preview/confirm, destructive actions, linked sources, backup/restore preview, audio export, progress/cancel, partial success, and bounded configuration.

The utility flow must clearly distinguish preview from committed state and communicate safety.

### P7 — Evidence Browser

Use for Review Calendar, Card History, and historical/evidence browsing that is not itself Analytics Landing.

Formula:

> **primary evidence surface + secondary selected-item detail**

The evidence representation dominates; the detail explains selection and does not become a generic dashboard.

### P8 — Settings Form

Use for Appearance, storage information, language/preferences, and other configuration.

Formula: Management Rail + categorized settings structure + comfortable form density. Settings is not a dashboard and should not use KPI/card grids merely for decoration.

---

## 9. Agent-Derived Design Formula

For every C surface — and for any B surface where the exact local composition is not already obvious from its parent pattern — the coding agent must produce a concise **Design Derivation Record** before implementation.

The record must answer all of the following:

1. **Interaction Mode** — Management, Study, Utility/Dialog, or Transient Overlay?
2. **Parent Pattern** — P1–P8 (or explicitly approved subordinate pattern)?
3. **Primary User Task** — what is the single most important task on this surface?
4. **Spatial Composition** — which major regions exist and how are they arranged?
5. **Dominance Rule** — which region/task must visually dominate; what is secondary?
6. **Density Rule** — which mode's density/spacing/typography does it inherit?
7. **Surface Hierarchy** — how do app-background / primary / secondary / sunken / elevated surfaces relate?
8. **Action Hierarchy** — what is primary, secondary, subtle, destructive?
9. **Editing Container** — inline, bottom detail, drawer, modal, or focused editor/workspace, and why?
10. **Navigation / Chrome Inheritance** — what shell is retained/removed?
11. **Motion / Transition** — which approved motion behavior is used, if any?
12. **Canonical Visual Relationship** — which registered visual authority is closest; which visual traits must be inherited?
13. **Native Human Acceptance Target** — what exact real native surface/state must be shown to a human to close visual acceptance?

A surface whose primary task cannot be stated clearly is a warning that too many responsibilities may have been combined.

---

## 10. Editing Container Decision

Do not default every edit to inline controls or permanently embed every form into the main workspace.

Use this decision logic:

```text
Tiny, local, low-risk, quickly reversible edit?
        → inline

Need to keep list/selection context visible while inspecting or making a bounded change?
        → bottom detail or temporary drawer

Focused multi-field edit with clear Save/Cancel and moderate complexity?
        → modal / focused dialog

Complex, multi-field task that deserves sustained attention or its own internal navigation?
        → independent Focused Editor workspace/window
```

Additional frozen decisions:

- Entries remains Table-First; editing does not permanently displace the table.
- Template Editor defaults to an independent Focused Workspace.
- Small Template Field edits may be modal.
- Study context is shown through transient drawers, not permanent inspectors.
- destructive/high-consequence changes use explicit confirmation, not silent inline mutation.

---

## 11. Implementation Freedom Boundary

### 11.1 Frozen Product Design Decisions

A coding agent must not change these without explicit human approval:

- canonical screen composition;
- Management navigation model/orientation;
- selected archetype or parent pattern;
- major regions and their relationship;
- dominant vs supporting region relationship;
- Management Mode vs Study Mode;
- major interaction containers (e.g. transient drawer vs permanent inspector);
- registered canonical visual references and their authority;
- Analytics interpretation/evidence order;
- approved theme architecture;
- frozen learning/product/data-safety semantics.

### 11.2 Adaptable Native Implementation Details

The agent may reasonably choose or adjust:

- exact PySide6 widget classes;
- `QGridLayout` / `QHBoxLayout` / `QVBoxLayout` / splitter or equivalent layout mechanics;
- small pixel/point spacing corrections;
- exact column widths and resize policies;
- exact font fallback under native rendering;
- native scrollbar behavior;
- high-DPI mechanics;
- minimum-size implementation;
- text wrapping/ellipsis behavior;
- small responsive adjustments;
- framework-specific accessibility changes.

These freedoms are bounded by one rule:

> **Native adaptation may alter dimensions and mechanics; it may not substitute composition.**

Examples:

- three-column widths may change; three columns may not become a single-column dashboard at normal desktop width;
- the left rail may become narrower; it may not become top tabs;
- a drawer may change width; it may not become a permanent right inspector;
- table row height may change; the table may not stop being the dominant Entries surface.

### 11.3 Agent-Derived Design

Only surfaces explicitly classified C may receive page-level design decisions from the coding agent. Those decisions must still follow §9 and the applicable parent authority.

### 11.4 Design Change Gate

If an agent believes a frozen design is impractical or inferior under PySide6/native constraints, it must not silently implement a replacement.

Submit a **Design Change Proposal** containing:

- existing design authority;
- problem observed in real native implementation;
- why allowed adaptation is insufficient;
- proposed change;
- affected canonical references/patterns;
- semantic/workflow impact, if any;
- human decision required.

Then stop. No canonical design change is authorized until explicit approval is given and DESIGN authority is updated.

---

## 12. Utility / Dialog Grammar

**Authority:** `VR-UTILITY-001`.

The approved Pattern Board covers Add/Edit, destructive confirmation, Import, Linked Source Refresh Preview, Audio Export, long-running progress, partial success, warning/error/empty/neutral states.

### 12.1 Normal dialogs

- focused, desktop-native proportions;
- primary action normally at bottom-right;
- Cancel/Back predictable and easy to find;
- background remains visible where useful but inactive;
- no new navigation shell inside a dialog.

### 12.2 Destructive actions

- visually and spatially distinct;
- use an outlined danger treatment rather than making destruction the loudest filled default button;
- state consequences precisely: what is changed/deleted, how many items, whether recovery exists;
- never make the destructive action the default keyboard target.

### 12.3 Preview vs commit

Preview must look and behave differently from committed state.

Import preserves:

```text
Upload → Validate → Preview → Confirm → Import
```

Validation and mutation are not collapsed into one opaque action.

Linked Collection Source refresh uses the same preview-before-commit grammar and must communicate:

> Refresh finds appendable new content.

not:

> Make the Collection identical to the source file.

A missing/unreadable linked file must not damage existing Collection/Entry data. Offer relink/replace recovery without rebuilding the Collection.

### 12.4 Long-running work

Show:

- what is happening;
- current progress;
- what has already succeeded;
- whether cancellation is safe;
- what remains after cancellation.

Applies to import analysis, linked-source refresh, backup generation, audio synthesis/export, and comparable operations.

### 12.5 Partial success

Partial success is a first-class result, not total failure.

For Card Audio Export preserve M15.3:

- outcomes are per Card: `succeeded`, `skipped`, `failed`, `unresolved`;
- completed files remain completed;
- retry targets failed/unresolved only;
- overwrite is explicit opt-in, never default;
- Collection export remains one Card → one audio file, never one monolithic Collection file.

### 12.6 State language

Every error answers, in order:

1. what happened;
2. what was not changed;
3. what the user can do next.

Empty, neutral, warning, controlled error, success, and partial-success states must be semantically distinct without relying on color alone.

---

## 13. Theme Architecture

Theme configuration is governed by two orthogonal axes: **Appearance Mode** and **Theme Customization** (authoritative baseline Presets + constrained semantic custom theme editing).

All theme resolution and rendering flows through a single source of truth: `ThemeManager` + semantic `ThemeTokens` + `Preferences`. **No per-view styling or secondary styling systems are permitted.**

### 13.1 Appearance

Supported values:

- `System`;
- `Light`;
- `Dark`.

`System` follows the OS appearance. Light and Dark are explicit overrides. Dark Mode is independently designed, not a naïve inversion.

On desktop, `System` resolves through a live read of the OS's current Light/Dark appearance (Qt's `QStyleHints.colorScheme()`, not a hand-rolled per-platform poll) and re-resolves automatically if the OS appearance changes while the app is running and `System` remains selected; switching to an explicit Light/Dark choice is never silently overridden by a later OS change (M17 Theme Completion).

Theme changes apply live without restart and must not mutate vocabulary data, Quiz state, Review evidence, Analytics, or other learning state.

### 13.2 Presets & Constrained Semantic Theme Customization

The product provides four official authoritative Presets:

1. **Calm Blue / Slate** — default baseline;
2. **Sage / Teal**;
3. **Indigo / Violet**;
4. **Warm Neutral**.

#### Authorized Custom Theme Model (v1.1.0 Phase D Contract)

Rather than exposing unconstrained arbitrary RGB/hex modifications that could break UI contrast or pollute semantic states, the design authority authorizes **constrained semantic theme customization**:

1. **Independent Per-Mode Customization**: Light Mode and Dark Mode can be customized and persisted independently (`preferences.custom_theme.light` and `preferences.custom_theme.dark`), each anchored to an official Preset.
2. **Constrained Customization Dimensions**:
   - **Preset**: Official starting baseline for the mode.
   - **Accent Color**: Interactive emphasis color.
   - **Background**: Application outermost window canvas color.
   - **Surfaces**: Primary content surface and card container color.
   - **Text**: Main typography color.
3. **Automatic Interaction Token Family Derivation**: Customizing an Accent color does not merely replace a single hex; the theme engine automatically derives a complete, internally consistent semantic token family (`accent-primary`, `on-accent-primary`, `accent-hover`, `on-accent-hover`, `accent-pressed`, `on-accent-pressed`, `accent-soft`, `on-accent-soft`, `accent-selected`, `on-accent-selected`, `accent-border`, and `focus-ring`).
4. **Mathematical Contrast Guard**: All custom Accent, Surface, and Text combinations are guarded to strictly achieve WCAG AA ($\ge 4.5:1$) contrast for readable text and text-bearing interactive components. The "Auto Guard" text option automatically resolves optimal readable typography against customized background and surface tones.
5. **Semantic State Immutability**: Business, assessment, and feedback state colors (`success`, `warning`, `danger`, `info`, `quiz-correct`, `quiz-wrong`, and `star`) are immutable invariants. They are **strictly protected from pollution or alteration by custom themes or accents**.

---

## 14. Theme Controls & Customization UX

### 14.1 Quick Theme Control

Compact popover reachable from the Management shell for immediate switching between Appearance modes and baseline Presets:

```text
Appearance          Preset
○ System             ● Calm Blue
○ Light              ○ Sage / Teal
○ Dark               ○ Indigo / Violet
                     ○ Warm Neutral
```

Changes apply immediately. Quick theme controls do not permanently occupy prominent navigation space.

### 14.2 Settings Theme Customization Studio (AG2.0 Experience)

The authoritative configuration surface is located at **Settings → Theme Customization**:

1. **`[Light Mode]` / `[Dark Mode]` Tabbed Workspace**: Two dedicated tabs allowing independent inspection and tuning of Light and Dark themes.
2. **Tab Switch Real-Time Live Preview**: Switching tabs temporarily switches the entire running application into that mode for complete, real-time live preview, **without altering the user's stored `Appearance = System / Light / Dark` preference**.
3. **In-Picker Real-Time Live Preview**: While selecting colors via the native color picker dialog (`QColorDialog`), interactive adjustments (dragging wheels or sliders) immediately preview live across the entire window. Rejecting or canceling the picker reverts the preview to the pre-picker staged state; accepting retains the selection in staged configuration.
4. **Staging vs. Committed Apply**:
   - Changes made in the editor are staged in memory with live visual feedback, but are **never written to disk (`preferences.json`) before `Apply` is clicked**.
   - **Cancel**: Discards all unstaged edits and completely restores the pre-editing theme snapshot.
   - **Apply**: Commits the staged theme to disk preferences, applies it permanently, and records an undo snapshot.
5. **Separated Staged vs. Committed Undo Lifecycle**:
   - **Staged Undo**: Undoing staged operations (e.g. `Reset to Preset` or `Reset All to Default` prior to Apply) restores the in-memory staged snapshot and active tab live preview, **without writing uncommitted changes to disk or modifying committed preferences**.
   - **Committed Undo**: Undoing after an `Apply` restores and persists the previous committed snapshot.
6. **Reset Lifecycle**:
   - **Reset to Preset**: Clears custom color overrides for the active tab's mode, preserving its selected Preset.
   - **Reset All to Default**: Resets both Light and Dark modes to factory default Calm Blue with custom colors cleared.
   - Both Reset actions are immediately undoable via `Undo`.
7. **Non-Modal Contextual Feedback**: Contextual status feedback provides clear, non-intrusive confirmation upon Apply, Reset, Undo, and Cancel actions without interrupting workflow.

Study Mode does not keep a prominent theme selector visible during an active Immersive Focus session.

---

## 15. Semantic Token Architecture

Theme implementation uses semantic tokens, never per-widget hard-coded colors.

### Neutral / surface tokens

`app-background`, `surface-primary`, `surface-secondary`, `surface-sunken`, `text-primary`, `text-secondary`, `text-muted`, `text-disabled`, `border-subtle`, `border-default`, `border-strong`, `overlay`, `shadow`.

### Accent tokens

`accent-primary` / `on-accent-primary`, `accent-hover` / `on-accent-hover`, `accent-pressed` / `on-accent-pressed`, `accent-soft` / `on-accent-soft`, `accent-selected` / `on-accent-selected`, `accent-border`, `focus-ring`.

### Semantic state tokens

`success` / `on-success` / `success-soft`, `warning` / `on-warning` / `warning-soft`, `danger` / `on-danger` / `danger-soft`, `info` / `on-info` / `info-soft`, `quiz-correct` / `on-quiz-correct` / `quiz-correct-soft`, `quiz-wrong` / `on-quiz-wrong` / `quiz-wrong-soft`, `star` / `on-star` (M17 Theme Completion).

`quiz-correct` aliases success and `quiz-wrong` aliases danger. Correct/Wrong are semantic states, not a theme-accent palette.

`star` is the Entries "Starred" affordance's own semantic (filled ★): independent of both accent and `warning`, chosen at a distinctly more yellow hue than `warning`'s brownish amber so a filled star can never be mistaken for a warning badge.

### Interaction-state layer

Hover, pressed, selected, focused, disabled, and read-only are expressed by combining semantic tokens rather than inventing one-off colors per component.

---

## 16. Explicit Foreground Pair Rule

> **Every colored surface must have an explicit, compatible `on-*` foreground token.**

Never use arbitrary combinations such as:

```text
background = accent-primary
text = text-muted
```

Use explicit pairs such as:

```text
background = accent-primary
text = on-accent-primary
```

Current Light accents happen to pair with white `on-accent-primary` and current Dark accents with dark `on-accent-primary`, but this must not become a permanent component assumption. `on-*` remains independently resolvable.

All reusable text-bearing components must explicitly resolve a foreground. Never rely on browser/framework default text color.

This requirement comes from a real hardening defect where unstyled table/status text inherited black on a dark surface, producing approximately 1.29:1 contrast.

---

## 17. Accent vs Semantic Color

Accent may influence:

- primary action;
- selected navigation/row/list item;
- active tab;
- progress;
- focus ring;
- restrained highlights;
- links.

Accent must not redefine semantic meaning.

Do not make Correct purple because the accent is Indigo, Delete teal because the accent is Sage, or Warning blue because the accent is Calm Blue.

Semantic states remain stable across accents and may vary only by Light/Dark for contrast. Meaning must also be expressed by text, icons, border/shape, or another non-color cue.

Sage/Teal and Success are the known nearby-hue risk; re-check them side-by-side if either palette is adjusted.

---

## 18. Frozen Theme Tokens

> **Numeric authority:** values in this section are the latest contrast-hardened values from `VR-CONTRAST-001`. Where an earlier visual-validation artifact differs, these values win.

Exact hex values are current numeric authority. Token names and relationships are the durable design contract. Any future palette refresh must re-pass §19.

### 18.1 Neutral Base

| Token | Light | Dark | Notes |
|---|---|---|---|
| `app-background` | `#F4F3EF` | `#17181A` | outermost shell background |
| `surface-primary` | `#FFFFFF` | `#1E2023` | main content surface |
| `surface-secondary` | `#F8F7F4` | `#232528` | scope panels, headers, hover, sunken toolbars |
| `surface-sunken` | `#ECEAE5` | `#131415` | recessed/inset elements |
| `text-primary` | `#1C1B18` | `#EDECE8` | primary reading text |
| `text-secondary` | `#56534C` | `#B7B4AC` | secondary/supporting text |
| `text-muted` | `#6E6B62` | `#8F8D87` | de-emphasized but readable metadata/captions |
| `text-disabled` | `#938F81` | `#726F67` | non-interactive identifiable text |
| `border-subtle` | `#E8E6E0` | `#2C2E31` | decorative dividers |
| `border-default` | `#D9D6CE` | `#383A3D` | ordinary component borders |
| `border-strong` | `#989486` | `#686B6F` | meaningful UI boundaries |
| `overlay` | `rgba(28,27,24,.45)` | `rgba(0,0,0,.6)` | modal/dialog scrim |
| `shadow` | soft, low-opacity, neutral-hued | soft, low-opacity, neutral-hued | elevation cue; exact native rendering is framework-dependent |

`surface-elevated` currently aliases `surface-primary`, separated by overlay/shadow. Add a distinct tone only if a real elevated surface proves insufficiently distinguishable.

M17 Theme Completion re-hardened Light `text-muted` (`#79766D` -> `#6E6B62`): the prior value's own audited contrast (§ 19) had only been checked against `surface-primary` (4.54:1, PASS), not against the `surface-secondary`/`app-background` pairs the token is actually deployed against in the running app, where it measured 4.24:1 / 4.09:1 -- a real WCAG AA failure. The new value clears 4.5:1 against all three.

### 18.2 Accent Families

| Family | Mode | `accent-primary` | `on-accent-primary` | `accent-hover` | `accent-pressed` | `accent-soft` | `on-accent-soft` | `accent-selected` |
|---|---|---|---|---|---|---|---|---|
| Calm Blue | Light | `#3E6690` | `#FFFFFF` | `#355A80` | `#2C4C6C` | `#E5EDF3` | `#2C4C6C` | `#DCE6EE` |
| Calm Blue | Dark | `#82ACD4` | `#17181A` | `#93B8DA` | `#6E97BC` | `#223140` | `#B7D1E8` | `#283A4B` |
| Sage/Teal | Light | `#4B7767` | `#FFFFFF` | `#40695A` | `#35594C` | `#E6EEEA` | `#35594C` | `#DCE9E2` |
| Sage/Teal | Dark | `#83B09E` | `#17181A` | `#93BAAA` | `#6E9C8B` | `#21302B` | `#B7D8C9` | `#263A32` |
| Indigo/Violet | Light | `#5C5C9B` | `#FFFFFF` | `#4E4E87` | `#414172` | `#EAEAF3` | `#414172` | `#E1E1EE` |
| Indigo/Violet | Dark | `#9C9CCF` | `#17181A` | `#ABABD6` | `#8A8AC0` | `#292A3B` | `#C7C7E5` | `#2F3044` |
| Warm Neutral | Light | `#8C6B4E` | `#FFFFFF` | `#7A5C42` | `#684D37` | `#F1E8DE` | `#684D37` | `#E9DDCE` |
| Warm Neutral | Dark | `#C9A57F` | `#17181A` | `#D3B392` | `#B98F68` | `#322820` | `#E4CBAE` | `#392E24` |

`accent-border` and `focus-ring` reuse `accent-primary` for their mode unless a later audited token revision changes that relationship.

### 18.3 Semantic State Tokens

| Token | Light | Dark |
|---|---|---|
| `success` / `on-success` | `#3B764C` / `#FFFFFF` | `#74B285` / `#17181A` |
| `success-soft` | `#E6F1E7` | `#1F2E23` |
| `warning` / `on-warning` | `#8F631B` / `#FFFFFF` | `#CDA059` / `#17181A` |
| `warning-soft` | `#F6ECDA` | `#332A19` |
| `danger` / `on-danger` | `#B23A3A` / `#FFFFFF` | `#DD8080` / `#17181A` |
| `danger-soft` | `#F7E4E3` | `#3A2323` |
| `info` / `on-info` | `#3F6D82` / `#FFFFFF` | `#7CAFC2` / `#17181A` |
| `info-soft` | `#E4EEF1` | `#21313A` |
| `quiz-correct` / `quiz-correct-soft` | = `success` / `success-soft` | = `success` / `success-soft` |
| `quiz-wrong` / `quiz-wrong-soft` | = `danger` / `danger-soft` | = `danger` / `danger-soft` |
| `star` / `on-star` (M17 Theme Completion) | `#8A6D00` / `#FFFFFF` | `#E8C547` / `#17181A` |

Each semantic solid may serve as foreground on its matching soft background only because that pair is explicitly audited, not because such pairing is assumed universally.

`star` has no `star-soft` background counterpart -- it is deployed as a foreground glyph color (the Entries Star column's filled ★) directly on `surface-primary`/`surface-secondary`, never as a filled chip.

---

## 19. Accessibility & Contrast Rules

Accessibility is a product requirement, not a polish phase.

Hard minimums:

- normal/readable muted text: **4.5:1**;
- large text and meaningful functional boundaries: **3:1**.

Preferred engineering margin where practical:

- ordinary/muted readable text: **≈4.7–5.0:1+**;
- meaningful functional borders/focus/control boundaries: **≈3.2:1+**.

Do not intentionally tune reusable tokens exactly to the threshold.

### Muted vs disabled

Muted content is still intended to be read and must meet 4.5:1. Disabled content communicates non-interactivity and may be weaker (target ≈3:1) but must remain identifiable. They must not share a token.

### Representative hardened audit

| Component | Result | Status |
|---|---:|---|
| Dark table row text (`text-primary` on `surface-primary`) | ~13.8:1 | PASS; previously ~1.29:1 when unstyled |
| Primary button, all 8 Accent × Appearance combos | ~4.9–7.8:1 | PASS |
| Selected nav/row (`on-accent-soft` on `accent-soft`) | ~6.4–9.2:1 | PASS |
| Muted text, Light, vs `app-background`/`surface-primary`/`surface-secondary` (M17 re-audit) | ~4.80 / 5.33 / 4.97:1 | PASS |
| Muted text, Dark, vs `app-background`/`surface-primary`/`surface-secondary` | ~5.35 / 4.92 / 4.63:1 | PASS |
| Disabled text | ~3.0:1 | design-target pass; exempt from AA (WCAG 1.4.3, inactive controls) |
| Success/Warning soft text, Light | ~4.52–4.66:1 | PASS |
| Danger/Info soft text, Light | ~4.78–4.82:1 | PASS |
| semantic soft text, Dark | ~5.17–5.90:1 | PASS |
| `border-strong` vs `surface-primary`, Light/Dark | ~3.04:1 / 3.05:1 | PASS |
| decorative subtle/default dividers | ~1.4–2.2:1 | exempt when purely decorative |
| `quiz-correct` / `quiz-wrong` text | ~5.4–6.6:1 | PASS |
| `star` vs `surface-primary`/`surface-secondary`, Light (M17 Theme Completion) | ~4.92 / 4.59:1 | PASS |
| `star` vs `surface-primary`/`surface-secondary`, Dark | ~9.73 / 9.15:1 | PASS |

All eight Accent × explicit Appearance combinations must remain auditable. `System` inherits Light/Dark behavior and is not a ninth palette.

---

## 20. Dark Mode Rules

Dark Mode preserves hierarchy; it is not an inversion filter.

Especially in Table-First, maintain clear distinction among:

- app background;
- scope pane;
- table;
- selected row;
- bottom detail;
- dialog/elevated surface.

Avoid:

- pure black everywhere;
- implicit/default black text on dark surfaces;
- neon accent borders;
- glowing text;
- gaming aesthetics.

All reusable text-bearing components must explicitly resolve foreground tokens.

---

## 21. Study Mode Color Restraint

In Immersive Focus, accent may appear on:

- progress;
- focus;
- primary action;
- restrained active state.

Accent should not dominate:

- page background;
- large vocabulary content regions;
- answer surfaces;
- full-screen headers.

> Changing Calm Blue to Indigo must not dramatically increase the emotional intensity of the session. Content first, theme second.

Correct/Wrong remain semantic states, not accent-dependent states.

---

## 22. Typography, Spacing, Density, Radius

Durable principles; exact metrics are validated against native PySide6 text/layout behavior rather than copied blindly from browser mockups.

- use a small type hierarchy: page title, section header, body, secondary/metadata;
- body/table text must support long desktop sessions;
- metadata may be smaller and use `text-secondary`/`text-muted`, never `text-disabled` unless truly non-interactive;
- use a compact spacing scale such as 4/8/12/16/24px-class increments rather than arbitrary per-widget values;
- Management tables favor denser row height suited to scanning;
- Study Mode deliberately uses more whitespace and lower density;
- utility dialogs use enough padding for safe comprehension;
- use one restrained small-to-moderate radius language; avoid heavily rounded card-heavy web aesthetics;
- use `border-subtle` decoratively, `border-default` for ordinary edges, `border-strong` only when boundary meaning matters;
- align control heights consistently within each density mode.

Management and Study may differ in density while remaining visually related.

---

## 23. Component / Interaction Rules

- **Navigation:** current location is always distinct; hover and selected states are distinguishable.
- **Buttons:** primary = filled accent; secondary = outlined/neutral; subtle = text/low-emphasis; destructive = outlined danger, not the default filled emphasis.
- **Tables:** header uses secondary surface/text; body rows resolve explicit foreground; selected row uses shared accent-soft selection language plus a non-color cue such as a left-edge marker.
- **Forms:** labels use secondary text; focused inputs use meaningful border/focus treatment; validation and required states use text/icon in addition to color.
- **Inputs:** placeholders use readable muted text, not disabled text.
- **Selection:** nav/table/list/chip selection shares one language: `accent-soft` + compatible foreground + accent marker.
- **Hover:** subtle neutral/accent-soft change; never the only interactivity cue.
- **Focus:** every interactive control has a visible keyboard focus indication.
- **Disabled:** identifiable but clearly non-interactive.
- **Read-only:** fully legible and visually distinct from disabled; use non-editable affordance rather than disabled styling.
- **Loading:** restrained, neutral; do not let decorative spinners dominate Study Mode.
- **Progress:** determinate where the workflow supports meaningful progress.
- **Empty state:** explain what belongs here and provide an appropriate population/recovery action when useful.
- **Warning:** semantic warning treatment, label/icon in addition to color.
- **Error:** what happened / what did not change / what next.
- **Success:** brief confirmation, not celebration.
- **Partial success:** mixed outcome summary, not a single pass/fail badge.

---

## 24. Keyboard & Desktop Behavior

- keyboard focus is always visible;
- Escape closes/cancels the active dialog/overlay where safe;
- Enter triggers only a safe/default action and never accidental destruction;
- destructive actions require deliberate selection and are never the default focus;
- high-frequency Review/Quiz flows remain keyboard-friendly;
- tables and dialogs are usable without mouse-only interaction;
- tab order follows visual/task order;
- selected/active state remains visible when navigating by keyboard.

This section freezes guarantees, not a full shortcut inventory.

---

## 25. Motion & Transition System

Motion explains state change; it does not decorate the application.

Approved motion language:

- workspace navigation: instant or near-instant;
- hover/focus: subtle native feedback;
- modal/popover: restrained native appearance/disappearance;
- transient drawer: short, restrained slide/reveal;
- Flip Card: card flip only inside the optional `VR-STUDY-002` presentation;
- progress/state changes: motion only when it communicates progress or transition;
- theme switching: no decorative full-screen animation required.

Do not introduce dashboard animation, parallax, decorative card movement, or a separate animation language per feature.

---

## 26. Anti-Patterns & Forbidden Composition Substitution

### 26.1 Global anti-patterns

- web landing-page aesthetics;
- mobile UI stretched onto desktop;
- excessive rounded cards;
- decorative gradients;
- neon AI-product styling;
- uncontrolled color proliferation;
- state conveyed by color alone;
- implementation convenience overriding composition authority.

### 26.2 Forbidden Composition Substitution

A **Forbidden Composition Substitution** occurs when required content/functionality still exists but the approved spatial organization is replaced by a different page structure.

Examples:

```text
Today:
left rail + central Command Workspace + right Context Rail
→ top nav + KPI dashboard + full-width table

Entries:
dominant table + bottom detail
→ card gallery + permanent right inspector

Study:
minimal session chrome + centered task
→ management shell + persistent side panels

Analytics:
Learning Brief First
→ chart/KPI dashboard or Findings-table-first landing
```

A composition substitution remains a DESIGN FAIL even if:

- tests are green;
- tokens are correct;
- all required data is present;
- accessibility thresholds pass;
- all buttons exist.

### 26.3 Specific anti-patterns

**Today:** chart-heavy business dashboard; statistics visually dominating Learning Queue; rejected Workspace Dashboard composition.

**Table-First:** detail dominating table; card gallery replacing dense manager; dark surfaces collapsing into one undifferentiated plane.

**Study:** Management Rail visible; persistent Study Cockpit; large accent surfaces; gamification that changes learning meaning.

**Analytics:** global mastery score; opaque learner grade; rainbow Findings; charts dominating interpretation.

**Theme:** accent overriding semantic state; arbitrary foreground/background pairing; naïve Light/Dark inversion; theme changes modifying learning data; ad-hoc per-view styling; unconstrained hex replacements bypassing contrast guards.

---

## 27. Visual Acceptance Contract

### 27.1 Completion equation

For A-class surfaces and any B/C surface with meaningful visual requirements:

```text
DESIGN → Implementation Trace
+ automated/structural conformance
+ real native-window rendering
+ comparison with applicable visual authority
+ explicit human acceptance
= visual design completion
```

Side-by-side comparison is **not** pixel-perfect comparison. Canonical references control composition, regions, dominance, interaction form, chrome relationship, and visual hierarchy. Native Qt may legitimately differ in exact font metrics, spacing, scrollbar geometry, widget mechanics, and other framework details.

The acceptance question is:

> **Is this the approved design expressed as a coherent native implementation?**

not:

> Is every pixel identical to the mockup?

### 27.2 Management Shell acceptance

PASS when the vertical left rail clearly reads as first-level Management navigation and the active workspace dominates.

FAIL when first-level navigation becomes top tabs/top toolbar or the rail is merely decorative.

### 27.3 Today acceptance

Visual invariants:

- persistent left Management Rail at normal desktop width;
- central Command Workspace is largest region;
- right Context Rail is visibly secondary but persistent;
- compact summary remains auxiliary;
- Today's Learning Queue is the central visual anchor;
- Suggested Next Actions remain associated with the command workspace;
- Recent Activity, Collections Needing Attention, and Quick Actions remain in the Context Rail at normal width.

Human acceptance target:

> On first glance, the reviewer should be able to answer “What should I learn/do next?” before interpreting summary metrics.

FAIL if the page reads primarily as a KPI/dashboard or if the right Context Rail has been substituted by stacked bottom panels.

### 27.4 Entries acceptance

Visual invariants:

- Management Rail remains;
- scope is visible when applicable;
- toolbar is compact;
- table dominates the workspace;
- bottom horizontal detail is clearly subordinate;
- selection relationship is obvious;
- normal scanning density is comfortable.

Human acceptance target:

> First glance lands on the Entries table, not on an editor or a collection of cards.

FAIL if detail becomes the page, table dominance is lost, or a card-gallery/right-inspector composition replaces the canonical arrangement.

### 27.5 Immersive Study acceptance

Visual invariants:

- Management navigation is gone;
- session bar is minimal;
- current learning task dominates;
- deliberate whitespace is preserved;
- contextual information is transient;
- Correct/Wrong remains semantic, restrained, non-gamified.

Human acceptance target:

> The reviewer should feel “I am currently doing one learning task,” not “I am still managing the whole app.”

FAIL when persistent sidebars/panels recreate a cockpit or when management density follows the user into Study Mode.

### 27.6 Analytics acceptance

Visual invariants:

- Learning Brief precedes and dominates supporting evidence;
- evidence panels support interpretation;
- drill-down is available but secondary;
- scope filters are clear;
- no global score is introduced.

Human acceptance target:

> The reviewer should understand “What deserves attention now, and why?” before reading charts/tables.

FAIL if charts, KPI tiles, a Finding table, or an opaque score becomes the landing-page authority.

### 27.7 Utility/Dialog acceptance

PASS when preview/commit are unmistakably distinct, destructive consequences are precise, progress/cancellation is understandable, and partial success remains actionable.

FAIL when data mutates before confirmation, destructive actions are ambiguous/default, or partial success is collapsed into total failure.

### 27.8 Theme/accessibility acceptance

PASS only when all supported baseline Presets and custom theme configurations preserve hierarchy, explicit foregrounds, contrast ($\ge 4.5:1$), and semantic-state independence.

Automated contrast checks are necessary but do not replace viewing representative real native surfaces in Light and Dark.

---

## 28. Required AI Coding Trace Formats

The format may be compact, but the information is mandatory.

### 28.1 Before/during implementation — DESIGN → Implementation Trace

Example:

| DESIGN authority | Requirement | Concrete implementation decision | Visual reference |
|---|---|---|---|
| Management Shell | vertical left first-level navigation | persistent left rail; active workspace uses shared selected state | `VR-SHELL-001` |
| Today | central Command Workspace dominates | main region receives primary width/visual weight | `VR-TODAY-001` |
| Today | persistent right Context Rail | Recent Activity / attention / quick actions kept in secondary right region | `VR-TODAY-001` |
| Study | Management chrome disappears | AppState Study Mode swaps shell to minimal session bar | `VR-STUDY-001` |

### 28.2 Delivery — Implemented UI → DESIGN Authority

Example:

| Implemented decision | DESIGN authority | Strict | Adapted | Deferred |
|---|---|---:|---:|---:|
| vertical Management Rail | §5 / `VR-SHELL-001` | ✓ | | |
| Today Context Rail | §6.1 / `VR-TODAY-001` | ✓ | | |
| exact column width | §11 native freedom | | ✓ | |
| narrow-window collapse | §6.1 allowed adaptation | | ✓ | |
| additional animation | §25 | | | ✓ |

The delivery report must also state the visual evidence level from §2.

---

## 29. Open Questions / Framework-Dependent Notes

These are implementation details or future validation questions. They do not weaken frozen decisions above.

- PySide6 is selected and complete through M16.1; exact widget choices remain implementation details.
- exact typography point sizes, line heights, and fallback chain require native validation;
- exact shadow/elevation blur/spread/opacity remains native-framework-dependent;
- `surface-elevated` remains aliased to `surface-primary` unless real native use proves insufficient;
- complete keyboard shortcut inventory is deferred, while §24 guarantees remain frozen;
- exact minimum supported desktop composition width and responsive breakpoints must be validated in real native windows; responsive behavior may not justify changing normal-width canonical composition;
- packaging-specific `System` appearance behavior belongs to packaging/platform integration;
- canonical visual-reference files should ultimately be stored in a durable shared/repository-accessible location; until then, §3.4 applies whenever an agent cannot access them.

---

## 30. Relationship to PySide6 Architecture

PySide6 is the selected native framework. Architecture/state boundaries live in [`docs/design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md`](docs/design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md).

This DESIGN governs **what the product/UI must become**, not **which Qt class must implement it**.

Controllers/AppState own transient desktop state according to the architecture contract. Durable learning/domain state stays in the reusable core/SQLite. Views/controllers do not reproduce domain SQL or business rules merely to make a UI easier to implement.

A framework implementation choice cannot override a frozen composition decision.

---

## 31. Document Provenance

This design authority consolidates:

1. the existing repository `DESIGN.md` product/UI baseline;
2. the approved grayscale A–F exploration for Today/Home, Entries & Collections, Review/Quiz, and Analytics;
3. user-selected canonical variants:
   - Today → Command Center;
   - Entries → Table-First;
   - Review/Quiz → Immersive Focus;
   - Review/Quiz alternate → Flip Card + Filmstrip;
   - Analytics → Learning Brief First;
4. the approved Utility / Dialog Pattern Board;
5. Theme Architecture Visual Validation;
6. Theme Contrast & Accessibility Hardening, which has numeric precedence over earlier theme values;
7. the M16 architecture/closure evidence demonstrating that structural correctness and real-window visual correctness are distinct forms of evidence;
8. the later AI-coding failure in which Today was implemented first as generic Qt widgets and then as top navigation + KPI tiles + a full-width management table despite claiming `DESIGN.md` adherence;
9. the resulting design-governance decisions: canonical composition authority, full surface coverage classification, derivation formulas, implementation-freedom boundaries, forward/reverse traceability, and mandatory human native-window acceptance.

The purpose of recording the failure mode is not historical commentary. It explains why this contract explicitly distinguishes **content hierarchy** from **spatial composition**, and **structural conformance** from **visual acceptance**.

---

## 32. Final Design Governance Rule

When a future implementation choice is ambiguous, resolve it in this order:

```text
1. Product / semantic truth
2. Coverage class
3. Registered canonical or parent visual authority
4. Frozen composition / dominance / chrome rules
5. Approved reusable pattern
6. Agent derivation formula
7. Native implementation freedom
```

Never reverse this order for convenience.

> **The coding agent implements the approved product design. It does not become the product designer merely because a screen has not yet been coded.**
