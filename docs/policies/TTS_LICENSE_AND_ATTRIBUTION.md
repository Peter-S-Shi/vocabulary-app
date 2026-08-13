# TTS License and Attribution Record

Date recorded: 2026-08-13 (M15.0 provider selection). Applies to the three
providers selected in
[`../history/M15_0_TTS_PROVIDER_SELECTION_CLOSURE.md`](../history/M15_0_TTS_PROVIDER_SELECTION_CLOSURE.md).
No other candidate evaluated during the M15.0 audition is covered here.

For each selected asset: runtime license, model/voice license, training-data
attribution, redistribution obligations, and bundled-vs-OS-provided status
are recorded separately, since these are frequently different things even
for a single "model."

---

## English — Kokoro-82M / `af_heart`

| Aspect | Finding |
|---|---|
| Runtime (`kokoro` pip package) license | **Apache 2.0** |
| Model/weights license | **Apache 2.0** (`hexgrad/Kokoro-82M` model card explicitly states Apache-licensed weights may be used for production/personal deployment) |
| `af_heart.pt` | Distributed as part of the same Apache-2.0 model repository; no separate/stricter license stated for this specific voice |
| Training-data attribution | The Kokoro v1.0 model card discloses CC-BY-licensed training sources, including **Koniwa (CC BY 3.0)** and, directly relevant to this voice family, **SIWIS (CC BY 4.0)** |
| Distribution | **Bundled/local** — model weights downloaded once and stored locally (standard Hugging Face cache, ≈314 MB for the full multilingual model; also available at a local `<SHARED_TTS_DIR>` for shared reuse across projects — see local setup notes for the exact path) |

**Handling adopted:**
- Retain Apache-2.0 license text and any NOTICE file obligations from the
  `kokoro` package and the Kokoro-82M model repository when bundling.
- Conservatively include attribution for the CC-BY training sources Kokoro
  itself discloses (Koniwa CC BY 3.0, SIWIS CC BY 4.0), even though `af_heart`
  is the English voice and SIWIS specifically trained the *French* voice in
  the same model — the model card discloses these as sources for the model
  as a whole, so attribution is included at the model level rather than
  narrowly scoped per-voice.
- No separate, more restrictive license is invented for `af_heart` beyond
  what upstream states.

---

## French — sherpa-onnx runtime + `fr_FR-siwis-medium` voice

| Aspect | Finding |
|---|---|
| Runtime (`sherpa-onnx`) license | **Apache 2.0** (`k2-fsa/sherpa-onnx` repository) |
| Voice repository/collection license | **MIT** (`rhasspy/piper-voices` on Hugging Face states `license: mit` for the collection) |
| Voice/model license (per `fr_FR-siwis-medium` MODEL_CARD) | Trained on the **SIWIS dataset, CC BY 4.0**, 22,050 Hz, 1 speaker — confirmed directly from the bundled `MODEL_CARD` file inside the downloaded voice archive |
| Distribution | **Bundled/local** — ONNX model + tokens + bundled `espeak-ng-data/` (≈78 MB), available at `<SHARED_TTS_DIR>\sherpa-onnx\voices\vits-piper-fr_FR-siwis-medium\` |

**Important runtime distinction (verified during the M15.0 audition, not
assumed):** the *currently maintained* Piper reference runtime
(`OHF-Voice/piper1-gpl`, the Open Home Foundation continuation of the
original `rhasspy/piper`) is **GPL-3.0**, specifically because it embeds
the GPL-licensed `espeak-ng` C library for phonemization. **This app does
not use that runtime.** The selected runtime is **sherpa-onnx**, which is
Apache 2.0 and uses only `espeak-ng`'s *data files* (phoneme dictionaries)
bundled alongside each voice, not the GPL `espeak-ng` C library/engine
itself — sherpa-onnx implements its own phonemization logic against that
data. This keeps the runtime dependency chain Apache-2.0-clean. (The
original, no-longer-primary `rhasspy/piper` repository was itself MIT; the
GPL obligation is specific to the newer, actively-maintained `piper1-gpl`
fork this app does not use.)

**Handling adopted:**
- Retain sherpa-onnx's Apache-2.0 license text/NOTICE obligations.
- Retain the MIT notice for the `rhasspy/piper-voices` repository/model
  packaging.
- Include a CC BY 4.0 attribution/license reference for the SIWIS dataset
  specifically (voice: `fr_FR-siwis-medium`).
- Do not bundle or link the GPL `piper1-gpl` runtime; sherpa-onnx remains
  the sole runtime for this voice.

---

## Mandarin — Windows OneCore Yaoyao (`zh-CN`)

| Aspect | Finding |
|---|---|
| Provider | Microsoft, via the Windows OS (OneCore speech platform) |
| Access mechanism | `Windows.Media.SpeechSynthesis.SpeechSynthesizer` (WinRT), a supported public Windows API |
| Bundled model/voice file | **None.** No Microsoft voice or model file is copied, extracted, reverse-engineered, or redistributed by this app. |
| License applicable to this app | Governed entirely by the end user's own Windows license and whatever language/voice components they have installed through normal Windows Settings; this app makes no separate license claim over the voice itself because it never possesses the voice's underlying assets |
| Distribution | **OS-provided, not bundled.** If Yaoyao (or any `zh-CN` voice) is not installed on a given user's machine, this app must not silently substitute another voice or attempt to install/copy voice files itself — see the no-silent-fallback policy in `docs/history/M15_0_TTS_PROVIDER_SELECTION_CLOSURE.md`. |

No fact here is marked `UNRESOLVED` — the OS-provided-voice model has no
ambiguity: the app is a *caller* of a supported Windows API, not a
distributor of Microsoft's voice data, so no separate license grant from
Microsoft to this app is needed for that reason alone. (This does not
constitute legal advice; if the product is ever distributed at a scale
where this matters commercially, a qualified reviewer should confirm this
reading against the current Windows SDK / OS licensing terms in force at
that time.)

---

## Summary table

| Language | Runtime license | Model/voice license | Training-data attribution | Distribution |
|---|---|---|---|---|
| English | Apache 2.0 (`kokoro`) | Apache 2.0 (Kokoro-82M) | CC BY 3.0 (Koniwa), CC BY 4.0 (SIWIS) — disclosed at model level | Bundled/local |
| French | Apache 2.0 (sherpa-onnx) | MIT (piper-voices repo) | CC BY 4.0 (SIWIS) | Bundled/local |
| Mandarin | N/A (OS API) | N/A (no bundled asset) | N/A | OS-provided, not bundled |

No entry in this record is marked `UNRESOLVED`.
