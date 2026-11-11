---
title: Patroni Failover v3
doc_type: runbook
owner: DBA Operations
last_reviewed: 2026-08-25
status: current
---
# Patroni Failover v3

## Authority and behavior

This is the current v3 procedure for PostgreSQL clusters managed by Patroni + Consul. Automatic failover has an RTO target of 60 seconds. The target measures service recovery, including writer routing and application reconnection; it is an objective, not a guarantee for every failure. The deprecated v1 document is historical and must not guide current incident actions.

## Unplanned failover

Check `patronictl list` and Grafana PG Overview to establish the leader, replica health, and timeline. Confirm Consul quorum and Patroni health before intervening. Watch automatic leader election and pooler routing, then verify successful application writes. Never run `pg_ctl promote` manually. Bypassing Patroni can create conflicting leadership and undermine fencing assumptions.

If automatic recovery stalls, page DBA-Primary and preserve Patroni logs, Consul observations, and application errors. Avoid repeated leadership changes while diagnosing connectivity. Coordinate any emergency intervention with the on-call DBA lead and engineering manager under the emergency change process.

## Planned switchover

A planned switchover is a standard change in the Tue/Thu 22:00-23:00 ET window, subject to change freezes. Open a standard change record, verify backups and replica replay, notify the application owner, and use `patronictl switchover` to select a healthy candidate. Confirm the resulting topology with `patronictl list`.

Validate reader &amp; writer routing, pooler reconnections, and application error rates after the transition. Record actual recovery time and any abandoned connections. If readiness checks fail, postpone the operation and document the reason rather than forcing a leadership change.

<!-- exported by confluence-export v2.3 -->

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
