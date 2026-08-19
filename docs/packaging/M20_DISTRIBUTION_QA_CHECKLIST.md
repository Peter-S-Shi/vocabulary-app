# M20 Distribution QA Checklist

Companion to `docs/packaging/M20_RELEASE_CONTRACT.md` §§ 2.8, 5 and the
loop prompt's § 10 "Distribution QA". Two distinct tests, per the
Release Contract's own framing — do not conflate them:

- **§ A — Fresh local Windows user account** (this same physical
  machine): the per-user-install-path check. Proves Start Menu entry,
  no admin prompt, `%LOCALAPPDATA%\vocabulary_app\` creation, and real
  browser-download SmartScreen behavior — but shares this machine's
  kernel/drivers/global runtimes, so it is *not* clean-machine proof.
- **§ B — Clean Windows VM** (VirtualBox + official Microsoft
  evaluation media, per § 2.8): the actual clean-machine verification
  path, since this dev machine is Windows 11 Home and cannot run
  Hyper-V/Windows Sandbox.

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
   - [ ] No admin-elevation (UAC) prompt appears.
   - [ ] Installs to `%LOCALAPPDATA%\Programs\Vocabulary App\`.
   - [ ] Start Menu entry exists ("Vocabulary App").
   - [ ] Desktop shortcut exists (default-enabled task).
   - [ ] App launches; a real top-level window appears.
   - [ ] `%LOCALAPPDATA%\vocabulary_app\vocab.db` is created fresh (no
     inherited data from the primary dev account).
   - [ ] Settings > Audio: "Refresh Voices" lists real installed
     Windows voices for this account.
5. Uninstall via Start Menu / Settings > Apps; verify:
   - [ ] Default uninstall preserves `%LOCALAPPDATA%\vocabulary_app\`.
   - [ ] Re-running the installer's uninstaller a second time (or a
     fresh reinstall) still opens the preserved data.
6. Optionally repeat uninstall choosing the explicit "delete my data"
   opt-in and confirm the directory is actually removed.

**Already verified by the agent on the primary dev account** (not a
substitute for the above, since it isn't a fresh account, but the
underlying mechanics are the same): installer runs elevation-free,
correct per-user install path, Start Menu entry, real window, fresh
`vocab.db` at the correct path, bundled Local Windows Speech Provider
scripts enumerate real voices, default uninstall preserves data,
explicit opt-in uninstall deletes it (tested against disposable
throwaway data). See the M20 Phase B packaging commit for the exact
verification transcript.

---

## § B. Clean Windows VM

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
