---
title: PostgreSQL Error Code Routing
doc_type: reference
owner: DBA Operations
last_reviewed: 2026-09-16
status: current
---
# PostgreSQL Error Code Routing

## Routing table

Use the five-character SQLSTATE from the driver or server log. Message text can vary by context; preserve the code, timestamp, cluster, and application name when opening a ticket. The table identifies the first useful runbook, not an automatic severity assignment.

| SQLSTATE | Meaning | Runbook to use |
| --- | --- | --- |
| 40P01 | deadlock_detected | runbook-deadlocks.md |
| 53300 | too_many_connections | runbook-connection-exhaustion.md |
| 57014 | query_canceled | runbook-long-running-queries.md |
| 23505 | unique_violation | runbook-deadlocks.md, transaction handling guidance; application owner diagnoses duplicates |
| 55P03 | lock_not_available | runbook-long-running-queries.md, blocker inspection |
| 53100 | disk_full | runbook-disk-full-wal.md |
| 40001 | serialization_failure | runbook-deadlocks.md, whole-transaction retry guidance |
| 08006 | connection_failure | runbook-pgbouncer.md, then runbook-patroni-failover.md if leadership changed |
| 25P02 | in_failed_sql_transaction | runbook-deadlocks.md, rollback guidance; investigate the original error |

## Interpret context

SQLSTATE 57014 can result from the application statement_timeout or an explicit cancellation. The normal application limit is 15min; analytics_ro is exempt. Inspect the original statement and session context before changing a timeout. For 25P02, issue `ROLLBACK;` and find the preceding failure rather than repeatedly issuing statements inside the aborted transaction.

Unique violations usually require application investigation of business keys or duplicate delivery. They do not by themselves indicate a deadlock. Serialization failures require a bounded retry of the entire transaction, with attention to idempotent side effects. A connection failure after sending a write can leave its outcome uncertain; check application identifiers before retrying blindly.

## Escalation

Apply customer impact and the relevant alert threshold to select severity. Deadlocks are not a DBA page unless >50 deadlocks/min. Route non-urgent questions to #dba-help and production pages to PagerDuty DBA-Primary. Exclude customer values from diagnostic excerpts.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
