# Vocabulary App Project Status

Last reviewed: 2026-08-28

This file is the authoritative evidence-based snapshot of the current project state. Detailed milestone history remains in `ROADMAP.md`, milestone QA/design/packaging documents, and the frozen pre-release snapshot archived at `docs/history/PROJECT_STATUS_PRE_V1_RELEASE_2026-08-19.md`.

## Current Phase

**Milestone 21 / Vocabulary App v1.1.0 is released. The `v1.1.0` tag and GitHub Release are published from verified merged `main`, and v1.1.0 is now the current public release.**

This is intentionally one step ahead of the exact publication mechanics
(installer build, signing, tag push, and GitHub Release creation) described
below -- it records the release-state this snapshot commit is authoritative
for once the `v1.1.0` tag is created pointing at it, the same convention
`v1.0.0`'s release used.

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
