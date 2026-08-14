# Third-Party Notices for Audio Foundation

This distribution-facing summary derives from
`docs/policies/TTS_LICENSE_AND_ATTRIBUTION.md`. Future packaged distributions
must also include complete applicable upstream license and NOTICE files.

## English: Kokoro-82M / `af_heart`

- Kokoro runtime and model/weights: Apache License 2.0.
- Model-level disclosed sources: Koniwa (CC BY 3.0) and SIWIS (CC BY 4.0).
- Bundling must retain applicable Apache notices and recorded attributions.

## French: sherpa-onnx / `fr_FR-siwis-medium`

- sherpa-onnx runtime: Apache License 2.0.
- `piper-voices` packaging: MIT.
- SIWIS voice/dataset: CC BY 4.0.
- The project does not use or introduce the GPL-3.0 `piper1-gpl` runtime.

## Mandarin: Windows Yaoyao

Yaoyao is OS-provided through Windows WinRT. No Microsoft voice/model asset is
bundled, copied, or redistributed. There is no silent fallback.

## Packaging gate

Before distribution, ship all license/NOTICE texts for the exact bundled
runtimes, models, voices, and datasets, and recheck them against the authority.
