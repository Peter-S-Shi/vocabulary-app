# Documentation Map

Current repository entry points remain at the project root:

- [`README.md`](../README.md) — product overview and local setup
- [`ROADMAP.md`](../ROADMAP.md) — active lifecycle and milestone plan
- [`PROJECT_STATUS.md`](../PROJECT_STATUS.md) — evidence-based current status
- [`ARCHITECTURE.md`](../ARCHITECTURE.md) — architecture and dependency boundaries
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — contribution guidance

Supporting documentation is organized by purpose:

- [`design/`](design/) — frozen semantic contracts and durable product design
- [`history/`](history/) — completed milestone records and reconstructed history
- [`qa/`](qa/) — public manual QA plans and checklists
- [`migration/`](migration/) — desktop-transition and migration-readiness guidance
- [`policies/`](policies/) — content, data, privacy, storage, and update policies
- [`packaging/`](packaging/) — packaging feasibility and support assessments

Current Version (`v1.2.0`), Release Evidence, and Storage Architecture:

- [`PROJECT_STATUS.md`](../PROJECT_STATUS.md) — current `v1.2.0` stable release record, M22/M23 acceptance and clean-VM verification evidence, and historical `v1.1.0` / `v1.0.0` release baselines
- [`ROADMAP.md`](../ROADMAP.md) — completed M1–M23 milestone history, `v1.2.0` closure, and deferred post-`v1.2.0` backlog
- [Local Data Storage Policy (`DATA_STORAGE.md`)](policies/DATA_STORAGE.md) — default `%LOCALAPPDATA%\vocabulary_app\` locator root, M23-A `data-root.json` startup resolution, and M23-B/C unified Settings → Storage relocation, locking, and recovery journal invariants
- [M20 Release Contract](packaging/M20_RELEASE_CONTRACT.md) and [M20 Code Signing Setup](packaging/M20_CODE_SIGNING_SETUP.md) — Windows PyInstaller + Inno Setup packaging and self-signed Authenticode signing contract

Historical M15 Audio Foundation decision records:

- [M15.0 TTS Provider Selection Closure](history/M15_0_TTS_PROVIDER_SELECTION_CLOSURE.md)
- [TTS License and Attribution Record](policies/TTS_LICENSE_AND_ATTRIBUTION.md)
- [M15.1 Speech Semantic Contract](design/M15_1_SPEECH_SEMANTIC_CONTRACT.md)
- [M15.2 Audio Asset and Card Composition Contract](design/M15_2_AUDIO_ASSET_COMPOSITION_CONTRACT.md)
- [M15.3 Batch Audio Export Contract](design/M15_3_BATCH_EXPORT_CONTRACT.md)
- [Milestone 15 Closure](history/MILESTONE15_CLOSURE.md)
- [Distribution-facing Third-Party Notices](../THIRD_PARTY_NOTICES.md)

Historical Milestone 19 hardening evidence:

- [Milestone 19 Hardening / Acceptance QA Record](qa/MILESTONE19_HARDENING_QA.md)

Executable development checks remain in [`scripts/`](../scripts/) and
[`tools/`](../tools/). Local databases, private QA results, imports, exports,
backups, secrets, and other user-owned artifacts are not repository
documentation and must remain outside Git.
