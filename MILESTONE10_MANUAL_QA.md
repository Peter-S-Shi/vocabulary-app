# Milestone 10 Manual QA

## Milestone 10.6 Software Update Compatibility

- [ ] Fresh database initializes successfully.
- [ ] Existing database opens without data loss.
- [ ] `app_metadata` table exists.
- [ ] `schema_version` is visible in Settings / Data.
- [ ] `app_data_version` is visible in Settings / Data.
- [ ] `last_migration_at` is visible in Settings / Data.
- [ ] Feature flags are disabled by default.
- [ ] Running the app multiple times does not duplicate migrations.
- [ ] Existing entries still search and display correctly.
- [ ] Existing collections still show card groups correctly.
- [ ] Existing review and quiz pages still work.
- [ ] `SOFTWARE_UPDATE_POLICY.md` exists and is accurate.

## Milestone 10.7 Productization Closure

- [ ] README reflects the current local-first, user-owned product identity.
- [ ] README does not imply built-in dictionary, pronunciation, audio, or AI content.
- [ ] Architecture documentation keeps Streamlit isolated to `app.py` and `src/ui_streamlit/`.
- [ ] Settings / Data shows local path and compatibility information clearly.
- [ ] Import / Export still follows Upload -> Validate -> Preview -> Confirm -> Import.
- [ ] Backup remains user-controlled.
- [ ] Restore-lite remains preview-only.
- [ ] Today page loads.
- [ ] Review page loads.
- [ ] Quiz page loads.
- [ ] Statistics page loads.
- [ ] Import / Export page loads.
- [ ] Settings / Data page loads.
- [ ] No personal database, import workbook, export file, or backup file is committed.
- [ ] `.gitignore` protects local databases, virtual environments, secrets, exports, and backups.
