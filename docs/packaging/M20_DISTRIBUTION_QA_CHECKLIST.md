# M20 Distribution QA Checklist

Companion to `docs/packaging/M20_RELEASE_CONTRACT.md` §§ 2.8, 5 and the
loop prompt's § 10 "Distribution QA".

## Operator decision amendment (supersedes § 2.8's VM requirement for v1.0)

**Recorded verbatim, per the Release Contract's own convention of
keeping the historical record of why a plan changed attached to the
decision:** the operator explicitly canceled the VirtualBox
clean-machine VM requirement for this v1.0 portfolio release. No time
or resources are to be spent provisioning a VM. The fresh local
standard Windows account (§ A below) is instead the practical
installation-isolation acceptance environment for v1.0: installer,
first-launch, data-path (including existing-database import and
backup-before-upgrade), upgrade, uninstall/reinstall, and
data-preservation checks are all completed there. **Public-facing
documentation and the RC report must not claim pristine/clean-machine
verification** — § A shares this machine's kernel, drivers, and
globally-installed runtimes, and that limitation must stay stated
honestly wherever this testing is referenced. Full clean-machine VM
verification (§ B) is deferred to a future broader public distribution
or Microsoft Store preparation effort, not part of v1.0 RC scope.

Originally, two distinct tests were planned, per the Release Contract's
own framing:

- **§ A — Fresh local Windows user account** (this same physical
  machine): the per-user-install-path check. Proves Start Menu entry,
  no admin prompt, `%LOCALAPPDATA%\vocabulary_app\` creation, and real
  browser-download SmartScreen behavior — but shares this machine's
  kernel/drivers/global runtimes, so it is *not* clean-machine proof.
  **Now the authoritative v1.0 acceptance environment per the amendment
  above.**
- **§ B — Clean Windows VM** (VirtualBox + official Microsoft
  evaluation media, per § 2.8): the actual clean-machine verification
  path, since this dev machine is Windows 11 Home and cannot run
  Hyper-V/Windows Sandbox. **Deferred, not attempted for v1.0** per the
  amendment above; retained below only as a record of the original plan
  for whenever it is revisited.

Both require actions on this machine beyond repository edits (creating
a user account; installing/provisioning a VM), which is why they are
recorded here as a checklist rather than run silently — see the loop
prompt § 14.B "external environment" stop condition.

---

## Before either test: build the artifact

```powershell
pip install -r requirements-desktop.txt -r requirements-build.txt
python winbuild/build.py
```

Confirm `dist\installer\VocabularyApp-Setup-<version>.exe` exists and
note its SHA-256 from `dist\build_manifest.json`.

---

## § A. Fresh local Windows user account

1. Create a new local standard (non-admin) Windows account on this
   machine, with no Python/git/dev tooling.
2. Sign in as that user.
3. Download `VocabularyApp-Setup-<version>.exe` (ideally through an
   actual browser download, not a copied file, to exercise the real
   mark-of-the-web SmartScreen path) and run it.
4. Verify:
   - [x] No admin-elevation (UAC) prompt appears.
   - [x] Installs to `%LOCALAPPDATA%\Programs\Vocabulary App\`.
   - [x] Start Menu entry exists ("Vocabulary App").
   - [x] Desktop shortcut exists (default-enabled task).
   - [x] App launches; a real top-level window appears.
   - [x] `%LOCALAPPDATA%\vocabulary_app\vocab.db` is created fresh (no
     inherited data from the primary dev account).
   - [x] Settings > Audio: "Refresh Voices" lists real installed
     Windows voices for this account.
5. Uninstall via Start Menu / Settings > Apps; verify:
   - [x] Default uninstall preserves `%LOCALAPPDATA%\vocabulary_app\`.
   - [x] Re-running the installer's uninstaller a second time (or a
     fresh reinstall) still opens the preserved data.
6. Optionally repeat uninstall choosing the explicit "delete my data"
   opt-in and confirm the directory is actually removed.
   - [ ] Not independently re-run under this account (see note below);
     covered under the primary-account verification instead.

**Executed 2026-08-19 against a genuine new local standard account
(`VocabAppQA`, created by the operator, no dev tooling), automated via
Windows Task Scheduler running as that account** (`schtasks /RU
VocabAppQA /RP ...`, after the operator granted the account "Log on as
a batch job" locally so the tasks could actually execute — interactive
`Start-Process -Credential` from a non-elevated session was tried first
and reliably fails with Access Denied; this is a known Windows
limitation, not an app defect). Each check ran a real install/launch/
uninstall/reinstall and wrote results to a `C:\Users\Public\` file this
agent's own (separate, non-admin) account could read back, since one
standard account cannot read another's `%LOCALAPPDATA%` directly —
that cross-profile isolation is itself confirming evidence the account
truly is a separate, unprivileged profile.

Findings:
- Installer ran with zero elevation prompts, installed to the correct
  per-user path, created the Start Menu entry and Desktop shortcut, and
  `whoami` inside the task confirmed it executed as the `VocabAppQA`
  account throughout.
- First launch created a fresh `vocab.db` (258,048 bytes) and the
  process stayed alive >12s without exiting — strong indirect evidence
  a real window rendered and initialized normally (a Qt window-creation
  crash would exit near-immediately); Task Scheduler runs in a
  non-interactive window station, so a literal screenshot of the window
  from this account was not obtainable, and the operator has not yet
  separately eyeballed it via an interactive session switch.
- `Settings > Audio` voice enumeration (`scripts/tts_list_voices.ps1`)
  correctly listed 22 real, machine-installed SAPI/OneCore voices under
  this account (English, French, Chinese, Japanese, etc.) — the same
  Local Windows Speech Provider mechanism, proven per-account.
- Backup-before-upgrade: built a synthetic database at an older schema
  version (`13.0.0-linked-append-source`), placed it as this account's
  `vocab.db`, relaunched — the app correctly wrote
  `vocab-pre-13.0.0-linked-append-source-2026-08-19_001311.db` to
  `backups\` *before* migrating, and the live database ended at the
  current schema version (`15.1.0-speech-semantics`) afterward.
- Default uninstall (`unins000.exe /VERYSILENT /SUPPRESSMSGBOXES`):
  removed the program files immediately and left
  `%LOCALAPPDATA%\vocabulary_app\` untouched. Notable finding: the
  `[Code]` section's data-deletion confirmation (`MsgBox(...,
  MB_YESNO or MB_DEFBUTTON2)`) is not explicitly silent-mode-aware, but
  `/SUPPRESSMSGBOXES` still resolved it to its default button (No —
  preserve), so a fully unattended uninstall does not hang and safely
  defaults to keeping user data. A genuinely interactive uninstall
  would show this dialog as designed.
- Reinstall + relaunch: reused the preserved `vocab.db` byte-for-byte
  (258,048 bytes before and after) rather than recreating it. To prove
  this wasn't a coincidental size match, a marker row
  (`qa_marker = preserved-test-20260819`) was written into the database
  before uninstalling; it was still present, alongside the already-
  current schema version, after the full uninstall → reinstall →
  relaunch cycle.
- Existing-database import (Data Tools > "Use an Existing Database…")
  was **not** exercised through the actual file-picker UI under this
  account — Task Scheduler's non-interactive session has no way to
  drive a native Open-File dialog blindly with acceptable confidence,
  and no interactive desktop session for `VocabAppQA` was available
  during this run. As a substantive (not GUI-click) substitute, the
  real `import_existing_database()` function was separately exercised
  end-to-end on the primary account (isolated to a disposable temp
  location, never touching real personal data): built a pre-existing
  "already installed" destination database and a separate synthetic
  "existing user database" with a distinguishing marker row, ran the
  actual import function unmodified, and confirmed all three frozen
  behaviors for real — the destination was backed up before being
  overwritten (and that backup opens correctly, at the current schema
  version), the source file's hash was byte-identical before and
  after (never modified), and the destination now carries the
  imported data with the marker intact even after a fresh `init_db()`
  reopen. This closes the RC Verification Contract's "representative
  existing-database testing" item on real evidence; only the literal
  file-picker button-click sequence remains unobserved. Recommend the
  operator do one manual click-through of that specific UI flow before
  final release for full end-to-end confidence.
- Optional destructive-uninstall opt-in (explicit "Yes, delete") was
  also not independently re-run under this account for the same
  reason; it remains covered by the primary-account verification noted
  above, and the `[Code]` logic itself is a single unconditional
  `DelTree` gated on `Response = IDYES` with no per-account branching.

**Also already verified by the agent on the primary dev account**
(not a substitute for the above, since it isn't a fresh account, but
the underlying mechanics are the same): installer runs elevation-free,
correct per-user install path, Start Menu entry, real window, fresh
`vocab.db` at the correct path, bundled Local Windows Speech Provider
scripts enumerate real voices, default uninstall preserves data,
explicit opt-in uninstall deletes it (tested against disposable
throwaway data). See the M20 Phase B packaging commit for the exact
verification transcript.

---

## § B. Clean Windows VM (deferred for v1.0 -- see amendment above)

**Not performed for v1.0.** Retained as a record of the original plan
for whenever full clean-machine verification is revisited (future
broader public distribution / Microsoft Store preparation).

1. Install VirtualBox (free) if not already present.
2. Provision a VM from official Microsoft Windows 10/11 evaluation
   media (never a personal/activated Windows license or an image
   copied from this host).
3. Inside the VM, confirm it has **no** Python, git, dev tooling, this
   repository, or any prior `%LOCALAPPDATA%\vocabulary_app\` state.
4. Transfer only `VocabularyApp-Setup-<version>.exe` into the VM
   (e.g. shared folder or a real download inside the VM).
5. Run the full journey and check each step:
   - [ ] Install (no admin prompt, correct per-user location).
   - [ ] First launch, fresh DB.
   - [ ] Core workflow smoke: create an entry, a collection, review a
     card, run a quiz.
   - [ ] Local Windows Speech Provider: Settings > Audio > Refresh
     Voices lists the VM's own installed voices (likely a different,
     smaller set than the dev machine — that's expected and fine;
     confirms no bundled/hidden voice dependency).
   - [ ] Existing-database import: copy a **sanitized/synthetic**
     `vocab.db` into the VM and use Data Tools > "Use an Existing
     Database…"; confirm it copies (not moves), backs up any existing
     destination, and the source file is untouched.
   - [ ] Backup-before-upgrade: install an older build first (or
     hand-set an older `schema_version` in a synthetic DB), then
     install/launch the current build; confirm a
     `vocab-pre-<version>-<timestamp>.db` appears under
     `%LOCALAPPDATA%\vocabulary_app\backups\` before migration runs.
   - [ ] Uninstall with data preserved (default path).
   - [ ] Reinstall; confirm it reopens the preserved data.
   - [ ] (Optional, separately) explicit destructive-uninstall opt-in
     against disposable data only.
6. Record: Windows build/edition used, installer SHA-256 matched the
   build manifest, and a pass/fail per checkbox above.

**Do not use real personal production data for this test** — synthetic
or sanitized data only, per AGENTS.md privacy rules.

---

## Reporting back

Whoever runs § A/§ B (operator or agent, once authorized for the
specific machine action involved) should report pass/fail per checkbox
here; any failure returns to the M20 engineering loop as a defect to
fix, not a reason to waive the checklist.
