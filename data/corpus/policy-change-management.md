---
title: Database Change Management
doc_type: policy
owner: Infrastructure Governance
last_reviewed: 2026-09-01
status: current
---
# Database Change Management

## Standard changes

Standard changes use preapproved procedures and a ServiceNow record with scope, validation, and rollback details. The standard list includes `CREATE INDEX CONCURRENTLY`, one volume grow per cluster per 24h using `nwctl volume grow --cluster X --size +100G`, and planned Patroni switchovers in the Tue/Thu 22:00-23:00 ET window. A second volume grow within 24h needs Director of Infrastructure approval. A standard classification does not override a freeze or a failed readiness check.

## Normal changes

Normal changes need CAB approval. CAB meets Tue & Thu 10:00 ET. Submit an implementation plan, impact assessment, owner communication, validation criteria, and rollback approach before review. Examples include pg_repack for >40% bloat, changes to max_connections that require a restart, and planned work outside a preapproved procedure. Application schema work also requires the Flyway and dba-review controls in the schema standard.

## Emergency changes

Emergency changes need on-call DBA lead + engineering manager approval. Record approvals in the incident timeline before implementation, and create or complete the retro ticket within 24h. Identify the responder, exact action, affected cluster, and expected customer impact. Emergency classification is for restoring or protecting service, not avoiding scheduled review. Extra volume growth still requires Director of Infrastructure approval.

## Freeze calendar

The change freeze covers the last 2 weeks of December and the last 3 business days of each quarter. Defer planned production changes during these periods. An urgent service-protection change follows emergency approvals with an explicit freeze exception recorded in ServiceNow. Verify the calendar in ET when scheduling work, and document the observed outcome before closure.

<!-- exported by confluence-export v2.3 -->

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
