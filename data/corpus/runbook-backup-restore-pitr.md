---
title: PostgreSQL Backup Restore and PITR
doc_type: runbook
owner: DBA Operations
last_reviewed: 2026-09-21
status: current
---
# PostgreSQL Backup Restore and PITR

## Backup schedule and intake

pgBackRest stores backups in S3: full Sunday 02:00 UTC, differential daily, continuous WAL. Review `pgbackrest --stanza=pg-orders info` for the affected stanza before choosing a recovery point. Standard production PITR retention is 35 days; pg-analytics has 14 days. Monthly fulls are retained for 13 months, but an older full does not imply continuous PITR coverage back to its date.

Non-incident restores require ServiceNow and have an SLA of 1 business day. Record the cluster, database, requested timestamp with timezone, requesting owner, and reason. During an incident, preserve the incident identifier and obtain emergency approvals where required.

## Restore safely

Never restore onto a running primary. Use `restore-01.db.nw.internal`, with an isolated data directory and application routing disabled. Confirm sufficient space and matching PostgreSQL major version before starting. For example, on the restore host run `pgbackrest --stanza=pg-orders --pg1-path=/srv/restore/pg-orders --type=time --target='2026-09-20 14:30:00+00' --target-action=promote restore`. Substitute the approved stanza, path, and timestamp. The restore command prepares files; start the isolated instance separately after reviewing recovery settings.

## Validate and release

Plan approximately 45 min per 500 GB, then allow additional time for WAL replay and validation. Verify recovery logs, expected tables, and owner-approved business checks before making data available. Compare backup &amp; recovery timestamps in UTC. Restored production data cannot go to non-production unless masked with nw-mask. Record actual restore duration, selected backup, recovered timestamp, and disposition of the isolated instance in the ticket.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
