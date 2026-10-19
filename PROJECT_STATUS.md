# Vocabulary App Project Status

Last reviewed: 2026-10-18

This file is the authoritative evidence-based snapshot of the current project state. Detailed milestone history remains in `ROADMAP.md`, milestone QA/design/packaging documents, and the frozen pre-release snapshot archived at `docs/history/PROJECT_STATUS_PRE_V1_RELEASE_2026-08-19.md`.

## Current Phase

**Milestones 22 and 23 / Vocabulary App v1.2.0 implementation, Windows-native Human Acceptance, clean-VM Release Candidate (`v1.2.0-rc.1`) acceptance, final signed `v1.2.0` clean-VM overlay acceptance, and GitHub Release publication are complete. Vocabulary App `v1.2.0` is the current published stable release.**

PR #51 merged the finalized `1.2.0` release metadata into `main` at `d6af0a684db403a4167bea6edf65f8db99523d1a`. The annotated `v1.2.0` tag (`e12ab99ad2ecafa1beb7563fb54d1541665e5380`) points to that exact commit, and the signed `VocabularyApp-Setup-1.2.0.exe` (`SHA-256 97a6781f8b54f63f35a6302f9a5a54fa9a981260794e876f5b76c5fc1299d428`) is published on the [v1.2.0 GitHub Release](https://github.com/Peter-S-Shi/vocabulary-app/releases/tag/v1.2.0).

## M22-A / Post-v1.1.0 Card workflow correction

This source increment implements the bounded M22-A fixes for
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

**Historical post-merge M22-A snapshot:** #40 and #42 were implemented, independently
reviewed, passed all six Windows-native Human Acceptance checks, and merged into
`main` via PR #44. At that interim subphase merge, `v1.1.0` remained the published
release (its installer does not include M22 fixes) and M22 as a whole was still in
progress; M22 (A/B/C/D) has since completed and shipped in `v1.2.0`.

## M22-B / Card-originated Matching correction

**Historical post-merge M22-B snapshot:** Issue #37
is implemented and merged into `main`. A Quiz launched from a selected Card
keeps that Card's stable identity; plain Matching draws only its eligible
Entries with distinct meanings and records the actual Card revision on the
session. Review's Matching count choices follow the selected Card, with an
explicit unavailable message when it cannot form two distinct answers.
Independent Collection and system-pool Quizzes remain separate.

The completed Card Matching session uses the M22-A Card history and next-review
scheduling paths without synthetic completion evidence. Local targeted tests
and the architecture audit cover this source change. The product owner reported
Windows-native Human Acceptance PASS on the then-active M22-B branch, and PR #45 passed
required CI and merged M22-B into `main`. At that interim subphase merge, `v1.1.0`
remained the published version; M22-B later shipped in `v1.2.0`.

## M22-C / Theme visibility and Quiz feedback

**Historical post-merge M22-C snapshot:** Issue #38
and Issue #41
are implemented and merged into `main`. The Starred and Proficient Pool Random
Quiz buttons have explicit theme-token colors for normal, hover, disabled,
and keyboard-focus states. Quiz answer presentation uses a contrast-safe error
color for adjudicated wrong answers and the active theme accent for correct
and expected answers; ungraded self-graded drafts remain neutral. Existing
Correct/Wrong grading labels, Matching flow, and learning data are unchanged.

PR #46 passed required PR and post-merge `main` CI and merged M22-C into
`main`. The product owner reported Windows-native Human Acceptance PASS for all
four M22-C check groups. At that interim subphase merge, `v1.1.0` remained the
published release and M22 as a whole remained open pending M22-D; M22 (A/B/C/D)
subsequently closed and shipped in `v1.2.0`.

## M22-D / Current Entry locations

**Historical post-merge M22-D snapshot:** Issue #39 is implemented and merged into
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
provide separate engineering evidence. Completing M22-D closed the M22 learning/UX
scope on `main` prior to M23 and the `v1.2.0` release.

## M23-A / Issue #43 data-root startup safety foundation

**Historical post-merge M23-A snapshot:** the approved unified-storage contract has
one startup path resolver and a minimal versioned bootstrap pointer at the
default data location. When no pointer exists, v1.1.0 paths and explicit
environment-override precedence remain unchanged. A configured root must
exist with a valid SQLite database before database initialization; damaged or
unavailable configuration stops startup with a recovery message instead of
creating a blank database or falling back. SQLite, backups, audio cache and
preferences resolve together under a valid selected root, and a running
process rejects a pointer change until restart.

PR #49 passed required PR checks and merged M23-A into `main`. Native Human
Acceptance was deferred to the consolidated M23-B/C workflow, which subsequently
passed and shipped in `v1.2.0`.

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
testing on the then-active `fix/m23bc-data-relocation` branch (merged into `main` via
PR #50) across all storage relocation scenarios, verifying move integrity, settings
feedback, and clean restart boundaries.

## M22–M23 / Vocabulary App v1.2.0 Closure and Publication

Feature scope, release verification, and public release publication are complete for **v1.2.0**:
- Consolidates merged Milestone 22 (A/B/C/D) learning/UX corrections (#37, #38, #39, #40, #41, #42).
- Consolidates merged Milestone 23 (A/B/C) data-root foundation and unified data-folder relocation (#43).
- Explicitly defers Issue #48 (UI/UX refresh / visual redesign) to a subsequent authorized milestone.
- **Historical RC Acceptance Record (`v1.2.0-rc.1`):** Built from merged `main` commit `0eb099bf5ebf65b47d471201677a199d3d67f76a` (where all required Release Closure CI shards and the Windows installer/upgrade-proof job succeeded in GitHub Actions run [39135461420](https://github.com/Peter-S-Shi/vocabulary-app/actions/runs/39135461420)), the signed `VocabularyApp-Setup-1.2.0-rc.1.exe` (`SHA-256 3662983f18092033b227b5bed34444648575b105275e8bea0e9e9206945a08dc`) passed Owner acceptance in the isolated clean Windows 11 VMware test environment (`Clean Windows 11 Baseline` snapshot).
- **Direct Stable Finalization (PR #51):** Following Owner direction after RC acceptance PASS, `v1.2.0-rc.1` was not published as a separate GitHub prerelease; PR #51 advanced release metadata directly from `1.2.0-rc.1` to **`1.2.0`** (`APP_VERSION = "1.2.0"`, Windows PE `FileVersion = "1.2.0.0"`, `ProductVersion = "1.2.0"`), synchronized the upgrade verification harness (`winbuild/verify_upgrade.py` and `tests/test_v1_1_phase_f2_upgrade_verification.py`), packaging version checks (`tests/test_m20_build_packaging.py`), and CI job label (`.github/workflows/windows_build.yml`), and merged into `main` at `d6af0a684db403a4167bea6edf65f8db99523d1a`.
- **Hosted Release-Closure CI & Final Signed Build Verification:** GitHub Actions runs [39137882334](https://github.com/Peter-S-Shi/vocabulary-app/actions/runs/39137882334) (PR #51) and [39138073680](https://github.com/Peter-S-Shi/vocabulary-app/actions/runs/39138073680) (`main@d6af0a684db403a4167bea6edf65f8db99523d1a`) passed all three Release Closure shards plus the Windows installer build, packaged-launch smoke test, and automated isolated `v1.1.0 → v1.2.0` overlay upgrade verification.
- **Final Stable Clean-VM Acceptance & Publication (`v1.2.0`):** Built and signed from clean `main` commit `d6af0a684db403a4167bea6edf65f8db99523d1a`, `VocabularyApp-Setup-1.2.0.exe` (`35,303,256` bytes, `SHA-256 97a6781f8b54f63f35a6302f9a5a54fa9a981260794e876f5b76c5fc1299d428`, signed with the established `CN=Peter Shi` developer certificate, thumbprint `3E812E6E86C40158C531222D026EA53D70775103`) passed clean Windows 11 VMware `v1.1.0 → v1.2.0` overlay upgrade Human Acceptance (verifying single uninstall registration, pre-/post-upgrade SHA-256 data preservation across all four components, sentinel records, and `Settings → Storage` readiness) and was published under annotated tag `v1.2.0` (`e12ab99ad2ecafa1beb7563fb54d1541665e5380`) on the [v1.2.0 GitHub Release](https://github.com/Peter-S-Shi/vocabulary-app/releases/tag/v1.2.0).

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

**Vocabulary App v1.2.0 is the current published stable release.**

Milestones 22 and 23 are **Complete**. All three parallel Release Closure shards plus the Windows installer/upgrade-proof job succeeded on merged `main` (`d6af0a684db403a4167bea6edf65f8db99523d1a`); that exact commit was tagged `v1.2.0`; the canonical Windows installer (`VocabularyApp-Setup-1.2.0.exe`) was built, signed, and verified against clean Windows 11 VMware `v1.1.0 → v1.2.0` overlay acceptance; and the public GitHub Release was published.

## Current Release — v1.2.0

- **Version:** `1.2.0`
- **Tag:** `v1.2.0` (`e12ab99ad2ecafa1beb7563fb54d1541665e5380`)
- **Release source / merged `main` SHA:** `d6af0a684db403a4167bea6edf65f8db99523d1a`
- **Merged PRs:** #44 (`M22-A`), #45 (`M22-B`), #46 (`M22-C`), #47 (`M22-D`), #49 (`M23-A`), #50 (`M23-B/C`), #51 (`Stable Release v1.2.0 Finalization`)
- **Canonical installer:** `VocabularyApp-Setup-1.2.0.exe` (`35,303,256` bytes)
- **Canonical installer SHA-256:** `97a6781f8b54f63f35a6302f9a5a54fa9a981260794e876f5b76c5fc1299d428` (published in `SHA256SUMS.txt` on the `v1.2.0` GitHub Release)
- **Distribution:** [GitHub Release `v1.2.0`](https://github.com/Peter-S-Shi/vocabulary-app/releases/tag/v1.2.0) (Latest)
- **Platform:** Windows 10/11 x64
- **License:** MIT

The canonical `v1.2.0` release build was produced from a clean checkout whose `HEAD` exactly matched the tagged `v1.2.0` source SHA (`d6af0a684db403a4167bea6edf65f8db99523d1a`), with `dist/build_manifest.json` reporting `source_dirty: false` and `app_version: "1.2.0"`. Both the installer SHA-256 and Authenticode signature (`CN=Peter Shi`, thumbprint `3E812E6E86C40158C531222D026EA53D70775103`) were independently re-verified against the published GitHub Release download.

## Previous Release: v1.1.0 (Historical Baseline)

- **Version:** `1.1.0`
- **Tag:** `v1.1.0`
- **Release source:** the merged `main` commit the `v1.1.0` tag points at (`6bc492082cb2db8e19fdbf6c8530468edb4edf02`)
- **Merged PR:** #36 — `M21: Vocabulary App v1.1.0 — Phase F Release Verification`
- **Canonical installer:** `VocabularyApp-Setup-1.1.0.exe`
- **Canonical installer SHA-256:** `8ae6bcf615ed180788119384e0c38b8d64590b6dbcce2b542e113b4fca3ecf89` (published in `SHA256SUMS.txt` with the `v1.1.0` GitHub Release)
- **Distribution:** GitHub Releases
- **Platform:** Windows 10/11 x64
- **License:** MIT

The canonical `v1.1.0` release build was produced from a clean checkout whose `HEAD` exactly matched the tagged `v1.1.0` source SHA. `dist/build_manifest.json` reported `source_dirty: false` and `app_version: "1.1.0"` against that SHA. The installer SHA-256 was computed by the release build pipeline and independently re-verified with Windows `certutil`; both values matched, and both are published in `SHA256SUMS.txt` on the `v1.1.0` GitHub Release.

## Previous Release: v1.0.0 (Historical Baseline)

- **Version:** `1.0.0`
- **Tag:** `v1.0.0`
- **Release source / merged `main` SHA:** `2363e73bbd85ca24f7e227f8007e0046eeabd471`
- **Merged PR:** #33 — `M20: Packaging and Release Candidate — Finalized 1.0.0, Human RC PASS`
- **Canonical installer:** `VocabularyApp-Setup-1.0.0.exe`
- **Canonical installer SHA-256:** `108095e3ce7d256bc610c33f427a9ee2fee4956cb69dde3bf0e105413865b297`

The remaining M20 evidence below (RC acceptance, engineering evidence, signing model, product state, data contract, known limitations) describes the v1.0.0 release baseline specifically and is preserved as the historical record of how that baseline was reached; where v1.1.0 and v1.2.0 reuse or extend the signing identity and data-location contract, that evolution is noted explicitly.

## Historical M20 / v1.0.0 Human RC Acceptance Record

**Human RC: PASS (2026-08-19).**

The authoritative v1.0.0 Human RC decision was granted against exact RC SHA:

`89263a4f0f477fe5455ed22bedffd1968218bb1e`

and its RC artifact:

- `VocabularyApp-Setup-1.0.0-rc.1.exe`
- SHA-256 `8b435657c5cecfecd52f96a6f49d648e1fcaa2e4b58cada03cfc3baf7ea87710`

That historical RC acceptance record is intentionally preserved. After PASS, the already-frozen release scheme advanced release metadata only from `1.0.0-rc.1` to `1.0.0`; no product behavior or scope was reopened. Targeted version/build/signature/install/launch/uninstall verification was then completed before merge and publication.

## Historical M20 Engineering Evidence (v1.0.0 Baseline)

At the Human-RC-accepted v1.0.0 RC source:

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

Publicly trusted code signing is deferred to a possible future broader public/commercial/Microsoft Store distribution effort and is not part of the completed Portfolio release contract.

v1.1.0 (`VocabularyApp-Setup-1.1.0.exe`), `v1.2.0-rc.1` (`VocabularyApp-Setup-1.2.0-rc.1.exe`), and v1.2.0 (`VocabularyApp-Setup-1.2.0.exe`) reuse this same `CN=Peter Shi` self-signed developer identity (`Thumbprint 3E812E6E86C40158C531222D026EA53D70775103`); the trust model above (not publicly trusted, SmartScreen warnings may still occur) applies unchanged.

## Product State

The PySide6 native desktop application is the primary product surface. It includes:

- Today / daily learning workflow
- Entries and Templates management
- Collections and Card organization
- Review and Quiz workflows
- Review Calendar / Card History
- Settings and Data Tools (including unified Settings → Storage data-folder relocation in v1.2.0)
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
- Default durable data root: `%LOCALAPPDATA%\vocabulary_app\` (also serves as the bootstrap locator directory for `data-root.json` and `migration-recovery.json`).
- Default database: `%LOCALAPPDATA%\vocabulary_app\vocab.db`.
- Default backups: `%LOCALAPPDATA%\vocabulary_app\backups\`.
- Unified data-folder relocation (v1.2.0+): Settings → Storage can relocate SQLite database, backups, preferences, and audio cache together to a user-selected folder with sibling staging, atomic no-clobber promotion, cross-process locking, a durable recovery journal, retained source rollback baseline, and fail-closed startup validation.
- Existing database import: explicit user-selected copy-with-backup; never silently moved or migrated in place from the source file.
- Upgrade: no automatic updater in v1.0, v1.1, or v1.2 (v1.1+ includes a manual/background release-availability check that reports available GitHub releases without downloading or installing them); a newer installer overlays application binaries while preserving durable user data and creating migration safety backups. Real isolated `v1.0.0 → v1.1.0` and `v1.1.0 → v1.2.0` overlay upgrade proofs are part of the M21 and M23/v1.2.0 release-closure evidence above.
- Uninstall: preserves user data by default; destructive deletion requires explicit opt-in.

## Known Limitations / Deferred Work

These are recorded limitations:

- For historical v1.0.0, full pristine clean-machine VM verification was deferred (distribution acceptance used a fresh local standard Windows account plus real install/migration/uninstall evidence); for v1.2.0, both the signed `v1.2.0-rc.1` candidate and final signed `1.2.0` stable installer passed clean Windows 11 VMware acceptance (`Clean Windows 11 Baseline` snapshot).
- Publicly trusted code signing / SmartScreen reputation remains deferred; v1.0.0, v1.1.0, and v1.2.0 use the self-signed developer certificate described above.
- Windows 10/11 x64 is the only packaged desktop platform.
- Audio capability depends on compatible speech voices already installed on the user's Windows system; the app does not silently download or redistribute third-party voice models/runtimes.
- No automatic updater; release update checks are notification-only.
- Issue #48 (UI/UX refresh / visual redesign) remains explicitly deferred to a separately authorized future milestone.

## Lifecycle Closure

The v1.0, v1.1, and v1.2 lifecycles are complete and released:

`M11 → M12 → M13 → M14 → M15 → M16 → M17 → M18 → M19 → M20 → v1.0.0 Released → M21 → v1.1.0 Released → M22 → M23 → v1.2.0 Released`

Completed release milestones (M20, M21, M22, M23) are closed and should not be reopened for ordinary future development. Any post-v1.2 work should begin from a new explicitly defined milestone/version decision.

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
