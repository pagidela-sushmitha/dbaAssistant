# DBA Assistant evaluation: baseline

Mode: retrieval and end-to-end. Questions: 20.

## Summary

| Metric | Value |
| --- | ---: |
| Resolution rate | 100.0% |
| Correct escalation rate | 100.0% |
| False escalation rate | 0.0% |
| Correct behaviour rate | 100.0% |
| Mean key-fact recall | 100.0% |
| Mean citation accuracy | 100.0% |
| Mean faithfulness | 93.3% |
| Judge coverage of non-escalated answers | 100.0% |
| p50 total latency (ms) | 10854.59 |
| p95 total latency (ms) | 21906.32 |
| Pipeline errors | 0.00 |

## Retrieval comparison

| Mode | Questions | Hit@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| bm25 | 14 | 100.0% | 0.93 |
| dense | 14 | 100.0% | 0.92 |
| hybrid | 14 | 100.0% | 1.00 |

A retrieval hit means any expected document appears in the first five chunks. MRR uses the first relevant chunk in those same five results. Multi-document hits do not imply complete evidence coverage.

## Per-question results

| ID | Category | Escalated | Key-fact recall | Faithful | Latency (ms) |
| --- | --- | --- | ---: | --- | ---: |
| q01 | single-doc | false | 100.0% | true | 6566.60 |
| q02 | single-doc | false | 100.0% | true | 22655.07 |
| q03 | single-doc | false | 100.0% | true | 8428.38 |
| q04 | single-doc | false | 100.0% | true | 17093.12 |
| q05 | single-doc | false | 100.0% | true | 13729.64 |
| q06 | single-doc | false | 100.0% | true | 18889.51 |
| q07 | single-doc | false | 100.0% | true | 11144.11 |
| q08 | single-doc | false | 100.0% | true | 10633.60 |
| q09 | single-doc | false | 100.0% | true | 4707.38 |
| q10 | multi-doc | false | 100.0% | true | 13401.59 |
| q11 | multi-doc | false | 100.0% | true | 9054.32 |
| q12 | multi-doc | false | 100.0% | false | 6393.66 |
| q13 | multi-doc | false | 100.0% | true | 21866.91 |
| q14 | conflict | false | 100.0% | true | 9585.37 |
| q15 | ambiguous | false | — | true | 7319.19 |
| q16 | should-escalate | true | — | — | 13487.82 |
| q17 | should-escalate | true | — | — | 7780.00 |
| q18 | should-escalate | true | — | — | 5016.65 |
| q19 | should-escalate | true | — | — | 11075.59 |
| q20 | should-escalate | true | — | — | 16517.51 |

## Mean node latency

| Node | Mean ms |
| --- | ---: |
| check_grounding | 650.10 |
| escalate | 0.02 |
| finalize | 0.03 |
| generate | 3385.98 |
| grade | 2740.33 |
| retrieve | 5672.87 |
| rewrite | 459.09 |

## Scoring notes

- The ambiguous question allows a short overview or clarification and has no key-fact or expected-document score.
- Empty fact lists are unscored. Escalated answerable cases receive zero key-fact recall; drafted escalation notes do not count as factual answers.
- Fact checks use literal case-insensitive substrings, so correct paraphrases may miss them. Expected documents are an explicit benchmark, not a semantic citation-support judge.
- Citation accuracy counts distinct cited documents, on non-escalated answers with expected docs; missing citations score zero.
- Faithfulness uses the main model and the actual generation sources. Escalations are skipped; judge errors are unscored and listed as failures. Judge coverage prevents hidden judge failures.
- Faithfulness is an automated model judgement; review the listed reasons against the source documents before treating a flagged answer as an established defect.
- Total latency covers ask(), excluding Part A and the separate faithfulness judge. Node means use only questions that executed the node; repeated-node times are accumulated by the pipeline.
- Retrieval-only mode uses query embeddings for dense/hybrid search but makes no generative LLM calls.

## Failures

### q12: It's 2am and an inactive replication slot is filling the disk — what approvals do I need to drop it, and when is the emergency change ticket due?

unfaithful: The answer incorrectly states that both on-call DBA lead and engineering manager approval are required to drop a slot, but source [1] says only slot owner or on-call DBA lead approval is needed under an emergency change. Source [2] requires both approvals for emergency changes generally, but source [1] provides a specific exception for slot dropping, and the answer fails to reconcile this conflict accurately.

Retrieved chunk IDs:
- bm25: runbook-disk-full-wal#2, policy-change-management#3, policy-oncall-escalation#2, postmortem-2026-03-pg-orders-outage#2, policy-production-access#3
- dense: postmortem-2026-03-pg-orders-outage#4, policy-oncall-escalation#0, runbook-disk-full-wal#2, policy-change-management#3, runbook-replication-lag#3
- hybrid: runbook-disk-full-wal#2, policy-change-management#3, postmortem-2026-03-pg-orders-outage#4, policy-production-access#2, postmortem-2026-03-pg-orders-outage#1
- Pipeline (all retrieval passes): runbook-disk-full-wal#2, policy-change-management#3, postmortem-2026-03-pg-orders-outage#4, policy-production-access#2, postmortem-2026-03-pg-orders-outage#1, policy-oncall-escalation#0, policy-oncall-escalation#2, postmortem-2026-03-pg-orders-outage#2
- Generation sources: runbook-disk-full-wal#2, policy-change-management#3, postmortem-2026-03-pg-orders-outage#4, postmortem-2026-03-pg-orders-outage#2

