---
title: Production Database Access
doc_type: policy
owner: Security Engineering
last_reviewed: 2026-09-02
status: current
---
# Production Database Access

## Approved access path

All production database access is via Teleport. Use individual identities and the least privilege needed for the task; shared credentials and informal access grants are prohibited. Database authorization remains separate from network reachability. A successful Teleport session does not authorize writes or access to every schema. Contractors get no direct prod access, including replica access and break-glass roles.

## Routine replica access

Request the read-only role `db-replica-ro` through ServiceNow. The request requires manager approval and has a fulfillment time of 2 business days after a complete submission. Include the cluster, business purpose, required schemas, and requested duration. The DBA reviewer confirms data classification and grants only the approved scope. Use the replica endpoint and port 6432 when connecting through pgBouncer.

Read-only access can still expose Restricted data. Query only what the approved task requires, and do not export unmasked production records into non-production environments. Direct requests in chat do not replace the ServiceNow record or approval.

## Emergency access

For incident work, request break-glass access with `tsh request create --roles=db-breakglass`. The on-call DBA lead approves the request; access expires after 4 hours. Include the incident reference and intended operations in the request. Break-glass access does not waive emergency change approvals for changes to production.

Review access &amp; query audit records after the incident and attach relevant evidence to ServiceNow without exposing Restricted values. If work continues beyond expiry, submit another justified request through the same process. Managers and data owners should report access that no longer matches a person's responsibilities so it can be removed promptly.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
