# Milestone 15.0 — TTS Provider Selection Closure

Status: **Closed** (2026-08-13). This is the authoritative routing decision
for formal Milestone 15.1 (Audio Foundation) implementation. Do not reopen
provider search without the product owner explicitly authorizing it.

This record consolidates the outcome of the M15.0 feasibility/audition
spike, which originally ran across three audition rounds plus a final
selection pass under `spikes/m15_tts_voice_audit/` (that directory has
since been removed — its durable conclusions live here and in
[`../policies/TTS_LICENSE_AND_ATTRIBUTION.md`](../policies/TTS_LICENSE_AND_ATTRIBUTION.md);
shared runtime/model assets live outside the repository, in a local
`<SHARED_TTS_DIR>` (a machine-specific path outside this Git repository —
see local setup notes for the exact location), documented below).

## Product target

> Standard, clear, neutral, stable, low-expression, recognizably
> synthetic/system-like speech — closer to a translation/dictionary/system
> voice (e.g. Google Translate) than to expressive human-like TTS. Higher
> human-realism is explicitly **not** a positive target for this product.

## Authoritative routing

| Language | Provider/runtime | Model/voice | Distribution |
|---|---|---|---|
| English | Kokoro (`kokoro` pip package) | Kokoro-82M / `af_heart` | Bundled/local model (~314 MB via the standard Hugging Face cache) |
| French | sherpa-onnx | `fr_FR-siwis-medium` (Piper/VITS, `sid=0`) | Bundled/local ONNX voice (~78 MB) |
| Mandarin | Windows WinRT `SpeechSynthesizer` | Yaoyao (`zh-CN`, OneCore) | **OS-installed, not bundled** — no Microsoft voice/model file is copied or redistributed |

**No-silent-fallback policy (Mandarin):** if Yaoyao is not installed on a
given user's machine, the app must fail visibly / surface a
missing-language-pack condition — never silently substitute Huihui,
Kangkang, or any other voice.

## Shared local assets

Runtime/model assets selected above live outside this repository, at a
local `<SHARED_TTS_DIR>` (see that directory's own `README.md` for full
reuse instructions), so they are available to future projects without a
`spikes/` dependency:

```text
<SHARED_TTS_DIR>\
|-- venv\                          # Python 3.11: kokoro, sherpa-onnx, soundfile, numpy, onnxruntime, CPU torch
|-- kokoro\synth.py                 # English adapter (af_heart)
|-- sherpa-onnx\
|   |-- synth.py                    # French adapter (fr_FR-siwis-medium)
|   `-- voices\vits-piper-fr_FR-siwis-medium\
`-- windows-mandarin-yaoyao\synthesize_yaoyao.ps1   # WinRT adapter, no bundled model
```

M15.1 implementation code should reference these paths (or install its own
copies of the same packages/voice files) rather than depending on anything
under the now-deleted `spikes/` directory.

## Why these three, not others

- **English:** Kokoro-82M `af_heart` won a blind audition against MeloTTS
  and sherpa-onnx's `en_US-libritts_r-medium` on perceptual grounds.
- **French:** sherpa-onnx `fr_FR-siwis-medium` won the same blind audition
  against Kokoro and MeloTTS's French voices.
- **Mandarin — three rejected rounds before landing on a plain OS voice:**
  - Round 1 rejected all three tested Mandarin candidates (regional
    accent, 8 kHz quality, general human/character-like coloration).
  - Round 2 tried modern expressive/voice-design TTS (Qwen3-TTS
    CustomVoice, CosyVoice-300M-SFT, VoxCPM1.5) — **all four candidates
    rejected** as too human-realistic, too character/persona-colored, or
    too electronic/glitchy for the target "standard, system-like" profile.
  - Round 3 pivoted to conventional fixed-speaker open-source TTS
    (PaddleSpeech FastSpeech2-CSMSC+HiFiGAN, ESPnet CSMSC full-band VITS)
    plus this machine's actual local Windows voices, on the hypothesis
    that a plain OS-provided voice might already match the desired
    texture better than any modern neural TTS tried so far. The product
    owner's final pick was exactly that: **Windows Yaoyao**, over every
    open-source model evaluated across all three rounds.
  - **Takeaway for future TTS-adjacent decisions on this product:** prefer
    simpler/older/fixed-speaker synthesis over newer expressive or
    voice-cloning-capable architectures — sophistication in the
    "sounds human" direction is actively counterproductive for this
    product's Mandarin voice, not merely neutral.

## Yaoyao Unicode/mojibake bug — root cause and fix (already resolved)

**Root cause:** Windows PowerShell 5.1's `Get-Content`, called without an
explicit `-Encoding` parameter, does not default to UTF-8 on this machine.
A BOM-less UTF-8 test-data file was misread as Windows-1252, so every
multi-byte UTF-8 Chinese character was corrupted into garbled Latin-1-range
mojibake *before* it reached WinRT — e.g. "学习" (UTF-8 bytes `E5 AD A6 E4
B9 A0`) became six garbled Latin-1 characters. `SynthesizeTextToStreamAsync`
correctly spoke the text it was given; Yaoyao and the WinRT API were never
at fault. A second instance of the identical root cause was found in
`.ps1` script files themselves: `powershell -File script.ps1` on a
BOM-less UTF-8 script containing literal Chinese text hit the same
misread-as-ANSI default.

**Fix (already applied in the retained `synthesize_yaoyao.ps1` adapter):**
1. Any file read of Chinese-bearing text must use explicit `-Encoding UTF8`.
2. Production-path Chinese strings are built from explicit `[char]0x....`
   Unicode code points in pure-ASCII `.ps1` source, avoiding the
   file-encoding boundary entirely.
3. The adapter logs exact text/length/UTF-16 code points immediately
   before calling WinRT and **refuses to synthesize** if a pre-flight
   code-point cross-check (against an independently-computed expected
   value) fails, rather than risking silent corruption reaching the voice.

**Verified:** all 8 required Chinese acceptance-gate items (isolated words
+ two full sentences) passed Unicode verification and produced correct,
non-silent audio before this closure was written.

## License and attribution

See [`../policies/TTS_LICENSE_AND_ATTRIBUTION.md`](../policies/TTS_LICENSE_AND_ATTRIBUTION.md)
for the full per-provider breakdown (runtime license, model/voice license,
training-data attribution, redistribution obligations). Summary: no
`UNRESOLVED` items. English and French both carry CC BY 4.0
training-data attribution obligations (SIWIS corpus, used by both the
Kokoro and the sherpa-onnx French voice); Mandarin carries no bundled-asset
obligation since no Microsoft file is redistributed.

## Data-model finding for M15.1: field spoken-language role

One open finding from the audition, relevant when the formal M15.1
speech-language contract is designed: **no explicit per-field
spoken-language-role metadata exists yet.** The schema has no field-level
attribute distinguishing "this field is in the Entry's source language"
from "this field is in the Entry's explanation language." The audition
used a heuristic, not a schema guarantee: the `meaning` field is treated
as the explanation-language field; every other populated field (including
`example`) is treated as the entry (source) language field. This
heuristic held for every sampled row during the audition, but nothing in
the schema enforces that an `example` field couldn't legitimately hold
explanation-language text for some future template. **Recommendation:**
add explicit field-role metadata (e.g. `speech_language_role: entry |
explanation | none`) to `entry_template_fields` rather than relying on a
naming heuristic. This remains an open M15.1 data-model question, not a
frozen decision.

## Outstanding product decision carried forward (not yet implemented)

**Frozen decision:** `required` is the single authoritative
template-validity rule, and it must be corrected at the schema level for
French conjugation/agreement fields — this is not merely a narration-time
concern to be worked around separately.

- `French Verb Present`'s present-tense conjugation fields — `je`, `tu`,
  `il_elle_on`, `nous`, `vous`, `ils_elles` — must become `required=1` in
  a formal template migration once M15.1 (or a dedicated
  template-migration task) begins.
- This generalizes to **any other French word form involving
  conjugation/agreement** on the same principle, including at least
  `French Adjective Agreement` (`feminine_singular`, `masculine_plural`,
  `feminine_plural`) and `French Noun Gender Plural` (`gender`, `plural`,
  `article`) — these must also become `required=1`.
- **Do not implement a separate speech-only workaround (e.g. a
  `speech-enabled` flag) for these fields instead of this schema fix.**
  `required` stays the one authoritative validity rule; there is no
  parallel "required for validity" vs. "required for speech" distinction
  for these fields.

(This was first identified during the M15.0 audition when it was
discovered that narrating only `required=1` fields would have gutted
French verb/adjective/noun Card audio down to headword-plus-translation,
since only the headword + meaning fields were `required=1` while the
actual conjugation/agreement forms were not.)
