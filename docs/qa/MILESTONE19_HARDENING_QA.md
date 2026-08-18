# Milestone 19 — Desktop Product Hardening: Hardening / Acceptance Evidence Record

**Status: Complete on `main` — Human Accepted 2026-08-18 at accepted
product head `a128c50d75154ff3f85eacfd3a96e54d27d11c4d` (§ 11), after
correctives for the Attempt 1 FAIL (§ 9) and the Attempt 2 partial FAIL
(§ 10), merged via PR #30 at
`2ad211711d96583b6fffdb65de912fa672502bc8`.** This is
a living evidence record, not a pre-hardening questionnaire. It
documents what was audited, what was found, what was fixed, and what
was verified during M19 — kept current with `PROJECT_STATUS.md`, the
authoritative evidence-based snapshot.

- **Branch:** `agent/m19-desktop-product-hardening` (merged)
- **PR:** #30 (MERGED)
- **Merge commit on `main`:** `2ad211711d96583b6fffdb65de912fa672502bc8`
- **Baseline:** `9dae05c49caec8f2a33fdaf74d0a1f3fd1db43bc` (M18 merge
  commit, PR #29)
- **Contract:** M19 Autonomous Product Hardening Execution Contract

## 1. Baseline Reconciliation (Phase A)

- Verified `origin/main` = `9dae05c` at milestone start; local `main`
  fast-forwarded to match.
- `PROJECT_STATUS.md`, `ROADMAP.md`, and `README.md` corrected from a
  stale "M18 READY FOR MERGE, awaiting authorization" / "M18 IN
  PROGRESS" narrative to the actual merged state.
- Baseline verification at `9dae05c`: full repository suite 782/782
  green (offscreen), architecture audit clean (87 files, 0 violations),
  quiz randomization check passed.
- Desktop Feature Freeze declared active for the remainder of the
  milestone.

## 2. Audit Coverage

Audited as an integrated system, not isolated widgets, per the M19
contract's coverage areas (ROADMAP § 19.2–19.5):

- Create/Import → Organize → Today → Review → Quiz → Learning Pools →
  Analytics → Export/Backup
- Template Definition Import → Entry Import → Linked-File Refresh
- Card/Collection Selection → Audio Generation → Batch Export
- Data/migration integrity, robustness/desktop interaction, privacy and
  repository safety

## 3. Findings

### M19-F1 — Shared TTS runtime required a manual environment variable (closed)

**Class:** mandatory M19/M20 productization handoff item (ROADMAP §
"Mandatory M19 / M20 Productization Handoff — Card Audio Export"), not
a regression.

**Evidence:** M18 closed the Card Audio Export *capability* against a
runtime resolved exclusively from `VOCAB_APP_SHARED_TTS_DIR`, an
environment variable a normal end user has no reason to know about.

**Fix:** new `src/ui_desktop/state/tts_runtime.py` resolution module —
`VOCAB_APP_SHARED_TTS_DIR` (advanced per-process override, the
`VOCAB_APP_DB_PATH` precedence model) → a new durable `shared_tts_dir`
app setting (Settings → Audio: folder picker, Clear, effective-source
display) → honestly not configured, with the unconfigured detail now
naming Settings → Audio first. `AudioExportController` resolves the
registry through this one seam for voice preflight, Plan building,
Retry, and the run itself — a connected defect where Plan/Retry
silently ignored an app-configured runtime and fell back to
environment-only resolution was fixed in the same change. Core
provider/voice/language routing (M15.0, frozen) was not reopened.

**Verification:** 16 new focused tests
(`tests/test_m19_tts_runtime_config.py`); 110/110 on the full
audio/settings regression battery; read-only preflight against the
real environment-resolved runtime (en/fr/zh-CN all available); explicit
QSS coverage for every new Settings control in both themes.

**Commit:** `264613c`.

### M19-F2 — Duplicate active Quiz sessions on a repeated launch (closed)

**Class:** release-relevant core-workflow / data-integrity-adjacent
defect (an orphaned learning-session row a normal recovery path could
not clear).

**Evidence:** `QuizController.start()`'s active-session guard rejected
only a *foreign* active session
(`active["id"] != self.session_id`); a repeated launch through the
*same* controller — a double-clicked Quick Quiz, or a second launch
action arriving before the first session finished — matched
`active["id"] == self.session_id` and created a second `quiz_sessions`
row while the first stayed `active` forever. Reproduced directly before
any code change:

```text
first start  -> session 1 (active)
second start -> session 2 (active)   # BUG: two concurrently active rows
get_active_quiz_session() -> 2       # session 1 is now unreachable
```

The orphan was invisible to existing recovery: `get_active_quiz_session()`
returns only the newest active row, and
`reconcile_finished_active_quiz_sessions()` only reconciles sessions
that are already fully answered — a never-answered orphan was never
cleaned up. "Cancel and retry" made it worse: it cancelled only the
displayed session, so the user was immediately blocked again by the
orphan with `cancel_blocked_and_retry()` returning `False` and nothing
on screen explaining why.

**Root-cause fix:** `start()` now cancels the controller's own
still-active, uncompleted session before creating a new one — the same
"abandoning an active Quiz cancels it" rule `exit_active()`/
`cancel_active()` already apply. Placed *after* item generation
succeeds, so a launch that cannot build items never destroys the
session already in progress. No completion is ever fabricated; answers
already recorded survive as Entry-level evidence (M14 keeps explicitly
answered Items eligible under a cancelled session).
`cancel_blocked_and_retry()` additionally clears every remaining stale
active session (bounded loop) so a database written by an earlier
build can still recover instead of looping.

**Verification:** 17 new regression tests
(`tests/test_m19_quiz_session_integrity.py`); 5 of them fail against
the pre-fix controller and pass against the fix (verified by reverting
the source file and re-running both ways); the other 12 record
already-correct behaviors (duplicate-answer protection,
submit-before-reveal refusal, idempotent completion, cancel/restart
semantics, foreign-session block never becoming a fake resume, repeated
Study-mode entry/exit through a real `MainWindow` creating no learning
evidence). Affected Quiz/Review/Today/learning-semantics regression:
226/226.

**Commit:** `a837b3d`.

### Product-truthfulness correction — "(Desktop Preview)" window title (closed)

The desktop application has been the accepted primary product surface
since M17/M18; the `MainWindow` title still read "Vocabulary App
(Desktop Preview)". Corrected to "Vocabulary App"
(`src/ui_desktop/main_window.py`; structural test updated in
`tests/test_m16_2_desktop_vertical_slice.py`).

**Commit:** `5517f1b`.

## 4. Verified-No-Defect Evidence

Each area below was investigated first (adversarial probing, hand-computed
expected values, or direct code reading) and found already correct — no
product change was needed or made. Recorded as durable regression
evidence rather than an invented change, per the M19 contract's
investigate-before-fix discipline.

| Area | Evidence file | Tests | Summary |
|---|---|---|---|
| Fresh/empty-database integrated behavior | `tests/test_m19_empty_database_hardening.py` | 7 | Every Management workspace renders on a fresh database; Study-mode entry/exit is a controlled empty state; a stale Card handoff fails honestly; a Quiz launch against a missing Collection renders an honest no-session state; a full browse cycle changes no database row against the post-init (system-Template-seeded) baseline; simulated restart reopens cleanly. |
| Backup/restore-preview adversarial boundaries | `tests/test_m19_adversarial_boundaries.py` | 8 | Truncated and pure-garbage workbook bytes report a controlled invalid preview with zero database mutation; a tampered `app_name` surfaces the existing-contract WARNING (restore is preview-only); an unsupported `backup_format_version` remains a hard error. |
| Linked Source file mutated between Preview and Confirm | (same file, 3 of the 8) | — | The TOCTOU window the M18 suite never exercised: file deleted or corrupted after Preview, before Confirm — fails closed (transaction rollback, link metadata and existing Entries untouched). The M13 v1 "Confirm re-scans at confirmation time" semantic is now locked in by test. |
| Analytics representative expected cases | `tests/test_m19_analytics_representative_cases.py` | 14 | Six hand-computed cases (one per Primary Finding arbitration class) matched the M14 semantic contract on the first run; Coverage bands matched the published thresholds; `EvidenceProfileCache` cached/uncached equivalence proven (Finding-for-Finding, Coverage-profile-for-Coverage-profile), including one cache reused across multiple scopes. |
| Data Tools synchronous-operation performance | (evidence in commit message, no dedicated test file — timing assertions would be flaky) | — | Against a disposable copy of the real production database (5,685 entries) and a 6,000-row synthetic CSV: export 0.15s, import preview 0.43s, import confirm 0.58s, SQLite backup 0.04s, XLSX backup 2.39s, restore preview 1.42s. Nowhere near the Analytics HG2 material-impairment precedent (137s); no background-threading rework justified inside the freeze. |
| Unwritable/invalid export destinations | `tests/test_m19_destination_and_scale.py` | 11 (5 of 11) | Every desktop write path (Entries export, Template Definition export, database backup, workbook backup) is guarded by `open(...)`/`except OSError`; export bytes are built in memory before any write is attempted; the audio-export batch records a per-Card publication failure and continues rather than aborting. |
| Large/dense dataset boundedness | (same file, 6 of 11) | — | `get_card_page_for_collection` verified against a 240-entry/30-card Collection: bounded page reads, honest clamp-and-report for an out-of-range page number, empty bounded projection for a missing Collection. `EvidenceProfileCache` verified against a 60-entry/480-event dense history: one cache build serves every scope with results identical to the uncached computation. |
| Background-thread completion after navigation / shutdown | `tests/test_m19_background_task_navigation.py` | 4 | `AnalyticsController` (the one controller with a legitimately long-running background load) probed through a real `MainWindow`: navigating away before a load finishes, navigating back before the first load returns (a second generation racing the first), closing the window mid-load, and rapid workspace bouncing — all safe: no crash, no hang, no stale/overwritten result, no leaked `QThread`. |

## 5. Data and Migration Integrity

- Fresh database: triple `init_db()` + repeated `run_migrations()` —
  idempotent, zero repeat actions, schema `15.1.0-speech-semantics`.
- Representative upgraded database: a disposable copy of the real
  production database (5,685 entries, 717 Cards, 50 Quiz sessions, 224
  Quiz item logs) — repeated migration produced zero actions and zero
  row-count drift across 9 core tables.
- No schema or `app_data_version` change was introduced during M19.

## 6. Convergence Verification

```text
Full repository suite:        859/859 (offscreen, QT_QPA_PLATFORM=offscreen)
Architecture audit:            94 Python files, 0 serious, 0 warnings
Quiz randomization check:      passed
Privacy/tracked-file scan:     clean across the full M19 diff
Native platform launch health: real Windows platform (not offscreen);
                                real top-level window confirmed via
                                process-tree enumeration (child PID,
                                title "Vocabulary App", non-zero window
                                handle); clean graceful shutdown; no
                                orphaned process
Working tree / remote:         clean; local HEAD matches
                                origin/agent/m19-desktop-product-hardening
```

Native launch health above is **Agent Verified only**: it proves the
real desktop process starts, produces a real window, and shuts down
cleanly on this machine's actual Windows platform. Per `AGENTS.md`
("Automated tests cannot establish visual quality"), it is not a
substitute for visual or functional acceptance and is not labeled Human
Accepted.

## 7. Known Limitations / Deferred (not M19 defects)

- SQLite `ResourceWarning: unclosed database` noise under the
  `unittest` harness — pre-existing, tracked in `PROJECT_STATUS.md`
  Known Risks; does not affect test results or product behavior.
- Three deferred Accent families (Sage/Teal, Indigo/Violet, Warm
  Neutral) and the Quick Theme Control popover — M17-era scope
  boundary, unchanged.
- Advanced Entries table personalization (saved sort/filter views,
  drag-reordering, column customization) — M17/M18-era scope boundary,
  unchanged.
- Packaging, installer, clean-machine distribution, and third-party
  bundle review remain M20 scope, per the M19/M20 productization
  handoff boundary.

## 8. Exit Criteria Status

Against `ROADMAP.md` § "Milestone 19 Exit Criteria":

- [x] No known release-blocking defect remains.
- [x] No known high-risk data-integrity, privacy, or security defect
      remains.
- [x] Core desktop workflows pass integrated (agent-operated)
      verification, and full-product manual acceptance is complete —
      the Final Human Acceptance Gate PASSed at Attempt 3 (§ 11 below).
- [x] Fresh-database scenarios pass.
- [x] Representative upgraded-database and repeated-migration scenarios
      pass.
- [x] Import/export safety passes.
- [x] Template Definition portability remains safe (unchanged M13/M18
      behavior; no regression found).
- [x] Linked Source safety passes (including the newly-covered
      preview-to-confirm TOCTOU window).
- [x] Backup generation / restore-preview boundaries pass.
- [x] Analytics outcomes match representative expected cases.
- [x] Audio generation/export and batch failure handling pass
      (existing M18 coverage plus the M19-F1 configuration fix).
- [x] Cancellation/retry/error recovery is verified where applicable
      (Quiz session recovery specifically hardened by M19-F2).
- [x] Architecture audit passes.
- [x] Automated regression passes (872/872 at the accepted head).
- [x] Privacy/repository audit passes.
- [x] Known limitations and deferred work are documented (§ 7 above).
- [x] `README.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, migration docs,
      and this M19 QA record agree.
- [x] Exact local branch/head and remote branch/head are verified.

## 9. Final Human Acceptance Gate — Attempt 1: FAIL, narrow UX corrective

The operator launched the real native application from Engineering Exit
Candidate head `2dc0893` and recorded **FAIL** with two narrow UX
correctives (explicitly not a reopening of broader M19 scope):

1. Settings → Audio had no visible feedback during its load (~5–6s
   observed natively).
2. Navigation Rail order should be Today → Study → Entries →
   Collections → Review Calendar → Templates → Data Tools → Analytics
   (Settings unchanged, separate bottom position).

### Corrective 1 — Settings → Audio loading feedback

**Investigation before changing code:** timed `SettingsController`/
`SettingsView` construction directly (including with the real
environment-configured shared TTS runtime present) — 6ms, not 5–6s.
Grepped the entire desktop layer for `.preflight(`/`build_provider_registry`
call sites: the only live per-language preflight (the genuinely slow,
subprocess-spawning check — kokoro/sherpa-onnx/Yaoyao PowerShell) lives
in `AudioExportController` (Data Tools → Card Audio Export), which
Settings → Audio's existing note text already points to and does not
call. The root cause of the operator's observed real-machine delay
could not be conclusively isolated in this environment.

**Fix (robust regardless of root cause):** Settings → Audio's status
rows are now populated behind a deferred, spinner-first load —
`src/ui_desktop/views/settings_view.py` shows an indeterminate
`QProgressBar` (`settings-audio-loading-spinner`, styled to match the
existing `analytics-progress-bar` pattern) immediately on construction;
the real rows are built up front but hidden; a `QTimer.singleShot(0, ...)`
defers the actual `shared_tts_dir_setting()`/`shared_tts_status()` calls
by one event-loop tick so the spinner has a chance to paint first, then
swaps to the real content. A later Browse/Clear update (already-loaded,
user-initiated, fast) updates the visible rows directly without
re-showing the spinner. This is correct whether the underlying call
takes 6ms or 6 seconds on a given machine.

**Verification:** 3 tests in `tests/test_m19_tts_runtime_config.py`
(`SettingsViewAudioSectionTests`) — the busy indicator is shown and the
content hidden immediately at construction; after the deferred load
runs, the content is shown and the indicator hidden; a later update
never re-shows the indicator. (`QWidget.isVisible()` requires a shown
top-level window and is unusable in an offscreen test harness;
`isHidden()` — the widget's own explicit visibility flag, independent
of ancestor state — is used instead.)

### Corrective 2 — Navigation Rail order

**Fix:** `PRIMARY_DESTINATIONS` in
`src/ui_desktop/widgets/navigation_rail.py` reordered to Today → Study
→ Entries → Collections → Review Calendar → Templates → Data tools →
Analytics. `SETTINGS_DESTINATION` is appended separately after
`layout.addStretch(1)` and was already unaffected by this tuple's
order.

**Verification:** existing structural tests (`test_m17_today_command_center_shell.py`)
assert rail contents as sets, not order, so they remained valid
unchanged; the new order was confirmed programmatically
(`[d.key for d in PRIMARY_DESTINATIONS]`).

### Regression evidence for this corrective pass

```text
Affected navigation/Settings/desktop regression: 378/378
Full repository suite:                           860/860 (offscreen)
Architecture audit:                               94 Python files, 0 serious, 0 warnings
Privacy/tracked-file scan:                        clean
```

## 10. Final Human Acceptance Gate — Attempt 2: Sidebar PASS, Audio loading feedback FAIL

The operator re-checked at head `98119db` and recorded:

- **Navigation Rail order: PASS.**
- **Audio loading feedback: FAIL**, with a precise correction of both
  the location and the required treatment:
  1. the indicator belongs **beside the Audio Export button**, and
     should be a progress ring that starts hollow and fills to solid;
  2. the real problem is in **Data Tools**, not Settings — every other
     Data Tools button responds immediately, while Audio Export takes
     6–7 seconds before anything happens.

### What Attempt 1 got wrong

Attempt 1 read the original report ("Settings → Audio Output") as the
Settings workspace and put a busy indicator there. Its own
investigation had actually already identified the correct culprit —
the live provider preflight in `AudioExportController` reached from
Data Tools → Card Audio Export — and recorded that Settings itself
resolves in 6ms, but it still placed the indicator in the wrong
surface. The Settings-side indicator was reverted in full (back to its
pre-Attempt-1 state) rather than left as unnecessary UI.

### Root cause (measured, not assumed)

`AudioExportDialog.__init__` calls `_populate_voice_table()` →
`AudioExportController.voice_assignment_rows()` →
`ProviderRegistry.preflight()` for each frozen language. The Mandarin
route's preflight shells out to `powershell.exe` via `subprocess.run`
(`src/tts_providers.py`, `CommandSpeechProvider.preflight`, 30s
timeout). All of it ran **synchronously on the Qt UI thread before the
dialog could paint** — so the button appeared dead for the duration
while every sibling Data Tools button, which opens its dialog directly,
responded instantly.

Measured per-language cost in this environment: `en` 0.00s, `fr` 0.00s,
`zh-CN` 0.25s. The cost is environment-dependent and **not bounded in
practice** — one probe of the same call inside a Qt worker thread was
still running past a 200s timeout — so the fix is to stop blocking on
it, not to try to make it fast.

### Fix

- **`_VoicePreflightWorker`** (`audio_export_controller.py`): runs the
  preflight on a background `QThread`, one language at a time, emitting
  truthful completed/total progress after each — never a fabricated
  within-language percentage. Follows the repository's established
  worker discipline exactly: real bound-method connections (never
  lambdas, so PySide6 queues onto the Qt UI thread), a monotonic
  generation guard discarding superseded runs, and a blocking
  `shutdown_voice_preflight()` join wired into `MainWindow.closeEvent`.
- **`ProgressRing`** (`src/ui_desktop/widgets/progress_ring.py`): a new
  determinate circular indicator that paints a track plus a clockwise
  arc from 12 o'clock — hollow at 0, solid at 100%, exactly as
  requested. Qt ships no circular progress widget and QSS cannot
  express an arc, so it paints directly and takes its colors from the
  active theme tokens through the same `apply_theme_tokens` seam
  `MainWindow` already uses for the Entries Star column.
- **Data Tools hub** (`data_tools_view.py`): clicking Audio Export now
  disables the button, shows the ring hollow with a
  "Checking speech providers… n/N" status, fills the ring as each
  language resolves, then opens the dialog **seeded with the real
  results** (`AudioExportDialog(..., voice_rows=...)`) so the cost is
  never paid twice. A repeated click cannot start a second preflight or
  open a second dialog, and a one-shot `_audio_launch_pending` guard
  ensures only a preflight the user actually initiated can open a modal
  dialog.

A failed preflight still opens the dialog — it renders the same
unavailable-provider diagnostics it always did, rather than silently
swallowing the action.

### Diagnosis note

The first run of the new tests hung. Rather than loosening the tests,
a `faulthandler` thread dump was taken, which showed the block was
`dialog.exec()` — a modal dialog opened from the completion handler,
with no user present in a headless run to close it. The dialog-opening
call was therefore split into `_open_audio_export_dialog()` so tests
can exercise the full preflight/ring/seed sequence without a modal
blocking forever. No threading defect existed.

Separately, `tests/test_m19_background_task_navigation.py` was found to
be timing-brittle (introduced in an earlier M19 batch): it assumed a
fixed 300ms pump was always enough for a background Analytics load to
finish and be reaped, which held in isolation but failed once more GUI
tests shared the process. Replaced with a bounded `_pump_until_idle`
wait — the invariant is "it finishes and cleans up", not "it finishes
within N milliseconds".

### Verification for Attempt 2's corrective

```text
New tests (tests/test_m19_audio_export_preflight_progress.py): 13/13
Affected Data Tools/audio/settings/navigation regression:      172/172
Full repository suite:                                         see § 6
Architecture audit:                                            0 serious, 0 warnings
```

## 11. Final Human Acceptance Gate — Attempt 3: PASS (Human Accepted)

The operator inspected the real native desktop application launched
from candidate head `a128c50d75154ff3f85eacfd3a96e54d27d11c4d` and
recorded **PASS** on 2026-08-18. Both Attempt 2 correctives were
accepted: the Navigation Rail order, and the hollow-to-solid progress
ring beside the Data Tools → Audio Export button with its background
provider preflight.

This is the authoritative M19 acceptance decision.

```text
Accepted product head:  a128c50d75154ff3f85eacfd3a96e54d27d11c4d
Branch:                 agent/m19-desktop-product-hardening (PR #30, MERGED)
Baseline:               9dae05c49caec8f2a33fdaf74d0a1f3fd1db43bc
Accepted on:            2026-08-18
Merge commit on main:   2ad211711d96583b6fffdb65de912fa672502bc8
```

Verification at the accepted head:

```text
Full repository suite:         872/872 (offscreen)
Architecture audit:            95 Python files, 0 serious, 0 warnings
Quiz randomization check:      passed
Privacy/tracked-file scan:     clean across the full M19 diff
Native platform launch:        real window confirmed, clean shutdown
Working tree / remote:         clean; local HEAD == remote branch head
```

**Milestone 19 — Desktop Product Hardening is complete on `main` and
Human Accepted. Milestone 20 — Packaging and Release Candidate is the
current/next lifecycle objective.**

The branch was merged by the operator: PR #30 → `main` at
`2ad211711d96583b6fffdb65de912fa672502bc8`. Per the M19 contract § 18,
the agent did not merge to `main` itself.

## 12. Handed to Milestone 20

- Packaging mechanism, installer, and clean-machine distribution
  (deliberately untouched by M19 per the contract's scope boundary).
- Shared TTS runtime *provisioning* for a clean external user: M19
  closed the durable in-app configuration contract (§ 3, M19-F1), but
  how an installed copy obtains the runtime, models, and voices —
  bundle vs. first-run download vs. another strategy — remains M20
  scope (ROADMAP § "Mandatory M19 / M20 Productization Handoff").
- Final third-party bundle/license review and Release Candidate
  acceptance.

## 13. Known Limitations Carried Forward (not defects)

Unchanged from § 7: the SQLite `ResourceWarning` test-harness noise;
the three deferred Accent families and the Quick Theme Control popover;
advanced Entries table personalization.
