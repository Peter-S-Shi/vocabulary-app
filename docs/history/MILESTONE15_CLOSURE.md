# Milestone 15 Closure

Status: Complete on `main`.

M15.3 PR #17 merged normally at
`9448f2e44940e0d426a965823aa66c48f53ec0f1` from independently reviewed final
head `765c4c5f92c29a5c30cb41b0c2aa3fbbc01df7db`. This merge completed Milestone
15 — Audio Foundation. PR #16 was superseded and absorbed through PR #17
ancestry. GitHub therefore marks it merged, but it produced no separate merge
commit.

- M15.0 selected and feasibility-tested fixed EN/FR/ZH providers and recorded
  license/attribution obligations.
- M15.1 added persisted required-field speech semantics, safe legacy migration,
  Template Definition compatibility, and a UI-independent provider boundary.
- M15.2 added content-addressed canonical assets, deterministic current-Card
  composition, segment-sequence render identity, and both repetition modes.
- M15.3 added snapshot-based single/selected/Collection export, one Card per
  file, safe naming/conflicts, per-Card atomic publication, partial-success
  results, explicit retry, progress, real-provider smoke, and third-party notice.

The completed milestone preserves fixed Kokoro `af_heart`, sherpa-onnx
`fr_FR-siwis-medium`, and Windows Yaoyao routing; canonical mono 24 kHz signed
16-bit PCM WAV; current Card/latest-revision truth; required field semantics;
and zero learning-state mutation. M15.3 adds no schema/app-data migration.

Final verification passed 13 focused M15.3 tests, 41 integrated
M15.1-M15.3 audio tests, and the full 161-test repository suite. Compilation
and architecture checks passed. A real synthetic Collection smoke routed EN to
Kokoro, FR to sherpa-onnx, and ZH-CN to Windows Yaoyao and published three
readable canonical WAV files for three Cards before cleaning all temporary
database, cache, and export artifacts.

Deferred beyond M15: spoken/audio Quiz modes, Quiz semantic changes,
substantial Streamlit audio UX, native desktop export UX, media management,
cloud TTS, voice cloning, provider reselection, background export daemons, and
automatic synchronization of old exports. Milestone 16 is Not Started and
requires separate authorization.
