---
title: PostgreSQL Connection Exhaustion
doc_type: runbook
owner: DBA Operations
last_reviewed: 2026-09-22
status: current
---
# PostgreSQL Connection Exhaustion

## Symptoms and limits

SQLSTATE 53300, "sorry, too many clients already", indicates connection exhaustion. PgConnectionsHigh alerts at 80% utilization. All apps must use pgBouncer 1.23 on port 6432. The pool figures below are the default per database/user server pool sizes; budget aggregate pools against each cluster's connection limit and administrative reserve.

| Cluster | max_connections | Pool size |
| --- | ---: | ---: |
| pg-orders | 500 | 40 |
| pg-billing | 300 | 25 |
| pg-analytics | 200 | 10 |

## Diagnose and contain

Run `SELECT application_name, usename, state, count(*) FROM pg_stat_activity GROUP BY 1,2,3 ORDER BY 4 DESC;`. Check deployment changes, retry loops, and pool fan-out. Query pgBouncer with `SHOW POOLS;` to distinguish waiting clients from backend exhaustion. The June Billing incident followed an application deployment that bypassed the pooler.

Identify sessions idle in transaction >10 min using `SELECT pid, application_name, now() - state_change AS idle_for FROM pg_stat_activity WHERE state = 'idle in transaction' AND state_change < now() - interval '10 minutes';`. Terminate those sessions with `SELECT pg_terminate_backend(<pid>);` after confirming their identity. This rolls back their open transactions; record the application owner and expected retry behavior.

## Recovery

Never raise max_connections during an incident: it needs a restart + CAB approval. Reduce excess client concurrency, restore pooler routing, or roll back the offending release. Check queue depth &amp; successful requests after containment. Confirm fresh application sessions use port 6432 and retain enough administrative capacity to investigate recurrence.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
