# Contributing

Thank you for helping improve Vocabulary App.

## Project Principles

- Keep the app local-first.
- Treat user-created and imported content as user-owned data.
- Keep reusable logic outside Streamlit UI files.
- Do not commit personal database files.
- Do not add copyrighted dictionary data, commercial word lists, pronunciation audio, voice models, or AI-generated bulk content.
- Prefer additive and backward-compatible database migrations.
- Preserve import safety: validate, preview, confirm, then write.
- Preserve explicit user control over review scheduling, quiz outcomes, deletion, and learning-pool membership.

## Architecture Rules

- Streamlit code belongs in `app.py` or `src/ui_streamlit/`.
- Core logic belongs in reusable modules under `src/`.
- Core modules must not import Streamlit or access `st.session_state`.
- New features should reuse the existing entry, collection, review, quiz, statistics, import/export, and backup systems.
- Do not create parallel review, quiz, import, or persistence systems.
- SQL and reusable algorithms do not belong in `app.py`.

## Data and Content Safety

- Never commit `data/vocab.db` or another real user database.
- Do not attach personal databases to public issues.
- Use only fictional, self-created, or permission-cleared sample content.
- Do not silently move, overwrite, reset, or delete user data.

## Development Setup

See the installation and run instructions in [README.md](README.md).

Before submitting a change:

1. Compile or run the affected Python modules.
2. Start the Streamlit app.
3. Verify the changed workflow manually.
4. Confirm that existing databases remain compatible.
5. Update relevant documentation and manual QA notes.

## Lifecycle Documentation Closure

After a milestone, repair batch, audit batch, or significant scope decision,
assess and update:

- `PROJECT_STATUS.md`;
- `ROADMAP.md` when lifecycle or scope changes;
- affected QA documentation; and
- README or release notes when user-visible claims change.

This reconciliation is part of completing the work. Do not mark manual QA,
Feature Freeze, Product Hardening, or release acceptance complete without
recorded evidence.
