# Vocabulary App Project Status

Last reviewed: 2026-08-19

This file is the authoritative evidence-based snapshot of the current project
state.

Lifecycle intent and future milestones are defined in `ROADMAP.md`.

Desktop-specific migration principles and workflow mapping are defined in
`docs/migration/DESKTOP_MIGRATION_PLAN.md`.

## Current Phase

**Milestone 20 — Packaging and Release Candidate: RC Engineering Exit
Candidate reached, Human RC PASS granted (2026-08-19) for SHA
`89263a4f0f477fe5455ed22bedffd1968218bb1e` on branch
`agent/m20-packaging-release-candidate` (Draft PR #33). Not yet merged
to `main` — merge, tag, and GitHub Release publication all require the
operator's separate, explicit authorization per the M20 execution
contract's authority boundaries; the agent does not perform any of
those itself.**

## Current Milestone

**Milestone 20 — Packaging and Release Candidate: RC Engineering Exit
Candidate reached, Human RC PASS granted.** Developed under the M20
Autonomous Release Engineering Loop on the single long-lived branch
`agent/m20-packaging-release-candidate` (Draft PR #33), from the M19
merge baseline `f615ab79b4266810fd6a88937f1917c473607136`.

**Human RC Acceptance Gate: PASS.** The operator granted Human RC PASS
(2026-08-19) for the exact SHA `89263a4f0f477fe5455ed22bedffd1968218bb1e`
and the installer built from it
(`VocabularyApp-Setup-1.0.0-rc.1.exe`, SHA-256
`8b435657c5cecfecd52f96a6f49d648e1fcaa2e4b58cada03cfc3baf7ea87710`).
This is the authoritative M20 RC acceptance decision. Per the loop
contract's GitHub/release authority boundaries (§ 13), the agent may
prepare the PR for merge but must not merge it, merge to `main`,
create/push a version tag, or publish a GitHub Release without a
further, separate explicit operator instruction to do so.

**RC Engineering Exit Candidate evidence (agent-verified, 2026-08-19,
at the accepted SHA):**

- Application version: `1.0.0-rc.1`.
- Full repository regression: **911 tests, 0 failures, 0 errors**
  (`unittest discover`, 1450.7s) — a full clean run, including the
  earlier-known `test_m18_review_calendar.py` failures that had
  appeared in an intermediate Phase B run but are absent here.
- Architecture audit: clean (90 Python files, 0 serious violations, 0
  warnings).
- Build: `python winbuild/build.py` — PyInstaller `--onedir` (126.0
  MiB / 132,089,241 bytes) + Inno Setup, both stages succeeded;
  `dist/build_manifest.json` `source_sha` matches the accepted HEAD
  exactly, `source_dirty: false`.
- Code signing (operator decision amendment — self-signed for this
  v1.0 Portfolio RC, not a publicly trusted certificate; SmartScreen
  reputation is explicitly not an M20 exit criterion, see
  `docs/packaging/M20_RELEASE_CONTRACT.md` § 2.7 Fourth Revision):
  both the onedir `.exe` and the installer carry a valid Authenticode
  signature from the self-signed `CN=Peter Shi` certificate, verified
  independently via `Get-AuthenticodeSignature` (status
  `UnknownError`/untrusted-root — the correct, expected result for a
  self-signed certificate, not a defect).
- Distribution QA § A (fresh local Windows account, `VocabAppQA` —
  operator decision amendment supersedes the earlier clean-VM
  requirement for v1.0, see `docs/packaging/M20_DISTRIBUTION_QA_CHECKLIST.md`):
  elevation-free install, correct per-user paths, Start Menu/Desktop
  shortcuts, fresh-DB first launch, per-account Local Windows Speech
  Provider voice enumeration (22 real voices), backup-before-upgrade
  with a real schema migration, default-preserve uninstall, and a
  marker-row-verified reinstall that reopens preserved data — all
  confirmed for real under that account.
- Representative existing-database import: verified end-to-end via the
  real `import_existing_database()` function against isolated,
  disposable data (copy-not-move, destination backed up, source
  untouched, reopens correctly after import).
- Release-archive/privacy scan: 181 files in the onedir payload, no
  `.venv`/`.env`/test fixtures/personal `vocab.db`; the compiled `.exe`
  binary-scanned for embedded local dev-machine paths — none found.
- `LICENSE`, `THIRD_PARTY_NOTICES.md`, and README audio/TTS disclosure
  all reconciled to the shipped RC build.

**Known limitations recorded, not blocking:** the existing-database-
import and destructive-uninstall-opt-in UI flows were verified by
direct function-level/primary-account evidence rather than a literal
file-picker click-through under the fresh `VocabAppQA` account (no
interactive desktop session was available to automate a native
dialog); full clean-machine VM verification (Release Contract § 2.8
§ B) is deferred beyond v1.0 per an earlier operator decision
amendment; publicly trusted code signing is deferred to a possible
future public/commercial/Microsoft Store distribution effort per the
Fourth Revision amendment.

---

**Milestone 19 — Desktop Product Hardening is Complete on `main`,
Human Accepted.** Developed under the M19 Autonomous Product
Hardening Execution Contract on the single long-lived branch
`agent/m19-desktop-product-hardening`, merged to `main` through PR #30
at `2ad211711d96583b6fffdb65de912fa672502bc8`, created from the
verified M18 merge baseline `9dae05c49caec8f2a33fdaf74d0a1f3fd1db43bc`.
The desktop **Feature Freeze was active throughout**:
correctness, data-integrity, migration/compatibility, privacy/security,
robustness, serious UX, and performance defects remained in scope; no
new product capability was introduced.

M19 baseline verification (2026-08-18, at `9dae05c`): full repository
suite 782/782 green (offscreen), architecture audit clean (87 Python
files, 0 serious, 0 warnings), quiz randomization check passed, working
tree clean, local `main` fast-forwarded to `origin/main`.

### M19 Engineering Exit Candidate summary (historical pre-gate snapshot, Agent Verified, 2026-08-18)

**Historical context, superseded below.** This subsection is the
evidence snapshot recorded when M19 reached Engineering Exit Candidate,
*before* the Final Human Acceptance Gate was presented. It is preserved
for the audit trail. The current, authoritative outcome is Attempt 3
PASS — Human Accepted, merged to `main` — recorded in the "Final Human
Acceptance Gate" subsections immediately following this one.

**One confirmed release-relevant defect, root-cause fixed and
regression-tested (M19-F2):** `QuizController.start()` only rejected a
*foreign* active Quiz session, so a repeated launch through the same
controller (a double-clicked Quick Quiz, or a second launch action
arriving before the first session finished) created a second active
session while the first stayed `active` forever -- an orphan invisible
to both `get_active_quiz_session()` (returns only the newest active row)
and `reconcile_finished_active_quiz_sessions()` (only reconciles fully
answered sessions), and "Cancel and retry" recovered nothing because it
cancelled only the displayed session. Fixed by cancelling the
controller's own still-active, uncompleted session before creating a new
one (the existing "abandoning an active Quiz cancels it" rule), and by
having `cancel_blocked_and_retry()` clear every remaining stale active
session. 17 new regression tests (5 of which fail against the pre-fix
controller, verified by reverting and re-running); no completion is ever
fabricated and no recorded answer is ever lost.

**One durable product-facing configuration gap closed (M19-F1):** the
mandatory M19/M20 productization handoff item (ROADMAP § "Mandatory
M19 / M20 Productization Handoff -- Card Audio Export") -- Card Audio
Export required a normal end user to set a shell environment variable.
Closed with a new Settings > Audio configuration surface
(`shared_tts_dir` durable preference) and a resolution order
(`VOCAB_APP_SHARED_TTS_DIR` override -> app setting -> honestly not
configured) implemented in `src/ui_desktop/state/tts_runtime.py`; a
connected defect in the same area was fixed alongside it (Plan
build/Retry previously ignored the app-configured runtime and fell back
to environment-only resolution).

**Documentation/lifecycle-truthfulness corrections:** `PROJECT_STATUS.md`
and `ROADMAP.md`'s stale "M18 READY FOR MERGE, awaiting authorization"
and "IN PROGRESS" narratives corrected to the actual merged state;
`README.md`'s stale M17-only feature list corrected to the full M17+M18
accepted surface; the desktop `MainWindow` title's "(Desktop Preview)"
suffix retired now that the desktop app has been the accepted primary
product surface since M17/M18.

**Every other hardening area investigated this milestone was verified
already correct, with no code change required** -- recorded as
regression evidence rather than an invented change: fresh/empty-database
integrated behavior (7 tests); adversarial backup/restore-preview
boundaries including truncated/garbage/tampered-metadata workbook bytes
(8 tests); Linked Source file-deleted/corrupted-between-preview-and-
confirm safety, closing a TOCTOU window the M18 suite never exercised (3
of those 8 tests); Analytics outcomes against six hand-computed
representative cases spanning every Primary Finding arbitration class,
plus `EvidenceProfileCache` cached/uncached equivalence (14 tests);
Data Tools synchronous-operation performance against a real 5,685-entry
production-database copy and a 6,000-row synthetic import (export
0.15s, import confirm 0.58s, XLSX backup 2.39s -- nowhere near the
Analytics HG2 material-impairment precedent of 137s); unwritable-
destination safety across every desktop write path and the audio-export
batch's per-Card publication-failure handling (11 tests); large/dense-
dataset boundedness (`get_card_page_for_collection` verified against a
240-entry/30-card Collection, `EvidenceProfileCache` against a
60-entry/480-event dense history); and background-thread completion
after navigation / shutdown behavior for the one controller with a
legitimately long-running load, probed through a real `MainWindow` (4
tests).

**Convergence evidence:**

```text
Full repository suite:        859/859 (offscreen, QT_QPA_PLATFORM=offscreen)
Architecture audit:            94 Python files, 0 serious, 0 warnings
Quiz randomization check:      passed
Privacy/tracked-file scan:     clean (full M19 diff, 833cc63..eb438c9 and
                                the destination/scale + background-nav
                                commits after it)
Native platform launch health: real Windows platform (not offscreen),
                                real top-level window found via process-
                                tree enumeration (PID 31420, title
                                "Vocabulary App", non-zero window
                                handle), clean graceful shutdown, no
                                orphaned process
Working tree / remote:         clean; local HEAD matches
                                origin/agent/m19-desktop-product-hardening
```

Native launch health above is **Agent Verified only** -- it proves the
real desktop process starts, produces a real window, and shuts down
cleanly on this machine's actual Windows platform. It is deliberately
not a substitute for visual/functional acceptance (AGENTS.md: "Automated
tests cannot establish visual quality"). At the time of this snapshot
the Final Human Acceptance Gate -- launching the app and leaving it open
for the operator's own inspection -- had not yet been presented. It was
subsequently presented, took three attempts, and PASSed; see "Final
Human Acceptance Gate — Attempt 3" below for the current, authoritative
outcome.

**Known limitations / deferred, not defects:** the SQLite
`ResourceWarning: unclosed database` noise under the test harness
(pre-existing, tracked in Known Risks below); the three deferred Accent
families and Quick Theme Control popover (M17-era, unchanged); advanced
Entries table personalization (M17-era, unchanged). No known
release-blocking defect, data-integrity/privacy/security defect, or
architecture-boundary violation remains open.

### Final Human Acceptance Gate — Attempt 1: FAIL (narrow UX corrective)

The operator launched the real native application from Exit Candidate
head `2dc0893` and recorded **FAIL** with two explicitly narrow UX
correctives (not a reopening of broader M19 scope): (1) Settings →
Audio's status load (~5-6s observed natively) had no visible loading
feedback; (2) the Navigation Rail order should read Today → Study →
Entries → Collections → Review Calendar → Templates → Data Tools →
Analytics (Settings unchanged, separate bottom position).

**Corrective applied.** Settings → Audio now shows an indeterminate
busy indicator immediately on load and swaps to real content once the
(deferred-by-one-tick) status resolution completes, regardless of how
long that resolution actually takes on a given machine
(`src/ui_desktop/views/settings_view.py`, styled via a new
`settings-audio-loading-spinner` QSS rule matching the existing
`analytics-progress-bar` pattern). The Navigation Rail's
`PRIMARY_DESTINATIONS` order was corrected to match exactly
(`src/ui_desktop/widgets/navigation_rail.py`); `SETTINGS_DESTINATION`
was already separate and unaffected. See `docs/qa/MILESTONE19_HARDENING_QA.md`
§ 9 for full investigation and verification detail.

Verification: affected navigation/Settings/desktop regression 378/378;
full repository suite 860/860; architecture audit clean (94 files, 0
violations); privacy scan clean.

### Final Human Acceptance Gate — Attempt 2: Sidebar PASS, Audio feedback FAIL

Re-checked at head `98119db`. **Navigation Rail order: PASS.** **Audio
loading feedback: FAIL**, with the location and treatment corrected by
the operator: the indicator belongs beside the **Data Tools → Audio
Export** button (not in Settings) and should be a progress ring that
starts hollow and fills to solid; the real symptom is that every other
Data Tools button responds instantly while Audio Export takes 6-7
seconds.

**Attempt 1's mistake:** it read the original report as the Settings
workspace and put the indicator there, even though its own
investigation had already identified the real culprit (the live
provider preflight reached from Data Tools) and measured Settings
itself at 6ms. The Settings-side indicator has been reverted in full.

**Root cause (measured):** `AudioExportDialog.__init__` ran
`voice_assignment_rows()` → `ProviderRegistry.preflight()` per frozen
language synchronously on the Qt UI thread before the dialog could
paint, and the Mandarin route's preflight shells out to
`powershell.exe` (`src/tts_providers.py`, 30s timeout). The cost is
environment-dependent and unbounded in practice -- one probe of the
same call inside a worker thread was still running past a 200s timeout
-- so the fix is to stop blocking on it rather than to optimize it.

**Corrective applied:** a new `_VoicePreflightWorker` runs the
preflight on a background `QThread` with truthful per-language
progress (real bound-method connections, generation guard, blocking
shutdown wired into `MainWindow.closeEvent`); a new `ProgressRing`
widget (`src/ui_desktop/widgets/progress_ring.py`) paints a
determinate hollow-to-solid arc, themed through the same
`apply_theme_tokens` seam the Entries Star column uses; and the Data
Tools hub shows the ring beside the button, fills it as each language
resolves, then opens the dialog seeded with the real results so the
cost is never paid twice. Repeated clicks cannot start two preflights
or open two dialogs.

Verification: 13 new tests; affected Data Tools/audio/settings/
navigation regression 172/172; architecture audit clean. A test hang
encountered during this work was diagnosed with a `faulthandler`
thread dump (a modal `exec()` with no user to close it, not a
threading defect) and a pre-existing timing-brittle assertion in
`tests/test_m19_background_task_navigation.py` was replaced with a
bounded wait. See `docs/qa/MILESTONE19_HARDENING_QA.md` § 10.

### Final Human Acceptance Gate — Attempt 3: PASS (Human Accepted)

The operator inspected the real native desktop application launched
from candidate head
`a128c50d75154ff3f85eacfd3a96e54d27d11c4d` and recorded **PASS**
(2026-08-18). Both Attempt 2 correctives were accepted: the Navigation
Rail order, and the hollow-to-solid progress ring beside the Data
Tools → Audio Export button with its background provider preflight.

This is the authoritative M19 acceptance decision.

**M19 status: Human Accepted — Desktop Product Hardening Complete on
`main`, ready to enter M20 Packaging and Release Candidate.** Per the
M19 contract § 18, the agent did not merge to `main` itself; the
operator reviewed and merged PR #30 directly.

Accepted product head: `a128c50d75154ff3f85eacfd3a96e54d27d11c4d`
Merged branch: `agent/m19-desktop-product-hardening` (PR #30, MERGED)
Merge commit on `main`: `2ad211711d96583b6fffdb65de912fa672502bc8`
Baseline: `9dae05c49caec8f2a33fdaf74d0a1f3fd1db43bc`

Final verification at the accepted head: full repository suite 872/872
(offscreen), architecture audit clean (95 Python files, 0 serious, 0
warnings), quiz randomization check passed, privacy/tracked-file scan
clean, native platform launch health agent-verified.

**Milestone 18 — Desktop Management and Major Feature Completion is
Complete on `main`** (merged via PR #29 at
`9dae05c49caec8f2a33fdaf74d0a1f3fd1db43bc` from final accepted head
`0ff85509f0cdb7248d7970b8af66c1da6a94c301`), developed under the M18
Autonomous Execution Contract on branch
`agent/m18-desktop-management-major-feature-completion` through PR #29.
Phases A through F (Human Gates 1, 2, and 3 all Human Accepted; Card
Audio Export; integrated exit verification) completed with no known
blocking defect.

**Human Gate 3 — Final M18 Native Acceptance: PASS (Human Accepted).**
Final native acceptance initially FAILed (see "Human Gate 3 corrective"
and "Human Gate 3 runtime recovery" below for the full record); a
diagnostic corrective was applied, verified, and independently
reviewed, and the retained M15 shared TTS runtime was then rediscovered
on this machine, audited read-only against the exact paths
`src/tts_providers.py` expects, bound temporarily via
`VOCAB_APP_SHARED_TTS_DIR` for verification only, and used to run a
real end-to-end Card Audio Export against the real production database
-- 2 of 2 Cards ready, 2 of 2 exported successfully to valid canonical
WAV files. The operator then independently launched the real desktop
application with the retained runtime bound the same way, verified the
real Card Audio Export happy path natively (legitimate Cards became
ready, `Start Export` became available, export succeeded), and recorded
**Human Gate 3 PASS**. **All three Human Gates are Human Accepted.**
The operator subsequently authorized the merge, and PR #29 was merged
to `main` at `9dae05c49caec8f2a33fdaf74d0a1f3fd1db43bc` — **M18 is
Complete on `main`.**

**Human Gate 1 — Management Grammar Calibration is complete and Human
Accepted.** Phase B implemented Collection Manager + Card Organization
(`e78764e`) and Template Manager + Template Editor (`0f5ae60`, a new
Templates workspace/rail destination), each delegating every read/write
to the existing `src.collections`/`src.entry_templates` core the
Streamlit Collections/Templates pages already use. Initial native visual
acceptance at `781d2a4` **FAILed** on two findings: Light Mode rendered
the new controls at effectively-invisible contrast (no explicit QSS
coverage existed for any control this checkpoint added -- the same
defect class M16.2's closure documented for Today/Entries navigation),
and existing Custom Templates had no discoverable entry point besides an
undocumented double-click gesture. Two corrective passes followed
(`5b3757c` root-cause QSS fix + discoverable "Open Template" action;
`283ab6f` a Templates-table selection-by-id integrity fix an independent
review of pass 1 found). **Native human visual acceptance PASSED
2026-08-17 against final accepted head
`283ab6f9298a7f64d2d311ffc11c01b2a186d2cf`.** See `ROADMAP.md` §
Milestone 18 for the full operating model and per-checkpoint acceptance
record.

**Phase C — Remaining Management/Data Workflows + Linked Source is also
complete.** Six checkpoints (Review Calendar / Card History; Settings
storage information; Data Tools Import/Export; Template Definition CSV
import/export; Backup / Restore Preview; Linked Source, the last
feature's first UI since M13 closed only its reusable core), each
independently reviewed and corrected before the next began -- see
`ROADMAP.md` § Milestone 18 for the full per-checkpoint record and the
Streamlit disposition table. Verified: full repository suite 723/723 at
final head `dc5401f461e8bef20f971910c40db587abd74144`; architecture
audit 83 files, 0 violations.

**Phase D — Analytics is also complete.** The Analytics Landing
workspace ("Learning Brief First", DESIGN.md § 6.5 CANONICAL
`VR-ANALYTICS-001`) and the Full Findings drill-down (§ 6.6
`VR-ANALYTICS-002`) (`c8e4f40`, corrected at `9b2b2c1`), built entirely
on the existing `src.insights`/`src.analytics` M14 core with no invented
scores or thresholds. This flips "analytics" -- the last disabled
Navigation Rail placeholder -- to enabled, so every destination in the
approved product IA (DESIGN.md § 4.1) now has a real workspace, and
finishes the M18-scoped `statistics_page.py`/`dashboard_page.py`
Streamlit disposition. Independent review found and fixed four real
issues before the first Human Gate 2 attempt (a misleading "Suggested:
None" label, scope labels that lost Collection/Template identity, an
unwired "show every current Entry" toggle, and a redundant double
reload).

**Human Gate 2 initially FAILed**: on a real production database,
opening Analytics made the app "Not Responding" (benchmarked root
cause: 137s in `get_all_findings`, from independently reloading and
recomputing the whole database's evidence profiles once per Collection
and again once per Card). Corrective pass `50597e7` fixed the root
cause with a shared `EvidenceProfileCache` (re-benchmarked at 0.71s,
~193x) and added a background `QThread` with staged progress/error UI
and stale-result guarding as defense-in-depth; independent review of
that pass found and fixed three more real defects (a cross-thread
signal race, a narrow-filter cache regression on an unrelated call
path, and a QThread shutdown-safety gap), and a fourth (a test-harness
segfault) was self-caught during re-verification. Full repository suite
re-verified green at `50597e7` (the same 5 pre-existing, unrelated
`test_m18_review_calendar.py` failures confirmed present on the clean
pre-corrective HEAD remain, out of scope for this corrective) and
architecture audit clean -- see `ROADMAP.md` § Milestone 18 for the
full record. Two further HG2-corrective passes followed real native
re-acceptance testing on a real production database: `9439be7`
(Appearance/Quiz combo boxes horizontally compressed/clipped at a
normal window size -- QSS `min-width` bump) and `8f57295` (root-cause
fix superseding it: the Settings page had no vertical `QScrollArea`, so
it could not grow taller than the window and re-created the same
squeeze whenever content grew -- wrapped in a native vertical
`QScrollArea`, horizontal scrolling explicitly disabled, 3 new focused
regression tests). **Human Gate 2 — Analytics Product Acceptance is
Human Accepted**, native visual acceptance PASSED against final
accepted head `8f572959f0239b3b866cb8af936c8c84e8f53170`. See
`ROADMAP.md` § Milestone 18 for the full per-checkpoint record.

**Phase E — Card Audio Export is also complete.** The desktop Card
Audio Export workflow (`AudioExportController` +
`AudioExportDialog`, DESIGN.md § 7.4 "Audio Export configuration: B,
`VR-UTILITY-001`") is a fourth Data Tools hub action, built entirely on
the existing `src.audio_export`/`src.audio_composition`/
`src.tts_providers` M15 core (no SQL, no second export engine). Scope:
Single Card / Selected Cards / Whole Collection (`src.audio_export`'s
existing scope model); voice configuration is deliberately READ-ONLY --
M15 froze provider/language routing and the M18 contract forbids
reopening it without an actual blocker, so this workspace confirms the
frozen per-language voice assignment rather than inventing a picker;
repetition mode/count and overwrite/skip conflict handling are the
genuinely configurable surface the roadmap names. Long-running work
follows Analytics' Human Gate 2 corrective precedent exactly: a
background `QThread`, a monotonic generation guard discarding a
superseded run's stale result, and worker signals connected to real
bound methods (never a lambda) for correct cross-thread queuing.
Cancellation is Card-atomic, added to `execute_audio_export_plan` as a
new `should_cancel` parameter and `cancelled` status (`src/audio_export.py`):
a Card already published stays published, every remaining Card comes
back `cancelled`, and `build_retry_plan` treats `cancelled` the same as
`failed`/`unresolved` -- a normal retry target. An independent
self-review pass (module docstring discipline) before checkpointing
found and fixed a real defect: several controller setters
(repetition/conflict/destination/card-selection) invalidated the built
Plan but never emitted `state_changed`, so the Start button's enabled
state and the consent checkbox's overwrite-warning text could go stale
after a config change -- fixed by emitting `state_changed` from every
one of them and resetting consent on every reload, the same
"confirmation checkbox must require fresh acknowledgment for every
state change" discipline Data Tools' Import Dialog corrective already
established. Full-suite verification also surfaced a second, unrelated
pre-existing defect: `tests/test_m18_settings_storage.py`'s Human Gate 2
scroll-area regression test measured a QComboBox's "natural width" via
`sizeHint()` before the widget was ever shown, which could intermittently
under-report once enough other GUI tests had run earlier in the same
`unittest discover` process and shifted global style/font-metric caching
state -- confirmed deterministic under the larger Phase E suite, not a
one-off flake, and not a real Settings layout regression (the sibling
scrollbar-orientation test in the same file passed throughout). Fixed by
measuring the natural width post-show/post-layout instead of pre-show,
the same way the test already measures the narrow-window width it
compares against.

Verified: 26/26 new focused tests (15 core `src.audio_export`
including 2 new cancellation/retry-of-cancelled tests, 11 new desktop
controller/dialog/QSS-coverage tests), full repository suite green
(778/778), and a clean architecture audit (87 files, 0 violations). This
finishes the M18-scoped audio-export Streamlit disposition (no legacy
audio-export UI existed to migrate or retire -- M15 closed only the
reusable core).

**Phase F — Integrated M18 Exit Verification** was completed at head
`aa0ad72`/`df78286`: full repository suite green (778/778), architecture
audit clean (87 files, 0 violations), no schema/migration change since
Human Gate 2, persistence-parity and Card-atomic cancellation/retry
evidence confirmed end-to-end through the real background `QThread`,
every `Workspace` cycled through a real `MainWindow` with 0 errors, the
Streamlit disposition table fully closed, and `docs/migration/DESKTOP_MIGRATION_PLAN.md`'s
Card Audio Export requirements all satisfied. See `ROADMAP.md` §
Milestone 18's Phase F entry for the full itemized record.

### Human Gate 3 corrective (Card Audio Export "0 of X ready" blocker)

**Human Gate 3 — Final M18 Native Acceptance FAILed.** Native
acceptance testing against head `df78286` found a blocking defect:
after configuring Card Audio Export and building a Plan, every Card
consistently showed unresolved ("0 of X Cards ready to export"), with
Start Export disabled and no visible explanation.

Investigated with real production data rather than guessing, per the
review's own instructions:

- `VOCAB_APP_SHARED_TTS_DIR` is unset in this desktop process's
  environment (confirmed via .NET `Environment.GetEnvironmentVariable`
  at User/Machine/Process scope, all empty) -- `ProviderRegistry.
  from_environment()` therefore falls back to an all-languages
  "unavailable" registry, and every Card's speech plan carries a
  `provider_unavailable`-class issue regardless of its content.
- No `kokoro`/`sherpa-onnx`/shared-runtime folder matching
  `build_shared_runtime_registry()`'s expected layout exists anywhere
  discoverable on this machine (a bounded search of the user profile and
  local drives found only the raw Kokoro-82M Hugging Face model cache
  and a populated `audio-cache` from an earlier session -- evidence real
  synthesis worked at some point, but the runtime that produced it is
  not present now).
- Swept all 715 active Cards across every real Collection in the
  production database (`data/vocab.db`) with a fake-but-realistic
  *available* provider: **100% become `ready` with zero issues.** No
  Card anywhere has a required-field/speech-role validation problem --
  the entire blocker is provider availability, not plan-building logic.

**Root cause: this machine's desktop process has no shared TTS runtime
configured** -- an environment prerequisite, not a code defect in the
Plan-building logic, which was proven correct against real data.

**Corrective (`555a47b`):** rather than enabling Start Export
unconditionally, fixed the actual reported problem -- the total absence
of an actionable reason:

- `AudioExportController.voice_assignment_rows()` now reports a live
  per-language preflight (`ProviderRegistry.from_environment().
  preflight()`), not just static provider/voice identity; the dialog's
  Voice Assignment panel gained a Status column showing e.g.
  "Unavailable — VOCAB_APP_SHARED_TTS_DIR is not set for this process."
  before the user ever builds a Plan.
- `src/tts_providers.py` gained a distinct
  `shared_tts_dir_not_configured` code/detail for the "no env var at
  all" case (previously indistinguishable from a configured-but-broken
  runtime), and `CommandSpeechProvider.preflight()`'s missing-asset
  message now names the actual missing path(s) -- same failure
  code/boolean as before, detail text only, so provider/language
  routing semantics are not reopened.
- The dialog gained a Plan Preview table showing every Card's own
  concrete reason (grouped by distinct issue code+detail, deduplicated
  across fields) instead of only the aggregate "0 of X ready" count.
  Partial-batch honesty is preserved and tested: a ready Card shows
  "Ready" with no reason, a not-ready Card shows its own real issue,
  never silently treated as ready.
- 4 new focused regression tests (live preflight status, unavailable
  detail text, per-Card plan-diagnostic rendering, and mixed-availability
  partial-batch honesty) plus the existing 15 core `src.audio_export` /
  11 desktop tests, all green (782/782 full repository suite),
  architecture audit clean.
- Independently self-reviewed before checkpointing: verified no test
  asserted on the exact provider-unavailable detail strings this
  corrective changed, confirmed the live preflight call is cheap in the
  common (unconfigured) case (no subprocess spawn), and confirmed
  `UnavailableSpeechProvider`'s new optional `detail` parameter is
  backward-compatible (default unchanged) with its only two callers.

**Per explicit operator direction, this diagnostic corrective is
sufficient for this defect; building a new shared TTS runtime is out of
scope for this corrective.** Real end-to-end Card Audio Export WAV
synthesis remains **unverified** on this machine and is recorded as an
explicit Human Gate 3 acceptance dependency: **Human Gate 3 has not been
re-presented, and M18 is not currently an EXIT CANDIDATE.** Human Gate 3
should be re-attempted once a `VOCAB_APP_SHARED_TTS_DIR` runtime is
available to verify against, or the operator otherwise instructs
resumption.

### Human Gate 3 runtime recovery (`VOCAB_APP_SHARED_TTS_DIR` resolved)

The retained M15 shared TTS runtime was rediscovered on this machine
(its own `README.md` self-identifies it as the shared,
project-independent runtime home created from Vocabulary App's M15.0
provider-selection audition). A read-only audit against
`src/tts_providers.py`'s exact
`build_shared_runtime_registry()` path expectations confirmed every
required asset is structurally intact and unmodified since M15 closure:
`venv\Scripts\python.exe` (Python 3.11 venv with `kokoro`, `sherpa_onnx`,
`numpy`, `soundfile`, `torch` installed), `kokoro\synth.py`,
`sherpa-onnx\synth.py` plus its `voices\vits-piper-fr_FR-siwis-medium\`
model directory. The repo-side `scripts\tts_yaoyao.ps1` adapter (used
directly, not sourced from the shared runtime) was already present and
unchanged. **No code defect existed** -- the only missing piece was the
environment binding itself.

With `VOCAB_APP_SHARED_TTS_DIR` pointed at the rediscovered runtime for
the verification process only (no permanent User/Machine change made):

- live preflight succeeded for all three frozen routes: `en`
  (Kokoro/af_heart), `fr` (sherpa-onnx/fr_FR-siwis-medium), `zh-CN`
  (Windows OneCore Yaoyao via WinRT);
- a real Audio Export Plan built against the real production database
  (`trial collection`, id 12, 2 active Cards) showed **2 of 2 Cards
  ready**, replacing the previous "0 of X ready" state;
- `execute_audio_export_plan()` ran a real small end-to-end export of
  both Cards: **2 succeeded, 0 failed, 0 unresolved**, producing real
  multi-unit-composed WAV files (37.12s and 51.73s), both verified
  against the app's canonical-WAV contract (`validate_canonical_wav()`);
  test artifacts were removed after verification.

**Human Gate 3's remaining acceptance dependency (a real, available
`VOCAB_APP_SHARED_TTS_DIR` runtime) is resolved on this machine.** No
repository code changed as part of this recovery. The temporary env
binding is process-scoped only; a permanent User/Machine
`VOCAB_APP_SHARED_TTS_DIR` value has **not** been set and is
left for the operator to configure (or re-bind per-session) as needed.
This resolved the runtime dependency and made Human Gate 3 READY for
native human acceptance (see "Human Gate 3 — Final PASS" below for the
operator's authoritative acceptance decision).

### Human Gate 3 — Final PASS (Human Accepted)

The operator independently launched the real desktop application with
the retained M15 shared TTS runtime temporarily bound through
`VOCAB_APP_SHARED_TTS_DIR` and verified the real Card Audio Export
happy path in native use: legitimate Cards became ready, `Start Export`
became available, and the real Audio Export workflow operated
successfully end to end. The operator recorded **Human Gate 3 PASS**.
This is the authoritative Human Gate 3 decision.

**Human Gate 1, Human Gate 2, and Human Gate 3 are all Human Accepted.
M18's product-acceptance exit criteria are satisfied. M18 is READY FOR
MERGE, pending explicit operator merge authorization into `main`.**

M16.0 Desktop UI Design Baseline is complete and frozen: [DESIGN.md](DESIGN.md)
records the approved desktop information architecture, theme architecture, and
accessibility rules. **M16.1 Desktop Architecture Foundation is complete on
`main`** through PR #21, merged at
`a1dc044721e9017d39842e96e0516a88a36d129f` from independently reviewed head
`439cc9612578b5dc78eda57e07f054bec8d60d38`. **M16.2 Minimal Desktop Vertical
Slice & M16 Exit is complete on `main`** through PR #23, merged at
`2e900d243950ca93aedf5cbde5b836dc6e378f25` from final reviewed head
`0e78e6f9c1892846e7b63d9696d2312dfcaa6b9a`. **Milestone 16 as a whole is
Complete on `main`**, closed after engineering review, SQLite-compatibility
review, AppState/state-boundary review, human native-window visual
acceptance, navigation-contrast acceptance, and desktop-launcher/icon
acceptance. See `ROADMAP.md` § Milestone 16 for exit criteria and
[Milestone 16 Closure](docs/history/MILESTONE16_CLOSURE.md) for full
evidence.

**Milestone 17 — Desktop Core Workflow Migration is complete on `main`**
(merged via PR #25), developed on the single long-lived branch
`agent/m17-desktop-core-workflow-migration`. It ran as one milestone: one
branch, one PR, and an ordered feature migration sequence (Today, Review,
Quiz, Quiz Presentation Choice, Entries, Minimum Collection Integration,
Theme Completion & Cross-Screen Validation, then Parity + Exit
Verification) rather than independent sub-milestone branches or PRs —
see `ROADMAP.md` § Milestone 17 for the full operating model, frozen
semantic boundaries, verification model, and per-checkpoint acceptance
record.

**Feature 1 — Today.** Its non-visual groundwork is implemented and
retained. A **third, fresh presentation** was implemented from the
replacement `DESIGN.md` design authority (`c19b686`) and its canonical
visual reference (`Today - Home.pdf` p2, Variant A). It went through two
visual-realization/calibration passes and one rendering-bug fix after
native visual acceptance FAILs, and **is now Human Accepted** at the
native visual acceptance gate: PASS recorded 2026-08-16 against commit
`fdd9cc0`. Per DESIGN.md § 2, this is Level 4 — Human Accepted, the only
level that closes a visual implementation requirement; structural tests
alone (Level 2) never could have.

Two earlier Today presentations were built and both were rejected before
this one; that history is preserved below, not erased:

1. The first implementation was rejected because the UI still read as
   default Qt widgets with token coloring rather than a designed product
   surface.
2. The follow-up visual-realization pass was **also rejected**: it
   improved polish and introduced a shared component grammar, but in
   doing so it replaced the approved spatial composition with a
   top-navigation / KPI-tile / full-width-table design of its own. Neither
   attempt is a valid Command Center, and this document does not describe
   either as one.

Throughout both rejections the automated suite was fully green. Structural
assertions — layout stretch factors, token contrast, component-role
coverage — cannot establish that an approved design was realized. That is
why human visual acceptance is a required gate (see the Human UI
Acceptance Delivery Pattern in `AGENTS.md`).

A **controlled reset** therefore removed the rejected presentation while
preserving design-neutral engineering. Reset to the M16.2 baseline:
`views/today_view.py` (back to the placeholder skeleton),
`theming/tokens.py` (the M17-added typography/spacing/radius/density
metrics removed so they cannot become implicit constraints on the
replacement design), `theming/theme_manager.py` (the M17 component grammar
removed; the earlier M16 `QToolButton` contrast fix preserved), and
`main_window.py` (M16.2 shell plus motion only — the M17 top-navigation
and brand treatment removed, and no replacement shell composition
introduced). Deleted outright:
`qt_models/learning_queue_table_model.py`, the `widgets/` primitives
package, and `tests/test_m17_visual_system.py`. The rejected commits
remain in branch history for audit; nothing was force-pushed away.

**Retained M17 engineering assets**, all independent of the rejected
composition:

- the **Motion / Transition Foundation** (`motion/transitions.py`,
  DESIGN.md § 25 in the current replacement authority): centralized
  `TransitionManager` with
  `Normal`/`Reduced`/`Disabled` policy, the `motion` durable preference,
  app-level wiring, and `MainWindow` decoration applied *after* each
  synchronous state change so motion never gates correctness. It also
  carries the animation-lifetime crash fix — animations are parented to
  the `QGraphicsOpacityEffect` they animate rather than to the long-lived
  manager, and the tracking dict keys by widget object rather than
  `id(widget)`;
- **`TodayController`'s read-only projections** over the unmodified
  `src.learning_workflow.get_today_overview()`: `queue_items()`,
  `primary_recommendation()`, `recent_activity()`,
  `collections_needing_attention()`;
- the **`LearningActionIntent` handoff contract** (`state/handoff.py`) and
  its fail-closed mapping: `card`/`random` → `quiz`, `suggestion` →
  `organize`, anything unrecognized → `unknown` (never guessed as
  `quiz`/`review`);
- the **Human UI Acceptance Delivery Pattern** in `AGENTS.md`.

These prescribe *what data Today reads and what a queue item means*, not
whether the final UI uses rows, cards, panels, a rail, or another approved
presentation. That is exactly what the fresh implementation below now
consumes.

**The replacement `DESIGN.md` was supplied and committed**
(`c19b686`, "Replace DESIGN.md with final design authority contract") and
is the authoritative canonical visual-reference and spatial-composition
authority for M17+. `DESIGN.md` was not modified to build this checkpoint.

**Fresh Today implementation (third presentation), built from that
authority, not from either rejected attempt:**

- a shared vertical left **Management Navigation Rail**
  (`src/ui_desktop/widgets/navigation_rail.py`, DESIGN.md § 5
  `VR-SHELL-001`) replaces the M16.2 `QToolBar` navigation. It shows the
  full approved product IA (Today, Entries, Collections, Study,
  Analytics, Data tools, Settings); only Today and Entries are wired to
  real workspaces, and every other destination is honestly disabled with
  a "not implemented yet" tooltip rather than a dead-looking active
  button;
- `TodayView` (`src/ui_desktop/views/today_view.py`) is a fresh
  three-region Command Center (DESIGN.md § 6.1 `VR-TODAY-001`): a
  central Command Workspace (compact 4-metric summary → Today's Learning
  Queue, the dominant visual anchor → Suggested Next Actions) plus a
  secondary, persistent right Context Rail (Recent Activity, Collections
  Needing Attention, Quick Actions);
- the compact summary intentionally reports this app's real metrics
  (Available Cards / Never Quizzed / Quizzed Today / Learned Today) from
  `TodayController` rather than the canonical mockup's "Due
  today"/"Mistake review" framing, which would imply a Review-due
  scheduling concept this product does not have (DESIGN.md § 6.1 product
  semantics, § 32 precedence: product truth over visual reference);
- every queue item still builds a real `LearningActionIntent`; any action
  that would launch Review/Quiz renders **honestly disabled** with an
  explicit tooltip, since neither is implemented in the desktop app yet.
  Only the real Entries destination is a live action;
- two small new modules — `theming/metrics.py` (compact spacing/radius
  constants) and `widgets/panels.py` (`SummaryStatCard`, `ActionRowCard`)
  — supply only the reusable grammar this checkpoint's rail and Today
  composition need; the deleted M17 primitive layer was not resurrected
  wholesale;
- Motion reuses the existing `TransitionManager.fade_in` for the rail's
  visibility swap and workspace switches; no new animation code was
  added outside `motion/transitions.py`.

`tests/test_m17_today_command_center_shell.py` (new, 14 tests) covers the
rail's honest-disabled-destination structure, the shell's rail/workspace
dominance, the Today region structure and dominance, and the functional-
honesty behavior above — structural proof only, per DESIGN.md § 2 Rule C,
not evidence that the canonical composition was visually realized.

**This third presentation's own path to acceptance** (macro archetype
confirmed correct at every review, never rebuilt from scratch):

1. First native visual acceptance on the third presentation — **FAIL**:
   under-realized (flat/borderless cards, dominant rail, queue overflow
   hid Suggested Next Actions, no right-rail section grammar). Fixed by
   visual-realization corrective pass #1 (`f917ccb`).
2. Second native visual acceptance — **FAIL**: density/rhythm too
   spacious versus the canonical sample, Suggested Next Actions read as
   a queue row instead of a small tile, right rail read as loose text,
   Quick Actions stretched full-width. Fixed by visual calibration pass
   #2 (`adb6882`).
3. Third native visual acceptance — **FAIL**: a genuine rendering bug
   (rail labels illegible at any font size). Root cause: `QAbstractButton`
   does not derive its `sizeHint()` from a child layout, so the rail
   items' icon+label content was crushed into an unrenderable sliver.
   Fixed with an explicit minimum height (`fdd9cc0`).
4. Fourth native visual acceptance — **PASS**, 2026-08-16, against
   `fdd9cc0`. Recorded as Human Accepted; see PR #25 for the full
   finding-by-finding record of each pass.

M17 implementation began from the verified `main` post-M16-closure commit
`c8842e0f77199ed9d3d0a2e3c48701d4289f137e` (PR #24 merge commit).

Verification for this checkpoint (last updated 2026-08-16, `fdd9cc0`):

```text
Implementation: COMPLETE
Structural conformance: PASS
Automated design guards: PASS
Native visual acceptance: PASS (Human Accepted, fdd9cc0, 2026-08-16)

Today Command Center + shell structure tests: 14/14 (tests/test_m17_today_command_center_shell.py)
Retained Today controller/handoff tests: 14/14 (tests/test_m17_today_controller_and_handoff.py)
Motion Foundation tests: 16/16 (tests/test_m17_motion_foundation.py)
M16.1 + M16.2 desktop regression: 33/33
Full repository suite: 248/248
Python compile check (all tracked .py): passed
scripts/audit_architecture.py: 66 Python files scanned, 0 serious, 0 warnings
scripts/check_quiz_randomization.py: passed
git diff --check: passed
```

No reusable core or schema/app-data version changed at any point;
`src/learning_workflow.py` is unmodified.

M16.1 selects **PySide6** as the desktop framework and freezes the
controller/view-state/core boundary, the initial `src/ui_desktop/` package
structure, the durable-vs-transient state taxonomy, the
`QThreadPool`/`QRunnable` background-task model, and the `QPalette`/QSS theme-
token implementation boundary. The full decision, license/distribution
finding, rejected alternatives, and technical-spike evidence are recorded in
[M16.1 Desktop Architecture Contract](docs/design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md).
A committed headless spike
(`tests/test_m16_1_architecture_spike.py`, 5 tests) proves PySide6
install/import, `QApplication`/window construction with event processing and
clean close (not a full blocking `QApplication.exec()` run/quit cycle), a
structurally-correct synthetic dense-table model/view surface (500 rows; not
a performance/responsiveness measurement), opening a temporary synthetic
database through the existing `src/db.py`/`src/app_config.py` path, calling
representative reusable core functions without Streamlit, a runtime
semantic-token style swap without restart, and a `QThreadPool`
worker-to-UI-thread signal handoff.
`requirements-desktop.txt` (new, additive) isolates the PySide6 dependency
from the Streamlit-only `requirements.txt`. `scripts/audit_architecture.py`
is extended to enforce the new `src/ui_desktop/` boundary the same way it
already enforces the Streamlit boundary. M16.1 adds no schema or app-data
migration, no product desktop UI, and does not alter learning, analytics,
import, or audio semantics.

PR #21 merged normally to `main` at
`a1dc044721e9017d39842e96e0516a88a36d129f`. Its independently reviewed final
head was `439cc9612578b5dc78eda57e07f054bec8d60d38`, which applied a
corrective patch to the initial implementation commit
(`703c7b42541d013f2ece5c453315632d23098ce6`) fixing evidence attribution
(the Toga rejection rationale, PySide6 licensing wording, and spike-claim
wording) and the durable-preference non-Windows path — no framework, state
taxonomy, package structure, or concurrency/theme boundary decision was
reopened by that correction.

Verification on 2026-08-14 passed:

```text
M16.1 spike tests: 5/5 (headless, QT_QPA_PLATFORM=offscreen)
Full repository suite including the spike: 166/166
Architecture audit (extended for src/ui_desktop/): 0 serious, 0 warnings
```

M16.2 builds the production `src/ui_desktop/` vertical slice against the
M16.1 contract without reopening it: a real bootstrap/shell
(`python -m src.ui_desktop`) with Today and Entries as native workspaces;
the Management ↔ Study chrome swap proven through `AppState`; a Today
controller consuming `get_today_overview()` unmodified; an Entries
controller/`QAbstractTableModel`/`QTableView` path over
`src.entries.search_entries()`; a Calm Blue Light/Dark theme pipeline
applying `QPalette` + QSS at runtime without restart; and durable
Appearance/Accent preferences persisted outside `vocab.db` via
`src/app_config.py:get_app_preferences_path()` (persistent config location,
never a cache directory, per the M16.1 contract). Background-task
infrastructure (`tasks/worker.py`) was deliberately not added: the
Today/Entries slice has no long-running operation that needs it. `AppState`
is structurally the single source of truth for active workspace and shell
mode: `MainWindow` renders whatever `AppState` holds at construction
(including an injected non-default workspace/mode) rather than hardcoding
Today/Management, and every transition path is proven to leave `AppState`
and the visible UI aligned. The SQLite compatibility proof exercises the
real desktop bootstrap (`build_application()`, including its own
`init_db()` call) reopening an already-populated synthetic database through
the real `VOCAB_APP_DB_PATH`/`get_database_path()` resolution, not just the
controllers in isolation. M16.2 adds no schema or app-data migration and
does not alter learning, analytics, import, or audio semantics. Full
evidence, including the SQLite compatibility proof and the human
acceptance evidence, is recorded in
[Milestone 16 Closure](docs/history/MILESTONE16_CLOSURE.md).

A human visual-acceptance pass found the Management-mode Today/Entries
navigation actions rendering with extremely low contrast, resembling
disabled controls — caused by `QApplication.setStyleSheet()` taking over
painting for every widget once set at all, leaving the unstyled
`QToolButton` without an explicit foreground. Fixed entirely through the
centralized `theming/theme_manager.py` QSS layer with explicit
`QToolButton`/`:hover`/`:pressed`/`:disabled` rules resolving paired
semantic tokens; no hardcoded one-off colors. `tools/setup_desktop_launcher.py`
(Windows-only, no new pip dependency) now creates a Desktop shortcut named
"Vocabulary App" that double-click-launches `python -m src.ui_desktop`
using `pythonw.exe` where available (no console window), with the
repository-owned `assets/icons/vocabulary_app.ico` as its icon and the
`QApplication`/`MainWindow` window icon. This is a development launcher,
not M20 packaging — no installer, no Nuitka/PyInstaller decision, no
standalone executable; the generated `.lnk` is machine/checkout-specific,
gitignored, and never committed.

Verification on 2026-08-15 passed:

```text
Focused M16.2 desktop tests: 38/38 (33 vertical-slice + 5 launcher)
M16.1 architecture-spike regression: 5/5
Full repository suite: 204/204 (161 existing + 5 M16.1 spike + 33 M16.2 slice + 5 M16.2 launcher)
Architecture audit: 59 Python files scanned, 0 serious, 0 warnings
Quiz randomization check: passed
Packaging readiness: expected local data/vocab.db exclusion warning only
```

A real (non-offscreen) launch was also attempted: the native `windows` Qt
platform plugin was confirmed active with one real screen detected, and the
application started, navigated to Entries with a synthetic entry loaded,
and shut down cleanly with exit code 0. This proves the app does not crash
on the real platform; it does not substitute for visual inspection. A
screenshot-based visual-verification attempt was aborted after it captured
the operator's live desktop instead of the application window and was
deleted immediately without being used as evidence. A final **targeted**
human acceptance pass confirmed three specific things: the desktop
shortcut launches the app without manual PowerShell interaction, the
repository icon appears correctly on the shortcut/application window/
taskbar, and the corrected Today/Entries navigation is visibly readable
after the contrast fix. The full `DESIGN.md` visual-acceptance checklist
was **not** re-run against the fixed build; broader Light/Dark, Entries
table usability, and full visual acceptance remain later M17/M19 work —
see
[Milestone 16 Closure](docs/history/MILESTONE16_CLOSURE.md) § Human
Acceptance Evidence for the exact scope of what was and was not
re-confirmed. Milestone 16 remains **Complete on `main`** through PR #23
at `2e900d243950ca93aedf5cbde5b836dc6e378f25`; none of its exit criteria
depend on the broader checklist having been re-run.

M15.3 adds a UI-independent snapshot-based Audio Export service for a single
current Card, an ordered Card selection, or all active Cards in a Collection.
It preserves one Card per canonical WAV, safe deterministic filenames, default
no-overwrite conflicts, per-Card atomic publication, structured partial-success
reporting, explicit failed/unresolved retry, and progress events. It adds no
schema or app-data migration and does not alter learning or Quiz semantics.

M15.3 PR #17 merged normally to `main` at
`9448f2e44940e0d426a965823aa66c48f53ec0f1`. Its independently reviewed final
head was `765c4c5f92c29a5c30cb41b0c2aa3fbbc01df7db`, based on the M15.2-complete
`main` commit `c9d7e8d05c968d52af2b77c76454f849706788bc`. PR #16 was superseded and its
lifecycle commit entered `main` through PR #17 ancestry. GitHub consequently
marks PR #16 merged, but it produced no separate merge commit.

Verification on 2026-08-13 passed:

```text
Focused M15.3 tests: 13/13
Integrated M15.1 + M15.2 + M15.3 audio tests: 41/41
Full repository suite: 161/161
Python compile/static check: passed
Architecture audit: 41 Python files; no violations or warnings
Packaging readiness: expected local data/vocab.db exclusion warning only
Real M15.3 Collection smoke: EN Kokoro + FR sherpa-onnx + ZH-CN Yaoyao passed
Real smoke outputs: 3 Cards = 3 readable canonical WAV files; temporary artifacts removed
```

M15.2 adds UI-independent content-addressed field audio assets and deterministic
current-Card composition. PR #15 merged normally to `main` at
`c9d7e8d05c968d52af2b77c76454f849706788bc` after the segment-sequence render
identity correction at head `71072e2386e7822f72282e7b2f432d522a6a3125`.
It adds no database migration; schema remains `15.1.0-speech-semantics` and
app-data remains `15.1`.

Unit identity includes exact text, canonical language, frozen provider/voice,
synthesis configuration, and format/contract versions while excluding Entry,
Field, Template, Collection, and Card identity. Card render identity includes
the final ordered segment sequence plus renderer, audio-contract, repetition,
and pause configuration. Generated mono
24 kHz signed 16-bit PCM WAV assets live in a configurable disposable local
filesystem cache outside authoritative learning data.

The current stable Card and latest revision define ordered Entry provenance.
Both Repeat Each Field and Repeat Whole Card are first-class deterministic
composition modes. Planning or generation does not mutate SQLite learning
state. M15.2 and M15.3 are complete on `main`, formally closing Milestone 15.
Substantial audio UI and spoken Quiz behavior remain deferred beyond M15.
Milestone 16 is complete on `main`; its M16.0 UI/Design Baseline is complete
and frozen in `DESIGN.md`. M16.1 Desktop Architecture Foundation is complete
on `main` (PR #21). M16.2 Minimal Desktop Vertical Slice & M16 Exit is
complete on `main` (PR #23, `2e900d243950ca93aedf5cbde5b836dc6e378f25`).
(Historical note, as of this 2026-08-13 snapshot: Milestone 17 — Desktop
Core Workflow Migration was the next objective and had not yet started.
Milestone 17 is now complete on `main` -- see "Current Milestone" above.)

Verification on 2026-08-13 passed:

```text
Focused M15.2 tests: 15/15
M15.2 + M15.1 compatibility tests: 28/28
Full repository suite: 148/148
Real M15.2 Card smoke: EN Kokoro + FR sherpa-onnx + ZH-CN Yaoyao passed
Canonical Card artifact: readable mono 24 kHz signed 16-bit PCM WAV
Generated smoke database/cache/audio: temporary and removed
```

M15.1 implements the UI-independent speech semantics and selected-provider
foundation. PR #13 merged normally to `main` at
`ebca2c2c5c6bf11f5e0a54b9782e15f08f51d216` after corrective invariant and
M13-era migration acceptance coverage at head
`760f260aebb306f14d8a38f5256a9290a30939e1`.

The additive migration advances schema version to
`15.1.0-speech-semantics` and app-data version to `15.1`. It adds persisted
field-level `speech_language_role`, assigns explicit roles to current system
Templates, and makes the approved French morphology fields required without
fabricating missing Entry values. Legacy custom required fields become
explicitly unresolved; optional fields become non-spoken.

Template Definition CSV v2 preserves speech roles and is now the default
export. Version 1 remains importable, with required fields unresolved rather
than guessed. `src/speech_semantics.py` builds deterministic required-field
plans from persisted roles and Entry/Explanation languages.
`src/tts_providers.py` preserves the frozen EN/FR/ZH routing, exposes controlled
preflight/failure results, and never silently falls back from Yaoyao.

Verification on 2026-08-13 passed:

```text
Focused M15.1 tests: 13/13
Full repository suite: 133/133
Real provider smoke: EN Kokoro, FR sherpa-onnx, ZH-CN WinRT Yaoyao passed
Generated smoke audio: temporary and removed
```

The frozen contract is recorded in
`docs/design/M15_1_SPEECH_SEMANTIC_CONTRACT.md`. Card composition, audio cache,
repetition modes, batch export, audio UI, and spoken Quiz behavior remain
outside M15.1. Existing Quiz learning semantics are unchanged. M15.1 is
complete on `main`; M15.2 remains unstarted and requires a new explicit prompt.

M15.0 started from the closed M14 baseline and completed TTS feasibility,
provider selection, Unicode verification, and license/attribution review. Its
authoritative closure was recorded on `main` at
`4dac641921701a8cc3b82ff80f507e9c63d5e188`.

Frozen provider routing:

- English: Kokoro-82M / `af_heart`;
- French: `sherpa-onnx` / `fr_FR-siwis-medium`; and
- Mandarin: Windows WinRT `SpeechSynthesizer` / Yaoyao (`zh-CN`), with no
  silent fallback when Yaoyao is unavailable.

The Yaoyao Unicode/mojibake issue is resolved. No license item is currently
recorded as `UNRESOLVED`. Reusable runtime/model assets remain external to the
repository and are represented portably as `<SHARED_TTS_DIR>`.

M15.0 also froze the requirement that the identified French morphology fields
be corrected to `required=1` and identified the missing explicit field-level
`speech_language_role`. M15.1 now implements those decisions without adopting
the audition heuristic as product behavior. No M15.2 Card-composition or cache
behavior has been implemented.

M14 began from synchronized `main` at
`98b6bc6567bc7bb61284344cd6452eb9cde11457` on branch
`agent/m14-learning-analytics-insight-core` after explicit product-owner
approval. After independent acceptance and the final Manual-QA
privacy/tracking audit, PR #10 was merged normally to `main` at
`880bda5c2bd0e8222af5489a9947469a333689ec`.

Batch A adds a reusable, Streamlit-independent, read-only analytics layer in
`src/analytics.py`. It derives eligible Quiz evidence, Entry Evidence Profiles,
Evidence State, freshness, recent/prior performance, trajectory, repeated
patterns, same-language Personal Baseline, current Card/Collection/Template
Coverage, historical Card revision context, and the distinction between
Collection Content Knowledge and Scope Activity.

The frozen product semantics are recorded in
`docs/design/M14_SEMANTIC_CONTRACT.md`. Batch A adds no schema change,
migration, persisted analytics state, user-facing Finding engine, Brief, or UI.
Existing Entry Health remains intentionally unchanged until Batch C.

Batch A verification on 2026-08-12 passed:

```text
Focused M14 Batch A tests: 11/11
Relevant M11/M13 regression tests: 73/73
Full repository suite: 98/98
Compile check: passed
Architecture audit: passed, no warnings
Packaging readiness: passed with the expected ignored local-database warning
```

Batch A was independently accepted at
`290494f328f17b14cf01cd81c47f6a72770510ac`. After explicit product-owner
authorization, Batch B added the reusable, Streamlit-independent,
deterministic interpretation layer in `src/insights.py`.

Batch B derives exactly one Primary Finding per current Entry, scope-level
Coverage Gap Findings, discrete priority, structured read-only actions,
same-Card compatible clusters, Brief-only Coverage hierarchy suppression, and
a deterministic Learning Brief capped at five items. Full Findings remain
separate from the lossy Brief. A global Brief resolves multi-Collection Entry
Card context deterministically; a Collection-scoped Brief preserves the
requested Collection context. Entry Health compatibility remains unchanged
until Batch C.

The verified Batch B correctness patch requires fresh evidence before an
urgent Needs Attention signal can upgrade from Medium to High; an otherwise
identical aging signal remains Medium. Cluster ranking metadata is derived
deterministically from supporting member Findings without rewriting their
individual priority, Evidence State, or reason codes.

Batch B verification on 2026-08-12 passed:

```text
Focused M14 Batch B tests: 17/17
Focused M14 Batch A regression: 11/11
Existing M11/M13 tests included in the full suite: 87/87
Full repository suite: 115/115
Compile check: passed
Architecture audit: passed, no warnings
Packaging readiness: passed with the expected ignored local-database warning
```

Batch B adds no schema change, migration, persisted Finding/Brief state, or
learning-state mutation. Semantic deviations: none.

After explicit Batch B acceptance, Batch C aligned the legacy Entry Health
surface with M14. Public function names remain available, but Weak,
Neglected, Strong, Proficient Risk, Mistake Recovery, overview, and Collection
weakness outputs are compatibility projections over M14 Evidence Profiles and
Primary Findings. The independent legacy threshold engine and obsolete
Streamlit threshold controls were removed. The Streamlit page received only
the minimum terminology and count changes needed to present M14 truth.

Verified Batch C implementation commit:
`7b667e578f0f36522ad2d07dfd64574661662165`.

Final Batch C acceptance-hardening commit:
`8b5df4576e16c10917edb2a00a869fe390c44983`.

Batch C verification on 2026-08-12 passed:

```text
Focused M14 Batch C tests: 5/5
Focused M14 Batch A regression: 11/11
Focused M14 Batch B regression: 17/17
Existing M11/M13 tests: 87/87
Full repository suite: 120/120
Compile/static check: passed
Architecture audit: passed, 36 Python files, no warnings
Packaging readiness: passed with the expected ignored local-database warning
Privacy/tracked-file audit: passed
```

The integrated synthetic acceptance used 100 current Entries and produced
exactly 100 Entry Primary Findings plus 15 Coverage Findings. Its deterministic
Top-5 Brief contained two High Needs Attention items, two High Collection
Breadth Gaps, and one Medium Stale Evidence item. Repeated execution was
identical and analysis changed no durable learning-table count.

M14 adds no schema change, migration, app-data-version change, persisted
analytics state, or learning-state mutation. Semantic deviations: none. M14 is
complete on `main`; its independent review and merge gate is complete.

M11.1 Semantic Alignment and QA Scope Lock has been merged to `main`.
M11.2 Unified Learning Flow and Core Integrity is merged to `main` at
`eb8cda4e50b987b5db37b36425d3e47c94c28eaa`.
M11.3 Stable Card Identity and Entry-Level History is merged to `main` at
`ccda6b8385215835f3de997f268e2165c37249de`.
M11.4 Semantic Re-acceptance and Baseline Closure was merged through PR #5 to
`main` at `f0e0d2c06fa4137c07ab2f892df117af2ed3a060`. Its independent review and
merge gate is complete.

M12 Repository Restructure began from synchronized `main` at
`0bce62833632e7e73bdc4daf4430ba028415adfd` on branch
`agent/m12-repository-restructure`. It moved 14 tracked supporting documents
with `git mv`, created `docs/README.md`, and repaired current repository
references without changing application behavior.

M12 verified restructure commit:
`b4c119a2eb0f88108ea93554355ee62ec5a72634`. A later documentation-only
metadata commit may be the Draft PR head.

M13 began from merged M12 commit
`6e339ec846f22f14ee454d9ad0d68ba3fb83aee6` on branch
`agent/m13-import-template-evolution`.

```text
M13 Batch A — Template Definition Portability independently reviewed / passed
M13 Batch B — Linked Append Source independently reviewed / passed
M13 Batch C — Integration, Regression, and Closure verified / complete
```

Batch A defines Template Definition CSV version 1 with these exact columns:

```text
definition_version
template_name
template_description
language
template_type
field_key
field_label
field_type
required
display_order
```

At M13 closure, the reusable core supported deterministic export, read-only
preview and full validation, explicit existing-name conflict handling, and
atomic confirmed import of one Template plus all fields. Imported definitions
always create a user-owned Template (`is_system = 0`). System ownership, internal IDs,
timestamps, Entry content, Entry field values, and database paths were not
portable fields. M15.1 subsequently adds `speech_language_role` through
Template Definition v2 while retaining v1 import compatibility.

Portable fields preserve their original non-negative integer `display_order`.
Ties are valid and use deterministic `(display_order ASC, field_key ASC)`
ordering for export, preview, and import insertion; values are not renumbered.

Batch A adds no schema or migration. Export/import round-trip verification
compares portable Template and ordered field semantics rather than internal IDs
or timestamps.

M13 Batch A verified correctness implementation commit:
`247652c56131b73f8bc582751c748e614dc7f890`. A later documentation-only
metadata commit may be the remote branch head during independent review.

Batch A passed independent review at branch head
`44fdde0fe79e6810b2cb1dc5a4fb3cbeea04dfab` and was merged through PR #8 to
`main` at `8574b31dde9b213fe83aade9583bf2e360fce0da`. The product owner then
authorized Batch B and Batch C on the same M13 branch. At that point, M14 had
not started; this records the historical M13 handoff rather than the current
lifecycle state.

Batch B implementation commit:
`633d7484874fbbf0beb7064e9abed9389414d9e4`.

Batch B adds one additive, idempotent migration:

```text
11.3.1-quiz-log-history
→ 13.0.0-linked-append-source
app_data_version = 13.0
```

The local-only `collection_source_links` table contains exactly:

```text
collection_id        INTEGER PRIMARY KEY
source_path          TEXT NOT NULL
source_type          TEXT NOT NULL        # csv | xlsx
import_mode          TEXT NOT NULL        # general_entry | template_aware
sheet_name           TEXT NULL
linked_at            TEXT NOT NULL
last_refreshed_at    TEXT NULL
```

Its Collection foreign key uses `ON DELETE CASCADE`. The linked file content,
source-row identity, row hashes, Entry mappings, and import history are not
stored. The metadata is included in database and XLSX backups.

The reusable Streamlit-independent core provides:

```text
get_collection_source_link(...)
preview_collection_source_link(...)
confirm_collection_source_link(...)
preview_linked_source_refresh(...)
confirm_linked_source_refresh(...)
unlink_collection_source(...)
```

Initial link and manual refresh rescan the current local CSV/XLSX through the
existing import engine and classify rows as New Valid, Invalid, or Duplicate.
Only New Valid rows can be appended after explicit confirmation. A readable
source with zero New Valid rows may still be linked. Preview is read-only;
confirmed writes use one transaction/savepoint for Entries, Collection
membership, Card-history reconciliation, link metadata, and refresh timestamp.

The linked file is non-authoritative. Source deletion, reordering, or editing
never deletes, reorders, or overwrites existing app Entries. App edits and
deletes never modify the source file. Because v1 deliberately stores no stable
source-row identity, an edited old row that becomes non-duplicate may later be
offered as New Valid and appended as another Entry. Missing or moved files
produce controlled errors while preserving the Collection, history, link, and
prior refresh timestamp. Unlink removes metadata only.

The existing General Entry and Template-aware import writers now reconcile
Card history on the same active connection even when the caller owns that
connection. Existing Collection Import explicitly defers per-row reconciliation
and continues to reconcile once per batch, avoiding history noise.

Before Batch C, `origin/main` and the reviewed Batch B branch were synchronized
with normal merge commit `5efaddc21a58e1610b2f8858dfd152507e1ec3c7`.
No upstream product changes existed beyond the known PR #8 Batch A merge.

Batch C verifies the combined M13 architecture end to end. A Template
Definition exported from one synthetic database imports as a user-owned
Template in another database and drives a template-aware Linked Append Source
without portable internal IDs. Shared `display_order = 0` fields remain
deterministic. Initial confirmation imports the Entry, field values, Collection
membership, Card revision, and source metadata atomically; unchanged refresh
imports zero and creates no history noise.

General Entry, Template-aware, and Collection import remain compatible.
Standalone duplicate `skip` and `import_anyway` retain their previous scope;
linked sources never expose `import_anyway`. Caller-owned transactions remain
rollbackable, while Collection Import defers row-level reconciliation and
creates one final Card-history reconciliation per batch.

Synthetic migration coverage proves the complete supported chain from
`10.6.0-baseline` through M11.3 to `13.0.0-linked-append-source`, direct M11.3
migration, failure rollback, fresh-schema convergence, and repeated-startup
idempotence without lost Entry, Collection, Quiz, Card, or link data. Database
and XLSX backups include link metadata. A copied database reopens cleanly; an
unavailable restored source path produces a controlled result without changing
Entries, Collection membership, Card history, link metadata, or refresh time.

Accepted M13 v1 limitations are:

- one linked source per Collection, manual refresh, and local CSV/XLSX only;
- `general_entry` and `template_aware` linked modes only;
- no source-row identity, hashes, overwrite, delete/reorder propagation,
  background watching, or desktop picker UI;
- an edited old row may appear as New Valid, and an app-deleted Entry may be
  offered again on a later refresh;
- a restored local source path may be unavailable on another machine; and
- Template Definition v1 is CSV-only, one Template per file, with no
  overwrite/merge/auto-rename, system ownership portability, or
  `speech_language_role`.

These are accepted scope limits, not data-integrity blockers.

```text
Milestone 12 Complete
Repository Restructure Complete
```

This is not Feature Freeze, Release Ready, Desktop Ready, Product Hardening
completion, or Current Version Complete.

The project is no longer preparing to freeze and release the existing
Streamlit application as the final current-version target.

Following full-product manual QA, real-world use, and product-owner review, the
scope has been reopened to:

- resolve correctness and data-semantic issues before migration;
- restructure the repository before another large development cycle;
- add reusable foundations for three new major capabilities;
- retire Streamlit as the long-term primary user interface; and
- complete the current product generation as a native desktop application.

## Product Direction

Vocabulary App remains a local-first, user-owned vocabulary learning system
built around a reusable Python + SQLite learning engine.

The strategic UI direction is now:

```text
Current Streamlit application
-> stabilized compatibility/reference baseline
-> native desktop application
-> desktop becomes the primary product
```

The governing migration principle remains:

> Replace the UI layer, preserve the learning engine.

Substantial new UI investment should target the desktop application rather than
the Streamlit interface unless a temporary Streamlit path is required to verify
reusable core behavior.

## Completed Historical Work

Milestones 1-10 remain completed historical development:

- Milestones 1-4: application foundation, entries, collections/cards, and
  review scheduling.
- Milestone 5: quiz sessions, learning pools, session safety, and quiz
  workflows.
- Milestone 6: entry templates, template-aware entries, template presets, and
  template-aware quizzes.
- Milestone 7: Statistics, Review Calendar, trends, and Entry Health.
- Milestone 8: CSV/XLSX import/export, backup generation, and restore preview.
- Milestone 9: Today and the daily learning workflow.
- Milestone 10: productization, repository documentation, architecture,
  packaging/migration assessments, app/schema metadata, and compatibility
  foundations.

These milestones established a substantial working Streamlit product baseline.

They do not represent the final desktop product or current-version completion.

## Full-Product Manual QA Status

A full-product manual QA artifact has now been established and used.

The latest reviewed QA set contains:

- 66 total items;
- 55 Pass;
- 6 Blocked;
- 5 Not Tested / N/A; and
- 0 Fail.

These counts do not mean the product is defect-free.

The QA process also identified:

- implementation defects;
- data/state semantic inconsistencies;
- UX and discoverability issues;
- stale historical acceptance expectations;
- documentation inconsistencies;
- product-design decisions;
- new feature requests; and
- areas requiring direct repository verification.

M11.1 reconciled all 66 stable QA IDs against the current repository and the
approved learning semantics:

- M11.2: 5 items;
- M11.3: 5 items;
- M11.4: 17 items;
- M12+/Desktop, M13, or Deferred: 12 items;
- stale expectation or verified no action: 27 items; and
- unable to verify from repository evidence: 0 items.

The counts above classify the QA inventory once per stable QA ID. Additional
repository-derived engineering findings are recorded separately in the M11.1
Draft PR and do not inflate the 66-item source total.

The original source results for M04-Q04, M05-Q05, and M07-Q02 remain Pass.
They are retained according to their own legacy-workflow meaning as
re-acceptance or superseded-expectation scope; they are not evidence for the
separate P1 finding that manual schedule updates are counted as completed
Review activity. That repository-derived finding is tracked independently as
`Derived M11-REVIEW-LOG-01` and does not change the source-item counts.

The manual QA artifact should remain a living project artifact and should be
updated only in sections affected by later milestones or regression work.

## Closed Pre-Desktop Priorities

### Entry Editing Integrity

M11.2 keyed editable state by permanent Entry ID. Automated Streamlit AppTest
coverage verifies that switching Entry A to Entry B does not leak unsaved
Language, Explanation Language, Entry Type, Status, canonical, Collection, or
Template-field widget state.

### Unified Review and Quiz Semantics

The approved authoritative model is:

```text
Browse / study a Card
-> complete a Card-scoped Quiz
-> one completed Card learning/review event
```

- Review is a Card browse/study/preparation surface and an entry point into
  Quiz. Browsing alone is not completion.
- A direct Card-scoped Quiz completion is valid without first entering Review.
- Quiz item activity remains the authoritative Entry-level performance
  evidence.
- A random or whole-pool Quiz remains valid performance activity but must not
  fabricate completion for an unrelated Card.
- Independent manual next-review scheduling, due/interval/ease state, and
  Again/Hard/Good/Easy are being retired from active product truth.
- No replacement SRS algorithm is approved for M11.

M11.2 enforces this model without adding a second event table:
`quiz_sessions.completed_at` is the Card learning-completion source for
completed Card-scoped Quiz sessions. Today, Statistics, and Learning History
derive Card completion only from that evidence. Manual scheduling and legacy
Review logs remain compatibility data but are no longer active completion
truth or active Streamlit workflow controls.

### Card Identity and Historical Truthfulness

The approved architecture resolves the product decision as follows:

- `entries.id` is the permanent authoritative Entry identity;
- Cards receive a stable durable `card_id`;
- `card_number` remains a display/order concept;
- Card membership remains user-mutable; and
- historical Card learning must retain the membership revision used at the
  time without false backfill.

M11.3 resolves the previous migration gap between:

- cards dynamically derived from collection order and `card_size`; and
- historical review/card records associated with collection and card number.

Current Card grouping remains dynamically derived from
`entry_collections.position + collections.card_size`. Stable `card_id` rows now
identify active slots, and immutable revisions record the ordered Entry IDs
that belonged to each Card at each material change.

The additive migration chain
`10.6.0-baseline -> 11.3.0-card-history -> 11.3.1-quiz-log-history`:

- establishes one active stable Card per current slot and one baseline revision;
- preserves active Card IDs across membership revisions;
- retires disappearing Cards and never reuses their IDs when a slot reappears;
- moves active Card names to stable identity while retaining the old metadata table as compatibility-only;
- binds new Card-scoped Quiz sessions to the exact `card_id` and `card_revision_id` used at start;
- leaves legacy pre-M11.3 Quiz composition null/unknown where it cannot be proved;
- records compact, field-level old/new evidence for successful non-no-op Entry edits;
- preserves existing `quiz_item_logs` after Entry hard deletion without
  inventing deleted Entry content; and
- requires an evidence-based Streamlit confirmation before user-driven cross-Card reorganization.

Collection mutation and Card-history reconciliation share one transaction.
Reads and ordinary Quiz activity create no Card revisions. The reusable core
remains Streamlit-independent and is suitable for a later native confirmation
dialog.

Known deletion boundary: Entry hard deletion preserves `quiz_item_logs`,
stored integer Entry IDs in Card revision snapshots, and
`entry_change_events`. Historical Quiz views fall back to
`Deleted Entry #<id>` plus the log's stored prompt/answer evidence.
Deleting an entire Collection retains the existing product behavior of
deleting that Collection's Card identity/revision history, legacy Review
history, Quiz sessions, and Quiz item logs. M11.4 accepts this as the current
destructive product contract because the UI requires the Collection name, an
explicit checkbox, and clear permanent-deletion wording. Vocabulary Entries
remain. No deleted-Collection preservation architecture is claimed.

M11.3 branch: `agent/m11-3-card-identity-history`.
M11.3 base: `eb8cda4e50b987b5db37b36425d3e47c94c28eaa`.
M11.3 verified implementation commit:
`f651a49271468c0442e75915f20a8b1aa17736e3`. The Draft PR head may include a
later documentation-only metadata commit; its exact head is recorded in the
Draft PR and closeout report.

M11.4 verification includes the complete M11.2/M11.3 regression suite plus
targeted stable-history, Entry Health, destructive Collection deletion,
restart/backup, stale-focus, duplicate-log, and edit-snapshot tests on isolated
synthetic databases. The complete suite passes all 38 tests, including the 6
targeted M11.4 closure tests. Python compilation, quiz-randomization,
migration-failure rollback, architecture, privacy, and packaging-readiness
checks also pass. The architecture audit scans 32 Python files with no serious
boundary violations or warnings. The packaging checker retains its expected
warning that the local personal database exists and must remain excluded from
Git/releases. No schema or migration file changes in M11.4.

M11.4 verified implementation commit:
`f0113e0592bf5198c429d3282c528c39b47f63fa`. PR #5 used documentation-only
head `b5c75ca52aa67f9fa5a7af7698358a709314d935` and merged as
`f0e0d2c06fa4137c07ab2f892df117af2ed3a060`.

Next engineering objective:
**Milestone 12 — Repository Restructure**.

### Entry Health

Entry Health remains an active compatibility surface over M14.

It is not deprecated.

Its interpretation is now derived from M14 Quiz-evidence semantics:

- Quiz attempts;
- correct/wrong outcomes;
- accuracy;
- recent performance;
- last-quizzed recency;
- Mistake Book;
- Proficient Pool; and
- related evidence.

Review count alone must not make an Entry Strong.

An Entry reviewed repeatedly but never tested can remain **Never Quizzed**.

M11.4 established that Entry Health must use Quiz evidence rather than Review
counts. M14 subsequently superseded the provisional Weak/Neglected/Strong/At
Risk thresholds with one authoritative Primary Finding per current Entry.
Legacy public API names now project Needs Attention, Stale Evidence, Strength,
Recovery, Never Quizzed, Insufficient Evidence, or None without creating a
second current diagnosis. Artificially high legacy `review_count` or
`correct_count` values still cannot change that truth.

## Other QA Findings Requiring Later Triage

QA findings assigned outside active M11 implementation include:

- partial Chinese/French localization;
- hard-coded Entry Type filter behavior that does not naturally cover custom
  types;
- whether the Status filter should remain as a product decision;
- lack of one unified configurable display-order model across canonical and
  custom fields;
- Template Import Preview not fully exposing dynamic `field:*` information and
  proposed Template-definition import, assigned to M13;
- duplicate/merge and wider import-matching ideas, assigned to M13/M14 or
  Deferred according to later approved scope;
- keyboard, narrow-screen, localization, and external-evaluator work assigned
  to the desktop/hardening lifecycle; and
- Ordered Quiz Queue editing being implemented but poorly discoverable,
  assigned to the later desktop experience.

The old M05-Q03 Again/Hard/Good/Easy expectation and Streamlit Release Candidate
recommendation items are stale QA expectations. The old QA reading guide's
`Review = exposure/history` plus manual-date model is also superseded by the
approved M11 semantics; the original local QA input remains unchanged as
historical evidence.

Streamlit-only polish does not receive the same priority as data correctness,
historical truthfulness, privacy, or reusable core behavior.

## Active New Product Scope

Three major capabilities have now been approved for active product development.

### 1. Import and Template Evolution

The intended scope includes:

- Template Definition export;
- Template Definition CSV import;
- one CSV file defining one Template;
- validated preview and atomic Template creation;
- round-trip Template portability;
- linking a Collection to a local CSV/XLSX append source; and
- refresh analysis identifying new valid, invalid, and duplicate rows.

Linked local files are append sources.

Version 1 does not synchronize:

- deletion;
- reorder;
- modification of existing rows;
- application changes back to the source file; or
- bidirectional conflicts.

Reusable core behavior is planned before desktop migration.

Desktop-native file selection and refresh interaction are planned after the
desktop foundation exists.

### 2. Learning Analytics and Insight System

Statistics is being repositioned from primarily metric display toward
explainable learning analytics.

The intended analytical model distinguishes:

- raw measurements;
- comparisons and trends;
- evidence sufficiency;
- interpretable findings; and
- actionable user recommendations.

Important analytical principles include:

- completed Card-scoped Quiz = Card learning/review completion;
- Quiz item logs = demonstrated Entry-level performance;
- sparse data must not produce overconfident conclusions;
- personal baselines and relative performance are more useful than isolated
  percentages;
- Entry Health remains interpretable rather than becoming an opaque global
  score; and
- the initial insight engine should be deterministic and testable rather than
  dependent on mandatory AI generation.

Core analytical semantics and logic are planned before desktop migration.

The major dashboard and visualization redesign is planned for desktop.

### 3. Card Audio Export

The intended initial audio scope is local audio export.

Key decisions include:

- exactly one Card per exported audio file;
- multiple Cards may be generated in one batch;
- Collection selection produces multiple Card audio files rather than one
  monolithic Collection recording;
- speech assets are conceptually associated with Entry/Field content;
- Card audio is assembled from current Card membership/order at export time;
- required Template fields are included in the initial audio scope;
- optional fields are deferred;
- supported repetition modes include per-field repetition and whole-Card
  repetition;
- English, French, and Chinese are the initial target languages; and
- local TTS technology should use a distribution-compatible license strategy.

Audio-enabled Quiz behavior is deferred beyond M15. M15 provides reusable
audio-export infrastructure only and must not add spoken Quiz modes or modify
existing Quiz learning semantics.

The reusable speech/provider and Card-composition foundation is planned before
desktop migration.

The full batch-generation UI is planned for desktop.

## Cross-Feature Architecture Dependencies

The three major capabilities are not independent.

### Template and Audio

Audio generation requires deterministic knowledge of the language associated
with required Template field values.

Template-definition work should therefore account for speech-language
semantics where needed, such as whether a field uses:

- Entry language; or
- Explanation language.

### Analytics and Data Semantics

Learning Analytics must not be finalized on top of ambiguous Review history or
untruthful Card history.

Review-event semantics and Card-history strategy are therefore prerequisites
for trusted analytics.

### Desktop and Reusable Core

Major new business logic should be implemented independently of Streamlit where
practical so that the desktop application calls reusable services rather than
reimplementing business rules.

## Repository Structure Status

The repository remains functionally usable but structurally cluttered at the
top level compared with the owner's other mature projects.

A dedicated repository-restructure milestone is planned before the next large
feature-development cycle.

The restructure should:

- reduce root-level document clutter;
- create clear locations for lifecycle, migration, manual QA, historical, and
  supporting documentation;
- preserve Git history through moves where practical;
- repair internal references; and
- avoid opportunistic business-logic refactoring.

The restructure has not yet been executed.

## Desktop Migration Status

Desktop migration is now active product scope.

The existing migration foundation is favorable:

- reusable core modules are already separated from Streamlit in many areas;
- SQLite remains the durable source of truth;
- import/export validation and execution are largely UI-independent;
- backup logic is largely reusable;
- durable Quiz state lives in SQLite/core logic;
- Today workflow queries are reusable; and
- architecture checks have previously confirmed substantial Streamlit/core
  separation.

However, no final desktop framework has yet been approved.

No minimal desktop shell has yet established production-level compatibility.

`docs/migration/DESKTOP_MIGRATION_PLAN.md` has been revised as part of the current lifecycle
alignment to remove the superseded Streamlit-first Release Candidate
prerequisite.

## Streamlit Status

Streamlit remains temporarily supported as:

- the current runnable UI;
- a reference implementation;
- a manual verification surface where useful; and
- a temporary fallback during migration.

It is no longer the long-term primary UI target.

New Streamlit work should generally be limited to:

- correctness;
- data integrity;
- privacy/security;
- migration blockers;
- serious workflow defects; or
- minimal validation of new reusable core capabilities.

Large new Streamlit-specific UI investments should be avoided.

## Feature Freeze Status

**ACTIVE as of Milestone 19 (2026-08-18).**

The intended desktop product scope was implemented and verified through
M17/M18 (all Human Gates accepted; M18 merged via PR #29). The desktop
Feature Freeze is now in effect: correctness, data-integrity,
migration/compatibility, privacy/security, robustness, serious UX, and
material performance defects remain in scope; new product modes,
learning systems, analytics concepts, synchronization models,
cloud/account functionality, and speculative redesigns move to deferred
work unless scope is explicitly reopened through a recorded decision.

The earlier planned Streamlit Feature Freeze was never passed and was
superseded by the reopened product scope; the freeze now applies to the
desktop product.

## Hardening Status

**Milestone 19 — Desktop Product Hardening is Complete on `main` and
Human Accepted** (2026-08-18, accepted product head
`a128c50d75154ff3f85eacfd3a96e54d27d11c4d`, merged via PR #30 at
`2ad211711d96583b6fffdb65de912fa672502bc8`; baseline
`9dae05c49caec8f2a33fdaf74d0a1f3fd1db43bc`). See "Current Milestone"
above for the full evidence record and the three Final Human
Acceptance Gate attempts. **Milestone 20 — Packaging and Release
Candidate has reached RC Engineering Exit Candidate with Human RC
PASS granted; see "Current Milestone" above for the full evidence
record.** Not yet merged to `main` — awaiting separate operator
authorization to merge, tag, and publish.

However, pre-desktop stabilization and full-product manual QA have already
identified issues that must be corrected before major migration work.

The new lifecycle separates:

**Pre-Desktop Stabilization**

from:

**Desktop Product Hardening**

This avoids spending full release-hardening effort on a Streamlit interface
that is scheduled for retirement.

## Verification Status

### Automated Checks

Historical repository checks have included Python compilation, architecture
audits, and packaging-readiness checks.

For the 2026-08-09 lifecycle-alignment change:

- `scripts/audit_architecture.py` scanned 30 Python files and reported no
  serious boundary violations or warnings;
- affected Markdown links and directly referenced repository paths resolved;
- the documentation diff contained no Python source changes; and
- full product regression was intentionally not run because this was a
  documentation-only lifecycle change.

These checks must be rerun as appropriate against each significant engineering
milestone baseline.

For M11.4:

- the complete automated suite passed all 38 tests;
- all 6 targeted M11.4 closure tests passed;
- quiz-randomization and Python compilation checks passed;
- `scripts/audit_architecture.py` scanned 32 Python files and reported no
  serious boundary violations or warnings;
- packaging readiness passed with only the expected local-database exclusion
  warning; and
- `git diff --check` passed, with no schema or migration file changes.

For M12:

- the complete automated suite passed all 38 tests;
- Python compilation and Quiz-randomization checks passed;
- `scripts/audit_architecture.py` scanned 32 Python files and reported no
  serious boundary violations or warnings;
- packaging readiness passed with only the expected local-database exclusion
  warning;
- 32 tracked relative Markdown links were resolved with zero broken links;
- current plain-text references to all 14 moved documents were repaired;
- the final root contains only durable entry points plus intentional source,
  test, support, data-placeholder, sample, and documentation directories;
- privacy/tracked-file and `git diff --check` audits passed; and
- no `app.py`, `src/`, test, schema, migration, or runtime behavior file changed.

For M13 Batch A:

- all 22 focused Template Definition tests passed;
- the complete automated suite passed all 60 tests;
- Python compilation and Quiz-randomization checks passed;
- `scripts/audit_architecture.py` scanned 33 Python files and reported no
  serious boundary violations or warnings;
- packaging readiness passed with only the expected local-database exclusion
  warning;
- privacy/tracked-file and `git diff --check` audits passed; and
- no schema, migration, Streamlit UI, linked-source, analytics, audio, or
  desktop implementation was introduced.

For M13 Batch B:

- all 21 focused Linked Append Source test methods passed, covering the 26
  required migration, CSV/XLSX, classification, transaction, non-authoritative
  source, missing-source, unlink, Card-history, and backup behaviors;
- the complete automated suite passed all 81 tests;
- Python compilation and Quiz-randomization checks passed;
- `scripts/audit_architecture.py` scanned 34 Python files and reported no
  serious boundary violations or warnings;
- packaging readiness passed with only the expected warning that the local
  `data/vocab.db` must remain excluded; and
- no Streamlit UI or desktop UI implementation was added.

For M13 Batch C:

- all 6 focused integration/closure tests passed;
- combined Batch A + Batch B + Batch C focused tests passed all 49 tests;
- the complete automated suite passed all 87 tests;
- migration, transaction, import, Card-history, backup/reopen, restored-path,
  and privacy assertions passed using synthetic databases and files only;
- Python compilation and Quiz-randomization checks passed;
- `scripts/audit_architecture.py` scanned 34 Python files and reported no
  serious boundary violations or warnings;
- packaging readiness passed with only the expected local-database exclusion
  warning; and
- no Streamlit UI, desktop UI, analytics, audio, or M14 implementation was
  introduced.

For M11.1, repository evidence was inspected across Entry editing, Review,
Quiz, Today, Statistics, Collection/Card mutation, schema, backup metadata, and
user-facing exception paths. M11.1 changes documentation only; validation
results are recorded in its Draft PR.

### Manual QA

Full-product manual QA now exists and has produced a baseline acceptance and
triage dataset.

Status:

**Established and closed for M11. All 66 QA IDs were reconciled by M11.1; all
17 IDs assigned to M11.4 have one final disposition in
`docs/history/MILESTONE11_CLOSURE.md`. No ambiguous M11-scope QA item remains.**

### Existing Database Compatibility

Additive schema/app metadata and migration foundations exist.

Existing SQLite databases remain protected assets and must continue to open
through later desktop development.

Future schema changes for analytics, Template speech metadata, or audio caching
must remain additive, versioned, backup-aware, and
compatibility-tested.

Status:

**M11 migration baseline verified through fresh, representative legacy,
intermediate, repeated-startup, rollback, and backup-readability scenarios.**

### Privacy and Secret Safety

The public repository must continue excluding:

- personal databases;
- imported vocabulary files;
- exports;
- backups;
- generated audio;
- logs containing private learning data;
- secrets;
- local caches; and
- private path information.

Privacy checks must be repeated after repository restructuring and before every
release candidate.

### Packaging

The existing Streamlit/source distribution is no longer the final intended
Release Candidate target.

Native desktop packaging remains future work after desktop functionality and
hardening.

Status:

**Desktop packaging not started.**

### Remote Repository Verification

On 2026-08-09, immediately before the lifecycle-alignment branch was created:

- branch: `main`;
- local `HEAD`: `16c21d173e8ebbb486c6f87b03fc047d2cf02e7a`;
- fetched `origin/main`: `16c21d173e8ebbb486c6f87b03fc047d2cf02e7a`;
- default remote branch: `main`; and
- local `main` matched the fetched remote branch.

The lifecycle-alignment PR was merged to `main` as:

`f5ce774bc6645d8e6b0e80dbef71c77158c98de8`

M11.1 started from that synchronized local/remote baseline on branch
`agent/m11-1-semantic-alignment`. Its own commit and Draft PR are recorded by
Git/GitHub rather than embedded recursively as this file's own commit identifier.

M11.1 was merged to `main` as:

`daf505b4fce0760af0c4c1eb97effcc9c0b74849`

M11.2 started from that exact synchronized commit on branch
`agent/m11-2-unified-learning-flow`.

Status:

**M11.1, M11.2, M11.3, and M11.4 are merged. The trustworthy pre-desktop
baseline is established on `main` at
`f0e0d2c06fa4137c07ab2f892df117af2ed3a060`.**

## Known Risks

- Deleting an entire Collection intentionally deletes its associated
  Card/Review/Quiz history after explicit confirmation; this is an accepted
  current product contract, not a retention promise.
- Legacy scheduler state and logs remain in the schema for compatibility even
  though active M11.2 UI and completion reporting no longer use them.
- SQLite connection cleanup emits ResourceWarnings under the isolated M11.2
  test harness; this does not affect test results but remains technical debt.
- Active Quiz recovery combines durable session state with transient UI state.
- Dense table and selection workflows depend on Streamlit behavior and must be
  redesigned deliberately for desktop.
- Today/Review/Quiz focus routing requires explicit desktop controller design.
- Date/local-time behavior requires desktop and packaged-environment
  verification.
- Linked-source local file paths introduce portability and unavailable-file
  scenarios that require controlled handling.
- Learning Analytics can become misleading if built before measurement
  semantics are corrected.
- Local TTS introduces model/runtime size, packaging, performance, and license
  obligations.
- Existing user-data migration to an eventual desktop application-data
  directory must remain explicit and reversible.

## Unknown or Unverified

- Large/dense dataset behavior under the future desktop UI.
- Desktop framework selection.
- Desktop accessibility and interaction model.
- Linked-source behavior with moved, renamed, unavailable, or malformed files.
- Final Analytics thresholds and evidence-sufficiency rules.
- Packaged-runtime performance and operational behavior for the selected TTS
  providers.
- Final M15.1 field-level `speech_language_role` contract and migration defaults.
- Audio-generation performance on representative hardware.
- Native packaging and clean-machine installation.
- Existing-data migration and rollback in packaged desktop form.
- Final public project license and third-party notice set.

## Deferred Features

The following remain outside the current active product scope unless explicitly
reopened:

- bidirectional local-file synchronization;
- automatic deletion/reordering of Collection data based on linked source
  files;
- advanced source conflict resolution;
- audio generation for optional Template fields;
- Audio Quiz / listening-Quiz integration;
- pronunciation assessment;
- mandatory AI-generated analytics;
- dictionary integrations;
- cloud sync;
- accounts and authentication;
- destructive/full database restore; and
- additional learning modes not required by the current product promise.

## Current Development Sequence

The approved high-level sequence is:

```text
M11  Pre-Desktop Stabilization
-> M12 Repository Restructure
-> M13 Import and Template Evolution Core
-> M14 Learning Analytics and Insight Core
-> M15 Audio Foundation
-> M16 Desktop Architecture and UI Design
-> M17 Desktop Core Workflow Migration
-> M18 Desktop Management and Major Feature Completion
-> M19 Desktop Product Hardening
-> M20 Packaging and Release Candidate
```

## Milestone 12 Closure Result

The repository root now retains the durable project entry points while
historical, QA, migration, policy, and packaging documents have clear homes
under `docs/`. `docs/README.md` is the supporting-document navigation index.

The existing flat `src/` core-module layout, `src/ui_streamlit/`, `tests/`,
`scripts/`, `tools/`, and `app.py` were intentionally left structurally and
behaviorally unchanged. Consolidating `scripts/` and `tools/`, decomposing
large core modules, and changing runtime package layout are deferred because
they would add churn without M12 user value.

## Milestone 13 Closure Result

Milestone 13 is complete. Template Definition Portability, Linked Append
Sources, migration convergence, existing import compatibility, Card-history
truth, backup/reopen readiness, privacy documentation, and architecture
boundaries passed the Batch C closure gate.

Batch A was merged separately through PR #8. Batch B plus Batch C were merged
through PR #9, bringing the complete M13 closure state onto `main` at
`b435c97cf48a7de22b417dec0a13775604ebd6d7`.

Batch C verified closure commit:
`9b3ea9ec50682f61ac55470b0ae5b189506ded81`.

Final M13 PR: #9, **M13: Complete import and template evolution core**. It was
merged from the verified Batch B + Batch C closure head. The M13 review and
merge gate is complete.

## Milestone 14 Closure Result

Milestone 14 is complete. The frozen semantic contract, read-only Evidence
Profiles, Coverage and Personal Baseline analytics, deterministic Findings and
Learning Brief, and Entry Health compatibility projections passed the Batch C
closure gate.

The accepted M14 branch head was
`8b5df4576e16c10917edb2a00a869fe390c44983`. PR #10, **M14: Complete learning
analytics and insight core**, was merged normally to `main` at
`880bda5c2bd0e8222af5489a9947469a333689ec`. The M14 review and merge gate is
complete.

## Next Objective

**Independently review and obtain native human visual acceptance for
Quiz (feature 3)**, now implemented on the same branch against
`VR-STUDY-001` (`Review - Quiz.pdf` p4 Variant C, parent pattern P3 --
Immersive Study). Structural conformance and automated design guards are
PASS; native visual acceptance is PENDING. Do not mark Quiz or Milestone
17 complete, and do not begin Entries (feature 4), until that review and
acceptance both close. (Historical note: this directive was current as
of the Quiz/feature-3 review point; Quiz was subsequently Human
Accepted, and Milestone 17 as a whole is now complete on `main` -- see
"Current Milestone" above.)

Milestone 16 is complete on `main` (PR #23,
`2e900d243950ca93aedf5cbde5b836dc6e378f25`). Post-M16 lifecycle
reconciliation merged through PR #24 at
`c8842e0f77199ed9d3d0a2e3c48701d4289f137e`. M17 is one milestone: one
long-lived branch (`agent/m17-desktop-core-workflow-migration`), one PR
(PR #25, Draft throughout development, merged 2026-08-17), and an
ordered feature migration sequence — Today, Review, Quiz,
Entries, minimum Collection integration, then parity/exit verification —
rather than independent sub-milestone branches or PRs. See `ROADMAP.md`
§ Milestone 17 for the full operating model, frozen semantic boundaries,
and verification model.

Today (feature 1) is **complete and Human Accepted** (third presentation,
fresh from the replacement `DESIGN.md`): its non-visual controller/handoff
groundwork, the Motion Foundation, and a Command Center presentation with
a shared Management Rail are all in place, structurally conformant, and
**native human visual acceptance PASSED** on 2026-08-16 against `fdd9cc0`
— after two earlier presentations were rejected pre-reset and this third
presentation itself went through two visual-calibration passes and one
rendering-bug fix before acceptance.

Review (feature 2) is **complete and Human Accepted**:
`ReviewController` projects the current Card roster, Entry composition,
and factual completed-Quiz history entirely through existing
`src.learning_workflow`/`src.collections` reads; `ReviewView` implements
the frozen Immersive Focus composition (Management Rail hidden, one
minimal session bar, one dominant learning surface, a transient right
Card Contents/History drawer reusing the shared `TransitionManager`).
**Native human visual acceptance PASSED** on 2026-08-16 against `38d53d2`.
Browsing a Card created no Quiz session and touched no legacy
`src/review.py` scheduling state (regression-tested).

Quiz (feature 3) is **complete and Human Accepted**: `QuizController`
owns active-session presentation state only, calling existing
`src.quiz`/`src.template_quiz` functions for every session/generation/
grading/completion step (no SQL, no duplicated grading logic). It
preserves all nine current Quiz families (term/meaning self-graded and
MCQ, mixed MCQ, Matching, and the three template-aware modes), the
single-global-active-session guard, duplicate-submission protection, and
Mistake Book/Proficient Pool side effects. Plain Matching stays
whole-Collection only (normalized inside the controller even if a
Card-scoped intent slips through); template-aware Matching stays
Card-scoped, since no core function generates a whole-Collection
template-matching set. Review's Quick Quiz / Choose Quiz Type and Today's
Learning Queue "quiz" action perform a real launch through this one
controller instead of the transitional honest-unavailable state.
`QuizView` implements the Immersive Focus session bar, self-graded/MCQ/
Matching task surfaces, a P6 restart/cancel confirmation, a
foreign-active-session recovery notice (never a fake resume), a compact
completion summary (Return to Today / Next Card / Review Mistakes), and a
read-only post-Quiz mistake-review state. **Native human visual
acceptance PASSED 2026-08-16 at head `311762c`**, after two corrective
passes: a typography/spacing visual-calibration pass against
`VR-STUDY-001` (`0660214`), and a UX-defect pass fixing long-content
clipping (a QScrollArea/box-layout heightForWidth negotiation
imprecision), Matching wheel-scroll/selection-rebuild instability, and
Review Mistakes routing (`311762c`). (Historical note: at this point in
the M17 checkpoint sequence, Milestone 17 was not yet complete; M17
Feature 3B (`VR-STUDY-002` Quiz presentation choice) is complete and
Human Accepted; see below. Milestone 17 as a whole is now complete --
see "Current Milestone" above.)

M17 Feature 3B — Quiz Presentation Choice (`VR-STUDY-002`, Quiz-only) adds
a second, optional Quiz presentation, Flip Card + Filmstrip
(`Review - Quiz.pdf` p5 Variant D), alongside the accepted Immersive
Focus default — not a redesign or replacement of feature 3. One durable
preference (`quiz_presentation`, `state/preferences.py`, never
`vocab.db`) is set from a new minimum Settings vertical slice (Settings →
Quiz → Quiz presentation) and resolved once per Quiz launch. Self-graded
and MCQ (including template-linear types) render inside a bordered Flip
Card + a non-interactive orientation filmstrip when selected; Matching
always falls back to the existing wider Immersive Matching presentation
regardless of the preference (a compatibility fallback that never alters
the saved preference). Completion and mistake review remain the single
shared Immersive-styled surfaces for both presentations — one Quiz
engine, two presentations. `VR-STUDY-002` explicitly does not propagate
outside Quiz (DESIGN.md § 6.4). **Native human visual acceptance PASSED
2026-08-16 at head `c54468e`** — Quiz Presentation Choice is complete and
Human Accepted (DESIGN.md § 2 Level 4), Milestone 17's fourth accepted
feature. See PR #25 (merged) for the full acceptance record.

M17 Feature 4 — Entries (`VR-ENTRIES-001`, `Entries & Collections
Manager.pdf` p3 Variant B, parent pattern P2) replaces the M16.2
architecture-proof placeholder with the real Table-First workflow.
`EntriesController` owns scope/filter/selection/editor-orchestration
state only, calling existing `src.entries`/`src.collections`/
`src.entry_templates`/`src.text_parser` functions for every read/write
(`search_entries`, `create_entry_with_template`,
`update_entry_with_template`, `delete_entries`,
`parse_and_validate_entry_card`, `update_entry_collections`) — no SQL, no
duplicated template validation/canonical-field-resolution/Card-history-
reconciliation logic. `EntriesView` implements the frozen composition
(Management Rail → Scope Pane → compact toolbar → dominant Entries Table
→ subordinate horizontal Entry Detail): the Scope Pane surfaces explicit
"Scope" (All Entries, the three system collections) and "Collections"
(real user Collections) sections behind a bounded user-resizable
`QSplitter`; the table uses real native multi-row selection plus an
explicit checkbox column and header "select all visible" affordance, all
sharing one selection truth, with selection restored by id across
refresh; Add/Edit use one P5 focused `_EntryEditorDialog` (template-
locked on Edit, dynamic per-template fields, manual canonical
Term/Meaning only when the template's mapping needs them, a scrollable
form body with a pinned Save/Cancel footer); Quick Add migrates the
still-live structured-text-card flow; Delete/batch-collection-removal
always go through the existing `CrossCardMoveConfirmationRequired` gate
(`src.collections`), never bypassed, with delete confirmation copy that
explicitly distinguishes permanent deletion from removing an Entry only
from the current Collection. One small batched core query
(`get_collection_names_for_entries`) was added to `src/collections.py` to
avoid an N+1 per-row query for the table's Collections column — the only
core addition, not raw SQL in the desktop layer. A first native visual-
acceptance pass (`9f63813`) found typography, toolbar-layout, Scope-Pane-
resizing, editor-scroll-safety, "Add to Collection" menu-interaction, and
checkbox-selection defects; a corrective pass (`2cc3332`) recalibrated
typography against the canonical hierarchy, split batch actions into
their own conditional row, replaced the fixed-width Scope Pane with a
bounded resizable splitter, made the Add/Edit dialog scroll-safe,
anchored the "Add to Collection" menu below its button (fixing a Qt/
Windows popup-dismissal interaction bug) with explicit `QMenu` QSS, added
the checkbox column/header-select-all affordance, and reworded the hard-
delete confirmation. **Native human visual acceptance PASSED 2026-08-16
at head `2cc3332`** — Entries is complete and Human Accepted (DESIGN.md
§ 2 Level 4), Milestone 17's fifth accepted feature. See PR #25 (merged)
for the full corrective-pass and acceptance history.

## Repository State

- Completed M14 branch: `agent/m14-learning-analytics-insight-core`
- M14 base commit: `98b6bc6567bc7bb61284344cd6452eb9cde11457`
- Accepted M14 Batch A head:
  `290494f328f17b14cf01cd81c47f6a72770510ac`
- Accepted M14 Batch B correctness head:
  `1ca61e6714e5bc84cd34a51287d4981c928a9752`
- Verified M14 Batch C implementation commit:
  `7b667e578f0f36522ad2d07dfd64574661662165`
- Accepted M14 branch head:
  `8b5df4576e16c10917edb2a00a869fe390c44983`
- Final M14 PR:
  `#10 — M14: Complete learning analytics and insight core` (merged)
- M14 merge commit on `main`:
  `880bda5c2bd0e8222af5489a9947469a333689ec`
- M15.0 closure baseline on `main`:
  `4dac641921701a8cc3b82ff80f507e9c63d5e188`
- M15.1 implementation branch:
  `agent/m15-1-speech-semantics-provider-foundation`
- Completed M13 branch: `agent/m13-import-template-evolution`
- Merged M12 base commit:
  `6e339ec846f22f14ee454d9ad0d68ba3fb83aee6`
- Verified M13 Batch A correctness implementation commit:
  `247652c56131b73f8bc582751c748e614dc7f890`
- Independently reviewed M13 Batch A head:
  `44fdde0fe79e6810b2cb1dc5a4fb3cbeea04dfab`
- M13 Batch A merge commit on `main`:
  `8574b31dde9b213fe83aade9583bf2e360fce0da`
- Verified M13 Batch B implementation commit:
  `633d7484874fbbf0beb7064e9abed9389414d9e4`
- M13 Batch C synchronization merge commit:
  `5efaddc21a58e1610b2f8858dfd152507e1ec3c7`
- Verified M13 Batch C closure commit:
  `9b3ea9ec50682f61ac55470b0ae5b189506ded81`
- Final M13 PR:
  `#9 — M13: Complete import and template evolution core` (merged)
- M13 Batch B + Batch C merge commit on `main`:
  `b435c97cf48a7de22b417dec0a13775604ebd6d7`
- Merged M11 trustworthy-baseline commit:
  `f0e0d2c06fa4137c07ab2f892df117af2ed3a060`
- Verified synchronized M12 base commit:
  `0bce62833632e7e73bdc4daf4430ba028415adfd`
- Verified M12 restructure commit:
  `b4c119a2eb0f88108ea93554355ee62ec5a72634`
- Verified M11.4 implementation commit:
  `f0113e0592bf5198c429d3282c528c39b47f63fa`
- M11.4 PR head:
  `b5c75ca52aa67f9fa5a7af7698358a709314d935`
- M11.4 merge commit on `main`:
  `f0e0d2c06fa4137c07ab2f892df117af2ed3a060`
- Release tag: none recorded
- M16.0 macro-reconciliation PR: `#20` (merged), merge commit
  `c273139ecb6d2dd98600d6e990552c754db9b44e`
- M16.1 synchronized base commit (verified `main` at prompt time):
  `c273139ecb6d2dd98600d6e990552c754db9b44e`
- M16.1 implementation branch (merged, deleted):
  `agent/m16-1-desktop-architecture-foundation`
- Verified M16.1 reviewed head (corrective patch applied):
  `439cc9612578b5dc78eda57e07f054bec8d60d38`
- Final M16.1 PR: `#21 — M16.1: Desktop Architecture Foundation — select
  PySide6, freeze state/concurrency/theme boundaries` (merged)
- M16.1 merge commit on `main`: `a1dc044721e9017d39842e96e0516a88a36d129f`
- M16.2 synchronized base commit (verified `main` at prompt time):
  `f2c139f758962b0684271e11df55770675cc8cbb`
- M16.2 implementation branch (merged): `agent/m16-2-desktop-vertical-slice`
- M16.2 final reviewed head: `0e78e6f9c1892846e7b63d9696d2312dfcaa6b9a`
- Final M16.2 PR: `#23 — M16.2 Minimal Desktop Vertical Slice & M16 Exit`
  (merged)
- M16.2 / Milestone 16 merge commit on `main`:
  `2e900d243950ca93aedf5cbde5b836dc6e378f25`
- Post-M16-closure lifecycle-reconciliation PR: `#24` (merged), merge
  commit `c8842e0f77199ed9d3d0a2e3c48701d4289f137e`
- M17 synchronized base commit (verified `main` at prompt time):
  `c8842e0f77199ed9d3d0a2e3c48701d4289f137e`
- M17 implementation branch (single long-lived branch for the whole
  milestone): `agent/m17-desktop-core-workflow-migration`
- M17 feature 1 (Today): non-visual controller/handoff groundwork, the
  Motion Foundation, and a **fresh third Command Center presentation**
  (shared Management Rail + Today three-region composition) implemented
  from the replacement `DESIGN.md` (`c19b686`); the two earlier
  presentations were rejected at human visual review and are preserved as
  history, not restored. **Native human visual acceptance for this third
  presentation PASSED 2026-08-16 at head `fdd9cc0`** — Today is complete
  and Human Accepted (DESIGN.md § 2 Level 4). See PR #25 (merged) for the
  exact head SHA and the full reject/reset/fresh-implementation/
  acceptance history.
- M17 feature 2 (Review): `ReviewController` + `ReviewView` implement the
  Card browse/study-preparation workflow against `VR-STUDY-001`
  (`Review - Quiz.pdf` p4 Variant C, parent pattern P3 -- Immersive
  Study/DESIGN.md § 6.3): Management Rail hidden, one minimal session bar,
  one dominant learning surface, a transient right Card Contents/History
  drawer. Reads only existing reusable core
  (`src.learning_workflow.get_study_cards`/`get_card_learning_history`,
  `src.collections.get_card_groups_for_collection`); never calls the
  legacy `src/review.py` SRS scheduler. **Native human visual acceptance
  PASSED 2026-08-16 at head `38d53d2`** — Review is complete and Human
  Accepted (DESIGN.md § 2 Level 4), Milestone 17's second accepted
  feature. See PR #25 (merged) for the full corrective-patch and
  acceptance history.
- M17 feature 3 (Quiz): `QuizController` + `QuizView` implement the
  native session/grading/completion workflow against `VR-STUDY-001`
  (`Review - Quiz.pdf` p4 Variant C, parent pattern P3 -- Immersive
  Study). Reads/writes only through existing reusable core
  (`src.quiz.create_quiz_session`/`create_quiz_items`/
  `generate_mcq_items`/`generate_matching_items`/`record_quiz_answer`/
  `mark_quiz_session_completed`, `src.template_quiz.
  generate_template_multi_rule_quiz_items`); no SQL, no duplicated
  grading logic. Preserves all nine current Quiz families, the
  single-global-active-session guard, duplicate-submission protection,
  and Mistake Book/Proficient Pool side effects; plain Matching stays
  whole-Collection only (normalized in-controller), template-aware
  Matching stays Card-scoped. Review's Quick Quiz / Choose Quiz Type and
  Today's Learning Queue "quiz" action perform a real launch through this
  one controller, replacing the M17 Feature 2 corrective patch's
  transitional honest-unavailable state. **Native human visual acceptance
  PASSED 2026-08-16 at head `311762c`** -- Quiz is complete and Human
  Accepted (DESIGN.md § 2 Level 4), Milestone 17's third accepted
  feature, after a typography/spacing visual-calibration corrective pass
  (`0660214`) and a UX-defect corrective pass (`311762c`: long-content
  clipping, Matching wheel/selection stability, a real post-Quiz
  mistake-review state). See PR #25 (merged) for the full corrective-
  pass and acceptance history.
- M17 feature 3B (Quiz Presentation Choice, `VR-STUDY-002`, Quiz-only):
  adds an optional Flip Card + Filmstrip Quiz presentation
  (`Review - Quiz.pdf` p5 Variant D) alongside the accepted Immersive
  Focus default, plus the one durable preference and minimum Settings
  vertical slice that control it (`state/preferences.py`
  `quiz_presentation`; `SettingsController`/`SettingsView`, P8 Settings
  Form). Both presentations share the same `QuizController`; Matching
  always falls back to the existing Immersive Matching presentation.
  **Native human visual acceptance PASSED 2026-08-16 at head `c54468e`**
  -- Quiz Presentation Choice is complete and Human Accepted (DESIGN.md
  § 2 Level 4), Milestone 17's fourth accepted feature. See PR #25
  (merged) for the full acceptance record.
- M17 feature 4 (Entries, `VR-ENTRIES-001`, `Entries & Collections
  Manager.pdf` p3 Variant B, parent pattern P2): replaces the M16.2
  architecture-proof placeholder with the real Table-First Entries
  Manager -- Scope Pane (explicit "Scope" section: All Entries/Starred/
  Mistake Book/Proficient Pool; explicit "Collections" section: real user
  Collections; bounded resizable `QSplitter`) -> two-row toolbar (search/
  filters/Quick Add/Add Entry, plus a conditional batch-action row) ->
  dominant Entries Table (native multi-selection + explicit checkbox
  column + header select-all, one shared selection truth) -> subordinate
  horizontal Entry Detail. `EntriesController` calls only existing
  `src.entries`/`src.collections`/`src.entry_templates`/`src.text_parser`
  functions (`search_entries`, `create_entry_with_template`,
  `update_entry_with_template`, `delete_entries`,
  `parse_and_validate_entry_card`, `update_entry_collections`); Add/Edit
  share one P5 `_EntryEditorDialog` with a scroll-safe form body, Quick
  Add's structured-text-card flow is preserved, and Delete/Collection-
  removal always honor the existing `CrossCardMoveConfirmationRequired`
  gate, with confirmation copy distinguishing permanent deletion from
  Collection removal. Implemented at `9f63813`; a corrective pass at
  `2cc3332` fixed typography, toolbar layout, Scope Pane resizing, editor
  scroll-safety, the "Add to Collection" menu interaction, and checkbox
  selection. **Native human visual acceptance PASSED 2026-08-16 at head
  `2cc333256d2a831c3268c150a86935276117f1c8`** — Entries is complete and
  Human Accepted (DESIGN.md § 2 Level 4), Milestone 17's fifth accepted
  feature. See PR #25 (merged) for the full corrective-pass and
  acceptance history.
- M17 Minimum Collection Integration (DESIGN.md § 6.8, Class B --
  "inherited from the invoking A/B surface", explicitly not a full
  Collection Manager): a real `Workspace.COLLECTIONS` Management Mode
  workspace, reached through the now-enabled `Collections` rail
  destination. `CollectionsController` is a read-only projection over
  `src.collections.get_collections`/`get_collection_by_id`/
  `get_card_groups_for_collection` -- no SQL, no mutation, no second Card
  model -- keeping normal Collections and system practice pools (Starred/
  Mistake Book/Proficient Pool) as two separate lists, the same
  separation `EntriesController`/`_ScopePane` already established for the
  Entries Scope Pane. `CollectionsView`: Management Rail -> left selector
  pane ("Collections"/"Practice Pools" sections) -> right read-only
  detail (factual metadata + compact Card list, or a pool summary) with
  "Open Entries"/"Open in Study" handoff actions, visual traits inherited
  from Entries' Scope Pane + detail vocabulary. Two typed handoffs
  (`state/handoff.py`) -- `EntriesScopeIntent` (Entries' own existing
  scope key) and `StudyTargetIntent` (`collection_id`, `card_number`) --
  are each consumed exactly once by `MainWindow`; `_open_review_at_card`
  fails honestly (no navigation, no fallback to `open_default()`) if the
  requested Card is gone. Today's "Collections Needing Attention" pool
  rows are now actionable via the same `EntriesScopeIntent` handoff. This
  checkpoint also fixed a real latent bug where
  `_render_workspace(REVIEW)` unconditionally called
  `ReviewController.open_default()` on every render, which would have
  silently overwritten any specific Collection/Card handoff -- now only
  the generic entry points call it. Implemented at `009645a`. A
  corrective pass at `6d8ed13` made Card browsing genuinely paged and
  scrollable for large Collections (a new read-only core query,
  `get_card_page_for_collection`, computes per-Card Entry counts via SQL
  aggregation rather than loading every Entry row), split Entries'
  single selection concept into independent `focused_id` (bottom
  detail/Edit) and `checked_ids` (batch actions) truths with distinct
  visual states, and added a direct per-row Star toggle reusing the
  existing Starred system-Collection core (including the
  `CrossCardMoveConfirmationRequired` safety gate on unstar). **Native
  human visual acceptance PASSED 2026-08-17 at head
  `6d8ed13c206018ece80277210abb858afd8930f9`** — Minimum Collection
  Integration is complete and Human Accepted (DESIGN.md § 2 Level 4),
  Milestone 17's sixth accepted feature. See PR #25 (merged) for the
  full corrective-pass and acceptance history.
- M17 Theme Completion & Cross-Screen Validation: closes the Appearance
  axis (System/Light/Dark, Calm Blue) as a complete, live-switchable,
  OS-aware product capability. `System` resolves through a live OS
  Light/Dark read (`system_appearance.py`, Qt's `QStyleHints.
  colorScheme()`) with an explicit logged fallback, and reacts to a live
  OS appearance change while `System` remains selected
  (`ThemeManager.watch_system_appearance()`) without ever overriding an
  explicit Light/Dark choice. Settings gained a real Appearance control
  persisting immediately and live-applying through the single existing
  `ThemeManager.apply()` call site. A contrast re-audit against the
  surfaces tokens are actually deployed on found and fixed two real
  defects the M16.2 audit had missed (Light `text-muted` against
  `surface-secondary`/`app-background`; the Entries Star column's fixed
  gold, now a theme-aware `star`/`on-star` semantic token,
  hue-separated from `warning`). Implemented at `934eeac`. A first
  corrective pass (`7b4a86c`) audited every text color across
  Today/Entries/Collections/Settings/Review/Quiz/Utility against the
  four-level primary/secondary/muted/disabled text-role hierarchy and
  fixed four confirmed defects; it also discovered, and correctly left
  out of its own scope, that `QPushButton:checked/:disabled/:hover` ->
  child `QLabel` descendant-pseudo-state QSS selectors are not reliably
  re-evaluated by Qt's style engine. A second corrective pass (`48a171f`)
  replaced that mechanism in the Navigation Rail with one driven
  reliably -- a Qt dynamic property (`navActive`) for the active/normal
  distinction plus static object names for the disabled destinations --
  verified through the real production bootstrap path. **Native human
  visual acceptance PASSED 2026-08-17 at head
  `48a171f6aaa7e7ce3b60be945024c8712e69ec64`** — Theme Completion &
  Cross-Screen Validation is complete and Human Accepted, Milestone 17's
  seventh accepted feature. See PR #25 (merged) for the full
  corrective-pass and acceptance history.
- M17 Parity + Exit Verification (the final M17 checkpoint): closed the
  three frozen final corrective items and verified the seven prior
  checkpoints as one integrated product. Custom Entry Type (Add/Edit
  Entry gains a "Custom..." option via a native `QInputDialog` prompt,
  saved as ordinary Entry data through the existing `entry_type`
  field -- no core/schema change, since `src/entries.py` already stored
  it as free text). Entries sorting (`search_entries()` gained an
  allowlisted `sort_by`/`sort_direction` capability -- Term/Created/
  Updated -- fulfilling a toolbar spec DESIGN.md § 6.2 had already
  documented but never implemented; a compact "Sort by" control composes
  with scope/search/filter). Entries result count (a subordinate "N
  entries" label reusing the count `EntriesController.refresh()` already
  computes). Integrated workflow parity verified: Today/Collections ->
  Entries exact scope, Collection/Card -> exact Review Card with no
  silent fallback, Review -> Quiz context preservation, Study exit ->
  correct Management workspace/Navigation Rail state, theme switching
  never mutates learning data. Implemented at `b686a99`. One corrective
  fix (`d232717`) followed: the Entries table's pre-existing
  `QTableView.setSortingEnabled(True)` (M17 Feature 4) wired native
  header-click sorting directly to `QSortFilterProxyModel`'s own
  independent sort state -- a parallel sorting mechanism a header click
  could use to silently override "Sort by"'s real SQL-level order
  (confirmed empirically the proxy defaulted to `sortColumn() == 0`, not
  `-1`, immediately on `setSortingEnabled(True)`, before any click).
  Removed; the proxy is forced to `sort(-1)` and stays a pure
  index-mapping adapter. New regression tests check the *visible*
  proxy/table order directly, not only the source model, which is what
  let the original defect through a fully-green suite -- confirmed to
  fail against the pre-fix code and pass against the fix. **Native Human
  Exit PASS recorded 2026-08-17 at final accepted head
  `d232717b6b225e7c798c510ae8e87ce87fe5d8c8`** — M17 Parity + Exit
  Verification is complete and Human Accepted, Milestone 17's eighth and
  final checkpoint. 592/592 local tests passing, architecture audit
  clean; no remote CI is configured in this repository. Full
  corrective-pass and acceptance history recorded on the M17 PR (merged
  into `main`); no separate `MILESTONE17_CLOSURE.md` was created.
- Current lifecycle documents:
  - `ROADMAP.md`
  - `PROJECT_STATUS.md`
  - `DESIGN.md` (§ 25 Motion / Transition System)
  - `docs/migration/DESKTOP_MIGRATION_PLAN.md`
  - `docs/design/M16_1_DESKTOP_ARCHITECTURE_CONTRACT.md`
  - `docs/history/MILESTONE16_CLOSURE.md` (final closure record)
- Current closure evidence:
  - `docs/history/MILESTONE11_CLOSURE.md`
  - `docs/history/MILESTONE14_CLOSURE.md`
  - `docs/history/M15_0_TTS_PROVIDER_SELECTION_CLOSURE.md`
  - `docs/policies/TTS_LICENSE_AND_ATTRIBUTION.md`
  - `docs/design/M15_1_SPEECH_SEMANTIC_CONTRACT.md`
  - `docs/design/M15_2_AUDIO_ASSET_COMPOSITION_CONTRACT.md`
  - `docs/design/M15_3_BATCH_EXPORT_CONTRACT.md`
  - `docs/history/MILESTONE15_CLOSURE.md`
  - `docs/history/MILESTONE16_CLOSURE.md`
  - `THIRD_PARTY_NOTICES.md`
- Current lifecycle state:
  **Milestone 15 — Audio Foundation Complete on `main`; Milestone 16 —
  Desktop Architecture and UI Design Complete on `main`. M16.0 Desktop UI
  Design Baseline Complete (`DESIGN.md`); M16.1 Desktop Architecture
  Foundation Complete on `main` (PR #21,
  `a1dc044721e9017d39842e96e0516a88a36d129f`); M16.2 Minimal Desktop
  Vertical Slice & M16 Exit Complete on `main` (PR #23,
  `2e900d243950ca93aedf5cbde5b836dc6e378f25`). Post-M16 lifecycle
  reconciliation Complete on `main` (PR #24,
  `c8842e0f77199ed9d3d0a2e3c48701d4289f137e`). **Milestone 17 — Desktop
  Core Workflow Migration is COMPLETE on `main`** (merged via PR #25):
  Today (feature 1) is **complete and
  Human Accepted** (native visual acceptance PASSED 2026-08-16 against
  `fdd9cc0`); Review (feature 2) is **complete and Human Accepted**
  (native visual acceptance PASSED 2026-08-16 against `38d53d2`, after one
  corrective patch for a functional-honesty finding); Quiz (feature 3) is
  **complete and Human Accepted** (native visual acceptance PASSED
  2026-08-16 against `311762c`, after a visual-calibration corrective pass
  and a UX-defect corrective pass); Quiz Presentation Choice (feature 3B,
  `VR-STUDY-002`, Quiz-only) is **complete and Human Accepted** (native
  visual acceptance PASSED 2026-08-16 against `c54468e`); Entries
  (feature 4) is **complete and Human Accepted** (native visual
  acceptance PASSED 2026-08-16 against
  `2cc333256d2a831c3268c150a86935276117f1c8`, after a corrective pass for
  typography, toolbar layout, Scope Pane resizing, editor scroll-safety,
  the "Add to Collection" menu interaction, and checkbox selection);
  Minimum Collection Integration is **complete and Human Accepted**
  (native visual acceptance PASSED 2026-08-17 against
  `6d8ed13c206018ece80277210abb858afd8930f9`, after a corrective pass for
  paged/scrollable Card navigation, efficient large-Collection Card
  projection, the focused-Entry-vs-checked-Entries separation, and the
  persistent direct Star toggle); Theme Completion & Cross-Screen
  Validation is **complete and Human Accepted** (native visual acceptance
  PASSED 2026-08-17 against `48a171f6aaa7e7ce3b60be945024c8712e69ec64`,
  after a typography color-role hierarchy corrective pass and a
  Navigation Rail active/normal/disabled state-rendering reliability
  fix); M17 Parity + Exit Verification (final checkpoint) is **complete
  and Human Accepted** (native Human Exit PASS recorded 2026-08-17
  against final accepted head
  `d232717b6b225e7c798c510ae8e87ce87fe5d8c8`, after a corrective fix for
  a parallel Entries-sorting mechanism). **Milestone 17 is COMPLETE.**
- M18 implementation branch (single long-lived branch for the whole
  milestone, merged): `agent/m18-desktop-management-major-feature-completion`
- M18 final accepted head: `0ff85509f0cdb7248d7970b8af66c1da6a94c301`
- Final M18 PR: `#29 — M18: Desktop Management and Major Feature
  Completion` (merged)
- M18 merge commit on `main`: `9dae05c49caec8f2a33fdaf74d0a1f3fd1db43bc`
- Exact next objective:
  **Milestone 19 — Desktop Product Hardening, IN PROGRESS** on the
  single long-lived branch `agent/m19-desktop-product-hardening` from
  baseline `9dae05c49caec8f2a33fdaf74d0a1f3fd1db43bc`. Known
  M17/M18-era deferred carryover (deferred features, not M19 defects):
  the three deferred Accent families (Sage/Teal, Indigo/Violet, Warm
  Neutral) and the Quick Theme Control popover; advanced Entries table
  personalization (saved sort/filter views, drag-reordering, column
  customization); the Entries Entry Type filter combo listing only the
  predefined set rather than live distinct values. The mandatory
  M19/M20 productization handoff (ROADMAP.md § "Mandatory M19 / M20
  Productization Handoff — Card Audio Export") — shared TTS runtime
  discovery, persistent runtime configuration, and
  absent/broken-runtime behavior — is explicit M19 hardening scope.
