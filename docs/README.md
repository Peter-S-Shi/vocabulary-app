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

Current Audio Foundation decision records:

- [M15.0 TTS Provider Selection Closure](history/M15_0_TTS_PROVIDER_SELECTION_CLOSURE.md)
- [TTS License and Attribution Record](policies/TTS_LICENSE_AND_ATTRIBUTION.md)
- [M15.1 Speech Semantic Contract](design/M15_1_SPEECH_SEMANTIC_CONTRACT.md)
- [M15.2 Audio Asset and Card Composition Contract](design/M15_2_AUDIO_ASSET_COMPOSITION_CONTRACT.md)

Executable development checks remain in [`scripts/`](../scripts/) and
[`tools/`](../tools/). Local databases, private QA results, imports, exports,
backups, secrets, and other user-owned artifacts are not repository
documentation and must remain outside Git.
