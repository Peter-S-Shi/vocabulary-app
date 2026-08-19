# M20 Code Signing Setup

Companion to `docs/packaging/M20_RELEASE_CONTRACT.md` § 2.7 (Fourth
Revision) and the `M20_AUTONOMOUS_RELEASE_ENGINEERING_LOOP.md` prompt § 9.

**Operator decision amendment (supersedes this document's original
"publicly trusted signing required" scope):** for this v1.0 **Portfolio
RC**, no publicly trusted code-signing service is required and no paid
signing cost is incurred. The installer and the bundled onedir
executable are signed with a **self-signed Authenticode developer
certificate**, Subject/Publisher `Peter Shi`, used solely to complete
and verify the Windows signing pipeline. **SmartScreen trust/reputation
handling is explicitly not an M20/v1.0 exit criterion** — a self-signed
certificate does not chain to a trusted root and does not earn
SmartScreen reputation. Public-facing documentation and the RC report
must describe the certificate accurately as self-signed and must never
state or imply it is publicly trusted or reduces/suppresses SmartScreen
warnings. A publicly trusted provider remains a legitimate option for a
future public/commercial/Microsoft Store distribution effort — the
original research is retained below in § 3 as candidate reference for
that future work, not as v1.0's requirement.

---

## 1. What is already done (autonomous, no operator action needed)

- `winbuild/build.py` has a provider-agnostic signing hook: if the
  `VOCAB_APP_SIGN_COMMAND` environment variable is set to a signing
  command template (with a literal `{file}` placeholder), the build
  script signs both the PyInstaller onedir `.exe` and the final Inno
  Setup installer `.exe`, independently, right after each is produced.
  Unset, it is a documented no-op — the rest of the build chain works
  exactly as before.
- Independent, tool-agnostic signature verification
  (`winbuild.build.verify_signature`) via PowerShell's
  `Get-AuthenticodeSignature` — real evidence of what actually got
  signed (status + certificate subject), not just that the signing
  command exited `0`.
- Both recorded in `dist/build_manifest.json`
  (`onedir_exe_signed`/`onedir_exe_signature`,
  `installer_signed`/`installer_signature`) for the RC report to quote
  directly.
- A locally-generated **self-signed Authenticode developer certificate**
  (Subject `CN=Peter Shi`), created once via PowerShell's
  `New-SelfSignedCertificate` (Code Signing EKU, stored in the local
  user's certificate store) and referenced by `VOCAB_APP_SIGN_COMMAND`
  pointing at a `Set-AuthenticodeSignature` invocation. This is the
  actual v1.0 signing configuration, not a throwaway test — the
  certificate is kept (not deleted after use) so the same signing
  identity is reused across RC rebuilds.
- No secret, credential, or private key material is committed to this
  repository. The self-signed certificate lives only in the local
  Windows certificate store; `VOCAB_APP_SIGN_COMMAND` lives only in the
  local build environment.

## 2. Verified result (expected and correct for a self-signed certificate)

Running `winbuild/build.py` with `VOCAB_APP_SIGN_COMMAND` configured
signs both artifacts and records, via `Get-AuthenticodeSignature`:

- the signature is **present** on the file, with a **subject and
  thumbprint matching the self-signed `Peter Shi` certificate**;
- the trust/chain status reflects an **untrusted root** (a self-signed
  certificate is not chained to any public CA) — this is the correct,
  expected outcome, not a defect, and must be reported honestly as
  "self-signed, untrusted root" rather than "Valid" in the publicly
  trusted sense.

Both are recorded in `dist/build_manifest.json` exactly as produced —
never overwritten or reworded to imply a stronger trust level than the
certificate actually has.

## 3. Retained for a possible future public/commercial/Store distribution
   (not required or pursued for v1.0)

The publicly trusted signing research from before this amendment is
kept here as candidate reference only:

### 3.1 Candidate: Azure Artifact Signing

Formerly branded "Azure Trusted Signing" — Microsoft's low-cost,
non-Store code-signing service, still in public preview as of this
writing. Advantages for an individual developer: no physical hardware
token required (unlike most traditional OV certificates), and identity
verification happens through Microsoft's own managed flow rather than a
separate CA's paperwork process. Historical research found Basic-tier
pricing of approximately US$9.99/month; the operator must verify current
eligibility, pricing, and identity-verification steps directly at
signup time before relying on any of this, since these are
provider-controlled and change. Official starting points:
`https://learn.microsoft.com/en-us/azure/artifact-signing/` and the
Azure Portal's "Artifact Signing" resource creation flow.

### 3.2 Candidate: a traditional CA certificate

A standard OV (Organization/Individual Validation) code-signing
certificate from any CA in the Microsoft Trusted Root Program (e.g.
SSL.com, Certum, Sectigo — not an exhaustive or ranked list), typically
**$100–700+/year** and, for most providers, requiring either a physical
hardware token or a provider-hosted HSM/cloud-signing add-on.

### 3.3 What the operator must still NOT do, if this is revisited later

Per the loop prompt's authority boundaries: do not paste API keys,
account credentials, private key material, or certificate files into
chat, and do not commit them to this repository under any filename.
`VOCAB_APP_SIGN_COMMAND` and whatever it references belong only in a
local shell environment variable or a CI secret store.

### 3.4 What would need to happen to adopt one later

1. Choose a provider (§ 3.1 or § 3.2) and complete its account/identity
   setup and payment — outside this repository, on the provider's own
   site.
2. Confirm the exact validated certificate subject/publisher name the
   provider issues — it must not be hard-coded as "Peter Shi" if the
   provider validates a different legal identity.
3. Determine the exact CLI signing invocation for the chosen provider
   and set it as `VOCAB_APP_SIGN_COMMAND`, replacing the self-signed
   `Set-AuthenticodeSignature` command.
4. Re-run `python winbuild/build.py`. No code changes are needed — only
   the environment variable changes, since both signing paths use the
   identical hook.
