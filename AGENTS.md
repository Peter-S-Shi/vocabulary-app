# Repository Instructions

## GitHub Privacy Rule

Before preparing, committing, pushing, uploading, or publishing content for
Git/GitHub, always perform a privacy and secret-safety check.

Never commit or expose:

- personal information, including real names, emails, phone numbers, addresses,
  account IDs, or school/work/immigration/financial details;
- local machine details, including absolute local paths, local usernames,
  computer names, personal folders, or IDE metadata;
- secrets, including API keys, tokens, passwords, cookies, private keys,
  `.env` files, or credentials; or
- local-only data, including SQLite databases, personal CSV/XLSX exports,
  backups, logs, caches, virtual environments, Python bytecode, or editor data.

Before any commit or push:

1. Check `git status`.
2. Review `git diff` and `git diff --staged`.
3. Verify `.gitignore` protects virtual environments, environment files, Python
   caches, SQLite databases, OS metadata, and local generated files.
4. Search for local paths, secrets, real emails, personal identifiers, and real
   user data.
5. Stop if anything sensitive is found. Remove, anonymize, ignore, or untrack it
   before continuing.

Use only synthetic examples and generic paths in documentation, screenshots,
samples, commit messages, issues, and pull requests. Treat GitHub as public by
default.

## Response Style

Be concise. Provide conclusions, essential rationale, and actions without
chain-of-thought, greetings, or routine apologies.

## Human UI Acceptance Delivery Pattern

Applies to every UI checkpoint from Milestone 17 onward (M17/M18/M19).

Automated tests cannot establish visual quality. The M17 Today checkpoint
passed engineering and architecture review, and every structural test was
green, while the product still visually read as default Qt widgets — the
failure was only caught by a human looking at a real window. Human visual
acceptance is therefore a required gate, and reaching that gate is the
agent's job, not the reviewer's.

When implementation, verification, commit, and push for a UI checkpoint
are complete, do **not** finish by asking the reviewer to launch the app
themselves. Before handing off the human-acceptance gate:

1. remain on the checkpoint's development branch — do not switch back to
   `main` before launching;
2. verify local `HEAD` matches the just-pushed checkpoint SHA (and the
   remote branch);
3. launch the real native application from that branch using the
   repository's desktop runtime (`.venv`, `python -m src.ui_desktop`);
4. leave the application window open for inspection;
5. confirm a visible top-level window actually exists rather than assuming
   the process started successfully;
6. report the branch and the exact head SHA being displayed; then
7. stop and wait for an explicit human PASS / FAIL.

Do not substitute screenshots, headless/offscreen runs, or instructions
telling the reviewer to run CLI commands. If the launch fails, diagnose
and fix the launch/environment problem before handing off the gate — a
failed launch is the agent's defect to resolve, not the reviewer's.

Never capture the operator's screen to produce this evidence.

## Local Prompt Drafts

For every new project, create a `.prompt-drafts/` directory for detailed
milestone and development prompt drafts.

For an existing project without this directory, do not create it retroactively
unless requested. Do not inspect or use it during normal development unless the
user explicitly refers to it.

When `.prompt-drafts/` exists:

- add `.prompt-drafts/` to the repository-local `.git/info/exclude`, not the
  shared `.gitignore`;
- treat all contents as local-only;
- never stage, commit, push, publish, or include its contents in patches, pull
  requests, releases, or documentation; and
- verify with `git check-ignore -v -- .prompt-drafts/` that the local exclude
  rule applies;
- verify with `git ls-files -- .prompt-drafts` that no prompt draft is tracked;
  and
- if any file is already tracked, stop and ask for explicit approval before
  removing it from Git tracking.
