# Vocabulary App · Desktop Design Contract (`DESIGN.md`)

Status: **Frozen UI Design Baseline — Milestone 16 In Progress**

This document freezes the Milestone 16 UI/design baseline. It is not a
statement that Milestone 16 itself is complete — the desktop framework
decision, controller/view-state boundaries, and minimal desktop shell remain
open. See `ROADMAP.md` § Milestone 16 and `PROJECT_STATUS.md` for the
authoritative current lifecycle state.

This document is the authoritative product/UI contract for the native desktop
migration. It consolidates and freezes the Milestone 16 design decisions:
information architecture, interaction grammar, theme architecture, semantic
tokens, accessibility rules, and visual acceptance criteria.

It is a **design-contract consolidation**, not a new design exploration. It
does not implement UI code, does not start the minimal desktop shell, and does
not change application code, database schema, or learning semantics.

## 1. Purpose and How to Use This Document

This document tells a future contributor (human or coding agent):

- what the desktop product should feel like;
- how the main workflows are structured;
- which visual and interaction principles are frozen;
- which semantics must not be changed by UI implementation;
- what constitutes a visual or interaction regression; and
- where implementation freedom still exists.

It is **not**:

- a component-by-component coding tutorial;
- a framework construction manual;
- a duplicate of [ROADMAP.md](ROADMAP.md) or [PROJECT_STATUS.md](PROJECT_STATUS.md);
- a restatement of every historical design conversation.

Read this document alongside:

- [ARCHITECTURE.md](ARCHITECTURE.md) — module and layer boundaries;
- [docs/migration/DESKTOP_MIGRATION_PLAN.md](docs/migration/DESKTOP_MIGRATION_PLAN.md) — migration strategy and phasing;
- [docs/design/M14_SEMANTIC_CONTRACT.md](docs/design/M14_SEMANTIC_CONTRACT.md) — Learning Analytics semantics referenced by Analytics;
- [docs/design/M15_1_SPEECH_SEMANTIC_CONTRACT.md](docs/design/M15_1_SPEECH_SEMANTIC_CONTRACT.md) and
  [docs/design/M15_3_BATCH_EXPORT_CONTRACT.md](docs/design/M15_3_BATCH_EXPORT_CONTRACT.md) — Audio Export semantics referenced by the Utility grammar.

`DESIGN.md` governs product/UI structure. It does not override the semantic
contracts above; where a UI rule and a semantic contract could conflict, the
semantic contract wins and the UI must be adjusted, not the other way around.

## 2. Governing Product Principle

> **Replace the UI layer, preserve the learning engine.**

The desktop UI may reorganize the current Streamlit-era pages and interactions
into more coherent desktop workflows. It must **not** mechanically reproduce
the old Streamlit page structure, and it must **not** silently change frozen
learning semantics, evidence semantics, data meanings, or safety behavior
(see [ARCHITECTURE.md § Learning Completion Semantics](ARCHITECTURE.md) and
the M14 contract).

The desktop product should feel:

> **Efficient when managing, quiet when studying, explanatory when analyzing,
> and precise when handling data.**

The theme system personalizes that product without changing its identity.

## 3. Macro Interaction Model

The product has two interaction modes. They belong to the same product but do
not share identical density or chrome.

### 3.1 Management Mode

Used for: Today / Home, Entries, Collections, Templates, Analytics, Data Tools
(Import/Export, Backup/Restore), Settings, and other organization / inspection
/ utility workflows.

Characteristics:

- the normal desktop shell (navigation, chrome) is visible;
- medium-to-high information density is acceptable;
- tables, filters, toolbars, dialogs, status indicators, and batch operations
  are first-class patterns;
- the UI should feel efficient, desktop-native, and calm.

### 3.2 Study Mode

Used for: Review, Quiz, Mistake Book practice, and Proficient Pool practice.

Characteristics:

- normal management navigation largely disappears;
- visual chrome is reduced to a minimal session bar;
- one learning task is prioritized at a time;
- accent usage is restrained (see § 14);
- Study Mode should feel quieter than Management Mode.

## 4. Frozen Core UI Archetypes

The following structural decisions are approved and frozen. Do not reopen
them unless the repository reveals a direct semantic conflict; if one is
found, record it under § 20 rather than silently redesigning.

| Screen | Frozen direction |
|---|---|
| Today / Home | **Command Center** — 学习指挥中心 |
| Entries & Collections | **Table-First** — 列表 + 底部详情 |
| Review / Quiz | **Immersive Focus** — primary Study Mode design language |
| Review / Quiz secondary view | **Flip Card + Filmstrip** — functional secondary view, does not govern the global design system |
| Analytics | **Learning Brief First** |
| Utility / Dialog | Pattern Board direction (§ 5) — approved, no further exploration needed |

### 4.1 Today / Home — Command Center

Purpose: tell the user what matters today, what can be resumed, and what the
next useful learning action is.

Hierarchy (top to bottom, priority order):

1. compact summary;
2. **Today's Learning Queue** as the dominant area;
3. suggested next actions;
4. recent activity / Collections needing attention;
5. quick actions.

Rules:

- the Learning Queue must have greater visual weight than statistics;
- the page must support quick resumption and task triage;
- it must not become a chart-heavy business dashboard — analytics belongs in
  Analytics, not on the Home screen;
- Today's Card-learning activity and summaries must reflect factual completed
  Card-scoped Quiz history (per `src/learning_workflow.py` and the Learning
  Completion Semantics in ARCHITECTURE.md), not legacy Review-schedule state.

### 4.2 Entries & Collections — Table-First

Purpose: efficiently browse, filter, compare, organize, and edit large numbers
of Entries.

Hierarchy:

1. scope / Collection navigation;
2. toolbar with search, filter, sort, and batch actions;
3. large dense Entries table as the dominant visual area;
4. selected Entry detail in a horizontal bottom detail region.

Rules:

- the table is the visual authority;
- the bottom detail area supports the table and must not overpower it;
- editing may use dialogs or focused editors where appropriate;
- the layout must remain suitable for high-frequency desktop data management;
- multi-selection and batch actions (delete, Starred, Proficient Pool) remain
  first-class, consistent with current Entry batch-action capability.

Dark Mode must preserve clear separation between: app background, scope
navigation, table, selected row, bottom detail region, and overlays/dialogs
(see § 13).

### 4.3 Review / Quiz — Immersive Focus

This is the global design authority for Study Mode.

Characteristics:

- normal application navigation largely disappears during an active session;
- a minimal session bar remains;
- generous whitespace; one learning task is presented at a time;
- optional context (e.g. Card history) is available through temporary drawers
  or lightweight controls, not persistent chrome;
- dense management UI is not carried into an active learning session.

Frozen learning semantic (must not be silently changed by UI work):

> Reviewing prepares the Card. A completed Card-scoped Quiz remains the
> authoritative Card learning/review completion event. Browsing/review
> exposure alone must not visually imply Card completion.

Additional rules:

- Quiz feedback must remain clear but non-gamified;
- do not revive legacy `Again / Hard / Good / Easy` scheduling semantics
  unless separately authorized — this UI rule mirrors the frozen product
  semantic in [ARCHITECTURE.md](ARCHITECTURE.md) and the Desktop Migration
  Plan (§ 12, Review) that independent manual scheduling and legacy SRS rating
  are retired from the active learning model.

#### Secondary Study View: Flip Card + Filmstrip

A valid optional Review/Quiz presentation mode, using front/back card
interaction, a compact filmstrip progress strip, and horizontal position
awareness.

> Flip Card + Filmstrip is a secondary, user-selectable view. It does not
> define the global design system. The application-wide Study Mode language
> remains governed by Immersive Focus.

### 4.4 Analytics — Learning Brief First

Purpose: tell the user what deserves attention now, why, and what evidence
supports that interpretation.

Hierarchy:

1. Learning Brief;
2. supporting evidence;
3. drill-down / Full Findings.

This hierarchy mirrors the Desktop Migration Plan's preferred Analytics
information order: `What matters now -> why it was flagged -> supporting
evidence -> deeper details -> useful next action`.

The desktop Analytics experience must preserve the frozen M14 semantics (see
[M14 Semantic Contract](docs/design/M14_SEMANTIC_CONTRACT.md)):

- no global mastery score, learner grade, or opaque health index;
- the Learning Brief contains at most five prioritized items and may be
  empty;
- Findings are evidence-backed and deterministic, using the frozen
  arbitration order (`Never Quizzed`, `Insufficient Evidence`, `Stale
  Evidence`, `Recovery`, `Needs Attention`, `Strength`, `None`);
- charts support interpretation rather than dominate the page;
- actions remain user-triggered recommendations — Analytics does not silently
  mutate Entry status, pool membership, due dates, Collection membership,
  Card order, or start a Quiz;
- the UI consumes structured analytical results from `src/statistics.py` /
  `src/analytics.py` / `src/insights.py` rather than inventing thresholds or
  classifications in presentation code.

The UI must preserve the distinctions between: factual **Statistics**,
neutral **Analytics**, **Findings/actions**, and the **Learning Brief**; and
between **Touched Coverage**, **Interpretable Coverage**, **Collection
Content Knowledge**, and **Scope Activity**. Do not merge these into a single
"mastery" metric or a single generic chart gallery.

## 5. Utility / Dialog Grammar

A coherent desktop interaction grammar covers: Add/Edit Entry, destructive
confirmation, Import, Linked Source refresh preview, Audio Export, progress /
cancellation, partial success, warning, error, empty state, and neutral
information state. This grammar direction (the Pattern Board) is approved; no
further exploration is required.

### Normal dialogs

- focused, desktop-native proportions;
- primary action normally at bottom-right;
- Cancel / Back predictable and easy to find;
- background UI may remain visible but inactive.

### Destructive actions

- visually and spatially distinct — an outlined danger treatment, not a
  filled default-looking button (see § 16, Buttons);
- do not use vague "Are you sure?" wording — state consequences precisely
  (what is deleted, how many items, whether it is recoverable);
- destructive action is never the default focus/keyboard target (see § 17).

### Preview vs. commit

Preview must look and behave differently from committed state (e.g. a
dashed/outlined preview treatment vs. a solid committed treatment).

Import preserves the existing product flow, unchanged by the UI layer:

```text
Upload -> Validate -> Preview -> Confirm -> Import
```

Validation and data mutation are never collapsed into one opaque action.

Linked Collection Source refresh follows the same preview-before-commit
grammar and must communicate:

> Refresh finds appendable new content.

not:

> Make the Collection identical to the source file.

An unavailable, moved, or unreadable linked file must not damage the
Collection or existing Entries; the UI must offer replace/relink without
requiring the Collection to be rebuilt (per Desktop Migration Plan § 17).

### Long-running work

Show: what is happening; current progress; what has already succeeded;
whether cancellation is safe; and what remains after cancellation. Applies to
imports, linked-file refresh analysis, backup generation, and audio
synthesis/export.

### Partial success

Partial success is a valid first-class result, not total failure. For Audio
Export specifically, preserve the frozen M15.3 semantics:

- outcomes are per-Card and independent: `succeeded`, `skipped`, `failed`, or
  `unresolved`;
- completed outputs remain completed;
- retry targets failed/unresolved items only, not a restart of the whole
  batch;
- overwrite remains an explicit choice, never the default conflict policy;
- the result is always **one Card → one audio file** — a Collection export is
  never a single combined file.

### Errors

Every error answers, in this order: (1) what happened, (2) what was not
changed, (3) what the user can do next.

## 6. Theme Architecture

The desktop product supports a user-selectable theme system with two
independent axes.

### 6.1 Appearance

Supported values: `System`, `Light`, `Dark`.

- `System` follows the OS Light/Dark preference.
- `Light` and `Dark` are explicit user overrides.
- **Dark Mode is independently designed and is not a simple inversion of
  Light Mode** (see § 13).
- Theme switching applies without an application restart.
- Theme preference is UI/application preference state and must not mutate
  vocabulary data, Quiz state, review evidence, analytics, or other learning
  state.

### 6.2 Accent Families

Four curated accent families, all supported, all first-class:

1. **Calm Blue / Slate** — default
2. **Sage / Teal**
3. **Indigo / Violet**
4. **Warm Neutral**

They are four moods of the same product, not four independent skins. Do not
allow arbitrary custom RGB/hex editing unless a later milestone explicitly
authorizes it.

## 7. Theme Controls

Two access levels.

**Quick Theme Control** — a compact popover reachable from the normal desktop
shell:

```text
Appearance          Accent
○ System             ● Calm Blue
○ Light               ○ Sage / Teal
○ Dark                ○ Indigo / Violet
                      ○ Warm Neutral
```

Changes apply immediately. Theme controls do not permanently occupy main
navigation space.

**Settings → Appearance** — the full authoritative configuration surface for
Appearance and Accent. Study Mode does not keep a prominent theme selector
visible during an active Immersive Focus session (see § 14).

## 8. Semantic Token Architecture

Theme implementation uses semantic tokens, never per-widget hard-coded
colors. Four token layers, kept separate:

**Neutral / surface tokens** — `app-background`, `surface-primary`,
`surface-secondary`, `surface-sunken`, `text-primary`, `text-secondary`,
`text-muted`, `text-disabled`, `border-subtle`, `border-default`,
`border-strong`, `overlay`, `shadow`.

**Accent tokens** — `accent-primary` / `on-accent-primary`, `accent-hover` /
`on-accent-hover`, `accent-pressed` / `on-accent-pressed`, `accent-soft` /
`on-accent-soft`, `accent-selected` / `on-accent-selected`, `accent-border`,
`focus-ring`.

**Semantic state tokens** — `success` / `on-success` / `success-soft`,
`warning` / `on-warning` / `warning-soft`, `danger` / `on-danger` /
`danger-soft`, `info` / `on-info` / `info-soft`, `quiz-correct` /
`on-quiz-correct` / `quiz-correct-soft`, `quiz-wrong` / `on-quiz-wrong` /
`quiz-wrong-soft`.

`quiz-correct` and `quiz-wrong` are documented aliases of the `success` and
`danger` families rather than independently invented colors — Correct/Wrong
remain semantic states, not a separate Study Mode palette (see § 11.3).

**Interaction-state layer** — hover, pressed, selected, focused, disabled,
and read-only are expressed by combining the tokens above (e.g. selected row
= `accent-soft` background + `on-accent-soft` text + `accent-primary` left
border), never by inventing new one-off colors per component.

## 9. Explicit Foreground Pair Rule

Freeze this rule:

> **Every colored surface must have an explicit, compatible `on-*`
> foreground token.**

Never allow ad hoc combinations such as `background = accent-primary; text =
text-muted`. Always use explicit pairs: `background = accent-primary; text =
on-accent-primary`.

Current approved values happen to allow all Light accent-primary surfaces to
share a white `on-accent-primary`, and all Dark accent-primary surfaces to
share a dark `on-accent-primary` (see § 11.2). This may be implemented
through aliasing/inheritance for efficiency, but:

> Do not encode "Light accent always means white text" or "Dark accent
> always means dark text" as a permanent component assumption.

The semantic `on-accent-primary` token must remain an explicit, independently
resolvable token so a future palette adjustment can change it safely without
touching component code.

This rule was added specifically because the Milestone 16 contrast-hardening
audit found real components (unstyled table rows and status pills) that
silently inherited a browser-default black foreground instead of resolving an
explicit token, producing unreadable text in Dark Mode (1.29:1 measured
contrast). See § 11.4.

## 10. Accent vs. Semantic Color

Freeze this distinction.

Accent **may** influence: primary action, selected navigation, selected row
emphasis, active tab, progress, focus ring, restrained highlights, and links.

Accent **must not** redefine semantic meaning. Do not make Correct purple
because the theme is Indigo, Delete teal because the theme is Sage, or
Warning blue because the theme is Calm Blue.

Semantic states (`success`, `warning`, `danger`/error, `info`,
`quiz-correct`, `quiz-wrong`) remain semantically stable across all four
accent families. They may have separate Light/Dark values for contrast, but
never separate per-accent values. Semantic meaning is never communicated by
color alone — pair it with labels, icons, borders, or typography.

**Sage/Teal vs. Success collision** is the one flagged per-accent risk: the
Sage accent and the semantic success green sit close in hue. Both were
verified side by side (accent swatch next to a success chip, same page) and
remain distinguishable by hue offset (~21°) and saturation/lightness
difference; this pairing should get a real-use visual check again if either
palette is ever adjusted.

## 11. Frozen Theme Tokens

> **Authority note:** these are the latest, contrast-hardened values from the
> Milestone 16 Theme Contrast & Accessibility Hardening pass. Where any
> earlier design artifact (including the initial Theme Architecture Visual
> Validation pass) recorded different numeric values, **these values win.**
> Do not revert to earlier, pre-hardening values.

Exact hex values are the current numeric authority; the token *names* and
*relationships* are the durable contract. A future palette refresh may adjust
hex values as long as it re-passes the audit in § 12.

### 11.1 Neutral Base

| Token | Light | Dark | Notes |
|---|---|---|---|
| `app-background` | `#F4F3EF` | `#17181A` | outermost shell background |
| `surface-primary` | `#FFFFFF` | `#1E2023` | main content surface (tables, cards, dialogs) |
| `surface-secondary` | `#F8F7F4` | `#232528` | scope panels, headers, hover, sunken toolbars |
| `surface-sunken` | `#ECEAE5` | `#131415` | recessed/inset elements (reserved; not yet exercised in a shipped component) |
| `text-primary` | `#1C1B18` | `#EDECE8` | primary reading text |
| `text-secondary` | `#56534C` | `#B7B4AC` | secondary/supporting text |
| `text-muted` | `#79766D` | `#8F8D87` | de-emphasized but still-read text (captions, metadata) |
| `text-disabled` | `#938F81` | `#726F67` | non-interactive, identifiable-only text |
| `border-subtle` | `#E8E6E0` | `#2C2E31` | decorative dividers, no contrast requirement |
| `border-default` | `#D9D6CE` | `#383A3D` | ordinary component borders |
| `border-strong` | `#989486` | `#686B6F` | meaningful UI boundaries (inputs, disabled-control outlines) |
| `overlay` | `rgba(28,27,24,.45)` | `rgba(0,0,0,.6)` | modal/dialog scrim |
| `shadow` | soft, low-opacity, neutral-hued | soft, low-opacity, neutral-hued | elevation cue for dialogs/popovers; exact blur/spread is framework-dependent (§ 20) |

`surface-elevated` (listed as a conceptual token category) is currently
aliased to `surface-primary` for dialogs/popovers, differentiated from the
page by `overlay` + `shadow` rather than a distinct flat color. If a future
pass finds this insufficient for a specific elevated surface, add a fifth
distinct tone rather than reusing `surface-primary` with an ad hoc shade.

### 11.2 Accent Families (all values include explicit `on-*` pairs)

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

`accent-border` and `focus-ring` reuse `accent-primary` for their respective
mode. `on-accent-primary` and `on-accent-hover`/`on-accent-pressed` share one
value per Appearance (white in Light, dark in Dark) because every accent
family was verified to keep enough contrast in both directions; this is an
allowed aliasing per § 9, not a hard-coded assumption.

### 11.3 Semantic State Tokens (independent of accent, per § 10)

| Token | Light | Dark |
|---|---|---|
| `success` / `on-success` (solid) | `#3B764C` / `#FFFFFF` | `#74B285` / `#17181A` |
| `success-soft` | `#E6F1E7` | `#1F2E23` |
| `warning` / `on-warning` (solid) | `#8F631B` / `#FFFFFF` | `#CDA059` / `#17181A` |
| `warning-soft` | `#F6ECDA` | `#332A19` |
| `danger` / `on-danger` (solid) | `#B23A3A` / `#FFFFFF` | `#DD8080` / `#17181A` |
| `danger-soft` | `#F7E4E3` | `#3A2323` |
| `info` / `on-info` (solid) | `#3F6D82` / `#FFFFFF` | `#7CAFC2` / `#17181A` |
| `info-soft` | `#E4EEF1` | `#21313A` |
| `quiz-correct` / `quiz-correct-soft` | = `success` / `success-soft` | = `success` / `success-soft` |
| `quiz-wrong` / `quiz-wrong-soft` | = `danger` / `danger-soft` | = `danger` / `danger-soft` |

Each solid semantic color also serves as its own soft-background foreground
(e.g. `success` text on `success-soft` background) — this pairing is audited
in § 12, not assumed.

### 11.4 Bug Found and Fixed During Hardening

The contrast audit found that reusable table-row and status-pill components
had no explicit `color` declaration and silently inherited the browser
default (black), producing 1.29:1 contrast on a Dark Mode row — effectively
invisible text. This is exactly the failure § 9's foreground-pair rule exists
to prevent. The fix (explicit `text-primary` / `text-secondary` resolution on
every reusable text-bearing component) is now a frozen implementation
requirement, not just a styling preference — see § 13.

## 12. Accessibility & Contrast Rules

Accessibility is a product rule, not an optional polish step.

Hard minimums:

- normal text / readable muted text: **4.5:1**
- large text and meaningful UI boundaries: **3:1**

> WCAG thresholds are minimum acceptance boundaries, not preferred targets.

Recommended design targets, left as engineering margin where practical:
normal/muted readable text **≈4.7–5.0:1+**; meaningful control/focus
boundaries **≈3.2:1+**. Do not deliberately tune a reusable token to sit
exactly on the acceptance threshold.

### Muted vs. Disabled

`Muted` content is still intended to be read and must hit the 4.5:1 minimum
(e.g. `text-muted` on `surface-primary`/`surface-secondary`). `Disabled`
communicates non-interactivity; it may be visually weaker (Vocabulary App
targets ≈3:1) but must remain identifiable, never invisible. They are not the
same visual state and must not share a token.

### Contrast audit (representative, computed via WCAG relative-luminance
formulas; full pairwise audit covers all 8 Accent × Appearance combinations)

| Component | Foreground | Background | Result | Status |
|---|---|---|---|---|
| Table row text (all themes, Dark) | `text-primary` | `surface-primary` | 13.8:1 | PASS (was 1.29:1 unstyled — fixed, § 11.4) |
| Primary button (8 combos) | `on-accent-primary` | `accent-primary` | 4.9–7.8:1 | PASS |
| Selected nav / selected row (8 combos) | `on-accent-soft` | `accent-soft` | 6.4–9.2:1 | PASS |
| Muted text, Light | `text-muted` | `surface-primary`/`secondary` | 4.54–4.60:1 | PASS (was 3.31–3.54:1 — corrected) |
| Muted text, Dark | `text-muted` | `surface-primary`/`secondary` | 4.61–4.63:1 | PASS (was 3.90–4.15:1 — corrected) |
| Disabled text | `text-disabled` | `surface-secondary` | ≈3.0:1 | Design-target pass (informational, not full AA) |
| Success/Warning soft-text, Light | `success`/`warning` | respective `*-soft` | 4.52–4.66:1 | PASS (was 4.25/4.31:1 — corrected) |
| Danger/Info soft-text, Light | `danger`/`info` | respective `*-soft` | 4.78–4.82:1 | PASS (unchanged) |
| All semantic soft-text, Dark | — | — | 5.17–5.90:1 | PASS (unchanged) |
| `border-strong` vs `surface-primary`, Light/Dark | `border-strong` | `surface-primary` | 3.04:1 / 3.05:1 | PASS (was 2.15:1 / 1.99:1 — corrected) |
| Decorative dividers (`border-subtle`/`border-default`) | — | — | 1.4–2.2:1 | Exempt — decorative only, no functional-boundary meaning |
| `quiz-correct`/`quiz-wrong` text | `success`/`danger` | `surface-primary` | 5.4–6.6:1 | PASS |

## 13. Dark Mode Rules

Dark Mode preserves hierarchy. Especially for Table-First, keep clear
distinction among: app background, scope pane, table, selected row, bottom
detail, and dialog/elevated surface.

Avoid:

- pure black everywhere;
- black/default browser text on dark surfaces;
- neon accent borders;
- glowing text;
- gaming aesthetics.

**All reusable text-bearing components must explicitly resolve a foreground
token. Do not rely on browser/framework default foreground color** — this is
a hard requirement, not a suggestion, following the real bug found in § 11.4.

Dark Mode is a genuinely separate design, not an inverted Light Mode: its
neutral scale, semantic colors, and accent tones were independently tuned
(e.g. accent hues are lightened rather than kept at their Light-mode
lightness, and semantic solids pair with dark rather than white text) so a
naive `1 - lightness` inversion of the Light tokens would fail this contract.

## 14. Study Mode Color Restraint

Strong design rule. In Immersive Focus, accent may appear on: progress,
focus, primary action, and restrained active state.

Accent should **not** dominate: page background, vocabulary content surface,
answer area, large card regions, or full-screen headers.

> Changing from Calm Blue to Indigo should not dramatically increase the
> emotional intensity of the session. Content first, theme second.

Correct/Wrong remain semantic states (`quiz-correct`/`quiz-wrong`), never
recolored by accent (per § 10).

## 15. Typography, Spacing, Density, Radius

Durable principles (exact pixel/pt values are framework-dependent, see § 20,
and should be finalized against the chosen desktop framework's native text
metrics rather than a browser-based mockup):

- **Typography hierarchy**: a small number of weight/size steps (e.g.
  page title, section header, body, secondary/metadata) is sufficient; avoid
  inventing a large type scale.
- **Body/readability**: body and table text sized for comfortable long-session
  desktop reading, not web-page-dense or mobile-large.
- **Compact metadata**: secondary text (counts, timestamps, tags) may run
  smaller and use `text-secondary`/`text-muted`, never `text-disabled` unless
  the item is genuinely non-interactive.
- **Spacing scale**: a small consistent step scale (e.g. 4/8/12/16/24px-class
  increments) applied uniformly rather than ad hoc per-component spacing.
- **Table density**: Management Mode tables (Table-First) favor a denser row
  height suited to scanning many Entries; Study Mode avoids table density
  entirely.
- **Dialog spacing**: generous enough padding to read destructive/warning
  copy comfortably; dialogs are not shrunk to table density.
- **Corner radius**: a single small-to-moderate radius used consistently
  (calm, desktop-native — not the heavily rounded, card-heavy web-app look
  rejected in § 18).
- **Borders/dividers**: `border-subtle` for decorative separation,
  `border-default` for ordinary component edges, `border-strong` only where
  the boundary carries meaning (§ 12).
- **Control height**: consistent control height across buttons/inputs within
  a density mode so toolbars and forms align predictably.

Management Mode may be denser than Study Mode; keep the system coherent
without forcing identical density everywhere.

## 16. Component / Interaction Rules

Reusable behavior, described as product behavior and visual expectation, not
framework construction steps:

- **Navigation**: current location always visually distinct (accent-soft
  selection, per § 8); hover and selected states are visually distinguishable
  from each other, never collapsed into one treatment.
- **Buttons**: primary (filled accent), secondary (outlined/neutral), subtle
  (text-only), destructive (outlined danger, not filled) — see § 5 for why
  destructive stays outlined rather than becoming the visually loudest,
  default-focus button.
- **Tables**: header row uses `surface-secondary` + `text-secondary`; body
  rows always resolve an explicit foreground (§ 13); selected row combines
  `accent-soft` background, `on-accent-soft` text, and an `accent-primary`
  left-edge marker so selection reads correctly even for colorblind users
  (shape + color, not color alone).
- **Forms**: labels use `text-secondary`; inputs use `border-default` at
  rest and `border-strong`/`accent-border` on focus; required-field and
  validation-error states are marked by icon/label in addition to color.
- **Dialogs**: see § 5.
- **Inputs**: placeholder text uses `text-muted` (still legible), not
  `text-disabled`.
- **Selection**: consistent `accent-soft`/`on-accent-soft`/`accent-primary`
  combination everywhere selection occurs (nav, table rows, list items,
  chips) — one selection language, not per-screen variants.
- **Hover**: `surface-secondary` background shift for neutral surfaces;
  never the sole indicator of interactivity for keyboard-only users (see
  § 17).
- **Focus**: visible focus ring using `focus-ring`/`accent-primary` on every
  interactive element, keyboard and mouse alike.
- **Disabled**: `text-disabled` + `border-subtle`/reduced-opacity fill;
  remains identifiable as a control, not removed from layout.
- **Read-only**: visually distinct from both editable and disabled — content
  is legible at full `text-primary`/`text-secondary` contrast but carries a
  non-editable affordance (e.g. no input border) rather than looking
  disabled.
- **Loading**: neutral, restrained indicator; do not use accent-saturated
  spinners that compete with § 14's restraint rule in Study Mode.
- **Progress**: determinate where the operation supports it (imports, audio
  batch export); see § 5's long-running-work requirements.
- **Empty state**: explains what would appear here and, where applicable, the
  action to populate it — never a bare blank area.
- **Warnings**: `warning`/`warning-soft`, label + icon, non-blocking unless
  the action truly requires acknowledgment.
- **Errors**: `danger`/`danger-soft`, structured per § 5 (what happened / what
  didn't change / what to do).
- **Success**: `success`/`success-soft`, brief and non-intrusive — success is
  confirmation, not celebration (consistent with § 4.3's "non-gamified").
- **Partial success**: its own visually distinct state (not success, not
  error) per § 5 — typically a mixed summary listing succeeded/skipped/
  failed/unresolved counts rather than a single pass/fail badge.

## 17. Keyboard & Desktop Behavior

- keyboard focus is always visible (§ 16);
- Escape reliably cancels/closes the current dialog or overlay;
- Enter only triggers the safe/default action, and never a destructive one by
  accident;
- destructive actions are never a keyboard default — they require deliberate
  selection (and, per § 5, are never the default-focused control in their
  dialog);
- high-frequency Review/Quiz workflows remain keyboard-friendly (e.g.
  answer-and-advance without requiring the mouse);
- tables and dialogs remain navigable without requiring mouse-only
  interaction (arrow-key row movement, tab order through form fields).

A complete shortcut map is not frozen here (§ 20) — only these behavioral
guarantees.

## 18. Anti-Patterns

### Global

- web landing-page aesthetics;
- mobile UI stretched onto desktop;
- excessive rounded cards;
- decorative gradients;
- neon AI-product styling;
- uncontrolled color proliferation;
- hidden state conveyed by color alone.

### Today

- chart-heavy business dashboard;
- statistics visually dominating the learning queue.

### Table-First

- detail panel becoming more visually dominant than the table;
- Dark Mode collapsing into one undifferentiated dark surface;
- implicit/default foreground colors (§ 11.4, § 13).

### Study Mode

- full management sidebar remaining visible;
- dense analytics or collection-management chrome;
- large accent-filled surfaces;
- gamified feedback that changes learning semantics.

### Analytics

- global mastery score;
- opaque learner grade;
- rainbow Findings;
- charts dominating interpretation.

### Themes

- accent overriding semantic colors;
- arbitrary foreground/background combinations;
- Light/Dark implemented by naïve inversion;
- theme changes modifying learning data.

## 19. Visual Acceptance Criteria

Concrete pass/fail criteria for reviewing a screen against this contract.

**Today / Home** — PASS when the learning queue is the visual priority and
current/resumable actions are obvious, with supporting statistics secondary.
FAIL when statistics or charts dominate the page, or the user cannot quickly
identify the next learning action.

**Table-First** — PASS when the table clearly dominates, and the selected
row/detail relationship is obvious, with dense browsing remaining
comfortable. FAIL when the bottom detail panel becomes the main page,
Dark Mode row text relies on implicit/default colors, or selected and hover
states become indistinguishable.

**Immersive Focus** — PASS when active Study Mode reduces normal application
chrome, the current task is visually dominant, and accent remains restrained.
FAIL when the normal management sidebar remains prominent, large accent
surfaces dominate, or Review browsing visually implies authoritative
completion.

**Analytics** — PASS when the Learning Brief appears before supporting
evidence and evidence/findings remain interpretable, with drill-down
available. FAIL when a global mastery score appears, charts replace
interpretation, or semantic Findings are reduced to colorful badges.

**Utility / Dialog** — PASS when preview and commit are clearly separated,
destructive actions state consequences, and progress/partial success are
understandable. FAIL when import mutates data before confirmation, partial
success is presented as total failure, or a destructive action is ambiguous
or accidentally the default/primary control.

**Theme / Accessibility** — PASS when all eight Accent × Appearance
combinations pass the same contrast audit (§ 12), all colored surfaces
resolve explicit compatible foregrounds (§ 9), and semantic states remain
independent of accent (§ 10). FAIL when a theme is only tested in Calm Blue,
Dark Mode relies on browser/framework default text colors, or text becomes
unreadable to preserve a preferred palette value.

## 20. Open Questions / Framework-Dependent Notes

Kept open deliberately; do not use this section to weaken an already-approved
decision above.

- **Desktop framework**: not yet selected (PySide6 remains the strong
  default candidate per the Desktop Migration Plan, but this remains an open
  Milestone 16 decision — see § 21). Do not read anything in this document as
  binding the product to a specific framework.
- **Exact typography metrics** (point sizes, line-height, font family
  fallback chain) are provisional until validated against the chosen desktop
  framework's native text rendering; § 15 states the durable structure, not
  final numbers.
- **Shadow/elevation values** for dialogs and popovers are conceptually
  frozen as tokens (§ 11.1) but their concrete blur/spread/opacity have not
  been visually validated the way the color tokens have; validate when the
  dialog system is actually implemented.
- **`surface-elevated`** is currently aliased to `surface-primary` (§ 11.1);
  revisit only if a real elevated surface proves visually indistinguishable
  from `surface-primary` in practice.
- **Complete keyboard shortcut map**: § 17 freezes behavioral guarantees, not
  a full shortcut inventory — that inventory is deferred to implementation.
  Windows platform-native shortcut/menu conventions (accelerators, system
  menu integration) are similarly deferred.
- **Packaging-specific theme behavior** (e.g. how `System` appearance is read
  on each target OS) is deferred to the packaging milestones.

## 21. Relationship to Framework Decision

This document does not bind the desktop UI to PySide6, PyQt, QFluentWidgets,
Electron, Toga, Tkinter, or any other framework — the repository does not yet
contain an approved framework decision (`ROADMAP.md` § M16.1 / Desktop
Migration Plan § 3 remain open).

It describes required capabilities instead: dense tables, dialogs, file
pickers, progress/cancel workflows, desktop navigation, theme tokens,
keyboard focus, and dynamic Light/Dark switching. It does not turn those
requirements into an unauthorized framework choice.

`DESIGN.md` is a product/UI contract. It is not a framework implementation
manual.

## 22. Document Provenance

Consolidated from the Milestone 16 design-exploration sequence, in order:

1. Grayscale wireframe exploration (variants A–F) for the four master
   screens, compiled to PDF.
2. User-approved locked master-screen decisions (§ 4 table).
3. Utility / Dialog Pattern Board (§ 5).
4. Theme Architecture Visual Validation — two-axis (Appearance × 4 Accent)
   theme system, token architecture, cross-screen validation.
5. Theme Contrast & Accessibility Hardening — WCAG-oriented contrast audit
   and correction pass producing the token values frozen in § 11.

Where the hardening pass (5) revised a numeric value set by the earlier
validation pass (4), this document uses the hardening pass's value, per the
explicit precedence rule stated at the top of § 11.
