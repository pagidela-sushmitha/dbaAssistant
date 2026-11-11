---
title: PostgreSQL Disk Full and WAL Growth
doc_type: runbook
owner: DBA Operations
last_reviewed: 2026-09-18
status: current
---
# PostgreSQL Disk Full and WAL Growth

## Trigger

PgDiskUsageHigh uses 80% warn / 90% critical thresholds. Check the database volume, WAL volume, growth rate, and remaining time to exhaustion in Grafana. Usage &gt;90% requires immediate assessment. Treat write failures as an incident even if the percentage alert has not fired. Preserve timestamps and affected mount points in ServiceNow.

## Inspect retained WAL

NEVER delete files from pg_wal. Removing WAL can break recovery and replication. Run `SELECT slot_name, slot_type, active, restart_lsn FROM pg_replication_slots;` and investigate inactive slots. Compare `SELECT pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) FROM pg_replication_slots;` with filesystem growth. The configured guardrail is `max_slot_wal_keep_size = 200GB`; it limits slot retention at checkpoints and is not a substitute for capacity monitoring.

Dropping a slot needs slot owner approval or on-call DBA lead approval under an emergency change. Identify the consumer and document its rebuild plan first. An invalidated or dropped logical slot can require a new downstream snapshot. The March Orders outage involved the inactive Debezium slot `debezium_orders`.

## Add capacity and verify

Use `nwctl volume grow --cluster X --size +100G`, replacing X with the affected cluster. One grow per 24h is a standard change; more needs Director of Infrastructure approval. Confirm filesystem capacity increases and writes recover. Review capacity &amp; consumer health together, rather than assuming added space fixed the underlying retention problem. Track inactive slots, checkpoint progress, and free space until stable, then assign the consumer owner a follow-up action with a due date.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
