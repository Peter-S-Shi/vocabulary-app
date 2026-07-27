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

## Local Prompt Drafts

For every new project, create a `.prompt-drafts/` directory for detailed
milestone and development prompt drafts.

For an existing project without this directory, do not create it retroactively
unless requested. Do not inspect or use it during normal development unless the
user explicitly refers to it.

When `.prompt-drafts/` exists:

- add `.prompt-drafts/` to `.gitignore`;
- treat all contents as local-only;
- never stage, commit, push, publish, or include its contents in patches, pull
  requests, releases, or documentation; and
- if any file is already tracked, stop and remove it from Git tracking before
  continuing.
