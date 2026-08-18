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

**Revision note:** this document was revised twice, before being
considered frozen, after operator review of each draft.

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
manifest in the relocatable, portable-Python runtime tree described below
(not a copy of this dev `venv`) with only the packages the shipped
`kokoro`/`sherpa-onnx` adapters import at runtime, dependency-resolved
from scratch, and verify its real size before the final payload size is
accepted — it may turn out smaller than 1.46 GB once dev-only extras are excluded, or it may
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

**Critical architecture finding, not previously surfaced: the frozen TTS
provider contract requires a private Python interpreter the end user does
not have.** `build_shared_runtime_registry()`
(`src/tts_providers.py`) resolves `python_exe = root / "venv" / "Scripts" /
"python.exe"` and shells out to it for both the Kokoro and sherpa-onnx
adapters — the frozen (M15.0) product contract is not "call `kokoro`/
`sherpa-onnx` as importable Python packages," it is specifically "invoke a
private interpreter's `python.exe` as a subprocess." A clean Windows
end-user machine has **no system Python at all** by default, so a
first-run provisioning step that simply runs `pip install kokoro
sherpa-onnx ...` has nothing to run `pip` *with* — there is no interpreter
to install into until one exists. **This was not resolved by the original
draft's "download via `pip`" framing, which implicitly assumed a system
Python was already present.**

**Correction: a normal `python -m venv` environment is also not itself a
valid answer, and must not be proposed as one.** An ordinary `venv` is not
a portable/copyable distribution artifact — its `pyvenv.cfg` records an
absolute `home` path back to the base Python installation that created it,
and its `Scripts\` launcher `.exe`s and `.pth`/config files can embed
absolute paths tied to the machine that built it. Building a dev-machine
`venv` and zip/unzipping it onto an end-user machine is not a supported
or reliable redistribution mechanism and is not proposed here. Both
architecture options below are instead built around a **self-contained,
relocatable private Python runtime** — a portable/embeddable Python
distribution (e.g. the official `python.org` Windows embeddable ZIP),
which is designed to be relocated as a plain directory tree with no
baked-in absolute-path dependency on the machine that assembled it — not
a standard `venv`. Phase B must choose and prove one of two such
architectures, neither of which depends on a preinstalled Python/pip on
the end-user machine:

1. **Pre-built, versioned self-contained TTS runtime pack:** in a
   controlled build environment, assemble the target directory tree from
   a portable/embeddable Python runtime plus pinned dependencies, the
   Kokoro/sherpa-onnx adapters, and the voice/model assets; package that
   already-relocatable tree as a versioned archive published as a GitHub
   Release asset; have the in-app downloader fetch and unpack it verbatim.
   No dependency resolution, `pip install`, or Python installation step
   ever runs on the end-user machine — the runtime tree arrives already
   built and is relocatable by construction because it is a portable
   interpreter, not a `venv`.
2. **Self-bootstrapping downloader with a portable/embeddable Python:**
   the first-run downloader first acquires the same portable/embeddable
   Python runtime (fetched pinned/hash-verified, e.g. from the official
   `python.org` embeddable-ZIP releases), then uses *that* private,
   already-relocatable interpreter — never a system Python — to construct
   the identical deterministic runtime tree on the end-user machine from
   pinned, hash-verified wheels/model assets, entirely under
   `%LOCALAPPDATA%`.

Both converge on the same target artifact shape (a relocatable portable-
Python tree, not a `venv`); Phase B must also confirm whether
`build_shared_runtime_registry()`'s `root / "venv" / "Scripts" /
"python.exe"` path resolution needs a corresponding small code update to
match whatever directory name the chosen architecture actually produces,
or whether Phase B provisioning simply names its output directory `venv\`
to match the existing frozen path unchanged — either is a Phase B
implementation detail, not decided here.

**Neither architecture is selected here — this is Phase B's decision to
make and prove against a real clean machine, not Phase A's** (§ 3 decision
4, § 4 OB-2 restated accordingly below). The 1–1.5 GB payload target (§ 1)
and the frozen English/French/Mandarin (`kokoro`/`sherpa-onnx`/Windows
Yaoyao) provider selection (M15.0) are unaffected by this correction —
this is purely about *how* that already-selected runtime reaches the
user's machine as a working, relocatable artifact, not about replacing
any provider, model, or language.

**Integrity contract correction:** the original draft's "verifies each
downloaded package/model against its origin's own integrity mechanism
(`pip`'s hash verification..., Hugging Face Hub's built-in file hash
verification)" is not sufficient by itself as an RC integrity contract —
default `pip`/Hugging Face Hub client behavior resolves to whatever the
latest matching version happens to be at download time and does not, on
its own, pin an exact version/revision or enforce a specific expected
hash chosen in advance by this project. Whichever architecture Phase B
selects, the RC integrity contract requires: **(a)** every package version
(or Hugging Face Hub revision/commit) pinned to an exact, recorded value,
not a floating "latest"; **(b)** an explicit manifest of expected SHA-256
hashes for every downloaded file, authored by this project and checked
after download, not merely delegated to the upstream tool's own default
verification step; **(c)** a documented, reproducible procedure for how
that pinned-version/hash manifest itself was produced and can be
regenerated when the TTS dependency set is deliberately updated.

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
| **Inno Setup** | **Recommended** | Free, scriptable (`.iss`), the most common companion to PyInstaller in the Python desktop-packaging community, natively supports per-user-only install mode (`PrivilegesRequired=lowest`, with no `PrivilegesRequiredOverridesAllowed` — that directive's `commandline`/`dialog` values expose an `/ALLUSERS` (or UI) path into administrative install mode, which would contradict the frozen per-user-only decision), Start Menu + optional Desktop shortcut checkboxes out of the box, built-in uninstaller generation, and an uninstall-time confirmation/control path for the "also delete local user data" opt-in the frozen decision requires. |
| WiX Toolset (MSI) | Not selected for v1 | More powerful for enterprise/MSI-based deployment (Group Policy, SCCM) than this per-user, GitHub-Releases-only product needs; steeper XML-based authoring; MSI's per-machine-oriented conventions fight the per-user-only frozen decision more than Inno Setup's do. |
| NSIS | Viable alternative, not selected | Comparable capability to Inno Setup; Inno Setup's Pascal-scripting model and documentation are a better fit for this project's existing all-Python/PowerShell tooling conventions and the one engineer maintaining it. |
| MSIX (Windows App Package) | Not selected for v1 | Requires either a trusted code-signing certificate or enabling Developer Mode/sideloading on the end-user machine for an unsigned package — would push installation friction onto exactly the non-technical users the desktop product targets if shipped unsigned, and the sign/unsigned choice itself is not yet decided (§ 2.7). Inno Setup does not have this dependency either way. Worth reconsidering only if signing is adopted later and a Store-adjacent distribution model becomes attractive. |

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

- An unsigned PyInstaller/Inno Setup executable **will** trigger Windows
  SmartScreen's "Windows protected your PC" interstitial on first run for
  most users, and has a non-trivial chance of a false-positive AV flag
  (materially higher for `--onefile` builds than `--onedir`, reinforcing
  the § 2.5 choice).
- **Corrected against current Microsoft guidance:** an EV (Extended
  Validation) certificate does **not** grant instant SmartScreen
  reputation any more than a standard OV certificate does. Microsoft
  retired EV's automatic-reputation carve-out; **all** code-signing
  certificates, OV and EV alike, now earn SmartScreen reputation the same
  way — through accumulated clean download/execution telemetry over time.
  A freshly purchased certificate of either kind shows warnings for a
  period regardless of validation level. The earlier draft's claim that EV
  buys instant reputation was wrong and is corrected here rather than
  silently dropped.
- **Current Microsoft-recommended low-cost signing option (researched,
  not purchased):** **Azure Artifact Signing** (Microsoft's current
  low-cost non-Store code-signing service; also referred to as "Trusted
  Signing" in some Microsoft documentation), Basic tier, **≈US$9.99/month**. Individual
  developers are eligible (Microsoft's eligibility criteria include
  individual developers based in Canada, among other qualifying
  countries/entities), and it does **not** require a physical hardware
  token — a materially lower-friction and lower-cost path than a
  traditional OV/EV certificate from a commercial CA (§ prior draft's
  $100–700+/year figures, which remain accurate for traditional CAs but
  are no longer the only realistic option).
- **Not decided in Phase A:** whether v1.0 ships signed or unsigned is
  **not frozen here**. Unsigned remains an acceptable, zero-cost option
  for v1.0 and was the operator's original framing ("no code-signing
  budget was frozen as a decision"), but the sign/unsigned choice is left
  open for a later M20 decision, to be made once a real RC installer
  artifact exists and the operator can weigh actual SmartScreen friction
  (or Azure Artifact Signing's ~$10/month) against a concrete build,
  rather than against a hypothetical one now.
- **Mitigation regardless of the eventual sign/unsigned decision:**
  (1) publish SHA-256 checksums for every release asset directly in the
  GitHub Release notes so users can verify integrity independently of
  SmartScreen; (2) if unsigned, document the expected SmartScreen warning
  and the "More info → Run anyway" path in the README install
  instructions, framed honestly (unsigned open-source software, verify the
  checksum) rather than instructing users to just click through blindly.

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
4. **TTS payload:** ship the base installer with zero TTS runtime; first
   Audio Export use triggers an in-app guided download of a minimal
   English/French/Mandarin runtime manifest, target approximately 1–1.5 GB
   (§ 1), derived and measured fresh in Phase B rather than assumed equal
   to the ~1.46 GB dev-environment measurement (§ 2.3, OB-2). **Not
   selected in Phase A:** which of the two self-contained provisioning
   architectures identified in § 2.3 (a pre-built, versioned runtime pack
   built around a portable/embeddable Python runtime, vs. a downloader
   that first bootstraps that same kind of portable/embeddable Python and
   then constructs the runtime tree itself) Phase B implements. Neither a
   live `pip install` against a system Python nor a copied ordinary
   `python -m venv` environment is viable against a clean end-user machine
   — the former has no system Python to run against, the latter is not a
   portable/relocatable artifact (§ 2.3) — so neither is frozen as the
   architecture. Whichever of the two named alternatives is chosen,
   packages/models come from the same upstream sources already selected
   and license-cleared at M15.0 (PyPI for the pinned dependency set,
   Hugging Face Hub for Kokoro weights, the existing `piper-voices`
   Hugging Face repo for the French voice) — not a new redistribution
   channel, not a re-hosted mirror, preserving "no silent provider/model/
   license substitution."
5. **Checksum/integrity:** publish SHA-256 for every GitHub Release
   installer asset in the release notes. The TTS provisioning integrity
   contract is **not** "rely on `pip`/Hugging Face Hub's own default
   verification alone" (corrected in § 2.3): Phase B must pin every
   package version (or Hugging Face Hub revision) to an exact recorded
   value, author an explicit SHA-256 manifest for every file the
   provisioning step downloads or unpacks, verify against that
   project-authored manifest (not merely trust the upstream tool's default
   behavior), and document how the manifest itself is produced/regenerated
   on a deliberate dependency update.
6. **Code-signing:** **not decided in Phase A.** Unsigned remains
   acceptable and zero-cost; Azure Artifact Signing (≈US$9.99/month Basic,
   no hardware token, individual-developer-eligible) is the current
   Microsoft-recommended low-cost option if signing is adopted (§ 2.7).
   The choice is deferred to a later M20 decision point, made against a
   real RC installer artifact rather than a hypothetical one. Regardless
   of the outcome, publish SHA-256 checksums for every release asset in
   the GitHub Release notes, and if the RC ships unsigned, document the
   expected SmartScreen warning honestly in the README.
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
- **OB-2 (TTS provisioning architecture and minimum manifest not yet
  derived — blocks Phase B's TTS provisioning work directly, not the rest
  of Phase B):** two compounding gaps, both surfaced in § 2.3:
  - **Architecture:** the frozen (M15.0) TTS provider contract requires a
    private `venv\Scripts\python.exe`-shaped interpreter
    (`build_shared_runtime_registry()` in `src/tts_providers.py`), and a
    clean end-user machine has no system Python to bootstrap one with. A
    plain `pip install` step is not viable as-is against a clean machine,
    and an ordinary `python -m venv` environment copied from a dev machine
    is not a portable/relocatable artifact either (§ 2.3 — its
    `pyvenv.cfg` and launcher scripts carry absolute paths back to the
    machine that created it). Phase B must select and prove one of the two
    self-contained architectures identified in § 2.3, both built around a
    portable/embeddable Python runtime rather than a `venv` — a pre-built
    versioned runtime pack, or a downloader that first bootstraps that
    same portable/embeddable Python and then constructs the runtime tree
    itself — before any provisioning code is written.
  - **Manifest size:** the frozen payload target is approximately 1–1.5 GB
    (§ 1), and the measured ~1.46 GB dev `venv` (§ 2.3) is an upper-bound
    observation that fits inside that range but is not yet the actual
    minimum-required manifest. Once the architecture above is chosen,
    Phase B must build a clean-directory install of exactly what the
    shipped English/French/Mandarin runtime needs (dependency-resolved
    from scratch with pinned versions/hashes per § 2.3's integrity
    contract, not copied from the dev `venv`), measure its real size, and
    confirm it lands inside 1–1.5 GB before the payload size is treated as
    final.

  No provider/model/license substitution is proposed or implied by either
  gap — both are about *how* the already-selected, license-cleared, frozen
  (M15.0) `kokoro`/`sherpa-onnx` runtime reaches the end user's machine
  intact and verifiable, not about replacing it.
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
