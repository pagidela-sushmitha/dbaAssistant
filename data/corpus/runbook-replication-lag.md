---
title: PostgreSQL Replication Lag
doc_type: runbook
owner: DBA Operations
last_reviewed: 2026-09-15
status: current
---
# PostgreSQL Replication Lag

## Trigger and impact

PgReplicationLagHigh warns when replay lag is >30s for 5 min and becomes critical at >300s. Check Grafana PG Overview to distinguish one delayed replica from a cluster-wide problem. Orders and Billing applications depend on replicas for reads; stale results can affect customer workflows even when writes succeed. Record the first threshold crossing in the incident ticket.

## Diagnose

On the primary, run `SELECT application_name, client_addr, state, sent_lsn, replay_lsn, replay_lag FROM pg_stat_replication;`. Compare both time lag and WAL distance. An idle primary can make timestamp-based lag misleading, so confirm that new transactions are actually failing to replay. Check replica CPU, disk latency, network errors, and long-running queries before choosing a remedy.

On the affected replica, inspect `SELECT pid, now() - query_start AS runtime, query FROM pg_stat_activity WHERE state = 'active' ORDER BY query_start;`. A report holding an old snapshot can delay recovery. Contact its owner and cancel the replica query with `SELECT pg_cancel_backend(<pid>);`. Cancellation interrupts the statement while preserving the session.

## Contain and recover

If lag stays >300s for 15+ min, drain the replica with `nwctl pool drain <host>`. Confirm read traffic has moved to healthy capacity. Lag lasting >30 min on pg-orders/pg-billing is Sev2; page DBA-Primary through PagerDuty. Review replication &amp; application metrics together before restoring traffic. Capture the cause, cancellation decisions, and a sustained return below the warning threshold in ServiceNow. Do not drain the only usable reader without coordinating application capacity.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
