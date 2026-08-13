# M15.1 Speech Semantic Contract

Status: implemented on the M15.1 review branch; not complete on `main` until
independent review and merge.

## Participation and roles

For M15, `entry_template_fields.required = 1` is the only speech-participation
gate. Optional fields do not participate and use `speech_language_role = none`.
There is no parallel `speech_enabled` flag.

Every participating field must persist one deterministic role:

- `entry`: resolve the Entry's `language`;
- `explanation`: resolve the Entry's `explanation_language`; or
- `unresolved`: the field is not audio-ready and synthesis must not begin.

The pair is canonicalized at every write/import/export boundary: optional fields
always use `none`; making an optional field required without selecting a role
uses `unresolved`; making a required field optional uses `none`. A required
field with an unresolved role or blank value produces a controlled unresolved
speech plan. Field keys and text content are never used to guess language roles.

## System Templates

System Template roles are explicit and migration-owned:

- General Entry: `term` is `entry`; `meaning` is `explanation`.
- French Verb Present: `infinitive`, `je`, `tu`, `il_elle_on`, `nous`,
  `vous`, and `ils_elles` are required `entry`; `meaning` is required
  `explanation`.
- French Adjective Agreement: `masculine_singular`, `feminine_singular`,
  `masculine_plural`, and `feminine_plural` are required `entry`; `meaning` is
  required `explanation`.
- French Noun Gender Plural: `singular`, `gender`, `plural`, and `article` are
  required `entry`; `meaning` is required `explanation`.

Other current system fields remain optional and non-spoken. Migration changes
Template metadata only; it does not fabricate missing Entry values.

## Custom Templates and portability

Legacy custom Template fields migrate safely:

- optional fields become `none`;
- required fields become `unresolved` until explicitly configured.

Core APIs expose Template readiness inspection and controlled custom-field role
updates. No substantial Streamlit UI is added.

Template Definition CSV v2 adds `speech_language_role` and is the default
export. Definition v1 remains importable. A v1 required field imports as
`unresolved`, never as a guessed role; an optional v1 field imports as `none`.

## Language and provider routing

Stored language labels are normalized by an explicit alias table, never by
examining text. The supported canonical routes are:

| Canonical language | Provider | Fixed voice/model |
|---|---|---|
| `en` | Kokoro | Kokoro-82M / `af_heart` |
| `fr` | sherpa-onnx | `fr_FR-siwis-medium` |
| `zh-CN` | Windows WinRT | Yaoyao (`zh-CN`) |

Unsupported languages and unavailable providers produce controlled issues.
Yaoyao has no fallback. Mandarin text crosses the Unicode Windows process
boundary directly, and independently computed UTF-16 code units are verified
immediately before WinRT synthesis.

Provider runtime/model paths are resolved from `VOCAB_APP_SHARED_TTS_DIR`.
Tracked code and documentation contain no machine-specific shared-asset path.
Unit tests inject fake providers and do not require real model assets.

## Speech plan

The UI-independent Entry speech plan preserves Template order and exposes:

- Entry, Template, and field identity;
- field key and text;
- persisted role;
- resolved canonical language; and
- selected provider and voice identity.

A plan is `ready` only when every required field has text, a valid role, a
supported language, and an available selected provider. Optional fields are
excluded.

Planning and one-unit synthesis do not create or alter Quiz sessions/evidence,
Card learning completion, Review history, Analytics evidence, pools, Card
history, or Collection membership.

## Deferred beyond M15.1

M15.1 does not implement Card concatenation, audio cache identity/invalidation,
repetition modes, batch export, final file naming, Streamlit/desktop audio UI,
or spoken Quiz behavior. Existing Quiz learning semantics are unchanged.
