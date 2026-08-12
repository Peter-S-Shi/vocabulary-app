# Milestone 8 Manual QA Checklist

## Export
- [ ] Export all entries as CSV and XLSX.
- [ ] Export a selected collection and verify position/card columns.
- [ ] Export a selected card and verify only that card is included.
- [ ] Export a selected template.
- [ ] Export collection summary.
- [ ] Confirm an empty collection shows a friendly empty state.

## Import
- [ ] Preview and import a valid General Entry file.
- [ ] Confirm invalid rows are skipped.
- [ ] Verify Skip duplicates and Import anyway.
- [ ] Import each French preset and an existing custom template.
- [ ] Confirm unknown templates and fields are rejected.
- [ ] Append a collection import without changing existing order.
- [ ] Create one new collection explicitly and verify normalized positions.
- [ ] Confirm the same preview cannot be imported twice without re-preview.

## Samples
- [ ] Download each CSV and XLSX sample.
- [ ] Preview each sample in its matching import mode.
- [ ] Download and inspect the current template field map.

## Backup
- [ ] Download and open the SQLite backup.
- [ ] Download and open the full XLSX backup.
- [ ] Preview the XLSX backup and verify no restore button exists.

## Safety
- [ ] Upload and preview without changing database counts.
- [ ] Export and backup without changing database counts.
- [ ] Confirm only explicit import actions write data.
- [ ] Confirm the active database cannot be overwritten from the UI.
