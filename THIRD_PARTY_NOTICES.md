# Third-Party Notices

This file describes the third-party runtime components actually bundled in
the Vocabulary App v1.0 Windows distribution (the PyInstaller `--onedir`
build packaged by the Inno Setup installer). It is reconciled against the
frozen release decisions in `docs/packaging/M20_RELEASE_CONTRACT.md` §§ 2.3,
2.5 and must be re-checked against the actual frozen build output
(`pip list` inside the build environment, plus PyInstaller's collected-module
report) before each release.

## Speech / text-to-speech: no bundled third-party TTS

Vocabulary App v1.0 does not bundle, download, install, or redistribute any
third-party TTS runtime, model, or voice package. Speech playback uses the
**Local Windows Speech Provider** capability: it calls the Windows-provided
speech synthesis API (WinRT `SpeechSynthesizer` / SAPI5, per
`src/tts_providers.py`) against whatever compatible voice the user's own
Windows installation already has installed (e.g. the built-in Yaoyao
Mandarin voice). No Microsoft or third-party voice/model asset is ever
possessed, bundled, or redistributed by this project.

Kokoro, sherpa-onnx, and Piper voices were evaluated as TTS runtimes during
earlier development (see `docs/policies/TTS_LICENSE_AND_ATTRIBUTION.md` for
that historical record) but are **not distributed in v1.0** and carry no
live redistribution obligation for this release.

## Bundled Python runtime libraries

| Component | License | Role in this distribution |
|---|---|---|
| Python (CPython) | PSF License | Interpreter frozen into the PyInstaller build. |
| PySide6 / PySide6-Essentials / PySide6-Addons | LGPL-3.0-only (or GPL-2.0/3.0) | Desktop UI toolkit (Qt for Python) — the application window, widgets, and styling. |
| shiboken6 | LGPL-3.0-only (or GPL-2.0/3.0) | PySide6's binding-generator runtime support library. |
| openpyxl | MIT | Reads/writes `.xlsx` for import, export, and backup-workbook features. |
| et_xmlfile | MIT | openpyxl's XML-writing dependency. |

PySide6/shiboken6 are used here under the LGPL-3.0 option: the application
links against unmodified upstream Qt for Python binaries and does not
statically link Qt in a way that would prevent a user from relinking against
a replacement LGPL-compatible build. Upstream license and copyright files for
each bundled package (as installed in the release build environment) must be
included alongside the installer output before public release.

Vocabulary App itself does not bundle Streamlit, pandas, numpy, or any other
dependency that only the separate `app.py` Streamlit compatibility UI uses —
those are development/alternate-UI dependencies (`requirements.txt`), not
part of the packaged desktop executable, and must not appear in the frozen
build's collected-module report.

## Packaging gate

Before each public release: regenerate this table from the exact build
environment's installed packages, attach each listed package's upstream
`LICENSE`/`NOTICE` text verbatim, and confirm PyInstaller's build report does
not include Kokoro/sherpa-onnx/Piper assets, a bundled TTS Python runtime, or
the Streamlit runtime.
