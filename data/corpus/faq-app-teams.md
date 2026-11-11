---
title: Database FAQ for Application Teams
doc_type: faq
owner: DBA Operations
last_reviewed: 2026-09-25
status: current
---
# Database FAQ for Application Teams

## How do we request a database?

Submit ServiceNow "Database Request" with the owning team, expected size, workload, classification, and availability needs. Allow 5 business days for a complete request. The DBA reviewer confirms cluster placement, backup expectations, and connection settings before provisioning. This request does not automatically grant every developer production access. All application connections must use pgBouncer on port 6432.

## Can developers read a replica?

Request `db-replica-ro` through ServiceNow with manager approval; fulfillment takes 2 business days. All access is via Teleport. Contractors get no direct prod access. Replica access remains subject to data-classification controls, including the prohibition on unmasked Restricted data in non-production. Use the appropriate replica endpoint and avoid reports that delay replay.

## Can we run our own migrations?

Yes, after dba-review and the applicable change approvals, use Flyway in CI. Label the PR dba-review and allow 2 business days for review. Set `lock_timeout = '5s';`, provide an impact and recovery plan, and index every FK. Concurrent index builds need a migration configured to run outside a transaction block. Check freezes before deployment.

## Why did a query stop after fifteen minutes?

Application roles have `statement_timeout = '15min'`, returning 57014 query_canceled when exceeded. analytics_ro is exempt, but that exemption does not approve heavy primary reporting. Review the long-running and slow-query runbooks with the query owner before requesting a role or workload change.

## Who should we contact?

Use #dba-help for non-urgent design and access questions. Page PagerDuty DBA-Primary for production incidents and coordinate in #dba-oncall. Include the cluster, SQLSTATE, deployment context, and impact without customer values. Service requests still require their ServiceNow record.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
