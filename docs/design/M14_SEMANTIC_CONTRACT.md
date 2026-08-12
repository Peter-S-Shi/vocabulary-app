# M14 Semantic Contract v1

Status: **Frozen**

This document records the durable product semantics for Milestone 14 —
Learning Analytics and Insight Core. It is the implementation authority for
M14 and is not a record of the design conversation.

## Purpose and boundaries

M14 evaluates the strength, freshness, and coverage of learning evidence. It
does not assign a global learner score, infer mastery from browsing, revive
legacy SRS scheduling, require AI, or mutate learning state.

The layers remain separate:

```text
durable SQLite evidence
-> factual Statistics
-> neutral Analytics
-> deterministic Findings and actions
-> capped Learning Brief
```

`src/statistics.py` remains the factual measurement layer.
`src/analytics.py` owns Evidence Profiles and neutral classifications.
`src/insights.py` owns Findings, actions, clustering, and Brief selection.
Core modules must remain independent of Streamlit.

## Authoritative evidence

Entry performance evidence comes from `quiz_item_logs`. An eligible attempt
has `is_correct IN (0, 1)`. Unknown correctness is excluded. Explicitly
answered Items may contribute even if their parent Quiz session is incomplete
or cancelled; that session must not become Card completion.

A completed Card-scoped Quiz remains the authoritative Card completion event.
Review browsing is exposure or preparation only and cannot prove knowledge,
Strength, Needs Attention, or Card completion.

Evidence ordering is deterministic by `answered_at`, then Quiz Item log ID.
Time-sensitive analysis accepts an injectable `as_of_date`; production may
default to today. Attempts after the reference date are not current evidence.

## Identity and history

- Entry identity is `entries.id` / `entry_id`.
- Card identity is stable `card_id`.
- Mutable Card composition is identified by `card_revision_id`.
- Current Card coverage uses current `entry_collections.position` and
  `collections.card_size` grouping.
- Historical Card interpretation uses the stored historical revision.
- Unknown legacy Card composition remains unknown and is never silently
  reconstructed from current membership.
- Deleted Entry logs and revision membership remain historical evidence, but
  deleted Entries are excluded from current Evidence Profiles and Coverage.

## Evidence State

Evidence quantity and freshness are separate. Use the highest satisfied state:

| State | Gate |
|---|---|
| `none` | 0 attempts |
| `sparse` | Evidence exists but the developing gate is not satisfied |
| `developing` | at least 3 attempts and 2 sessions |
| `sufficient` | at least 5 attempts and 3 sessions |
| `strong` | at least 8 attempts, 4 sessions, and 2 days |

## Freshness

| State | Latest eligible attempt age |
|---|---:|
| `fresh` | 0–30 days |
| `aging` | 31–89 days |
| `stale` | 90 or more days |
| `unavailable` | no eligible attempt |

Freshness does not decay historical accuracy.

## Performance, windows, and trajectory

Performance bands are analytical classifications:

| State | Accuracy |
|---|---:|
| `positive` | at least 80% |
| `mixed` | 60–79% |
| `negative` | below 60% |
| `unavailable` | the applicable evidence gate is not satisfied |

Overall performance requires at least `sufficient` evidence. The Recent Window
is the last five eligible attempts. The Prior Window is the immediately
preceding five attempts. Each window requires at least three attempts across
at least two sessions.

Trajectory is the Recent accuracy minus Prior accuracy:

- `improving`: at least +20 percentage points;
- `declining`: at most -20 percentage points;
- `stable`: inside those boundaries; and
- `unavailable`: either window is ineligible.

Repeated recent errors require at least three wrong answers in the Recent
Window across at least two sessions. Repeated recent success requires at least
four correct answers across at least two sessions.

## Personal Baseline

Personal Baseline is contextual and never overrides absolute performance. The
comparator:

- uses the same language;
- excludes the target Entry, or all current Entries in the target Collection
  or Template when that scope is analyzed;
- uses at most the 50 most recent eligible comparator attempts; and
- requires at least 20 attempts, 5 sessions, and 3 days.

No cross-language fallback is allowed. Relative comparison is
`above_baseline` at +15 percentage points or more, `below_baseline` at -15
points or less, and `near_baseline` otherwise. It is `unavailable` when the
comparator gate or target accuracy is unavailable. For an Entry-level
comparison, the target Entry must also have at least `sufficient` Evidence
State. A sparse or developing target may still expose available comparator
metadata, but its comparison remains `unavailable` and its delta remains null.

## Coverage and Collection meanings

Coverage concerns current Entries only.

Touched Coverage is the proportion with at least one eligible Quiz attempt:

- 0%: `none`;
- 1–49%: `limited`;
- 50–79%: `partial`;
- at least 80%: `broad`.

Interpretable Coverage is the proportion with Evidence State at least
`sufficient`:

- 0%: `none`;
- 1–29%: `limited`;
- 30–59%: `partial`;
- at least 60%: `substantial`.

Both expose an independent 100% complete flag. Empty scopes are
`unavailable`, not 0% learning progress.

For a Collection, Content Knowledge uses all eligible evidence for its current
Entries, regardless of the Collection context in which an attempt occurred.
Scope Activity measures eligible Quiz Items actually answered under that
Collection context. These meanings must not be merged into one metric.

## Findings and arbitration

At one analysis time, each current Entry receives at most one Primary Finding:

```text
Never Quizzed
Insufficient Evidence
Stale Evidence
Recovery
Needs Attention
Strength
None
```

The order above is the arbitration order. `None` is valid.

- Never Quizzed: no eligible attempts.
- Insufficient Evidence: attempts exist but Evidence State is below
  `sufficient`.
- Stale Evidence: at least sufficient evidence and stale freshness. Stale
  performance and trajectory remain historical context, not current reasons.
- Recovery: eligible Prior and Recent Windows move from negative to positive,
  trajectory improves, and repeated recent success is present.
- Needs Attention: eligible Recent Window is negative and has repeated recent
  errors.
- Strength: strong, non-stale evidence; positive overall and Recent
  performance; repeated recent success; and no declining trajectory.

Mistake Book, Proficient Pool, and Starred membership are auxiliary context.
They do not change evidence sufficiency or independently prove ability.

## Coverage Gaps, actions, and Brief

Coverage Gap Findings belong to Card, Collection, or Template scopes.
Breadth Gap means Touched Coverage below 80%. Evidence Depth Gap means Touched
Coverage at least 80% and Interpretable Coverage below 60%.

Actions are recommendations only. M14 must not automatically change Entry
status, pool membership, due dates, Collection membership, Card order, or start
a Quiz.

Full Findings and the Learning Brief are separate. The Brief is a deterministic
selection of no more than five items and may be empty. Same-Card compatible
Entry Findings may cluster, but aggregation does not escalate to a whole-Card
workflow. Cluster priority ranks the cluster and never rewrites member
priority. Coverage hierarchy suppression affects only the Brief; Full Findings
retain every valid gap, and a healthy parent cannot hide a more severe child.
Recovery diversity promotion may replace only a Low-priority candidate and
never a High or Medium candidate.

## Frozen semantic locks

1. Evidence State uses the highest satisfied level.
2. Deleted Entries do not participate in current actionable analytics.
3. Finding aggregation does not automatically escalate to whole-Card workflow.
4. Recovery diversity promotion does not displace High or Medium Findings.
5. M14 is the Entry-level interpretation authority; Entry Health becomes a
   compatibility projection.
6. Cluster priority does not rewrite supporting Entry priority.
7. Stale performance and trajectory are historical context when Stale Evidence
   wins arbitration.
8. Coverage hierarchy suppression applies only to the Brief.

## Persistence and compatibility

M14 v1 is read-only. It adds no schema migration, persisted Evidence Profile,
Finding history, learning score, or parallel database. Existing Entry Health
API names remain available as compatibility projections over M14 Evidence
Profiles and Primary Findings. They do not retain an independent Weak,
Neglected, Strong, At Risk, or Recovery threshold engine.
