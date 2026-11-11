# DBA Assistant evaluation: iteration1

Mode: retrieval and end-to-end. Questions: 20.

## Summary

| Metric | Value |
| --- | ---: |
| Resolution rate | 100.0% |
| Correct escalation rate | 100.0% |
| False escalation rate | 0.0% |
| Correct behaviour rate | 100.0% |
| Mean key-fact recall | 100.0% |
| Mean citation accuracy | 91.7% |
| Mean faithfulness | 93.3% |
| Judge coverage of non-escalated answers | 100.0% |
| p50 total latency (ms) | 7343.60 |
| p95 total latency (ms) | 12506.73 |
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
| q01 | single-doc | false | 100.0% | true | 10155.50 |
| q02 | single-doc | false | 100.0% | true | 7839.34 |
| q03 | single-doc | false | 100.0% | true | 6799.73 |
| q04 | single-doc | false | 100.0% | true | 7036.00 |
| q05 | single-doc | false | 100.0% | true | 4907.88 |
| q06 | single-doc | false | 100.0% | true | 6575.32 |
| q07 | single-doc | false | 100.0% | true | 5767.76 |
| q08 | single-doc | false | 100.0% | false | 5565.41 |
| q09 | single-doc | false | 100.0% | true | 3996.84 |
| q10 | multi-doc | false | 100.0% | true | 10756.84 |
| q11 | multi-doc | false | 100.0% | true | 8876.38 |
| q12 | multi-doc | false | 100.0% | true | 5486.55 |
| q13 | multi-doc | false | 100.0% | true | 9438.74 |
| q14 | conflict | false | 100.0% | true | 6541.70 |
| q15 | ambiguous | false | — | true | 7651.20 |
| q16 | should-escalate | true | — | — | 12281.48 |
| q17 | should-escalate | true | — | — | 3786.23 |
| q18 | should-escalate | true | — | — | 10352.04 |
| q19 | should-escalate | true | — | — | 16786.47 |
| q20 | should-escalate | true | — | — | 9391.90 |

## Mean node latency

| Node | Mean ms |
| --- | ---: |
| check_grounding | 688.18 |
| escalate | 0.05 |
| finalize | 0.04 |
| generate | 2191.40 |
| grade | 2456.88 |
| retrieve | 2993.88 |
| rewrite | 497.53 |

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

### q01: What SQLSTATE and exact error message indicate too many PostgreSQL connections?

missing citations or citations outside expected docs

Retrieved chunk IDs:
- bm25: postmortem-2026-06-pg-billing-connection-storm#1, runbook-connection-exhaustion#1, reference-postgres-error-codes#1, reference-postgres-error-codes#3, postmortem-2026-06-pg-billing-connection-storm#2
- dense: runbook-connection-exhaustion#0, runbook-connection-exhaustion#1, reference-postgres-error-codes#2, reference-postgres-error-codes#0, runbook-pgbouncer#0
- hybrid: runbook-connection-exhaustion#1, reference-postgres-error-codes#2, reference-postgres-error-codes#1, reference-postgres-error-codes#0, reference-postgres-error-codes#3
- Pipeline (all retrieval passes): runbook-connection-exhaustion#1, reference-postgres-error-codes#2, reference-postgres-error-codes#1, reference-postgres-error-codes#0, reference-postgres-error-codes#3, runbook-deadlocks#1, runbook-pgbouncer#2, reference-postgres-error-codes#4
- Generation sources: runbook-connection-exhaustion#1, reference-postgres-error-codes#2

### q07: How many days of PITR do normal production clusters and pg-analytics retain, and how many months are monthly full backups kept?

missing citations or citations outside expected docs

Retrieved chunk IDs:
- bm25: policy-backup-retention#1, runbook-backup-restore-pitr#1, faq-app-teams#1, onboarding-dba-new-hire#2, runbook-connection-exhaustion#1
- dense: policy-backup-retention#1, runbook-backup-restore-pitr#1, runbook-backup-restore-pitr#0, policy-backup-retention#0, runbook-backup-restore-pitr#3
- hybrid: policy-backup-retention#1, runbook-backup-restore-pitr#1, onboarding-dba-new-hire#2, reference-cluster-inventory#2, runbook-backup-restore-pitr#0
- Pipeline (all retrieval passes): policy-backup-retention#1, runbook-backup-restore-pitr#1, onboarding-dba-new-hire#2, reference-cluster-inventory#2, runbook-backup-restore-pitr#0, runbook-backup-restore-pitr#3, runbook-patroni-failover#1, faq-app-teams#1
- Generation sources: policy-backup-retention#1, runbook-backup-restore-pitr#1, onboarding-dba-new-hire#2

### q08: How do I request routine replica read-only access, what is the role name, and what is the fulfillment time?

unfaithful: The answer incorrectly states that all connections must be made via Teleport, which is not supported by the evidence; while [2] mentions Teleport, [1] specifies using the replica endpoint and port 6432 through pgBouncer without mentioning Teleport, creating a conflict that the answer falsely resolves by combining both.

Retrieved chunk IDs:
- bm25: policy-production-access#2, faq-app-teams#2, faq-app-teams#1, policy-backup-retention#2, policy-production-access#3
- dense: policy-production-access#2, faq-app-teams#2, policy-backup-retention#0, faq-app-teams#1, policy-production-access#0
- hybrid: policy-production-access#2, faq-app-teams#2, faq-app-teams#1, policy-backup-retention#2, policy-production-access#3
- Pipeline (all retrieval passes): policy-production-access#2, faq-app-teams#2, faq-app-teams#1, policy-backup-retention#2, policy-production-access#3, policy-production-access#1, runbook-replication-lag#3, runbook-long-running-queries#1
- Generation sources: policy-production-access#2, faq-app-teams#2

