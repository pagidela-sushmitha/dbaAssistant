---
title: Long-Running Query Response
doc_type: runbook
owner: DBA Operations
last_reviewed: 2026-09-14
status: current
---
# Long-Running Query Response

## Scope and trigger

Application roles have `statement_timeout = '15min'`; timed-out statements return SQLSTATE 57014, query_canceled. The `analytics_ro` role is exempt from this application timeout because approved reports may run longer. Exemption does not authorize unlimited resource use or disruptive reporting on a primary. Alert at 30 min on a primary and investigate the owner, purpose, and current impact.

## Inspect the session

Use `SELECT pid, usename, application_name, now() - query_start AS runtime, wait_event_type, wait_event, query FROM pg_stat_activity WHERE state = 'active' AND query_start < now() - interval '30 minutes';`. Check blockers with `SELECT pg_blocking_pids(<pid>);`. Determine whether the statement is making progress, waiting on a lock, or consuming resources needed by production traffic. Avoid pasting query literals containing customer data into incident notes.

## Cancel before terminate

Cancel before terminate: issue `SELECT pg_cancel_backend(<pid>);`, then check whether the statement stopped and the transaction released its locks. A cancelled statement can leave a client in an aborted transaction until rollback. If cancellation does not resolve the impact, notify the app owner before `SELECT pg_terminate_backend(<pid>);` unless an outage requires immediate action. Termination disconnects the client and rolls back its transaction.

Record the notification, reason, and result. Review query plans on a replica using the slow-query triage runbook, then work with the application team on indexing, query shape, or batch size. Validate response time &amp; resource recovery before closing the alert, and verify that connection retries have not created a second problem.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
