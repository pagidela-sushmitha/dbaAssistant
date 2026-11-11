---
title: Manual PostgreSQL Failover v1 — Deprecated
doc_type: runbook
owner: DBA Operations
last_reviewed: 2023-02-11
status: deprecated
---
# Manual PostgreSQL Failover v1 — Deprecated

## Historical scope

This archived v1 procedure describes the former manual failover process and an RTO of 5 minutes. It is retained for historical incident interpretation. It conflicts with the current Patroni Failover v3 runbook, which supersedes it. Do not execute these steps on the current Patroni + Consul estate. Use the current runbook for operational decisions and current recovery objectives.

## Former readiness checks

The old process required the responder to establish that the former primary was stopped and fenced from application traffic. The responder compared replay positions, selected the most advanced surviving standby, and recorded the potential data-loss interval. Application owners were told to pause writes while the DBA confirmed that a second writer could not remain reachable.

## Archived promotion procedure

Under the former procedure, the responder connected to the selected standby through the approved production access path and ran `pg_ctl promote -D /var/lib/postgresql/data`. The responder then checked `SELECT pg_is_in_recovery();`, expecting false, and manually changed the writer endpoint. The old instructions called for a small application write test and a connection reset before reopening traffic.

## Historical completion criteria

Operators recorded the selected host, last replay position, promotion time, and endpoint update. The former primary stayed isolated until it could be rebuilt as a standby; it was never simply restarted as a second writer. These notes explain older incident records, not an exception to current controls. Current operators must use Patroni-managed leadership, the current 60-second RTO target, and the current change and escalation policies.

<!-- exported by confluence-export v2.3 -->

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
