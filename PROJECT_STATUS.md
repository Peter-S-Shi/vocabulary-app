# Vocabulary App Project Status

Last reviewed: 2026-10-18

This file is the authoritative evidence-based snapshot of the current project state. Detailed milestone history remains in `ROADMAP.md`, milestone QA/design/packaging documents, and the frozen pre-release snapshot archived at `docs/history/PROJECT_STATUS_PRE_V1_RELEASE_2026-08-19.md`.

## Current Phase

**Milestones 22 and 23 / Vocabulary App v1.2.0 implementation, Windows-native Human Acceptance, and clean-VM Release Candidate acceptance are complete on merged `main`. Release metadata is finalized as `1.2.0`, and the next authorized lifecycle step is to build, verify, and publish stable v1.2.0 from verified merged `main`.**

This is intentionally one step ahead of the merge-ready PR branch. It does not
claim that a `v1.2.0` tag or GitHub Release already exists; **v1.1.0 remains the
current published GitHub Release** until stable v1.2.0 publication is completed.

## M22-A / Post-v1.1.0 Card workflow correction

This source snapshot implements the bounded M22-A fixes for
[Issue #40](https://github.com/Peter-S-Shi/vocabulary-app/issues/40) and
[Issue #42](https://github.com/Peter-S-Shi/vocabulary-app/issues/42).
Review Calendar exposes active unscheduled Cards through a separate current-Card
selection path, while completed-Quiz history stays read-only. Card-scoped Quiz
completion shows a completed-attempt number and compact history keyed by stable
Card ID. Collection-scoped completion has no Card attempt history.

The Card history table also shows read-only Accuracy calculated from the
existing correct/total counts, with zero-item records marked unavailable.
M22-A changes presentation/controller behavior only; the Quiz, scheduling,
persistence, revision, and migration contracts remain unchanged.

**Post-merge M22-A state:** #40 and #42 are implemented, independently reviewed,
Windows-native Human Acceptance has passed all six checks, and the changes are
merged into `main`. v1.1.0 remains the current published release, and its
installer does not include these fixes. M22 as a whole is not closed, and no
new version has shipped.

## M22-B / Card-originated Matching correction

**Post-merge M22-B source state:** Issue #37
is implemented and merged into `main`. A Quiz launched from a selected Card
keeps that Card's stable identity; plain Matching draws only its eligible
Entries with distinct meanings and records the actual Card revision on the
session. Review's Matching count choices follow the selected Card, with an
explicit unavailable message when it cannot form two distinct answers.
Independent Collection and system-pool Quizzes remain separate.

The completed Card Matching session uses the M22-A Card history and next-review
scheduling paths without synthetic completion evidence. Local targeted tests
and the architecture audit cover this source change. The product owner reported
Windows-native Human Acceptance PASS on the M22-B branch. PR #45 passed
required CI and merged M22-B into `main`. No public release or installer
contains M22-B; v1.1.0 remains the published version.

## M22-C / Theme visibility and Quiz feedback

**Post-merge M22-C source state:** Issue #38
and Issue #41
are implemented and merged into `main`. The Starred and Proficient Pool Random
Quiz buttons have explicit theme-token colors for normal, hover, disabled,
and keyboard-focus states. Quiz answer presentation uses a contrast-safe error
color for adjudicated wrong answers and the active theme accent for correct
and expected answers; ungraded self-graded drafts remain neutral. Existing
Correct/Wrong grading labels, Matching flow, and learning data are unchanged.

PR #46 passed required PR and post-merge `main` CI and merged M22-C into
`main`. The product owner reported Windows-native Human Acceptance PASS for all
four M22-C check groups. v1.1.0 remains the current published release; no
installer containing M22-C has shipped, and M22 as a whole remains open.

## M22-D / Current Entry locations

**Post-merge M22-D source state:** Issue #39 is implemented and merged into
`main`. The Entries detail panel displays each current ordinary Collection
and its position-based Card number, including Entries shared by Collections
with different Card sizes. System practice pools are labeled separately as
pool memberships. The reusable batched core query reads current membership;
it does not change stable Card identities, revisions, historical learning
records, or the Entries table's Collection-name behavior. The detail has a
clear empty state and updates when Entries is refreshed after Collection
changes.

PR #47 passed required PR checks, merged M22-D into `main`, and its post-merge
`main` CI passed. The product owner reported Windows-native Human Acceptance
PASS, recorded in Issue #39. Focused local tests and architecture checks
provide separate engineering evidence. v1.1.0 remains the published release;
these source changes have not shipped in an installer.

## M23-A / Issue #43 data-root startup safety foundation

**Post-merge M23-A source state:** the approved unified-storage contract has
one startup path resolver and a minimal versioned bootstrap pointer at the
default data location. When no pointer exists, v1.1.0 paths and explicit
environment-override precedence remain unchanged. A configured root must
exist with a valid SQLite database before database initialization; damaged or
unavailable configuration stops startup with a recovery message instead of
creating a blank database or falling back. SQLite, backups, audio cache and
preferences resolve together under a valid selected root, and a running
process rejects a pointer change until restart.

PR #49 passed required PR checks and merged M23-A into `main`. Native Human
Acceptance was deferred to the consolidated M23-B/C workflow. v1.1.0 remains the
published release; no installer with M23-A has shipped.

## M23-B/C / Unified data relocation engine and Settings storage workflow

**Post-merge M23-B/C source state:** Issue #43 is fully implemented and merged
into `main`. Vocabulary App provides a safe, unified data-relocation engine and
native Settings → Storage folder chooser workflow allowing users to relocate
their durable user data (SQLite database, backups, audio cache, and preferences)
together to another volume or folder (e.g. `D:\VocabularyAppData`).

The implementation enforces all approved Owner and engineering safety invariants:
- **Sibling-directory staging & atomic no-clobber promotion:** staging directory
  is created under the target volume's parent filesystem (`<parent>/.vocab-stage-<uuid>`)
  and atomically promoted via `MoveFileExW` (`MOVEFILE_WRITE_THROUGH` without
  `MOVEFILE_REPLACE_EXISTING` on Windows) to an absent target folder. Existing
  occupied targets are strictly rejected without a check-then-replace race, and
  the target's authoritative provenance and four-component manifest marker
  (`.vocab_app_root_marker.json`) is written inside the staging directory prior
  to promotion.
- **SQLite snapshot consistency:** uses SQLite online backup (`Connection.backup()`)
  and staging WAL truncation to create a coherent database snapshot without raw
  WAL/SHM copying or disruptive source checkpoints.
- **Cross-process writer quiescence:** an explicit shared vs. exclusive OS file lock
  (`.app_data.lock`, using pointer-sized Win64 `OVERLAPPED` with `LockFileEx`)
  guards the data root across processes. Active SQLite connections (`LockedConnection`),
  preference writes, audio-cache materialization/composition (`AudioAssetStore.materialize`
  and `compose_card_audio`), pre-migration backups, and database imports hold shared
  locks for their active operation/connection lifetimes, while relocation acquires
  an exclusive lock.
- **Durable recovery journal & crash-consistent state transitions:** an independent
  migration-recovery journal (`migration-recovery.json`) in the default OS root
  records relocation transitions (`SWITCHING` → `COMMITTED`). Staging verification
  and crash recovery compare complete four-component manifests with relative POSIX file
  paths and streaming 64KB `SHA-256` digests for `vocab.db`, `preferences.json`,
  `backups`, and `audio-cache`. Equal-size file substitutions and corruptions fail closed.
  If a crash occurs after `SWITCHING` is recorded but before atomic target promotion
  (verified via the unpromoted sibling staging directory and matching `.vocab_app_root_marker.json`),
  startup idempotently rolls back the journal to the prior committed root and cleans
  up staging. If a crash occurs after target promotion, startup verifies full
  four-component integrity (`vocab.db`, `preferences.json`, `backups`, `audio-cache`)
  and marker provenance (`source_root`, `target_root`, `marker_uuid`) before
  forward-rolling `data-root.json` and the journal to `COMMITTED`. Any missing,
  unavailable, or incomplete promoted target fails closed with `DataRootError`.
- **Target filesystem preflight & disk space verification:** destination directories
  and source components are strictly verified against symbolic links/junctions,
  non-regular files, and insufficient disk space prior to staging.
- **Retained rollback baseline:** original data files at the source location
  are preserved intact and never deleted.
- **Settings → Storage UX & worker lifecycle:** Settings executes relocation on a
  dedicated `QThread` worker (`RelocationWorker`) registered with `SettingsController`.
  Worker unregistration is deferred until the worker thread actually finishes via
  `worker.finished`, while UI completion/error callbacks and `controller.shutdown()`
  wait for thread execution to exit cleanly before UI dialogs or application quit,
  keeping the GUI responsive while quiescing UI actions, reporting accurate post-error
  recovery status, and enforcing an immediate application restart boundary upon completion.
- **Integration Preflight & Test Evidence:** All unit and Windows-native end-to-end
  integration preflight tests (`test_m23a_data_root`, `test_m23b_data_relocation`,
  `test_m23c_settings_storage_ui`, and `test_m23bc_e2e_integration_preflight`) pass
  cleanly on Windows. The integration suite validates full 4-component preservation,
  restart and reopening, chained migrations, occupied destination rejection, disconnected
  volume fail-closed protections, journal crash recovery across pre/post-promotion boundaries,
  in-process stale-root write blocking, and Qt window closing during active worker execution.
  Architecture audit `scripts/audit_architecture.py` reports 0 violations across 98 Python files.

**Human Acceptance: PASS.** The Product Owner completed live Windows Human Acceptance
testing on the active `fix/m23bc-data-relocation` branch across all storage relocation
scenarios, verifying move integrity, settings feedback, and clean restart boundaries.

## Stable Release v1.2.0 Finalization (Pre-Publication)

Feature scope and release metadata are finalized for the **v1.2.0** stable upgrade:
- Consolidates merged Milestone 22 (A/B/C/D) learning/UX corrections (#37, #38, #39, #40, #41, #42).
- Consolidates merged Milestone 23 (A/B/C) data-root foundation and unified data-folder relocation (#43).
- Explicitly defers Issue #48 (UI/UX refresh / visual redesign) to a subsequent authorized milestone.
- **RC Acceptance Record (`v1.2.0-rc.1`):** Built from merged `main` commit `0eb099bf5ebf65b47d471201677a199d3d67f76a` (where all required Release Closure CI shards and the Windows installer/upgrade-proof job succeeded in GitHub Actions run [39135461420](https://github.com/Peter-S-Shi/vocabulary-app/actions/runs/39135461420)), the signed `VocabularyApp-Setup-1.2.0-rc.1.exe` (`SHA-256 3662983f18092033b227b5bed34444648575b105275e8bea0e9e9206945a08dc`) passed Owner acceptance in the isolated clean Windows 11 VMware test environment (restored to its clean baseline snapshot).
- Following Owner direction after RC acceptance PASS, `v1.2.0-rc.1` is not published as a separate GitHub prerelease; release metadata advances directly from `1.2.0-rc.1` to **`1.2.0`** (`APP_VERSION = "1.2.0"`, Windows PE `FileVersion = "1.2.0.0"`, `ProductVersion = "1.2.0"`), preserving the existing Inno Setup `AppId` and `CN=Peter Shi` self-signed developer publisher identity without reopening product behavior or scope.
- Synchronizes the upgrade verification harness (`winbuild/verify_upgrade.py` and `tests/test_v1_1_phase_f2_upgrade_verification.py`), packaging version checks (`tests/test_m20_build_packaging.py`), and CI job label (`.github/workflows/windows_build.yml`) to target `1.2.0` (`VocabularyApp-Setup-1.2.0.exe`).
- **Focused Local Validation:** 75 unit tests across `test_m20_build_packaging`, `test_v1_1_phase_f2_upgrade_verification`, `test_v1_1_phase_e_update_checker`, `test_v1_1_phase_e_update_settings_ui`, and `test_m23a_data_root` pass cleanly on Windows, and `scripts/audit_architecture.py` reports 0 boundary violations or warnings across 98 Python files.
- Following our one-step-ahead macro-documentation convention, repository documentation describes post-merge, pre-publication `v1.2.0` stable-release readiness. No `v1.2.0` tag or GitHub Release exists yet; `v1.1.0` remains the active public release until PR merge, final signed `1.2.0` installer build/VM smoke verification, and authorized GitHub Release publication.

## M21 / v1.1.0 Closure

M21 closed the approved v1.1 scope without reopening product development:

- **Implementation Phases A-E:** stable Card review scheduling; direct Star
  actions and Collection progress; local-time presentation and one durable
  Windows product identity; constrained per-mode theme customization; and
  release update awareness without automatic download or installation.
- **Phase Patch:** coherent Quiz-to-schedule and Review Calendar behavior;
  consistent Proficient Pool, manual-proficient, strength-recommendation, and
  random-practice contracts; and one normalized duplicate definition shared by
  import preview and write paths.
- **Phase F verification:** v1.1.0 version/provenance authority, reproducible
  Windows packaging, packaged-launch smoke coverage, and a real isolated
  v1.0.0 → v1.1.0 overlay proof preserving user data, preferences, version
  identity, and the established Windows product identity.
- **Data safety corrective:** upgrade verification requires an explicit
  isolated data root and rejects the production data root (including its
  descendants); synthetic scheduling fixtures fail closed before opening the
  production database.

Human overlay acceptance on a real Windows installation passed for launch,
legacy data, preferences, displayed version, representative v1.1 behavior, and
single-product identity. The original single timeout-bounded `unittest
discover` release gate could not complete within the 45-minute CI limit and
was replaced with three parallel Release Closure shards (Theme & Update
Surface; M18 remainder + full M19; M20 + timezone + v1.1 Phase/Patch/Review
Scheduling); `unittest discover` remains available as a manual-only
`workflow_dispatch` job, not the active gate. GitHub Actions run
[33156983972](https://github.com/Peter-S-Shi/vocabulary-app/actions/runs/33156983972)
at head `f94e3eb` shows all three Release Closure shards green together with a
green Windows installer build, packaged-launch smoke test, and real isolated
v1.0.0 → v1.1.0 overlay upgrade proof.

The `v1.1.0` tag points at this release-state commit on `main`; the canonical
Windows installer is built from that exact tagged source and the GitHub
Release is published from it, per the F4B publication record below.

## Released Baseline

**Vocabulary App v1.1.0 is the current released version.**

Milestone 21 — Phase F Release Verification is **Complete**. F4A release-closure CI evidence (three parallel Release Closure shards plus the Windows installer/upgrade-proof job) is green on merged `main`; PR #36 merged M21 to `main`; this release-state commit was tagged `v1.1.0`; the canonical Windows installer was built and signed from that tagged source; and the GitHub Release was published.

## Current Release

- **Version:** `1.1.0`
- **Tag:** `v1.1.0`
- **Release source:** the merged `main` commit the `v1.1.0` tag points at (this release-state commit)
- **Merged PR:** #36 — `M21: Vocabulary App v1.1.0 — Phase F Release Verification`
- **Canonical installer:** `VocabularyApp-Setup-1.1.0.exe`
- **Canonical installer SHA-256:** see `SHA256SUMS.txt` published with the `v1.1.0` GitHub Release
- **Distribution:** GitHub Releases
- **Platform:** Windows 10/11 x64
- **License:** MIT

The canonical release build was produced from a clean checkout whose `HEAD` exactly matched the tagged `v1.1.0` source SHA. `dist/build_manifest.json` reports `source_dirty: false` and `app_version: "1.1.0"` against that SHA.

The installer SHA-256 was computed by the release build pipeline and independently re-verified with Windows `certutil`; both values matched, and both are published in `SHA256SUMS.txt` on the `v1.1.0` GitHub Release.

## Previous Release: v1.0.0

- **Version:** `1.0.0`
- **Tag:** `v1.0.0`
- **Release source / merged `main` SHA:** `2363e73bbd85ca24f7e227f8007e0046eeabd471`
- **Merged PR:** #33 — `M20: Packaging and Release Candidate — Finalized 1.0.0, Human RC PASS`
- **Canonical installer:** `VocabularyApp-Setup-1.0.0.exe`
- **Canonical installer SHA-256:** `108095e3ce7d256bc610c33f427a9ee2fee4956cb69dde3bf0e105413865b297`

The remaining M20 evidence below (RC acceptance, engineering evidence, signing model, product state, data contract, known limitations) describes the v1.0.0 release process specifically and is preserved as the historical record of how that baseline was reached; where v1.1.0 reuses the same signing identity and data-location contract, that reuse is noted rather than restated in full.

## Human RC Acceptance Record

**Human RC: PASS (2026-08-19).**

The authoritative Human RC decision was granted against exact RC SHA:

`89263a4f0f477fe5455ed22bedffd1968218bb1e`

and its RC artifact:

- `VocabularyApp-Setup-1.0.0-rc.1.exe`
- SHA-256 `8b435657c5cecfecd52f96a6f49d648e1fcaa2e4b58cada03cfc3baf7ea87710`

That historical RC acceptance record is intentionally preserved. After PASS, the already-frozen release scheme advanced release metadata only from `1.0.0-rc.1` to `1.0.0`; no product behavior or scope was reopened. Targeted version/build/signature/install/launch/uninstall verification was then completed before merge and publication.

## M20 Engineering Evidence

At the Human-RC-accepted RC source:

- Full repository regression: **911 tests, 0 failures, 0 errors** (`unittest discover`, 1450.7s).
- Architecture audit: clean (90 Python files, 0 violations).
- PyInstaller `--onedir` + Inno Setup build chain completed successfully.
- Production durable data root moved to `%LOCALAPPDATA%\vocabulary_app\`, separated from installed binaries.
- Fresh database creation verified under a genuine fresh local standard Windows account (`VocabAppQA`).
- Existing-database import verified with copy-not-move semantics, destination backup, source untouched, and successful reopen.
- Backup-before-upgrade verified through a real schema migration.
- Per-user install, Start Menu/Desktop shortcuts, default-preserve uninstall, reinstall, and preserved-data reopen were verified.
- Local Windows Speech Provider / Installed Voice Binding enumerated real installed voices on the fresh account.
- Release payload/privacy inspection found no `.venv`, `.env`, test fixtures, personal `vocab.db`, secrets, or embedded local development paths in the published payload path.
- `LICENSE`, `THIRD_PARTY_NOTICES.md`, README audio/TTS disclosure, and release documentation were reconciled to the shipped product model.

## Signing / Trust Model

v1.0.0 uses a **self-signed Authenticode developer certificate** with Subject/Publisher `Peter Shi` (`CN=Peter Shi`) to complete and verify the Windows signing pipeline.

This certificate is **not publicly trusted**. Independent `Get-AuthenticodeSignature` verification reported the expected untrusted-root status (`UnknownError`) for both the onedir executable and installer. This is not represented as SmartScreen reputation or public identity trust, and SmartScreen warnings may still occur.

Publicly trusted code signing is deferred to a possible future broader public/commercial/Microsoft Store distribution effort and is not part of the completed v1.0 Portfolio release contract.

v1.1.0 reuses this same `CN=Peter Shi` self-signed developer identity for `VocabularyApp-Setup-1.1.0.exe`; the trust model above (not publicly trusted, SmartScreen warnings may still occur) applies unchanged to v1.1.0.

## Product State

The PySide6 native desktop application is the primary product surface. It includes:

- Today / daily learning workflow
- Entries and Templates management
- Collections and Card organization
- Review and Quiz workflows
- Review Calendar / Card History
- Settings and Data Tools
- CSV/XLSX import/export
- Template Definition CSV workflows
- Backup / Restore Preview
- Linked Sources
- Analytics (Learning Brief + Full Findings)
- Card Audio Export using compatible speech voices already installed on Windows

Streamlit remains in the repository as a compatibility/reference UI; it is not the packaged release target.

The release remains local-first: no account, telemetry, cloud sync, or mandatory external service is required.

## Data / Upgrade Contract

- Install model: per-user, no administrative install mode required.
- Installed binaries: under the user's Local AppData Programs area.
- Durable data root: `%LOCALAPPDATA%\vocabulary_app\`.
- Default database: `%LOCALAPPDATA%\vocabulary_app\vocab.db`.
- Backups: `%LOCALAPPDATA%\vocabulary_app\backups\`.
- Existing database: explicit user-selected copy-with-backup; never silently moved or migrated in place from the source file.
- Upgrade: no automatic updater in v1.0 or v1.1 (v1.1 adds a manual/background release-availability check that reports available GitHub releases without downloading or installing them); a newer installer overlays application binaries while preserving durable user data and creating migration safety backups. The real isolated v1.0.0 → v1.1.0 overlay upgrade proof is part of the F4A release-closure evidence above.
- Uninstall: preserves user data by default; destructive deletion requires explicit opt-in.

## Known Limitations / Deferred Work

These are recorded limitations, not M20 blockers:

- Full pristine clean-machine VM verification was deferred for v1.0; distribution acceptance used a fresh local standard Windows account plus real install/migration/uninstall evidence.
- Publicly trusted code signing / SmartScreen reputation was deferred; v1.0 uses the self-signed developer certificate described above.
- Windows 10/11 x64 is the only packaged v1.0 platform.
- Audio capability depends on compatible speech voices already installed on the user's Windows system; the app does not silently download or redistribute third-party voice models/runtimes.
- v1.0 has no automatic updater.

## Lifecycle Closure

The v1.0 and v1.1 lifecycles are both complete:

`M11 → M12 → M13 → M14 → M15 → M16 → M17 → M18 → M19 → M20 → v1.0.0 Released → M21 → v1.1.0 Released`

Neither M20 nor M21 should be reopened for ordinary future development. Any post-v1.1 work should begin from a new explicitly defined milestone/version decision.

## Historical Audit Trail

The former root `PROJECT_STATUS.md` contained the long-form pre-release milestone audit trail and still described PR #33/tag/publication as pending at the moment it was frozen. It is preserved verbatim at:

`docs/history/PROJECT_STATUS_PRE_V1_RELEASE_2026-08-19.md`

Read that file as a timestamped historical snapshot, not as the current repository state.

Additional authoritative evidence:

- `ROADMAP.md` — milestone definitions and lifecycle history
- `docs/packaging/M20_RELEASE_CONTRACT.md` — release-engineering contract and amendments
- `docs/packaging/M20_DISTRIBUTION_QA_CHECKLIST.md` — distribution QA evidence
- `docs/packaging/M20_CODE_SIGNING_SETUP.md` — self-signed signing-pipeline setup/verification
- `docs/qa/MILESTONE19_HARDENING_QA.md` — M19 hardening evidence
