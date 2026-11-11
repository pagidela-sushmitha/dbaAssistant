---
title: March 2026 Orders WAL Disk Outage
doc_type: postmortem
owner: Orders Team
last_reviewed: 2026-09-11
status: current
---
# March 2026 Orders WAL Disk Outage

## Incident summary

On 2026-03-14, pg-orders experienced a Sev1 outage lasting 42 minutes. The database volume filled with WAL retained by the inactive Debezium slot `debezium_orders`. Orders writes failed and application retries increased load. The primary remained the authoritative writer; a failover would not have removed the retention condition or provided a durable correction.

## Timeline and recovery

At 09:12 UTC, write errors and disk alerts triggered the incident. The responder confirmed free-space exhaustion and inspected `SELECT slot_name, active, restart_lsn FROM pg_replication_slots;`. By 09:22 UTC, the inactive consumer was identified as the source of retained WAL. The Debezium owner confirmed that the downstream pipeline was stopped and accepted a consumer rebuild.

The team recorded emergency approvals, grew the volume once using the approved procedure, and removed the obsolete slot after owner approval. No files were manually deleted from pg_wal. WAL recycling and restored headroom allowed writes to resume; application validation completed at 09:54 UTC, ending the 42-minute outage.

## Contributing factors

Disk percentage alerts did not explain why WAL was growing. Consumer shutdown ownership was unclear, and the inactive slot remained after the pipeline stopped. Retry traffic prolonged the recovery checks after capacity became available.

## Actions and verification

DBA Operations added PgReplicationSlotInactive alerting for slots inactive >1h and set `max_slot_wal_keep_size = 200GB`. Consumer owners must track slot lifecycle and document rebuild procedures. The disk runbook now emphasizes approval before dropping slots and the prohibition on deleting WAL files. Follow-up review verified the alert route, retention setting, and consumer ownership record. Capacity &amp; slot health are reviewed together during incident handoff.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
