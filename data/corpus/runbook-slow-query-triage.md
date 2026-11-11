---
title: PostgreSQL Slow Query Triage
doc_type: runbook
owner: DBA Operations
last_reviewed: 2026-09-17
status: current
---
# PostgreSQL Slow Query Triage

## Find the workload

Start with application latency and Grafana PG Overview for the affected cluster. Identify whether the change follows a deployment, data growth, or resource contention. Use pg_stat_statements to rank normalized statements: `SELECT queryid, calls, total_exec_time, mean_exec_time, rows FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 20;`. Record the observation interval because cumulative totals alone can make an old expensive query look like the current cause.

## Inspect execution

Run `EXPLAIN (ANALYZE, BUFFERS)` on a replica only. ANALYZE executes the statement, so first review its behavior and limit testing to suitable read queries. Use a representative parameter set that does not expose Restricted values in the ticket. Compare estimated versus actual rows, scan choices, sort spills, and buffer reads. Confirm the replica has representative data and is healthy enough to accept diagnostic load.

For production-primary diagnosis, use existing telemetry and a plan without ANALYZE. Review locks and long transactions with the relevant runbooks before attributing every latency increase to a missing index.

## Remediate and verify

`CREATE INDEX CONCURRENTLY` is a standard change, subject to a recorded change, readiness checks, and freezes. For example, `CREATE INDEX CONCURRENTLY orders_created_at_idx ON orders (created_at);` must be adapted to the actual schema and access pattern. It cannot run inside a transaction block. Coordinate schema changes through Flyway and dba-review.

Compare latency &amp; resource use after the change and check for invalid indexes if a concurrent build fails. Document the query identifier, chosen intervention, measured result, and application owner responsible for any follow-up query rewrite.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
