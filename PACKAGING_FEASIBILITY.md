# Packaging Feasibility

## 1. Current App Form

Vocabulary App is a local Streamlit application launched with:

```powershell
python -m streamlit run app.py
```

It uses a local SQLite database and is not a hosted SaaS product. The current form is transparent and suitable for development, personal use, demonstrations, and an early public GitHub release.

## 2. Distribution Options

### Option A: Developer / Power User Setup

Users clone or download the repository, create a virtual environment, install requirements, and run Streamlit.

**Advantages**

- Simplest and most reproducible GitHub release
- Transparent dependencies and startup process
- Easy to inspect and debug
- No platform-specific packaging layer

**Limitations**

- Requires Python and command-line use
- Dependency setup is unfamiliar to non-technical users
- Does not feel like a conventional installed application

**Suitability:** the current credible distribution path after Milestone 11
Product Hardening and Milestone 12 release-candidate acceptance.

### Option B: Local Script Launcher

A future `.bat`, `.ps1`, or shell script could check the environment and launch Streamlit.

**Advantages**

- Reduces repeated command-line steps
- Small implementation and maintenance cost
- Useful for personal or controlled Windows deployment

**Limitations**

- Still requires Python and installed dependencies
- Scripts differ across operating systems
- The UI remains a browser-based local Streamlit session
- Error handling and environment setup require care

**Suitability:** reasonable optional convenience after the current release
passes Product Hardening and release-candidate acceptance.

### Option C: PyInstaller or Executable Wrapper Around Streamlit

Streamlit can be investigated inside a packaged runtime, but it still expects server startup, static assets, a browser or embedded webview, and a large Python dependency set.

**Advantages**

- May reduce visible command-line setup
- Can support controlled personal distribution
- Preserves the current UI

**Limitations**

- Large executable and build output
- Hidden imports and Streamlit assets may be fragile
- Local server/browser behavior remains
- Antivirus and Windows path behavior can complicate support
- Packaged failures are harder to diagnose
- User-data paths must be separated from read-only application files

**Suitability:** feasibility experiment only; do not force it into the main distribution path yet.

### Option D: Future Desktop GUI

Replace the Streamlit UI with PySide6 or PyQt while retaining core modules and SQLite.

**Advantages**

- Conventional desktop windows, menus, dialogs, and navigation
- Better control over local data paths and lifecycle
- Native file selection for import/export and backup
- More predictable packaging as a desktop product

**Limitations**

- Requires rebuilding every UI workflow
- Needs desktop interaction and visual design work
- Quiz state, dense tables, and confirmation flows require explicit controllers
- Full parity must be tested before Streamlit can be retired

**Suitability:** strongest medium-term product path after workflow and schema stability.

## 3. Recommended Current-Release Path

For the current Streamlit source release:

1. Keep Streamlit as the MVP/local interface.
2. Complete Feature Complete Review and explicitly pass Feature Freeze.
3. Complete Milestone 11 Product Hardening and full-product acceptance.
4. Complete Milestone 12 clean-environment and release-candidate verification.
5. Publish a clean, documented, reproducible source release.
6. Consider launch scripts only as an optional later convenience.
7. Do not spend substantial effort forcing Streamlit into a polished executable.

## 4. Recommended Medium-Term Path

After workflows and migrations are stable, build a small PySide6/PyQt desktop shell that opens an existing database, shows Today, and lists entries.

Use that prototype to validate architecture and interaction quality before committing to a full UI migration.

## 5. Packaging Risk Checklist

- [ ] Python and native dependency size measured
- [ ] Clean environment build is reproducible
- [ ] Streamlit static assets and hidden imports included
- [ ] Local server startup and shutdown controlled
- [ ] Browser or webview launch behavior defined
- [ ] Application files separated from writable user data
- [ ] SQLite database path uses a user-data directory
- [ ] Existing project database migration is explicit and backed up
- [ ] Import/export and backup locations use safe file dialogs
- [ ] Windows, macOS, and Linux differences documented
- [ ] Logs avoid exposing personal learning content
- [ ] Upgrade and rollback behavior tested
- [ ] No private files included in build artifacts

## 6. What Must Never Be Packaged

Public builds and release archives must not include:

- personal `data/vocab.db`
- user backups
- user exports or imported CSV/XLSX files
- `.env` files, API keys, or secrets
- copyrighted word lists or dictionary datasets
- pronunciation audio libraries
- voice/TTS models
- AI model weights or generated bulk datasets

Only fictional, self-created, permission-cleared sample files may be distributed.

## Decision

Developer/power-user source setup is the current credible distribution model,
subject to Feature Freeze, Product Hardening, full regression/manual
acceptance, and release-candidate verification. No native installer or
standalone desktop executable currently exists. A Streamlit executable wrapper
remains a feasibility experiment, while PySide6/PyQt is the stronger
medium-term path after the current release lifecycle is complete.
