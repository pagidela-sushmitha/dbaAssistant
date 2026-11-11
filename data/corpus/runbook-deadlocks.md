---
title: PostgreSQL Deadlock Handling
doc_type: runbook
owner: DBA Operations
last_reviewed: 2026-09-10
status: current
---
# PostgreSQL Deadlock Handling

## Recognize the failure

SQLSTATE 40P01 means PostgreSQL detected a deadlock and aborted one participating transaction. Northwind Data uses `deadlock_timeout = '1s'` and `log_lock_waits = on`. The timeout controls when PostgreSQL checks for deadlocks; it does not guarantee that every lock wait ends after one second. Applications must handle the aborted transaction explicitly.

## Collect evidence

Search database logs for the deadlock detail and capture both statements, transaction identifiers, application names, and timestamps. Inspect current activity with `SELECT pid, application_name, wait_event_type, wait_event, pg_blocking_pids(pid) FROM pg_stat_activity WHERE wait_event_type = 'Lock';`. The original cycle may already be gone because PostgreSQL selected a victim. Correlate repeated cases with the deployment timeline and application traces, keeping Restricted values out of tickets.

## Resolve and route

The durable fix is consistent lock ordering + retries. For example, code updating two order rows should acquire them in the same identifier order in every transaction. Retry the whole transaction after rollback using bounded attempts and jitter, and ensure externally visible side effects are idempotent. Retrying only the failed statement inside an aborted transaction will not recover it.

Deadlocks are not a DBA page unless >50 deadlocks/min. Below that threshold, send the evidence to the owning application team and use #dba-help for consultation. At rates &gt;50/min, page DBA-Primary and correlate errors &amp; throughput to establish impact. After a fix, verify the deadlock rate falls and retries do not create additional load. Record the affected code path and its owner before closing the investigation.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
