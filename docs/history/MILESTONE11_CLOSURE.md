# Milestone 11 Closure

## Outcome

```text
Milestone 11 Complete
Trustworthy Pre-Desktop Baseline Established
```

This is a verified pre-desktop engineering baseline. It is not Feature Freeze,
Release Ready, Desktop Ready, Product Hardening completion, or Current Version
Complete.

M11.4 started from merged M11.3 commit
`ccda6b8385215835f3de997f268e2165c37249de` on branch
`agent/m11-4-baseline-closure`.

Verified M11.4 implementation commit:
`f0113e0592bf5198c429d3282c528c39b47f63fa`. PR #5 used documentation-only
head `b5c75ca52aa67f9fa5a7af7698358a709314d935` and was merged to `main` as
`f0e0d2c06fa4137c07ab2f892df117af2ed3a060`.

## Final semantics

- `entries.id` remains the authoritative Entry identity.
- Completed Card-scoped Quiz sessions are the only current Card learning
  completions. Review browsing and legacy schedule changes are not completion.
- Entry performance and Entry Health use Quiz item evidence and explicit
  special-pool membership, not Review browsing frequency or legacy due state.
- Current Card membership remains derived from Collection position and
  `card_size`; current-facing completion status and history use stable
  `card_id` so a retired Card's history cannot move to a later Card with the
  same display number.
- New Card-scoped Quiz sessions remain bound to the `card_id` and
  `card_revision_id` used at session start. Unprovable legacy composition
  remains unknown.
- Hard-deleting one Entry preserves prior Quiz item logs, stored Quiz evidence,
  Card revision membership IDs, and Entry change events without fabricating
  deleted Entry content.
- Deleting an entire Collection is an intentionally destructive operation. The
  confirmation explicitly states that Card identity/revision history, legacy
  Review history, Quiz sessions, and Quiz item logs are permanently deleted;
  the Vocabulary Entries themselves remain.

## M11.4 Closure Manifest

| Invariant ID | Exact evidence | Assertion | Verification | Result | Remaining limitation |
|---|---|---|---|---|---|
| M11.4-ENTRY-HEALTH | `src/statistics.py:get_entry_performance_summary`, `get_strong_entries`, `get_entry_health_overview` | Quiz/pool evidence is authoritative; legacy Review counts cannot make an Entry Strong | `test_entry_health_is_quiz_authoritative_and_m14_compatible` | Pass | M14 later replaced provisional thresholds with compatibility projections |
| M11.4-TODAY | `src/learning_workflow.py:get_study_cards`, `get_today_card_learning_activity`, `build_today_completion_summary` | Today uses Quiz-backed Card completion and active stable Card identity | M11.2 activity tests plus `test_current_card_views_do_not_inherit_retired_card_history` | Pass | Visual redesign belongs to Desktop |
| M11.4-STATISTICS | `src/statistics.py:get_card_learning_overview_stats`, `get_card_learning_sessions_between_dates` | Current Card status does not inherit retired-Card history; event rows retain session identity | Stable-history and Entry Health tests | Pass | Legacy sessions may have unknown Card identity |
| M11.4-HISTORY | `src/learning_workflow.py:get_card_learning_history`; `src/ui_streamlit/review_history_page.py` | Current Card history is selected by stable `card_id`; legacy Review logs remain compatibility-only | Stable-history test and source inspection | Pass | Retired-Card browser UI is deferred |
| M11.4-REVIEW-BROWSE | `src/ui_streamlit/review_page.py:render_review_page` | Browsing/studying creates no completion | `test_browsing_card_without_quiz_does_not_complete_learning` | Pass | Streamlit interaction design is transitional |
| M11.4-DIRECT-CARD-QUIZ | `src/quiz.py:create_quiz_session`, `complete_quiz_session` | Direct Card Quiz produces one Card completion | `test_direct_and_both_review_routes_use_one_completion_per_session` | Pass | None |
| M11.4-QUICK-QUIZ | `src/ui_streamlit/review_page.py:_review_quiz_focus_values` | Quick Quiz preserves Collection, Card number, and stable Card ID | M11.2 route tests plus stable-focus tests | Pass | None |
| M11.4-CHOOSE-QUIZ | `src/ui_streamlit/quiz_page.py:_compatible_quiz_type_options`, `_get_quiz_focus` | Choose Quiz Type preserves Card identity and excludes incompatible whole-Collection Matching | M11.2 AppTest and route tests | Pass | Matching redesign is outside M11 |
| M11.4-NONCARD-QUIZ | `src/quiz.py:create_random_quiz_session`; `src/learning_workflow.py:get_today_card_learning_activity` | Whole-Collection/random Quiz remains performance evidence without Card completion | `test_non_card_quiz_does_not_create_card_learning_activity`, `test_whole_collection_quiz_has_no_card_identity` | Pass | None |
| M11.4-COMPLETION-IDEMPOTENCE | `src/quiz.py:mark_quiz_session_completed`, `reconcile_finished_active_quiz_sessions` | Completion/recovery occurs once and retains durable answer time | M11.2 idempotence, cancellation, and reconciliation tests | Pass | Full desktop recovery controller remains future work |
| M11.4-CARD-REORDER | `src/card_history.py:reconcile_collection_card_history` | Same-Card reorder keeps Card ID and creates only the required revision | `test_within_card_reorder_revises_only_affected_card` | Pass | None |
| M11.4-CROSS-CARD | `src/collections.py:preview_collection_transition`, `CrossCardMoveConfirmationRequired` | Cross-Card movement requires confirmation and preserves old revisions | Core rollback test and Streamlit AppTest | Pass | Native confirmation UI belongs to Desktop |
| M11.4-CARD-SIZE | `src/collections.py:update_collection`; `cards.is_active/retired_at` | Surviving IDs remain; removed Cards retire; reappearance does not reuse identity | `test_card_size_retirement_reappearance_and_name_identity` | Pass | None |
| M11.4-CARD-NAME | `src/collections.py:set_card_name`; `cards.name` | Name follows stable Card identity and is not transferred to a replacement Card | Card retirement/name test | Pass | Legacy metadata table remains compatibility-only |
| M11.4-QUIZ-REVISION | `quiz_sessions.card_id`, `quiz_sessions.card_revision_id` | Active session stays on its start revision; later session uses the new revision | `test_quiz_binds_revision_and_study_activity_creates_no_revision_noise` | Pass | None |
| M11.4-LEGACY-UNKNOWN | `src/migrations.py:migrate_to_m11_3_card_history` | Pre-M11.3 composition is not falsely backfilled | `test_legacy_quiz_remains_unknown_and_card_name_migrates` | Pass | Unknown history remains intentionally unknown |
| M11.4-ENTRY-DELETE-HISTORY | `src/migrations.py:migrate_quiz_logs_to_preserved_entry_identity`; `src/quiz.py:get_quiz_item_log_view` | Entry deletion preserves log ID, Entry ID, prompt/answers/correctness/time, Card revision membership, and change events | M11.3 hard-delete and schema-convergence tests | Pass | Deleted current Entry content is not reconstructed |
| M11.4-COLLECTION-DELETE-CONTRACT | `src/collections.py:delete_collection`, `COLLECTION_DELETE_WARNING`, `COLLECTION_DELETE_CONFIRMATION` | Whole-Collection deletion is deterministic, explicitly destructive, and preserves Vocabulary Entries | `test_collection_delete_contract_is_explicit_and_deterministic` | Pass | Deleted-Collection history preservation is not implemented |
| M11.4-MIGRATION | `src/migrations.py:MIGRATIONS` | `10.6.0-baseline -> 11.3.0-card-history -> 11.3.1-quiz-log-history` converges safely | Fresh, legacy, intermediate, FK, and rollback tests | Pass | Real personal database was not mutated |
| M11.4-RESTART | `src/db.py:init_db`; backup table registry | Repeated startup adds no duplicate history and a SQLite backup remains readable | `test_restart_backup_and_schema_baseline_are_stable` | Pass | Clean-machine packaged-app testing belongs to M20 |
| M11.4-QA-CLOSURE | M11.1 66-item manifest and table below | Every QA ID assigned to M11.4 receives one final non-ambiguous disposition | Exact-ID reconciliation | Pass | No new broad manual pass was required |
| M11.4-ARCHITECTURE | `src/card_history.py`, `src/learning_workflow.py`, `src/statistics.py`, UI callers | Historical rules remain in reusable core/data modules | `scripts/audit_architecture.py` | Pass | File restructuring belongs to M12 |
| M11.4-PRIVACY | `.gitignore`, repository-local exclusions, controlled UI errors | No private QA output, database, secret, or local path enters the change | tracked/staged-file and sensitive-pattern audit | Pass | Intentional Settings path display remains local UI behavior |
| M11.4-PACKAGING-REGRESSION | `tools/check_packaging_readiness.py` | Existing source distribution remains internally consistent | Packaging-readiness checker | Pass with expected local-DB warning | Packaging work belongs to M20 |

## M11.4 QA closure

These are the 17 source QA IDs assigned to M11.4 by the accepted M11.1
manifest. The table preserves the original QA as historical evidence and gives
the current final disposition; it does not relabel an earlier successful
observation as a defect. No private QA free-text, attachment, tester, path, or
result-export data is reproduced.

| QA ID | Original QA meaning | Final disposition | Current evidence |
|---|---|---|---|
| M04-Q01 | Today recommendations and empty state | Verified under new semantics | Recommendations derive from current study cards/pools and now carry stable Card identity |
| M04-Q02 | Review focus handoff | Verified under new semantics | Today/Review focus carries and validates `card_id`; stale focus is explained and cleared |
| M04-Q04 | Daily completion summary | Product decision resolved | Legacy behavior passed at the time; current summary is Quiz-backed and excludes schedule logs |
| M05-Q01 | Card-level Review view | Verified under new semantics | Review remains Card browse/study; browsing creates no completion |
| M06-Q01 | Self-Graded Quiz logging | Verified under new semantics | Shared item logging remains one durable log per item and completion uses Quiz evidence |
| M06-Q02 | MCQ and duplicate submission | Verified under new semantics | Duplicate log protection and one-session summary reconciliation are deterministic |
| M06-Q03 | Matching completeness | Verified under new semantics | Incomplete matching is blocked before grading; submitted state prevents resubmission; whole-Collection Matching is excluded from focused Card flow |
| M06-Q04 | Template multi-rule Quiz and difficulty | Verified under new semantics | Existing rule/mode/difficulty behavior remains intact; Card-scoped sessions bind stable identity |
| M06-Q05 | Active-session protection and restart | Verified under new semantics | Existing active session blocks replacement; reconciliation is idempotent and preserves logs |
| M06-Q08 | Quiz logs and summary | Verified under new semantics | Item/session totals reconcile; snapshots remain truthful after Entry edits/deletion |
| M07-Q03 | Quiz Performance and trends | Verified under new semantics | Aggregates use Quiz item/session evidence and Card history rows expose stable identity |
| M07-Q04 | Entry Health and special pools | Verified, then superseded by M14 interpretation | Quiz authority remains intact; current legacy-shaped APIs now project M14 Primary Findings and pool context |
| M09-Q01 | Durable data after restart | Verified under new semantics | Repeated initialization preserves counts/schema; backup reopens with integrity `ok` |
| M09-Q02 | Active Quiz refresh recovery | Verified under new semantics | Finished active sessions reconcile once from durable logs without duplicate items |
| M09-Q03 | Stale focus and queue | Verified under new semantics | Missing/mismatched stable Card focus is explained and cleared; unavailable queue items are removed |
| M10-Q01 | End-to-end learning journey | Verified under new semantics | Entry/Collection/Card/Quiz identities, counts, snapshots, and export rows reconcile |
| M10-Q02 | Edit propagation | Verified under new semantics | Current Entry/export content updates while historical Quiz snapshots remain unchanged |

All 17 assigned QA IDs appear exactly once. None remains `probably fixed`,
`likely okay`, or `assumed pass`.

## Final M11 regression matrix

| Area | Final invariant | Evidence |
|---|---|---|
| Entry editing | Entry A/B widget state is isolated; successful edits create compact change events | M11.2 Entry AppTest; M11.3 Entry-history tests |
| Review and Quiz routes | Browse-only is not completion; direct, Quick, and Choose routes preserve Card scope | M11.2 route/activity tests |
| Completion integrity | One completed Card Quiz is one event; cancel/restart/idempotence cannot duplicate it | M11.2 completion tests |
| Scheduling retirement | Active UI exposes no independent due-date/SRS mutation and legacy logs are excluded | M11.2 source and activity tests |
| Stable Card identity | Reorder, cross-Card movement, resize, retirement/reappearance, and names retain truthful identity | M11.3 mutation/AppTests |
| Historical evidence | Quiz revision binding, legacy unknown history, Entry deletion, and edited snapshots remain truthful | M11.3 and M11.4 history tests |
| Current summaries | Today, Statistics, Learning History, and Entry Health use Quiz-backed semantics; M14 is now the Entry-level interpretation authority | M11.4 stable-history test plus M14 Batch C compatibility tests |
| Persistence | Fresh/legacy/intermediate migrations, rollback, restart, and backup readability are deterministic | M11.3 migration tests and M11.4 restart test |

## Verification results

- Complete automated suite: 38 tests passed.
- Targeted M11.4 closure suite: 6 tests passed.
- Quiz randomization checker: passed.
- Python compilation for `app.py`, `src`, and `tests`: passed.
- Architecture audit: 32 Python files scanned; no serious boundary violations
  and no warnings.
- Packaging-readiness check: passed with the expected warning that the local
  personal database exists and must remain excluded from Git and releases.
- `git diff --check`: passed.
- Fresh-schema, migrated-schema, restart, and backup-readability checks use
  isolated synthetic databases. The local personal database was not modified.
- No schema or migration file changed in M11.4. M12 has not started.

The full suite also emits existing SQLite connection `ResourceWarning` noise
and Streamlit bare-mode/deprecation warnings. They do not change the passing
assertions and remain classified below rather than being hidden as closure
failures.

## Technical debt classification

| Item | Classification | Closure effect |
|---|---|---|
| SQLite connection `ResourceWarning` noise in isolated tests | Safe compatibility debt for M12 | Does not affect assertions or stored data |
| Legacy Review/SRS tables and functions | Safe compatibility debt for M12/later migration | Retained but excluded from active UI and completion truth |
| `collection_card_metadata` | Safe compatibility debt for M12 | Compatibility-only; stable names live on `cards` |
| Streamlit `use_container_width` deprecation warnings | Desktop scope | Does not block the pre-desktop data/business baseline |
| Streamlit visual, localization, keyboard, narrow-layout, and accessibility work | Desktop scope | Not an M11 closure blocker |
| Limited active-Quiz UI recovery | M12/Desktop controller work | Durable reconciliation is idempotent; UI continuation remains limited |
| Whole-Collection deletion removes associated history | Accepted current product contract | Explicitly confirmed and documented as destructive |
| Native packaging and clean-machine install | M20 | Packaging checker is regression evidence only |

No remaining item blocks M11 closure. There is no known current query that
silently reassigns a completed Card Quiz to a different active Card identity.

## Next objective

The exact next engineering objective is:

**Milestone 12 — Repository Restructure**

The M11.4 independent review and merge gate is complete. M12 is ready to begin;
its implementation has not started.
