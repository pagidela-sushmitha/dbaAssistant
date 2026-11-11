---
title: Production Database Cluster Inventory
doc_type: reference
owner: DBA Operations
last_reviewed: 2026-09-24
status: current
---
# Production Database Cluster Inventory

## Inventory

Sizes are planning snapshots of database data, not guarantees of provisioned free space or backup transfer size. PostgreSQL node counts include the primary. The accountable data owner is a business role within the owner team; DBA Operations maintains the database service and routes data-use decisions to that role.

| Cluster | Version | Nodes | Size | Owner team | Data owner |
| --- | --- | --- | --- | --- | --- |
| pg-orders | PostgreSQL 16 | 3 | 2.1 TB | Orders team | Orders Product Owner |
| pg-billing | PostgreSQL 16 | 3 | 800 GB | Billing team | Billing Product Owner |
| pg-analytics | PostgreSQL 15 | 2 | 6 TB | Data Platform | Data Platform Analytics Owner |
| mysql-crm | MySQL 8.0 | Not recorded here | Not recorded here | CRM Platform | CRM Product Owner |

## Shared PostgreSQL services

PostgreSQL clusters use Patroni + Consul for leadership and pgBouncer 1.23 on port 6432 for application connections. pgBackRest writes backups to S3. Access is through Teleport, production pages through PagerDuty DBA-Primary, telemetry through Grafana PG Overview, change records through ServiceNow, and schema delivery through Flyway in CI.

To confirm a PostgreSQL server version, run `SHOW server_version;` through the approved connection path. Use `patronictl list` for live topology rather than treating this inventory as a health check. Pool defaults and max_connections are documented in the connection-exhaustion runbook.

## Lifecycle and ownership

pg-analytics has an upgrade to 16 planned Q1 2027. Legacy mysql-crm is scheduled for decommission Q2 2027 and uses its separate MySQL replication runbook. Confirm implementation dates in approved change records before scheduling dependent work. Request data access and new databases through ServiceNow; ownership listed here does not confer access approval by itself.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
