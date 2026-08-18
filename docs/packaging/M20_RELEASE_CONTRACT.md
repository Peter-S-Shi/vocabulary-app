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

**Revision note:** this document was revised three times. The first two
revisions were operator-reviewed corrections to Phase A's own drafting
(inaccuracies, missing detail, un-frozen items) before the contract was
considered frozen. The **third revision is different in kind: it is an
operator decision amendment**, changing two decisions the operator had
previously made, not correcting a Phase A mistake.

*First revision* (1) corrected an inaccurate LGPL-incompatibility claim
against PyInstaller `--onefile` (§ 2.4, § 2.5), (2) replaced the
fresh-local-user-account recommendation as the clean-machine verification
method with a clean VirtualBox VM, demoting the fresh-user account to a
per-user-install-path check only (§ 2.8), (3) reframed the measured
~1.46 GB TTS dev-environment figure as an upper-bound observation rather
than the distribution manifest, and froze the payload target at
approximately 1–1.5 GB pending a Phase B minimum-manifest derivation (§ 1,
§ 2.3, OB-2), and (4) finalized and resolved OB-3 with the operator's
chosen MIT copyright-holder line without editing the repository `LICENSE`
file itself in Phase A (§ 1, § 3 decision 8, § 4).

*Second revision* (1) removed `PrivilegesRequiredOverridesAllowed` from
the Inno Setup decision — that directive's `/ALLUSERS` escape hatch would
have permitted administrative install mode, contradicting the frozen
per-user-only decision (§ 2.5, § 3 decision 2), (2) corrected § 2.7's
claim that EV certificates grant instant SmartScreen reputation (Microsoft
retired that carve-out), added Azure Artifact Signing (≈US$9.99/month
Basic, no hardware token) as the current Microsoft-recommended low-cost
option, and un-froze the sign/unsigned choice as a later M20 decision
rather than settling on "unsigned" now (§ 2.7, § 3 decision 6, § 6),
(3) identified that the frozen TTS provider contract requires a private
`venv\Scripts\python.exe`-shaped interpreter a clean end-user machine does
not have, replaced the "download via `pip`" framing with two named
self-contained architectures built around a portable/embeddable Python
runtime rather than a copied ordinary `venv` (an ordinary `venv` is not
itself a portable/relocatable artifact — § 2.3), and strengthened the
integrity contract to require pinned versions/revisions and a
project-authored trusted-hash manifest rather than relying on `pip`/
Hugging Face Hub default verification alone (§ 2.3, § 3 decisions 4–5,
OB-2), and (4) froze only the required uninstall behavior (explicit,
unchecked destructive-data opt-in through a supported Inno Setup
uninstall-time code path) without naming a specific implementation
mechanism, leaving that entirely to Phase B (§ 2.5, § 2.6).

*Third revision (operator decision amendment, supersedes prior content
rather than correcting it)* (1) **superseded the entire third-party TTS
provisioning decision** from the first and second revisions (the
1–1.5 GB optional payload target; the portable/embeddable-Python runtime-
pack and self-bootstrapping-downloader architectures; the pinned-version/
trusted-hash provisioning manifest requirement; OB-2 as previously
written) with a **Local Windows Speech Provider / Installed Voice
Binding** model — v1.0 does not bundle, download, or redistribute any
third-party TTS runtime, model, or voice package at all; it binds to
speech voices the user has already installed on their own Windows system
(§ 1, § 2.3 — rewritten, § 3 decision 4, § 4 OB-2 — rewritten). The
earlier Kokoro/sherpa-onnx engineering investigation is retained in § 2.3
only as historical/internal context, not as the v1.0 distribution
contract, and Feature Freeze is preserved — this amendment authorizes no
new product-language support during M20, and the fact that additional
Windows voices are discoverable does not by itself expand v1.0 language
scope. (2) **changed code-signing from an open decision to a required RC
release step** — the v1.0 Release Candidate and public installer must now
go through a real, publicly trusted Authenticode signing workflow before
release, without claiming signing guarantees SmartScreen will never warn
(§ 1, § 2.7, § 3 decision 6). Exact signing provider/certificate/subject
details remain Phase B/RC scope. (3) the fresh-user-account-plus-clean-VM
clean-machine verification decision (§ 2.8) is explicitly **not**
reopened by this revision.

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
- **TTS distribution model (product-level, frozen — supersedes the
  original "acquire a third-party TTS runtime" decision, see the Third
  Revision note above and § 2.3):** for public v1.0 distribution,
  Vocabulary App does **not** bundle, download, install, or redistribute
  any third-party TTS runtime, model, or voice package (Kokoro,
  sherpa-onnx, Piper voices, a Python runtime for TTS purposes, or any
  other third-party TTS package) for end users. There is no optional TTS
  download payload, no payload-size target, and no TTS
  dependency/download/hash manifest for the M20 release pipeline to
  maintain. Instead, the application exposes a **Local Windows Speech
  Provider / Installed Voice Binding** capability: it inspects/enumerates
  compatible speech voices already installed on the user's own Windows
  system, lets the user explicitly choose and bind one for supported audio
  functionality, and persists that choice. It never silently installs or
  downloads a missing Windows voice; if no compatible local voice exists,
  the capability reports itself unavailable/requiring configuration rather
  than provisioning a third-party replacement. This must be documented
  accurately in the public README (§ 2.3): Vocabulary App does not bundle
  or redistribute third-party TTS models or voice packages, and audio
  availability depends on compatible speech voices already installed and
  licensed on the user's own device. This amendment does not authorize new
  product-language support during M20 (Feature Freeze, § 2.3) merely
  because additional installed Windows voices happen to be discoverable.
- **Windows code signing (product-level, frozen — supersedes the earlier
  "sign/unsigned left open" position, see the Third Revision note above
  and § 2.7):** the v1.0 Release Candidate and the public GitHub-
  distributed installer **must** go through a real, publicly trusted
  Windows Authenticode code-signing workflow before final public release.
  The purpose is a verifiable publisher identity, a credible Windows
  release-engineering workflow, and improved (not guaranteed) SmartScreen
  trust/reputation handling — signing does **not** guarantee SmartScreen
  will never warn or will auto-approve a newly released installer. Exact
  implementation (signing provider/service, certificate/account setup,
  the exact validated certificate subject/publisher name, and
  timestamping/signing command integration) remains Phase B/RC-packaging
  work, not decided here. The public portfolio/author identity may
  continue to use Peter Shi, but the Authenticode certificate subject
  must follow whatever identity the selected trusted signing provider
  actually validates — an unsupported certificate subject must not be
  hard-coded merely for branding consistency. SHA-256 publication/
  verification for release assets, signed-artifact verification as RC
  evidence, and the existing GitHub Releases distribution target are all
  preserved unchanged. A longer-term possibility of Microsoft Store
  distribution is not a current M20 exit criterion and this amendment
  does not expand M20 into Store/MSIX work.

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

### 2.3 TTS distribution model: Local Windows Speech Provider (v1.0)

**This section was substantively superseded by a Third Revision operator
decision amendment (see the revision note above) and no longer describes
what Phase B builds.** It is kept in one place — rewritten rather than
deleted — so the historical record of why the earlier plan changed stays
attached to the evidence that originally justified it.

**Current v1.0 decision.** Vocabulary App does not bundle, download,
install, or redistribute any third-party TTS runtime, model, or voice
package for end users — not Kokoro, not sherpa-onnx, not Piper voices,
not a Python runtime acquired for TTS purposes, and not any other
third-party TTS package. There is no optional TTS download payload, no
payload-size target, and no TTS dependency/download/hash manifest for the
M20 release pipeline to build or maintain. Instead the product exposes a
**Local Windows Speech Provider / Installed Voice Binding** capability:

- inspect/enumerate compatible speech voices already installed on the
  user's own Windows system;
- expose the available local voices to the user;
- let the user explicitly choose and bind an installed voice for
  supported audio functionality;
- persist that selection;
- invoke the voice through the local Windows speech API, the existing
  PowerShell-based Windows speech path, or a simpler equivalent native
  Windows mechanism if implementation evidence later supports one;
- **never** silently install or download a missing Windows voice — if no
  compatible local voice exists, report the capability
  unavailable/requiring configuration rather than provisioning a
  third-party replacement.

**Existing prior art to build from, not invent from scratch:**
`scripts/tts_yaoyao.ps1` and the `windows-winrt` provider spec in
`src/tts_providers.py` (`FROZEN_PROVIDER_SPECS["zh-CN"]`) already
implement exactly this pattern for Mandarin today — a PowerShell script
that calls the OS-provided `Windows.Media.SpeechSynthesis.SpeechSynthesizer`
WinRT API against whatever `zh-CN` voice (e.g. Yaoyao) the user's own
Windows installation already has, with an explicit no-silent-fallback
policy if that voice is absent. The Local Windows Speech Provider
capability generalizes that existing, already-working pattern — voice
enumeration and explicit user binding — across whatever compatible
Microsoft-signed voices a given Windows installation exposes, rather than
introducing a new mechanism. **Not decided here, left to Phase B:**
whether English/French coverage under this model uses the same WinRT
`SpeechSynthesizer` enumeration path, the older SAPI5 voice-enumeration
API, or another native Windows mechanism — Phase A found no repository
evidence pointing to one over the others for languages beyond the
existing Mandarin implementation, and manufacturing that evidence would
be new research beyond this amendment's scope.

**Feature Freeze is preserved.** This amendment authorizes no new
product-language support (Spanish, Japanese, Korean, or otherwise) during
M20. The binding mechanism may be architecturally extensible to
additional installed Windows voices in future versions, but v1.0
language/product scope must not expand merely because additional Windows
voices happen to be discoverable on a given machine.

**Public documentation requirement.** The README must accurately state,
in substance: Vocabulary App does not bundle or redistribute third-party
TTS models or voice packages; audio availability depends on compatible
speech voices already installed and licensed on the user's own Windows
device; the application may help the user select and bind a compatible
local Windows voice. No copyright claim broader than this evidence
supports should be made — the explicit goal of this amendment is that
Vocabulary App is not the distributor or provisioner of third-party TTS
runtimes and models.

---

**Historical/internal engineering context (superseded — not the v1.0
public distribution contract).** The M15.0 provider-selection work
selected and license-cleared Kokoro-82M/`af_heart` (English) and
sherpa-onnx/`fr_FR-siwis-medium` (French) as *engineering-evaluated*
providers, and the developer's real shared TTS runtime folder
(`F:\AI-TTS`, referenced by `VOCAB_APP_SHARED_TTS_DIR` and documented in
`docs/history/M15_0_TTS_PROVIDER_SELECTION_CLOSURE.md`) was measured
directly during Phase A's original drafting:

| Component | Size | Notes |
|---|---|---|
| `venv\` (Python 3.11 + `kokoro`, `sherpa-onnx`, `torch` CPU, `transformers`, `spacy`, etc.) | **1,106.2 MB** | `torch` alone is 493.9 MB (already the CPU-only wheel, not CUDA); `transformers` 98 MB, `spacy` 92.6 MB |
| `sherpa-onnx\voices\vits-piper-fr_FR-siwis-medium\` | 77.4 MB | ONNX model + tokens + bundled `espeak-ng-data` |
| `kokoro\` (adapter script only) | ~0 MB | model weights are **not** stored here |
| Kokoro-82M weights (`~/.cache/huggingface/hub/models--hexgrad--Kokoro-82M`) | **313.6 MB** | Auto-downloaded on first use to the standard Hugging Face cache — a *separate* location from the shared TTS folder, shared machine-wide |
| Windows Yaoyao (Mandarin) | 0 MB | OS-provided, never bundled/copied |
| **Total real footprint if fully provisioned** | **≈ 1,497 MB (≈ 1.46 GB)** | Sum of the four rows above |

This measurement, the payload-size analysis built on it, the two
self-contained provisioning-architecture alternatives Phase A designed
(a pre-built portable-Python runtime pack, and a self-bootstrapping
downloader), and the pinned-version/trusted-hash integrity-manifest
requirement drafted around them are **all superseded by the Third
Revision decision above and are not part of the v1.0 distribution
contract.** They remain here as the internal engineering record of what
was evaluated and why (including the earlier corrective finding that an
ordinary `python -m venv` is not a portable/relocatable redistribution
artifact — its `pyvenv.cfg` and launcher scripts carry absolute paths
back to the machine that built it), in case a future version revisits
bundled/downloaded third-party TTS provisioning.

**Two existing TTS license/notice documents need to be told apart here,
not treated the same way.** Both predate the Third Revision and both are
left unedited in Phase A (this amendment is documentation-consistency
only, not a license-file edit), but their staleness status differs:

- `docs/policies/TTS_LICENSE_AND_ATTRIBUTION.md` records the M15.0
  license *findings* for Kokoro (Apache-2.0 + CC BY training-source
  attribution) and sherpa-onnx/`piper-voices` (Apache-2.0 runtime, MIT
  packaging, CC BY 4.0 SIWIS dataset). As an evidentiary record of what
  was investigated and concluded at the time, it **may remain as
  historical/internal engineering evidence** without correction — it
  does not claim to be a current distribution-facing notice.
- `THIRD_PARTY_NOTICES.md`, by contrast, explicitly describes itself as
  "a distribution-facing summary" and still lists Kokoro/sherpa-onnx/
  Piper distribution obligations as if they apply to what the project
  ships. That framing is now **stale relative to the Local Windows
  Speech Provider decision** above: v1.0 does not distribute any of
  those assets, so a notice file that still presents their obligations
  as live distribution-facing content no longer accurately describes
  what v1.0 actually ships. **`THIRD_PARTY_NOTICES.md` is intentionally
  left untouched in Phase A** — editing it is Phase B/RC documentation
  work, not a Phase A contract-definition task — but it must not be read
  as already release-ready. **Phase B / RC documentation reconciliation
  (§ 5 item 10) must revise it before public release** so it lists and
  gives notice only for what the actual shipped v1.0 distribution
  requires, which under the current decision is none of the M15.0-
  evaluated TTS assets.

### 2.4 Dependency license audit (project MIT vs. bundled/distributed code)

| Dependency | License | Distribution | MIT-compatibility note |
|---|---|---|---|
| `PySide6` (Qt for Python) | **LGPL-3.0** (Qt itself) + PySide's own LGPL wrapper terms | Bundled (dynamically linked) | LGPL-3.0 permits proprietary/MIT-licensed application code as long as Qt is **dynamically linked** (not statically) and the end user retains the ability to relink/replace the LGPL components. PyInstaller's Qt DLLs remain separate files at runtime in *both* `--onedir` and `--onefile` mode — `--onefile` self-extracts those same separate DLL files to a temp directory before launch rather than statically embedding them into a single binary, so it is not itself LGPL-incompatible. `--onedir` is nonetheless the selected mode; see § 2.5 for the release-engineering reasoning (not an LGPL requirement). |
| `openpyxl` | MIT | Bundled | Compatible |
| `streamlit` | Apache-2.0 | **Not distributed** in the desktop build (compatibility UI only, separate `requirements.txt`) | N/A to desktop installer |
| `kokoro` runtime + Kokoro-82M weights | Apache-2.0 | **Not distributed in v1.0** — historical M15.0 engineering evaluation only (§ 2.3); v1.0 uses the Local Windows Speech Provider model instead | v1.0 incurs no *redistribution* obligation for this superseded asset (nothing is shipped); this does not certify that `THIRD_PARTY_NOTICES.md` is already reconciled to say so — see § 2.3's Phase B/RC note |
| `torch` (CPU), `transformers`, `spacy`, `numpy`, `onnxruntime`, `sherpa-onnx` | BSD-3-Clause / Apache-2.0 / BSD (per-package) | **Not distributed in v1.0** — same historical-only status as above (§ 2.3) | N/A to v1.0 |
| `piper-voices` (fr_FR-siwis-medium packaging) | MIT | **Not distributed in v1.0** — same historical-only status as above (§ 2.3) | N/A to v1.0 |
| SIWIS training dataset attribution | CC BY 3.0/4.0 (Koniwa, SIWIS) | **Not distributed in v1.0** — attribution obligation only arises if the underlying asset is distributed, and it is not (§ 2.3) | v1.0 incurs no redistribution/attribution obligation for this superseded asset; `docs/policies/TTS_LICENSE_AND_ATTRIBUTION.md` may stay as historical record as-is, but `THIRD_PARTY_NOTICES.md` still presents this as a live distribution-facing obligation and is stale until Phase B/RC revises it (§ 2.3) |
| Windows Yaoyao / other Local Windows Speech Provider voices | N/A — OS API only, no asset possessed | Not distributed (v1.0's actual TTS model, § 2.3) | No obligation — the app calls a supported Windows API against voices the user's own OS already has; no Microsoft voice/model asset is ever possessed or redistributed |
| PyInstaller (build-time only, not distributed in output in a way that imposes license terms on it) | GPL-2.0-with-bootloader-exception | Build tool only | The bootloader exception explicitly permits distributing PyInstaller-built binaries under any license, including MIT; PyInstaller's own GPL license does not propagate to the packaged app |

**No GPL code is present in the base application.** The one LGPL
component (Qt/PySide6) is compatible with an MIT project **conditional on
dynamic linking**, which is the default and recommended PyInstaller mode
anyway (`--onedir`), not a special accommodation. The M15.0-evaluated TTS
dependency chain (Kokoro/`torch`/sherpa-onnx/`piper-voices`) is licensed
compatibly (Apache-2.0/BSD/MIT, no GPL) but this is now moot for v1.0
distribution purposes, since v1.0 does not distribute any of it (§ 2.3).

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
| **Inno Setup** | **Recommended** | Free, scriptable (`.iss`), the most common companion to PyInstaller in the Python desktop-packaging community, natively supports per-user-only install mode (`PrivilegesRequired=lowest`, with no `PrivilegesRequiredOverridesAllowed` — that directive's `commandline`/`dialog` values expose an `/ALLUSERS` (or UI) path into administrative install mode, which would contradict the frozen per-user-only decision), Start Menu + optional Desktop shortcut checkboxes out of the box, built-in uninstaller generation, and an uninstall-time confirmation/control path for the "also delete local user data" opt-in the frozen decision requires. |
| WiX Toolset (MSI) | Not selected for v1 | More powerful for enterprise/MSI-based deployment (Group Policy, SCCM) than this per-user, GitHub-Releases-only product needs; steeper XML-based authoring; MSI's per-machine-oriented conventions fight the per-user-only frozen decision more than Inno Setup's do. |
| NSIS | Viable alternative, not selected | Comparable capability to Inno Setup; Inno Setup's Pascal-scripting model and documentation are a better fit for this project's existing all-Python/PowerShell tooling conventions and the one engineer maintaining it. |
| MSIX (Windows App Package) | Not selected for v1 | Code signing is now required regardless of installer format (§ 2.7), so MSIX's signing requirement is no longer the deciding factor against it. It remains unselected because it is Store/App-Installer-shaped packaging this per-user, GitHub-Releases-only product does not need, and because Inno Setup already covers the frozen per-user-install, Start Menu/Desktop-shortcut, and uninstall-opt-in requirements without that added complexity. Worth reconsidering only if a Store-adjacent distribution model becomes attractive later (§ 1, § 6 — not a current M20 exit criterion). |

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
- **Uninstall (frozen: preserves data by default):** the uninstaller
  removes only the install directory
  (`%LOCALAPPDATA%\Programs\Vocabulary App\`); `%LOCALAPPDATA%\vocabulary_app\`
  is left untouched unless the user explicitly opts in to also deleting it,
  through an unchecked-by-default control presented at uninstall time. The
  **required product behavior** is frozen — an explicit, unchecked
  destructive-data opt-in the user must actively select, through a
  supported Inno Setup uninstall-time code path, never a default or
  ambiguous action. The **exact implementation mechanism is Phase B
  scope**, not committed here.
- **Rollback (frozen: manual, via reinstall):** document the rollback
  procedure as: (1) download the prior version's installer from GitHub
  Releases, (2) install over/alongside, (3) if the new version's schema
  migration is incompatible with the old code, restore the relevant
  `backups\vocab-pre-*.db` file over `vocab.db` before launching the old
  version. No in-app rollback tooling is required for v1.0.

### 2.7 Code-signing and SmartScreen

**Frozen (Third Revision operator decision amendment, § 1): the v1.0 RC
and public installer must be code-signed before final release.** The
earlier position leaving signed vs. unsigned as a later, open M20
decision is superseded — this is no longer optional or deferred.

- An unsigned PyInstaller/Inno Setup executable **will** trigger Windows
  SmartScreen's "Windows protected your PC" interstitial on first run for
  most users, and has a non-trivial chance of a false-positive AV flag
  (materially higher for `--onefile` builds than `--onedir`, reinforcing
  the § 2.5 choice) — this is the problem the frozen signing requirement
  addresses.
- **Purpose (frozen, § 1):** a verifiable publisher identity for the
  distributed Windows installer; a credible Windows release-engineering
  workflow; improved (not guaranteed) SmartScreen trust/reputation
  handling. **Explicitly not claimed:** that signing makes SmartScreen
  never warn, or that it auto-approves a newly released installer.
- **Corrected against current Microsoft guidance:** an EV (Extended
  Validation) certificate does **not** grant instant SmartScreen
  reputation any more than a standard OV certificate does. Microsoft
  retired EV's automatic-reputation carve-out; **all** code-signing
  certificates, OV and EV alike, now earn SmartScreen reputation the same
  way — through accumulated clean download/execution telemetry over time.
  A freshly signed certificate of either kind can still show warnings for
  a period regardless of validation level — consistent with the "not
  guaranteed" framing above, not in tension with it.
- **Current Microsoft-recommended low-cost signing option (researched,
  not yet purchased/configured):** **Azure Artifact Signing** (Microsoft's
  current low-cost non-Store code-signing service; also referred to as
  "Trusted Signing" in some Microsoft documentation), Basic tier,
  **≈US$9.99/month**. Individual developers are eligible (Microsoft's
  eligibility criteria include individual developers based in Canada,
  among other qualifying countries/entities), and it does **not** require
  a physical hardware token — a materially lower-friction and lower-cost
  path than a traditional OV/EV certificate from a commercial CA
  (traditional CA certificates still typically run $100–700+/year and
  remain a viable alternative, just not the only realistic one).
- **Not decided here, left to Phase B/RC packaging work (frozen, § 1):**
  the exact signing provider/service (Azure Artifact Signing vs. a
  traditional CA), certificate/account setup, the exact validated
  certificate subject/publisher name, and timestamping/signing command
  integration. **On certificate subject specifically:** the public
  portfolio/author identity may continue to use Peter Shi, but the
  Authenticode certificate subject must be whatever identity the selected
  trusted signing provider actually validates — an unsupported subject
  must not be hard-coded merely for branding consistency.
- **Preserved unchanged:** SHA-256 checksum publication for every release
  asset in the GitHub Release notes (independent, additional verification
  alongside the Authenticode signature, not a substitute for it);
  signed-artifact verification as part of RC evidence (§ 5); the existing
  GitHub Releases distribution target (§ 1). A longer-term possibility of
  Microsoft Store distribution is not a current M20 exit criterion and
  this section does not expand M20 into Store/MSIX work (§ 1, § 6).

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
2. **Installer:** Inno Setup, per-user-only install mode
   (`PrivilegesRequired=lowest`, with **no** `PrivilegesRequiredOverridesAllowed`
   directive — omitting it removes the `/ALLUSERS` administrative-install
   escape hatch and keeps the frozen per-user-only decision structurally
   enforced, not just documented), Start Menu group created
   unconditionally, Desktop shortcut task checked by default and
   user-togglable.
3. **Application-data root:** `%LOCALAPPDATA%\vocabulary_app\` for
   `vocab.db`, `backups\`, `preferences.json`, `audio-cache\` — extending
   the pattern already implemented for preferences/audio-cache to the
   database and backup paths (Phase B code change, tracked as Open Blocker
   OB-1 below, not done in Phase A).
4. **TTS distribution:** ship v1.0 with **no** third-party TTS runtime,
   model, or voice package at all — not bundled, not downloaded, not
   redistributed (frozen operator decision, § 1). Implement a **Local
   Windows Speech Provider / Installed Voice Binding** capability instead:
   enumerate compatible speech voices already installed on the user's own
   Windows system, let the user explicitly choose and bind one, persist
   the choice, and never silently install/download a missing voice (§ 1,
   § 2.3). **Not selected in Phase A, left to Phase B:** which native
   Windows mechanism implements voice enumeration/invocation for English
   and French coverage under this model — the WinRT
   `SpeechSynthesizer` path `scripts/tts_yaoyao.ps1` already uses for
   Mandarin, the older SAPI5 voice-enumeration API, or another native
   mechanism if evidence later supports one (§ 2.3). This supersedes the
   prior "1–1.5 GB optional TTS payload, portable-Python provisioning
   architecture" decision entirely — that content is retained in § 2.3
   only as superseded historical/internal engineering context.
5. **Checksum/integrity (installer assets only — the TTS provisioning
   integrity contract from the superseded model no longer applies, § 2.3,
   OB-2):** publish SHA-256 for every GitHub Release installer asset in
   the release notes, as an independent, additional verification
   mechanism alongside the Authenticode signature required by decision 6
   below, not a substitute for it.
6. **Code-signing:** **required for the v1.0 RC and public release**
   (frozen operator decision, § 1, § 2.7 — supersedes the earlier "not
   decided" position). Azure Artifact Signing (≈US$9.99/month Basic, no
   hardware token, individual-developer-eligible) is the current
   Microsoft-recommended low-cost option; a traditional OV/EV CA
   certificate remains a viable alternative. Exact provider, certificate/
   account setup, the exact validated certificate subject, and
   timestamping/signing command integration are Phase B/RC-packaging
   decisions, not made here. The public author identity may stay "Peter
   Shi"; the certificate subject itself must be whatever the chosen
   provider actually validates. Signing does not eliminate SmartScreen
   warnings outright and must not be documented as if it does.
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
- **OB-2 — REWRITTEN by Third Revision (was: TTS provisioning architecture
  and minimum manifest for a third-party runtime download; that content is
  superseded, not applicable to v1.0, and retained only as historical
  context in § 2.3):** the current, active OB-2 is the **Local Windows
  Speech Provider implementation mechanism**, not yet selected — Phase B
  must determine which native Windows API/mechanism enumerates and invokes
  compatible English and French voices for the "Installed Voice Binding"
  capability (§ 1, § 2.3, § 3 decision 4). The existing Mandarin path
  (`scripts/tts_yaoyao.ps1`, WinRT `SpeechSynthesizer`) is working prior
  art but Phase A found no evidence establishing whether that same WinRT
  path, the older SAPI5 voice-enumeration API, or another mechanism is the
  right choice for English/French — this requires Phase B investigation
  against real installed-voice enumeration behavior, not Phase A
  speculation. Also open for Phase B: the exact UI for voice
  discovery/selection/binding, and the exact "capability unavailable"
  messaging when no compatible local voice exists. No provider/model
  substitution risk here — there is no third-party provider or model in
  this model at all, only OS-supplied voices the app calls through a
  supported API, never possesses, and never installs.
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
- **OB-6 (code-signing provider/account setup not yet made — blocks final
  RC release, not earlier Phase B work):** the frozen decision (§ 1, § 2.7,
  § 3 decision 6) requires the v1.0 RC and public installer to be signed,
  but the signing provider (Azure Artifact Signing vs. a traditional CA),
  account/certificate setup, the exact validated certificate subject, and
  timestamping/signing command integration into the Inno Setup/PyInstaller
  build are all undecided. This does not block earlier Phase B packaging
  work (bundler/installer scripting, path fixes, TTS provider mechanism)
  but does block declaring an RC installer artifact final and ready for
  public release.

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
   `python -m src.ui_desktop`) executable, including the Local Windows
   Speech Provider capability specifically: voice enumeration/selection
   on a machine with a compatible voice installed, and the honest
   "capability unavailable/configuration required" path on a machine (or
   the clean VM, § 2.8) without one — never a silent third-party
   provisioning fallback (§ 2.3).
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
   inclusion of `.venv`, test fixtures, developer-machine-specific paths,
   or any third-party TTS runtime/model/voice asset — none should be
   present at all under the § 2.3 distribution model).
9. **Signed-artifact verification (new, § 2.7, OB-6):** confirm the public
   installer carries a valid Authenticode signature from the selected
   trusted signing provider, and confirm the published SHA-256 checksum
   matches the actual release asset — both checks are required, neither
   substitutes for the other.
10. **Documentation reconciliation:** README install instructions
    (including the Local Windows Speech Provider disclosure required by
    § 2.3 — no bundled/redistributed third-party TTS claim, audio depends
    on voices already installed on the user's device), `THIRD_PARTY_NOTICES.md`
    (revised per § 2.3 to list/notice only what v1.0 actually distributes —
    it still describes itself as a distribution-facing summary listing
    Kokoro/sherpa-onnx/Piper obligations as of this writing, which is stale
    against the superseding decision and is not release-ready as-is), and
    `LICENSE` all match the shipped RC build before tagging.

Any failure returns the project to the relevant M20 hardening work and
requires the affected regression to be repeated in full, per ROADMAP § 20.3
— Phase A does not weaken that rule.

---

## 6. Deferred / Future Distribution Work

Explicitly out of scope for v1.0 per the frozen decisions, recorded so
later milestones don't silently reopen them without an operator decision:

- Automatic update checking/installation.
- macOS/Linux packaging.
- MSIX/Microsoft Store distribution.
- Any distribution channel other than GitHub Releases.
- Bundling, downloading, or redistributing any third-party TTS runtime,
  model, or voice package for end users, in any form — not just excluded
  from the base installer, excluded entirely (§ 1, § 2.3, superseding the
  earlier optional-download-payload model).
- New product-language support (Spanish, Japanese, Korean, or otherwise)
  merely because the Local Windows Speech Provider capability makes
  additional installed Windows voices discoverable (§ 1, § 2.3 — Feature
  Freeze preserved).
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

**Third Revision (operator decision amendment) reconciliation check:**
`ROADMAP.md` § 20.1–20.2 and `PROJECT_STATUS.md` were reviewed again
specifically for the TTS distribution model and code-signing changes.
Neither commits to a specific TTS payload size, provisioning architecture,
or sign/unsigned position — ROADMAP § 20.2 speaks generically of
"third-party notices" and "TTS runtime and voice/model licenses where
applicable," which remains accurate under the Local Windows Speech
Provider model (§ 2.3) without requiring a wording change. `LICENSE`,
`THIRD_PARTY_NOTICES.md`, and `docs/policies/TTS_LICENSE_AND_ATTRIBUTION.md`
were left unedited, consistent with this amendment's docs-only,
this-file-and-PR-only scope — but **not for the same reason in each
case** (§ 2.3 above records the distinction in full): `docs/policies/
TTS_LICENSE_AND_ATTRIBUTION.md` may remain as-is because it is a
historical evidentiary record, not a claim about what v1.0 currently
ships. `THIRD_PARTY_NOTICES.md` is left unedited only because editing it
is Phase B/RC work, not because its current Kokoro/sherpa-onnx/Piper
content is still accurate — it explicitly presents itself as a
distribution-facing summary and, as of this writing, still lists
distribution obligations for TTS assets the Third Revision decision means
v1.0 does not ship. It is stale relative to that decision and must be
revised (§ 5 item 10) before public release.
