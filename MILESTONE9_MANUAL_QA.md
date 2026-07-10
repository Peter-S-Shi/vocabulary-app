# Milestone 9 Manual QA

Use a disposable test database or back up `data/vocab.db` before tests that create learning records. Do not delete the active database for this checklist.

## 1. Startup and Empty States

- [ ] A fresh app session opens on `Today`.
- [ ] With no entries, Today explains how to start and `Open Entries` navigates correctly.
- [ ] With entries but no normal collections, Today recommends creating a collection.
- [ ] With collections but no review states, Today recommends syncing cards from Review.
- [ ] No empty or partially configured database state causes an exception.

## 2. Today Structure

- [ ] Sections appear in this learning order: suggested next action, review, quiz, special pools, summary, shortcuts.
- [ ] Counts reflect the local database and do not imply content has been verified externally.
- [ ] No due-card state offers optional practice without implying that mistakes are required.
- [ ] Empty Mistake Book is presented positively.
- [ ] Empty Proficient Pool explains that mastered entries can be added from Entries Select Mode.

## 3. Review Focus

- [ ] A due or overdue card appears on Today.
- [ ] `Start Today's Review` opens Review with the intended card focused.
- [ ] Focusing a card does not create a review log or change `next_due_at`.
- [ ] The schedule changes only after an explicit Review scheduling action.
- [ ] `Back to Today` returns to Today.

## 4. Quiz Focus

- [ ] Quiz suggestions appear only when their source data exists.
- [ ] A Today quiz action opens Quiz with the intended collection, card, and type when available.
- [ ] Focus navigation does not create a quiz session or item log.
- [ ] An active quiz is not silently cancelled or overwritten.
- [ ] Quiz logs and entry counts change only after an answer is submitted.
- [ ] `Back to Today` returns to Today.

## 5. Daily Summary

- [ ] Explicit review actions update reviewed-card and reviewed-entry counts.
- [ ] Submitted quiz answers update attempts, correct, wrong, and accuracy values.
- [ ] Completed-session counts match existing quiz session logs.
- [ ] Mistake recovery and Proficient Pool failure details appear only when supported by logs.
- [ ] The app uses today's local date consistently across the summary.
- [ ] Reloading Today does not create or modify learning records.

## 6. Navigation

- [ ] Sidebar order starts with Today, Entries, Collections, Review, Quiz, and Statistics.
- [ ] Today shortcuts open Review, Quiz, Review Calendar, and Entry Health.
- [ ] Review, Quiz, and Statistics use the consistent `Back to Today` wording.
- [ ] Review History / Schedule remains directly available from the sidebar.

## 7. Non-Regression

- [ ] Entries add, search, edit, select, and delete workflows still work.
- [ ] Collections create, reorder, remove-entry, and delete workflows still work.
- [ ] Review works independently of Today.
- [ ] Quiz works independently of Today.
- [ ] Statistics tabs load without changing data.
- [ ] Import preview, confirmed import, export, backup, and restore preview still work.
- [ ] Existing user data opens without a schema reset.

## 8. Architecture and Product Boundaries

- [ ] `src/learning_workflow.py` imports no Streamlit modules.
- [ ] Workflow helpers return plain Python data and perform read-only queries.
- [ ] `src/ui_streamlit/today_page.py` contains no raw SQL.
- [ ] Today does not duplicate review scheduling or quiz generation logic.
- [ ] `app.py` contains routing and initialization only.
- [ ] No dictionary, pronunciation, audio, TTS, AI-content, cloud, or external language-content dependency was introduced.
