# Milestone 20 Release Contract — Phase A: Contract and Packaging Decision Audit

Baseline: `main` at `f615ab79b4266810fd6a88937f1917c473607136` (M19 fully
merged, PR #30 + PR #31).

Phase A is release-engineering analysis and contract definition, not
implementation. No installer was built, no packaging code was written, and
no product/runtime behavior changed as part of this phase. The only
artifacts produced are this document and the doc-truthfulness reconciliation
recorded in [§ Deferred / Future Distribution Work](#deferred--future-distribution-work)
and the "Doc reconciliation performed in Phase A" note at the end of this
file.

**Revision note:** this document was revised once, before being considered
frozen, after operator review of the first draft. The revision (1)
corrected an inaccurate LGPL-incompatibility claim against PyInstaller
`--onefile` (§ 2.4, § 2.5), (2) replaced the fresh-local-user-account
recommendation as the clean-machine verification method with a clean
VirtualBox VM, demoting the fresh-user account to a per-user-install-path
check only (§ 2.8), (3) reframed the measured ~1.46 GB TTS dev-environment
figure as an upper-bound observation rather than the distribution
manifest, and froze the payload target at approximately 1–1.5 GB pending a
Phase B minimum-manifest derivation (§ 1, § 2.3, OB-2), and (4) finalized
and resolved OB-3 with the operator's chosen MIT copyright-holder line
without editing the repository `LICENSE` file itself in Phase A (§ 1, § 3
decision 8, § 4).

---

## 1. Frozen Operator Decisions

Recorded verbatim from the Phase A instruction so later milestones do not
relitigate them. These are not open for reinterpretation inside M20; a
change requires an explicit new operator decision.

- **Platform:** Windows 10/11 x64 only.
- **Install model:** per-user installation; conventional installer only (no
  portable/zip-only distribution as the primary path).
- **Data separation:** standard Windows per-user application-data storage,
  separated from the application binaries.
- **Existing-database import:** an explicit, user-selected copy-with-backup
  path (never a silent in-place migration of a file the user points at).
- **Uninstall:** preserves user data by default; may offer an explicit,
  unchecked "also delete all local user data" option.
- **Updates:** no automatic updater in v1.0.
- **Rollback:** manual only, via upgrade backups and reinstalling an earlier
  version.
- **Distribution channel:** GitHub Releases only.
- **License:** MIT for the project. **Copyright-holder line finalized
  after initial Phase A review:** `Copyright (c) 2026 Yunsong Shi (Peter
  Shi)` — the exact text this resolves into is recorded in § 3 decision 8;
  see the note at the end of § 4 OB-3 for why the repository `LICENSE`
  file itself is not edited in Phase A.
- **No telemetry, no accounts, no cloud dependency.**
- **Shortcuts:** Start Menu entry required; Desktop shortcut
  optional/default-enabled.
- **Versioning/gate:** `v1.0.0-rc.1` → Human RC Acceptance → `v1.0.0`; one
  concentrated final Human RC Gate (not per-milestone gates).
- **TTS provisioning (product-level, frozen):** the base installer does not
  bundle the full TTS runtime. The application installs and remains fully
  usable without it. On first need for Audio Export, the product guides
  acquisition of the required English/French/Mandarin TTS
  runtime/models/voices. No silent provider/model/license substitution.
  This behavior must be documented in the public README.
  **Payload target (revised after initial Phase A review, superseding the
  original "roughly the 1 GB class" phrasing):** frozen at approximately
  **1–1.5 GB** for the optional TTS payload. Phase B must derive and
  verify the actual minimum-required manifest (exactly which files a clean
  install of the English/French/Mandarin runtime needs — see § 2.3) before
  a final payload size is accepted; the measured ~1.46 GB developer
  environment (§ 2.3) is an upper-bound observation of an unpruned dev
  venv, not itself the distribution manifest.

---

## 2. Evidence / Findings

### 2.1 Application shape as it exists today

- Desktop entry point: `python -m src.ui_desktop`
  (`src/ui_desktop/app.py::build_application`), builds a `QApplication`,
  loads the icon from `assets/icons/vocabulary_app.ico`, initializes the
  database, applies theme preferences, and runs `MainWindow`.
- `app.py` at the repo root is the **separate, still-present Streamlit
  compatibility UI** (`streamlit>=1.35`), not the desktop product. It has
  its own dependency set in `requirements.txt` and is out of scope for the
  M20 installer — the desktop path is `requirements.txt` (core, framework-
  independent) + `requirements-desktop.txt` (`PySide6>=6.11,<7`).
- `src/app_config.py` already defines `APP_NAME = "Vocabulary App"`,
  `APP_SLUG = "vocabulary_app"`, `APP_VERSION = "0.11.3"` — the version
  constant is a pre-release dev value and does not yet reflect the frozen
  `v1.0.0-rc.1` scheme.
- No build script, `.spec` file, or installer script exists anywhere in the
  repository today (`find` for `*.spec`, `*.iss`, `build*.ps1`, `build*.py`
  returned nothing). Phase A starts from zero packaging tooling.

### 2.2 Current application-data path behavior (critical finding)

`src/app_config.py` shows **inconsistent** path conventions already in the
codebase:

| Path | Current default | Correct per frozen decision? |
|---|---|---|
| `get_default_db_path()` | `<project_root>/data/vocab.db` | **No** — resolves inside the application/source tree |
| `get_backup_dir()` | `<project_root>/backups` | **No** — same problem |
| `get_audio_cache_dir()` | `%LOCALAPPDATA%\vocabulary_app\audio-cache` (falls back to `~/.cache`) | Yes — already correct |
| `get_app_preferences_path()` | `%LOCALAPPDATA%\vocabulary_app\preferences.json` (XDG fallback) | Yes — already correct |

All four already support an environment-variable override
(`VOCAB_APP_DB_PATH`, `VOCAB_APP_AUDIO_CACHE_DIR`,
`VOCAB_APP_PREFERENCES_PATH`) and `get_backup_dir()` does not even have one.
The audio-cache and preferences paths already establish the exact pattern
(`%LOCALAPPDATA%\vocabulary_app\...`, override env var first) that the
database and backups paths need to follow. **This is real code, not a
symmetric convention yet — closing this gap is packaging-code work, which
is explicitly Phase B, not Phase A.** It is recorded here as the single
most important Open Blocker (§ 4) because it directly contradicts the
frozen "data separated from application binaries" decision as installed
(under a per-user install root, `project_root` would resolve inside the
install directory, and a `data/` folder would sit next to the executable —
not in `%LOCALAPPDATA%`).

### 2.3 Actual TTS payload composition (measured, not estimated)

The developer's real shared TTS runtime folder (`F:\AI-TTS`, referenced by
`VOCAB_APP_SHARED_TTS_DIR` and documented in
`docs/history/M15_0_TTS_PROVIDER_SELECTION_CLOSURE.md`) was measured
directly:

| Component | Size | Notes |
|---|---|---|
| `venv\` (Python 3.11 + `kokoro`, `sherpa-onnx`, `torch` CPU, `transformers`, `spacy`, etc.) | **1,106.2 MB** | `torch` alone is 493.9 MB (already the CPU-only wheel, not CUDA); `transformers` 98 MB, `spacy` 92.6 MB |
| `sherpa-onnx\voices\vits-piper-fr_FR-siwis-medium\` | 77.4 MB | ONNX model + tokens + bundled `espeak-ng-data` |
| `kokoro\` (adapter script only) | ~0 MB | model weights are **not** stored here |
| Kokoro-82M weights (`~/.cache/huggingface/hub/models--hexgrad--Kokoro-82M`) | **313.6 MB** | Auto-downloaded on first use to the standard Hugging Face cache — a *separate* location from the shared TTS folder, shared machine-wide |
| Windows Yaoyao (Mandarin) | 0 MB | OS-provided, never bundled/copied |
| **Total real footprint if fully provisioned** | **≈ 1,497 MB (≈ 1.46 GB)** | Sum of the four rows above |

**Finding: this ~1.46 GB figure is a measurement of the developer's
existing, unpruned dev `venv` — an upper-bound observation, not a
distribution payload manifest.** It falls inside the revised frozen target
of approximately 1–1.5 GB (§ 1), but it was never built as a minimal
install manifest: it includes whatever `pip install kokoro sherpa-onnx
soundfile numpy` pulled in for general development use, not a
deliberately-pruned "exactly what the shipped downloader needs" set. The
size is driven almost entirely by the `venv` (mainly `torch`,
`transformers`, `spacy` — Kokoro's actual runtime dependency chain, not
padding this project added). Phase B must derive the actual minimum
manifest in a clean directory (a fresh venv with only the packages the
shipped `kokoro`/`sherpa-onnx` adapters import at runtime, dependency-
resolved from scratch rather than copied from this dev environment) and
verify its real size before the final payload size is accepted — it may
turn out smaller than 1.46 GB once dev-only extras are excluded, or it may
confirm close to this figure; either is acceptable within the 1–1.5 GB
frozen target. No provider/model substitution is implied — the same
already-selected, license-cleared, frozen (M15.0) `kokoro`/`sherpa-onnx`
runtime is what gets a minimal manifest, not a different one. See § 4 Open
Blockers.

Distribution/redistribution rights: `venv` site-packages (Apache-2.0/BSD/MIT
per-package, no GPL packages present in this dependency chain), the
sherpa-onnx voice archive (Apache-2.0 runtime, MIT `piper-voices` packaging,
CC BY 4.0 SIWIS dataset), and Kokoro weights (Apache-2.0, CC BY 3.0/4.0
training-source attribution) are all redistribution-permissive per
`docs/policies/TTS_LICENSE_AND_ATTRIBUTION.md`. Nothing here blocks
redistribution; it only affects payload size and download UX.

### 2.4 Dependency license audit (project MIT vs. bundled/distributed code)

| Dependency | License | Distribution | MIT-compatibility note |
|---|---|---|---|
| `PySide6` (Qt for Python) | **LGPL-3.0** (Qt itself) + PySide's own LGPL wrapper terms | Bundled (dynamically linked) | LGPL-3.0 permits proprietary/MIT-licensed application code as long as Qt is **dynamically linked** (not statically) and the end user retains the ability to relink/replace the LGPL components. PyInstaller's Qt DLLs remain separate files at runtime in *both* `--onedir` and `--onefile` mode — `--onefile` self-extracts those same separate DLL files to a temp directory before launch rather than statically embedding them into a single binary, so it is not itself LGPL-incompatible. `--onedir` is nonetheless the selected mode; see § 2.5 for the release-engineering reasoning (not an LGPL requirement). |
| `openpyxl` | MIT | Bundled | Compatible |
| `streamlit` | Apache-2.0 | **Not distributed** in the desktop build (compatibility UI only, separate `requirements.txt`) | N/A to desktop installer |
| `kokoro` runtime + Kokoro-82M weights | Apache-2.0 | Optional/downloaded, not in base installer | Compatible; Apache-2.0 NOTICE obligations apply to the optional TTS payload, not the base app |
| `torch` (CPU), `transformers`, `spacy`, `numpy`, `onnxruntime`, `sherpa-onnx` | BSD-3-Clause / Apache-2.0 / BSD (per-package) | Optional/downloaded | Compatible |
| `piper-voices` (fr_FR-siwis-medium packaging) | MIT | Optional/downloaded | Compatible |
| SIWIS training dataset attribution | CC BY 3.0/4.0 (Koniwa, SIWIS) | Attribution notice only, not code | Not a code license; satisfied by notice text, already drafted in `THIRD_PARTY_NOTICES.md` |
| Windows Yaoyao voice | N/A — OS API only, no asset possessed | Not distributed | No obligation (confirmed in `TTS_LICENSE_AND_ATTRIBUTION.md`) |
| PyInstaller (build-time only, not distributed in output in a way that imposes license terms on it) | GPL-2.0-with-bootloader-exception | Build tool only | The bootloader exception explicitly permits distributing PyInstaller-built binaries under any license, including MIT; PyInstaller's own GPL license does not propagate to the packaged app |

**No GPL code is present in the base application or the frozen TTS
dependency chain.** The one LGPL component (Qt/PySide6) is compatible with
an MIT project **conditional on dynamic linking**, which is the default and
recommended PyInstaller mode anyway (`--onedir`), not a special
accommodation.

`LICENSE` currently reads "License decision pending" — it has **not yet
been updated** to reflect the frozen MIT decision. The copyright-holder
attribution line is now finalized (`Copyright (c) 2026 Yunsong Shi (Peter
Shi)`, § 1) and the exact replacement text is recorded in § 3 decision 8
for Phase B to apply — the repository `LICENSE` file itself is intentionally
left unchanged in Phase A (see § 4 OB-3), since Phase A's own instruction
scopes it to contract/analysis documentation, not product or repository-
metadata edits.

### 2.5 Windows bundler and installer stack

Evaluated for the current PySide6 (Qt6) + stdlib `sqlite3` architecture,
no other native extensions:

| Option | Verdict | Reasoning |
|---|---|---|
| **PyInstaller, `--onedir` mode** | **Recommended (selected)** | Both `--onedir` and `--onefile` are LGPL-compliant (§ 2.4) — `--onedir` is chosen on release-engineering merits, not license necessity: Qt DLLs and dependencies sit as a plain, inspectable directory tree (auditability — straightforward to verify what actually shipped against `THIRD_PARTY_NOTICES.md`, and to attach per-file notices where a license requires them); predictable, consistent startup time on every launch (no self-extraction step); more diagnosable failures (a missing/corrupt DLL is a visible file-not-found in a known directory, not a failure inside a temp self-extraction step); and Inno Setup can enumerate and install the directory tree directly, which keeps the installer script simple. |
| PyInstaller, `--onefile` mode | Not selected for v1, not an LGPL problem | LGPL-compliant (§ 2.4) — not excluded on license grounds. Not selected because it self-extracts to a temp directory on every launch (slower, less predictable cold start), has a materially higher antivirus false-positive rate for single-file self-extracting executables (a real SmartScreen/AV friction concern for an unsigned app, § 2.7), and is harder to audit/diagnose than a plain `--onedir` tree. Worth reconsidering only if a single-file artifact becomes a hard distribution requirement later. |
| Nuitka | Viable alternative, not selected for v1 | Compiles to C, can produce a faster-starting binary and sometimes better AV reputation than PyInstaller, but has a steeper build-configuration learning curve for PySide6 plugin/resource discovery and a smaller "known-good desktop app" track record in this project's toolchain. Worth reconsidering post-v1.0 if PyInstaller AV false-positive rate proves to be a real support burden. |
| cx_Freeze | Not selected | Smaller community, weaker current PySide6/Qt6 plugin-path handling track record than PyInstaller. |
| Briefcase (BeeWare) | Not selected | Targets a broader cross-platform packaging abstraction the frozen decision doesn't need (Windows-only v1); adds an extra abstraction layer over PyInstaller/other backends without a corresponding benefit here. |

Installer wrapper (turns the PyInstaller `--onedir` output into a
conventional installed Windows app):

| Option | Verdict | Reasoning |
|---|---|---|
| **Inno Setup** | **Recommended** | Free, scriptable (`.iss`), the most common companion to PyInstaller in the Python desktop-packaging community, natively supports per-user install mode (`PrivilegesRequiredOverridesAllowed`/`PrivilegesRequired=lowest`), Start Menu + optional Desktop shortcut checkboxes out of the box, built-in uninstaller generation, and straightforward custom pages for the "also delete local user data" opt-in checkbox the frozen decision requires. |
| WiX Toolset (MSI) | Not selected for v1 | More powerful for enterprise/MSI-based deployment (Group Policy, SCCM) than this per-user, GitHub-Releases-only product needs; steeper XML-based authoring; MSI's per-machine-oriented conventions fight the per-user-only frozen decision more than Inno Setup's do. |
| NSIS | Viable alternative, not selected | Comparable capability to Inno Setup; Inno Setup's Pascal-scripting model and documentation are a better fit for this project's existing all-Python/PowerShell tooling conventions and the one engineer maintaining it. |
| MSIX (Windows App Package) | Not selected for v1 | Requires either a trusted code-signing certificate or enabling Developer Mode/sideloading on the end-user machine for an unsigned package — directly conflicts with "no code-signing purchase" and would push installation friction onto exactly the non-technical users the desktop product targets. Worth reconsidering only if code-signing is purchased later (§ 2.7). |

### 2.6 Application-data layout, migration, backup, uninstall, rollback

Recommended production layout (Windows per-user, matching the pattern
`get_audio_cache_dir()`/`get_app_preferences_path()` already establish):

```text
Application binaries (read-only, replaced wholesale on upgrade/uninstall):
  %LOCALAPPDATA%\Programs\Vocabulary App\   (Inno Setup per-user default install root)

Per-user application data (never touched by the installer/uninstaller
except the explicit opt-in "delete all local data" path):
  %LOCALAPPDATA%\vocabulary_app\
    |-- vocab.db                  (moved from <project_root>/data/vocab.db)
    |-- preferences.json          (already here today — unchanged)
    |-- audio-cache\              (already here today — unchanged)
    `-- backups\                  (moved from <project_root>/backups)
```

This requires the § 2.2 code gap (DB and backup paths) to be closed in
Phase B before packaging — it is a precondition for a correct installer,
not a packaging-tool detail.

- **Existing-database import (frozen: explicit, user-selected,
  copy-with-backup):** first-run (or Settings → Data) flow lets the user
  pick an existing `vocab.db` via a native file dialog; the app copies it
  into `%LOCALAPPDATA%\vocabulary_app\vocab.db`, first writing a
  timestamped backup of anything already at the destination if non-empty.
  The source file the user pointed at is never modified or deleted.
- **Backup-before-upgrade:** on first launch after a version bump (compare
  `APP_VERSION` against a stored last-run version, or a schema/migration
  version if one exists), copy the current `vocab.db` to
  `backups\vocab-pre-<old_version>-<timestamp>.db` before any migration
  runs.
- **Uninstall (frozen: preserves data by default):** the Inno Setup
  uninstaller removes only the install directory
  (`%LOCALAPPDATA%\Programs\Vocabulary App\`); `%LOCALAPPDATA%\vocabulary_app\`
  is left untouched unless the user checked the explicit, unchecked-by-
  default "also delete all local user data" box on an uninstall custom
  page.
- **Rollback (frozen: manual, via reinstall):** document the rollback
  procedure as: (1) download the prior version's installer from GitHub
  Releases, (2) install over/alongside, (3) if the new version's schema
  migration is incompatible with the old code, restore the relevant
  `backups\vocab-pre-*.db` file over `vocab.db` before launching the old
  version. No in-app rollback tooling is required for v1.0.

### 2.7 Code-signing and SmartScreen

- An unsigned PyInstaller/Inno Setup executable **will** trigger Windows
  SmartScreen's "Windows protected your PC" interstitial on first run for
  most users, and has a non-trivial chance of a false-positive AV flag
  (materially higher for `--onefile` builds than `--onedir`, reinforcing
  the § 2.5 choice).
- **Cost/benefit without purchasing anything:**
  - A standard OV (Organization Validation) code-signing certificate
    typically runs on the order of $100–400/year from a commercial CA and
    still does not eliminate SmartScreen warnings immediately — Microsoft's
    SmartScreen reputation is *earned* per-certificate via accumulated
    clean download/execution telemetry, so even a freshly purchased OV
    cert shows warnings for a period.
  - An EV (Extended Validation) certificate does grant instant SmartScreen
    reputation but costs substantially more (roughly $300–700+/year) and
    typically requires a hardware token / stricter identity verification.
  - Neither is purchased in Phase A or required for v1.0 per the frozen
    decision set (no explicit code-signing budget was frozen as a
    decision).
- **Recommended mitigation without signing:** (1) publish SHA-256 checksums
  for every release asset directly in the GitHub Release notes so users can
  verify integrity independently of SmartScreen; (2) document the expected
  SmartScreen warning and the "More info → Run anyway" path in the README
  install instructions, framed honestly (unsigned open-source software,
  verify the checksum) rather than instructing users to just click through
  blindly; (3) revisit paid code-signing only if/when SmartScreen friction
  is shown to be a real adoption blocker post-release — deferred, not
  decided now.

### 2.8 Clean-machine verification strategy (this actual dev environment)

Measured directly on this machine:

- `Get-ComputerInfo` reports `WindowsEditionId: Core`,
  `WindowsProductName: Windows 10 Home` (build reports as Windows 11 Home,
  `WindowsVersion 2009` — Home edition, confirmed independently in the
  environment's own system info as Windows 11 Home 10.0.26200).
- `dism /online /get-featureinfo /featurename:Containers-DisposableClientVM`
  (Windows Sandbox) and `.../featurename:Microsoft-Hyper-V-All` both
  returned error 740 (elevation required) when probed non-elevated: this is
  **not conclusive by itself**, but combined with the confirmed Home
  edition it is decisive — **Windows Sandbox and Hyper-V are Pro/
  Enterprise/Education-only features and are architecturally unavailable on
  Windows Home regardless of elevation.** No amount of local admin rights
  unlocks them on this SKU.

**Two distinct tests, not one, with the fresh-user account demoted to a
narrower role than originally proposed:**

- **Fresh local Windows user account (this same physical machine) —
  per-user installation test, not clean-machine verification.** A
  dedicated new local account with no Python, `git`, or dev tooling, and a
  fresh `%LOCALAPPDATA%`, is genuinely useful for exercising the per-user
  install path itself (Start Menu entry, per-user registry/shortcut
  behavior, `%LOCALAPPDATA%\vocabulary_app\` creation, no admin-elevation
  prompt) and for downloading the installer through a browser under that
  account to pick up Windows' real mark-of-the-web SmartScreen path. It
  shares this machine's kernel, drivers, globally-installed runtimes (e.g.
  a Visual C++ redistributable already present from other software), and
  any machine-wide state — so a pass here does not demonstrate the
  installer succeeds on a machine that does not already happen to have
  whatever this dev machine has accumulated. It is retained in the RC
  Verification Contract (§ 5) as the per-user-install-path check, not as
  the clean-machine check.
- **Clean Windows VM — the actual M20 clean-machine verification path.**
  Since this machine is confirmed Windows 11 Home (evidence above),
  Hyper-V and Windows Sandbox are unavailable regardless of elevation, so
  the recommended no-cost method is a **Type-2 hypervisor VM**: install
  **VirtualBox** (free, no license cost, runs on Windows Home as the host)
  and provision it with an **official Microsoft Windows 10/11 evaluation
  ISO** (Microsoft's own free, time-limited evaluation media, not a
  third-party or pirated image — preserves the "no telemetry/no cost"
  spirit and keeps provenance clean for a project that itself cares about
  license/source authenticity). This gives a genuinely clean OS instance —
  no accumulated runtimes, no dev tooling, no prior `%LOCALAPPDATA%` state
  — and is the artifact the RC Verification Contract (§ 5) treats as
  authoritative for "clean-machine installation and launch succeed"
  (ROADMAP § 20 Exit Criteria). No repository or environment evidence
  found a better no-cost alternative: this machine has neither Hyper-V nor
  Windows Sandbox available (below), and no existing VM tooling,
  snapshot/image, or CI runner was found in the repository to reuse
  instead.

### 2.9 Stale pre-desktop/Streamlit packaging assumptions

`docs/packaging/PACKAGING_FEASIBILITY.md` (last authored during the
Streamlit-to-desktop transition, referenced from `PROJECT_STATUS.md`
history) is now superseded in the following specific ways:

- Its "Option A/B/C/D" framing treats the desktop GUI (its own "Option D")
  as a still-open future direction ("active product direction after the
  pre-desktop baseline"). Desktop is no longer a direction under
  consideration — it is the shipped product as of M16–M19, and Streamlit
  (`app.py`) is now the legacy compatibility UI, not a packaging candidate.
- Its § 5 "Packaging Risk Checklist" and § 6 "What Must Never Be Packaged"
  remain substantively correct and reusable — they were written generically
  enough to apply to the desktop build too — but are framed around
  Streamlit-executable-wrapper feasibility (its Option C), which is now
  moot: the product packages the PySide6 desktop app directly, not a
  Streamlit wrapper.
- Its "Decision" section correctly deferred final packaging to "Milestones
  19-20," which is now current — the document's own deferred trigger has
  arrived, so this M20_RELEASE_CONTRACT.md document (not
  PACKAGING_FEASIBILITY.md) is the current authority for M20 packaging
  decisions. `PACKAGING_FEASIBILITY.md` is retained as historical
  feasibility-analysis record, not deleted, but must no longer be read as
  current guidance.
- No other repository doc (`PROJECT_STATUS.md`, `ROADMAP.md`) was found to
  contain stale Streamlit-as-primary-UI packaging assumptions beyond this
  one file; both already correctly describe the desktop app as the shipped
  product and Streamlit as compatibility-only.

---

## 3. Selected Technical Decisions

These are Phase A's own conclusions (not operator-frozen), adopted for M20
Phase B implementation planning:

1. **Bundler:** PyInstaller, `--onedir` mode.
2. **Installer:** Inno Setup, per-user install mode
   (`PrivilegesRequiredOverridesAllowed=commandline`,
   `PrivilegesRequired=lowest`), Start Menu group created unconditionally,
   Desktop shortcut task checked by default and user-togglable.
3. **Application-data root:** `%LOCALAPPDATA%\vocabulary_app\` for
   `vocab.db`, `backups\`, `preferences.json`, `audio-cache\` — extending
   the pattern already implemented for preferences/audio-cache to the
   database and backup paths (Phase B code change, tracked as Open Blocker
   OB-1 below, not done in Phase A).
4. **TTS payload:** ship the base installer with zero TTS runtime; first
   Audio Export use triggers an in-app guided download of a minimal
   English/French/Mandarin runtime manifest, target approximately 1–1.5 GB
   (§ 1), derived and measured fresh in Phase B rather than assumed equal
   to the ~1.46 GB dev-environment measurement (§ 2.3, OB-2), downloaded
   from the same upstream sources already selected and license-cleared at
   M15.0 (PyPI packages via `pip`, Hugging Face Hub for Kokoro weights, the
   existing `piper-voices` Hugging Face repo for the French voice) — not a
   new redistribution channel, not a re-hosted mirror, preserving "no
   silent provider/model/license substitution."
5. **Checksum/integrity:** publish SHA-256 for every GitHub Release
   installer asset in the release notes; the TTS first-run downloader
   verifies each downloaded package/model against its origin's own
   integrity mechanism (`pip`'s hash verification for PyPI wheels,
   Hugging Face Hub's built-in file hash verification) rather than
   inventing a separate checksum scheme.
6. **Code-signing:** none for v1.0; document the expected SmartScreen
   warning honestly in the README; revisit only if adoption data later
   justifies the cost.
7. **Clean-machine verification:** a fresh local Windows user account on
   the current dev machine is a per-user-installation-path check only, not
   clean-machine verification. The actual clean-machine verification path
   is a VirtualBox VM provisioned from an official Microsoft Windows
   10/11 evaluation ISO.
8. **License file:** finalized (operator decision, § 1) — Phase B replaces
   the current `LICENSE` contents verbatim with:

   ```text
   MIT License

   Copyright (c) 2026 Yunsong Shi (Peter Shi)

   Permission is hereby granted, free of charge, to any person obtaining a
   copy of this software and associated documentation files (the
   "Software"), to deal in the Software without restriction, including
   without limitation the rights to use, copy, modify, merge, publish,
   distribute, sublicense, and/or sell copies of the Software, and to
   permit persons to whom the Software is furnished to do so, subject to
   the following conditions:

   The above copyright notice and this permission notice shall be included
   in all copies or substantial portions of the Software.

   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
   OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
   MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
   IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
   CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
   TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
   SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
   ```

   This is the standard, unmodified MIT License template (OSI-published
   text) with only the copyright line filled in — not done in Phase A
   (§ 4 OB-3), staged here so Phase B has no remaining decision to make.

---

## 4. Open Blockers

Ranked by what actually blocks Phase B start:

- **OB-1 (blocks Phase B packaging work directly):** `get_default_db_path()`
  and `get_backup_dir()` in `src/app_config.py` still default inside the
  project/install tree, not `%LOCALAPPDATA%\vocabulary_app\`. This is a
  small, well-scoped code change (mirror the existing
  `get_audio_cache_dir()`/`get_app_preferences_path()` pattern, plus a
  first-run copy-with-backup migration for anyone with an existing
  `data/vocab.db`) but it is genuine product-behavior code, out of Phase A
  scope by the operator's own instruction. Must be the first Phase B item.
- **OB-2 (minimum TTS manifest not yet derived — blocks final payload-size
  acceptance, not Phase B start):** the frozen payload target is now
  approximately 1–1.5 GB (§ 1), and the measured ~1.46 GB dev `venv`
  (§ 2.3) is an upper-bound observation that fits inside that range, but
  it is not yet the actual minimum-required manifest. Phase B must build a
  clean-directory install of exactly what the shipped English/French/
  Mandarin downloader needs (dependency-resolved from scratch, not copied
  from the dev `venv`), measure its real size, and confirm it lands
  inside 1–1.5 GB before the payload size is treated as final. No
  provider/model/license substitution is proposed or implied — this is
  manifest minimization of the already-selected, license-cleared, frozen
  (M15.0) `kokoro`/`sherpa-onnx` runtime, not a different runtime.
- **OB-3 — RESOLVED (was: LICENSE file still says "pending"):** the
  operator finalized the copyright-holder attribution line as
  `Copyright (c) 2026 Yunsong Shi (Peter Shi)`. The exact replacement
  `LICENSE` text is staged in § 3 decision 8. **The repository `LICENSE`
  file is deliberately not edited in Phase A** — Phase A's own instruction
  scopes this phase to contract/analysis documentation (this file, plus
  reconciling `PROJECT_STATUS.md`/`ROADMAP.md` "only as needed to
  establish Phase A truthfulness"), and a `LICENSE` file replacement is a
  repository-metadata/product-facing change, not a Phase A documentation
  update — so it remains queued as the first trivial Phase B action
  instead of being applied here. No remaining operator input is needed;
  this blocker no longer blocks anything.
- **OB-4 (version scheme not yet wired):** `APP_VERSION = "0.11.3"` in
  `src/app_config.py` needs a concrete plan for when/how it becomes
  `1.0.0-rc.1` and then `1.0.0` (single constant update per release, tagged
  to match) — mechanically simple, just not yet decided as a checklist
  item anywhere. Recorded here so Phase B RC tagging doesn't improvise it.
- **OB-5 (no automated build reproducibility check yet):** no CI or local
  script currently proves the PyInstaller build is reproducible across
  runs; Phase B should add a documented, scripted build command (not
  necessarily CI) before RC verification (ROADMAP § 20.3) can credibly
  claim "reproducible packaging succeeds."

None of these blockers required a Phase A code change to document; all are
scoped for Phase B.

---

## 5. RC Verification Contract

Restates and makes concrete ROADMAP § 20.3's checklist for this specific
product, to be executed once as the single concentrated Final Human RC Gate
(frozen decision — not per-milestone gates):

1. **Final automated regression:** full existing repository test suite
   green on the RC build commit.
2. **Final manual smoke testing:** exercise Today, Entries, Review, Quiz,
   Statistics, Import/Export, Settings/Audio in the packaged (not
   `python -m src.ui_desktop`) executable.
3. **Clean-database testing:** run twice — once on the fresh local user
   account (per-user-install-path check) and once inside the clean
   VirtualBox VM (§ 2.8, the authoritative clean-machine check) — no
   existing `vocab.db` reachable in either, confirm the app creates
   `%LOCALAPPDATA%\vocabulary_app\vocab.db` correctly and all core flows
   work with zero data in both.
4. **Representative existing-database testing:** copy a real (sanitized)
   `vocab.db` in through the explicit copy-with-backup import flow;
   confirm the original source file is untouched and a backup was written.
5. **Installer/uninstaller testing:** install, confirm Start Menu entry and
   default-enabled Desktop shortcut, confirm per-user install path;
   uninstall with the data-preserving default and confirm
   `%LOCALAPPDATA%\vocabulary_app\` survives; separately test the explicit
   "also delete local data" opt-in and confirm it removes that directory.
6. **Update/migration testing:** install an older build, run it to create
   data, install the RC over it, confirm the pre-upgrade backup was written
   to `backups\` and the app still opens the migrated data correctly.
7. **Privacy and secret scan:** confirm the release archive contains no
   `.env`, no personal `data/vocab.db`, no personal backups/exports, no API
   keys — per `PACKAGING_FEASIBILITY.md` § 6, still binding.
8. **Release-archive inspection:** unpack the actual built installer and
   manually confirm its file manifest matches expectations (no accidental
   inclusion of `.venv`, test fixtures, or the developer's `F:\AI-TTS`
   path).
9. **Documentation reconciliation:** README install instructions, the TTS
   first-run guidance text, `THIRD_PARTY_NOTICES.md`, and `LICENSE` all
   match the shipped RC build before tagging.

Any failure returns the project to the relevant M20 hardening work and
requires the affected regression to be repeated in full, per ROADMAP § 20.3
— Phase A does not weaken that rule.

---

## 6. Deferred / Future Distribution Work

Explicitly out of scope for v1.0 per the frozen decisions, recorded so
later milestones don't silently reopen them without an operator decision:

- Automatic update checking/installation.
- macOS/Linux packaging.
- Paid code-signing (OV or EV certificate).
- MSIX/Microsoft Store distribution.
- Any distribution channel other than GitHub Releases.
- Bundling the TTS runtime inside the base installer.
- In-app rollback tooling beyond "restore a backup file manually."
- CI-automated release builds (Phase B may add a local reproducible build
  script per OB-5; a full CI pipeline is not required for v1.0 and is not
  addressed by this contract).

---

## Doc reconciliation performed in Phase A

`PROJECT_STATUS.md` and `ROADMAP.md` were reviewed against this document's
findings and required **no changes** — both already correctly describe M19
as complete/merged and M20 (Packaging and Release Candidate) as the current
milestone, and neither contains a stale Streamlit-as-primary-UI packaging
assumption. The only stale-assumption doc found was
`docs/packaging/PACKAGING_FEASIBILITY.md`, addressed by superseding it in
substance here (§ 2.9) rather than editing it in place, since it remains a
legitimate historical record of the Streamlit-to-desktop transition
reasoning and this new document is now the current authority for M20
packaging decisions per ROADMAP § 20.
