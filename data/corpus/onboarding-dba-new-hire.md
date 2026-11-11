---
title: DBA New Hire First Week
doc_type: onboarding
owner: DBA Operations
last_reviewed: 2026-09-28
status: current
---
# DBA New Hire First Week

## First-week checklist

- Confirm your manager has requested approved Teleport access and the database roles needed for training. Use individual identities and review the production-access policy before connecting.
- Configure PagerDuty and locate the DBA-Primary service, current primary, and secondary. Join #dba-oncall for coordination and #dba-help for non-urgent questions.
- Open Grafana "PG Overview" and identify replication, connections, disk, and transaction-age panels for each PostgreSQL cluster.
- Find ServiceNow change templates and the Flyway CI workflow. Review an approved dba-review PR with your mentor.
- Read the inventory and distinguish current Patroni Failover v3 from the deprecated manual v1 procedure.

## Guided operational practice

With a mentor, connect through Teleport and inspect `SELECT version();` and `SELECT pg_is_in_recovery();` on an approved endpoint. Observe `patronictl list` and pgBouncer `SHOW POOLS;` without changing production state. Explain how per database/user pool sizes relate to backend connection limits.

Review pgBackRest backup status and walk through an isolated restore plan for `restore-01.db.nw.internal`. Identify the 35-day production PITR window, the 14-day pg-analytics exception, and the masking requirement before any non-production copy. Read the three postmortems and locate the runbook changes they produced.

## On-call readiness

Shadow 2 full rotations before primary on-call. Attend Monday 10:00 ET handoffs and practice a written timeline using a historical incident. Demonstrate the difference between cancellation and termination, emergency access and emergency change approval, and an alert acknowledgement and recovery.

Your mentor records completed exercises and remaining access gaps. Review escalation timing with DBA manager Priya Raman before joining the primary rotation. Training never authorizes unsupervised production changes outside the normal controls.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
