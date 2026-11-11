---
title: November 2025 Analytics Transaction Age Incident
doc_type: postmortem
owner: Data Platform
last_reviewed: 2026-08-29
status: current
---
# November 2025 Analytics Transaction Age Incident

## Incident summary

During November 2025, pg-analytics database transaction age reached 1.9 billion. Aggressive vacuum took 6 hours to bring the oldest relations back under control. The response consumed substantial I/O capacity and delayed scheduled reporting. The cluster was running PostgreSQL 15; its upgrade to PostgreSQL 16 remains planned for Q1 2027. A version upgrade alone would not correct the maintenance and monitoring gaps found here.

## Detection and response

The responder inspected `SELECT datname, age(datfrozenxid) FROM pg_database ORDER BY age(datfrozenxid) DESC;` after maintenance logs showed increasingly urgent anti-wraparound activity. Table-level ages revealed that several large relations were not advancing their frozen transaction horizons. Long report transactions and sustained storage pressure reduced effective maintenance progress.

Data Platform coordinated report cancellations and paused additional heavy jobs. DBA Operations ran `VACUUM (FREEZE, VERBOSE);` in the affected database while tracking `pg_stat_progress_vacuum` and relation ages. The six-hour period covered aggressive vacuum work; subsequent workload checks continued before deferred reports resumed. VACUUM FULL was not used as an incident shortcut.

## Findings and follow-up

Existing dashboards focused on storage usage and query duration, leaving transaction age without an actionable early warning. Maintenance completion was inferred from process activity instead of measured against the oldest database and relation ages.

This incident led to PgXidWraparoundRisk thresholds of 1.2B warning and 1.6B critical. Data Platform now reviews long report transactions and vacuum progress together. The runbook directs responders to remove blockers, monitor actual age reduction, and separate bloat remediation from wraparound recovery. Follow-up review confirmed alert delivery and dashboard coverage for every database on pg-analytics.

<!-- exported by confluence-export v2.3 -->

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
