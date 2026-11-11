---
title: Vacuum and Transaction ID Wraparound
doc_type: runbook
owner: DBA Operations
last_reviewed: 2026-08-28
status: current
---
# Vacuum and Transaction ID Wraparound

## Alert thresholds

PgXidWraparoundRisk warns when `age(datfrozenxid) >1.2B` and becomes critical at `>1.6B`. Evaluate every database on the cluster with `SELECT datname, age(datfrozenxid) FROM pg_database ORDER BY age(datfrozenxid) DESC;`. A low average across databases does not make the oldest database safe. The November 2025 analytics incident reached 1.9 billion and required six hours of aggressive vacuum.

## Diagnose stalled maintenance

Connect to the affected database and inspect `SELECT relname, age(relfrozenxid) FROM pg_class WHERE relkind = 'r' ORDER BY age(relfrozenxid) DESC LIMIT 20;`. Review autovacuum logs, long transactions, replication slots, and I/O saturation. Use `SELECT * FROM pg_stat_progress_vacuum;` to distinguish slow progress from a blocked operation. Coordinate cancellation of obstructing queries through the long-running query procedure.

## Recover and prevent recurrence

Run `VACUUM (FREEZE, VERBOSE);` in the affected database after checking available capacity and coordinating incident work. Track database and relation ages as well as vacuum progress; completion on one table does not prove the entire database is safe. Keep the incident open until the oldest ages are falling and normal maintenance can continue.

No VACUUM FULL in business hours. It rewrites tables and takes an exclusive lock, making it unsuitable for routine incident relief. Use pg_repack for >40% bloat through a normal change with CAB review. Bloat &amp; transaction age are separate measurements: reclaiming space alone does not establish wraparound safety. Assign follow-up ownership for autovacuum tuning and workload changes based on the evidence collected.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
