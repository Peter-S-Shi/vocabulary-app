# Pre-Git Development History

Vocabulary App was developed locally before Git was initialized. The first
public commit therefore records a mature project snapshot rather than the
project's first line of code.

This document reconstructs the development sequence from preserved Codex task
records, milestone prompts, acceptance notes, and the source tree present at
the initial public commit. It is a historical narrative, not a substitute for
missing Git commits or independently preserved source snapshots. Dates identify
the development period supported by those records; they should not be read as
commit timestamps.

## Public Git Baseline

- Initial public commit: `1b8326e3554fdb20c8e2a04b4972409a223ee54e`
- Commit date: 2026-07-10
- Commit message: `Prepare public GitHub release`
- Repository state: Milestones 1 through 10.7 plus the pre-release
  stabilization work described below

No source-level Git history exists before this baseline. Earlier milestones can
be understood through this document, but they cannot be checked out as original
historical revisions.

## Development Timeline

### 2026-06-06 - Product foundation and Milestone 1

The project began as a local-first multilingual vocabulary learning system. The
initial technical choice was Python, Streamlit, and SQLite, with a deliberately
small first release:

- initialize a local SQLite database;
- add a vocabulary entry;
- persist entries across restarts; and
- display saved entries in a Streamlit table.

The first core separation was established at this stage: Streamlit handled the
interface, while database and entry operations lived under `src/`.

A project-local virtual environment and repeatable PowerShell launch workflow
were subsequently established. Git ignore rules were also introduced early to
keep the virtual environment and personal SQLite data outside version control.

### 2026-06-06 - Milestone 2 and entry-management patches

Milestone 2 expanded the entry store into a basic management system:

- search across term, meaning, tags, and source;
- filter by language, entry type, and status;
- edit existing entries; and
- delete entries with confirmation.

Milestone 2.5 added structured Quick Add parsing in `src/text_parser.py`, plus
multi-selection and batch deletion. Milestone 2.5.2 replaced separate deletion
sections with an email-style selection mode backed by transient Streamlit
session state.

During this period the long-term architecture direction was made explicit:
Streamlit was the MVP interface, not the permanent product boundary. Reusable
database, learning, parsing, and scheduling behavior would remain independent
of Streamlit so a future desktop interface could reuse it.

### 2026-06-07 - Milestone 3: collections and dynamic cards

Milestone 3 introduced collections, collection-specific ordering, and dynamic
cards. A card was intentionally not stored as a fixed entry attribute. Instead,
card membership was calculated from:

- the collection's configurable `card_size`; and
- each membership row's collection-specific `position`.

This allowed one entry to occupy different positions in different collections.
The collection workflow later gained removal and reordering controls without
deleting the underlying vocabulary entries.

### 2026-06-08 - Milestone 4: card-level review scheduling

Milestone 4 added the first review system. The review unit was a Collection Card,
not an individual entry. Review state and history were stored separately, with
the user selecting Again, Hard, Good, or Easy.

Follow-up patches connected entry creation and batch selection to collections,
added direct next-review scheduling, and fixed a selection-mode initialization
error. These changes preserved the rule that collection membership and review
scheduling logic belonged in core modules rather than in the Streamlit shell.

### 2026-06-08 - Milestone 4.4: Streamlit UI separation

The original long Streamlit page was split into sidebar-routed pages under
`src/ui_streamlit/`. `app.py` became a thin application shell responsible for
configuration, initialization, navigation, and page dispatch.

The initial page set included Dashboard, Entries, Collections, Review, Review
History / Schedule, and Settings / Data. This was a major migration-readiness
step: future UI work could replace the Streamlit layer without moving SQL or
learning rules out of the reusable core.

### 2026-06-09 - Milestone 5: quiz system

Milestone 5 introduced card-based quiz sessions and answer logs. The first quiz
mode was self-graded: users entered an answer, revealed the expected answer, and
marked the result Correct or Wrong.

The milestone then grew through focused sub-stages:

- quiz summaries and visible mistake details;
- entry-level performance counts;
- Mistake Book and Starred system collections;
- log filtering and clearer page-level navigation;
- multiple-choice and matching quizzes;
- normalized-answer checks to avoid ambiguous distractors;
- randomized question and option generation;
- active/completed/cancelled session states and duplicate-answer protection;
- quick quiz presets;
- Mistake Book recovery and recommended-removal workflows; and
- a Proficient Pool with random audit quizzes.

Several UI and state bugs were corrected during this work, including a
Streamlit widget-state mutation error and incomplete active-session handling.
The durable quiz rules and writes remained in `src/quiz.py`; Streamlit retained
only rendering and transient interaction state.

### 2026-06-09 to 2026-07-10 - Milestone 6: entry templates

Milestone 6 changed the entry model from a fixed general-entry form into a
template-aware system. The implementation introduced:

- entry templates and template-field definitions;
- stored field values associated with entries;
- custom template management;
- template-driven Add and Edit forms;
- canonical term and meaning mapping;
- template-aware search, filtering, collection display, and special pools;
- protected built-in French template presets; and
- template-aware quiz rules.

The quiz portion later expanded from one rule at a time to multi-rule practice,
Select All, multiple-choice, matching, and self-graded filling blanks. Difficulty
levels and progressively broader same-template distractor pools were added.

Manual acceptance produced several refinements: Template Management became
available under Settings / Data, validation failures preserved entered form
values, required-field errors became more visible, and Edit Entry gained
collection-membership controls.

### 2026-06-26 to 2026-06-27 - Milestone 7: statistics and review calendar

Milestone 7 added a read-only analytical layer in `src/statistics.py`, followed
by a dedicated Statistics page. It covered:

- entry, language, status, type, and template counts;
- collection and card summaries;
- due, overdue, and upcoming review workload;
- Review Calendar date and range views;
- quiz accuracy and activity trends;
- review action trends;
- special-pool statistics;
- entry-health views for weak, neglected, strong, and at-risk entries; and
- template completeness and template-specific performance.

The final polish standardized empty states, date handling, metrics, and table
formatting. Statistics remained read-only and Streamlit-free at the query layer.

### 2026-06-27 to 2026-06-28 - Milestone 8: import, export, and backup

Milestone 8 made local data portable while preserving explicit user control.
The work progressed through:

- CSV and XLSX export foundations;
- parsing, normalization, and validation without database writes;
- preview-and-confirm General Entry import;
- template-based import;
- collection/card-aware import and export;
- consistent SQLite snapshots;
- structured multi-sheet XLSX backup; and
- restore-lite preview without destructive restore.

Safety rules included duplicate handling, row-level rollback, transaction-safe
writes, explicit confirmation, sample formats, template field maps, and stale
preview protection. A later patch added safe deletion of normal collections
while protecting system collections and preserving their underlying entries.

### 2026-06-29 to 2026-06-30 - Milestone 9: daily learning workflow

Milestone 9 clarified the product as a local-first, user-owned learning workflow
rather than a bundled dictionary, pronunciation engine, or AI content service.

The new `src/learning_workflow.py` query layer and Today page connected the main
learning activities:

- due and overdue review work;
- suggested next actions;
- daily quiz suggestions;
- Mistake Book and Proficient Pool status;
- review and quiz activity summaries;
- focus navigation into Review, Quiz, and Statistics; and
- consistent return navigation to Today.

Today became the default learning home. Its summaries remained read-only and
were derived from existing review and quiz logs rather than creating activity
implicitly.

### 2026-07-02 to 2026-07-10 - Milestone 10: productization

Milestone 10 prepared the project for public distribution and future product
forms. The first five stages added:

- public-repository documentation and safety guidance;
- user-owned content policy and data responsibility boundaries;
- centralized application and database-path configuration;
- architecture boundary auditing;
- packaging feasibility analysis; and
- a desktop migration plan.

Milestone 10.6 introduced the software-update compatibility baseline:

- `app_metadata`;
- schema and application-data version values;
- migration timestamps;
- a migration registry pattern in `src/migrations.py`; and
- disabled-by-default feature flags for optional future assistance modules.

Milestone 10.7 completed productization QA, strengthened ignore rules, reconciled
the public documentation, and recorded closure and manual test checklists.

### 2026-07-08 to 2026-07-10 - Pre-release stabilization

Before the first public commit, a final patch cycle filled workflow gaps and
stabilized the expanded Streamlit application. It included:

- worksheet selection for multi-sheet XLSX imports;
- downloadable CSV/XLSX files generated from entry templates;
- stronger quiz randomization checks;
- removal of repeated expensive initialization from each Streamlit rerun;
- defensive completion of stale quiz sessions;
- user-defined card names and card-name search;
- English, Chinese, and French interface text foundations;
- paginated and sortable card views in Collections;
- Card View and Table View modes in Review, including flip, properties, edit,
  and navigation controls;
- quiz launch from a reviewed card;
- an ordered daily quiz queue with reorder, remove, and add controls;
- next-review scheduling directly from review and quiz summaries; and
- removal of an experimental whole-collection distractor-scope control.

The performance patch reduced repeated initialization work that had been
triggered by every Streamlit interaction. Milestone-specific acceptance was
reported before the final update-compatibility and release-closure work, but
the preserved repository checklists do not establish a current full-product
regression or release acceptance.

## Important Decisions and Superseded Directions

Some early roadmap ideas were intentionally replaced as the product matured:

- A fixed eight-entry card concept became configurable dynamic card sizing.
- Review scheduling was attached to Collection Cards rather than entries.
- A single long Streamlit page became a routed UI layer.
- Dictionary, pronunciation, bundled language data, and mandatory AI assistance
  were removed from the core product direction.
- Streamlit remained an MVP interface while the reusable core was kept suitable
  for a future desktop UI.
- Data ownership, explicit confirmation, additive migrations, and non-destructive
  backup/restore behavior became permanent product constraints.

## Evidence and Limitations

This reconstruction is supported by two preserved development tasks covering
the project from its initial vision through public release, together with the
milestone QA documents and the initial public source tree.

The task records include implementation summaries, changed-file lists, reported
bugs, verification results, and acceptance decisions. Some task context was
compacted during long sessions, so this document records supported milestone
outcomes rather than claiming to reproduce every temporary edit or failed
experiment.

For that reason:

- this document must not be used to manufacture apparently original commits;
- pre-Git milestones do not have independently verifiable commit hashes;
- exact intermediate source snapshots may not be recoverable; and
- the public Git history should treat the initial release commit as its honest
  technical baseline.
