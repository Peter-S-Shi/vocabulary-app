# Milestone 14 Closure

## Outcome

```text
Milestone 14 Complete on the M14 Draft Branch
Learning Analytics and Insight Core Established
Independent Review and Merge Pending
```

M14 started from synchronized `main` commit
`98b6bc6567bc7bb61284344cd6452eb9cde11457` on branch
`agent/m14-learning-analytics-insight-core`.

Accepted implementation heads:

- Batch A: `290494f328f17b14cf01cd81c47f6a72770510ac`
- Batch B correctness: `1ca61e6714e5bc84cd34a51287d4981c928a9752`
- Batch C implementation: `7b667e578f0f36522ad2d07dfd64574661662165`

M14 completion is a milestone closure only. It is not Feature Freeze, Desktop
Ready, Release Ready, Product Hardening completion, or Current Version
Complete.

## Established architecture

```text
SQLite Quiz evidence
-> src/statistics.py factual measurements
-> src/analytics.py neutral Evidence Profiles and Coverage
-> src/insights.py deterministic Findings, actions, and Learning Brief
-> legacy Entry Health compatibility projection
-> current or future UI
```

Batch A established eligible Quiz evidence, Evidence State, freshness,
performance windows, trajectory, repeated patterns, same-language Personal
Baseline, Card/Collection/Template Coverage, Collection Scope Activity, and
historical Card revision context.

Batch B established exactly one Primary Finding per current Entry, Coverage
Gap Findings, discrete priority, structured read-only actions, same-Card
compatible clustering, Brief-only Coverage hierarchy suppression, category
caps, Recovery diversity, and deterministic Top-5 Brief selection.

Batch C made M14 the Entry-level interpretation authority. Legacy Entry Health
function names remain available but project M14 truth rather than applying a
second Weak/Neglected/Strong/At Risk/Recovery threshold engine. The Streamlit
surface received only the minimum terminology and obsolete-control cleanup
needed to avoid contradicting that authority.

## Integrated acceptance

The deterministic integrated fixture used 100 current synthetic Entries, two
languages, two Templates, three normal Collections, overlapping membership,
Mistake Book and Proficient Pool context, multiple Cards, and mixed evidence
archetypes. It used no personal database or user content.

Entry Primary Finding counts:

| Finding | Count |
|---|---:|
| Never Quizzed | 90 |
| Insufficient Evidence | 2 |
| None | 1 |
| Needs Attention | 2 |
| Recovery | 1 |
| Strength | 3 |
| Stale Evidence | 1 |
| **Total** | **100** |

The fixture produced 15 valid Coverage Gap Findings. Its deterministic Brief
contained:

1. High Needs Attention / focused practice;
2. High Needs Attention / focused practice;
3. High Collection Breadth Gap / quiz uncovered content;
4. High Collection Breadth Gap / quiz uncovered content; and
5. Medium Stale Evidence / verify knowledge.

Recovery remained outside this Brief because five High/Medium candidates were
already selected. This is the frozen diversity rule, not a missing positive
signal. Scope-level Coverage Gaps represented the large Never Quizzed and
Insufficient populations without deleting their individual Full Findings.

Repeated execution with the same database and reference date produced
identical Findings, priorities, clusters, actions, counts, and Brief ordering.
Durable learning-table counts were identical before and after analysis.

## Compatibility and historical acceptance

- Personal Baseline remained same-language, target-excluding, bounded, and
  contextual; relative comparison did not override absolute performance.
- Collection Content Knowledge used all eligible evidence for current members.
- Collection Scope Activity remained attached to
  `quiz_sessions.collection_id` after current membership removal.
- Current Card coverage used current membership while historical Card context
  used the stored `card_revision_id` composition.
- Hard-deleted Entries disappeared from current Profiles, Findings, Coverage,
  and Brief targets while preserved Quiz log Entry IDs and snapshots remained.
- Proficient Pool and Mistake Book membership remained context only and was not
  mutated by analytics.
- Existing M11 stable identity/history and M13 portability/migration behavior
  remained covered by the full regression suite.

## Verification

```text
Focused M14 Batch C tests: 5/5
Focused M14 Batch A tests: 11/11
Focused M14 Batch B tests: 17/17
Existing M11/M13 tests: 87/87
Full repository suite: 120/120
Compile/static check: passed
Architecture audit: passed, 36 Python files, no warnings
Packaging readiness: passed with expected ignored local-database warning
Privacy/tracked-file audit: passed
```

GitHub-hosted status checks were not configured at verification time. The
results above are local automated verification, distinct from the required
independent review of the Draft PR.

## Persistence and migration status

```text
schema changed: NO
migration added: NO
app data version changed: NO
persisted analytics state added: NO
learning-state mutation added: NO
```

## Accepted M14 v1 limitations

- no persisted insight or transition history;
- no newly-Strong notification history;
- no global learning score;
- no AI/LLM judgment or wording dependency;
- no automatic pool, status, due-date, Card, or Collection mutation;
- no overdue insight backlog;
- no advanced statistical significance model;
- no quiz-type difficulty weighting;
- no mathematically decayed forgetting score; and
- no desktop-native analytics presentation yet.

These are accepted scope limits, not M14 closure blockers.

## Next gate

The existing M14 Draft PR must receive product-owner and independent review
before merge. Do not merge automatically and do not begin M15 from this closure
record alone. After M14 is accepted and merged, the Roadmap next milestone is
M15 — Audio Foundation.
