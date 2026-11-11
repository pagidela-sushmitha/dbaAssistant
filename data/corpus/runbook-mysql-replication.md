---
title: Legacy CRM MySQL Replication Recovery
doc_type: runbook
owner: CRM Platform
last_reviewed: 2026-09-04
status: current
---
# Legacy CRM MySQL Replication Recovery

## Scope and severity

mysql-crm runs MySQL 8.0 and is scheduled for decommission in Q2 2027. Replication failures involving Error 1062 or Error 1032 are Sev3 under this procedure. Capture business impact in the ticket and reassess severity if the failure also causes a broader production outage. The PostgreSQL Patroni commands do not apply to this system.

## Identify divergence

Run `SHOW REPLICA STATUS\G` on the affected replica. Capture the last SQL error, source coordinates or GTID details, affected table, and replication thread state. Error 1062 indicates a duplicate entry; Error 1032 generally means the row needed by a replication event cannot be found. Check for writes made directly on the replica and compare the timeline with CRM imports or maintenance.

Do not blindly use `sql_replica_skip_counter`. Skipping an event can hide divergence and leave dependent records inconsistent. Preserve the error evidence and involve the CRM data owner before selecting a repair approach. Avoid copying customer values into a general incident channel.

## Repair and validate

Use pt-table-checksum with the DBA-approved configuration to identify inconsistent tables, observing load and replication behavior throughout. Review checksum differences before considering targeted repair. For widespread or unexplained divergence, rebuild the replica with XtraBackup; allow approximately 2h for the rebuild, plus validation time. Obtain the applicable change approvals and confirm a valid source backup before replacing replica data.

After recovery, verify replication threads, lag, checksums, and a CRM read workflow. Record the cause and repair evidence. Keep the decommission plan visible so incident remediation remains aligned with the remaining service lifetime.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
