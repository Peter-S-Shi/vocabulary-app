# Milestone 15 Closure Candidate

Status: pending independent M15.3 review and merge. This document does not
claim that M15.3 is complete on `main`.

- M15.0 selected and feasibility-tested fixed EN/FR/ZH providers and recorded
  license/attribution obligations.
- M15.1 added persisted required-field speech semantics, safe legacy migration,
  Template Definition compatibility, and a UI-independent provider boundary.
- M15.2 added content-addressed canonical assets, deterministic current-Card
  composition, segment-sequence render identity, and both repetition modes.
- M15.3 adds snapshot-based single/selected/Collection export, one Card per
  file, safe naming/conflicts, per-Card atomic publication, partial-success
  results, explicit retry, progress, real-provider smoke, and third-party notice.

The closure candidate preserves fixed Kokoro `af_heart`, sherpa-onnx
`fr_FR-siwis-medium`, and Windows Yaoyao routing; canonical mono 24 kHz signed
16-bit PCM WAV; current Card/latest-revision truth; required field semantics;
and zero learning-state mutation. M15.3 adds no schema/app-data migration.

Review-branch verification passed 13 focused M15.3 tests, 41 integrated
M15.1-M15.3 audio tests, and the full 161-test repository suite. Compilation
and architecture checks passed. A real synthetic Collection smoke routed EN to
Kokoro, FR to sherpa-onnx, and ZH-CN to Windows Yaoyao and published three
readable canonical WAV files for three Cards before cleaning all temporary
database, cache, and export artifacts.

After review and merge, a documentation-only reconciliation may record the
actual merge SHA and mark M15 complete on `main`.

Deferred beyond M15: spoken/audio Quiz modes, Quiz semantic changes,
substantial Streamlit audio UX, native desktop export UX, media management,
cloud TTS, voice cloning, provider reselection, background export daemons, and
automatic synchronization of old exports. Milestone 16 has not started.
