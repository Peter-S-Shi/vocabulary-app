# M15.2 Audio Asset and Card Composition Contract

Status: implemented on the M15.2 review branch; incomplete on `main` until
independent review and merge.

## Field asset identity

A field asset is addressed by a SHA-256 fingerprint over canonical JSON containing:

- exact speech text;
- canonical language;
- frozen provider and voice/model identity;
- relevant synthesis configuration;
- field-asset fingerprint version; and
- canonical audio contract version.

Entry, Template, Field, Collection, Card, Card number/name, and Card revision
identifiers are excluded. Identical speech under identical synthesis inputs can
therefore reuse one unit asset. Any audio-relevant input change produces a new
key without mutable invalidation bookkeeping.

## Cache authority

Generated units and Card renders are disposable filesystem artifacts. The root
is resolved from `VOCAB_APP_AUDIO_CACHE_DIR`, then the platform-local app-data
directory. It is outside SQLite and normally outside the repository. Deleting
it loses no learning data; backup and restore do not depend on it.

A cache hit must be a readable canonical WAV. A miss synthesizes into a
temporary directory, normalizes and validates there, then publishes atomically.
Provider/normalization failure leaves no final asset. Per-key process locks and
atomic replacement keep repeated/concurrent local requests correct.

## Canonical audio format

All composition assets are RIFF WAV containing mono, 24 kHz, signed 16-bit PCM.
This is a practical common denominator for the frozen EN/FR/ZH providers,
supports deterministic dependency-free concatenation, and is suitable for
future desktop playback/export. Provider WAVs are decoded, mixed to mono, and
linearly resampled before use; incompatible or empty payloads are rejected.

## Current Card truth and planning

Planning resolves the active stable `card_id`, its latest `card_revision_id`,
and immutable revision membership in `position_within_card` order. Each Entry
then uses the M15.1 required-field plan in Template/display order. Historical
revisions remain historical. Any unresolved required unit blocks the whole Card
before composition; required content is never silently skipped.

The inspectable plan includes Card/revision provenance, ordered Entry IDs,
ordered units and asset keys, provider/voice/language provenance, composition
configuration, explicit segments, readiness, and controlled issues.

## Card render identity and boundaries

A Card render key fingerprints the ordered unit asset keys, canonical format,
renderer version, repetition mode/count, and all pause timings. Card number,
name, ID, and revision ID are excluded from content identity. Text/voice changes
and current membership/order changes naturally produce a new render key.

Boundaries are explicit zero-valued PCM frames:

- repeated copy boundary: 350 ms;
- field boundary inside one Entry: 500 ms;
- Entry boundary: 900 ms; and
- repeated whole-Card pass boundary: 1200 ms.

These values are structured/versioned composition inputs, not UI preferences.

## Repetition semantics

- **Repeat Each Field:** repeat a unit in place before advancing to the next
  field.
- **Repeat Whole Card:** render one complete ordered Card pass, then repeat the
  complete pass.

Repeat count is explicit, deterministic, and limited to 1-20 in the reusable
API. No persistent preference is introduced.

## Failure and learning-state boundary

Planning, unit synthesis, cache publication, and Card rendering are read-only
with respect to SQLite. They do not create or alter Quiz evidence, Card learning
completion, review history, analytics evidence, pools, Collection membership,
or Card revisions. Failures are controlled results and do not corrupt the
learning database.

## Deferred to M15.3 or later

M15.2 does not implement multi-Card/Collection batch export, final export
naming/location, batch progress/retry/cleanup orchestration, substantial audio
UI, desktop audio UI, spoken Quiz modes, provider reselection, cloud voices, or
media-library management. Existing Quiz learning semantics remain unchanged.
