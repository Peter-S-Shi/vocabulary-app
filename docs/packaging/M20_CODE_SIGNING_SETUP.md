# M20 Code Signing Setup

Companion to `docs/packaging/M20_RELEASE_CONTRACT.md` § 2.7 and the
`M20_AUTONOMOUS_RELEASE_ENGINEERING_LOOP.md` prompt § 9. Records exactly
what remains before the v1.0 RC/public installer can carry a real,
publicly trusted Authenticode signature, and exactly what
`winbuild/build.py` needs from the operator once a provider is chosen.

**Frozen (not open for reconsideration here):** the installer must be
signed before final public release. **Not frozen, and the subject of
this document:** which provider, and the account/certificate setup that
requires the operator's own identity, payment, and judgment — none of
which this agent can or should do autonomously.

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
- **Verified end-to-end** (not just written, actually run) against a
  locally-generated, non-trusted self-signed test certificate: created
  a throwaway code-signing certificate with PowerShell's
  `New-SelfSignedCertificate`, pointed `VOCAB_APP_SIGN_COMMAND` at a
  `Set-AuthenticodeSignature` wrapper script, ran a full
  `winbuild/build.py` build, and confirmed the manifest correctly
  recorded the signed `.exe` and the exact (expected-untrusted)
  signature status/subject read back from the file. The test
  certificate and script were deleted afterward; nothing from that test
  is committed. This proves the wiring — swapping in a real trusted
  signing command needs no code changes, only the environment variable.
- No secret, credential, certificate, or provider-specific tool
  invocation is hard-coded anywhere in this repository. The signing
  command itself (which may reference a certificate thumbprint, a cloud
  account, or a hardware token) lives only in the operator's own build
  environment/CI secret store, never committed.

## 2. What genuinely requires the operator

Nothing below can be done by an autonomous agent: it requires the
operator's real-world identity, a payment method, and a judgment call
about which provider fits their budget and country of residence.

### 2.1 Recommended starting point: Azure Artifact Signing

Formerly branded "Azure Trusted Signing" — Microsoft's low-cost,
non-Store code-signing service, still in public preview as of this
writing. Advantages for an individual developer: no physical hardware
token required (unlike most traditional OV certificates), and identity
verification happens through Microsoft's own managed flow rather than a
separate CA's paperwork process.

**The operator must verify directly, at signup time, before relying on
any of this** — these details are provider-controlled and change:

- current eligibility for *individual* (not organization) identity
  validation, including which countries/regions currently qualify;
- current Basic-tier pricing (Microsoft's own pricing page does not
  publish a committed figure at the time of this document; Phase A's
  earlier research found approximately US$9.99/month, but treat that as
  historical evidence, not a quote);
- exactly which documents/verification steps the individual identity
  path requires today.

Official starting points: `https://learn.microsoft.com/en-us/azure/artifact-signing/`
and the Azure Portal's "Artifact Signing" resource creation flow.

### 2.2 Fallback: a traditional CA certificate

If individual-developer eligibility for Azure Artifact Signing does not
work out (geography, timing, or preview-service risk tolerance), a
standard OV (Organization/Individual Validation) code-signing
certificate from any CA in the Microsoft Trusted Root Program (e.g.
SSL.com, Certum, Sectigo — not an exhaustive or ranked list) remains a
viable alternative, typically **$100–700+/year** and, for most
providers, requiring either a physical hardware token or a
provider-hosted HSM/cloud-signing add-on. Compare current offerings at
signup time; do not assume last year's pricing or process still holds.

### 2.3 What the operator must NOT do here

Per the loop prompt's authority boundaries: do not paste API keys,
account credentials, private key material, or certificate files into
chat, and do not commit them to this repository under any filename.
`VOCAB_APP_SIGN_COMMAND` and whatever it references belong only in a
local shell environment variable or a CI secret store.

## 3. Minimum operator action to unblock signing

1. Choose a provider (§ 2.1 or § 2.2) and complete its account/identity
   setup and payment — outside this repository, on the provider's own
   site.
2. Confirm the exact validated certificate subject/publisher name the
   provider issues. Per the Release Contract, this is whatever identity
   the provider actually validates — it must not be hard-coded as
   "Peter Shi" if the provider validates a different legal identity;
   the public portfolio/author identity may still say "Peter Shi"
   regardless of what the certificate itself says.
3. Determine the exact CLI signing invocation for the chosen provider
   (e.g. `AzureSignTool sign -kvu ... -kvc ... -tr ... -td sha256 {file}`
   for Azure Artifact Signing, or `signtool.exe sign /sha1 <thumbprint>
   /tr ... /td sha256 {file}` for a traditional CA with a local/HSM
   certificate) and set it as `VOCAB_APP_SIGN_COMMAND` in the build
   environment.
4. Re-run `python winbuild/build.py`. It will sign both artifacts
   automatically and report the verified signature status in
   `dist/build_manifest.json` — no further code changes needed.

## 4. What happens automatically afterward

Once `VOCAB_APP_SIGN_COMMAND` is set correctly, every future
`winbuild/build.py` run signs and verifies both the payload `.exe` and
the installer `.exe`, and the RC Engineering Exit Candidate report can
quote the manifest's real `Valid` status and certificate subject
directly, alongside the independently-recorded SHA-256 of the release
asset.
